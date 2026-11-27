"""ca_tmx — TMX Toronto Stock Exchange listed-company directory + GraphQL
data-gateway family (www.tsx.com keyless directory JSON + app-money.tmx.com
Apollo GraphQL gateway; 0.3.78 batch E21).

2026-11-27 probed laws (tmp/probe-e21/; research volume
company/ca-tmx-listed-company-directory.md, probe ancestry tmp/probe-audit/r534
+r542/watch1123/ca/):

  - ONE PROVIDER OVER TWO HOSTS (the hk_hkex/edgar_xbrl/gb_lse absolute-path
    precedent): the four directory faces ride www.tsx.com
    /json/company-directory/* (plain keyless JSON), the nine gateway faces POST
    https://app-money.tmx.com/graphql (Apollo Server, keyless). Each host keeps
    its own polite bucket. BOTH stacks pass — urllib with the bare SDK UA
    answers 200 on both hosts (probe-e21 dualstack.py, same-day curl
   对照 14/14 200), so NO transport='curl' pin (the nasdaq-nordic contrast).
  - THE WAF WINDOW LAW: tsx.com flipped to an AWS WAF JS challenge on
    2026-11-18 pm (E10 probe-e10 p2c-p2e, every-UA matrix challenged) and
    flipped back by 2026-11-23 (r542 watch1123 — bare UA and full browser
    headers both 200, the same exit): the gate keys on EXIT-IP REPUTATION
    WINDOWS, not headers or stacks. Both 2026-11-27 probes answered clean
    14/14. A renewed 202 challenge propagates as upstream_unavailable (the
    transport's 2xx-non-JSON normalization) — re-probe from another egress,
    never force.
  - THE CRAWL-DELAY LAW: www.tsx.com robots declares Crawl-delay: 15 — the
    directory host is harvested at ≥15s cadence (the SDK token bucket 1 rps
    is the floor, not the ceiling; bulk letter-scans are a HARVEST-side job,
    the SDK face is a point-lookup surface).
  - THE DIRECTORY ENVELOPE LAW: {last_updated, length, results, isHttpError}
    — length is the authoritative count, last_updated the epoch snapshot
    instant (identical across all four actions on probe day = one census).
  - THE SEARCH PREFIX LAW: search/{exchange}/{q} matches NAME OR SYMBOL
    prefix — a single-letter scan carries ~10% non-matching-symbol rows (HDGE
    enters via the name "Accelerate…"); the universe census dedups on symbol.
    Rows are company-level {symbol, name, instruments:[…]} — one parent may
    carry several instrument children (.U USD variants, AB share classes);
    17 of 140 TSX "a" rows on probe day were multi-instrument.
  - THE EVENT-WINDOW LAW: recent (new listings) and delisted are ROLLING
    WINDOWS (~12 weeks probe-certified: TSX 13 rows spanning 2026-09-02→11-19
    on 2026-11-23; 18 rows on 2026-11-27) with NO pagination (?page=2 answers
    byte-identical rows) — a monthly sweep is the archival duty; there is no
    deep backfill through this door. suspended is a PRESENT-STATE register
    (name/symbol only, no dates) — the TMX analogue of nasdaq_nordic
    trading_halt: a snapshot, not an event stream.
  - THE GRAPHQL ENVELOPE LAW: {"data": {…}} on success, {"errors": […]} on
    failure — introspection is disabled in production (400 explicitly names
    it); every gateway contract in this module was excavated from the site's
    webpack chunks (app bundle + shared chunks carry the full operation
    texts) and re-verified live 2026-11-27 (probe-e21 probe1.py 14/14 200).
  - THE PROFILE RED-LINE STRIP (query-level): the gateway's getQuoteBySymbol
    answers a 48-field card that is half quote block (price/priceChange/
    percentChange/volume/openPrice/dayHigh/dayLow/prevClose/close/vwap/
    weeks52high-low/alpha/averageVolume10D-50D/day21|50|200MovingAvg) —
    market data, deliberately NEVER ASKED. The face pins a 41-field selection
    of identity + fundamentals + corporate-action + contact fields; the
    upstream returns exactly the asked set (39 live / 2 nullable for RY:
    marketPlace, sharesESCROW).
  - THE WSH SHAPE LAW: getWSHEventData rides an aliased two-level shape —
    data.quote.data is a LIST of event dicts (event_id/company_id/ISIN/
    event_type/event_date/event_status/event_url/event_name/qmSymbol).
    event_date is MM/DD/YYYY (US order, verbatim — never reformatted).
    Wall Street Horizon is the upstream source; the earnings-calendar dates
    are fact-like schedule data, not quotes.
  - THE FILINGS METADATA-ONLY LAW: getCompanyFilings returns
    filingDate/description/name/size/urlToPdf — the urlToPdf pointer lands on
    app.quotemedia.com, whose robots (302 → static.quotemedia.com
    site-settings) declares `Disallow: /` with an Allow whitelist NOT
    covering /data/ — the PDF content is a BANNED FACE (harvest-side
    probe-e21-prior: 200 real PDF, not saved, per the ban discipline). The
    SDK serves the metadata row and keeps urlToPdf as a pointer value; it
    never fetches it.
  - THE INSIDER DEPTH LAW: getInsiderTransactions(monthDuration) controls
    history depth — 12 ≈ 477-496 rows, 120 = 4,177 rows ≈ ten years (the SEDI
    ceiling); the face clamps 1..120. The aggregated view
    (getCompanyInsidersActivities) answers three period windows
    (threeMonths/sixMonths/twelveMonths) with per-insider buy/sell aggregates
    + an activitySummary net per period.
  - SYMBOL/INDEX FORMS: gateway symbols are TMX ticker forms (RY, BIP.UN
    style, uppercased; the gateway answers RY:CA qmSymbols); index symbols
    carry the caret (^TSX, 215 constituents + keyData weights).
  - RED LINE (face selection): the market-data surfaces stay out — delayed
    quotes/order book, price history OHLCV (1997-01 floor, ~25-row pages),
    index price history, most-recent trades with broker names, market movers,
    trending, news (a QuoteMedia/SeekingAlpha aggregator — third-party
    content), analyst consensus (a premium estimates product), cannabis
    tickers and the watchlist/alerts login family.

Politeness 1 rps (Crawl-delay 15 makes bulk sweeps harvest-side work).
TTLs: directory search 1d, recent/delisted/suspended 1h (event windows),
profile 1d, short interest 1h, insider transactions/activities 1d,
constituents 1d, WSH calendar 1h, filings 1h, dividends 1d, instrument
search 1d.
"""
import re

