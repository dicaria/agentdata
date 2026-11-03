"""who_xmart — WHO xMart OData service (xmart-api-public.who.int; keyless, no registration).

Three ops behind two faces:
  * indicator_directory — IND_DIRECTORY_WIDE, the 1,561-indicator catalog; each row carries
    IND_URI_API (the per-indicator API diameter) and IND_URI_WEB (the human page).
  * indicator_values   — DATA_/{entity set}, the observations of one indicator.
  * geo_reference      — REF_GEO_WIDE, the M49 <-> ISO3/ISO2 geography join.

Shapes verified by first-hand live probing 2026-11-02 (tmp/probe-economy/):
GET /DATA_/IND_DIRECTORY_WIDE?$filter=IND_NAME eq 'TB_ppm_enrol_tx_prct'
  -> {"@odata.context":..., "@odata.count":1561, "value":[{IND_ID, IND_UUID, IND_PER_CODE,
      IND_NAME, IND_NAME_FULL, IND_CODE_GHO, VALUE_TYPE, IND_UNIT, IND_URI_API, IND_URI_WEB,
      IND_PUBLISH_TIME_PREV, DATA_PROVENANCE, DIM_GEO_COVERAGE, DIM_GEO_GRANULARITY, ...}]}
GET /DATA_/RELAY_TBPPM?$filter=IND_CODE eq 'TB_ppm_enrol_tx_prct'
  -> {"value":[{IND_CODE, DIM_TIME ("2020"), DIM_TIME_TYPE, DIM_GEO_CODE_M49 ("586"),
      DIM_GEO_CODE_TYPE, DIM_1_CODE/DIM_MEMBER_1_CODE … DIM_9_CODE/DIM_MEMBER_9_CODE,
      VALUE_NUMERIC, VALUE_LABEL, OBSERVATION_STATUS, DIM_PUBLISH_STATE_CODE, IND_ID}]}
GET /DATA_/REF_GEO_WIDE?$filter=GEO_CODE_M49 eq '586' and TERM_LANG eq 'en'
  -> {"value":[{GEO_CODE_M49 ("586"), GEO_CODE_ISO_3 ("PAK"), GEO_CODE_ISO_2 ("PK"),
      GEO_NAME_SHORT ("Pakistan"), GEO_TYPE, GEO_CLASS, GEO_SOVEREIGN, TERM_LANG}]}
Traps found by probing (each one cost a call):
  * DIM_TIME is Edm.String -> the year needs QUOTES ("DIM_TIME eq '2021'"; an unquoted year
    is a 400 type error). DIM_GEO_CODE_M49 is a string too ('586');
  * the geography table is multilingual — one row per TERM_LANG; add "and TERM_LANG eq 'en'";
  * the property is GEO_CODE_M49 in REF_GEO_WIDE but DIM_GEO_CODE_M49 in the value tables;
  * the indicator -> entity-set diameter travels in IND_URI_API (the last path segment is the
    entity set name); several entity sets may carry the same indicator name, and the
    candidate list is NOT auto-picked (the caller chooses, OpenAlex-style discipline);
  * a malformed $filter is a 400 — a usage error, not an upstream outage (re-mapped here).
Rate: no published limit -> polite tier 0.5 rps / burst 2. TTL: 24h (WHO publishes daily).
"""
from ..errors import SdkError

provider = {
    "id": "who_xmart",
    "baseUrl": "https://xmart-api-public.who.int/DATA_",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "indicator_directory": {"path": "/IND_DIRECTORY_WIDE", "notFound": [404]},
        "indicator_values": {"path": "/{entity_set}", "notFound": [404]},
        "geo_reference": {"path": "/REF_GEO_WIDE", "notFound": [404]},
    },
    "ttl": {"indicator_directory": 24 * 3600, "indicator_values": 24 * 3600,
            "geo_reference": 7 * 86400},
}

