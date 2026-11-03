"""ecb — European Central Bank reference exchange rates (data-api.ecb.europa.eu; keyless).

One face: fx_rates (one currency against the euro, over a date window).

Channel decision (this is the important part):
  * The data-api SDMX endpoint with `format=csvdata` answers text/csv — it survives the
    JSON-only transport untouched (verified 2026-11-02: HTTP 200, text/csv, 4,900 B for
    USD 2026-10-01..2026-11-02, header KEY,FREQ,CURRENCY,…,TIME_PERIOD,OBS_VALUE,…).
    BUT the SDMX endpoint negotiates on the Accept header FIRST and ignores `format=csvdata`
    when the client asks for JSON: with the transport's default `Accept: application/json` it
    answers 200 with an SDMX-JSON envelope (6,119 B, "header"/"dataSets") — a 2xx that looks
    healthy and is not the csvdata contract. So the op sends `Accept: text/csv` explicitly
    (the ca_sema XML-accept idiom); with that header the `format=csvdata` parameter is not
    even needed, but it is kept as the fallback for a client that drops the header.
  * The historical eurofxref-hist.zip is a ZIP (binary -> destroyed by the JSON-only
    transport, the 0.3.22 binary-wall ruling) and its eurofxref-hist.csv sibling is a STALE
    snapshot (2,801 rows ending 2010-02-14; the daily csv stops at 2017-07-14) — neither is
    used here; the live SDMX endpoint is the only current series.
  * The eurofxref-hist.xml is an SDMX Envelope (gesmes namespace + ecb vocabulary Cube with
    time=/currency=/rate= attributes), not the simple <eurofxref><dailyrates> shape — a
    different parser would be needed; the csvdata form avoids that entirely.

Series semantics: EXR.D.{CCY}.EUR.SP00.A = the daily euro reference rate, quoted as
units of {CCY} per 1 EUR (USD 1.1298 means 1 EUR = 1.1298 USD). The rate + its date travel
with every row (the amount-normalisation rule: the rate source and date are never dropped).
Rate: no official limit published -> polite tier 0.5 rps / burst 2. TTL: 12h (the ECB
publishes once a working day, ~16:15 CET).
"""
import csv
import io

from ..errors import SdkError

provider = {
    "id": "ecb",
    "baseUrl": "https://data-api.ecb.europa.eu/service/data",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "fx_rates": {"path": "/EXR/D.{currency}.EUR.SP00.A", "accept": "text", "notFound": [404]},
    },
    "ttl": {"fx_rates": 12 * 3600},
}

_CURRENCY_RE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# The SDMX content negotiation answers the Accept header first (see the module docstring):
# application/json -> an SDMX-JSON envelope that is NOT the csvdata contract. Ask for CSV.
_CSV_ACCEPT = {"Accept": "text/csv"}


def _norm_currency(cur):
    """The upstream key part is a 3-letter currency code (USD, JPY, GBP …)."""
    c = str(cur or "").strip().upper()
    if len(c) != 3 or any(ch not in _CURRENCY_RE for ch in c):
        raise SdkError("usage_error", provider="ecb",
                       detail="ecb_fx_rates requires --currency as a 3-letter ISO 4217 code "
                              "(e.g. USD, JPY, GBP) — the upstream series key is EXR.D.{CCY}.EUR.SP00.A")
    return c


def _parse_csv(text):
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        raise SdkError("upstream_unavailable", provider="ecb", detail="The ECB CSV answer was empty")
    head = lines[0].split(",")
    if "TIME_PERIOD" not in head or "OBS_VALUE" not in head:
        # not a csvdata answer (an error page, an SDMX XML answer, a redirect notice)
        raise SdkError("upstream_unavailable", provider="ecb",
                       detail=f"The ECB answer is not a csvdata table (head {lines[0][:120]!r})")
    rows = []
    for rec in csv.DictReader(io.StringIO("\n".join(lines))):
        rows.append(rec)
    return rows


def fx_rates_raw(currency, *, start=None, end=None, cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /EXR/D.{currency}.EUR.SP00.A?format=csvdata
    currency = the 3-letter ISO 4217 code; start / end = the upstream startPeriod / endPeriod
    (one of them is required — a bounded window; the full history is ~8,000 rows);
    the value is units of {currency} per 1 EUR and the date travels with every row."""
    from ..transport import call_provider

    cur = _norm_currency(currency)
    s = str(start).strip() if start else None
    e = str(end).strip() if end else None
    if not (s or e):
        raise SdkError("usage_error", provider="ecb",
                       detail="ecb_fx_rates requires --start and/or --end (the upstream "
                              "startPeriod/endPeriod window; the full history is ~8,000 rows)")
    params = {"currency": cur, "format": "csvdata"}
    if s:
        params["startPeriod"] = s
    if e:
        params["endPeriod"] = e
    r = call_provider(provider, "fx_rates", params, cache=cache, no_cache=no_cache,
                      extra_headers=_CSV_ACCEPT)
    recs = _parse_csv(r["data"])
    rows = []
    for rec in recs:
        try:
            rate = float(rec.get("OBS_VALUE"))
        except (TypeError, ValueError):
            rate = None
        rows.append({
            "currency": rec.get("CURRENCY") or cur,
            "base_currency": rec.get("CURRENCY_DENOM") or "EUR",
            "rate_type": rec.get("EXR_TYPE"),
            "variation": rec.get("EXR_SUFFIX"),
            "date": rec.get("TIME_PERIOD"),
            "rate": rate,
            "status": rec.get("OBS_STATUS") or None,
            "title": rec.get("TITLE") or None,
        })
    rows.sort(key=lambda x: (x.get("date") or ""))
    return {"total": len(rows), "count": len(rows), "rows": rows,
            "unit": f"{cur} per 1 EUR (ECB reference rate)",
            "params": {"currency": cur, "start": s, "end": e}, "_meta": r}
