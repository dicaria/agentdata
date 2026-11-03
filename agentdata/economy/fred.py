"""fred — US Federal Reserve Economic Data (fred.stlouisfed.org/graph/fredgraph.csv; keyless).

One face: series (one FRED series over a date window).

Channel decisions (verified 2026-11-02, tmp/probe-economy/):
  * GET /fredgraph.csv?id={SERIES}[&cosd=&coed=] answers text/csv:
    "observation_date,SERIES" then one row per observation (1947-01-01,21.480 for CPIAUCSL).
  * SEVERAL series ids in one call answer application/zip (a ZIP with README.txt + one CSV
    per series) — a binary payload, destroyed by the JSON-only transport (the 0.3.22
    binary-wall ruling) -> one series per call, enforced locally.
  * An unknown series id answers an HTML ERROR PAGE ("Error - St. Louis Fed", 29 KB) instead
    of a 4xx -> the magic-number check is mandatory: the answer must start with
    "observation_date", otherwise it is an upstream_not_found (an unknown series id), never
    data. (A 2xx non-CSV answer is never passed through as if it were a series.)
  * A missing observation is a lone "." in the CSV -> null (a gap is a fact).
  * cosd / coed are the upstream observation-window bounds (verified: GDP 2020-01-01..2021-01-01).
Rate: FRED publishes no public limit for the CSV endpoint -> polite tier 1 rps / burst 2.
TTL: 12h (the cadence differs per series — daily, monthly, quarterly).
"""
import csv
import io

from ..errors import SdkError

provider = {
    "id": "fred",
    "baseUrl": "https://fred.stlouisfed.org/graph",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "series": {"path": "/fredgraph.csv", "accept": "text", "notFound": [404]},
    },
    "ttl": {"series": 12 * 3600},
}

_MAGIC = "observation_date"


def _norm_series(series):
    """One series id per call (several ids answer a ZIP = binary wall)."""
    s = str(series or "").strip().upper()
    if not s:
        raise SdkError("usage_error", provider="fred",
                       detail="fred_series requires --series (a FRED series id, e.g. GDP, CPIAUCSL, "
                              "DGS10) — several ids in one call answer a ZIP archive, which the "
                              "JSON transport cannot carry")
    if "," in s or ";" in s:
        raise SdkError("usage_error", provider="fred",
                       detail="fred_series takes ONE series id per call — the upstream answers a "
                              "ZIP archive (binary) when several ids are requested")
    return s


def series_raw(series, *, start=None, end=None, cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /fredgraph.csv?id={series}
    series = the FRED series id; start / end = the upstream cosd / coed observation window;
    the rows are long-form {date, series, value} and a missing observation is null."""
    from ..transport import call_provider

    sid = _norm_series(series)
    params = {"id": sid}
    s = str(start).strip() if start else None
    e = str(end).strip() if end else None
    if s:
        params["cosd"] = s
    if e:
        params["coed"] = e
    r = call_provider(provider, "series", params, cache=cache, no_cache=no_cache)
    text = r["data"]
    if not isinstance(text, str) or not text.lstrip().startswith(_MAGIC):
        # the upstream answers an HTML error page for an unknown series id
        raise SdkError("upstream_not_found", provider="fred",
                       detail=f"FRED answered a non-CSV page for series '{sid}' (the upstream "
                              "returns an HTML error page for an unknown series id)")
    recs = list(csv.DictReader(io.StringIO(text)))
    rows = []
    for rec in recs:
        date = rec.get("observation_date") or rec.get("DATE")
        for col, val in rec.items():
            if col in (None, "observation_date", "DATE"):
                continue
            v = (val or "").strip()
            if v in (".", "", "NA", "NaN"):
                v = None
            else:
                try:
                    v = float(v)
                except ValueError:
                    pass
            rows.append({"date": date, "series": col, "value": v})
    rows.sort(key=lambda x: ((x.get("date") or ""), (x.get("series") or "")))
    return {"total": len(rows), "count": len(rows), "rows": rows,
            "params": {"series": sid, "start": s, "end": e}, "_meta": r}
