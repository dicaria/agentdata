"""ukec — UK Electoral Commission political funding provider (donations + loans two faces; keyless).

search.electoralcommission.org.uk/api/search/. Shape verified 2026-10-20: donations carry the full param set
sort/order/et/date/rptPd/prePoll + from/to; loans need the triplicate params loanStatus×2 + register×3 +
isIrishSource×2 — missing params → Total=-1 (fake success); the response is a .NET-family shape —
rows live in **Result (singular)**, the amount key is Value, dates are `/Date(epoch)/`.
Channel note (real-machine Python test 2026-10-20): Node undici hits a connection-level timeout and needs the
curl channel; **Python urllib connects directly with 200** (machine-local probe: donations 200), so the default
urllib path is used — gating is client-stack dependent, verify each stack on the real machine.
urllib cannot assemble repeated query keys → the full param set is baked into op.path (the dynamic keys
query/start/rows/from/to are appended by core).
rows is hard-clamped to 50: verified 2026-10-26, rows=51→50 and 200→50 (an earlier note saying "100 = polite cap"
never actually got 50+ rows — the old verb face's limit_applied=100 only ever got 50 upstream).
TTL 24h (quarterly cadence, rows change slowly); polite rate 0.5 rps.
"""
import re
from datetime import date

from ..errors import SdkError

provider = {
    "id": "ukec",
    "baseUrl": "https://search.electoralcommission.org.uk/api/search",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "donations": {"path": "/donations?sort=AcceptedDate&order=desc&et=pp&date=Accepted&rptPd=&prePoll=false"},
        "loans": {"path": "/loans?sort=StartDate&order=desc&loanStatus=outstanding&loanStatus=ended&register=gb&register=ni&register=none&isIrishSourceYes=true&isIrishSourceNo=true"},
    },
    "ttl": {"donations": 24 * 3600, "loans": 24 * 3600},
}

REGISTER_START = "2001-02-16"  # PPERA 2000 in force (register origin) — the default for the full-history window


def date_window(_from=None, to=None):
    """Complete the ends into a full range (guards against the -1 fake success caused by donations' from/to
    defaults; the edgar-fts end-completion has the same semantics)."""
    f = str(_from or REGISTER_START)
    t = str(to or date.today().isoformat())
    return {"params": {"from": f, "to": t}, "date_range": {"from": f, "to": t}}


