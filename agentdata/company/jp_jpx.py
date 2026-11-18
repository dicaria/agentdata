"""jp_jpx — JPX quote gateway (quote.jpx.co.jp qjsonp.aspx JSON, keyless + Referer door).

2026-11-18 probed shape (tmp/probe-e10/p5):
  F=ctl/stock_list&key2={section}&refindex=01&maxdisp=100&page={n} → {section1: {hitcount,
  pagecount, data[100]}} — key2=1 walks the WHOLE universe (hitcount 4,490 / pagecount 45 on
  probe day); each row self-describes its board (LISSE_CNV: Prime/Standard/Growth/…) and 33-sector
  industry (JSEC code + JSECE_CNV English) alongside TTCODE2 (issue code), FLLN/FLLNE (JP/EN
  long names), DPP last price, DV volume, ROE/PER/PBR. The HTML listing pages are placeholder
  shells — the gateway is the only data path (memory 680).
  F=ctl/stock_detail&qcode={code} → section1.data is a DICT keyed "{code}/T" carrying 57 fields:
  ISIN, MKCP market cap (JPY, comma-grouped), SHRK shares issued, LOSH trading lot,
  A_HISTDAYL embedded daily OHLCV block, INDEX_INFOMATION yearly EPS history, 52-week
  YHPR/YLPR with dates, full quote stack (DHP/DLP/DOP/DPP…).
REFERER DOOR (life-or-death): a bare gateway call → 503 {"error":"リファラー…"} naming the missing
Referer; with Referer …/index.aspx?f=e_stock_list → 200. No cookie. The engine pins the Referer
on every call via extra_headers (transport extension 8).
TTL 1 day (daily-moving fields); politeness 1 rps (probed at 1.5s spacing).
"""
from ..errors import SdkError

provider = {
    "id": "jp_jpx",
    "baseUrl": "https://quote.jpx.co.jp",
    "rate": {"rps": 1.0, "burst": 2},
    "ops": {
        # params: F(fixed ctl/stock_list)/key2/refindex/maxdisp/page — F is fixed by the op, sent as param
        "list": {"path": "/jpxhp/jcgi/wrap/qjsonp.aspx", "idempotent": True, "timeout": 30.0},
        # params: F(fixed ctl/stock_detail)/qcode
        "detail": {"path": "/jpxhp/jcgi/wrap/qjsonp.aspx", "idempotent": True, "timeout": 30.0},
    },
    "ttl": {"list": 86400, "detail": 86400},
}

_REFERER = {"Referer": "https://quote.jpx.co.jp/jpxhp/en/index.aspx?f=e_stock_list"}

_LIST_ROW = {
    "TTCODE2": "code", "FLLN": "name_ja", "FLLNE": "name_en",
    "LISSE": "board", "LISSE_CNV": "board_ja",
    "JSEC": "industry_code", "JSECE_CNV": "industry_en", "JSEC_CNV": "industry_ja",
    "DPP": "last_price", "DV": "volume", "ROE": "roe_pct", "PER": "per", "PBR": "pbr",
}


def list_stocks(*, section="1", page=1, maxdisp=100, cache=None, no_cache=False):
    """→ {stocks[], hitcount, pagecount, page, section, params, _meta}; one page of the listed universe.
    section is the upstream key2 board-section code ("1" = all sections — rows carry their own board);
    page is 1-based (page 1 = empty/1 upstream, both accepted probed); maxdisp 1-100 is the upstream page cap."""
    from ..transport import call_provider

    sec = str(section or "1").strip() or "1"
    pg = max(1, int(page or 1))
    md = min(max(1, int(maxdisp or 100)), 100)
    r = call_provider(provider, "list",
                      {"F": "ctl/stock_list", "key2": sec, "refindex": "01",
                       "maxdisp": md, "page": pg},
                      cache=cache, no_cache=no_cache, extra_headers=_REFERER)
    s1 = (r["data"] or {}).get("section1") or {}
    rows = []
    for d in s1.get("data") or []:
        row = {v: d.get(k) for k, v in _LIST_ROW.items()}
        row["code"] = row.get("code") or None
        rows.append(row)
    return {"stocks": rows,
            "hitcount": s1.get("hitcount"), "pagecount": s1.get("pagecount"),
            "page": pg, "section": sec,
            "params": {"F": "ctl/stock_list", "key2": sec, "refindex": "01",
                       "maxdisp": md, "page": pg},
            "_meta": r}


def stock_detail(qcode, *, cache=None, no_cache=False):
    """→ {detail, params, _meta}; the 57-field card by issue code (e.g. 7203 = Toyota).
    section1.data is a dict keyed "{code}/T" — the engine takes the single value (any suffix form).
    Unknown codes return an EMPTY data dict upstream (honest zero, not an error)."""
    from ..transport import call_provider

    q = str(qcode or "").strip()
    if not q or not q.replace("/", "").isdigit():
        raise SdkError("usage_error", provider="jp_jpx",
                       detail=f"qcode must be a JPX issue code like 7203 (digits, optional /T), got \"{qcode}\"")
    r = call_provider(provider, "detail", {"F": "ctl/stock_detail", "qcode": q},
                      cache=cache, no_cache=no_cache, extra_headers=_REFERER)
    s1 = (r["data"] or {}).get("section1") or {}
    data = s1.get("data") or {}
    card = None
    if isinstance(data, dict) and data:
        key = next(iter(data))          # "{code}/T"
        card = dict(data[key])
        card["TTCODE"] = card.get("TTCODE") or key
    return {"detail": card, "params": {"F": "ctl/stock_detail", "qcode": q}, "_meta": r}
