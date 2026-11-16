"""dk_ft — Finanstilsynet (Denmark's financial supervisory authority) supervision archive
(inspection reports + supervisory decisions, www.finanstilsynet.dk/gbapi/search/getPage, keyless).

DK legal face (0.3.60; admitted from research booklet dk-ft-gbapi-eu-finreg-sweep 册, re-probed
live 2026-11-13, tmp/probe-e2/dk_*.json — two live laws the booklet did not carry are baked in
here: (1) the POST REQUIRES a Referer header (without it the API answers 400 "Incorrect request
referer header" — the booklet's "零门 urllib bare POST" no longer holds); (2) the request body is
a NESTED object — userInput is an object {query, months, categorizations, additionalFilters,
template} (+ from/to/exactMatch/sortBy), not a plain string (a string userInput answers 400).
The page HTML also carries the search configuration that the POST body must echo back verbatim.

CONTRACT (two steps, both keyless):
  1. GET /tilsyn/inspektionsredegoerelser-og-afgoerelser/ → the archive page; the
     `data-config` attribute of the archive-search-result div is HTML-escaped JSON
     (&#xA; newlines, &quot; quotes) — unescape → the `config` object the POST body must carry
     ({options{…}, clearAllFiltersText, mobileFiltersText, context, hash}).
  2. POST /gbapi/search/getPage, Content-Type application/json, Referer = the archive page URL
     (REQUIRED — 400 without it), body:
       {config: <step-1 object verbatim>, page: <1-based>,
        userInput: {query, months: [], categorizations: [], additionalFilters: {}, template: "All"}
                   + from/to (year window) + exactMatch + sortBy,
        lastGroupName: null, rootFolders: null}
     Response: {pageHtml, totalResultCount: {All, WebPage, NewsPage, PublicationPage, PDF},
                additionalData, lastGroupName}. 10 items per page (measured).
     The year filter rides userInput.from / userInput.to as
     `${year}-01-01T00:00:00` / `${year}-12-31T23:59:59` (server-side — the page label
     "2025 (214)" matches the API count exactly, measured).
     pageHtml items: <div class="item" data-url="URL"><div class="text">
     <p class="pre-heading">TYPE</p><h2 class="heading"><a href="URL">TITLE</a></h2>
     <span class="date"><span class="datetime" data-date="ISO" data-format="dd-MM-yyyy">
     DD-MM-YYYY</span></span><p>TEASER</p> — the text carries numeric HTML entities
     (&#xF8; = ø), so it is unescaped, not passed through.

Counts (live 2026-11-13): 4,038 decisions in the archive (All = NewsPage = 4,038; WebPage /
PublicationPage / PDF = 0); "Danske Bank" → 1,651; year 2025 → 214; "Realkredit Danmark" + 2025
→ 95. The archive page states the filters combine with the year only — the face keeps the
server-side year window and the free-text query, both upstream parameters.

Politeness: 0.25/2, concurrency 1, TTL 12h (the archive refreshes daily).
"""
import html
import json
import re

from ..errors import SdkError

provider = {
    "id": "dk_ft",
    "baseUrl": "https://www.finanstilsynet.dk",
    "rate": {"rps": 0.25, "burst": 2},
    "concurrency": 1,
    "ops": {
        # step 1 — the archive page (the data-config attribute is the POST body's config object)
        "config": {"path": "/tilsyn/inspektionsredegoerelser-og-afgoerelser/", "accept": "text",
                   "timeout": 30.0},
        # step 2 — the search POST (Referer REQUIRED — 400 "Incorrect request referer header")
        "search": {"path": "/gbapi/search/getPage", "method": "POST", "idempotent": True,
                   "timeout": 30.0},
    },
    "ttl": {"config": 6 * 3600, "search": 12 * 3600},
}

_ARCHIVE_URL = "https://www.finanstilsynet.dk/tilsyn/inspektionsredegoerelser-og-afgoerelser/"

_DATA_CONFIG = re.compile(r'data-config="([^"]+)"', re.S)
_ITEM = re.compile(r'<div class="item"[^>]*data-url="([^"]*)"(.*?)(?=<div class="item"|</div></div>\s*$|$)', re.S)
_PRE_HEADING = re.compile(r'<p class="pre-heading">(.*?)</p>', re.S)
_HEADING = re.compile(r'<h2 class="heading"><a href="([^"]*)">(.*?)</a></h2>', re.S)
_DATETIME = re.compile(r'<span class="datetime[^"]*"[^>]*data-date="([^"]*)"[^>]*>(.*?)</span>', re.S)
_TEASER = re.compile(r'</span></span><p>(.*?)</p>', re.S)