from ..errors import SdkError

provider = {
    "id": "ca-tmx",
    "baseUrl": "https://www.tsx.com",
    "rate": {"rps": 1.0, "burst": 1},
    "ops": {
        "dir_search":   {"path": "/json/company-directory/search/{exchange}/{q}",
                         "idempotent": True, "timeout": 60.0},
        "dir_recent":   {"path": "/json/company-directory/recent/{exchange}",
                         "idempotent": True, "timeout": 60.0},
        "dir_delisted": {"path": "/json/company-directory/delisted/{exchange}",
                         "idempotent": True, "timeout": 60.0},
        "dir_suspended": {"path": "/json/company-directory/suspended/{exchange}",
                          "idempotent": True, "timeout": 60.0},
        # the nine gateway ops share ONE Apollo endpoint — absolute path on the
        # app-money host (the hk_hkex/edgar_xbrl/gb_lse absolute-path precedent);
        # each op name keeps its own cache slot
        "profile":           {"path": "https://app-money.tmx.com/graphql",
                              "method": "POST", "idempotent": True, "timeout": 60.0},
        "short_interest":    {"path": "https://app-money.tmx.com/graphql",
                              "method": "POST", "idempotent": True, "timeout": 60.0},
        "insider":           {"path": "https://app-money.tmx.com/graphql",
                              "method": "POST", "idempotent": True, "timeout": 120.0},
        "insider_activities": {"path": "https://app-money.tmx.com/graphql",
                               "method": "POST", "idempotent": True, "timeout": 60.0},
        "constituents":      {"path": "https://app-money.tmx.com/graphql",
                              "method": "POST", "idempotent": True, "timeout": 60.0},
        "wsh":               {"path": "https://app-money.tmx.com/graphql",
                              "method": "POST", "idempotent": True, "timeout": 60.0},
        "filings":           {"path": "https://app-money.tmx.com/graphql",
                              "method": "POST", "idempotent": True, "timeout": 60.0},
        "dividends":         {"path": "https://app-money.tmx.com/graphql",
                              "method": "POST", "idempotent": True, "timeout": 60.0},
        "instr_search":      {"path": "https://app-money.tmx.com/graphql",
                              "method": "POST", "idempotent": True, "timeout": 60.0},
    },
    "ttl": {"dir_search": 86400, "dir_recent": 3600, "dir_delisted": 3600,
            "dir_suspended": 3600, "profile": 86400, "short_interest": 3600,
            "insider": 86400, "insider_activities": 86400, "constituents": 86400,
            "wsh": 3600, "filings": 3600, "dividends": 86400, "instr_search": 86400},
}

