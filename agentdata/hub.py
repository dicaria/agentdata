"""agentdata.hub — the Hub family: PAT -> short-lived subject JWT -> allowlisted GET on OmniHub.

Contract: RFC-002 (AgentData PAT -> MCP/Hub integration) sections 3.4/3.5.
- Token: POST AGENTDATA_TOKEN_URL (mcpserver /agentdata/downstream-token) with the PAT as
  "Authorization: Bearer <PAT>", no body and no Content-Type (the endpoint rejects both).
  Response: access_token / token_type=Bearer / expires_in=55 / subject.
- The JWT is cached in-process until expires_in - 10 (55s -> 45s usable). A lock gives
  singleflight semantics: concurrent callers share one fetch and never see a half-written cache.
- Requests: GET only, exact allowlist. The eight path regexes are the client-side copy of the
  OmniHub/mcpserver read policy (defense-in-depth: the SDK rejects early, the server stays the
  authority). Query strings are generated only from params; the path never carries '?'/ '#'.
- Credential boundary: the PAT crosses exactly one boundary (the token endpoint). hub_request
  headers carry only the short-lived JWT; neither the PAT nor the JWT is ever logged or echoed.
- clock/transport are injectable for tests (default: time.time / urllib).
"""
import email.utils
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timezone

from .errors import SdkError

TOKEN_MARGIN_SECONDS = 10.0  # refresh margin: a cached JWT is dead at expires_in - 10

# RFC-002 section 3.5 exact allowlist (byte-identical policy to OmniHub authorization and the
# mcpserver runtime; Task 10 pins the fixture checksum that keeps the three copies in sync).
PATH_ALLOWLIST = (
    re.compile(r"^/v1/company/companies(?::search|:screen)?$"),
    re.compile(r"^/v1/company/companies/[0-9a-f]{32}$"),
    re.compile(r"^/v1/(cn|us)/(drug|device)/approvals(?:/[0-9a-f]{32})?$"),
    re.compile(r"^/v1/(cn|us)/risk/events(?:/[0-9a-f]{32})?$"),
    re.compile(r"^/v1/(cn|us)/hospital/institutions(?:/[0-9a-f]{32})?$"),
    re.compile(r"^/v1/(cn|us)/clinical-trials/studies(?:/[0-9a-f]{32})?$"),
    re.compile(r"^/v1/(cn|us)/pricing/rows(?:/[0-9a-f]{32})?$"),
    re.compile(r"^/v1/(cn|us)/aggregate/timelines$"),
)

_ABSOLUTE_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")  # any scheme: prefix (a path starts with '/')
_BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")  # every % must open a valid pct-encoded triplet

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Credential-bearing calls never follow redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _no_redirect_opener():
    return urllib.request.build_opener(NoRedirectHandler())


_STATUS_CODES = {400: "usage_error", 401: "unauthenticated", 402: "insufficient_credits",
                 403: "forbidden", 404: "upstream_not_found", 429: "rate_limited"}


def _usage(detail: str) -> SdkError:
    return SdkError("usage_error", detail=detail)


