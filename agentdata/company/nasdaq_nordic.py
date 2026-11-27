"""nasdaq_nordic — Nasdaq Nordic exchange-universe family (api.nasdaq.com/api/nordic
keyless REST: the four Nordic venues Copenhagen/Stockholm/Helsinki/Iceland in one
screener; 0.3.77 batch E20).

2026-11-24 probed laws (tmp/probe-e20/; research volume
company/eu-nasdaq-nordic-market-api.md, probe ancestry tmp/probe-audit/r539
+r542/watch1123/nordic/):

  - THE TLS-FINGERPRINT GATE (JA3): api.nasdaq.com sits behind an Akamai bot
    gate that keys on the TLS handshake — python urllib (OpenSSL) answers 403
    "Access Denied" to EVERY header combination (re-certified 2026-11-24:
    urllib 403 411B vs system curl 200 on the same face, probe ctrl.sh), while
    curl passes with nothing but a User-Agent. ALL ops therefore declare
    transport="curl" — the SDK's curl-subprocess channel sends exactly the
    passing stance (agentdata UA + Accept: application/json). This is the
    FIRST batch to pin the curl channel on shipped ops (the channel existed
    since the GUDID lesson; never before load-bearing).
  - THE MANDATORY assetClass LAW: /instruments/{id}/info and /summary answer
    400 10001 "Mandatory field missing" without ?assetClass=SHARES — the
    nordicApiSettings dump's queryParams field carries the required query
    ("assetClass:SHARES"). The star family needs none.
  - THE 400-NOT-FOUND LAW: an unknown orderbookId on the instrument family
    answers 400 code 10003 "Instrument not found" (NOT 404) — ops declare
    notFound=[400] so the SDK raises upstream_not_found and the faces answer
    found=false honestly. Params are enum-validated client-side, so a 400 can
    only mean "no such instrument".
  - THE STAR DRUPAL-SHELL LAW: the /star/{id} family on an unknown id answers
    200 with a Drupal HTML page (BOM + <html>) instead of JSON — same shape as
    the currency-fixing api-path law. The star faces catch that as
    found=false (status 200 + non-JSON body = the miss); a genuine WAF
    challenge (202) still propagates as upstream_unavailable.
  - THE INDEX-CHILDREN WINDOW LAW: /instruments/{id}/index-children returns
    the FIRST 100 members and IGNORES offset/size (re-certified 2026-11-24:
    IX10282 offset=100 and size=200 both return the byte-identical first-100
    window, no pagination block). Members beyond #100 are unreachable through
    this endpoint — a rolling cap, not a coverage claim. OMXS30 (IX447) has
    exactly 30 members;indexes 86 (IX-prefixed orderbookIds).
  - THE DEFAULT-SEGMENT TRAP: screener/shares without segment answers ONLY
    Large Cap (255 rows, not the 702 Main-Market total) — a full census needs
    MAIN_MARKET×{LARGE,MID,SMALL_CAP,SPAC} + FIRST_NORTH. Probe day census:
    255+238+210+0+409 = 1,112 (SPAC honestly empty; Mid gained one listing
    vs the 2026-11-23 probe). FIRST_NORTH takes no segment (the growth board
    has no cap split).
  - THE MARKET PARAM LAW: filter market accepts CPH/STO/HEL/ICE or absent
    (= the merged Nordic book); lowercase country codes answer 400 10002.
  - RED LINE: the quote surfaces (price-history OHLCV bars, trade-history
    ticks, order-depth book, price-info, trades, chart/download,
    market-prices ELECTRICITY, the fixed-income rate tables and the carbon
    family) are MARKET-DATA surfaces — licensed goods, deliberately out of
    this module. The screener rows DO carry quote columns upstream; the faces
    strip them at the identity filter below and serve company-axis identity
    columns only.
  - orderbookId IS THE JOIN KEY: TX-prefixed internal ids (TX2195 = Maersk A),
    not ISIN, not the ticker — the instrument/star faces key on it; ISIN sits
    flat inside every row for the registry join.
"""
import re

from ..errors import SdkError

provider = {
    "id": "nasdaq-nordic",
    "baseUrl": "https://api.nasdaq.com/api/nordic",
    "rate": {"rps": 1.0, "burst": 1},
    "ops": {
        "universe":  {"path": "/screener/shares", "transport": "curl"},
        "indexes":   {"path": "/screener/indexes", "transport": "curl"},
        "halt":      {"path": "/screener/knocked-out", "transport": "curl"},
        "etf":       {"path": "/screener/etp", "transport": "curl"},
        "children":  {"path": "/instruments/{id}/index-children", "transport": "curl",
                      "notFound": [400]},
        "info":      {"path": "/instruments/{id}/info", "transport": "curl",
                      "notFound": [400]},
        "summary":   {"path": "/instruments/{id}/summary", "transport": "curl",
                      "notFound": [400]},
        "key_stats": {"path": "/star/{id}/key-stats", "transport": "curl"},
        "company":   {"path": "/star/{id}/company-details", "transport": "curl"},
        "search":    {"path": "/search", "transport": "curl"},
    },
    "ttl": {"universe": 3600, "indexes": 3600, "halt": 3600, "etf": 3600,
            "children": 86400, "info": 3600, "summary": 3600,
            "key_stats": 86400, "company": 86400, "search": 86400},
}

