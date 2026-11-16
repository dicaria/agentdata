"""mx_sgm — Mexican mining-concession cadastre (SGM CartoMinMex ArcGIS FeatureServer, keyless).

esg extractives-assets face (0.3.55; register 284, probed tmp/probe-mx-sgm/ + re-verified live
2026-11-12, tmp/probe-sdk-0355/). Shape measured 2026-11-12:
GET /server/rest/services/Hosted/CartoWebMap_Pro4_WFL1/FeatureServer/49/query (layer 49 =
"Concesiones mineras", the layer name carries its own live count) → the ArcGIS envelope
{features: [{attributes, geometry?}], exceededTransferLimit, fields}. where=1=1 count 19,840
concessions live; the holders column ctithomolo (6,117 distinct companies measured in the
register probe) + municipio/estado geography + superfic_2 hectares + inicio_de_ (an epoch-ms
field on the 1899-12-30 Excel base — negative values reach the 1890s) + the SHAPE polygon (dropped
unless requested). Where-clauses verified live 2026-11-12: exact titulo='214536'; bare LIKE;
UPPER(field) LIKE UPPER('%saucito%') (case-insensitive contains); AND across clauses
(ctithomolo×estado). returnCountOnly=true answers {count} (472 for the Saucito filter — the total
for the SAME where, cached separately). exceededTransferLimit=true = more rows past
resultOffset+resultRecordCount (maxRecordCount 2000 = the page ceiling, orderByFields=fid pins
the walk). Zero-hit where answers features=[] cleanly (titulo='999999999').
The property-chain card face (产权链: tarjetarpm.economia.gob.mx CSV/PDF per titulo) and the
name-lookup POST
face (500/503, watch) are NOT this face — the FeatureServer is the geometry+holder register; the
card is a batch-pipeline concern (19,840 × GET at 4-5s pacing ≈ 23h for the full chain history).
Sibling layers on the same FeatureServer (reservas /12 /13 /14, ANP /0) — future faces.
TTL: page 1h (cadastre is month-fresh), count 24h; polite tier 0.5 rps.
"""
import datetime as _dt

from ..errors import SdkError

provider = {
    "id": "mx_sgm",
    "baseUrl": "https://srvprodarcgisp.economia.gob.mx",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "concessions": {"path": "/server/rest/services/Hosted/CartoWebMap_Pro4_WFL1/FeatureServer/49/query",
                        "timeoutMs": 45000, "ttl": 3600},
        "concessions_count": {"path": "/server/rest/services/Hosted/CartoWebMap_Pro4_WFL1/FeatureServer/49/query",
                              "timeoutMs": 30000, "ttl": 24 * 3600},
    },
}

_EXCEL_EPOCH = _dt.date(1899, 12, 30)  # the inicio_de_ epoch-ms base (negative values = pre-1900 concessions)


def build_where(titular=None, estado=None, municipio=None, titulo=None):
    """face filters → the ArcGIS where clause (pure function). titular/estado/municipio are
    case-insensitive contains (UPPER LIKE UPPER, verified live; % and _ are SQL metacharacters the
    caller manages — the eiti company_name__like precedent); titulo is exact (the concession
    number is a closed-form key). at least one filter required — a bare 19,840-row scan is a
    batch-pipeline concern, not a face (the epa_frs precedent). Single quotes are escaped ('')."""
    clauses = []
    if titulo is not None:
        t = str(titulo).strip()
        if not t:
            raise SdkError("usage_error", provider="mx_sgm", detail="titulo must be a non-empty concession number, e.g. 214536")
        clauses.append("titulo='%s'" % t.replace("'", "''"))
    for field, value in (("ctithomolo", titular), ("estado", estado), ("municipio", municipio)):
        if value is None:
            continue
        v = str(value).strip()
        if not v:
            raise SdkError("usage_error", provider="mx_sgm", detail=f"{field} filter must be non-empty")
        clauses.append("UPPER(%s) LIKE UPPER('%%%s%%')" % (field, v.replace("'", "''")))
    if not clauses:
        raise SdkError("usage_error", provider="mx_sgm",
                       detail="mx_sgm_concesiones requires at least one of titular/estado/municipio/titulo "
                              "(a bare 19,840-row cadastre scan is a batch-pipeline concern, politely walled)")
    return " AND ".join(clauses)


