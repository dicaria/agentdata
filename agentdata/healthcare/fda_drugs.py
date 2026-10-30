"""fda_drugs — FDA drug provider, three faces (openFDA drug/drugsfda · drug/ndc · drug/orangebook; keyless).

Wave 10b of the healthcare domain (second batch; row shapes measured 2026-10-29).
The family contract is shared with fda_recalls/shortages: GET /<ep>.json?search=&limit=&skip=&sort=, zero hits = HTTP 404
{"error":{"code":"NOT_FOUND"}} is a legal answer (notFound:[404] → an empty envelope that is not cached).
Probing anchors on 2026-10-29 (field names verified by _exists_, not inferred from the docs):
  drug/drugsfda (29,420 applications): company field = **sponsor_name** (the docs once said applicant_name — overturned by _exists_);
    a row = application_number × products[] × submissions[]; the default sort is the nested key submissions.submission_status_date:desc (measured to sort).
  drug/ndc (NDC catalogue, 138,153+ rows, daily refresh): company field = labeler_name (plus the openfda.manufacturer_name normalization layer);
    marketing_start/end_date + marketing_category + listing_expiration_date are in the columns — **the NSDE endpoint is dead (Cannot GET
    /drug/nsde.json) and its content was merged into this face** (confirmed by probing on wave10b).
  drug/orangebook (48,865 rows, the Orange Book's first API face): company field = products[].application_name/_full_name
    (the licence holder); the RLD/reference_standard flags sit on the row; **it replaces the dead nsde as wave10b's 7th face**.
    applicant/applicant_holder/holder etc. all 404 under _exists_ — the company key only exists inside products[].
Rate limit: a keyless quota shared with fda_recalls/shortages on the same host (polite 2 rps per face, the family total must stay under ~4 rps).
TTL 24h (all three faces refresh on a daily-to-weekly cadence).
"""
from datetime import datetime, timezone

from ..errors import SdkError

provider = {
    "id": "fda_drugs",
    "baseUrl": "https://api.fda.gov",
    "rate": {"rps": 2, "burst": 5},
    "ops": {
        "approvals": {"path": "/drug/drugsfda.json", "notFound": [404]},
        "catalog": {"path": "/drug/ndc.json", "notFound": [404]},
        "orange_book": {"path": "/drug/orangebook.json", "notFound": [404]},
    },
    "ttl": {"approvals": 24 * 3600, "catalog": 24 * 3600, "orange_book": 24 * 3600},
}

# Default sort per face (our default, not the upstream one; drugsfda by latest submission date, ndc by marketing start, the Orange Book by approval date; all measured to sort on 2026-10-29)
_DEFAULT_SORT = {"approvals": "submissions.submission_status_date:desc",
                 "catalog": "marketing_start_date:desc",
                 "orange_book": "approval_date:desc"}


def _approvals_rows(results):
    """drug/drugsfda rows → application dossier rows (pure function, testable offline). Key order verified against the 2026-10-29 probe of drugsfda.exists.json."""
    out = []
    for r in results if isinstance(results, list) else []:
        out.append({
            "application_number": r.get("application_number"),        # NDA/ANDA/BLA number (hub key linking to the Orange Book)
            "sponsor_name": r.get("sponsor_name"),                    # company edge, primary column (the applicant)
            "products": [{"product_number": p.get("product_number"),
                          "brand_name": p.get("brand_name"),
                          "active_ingredients": p.get("active_ingredients"),
                          "dosage_form": p.get("dosage_form"),
                          "route": p.get("route"),
                          "marketing_status": p.get("marketing_status"),
                          "reference_drug": p.get("reference_drug"),
                          "reference_standard": p.get("reference_standard")}
                         for p in (r.get("products") or []) if isinstance(p, dict)],
            "submissions": [{"submission_type": s.get("submission_type"),
                             "submission_number": s.get("submission_number"),
                             "submission_status": s.get("submission_status"),
                             "submission_status_date": s.get("submission_status_date")}
                            for s in (r.get("submissions") or []) if isinstance(s, dict)],
        })
    return out


