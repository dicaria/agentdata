"""wa_doh — Washington State Department of Health Health Care Provider Credential Data
(data.wa.gov Socrata; keyless).

company roster (admitted in 0.3.48, probes tmp/probe-us-state-license-0348/ + research evidence
tmp/probe-us-statelicense/; harvest-side recipe in the us-state-license volume, 册 323).
Shape verified 2026-11-05: GET /resource/qxh8-f4bd.json?$limit= → array straight out
(2,468,860-row corpus as of the 2026-11-05 probe — the register batch-refreshed past the research
probe's 2,468,859 by one row the same day; 11 columns, all text-typed — dates arrive MM/DD/YYYY).
Row key and profile: credentialnumber hard key in the registrar's own grammar
('RN.RN.61687583.MSL' — profession.board.number suffix family; the bare 'RN.RN.00079891' 1983-vintage
rows predate the suffix) + lastname/firstname/middlename (practitioner names in a public
credential register are collectable — no_brreg roller precedent) + credentialtype
('Registered Nurse License' 377,103 / 'Nursing Assistant Registration' 296,694 / …) + status
(Expired 1,518,554 / Active 564,934 / Closed / Superseded / Pending / …) + the three-axis date
family firstissuedate/lastissuedate/expirationdate (+ceduedate continuing-education due).

**PII gate (red line, pinned by the research probe)**: the birthyear column is stripped from every
row before it leaves this module — birth year + full name is exactly the combination the recipe
rules out for person-level entity building (LEIE-volume precedent). The face keeps names and
credential facts; it does not keep birth years.
Socrata $-param verbatim channel (same contract as co_rues/ny_open_data/tx_tdlr).
TTL: 24 hours (daily-refreshed register); politeness 1 rps (conservative tier for anonymous Socrata).
"""
from ..errors import SdkError

provider = {
    "id": "wa_doh",
    "baseUrl": "https://data.wa.gov",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "credentials": {"path": "/resource/qxh8-f4bd.json"},  # Socrata $limit/$offset/$where/$order
    },
    "ttl": {"credentials": 24 * 3600},
}

# 2026-11-05 facet probe (2,468,860 rows — one past the research probe the same day; daily drift)
CORPUS = 2468860
TOP_TYPES = (("Registered Nurse License", 377103), ("Nursing Assistant Registration", 296694),
             ("Nursing Assistant Certification", 259915))

# PII red-line column: birth year — name columns kept, birth year always stripped (research-probe red line)
_PII_COLUMNS = ("birthyear",)


def _strip_pii(row):
    # non-mutating (the caller's rows — cached payloads included — stay untouched; a fresh
    # dict per row, the birth-year keys simply never survive the shaping)
    return {k: v for k, v in row.items() if k not in _PII_COLUMNS}


def credentials_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, params, _meta} (Socrata echoes no total; birthyear stripped from every row)."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20  # explicit None check — 0 swallowed by or is the 0.2.10-style pit
    if not 1 <= size <= 500:
        raise SdkError("usage_error", provider="wa_doh",
                       detail=f"limit must be 1-500 (politeness cap), got {limit!r}")
    off = int(offset) if offset is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="wa_doh", detail=f"offset must be >=0, got {offset!r}")
    params = {"$limit": size, "$offset": off}
    w = str(where or "").strip() or None
    if w:
        params["$where"] = w
    o = str(order or "").strip() or None
    if o:
        params["$order"] = o
    r = call_provider(provider, "credentials", params, cache=cache, no_cache=no_cache)
    data = [_strip_pii(x) for x in (r["data"] or [])]
    return {"rows": data, "count": len(data), "limit_applied": size, "params": params, "_meta": r}
