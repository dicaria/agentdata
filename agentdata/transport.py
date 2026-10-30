"""agentdata.transport — the upstream-call core: token bucket + dual channel (urllib / curl subprocess) + retries + cache weaving.

Python counterpart of the Node-side baseline transport (api.md section 9.5 is the single authority:
the Phase 2 Python implementation is the complete, authoritative local implementation; the bar to clear
is capability/error/cache vectors + real transport verification).

- Transport channel: urllib by default; a provider/op declaring transport='curl' goes through a system
  curl subprocess — the countermeasure against WAF bot gates (the GUDID lesson: gating holds on both
  the client stack and the egress IP, and curl only passes from this machine's egress; a 2xx non-JSON
  response is normalized into an error carrying an egress-troubleshooting hint — verify the egress
  first, only then consider pinning transport='curl').
- Three normalized error codes: upstream_unavailable / upstream_rate_limited (empty bucket or upstream
  429/503) / upstream_not_found (notFound declaration).
- Retries: 2 by default, exponential backoff + honouring Retry-After; only for retryable statuses
  (408/429/500/502/503/504).
- POST read semantics (filled in by the company wave, aligned with the Node core's three small
  extensions): when an op declares method='POST', non-path-template parameters go into the JSON body,
  not the query string; it must also declare idempotent=True to take part in retries; the curl
  subprocess channel has no JSON-body parameter surface, so POST+curl is intercepted ahead of
  call_provider as a usage_error.
- form channel (filled in by the esg/legal wave, aligned with the Node core's fourth extension): when an
  op declares form='<field name>', the POST body is a single-field multipart whose value is the JSON blob
  of params[form] (same as the browser FormData.append(field, Blob): filename="blob" +
  Content-Type: application/json); control parameters (apiKey/pageNumber and the like) go into the query
  string. First used by dgcomp (webgate ES). The curl channel has no multipart surface, so the
  POST+curl interception stands.
"""
import json
import math
import os
import random
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

UA = "agentdata/0.2.0"  # compatibility constant; at runtime _ua() computes it fresh (an AGENTDATA_CONTACT env var set later still takes effect)
RETRYABLE = {408, 429, 500, 502, 503, 504}
MAX_BACKOFF = 30.0


def resolve_execution(requested=None) -> str:
    from .errors import SdkError  # function-level import (this module's cycle-avoidance style)

    x = requested or "auto"
    if x not in ("local", "hosted", "auto"):
        raise SdkError("usage_error", detail=f"execution must be local|hosted|auto, got '{x}'")
    if x == "hosted":
        raise SdkError("capability_unavailable",
                       detail="Realtime queries support local execution only (direct connection to the upstream official public API, no credentials needed)")
    return "local"


def enrich_source(provider_id: str, execution: str, *metas) -> dict:
    metas = [m for m in metas if m]
    from_cache = bool(metas) and all(m.get("from_cache") for m in metas)
    last = metas[-1]
    if from_cache:
        return {"provider": provider_id, "execution": execution, "from_cache": True, "fetched_at": last["fetched_at"]}
    return {"provider": provider_id, "execution": execution, "from_cache": False, "observed_at": last["fetched_at"]}


# RxNav tty (concept level) -> reason label: BN=brand name / IN=ingredient (the level decides whether ATC has a value)
_TTY_LABELS = {"BN": "brand-name level", "IN": "ingredient level"}


def _tty_tag(tty) -> str:
    if not tty:
        return ""
    return f" ({_TTY_LABELS.get(tty, tty)})"

def _ua() -> str:
    """Polite UA: agentdata/<version> (+<contact>) — the contact comes from env AGENTDATA_CONTACT (e.g. mailto:)."""
    try:
        from . import __version__ as _v
    except ImportError:  # mid package init (transport imported early by providers) — fall back to a hardcoded version
        _v = "0.2.0"
    contact = os.environ.get("AGENTDATA_CONTACT")
    return f"agentdata/{_v} (+{contact})" if contact else f"agentdata/{_v}"


