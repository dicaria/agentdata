"""unsd_sdg — UN Statistics Division SDG Global Database (unstats.un.org/SDGAPI/v1; keyless).

Two faces: indicators (the 251-indicator catalog with the per-indicator series codes nested in
each row) and series (the observations of ONE series — 17 goals, 713 series codes).

Traps (research chapter 90, 2026-11-02 — every one of these decided this face's shape):
  * the `area` parameter on GET Series/Data is DECORATIVE — with and without it the answer is
    byte-identical (areaCodes / geoAreaCode variants are ignored the same way), so the geo
    filter is a LOCAL pass over the fetched page, never an upstream param.
  * `timePeriod` DOES filter upstream (seriesCode=DC_ODA_POVLG&timePeriod=2020 -> 138 rows
    totalElements vs 3,499 unfiltered) — the only upstream filter that works on this endpoint.
  * POST Series/Data is a 404; the GET form is the only live channel.
  * Indicator/Data (whole-indicator granularity) answers 3,198,008 rows for one indicator —
    the beast. This module never forms that call: the series face is seriesCode-granularity
    only, and the catalog face is what tells you the valid seriesCodes.

Rate: no published limit -> polite 0.5 rps / burst 2. TTL: 7 days (the 251-indicator catalog)
and 24h (series observations; the SDG database refreshes per quarterly release).
"""
from ..errors import SdkError

provider = {
    "id": "unsd_sdg",
    "baseUrl": "https://unstats.un.org/SDGAPI/v1/sdg",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "indicators": {"path": "/Indicator/List"},
        "series": {"path": "/Series/Data"},
    },
    "ttl": {"indicators": 7 * 24 * 3600, "series": 24 * 3600},
}


def _norm_series(series):
    t = str(series or "").strip().upper()
    if not t:
        raise SdkError("usage_error", provider="unsd_sdg",
                       detail="--series is required (an SDG series code, e.g. SI_POV_DAY1, "
                              "DC_ODA_POVLG — list them with unsd_sdg_indicators; the "
                              "whole-indicator endpoint is a 3.2M-row wall and is never used)")
    return t


def _norm_period(p):
    """timePeriodStart arrives as a JSON number when the period is a plain year (2020.0) and as
    a string for split periods — normalise to the plain form the caller reads."""
    if p is None:
        return None
    try:
        f = float(p)
        return str(int(f)) if f.is_integer() else str(f)
    except (TypeError, ValueError):
        return str(p)


def _indicator_row(x):
    series = x.get("series") or []
    return {"goal": str(x.get("goal") or "") or None,
            "target": str(x.get("target") or "") or None,
            "code": x.get("code"),
            "description": x.get("description"),
            "tier": x.get("tier"),
            "uri": x.get("uri"),
            "series_count": len(series),
            "series_codes": [s.get("code") for s in series if s.get("code")]}


def indicators_raw(*, page=1, per_page=50, search=None, cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /Indicator/List
    The upstream answers the whole 251-row catalog in one payload (no upstream pagination) —
    page / per_page slice it locally; search is a LOCAL keyword scan (code / description /
    series codes), never an upstream filter."""
    from ..transport import call_provider

    pg = int(page or 1)
    pp = int(per_page or 50)
    if pg < 1:
        raise SdkError("usage_error", provider="unsd_sdg", detail="page must be >= 1")
    if not 1 <= pp <= 500:
        raise SdkError("usage_error", provider="unsd_sdg", detail="per_page must be 1-500")
    r = call_provider(provider, "indicators", {}, cache=cache, no_cache=no_cache)
    data = r["data"]
    if not isinstance(data, list):
        raise SdkError("upstream_unavailable", provider="unsd_sdg",
                       detail="The SDGAPI Indicator/List answer is not the catalog list")
    rows = [_indicator_row(x) for x in data]
    q = str(search or "").strip().lower()
    if q:
        rows = [x for x in rows
                if q in (x["code"] or "").lower() or q in (x["description"] or "").lower()
                or any(q in (c or "").lower() for c in x["series_codes"])]
    total = len(rows)
    rows = rows[(pg - 1) * pp: pg * pp]
    return {"total": total, "count": len(rows), "rows": rows,
            "params": {"page": pg, "per_page": pp, "search": q or None}, "_meta": r}


def series_raw(series, *, geo=None, time=None, page=1, page_size=100,
               cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /Series/Data?seriesCode=..
    One series code per call. geo = a LOCAL filter over the fetched page (the upstream `area`
    param is decorative — byte-identical with and without it); it matches the numeric M49-style
    geoAreaCode or the geoAreaName, case-insensitively. time = the upstream timePeriod filter
    (the one upstream filter that works). page / page_size ride the upstream pager."""
    from ..transport import call_provider

    code = _norm_series(series)
    pg = int(page or 1)
    ps = int(page_size or 100)
    if pg < 1:
        raise SdkError("usage_error", provider="unsd_sdg", detail="page must be >= 1")
    if not 1 <= ps <= 1000:
        raise SdkError("usage_error", provider="unsd_sdg", detail="page_size must be 1-1000")
    params = {"seriesCode": code, "page": pg, "pageSize": ps}
    t = str(time).strip() if time else None
    if t:
        params["timePeriod"] = t
    r = call_provider(provider, "series", params, cache=cache, no_cache=no_cache)
    data = r["data"]
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise SdkError("upstream_unavailable", provider="unsd_sdg",
                       detail="The SDGAPI Series/Data answer is not the paged envelope")
    g = str(geo).strip() if geo else None
    gl = g.lower() if g else None

    def _row(x):
        return {"series": x.get("series") or code,
                "series_description": x.get("seriesDescription"),
                "goal": (x.get("goal") or [None])[0],
                "target": (x.get("target") or [None])[0],
                "indicator": (x.get("indicator") or [None])[0],
                "geo_area_code": x.get("geoAreaCode"),
                "geo_area_name": x.get("geoAreaName"),
                "period": _norm_period(x.get("timePeriodStart")),
                "value": x.get("value"),
                "value_type": x.get("valueType"),
                "attributes": x.get("attributes") or {},
                "dimensions": x.get("dimensions") or {},
                "source": x.get("source"),
                "footnotes": x.get("footnotes") or []}

    rows = [_row(x) for x in data["data"]]
    total = data.get("totalElements")
    pages = data.get("totalPages")
    if gl:
        rows = [x for x in rows
                if gl == str(x["geo_area_code"] or "").lower()
                or gl == str(x["geo_area_name"] or "").lower()]
    rows.sort(key=lambda x: (str(x["geo_area_code"] or ""), str(x["period"] or "")))
    return {"total": total, "count": len(rows), "rows": rows,
            "total_pages": pages, "page": data.get("pageNumber"),
            "geo_filtered": bool(gl), "params": {"series": code, "geo": g, "time": t,
                                                 "page": pg, "page_size": ps},
            "_meta": r}