EXCHANGES = ("tsx", "tsxv")

_GQL_HEADERS = {"Origin": "https://money.tmx.com", "Referer": "https://money.tmx.com/"}

_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,11}$")
_INDEX_RE = re.compile(r"^\^[A-Za-z0-9.\-]{1,15}$")

# the 41-field profile selection — identity + fundamentals + corporate-action +
# contact; the upstream's quote block (prices/volumes/ranges/moving averages/
# 52-week/alpha/vwap) is NEVER ASKED (red line at the query level, not a strip
# after the fact)
_PROFILE_FIELDS = (
    "symbol name exchangeName exShortName exchangeCode marketPlace "
    "sector industry MarketCap MarketCapAllClasses peRatio "
    "dividendFrequency dividendYield dividendAmount dividendCurrency beta eps "
    "exDividendDate dividendPayDate dividend3Years dividend5Years "
    "longDescription fulldescription website email phoneNumber fullAddress "
    "employees shareOutStanding totalSharesOutStanding totalDebtToEquity "
    "sharesESCROW priceToBook priceToCashFlow returnOnEquity returnOnAssets "
    "currency datatype issueType secType qmdescription"
)

_Q_PROFILE = ("query getQuoteBySymbol($symbol: String, $locale: String) { "
              "getQuoteBySymbol(symbol: $symbol, locale: $locale) { "
              + _PROFILE_FIELDS + " } }")
_Q_SHORT = ("query GetCompanyShortInterest($symbol: String!) { "
            "getCompanyShortInterest(symbol: $symbol) { QM_TICKER BUSINESS_DATE "
            "TICKER SHORT_INTEREST SHORTINTERESTPCT DAYSTOCOVER10DAY "
            "DAYSTOCOVER30DAY DAYSTOCOVER90DAY } }")
_Q_INSIDER = ("query getInsiderTransactions($symbol: String!, $monthDuration: Int) "
              "{ getInsiderTransactions(symbol: $symbol, monthDuration: $monthDuration) }")
_Q_INSIDER_ACT = ("query getCompanyInsidersActivities($symbol: String) { "
                  "getCompanyInsidersActivities(symbol: $symbol) { insiderActivities "
                  "{ periodkey buy { name trades shares sharesHeld tradeValue } "
                  "sell { name trades shares sharesHeld tradeValue } } "
                  "activitySummary { periodkey buyShares soldShares netActivity "
                  "totalShares buyTrades sellTrades totalTrades } } }")
