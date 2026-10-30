"""lda — US LDA lobbying-disclosure API v1 provider (company name → lobbying filing face; keyless).

The official OpenAPI (lda.gov/api/openapi/v1/) is anonymously usable but rate-limited harder: the ToS anonymous
tier is 15/min (API key 120/min) — the 0.2.5 fix runs at 14/60 rps with burst 1 (the earlier 0.5 rps = 30/min
exceeded the limit by 2×; compliance fixed; recorded as an exception in docs/domains/rate-limits.md).
Channel note (real-machine Python test 2026-10-20): lda.gov fronts with Akamai gating on the **client stack** —
Node undici always gets 403 and needs the curl subprocess channel; **Python urllib connects directly with 200**
(machine-local probe: filings count=70,545), so the default urllib path is used
(gating is stack-dependent — verify per stack on the real machine, do not copy the transport declaration from the Node side).
DRF requires the trailing slash (without it, 301). Amount pitfall: income/expenses only carry values on
quarterly reports (Q1-Q4); registration filings (RR/RA) are always null.
page_size is hard-clamped to 25: verified 2026-10-26, page_size 26/50/100/500 all silently return only 25 rows
(an earlier note claiming "no published ceiling, 100 = polite cap" was a mis-record — the old verb face's
limit_applied=100 never actually got more than 25 rows); paging goes through the page param (true offset paging,
page=2 has a different first row and next/previous are echoed back, verified 2026-10-26).
"""
from ..errors import SdkError

provider = {
    "id": "lda",
    "baseUrl": "https://lda.gov/api/v1",
    "rate": {"rps": 14 / 60, "burst": 1},  # anonymous tier 15/min, hugging the line (quota semantics): the upper bound in any 60s window is 1+14=15≤15 (burst counts against the budget)
    "ops": {
        "filings": {"path": "/filings/"},                       # DRF trailing slash; params: registrant_name|client_name|filing_year + page_size/ordering
        "filing": {"path": "/filings/{filing_uuid}/", "notFound": [404]},
        "registrant": {"path": "/registrants/{id}/", "notFound": [404]},  # id=house_registrant_id (official key)
        "client": {"path": "/clients/{id}/", "notFound": [404]},          # id=client_id
    },
    "ttl": {"filings": 7 * 86400, "filing": 7 * 86400, "registrant": 30 * 86400, "client": 30 * 86400},
}


def search_filings(client_name=None, registrant_name=None, filing_year=None, *,
                   limit=20, cache=None, no_cache=False):
    """→ {total, rows[], _meta}; the client=lobbied company / registrant=lobbying firm two-name face.
    Amounts are fetched per filing_type (only quarterly reports carry them) — do not judge liveness by
    "has an amount or not"."""
    from ..transport import call_provider
    from datetime import date

    filters = {}
    if registrant_name:
        filters["registrant_name"] = str(registrant_name).strip()
    if client_name:
        filters["client_name"] = str(client_name).strip()
    if filing_year is not None:
        y = int(filing_year)
        if y < 1999 or y > date.today().year + 1:
            raise SdkError("usage_error", provider="lda", detail=f"filing_year must be a year from 1999 on, got \"{filing_year}\"")
        filters["filing_year"] = y
    if not filters:
        raise SdkError("usage_error", provider="lda",
                       detail="search_filings requires registrant_name / client_name / filing_year — at least one of the three")
    size = min(max(1, int(limit or 20)), 100)  # the verb face keeps the inherited behaviour (upstream hard-clamps to 25, see the module header — overturned 2026-10-26)
    r = call_provider(provider, "filings", {
        **filters,
        "page_size": size,
        "ordering": "-dt_posted",
    }, cache=cache, no_cache=no_cache)
    return {**_rows_from(r["data"]), "total": (r["data"] or {}).get("count"),
            "limit_applied": size, "_meta": r}


