"""comext — Eurostat Comext trade-flows API (dedicated dissemination root; keyless).

One face: flows — the ANNUAL HS2-4-6 mirror of EU and non-EU trade since 2002 (dataset
ds-059341), the "Germany imported ~X EUR of HS85 from China in 2024" denominator layer.
The monthly CN8 detail (DS-045409, 37,069 product codes) and the 399k-row full history
travel the raw side as the full_v2 7z archives — this face is the point query.

Channel (research chapter 84 + the dedicated-root recipe, verified live 2026-11-03 in
tmp/probe-economy-0326/): the Comext service hides BEHIND the plain Eurostat dissemination
root — the URL must insert the `comext/` segment:
  https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/ds-059341
A plain-root call for a DS-/ds- dataset is a 404 "not available for dissemination". The
answer is JSON-stat 2.0 — the SAME grid contract as the eurostat provider (flat index map,
last dimension fastest), so the decoder is imported from the sibling module rather than
duplicated.

Walls and traps (probed first-hand):
  * NO filter at all = HTTP 413 "Full extraction forbidden" (the full mirror is 31.3 billion
    cells; a single query caps at 5 million) — the face requires at least one dimension
    filter locally and never forms the bare call;
  * several values for one dimension = REPEATED parameters (the same "+"/comma trap family
    as eurostat: "+" is a 400, the comma form silently yields zero cells);
  * flow = 1 imports / 2 exports; indicators = VALUE_EUR (euros) or QUANTITY_IN_100KG;
  * reporter aggregates live alongside countries (EU, EU27_2020, EA, EA21) — EU27_2020 is
    the standing EU-27 aggregate;
  * time is the plain year (2024); the monthly dataset spells YYYY-MM but is not this face.

Rate: no published limit -> polite 0.5 rps / burst 2 (the aggregation backend is heavier
than the plain Eurostat tables). TTL: 24h (annual mirror refreshed monthly-ish; the probe
answer stamped updated 2026-10-16).
"""
from ..errors import SdkError
from .eurostat import _decode, _split_values

provider = {
    "id": "comext",
    "baseUrl": "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "flows": {"path": "/data/ds-059341", "notFound": [404]},
    },
    "ttl": {"flows": 24 * 3600},
}

_CELL_CAP = 500_000        # same posture as eurostat_table: a filterless call is bulk, not query


def flows_raw(*, reporter=None, partner=None, product=None, flow=None, indicators=None,
              time=None, since=None, until=None, cache=None, no_cache=False):
    """-> {total, count, rows, label, updated, dimensions, params, _meta}; /data/ds-059341.
    reporter / partner = Eurostat geo codes (reporter aggregates EU, EU27_2020, EA, EA21 are
    valid values; several values become repeated upstream parameters); product = the HS 2/4/6
    code (85 = electrical machinery); flow = 1 imports / 2 exports; indicators defaults to
    VALUE_EUR; time = plain years (repeatable); since / until bound the time axis (upstream
    sinceTimePeriod / untilTimePeriod).
    Local wall: at least one filter — the bare mirror is a 413 "Full extraction forbidden"."""
    from ..transport import call_provider

    params = {"format": "JSON"}
    rep = _split_values(reporter)
    par = _split_values(partner)
    prd = _split_values(product)
    flw = _split_values(flow)
    ind = _split_values(indicators) or ["VALUE_EUR"]
    tim = _split_values(time)
    if rep:
        params["reporter"] = rep
    if par:
        params["partner"] = par
    if prd:
        params["product"] = prd
    if flw:
        params["flow"] = flw
    if ind:
        params["indicators"] = ind if len(ind) > 1 else ind[0]
    if tim:
        params["time"] = tim
    if since:
        params["sinceTimePeriod"] = str(since).strip()
    if until:
        params["untilTimePeriod"] = str(until).strip()
    if not (rep or par or prd or flw or tim or since or until):
        raise SdkError("usage_error", provider="comext",
                       detail="comext_flows requires at least one filter (--reporter / --partner / "
                              "--product / --flow / --time / --since / --until) — the filterless "
                              "mirror is a 413 \"Full extraction forbidden\" upstream (31.3 billion "
                              "cells; one query caps at 5 million)")
    if len(params.get("reporter", [])) == 1:
        params["reporter"] = params["reporter"][0]
    if len(params.get("partner", [])) == 1:
        params["partner"] = params["partner"][0]
    if len(params.get("product", [])) == 1:
        params["product"] = params["product"][0]
    if len(params.get("flow", [])) == 1:
        params["flow"] = params["flow"][0]
    if len(params.get("time", [])) == 1:
        params["time"] = params["time"][0]
    r = call_provider(provider, "flows", params, cache=cache, no_cache=no_cache)
    payload = r["data"]
    if not isinstance(payload, dict) or "value" not in payload:
        raise SdkError("upstream_unavailable", provider="comext",
                       detail=f"Unexpected Comext payload shape: {str(payload)[:160]!r}")
    sizes = [int(x) for x in (payload.get("size") or [])]
    cells = 1
    for s in sizes:
        cells *= (s or 0)
    if cells > _CELL_CAP:
        raise SdkError("usage_error", provider="comext",
                       detail=f"The filtered mirror still holds {cells:,} cells (local cap "
                              f"{_CELL_CAP:,}) — narrow the filters (reporter / partner / product / time)")
    rows, summary = _decode(payload)
    return {"total": cells, "count": len(rows), "rows": rows,
            "label": payload.get("label"), "updated": payload.get("updated"),
            "dimensions": summary,
            "params": params, "_meta": r}
