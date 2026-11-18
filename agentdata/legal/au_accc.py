"""au_accc — Australian Competition & Consumer Commission, the news-centre
Compliance & enforcement axis (www.accc.gov.au, Drupal 10 views, keyless
but fingerprinted + lazy).

AU legal face (0.3.63; admitted from the research booklet 册 legal-enforcement
3c; probed live 2026-11-16 tmp/probe-e5/): the enforcement-actions stream —
media releases / speeches / updates on the Compliance and enforcement topic
(topic:12039, ~3,106 items / 125 pages on 2026-11-16).

LIVE LAWS (measured 2026-11-16, tmp/probe-e5/; the listing was REDEPLOYED
mid-batch — the morning channel died at 09:00Z, re-probed 10:30-11:30Z):
  - HEADER FINGERPRINT GATE: the SDK's polite UA alone is not refused, but
    the pinned Chrome browser-header suite (the afdb ext-8 law) is what the
    probes passed with — every op rides the suite.
  - LAZY VIEWS, TWO HOPS: the listing page renders form + FILTERED pager but
    an EMPTY view-content behind a lazy-views-placeholder. The rows exist
    ONLY through GET /views/ajax — the viewsAjaxHistory module's own hop
    (httpMethod GET,Drupal.ajax) — with the FULL exposed-input shape:
      view_name=news_centre&view_display_id=listing_search&view_args=&
      view_path=/node/162342&view_base_path=rss/news_centre.xml&
      pager_element=0&f[]=topic:<N>&page=<0-BASED>[&type=accc_news|acccgov_update]
    → 200 BARE JSON command object {"0":{command:settings…},…,"3":{command:
    insert,method:replaceWith,selector:.js-view-dom-id-,data:108KB HTML}}.
    (The legacy textarea-wrapped envelope lives on the _wrapper_format=drupal_ajax
    listing GET, which since the redeploy returns form+pager WITHOUT rows —
    parse_list keeps both envelope branches.) X-Requested-With is NOT needed
    on the GET (it gates the POST path only); the pinned suite alone passes.
  - EXPOSED-INPUT-BOUND FILTERS: the topic filter is the ARRAY form f[]
    (f[0] is ignored by /views/ajax) and `type` is the content-type tab —
    topic:12039 → 125 pages, topic:141 → 17, type=acccgov_update → 2,
    type=accc_news → 120 (measured). Dropping any of the shape fields
    (view_path/pager_element/…) drops the rows with them — send the full
    shape verbatim.
  - PAGES ARE 0-BASED (page=0..124 in the pager links). 25 cards per page
    measured; the /views/ajax pager hrefs ride the entity-escaped &amp;.
  - CARD SHAPE: <div data_url="{path}" … data_type="accc-news|acccgov-update">
    wrapping accc-date-card markup — the ribbon div is the type label
    (Media release / Speech / Update), the publish--day/--month/--year spans
    the date (3-letter EN month), the h2 inside field--name-node-title the
    title (&#039; entities), field--name-field-acccgov-summary the summary,
    terms-badge links the topics. Attribute order varies — parse
    whitespace-tolerantly (the data_url attribute may sit on its own line).
  - PATH FAMILIES: /media-release/{slug}, /about-us/news/media-updates/{slug},
    /about-us/news/speeches/{slug} — data_url is the stable item key.

TERMS 🟢 CC BY 4.0 (the Disclaimer-and-copyright page, node/454, verbatim):
"All material presented on this website is provided under a Creative Commons
Attribution 4.0 International licence (or CC BY 4.0 licence)" — attribution
"Source: ACCC © Commonwealth of Australia"; modified material "Based on ACCC
data or other content". The AU-gov standard family (au_cer/ausTender/ASIC).

Politeness: 0.5/2, concurrency 1 (a heavy Drupal host), TTL 12h.
"""
import html as _html
import json
import re

from ..errors import SdkError

provider = {
    "id": "au_accc",
    "baseUrl": "https://www.accc.gov.au",
    "rate": {"rps": 0.5, "burst": 2},
    "concurrency": 1,
    "ops": {
        "list": {"path": "/views/ajax", "accept": "text", "timeout": 60.0},
    },
    "ttl": {"list": 12 * 3600},
}

_SUITE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
}
_DEFAULT_TOPIC = "12039"   # Compliance and enforcement — the enforcement-actions axis
_TYPES = {"news": "accc_news", "update": "acccgov_update"}

_TAG = re.compile(r"<[^>]+>")
_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
_CARD_KEY = re.compile(r'<div[^>]*data_url="([^"]+)"[^>]*data_type="([^"]*)"')
_RIBBON = re.compile(r'(?s)accc-date-card__ribbon[^>]*>\s*<div[^>]*>\s*(.*?)\s*</div>')
_DATE = re.compile(r'publish--day">(\d+)</span>\s*<span[^>]*publish--month">(\w+)</span>\s*'
                   r'<span[^>]*publish--year">(\d+)')
_TITLE = re.compile(r"(?s)<h2[^>]*>(.*?)</h2>")
_SUMMARY = re.compile(r'(?s)field--name-field-acccgov-summary[^>]*>\s*(.*?)\s*</div>')
_TOPIC = re.compile(r'terms-badge"><a href="[^"]*topic%3A(\d+)[^"]*"[^>]*>(.*?)</a>')
# pager links ride the entity-escaped &amp; inside the insert HTML (measured on
# both channels: ?f%5B0%5D=…&amp;_wrapper_format=drupal_ajax&amp;page=0..124 on
# the legacy listing GET, ?f%5B0%5D=…&amp;page=0..124 on /views/ajax — a bare
# [?&]page= regex silently sees page 0 forever)
_PAGER = re.compile(r"(?:[?&]|&amp;)page=(\d+)")


