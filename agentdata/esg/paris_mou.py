"""paris_mou — Paris MoU port state control (THETIS public REST, EMSA portal) provider (keyless).

esg port-state supervision axis (2026-10-29, 0.3.5 batch): parismou.org itself is all iframe shells; the real
data door is the EMSA Liferay portlet same-origin REST `portal.emsa.europa.eu/o/portlet-public/rest/*`
(contextRoot is emitted by the inline JS of the portlet page; the full endpoint table lives in the 160KB ExtJS
bundle thetis-public.js). Measured shape (2026-10-29):
- The three GET snapshot faces share the envelope `{results, total, success}`.
  - Detentions: detention/getCurrentDetentions 53 rows (daily rolling — the 10-20 probe saw 48 rows).
  - Bans: ban/getBanShips 486 rows ~1MB, with **ismCompany{id/imoNumber/name/address/city/countryCode}
    embedded = the official ship x management-company edge** (310 rows carry a company IMO number).
  - Low-performance ISM companies: companyperformance/getLowPerformance6MonthsISMCompanies 65 rows
    (**100% carry an IMO company number**, a zero-padded 7-digit string; companyPerformance is mostly LOW with a few MEDIUM).
- Historical inspections: inspection/getPublicInspections **POST form-encoded** — a JSON body is silently
  dropped upstream (200 + total=0, a poisoned empty-window response, measured 2026-10-29) -> the op declares
  `urlencoded: True` (transport extension 7).
  Params: pscInspectionRegime=1 is mandatory (PSC default); periodMin/periodMax dd/mm/yyyy, window <= 3 years;
  **page is the paging switch** — without page the limit is ignored and the whole window is dumped (measured
  limit=25 returned 1,202 rows); with page+start+limit it is start-offset paging (page1/page2 measured zero
  overlap); ismCompanyName/ismCompanyImoNumber query a company directly (+resume window stats
  ships/inspections/detentions/ismDeficiencies/bans).
TTL: detentions 1h (daily rolling); bans/low-performance 6h; inspections 30min (window query replay).
Politeness tier 0.5 rps.
"""
from ..errors import SdkError

provider = {
    "id": "paris_mou",
    "baseUrl": "https://portal.emsa.europa.eu",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "detentions": {"path": "/o/portlet-public/rest/detention/getCurrentDetentions.json"},
        "bans": {"path": "/o/portlet-public/rest/ban/getBanShips.json", "timeout": 45.0},  # ~1MB in one response, the default 20s timed out as measured
        "low_performance": {"path": "/o/portlet-public/rest/companyperformance/getLowPerformance6MonthsISMCompanies.json"},
        "inspections": {
            "path": "/o/portlet-public/rest/inspection/getPublicInspections.json",
            "method": "POST",
            "urlencoded": True,   # extension 7: the body is standard form encoding (a JSON body = silently 0 rows, a poisoned response)
            "idempotent": True,   # read-semantics POST (a search), retryable
        },
    },
    "ttl": {"detentions": 3600, "bans": 21600, "low_performance": 21600, "inspections": 1800},
}


def _flag(d):
    return {"code": d.get("code"), "name": d.get("description")} if isinstance(d, dict) else {"code": None, "name": None}


def _ism_company(c):
    """Embedded ISM management company -> flat row keys (the zero-padded 7-digit official imoNumber string is kept as-is)."""
    if not isinstance(c, dict):
        return {"company_imo_number": None, "company_name": None, "company_address": None,
                "company_city": None, "company_country_code": None, "company_country_name": None}
    return {
        "company_imo_number": c.get("imoNumber"),
        "company_name": c.get("name"),
        "company_address": c.get("address"),
        "company_city": c.get("city"),
        "company_country_code": c.get("countryCode"),
        "company_country_name": c.get("countryDescription"),
    }


