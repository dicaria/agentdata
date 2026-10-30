"""agentdata.client — one object, both families share a shape: enrichment (local, zero config) + corpus (hosted, base_url+api_key).

Contract: docs/domains/api.md (section 8 corpus / section 9 enrichment capability axis).
- The quartet is mandatory: result / reason / evidence / source.
- Enrichment rows carry source={provider, execution, from_cache, observed_at|fetched_at} (the cache is not a backend).
- execution axis local|hosted|auto: auto->local (all current capabilities are keyless); requesting a keyless
  capability as hosted -> capability_unavailable, never a silent rerouting (api.md section 9.2).
- request_id: for local execution the SDK generates one (uuid4) and puts it on the envelope; for hosted corpus
  the server-side request_id wins.
"""
import os
import uuid
import json
import urllib.error
import urllib.parse
import urllib.request

from .company.faces import CompanyFaces
from .esg.faces import EsgFaces
from .healthcare.faces import HealthcareFaces
from .legal.faces import LegalFaces
from .procurement.faces import ProcurementFaces
from .research.faces import ResearchFaces
from .security.faces import SecurityFaces
from .errors import SdkError
from .cache import Cache
from .transport import enrich_source, resolve_execution  # three helpers live in transport (0.3.0 verb-layer removal; _tty_tag now domain-internal)

CONTRACT = "docs/domains/api.md"


class Client:
    def __init__(self, base_url=None, api_key=None, *, execution="auto", cache_dir=None,
                 no_cache=False, timeout=20.0):
        if execution not in ("local", "hosted", "auto"):
            raise SdkError("usage_error", detail=f"execution must be local|hosted|auto, got '{execution}'")
        self.default_execution = execution
        self.no_cache = bool(no_cache)
        self.timeout = timeout
        self._cache = Cache(cache_dir, enabled=not no_cache)
        self.base_url = (base_url or os.environ.get("AGENTDATA_BASE_URL") or "").rstrip("/") or None
        self.api_key = api_key or os.environ.get("AGENTDATA_API_KEY") or None
        self.healthcare = _Domain(self, "healthcare")
        self.company = _Domain(self, "company")
        self.esg = _Domain(self, "esg")
        self.legal = _Domain(self, "legal")
        self.procurement = _Domain(self, "procurement")  # 0.3.0: the seventh domain
        self.research = _Domain(self, "research")
        self.security = _Domain(self, "security")

    def _request_id(self) -> str:
        return str(uuid.uuid4())

    # —— corpus family: hosted HTTP (Bearer PAT; the closed error-envelope set passes straight through) ——
    def _corpus(self, domain: str, verb: str, payload: dict) -> dict:
        if not self.base_url or not self.api_key:
            raise SdkError("usage_error",
                           detail="The corpus family uses hosted HTTP: Client(base_url=…, api_key=…) (enrichment works with zero config; ask us to issue you a PAT)")
        url = f"{self.base_url}/v1/{domain}/{verb}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=max(self.timeout, 120)) as resp:
                status, raw, headers = resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            status, raw, headers = e.code, e.read(), e.headers
        except (urllib.error.URLError, OSError) as e:
            raise SdkError("capability_unavailable", detail=f"Gateway unreachable: {e}") from e
        try:
            doc = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            raise SdkError("capability_unavailable", status=status, detail=f"Gateway returned a non-JSON response (HTTP {status})")
        if status >= 400:
            err = doc.get("error") or {}
            ra_hdr = headers.get("Retry-After") if headers else None
            try:
                ra = float(ra_hdr) if ra_hdr else None
            except (TypeError, ValueError):
                ra = None
            raise SdkError(err.get("code", "internal"), status=status,
                           detail=err.get("message") or f"HTTP {status}", retry_after=ra)
        return doc


class _Domain(HealthcareFaces, CompanyFaces, EsgFaces, LegalFaces, ProcurementFaces,
              ResearchFaces, SecurityFaces):
    """Domain namespace object — the flat faces are mixed in from each domain's faces; the corpus-family
    search/read stay on the base class (hosted, api.md section 8 living contract). In 0.3.0 the verb layer
    (resolve/evidence/trials/label/related/fulltext), the csl_screening frozen alias and the grants domain
    alias were removed per the established contract."""
    def __init__(self, client: Client, name: str):
        self._c = client
        self.name = name

    # ---------- quartet envelope (shared by every domain's faces) ----------
    # A single upstream request passes through; we may add defaults/validation/rate limiting/caching/
    # error normalization/row shaping, but must never permanently hide a capability the upstream can
    # express; a cap is allowed only for a hard protocol limit or local safety. Quartet envelope + the
    # query echo quartet.

    def _flat_env(self, *, tool, input, reason, result, evidence, provider_id, metas,
                  query=None, deprecations=None):
        ex = resolve_execution(self._c.default_execution)
        metas = [m for m in metas if m]
        out = {
            "ok": True, "domain": self.name, "tool": tool,
            "input": input,
            "from_cache": bool(metas) and all(m.get("from_cache") for m in metas),
            "reason": reason,
            "result": result,
            "evidence": evidence,
            "source": enrich_source(provider_id, ex, *metas),
            "request_id": self._c._request_id(),
        }
        if query is not None:
            out["query"] = query
        if deprecations:
            out["deprecations"] = deprecations
        return out

    # ---------- corpus (hosted) ----------

    def search(self, *, filters=None, record_kind=None, facets=None, level="tier1",
               limit=50, cursor=None, mode=None, screen_inputs=None):
        """Corpus search (hosted API). mode="screen" + screen_inputs is the batch-screening mode."""
        payload = {"level": level, "limit": limit}
        if filters:
            payload["filters"] = filters
        if record_kind:
            payload["record_kind"] = record_kind
        if facets:
            payload["facets"] = facets if isinstance(facets, list) else [facets]
        if cursor:
            payload["cursor"] = cursor
        if mode:
            payload["mode"] = mode
        if screen_inputs is not None:
            payload["screen_inputs"] = screen_inputs
        out = self._c._corpus(self.name, "search", payload)
        out["request_id"] = out.get("request_id") or self._c._request_id()
        return out

    def read(self, id=None, *, target=None, level="tier1"):
        """Corpus single-record read (hosted API): id (or target) + T-layer depth."""
        payload = {"level": level}
        if id is not None:
            payload["id"] = id
        elif target is not None:
            payload["target"] = target
        out = self._c._corpus(self.name, "read", payload)
        out["request_id"] = out.get("request_id") or self._c._request_id()
        return out
