"""us_fmcsa — FMCSA Motor Carrier Management Information Company Census (data.transportation.gov Socrata; keyless).

company roster (0.3.51; admitted from research 册 288 us-fmcsa-census, probed live 2026-11-09,
tmp/probe-sdk0350/l5/ p05-p07). The Company Census File az4n-8mr2 is the full-history US motor
carrier universe — active AND out-of-service, 4,528,322 rows live 2026-11-09 ($select=count(*);
up from the 2026-10 research probe's 4,526,044). The audit's ~400k estimate was the active face;
the full-history register is an order of magnitude bigger.

Keys and profile (live row, dot 963305 = WINSUPPLY SALIDA CO CO): dot_number is the hard key of
the US transport-compliance universe (CSA/SMS join key); status_code is the lifecycle (A active
verified live); dun_bradstreet_no is the rare official DUNS cross-key (whole-corpus join into the
D&B sphere — mind its "0" sentinel values); dual address blocks phy_* vs carrier_mailing_* (this
carrier ships CO street, OH mail); company_officer_1/2 ride verbatim (public-register precedent);
fleet trio truck_units/power_units/bus_units + mcs150_mileage(year) + hm_ind hazmat + crgo_* cargo
flags + classdef; email_address present on this row. The catalog advertises ~58 columns but
Socrata omits null fields per row — a populated row ships 53 keys here, unrated carriers simply
lack safety_rating/safety_rating_date (they ride in the view, appear only when set).

Socrata $-param verbatim channel (same contract as tx_tdlr/co_rues): $where raw SoQL passthrough /
$limit 1-500 / $offset>=0 / $order rejects NULLS; no total echo, none faked (corpus count probed
separately via $select=count(*)). Deterministic forms verified live: dot_number='963305' (exact)
and upper(legal_name) like '%SCHNEIDER%' (3 rows). Walk-away: sibling dataset 4a2k-zf79 (Motor
Carrier Registrations-Census Files) is a 403 dead single-dataset — az4n is the live set; SMS Input
kjg3-diqy is the sibling input face (not this face).
TTL: 7 days (batch-refreshed census); politeness 1 rps (conservative tier for anonymous Socrata).
"""
from ..errors import SdkError

provider = {
    "id": "us_fmcsa",
    "baseUrl": "https://data.transportation.gov",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "carriers": {"path": "/resource/az4n-8mr2.json"},  # Socrata $limit/$offset/$where/$order
    },
    "ttl": {"carriers": 7 * 86400},
}

# 2026-11-09 live count probe (p07; research probe 2026-10 counted 4,526,044)
CORPUS = 4528322


def carriers_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, params, _meta} (Socrata echoes no total; rows are the raw
    census records — null fields absent per row, so key sets differ between carriers)."""
    from ..transport import call_provider

    size = None
    if limit is not None:
        try:
            size = int(limit)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="us_fmcsa",
                           detail=f"limit must be an integer 1-500, got {limit!r}")
    if size is None:
        size = 20  # explicit None check — 0 swallowed by or is the 0.2.10-style pit
    if not 1 <= size <= 500:
        raise SdkError("usage_error", provider="us_fmcsa",
                       detail=f"limit must be 1-500 (politeness cap), got {limit!r}")
    off = 0
    if offset is not None:
        try:
            off = int(offset)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="us_fmcsa",
                           detail=f"offset must be an integer >=0, got {offset!r}")
    if off < 0:
        raise SdkError("usage_error", provider="us_fmcsa", detail=f"offset must be >=0, got {offset!r}")
    params = {"$limit": size, "$offset": off}
    w = str(where or "").strip() or None
    if w:
        params["$where"] = w
    o = str(order or "").strip() or None
    if o:
        params["$order"] = o
    r = call_provider(provider, "carriers", params, cache=cache, no_cache=no_cache)
    return {"rows": r["data"] or [], "count": len(r["data"] or []), "limit_applied": size,
            "params": params, "_meta": r}