def _text(s):
    """HTML fragment → plain text (numeric entities like &#xF8; included)."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _config_from_page(page_text):
    """The archive page's data-config attribute → the config object the POST body must carry."""
    m = _DATA_CONFIG.search(page_text or "")
    if not m:
        raise SdkError("upstream_unavailable", provider="dk_ft",
                       detail="the archive page carries no data-config attribute — the gbapi "
                              "search configuration is no longer embedded in the page")
    try:
        cfg = json.loads(html.unescape(m.group(1)))
    except ValueError as e:
        raise SdkError("upstream_unavailable", provider="dk_ft",
                       detail=f"the archive page's data-config is not parsable JSON: {e}")
    if not isinstance(cfg, dict) or "options" not in cfg:
        raise SdkError("upstream_unavailable", provider="dk_ft",
                       detail="the archive page's data-config carries no options object — the "
                              "gbapi body shape may have changed")
    return cfg


def item_from_html(url, body):
    """One archive item (pure function — split out for offline testing)."""
    pre = _PRE_HEADING.search(body)
    head = _HEADING.search(body)
    dt = _DATETIME.search(body)
    teaser = _TEASER.search(body)
    return {
        "type": _text(pre.group(1)) if pre else None,
        "title": _text(head.group(2)) if head else None,
        "url": head.group(1) if head else url,
        "date": dt.group(1) if dt else None,
        "date_display": dt.group(2).strip() if dt else None,
        "teaser": _text(teaser.group(1)) if teaser else None,
    }


def parse_items(page_html):
    """The pageHtml → item cards (pure function — split out for offline testing)."""
    out = []
    for url, body in _ITEM.findall(page_html or ""):
        row = item_from_html(html.unescape(url), body)
        if row["title"] or row["url"]:
            out.append(row)
    return out


def _user_input(term="", year=None, exact_match=None):
    """The nested userInput object (live law: an OBJECT, not a string)."""
    ui = {
        "query": term or "",
        "months": [],
        "categorizations": [],
        "additionalFilters": {},
        "template": "All",
    }
    if year:
        ui["from"] = f"{year}-01-01T00:00:00"
        ui["to"] = f"{year}-12-31T23:59:59"
    if exact_match is not None:
        ui["exactMatch"] = bool(exact_match)
    return ui


def decisions_raw(term="", *, year=None, page=1, exact_match=None, cache=None, no_cache=False):
    """→ {total, counts, rows[], params, _meta}. term = free-text query (upstream server-side,
    e.g. "Danske Bank" → 1,651 hits); year = server-side year window (2025 → 214 hits, the
    page label matches); page is 1-based (10 items per page upstream)."""
    from ..transport import call_provider

    q = str(term or "").strip()
    try:
        pg = int(page) if page is not None else 1
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="dk_ft", detail=f"page must be an integer >=1, got {page!r}")
    if pg < 1:
        raise SdkError("usage_error", provider="dk_ft", detail=f"page is 1-based, got {pg}")
    if year is not None:
        try:
            yr = int(year)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="dk_ft", detail=f"year must be an integer, got {year!r}")
        if not 1900 <= yr <= 2100:
            raise SdkError("usage_error", provider="dk_ft", detail=f"year must be a plausible year, got {yr}")
    else:
        yr = None

    r_cfg = call_provider(provider, "config", {}, cache=cache, no_cache=no_cache)
    cfg = _config_from_page(r_cfg.get("data") or "")

    body = {"config": cfg, "page": pg, "userInput": _user_input(q, yr, exact_match),
            "lastGroupName": None, "rootFolders": None}
    r = call_provider(provider, "search", body, cache=cache, no_cache=no_cache,
                      extra_headers={"Referer": _ARCHIVE_URL,
                                     "Origin": "https://www.finanstilsynet.dk"})
    doc = r["data"] or {}
    if not isinstance(doc, dict) or "pageHtml" not in doc:
        raise SdkError("upstream_unavailable", provider="dk_ft",
                       detail="getPage answered an unexpected shape (no pageHtml — the Referer "
                              "law or the nested userInput body shape may have drifted)")
    counts = doc.get("totalResultCount") or {}
    rows = parse_items(doc.get("pageHtml"))
    return {
        "total": counts.get("All"),
        "counts": counts,
        "rows": rows,
        "params": {"q": q, "year": yr, "page": pg, "exact_match": exact_match},
        "_meta": r,
    }
