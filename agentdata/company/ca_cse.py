"""ca_cse — Canadian Securities Exchange (CSE) listed universe + issuer market card
(thecse.com, keyless; 0.3.71 batch E13).

2026-11-19 probed laws (tmp/probe-e13/):
  - THE SITE IS A NEXT.JS HEAD OVER WORDPRESS, and every data surface rides the
    site's own /api/* JSON routes — no screen-scraping needed. The build manifest
    (/_next/static/<buildId>/_buildManifest.js) enumerates them: /api/webapi/
    listed-companies/ (the universe), /api/webapi/company/?symbol=…&type=listed
    (the issuer card), /api/indices, /api/export/… (POST), /api/csrf-token (form
    submits only — the GET faces never touch it).
  - LOCALE PREFIX IS MANDATORY: /en/api/webapi/listed-companies/ answers 200;
    the bare path answers 308 "Redirecting…" (text/plain 15B) whose target 404s
    when the trailing slash is dropped. Pin the slash AND the /en prefix — never
    ride redirects.
  - UNIVERSE: 739 rows probe day, one JSON array, fields already snake_case.
    Status distribution is the negative-list material: Active 628 / Suspended 85
    / Halted Pending Fundamental Change 23 / Delisted 3. tier 2×731, 1×8.
    security_type Equity 735 / Debenture 2 / ETF 2; currency CAD 733 / USD 6.
    outstanding_shares present on every row. trading_date is PER-ROW (last
    trade date, not an as-at anchor — Urbana 2014 rows still carry 2014).
  - ISSUER CARD: symbol → metadata (the same universe fields + description on
    the profile page payload), quote (bid/ask), ticker (OHLC/volume/value),
    trades (per-trade with buy_dealer/sell_dealer market-maker names), depth
    by order and by price, a CSE2 twin block, and consolidated (CSE+CSE2
    combined). `metatdata` [sic] is DEPRECATED upstream (removal_date
    2022-07-01) — the face reads `metadata` only and never emits the dead key.
  - BAD SYMBOL = 200 WITH A ZERO-BYTE BODY (application/json, 0B): the silent
    -empty law — found=false, never fabricated (the it_borsa silent-shape
    precedent).
  - `legal` rides the card too but is the DISCLAIMER text only (CNSX Markets
    no-warranty) — carried verbatim on the result, not a facts surface.

Politeness 1 rps (no published quota; probes all 200). TTLs: universe 1h
(intraday fields ride the rows), issuer card 5min (live quote fields).
"""
import json

from ..errors import SdkError

provider = {
    "id": "ca_cse",
    "baseUrl": "https://thecse.com",
    "rate": {"rps": 1.0, "burst": 1},
    "ops": {
        # /en prefix + trailing slash are the measured live shape (bare path
        # 308-redirects and the slashless target 404s — pin, never ride)
        "listed": {"path": "/en/api/webapi/listed-companies/",
                   "idempotent": True, "accept": "text", "timeout": 45.0},
        "company": {"path": "/en/api/webapi/company/",
                    "idempotent": True, "accept": "text", "timeout": 45.0},
    },
    "ttl": {"listed": 3600, "company": 300},
}


def _parse_json(text):
    """accept:'text' + manual parse — the 0-byte body must be distinguishable
    from JSON null (the bad-symbol law answers 200/0B, not 404)."""
    if not text or not text.strip():
        return None
    return json.loads(text)


def listed(*, symbol=None, name=None, sector=None, status=None, security_type=None,
           tier=None, limit=None, cache=None, no_cache=False):
    """→ {total, rows[], params, _meta}; the CSE listed universe (739 rows probe
    day), fields verbatim as the upstream serves them (already snake_case).
    Client-side selectors: --symbol exact (case-insensitive), --name substring,
    --sector/--status/--security-type exact case-insensitive, --tier int,
    --limit slices the display. Suspended/Halted/Delisted rows ride the
    universe — --status is the negative-list filter."""
    from ..transport import call_provider

    r = call_provider(provider, "listed", {}, cache=cache, no_cache=no_cache)
    data = _parse_json(r["data"])
    if not isinstance(data, list):
        raise SdkError("upstream_unavailable", provider="ca_cse",
                       detail="listed-companies did not answer a JSON array — "
                              "the site API may have moved; re-probe")
    q_symbol = str(symbol).strip().upper() if symbol else None
    q_name = str(name).strip().lower() if name else None
    q_sector = str(sector).strip().lower() if sector else None
    q_status = str(status).strip().lower() if status else None
    q_type = str(security_type).strip().lower() if security_type else None
    rows = []
    for row in data:
        if q_symbol and str(row.get("symbol") or "").upper() != q_symbol:
            continue
        if q_name and q_name not in str(row.get("security_name") or "").lower():
            continue
        if q_sector and str(row.get("sector") or "").lower() != q_sector:
            continue
        if q_status and str(row.get("status") or "").lower() != q_status:
            continue
        if q_type and str(row.get("security_type") or "").lower() != q_type:
            continue
        if tier is not None and row.get("tier") != int(tier):
            continue
        rows.append(row)
    total = len(rows)
    if limit is not None and int(limit) >= 0:
        rows = rows[: int(limit)]
    return {"total": total, "rows": rows,
            "params": {"symbol": symbol, "name": name, "sector": sector,
                       "status": status, "security_type": security_type,
                       "tier": tier, "limit": limit},
            "_meta": r}


def company(*, symbol, cache=None, no_cache=False):
    """→ {found, symbol, card|None, params, _meta}; the issuer market card for
    one CSE symbol: metadata (issuer fields + description), quote (bid/ask),
    ticker (OHLC/volume/value), trades (per-trade with dealer names),
    depth_by_order / depth_by_price, the CSE2 twin block and consolidated.
    The card is returned verbatim (minus the deprecated `metatdata` key — the
    upstream itself marked it for removal 2022-07-01; `metadata` is the live
    one). Bad symbol = 200 with a ZERO-BYTE body → found=false (the
    silent-empty law; never fabricated)."""
    from ..transport import call_provider

    sym = str(symbol or "").strip().upper()
    if not sym:
        raise SdkError("usage_error", provider="ca_cse",
                       detail="--symbol is required (a CSE ticker, e.g. PAU)")
    r = call_provider(provider, "company", {"symbol": sym, "type": "listed"},
                      cache=cache, no_cache=no_cache)
    card = _parse_json(r["data"])
    found = isinstance(card, dict) and bool(card.get("metadata"))
    if found:
        card.pop("metatdata", None)  # deprecated upstream 2022-07-01 — dead key, never emit
    return {"found": found, "symbol": sym, "card": card if found else None,
            "params": {"symbol": sym, "type": "listed"}, "_meta": r}