_DIR_COLS = ("IND_ID", "IND_NAME", "IND_NAME_FULL", "IND_NAME_SHORT", "IND_UUID", "IND_PER_CODE",
             "IND_CODE_GHO", "VALUE_TYPE", "IND_UNIT", "IND_URI_API", "IND_URI_WEB",
             "IND_PUBLISH_TIME_PREV", "DATA_PROVENANCE", "DIM_GEO_COVERAGE",
             "DIM_GEO_GRANULARITY", "IND_PROGRESS_DIRECTION_CODE", "SOURCE_TABLE", "TERM_LANG")
_VAL_COLS = ("IND_ID", "IND_CODE", "DIM_TIME", "DIM_TIME_TYPE", "DIM_GEO_CODE_M49",
             "DIM_GEO_CODE_TYPE", "DIM_1_CODE", "DIM_MEMBER_1_CODE", "DIM_2_CODE",
             "DIM_MEMBER_2_CODE", "DIM_3_CODE", "DIM_MEMBER_3_CODE", "DIM_4_CODE",
             "DIM_MEMBER_4_CODE", "DIM_5_CODE", "DIM_MEMBER_5_CODE", "DIM_6_CODE",
             "DIM_MEMBER_6_CODE", "DIM_7_CODE", "DIM_MEMBER_7_CODE", "DIM_8_CODE",
             "DIM_MEMBER_8_CODE", "DIM_9_CODE", "DIM_MEMBER_9_CODE", "VALUE_NUMERIC",
             "VALUE_LABEL", "VALUE_NUMERIC_LOWER", "VALUE_NUMERIC_UPPER", "OBSERVATION_STATUS",
             "DIM_PUBLISH_STATE_CODE", "VALUE_PROVENANCE")
_GEO_COLS = ("GEO_CODE_M49", "GEO_CODE_ISO_3", "GEO_CODE_ISO_2", "GEO_NAME_SHORT",
             "GEO_NAME_FORMAL", "GEO_TYPE", "GEO_CLASS", "GEO_SOVEREIGN", "GEO_GROUP_TYPE",
             "GEO_CAPITAL", "TERM_LANG")