# 0.2.0 anti-ban rate-limiting six-pack (independent of the command surface):
# (1) 429/Retry-After aware exponential backoff + jitter (capped at 30s); (2) no blind retry on 401/403
# (a WAF/permission gate is not rate limiting; retrying hurts yourself);
# (3) sliding-window circuit breaker (3 consecutive fails or 5 fails in a 60s window -> 60s cooldown ->
# half-open with 1 probe -> a repeat fail extends to 5min; not_found = a clean round trip, not a fail);
# (4) provider+host two-layer token bucket (host default 5rps/burst10, provider["hostRate"] overrides)
#   + (4b) family group bucket (a provider["rate"]["group"] name -> a GROUP_LIMITS group quota shared by
#   multiple sources of the same official family — NLM was the first case in 0.2.8);
# (5) host concurrency cap (default 2, provider["concurrency"] overrides — fragile government sources pin 1);
# (6) polite UA agentdata/<ver> (+contact).
# State is in-process (not shared across processes; persisting severe cooldowns is a separate project).


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class TokenBucket:
    """Per-provider token bucket: capacity=burst, refill rate=rps; waits when empty (30s cap -> upstream_rate_limited)."""

    def __init__(self, rps: float, burst: int):
        self.rps, self.burst = rps, burst
        self.tokens, self.last = float(burst), time.monotonic()

    def take(self):
        deadline = time.monotonic() + 30
        while True:
            now = time.monotonic()
            self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rps)
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
            if now > deadline:
                raise TimeoutError("local token bucket wait exceeded")
            time.sleep(max(0.05, (1 - self.tokens) / self.rps / 2))


_buckets = {}
_host_buckets = {}   # (4) host-layer token bucket: hostname -> TokenBucket (multiple providers on one host share the polite quota)
_group_buckets = {}  # (4b) family group bucket: rate.group name -> TokenBucket (multiple providers of one official family share the official quota)
_host_slots = {}     # (5) host concurrency cap: hostname -> Semaphore
_state_lock = threading.Lock()

# Family group quota registry (0.2.8): key = the rate.group a provider declares; quota = a conservative
# window for the official family policy (quota semantics b + r x 1s <= the official limit). First case nlm:
# RxNav ToS 20/s per IP (top tier), group bucket 10+10=20 right at the line.
GROUP_LIMITS = {
    "nlm": {"rps": 10.0, "burst": 10},  # NLM family (shared by rxnav/dailymed/mesh; gudid has no official number, not in the group)
}


def _take_token(provider):
    rps = provider["rate"]["rps"]
    burst = provider["rate"].get("burst", max(2, int(rps * 2)))
    b = _buckets.get(provider["id"])
    if b is None:
        b = _buckets[provider["id"]] = TokenBucket(rps, burst)
    try:
        b.take()
    except TimeoutError as e:  # an empty-bucket wait timing out is the local polite tier protecting itself, not an upstream error
        from .errors import SdkError
        raise SdkError("rate_limited", provider=provider["id"],
                       detail=f"Local token bucket wait exceeded (polite tier {rps} rps): {e}")


def _take_group_token(provider):
    """(4b) family group bucket: when a provider declares rate.group, all providers in the group share the
    GROUP_LIMITS group quota — after a speed-up this prevents "each source compliant, the family stacked
    over the limit" (the NLM 20/s official family-policy scenario). An unknown/unregistered group is a
    declaration error, intercepted on the spot."""
    group = provider["rate"].get("group")
    if not group:
        return
    gl = GROUP_LIMITS.get(group)
    if gl is None:
        from .errors import SdkError
        raise SdkError("usage_error", provider=provider["id"],
                       detail=f"rate.group '{group}' is not registered in transport.GROUP_LIMITS — register the group quota before enabling it")
    b = _group_buckets.get(group)
    if b is None:
        with _state_lock:
            b = _group_buckets.get(group) or TokenBucket(float(gl["rps"]), int(gl["burst"]))
            _group_buckets[group] = b
    try:
        b.take()
    except TimeoutError as e:
        from .errors import SdkError
        raise SdkError("rate_limited", provider=provider["id"],
                       detail=f"Family group '{group}' token bucket wait exceeded (shared group quota {gl['rps']} rps): {e}")


