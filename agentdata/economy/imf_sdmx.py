"""imf_sdmx — IMF SDMX 2.1 data service (api.imf.org/external/sdmx/2.1; keyless).

One face: sdmx_series — one dataflow × one country × one indicator over an optional period
window (the trailing key dimensions — FREQUENCY and beyond — are omittable upstream; the face
keeps the optional trailing FREQUENCY and nothing else).

Channel decision (the ecb csvdata idiom, 0.3.23): the SDMX 2.1 endpoint answers the Accept
header FIRST — with the transport default `Accept: application/json` the answer comes back as
SDMX-XML (mangled by the JSON-only transport); asking explicitly for
`application/vnd.sdmx.data+csv;version=1.0.0` yields the SDMX 2.1 generic CSV (DATAFLOW, one
column per key dimension, TIME_PERIOD, OBS_VALUE, then attribute columns — verified
2026-11-02: WEO/USA.NGDP_RPCH -> 200, 111,674 B, 52 data rows 1980-2031 at full precision).

Walls and traps (research chapter 87, 2026-11-02):
  * the country-only key (ONE key segment) is the multi-megabyte wall — the whole dataset for
    one country. The face requires BOTH --country and --indicator, so a one-segment key is
    never formed here.
  * the DSD codelists come back partial/empty (the indicator dictionary is not fetchable that
    way) — the CSV columns ARE the dimension list, and they vary per flow: WEO/GDD spell them
    COUNTRY.INDICATOR.FREQUENCY; UNFCCC inserts INDUSTRY/GAS_TYPE before the indicator, so the
    country.indicator key shape fits the WEO/GDD/CPI family and NOT UNFCCC (documented limit,
    wrong-order keys upstream 404).
  * SCALE is a display hint — OBS_VALUE already carries the true value (DataMapper's rounded
    1-decimal numbers are the reason that surface is a background board, not a source).

Rate: no published limit -> polite 0.5 rps / burst 2. TTL 24h (the WEO family refreshes on its
own vintage cadence; 101 of the 229 dataflows are standing, the rest are monthly vintages).
"""
import csv
import io
import re

from ..errors import SdkError

provider = {
    "id": "imf_sdmx",
    "baseUrl": "https://api.imf.org/external/sdmx/2.1",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "sdmx_series": {"path": "/data/{flow}/{key}", "accept": "text", "notFound": [404]},
    },
    "ttl": {"sdmx_series": 24 * 3600},
}

_TOKEN_RE = re.compile(r"^[A-Z0-9_]+$")

# The SDMX 2.1 generic CSV: ask for the CSV flavour explicitly (see the module docstring —
# the JSON Accept is ignored upstream and the answer degrades to XML).
_CSV_ACCEPT = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}


def _norm_token(value, what, provider_id="imf_sdmx"):
    """The key parts are upper-case tokens (USA, NGDP_RPCH, WEO, A)."""
    t = str(value or "").strip().upper()
    if not t or not _TOKEN_RE.match(t):
        raise SdkError("usage_error", provider=provider_id,
                       detail=f"{what} must be an upper-case code token (letters/digits/'_'), "
                              f"got {value!r}")
    return t


def _dim_names(head):
    """The key-dimension columns of the SDMX 2.1 generic CSV: everything between DATAFLOW and
    TIME_PERIOD (they vary per flow — WEO/GDD say COUNTRY,INDICATOR,FREQUENCY; UNFCCC inserts
    INDUSTRY/GAS_TYPE — so the boundary, not a fixed list, is the reliable rule)."""
    names = []
    for col in head:
        if col in ("DATAFLOW",):
            continue
        if col == "TIME_PERIOD":
            break
        names.append(col)
    return names


def _parse_csv(text):
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        raise SdkError("upstream_unavailable", provider="imf_sdmx",
                       detail="The IMF SDMX CSV answer was empty")
    head = lines[0].split(",")
    if "TIME_PERIOD" not in head or "OBS_VALUE" not in head:
        # not the generic CSV (an SDMX XML error page, a gateway notice)
        raise SdkError("upstream_unavailable", provider="imf_sdmx",
                       detail=f"The IMF SDMX answer is not the generic CSV table "
                              f"(head {lines[0][:120]!r})")
    dims = _dim_names(head)
    rows = []
    for rec in csv.DictReader(io.StringIO("\n".join(lines))):
        try:
            value = float(rec.get("OBS_VALUE"))
        except (TypeError, ValueError):
            value = None
        out = {"flow": (rec.get("DATAFLOW") or "").split(":")[-1].split("(")[0] or None,
               "dims": {d: rec.get(d) for d in dims if rec.get(d) not in (None, "")},
               "period": rec.get("TIME_PERIOD"),
               "value": value,
               "scale": rec.get("SCALE") or None,
               "series_name": rec.get("SERIES_NAME") or None,
               "description": rec.get("FULL_DESCRIPTION") or None,
               "doi": rec.get("DOI") or None}
        rows.append(out)
    return rows


def sdmx_series_raw(flow, country, indicator, frequency=None, *, start=None, end=None,
                    cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /data/{flow}/{COUNTRY.INDICATOR[.FREQUENCY]}
    flow = the dataflow id (WEO, GDD, CPI …); country + indicator are BOTH required — the
    country-only key is the multi-megabyte wall; frequency = the optional trailing key
    dimension; start / end = the upstream startPeriod / endPeriod bounds."""
    from ..transport import call_provider

    fl = _norm_token(flow, "--flow")
    cc = _norm_token(country, "--country")
    ind = _norm_token(indicator, "--indicator")
    freq = _norm_token(frequency, "--frequency") if frequency else None
    key = ".".join([cc, ind] + ([freq] if freq else []))
    s = str(start).strip() if start else None
    e = str(end).strip() if end else None
    params = {"flow": fl, "key": key}
    if s:
        params["startPeriod"] = s
    if e:
        params["endPeriod"] = e
    r = call_provider(provider, "sdmx_series", params, cache=cache, no_cache=no_cache,
                      extra_headers=_CSV_ACCEPT)
    rows = _parse_csv(r["data"])
    rows.sort(key=lambda x: (x.get("period") or ""))
    return {"total": len(rows), "count": len(rows), "rows": rows, "key": key,
            "params": {"flow": fl, "country": cc, "indicator": ind, "frequency": freq,
                       "start": s, "end": e},
            "_meta": r}
