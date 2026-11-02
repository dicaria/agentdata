"""safety_gate — EU Safety Gate (the ex-RAPEX rapid alert system for dangerous non-food products)
weekly-report XML face provider (ec.europa.eu/safety-gate-alerts/api/download/; keyless).

healthcare domain (0.3.19; admitted 2026-11-02, probed). Shapes verified by first-hand live probing
2026-11-02 (the probe corpus lives in tmp/probe-ca-eu-faces/):
GET /safety-gate-alerts/api/download/weeklyReport/list/xml/en
  → the whole weekly-report index in ONE XML document (1,122 reports measured 2026-11-02;
    Report-2005-1 → Report-2026-43). Each <weeklyReport> entry: reference (Report-YYYY-WW),
    publicationDate (dd/mm/yyyy), year/month/day/week, and URL — the URL path embeds the numeric
    reportId (…/detail/xml/10000329), which is the join key into the detail face.
GET /safety-gate-alerts/api/download/weeklyReport/detail/xml/<reportId>?language=en&search=WEB_REPORT|:|<reportId>,
  → the single weekly report as XML: a <Safety-Gate> root (report_language/report_date/report_year/
    report_week) wrapping N <notifications> entries (67 measured for report 10000329 = 2026-W43).
    Alert fields: caseNumber (SR/03023/26), reference (the alert-detail URL → the numeric alert id),
    category, product, brand, name, type_numberOfModel, batchNumber, barcode, riskType, danger
    (the risk narrative), measures (the concatenated operator/measure/effective-date blocks),
    URLrecall, description, notifyingCountry, countryOfOrigin, type (Consumer…), level
    (Serious risk…), onlineTrader, companyRecallCode, productionDates.
    language is a query param but search is the SPA's own echo parameter — both are FIXED for this
    face (constructed from the report id; the en channel is the one probed).
The list/detail pair is the same shape family as gb_tna_caselaw (an XML face among JSON APIs).
Local row slicing (limit/skip) and the year post-filter slice the single cached full documents.
TTL: list 24h (new reports land weekly) / detail 7 days (a published weekly report is immutable);
polite rate 1 rps (the download family publishes no quota).
"""
import re
import xml.etree.ElementTree as ET

from ..errors import SdkError

provider = {
    "id": "safety_gate",
    "baseUrl": "https://ec.europa.eu",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "weekly_list": {"path": "/safety-gate-alerts/api/download/weeklyReport/list/xml/en", "accept": "text"},
        # the detail query string is baked into the path byte-exact as probed (the ukec shape: urlencode
        # would re-encode the SPA's echo parameter WEB_REPORT|:|<id>, — a silent near-miss risk not worth taking)
        "weekly_detail": {"path": "/safety-gate-alerts/api/download/weeklyReport/detail/xml/{report_id}"
                                   "?language=en&search=WEB_REPORT%7C:%7C{report_id},",
                          "accept": "text"},
    },
    "ttl": {"weekly_list": 24 * 3600, "weekly_detail": 7 * 86400},
}

_REPORT_ID = re.compile(r"/detail/xml/(\d+)")   # the list face's download URL → the report id
_ALERT_ID = re.compile(r"alertDetail/(\d+)")    # the detail rows' reference URL → the alert id (a different path shape)


def _txt(el):
    return (el.text or "").strip() or None if el is not None else None


def alerts_from_upstream(xml_text):
    """The list XML → weekly-report index rows (pure function, offline-testable).

    The reportId lives only inside the URL element — it is carved out here as the join key."""
    root = ET.fromstring(xml_text)
    rows = []
    for wr in root.iter("weeklyReport"):
        url = _txt(wr.find("URL")) or ""
        rid = _REPORT_ID.search(url)
        rows.append({
            "report_id": rid.group(1) if rid else None,   # the join key into the detail face
            "reference": _txt(wr.find("reference")),       # Report-YYYY-WW
            "publication_date": _txt(wr.find("publicationDate")),
            "year": _txt(wr.find("year")),
            "week": _txt(wr.find("week")),
            "url": url or None,
        })
    return {"rows": rows, "count": len(rows)}


