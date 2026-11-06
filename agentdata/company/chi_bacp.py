"""chi_bacp — Chicago BACP business licenses full history (data.cityofchicago.org Socrata; keyless).

company roster (admitted in 0.3.49, probes tmp/probe-us-citylicense-0349/ + research evidence
tmp/probe-us-citylicense/; harvest-side recipe in the us-city-license volume, 册 328 — the SDK's
first US city-axis faces, tx_tdlr/wa_doh the state axis).
Shape verified 2026-11-05: GET /resource/r5kz-chrr.json?$limit= → array straight out
(1,210,956-row corpus, full history 1997→; payment_date refreshed DAILY — the probe rows carry
2026-11-03 payments and 2026-11-04 issuances).
Row key and profile: id = license_number-expiration compact key ('2993638-20261216') over the
TWO-LEVEL business key — account_number (the enterprise account aggregating across addresses)
x site_number (the address-level site) — plus license_id (the issuance). legal_name x
doing_business_as_name duality, license_code x license_description x business_activity_id x
business_activity (the taxonomy four), application_type (RENEW/ISSUE/C_C/R_E family), the
six-date lifecycle family (application_requirements_complete → payment_date →
license_approved_for_issuance → date_issued → license_start_date → expiration_date),
license_status (AAI = issued; the research volume warns the lifecycle codes are AA/AIN/CAN —
do not guess 'clear' variants, the SoQL filter takes them verbatim), the Chicago geo stack
(ward/precinct/ward_precinct/police_district/community_area(+name)/neighborhood/ssa) and
lat/lon + the Socrata point column. ~40 columns; :@computed_region_* system columns ride the
wire and pass through verbatim in ALL THREE city faces of this batch (chi/nyc/lacity) — the
Socrata verbatim channel contract wins over per-face projection, and the region-column COUNT
itself drifts per row (lacity probed 5 vs 6), so any silent projection would lie about the
corpus shape.

Socrata $-param verbatim channel (same contract as tx_tdlr/wa_doh/co_rues): $where raw SoQL /
$limit 1-500 / $offset>=0 (deep offsets probed to 1,210,000) / $order rejects NULLS; no total
echo, none faked (corpus count probed separately via $select=count).
TTL: 24 hours (payment_date refreshes daily); politeness 1 rps (conservative tier).
"""
from ..errors import SdkError

provider = {
    "id": "chi_bacp",
    "baseUrl": "https://data.cityofchicago.org",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "licenses": {"path": "/resource/r5kz-chrr.json"},  # Socrata $limit/$offset/$where/$order
    },
    "ttl": {"licenses": 24 * 3600},
}

CORPUS = 1210956  # 2026-11-05 probe (matches the research volume)


def licenses_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, params, _meta} (Socrata echoes no total; computed-region system
    columns pass through verbatim — the corpus ships them)."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20  # explicit None check — 0 swallowed by or is the 0.2.10-style pit
    if not 1 <= size <= 500:
        raise SdkError("usage_error", provider="chi_bacp",
                       detail=f"limit must be 1-500 (politeness cap), got {limit!r}")
    off = int(offset) if offset is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="chi_bacp", detail=f"offset must be >=0, got {offset!r}")
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
