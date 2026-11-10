"""us_cftc — CFTC enforcement-actions index (www.cftc.gov Drupal views; keyless).

legal enforcement face (0.3.51; admitted from research 册 286 us-cftc-enforcement, probed live
2026-11-09, tmp/probe-sdk0350/l5/ p04+p08). The Drupal views table is the commission's full
enforcement history: 1995→2026, ~10 rows per page, ?page=0..260 (page 260 ends at 1995-07-27,
MG Refining and Marketing $2.25M — the register's own floor), ≈2,610 actions total. Optional
?year=YYYY filter (2023 live-verified: 10/page, releases 8845-23…8809-23). Two walk-aways from
the recipe: the solr-search endpoint sits behind Cloudflare (don't), and publicreporting.cftc.gov
/data.cftc.gov are dead exits (domain resold / egress reset) — the views table is the one live
surface. Header gate drift: the research probe passed bare-UA, but 2026-11-09 a bare UA got 403'd
while the full browser suite passed (ext-8, same family as ferc elibrary) — the face ships the
suite, not the bare UA.

Rows are the server-rendered views rows: <time datetime="ISO">MM/DD/YYYY</time> + the press-release
anchor (/PressRoom/PressReleases/<release>-<yy>, the release_number is the anchor tail) + zero or
more related-document links (https://www.cftc.gov/media/.../download with their labels — Final
Judgment / Consent Order / Complaint …, up to 6 in one row live). Titles carry HTML entities
(&amp;) and trailing whitespace — unescaped and whitespace-normalized locally.
Year walls are the register's own dropdown: 1995→current, and 1998 is NOT offered (historical
broken year, absent from the filter — recorded as-is, per recipe). ?page is 0-based upstream
verbatim (no local wall beyond >=0; past-the-end answers an empty table, reported honestly).
Politeness 0.5/2, TTL 12h (the index updates with each press release).
"""
import html
import re

provider = {
    "id": "us_cftc",
    "baseUrl": "https://www.cftc.gov",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "actions": {"path": "/LawRegulation/EnforcementActions/index.htm",
                    "accept": "text", "timeout": 60.0},
    },
    "ttl": {"actions": 12 * 3600},
}

# Bare/polite UA 403'd live 2026-11-09 (p08 first attempt) — full browser suite passes (ext-8).
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

YEAR_FLOOR = 1995
YEAR_ABSENT = frozenset({1998})  # the register's own dropdown skips 1998 (historical broken year)

_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
_TIME_RE = re.compile(r'<time datetime="([^"]+)">([^<]+)</time>')
_REL_RE = re.compile(r'<a href="(/PressRoom/PressReleases/[^"]+)"[^>]*>(.*?)</a>', re.S)
_DOC_RE = re.compile(r'<a href="(https://www\.cftc\.gov/media/[^"]+)"[^>]*>(.*?)</a>', re.S)


def _clean(s):
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def actions_raw(year=None, *, page=0, cache=None, no_cache=False):
    """→ {page, year, count, rows[], params, _meta} (rows oldest-first on the deepest pages —
    the register's own order: newest first at page 0, 1995 at the tail of page 260).

    rows carry datetime (ISO 8601 Z), date (MM/DD/YYYY verbatim), release_path (site-relative —
    prefix https://www.cftc.gov), release_number (anchor tail, e.g. "9320-26"), title, and
    related_docs [{url, label}] (the order/complaint attachments under /media/).
    """
    import datetime
    from ..errors import SdkError
    from ..transport import call_provider

    params = {}
    yr = None
    if year is not None and str(year).strip():
        try:
            yr = int(str(year).strip())
        except ValueError:
            raise SdkError("usage_error", provider="us_cftc",
                           detail=f"year must be an integer, got {year!r}")
        if yr < YEAR_FLOOR or yr > datetime.date.today().year:
            raise SdkError("usage_error", provider="us_cftc",
                           detail=f"year must be {YEAR_FLOOR}→{datetime.date.today().year} "
                                  f"(the register's own dropdown span), got {yr}")
        if yr in YEAR_ABSENT:
            raise SdkError("usage_error", provider="us_cftc",
                           detail=f"year {yr} is not offered by the register's own filter "
                                  f"(historical broken year, absent from the dropdown)")
        params["year"] = str(yr)
    p = int(page) if page is not None else 0
    if p < 0:
        raise SdkError("usage_error", provider="us_cftc",
                       detail=f"page is 0-based upstream (0..260 live), got {page!r}")
    params["page"] = str(p)

    r = call_provider(provider, "actions", params, cache=cache, no_cache=no_cache,
                      extra_headers=_BROWSER_HEADERS)
    body = r["data"] or ""
    if not isinstance(body, str) or "<html" not in body[:400].lower():
        raise SdkError("upstream_unavailable", provider="us_cftc",
                       detail="the enforcement-actions index answered non-HTML "
                              "(shape drift, gate, or maintenance)")

    rows = []
    for rm in _ROW_RE.finditer(body):
        block = rm.group(1)
        t = _TIME_RE.search(block)
        a = _REL_RE.search(block)
        if not (t and a):
            continue  # header row and view chrome
        href = a.group(1)
        docs = [{"url": u, "label": _clean(lb)} for u, lb in _DOC_RE.findall(block)]
        rows.append({
            "datetime": t.group(1),
            "date": t.group(2),
            "release_path": href,
            "release_number": href.rsplit("/", 1)[-1],
            "title": _clean(a.group(2)),
            "related_docs": docs,
        })

    return {"page": p, "year": yr, "count": len(rows), "rows": rows,
            "params": params, "_meta": r}
