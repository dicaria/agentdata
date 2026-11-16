"""us_occ — US Office of the Comptroller of the Currency enforcement actions
(apps.occ.gov/EASearch, keyless).

US legal face (0.3.61; admitted from the research booklet us-occ-enforcement 册 127,
re-probed live 2026-11-16):

CONTRACT:
  1. enforcements — GET /EASearch/Search/ExportToJson → the actions list (200, JSON array):
     14 fields per row — Institution (bank full name) / CharterNumber (the OCC charter =
     the hard join key into the US bank registers) / Company / Individual (the sanctioned
     person) / Location / TypeCode+TypeDescription (C&D, CMP, Prohibition …) / Amount
     (the fine, numeric string) / StartDate (MM/DD/YYYY) / StartDocuments (the official
     AA-ENF-YYYY-NN doc ids — the PDF download key) / TerminationDate+TerminationDocuments
     / DocketNumber (criminal-referral dockets) / SubjectMatters (violation codes, list).
     No params = the FULL HISTORY in one shot (6,072 actions 1989→2026, 1.2MB CSV twin).

LIVE LAWS (measured 2026-11-16, tmp/probe-e3/):
  - q= filters by institution name substring across history ("Wells Fargo" → 164 rows
    incl. National City Bank — the substring matches, not the word).
  - startDteMin/startDteMax take ISO dates (2026-01-01) though the UI renders MM/DD/YYYY.
  - the filter flags are honored: terminatedOnly=true → 2,344 rows (≠ the 50-row 2026
    window); indOnly/instOnly/activeOnly same family.
  - StartDocuments/TerminationDocuments/SubjectMatters arrive as JSON LISTS already; the
    CSV twin carries them pipe-joined and names the type column "Type" vs "TypeDescription".

Politeness: 0.5/4, concurrency 2, TTL 24h (the live database republishes continuously;
full exports are heavy — 1.3MB — so the cache rides along).
"""
from ..errors import SdkError

provider = {
    "id": "us_occ",
    "baseUrl": "https://apps.occ.gov",
    "rate": {"rps": 0.5, "burst": 4},
    "concurrency": 2,
    "ops": {
        "enforcements": {"path": "/EASearch/Search/ExportToJson", "timeout": 90.0},
    },
    "ttl": {"enforcements": 24 * 3600},
}

_FLAGS = ("active_only", "terminated_only", "ind_only", "inst_only")


def parse_row(doc):
    """One upstream row → the flat row (keys snake_cased, Amount floated)."""
    if not isinstance(doc, dict):
        raise SdkError("upstream_unavailable", provider="us_occ",
                       detail="the enforcement export answered an unexpected shape (row is not an object)")
    amount = doc.get("Amount")
    try:
        amount = float(str(amount).replace(",", "")) if str(amount or "").strip() else 0.0
    except ValueError:
        pass
    docs = doc.get("StartDocuments") or []
    return {
        "institution": doc.get("Institution") or None,
        "charter_number": str(doc.get("CharterNumber") or "") or None,
        "company": doc.get("Company") or None,
        "individual": doc.get("Individual") or None,
        "location": doc.get("Location") or None,
        "type_code": doc.get("TypeCode") or None,
        "type_description": doc.get("TypeDescription") or doc.get("Type") or None,
        "amount_usd": amount,
        "start_date": doc.get("StartDate") or None,
        "start_documents": docs,
        "termination_date": doc.get("TerminationDate") or None,
        "termination_documents": doc.get("TerminationDocuments") or [],
        "docket_number": doc.get("DocketNumber") or None,
        "subject_matters": doc.get("SubjectMatters") or [],
        "pdf_urls": [f"https://www.occ.gov/static/enforcement-actions/ea{d}.pdf" for d in docs],
    }


def enforcements_raw(q=None, *, start_dte_min=None, start_dte_max=None,
                     active_only=None, terminated_only=None, ind_only=None, inst_only=None,
                     limit=None, cache=None, no_cache=False):
    """→ {rows[], total, params, _meta}. Enforcement actions (no filter = full history)."""
    from ..transport import call_provider

    params = {}
    if q:
        params["q"] = str(q)
    if start_dte_min:
        params["startDteMin"] = str(start_dte_min)
    if start_dte_max:
        params["startDteMax"] = str(start_dte_max)
    for flag, upstream in zip(_FLAGS, ("activeOnly", "terminatedOnly", "indOnly", "instOnly")):
        v = {"active_only": active_only, "terminated_only": terminated_only,
             "ind_only": ind_only, "inst_only": inst_only}[flag]
        if v is True:
            params[upstream] = "true"
    if not params:
        raise SdkError("usage_error", provider="us_occ",
                       detail="at least one filter is required (q / start_dte_min / a flag) — "
                              "the unfiltered call is the full history (6,000+ rows); "
                              "see the booklet for the bulk path")
    r = call_provider(provider, "enforcements", params, cache=cache, no_cache=no_cache)
    data = r["data"]
    if not isinstance(data, list):
        raise SdkError("upstream_unavailable", provider="us_occ",
                       detail=f"the enforcement export answered an unexpected shape ({type(data).__name__})")
    rows = [parse_row(d) for d in data]
    n = len(rows)
    if limit is not None:
        try:
            rows = rows[: max(0, int(limit))]
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="us_occ", detail=f"limit must be an integer, got {limit!r}")
    return {
        "rows": rows,
        "total": n,
        "truncated": bool(limit is not None and int(limit) < n),
        "params": params,
        "_meta": r,
    }
