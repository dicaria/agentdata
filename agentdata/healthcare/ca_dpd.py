"""ca_dpd — Health Canada Drug Product Database open API face provider
(health-products.canada.ca/api/drug/; keyless).

healthcare domain (0.3.19; admitted 2026-11-02, probed). Shapes verified by first-hand live probing
2026-11-02 (the probe corpus lives in tmp/probe-ca-eu-faces/):
GET /api/drug/company/?lang=en&type=json
  → the full company register in ONE shot (no pagination surface on this host — 5,253 rows
    measured 2026-11-02; rows carry company_code (the DPD join key) + company_name +
    company_type (DIN OWNER / …) + the full postal address).
    **Pit nailed: the Read Me page (GET /api/drug/ — the HTML index of the API family) is the
    only enum documentation; the naive guess "status codes endpoint" (/api/drug/status) returns
    the per-drug status *history* table (10.3MB), not the enum.**
GET /api/drug/drugproduct/?status=<n>&lang=en&type=json
  → drug products filtered by market status. **status is a closed set 1|2|3|4|6 per the Read Me
    page — 1=Approved, 2=Marketed, 3=Cancelled Pre-Market, 4=Cancelled Post-Market, 6=Dormant
    (no 5 in the official set); any other value is silently ignored and the endpoint dumps the
    whole unfiltered register (15MB, ~55k rows — the silent-filter-ignored trap, same family as
    the Socrata ones), so status is REQUIRED here and validated against the closed set.**
    Rows carry drug_code + drug_identification_number (DIN) + brand_name + company_name inline
    (company_code is NOT echoed on this face — join via company_name or run the company face);
    the row does not echo the requested status either.
  Measured: status=3 → 4,116 rows (2026-11-02).
Param-minimalism pitfall (this host publishes no per-endpoint docs beyond the Read Me links):
unprobed param combinations → either silent no-op or a full dump — this face accepts only the
documented lang/type/status family, do not widen it.
Local row slicing (limit/skip) is a post-slice over the single cached full shot — the upstream
has no paging, and the register itself is the payload (a monthly static extract).
TTL 7 days (the DPD monthly extract changes slowly); polite rate 1 rps (the host publishes no
quota — conservative; the same host also serves ca_mdall, the shared host bucket coordinates them).
"""
from ..errors import SdkError

provider = {
    "id": "ca_dpd",
    "baseUrl": "https://health-products.canada.ca",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "companies": {"path": "/api/drug/company/"},        # params: lang/type fixed for this face
        "drug_products": {"path": "/api/drug/drugproduct/"},  # params: lang/type fixed + status (required, closed set)
    },
    "ttl": {"companies": 7 * 86400, "drug_products": 7 * 86400},
}

_STATUS = {1: "Approved", 2: "Marketed", 3: "Cancelled Pre-Market",
           4: "Cancelled Post-Market", 6: "Dormant"}  # the Read Me closed set (measured: no 5 in the family links)


def companies_from_upstream(data):
    """Upstream company array → company rows (pure function, offline-testable)."""
    rows = [{
        "company_code": r.get("company_code"),          # the DPD join key
        "company_name": r.get("company_name"),
        "company_type": r.get("company_type"),          # e.g. DIN OWNER
        "address": {k: r.get(k) for k in ("street_name", "city_name", "province_name",
                                          "country_name", "postal_code")},
    } for r in (data or []) if isinstance(r, dict)]
    return {"rows": rows, "count": len(rows)}


def drug_products_from_upstream(data, status):
    """Upstream drug-product array → product rows (pure function, offline-testable)."""
    rows = [{
        "drug_code": r.get("drug_code"),
        "din": r.get("drug_identification_number"),     # the 8-digit DIN (the dispensed-product key)
        "brand_name": r.get("brand_name"),
        "class_name": r.get("class_name"),              # Human / Veterinary
        "company_name": r.get("company_name"),          # inline on this face; company_code is NOT echoed
        "number_of_ais": r.get("number_of_ais"),
        "ai_group_no": r.get("ai_group_no"),
        "last_update_date": r.get("last_update_date"),
    } for r in (data or []) if isinstance(r, dict)]
    return {"rows": rows, "count": len(rows), "total": len(rows),
            "status": int(status), "status_label": _STATUS[int(status)]}


def _slice(rows, limit, skip):
    """Local post-slice over the single cached full shot (the upstream has no paging surface)."""
    off = int(skip) if skip is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="ca_dpd", detail=f"skip must be >=0, got \"{skip}\"")
    size = int(limit) if limit is not None else 200
    if size < 1:
        raise SdkError("usage_error", provider="ca_dpd", detail=f"limit must be >=1 (local post-slice, no upstream cap), got \"{limit}\"")
    return rows[off:off + size]


def companies_raw(*, limit=200, skip=0, cache=None, no_cache=False):
    """Flat-panel low-level face: the DPD company register, one full shot (5,253 rows measured
    2026-11-02) cached whole; limit/skip is a local post-slice.

    → {rows[], count, total, params, _meta} — total = the whole register size (not the page)."""
    from ..transport import call_provider

    params = {"lang": "en", "type": "json"}
    r = call_provider(provider, "companies", params, cache=cache, no_cache=no_cache)
    out = companies_from_upstream(r["data"])
    rows = _slice(out["rows"], limit, skip)
    return {"rows": rows, "count": len(rows), "total": out["count"],
            "params": params, "_meta": r}


def drug_products_raw(status, *, limit=200, skip=0, cache=None, no_cache=False):
    """Flat-panel low-level face: DPD drug products by market status.

    status = the Read Me closed set 1|2|3|4|6 (1=Approved 2=Marketed 3=Cancelled Pre-Market
    4=Cancelled Post-Market 6=Dormant) — REQUIRED and validated: any other value is silently
    ignored upstream and dumps the whole 15MB register (the silent-filter trap).
    → {rows[], count, total, status, status_label, params, _meta}."""
    from ..transport import call_provider

    try:
        st = int(status)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ca_dpd",
                       detail=f"status must be one of the Read Me closed set {sorted(_STATUS)} (1=Approved 2=Marketed 3=Cancelled Pre-Market 4=Cancelled Post-Market 6=Dormant), got \"{status}\"")
    if st not in _STATUS:
        raise SdkError("usage_error", provider="ca_dpd",
                       detail=f"status must be one of {sorted(_STATUS)} ({'; '.join(f'{k}={v}' for k, v in sorted(_STATUS.items()))}) — an unknown value is silently ignored upstream and dumps the whole 15MB register, got \"{status}\"")
    params = {"lang": "en", "type": "json", "status": st}
    r = call_provider(provider, "drug_products", params, cache=cache, no_cache=no_cache)
    out = drug_products_from_upstream(r["data"], st)
    rows = _slice(out["rows"], limit, skip)
    return {**out, "rows": rows, "count": len(rows), "params": params, "_meta": r}
