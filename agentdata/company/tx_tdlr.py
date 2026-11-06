"""tx_tdlr — Texas Department of Licensing and Regulation All Licenses (data.texas.gov Socrata; keyless).

company roster (admitted in 0.3.48, probes tmp/probe-us-state-license-0348/ + research evidence
tmp/probe-us-statelicense/; harvest-side recipe in the us-state-license volume, 册 323).
Shape verified 2026-11-05: GET /resource/7358-krk7.json?$limit= → array straight out (966,778-row
corpus, 26 columns in the view — 18 real + 8 :@computed_region_* system columns; Socrata omits null
fields per row, so a bare A/C Technician row ships 9 keys while an establishment row ships the
business_address/telephone family).
Row key and profile: license_type x license_number (registry key, e.g. 'A/C Technician' x 2716) +
business_name/owner_name (both present — the establishment vs individual duality rides in the data,
not the schema) + business_county + license_subtype (AE apprentice/REG registration/CER
certificate/OP operator family) + license_expiration_date_mmddccyy (MM/DD/YYYY as the column name
advertises — parsed only for display, shipped verbatim) + continuing_education_flag.
~40 license types; top by rows: Apprentice Electrician 283,425 / Cosmetology Operator 198,702 /
Cosmetology Manicurist 71,351 / A/C Technician 61,248 (facet probe 2026-11-05).
rowsUpdatedAt ≈2026-10-18 — TDLR batch-refreshes rather than daily.

Socrata $-param verbatim channel (same contract as co_rues/ny_open_data): $where raw SoQL passthrough /
$limit 1-500 / $offset>=0 / $order rejects NULLS; no total echo, none faked (corpus count probed
separately via $select=count).
TTL: 7 days (batch-refreshed register); politeness 1 rps (conservative tier for anonymous Socrata).
"""
from ..errors import SdkError

provider = {
    "id": "tx_tdlr",
    "baseUrl": "https://data.texas.gov",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "licenses": {"path": "/resource/7358-krk7.json"},  # Socrata $limit/$offset/$where/$order
    },
    "ttl": {"licenses": 7 * 86400},
}

# 2026-11-05 facet probe (count stable since the research probe same day)
CORPUS = 966778
TOP_TYPES = (("Apprentice Electrician", 283425), ("Cosmetology Operator", 198702),
             ("Cosmetology Manicurist", 71351), ("A/C Technician", 61248))


def licenses_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, params, _meta} (Socrata echoes no total; system :@computed_region_* columns are
    not requested and naturally absent from unprojected rows when null)."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20  # explicit None check — 0 swallowed by or is the 0.2.10-style pit
    if not 1 <= size <= 500:
        raise SdkError("usage_error", provider="tx_tdlr",
                       detail=f"limit must be 1-500 (politeness cap), got {limit!r}")
    off = int(offset) if offset is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="tx_tdlr", detail=f"offset must be >=0, got {offset!r}")
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