def _text(fragment):
    return re.sub(r"\s+", " ", _TAG.sub(" ", _html.unescape(str(fragment)))).strip()


def parse_list(text):
    """drupal_ajax / views-ajax command stream → (cards[], max_page_seen)
    (pure function; the insert command carries the whole rendered listing +
    pager). Two envelope branches, both measured: the legacy textarea-wrapped
    JSON array (_wrapper_format GET) and the bare JSON command OBJECT
    {"0":{…},…} that GET /views/ajax answers (the 0.3.63 redeploy channel)."""
    m = re.match(r"(?s)^\s*<textarea[^>]*>(.*)</textarea>\s*$", text)
    if m:
        try:
            cmds = json.loads(m.group(1))
        except ValueError:
            return [], 0
    else:
        if text.lstrip()[:1] not in ("{", "["):
            return [], 0
        try:
            doc = json.loads(text)
        except ValueError:
            return [], 0
        cmds = list(doc.values()) if isinstance(doc, dict) else doc
    ins = next((c for c in cmds if isinstance(c, dict) and c.get("command") == "insert"), None)
    html = (ins or {}).get("data") or ""
    keys = list(_CARD_KEY.finditer(html))
    cards = []
    for i, km in enumerate(keys):
        seg = html[km.start(): keys[i + 1].start() if i + 1 < len(keys) else len(html)]
        path = _html.unescape(km.group(1))
        dm = _DATE.search(seg)
        tm = _TITLE.search(seg)
        if not tm:
            continue
        day, mon, year = (dm.group(1), dm.group(2), dm.group(3)) if dm else (None, None, None)
        date_iso = None
        if dm and mon in _MONTHS:
            date_iso = f"{year}-{_MONTHS[mon]:02d}-{int(day):02d}"
        sm = _SUMMARY.search(seg)
        topics = [(_html.unescape(t), _text(lbl)) for t, lbl in _TOPIC.findall(seg)]
        cards.append({
            "path": path,
            "url": f"{provider['baseUrl']}{path}",
            "content_type": km.group(2),                       # accc-news | acccgov-update
            "item_type": _text(_RIBBON.search(seg).group(1)) if _RIBBON.search(seg) else None,
            "date_iso": date_iso,
            "date": f"{day} {mon} {year}" if dm else None,
            "title": _text(tm.group(1)),
            "summary": _text(sm.group(1)) if sm else None,
            "topics": [{"id": t, "label": lbl} for t, lbl in topics] or None,
        })
    pages = max((int(p) for p in _PAGER.findall(html)), default=0) + 1
    return cards, pages


def actions_raw(topic=_DEFAULT_TOPIC, q=None, page=0, action_type=None, *,
                limit=20, cache=None, no_cache=False):
    """→ {rows, total_matched, page, pages, page_size, params, _meta}.

    topic = the news-centre topic id (default 12039 = Compliance and
    enforcement, the enforcement-actions axis; other ids exist — 141 Food
    and groceries, 138 Franchising…). page is 0-BASED (the Drupal views
    convention). action_type = news|update (the news-centre content-type
    tabs). q is a LOCAL substring over title+summary on the fetched page —
    the upstream search box is a separate unexposed surface. 25 cards/page
    measured; the face walks one page per call."""
    if action_type not in (None, "") and action_type not in _TYPES:
        raise SdkError("usage_error", provider="au_accc",
                       detail=f"action_type must be one of {'|'.join(_TYPES)}, got {action_type!r}")
    page_i = int(page) if page not in (None, "") else 0
    if page_i < 0:
        raise SdkError("usage_error", provider="au_accc",
                       detail=f"page is 0-based, got {page!r}")
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="au_accc",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    topic_s = str(topic or _DEFAULT_TOPIC).strip()
    if not topic_s.isdigit():
        raise SdkError("usage_error", provider="au_accc",
                       detail=f"topic must be the numeric news-centre topic id, got {topic!r}")
    from ..transport import call_provider

    # the FULL exposed-input shape (the viewsAjaxHistory module's own hop) —
    # dropping any field drops the rows with it; f[] array form (f[0] ignored)
    params = {
        "view_name": "news_centre",
        "view_display_id": "listing_search",
        "view_args": "",
        "view_path": "/node/162342",
        "view_base_path": "rss/news_centre.xml",
        "pager_element": "0",
        "f[]": f"topic:{topic_s}",
        "page": str(page_i),
    }
    if action_type:
        params["type"] = _TYPES[action_type]
    r = call_provider(provider, "list", params, cache=cache, no_cache=no_cache,
                      extra_headers=_SUITE)
    cards, pages = parse_list(r["data"])
    needle = str(q or "").strip().lower() or None
    hits = [c for c in cards
            if not needle or needle in f"{c.get('title') or ''} {c.get('summary') or ''}".lower()]
    return {
        "rows": hits[:size],
        "total_matched": len(hits),
        "page": page_i,
        "pages": pages or None,
        "page_size": len(cards),
        "params": {"topic": topic_s, "q": needle, "page": page_i,
                   "action_type": action_type or None, "limit": size},
        "_meta": r,
    }
