"""de_lobbyregister — German Bundestag lobby register (Lobbyregister des Deutschen
Bundestages, www.lobbyregister.bundestag.de, keyless JSON export).

DE legal face (0.3.60; admitted from the research booklet de-lobbyregister, re-probed live
2026-11-13):

CONTRACT (one keyless export):
  GET /sucheJson?sort=REGISTRATION_DESC → the whole register as JSON (18.0 MB measured),
  keys: $schema / source / sourceUrl / sourceDate / jsonDocumentationUrl / searchUrl /
  searchParameters / resultCount / results[] — 7,044 entries live (measured 2026-11-13).
  The official REST API (v1/v2) is ApiKey-gated, so it is NOT on the route (keyless-only
  ruling) — this export is the machine-readable surface.

Each entry (the register's own shape, R2.27 schema):
  registerNumber (R008328) · registerEntryDetails{registerEntryId, legislation, detailsPageUrl,
  validFromDate} · accountDetails{activeLobbyist, firstPublicationDate,
  accountHasCodexViolations} · lobbyistIdentity{identity (ORGANIZATION|PERSON), name,
  entrustedPersonsCount, membersCount, membershipsCount} · activitiesAndInterests{activity,
  fieldsOfInterest[]} · employeesInvolvedInLobbying{relatedFiscalYear…, employeeFTE} ·
  financialExpenses{financialExpensesEuro} · donators{totalDonationsEuro} ·
  membershipFees{totalMembershipFees} · regulatoryProjects{regulatoryProjectsCount} ·
  statements{statementsCount} · contracts{contractsCount}.
  The money columns (expenses, donations, membership fees) and the project/statement/contract
  counts are the compliance-grade part: they are the German lobbying-law disclosure.

LIVE LAWS (measured 2026-11-13):
  - the export carries NO server-side filter (it is the full register; the SSR page /suche
    supports filter[activelobbyist][true] and pageSize/paging) — the face reads the export
    once (cached, TTL 24 h) and filters locally.
  - the payload is 18 MB — the cached answer is the whole register.

Politeness: 0.2/2, concurrency 1, TTL 24h (the register is published daily).
"""
from ..errors import SdkError

provider = {
    "id": "de_lobbyregister",
    "baseUrl": "https://www.lobbyregister.bundestag.de",
    "rate": {"rps": 0.2, "burst": 2},
    "concurrency": 1,
    "ops": {
        # the full register as JSON (18.0 MB measured; resultCount = 7,044 entries)
        "entries": {"path": "/sucheJson?sort=REGISTRATION_DESC", "timeout": 120.0},
    },
    "ttl": {"entries": 24 * 3600},
}


def _flat(entry):
    """One register entry → the flat row the face returns (the money columns and the
    counts are lifted out of their nested blocks)."""
    ident = entry.get("lobbyistIdentity") or {}
    acct = entry.get("accountDetails") or {}
    red = entry.get("registerEntryDetails") or {}
    act = entry.get("activitiesAndInterests") or {}
    emp = entry.get("employeesInvolvedInLobbying") or {}
    fin = entry.get("financialExpenses") or {}
    don = entry.get("donators") or {}
    fee = entry.get("membershipFees") or {}
    proj = entry.get("regulatoryProjects") or {}
    stm = entry.get("statements") or {}
    con = entry.get("contracts") or {}
    activity = act.get("activity") or {}
    return {
        "register_number": entry.get("registerNumber"),
        "register_entry_id": red.get("registerEntryId"),
        "legislation": red.get("legislation"),
        "details_page_url": red.get("detailsPageUrl"),
        "valid_from": red.get("validFromDate"),
        "first_publication": acct.get("firstPublicationDate"),
        "active": acct.get("activeLobbyist"),
        "codex_violations": acct.get("accountHasCodexViolations"),
        "identity": ident.get("identity"),
        "name": ident.get("name"),
        "entrusted_persons": ident.get("entrustedPersonsCount"),
        "members": ident.get("membersCount"),
        "memberships": ident.get("membershipsCount"),
        "activity_code": activity.get("code"),
        "activity_de": activity.get("de"),
        "fields_of_interest": [f.get("code") for f in (act.get("fieldsOfInterest") or [])
                               if isinstance(f, dict)],
        "employee_fte": emp.get("employeeFTE"),
        "financial_expenses_eur": fin.get("financialExpensesEuro"),
        "total_donations_eur": don.get("totalDonationsEuro"),
        "total_membership_fees": fee.get("totalMembershipFees"),
        "regulatory_projects": proj.get("regulatoryProjectsCount"),
        "statements": stm.get("statementsCount"),
        "contracts": con.get("contractsCount"),
    }


def entries_raw(*, name=None, active=None, identity=None, codex_violations=None,
                legislation=None, limit=50, offset=0, cache=None, no_cache=False):
    """→ {total, rows[], source_date, params, _meta}. The export has no server-side filter —
    the whole register is read once (cached) and filtered locally."""
    from ..transport import call_provider

    try:
        lim = int(limit)
        off = int(offset)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="de_lobbyregister",
                       detail=f"limit/offset must be integers, got limit={limit!r} offset={offset!r}")
    if lim < 1:
        raise SdkError("usage_error", provider="de_lobbyregister", detail=f"limit must be >= 1, got {lim}")
    if off < 0:
        raise SdkError("usage_error", provider="de_lobbyregister", detail=f"offset must be >= 0, got {off}")

    r = call_provider(provider, "entries", {}, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    entries = doc.get("results")
    if not isinstance(entries, list):
        raise SdkError("upstream_unavailable", provider="de_lobbyregister",
                       detail="the register export answered an unexpected shape (no results array)")
    rows = [_flat(e) for e in entries]

    q = str(name).strip().lower() if name else None
    if q:
        rows = [x for x in rows if q in (x.get("name") or "").lower()]
    if active is not None:
        rows = [x for x in rows if bool(x.get("active")) is bool(active)]
    if identity:
        rows = [x for x in rows if (x.get("identity") or "").upper() == str(identity).upper()]
    if codex_violations is not None:
        rows = [x for x in rows if bool(x.get("codex_violations")) is bool(codex_violations)]
    if legislation:
        rows = [x for x in rows if str(x.get("legislation") or "") == str(legislation)]

    total = len(rows)
    return {
        "total": total,
        "rows": rows[off:off + lim],
        "source_date": doc.get("sourceDate"),
        "source_url": doc.get("sourceUrl"),
        "register_total": doc.get("resultCount"),
        "params": {"name": name, "active": active, "identity": identity,
                   "codex_violations": codex_violations, "legislation": legislation,
                   "limit": lim, "offset": off},
        "_meta": r,
    }
