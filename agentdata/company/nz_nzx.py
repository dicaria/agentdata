"""nz_nzx — NZX (New Zealand's exchange) listed universe + issuer governance
card + announcements stream (www.nzx.com, keyless; 0.3.72 batch E14).

2026-11-19 probed laws (tmp/probe-e14/):
  - THE SITE IS NEXT.JS SSR AND EVERY PAGE CARRIES ITS DATA in the
    __NEXT_DATA__ blob at props.pageProps.dehydratedState.queries (the
    TanStack Query dehydrated state). /markets/NZSX answers ONE 958KB page
    whose q0 ["activeInstruments"] is the WHOLE-EXCHANGE master: 427 rows ×
    16 keys (isin/code/name/securityClass/marketType/tradingBoard/category/
    subCategory/type/sustainabilityCategory/companyId/currencyCode/
    sharesIssued/indexedFraction/firstListedDate/lastListedDate). The NZDX
    page carries the SAME master (identical 427-row set, verified live) plus
    its own 135-row bond quote panel (AIA 4.04% 2031 bonds and kin); the NZSX
    page carries the 178-row equity quote panel. TWO PAGES = THE WHOLE
    EXCHANGE.
  - robots.txt disallows /api/ and /search — the SSR pages ARE the compliant
    surface; this provider never touches the API routes.
  - COMPANY PAGE (/companies/{code}) carries FOUR queries: company/contact
    (address/country/website/secretary), company/summary (financialYearEnd
    {month,day} + auditor + solicitor + primaryRegistry + primaryListingVenue
    — the four governance registers), company/directors (personId/role/type
    I|N/isCurrent/startDate/endDate + names — the official registry, carried
    verbatim), instruments/company (the live quote rows for the issuer).
    Directors are public statutory register data (the Companies-Office
    officers precedent) — verbatim, never trimmed.
  - ANNOUNCEMENTS PAGE q0 ["announcements","recent",<board>]: 200 rows
    id-desc (max 484034 probe day; the id is the sequential anchor for
    incremental pulls), each {id, summary{id,publicationDate,title,type,
    companyCode,securityCode}, details{id,releaseDate,isPriceSensitive,
    isThirdParty,body}, attachments[]}. THE ?page= QUERY PARAM IS IGNORED
    SERVER-SIDE (page=2 dehydrates the same page-1 state) — the face is the
    newest-200 snapshot per board; deeper paging lives only in the
    robots-blocked API. That boundary is final, documented, not worked around.
  - BAD COMPANY CODE = an honest 404 whose dehydratedState.queries is an
    EMPTY list → found=false, never fabricated (NZX answers a real 404 —
    unlike the CSE zero-byte silent-empty shape).
  - 3000-01-01 SENTINEL: lastListedDate "3000-01-01…" means currently listed;
    the master is the ACTIVE set — delisted instruments simply drop out of
    activeInstruments (NZX exposes no delisted archive; snapshot diffs are
    the delisting ledger, a harvest-side concern).
  - NZSX/NZDX quote rows differ in kind: equities carry priceAmount/
    priceChange*/marketValue; bond rows add nothing exotic but ride type "F"
    securityClass "W" — all verbatim.

Politeness 1 rps (each page is a ~1MB SSR document). TTLs: market 15min (the
quote panel rides the page), company 15min (live quote rows), announcements
30min (the stream grows intraday — pull by id anchor).
"""
import json
import re

from ..errors import SdkError

provider = {
    "id": "nz_nzx",
    "baseUrl": "https://www.nzx.com",
    "rate": {"rps": 1.0, "burst": 1},
    "ops": {
        "market": {"path": "/markets/{board}", "idempotent": True,
                   "accept": "text", "timeout": 90.0},
        "company": {"path": "/companies/{code}", "idempotent": True,
                    "accept": "text", "timeout": 90.0, "notFound": [404]},
        "announcements": {"path": "/markets/{board}/announcements",
                          "idempotent": True, "accept": "text", "timeout": 90.0},
    },
    "ttl": {"market": 900, "company": 900, "announcements": 1800},
}