def _dotnet_date(v):
    """/Date(1762214400000)/ → ISO date; non-.NET date values pass through unchanged."""
    m = re.search(r"/Date\((\d+)\)/", str(v or ""))
    if m:
        return date.fromtimestamp(int(m.group(1)) // 1000).isoformat()
    return v


def _pick(row, *keys):
    for k in keys:
        if row.get(k) is not None:
            return row[k]
    return None


def _to_rows(data):
    """Row normalization: .NET PascalCase keys (Result, singular, array); the donations and loans faces share
    the same shape (same Value key).
    Loan rows have no LenderName key — the counterparty is in LoanParticipantName (probed in the 2026-10-21 audit,
    fixing the bug where the lender name on the loans face was always null); the loan type key is LoanType,
    not TypeDescription."""
    return [{
        "donor_or_lender": _pick(d, "DonorName", "LenderName", "LoanParticipantName"),
        "recipient": _pick(d, "RegulatedEntityName", "RecipientName"),
        "recipient_registration": _pick(d, "CompanyRegistrationNumber"),
        "value_gbp": _pick(d, "Value", "AcceptedValue"),
        "date": _dotnet_date(_pick(d, "AcceptedDate", "StartDate")),
        "type_description": _pick(d, "DonationType", "TypeDescription", "LoanType"),
        "donation_action": _pick(d, "DonationAction"),
        "ec_ref": _pick(d, "ECRef"),
    } for d in ((data or {}).get("Result") or (data or {}).get("Results") or [])[:100]]


def search_donations(query, *, _from=None, to=None, limit=20, cache=None, no_cache=False):
    """→ {total, rows[], date_range, _meta}; query = donor/regulated-entity name, contains-match."""
    from ..transport import call_provider

    q = str(query or "").strip()
    if not q:
        raise SdkError("usage_error", provider="ukec", detail="donations requires query (donor / regulated-entity name)")
    win = date_window(_from, to)
    size = min(max(1, int(limit or 20)), 100)  # the verb face keeps the inherited behaviour (upstream hard-clamps to 50, see the module header — overturned 2026-10-26)
    r = call_provider(provider, "donations", {
        "query": q, "start": 0, "rows": size, **win["params"],
    }, cache=cache, no_cache=no_cache)
    return {"total": (r["data"] or {}).get("Total"), "rows": _to_rows(r["data"]),
            "limit_applied": size, "date_range": win["date_range"], "_meta": r}


def search_loans(query, *, limit=20, cache=None, no_cache=False):
    """→ {total, rows[], _meta}; the loans face (the regulatory params are baked into the path)."""
    from ..transport import call_provider

    q = str(query or "").strip()
    if not q:
        raise SdkError("usage_error", provider="ukec", detail="loans requires query (lender / borrower name)")
    size = min(max(1, int(limit or 20)), 100)  # the verb face keeps the inherited behaviour (upstream hard-clamps to 50, see the module header — overturned 2026-10-26)
    r = call_provider(provider, "loans", {
        "query": q, "start": 0, "rows": size,
    }, cache=cache, no_cache=no_cache)
    return {"total": (r["data"] or {}).get("Total"), "rows": _to_rows(r["data"]), "limit_applied": size, "_meta": r}


def _wall_rows_limit(limit):
    lim = int(limit or 20)
    if not 1 <= lim <= 50:
        raise SdkError("usage_error", provider="ukec",
                       detail=f"limit must be 1-50 (upstream rows hard clamp: verified 2026-10-26, 51→50 and 200→50), got \"{limit}\"")
    return lim


def donations_raw(query, *, _from=None, to=None, limit=20, start=0, cache=None, no_cache=False):
    """Flat-panel low-level face: query/from/to/start/rows go through with upstream verbatim names (donations face).

    → {total, rows[], limit_applied, date_range, params, _meta}. When the window is missing we complete the ends
    (a missing from/to → upstream Total=-1 fake success — we fill from the 2001-02-16 register origin to today);
    limit wall 1-50 (upstream rows hard clamp of 50, verified 2026-10-26)."""
    from ..transport import call_provider

    q = str(query or "").strip()
    if not q:
        raise SdkError("usage_error", provider="ukec", detail="donations requires query (donor / regulated-entity name)")
    lim = _wall_rows_limit(limit)
    win = date_window(_from, to)
    params = {"query": q, "start": max(0, int(start or 0)), "rows": lim, **win["params"]}
    r = call_provider(provider, "donations", params, cache=cache, no_cache=no_cache)
    return {"total": (r["data"] or {}).get("Total"), "rows": _to_rows(r["data"]),
            "limit_applied": lim, "date_range": win["date_range"], "params": params, "_meta": r}


def loans_raw(query, *, limit=20, start=0, cache=None, no_cache=False):
    """Flat-panel low-level face: query/start/rows go through with upstream verbatim names (loans face; the
    regulatory triplicate is baked into op.path).

    → {total, rows[], limit_applied, params, _meta}; the limit wall is the same as for donations
    (upstream hard clamp 50)."""
    from ..transport import call_provider

    q = str(query or "").strip()
    if not q:
        raise SdkError("usage_error", provider="ukec", detail="loans requires query (lender / borrower name)")
    lim = _wall_rows_limit(limit)
    params = {"query": q, "start": max(0, int(start or 0)), "rows": lim}
    r = call_provider(provider, "loans", params, cache=cache, no_cache=no_cache)
    return {"total": (r["data"] or {}).get("Total"), "rows": _to_rows(r["data"]),
            "limit_applied": lim, "params": params, "_meta": r}
