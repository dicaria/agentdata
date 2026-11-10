"""ua_nazk — Ukrainian NACP political-party finance portal (politdata.nazk.gov.ua /api/v2; keyless).

legal party-finance faces (0.3.50; admitted 2026-11-09, probed tmp/probe-sdk0350/ + the
2026-11-05 recipe round tmp/probe-us-wcluster/). The SDK's first UA jurisdiction. The National
Agency on Corruption Prevention's politdata portal (NOT data.nazk.gov.ua — the declarations
repository host is egress-blocked from this network, watched separately): 321 registered parties
(count echo, live 2026-11-09) with the register's own keys — code (the party's registration
number), head_info (named leadership), register_address — plus each party's report inventory
(2021→2026Q3; rows embed public_summary, the aggregated receipts/expenses the upstream computed,
zero extra calls).

**All-POST contract (pinned live 2026-11-05 + 2026-11-09)**: every endpoint answers GET with 404
— the channel is POST with a {page, pageSize, draw} JSON body (draw echoes the datatables shape,
any int works). **pageSize server-clamp**: the upstream silently returns its own preferred page
size (send 10 → 20 come back) — the face sends the asked size verbatim and reports what came
back (count + len(list)); never promise the asked size. results = {list, count} where count is
the register total (321), not the page size.

The per-report payment layers (nine asset faces, eight payment types — monetary_contributions
carries payer_name/payer_type with the payer_code field masked "[конфіденційна інформація]"
upstream) ride the report ids this face returns; they stay a follow-up face.
"""
from ..errors import SdkError

provider = {
    "id": "ua_nazk",
    "baseUrl": "https://politdata.nazk.gov.ua",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "parties": {"path": "/api/v2/parties", "method": "POST", "idempotent": True, "timeout": 60.0},
        "party_reports": {"path": "/api/v2/party/{party_id}/reports", "method": "POST",
                          "idempotent": True, "timeout": 60.0},
    },
    "ttl": {"parties": 86400, "party_reports": 86400},
}

PAGE_SIZE_DEFAULT = 20   # the upstream's own preferred page size (what a 10-ask actually returns)


def _post(op, params, cache, no_cache):
    """One POST read: params carry the path token (if any) + the {page, pageSize, draw} body."""
    from ..transport import call_provider
    r = call_provider(provider, op, params, cache=cache, no_cache=no_cache)
    res = (r["data"] or {}).get("results") or {}
    return res.get("list") or [], res.get("count"), r


def parties_raw(page=1, limit=PAGE_SIZE_DEFAULT, cache=None, no_cache=False):
    """The party register → {total, page, page_size, count, rows[], params, _meta}.

    Rows verbatim: id (the party uuid — the reports face's key), is_active, code (registration
    number), name, head_info {head_last_name, head_first_name, head_middle_name},
    register_address, contacts. page_size echoes the ASKED size while count/len(rows) carry the
    upstream's clamped reality — read those."""
    p, n = int(page), int(limit)
    if p < 1:
        raise SdkError("usage_error", provider="ua_nazk", detail=f"page is 1-based, got '{page}'")
    if n < 1:
        raise SdkError("usage_error", provider="ua_nazk", detail=f"limit must be ≥1, got '{limit}'")
    body = {"page": p, "pageSize": n, "draw": 1}
    rows, total, r = _post("parties", body, cache, no_cache)
    return {"total": total, "page": p, "page_size": n, "count": len(rows), "rows": rows,
            "params": body, "_meta": r}


def party_reports_raw(party_id, page=1, limit=PAGE_SIZE_DEFAULT, cache=None, no_cache=False):
    """One party's report inventory → {party_id, total, page, page_size, count, rows[], params, _meta}.

    party_id = the party uuid from ua_nazk_parties. Rows verbatim with the embedded public_summary
    (aggregated receipts/expenses per category, sums + row_counts — the zero-extra-call money
    view): id (the report uuid — the key for the follow-up payment faces), report_type (main /
    corrections), year, quarter, signed_date, created_date, is_party_office (regional-office
    reports sit in the same inventory)."""
    if not party_id or not str(party_id).strip():
        raise SdkError("usage_error", provider="ua_nazk",
                       detail="party_id is required (the party uuid from ua_nazk_parties)")
    p, n = int(page), int(limit)
    if p < 1:
        raise SdkError("usage_error", provider="ua_nazk", detail=f"page is 1-based, got '{page}'")
    if n < 1:
        raise SdkError("usage_error", provider="ua_nazk", detail=f"limit must be ≥1, got '{limit}'")
    params = {"party_id": str(party_id).strip()}
    body = {"page": p, "pageSize": n, "draw": 1}
    rows, total, r = _post("party_reports", {**params, **body}, cache, no_cache)
    return {"party_id": params["party_id"], "total": total, "page": p, "page_size": n,
            "count": len(rows), "rows": rows, "params": {**params, **body}, "_meta": r}