def _host_of(provider) -> str:
    return urlsplit(provider["baseUrl"]).hostname or provider["baseUrl"]


def _take_host_token(provider):
    """(4) host-layer bucket: defaults 5rps/burst10 (a mere second gate when the provider bucket is tighter); provider["hostRate"] overrides."""
    hr = provider.get("hostRate") or {"rps": 5.0, "burst": 10}
    host = _host_of(provider)
    b = _host_buckets.get(host)
    if b is None:
        with _state_lock:
            b = _host_buckets.get(host) or TokenBucket(float(hr["rps"]), int(hr["burst"]))
            _host_buckets[host] = b
    try:
        b.take()
    except TimeoutError as e:
        from .errors import SdkError
        raise SdkError("rate_limited", provider=provider["id"],
                       detail=f"Host-layer token bucket wait exceeded ({host} polite tier {hr['rps']} rps): {e}")


def _host_slot(host: str, limit: int):
    """(5) host concurrency semaphore: default 2 concurrent (provider["concurrency"] overrides); single-threaded callers always pass straight through."""
    sem = _host_slots.get(host)
    if sem is None:
        with _state_lock:
            sem = _host_slots.get(host) or threading.Semaphore(max(1, int(limit)))
            _host_slots[host] = sem
    return sem


def _backoff_wait(i: int, retry_after=None) -> float:
    """(1) Backoff: max(1x2^i, Retry-After) capped at 30s, plus 0~1s jitter (staggering prevents an avalanche)."""
    base = min(MAX_BACKOFF, float(1 << i))
    wait = max(base, float(retry_after or 0.0))
    return min(MAX_BACKOFF, wait) + random.uniform(0.0, 1.0)


class CircuitBreaker:
    """(3) Sliding-window circuit breaker (in-process): 3 consecutive fails or 5 fails in a 60s window -> open 60s
    -> half-open with 1 probe -> a repeat fail extends the open state to 5min, a success closes it."""

    def __init__(self):
        self.fails = []          # failure timestamps inside the 60s sliding window (monotonic)
        self.consec = 0          # consecutive failure count
        self.state = "closed"    # closed | open | half_open
        self.opened_at = 0.0
        self.open_for = 0.0

    def allow(self) -> float:
        """-> 0.0 = pass (including the first probe right after switching to half-open); >0 = N seconds of cooldown left (the request should be refused)."""
        if self.state == "open":
            elapsed = time.monotonic() - self.opened_at
            if elapsed >= self.open_for:
                self.state = "half_open"  # cooldown over: let one probe request through
                return 0.0
            return self.open_for - elapsed
        return 0.0

    def record(self, ok: bool):
        now = time.monotonic()
        self.fails = [t for t in self.fails if now - t <= 60.0]
        if ok:
            self.consec = 0
            self.state = "closed"
            return
        was_half = self.state == "half_open"
        self.consec += 1
        self.fails.append(now)
        if was_half or self.consec >= 3 or len(self.fails) >= 5:
            self.state = "open"
            self.opened_at = now
            self.open_for = 300.0 if was_half else 60.0


_breakers = {}


def _breaker(provider_id: str) -> CircuitBreaker:
    b = _breakers.get(provider_id)
    if b is None:
        with _state_lock:
            b = _breakers.get(provider_id) or CircuitBreaker()
            _breakers[provider_id] = b
    return b


def _reset_rate_state():
    """Test hook: clear the in-process state of the six-pack (buckets/semaphores/circuit breakers/group buckets)."""
    with _state_lock:
        _buckets.clear()
        _host_buckets.clear()
        _group_buckets.clear()
        _host_slots.clear()
        _breakers.clear()


