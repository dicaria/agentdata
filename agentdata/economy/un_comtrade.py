"""un_comtrade — UN Comtrade public preview API (comtradeapi.un.org; keyless, no registration).

One face: trade (one reporter x partner x period x commodity trade flow).

Channels (verified 2026-11-02, tmp/probe-economy/):
  * data: GET /public/v1/preview/{type}/{freq}/{cl}?reporterCode=&period=&partnerCode=&cmdCode=
    &flowCode=&maxRecords=&includeDesc=
    -> {"elapsedTime":"0.95 secs","count":1,"data":[{typeCode, freqCode, refPeriodId, period,
        reporterCode, reporterISO, reporterDesc, flowCode, flowDesc, partnerCode, partnerISO,
        partnerDesc, partner2Code/ISO/Desc, classificationCode, cmdCode, cmdDesc, customsCode,
        mosCode, motCode, qtyUnitCode, qty, netWgt, grossWgt, cifvalue, fobvalue, primaryValue,
        isAggregate}], "error":""}
    The preview answer is capped at 500 records; the full subscription API is keyed (out of scope).
  * areas: GET /files/v1/app/reference/partnerAreas.json -> 310 area rows {id, text,
    PartnerCode, PartnerDesc, PartnerCodeIsoAlpha2, PartnerCodeIsoAlpha3, isGroup}.

The area-code trap (the reference is NOT a clean ISO3 map):
  * 16 ISO3 codes carry SEVERAL rows — the historical ones carry a "(...YYYY)" suffix in the
    text (Germany: "Fed. Rep. of Germany (...1990)" = 280 vs the current "Germany" = 276);
  * the USA carries THREE rows: 840 "United States of America", 842 "USA", 841 "USA and Puerto
    Rico (...1980)" — and the live preview answers reporterCode=842 for the USA (840 is the
    ISO 3166 numeric, 842 is the Comtrade trade code). So a naive "ISO3 -> code" dict built by
    insertion order picks the WRONG code (841) — the resolution rule below drops the historical
    rows and then prefers the shortest current name, which reproduces every current code
    (USA 842, DEU 276, FRA 251, IND 699, PAK 586, VNM 704, NOR 579 …);
  * reporterCode=USA (the ISO3 string) is a 400 "The field reporterCode is invalid" — the
    numeric code is mandatory, hence the translation step;
  * partner 0 = the World aggregate (partnerISO "W00").
Rate: the preview answers with a rate-limit header in the paid API; the public preview is
polite-tier 0.5 rps / burst 2. TTL: 12h (the preview data is refreshed hourly).
"""
from ..errors import SdkError

provider = {
    "id": "un_comtrade",
    "baseUrl": "https://comtradeapi.un.org",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "trade": {"path": "/public/v1/preview/{type_code}/{freq_code}/{cl_code}", "notFound": [404]},
        "areas": {"path": "/files/v1/app/reference/partnerAreas.json", "notFound": [404]},
    },
    "ttl": {"trade": 12 * 3600, "areas": 7 * 86400},
}

_PREVIEW_CAP = 500     # the public preview answers at most 500 records per call


def _norm_code(value, what):
    """A Comtrade area code: digits pass through, an ISO3 code is translated."""
    v = str(value or "").strip()
    if not v:
        return None
    if v.isdigit():
        return int(v)
    return v.upper()


def _pick_area(rows, iso3):
    """The Comtrade code of one ISO3 area, resolved against the reference rows.
    Rule (verified against the live preview): drop the historical rows (their text carries a
    "(...YYYY)" suffix), then prefer the shortest current name — USA -> 842 (not 840, not 841),
    DEU -> 276, FRA -> 251, IND -> 699, PAK -> 586."""
    code = str(iso3 or "").strip().upper()
    if not code:
        return None
    cands = [r for r in rows if (r.get("PartnerCodeIsoAlpha3") or "").strip().upper() == code]
    if not cands:
        return None
    live = [r for r in cands if "(..." not in (r.get("text") or "")]
    pool = live or cands
    best = sorted(pool, key=lambda r: (len((r.get("text") or "").strip()), r.get("PartnerCode") or 0))[0]
    return best.get("PartnerCode")


def _areas(cache=None, no_cache=False):
    """-> (rows, meta): the area reference table (310 rows)."""
    from ..transport import call_provider
    r = call_provider(provider, "areas", {}, cache=cache, no_cache=no_cache)
    data = r["data"]
    rows = data.get("results") if isinstance(data, dict) else None
    if rows is None:
        rows = data if isinstance(data, list) else []
    return rows, r


def _resolve_area(value, what, *, cache=None, no_cache=False):
    """An area argument -> the numeric Comtrade code (the ISO3 is translated)."""
    v = str(value or "").strip()
    if not v:
        raise SdkError("usage_error", provider="un_comtrade",
                       detail=f"un_comtrade_trade requires {what}")
    if v.isdigit():
        return int(v)
    up = v.upper()
    if up in ("W00", "WORLD", "WLD"):
        return 0
    rows, meta = _areas(cache=cache, no_cache=no_cache)
    code = _pick_area(rows, up)
    if code is None:
        raise SdkError("upstream_not_found", provider="un_comtrade",
                       detail=f"No Comtrade area code for '{v}' (the area reference has no such "
                              "ISO3 code — check the spelling)")
    return int(code)