# screener category values (probe-certified; anything else answers 400 10002)
CATEGORIES = ("MAIN_MARKET", "FIRST_NORTH")
SEGMENTS = ("LARGE_CAP", "MID_CAP", "SMALL_CAP", "SPAC")
MARKETS = ("CPH", "STO", "HEL", "ICE")  # absent = the merged Nordic book

# the quote/volume column family the nordic row schema carries (one 42-key superset
# row shape across all four screeners; the shares rows answer most of these as empty
# strings, ETF/index rows can carry values) — the market-data red line strips them at
# the face layer. The kept identity/instrument columns (19): isin/orderbookId/symbol/
# fullName/issuerFullName/sector/currency/micCode/exchangeSymbol/assetClass/type/
# strikePrice/couponRate/contractSize/expirationDate/totalExpenseRatio/
# greenEquityDesignation/noteCode/noteDescription — instrument terms, not quotes.
_QUOTE_COLUMNS = {
    # prices
    "lastSalePrice", "askPrice", "bidPrice", "high", "low",
    "medianPrice", "netAssetValue", "priceNotation", "settlementPrice",
    "allTradesAvgPrice",
    # change flags
    "netChange", "percentageChange", "deltaIndicator",
    # volume / trades
    "volume", "turnover", "totalVolume", "tradesCount", "reportedVolume",
    "openInterest",
    # quote timestamps
    "lastTraded", "lastTradedDate", "time", "navUpdatedTime",
}

_ID_RE = re.compile(r"^(IX|TX)[A-Z0-9]{2,10}$")


def _call(op, params, cache=None, no_cache=False):
    from ..transport import call_provider
    return call_provider(provider, op, params, cache=cache, no_cache=no_cache)


def _payload(r):
    """the api.nasdaq.com envelope is {data, messages, status} — the payload sits one
    level down; call_provider hands the full parsed body at r["data"]. Every op in this
    provider wraps the same way (probe-e20 n01-n18)."""
    body = r.get("data")
    if isinstance(body, dict):
        return body.get("data")
    return body


def _screener_rows(r):
    """→ (rows, total): the {instrumentListing:{rows},pagination:{total}} payload shape,
    tolerant to rows:null (an honest empty segment — SPAC answers exactly this) and to
    a missing pagination block (index-children carries none)."""
    data = _payload(r) or {}
    listing = data.get("instrumentListing") or {}
    rows = listing.get("rows") or []
    total = ((data.get("pagination") or {}).get("total"))
    out = []
    for row in rows:
        if isinstance(row, dict):
            out.append({k: v for k, v in row.items() if k not in _QUOTE_COLUMNS})
    return out, total


def _rows_result(r, params):
    rows, total = _screener_rows(r)
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    return {"rows": rows, "total": total, "params": params, "_meta": meta}


def universe(*, category="MAIN_MARKET", segment=None, market=None, cache=None, no_cache=False):
    """→ {rows, total, params, _meta}; the Nordic listed-company census, one anchor
    across Copenhagen/Stockholm/Helsinki/Iceland. category MAIN_MARKET takes a
    segment (LARGE_CAP|MID_CAP|SMALL_CAP|SPAC — ABSENT answers only Large Cap, the
    default-segment trap); FIRST_NORTH takes none. market narrows to one venue
    (CPH|STO|HEL|ICE, optional — absent = the merged Nordic book). Rows carry
    ISIN/orderbookId/symbol/sector/green-equity flags; the upstream's quote
    columns are stripped (red line). --segment LARGE_CAP --category MAIN_MARKET."""
    cat = str(category or "").strip().upper()
    if cat not in CATEGORIES:
        raise SdkError("usage_error", provider="nasdaq-nordic",
                       detail=f"category must be one of {CATEGORIES}, got {category!r}")
    seg = str(segment).strip().upper() if segment else None
    mkt = str(market).strip().upper() if market else None
    if seg and seg not in SEGMENTS:
        raise SdkError("usage_error", provider="nasdaq-nordic",
                       detail=f"segment must be one of {SEGMENTS}, got {segment!r}")
    if cat == "FIRST_NORTH" and seg:
        raise SdkError("usage_error", provider="nasdaq-nordic",
                       detail="FIRST_NORTH has no cap segments — drop --segment (the growth board answers as one anchor)")
    if mkt and mkt not in MARKETS:
        raise SdkError("usage_error", provider="nasdaq-nordic",
                       detail=f"market must be one of {MARKETS}, got {market!r}")
    params = {"category": cat, "tableonly": "false", "lang": "en"}
    if seg:
        params["segment"] = seg
    if mkt:
        params["market"] = mkt
    return _rows_result(_call("universe", params, cache=cache, no_cache=no_cache), params)


