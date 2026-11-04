"""bls — US Bureau of Labor Statistics public data API v2 (api.bls.gov/publicAPI/v2; keyless).

One face: series (up to 25 series ids over one <= 10-year window).

Channel decisions (verified 2026-11-03, tmp/probe-economy-0329/):
  * POST /publicAPI/v2/timeseries/data/ with a JSON body {seriesid:[...], startyear, endyear}
    (years as four-digit STRINGS per the signature doc); the answer is JSON with the top keys
    Results/message/responseTime/status — REQUEST_SUCCEEDED even for partly bogus input.
  * Keyless tier (documented + pinned): at most 25 series ids, a 10-YEAR window and 500
    queries/day. catalog / calculations / annualaverage / aspects are key-gated options —
    catalog:true on the keyless tier answers "The catalog has been disabled for this
    request." (pinned) — none of them is ever sent.
  * THE INVERTED CLAMP: a window wider than 10 years is not rejected — endyear is silently
    reduced to startyear+9 with only a message line ("Year range has been reduced to the
    system-allowed limit of 10 years."), and the KEPT years are the EARLIEST ten: the pinned
    2010..2026 ask answered 2010..2019 (no latest marker). A caller asking 2010-2026 would
    silently lose 2020-2026 -> local wall BEFORE the call: narrow or split the window.
  * A bogus series id is NOT an error: the answer stays 200/REQUEST_SUCCEEDED, a message
    line "Invalid Series for Series BOGUS0000001" is added and the id still appears in
    Results.series with an EMPTY data array -> invalid ids surface as series_without_data
    plus the message lines; upstream_not_found is raised only when EVERY requested id is
    explicitly invalid (a valid series can legitimately answer zero rows in a window).
  * Values travel as STRINGS ("336.940", "4.2"); a missing observation is "." -> float /
    None. The newest-first upstream order is sorted ascending (series, year, period) for
    time-series readability; footnotes ride along compact ("P=preliminary"), the empty {}
    footnote rows are dropped.
  * Omitting both years answers the latest ~3 calendar years (pinned: 33 obs, 2024..2026,
    no message). Years travel together (both or neither) — half windows are unpinned
    upstream behavior and are not shipped.
Rate: no published per-second limit (the keyless tier is 500 queries/day) -> polite tier
0.5 rps / burst 2.
TTL: 12h (BLS series refresh monthly/quarterly; the default window shifts monthly).
"""
import re

from ..errors import SdkError

provider = {
    "id": "bls",
    "baseUrl": "https://api.bls.gov",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "series": {"path": "/publicAPI/v2/timeseries/data/", "method": "POST", "idempotent": True},
    },
    "ttl": {"series": 12 * 3600},
}

# the signature doc: "Series IDs must be numbers and upper case letters"
_SERIES_RE = re.compile(r"[A-Z0-9]+")
_MAX_SERIES = 25   # documented keyless cap: 25 series per query
_MAX_SPAN = 10     # documented keyless cap: 10 years per query


def _norm_series(series):
    """comma/whitespace-separated list -> deduped uppercase ids (documented charset [A-Z0-9])."""
    if series is None or not str(series).strip():
        raise SdkError("usage_error", provider="bls",
                       detail="bls_series requires --series (BLS series id(s), comma-separated, "
                              "e.g. CUUR0000SA0 = CPI-U, LNS14000000 = unemployment rate, "
                              "CES0000000001 = nonfarm payrolls)")
    ids, seen = [], set()
    for tok in re.split(r"[,\s]+", str(series).strip()):
        sid = tok.strip().upper()
        if not sid:
            continue
        if not _SERIES_RE.fullmatch(sid):
            raise SdkError("usage_error", provider="bls",
                           detail=f"series id '{sid}' is not a BLS id — the signature doc allows "
                                  "numbers and upper case letters only")
        if sid not in seen:
            seen.add(sid)
            ids.append(sid)
    if not ids:
        raise SdkError("usage_error", provider="bls", detail="--series resolved to an empty id list")
    if len(ids) > _MAX_SERIES:
        raise SdkError("usage_error", provider="bls",
                       detail=f"{len(ids)} series ids requested — the keyless tier takes at most "
                              f"{_MAX_SERIES} per query")
    return ids