def normalize_hub_path(path) -> str:
    """Strict RFC3986 canonicalization + exact allowlist. Returns the path unchanged on success
    (every allowlisted path is plain ASCII, so percent-encoding has nothing legitimate to do here);
    raises SdkError(usage_error) before any HTTP work otherwise."""
    if not isinstance(path, str) or not path:
        raise _usage("hub path must be a non-empty relative path string")
    if _ABSOLUTE_URL.match(path):
        raise _usage(f"hub path must be a relative path, got an absolute URL/scheme: {path[:80]!r}")
    if path.startswith("//"):
        raise _usage("hub path must not be scheme-relative ('//...')")
    if "\\" in path:
        raise _usage("hub path must not contain backslashes")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in path):
        raise _usage("hub path must not contain control characters")
    if any(ord(c) > 0x7E for c in path):
        raise _usage("hub path must be ASCII (RFC3986); allowlisted paths need no non-ASCII")
    if any(c.isspace() for c in path):
        raise _usage("hub path must not contain whitespace")
    if "?" in path:
        raise _usage("hub path must not carry a query string; pass query parameters via params=")
    if "#" in path:
        raise _usage("hub path must not carry a fragment")
    if _BAD_PERCENT.search(path):
        raise _usage("hub path contains an invalid percent-encoding")
    if "%" in path:
        # decode once and forbid separators/controls/double-encoding (%2f, %5c, %25, %00 tricks)
        try:
            decoded = urllib.parse.unquote(path, encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            raise _usage("hub path percent-encoding does not decode to valid UTF-8") from None
        if ("/" in decoded or "\\" in decoded or "%" in decoded
                or any(ord(c) < 0x20 or ord(c) == 0x7F or ord(c) > 0x7E for c in decoded)):
            raise _usage("hub path encoded characters are not allowed (no separators, controls or double encoding)")
    if "//" in path:
        raise _usage("hub path must not contain repeated slashes")
    if any(seg in (".", "..") for seg in path.split("/")):
        raise _usage("hub path must not contain dot segments")
    if not path.startswith("/"):
        raise _usage("hub path must start with '/'")
    if path.endswith("/"):
        raise _usage("hub path must not have a trailing slash")
    for rx in PATH_ALLOWLIST:
        if rx.fullmatch(path):
            return path
    raise _usage("hub path is not in the Hub allowlist (RFC-002 section 3.5 read-only paths)")


def _default_transport(method: str, url: str, headers: dict, timeout: float):
    """urllib channel: -> (status, body_bytes, headers-with-.get). HTTP errors are returned, not
    raised, so error mapping lives in exactly one place; network failures raise OSError."""
    req = urllib.request.Request(url, data=None, method=method, headers=headers)
    try:
        with _no_redirect_opener().open(req, timeout=timeout) as resp:
            return resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as e:  # 4xx/5xx: body still read, mapped by the caller
        try:
            body = e.read()
        finally:
            e.close()
        return e.code, body, e.headers


def _parse_retry_after(headers, now: float):
    raw = headers.get("Retry-After") if headers else None
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        pass
    try:  # RFC 7231 HTTP-date form
        dt = email.utils.parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, dt.timestamp() - now)
    except (TypeError, ValueError, OverflowError):
        return None