def build_url(base: str, path_tmpl: str, params: dict, query: bool = True) -> str:
    """With query=False only the path template is substituted (POST read semantics: the remaining parameters go into the JSON body, not the query string)."""
    path = path_tmpl
    qs = {}
    for k, v in params.items():
        if v is None:
            continue
        token = "{%s}" % k
        if token in path:
            path = path.replace(token, urllib.parse.quote(str(v), safe=""))
        elif query:
            qs[k] = str(v)
    url = base.rstrip("/") + (path if path.startswith("/") else "/" + path)
    if qs:
        # when the path already carries a query string (the ukec shape with the full parameter set baked
        # into the path) append with & — a second "?" would turn the query and everything after it into
        # the value of the previous parameter (proven 2026-10-21: the UK EC name filter silently stopped
        # working and always returned the whole register)
        url += ("&" if "?" in path else "?") + urllib.parse.urlencode(qs)
    return url


def multipart_json_field(field: str, obj) -> tuple[bytes, str]:
    """Extension (4) form-channel body: single-field multipart whose field value is a JSON blob. -> (body, content_type)."""
    boundary = "----agentdataForm" + uuid.uuid4().hex
    payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    head = (f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="{field}"; filename="blob"\r\n'
            f'Content-Type: application/json\r\n\r\n').encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + payload + tail, f"multipart/form-data; boundary={boundary}"