def _norm_years(start_year, end_year):
    """both or neither; four-digit ints; span <= 10 — the upstream clamp keeps the EARLIEST
    ten years (startyear-anchored), a silent loss we refuse locally."""
    s = str(start_year).strip() if start_year not in (None, "") else None
    e = str(end_year).strip() if end_year not in (None, "") else None
    if (s is None) != (e is None):
        raise SdkError("usage_error", provider="bls",
                       detail="--start-year and --end-year travel together (both or neither); "
                              "omitting both answers the latest ~3 calendar years")
    if s is None:
        return None, None
    if not (s.isdigit() and len(s) == 4 and e.isdigit() and len(e) == 4):
        raise SdkError("usage_error", provider="bls",
                       detail=f"years must be four-digit integers, got {s}..{e}")
    si, ei = int(s), int(e)
    if si > ei:
        raise SdkError("usage_error", provider="bls", detail=f"start year {s} is after end year {e}")
    if ei - si + 1 > _MAX_SPAN:
        raise SdkError("usage_error", provider="bls",
                       detail=f"window {s}..{e} spans {ei - si + 1} years — the keyless tier caps "
                              f"the window at {_MAX_SPAN} years, and the upstream clamp KEEPS THE "
                              f"EARLIEST {_MAX_SPAN} (startyear-anchored: a 2010..2026 ask answered "
                              "2010..2019, pinned 2026-11-03) — narrow the window or split it")
    return s, e


def _value(v):
    v = (v or "").strip()
    if v in ("", ".", "-"):
        return None
    try:
        return float(v)
    except ValueError:
        return v  # never fabricated


def _footnotes(fns):
    out = []
    for f in fns or []:
        if not isinstance(f, dict):
            continue
        code, text = (f.get("code") or "").strip(), (f.get("text") or "").strip()
        if code and text:
            out.append(f"{code}={text}")
        elif code or text:
            out.append(code or text)
    return out


def series_raw(series, *, start_year=None, end_year=None, cache=None, no_cache=False):
    """-> {total, count, rows, series, series_without_data, messages, params, _meta};
    POST {seriesid, startyear, endyear}; rows are long-form
    {series, year, period, period_name, value, latest, footnotes} sorted ascending."""
    from ..transport import call_provider

    ids = _norm_series(series)
    s, e = _norm_years(start_year, end_year)
    body = {"seriesid": ids}
    if s:
        body["startyear"] = s
        body["endyear"] = e
    r = call_provider(provider, "series", body, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    if d.get("status") == "REQUEST_NOT_PROCESSED":
        raise SdkError("upstream_unavailable", provider="bls",
                       detail="BLS answered REQUEST_NOT_PROCESSED: "
                              + "; ".join(str(m) for m in d.get("message") or []))
    messages = [str(m) for m in d.get("message") or []]
    invalid = set()
    for m in messages:
        mm = re.match(r"Invalid Series for Series (\S+)", m)
        if mm:
            invalid.add(mm.group(1))
    rows, without = [], []
    for sr in (d.get("Results") or {}).get("series") or []:
        sid = sr.get("seriesID")
        data = sr.get("data") or []
        if not data:
            without.append(sid)
            continue
        for ob in data:
            rows.append({
                "series": sid,
                "year": int(ob["year"]) if ob.get("year") else None,
                "period": ob.get("period"),
                "period_name": ob.get("periodName"),
                "value": _value(ob.get("value")),
                "latest": bool(ob.get("latest")),
                "footnotes": _footnotes(ob.get("footnotes")),
            })
    rows.sort(key=lambda x: (x["series"], x["year"] or 0, x["period"] or ""))
    if invalid and set(ids) <= invalid:
        raise SdkError("upstream_not_found", provider="bls",
                       detail="every requested series id is invalid upstream: "
                              + ", ".join(sorted(invalid)))
    return {"total": len(rows), "count": len(rows), "rows": rows, "series": ids,
            "series_without_data": without, "messages": messages,
            "params": {"seriesid": ids, "startyear": s, "endyear": e}, "_meta": r}
