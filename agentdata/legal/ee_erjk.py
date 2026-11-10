"""ee_erjk — Estonian Party Financing Surveillance Committee open data (erjk.ee/avaandmed; keyless).

legal party-finance faces (0.3.50; admitted 2026-11-09, probed tmp/probe-sdk0350/ + the
2026-11-05 recipe round tmp/probe-us-wcluster/). The SDK's first EE jurisdiction and the
party-finance family's first EE pillar: Estonian political-party money in two layers —
(1) the quarterly-reports receipts matrix (party × period × donation category, 455 rows 2013→2026
in one shot) and (2) the election/candidate report (the register's company-hard-key layer:
entries carry payer + reg_code, and reg_code is a direct RIK äriregister registry code).

API shape (OpenAPI 3, 19 endpoints — erjkapi.yaml): the API host carries no www and every path is
language-prefixed (/et/api/… — the bare /api/events is a 301 to /et/api/events, followed here
explicitly). Two faces, one upstream call each (the election face's discovery step is cached
separately): /quarterly-reports/queries/receipts?party_id=all&category_id=all&period=show_all =
the whole matrix; /events/{eid}/organisation-reports/{oid} = the organisation's report slots
(Põhiaruanne = main, Täiendaruanne = supplementary); /events/reports/{rid}?report_type=receipts =
{person_key: [entries]} keyed "NAME DD.MM.YYYY" (the candidate/official receiving), entries
{payment_date, receipt_group, payer, reg_code, amount}.

Election-law stance (the recipe's measured truth): party donations are natural-persons-only BY
LAW — the corporate money edge lives only in the election/candidate layer (payer + reg_code),
which is exactly this face's projection.
"""
import re

from ..errors import SdkError

provider = {
    "id": "ee_erjk",
    "baseUrl": "https://erjk.ee",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "receipts_matrix": {"path": "/et/api/quarterly-reports/queries/receipts"},
        "parties": {"path": "/et/api/quarterly-reports/parties"},
        "org_reports": {"path": "/et/api/events/{event_id}/organisation-reports/{organisation_id}"},
        "report": {"path": "/et/api/events/reports/{report_id}"},
    },
    "ttl": {"receipts_matrix": 24 * 3600, "parties": 24 * 3600,
            "org_reports": 24 * 3600, "report": 7 * 86400},
}

_PERSON_KEY = re.compile(r"^(?P<name>.+?)\s(?P<birthdate>\d{2}\.\d{2}\.\d{4})$")
# the main-report slot (Põhiaruanne); supplementary slots (Täiendaruanne N. kv YYYY) ride available_reports
_MAIN_SLOT = "Põhiaruanne"


def _float(cell):
    """"1400.00" → 1400.0; ""/None → None (the matrix's amount column is a decimal string)."""
    if cell is None or cell == "":
        return None
    try:
        return float(str(cell).replace(",", "."))
    except ValueError:
        return None


def quarterly_reports_raw(party_id=None, period=None, limit=100,
                          cache=None, no_cache=False):
    """The receipts matrix one-shot → {party_id, period, total, rows[], params, _meta}.

    party_id narrows to one party (the integer id from the parties register — 163 = Keskerakond,
    158 = Reformierakond; default 'all'); period narrows to one year ("2025"; default 'show_all'
    = the whole 2013→ history); limit is a local slice over the (at most few-hundred-row) matrix.
    Rows are the upstream's own aggregates verbatim — {party_id, party_name, _party_short,
    period, category_id, category_name, amount} — one row per party × period × donation
    category (Rahaline annetus = cash donation etc.)."""
    from ..transport import call_provider

    params = {"party_id": (str(party_id).strip() if party_id not in (None, "") else "all"),
              "category_id": "all",
              "period": (str(period).strip() if period not in (None, "") else "show_all")}
    if params["period"] != "show_all" and not (params["period"].isdigit() and 2000 <= int(params["period"]) <= 2100):
        raise SdkError("usage_error", provider="ee_erjk",
                       detail=f"period is a year like \"2025\" or the default show_all, got '{period}'")
    n = int(limit)
    if n < 1:
        raise SdkError("usage_error", provider="ee_erjk", detail=f"limit must be ≥1, got '{limit}'")

    r = call_provider(provider, "receipts_matrix", params, cache=cache, no_cache=no_cache)
    data = r["data"] or []
    rows = []
    for it in data:
        row = dict(it)
        row["amount"] = _float(it.get("amount"))
        rows.append(row)
    return {"party_id": params["party_id"], "period": params["period"],
            "total": len(rows), "rows": rows[:n], "params": params, "_meta": r}


