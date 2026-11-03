"""eurostat — Eurostat dissemination API provider (ec.europa.eu; keyless, no registration).

One face: table (one Eurostat table x the filters you give). The upstream speaks JSON-stat 2.0:
values live in a flat index map and the dimensions carry the code -> position map that rebuilds
the grid.

Shapes verified by first-hand live probing 2026-11-02 (tmp/probe-economy/):
GET /data/{table}?format=JSON&lang=EN&geo=DE&sinceTimePeriod=2022&untilTimePeriod=2023
  -> {version, class, label, source, updated, value:{flatIdx:num}, status:{flatIdx:code},
      id:[dim...], size:[...], dimension:{dim:{label, category:{index:{code:pos}, label:{...}}}}}
  * several values for one dimension = REPEATED parameters (geo=DE&geo=FR -> 2 cells; the "+"
    form is a 400 and the comma form silently yields 0 cells — the upstream "empty, no error"
    trap);
  * sinceTimePeriod / untilTimePeriod bound the time axis (verified: DE 2022-2023 -> 2 cells);
  * a geo that is not in the table yields size 0 / zero cells and NO error (the upstream
    "silent empty" family — a zero-cell answer is reported as zero cells, never as data);
  * the grid is row-major with the LAST dimension fastest (verified: flat 157 -> time 1985, sex F);
  * `status` carries the cell flags (b = break in time series, e = estimated, p = provisional).
Rate: no official limit published -> polite tier 1 rps / burst 2. TTL: 12h (Eurostat refreshes
daily and stamps `updated`).
"""
from ..errors import SdkError

provider = {
    "id": "eurostat",
    "baseUrl": "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "table": {"path": "/data/{table}", "notFound": [404]},
    },
    "ttl": {"table": 12 * 3600},
}

_CELL_CAP = 500_000        # a bare table (no filter) can be tens of millions of cells
_LABEL_CAP = 500          # per-dimension code->label map: skipped above this size


def _split_values(v):
    """A CLI value may be a list (repeated flags) or one string; Eurostat takes repeated params."""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        items = [str(x).strip() for x in v]
    else:
        items = [x.strip() for x in str(v).split(",")]
    return [x for x in items if x]


def _ordered_codes(dim_payload):
    """category.index is code -> position; the position defines the order."""
    idx = (dim_payload.get("category") or {}).get("index") or {}
    if not idx:
        return []
    ordered = [None] * (max(int(p) for p in idx.values()) + 1)
    for code, pos in idx.items():
        ordered[int(pos)] = code
    return ordered


def _decode(payload):
    """JSON-stat 2.0 -> (rows, dimension summary). The flat index is row-major, last dim fastest."""
    dims = payload.get("id") or []
    sizes = [int(x) for x in (payload.get("size") or [])]
    dim_payloads = payload.get("dimension") or {}
    codes = [_ordered_codes(dim_payloads.get(d) or {}) for d in dims]
    values = payload.get("value") or {}
    statuses = payload.get("status") or {}
    rows = []
    for flat_s, val in sorted(values.items(), key=lambda kv: int(kv[0])):
        flat = int(flat_s)
        coords = []
        rem = flat
        for i in range(len(dims) - 1, -1, -1):
            sz = sizes[i] if i < len(sizes) else 1
            sz = sz or 1
            coords.insert(0, rem % sz)
            rem //= sz
        row = {}
        for i, d in enumerate(dims):
            pos = coords[i]
            row[d] = codes[i][pos] if pos < len(codes[i]) else None
        row["value"] = val
        st = statuses.get(flat_s)
        if st:
            row["status"] = st
        rows.append(row)
    summary = {}
    for i, d in enumerate(dims):
        dp = dim_payloads.get(d) or {}
        entry = {"label": dp.get("label"), "codes": codes[i]}
        labels = (dp.get("category") or {}).get("label") or {}
        if labels and len(labels) <= _LABEL_CAP:
            entry["labels"] = labels
        summary[d] = entry
    return rows, summary


def table_raw(table, *, geo=None, time=None, dims=None, since=None, until=None, lang="EN",
              cache=None, no_cache=False):
    """-> {total, count, rows, params, updated, label, dimensions, _meta}; /data/{table}.
    table = the Eurostat table code (e.g. tec00001, demo_pjan, nama_10_a64); geo / time /
    dims are the upstream dimension filters (several values = repeated parameters); dims is the
    generic carrier for the table-specific dimension ids (age, sex, unit, nace_r2 …) as
    k=v pairs; since / until bound the time axis (upstream sinceTimePeriod / untilTimePeriod);
    lang = the upstream language (EN default).
    Local wall: at least one filter (a bare table is a bulk download), and the cell count must
    stay under the local cap."""
    from ..transport import call_provider

    tbl = str(table or "").strip()
    if not tbl:
        raise SdkError("usage_error", provider="eurostat",
                       detail="eurostat_table requires --table (the Eurostat table code, e.g. tec00001)")
    params = {"format": "JSON", "lang": str(lang or "EN").strip() or "EN", "table": tbl}
    geo_v = _split_values(geo)
    time_v = _split_values(time)
    if geo_v:
        params["geo"] = geo_v
    if time_v:
        params["time"] = time_v
    if since:
        params["sinceTimePeriod"] = str(since).strip()
    if until:
        params["untilTimePeriod"] = str(until).strip()
    dim_items = []
    for raw in (dims or []):
        if isinstance(raw, dict):
            items = list(raw.items())
        else:
            items = [tuple(str(raw).split("=", 1))]
        for k, v in items:
            k = str(k).strip()
            if not k:
                continue
            dim_items.append((k, _split_values(v)))
    if not (geo_v or time_v or dim_items or since or until):
        raise SdkError("usage_error", provider="eurostat",
                       detail="eurostat_table requires at least one filter (--geo / --time / --dim / "
                              "--since / --until) — a bare table is a bulk download, not a query")
    for k, vals in dim_items:
        if len(vals) == 1:
            params[k] = vals[0]
        else:
            params[k] = vals
    r = call_provider(provider, "table", params, cache=cache, no_cache=no_cache)
    payload = r["data"]
    if not isinstance(payload, dict):
        raise SdkError("upstream_unavailable", provider="eurostat",
                       detail=f"Unexpected Eurostat payload shape: {str(payload)[:160]!r}")
    sizes = [int(x) for x in (payload.get("size") or [])]
    cells = 1
    for s in sizes:
        cells *= (s or 0)
    if cells > _CELL_CAP:
        raise SdkError("usage_error", provider="eurostat",
                       detail=f"The filtered table still holds {cells:,} cells (local cap "
                              f"{_CELL_CAP:,}) — narrow the filters (geo / time / dim)")
    rows, summary = _decode(payload)
    return {"total": cells, "count": len(rows), "rows": rows,
            "label": payload.get("label"), "updated": payload.get("updated"),
            "source": payload.get("source"), "dimensions": summary,
            "params": {k: v for k, v in params.items() if k != "table"},
            "_meta": r}