def report_from_upstream(xml_text, report_id):
    """The detail XML → {report header, rows[]} (pure function, offline-testable)."""
    root = ET.fromstring(xml_text)
    rows = []
    for n in root.iter("notifications"):
        ref_url = _txt(n.find("reference")) or ""
        aid = _ALERT_ID.search(ref_url)
        rows.append({
            "order": _txt(n.find("order")),
            "case_number": _txt(n.find("caseNumber")),
            "alert_id": aid.group(1) if aid else None,     # the numeric id from the alert-detail URL
            "alert_url": ref_url or None,
            "category": _txt(n.find("category")),
            "product": _txt(n.find("product")),
            "brand": _txt(n.find("brand")),
            "name": _txt(n.find("name")),
            "type_number_of_model": _txt(n.find("type_numberOfModel")),
            "batch_number": _txt(n.find("batchNumber")),
            "barcode": _txt(n.find("barcode")),
            "risk_type": _txt(n.find("riskType")),         # e.g. "Electric shock, Fire"
            "danger": _txt(n.find("danger")),               # the risk narrative
            "measures": _txt(n.find("measures")),           # operator/measure/effective-date blocks
            "url_recall": _txt(n.find("URLrecall")),
            "description": _txt(n.find("description")),
            "notifying_country": _txt(n.find("notifyingCountry")),
            "country_of_origin": _txt(n.find("countryOfOrigin")),
            "type": _txt(n.find("type")),                   # e.g. Consumer
            "level": _txt(n.find("level")),                 # e.g. Serious risk
            "online_trader": _txt(n.find("onlineTrader")),
            "company_recall_code": _txt(n.find("companyRecallCode")),
            "production_dates": _txt(n.find("productionDates")),
        })
    return {
        "report_id": str(report_id),
        # the detail XML carries no Report-YYYY-WW reference field — the caller stitches it from the
        # list face; the report_year/report_week pair below is the upstream's own framing
        "report_date": _txt(root.find("report_date")),
        "report_year": _txt(root.find("report_year")),
        "report_week": _txt(root.find("report_week")),
        "report_language": _txt(root.find("report_language")),
        "rows": rows, "count": len(rows),
    }


def _slice(rows, limit, skip):
    off = int(skip) if skip is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="safety_gate", detail=f"skip must be >=0, got \"{skip}\"")
    size = int(limit) if limit is not None else 200
    if size < 1:
        raise SdkError("usage_error", provider="safety_gate", detail=f"limit must be >=1 (local post-slice, no upstream cap), got \"{limit}\"")
    return rows[off:off + size]


def weekly_list_raw(*, year=None, limit=200, skip=0, cache=None, no_cache=False):
    """Flat-panel low-level face: the weekly-report index (1,122 reports 2005→now, one cached XML).

    year = an optional local post-filter on the report year (the upstream index has no filter —
    it always serves the whole index); limit/skip is a local post-slice.
    → {rows[], count, total, params, _meta} — total = the whole index size (post-year-filter)."""
    from ..transport import call_provider

    params = {}
    if year is not None:
        y = str(year).strip()
        if not y.isdigit():
            raise SdkError("usage_error", provider="safety_gate", detail=f"year must be a 4-digit year (a local post-filter on the report index), got \"{year}\"")
        params["year"] = y
    r = call_provider(provider, "weekly_list", {}, cache=cache, no_cache=no_cache)
    out = alerts_from_upstream(r["data"])
    rows = [x for x in out["rows"] if (not params.get("year") or x["year"] == params["year"])]
    rows = _slice(rows, limit, skip)
    return {"rows": rows, "count": len(rows), "total": len(out["rows"]) if not params.get("year")
            else sum(1 for x in out["rows"] if x["year"] == params["year"]),
            "params": params or None, "_meta": r}


def _clean_report_id(report_id):
    """Numeric reportId; a pasted detail URL gets its id carved out (the join key echoed by the list rows)."""
    s = str(report_id or "").strip()
    m = _REPORT_ID.search(s)
    if m:
        s = m.group(1)
    if not s.isdigit():
        raise SdkError("usage_error", provider="safety_gate",
                       detail=f"report_id must be the numeric report id (e.g. 10000329 — the report_id field echoed by safety_gate_alerts; a pasted detail URL also works), got \"{report_id}\"")
    return s


def weekly_detail_raw(report_id, *, limit=200, skip=0, cache=None, no_cache=False):
    """Flat-panel low-level face: one weekly report's alerts (the detail XML — 67 alerts for 2026-W43).

    → {report header…, rows[], count, params, _meta} — the alert rows carry caseNumber/risk/level/
    notifyingCountry/countryOfOrigin/onlineTrader (the company-relevant edges) verbatim."""
    from ..transport import call_provider

    rid = _clean_report_id(report_id)
    params = {"report_id": rid}
    r = call_provider(provider, "weekly_detail", params, cache=cache, no_cache=no_cache)
    out = report_from_upstream(r["data"] or "", rid)
    rows = _slice(out["rows"], limit, skip)
    return {**out, "rows": rows, "count": len(rows), "params": params, "_meta": r}
