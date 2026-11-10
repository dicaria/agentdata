"""us_npi — US NPPES NPI registry, organizational face (npiregistry.cms.hhs.gov v2.1; keyless).

healthcare provider-master face (0.3.53; admitted from research 册 106 us-npi-providers, probed
live 2026-11-10, tmp/probe-sdk0352/). The National Provider Identifier is the US healthcare
universe's join key (CMS Open Payments, LEIE exclusions — the 册 106 bridges). The face pins
enumerationType=Organizational (NPI-2): organization_name reverse lookup is the
company-enrichment channel (an exact-phrase match — "Mayo" alone answers zero, "Mayo Clinic"
answers 2; spaces must travel URL-encoded, both measured live), and the organizational record
carries the authorized official (name/title/phone), organizational_subpart, status,
enumeration/last-updated dates, taxonomy blocks (code, desc, primary, state license) and the
practice/mailing addresses.

Measured contract (live 2026-11-10): number= is the deterministic exact lookup (1881018208 →
exactly one row); organization_name / taxonomy_description / postal_code / city are each valid
single criteria (each answers the default 10-row page); state ALONE is refused upstream with
error 07 "Field state requires additional search criteria" — state is a refiner, never a
criterion; enumerationType=Organizational has been observed mixing NPI-1 individual rows
(册 106 probe 11-02), so the face filters enumeration_type=="NPI-2" client-side. limit: the
API SILENTLY CLAMPS >200 to 200 (limit=250 answered result_count=200, no error — the
upstream-silent-clamp family), so 1-200 is a local wall pinned by measurement. skip: no
total echo — enumeration is a walk-to-empty-page (skip=1200 still answered a full page live,
past the documented 1000 ceiling); result_count is the PAGE row count, never a corpus total.
Upstream Errors [{number, description, field}] map verbatim into usage_error detail.
The bulk download hosts (download.npi.nppes / ndhdata) are network-dead from this egress
(roadmap §七) — the monthly full files ride the raw harvest line, not this face.
No published quota → 1/2 polite, TTL 24h (registry records change slowly).
"""
provider = {
    "id": "us_npi",
    "baseUrl": "https://npiregistry.cms.hhs.gov",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "search": {"path": "/api/", "timeout": 30.0},
    },
    "ttl": {"search": 24 * 3600},
}

_CRITERIA = ("number", "organization_name", "taxonomy_description", "postal_code", "city")


def search_raw(number=None, organization_name=None, taxonomy_description=None,
               city=None, state=None, postal_code=None, *, limit=20, skip=0,
               cache=None, no_cache=False):
    """→ {result_count, count, rows[], params, _meta}. rows are the NPI-2 records verbatim
    (basic/taxonomies/addresses/identifiers sub-objects intact); at least one search criterion
    among number/organization_name/taxonomy_description/postal_code/city is required — state
    alone is an upstream error (07), it only refines."""
    from ..errors import SdkError
    from ..transport import call_provider

    params = {"version": "2.1", "enumerationType": "Organizational"}
    if number is not None and str(number).strip():
        n = str(number).strip()
        if not (n.isdigit() and len(n) == 10):
            raise SdkError("usage_error", provider="us_npi",
                           detail=f"number must be the 10-digit NPI, got {number!r}")
        params["number"] = n
    for key, val in (("organization_name", organization_name),
                     ("taxonomy_description", taxonomy_description),
                     ("city", city), ("state", state), ("postal_code", postal_code)):
        v = str(val or "").strip()
        if v:
            params[key] = v
    if not any(k in params for k in _CRITERIA):
        raise SdkError("usage_error", provider="us_npi",
                       detail=f"at least one search criterion is required (one of {', '.join(_CRITERIA)}) — "
                              "state alone is refused upstream (error 07: it requires additional criteria), "
                              "and a bare version query answers error 04 (no valid search criteria)")
    size = 20
    if limit is not None:
        try:
            size = int(limit)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="us_npi",
                           detail=f"limit must be an integer 1-200, got {limit!r}")
    if not 1 <= size <= 200:
        raise SdkError("usage_error", provider="us_npi",
                       detail=f"limit must be 1-200 (the API SILENTLY CLAMPS >200 to 200 — measured live "
                              f"limit=250 → result_count=200, no error), got {limit!r}")
    params["limit"] = size
    off = 0
    if skip is not None:
        try:
            off = int(skip)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="us_npi",
                           detail=f"skip must be an integer >=0, got {skip!r}")
    if off < 0:
        raise SdkError("usage_error", provider="us_npi", detail=f"skip must be >=0, got {skip!r}")
    params["skip"] = off

    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    doc = r["data"]
    if not isinstance(doc, dict):
        raise SdkError("upstream_unavailable", provider="us_npi",
                       detail="the NPPES API answered non-JSON (shape drift or maintenance)")
    if "Errors" in doc:
        errs = "; ".join(f"[{e.get('number')}] {e.get('description')}"
                         + (f" (field {e.get('field')})" if e.get("field") and e.get("field") != "generic" else "")
                         for e in doc["Errors"])
        raise SdkError("usage_error", provider="us_npi",
                       detail=f"the NPPES API refused the query: {errs}")
    rows = [x for x in (doc.get("results") or []) if x.get("enumeration_type") == "NPI-2"]
    return {"result_count": doc.get("result_count"), "count": len(rows), "rows": rows,
            "params": params, "_meta": r}
