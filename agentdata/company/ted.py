"""ted — EU TED (Tenders Electronic Daily) v3 provider (EU procurement notices; keyless).

The old face (search.api.ted.europa.eu REST/SOAP) was 429-blocked three times in 2026-10 — overturned on
2026-10-23: api.ted.europa.eu/v3 POST expert search works from this egress (the old block only applied to the old
face; do not extrapolate across faces).
Contract pitfalls (self-evidenced by the 400 error body): 1. GET→405 (POST-only); 2. body {query, fields[], limit, page};
3. fields must come from the eForms field enumeration (a wrong name 400s and dumps the full 1,833-field list — the error
body is the documentation).
Wildcard pitfall: values must match ^[^*?] — leading wildcards are forbidden (*Siemens* 400), a trailing wildcard is
legal (Siemens* = prefix match).
Return-shape pitfall: text fields are language dicts ({'deu':['…']}) — loc() flattens preferring eng; publication-date
carries a 'Z' suffix.
TTL: search 24h (notice feeds update daily). Politeness tier 0.5 rps (conservative given the old face's 429 record).
"""
import re

from ..errors import SdkError

provider = {
    "id": "ted",
    "baseUrl": "https://api.ted.europa.eu/v3",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # POST with read semantics: expert search is idempotent read-only; all params go in the JSON body
        "search": {"path": "/notices/search", "method": "POST", "idempotent": True, "timeoutMs": 30000},
    },
    "ttl": {"search": 24 * 3600},
}

_FIELDS = ["publication-number", "publication-date", "notice-title", "notice-type",
           "organisation-name-buyer", "organisation-country-buyer", "total-value"]


def loc(v):
    """Language dict/array flattening: {'eng':['X'],'deu':['Y']} → prefer eng, take the first value."""
    if isinstance(v, list):
        return next((x for x in v if x), None)
    if isinstance(v, dict):
        k = "eng" if "eng" in v else next(iter(v), None)
        return loc(v.get(k)) if k is not None else None
    return v


def ted_from_upstream(data, limit=10):
    """Upstream payload → {notices[], has_more} (pure function, offline-testable); no total — inferred from a full page."""
    ns = (data or {}).get("notices") or []
    return {
        "has_more": len(ns) >= limit,
        "notices": [{
            "publication_number": n.get("publication-number"),   # stable key (e.g. 671086-2023)
            "publication_date": (n.get("publication-date") or "").removesuffix("Z") or None,
            "title": loc(n.get("notice-title")),
            "notice_type": n.get("notice-type"),                 # eForms type (cn-standard = contract notice, standard…)
            "buyer": loc(n.get("organisation-name-buyer")),
            "buyer_country": n.get("organisation-country-buyer"),
            "total_value": n.get("total-value"),
            "xml_url": (n.get("links") or {}).get("xml"),        # eForms XML original anchor (the corpus line pulls full text from it)
        } for n in ns],
    }


def company_eu_tenders(name=None, *, country=None, cpv=None, limit=10, cache=None, no_cache=False):
    """→ {notices[], has_more, query, _meta}; EU procurement notice rows (buyer prefix match).
    Join discipline (same as fed_awards): match on name against the buyer face, parent/subsidiary groups are not merged,
    narrow by VAT/LEI before persisting."""
    from ..transport import call_provider

    parts = []
    q = str(name or "").strip()
    if q:
        if q[:1] in "*?":
            raise SdkError("usage_error", provider="ted",
                           detail="upstream forbids leading wildcards (^[^*?]) — use prefix matching (e.g. Siemens)")
        parts.append(f"organisation-name-buyer={re.sub(r'[*?]', '', q)}*")  # trailing wildcard = prefix match
    c = str(country or "").strip().upper()
    if c:
        if not re.fullmatch(r"[A-Z]{3}", c):
            raise SdkError("usage_error", provider="ted", detail="country must be ISO-3 (e.g. DEU)")
        parts.append(f"organisation-country-buyer={c}")
    cp = str(cpv or "").strip()
    if cp:
        if not re.fullmatch(r"\d{8}", cp):
            raise SdkError("usage_error", provider="ted", detail="cpv must be an 8-digit CPV code (e.g. 33100000 medical consumables)")
        parts.append(f"classification-cpv={cp}")
    if not parts:
        raise SdkError("usage_error", provider="ted", detail="give at least one of name / country / cpv")
    lim = min(max(1, int(limit) or 10), 20)
    query = " AND ".join(parts)
    r = call_provider(provider, "search", {"query": query, "fields": _FIELDS, "limit": lim, "page": 1},
                      cache=cache, no_cache=no_cache)
    return {**ted_from_upstream(r["data"], lim), "query": query, "_meta": r}


def search_raw(query, *, fields=None, limit=10, page=1, cache=None, no_cache=False):
    """→ {notices[], has_more, query, params, _meta}; expert search verbatim (query goes into the POST body by its upstream name).
    limit wall 1-250: measured 2026-10-23, 251→400 SEARCH_EXCEEDS_MAX_LIMIT
    ("Value (251) of parameter 'limit' exceeds maximum allowed value (250)"); 250 served in full.
    fields defaults to the seven _FIELDS columns and can be overridden with a comma-separated string — a wrong name 400s and
    dumps the full 1,833-field list (the error body is the documentation).
    The old company_eu_tenders 20 clamp is this repo's politeness tier, not an upstream limit — the flat face follows the
    measured wall."""
    from ..transport import call_provider
    from ..errors import SdkError

    q = str(query or "").strip()
    if not q:
        raise SdkError("usage_error", provider="ted",
                       detail="ted_notices_search requires query (expert syntax, e.g. organisation-name-buyer=Siemens*)")
    lim = int(limit)
    if not 1 <= lim <= 250:
        raise SdkError("usage_error", provider="ted",
                       detail="limit must be 1-250 (measured 2026-10-23: 251→400 SEARCH_EXCEEDS_MAX_LIMIT, "
                              "upstream text \"exceeds maximum allowed value (250)\")")
    flds = [f.strip() for f in str(fields).split(",") if f.strip()] if fields else list(_FIELDS)
    params = {"query": q, "fields": flds, "limit": lim, "page": int(page)}
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    return {**ted_from_upstream(r["data"], lim), "query": q, "params": params, "_meta": r}