_Q_CONSTITUENTS = ("query getIndexConstituents($symbol: String!) { "
                   "constituents: getIndexConstituents(symbol: $symbol) { symbol "
                   "quotedMarketValue longName shortName weight exShortName "
                   "exchange exLongName } keyData: getIndexKeyData(symbol: $symbol) "
                   "{ adjMarketCap avgConstituentMarketCap numConstituents "
                   "top10HoldingsAdjMarketCap ytdPriceReturn prevDayPriceReturn "
                   "prevMonthPriceReturn prevQuarterPriceReturn "
                   "percentWeightLargestConstituent peRatio pbRatio priceToSales "
                   "divYield pcfRatio } }")
_Q_WSH = ("query WSH($symbols: [String]) { quote: getWSHEventData(symbols: $symbols) "
          "{ data } }")
_Q_FILINGS = ("query getCompanyFilings($symbol: String!, $fromDate: String, "
              "$toDate: String, $limit: Int) { filings: getCompanyFilings(symbol: "
              "$symbol, fromDate: $fromDate, toDate: $toDate, limit: $limit) { size "
              "filingDate description name urlToPdf } }")
_Q_DIVIDENDS = ("query getDividendsForSymbol($symbol: String!, $page: Int, "
                "$batch: Int) { dividendHistory: getDividendsForSymbol(symbol: "
                "$symbol, page: $page, batch: $batch) { pageNumber hasNextPage "
                "dividends { exDate amount currency payableDate declarationDate "
                "recordDate } } }")
_Q_INSTR_SEARCH = ("query searchInstruments($keywords: String) { "
                   "searchInstruments(keywords: $keywords) { symbol name exchange "
                   "instrumentType } }")


def _call(op, params, cache=None, no_cache=False):
    from ..transport import call_provider
    return call_provider(provider, op, params, cache=cache, no_cache=no_cache)


def _gql(op, query, variables, *, cache, no_cache):
    """GraphQL round trip: params = {query, variables} → the transport's JSON
    body (method=POST law); the Apollo envelope {data}/{errors} is unwrapped
    here. Returns (data-root-dict, meta)."""
    from ..transport import call_provider

    def ask(**kw):
        nc = kw.pop("no_cache", no_cache)  # the retry passes no_cache=True — pop, never double-bind
        return call_provider(provider, op, {"query": query, "variables": variables},
                             cache=cache, no_cache=nc, **kw)

    r = ask(extra_headers=_GQL_HEADERS)
    body = r.get("data")
    if isinstance(body, dict) and body.get("errors"):
        msg = body["errors"][0].get("message", "—") if isinstance(body["errors"], list) and body["errors"] else "—"
        raise SdkError("upstream_unavailable", provider="ca-tmx",
                       detail=f"the {op} gateway answered GraphQL errors: {str(msg)[:220]}")
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise SdkError("upstream_unavailable", provider="ca-tmx",
                       detail=(f"the {op} gateway answer carries no data root — the Apollo "
                               f"envelope shape may have moved; re-probe (tmp/probe-e21/)"))
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    return data, meta


def _meta(r):
    return {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}


def _directory(op, params, cache=None, no_cache=False):
    r = _call(op, params, cache=cache, no_cache=no_cache)
    env = r.get("data")
    if not isinstance(env, dict) or "results" not in env:
        raise SdkError("upstream_unavailable", provider="ca-tmx",
                       detail=(f"the {op} answer carries no results envelope — the directory "
                               f"shape may have moved; re-probe (tmp/probe-e21/)"))
    rows = [x for x in (env.get("results") or []) if isinstance(x, dict)]
    out = {"rows": rows, "total": env.get("length", len(rows)),
           "last_updated": env.get("last_updated"), "params": params, "_meta": _meta(r)}
    return out


def _exchange_arg(exchange):
    ex = str(exchange or "").strip().lower()
    if ex not in EXCHANGES:
        raise SdkError("usage_error", provider="ca-tmx",
                       detail=f"exchange must be one of {EXCHANGES}, got {exchange!r}")
    return ex


def _symbol_arg(symbol):
    s = str(symbol or "").strip().upper()
    if not _SYMBOL_RE.fullmatch(s):
        raise SdkError("usage_error", provider="ca-tmx",
                       detail=(f"symbol must be a TMX ticker form (RY, BIP.UN style, uppercased), "
                               f"got {symbol!r}"))
    return s


