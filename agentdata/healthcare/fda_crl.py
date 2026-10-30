"""fda_crl — FDA Complete Response Letters provider (openFDA transparency/crl.json; keyless).

Fourth of the four Wave 10 healthcare faces. A CRL is the closing letter of a drug application review: FDA's formal
"cannot approve" letter for an NDA/ANDA application — a **company × negative-approval event** stream (approval-risk face).
The contract is shared with the shortages/recalls family: GET /transparency/crl.json?search=&limit=&skip=&sort=,
zero hits = HTTP 404 NOT_FOUND is a legal answer (the empty envelope is not cached).
Row shape measured 2026-10-28: company_name:"InnoPharma" → 3 hits;
rows have 13 keys, and **company_rep (the letter recipient's representative) and approver_name (the issuing officer) are both person names and are not returned, nor is text (OCR full-text
noise)** — PII red line + noise reduction (aligned with the PhilGEPS Contact Person / UK IIR personal-face precedents).
TTL 30d (a historical letter face, near-zero increments); rate limit is the polite 2 rps shared by the same-host family.
"""
from datetime import datetime, timezone

from ..errors import SdkError

provider = {
    "id": "fda_crl",
    "baseUrl": "https://api.fda.gov",
    "rate": {"rps": 2, "burst": 5},
    "ops": {
        "search": {"path": "/transparency/crl.json", "notFound": [404]},  # params: search, limit, skip, sort
    },
    "ttl": {"search": 30 * 24 * 3600},
}


def rows_from_upstream(results):
    """Upstream rows → CRL rows (pure function, testable offline; key order verified against the 13 keys seen on 2026-10-28).

    company_rep (the letter recipient's representative) and approver_name (the issuing officer) are both person names and are not returned — PII red line;
    text (OCR full-text noise) is not returned — noise reduction.
    """
    rows = results if isinstance(results, list) else []
    out = []
    for r in rows:
        out.append({
            "company_name": r.get("company_name"),          # company edge, primary column
            "company_address": r.get("company_address"),
            "letter_date": r.get("letter_date"),
            "letter_year": r.get("letter_year"),
            "letter_type": r.get("letter_type"),
            "application_number": r.get("application_number"),  # links to the drugsfda application line
            "approval_status": r.get("approval_status"),    # application outcome after the CRL
            "file_name": r.get("file_name"),                # key of the original letter PDF
            "approver_center": r.get("approver_center"),    # issuing center (organizational side, e.g. CDER)
            "approver_title": r.get("approver_title"),      # issuing officer's title (organizational side)
        })
    return out


def search(search, *, limit=20, skip=0, sort="letter_date:desc", cache=None, no_cache=False):
    """Born flat: the search expression is passed through verbatim (upstream param names search/limit/skip/sort, zero sugar).
    limit 1-1000 (the openFDA search hard limit); search is required (local safety gate: a bare full-table query is served by the bulk harvest line).
    → {rows[], total, count, skip, limit_applied, has_more, search, sort, _meta}; zero hits = an empty set that is not cached.
    """
    from ..transport import call_provider

    q = str(search or "").strip()
    if not q:
        raise SdkError("usage_error", provider=provider["id"],
                       detail="search requires an expression (e.g. company_name:\"Firm Name\"; a bare full-table query is served by the bulk line)")
    size = int(limit) if limit is not None else 20  # 0 is an explicitly bad value (do not let `or` swallow it into the default); the gate below rejects it
    if not 1 <= size <= 1000:
        raise SdkError("usage_error", provider=provider["id"],
                       detail=f"limit must be 1-1000 (the openFDA search hard limit, same as measured for shortages), got {size}")
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
