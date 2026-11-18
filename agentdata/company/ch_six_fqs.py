"""ch_six_fqs — SIX Swiss Exchange FQS reference query (six-group.com /fqs/ref.json, keyless).

2026-11-18 probed shape (tmp/probe-e10/p3/p3b): GET /fqs/ref.json?select={cols}&where=PortalSegment={seg}
&orderby={col}&page={n}&pagesize={n} → {totalRows, colNames[], rowData[][], pageNumber, pageSize,
delayMinutes, copyRight…} — a command-style query API (15-min delayed feed; protocol fqs.json).
Segment cardinalities re-verified live: EQ 813 / BO 3,010 / FU 3,207 / IN 2,548.

COLUMN ORACLE (probed): an invalid select column → 400 "Invalid name 'X' in select parameter";
select is REQUIRED ("Missing request parameter 'select'"). Valid reference columns (the engine's
default preset): ISIN, IssuerNameFull, ValorNumber, SBISector, SBISectorDesc, SecTypeDesc,
FirstTradingDate, LastTradingDate, Currency. Valid opt-in columns: ValorId (ISIN+currency+segment
16-char composite), NumberInIssue, ClosingPriceCHF (SIX closing prices carry a commercial-use
caveat — they are opt-in via --columns, never in the default preset), PortalSegment.
INVALID (oracle-rejected, do not guess): IssuerName, InstrumentName, SecurityName, Symbol,
TradingSymbol, TickerSymbol, SecType (only SecTypeDesc exists), ICB, Market, ListingVenue.
EQ-segment honesty law: SBISector/SBISectorDesc are EMPTY strings on most EQ rows (sector codes
fill on the bond segment) — passed through verbatim, never fabricated.
TTL 15 min (aligns with the upstream delayMinutes); politeness 1 rps.
"""
from ..errors import SdkError

provider = {
    "id": "ch_six_fqs",
    "baseUrl": "https://www.six-group.com",
    "rate": {"rps": 1.0, "burst": 2},
    "ops": {
        # params: select/where/orderby/page/pagesize (all query params)
        "search": {"path": "/fqs/ref.json", "idempotent": True, "timeout": 30.0},
    },
    "ttl": {"search": 900},
}

SEGMENTS = ("EQ", "BO", "FU", "EP", "DE", "IN", "OT")
DEFAULT_COLUMNS = ("ISIN", "IssuerNameFull", "ValorNumber", "SBISector", "SBISectorDesc",
                   "SecTypeDesc", "FirstTradingDate", "Currency")
OPT_IN_COLUMNS = ("ValorId", "NumberInIssue", "ClosingPriceCHF", "LastTradingDate", "PortalSegment")
_KNOWN_INVALID = ("IssuerName", "InstrumentName", "SecurityName", "Symbol", "TradingSymbol",
                  "TickerSymbol", "SecType", "ICB", "Market", "ListingVenue", "MarketCapitalization")


def search_universe(segment="EQ", *, columns=None, order_by="ISIN", page=1, pagesize=100,
                    cache=None, no_cache=False):
    """→ {instruments[], total_rows, col_names, page, pagesize, params, _meta}; one FQS page.
    columns: comma list overriding the default reference preset — opt-in price columns
    (ClosingPriceCHF/NumberInIssue) travel ONLY here (SIX commercial-use caveat on closing prices)."""
    from ..transport import call_provider

    seg = str(segment or "EQ").strip().upper()
    if seg not in SEGMENTS:
        raise SdkError("usage_error", provider="ch_six_fqs",
                       detail=f"segment must be one of {'/'.join(SEGMENTS)}, got \"{segment}\"")
    cols = [c.strip() for c in str(columns or "").split(",") if c.strip()] if columns else list(DEFAULT_COLUMNS)
    bad = [c for c in cols if c in _KNOWN_INVALID]
    if bad:
        raise SdkError("usage_error", provider="ch_six_fqs",
                       detail=f"column(s) {bad} are oracle-rejected by the upstream (400 Invalid name) — see ch_six_fqs docstring for the valid column space")
    pg = max(1, int(page or 1))
    ps = min(max(1, int(pagesize or 100)), 500)
    sel = ",".join(cols)
    where = f"PortalSegment={seg}"
    params = {"select": sel, "where": where, "orderby": str(order_by or "ISIN"),
              "page": pg, "pagesize": ps}
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    names = d.get("colNames") or []
    instruments = [dict(zip(names, row)) for row in d.get("rowData") or []]
    return {"instruments": instruments,
            "total_rows": d.get("totalRows"), "col_names": names,
            "delay_minutes": d.get("delayMinutes"),
            "page": pg, "pagesize": ps,
            "params": params, "_meta": r}
