"""mx_sabg — sanctioned public servants in-force register (datos.gob.mx CKAN DataStore, keyless).

legal public-integrity face (0.3.55; register 387, probed tmp/probe-mx-sat/ p4-p9 + re-verified
live 2026-11-12, tmp/probe-sdk-0355/). Shape measured 2026-11-12:
GET /api/3/action/datastore_search?resource_id=d5da6695-1a3b-4a86-93e2-4297e9463370 → the CKAN
envelope {result: {records[], total}} — the DATASTORE BYPASS: the direct CSV download
(repodatos.atdt.gob.mx, Akamai edgesuite) 403s on every stack, but the CKAN datastore inlines the
whole dataset into JSON, so the register reads keyless through www.datos.gob.mx. Total 435 rows
live (the in-force snapshot; the historical "already-unbarred" archive lives behind the PDN S3
ZenEdge challenge gate and is deliberately NOT this face). Rows carry the 13 columns verbatim:
_id / expediente (case number) / fecha_resolucion / apellido_paterno + apellido_materno + nombre
(the person's three name parts) / autoridad (the adjudicating body) / dependencia (the ministry) /
sancion_impuesta (Inhabilitación) / causa (Abuso de autoridad…) / inicio + fin (THE BARRING
WINDOW — the two dates that make a row "live") / ley (LFRASP, the statute).
Query semantics (verified live 2026-11-12): q = full-text (q=Abuso → 78 rows); filters = JSON
field→value exact match ({"ley": "LFRASP"} → 364); sort = "fecha_resolucion desc" style; offset
paging (offset 430 + limit 10 → the last 5 rows); total rides every response. The plain agentdata
UA passes. PII stance: this is a statutory publication recorded verbatim (name/case/cause), the
ie_sipo/ie_revenue family — no person-level entities are built from it.
TTL: 24h; polite tier 0.5 rps.
"""
import json

from ..errors import SdkError

provider = {
    "id": "mx_sabg",
    "baseUrl": "https://www.datos.gob.mx",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/api/3/action/datastore_search", "timeoutMs": 30000},
    },
    "ttl": {"search": 24 * 3600},
}

_RESOURCE_ID = "d5da6695-1a3b-4a86-93e2-4297e9463370"  # servidores_publicos_sancionados_vigentes (SABG monthly)


def rows_from_upstream(data):
    """CKAN result → servant rows (pure function; the 13 upstream columns verbatim, string values
    trimmed — same normalization as the idb mirror-discipline precedent)."""
    result = (data or {}).get("result") or {}
    rows = []
    for r in result.get("records") or []:
        row = {}
        for k, v in r.items():
            row[k] = v.strip() if isinstance(v, str) else v
        rows.append(row)
    return rows, result.get("total")


def sanctioned_servants_raw(q=None, *, filters=None, limit=100, offset=0, sort=None,
                            cache=None, no_cache=False):
    """→ {rows, total, limit_applied, offset, params, _meta} (server-side search; include_total
    always sent — total echoes the in-force register size on every call).

    q = full-text across all fields (upstream param verbatim); filters = JSON field→value
    exact-match dict in JSON text form (upstream param verbatim — {"ley": "LFRASP"},
    {"causa": "Abuso de autoridad"}); limit 1-1000 politeness cap (the CKAN wall is 32000 and the
    whole register is 435 rows — the cap keeps a typo from requesting the ceiling); offset paging;
    sort = "fecha_resolucion desc" style (upstream param verbatim)."""
    from ..transport import call_provider

    try:
        size = int(limit) if limit is not None else 100
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="mx_sabg",
                       detail=f"limit must be an integer 1-1000, got {limit!r}")
    if not 1 <= size <= 1000:
        raise SdkError("usage_error", provider="mx_sabg",
                       detail=f"limit must be 1-1000 (politeness cap; the whole in-force register is ~435 rows), got '{limit}'")
    try:
        off = int(offset) if offset is not None else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="mx_sabg",
                       detail=f"offset must be an integer >=0, got {offset!r}")
    if off < 0:
        raise SdkError("usage_error", provider="mx_sabg",
                       detail=f"offset must be ≥0, got '{offset}'")
    if isinstance(filters, str):  # the CLI face hands us JSON text — normalize to the dict channel
        try:
            filters = json.loads(filters) if filters.strip() else None
        except ValueError:
            raise SdkError("usage_error", provider="mx_sabg",
                           detail="filters must be a JSON object of field→value exact matches, "
                                  'e.g. \'{"ley": "LFRASP"}\'')
    if filters is not None and not isinstance(filters, dict):
        raise SdkError("usage_error", provider="mx_sabg",
                       detail="filters must be dict-shaped (field→value exact match), e.g. {\"ley\": \"LFRASP\"}")
    qq = str(q or "").strip() or None
    ss = str(sort or "").strip() or None
    params = {"resource_id": _RESOURCE_ID, "limit": size, "offset": off, "include_total": "true"}
    if qq:
        params["q"] = qq
    if filters:
        params["filters"] = json.dumps(filters, ensure_ascii=False)
    if ss:
        params["sort"] = ss
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    rows, total = rows_from_upstream(r["data"])
    return {"rows": rows, "total": total, "limit_applied": size, "offset": off,
            "params": params, "_meta": r}