def indexes(*, cache=None, no_cache=False):
    """→ {rows, total, params, _meta}; the index board — 86 indexes (IX-prefixed
    orderbookIds, OMXS30 = IX447), the enumeration source for index_members."""
    return _rows_result(_call("indexes", {"tableonly": "false", "lang": "en"}, cache=cache, no_cache=no_cache),
                        {"tableonly": "false", "lang": "en"})


def index_members(*, index_id, cache=None, no_cache=False):
    """→ {found, index_id, rows, count, params, _meta}; an index's constituent list
    (OMXS30 IX447 = exactly 30). THE WINDOW LAW: the upstream returns the FIRST 100
    members and ignores offset/size — larger boards (Nordic 120 IX10282) come back
    truncated with no pagination surface; a beyond-100 reach is a documented cap,
    never a coverage claim. --id IX447."""
    ix = str(index_id or "").strip().upper()
    if not _ID_RE.fullmatch(ix) or not ix.startswith("IX"):
        raise SdkError("usage_error", provider="nasdaq-nordic",
                       detail=f"index_id must be an IX-prefixed orderbookId (e.g. IX447), got {index_id!r}")
    try:
        r = _call("children", {"id": ix}, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_not_found":
            return {"found": False, "index_id": ix, "rows": [],
                    "params": {"id": ix}, "_meta": {"from_cache": False, "fetched_at": None,
                                                    "note": "honest miss — no such index orderbookId"}}
        raise
    rows, _ = _screener_rows(r)
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    if len(rows) >= 100:
        meta["window_note"] = ("upstream caps index-children at the first 100 members and "
                               "ignores offset/size — the list may be truncated")
    return {"found": True, "index_id": ix, "rows": rows, "count": len(rows),
            "params": {"id": ix}, "_meta": meta}


def instrument_info(*, instrument_id, cache=None, no_cache=False):
    """→ {found, instrument_id, card, params, _meta}; the instrument master card
    (qdHeader): symbol/companyName/exchange/segment/marketStatus/isin/currency.
    assetClass=SHARES is MANDATORY upstream (400 10001 without it — the face
    always sends it). The embedded quote blocks (primaryData/bid/ask/52-week)
    are market data and are stripped (red line). --id TX2195."""
    ix = _require_tx(instrument_id)
    try:
        r = _call("info", {"id": ix, "assetClass": "SHARES"}, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_not_found":
            return _miss(ix)
        raise
    card_full = ((_payload(r) or {}).get("qdHeader")) or {}
    card = {k: v for k, v in card_full.items()
            if k not in ("primaryData", "keyStats")}
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    return {"found": bool(card), "instrument_id": ix, "card": card,
            "params": {"id": ix, "assetClass": "SHARES"}, "_meta": meta}


def instrument_summary(*, instrument_id, cache=None, no_cache=False):
    """→ {found, instrument_id, summary, params, _meta}; the share-base card:
    shares outstanding + market-cap-of-share-series + ISIN + green-equity flags +
    liquidity flags (Maersk TX2195: 9,586,488 shares, DKK 188.5bn series cap).
    assetClass=SHARES mandatory; the day-range/52-week/volume price blocks and the
    sharePriceChange* return family are market data and are stripped (red line). --id TX2195."""
    ix = _require_tx(instrument_id)
    try:
        r = _call("summary", {"id": ix, "assetClass": "SHARES"}, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_not_found":
            return _miss(ix)
        raise
    full = ((_payload(r) or {}).get("summaryData")) or {}
    # the strip set is the LIVE key census (probe n09b): the six day/52-week/volume
    # blocks PLUS the sharePriceChange{Week,Month,3Month,6Month,Year,YTD} family and
    # priceNotation — every price/return column is market data (red line); the kept
    # keys are share base/identity/market metadata (shares/marketCap/isin/green
    # flags/liquidityProvider/marketName/note/icbCode/sectorName/insSegment/venues)
    summary = {k: v for k, v in full.items()
               if k not in ("todayHighLow", "fiftyTwoWeekHighLow", "yearHighLow",
                            "openingPrice", "volume", "noOfTrades",
                            "sharePriceChangeWeek", "sharePriceChangeMonth",
                            "sharePriceChange3Month", "sharePriceChange6Month",
                            "sharePriceChangeYear", "sharePriceChangeYTD",
                            "priceNotation")}
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    return {"found": bool(summary), "instrument_id": ix, "summary": summary,
            "params": {"id": ix, "assetClass": "SHARES"}, "_meta": meta}


def fundamentals(*, instrument_id, cache=None, no_cache=False):
    """→ {found, instrument_id, metrics, params, _meta}; the Morningstar key-stats
    card (Maersk TX2195: PE 10.59 / PB 0.75 / margins / ROE / Debt-Equity — nine
    ratio metrics verbatim). THE STAR SHELL LAW: an unknown id answers 200 with a
    Drupal HTML page instead of JSON — caught as found=false; a 202 WAF challenge
    still propagates. --id TX2195."""
    ix = _require_tx(instrument_id)
    try:
        r = _call("key_stats", {"id": ix}, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_unavailable" and e.status == 200:
            # 200 + non-JSON = the Drupal HTML shell (the star miss); a WAF
            # challenge answers 202 and is NOT caught here
            return _miss(ix)
        raise
    metrics = _payload(r) or []
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    return {"found": bool(metrics), "instrument_id": ix, "metrics": metrics,
            "params": {"id": ix}, "_meta": meta}


def company_details(*, instrument_id, cache=None, no_cache=False):
    """→ {found, instrument_id, profile, params, _meta}; the Morningstar company
    profile (narrative companyProfile + stockStyle/fiscalYearEnd/employees/
    website). Same star shell law as fundamentals. --id TX2195."""
    ix = _require_tx(instrument_id)
    try:
        r = _call("company", {"id": ix}, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_unavailable" and e.status == 200:
            return _miss(ix)
        raise
    profile = _payload(r) or {}
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    return {"found": bool(profile), "instrument_id": ix, "profile": profile,
            "params": {"id": ix}, "_meta": meta}


def trading_halt(*, cache=None, no_cache=False):
    """→ {rows, total, params, _meta}; the current TRADING_HALT register
    (screener/knocked-out) — the Nordic analogue of TMX suspended/Euronext
    Newsboard: a present-state register, not an event stream (probe day 16 rows;
    the count moves daily). Row quote columns arrive empty from the upstream and
    are stripped regardless (red line)."""
    return _rows_result(_call("halt", {"category": "TRADING_HALT", "tableonly": "false",
                                       "lang": "en"}, cache=cache, no_cache=no_cache),
                        {"category": "TRADING_HALT", "tableonly": "false", "lang": "en"})


def etf(*, cache=None, no_cache=False):
    """→ {rows, total, params, _meta}; the ETP board under its TRUE enumeration —
    the nordicApiSettings default ('ETP') answers 400, the real category value is
    ETF (probe day 32 rows, single page). Same identity-filter/quote-strip as
    universe."""
    return _rows_result(_call("etf", {"category": "ETF", "tableonly": "false",
                                      "lang": "en"}, cache=cache, no_cache=no_cache),
                        {"category": "ETF", "tableonly": "false", "lang": "en"})


def lookup(*, q, cache=None, no_cache=False):
    """→ {found, q, groups, hits, params, _meta}; the search resolver — data is a
    LIST of {group, instruments[{orderbookId,fullName,isin,symbol,assetClass,
    currency}]} groups. One company may list on several venues/currencies (Ericsson
    B: ERIC B/SEK + ERIBR/EUR) — the join key is orderbookId, never the bare name
    or ISIN. An unknown query returns zero groups (found=false, honest). --q Ericsson."""
    query = str(q or "").strip()
    if not query:
        raise SdkError("usage_error", provider="nasdaq-nordic",
                       detail="lookup requires q (a company name or ticker fragment)")
    if len(query) > 80:
        raise SdkError("usage_error", provider="nasdaq-nordic",
                       detail=f"q too long ({len(query)} chars) — pass a company-name fragment")
    r = _call("search", {"searchText": query}, cache=cache, no_cache=no_cache)
    groups = _payload(r) or []
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    hits = sum(len(g.get("instruments") or []) for g in groups if isinstance(g, dict))
    return {"found": hits > 0, "q": query, "groups": groups, "hits": hits,
            "params": {"searchText": query}, "_meta": meta}


def _require_tx(instrument_id):
    ix = str(instrument_id or "").strip().upper()
    if not _ID_RE.fullmatch(ix) or not ix.startswith("TX"):
        raise SdkError("usage_error", provider="nasdaq-nordic",
                       detail=(f"instrument_id must be a TX-prefixed orderbookId "
                               f"(e.g. TX2195 — the join key, never the ISIN/ticker), got {instrument_id!r}"))
    return ix


def _miss(ix):
    return {"found": False, "instrument_id": ix, "card": None, "summary": None,
            "metrics": None, "profile": None,
            "_meta": {"from_cache": False, "fetched_at": None,
                      "note": "honest miss — no such instrument orderbookId"}}