def _odata(op, params, *, cache=None, no_cache=False):
    """One OData call; a 400 (malformed $filter / wrong property) is a usage error, not an outage."""
    from ..transport import call_provider
    try:
        r = call_provider(provider, op, params, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.status == 400:
            raise SdkError("usage_error", provider="who_xmart",
                           detail=f"The WHO xMart service rejected the query (HTTP 400): {e.detail}")
        raise
    data = r["data"]
    if not isinstance(data, dict) or "value" not in data:
        raise SdkError("upstream_unavailable", provider="who_xmart",
                       detail=f"Unexpected xMart payload shape: {str(data)[:160]!r}")
    return data, r


def _pick(row, cols):
    return {c: row.get(c) for c in cols if c in row}


def indicator_directory_raw(*, filter=None, top=500, skip=0, search=None,
                             cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /IND_DIRECTORY_WIDE
    filter = the raw upstream OData $filter (advanced; the property names are the upstream's);
    top / skip = the upstream $top / $skip paging; search = a LOCAL keyword scan over the
    returned page (name / full name / unit / web URI) — never an upstream filter."""
    from ..transport import call_provider  # noqa: F401  (kept for symmetry with the other ops)

    f = str(filter).strip() if filter else None
    tp = int(top or 500)
    sk = int(skip or 0)
    if tp < 1 or tp > 5000:
        raise SdkError("usage_error", provider="who_xmart", detail="$top must be 1-5000")
    if sk < 0:
        raise SdkError("usage_error", provider="who_xmart", detail="$skip must be >= 0")
    params = {"$top": tp, "$skip": sk, "$count": "true"}
    if f:
        params["$filter"] = f
    data, r = _odata("indicator_directory", params, cache=cache, no_cache=no_cache)
    rows = [_pick(x, _DIR_COLS) for x in data.get("value") or []]
    q = str(search or "").strip().lower()
    if q:
        rows = [x for x in rows
                if q in (x.get("IND_NAME") or "").lower()
                or q in (x.get("IND_NAME_FULL") or "").lower()
                or q in (x.get("IND_NAME_SHORT") or "").lower()
                or q in (x.get("IND_UNIT") or "").lower()
                or q in (x.get("IND_URI_WEB") or "").lower()]
    return {"total": data.get("@odata.count"), "count": len(rows), "rows": rows,
            "params": {"filter": f, "top": tp, "skip": sk, "search": q or None}, "_meta": r}


def indicator_values_raw(entity_set, *, filter=None, top=500, skip=0,
                         cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /DATA_/{entity_set}
    entity_set = the WHO entity set (e.g. RELAY_TBPPM) — the last path segment of the
    directory's IND_URI_API; filter = the raw upstream OData $filter."""
    es = str(entity_set or "").strip().strip("/")
    if not es:
        raise SdkError("usage_error", provider="who_xmart",
                       detail="who_xmart_values needs the entity set (IND_URI_API's last path "
                              "segment, e.g. RELAY_TBPPM) — resolve it with who_xmart_indicators")
    tp = int(top or 500)
    sk = int(skip or 0)
    if tp < 1 or tp > 5000:
        raise SdkError("usage_error", provider="who_xmart", detail="$top must be 1-5000")
    params = {"$top": tp, "$skip": sk, "$count": "true"}
    f = str(filter).strip() if filter else None
    if f:
        params["$filter"] = f
    data, r = _odata("indicator_values", dict(params, entity_set=es), cache=cache, no_cache=no_cache)
    rows = [_pick(x, _VAL_COLS) for x in data.get("value") or []]
    return {"total": data.get("@odata.count"), "count": len(rows), "rows": rows,
            "params": {"entity_set": es, "filter": f, "top": tp, "skip": sk}, "_meta": r}


def geo_reference_raw(*, filter=None, top=100, skip=0, cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /REF_GEO_WIDE
    filter = the raw upstream OData $filter (e.g. "GEO_CODE_ISO_3 eq 'USA' and TERM_LANG eq 'en'")."""
    f = str(filter).strip() if filter else None
    tp = int(top or 100)
    sk = int(skip or 0)
    params = {"$top": tp, "$skip": sk, "$count": "true"}
    if f:
        params["$filter"] = f
    data, r = _odata("geo_reference", params, cache=cache, no_cache=no_cache)
    rows = [_pick(x, _GEO_COLS) for x in data.get("value") or []]
    return {"total": data.get("@odata.count"), "count": len(rows), "rows": rows,
            "params": {"filter": f, "top": tp, "skip": sk}, "_meta": r}


def m49_for_iso3(iso3, *, cache=None, no_cache=False):
    """ISO-3166 alpha-3 -> the M49 code used by DIM_GEO_CODE_M49.
    -> (m49, rows, meta); the lookup is a real upstream call (the geography table is the
    authoritative mapping) and its answer is cached for a week."""
    code = str(iso3 or "").strip().upper()
    if not code:
        return None, [], None
    f = f"GEO_CODE_ISO_3 eq '{code}' and TERM_LANG eq 'en'"
    res = geo_reference_raw(filter=f, top=5, cache=cache, no_cache=no_cache)
    for row in res["rows"]:
        m49 = row.get("GEO_CODE_M49")
        if m49:
            return str(m49), res["rows"], res["_meta"]
    return None, res["rows"], res["_meta"]


def entity_sets_for_indicator(code, *, cache=None, no_cache=False):
    """The directory rows of one indicator code -> the candidate entity sets.
    -> (rows, meta). The candidate list is never auto-picked."""
    f = f"IND_NAME eq '{code}'"
    res = indicator_directory_raw(filter=f, top=50, cache=cache, no_cache=no_cache)
    return res["rows"], res["_meta"]