def _catalog_rows(results):
    """drug/ndc rows → NDC catalogue rows (pure function). The openfda sub-object is kept whole (rxcui/spl_set_id/unii product metadata, no PII)."""
    out = []
    for r in results if isinstance(results, list) else []:
        out.append({
            "product_ndc": r.get("product_ndc"),                      # hub key (links to shortages/recall product_ndcs)
            "brand_name": r.get("brand_name"),
            "generic_name": r.get("generic_name"),
            "labeler_name": r.get("labeler_name"),                    # company edge, primary column (the labeler)
            "dosage_form": r.get("dosage_form"),
            "route": r.get("route"),
            "finished": r.get("finished"),
            "marketing_category": r.get("marketing_category"),
            "marketing_start_date": r.get("marketing_start_date"),    # YYYYMMDD (field merged in from NSDE)
            "marketing_end_date": r.get("marketing_end_date"),
            "listing_expiration_date": r.get("listing_expiration_date"),
            "application_number": r.get("application_number"),
            "product_type": r.get("product_type"),
            "active_ingredients": r.get("active_ingredients"),
            "package_ndcs": [p.get("package_ndc") for p in (r.get("packaging") or [])
                             if isinstance(p, dict) and p.get("package_ndc")],
            "openfda": r.get("openfda"),                              # manufacturer_name/rxcui/spl_set_id/unii
        })
    return out


def _orange_rows(results):
    """drug/orangebook rows → Orange Book rows (pure function). The company key lives inside products[] (the top-level applicant fields all 404 under _exists_)."""
    out = []
    for r in results if isinstance(results, list) else []:
        out.append({
            "approval_date": r.get("approval_date"),                  # YYYYMMDD
            "product_number": r.get("product_number"),
            "products": [{"brand_name": p.get("brand_name"),
                          "active_ingredients": p.get("active_ingredients"),
                          "application_name": p.get("application_name"),          # company edge, primary column (short name of the licence holder)
                          "application_full_name": p.get("application_full_name"), # the company's full name
                          "application_type": p.get("application_type"),           # N/ANDA
                          "application_number": p.get("application_number"),       # hub key linking to drugsfda
                          "reference_listed_drug": p.get("reference_listed_drug"),
                          "reference_standard": p.get("reference_standard"),
                          "marketing_status": p.get("marketing_status"),
                          "dosage_form": p.get("dosage_form"),
                          "route": p.get("route")}
                         for p in (r.get("products") or []) if isinstance(p, dict)],
        })
    return out


_ROWS = {"approvals": _approvals_rows, "catalog": _catalog_rows, "orange_book": _orange_rows}


def search(face, search, *, limit=20, skip=0, sort=None, cache=None, no_cache=False):
    """Born flat: the search expression is passed through verbatim (upstream param names search/limit/skip/sort, zero sugar).
    face ∈ approvals|catalog|orange_book. limit 1-1000 (the openFDA search hard limit, same as shortages measured 1001→400).
    search is required (local safety gate: under a keyless quota a bare full-table query is served by the bulk harvest line).
    → {rows[], total, count, skip, limit_applied, has_more, search, sort, _meta}; zero hits = an empty set that is not cached.
    """
    from ..transport import call_provider

    if face not in provider["ops"]:
        raise SdkError("usage_error", provider=provider["id"],
                       detail=f"face must be approvals|catalog|orange_book, got '{face}'")
    q = str(search or "").strip()
    if not q:
        raise SdkError("usage_error", provider=provider["id"],
                       detail="search requires an expression (e.g. sponsor_name:\"TEVA\" — the keyword field is case-sensitive, so use the form stored in the rows; a bare full-table query is served by the bulk line)")
    size = int(limit) if limit is not None else 20  # 0 is an explicitly bad value (do not let `or` swallow it into the default); the gate below rejects it
    if not 1 <= size <= 1000:
        raise SdkError("usage_error", provider=provider["id"],
                       detail=f"limit must be 1-1000 (the openFDA search hard limit, same as shortages measured on 2026-10-23), got {size}")
    sk = max(0, int(skip or 0))
    so = str(sort).strip() if sort is not None else _DEFAULT_SORT[face]
    params = {"search": q, "limit": size}
    if sk:
        params["skip"] = sk
    if so:
        params["sort"] = so
    try:
        r = call_provider(provider, face, params, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_not_found":
            return {"rows": [], "total": 0, "count": 0, "skip": sk, "limit_applied": size,
                    "has_more": False, "search": q, "sort": so or None,
                    "_meta": {"from_cache": False,
                              "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}}
        raise
    data = r.get("data") or {}
    rows = _ROWS[face](data.get("results"))
    total = (data.get("meta") or {}).get("results", {}).get("total", len(rows))
    return {"rows": rows, "total": total, "count": len(rows), "skip": sk, "limit_applied": size,
            "has_more": total > sk + len(rows), "search": q, "sort": so or None, "_meta": r}