def detentions_from_upstream(data):
    """Detentions snapshot -> rows (pure function, offline-testable)."""
    rows = [{
        "id": d.get("id"),
        "imo_number": d.get("imoNumber"),               # ship IMO number (asset key)
        "ship_name": d.get("shipName"),
        "ship_type": (d.get("shipType") or {}).get("description") if isinstance(d.get("shipType"), dict) else None,
        "flag_code": _flag(d.get("flag"))["code"],
        "flag_name": _flag(d.get("flag"))["name"],
        "detention_date": d.get("detentionDate"),        # dd/mm/yyyy
        "detention_port": (d.get("detentionPort") or {}).get("name") if isinstance(d.get("detentionPort"), dict) else None,
        "detention_country_code": ((d.get("detentionPort") or {}).get("country") or {}).get("code") if isinstance(d.get("detentionPort"), dict) else None,
        "reporting_authority": _flag(d.get("detentionReportingAuthority"))["name"],
    } for d in ((data or {}).get("results") or []) if isinstance(d, dict)]
    return {"rows": rows, "count": len(rows)}


def bans_from_upstream(data):
    """Bans face -> rows (the embedded ismCompany is flattened into a ship x management-company edge)."""
    rows = []
    for b in ((data or {}).get("results") or []):
        if not isinstance(b, dict):
            continue
        rows.append({
            "id": b.get("id"),
            "imo_number": b.get("imoNumber"),
            "ship_name": b.get("shipName"),
            "flag_code": _flag(b.get("flag"))["code"],
            "flag_name": _flag(b.get("flag"))["name"],
            "ban_date": b.get("banDate"),                 # dd/mm/yyyy
            "ban_occurrence": b.get("banOccurrence"),
            "ban_order_status": b.get("banOrderStatus"),
            "ban_reason": b.get("banReason"),
            "minimum_duration": b.get("minimumDuration"),
            "banning_authority": _flag(b.get("banningAuthority"))["name"],
            **_ism_company(b.get("ismCompany")),
        })
    return {"rows": rows, "count": len(rows)}


def low_performance_from_upstream(data):
    """Low-performance ISM company list -> rows (rolling 6-month window; 100% carry an IMO company number)."""
    rows = [{
        "id": c.get("id"),
        "imo_number": c.get("imoNumber"),                # IMO company number (zero-padded 7-digit string)
        "name": c.get("name"),
        "address": c.get("address"),
        "city": c.get("city"),
        "country_code": c.get("countryCode"),
        "country_name": c.get("countryDescription"),
        "performance": c.get("companyPerformance"),       # mostly LOW, with a few MEDIUM
        "effect_date": c.get("effectDate"),               # dd/mm/yyyy (listing date)
        "expiry_date": c.get("expiryDate"),
        "status": c.get("ismCompanyStatus"),              # ACTIVE/null
    } for c in ((data or {}).get("results") or []) if isinstance(c, dict)]
    return {"rows": rows, "count": len(rows)}


def inspections_from_upstream(data, params):
    """Historical inspections -> rows + resume window stats (envelope {results, total, resume, success})."""
    rows = [{
        "id": i.get("id"),                                # -> getInspectionDetail?inspectionId= key for the full per-inspection record
        "imo_number": i.get("imoNumber"),
        "ship_name": i.get("shipName"),
        "ship_type": i.get("shipTypeDescription"),
        "flag_code": _flag(i.get("flag"))["code"],
        "flag_name": _flag(i.get("flag"))["name"],
        "age": i.get("age"),
        "inspection_date": i.get("inspectionDate"),        # dd/mm/yyyy
        "inspection_type": (i.get("inspectionType") or {}).get("description") if isinstance(i.get("inspectionType"), dict) else None,
        "member_state": i.get("memberStateDescription"),
        "port_name": i.get("portName"),
        "port_and_ms": i.get("portAndMS"),                 # "Slovenia - Koper"
        "ndeficiencies": i.get("ndeficiencies"),
        "results_desc": i.get("resultsDesc"),
    } for i in ((data or {}).get("results") or []) if isinstance(i, dict)]
    resume = (data or {}).get("resume") or {}
    return {
        "rows": rows,
        "count": len(rows),
        "total": (data or {}).get("total"),
        "resume": {
            "ships": resume.get("ships"),
            "inspections": resume.get("inspections"),
            "detentions": resume.get("detentions"),
            "ism_deficiencies": resume.get("ismDeficiencies"),
            "non_ism_deficiencies": resume.get("nonISMDeficiencies"),
            "bans": resume.get("bans"),
        } if isinstance(resume, dict) else None,
        "paging": {"page": params.get("page"), "start": params.get("start"), "limit": params.get("limit")},
    }