def rows_from_upstream(data):
    """ArcGIS envelope → concession rows (pure function). attributes ride verbatim (the 10 column
    names are the register's own, underscores included); inicio_fecha is the derived calendar date
    from the Excel-base epoch-ms field (negative ms reach 1899); geometry rides only when
    returnGeometry was requested (kept under 'geometry', unprojected)."""
    rows = []
    for f in (data or {}).get("features") or []:
        attrs = dict(f.get("attributes") or {})
        raw = attrs.get("inicio_de_")
        if isinstance(raw, (int, float)):
            try:
                attrs["inicio_fecha"] = (_EXCEL_EPOCH + _dt.timedelta(milliseconds=raw)).isoformat()
            except (OverflowError, ValueError):
                attrs["inicio_fecha"] = None
        else:
            attrs["inicio_fecha"] = None
        if f.get("geometry") is not None:
            attrs["geometry"] = f.get("geometry")
        rows.append(attrs)
    return rows


def concesiones_raw(titular=None, estado=None, municipio=None, titulo=None, *,
                    limit=50, offset=0, geometry=False, want_total=True,
                    cache=None, no_cache=False):
    """→ {rows, total, limit_applied, offset, where, exceeded_transfer_limit, _meta, _count_meta}.

    titular/estado/municipio = case-insensitive contains over the holder/company name, state
    (e.g. Zacatecas — full official forms like "Coahuila de Zaragoza" ride the column) and
    municipality; titulo = the exact concession number (214536 → the Saucito card). limit 1-2000
    (the service maxRecordCount), offset paging (exceeded_transfer_limit echoes whether more rows
    follow); geometry = return the concession polygon (SHAPE) — off by default (the register is
    month-fresh; polygons are heavy). total via a returnCountOnly call on the same where (cached
    24h; set want_total=False to skip it for pure page walks)."""
    from ..transport import call_provider

    try:
        size = int(limit) if limit is not None else 50
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="mx_sgm",
                       detail=f"limit must be an integer 1-2000, got {limit!r}")
    if not 1 <= size <= 2000:
        raise SdkError("usage_error", provider="mx_sgm",
                       detail=f"limit must be 1-2000 (the service maxRecordCount ceiling), got '{limit}'")
    try:
        off = int(offset) if offset is not None else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="mx_sgm",
                       detail=f"offset must be an integer >=0, got {offset!r}")
    if off < 0:
        raise SdkError("usage_error", provider="mx_sgm", detail=f"offset must be ≥0, got '{offset}'")
    where = build_where(titular, estado, municipio, titulo)
    params = {"f": "json", "where": where, "outFields": "*",
              "resultRecordCount": size, "resultOffset": off,
              "orderByFields": "fid", "returnGeometry": "true" if geometry else "false"}
    r = call_provider(provider, "concessions", params, cache=cache, no_cache=no_cache)
    rows = rows_from_upstream(r["data"])
    total = None
    cm = None
    if want_total:
        rc = call_provider(provider, "concessions_count",
                           {"f": "json", "where": where, "returnCountOnly": "true"},
                           cache=cache, no_cache=no_cache)
        total = (rc["data"] or {}).get("count")
        cm = rc  # the call_provider return IS the meta (the idb/epa_frs shape)
    return {"rows": rows, "total": total, "limit_applied": size, "offset": off, "where": where,
            "exceeded_transfer_limit": bool((r["data"] or {}).get("exceededTransferLimit")),
            "_meta": r, "_count_meta": cm}