def election_reports_raw(event_id=None, organisation_id=None, report_id=None, limit=500,
                         cache=None, no_cache=False):
    """One election/candidate receipts report → {report_id, report_title, available_reports,
    total, rows[], params, _meta} — the register's company-hard-key layer.

    Two entry forms: report_id directly (the exact slot, from a previous call's
    available_reports), or event_id + organisation_id (the discovery pair — the face resolves
    the organisation's slots and takes the MAIN report Põhiaruanne; every slot rides
    available_reports for pinning). Rows flatten {person_key: [entries]}: one row per entry with
    person (verbatim NAME), birthdate (DD.MM.YYYY, from the key — the register's own key form,
    kept verbatim not re-typed), payment_date, receipt_group, payer, **reg_code** (the RIK
    äriregister registry code — empty for natural-person entries, the company edge when set),
    amount (int)."""
    from ..transport import call_provider

    n = int(limit)
    if n < 1:
        raise SdkError("usage_error", provider="ee_erjk", detail=f"limit must be ≥1, got '{limit}'")
    resolved_title, available = None, []
    if report_id is None:
        if event_id is None or organisation_id is None:
            raise SdkError("usage_error", provider="ee_erjk",
                           detail="give report_id (exact slot) or event_id + organisation_id (the "
                                  "discovery pair — resolves the organisation's report slots)")
        inv = call_provider(provider, "org_reports",
                            {"event_id": str(event_id), "organisation_id": str(organisation_id)},
                            cache=cache, no_cache=no_cache)
        slots = inv["data"] or []
        if not slots:
            raise SdkError("upstream_not_found", provider="ee_erjk",
                           detail=f"no report slots for organisation {organisation_id} under event "
                                  f"{event_id} (wrong ids, or the organisation filed nothing)")
        available = [{"report_id": s.get("report_id"), "report_title": s.get("report_title")}
                     for s in slots]
        chosen = next((s for s in slots if s.get("report_title") == _MAIN_SLOT), slots[0])
        report_id, resolved_title = chosen.get("report_id"), chosen.get("report_title")
    r = call_provider(provider, "report",
                      {"report_id": str(report_id), "report_type": "receipts"},
                      cache=cache, no_cache=no_cache)
    doc = r["data"]
    if not isinstance(doc, dict):
        raise SdkError("upstream_unavailable", provider="ee_erjk",
                       detail="the receipts report did not answer the {person: [entries]} shape "
                              "(upstream format change?)")
    rows = []
    for person_key, entries in doc.items():
        m = _PERSON_KEY.match(str(person_key or ""))
        person = m.group("name") if m else (str(person_key) if person_key else None)
        birthdate = m.group("birthdate") if m else None
        for e in entries or []:
            if not isinstance(e, dict):
                continue
            rows.append({"person": person, "birthdate": birthdate,
                         "payment_date": e.get("payment_date"),
                         "receipt_group": e.get("receipt_group"),
                         "payer": e.get("payer") or None,
                         "reg_code": e.get("reg_code") or None,
                         "amount": e.get("amount")})
    out = {"report_id": str(report_id), "report_title": resolved_title, "total": len(rows),
           "rows": rows[:n],
           "params": {"report_id": str(report_id), "report_type": "receipts"}, "_meta": r}
    if available:
        out["available_reports"] = available
    return out