def directory_search(*, exchange, q, cache=None, no_cache=False):
    """→ {rows, total, last_updated, params, _meta}; the letter/word-prefix search
    over one board's listed-company directory. THE PREFIX LAW: the match is NAME
    OR SYMBOL — a single-letter scan carries ~10% name-only rows (dedup on symbol
    for a census); each row is company-level {symbol, name, instruments:[…]} with
    one child per instrument (.U variants, AB classes). --exchange tsx --q bank."""
    ex = _exchange_arg(exchange)
    query = str(q or "").strip()
    if not query or len(query) > 40 or "/" in query:
        raise SdkError("usage_error", provider="ca-tmx",
                       detail=(f"q must be a name/symbol prefix of 1..40 chars with no path "
                               f"separator, got {q!r}"))
    return _directory("dir_search", {"exchange": ex, "q": query}, cache=cache, no_cache=no_cache)


def recent_listings(*, exchange, cache=None, no_cache=False):
    """→ {rows, total, last_updated, params, _meta}; the new-listing event window
    (rows carry name/symbol/epoch date). THE EVENT-WINDOW LAW: a rolling window,
    no pagination — sweep monthly; there is no deep backfill. --exchange tsx."""
    ex = _exchange_arg(exchange)
    return _directory("dir_recent", {"exchange": ex}, cache=cache, no_cache=no_cache)


def delisted(*, exchange, cache=None, no_cache=False):
    """→ {rows, total, last_updated, params, _meta}; the delisting event window
    (~12 weeks rolling, probe-certified; ?page is ignored upstream — the window
    is the whole surface). Monthly sweep is the archival duty. --exchange tsx."""
    ex = _exchange_arg(exchange)
    out = _directory("dir_delisted", {"exchange": ex}, cache=cache, no_cache=no_cache)
    out["_meta"]["window_note"] = ("rolling ~12-week delisting window, no pagination — "
                                   "sweep monthly, no deep backfill through this door")
    return out


def suspended(*, exchange, cache=None, no_cache=False):
    """→ {rows, total, last_updated, params, _meta}; the suspension PRESENT-STATE
    register (name/symbol only, no dates — a snapshot, not an event stream; the
    TMX analogue of nasdaq_nordic_trading_halt). --exchange tsxv."""
    ex = _exchange_arg(exchange)
    return _directory("dir_suspended", {"exchange": ex}, cache=cache, no_cache=no_cache)


def company_profile(*, symbol, cache=None, no_cache=False):
    """→ {found, symbol, card, params, _meta}; the company master card — identity
    (name/exchange), sector/industry, market cap, PE/PB/PS-adjacent ratios,
    dividend family, beta/eps/ROE/ROA/debt-equity, share base, description,
    contacts, employees. THE RED-LINE STRIP IS QUERY-LEVEL: the 48-field upstream
    card is asked down to 41 fields with every price/volume/range/moving-average
    key excluded — the quote block never enters the request, let alone the
    response. --symbol RY."""
    s = _symbol_arg(symbol)
    data, meta = _gql("profile", _Q_PROFILE, {"symbol": s, "locale": "en"},
                      cache=cache, no_cache=no_cache)
    card = data.get("getQuoteBySymbol") or {}
    return {"found": bool(card), "symbol": s, "card": card,
            "params": {"symbol": s, "locale": "en"}, "_meta": meta}


def short_interest(*, symbol, cache=None, no_cache=False):
    """→ {found, symbol, record, params, _meta}; the short-interest record
    (biweekly: SHORT_INTEREST shares / SHORTINTERESTPCT / days-to-cover 10|30|90 /
    BUSINESS_DATE settlement instant). --symbol RY."""
    s = _symbol_arg(symbol)
    data, meta = _gql("short_interest", _Q_SHORT, {"symbol": s},
                      cache=cache, no_cache=no_cache)
    record = data.get("getCompanyShortInterest") or {}
    return {"found": bool(record), "symbol": s, "record": record,
            "params": {"symbol": s}, "_meta": meta}


