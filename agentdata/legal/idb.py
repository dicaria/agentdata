"""idb — Inter-American Development Bank sanctioned-firms roster provider (data.iadb.org CKAN DataStore; keyless).

legal debarment-roster face (0.3.21; admitted 2026-11-02, probed tmp/probe-debar-0321). Shape measured 2026-11-02:
GET /api/action/datastore_search?resource_id=cd0bd9ac-18c6-44bc-8592-9be468c2efd9&… → CKAN envelope
{result: {records[], total}} — **live total 1,343 rows** (the census-era 2,603 counted cumulative history; the
live DataStore holds the current register). Rows carry 13 columns verbatim: _id / Title (firm or individual name) /
Entity (Firm/Individual) / Nationality / Country (a **multi-country cell exists**: " Kenya, United Republic of
Tanzania, Zambia" — and values carry leading spaces, trimmed at the mapping layer) / From~To (**"Ongoing" or a
datetime**; From arrives as "2009-07-10 00:00:00.000000000" nanosecond text, kept verbatim) / Prohibited Practice
("Fraud, Extortion" — the violation family) / Source (**"IDB" or the cross-debarment marker "ADB cross debarment"
/ "WBG cross debarment"**) / "Tipo de sancion del BID" (Spanish column = the sanction type, "Debarment") /
IDB Sanction Source (SCOM = Sanctions Committee) / Other Name.
Query semantics (verified live 2026-11-02): q = full-text across all fields (returns a rank); filters = JSON
field→value **exact** match (e.g. {"To": "Ongoing"}); sort = "From desc" style; offset paging; include_total=true
echoes the exact total. The plain agentdata UA passes (no UA gate).
TTL: 24h; polite tier 0.5 rps (conservative pick; the CKAN publishes no quota).
"""
import json

from ..errors import SdkError

provider = {
    "id": "idb",
    "baseUrl": "https://data.iadb.org",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "debarred": {"path": "/api/action/datastore_search", "timeoutMs": 30000},
    },
    "ttl": {"debarred": 24 * 3600},
}

_RESOURCE_ID = "cd0bd9ac-18c6-44bc-8592-9be468c2efd9"  # the "Dataset of Sanctioned firms and individuals" resource


def rows_from_upstream(data):
    """CKAN result → sanction rows (pure function; the 13 upstream columns verbatim, string values trimmed —
    the register ships leading spaces in Country/Prohibited Practice, measured 2026-11-02)."""
    result = (data or {}).get("result") or {}
    rows = []
    for r in result.get("records") or []:
        row = {}
        for k, v in r.items():
            row[k] = v.strip() if isinstance(v, str) else v
        rows.append(row)
    return rows, result.get("total")


def debarred_entities_raw(q=None, *, filters=None, limit=20, offset=0, sort=None, cache=None, no_cache=False):
    """→ {rows, total, limit_applied, offset, params, _meta} (server-side search; include_total=true always sent).

    q = full-text across all fields (upstream param verbatim); filters = JSON field→value exact-match dict in
    JSON text form (upstream param verbatim — {"To": "Ongoing"}, {"Entity": "Firm"}); limit 1-100 politeness
    cap; offset paging; sort = "From desc" style (upstream param verbatim)."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="idb",
                       detail=f"limit must be 1-100 (politeness cap), got '{limit}'")
    off = int(offset) if offset is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="idb", detail=f"offset must be ≥0, got '{offset}'")
    if isinstance(filters, str):  # the CLI face hands us JSON text — normalize to the dict channel
        try:
            filters = json.loads(filters) if filters.strip() else None
        except ValueError:
            raise SdkError("usage_error", provider="idb",
                           detail="filters must be a JSON object of field→value exact matches, "
                                  'e.g. \'{"To": "Ongoing"}\'')
    if filters is not None and not isinstance(filters, dict):
        raise SdkError("usage_error", provider="idb",
                       detail="filters must be dict-shaped (field→value exact match), e.g. {\"Entity\": \"Firm\"}")
    qq = str(q or "").strip() or None
    ss = str(sort or "").strip() or None
    params = {"resource_id": _RESOURCE_ID, "limit": size, "offset": off, "include_total": "true"}
    if qq:
        params["q"] = qq
    if filters:
        params["filters"] = json.dumps(filters, ensure_ascii=False)
    if ss:
        params["sort"] = ss
    r = call_provider(provider, "debarred", params, cache=cache, no_cache=no_cache)
    rows, total = rows_from_upstream(r["data"])
    return {"rows": rows, "total": total, "limit_applied": size, "offset": off,
            "params": params, "_meta": r}
