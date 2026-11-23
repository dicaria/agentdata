"""de_xetra — Deutsche Börse Xetra/Frankfurt tradable-instrument universe +
Newsboard event stream (cashmarket.deutsche-boerse.com, keyless; 0.3.73 batch E15).

The site moved here from www.xetra.com (og:description self-describes
"formerly xetra.com"); robots on the new host carries zero Disallow.

2026-11-20 probed laws (tmp/probe-e15/):
  - TWO-STEP BLOB-HASH LAW: the T7 CSVs live at /resource/blob/{id}/{hash}/data/
    t7-{xetr|xfra-BF}-allTradableInstruments.csv and the hash VERSIONS on every
    upload — the link must be re-parsed from its landing page on every fetch,
    never hard-coded. XETR page: /cash-en/trading/Tradable-Instruments-Xetra/
    Downloads; XFRA page: /cash-en/trading/Tradable-Instruments-Xetra/
    boersefrankfurt (yes — the Frankfurt variant hangs UNDER the Xetra section;
    /cash-en/trading/Tradable-Instruments-Frankfurt/Downloads is a 404 decoy).
    The CSV filenames differ by prefix: t7-xetr-… vs t7-xfra-BF-….
  - CSV SHAPE: ';' separated; rows 1-2 are metadata (Market:;XETR and
    Date Last Update:;20.11.2026 — the snapshot anchor), row 3 is the header,
    row 4+ data. A UTF-8 BOM appears on some fetches and not others —
    decode utf-8-sig covers both. XETR ≈5.5k rows × 153 cols (ETF/CS/ETN/ETC);
    XFRA ≈56k rows, bond-heavy — the engine exposes both, default XETR.
  - INSTRUMENT TYPE lives at the 'Instrument Type' column (ETF/CS/ETN/ETC…);
    the PAG country grouping rides 'Product Assignment Group' (AST0-style
    codes). Counts drift daily (ETF 3,204 vs 3,179 three days earlier) —
    snapshot counts are annotated, never pinned.
  - NEWSBOARD RSS = /cash-en/Stay-Informed/newsroom/Xetra-Frankfurt-Newsboard/
    4091644!rss — a 100-item ROLLING window (~15h at the probe cadence);
    titles carry the venue prefix (XETR:/XFRA:), the event class and the ISIN
    or mnemonic ("XETR: DIVIDEND/INTEREST INFORMATION -  23.11.2026 -
    IE000T8QD852", "XETR: DE000A4APQX6: Aussetzung/Suspension"). Hourly
    polling is the no-loss cadence; deeper history = the search face.
  - SEARCH FACE = …/4091644!search?query=…&pageNum=…&hitsPerPage=100 — full
    history (delisting notices back to the 2020 number block ride ISINs in the
    path). Page 1 answers WITHOUT a state token; the response carries a
    gzip+base64 state parameter (H4sIAAAA… — it embeds "&sort=sDate desc"),
    pageNum rides statelessly. Results: 100 × class="search-result-content" +
    search-result-date + download links.
  - api.live.deutsche-boerse.com is a CATCH-ALL SHELL (every endpoint answers
    200 with a 2-byte {}, null paths echo the same shape — the null-path
    contrast law; Origin/Referer/cookie all ineffective) — NEGATIVE, never
    touched by this engine.

Politeness 1 rps, burst 1. TTLs: instruments 6h (the CSV re-versions
intraday; Date Last Update is the anchor), newsboard 30min (rolling window),
search 1h.
"""
import csv
import io
import re
import time
import xml.etree.ElementTree as ET

from ..errors import SdkError