BOARDS = ("NZSX", "NZDX")
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                        re.S)


def _dehydrated(text, what):
    m = _NEXT_DATA.search(text or "")
    if not m:
        raise SdkError("upstream_unavailable", provider="nz_nzx",
                       detail=f"the {what} page carries no __NEXT_DATA__ blob — the SSR shape may have moved; re-probe")
    try:
        data = json.loads(m.group(1))
    except ValueError:
        raise SdkError("upstream_unavailable", provider="nz_nzx",
                       detail=f"the {what} page __NEXT_DATA__ blob is not valid JSON — re-probe")
    queries = (((data.get("props") or {}).get("pageProps") or {})
               .get("dehydratedState") or {}).get("queries") or []
    return queries


def _by_key(queries, key_head):
    """first query whose queryKey starts with key_head → its state.data (or None)."""
    for q in queries:
        k = q.get("queryKey")
        if isinstance(k, list) and k and k[0] == key_head:
            return (q.get("state") or {}).get("data")
    return None


def _board_arg(board):
    b = str(board or "NZSX").strip().upper()
    if b not in BOARDS:
        raise SdkError("usage_error", provider="nz_nzx",
                       detail=f"board must be one of {'/'.join(BOARDS)}, got \"{board}\"")
    return b


def listed(*, board="NZSX", code=None, name=None, security_class=None,
           category=None, quotes=False, limit=None, cache=None, no_cache=False):
    """→ {board, total, rows[], quote_rows, market_info, params, _meta}; the NZX
    whole-exchange master (427 rows probe day — activeInstruments, the ACTIVE
    set; delisted instruments drop out, lastListedDate 3000-01-01 is the
    listed sentinel) plus the board's own quote panel count. --quotes merges
    the panel's live quote onto each matching row as `quote`. Client-side
    selectors: --code exact, --name substring, --security-class exact
    (E equities on NZSX / F bonds on NZDX), --category exact (SHRS/…),
    --limit slices the display."""
    from ..transport import call_provider

    b = _board_arg(board)
    r = call_provider(provider, "market", {"board": b}, cache=cache, no_cache=no_cache)
    queries = _dehydrated(r["data"], f"/markets/{b}")
    master = _by_key(queries, "activeInstruments")
    if not isinstance(master, list):
        raise SdkError("upstream_unavailable", provider="nz_nzx",
                       detail=f"/markets/{b} dehydrated no activeInstruments master — the SSR shape may have moved; re-probe")
    panel = _by_key(queries, "marketInstruments")
    panel = panel if isinstance(panel, list) else []
    info = _by_key(queries, "marketInfo")

    q_code = str(code).strip().upper() if code else None
    q_name = str(name).strip().lower() if name else None
    q_class = str(security_class).strip().upper() if security_class else None
    q_cat = str(category).strip().upper() if category else None
    quote_by_code = {}
    if quotes:
        for qrow in panel:
            qc = str(qrow.get("code") or "").upper()
            if qc:
                quote_by_code[qc] = qrow
    rows = []
    for row in master:
        if q_code and str(row.get("code") or "").upper() != q_code:
            continue
        if q_name and q_name not in str(row.get("name") or "").lower():
            continue
        if q_class and str(row.get("securityClass") or "").upper() != q_class:
            continue
        if q_cat and str(row.get("category") or "").upper() != q_cat:
            continue
        out = dict(row)
        if quotes:
            out["quote"] = quote_by_code.get(str(row.get("code") or "").upper())
        rows.append(out)
    total = len(rows)
    if limit is not None and int(limit) >= 0:
        rows = rows[: int(limit)]
    return {"board": b, "total": total, "rows": rows,
            "quote_rows": len(panel), "market_info": info if isinstance(info, dict) else None,
            "params": {"board": b, "code": code, "name": name,
                       "security_class": security_class, "category": category,
                       "quotes": bool(quotes), "limit": limit},
            "_meta": r}


