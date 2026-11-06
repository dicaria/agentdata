"""nyc_dcwp — NYC DCWP license register (data.cityofnewyork.us Socrata; keyless).

company roster (admitted in 0.3.49, probes tmp/probe-us-citylicense-0349/; research evidence
tmp/probe-us-citylicense/, harvest-side recipe in the us-city-license volume, 册 328 — city
axis, chi_bacp/lacity the siblings).
Shape verified 2026-11-05: GET /resource/w7w3-xahh.json?$limit= → array straight out
(72,452-row corpus — DCWP's own applications+licenses book, NOT the padlocked licensed-
locations table; the research volume pinned the ~2.5-month refresh lag → TTL 7d).
Row key and profile: license_nbr = number+agency-suffix ('0016371-DCA') over business_unique_id
('BA-1322274-2022' — the enterprise-level anchor, year-sufficed), business_category x
license_type (Premises/Individual duality — the ~50 DCWP categories ride in the data),
license_status (Active/Surrendered/Expired family — Surrendered rows STAY in the register,
history not just actives), license_creation_date → lic_expir_dd lifecycle pair (floating
ISO-with-.000 timestamps, Socrata house style), contact_phone, the split address family
(address_type/address_building/address_street_name/address_secondary_name present-only/
address_city/address_state/address_zip/address_borough — borough as its own column, Manhattan
spelled out), and the NYC planning geo stack: community_board (e.g. '105') / council_district /
bin (building) / bbl (borough-block-lot tax parcel '1012940033' — bbl/nta/census join to the
city's own layers) / nta ('MN17') / census_tract / census_block_2010_ / lat/lon. No
:@computed_region_* columns on this host — the three-column geo stack IS the projection.

Socrata $-param verbatim channel (same contract as chi_bacp/lacity/tx_tdlr/wa_doh/co_rues):
$where raw SoQL / $limit 1-500 / $offset>=0 / $order rejects NULLS; no total echo, none faked
(corpus count probed separately via $select=count).
TTL: 7 days (research-pinned ~2.5-month refresh lag; politeness 1 rps).
"""
from ..errors import SdkError

provider = {
    "id": "nyc_dcwp",
    "baseUrl": "https://data.cityofnewyork.us",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "licenses": {"path": "/resource/w7w3-xahh.json"},  # Socrata $limit/$offset/$where/$order
    },
    "ttl": {"licenses": 7 * 24 * 3600},
}

CORPUS = 72452  # 2026-11-05 probe (matches the research volume)


def licenses_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, params, _meta} (Socrata echoes no total; Surrendered rows stay —
    history, not actives-only)."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20  # explicit None check — 0 swallowed by or is the 0.2.10-style pit
    if not 1 <= size <= 500:
        raise SdkError("usage_error", provider="nyc_dcwp",
                       detail=f"limit must be 1-500 (politeness cap), got {limit!r}")
    off = int(offset) if offset is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="nyc_dcwp", detail=f"offset must be >=0, got {offset!r}")
    params = {"$limit": size, "$offset": off}
    w = str(where or "").strip() or None
    if w:
        params["$where"] = w
    o = str(order or "").strip() or None
    if o:
        params["$order"] = o
    r = call_provider(provider, "licenses", params, cache=cache, no_cache=no_cache)
    return {"rows": r["data"] or [], "count": len(r["data"] or []), "limit_applied": size,
            "params": params, "_meta": r}
