"""shortages — FDA Drug Shortages provider (openFDA drug/shortages.json; keyless).

Wave 5 of the healthcare domain: related
kind=drug_shortages — manufacturer/drug name → drug shortage records, the supply-risk event stream: the last piece of the pipeline × safety × supply triad.
Row shapes measured 2026-10-23:
GET /drug/shortages.json?search=<q>&limit=N&skip=M&sort=update_date:desc
  search segments (three, AND-combinable, measured q1=179/q2=82/q3=AND 18):
    manufacturer → openfda.manufacturer_name.exact:"Fresenius Kabi USA, LLC" (exact phrase; bare tokens scatter)
    drug name → generic_name:"bupivacaine" (phrase search, multi-word ingredient names match whole)
    status → status:Current (the enum Current/Resolved/To Be Discontinued — measured on a 100-row Fresenius sample as 83/1/16)
  **zero hits = 404 {"error":{"code":"NOT_FOUND","message":"No matches found!"}}** — a legal answer, not an error
  (the openFDA convention); the op declares notFound:[404], and upstream_not_found turns into an empty set at this layer.
Row fields: generic_name/company_name/availability/status/update_type/update_date/initial_posting_date/
  package_ndc/presentation/dosage_form/shortage_reason/therapeutic_category/contact_info
  + the openfda enrichment block (manufacturer_name/application_number/product_ndc/rxcui/substance_name)
  — company_name = the manufacturer registered on the shortage record (may differ from openfda.manufacturer_name: that is the normalization layer, both columns are kept).
update_date can be sorted desc (measured: 10/15/2026 comes back first); the date form is MM/DD/YYYY.
TTL: a daily cadence (meta.last_updated measured 2026-10-22) → 24h; the keyless quota is 240/min → polite tier 2 rps.
"""
from datetime import datetime, timezone

from ..errors import SdkError

provider = {
    "id": "shortages",
    "baseUrl": "https://api.fda.gov",
    "rate": {"rps": 2, "burst": 5},
    "ops": {
        "search": {"path": "/drug/shortages.json", "notFound": [404]},  # params: search, limit, skip, sort
    },
    "ttl": {"search": 24 * 3600},
}


def rows_from_upstream(results):
    """Upstream rows → shortage record rows (pure function, testable offline): both company columns are kept (the registered manufacturer + the openFDA normalized manufacturer)."""
    rows = results if isinstance(results, list) else []
    out = []
    for r in rows:
        of = r.get("openfda") or {}
        out.append({
            "generic_name": r.get("generic_name"),
            "company_name": r.get("company_name"),          # the manufacturer registered on the shortage record (company edge, primary column)
            "manufacturers": of.get("manufacturer_name"),   # the openFDA normalized manufacturer (company edge, comparison column)
            "availability": r.get("availability"),
            "status": r.get("status"),
            "update_type": r.get("update_type"),
            "update_date": r.get("update_date"),
            "first_posted": r.get("initial_posting_date"),
            "package_ndc": r.get("package_ndc"),
            "presentation": r.get("presentation"),
            "dosage_form": r.get("dosage_form"),
            "shortage_reason": r.get("shortage_reason"),
            "therapeutic_category": r.get("therapeutic_category"),
            "applications": of.get("application_number"),
            "product_ndcs": of.get("product_ndc"),
            "rxcuis": of.get("rxcui"),
            "substances": of.get("substance_name"),
            "contact": r.get("contact_info"),
        })
    return out


def search_raw(search, *, limit=20, skip=0, sort="update_date:desc", cache=None, no_cache=False):
    """0.2.0 mirror face: the search expression is passed through verbatim (openFDA query syntax) + the upstream param names limit/skip/sort.

    Hard limit (protocol, confirmed by probing on 2026-10-23): limit 1-1000 — 1001 → 400 BAD_REQUEST
    «Limit cannot exceed 1000 results for search requests. Use the skip or search_after param»;
    deeper paging goes through skip — search_after is not accepted (probed 2026-10-28): with sort → 400 «search_after has 1 value(s)
    but sort has 2» (a semicolon double value → an ES parse error; the default sort → 200 but the rows are identical to the baseline = silently ignored); and the whole
    database holds only ~1604 rows, so limit 1000 + skip reaches the bottom in two pages — the deep-paging gap does not exist, skip is complete.
    search is required (local safety gate: under the keyless 240/min quota a bare full-table query is served by the bulk harvest line, not by this single-lookup face).
    A free sort string passes through (measured update_date:desc works; the default is ours, not the upstream one).
    → {rows[], total, count, skip, limit_applied, has_more, search, sort, _meta}; zero hits = an empty set that is not cached (same as above).
    """
    from ..transport import call_provider

    q = str(search or "").strip()
    if not q:
        raise SdkError("usage_error", provider="shortages",
                       detail="search requires an expression (e.g. generic_name:'bupivacaine' — the phrase segment needs double quotes; a bare full-table query is served by the bulk line)")
    size = int(limit or 20)
    if not 1 <= size <= 1000:
        raise SdkError("usage_error", provider="shortages",
                       detail=f"limit must be 1-1000 (upstream 400: Limit cannot exceed 1000 results for search "
                              f"requests — measured 2026-10-23; to page deeper use skip, the whole database of ~1604 rows is reached in two pages), got {size}")
    sk = max(0, int(skip or 0))
    so = str(sort or "").strip()
    params = {"search": q, "limit": size}
    if sk:
        params["skip"] = sk
    if so:
        params["sort"] = so
    try:
        r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_not_found":
            return {"rows": [], "total": 0, "count": 0, "skip": sk, "limit_applied": size,
                    "has_more": False, "search": q, "sort": so or None,
                    "_meta": {"from_cache": False,
                              "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}}
        raise
    data = r.get("data") or {}
    rows = rows_from_upstream(data.get("results"))
    total = (data.get("meta") or {}).get("results", {}).get("total", len(rows))
    return {"rows": rows, "total": total, "count": len(rows), "skip": sk, "limit_applied": size,
            "has_more": total > sk + len(rows), "search": q, "sort": so or None, "_meta": r}
