"""bis — Bank for International Settlements SDMX (stats.bis.org/api/v1; keyless).

One face: sdmx_series — one of the 25 dataflows (WS_*) times one series key, over an optional
period window. The key dimensions differ per flow, so the key is passed through as the raw
dot-separated SDMX key (the imf_sdmx face hard-codes country×indicator; here the pass-through
is the honest shape):
    WS_CBPOL  FREQ.REF_AREA                    M.US          policy rate, US, monthly
    WS_DSR    FREQ.BORROWERS_CTY.DSR_BORROWERS Q.US.N        debt-service ratio, US non-financial
    WS_XRU    FREQ.REF_AREA.CURRENCY.COLLECTION M.CN.CNY.E  USD per CNY, monthly, end-period

Channel decision: same SDMX 2.1 generic-CSV idiom as imf_sdmx/ecb (Accept
`application/vnd.sdmx.data+csv;version=1.0.0`; verified 2026-11-02: WS_CBPOL/M.US -> 200,
241,844 B CSV from 1954-07, WS_XRU/M.CN.CNY.E?startPeriod=2026-06-01 honored).

Walls and traps (research chapter 89, 2026-11-02):
  * a ONE-segment key (the frequency alone) means every area at once — the multi-megabyte
    wall; the face requires at least two key segments.
  * a wrong key is NOT a block: it answers HTTP 404 with an SDMX <message:Error> (code 100
    "No results" inside) — carried as not-found by the op, never mistaken for an egress wall.
  * the DSD id is NOT the flow-id prefix (WS_XRU's structure is BIS_XR — read from the
    dataflow Structure Ref) and `references=children` answers empty codelists — neither DSD
    path is needed here, the CSV columns carry the dimensions.

Rate: no published limit -> polite 0.5 rps / burst 2. TTL 24h (the WS_* family refreshes on
mixed monthly/quarterly cadences).
"""
import csv
import io
import re

from ..errors import SdkError

provider = {
    "id": "bis",
    "baseUrl": "https://stats.bis.org/api/v1",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "sdmx_series": {"path": "/data/{flow}/{key}/all", "accept": "text", "notFound": [404]},
    },
    "ttl": {"sdmx_series": 24 * 3600},
}

_KEY_SEG_RE = re.compile(r"^[A-Z0-9_]+$")

_CSV_ACCEPT = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}


def _norm_flow(flow):
    t = str(flow or "").strip().upper()
    if not t or not _KEY_SEG_RE.match(t):
        raise SdkError("usage_error", provider="bis",
                       detail=f"--flow must be an upper-case BIS dataflow id (e.g. WS_CBPOL, "
                              f"WS_DSR, WS_XRU), got {flow!r}")
    return t


def _norm_key(key):
    """The raw SDMX series key: >= 2 dot-separated segments (FREQ plus at least one dimension —
    a one-segment key is every area at once, the multi-megabyte wall)."""
    k = str(key or "").strip().upper().strip(".")
    segs = k.split(".") if k else []
    if len(segs) < 2 or any(not _KEY_SEG_RE.match(s) for s in segs):
        raise SdkError("usage_error", provider="bis",
                       detail="--key must be the dot-separated SDMX series key with AT LEAST "
                              "two segments (e.g. M.US for WS_CBPOL, Q.US.N for WS_DSR, "
                              "M.CN.CNY.E for WS_XRU — a one-segment key is every area at "
                              "once, a multi-megabyte answer)")
    return ".".join(segs)


def _dim_names(head):
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
        raise SdkError("upstream_unavailable", provider="bis",
                       detail="The BIS SDMX CSV answer was empty")
    head = lines[0].split(",")
    if "TIME_PERIOD" not in head or "OBS_VALUE" not in head:
        raise SdkError("upstream_unavailable", provider="bis",
                       detail=f"The BIS SDMX answer is not the generic CSV table "
                              f"(head {lines[0][:120]!r})")
    dims = _dim_names(head)
    rows = []
    for rec in csv.DictReader(io.StringIO("\n".join(lines))):
        try:
            value = float(rec.get("OBS_VALUE"))
        except (TypeError, ValueError):
            value = None
        rows.append({"flow": (rec.get("DATAFLOW") or "").split(":")[-1].split("(")[0] or None,
                     "dims": {d: rec.get(d) for d in dims if rec.get(d) not in (None, "")},
                     "period": rec.get("TIME_PERIOD"),
                     "value": value,
                     "unit_mult": rec.get("UNIT_MULT") or None,
                     "decimals": rec.get("DECIMALS") or None,
                     "title": (rec.get("TITLE") or "").strip() or None,
                     "obs_status": rec.get("OBS_STATUS") or None})
    return rows


def sdmx_series_raw(flow, key, *, start=None, end=None, cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /data/{flow}/{key}/all
    flow = the WS_* dataflow id; key = the raw dot-separated series key (>= 2 segments —
    the segment order is flow-specific: WS_CBPOL FREQ.REF_AREA, WS_DSR
    FREQ.BORROWERS_CTY.DSR_BORROWERS, WS_XRU FREQ.REF_AREA.CURRENCY.COLLECTION);
    start / end = the upstream startPeriod / endPeriod bounds."""
    from ..transport import call_provider

    fl = _norm_flow(flow)
    k = _norm_key(key)
    s = str(start).strip() if start else None
    e = str(end).strip() if end else None
    params = {"flow": fl, "key": k}
    if s:
        params["startPeriod"] = s
    if e:
        params["endPeriod"] = e
    r = call_provider(provider, "sdmx_series", params, cache=cache, no_cache=no_cache,
                      extra_headers=_CSV_ACCEPT)
    rows = _parse_csv(r["data"])
    rows.sort(key=lambda x: (x.get("period") or ""))
    return {"total": len(rows), "count": len(rows), "rows": rows, "key": k,
            "params": {"flow": fl, "key": k, "start": s, "end": e}, "_meta": r}