class HubClient:
    """One object, one credential flow: hub_token()/token_payload() exchange the PAT once and cache
    the short-lived JWT; request()/get() enforce GET + allowlist and call the Hub with the JWT."""

    def __init__(self, token_url=None, hub_base_url=None, api_key=None, *,
                 timeout=20.0, clock=None, transport=None, allow_http=False):
        self._token_url = token_url or None
        self._hub_base_url = hub_base_url or None
        self.api_key = api_key or None
        self.timeout = timeout
        self._clock = clock            # None -> time.time at call time (late env/patch binding)
        self._transport = transport    # None -> _default_transport at call time
        self.allow_http = bool(allow_http)  # test-only escape hatch; production is HTTPS-only
        self._lock = threading.Lock()
        self._cached = None            # {"payload": dict, "expires_at": float}

    # ---------- token ----------

    def _now(self) -> float:
        return self._clock() if self._clock is not None else time.time()

    def _send(self, method: str, url: str, headers: dict):
        transport = self._transport if self._transport is not None else _default_transport
        try:
            return transport(method, url, headers, self.timeout)
        except OSError as e:  # URLError/timeout/socket family (SdkError passes through untouched)
            raise SdkError("capability_unavailable", detail=f"Hub endpoint unreachable: {e}") from e

    def _require_config(self, value, what: str, env: str):
        if not value:
            raise _usage(f"The Hub family needs {what}: pass it explicitly or set {env}")
        return value

    def _token_url_validated(self) -> str:
        url = self._require_config(self._token_url, "a token URL", "AGENTDATA_TOKEN_URL").strip()
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" and not (self.allow_http and parts.scheme == "http"):
            raise _usage(f"invalid token URL {url!r} (HTTPS required; HTTP requires test-only allow_http)")
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise _usage(f"invalid token URL {url!r} (expected http(s)://host/…)")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise _usage("invalid token URL (no userinfo/query/fragment allowed)")
        return url

    def token_payload(self) -> dict:
        """Bearer token for Hub calls, cached until expires_in - TOKEN_MARGIN_SECONDS.
        Singleflight: the lock covers check + fetch, so concurrent refreshers share one request."""
        with self._lock:
            cached = self._cached
            if cached is not None and self._now() < cached["expires_at"]:
                return cached["payload"]
            payload = self._fetch_token_payload()
            # expires_in <= margin (or <= 0) -> already expired -> nothing cacheable, refetch next call
            self._cached = {"payload": payload,
                            "expires_at": self._now() + float(payload["expires_in"]) - TOKEN_MARGIN_SECONDS}
            return payload

    def hub_token(self) -> str:
        return self.token_payload()["access_token"]

    def _fetch_token_payload(self) -> dict:
        self._require_config(self.api_key, "a PAT (api_key)", "AGENTDATA_API_KEY")
        status, raw, headers = self._send("POST", self._token_url_validated(), {
            "Authorization": f"Bearer {self.api_key}",  # the PAT crosses exactly this one boundary
            "Accept": "application/json",
        })
        doc = self._parse_json(status, raw)
        if not 200 <= status < 300:
            raise self._http_error(status, doc, headers)
        token, ttype, expires_in = doc.get("access_token"), doc.get("token_type"), doc.get("expires_in")
        if not isinstance(token, str) or not token:
            raise SdkError("capability_unavailable", status=status,
                           detail="token endpoint returned no access_token (invalid response)")
        if not isinstance(ttype, str) or ttype.lower() != "bearer":
            raise SdkError("capability_unavailable", status=status,
                           detail=f"token endpoint returned unsupported token_type {ttype!r} (expected Bearer)")
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)) or expires_in <= 0:
            raise SdkError("capability_unavailable", status=status,
                           detail=f"token endpoint returned invalid expires_in {expires_in!r}")
        subject = doc.get("subject")
        return {"access_token": token, "token_type": ttype, "expires_in": expires_in,
                "subject": subject if isinstance(subject, str) else None}

    # ---------- requests ----------

    def request(self, method, path, params=None) -> dict:
        if not isinstance(method, str) or method.upper() != "GET":
            raise _usage(f"hub_request supports GET only, got {method!r} (the Hub read face is GET-only)")
        norm = normalize_hub_path(path)
        url = self._hub_url_validated().rstrip("/") + norm
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        qs = urllib.parse.urlencode(clean, doseq=True)  # the query comes only from params
        if qs:
            url += "?" + qs
        jwt = self.token_payload()["access_token"]  # short-lived JWT, never the PAT
        status, raw, headers = self._send("GET", url, {"Authorization": f"Bearer {jwt}",
                                                       "Accept": "application/json"})
        doc = self._parse_json(status, raw)
        if not 200 <= status < 300:
            raise self._http_error(status, doc, headers)
        return doc

    def get(self, path, params=None) -> dict:
        return self.request("GET", path, params)

    def _hub_url_validated(self) -> str:
        base = self._require_config(self._hub_base_url, "a Hub base URL", "AGENTDATA_HUB_BASE_URL").strip()
        parts = urllib.parse.urlsplit(base)
        if parts.scheme != "https" and not (self.allow_http and parts.scheme == "http"):
            raise _usage(f"invalid Hub base URL {base!r} (HTTPS required; HTTP requires test-only allow_http)")
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise _usage(f"invalid Hub base URL {base!r} (expected http(s)://host[/root])")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise _usage("invalid Hub base URL (no userinfo/query/fragment allowed)")
        return base

    # ---------- response handling ----------

    def _parse_json(self, status: int, raw) -> dict:
        if isinstance(raw, dict):  # injected transports may pre-decode; urllib returns bytes
            return raw
        try:
            doc = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            raise SdkError("capability_unavailable", status=status,
                           detail=f"Hub endpoint returned a non-JSON response (HTTP {status})") from None
        if not isinstance(doc, dict):
            raise SdkError("capability_unavailable", status=status,
                           detail=f"Hub endpoint returned a non-object JSON response (HTTP {status})")
        return doc

    def _http_error(self, status: int, doc: dict, headers) -> SdkError:
        retry_after = _parse_retry_after(headers, self._now())
        err = doc.get("error") if isinstance(doc, dict) else None
        if isinstance(err, dict) and err.get("code"):
            return SdkError(err["code"], status=status,
                            detail=err.get("message") or f"HTTP {status}", retry_after=retry_after)
        detail = doc.get("detail") if isinstance(doc.get("detail"), str) else f"HTTP {status}"
        code = _STATUS_CODES.get(status) or ("upstream_unavailable" if status >= 500 or status == 408
                                             else "usage_error")
        return SdkError(code, status=status, detail=detail, retry_after=retry_after)