provider = {
    "id": "de_xetra",
    "baseUrl": "https://www.cashmarket.deutsche-boerse.com",
    "rate": {"rps": 1.0, "burst": 1},
    "ops": {
        "xetra_downloads": {"path": "/cash-en/trading/Tradable-Instruments-Xetra/Downloads",
                            "idempotent": True, "accept": "text", "timeout": 90.0},
        "frankfurt_downloads": {"path": "/cash-en/trading/Tradable-Instruments-Xetra/boersefrankfurt",
                                "idempotent": True, "accept": "text", "timeout": 90.0},
        # {blob_path} substitutes a FULL https:// URL (extension 10) — the
        # blob hash versions on every upload, so the link is re-parsed from
        # the landing page on every fetch and never hard-coded
        "csv": {"path": "{blob_path}",
                "idempotent": True, "accept": "text", "timeout": 300.0},
        "newsboard_rss": {"path": "/cash-en/Stay-Informed/newsroom/Xetra-Frankfurt-Newsboard/4091644!rss",
                          "idempotent": True, "accept": "text", "timeout": 90.0},
        "newsboard_search": {"path": "/cash-en/Stay-Informed/newsroom/Xetra-Frankfurt-Newsboard/4091644!search",
                             "idempotent": True, "accept": "text", "timeout": 90.0},
    },
    "ttl": {"xetra_downloads": 3600, "frankfurt_downloads": 3600,
            "csv": 21600, "newsboard_rss": 1800, "newsboard_search": 3600},
}

VENUES = ("xetra", "frankfurt")
_BLOB_RE = re.compile(r"(/resource/blob/\d+/[0-9a-f]{32}/data/t7-[a-z\-]+"
                      r"-allTradableInstruments\.csv)")

_VENUE_PAGES = {
    # full-path patterns (the blob id + hash version on every upload — only
    # the filename stem is stable)
    "xetra": ("xetra_downloads",
              r"/resource/blob/\d+/[0-9a-f]{32}/data/t7-xetr-allTradableInstruments\.csv"),
    "frankfurt": ("frankfurt_downloads",
                  r"/resource/blob/\d+/[0-9a-f]{32}/data/t7-xfra-BF-allTradableInstruments\.csv"),
}


def _norm_venue(venue):
    v = str(venue or "xetra").strip().lower()
    if v not in VENUES:
        raise SdkError("usage_error", provider="de_xetra",
                       detail=f"--venue must be one of {'/'.join(VENUES)} (xetra = T7 master ~5.5k rows; "
                              f"frankfurt = the bond-heavy ~56k variant), got \"{venue}\"")
    return v


def _resolve_blob(venue, cache, no_cache):
    """the blob-hash law: the CSV link versions on every upload — re-parse it
    from the landing page each fetch (never cache the page longer than the
    link stays valid: page TTL 1h, CSV TTL 6h). Returns the FULL URL so the
    {blob_path} substitution rides extension 10 raw."""
    from ..transport import call_provider

    op, pat = _VENUE_PAGES[venue]
    r = call_provider(provider, op, {}, cache=cache, no_cache=no_cache)
    m = re.search(pat, r["data"])
    if not m:
        # fall back to any t7 blob on the page (the filename drifts)
        m2 = _BLOB_RE.search(r["data"])
        if not m2:
            raise SdkError("upstream_unavailable", provider="de_xetra",
                           detail=f"the {venue} downloads page no longer links a t7 allTradableInstruments CSV — "
                                  "the blob layout may have moved; re-probe")
        m = m2
    path = m.group(0)
    return provider["baseUrl"].rstrip("/") + path, r


def _parse_csv(text):
    """rows 1-2 metadata → {market, date_last_update}; row 3 header; row 4+
    data — every column verbatim (153 keys; no pruning)."""
    if not text or len(text) < 200:
        return None, None, None
    # the BOM rides some fetches (transport's text channel decodes plain utf-8,
    # so it arrives here as ﻿ — strip it or the meta keys miss)
    lines = text.lstrip("﻿").splitlines()
    meta = {}
    for ln in lines[:2]:
        if ":" in ln:
            k, _, v = ln.partition(":")
            v = v.lstrip(";").strip()
            if v:
                meta[k.strip()] = v  # keys arrive WITHOUT the colon: Market / Date Last Update
    body = "\n".join(lines[2:])
    rd = csv.reader(io.StringIO(body), delimiter=";")
    try:
        hdr = next(rd)
    except StopIteration:
        return meta.get("Market"), meta.get("Date Last Update"), None
    rows = []
    for rec in rd:
        if not rec or all(not c.strip() for c in rec):
            continue
        rows.append({h: (rec[i].strip() if i < len(rec) else "")
                     for i, h in enumerate(hdr) if h})
    return meta.get("Market"), meta.get("Date Last Update"), rows