def insider_transactions(*, symbol, month_duration=12, cache=None, no_cache=False):
    """→ {symbol, month_duration, rows, count, params, _meta}; the SEDI insider
    transaction ledger — raw one-row-per-transaction (filer/relationship/
    securitydesignation/transactionTypeCode/amount/marketvalue/filingdate…).
    THE DEPTH LAW: month_duration controls history depth (12 ≈ ~480 rows,
    120 ≈ 4,177 rows ≈ ten years, the SEDI ceiling); clamped 1..120.
    --symbol RY --month-duration 12."""
    s = _symbol_arg(symbol)
    try:
        md = int(month_duration)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ca-tmx",
                       detail=f"month_duration must be an integer, got {month_duration!r}")
    if not 1 <= md <= 120:
        raise SdkError("usage_error", provider="ca-tmx",
                       detail=("month_duration must be 1..120 (120 ≈ ten years — the SEDI "
                               f"history ceiling), got {md}"))
    data, meta = _gql("insider", _Q_INSIDER, {"symbol": s, "monthDuration": md},
                      cache=cache, no_cache=no_cache)
    rows = data.get("getInsiderTransactions") or []
    if not isinstance(rows, list):
        rows = []
    rows = [x for x in rows if isinstance(x, dict)]
    return {"symbol": s, "month_duration": md, "rows": rows, "count": len(rows),
            "params": {"symbol": s, "monthDuration": md}, "_meta": meta}


def insider_activities(*, symbol, cache=None, no_cache=False):
    """→ {found, symbol, periods, summary, params, _meta}; the SEDI AGGREGATED
    view — per-insider buy/sell aggregates over three windows (threeMonths/
    sixMonths/twelveMonths) + an activitySummary net per period. --symbol RY."""
    s = _symbol_arg(symbol)
    data, meta = _gql("insider_activities", _Q_INSIDER_ACT, {"symbol": s},
                      cache=cache, no_cache=no_cache)
    root = data.get("getCompanyInsidersActivities") or {}
    return {"found": bool(root), "symbol": s,
            "periods": root.get("insiderActivities") or [],
            "summary": root.get("activitySummary") or [],
            "params": {"symbol": s}, "_meta": meta}


def index_constituents(*, index_symbol, cache=None, no_cache=False):
    """→ {found, index_symbol, rows, count, key_data, params, _meta}; an index's
    constituent list with quotedMarketValue/weight + the index keyData card
    (^TSX: 215 constituents, RY weight 7.7% on probe day). Index symbols carry
    the caret. --index-symbol ^TSX."""
    ix = str(index_symbol or "").strip()
    if not _INDEX_RE.fullmatch(ix):
        raise SdkError("usage_error", provider="ca-tmx",
                       detail=(f"index_symbol must be a caret TMX index form (e.g. ^TSX), "
                               f"got {index_symbol!r}"))
    data, meta = _gql("constituents", _Q_CONSTITUENTS, {"symbol": ix},
                      cache=cache, no_cache=no_cache)
    rows = [x for x in (data.get("constituents") or []) if isinstance(x, dict)]
    key_data = data.get("keyData") or {}
    return {"found": bool(rows), "index_symbol": ix, "rows": rows,
            "count": len(rows), "key_data": key_data,
            "params": {"symbol": ix}, "_meta": meta}


def wsh_events(*, symbol, cache=None, no_cache=False):
    """→ {symbol, events, count, params, _meta}; the corporate-events calendar
    (Wall Street Horizon sourced: EAD earnings announcement / ECC conference
    call / CON status, ISIN aboard for the registry join). THE SHAPE LAW:
    data.quote.data is the event LIST; event_date is MM/DD/YYYY verbatim (US
    order). --symbol RY."""
    s = _symbol_arg(symbol)
    data, meta = _gql("wsh", _Q_WSH, {"symbols": [s]}, cache=cache, no_cache=no_cache)
    quote = data.get("quote") or {}
    raw = quote.get("data") if isinstance(quote, dict) else None
    events = raw if isinstance(raw, list) else []
    events = [x for x in events if isinstance(x, dict)]
    return {"symbol": s, "events": events, "count": len(events),
            "params": {"symbols": [s]}, "_meta": meta}