def _check_date(s, label):
    """Strict dd/mm/yyyy validation (the upstream format really is day/month/year — a wrong order silently returns empty)."""
    from datetime import datetime
    try:
        return datetime.strptime(s, "%d/%m/%Y")
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider=provider["id"],
                       detail=f"{label} must be dd/mm/yyyy (e.g. 01/01/2026) — {s!r} does not match as measured")


def detentions_raw(*, cache=None, no_cache=False):
    """0.3.5 flat face internals: the current detentions snapshot in one request (upstream has no filter params).

    -> {rows[], count, params, _meta} — params={} (zero upstream params)."""
    from ..transport import call_provider

    params = {}
    r = call_provider(provider, "detentions", params, cache=cache, no_cache=no_cache)
    return {**detentions_from_upstream(r["data"]), "params": params, "_meta": r}


def bans_raw(*, cache=None, no_cache=False):
    """0.3.5 flat face internals: the bans register in one request (upstream has no filter params).

    -> {rows[], count, params, _meta}."""
    from ..transport import call_provider

    params = {}
    r = call_provider(provider, "bans", params, cache=cache, no_cache=no_cache)
    return {**bans_from_upstream(r["data"]), "params": params, "_meta": r}


def low_performance_raw(*, cache=None, no_cache=False):
    """0.3.5 flat face internals: the low-performance ISM company list in one request (rolling 6-month window, upstream has no filter params).

    -> {rows[], count, params, _meta}."""
    from ..transport import call_provider

    params = {}
    r = call_provider(provider, "low_performance", params, cache=cache, no_cache=no_cache)
    return {**low_performance_from_upstream(r["data"]), "params": params, "_meta": r}


def inspections_raw(*, period_min, period_max, psc_inspection_regime=1, page=1, start=0, limit=50,
                    ism_company_name=None, ism_company_imo_number=None,
                    cache=None, no_cache=False):
    """0.3.5 flat face internals: historical PSC inspection window search (form-encoded POST).

    -> {rows[], count, total, resume, paging, params, _meta}. The <= 3 year window is validated locally first
    (upstream silently returns empty beyond it); **page always travels with the request** (without page the whole
    window is dumped and the limit is void — the face pins the paging semantics)."""
    from ..transport import call_provider

    d1, d2 = _check_date(period_min, "period_min"), _check_date(period_max, "period_max")
    if d2 < d1:
        raise SdkError("usage_error", provider=provider["id"],
                       detail=f"period_max({period_max}) is earlier than period_min({period_min}) — inverted window")
    if (d2 - d1).days > 366 * 3:
        raise SdkError("usage_error", provider=provider["id"],
                       detail=f"the search window of {(d2 - d1).days} days exceeds the 3-year cap (an upstream limit) — split the search")
    params = {
        "pscInspectionRegime": int(psc_inspection_regime),  # mandatory (1 = PSC default regime; without it = 200 empty)
        "periodMin": period_min,
        "periodMax": period_max,
        "page": max(1, int(page)),
        "start": max(0, int(start)),
        "limit": min(500, max(1, int(limit))),
        "ismCompanyName": ism_company_name,
        "ismCompanyImoNumber": ism_company_imo_number,
    }
    r = call_provider(provider, "inspections", params, cache=cache, no_cache=no_cache)
    return {**inspections_from_upstream(r["data"], params), "params": params, "_meta": r}