def instruments(*, venue="xetra", instrument_type=None, pag=None, isin=None,
                limit=None, cache=None, no_cache=False):
    """→ {venue, market, date_last_update, row_count, rows[], params, _meta};
    the T7 tradable-instruments master (153 columns verbatim). venue=xetra
    ≈5.5k rows (ETF/CS/ETN/ETC); venue=frankfurt ≈56k bond-heavy — the CSV
    link re-resolves from the landing page every fetch (blob hashes version).
    instrument_type filters 'Instrument Type' locally (ETF/CS/ETN/ETC/…);
    pag filters 'Product Assignment Group' (AST0-style codes); isin is an
    exact match. Row counts drift daily — snapshot counts, never pinned."""
    from ..transport import call_provider

    v = _norm_venue(venue)
    blob_path, _page = _resolve_blob(v, cache, no_cache)  # _page's url rides _meta of the csv call
    r = call_provider(provider, "csv", {"blob_path": blob_path},
                      cache=cache, no_cache=no_cache)
    market, upd, rows = _parse_csv(r["data"])
    if rows is None:
        raise SdkError("upstream_unavailable", provider="de_xetra",
                       detail="the t7 CSV did not answer the 2-metadata-rows + header + data shape — "
                              "the blob layout may have moved; re-probe")
    it = str(instrument_type).strip().upper() if instrument_type else None
    if it:
        rows = [x for x in rows if x.get("Instrument Type", "").upper() == it]
    if pag:
        p = str(pag).strip().upper()
        rows = [x for x in rows if x.get("Product Assignment Group", "").upper() == p]
    if isin:
        rows = [x for x in rows if x.get("ISIN", "") == str(isin).strip().upper()]
    total = len(rows)
    if limit is not None and int(limit) >= 0:
        rows = rows[: int(limit)]
    return {"venue": v, "market": market, "date_last_update": upd,
            "row_count": total, "rows": rows,
            "params": {"venue": v, "instrument_type": it, "pag": pag, "isin": isin},
            "_meta": r}