def _rows_from(data):
    """Upstream response → {"rows": [...]} (pure function, offline-testable; shared by both faces)."""
    return {"rows": [{
        "filing_uuid": f.get("filing_uuid"),
        "filing_type": f.get("filing_type"),           # RR registration / Q1-Q4 quarterly report (amounts only on quarterly reports)
        "filing_type_display": f.get("filing_type_display"),  # upstream human-readable type (reconciled and added in the 2026-10-21 audit)
        "filing_year": f.get("filing_year"),
        "period": f.get("filing_period_display") or f.get("filing_period"),
        "dt_posted": f.get("dt_posted"),
        "income": f.get("income"),                     # lobbying income (quarterly reports)
        "expenses": f.get("expenses"),                 # lobbying expenses (quarterly reports)
        "termination_date": f.get("termination_date"),  # termination filing date (Q Termination reports)
        "registrant": ({"house_registrant_id": f["registrant"].get("house_registrant_id"),
                        "name": f["registrant"].get("name"), "state": f["registrant"].get("state")}
                       if f.get("registrant") else None),
        "client": ({"client_id": f["client"].get("client_id"), "name": f["client"].get("name"),
                    "state": f["client"].get("state"), "country": f["client"].get("country")}
                   if f.get("client") else None),
        "issues": [a.get("general_issue_code_display") or a.get("general_issue_code")
                   for a in f.get("lobbying_activities") or []
                   if a.get("general_issue_code_display") or a.get("general_issue_code")],
        "document_url": f.get("filing_document_url"),  # direct link to the filing PDF/print view
    } for f in (data or {}).get("results") or []]}


def search_raw(client_name=None, registrant_name=None, filing_year=None, *,
               limit=20, page=None, ordering="-dt_posted", cache=None, no_cache=False):
    """Flat-panel low-level face: client_name/registrant_name/filing_year/page_size/ordering/page all go through
    with verbatim names.

    → {total, rows[], limit_applied, params, _meta}. limit wall 1-25: verified 2026-10-26,
    page_size 26/50/100/500 all silently return only 25 rows (upstream hard clamp); page through page (true offset paging).
    client_name (the lobbied company) and registrant_name (the lobbying firm) can be combined (upstream ANDs them)."""
    from ..transport import call_provider
    from datetime import date

    params = {}
    if registrant_name:
        params["registrant_name"] = str(registrant_name).strip()
    if client_name:
        params["client_name"] = str(client_name).strip()
    if filing_year is not None:
        y = int(filing_year)
        if y < 1999 or y > date.today().year + 1:
            raise SdkError("usage_error", provider="lda", detail=f"filing_year must be a year from 1999 on, got \"{filing_year}\"")
        params["filing_year"] = y
    if not params:
        raise SdkError("usage_error", provider="lda",
                       detail="search_raw requires client_name / registrant_name / filing_year — at least one of the three"
                              " (local safety wall: enumerating the full 70,545+ row corpus belongs to the batch line)")
    lim = int(limit or 20)
    if not 1 <= lim <= 25:
        raise SdkError("usage_error", provider="lda",
                       detail=f"limit must be 1-25 (upstream page_size hard clamp: verified 2026-10-26, "
                              f"26/50/100/500 silently return only 25 rows), page through page — got \"{limit}\"")
    params.update({"page_size": lim, "ordering": str(ordering or "-dt_posted")})
    if page is not None:
        params["page"] = max(1, int(page))
    r = call_provider(provider, "filings", params, cache=cache, no_cache=no_cache)
    return {**_rows_from(r["data"]), "total": (r["data"] or {}).get("count"),
            "limit_applied": lim, "params": params, "_meta": r}


def lookup_registrant(registrant_id, *, cache=None, no_cache=False):
    """→ the lobbying firm's master record (house_registrant_id official key, normalized)."""
    from ..transport import call_provider

    try:
        n = int(registrant_id)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        raise SdkError("usage_error", provider="lda",
                       detail=f"registrant id must be a positive integer (house_registrant_id), got \"{registrant_id}\"")
    r = call_provider(provider, "registrant", {"id": n}, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    address = ", ".join(x for x in (d.get("address_1"), d.get("city"), d.get("state"), d.get("country")) if x)
    return {
        "house_registrant_id": d.get("house_registrant_id") or n,
        "name": d.get("name"),
        "description": d.get("description"),
        "address": address or None,
        "_meta": r,
    }
