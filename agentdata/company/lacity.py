"""lacity — Los Angeles Office of Finance active-business tax registrations
(data.lacity.org Socrata; keyless). Provider id deliberately NOT 'la_' — 'LA' is ISO-3166
alpha-2 Laos and the SDK prefixes are country codes; city faces take the host/locality stem
(chi_bacp/nyc_dcwp/lacity — the 0.3.48 tx_/wa_ state-axis ruling extended).

company roster (admitted in 0.3.49, probes tmp/probe-us-citylicense-0349/; research evidence
tmp/probe-us-citylicense/, harvest-side recipe in the us-city-license volume, 册 328).
Shape verified 2026-11-05: GET /resource/6rrh-rzua.json?$limit= → array straight out
(632,799-row corpus — the Listing of Active Businesses, business-tax registration register:
NOT a license book; a location can pre-register with a future location_start_date).
Row key and profile: location_account = account-location-segment compact key
('0000000108-0001-3' — the ONLY join key; no DUNS/registration-number column exists),
business_name, street_address/city/zip_code + location_description composite, the
mailing_* family present-only (null omitted per row — Socrata house behavior), naics +
primary_naics_description (the THREE-CITY batch's only industry-code face — Chicago/NYC
carry license taxonomies, LA carries NAICS), council_district, location_start_date, and
location_1 = Socrata point object (lat/long/human_address triple). :@computed_region_*
system columns pass through verbatim with a per-row COUNT DRIFT (probed 5 vs 6 — a row in an
extra region gains a column; documented, not projected away).

Socrata $-param verbatim channel (same contract as chi_bacp/nyc_dcwp/tx_tdlr/wa_doh/co_rues):
$where raw SoQL / $limit 1-500 / $offset>=0 / $order rejects NULLS; no total echo, none faked
(corpus count probed separately via $select=count).
TTL: 7 days (rolling register, no pinned cadence — conservative); politeness 1 rps.
"""
from ..errors import SdkError

provider = {
    "id": "lacity",
    "baseUrl": "https://data.lacity.org",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "registrations": {"path": "/resource/6rrh-rzua.json"},  # Socrata $limit/$offset/$where/$order
    },
    "ttl": {"registrations": 7 * 24 * 3600},
}

CORPUS = 632799  # 2026-11-05 probe (matches the research volume)


def registrations_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, params, _meta} (Socrata echoes no total; computed-region column
    count drifts per row 5↔6 — verbatim, not projected)."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20  # explicit None check — 0 swallowed by or is the 0.2.10-style pit
    if not 1 <= size <= 500:
        raise SdkError("usage_error", provider="lacity",
                       detail=f"limit must be 1-500 (politeness cap), got {limit!r}")
    off = int(offset) if offset is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="lacity", detail=f"offset must be >=0, got {offset!r}")
    params = {"$limit": size, "$offset": off}
    w = str(where or "").strip() or None
    if w:
        params["$where"] = w
    o = str(order or "").strip() or None
    if o:
        params["$order"] = o
    r = call_provider(provider, "registrations", params, cache=cache, no_cache=no_cache)
    return {"rows": r["data"] or [], "count": len(r["data"] or []), "limit_applied": size,
            "params": params, "_meta": r}