def http_json(url: str, timeout: float, body: dict | None = None, multipart=None, urlencoded=None):
    """urllib channel -> {'ok', 'status', 'retry_after', 'json'} (a non-JSON body is left for the status code to judge).
    body not None -> POST JSON; multipart=(bytes, content_type) -> extension (4) form-channel POST;
    urlencoded=bytes -> extension (7) form-urlencoded channel POST (body = standard form encoding)
    (a read-semantics POST only takes part in call_provider retries when the op declares idempotent)."""
    headers = {"User-Agent": _ua(), "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif multipart is not None:
        data, ct = multipart
        headers["Content-Type"] = ct
    elif urlencoded is not None:
        data = urlencoded
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw, ra = resp.status, resp.read(), resp.headers.get("Retry-After")
    except urllib.error.HTTPError as e:  # 4xx/5xx land here (the body is still read)
        status, raw, ra = e.code, e.read(), e.headers.get("Retry-After")
        e.close()
    try:
        doc = json.loads(raw.decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError):
        doc = None
    ra = float(ra) if ra is not None else None
    # the full text is brought back: accept:'text' ops (HTML surfaces, e.g. TGA eBS Domino SearchView) pass through on this channel and the provider parses them itself
    return {"ok": 200 <= status < 300, "status": status, "retry_after": ra, "json": doc,
            "text": raw.decode("utf-8", "replace"),
            "body_head": raw[:160].decode("utf-8", "replace")}


def curl_json(url: str, timeout: float):
    """curl subprocess channel (the trailer line carries the status code and Retry-After — same as the Node curlJson)."""
    mark = "\n__META__"
    p = subprocess.run(
        ["curl", "-sS", "-m", str(math.ceil(timeout)),
         "-H", f"User-Agent: {_ua()}", "-H", "Accept: application/json",
         "-w", mark + "%{http_code}|%{retry_after}", url],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout + 10,
    )
    out = p.stdout
    i = out.rfind(mark)
    body = out if i == -1 else out[:i]
    head = "0|" if i == -1 else out[i + len(mark):]
    status_s, _, ra_s = head.partition("|")
    try:
        doc = json.loads(body)
    except ValueError:
        doc = None
    status = int(status_s or 0)
    return {"ok": 200 <= status < 300, "status": status,
            "retry_after": float(ra_s) if ra_s else None, "json": doc, "text": body,
            "body_head": body[:160]}


def _send(url: str, transport: str, timeout: float, body: dict | None = None, multipart=None, urlencoded=None):
    if body is not None:  # POST only via the urllib channel (call_provider already intercepts curl+POST)
        return http_json(url, timeout, body)
    if multipart is not None:  # extension (4) form channel (urllib only as well; curl+POST is intercepted)
        return http_json(url, timeout, multipart=multipart)
    if urlencoded is not None:  # extension (7) form-urlencoded channel (urllib only as well)
        return http_json(url, timeout, urlencoded=urlencoded)
    return curl_json(url, timeout) if transport == "curl" else http_json(url, timeout)


def cache_key_for(op: str, params: dict) -> str:
    """Cache key: exported so a provider can recompute it (dropping an empty-result entry must use the same key as inside call_provider — do not copy the format)."""
    return json.dumps([op] + sorted(params.items()), ensure_ascii=False)


def call_provider(provider, op: str, params=None, cache=None, no_cache: bool = False):
    """-> {'ok', 'data', 'from_cache', 'fetched_at', 'provider'}; a cache hit does zero network work; a pass-through is stored under the op TTL."""
    params = {k: v for k, v in (params or {}).items() if v is not None}
    opdef = provider["ops"].get(op)
    if opdef is None:
        from .errors import SdkError
        raise SdkError("op_unknown", provider=provider["id"], detail=f"Undeclared op: {op}")

    ttl = opdef.get("ttl", provider.get("ttl", {}).get(op))
    cache_key = cache_key_for(op, params)
    if not no_cache and cache is not None:
        hit = cache.get(provider["id"], cache_key, ttl)
        if hit:
            return {"ok": True, "data": hit["payload"], "from_cache": True,
                    "fetched_at": hit["fetched_at_iso"], "provider": provider["id"]}

    from .errors import SdkError

    # POST read semantics (aligned with the Node core's third small extension): for a method=POST op the
    # non-path parameters go into the JSON body; it takes part in retries only when idempotent=True is
    # declared (a read-semantics POST is naturally idempotent; only flush-style write POSTs are barred from retrying).
    # form channel (extension 4): when op.form='<field name>' is declared the body is a single-field
    # multipart (JSON blob) and control parameters go into the query string.
    # form-urlencoded channel (extension 7): when op.urlencoded=True is declared the body is standard form
    # encoding (interfaces that read parameters as a form, e.g. the EMSA portal REST — a JSON body is
    # silently dropped by the upstream, 200 with 0 rows for the whole window, measured on Paris MoU 2026-10-29).
    # The curl subprocess channel has no body-parameter surface (none of JSON/multipart/urlencoded) ->
    # intercepted directly as a usage error (aligned with Node: POST currently supports urllib only).
    is_post = opdef.get("method") == "POST"
    is_form = is_post and isinstance(opdef.get("form"), str)
    if is_post and opdef.get("transport", "urllib") == "curl":
        raise SdkError("usage_error", provider=provider["id"],
                       detail="POST read semantics currently support the urllib channel only (the curl subprocess has no JSON/multipart/urlencoded body-parameter surface)")
    multipart = None
    urlenc = None
    if is_form:
        url_params = {k: v for k, v in params.items() if k != opdef["form"]}
        url = build_url(provider["baseUrl"], opdef["path"], url_params, query=True)
        multipart = multipart_json_field(opdef["form"], params.get(opdef["form"]) or {})
        body = None
    else:
        url = build_url(provider["baseUrl"], opdef["path"], params, query=not is_post)
        if is_post and opdef.get("urlencoded") is True:
            body = None
            urlenc = urllib.parse.urlencode(params).encode("utf-8")
        else:
            body = {k: v for k, v in params.items() if ("{%s}" % k) not in opdef["path"]} if is_post else None
    # (3) circuit-breaker gate: open = refused locally (prevents the IP being collectively banned), error
    # code rate_limited (local protection, not an upstream response)
    breaker = _breaker(provider["id"])
    cooldown = breaker.allow()
    if cooldown > 0:
        raise SdkError("rate_limited", provider=provider["id"],
                       detail=f"Circuit breaker cooling down ({int(cooldown)}s left) — protection after consecutive recent failures; try again later")

    attempts = opdef.get("retries", 2) if (not is_post or opdef.get("idempotent") is True) else 0
    last_was_limited = False
    last_err = None
    clean_round_trip = False  # a successful round trip (incl. not_found) — not counted as a breaker failure
    host = _host_of(provider)
    conc = int(provider.get("concurrency", 2))
    try:
        for i in range(attempts + 1):
            _take_token(provider)
            _take_host_token(provider)  # (4) host-layer bucket (multiple providers on one host share the quota)
            _take_group_token(provider)  # (4b) family group bucket (multiple providers of one official family share the group quota; no group declared = pass through)
            try:
                # multipart is passed as the fifth argument only on the form-channel path, urlencoded as
                # the sixth — every other path keeps the four-argument call shape (the golden vectors
                # patch the four-argument _send signature)
                with _host_slot(host, conc):  # (5) host concurrency cap
                    if multipart is not None:
                        r = _send(url, opdef.get("transport", "urllib"), opdef.get("timeout", 20.0), None, multipart)
                    elif urlenc is not None:
                        r = _send(url, opdef.get("transport", "urllib"), opdef.get("timeout", 20.0), None, None, urlenc)
                    else:
                        r = _send(url, opdef.get("transport", "urllib"), opdef.get("timeout", 20.0), body)
            except (subprocess.TimeoutExpired, urllib.error.URLError, OSError) as e:
                last_was_limited, last_err = False, e
                if i < attempts:
                    time.sleep(_backoff_wait(i))
                continue
            if r["ok"] and (r["json"] is not None if opdef.get("accept") != "text" else isinstance(r.get("text"), str)):
                # accept:'text': an HTML-surface op (a 2xx HTML page is the expected payload, not a WAF
                # challenge); payload = the raw string, parsed at the provider layer (aligned with Node)
                payload = r["text"] if opdef.get("accept") == "text" else r["json"]
                clean_round_trip = True
                if not no_cache and cache is not None:
                    cache.set(provider["id"], cache_key, payload, ttl)
                return {"ok": True, "data": payload, "from_cache": False,
                        "fetched_at": now_iso(), "provider": provider["id"]}
            if r["ok"]:
                # 2xx but not JSON — the typical AWS WAF bot challenge (202 + x-amzn-waf-action HTML).
                # The gating holds on both the client stack and the egress IP (measured 2026-10-16:
                # undici from this machine is always 202; after switching the proxy egress, curl was
                # all 202 too).
                raise SdkError("upstream_unavailable", provider=provider["id"], status=r["status"],
                               detail=(f"Upstream {r['status']} returned non-JSON (body head {r['body_head'][:80]!r})"
                                       " — suspected AWS WAF bot challenge (x-amzn-waf-action);"
                                       " check the proxy egress IP / verify from another network first, do not blindly pin transport='curl'"))
            if r["status"] in (opdef.get("notFound") or []):
                clean_round_trip = True  # 404 = a clean round trip (zero hits on a search face that declared notFound)
                raise SdkError("upstream_not_found", provider=provider["id"], status=r["status"])
            if r["status"] in (401, 403):
                # (2) no blind retry for the gate/permission family: usually a WAF bot challenge or auth
                # (not rate limiting) — a retry hits the same wall and may deepen the block
                raise SdkError("upstream_unavailable", provider=provider["id"], status=r["status"],
                               detail=(f"Upstream {r['status']} (401/403 not retried — usually a WAF bot gate or auth rather than rate limiting; "
                                       "verify via another network egress or check the parameters; blind retries may escalate into an IP block)"))
            if r["status"] not in RETRYABLE:
                raise SdkError("upstream_unavailable", provider=provider["id"], status=r["status"],
                               detail=f"Upstream {r['status']}")
            last_was_limited = r["status"] in (429, 503)
            last_err = OSError(f"Upstream {r['status']}")
            if i < attempts:
                time.sleep(_backoff_wait(i, r["retry_after"]))  # (1) Retry-After first + exponential + jitter (capped at 30s)
        if last_was_limited:
            raise SdkError("upstream_rate_limited", provider=provider["id"], detail=str(last_err))
        raise SdkError("upstream_unavailable", provider=provider["id"],
                       detail=str(last_err)[:200] or "upstream unreachable")
    finally:
        breaker.record(clean_round_trip)