def _row(rec):
    return {
        "type_code": rec.get("typeCode"),
        "freq_code": rec.get("freqCode"),
        "period": rec.get("period"),
        "ref_period_id": rec.get("refPeriodId"),
        "ref_year": rec.get("refYear"),
        "reporter_code": rec.get("reporterCode"),
        "reporter_iso3": rec.get("reporterISO"),
        "reporter_name": rec.get("reporterDesc"),
        "flow_code": rec.get("flowCode"),
        "flow_name": rec.get("flowDesc"),
        "partner_code": rec.get("partnerCode"),
        "partner_iso3": rec.get("partnerISO"),
        "partner_name": rec.get("partnerDesc"),
        "partner2_code": rec.get("partner2Code"),
        "partner2_iso3": rec.get("partner2ISO"),
        "classification_code": rec.get("classificationCode"),
        "cmd_code": rec.get("cmdCode"),
        "cmd_name": rec.get("cmdDesc"),
        "customs_code": rec.get("customsCode"),
        "customs_name": rec.get("customsDesc"),
        "mot_code": rec.get("motCode"),
        "mot_name": rec.get("motDesc"),
        "qty_unit_code": rec.get("qtyUnitCode"),
        "qty_unit": rec.get("qtyUnitAbbr"),
        "qty": rec.get("qty"),
        "net_weight": rec.get("netWgt"),
        "gross_weight": rec.get("grossWgt"),
        "cif_value": rec.get("cifvalue"),
        "fob_value": rec.get("fobvalue"),
        "primary_value": rec.get("primaryValue"),
        "is_aggregate": rec.get("isAggregate"),
        "is_reported": rec.get("isReported"),
    }


def trade_raw(reporter, *, period=None, partner=None, cmd=None, flow=None, type_code="C",
              freq_code="A", cl_code="HS", max_records=500, partner2=None, customs=None,
              mot=None, cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /public/v1/preview/{type}/{freq}/{cl}
    reporter = the reporting country (ISO3 or the numeric code — the ISO3 is translated through
    the area reference); period = the upstream period (2023 / 202301 / a comma list);
    partner = the partner area (ISO3 or code; 0 / "W00" = the World aggregate);
    cmd = the commodity code (a comma list; TOTAL = all goods); flow = the trade flow
    (X export / M import / "X,M"); type_code / freq_code / cl_code = the path segments
    (C commodities / A annual / HS classification); max_records 1-500 (the preview cap)."""
    from ..transport import call_provider

    rep = _resolve_area(reporter, "--reporter (the reporting country)", cache=cache, no_cache=no_cache)
    per = str(period or "").strip()
    if not per:
        raise SdkError("usage_error", provider="un_comtrade",
                       detail="un_comtrade_trade requires --period (e.g. 2023 or 202301)")
    par = _resolve_area(partner if partner not in (None, "") else "W00",
                         "--partner (the partner area; '0' = the World aggregate)",
                         cache=cache, no_cache=no_cache)
    mr = int(max_records) if max_records is not None else 500   # `or` would swallow 0 into the default
    if not 1 <= mr <= _PREVIEW_CAP:
        raise SdkError("usage_error", provider="un_comtrade",
                       detail=f"maxRecords must be 1-{_PREVIEW_CAP} (the public preview cap)")
    params = {
        "type_code": str(type_code or "C").strip().upper(),
        "freq_code": str(freq_code or "A").strip().upper(),
        "cl_code": str(cl_code or "HS").strip().upper(),
        "reporterCode": rep,
        "period": per,
        "partnerCode": par,
        "cmdCode": str(cmd or "TOTAL").strip(),
        "maxRecords": mr,
        "includeDesc": "true",
    }
    if flow:
        params["flowCode"] = str(flow).strip().upper()
    if partner2 not in (None, ""):
        params["partner2Code"] = _resolve_area(partner2, "--partner2", cache=cache, no_cache=no_cache)
    if customs not in (None, ""):
        params["customsCode"] = str(customs).strip()
    if mot not in (None, ""):
        params["motCode"] = str(mot).strip()
    r = call_provider(provider, "trade", params, cache=cache, no_cache=no_cache)
    data = r["data"]
    if not isinstance(data, dict):
        raise SdkError("upstream_unavailable", provider="un_comtrade",
                       detail=f"Unexpected Comtrade payload shape: {str(data)[:160]!r}")
    err = (data.get("error") or "").strip()
    if err:
        raise SdkError("upstream_unavailable", provider="un_comtrade", detail=f"Comtrade: {err}")
    recs = data.get("data") or []
    rows = [_row(x) for x in recs]
    return {"total": data.get("count"), "count": len(rows), "rows": rows,
            "elapsed": data.get("elapsedTime"),
            "params": {k: v for k, v in params.items() if k not in ("type_code", "freq_code", "cl_code")},
            "_meta": r}
