"""ilo_stat — ILOSTAT bulk API via the rplumber endpoint (rplumber.ilo.org; keyless).

One face: indicator (one indicator x one country x a year window).

Shapes verified by first-hand live probing 2026-11-02 (tmp/probe-economy/):
GET /data/indicator/?id=EMP_TEMP_SEX_ECO_NB_A&ref_area=USA&timefrom=2020&format=json
  -> [ {ref_area, source, indicator, sex, classif1, time, obs_value, obs_status,
        note_indicator, note_source}, ... ]  (612 rows for USA 2020-2025: 6 years x 3 sexes x
      34 classif1 buckets — the economic-sector breakdown of employment)
Traps found by probing:
  * the format flag is the QUERY parameter `format=json` — the path suffix ".jsondata" is a
    400 ("Unsupported format") and ".json" as a path suffix is a 404 ("wrong query");
  * the trailing slash of /data/indicator/ is part of the route;
  * the CLIENT STACK decides: the curl subprocess returns an EMPTY 200 (0 bytes) and a
    schannel TLS handshake failure on this host, while the urllib channel (the SDK default)
    answers 612 rows / 118,127 bytes every time — the mirrored twin of the AU ABS lesson
    (curl-schannel family). This provider therefore keeps the default urllib channel and
    must NOT be pinned to transport='curl';
  * the upper year bound is spelled `timeto` upstream — `timeuntil` is accepted and SILENTLY
    IGNORED, so the answer runs from `timefrom` to the newest year (verified 2026-11-02:
    timefrom=2020&timeuntil=2022 -> 612 rows 2020-2025, the same set as no upper bound;
    timefrom=2020&timeto=2022 -> 306 rows 2020-2022). A 200 that looks healthy and drops
    the filter — the "silent clamp" family, caught by the row-count cross-check;
  * the answer carries Content-Type: application/octet-stream while the body IS JSON — the
    body is parsed, not the content type.
Rate: the public rplumber endpoint publishes no limit -> polite tier 0.5 rps / burst 2.
TTL: 24h (ILOSTAT refreshes monthly/quarterly per series).
"""
from ..errors import SdkError

provider = {
    "id": "ilo_stat",
    "baseUrl": "https://rplumber.ilo.org/data",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "indicator": {"path": "/indicator/", "notFound": [404]},
    },
    "ttl": {"indicator": 24 * 3600},
}


def indicator_raw(indicator, *, ref_area=None, time_from=None, time_until=None, sex=None,
                  classif=None, source=None, cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /data/indicator/
    indicator = the ILOSTAT indicator code (e.g. EMP_TEMP_SEX_ECO_NB_A); ref_area = the
    country (ISO-3, e.g. USA); time_from / time_until = the year bounds (the upstream
    timefrom / timeto — `timeuntil` is ignored upstream, see the module docstring);
    sex / classif / source = the upstream dimension filters.
    Local wall: --ref-area is required — the world-wide answer of one indicator is orders of
    magnitude bigger than the country answer."""
    from ..transport import call_provider

    ind = str(indicator or "").strip().upper()
    if not ind:
        raise SdkError("usage_error", provider="ilo_stat",
                       detail="ilo_stat_indicator requires --indicator (the ILOSTAT code, "
                              "e.g. EMP_TEMP_SEX_ECO_NB_A)")
    area = str(ref_area or "").strip().upper()
    if not area:
        raise SdkError("usage_error", provider="ilo_stat",
                       detail="ilo_stat_indicator requires --ref-area (the ISO-3 country code, "
                              "e.g. USA) — the world-wide answer of one indicator is orders of "
                              "magnitude bigger than the country answer")
    params = {"id": ind, "ref_area": area, "format": "json"}
    if time_from:
        params["timefrom"] = str(time_from).strip()
    if time_until:
        params["timeto"] = str(time_until).strip()   # NOT `timeuntil` — silently ignored upstream
    if sex:
        params["sex"] = str(sex).strip().upper()
    if classif:
        params["classif1"] = str(classif).strip().upper()
    if source:
        params["source"] = str(source).strip()
    r = call_provider(provider, "indicator", params, cache=cache, no_cache=no_cache)
    data = r["data"]
    if not isinstance(data, list):
        raise SdkError("upstream_unavailable", provider="ilo_stat",
                       detail=f"Unexpected ILOSTAT payload shape: {str(data)[:160]!r}")
    rows = [{
        "ref_area": x.get("ref_area"),
        "indicator": x.get("indicator"),
        "source": x.get("source"),
        "sex": x.get("sex"),
        "classif1": x.get("classif1"),
        "time": x.get("time"),
        "obs_value": x.get("obs_value"),
        "obs_status": x.get("obs_status"),
        "note_indicator": x.get("note_indicator"),
        "note_source": x.get("note_source"),
    } for x in data]
    # Newest year first, deterministically (the upstream order is not pinned): the reason
    # line names rows[0] as the latest observation, so the order has to be ours.
    rows.sort(key=lambda x: (x.get("time") or ""), reverse=True)
    return {"total": len(rows), "count": len(rows), "rows": rows,
            "params": {"indicator": ind, "ref_area": area, "time_from": time_from,
                       "time_until": time_until, "sex": sex, "classif1": classif,
                       "source": source},
            "_meta": r}