def company(*, code, cache=None, no_cache=False):
    """→ {found, code, card|None, params, _meta}; the issuer governance card:
    summary (financialYearEnd + auditor + solicitor + primaryRegistry +
    primaryListingVenue — the four registers), contact (address/website/
    secretary), directors (the official register — role/type/isCurrent/
    start/end + names, verbatim) and instruments (the live quote rows).
    Bad code = honest 404 with EMPTY queries → found=false, never fabricated."""
    from ..transport import call_provider

    c = str(code or "").strip().upper()
    if not c:
        raise SdkError("usage_error", provider="nz_nzx",
                       detail="--code is required (an NZX issuer code, e.g. TRA)")
    try:
        r = call_provider(provider, "company", {"code": c}, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_not_found":
            # honest 404: no response body, so the meta is the observation itself
            # (observed_at = the moment the 404 was seen — never fabricated data)
            from datetime import datetime, timezone
            return {"found": False, "code": c, "card": None,
                    "params": {"code": c},
                    "_meta": {"from_cache": False,
                              "fetched_at": datetime.now(timezone.utc).isoformat(),
                              "note": "honest 404 — meta is the observation, not a body"}}
        raise
    queries = _dehydrated(r["data"], f"/companies/{c}")
    if not queries:
        return {"found": False, "code": c, "card": None,
                "params": {"code": c}, "_meta": r}
    card = {}
    for q in queries:
        k = q.get("queryKey")
        data = (q.get("state") or {}).get("data")
        if not isinstance(k, list) or not k:
            continue
        if k[0] == "company" and len(k) >= 2:
            card[str(k[1])] = data  # contact / summary / directors
        elif k[0] == "instruments":
            card["instruments"] = data  # the issuer's live quote rows
    found = bool(card.get("summary") or card.get("contact") or card.get("directors"))
    return {"found": found, "code": c, "card": card if found else None,
            "params": {"code": c}, "_meta": r}


def announcements(*, board="NZSX", code=None, type=None, price_sensitive=None,
                  limit=None, cache=None, no_cache=False):
    """→ {board, total, rows[], params, _meta}; the newest-200 announcements
    snapshot for the board (id-desc; the id is the sequential anchor — max
    484034 probe day). THE ?page PARAM IS IGNORED UPSTREAM (page 2 dehydrates
    page 1) — 200 rows is the whole SSR surface, the deeper API is
    robots-blocked. Rows carry summary/details/attachments verbatim.
    Client-side selectors: --code exact on companyCode, --type exact (SHINTR
    substantial-holder family and kin), --price-sensitive bool, --limit slices."""
    from ..transport import call_provider

    b = _board_arg(board)
    r = call_provider(provider, "announcements", {"board": b}, cache=cache, no_cache=no_cache)
    queries = _dehydrated(r["data"], f"/markets/{b}/announcements")
    data = _by_key(queries, "announcements")
    rows_all = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows_all, list):
        raise SdkError("upstream_unavailable", provider="nz_nzx",
                       detail=f"/markets/{b}/announcements dehydrated no announcements panel — the SSR shape may have moved; re-probe")
    q_code = str(code).strip().upper() if code else None
    q_type = str(type).strip().upper() if type else None
    ps = None if price_sensitive is None else bool(price_sensitive)
    rows = []
    for row in rows_all:
        s = row.get("summary") or {}
        d = row.get("details") or {}
        if q_code and str(s.get("companyCode") or "").upper() != q_code:
            continue
        if q_type and str(s.get("type") or "").upper() != q_type:
            continue
        if ps is not None and bool(d.get("isPriceSensitive")) != ps:
            continue
        rows.append(row)
    total = len(rows)
    if limit is not None and int(limit) >= 0:
        rows = rows[: int(limit)]
    return {"board": b, "total": total, "rows": rows,
            "params": {"board": b, "code": code, "type": type,
                       "price_sensitive": ps, "limit": limit},
            "_meta": r}
