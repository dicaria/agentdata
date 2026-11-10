"""ie_sipo — Standards in Public Office Commission lobbying register (api.lobbying.ie; keyless).

legal lobbying face (0.3.50; admitted 2026-11-09, probed tmp/probe-sdk0350/). The Regulation of
Lobbying Act 2015 register: 123,591 returns live 2026-11-09 (Total echo), each row a lobbying
return embedding the three-party shape — Lobbyist (the lobbying firm/employer, with
CompanyRegistrationNumber = the CRO key, populated on 43.6% of registrants per the 2026-11-05
recipe census) × Clients (the lobbied-for, carrying Cro) × Dpos (the lobbied designated public
officials). IE's register is the second lobbying register in the SDK after lda_filings (US).

**The 13-mandatory-params wall (pinned live)**: /api/Search 404s unless EVERY parameter rides the
query string — empty values explicit (currentPage=1&pageSize=20&queryText=&subjectMatters=…
&lobbyistId=). The transport drops None params, so the face assembles the full 13 with ""
defaults; only the wanted filters carry values.

**Date shape**: returnDateFrom/returnDateTo are DD-MM-YYYY (an ISO date is answered HTTP 500 —
the wall is local: shape + calendar validated before the call).
"""
from ..errors import SdkError

provider = {
    "id": "ie_sipo",
    "baseUrl": "https://api.lobbying.ie",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/api/Search", "timeout": 60.0},
    },
    "ttl": {"search": 24 * 3600},
}

PAGE_SIZE_MAX = 1000  # pageSize honoured ceiling (probed 2026-11-05 recipe; larger asks unverified)

# the 13 mandatory params, upstream names verbatim — every one rides every call ("" when unused)
_QUERY_KEYS = ("queryText", "subjectMatters", "subjectMatterAreas", "publicBodys", "jobTitles",
               "returnDateFrom", "returnDateTo", "period", "dpo", "client", "responsible",
               "lobbyist", "lobbyistId")

# the projected return row: the register's substantive shape (lobbyist / clients / dpos carried
# verbatim — the Cro and CompanyRegistrationNumber keys inside are the join keys)
_ROW_KEYS = ("Id", "Period", "PeriodName", "SubjectMatterText", "SubjectMatterName",
             "PublicPolicyAreaName", "IntendedResultsText", "NilReturn", "IsOnBehalfOfClient",
             "OnBehalfOfClient", "SubmittedDate", "DateCreated", "CeasedLobbying",
             "LobbyingActivity", "LobbyingActivityText", "IsGrassRootsCampaign",
             "GrassRootsDirective", "FriendlyUrlName", "FormattedUrl")


def _ddmmyyyy(val, label):
    """A DD-MM-YYYY date (the upstream's own form shape — ISO answers HTTP 500; wall is local)."""
    s = str(val or "").strip()
    if len(s) != 10 or s[2] != "-" or s[5] != "-" or not s.replace("-", "").isdigit():
        raise SdkError("usage_error", provider="ie_sipo",
                       detail=f"{label} wants DD-MM-YYYY (the register form's own shape; ISO dates are "
                              f"answered HTTP 500 — got \"{val}\")")
    import datetime
    try:
        datetime.datetime.strptime(s, "%d-%m-%Y")
    except ValueError:
        raise SdkError("usage_error", provider="ie_sipo",
                       detail=f"{label} is not a real calendar date (got \"{s}\")")
    return s


def lobbying_raw(query_text=None, client=None, dpo=None, public_bodys=None, period=None,
                 return_date_from=None, return_date_to=None, page=1, limit=20,
                 cache=None, no_cache=False):
    """One /api/Search GET → {total, page, page_size, rows[], params, _meta}.

    Filters: query_text = the free search phrase; client = the lobbied-for side; dpo = the
    designated public official; public_bodys = the office lobbied; period = the return period;
    return_date_from/to = the submission window (DD-MM-YYYY). Rows project the substantive
    return (subject matter, intended results, nil-return flag, dates, friendly URL) plus the
    three verbatim embedded parties Lobbyist / Clients / Dpos."""
    from ..transport import call_provider

    n, p = int(limit), int(page)
    if n < 1 or n > PAGE_SIZE_MAX:
        raise SdkError("usage_error", provider="ie_sipo",
                       detail=f"limit must be 1-{PAGE_SIZE_MAX} (pageSize ceiling, probed), got '{limit}'")
    if p < 1:
        raise SdkError("usage_error", provider="ie_sipo", detail=f"page is 1-based, got '{page}'")
    vals = {"queryText": (str(query_text).strip() if query_text else ""),
            "client": (str(client).strip() if client else ""),
            "dpo": (str(dpo).strip() if dpo else ""),
            "publicBodys": (str(public_bodys).strip() if public_bodys else ""),
            "period": (str(period).strip() if period else ""),
            "returnDateFrom": (_ddmmyyyy(return_date_from, "return_date_from") if return_date_from else ""),
            "returnDateTo": (_ddmmyyyy(return_date_to, "return_date_to") if return_date_to else "")}
    params = {"currentPage": p, "pageSize": n}
    for k in _QUERY_KEYS:                       # all thirteen, every call — the 404 wall
        params[k] = vals.get(k, "")

    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    rows = []
    for it in d.get("Data") or []:
        row = {k: it.get(k) for k in _ROW_KEYS}
        row["Lobbyist"] = it.get("Lobbyist")
        row["Clients"] = it.get("Clients")
        row["Dpos"] = it.get("Dpos")
        rows.append(row)
    return {"total": d.get("Total"), "page": p, "page_size": n, "count": len(rows),
            "rows": rows, "params": {k: params[k] for k in _QUERY_KEYS}, "_meta": r}
