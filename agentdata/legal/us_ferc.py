"""us_ferc — FERC eLibrary document search (elibrary.ferc.gov/eLibraryWebAPI; keyless).

legal energy-regulatory document face (0.3.50; admitted 2026-11-09, probed tmp/probe-sdk0350/).
The eLibrary corpus is 4.7M documents 1980→today (totalHits echo 4,722,924 live 2026-11-09) —
dockets, orders, comments, transmittals over the whole FERC-regulated energy infrastructure
lifecycle (pipeline certificates CP-*, hydro licenses P-*, tariffs, rate cases).

**Cloudflare UA-fingerprint gate (the afdb ext-8 family's fifth pinned member)**: the transport's
polite UA → HTTP 403; the full browser suite (Chrome UA + Accept + Origin + Referer) passes —
verified live 2026-11-09 on both the wildcard and the filtered shapes.

Contract (POST /Search/AdvancedSearch, JSON): searchText empty intent = the literal "*" (the
upstream's own wildcard form — sent verbatim, not omitted); docketSearches = [{docketNumber,
subDocketNumbers: []}]; dateSearches = [{dateType: filed_date|issued_date|posted_date|created_date,
startDate, endDate}] with yyyy-MM-dd dates; resultsPerPage honoured to 1000 (probed) + curPage
1-based. Answer: {totalHits, numHits, searchHits[]} — hits carry the docketNumbers list, the three
date faces (MM/dd/yyyy verbatim), and **acesssionNumber with the upstream's own triple-s** (the
official key; the PDF rides /File/DownloadPDF?accesssionNumber=… out of SDK scope). Response rows
pass through verbatim minus the internal 'reference' pair-key; 'score' is kept (it is the
relevance rank the upstream computed).
"""
from ..errors import SdkError

provider = {
    "id": "us_ferc",
    "baseUrl": "https://elibrary.ferc.gov",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/eLibraryWebAPI/api/Search/AdvancedSearch",
                   "method": "POST", "idempotent": True, "timeout": 60.0},
    },
    "ttl": {"search": 12 * 3600},
}

# Cloudflare UA-fingerprint gate (ext-8): polite UA → 403; browser suite passes (pinned live 2026-11-09).
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://elibrary.ferc.gov",
    "Referer": "https://elibrary.ferc.gov/eLibraryWebAPI/",
}

DATE_TYPES = ("filed_date", "issued_date", "posted_date", "created_date")
PER_PAGE_MAX = 1000  # resultsPerPage honoured ceiling (probed; larger asks unverified — clamped locally)


def _ymd(val, label):
    """A yyyy-MM-dd dateSearches field: shape + calendar check (the upstream silently answers the
    wildcard for malformed dates — the wall is local, mirroring the at_ris date posture)."""
    s = str(val or "").strip()
    if len(s) != 10 or s[4] != "-" or s[7] != "-" or not s.replace("-", "").isdigit():
        raise SdkError("usage_error", provider="us_ferc",
                       detail=f"{label} wants YYYY-MM-DD (got \"{val}\")")
    import datetime
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        raise SdkError("usage_error", provider="us_ferc",
                       detail=f"{label} is not a real calendar date (got \"{s}\")")
    return s


def elibrary_raw(text=None, docket=None, *, date_type=None, date_from=None, date_to=None,
                 page=1, limit=20, cache=None, no_cache=False):
    """One AdvancedSearch POST → {total, page, page_size, rows[], params, _meta}.

    All filters optional and combinable (probed combined: docket CP17-101 + "gas pipeline" +
    filed_date 2026 window → 37 hits): text = full-text phrase; docket = one docket number with
    sub-docket suffixes ("CP17-101" or "CP17-101-007" — the suffix rides docketNumber verbatim);
    date_type + date_from + date_to = one date facet (both bounds together). No filter = the
    wildcard "*", the newest documents corpus-wide."""
    from ..transport import call_provider

    payload = {"searchText": str(text).strip() if text and str(text).strip() else "*",
               "docketSearches": [], "dateSearches": []}
    if docket:
        payload["docketSearches"] = [{"docketNumber": str(docket).strip(), "subDocketNumbers": []}]
    if date_type is not None or date_from is not None or date_to is not None:
        if date_type not in DATE_TYPES:
            raise SdkError("usage_error", provider="us_ferc",
                           detail=f"date_type must be one of {', '.join(DATE_TYPES)}, got '{date_type}'")
        if date_from is None or date_to is None:
            raise SdkError("usage_error", provider="us_ferc",
                           detail="date_from and date_to come together (one date facet, both bounds)")
        f, t = _ymd(date_from, "date_from"), _ymd(date_to, "date_to")
        if f > t:
            raise SdkError("usage_error", provider="us_ferc",
                           detail=f"date_from ({f}) is after date_to ({t})")
        payload["dateSearches"] = [{"dateType": date_type, "startDate": f, "endDate": t}]
    n, p = int(limit), int(page)
    if n < 1 or n > PER_PAGE_MAX:
        raise SdkError("usage_error", provider="us_ferc",
                       detail=f"limit must be 1-{PER_PAGE_MAX} (resultsPerPage ceiling, probed), got '{limit}'")
    if p < 1:
        raise SdkError("usage_error", provider="us_ferc", detail=f"page is 1-based, got '{page}'")
    payload.update({"resultsPerPage": n, "curPage": p})

    r = call_provider(provider, "search", payload, cache=cache, no_cache=no_cache,
                      extra_headers=_BROWSER_HEADERS)
    d = r["data"] or {}
    if d.get("success") is False:
        raise SdkError("upstream_unavailable", provider="us_ferc",
                       detail=f"AdvancedSearch answered success=false: {str(d.get('errorMessage'))[:200]}")
    hits = d.get("searchHits") or []
    rows = [{k: v for k, v in h.items() if k != "reference"} for h in hits]
    return {"total": d.get("totalHits"), "page": p, "page_size": n, "count": len(rows),
            "rows": rows, "params": payload, "_meta": r}