def filings(*, symbol, limit=10, from_date=None, to_date=None,
            cache=None, no_cache=False):
    """→ {symbol, rows, count, params, _meta}; the regulatory-filings register
    (filingDate/description/name/size/urlToPdf). METADATA ONLY — urlToPdf
    points at app.quotemedia.com, robots-disallowed for /data/ (the PDF content
    is a banned face; the pointer value is kept, never fetched). from_date/
    to_date are API-level passthrough (upstream-supported, format unverified —
    probe certified symbol+limit only). --symbol RY --limit 10."""
    s = _symbol_arg(symbol)
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ca-tmx",
                       detail=f"limit must be an integer, got {limit!r}")
    if not 1 <= lim <= 50:
        raise SdkError("usage_error", provider="ca-tmx",
                       detail=f"limit must be 1..50, got {lim}")
    variables = {"symbol": s, "limit": lim}
    if from_date:
        variables["fromDate"] = str(from_date)
    if to_date:
        variables["toDate"] = str(to_date)
    data, meta = _gql("filings", _Q_FILINGS, variables, cache=cache, no_cache=no_cache)
    rows = [x for x in (data.get("filings") or []) if isinstance(x, dict)]
    return {"symbol": s, "rows": rows, "count": len(rows),
            "params": variables, "_meta": meta}


def dividends(*, symbol, page=1, batch=10, cache=None, no_cache=False):
    """→ {symbol, page, batch, rows, page_number, has_next_page, params, _meta};
    the dividend history, paginated (exDate/amount/currency/payableDate/
    declarationDate/recordDate). Page forward while has_next_page. --symbol RY
    --page 1 --batch 10."""
    s = _symbol_arg(symbol)
    try:
        pg = int(page)
        bt = int(batch)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ca-tmx",
                       detail=f"page/batch must be integers, got {page!r}/{batch!r}")
    if not 1 <= pg <= 500:
        raise SdkError("usage_error", provider="ca-tmx", detail=f"page must be 1..500, got {pg}")
    if not 1 <= bt <= 100:
        raise SdkError("usage_error", provider="ca-tmx", detail=f"batch must be 1..100, got {bt}")
    data, meta = _gql("dividends", _Q_DIVIDENDS, {"symbol": s, "page": pg, "batch": bt},
                      cache=cache, no_cache=no_cache)
    hist = data.get("dividendHistory") or {}
    rows = [x for x in (hist.get("dividends") or []) if isinstance(x, dict)]
    return {"symbol": s, "page": pg, "batch": bt, "rows": rows,
            "page_number": hist.get("pageNumber"),
            "has_next_page": bool(hist.get("hasNextPage")),
            "params": {"symbol": s, "page": pg, "batch": bt}, "_meta": meta}


def instrument_search(*, keywords, cache=None, no_cache=False):
    """→ {keywords, rows, hits, params, _meta}; the cross-exchange instrument
    resolver (symbol/name/exchange/instrumentType equity|etf) — spans the US
    cross-listings (A:US NYE forms), complementing the CA-only directory
    search. --keywords bank."""
    kw = str(keywords or "").strip()
    if not kw or len(kw) > 80:
        raise SdkError("usage_error", provider="ca-tmx",
                       detail=f"keywords must be 1..80 chars, got {keywords!r}")
    data, meta = _gql("instr_search", _Q_INSTR_SEARCH, {"keywords": kw},
                      cache=cache, no_cache=no_cache)
    rows = [x for x in (data.get("searchInstruments") or []) if isinstance(x, dict)]
    return {"keywords": kw, "rows": rows, "hits": len(rows),
            "params": {"keywords": kw}, "_meta": meta}
