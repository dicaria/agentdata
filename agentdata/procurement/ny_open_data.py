"""ny_open_data — New York State open data Socrata three-face provider (data.ny.gov; keyless).

procurement register (0.3.6 twin faces + 0.3.12 OGS third face; shapes verified by first-hand live probing). Probed live 2026-10-29/30:
GET /resource/ehig-g5x3.json?$limit=2 → [rows…25 cols] (ABO state-authority contracts **275,763 rows**)
GET /resource/twsw-2mqa.json?$limit=2 → [rows…27 cols] (MTA procurements **107,503 rows**)
GET /resource/rb9h-9fit.json?$limit=1 → [rows…7 cols] (OGS design & construction payments **69,221 rows**)
  —— Socrata emits a bare array with no total echo (same contract as co_secop: page via $offset, probe the
  full corpus separately with $select=count).
ABO row (Authorities Budget Office state-authority universe): authority_name (buyer authority) × vendor_name+
vendor_address_1/city/state/postal_code/country (**name+full address — no UEI/DUNS, name-walk identification**) +
contract_amount/amount_expended_for_fiscal_year/amount_expended_to_date/
current_or_outstanding_balance four value columns + award_date/begin_date/renewal_date/
fiscal_year_end_date date family + status/type_of_procurement/award_process/
number_of_bids_or_proposals_received + solicited_mwbe/vendor_is_a_mwbe/
nys_or_foreign_business_enterprise procurement-preference flag family.
MTA row (Metropolitan Transportation Authority): same skeleton + end_date/transaction_number/number_of_mwbe_proposals/
vendor_is_nys_or_fbe (no authority_name — buyer is always the MTA).
OGS row (Office of General Services design & construction payments, probed live 2026-10-30): contractnumber/
vendor/typeofservice/paymentamount/fiscalyear (a "2014-2015"-form string)/quarter/county — seven columns,
buyer always OGS, **no address columns** (name-walk single key; contractnumber+vendor+quarter pin a payment row).
Socrata $-param verbatim channel shares the co_secop contract: $where raw SoQL verbatim pass-through/$limit/$offset/$order;
$order does not take NULLS syntax. Socrata float-coercion pitfall on record: without a $select projection
transaction_number comes back in scientific-notation form — the row face returns it as upstream does; when exact
numeric keys are needed, narrow with --order/--where and probe separately.
TTL: contract/procurement rows drift slowly with status — 24h; payment rows are historical fact — 7d;
polite tier 1 rps (conservative pick for anonymous Socrata).
"""
from ..errors import SdkError

provider = {
    "id": "ny_open_data",
    "baseUrl": "https://data.ny.gov",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "abo_contracts": {"path": "/resource/ehig-g5x3.json"},      # Socrata $limit/$offset/$where/$order
        "mta_procurements": {"path": "/resource/twsw-2mqa.json"},
        "ogs_dc_payments": {"path": "/resource/rb9h-9fit.json"},
    },
    "ttl": {"abo_contracts": 24 * 3600, "mta_procurements": 24 * 3600,
            "ogs_dc_payments": 7 * 24 * 3600},
}


def _socrata_raw(op, where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """Socrata $-channel, same contract (co_secop-shaped): where=$where raw SoQL/limit 1-500/offset≥0/order=column [ASC|DESC]."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20  # test None explicitly — 0 swallowed by `or` into the default is the same-shaped 0.2.10 pitfall
    if not 1 <= size <= 500:
        raise SdkError("usage_error", provider="ny_open_data",
                       detail=f"limit must be 1-500 (polite tier), got '{limit}'")
    off = int(offset) if offset is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="ny_open_data", detail=f"offset must be ≥0, got '{offset}'")
    params = {"$limit": size, "$offset": off}
    w = str(where or "").strip() or None
    if w:
        params["$where"] = w
    o = str(order or "").strip() or None
    if o:
        params["$order"] = o
    r = call_provider(provider, op, params, cache=cache, no_cache=no_cache)
    data = r["data"] or []
    return {"rows": data, "count": len(data), "limit_applied": size, "params": params, "_meta": r}


def abo_contracts_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, params, _meta} (Socrata sends no total echo)."""
    return _socrata_raw("abo_contracts", where, limit=limit, offset=offset, order=order,
                        cache=cache, no_cache=no_cache)


def mta_procurements_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ same as above (buyer is always the MTA — rows carrying no authority_name column is the upstream shape, not missing data)."""
    return _socrata_raw("mta_procurements", where, limit=limit, offset=offset, order=order,
                        cache=cache, no_cache=no_cache)


def ogs_dc_payments_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ same as above (OGS design & construction payments, 69,221 rows — buyer is always OGS; rows carry no address columns, name-walk identity)."""
    return _socrata_raw("ogs_dc_payments", where, limit=limit, offset=offset, order=order,
                        cache=cache, no_cache=no_cache)