def _rss_items(text):
    """the 100-item rolling window: title/link/description/pubDate verbatim;
    the venue prefix and event class live in the title (XETR: … IE000T8QD852)."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    out = []
    for it in root.iter("item"):
        d = {}
        for tag in ("title", "link", "description", "pubDate", "guid"):
            el = it.find(tag)
            if el is not None and el.text is not None:
                d[tag if tag != "pubDate" else "pub_date"] = el.text.strip()
        if d:
            out.append(d)
    return out


_TITLE_RE = re.compile(r"^(XETR|XFRA):\s*(.*)$")


def newsboard(*, venue=None, event_type=None, isin=None, limit=None,
              cache=None, no_cache=False):
    """→ {item_count, window_note, rows[], params, _meta}; the Newsboard RSS
    rolling window — the last 100 notices (~15h at probe cadence; hourly
    polling is the no-loss cadence, deeper history = newsboard_search).
    Titles carry venue prefix + event class + ISIN/mnemonic; venue/event_type
    filter on the title locally, isin matches anywhere in the title (both
    ISIN and mnemonic rides exist — Aussetzung/Suspension rows carry the
    ISIN, some legacy rows the mnemonic)."""
    from ..transport import call_provider

    r = call_provider(provider, "newsboard_rss", {}, cache=cache, no_cache=no_cache)
    items = _rss_items(r["data"])
    if items is None:
        raise SdkError("upstream_unavailable", provider="de_xetra",
                       detail="the Newsboard RSS did not parse as XML — the feed may have moved; re-probe")
    vx = str(venue).strip().upper() if venue else None
    if vx is not None and vx not in ("XETR", "XFRA"):
        raise SdkError("usage_error", provider="de_xetra",
                       detail=f"--venue must be XETR or XFRA (the title prefix), got \"{venue}\"")
    ev = str(event_type).strip().upper() if event_type else None
    rows = []
    for it in items:
        title = it.get("title", "")
        m = _TITLE_RE.match(title)
        item_venue = m.group(1) if m else None
        rest = m.group(2) if m else title
        if vx and item_venue != vx:
            continue
        if ev and ev not in rest.upper():
            continue
        if isin and str(isin).strip().upper() not in title.upper():
            continue
        rows.append({**it, "venue": item_venue, "event": rest})
    total = len(rows)
    if limit is not None and int(limit) >= 0:
        rows = rows[: int(limit)]
    return {"item_count": total,
            "window_note": "rolling window of the latest 100 notices (~15h); "
                           "hourly polling is the no-loss cadence — full history via newsboard_search",
            "rows": rows,
            "params": {"venue": vx, "event_type": ev, "isin": isin},
            "_meta": r}


# the live row shape (parsed 2026-11-20): each hit is an anchor-wrapped
# container — <a class="teasable-search-result-link" href="/cash-en/…/XFRA-BVU-
# Aussetzung-Suspension-5742724"> … <p class="search-result-date">Nov 11, 2026
# 10:05:02 AM CET</p> <h2 class="search-result-tagline">Börse Frankfurt</h2>
# <h1 class="search-result-description ">XFRA: …: Aussetzung/Suspension</h1> …</a>
_SEARCH_ROW_RE = re.compile(
    r'<a[^>]*teasable-search-result-link[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
_SEARCH_DATE_RE = re.compile(r'class="search-result-date"[^>]*>([^<]+)<')
_SEARCH_DESC_RE = re.compile(r'class="search-result-description[^"]*"[^>]*>(.*?)</h[1-6]>',
                             re.DOTALL)
_SEARCH_TAGLINE_RE = re.compile(r'class="search-result-tagline"[^>]*>(.*?)</h[1-6]>',
                                re.DOTALL)


def _strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def newsboard_search(*, query, page=1, limit=None, cache=None, no_cache=False):
    """→ {query, page, row_count, rows[], params, _meta}; the Newsboard
    full-history search (delisting notices back to the 2020 number block ride
    ISINs in the path — query by ISIN, by 'Aussetzung', 'Wiederaufnahme',
    'delisting'…). pageNum rides statelessly (page 1 answers without the
    gzip+base64 state token the page emits); 100 hits/page. Rows carry the
    notice href (the ISIN rides the path), the timestamp, the venue tagline
    and the description verbatim."""
    from ..transport import call_provider

    q = str(query or "").strip()
    if not q:
        raise SdkError("usage_error", provider="de_xetra",
                       detail="--query is required (an ISIN, an event word like Aussetzung/Suspension, delisting…)")
    pg = max(1, int(page or 1))
    r = call_provider(provider, "newsboard_search",
                      {"query": q, "pageNum": pg, "hitsPerPage": 100},
                      cache=cache, no_cache=no_cache)
    text = r["data"] or ""
    rows = []
    for m in _SEARCH_ROW_RE.finditer(text):
        href, body = m.group(1).strip(), m.group(2)
        dm = _SEARCH_DESC_RE.search(body)
        desc = _strip_tags(dm.group(1)) if dm else _strip_tags(body)
        tm = _SEARCH_TAGLINE_RE.search(body)
        dmatch = _SEARCH_DATE_RE.search(body)
        rows.append({
            "href": href,
            "date": _strip_tags(dmatch.group(1)) if dmatch else None,
            "tagline": _strip_tags(tm.group(1)) if tm else None,
            "text": desc,
        })
    total = len(rows)
    if limit is not None and int(limit) >= 0:
        rows = rows[: int(limit)]
    return {"query": q, "page": pg, "row_count": total, "rows": rows,
            "params": {"query": q, "pageNum": pg, "hitsPerPage": 100},
            "_meta": r}
