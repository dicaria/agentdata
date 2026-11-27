"""us_cftc — CFTC enforcement register (www.cftc.gov Drupal views; keyless).

legal enforcement faces (0.3.51 actions; 0.3.64 redlist+dispositions — batch E6; 0.3.65
opinions — batch E7; admitted from research booklet 286 us-cftc-enforcement, actions probed live
2026-11-09 tmp/probe-sdk0350/l5/, redlist+dispositions probed live 2026-11-16 tmp/probe-e6/,
opinions probed live 2026-11-17 tmp/probe-e7/). Four views surfaces:

actions — the commission's full enforcement history: 1995→2026, ~10 rows per page,
?page=0..260 (page 260 ends at 1995-07-27, MG Refining and Marketing $2.25M — the register's
own floor), ≈2,610 actions total. Optional ?year=YYYY filter (2023 live-verified: 10/page,
releases 8845-23…8809-23). Two walk-aways from the recipe: the solr-search endpoint sits behind
Cloudflare (don't), and publicreporting.cftc.gov / data.cftc.gov are dead exits (domain resold /
egress reset) — the views table is the one live surface. Header gate drift: the research probe
passed bare-UA, but 2026-11-09 a bare UA got 403'd while the full browser suite passed (ext-8,
same family as ferc elibrary) — the face ships the suite, not the bare UA.

redlist — the Registration Deficiency List (unregistered foreign entities the CFTC has charged
or settled with; complementary to OFAC CSL — a non-sanctions, unregistered-forex-derivatives
negative register). 0.3.64 probed: 29 pages ?page=0..28 ×10/page, last page 4 rows → 284
entities live; the register's own order is ALPHABETICAL by company (page 0 "1Billion Forex"
→ "Abnas Global Securities", page 28 "WinOptions"→"YesOption") — Date Entered is scattered, not
sorted (2015-08…2023-06 on page 0). Columns: Date Entered | Company; each row anchors a Drupal
node (/REDlist/node/220626 → "RED List: 1Billion Forex", live 200/38KB). ?items_per_page=100
answers a table with ZERO rows (the views exposed setting is decorative — never widened; page
size stays the upstream 10).

dispositions — the reparations-decision register (complainant v. registrant, e.g. "David
Kaminski v. TradeStation Securities, Inc."), 0.3.64 probed: 46 pages ?page=0..45 ×10/page ≈456
rows, newest-first (2026-10-26 top). Each row: <time> + blurb cell whose anchor IS the decision
PDF (/sites/default/files/YYYY/MM/<name>.pdf) + "CFTC Docket No. <id>" after a <br/>.

opinions — the OGC Opinions & Adjudicatory Orders register (reparations appeals and initial
decisions, parties-first captions "Eric Thompson, … v. …"), 0.3.65 probed: 9 pages ?page=0..8
×10/page, last page 7 rows → ≈87 rows, date-descending 2012→2025. DUAL-ERA PDF PATHS: recent
rows anchor /sites/default/files/YYYY/MM/<name>.pdf while older rows anchor the legacy
/idc/groups/public/%40lropinionsandadjudicaryorders/documents/legalpleading/<name>.pdf path —
both verbatim (%40 is the encoded @; "adjudicary" is the upstream's own misspelling, kept as-is).
Docket rides INLINE in the blurb text ("CFTC Docket No. 23-R001" — unlike dispositions' <br/>
placement), and multi-docket rows caption the PLURAL "CFTC Docket Nos. 20-R007; 20-R008; …;
and 20-R025" — the whole semicolon list is captured as one docket_no string (the singular
regex alone would grab the stray "s" of "Nos"). Legacy-era tolerance: older rows DROP the
"CFTC " prefix ("Docket No. 10-R015"), dockets are not always R-numbered ("11-E-01"), and
NFA-arbitration rows carry a space-separated pair ("Docket No. CRAA 12-03") — the
opinions-only singular regex tolerates all three (dispositions' shared regex stays
CFTC-anchored); the two 2012 rows with no docket caption at all report None honestly.

Rows are the server-rendered views rows: <time datetime="ISO">MM/DD/YYYY</time> + the anchor
(+ zero or more related-document links on actions — https://www.cftc.gov/media/.../download
with their labels — Final Judgment / Consent Order / Complaint …, up to 6 in one row live).
Titles carry HTML entities (&amp;) and trailing whitespace — unescaped and whitespace-normalized
locally.
Year walls are the register's own dropdown: 1995→current, and 1998 is NOT offered (historical
broken year, absent from the filter — recorded as-is, per recipe). ?page is 0-based upstream
verbatim (no local wall beyond >=0; past-the-end answers an empty table, reported honestly).
Politeness 0.5/2, TTL: actions 12h (updates with each press release) / dispositions 24h /
redlist 7d (a slow-moving negative register).
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
        "redlist": {"path": "/LearnAndProtect/Resources/Check/redlist.htm",
                    "accept": "text", "timeout": 60.0},
        "dispositions": {"path": "/LawRegulation/Dispositions/index.htm",
                         "accept": "text", "timeout": 60.0},
        "opinions": {"path": "/LawRegulation/OpinionsAdjudicatoryOrders/index.htm",
                     "accept": "text", "timeout": 60.0},
    },
    "ttl": {"actions": 12 * 3600, "redlist": 7 * 86400, "dispositions": 24 * 3600,
            "opinions": 24 * 3600},
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
_REDNODE_RE = re.compile(r'<a href="(/REDlist/node/\d+)"[^>]*>(.*?)</a>', re.S)
_DISPDF_RE = re.compile(r'<a href="(/sites/default/files/[^"]+\.pdf)"[^>]*>(.*?)</a>', re.S)
# opinions anchors span TWO eras: recent /sites/default/files/YYYY/MM/ and legacy
# /idc/groups/public/%40lr…/documents/legalpleading/ (%40=@, "adjudicary" upstream verbatim)
_OPPDF_RE = re.compile(
    r'<a href="((?:/sites/default/files/|/idc/groups/public/)[^"]+\.pdf)"[^>]*>(.*?)</a>', re.S)
_DOCKET_RE = re.compile(r"CFTC Docket No\.?\s*([A-Za-z0-9\-]+)")
# opinions-only PLURAL law: multi-docket rows caption "CFTC Docket Nos. 20-R007; 20-R008;
# … ; and 20-R025" — the singular regex above would capture the stray "s" of "Nos" —
# test plural FIRST and capture the whole semicolon list as one string.
_DOCKETS_RE = re.compile(
    r"(?:CFTC\s+)?Docket Nos\.?\s*((?:\d+-R\d+)(?:\s*[,;]\s*(?:and\s+)?\d+-R\d+)*)")
# opinions-only SINGULAR tolerance (dispositions' shared _DOCKET_RE stays CFTC-anchored —
# its <br/> placement is uniformly prefixed): legacy-era rows DROP the "CFTC " prefix
# ("… Sendlosky, Docket No. 10-R015"), dockets are not always R-numbered ("11-E-01"),
# and NFA-arbitration rows carry a space-separated pair ("Docket No. CRAA 12-03") —
# hence the optional prefix and the bounded second token (never more: the docket ends
# the caption's text run in both observed layouts).
_OPDOCKET_RE = re.compile(
    r"(?:CFTC\s+)?Docket No\.?\s*([A-Za-z0-9\-]+(?:\s+[A-Za-z0-9\-]+)?)")


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


def redlist_raw(*, page=0, cache=None, no_cache=False):
    """→ {page, count, rows[], params, _meta} — the RED List (registration-deficiency
    register): unregistered foreign entities the CFTC has charged or settled with.

    The register's own order is ALPHABETICAL by company name (not date — Date Entered
    scatters 2015→2023 within a page); 29 pages live (0..28) ×10, last page 4 rows →
    284 entities. rows carry datetime (ISO Z), date (MM/DD/YYYY verbatim), name, and
    node_path (/REDlist/node/<id> — the entity's detail page, title "RED List: <name>").
    Past-the-end pages answer an empty table, reported honestly."""
    from ..errors import SdkError
    from ..transport import call_provider

    p = int(page) if page is not None else 0
    if p < 0:
        raise SdkError("usage_error", provider="us_cftc",
                       detail=f"page is 0-based upstream (0..28 live), got {page!r}")
    params = {"page": str(p)}

    r = call_provider(provider, "redlist", params, cache=cache, no_cache=no_cache,
                      extra_headers=_BROWSER_HEADERS)
    body = r["data"] or ""
    if not isinstance(body, str) or "<html" not in body[:400].lower():
        raise SdkError("upstream_unavailable", provider="us_cftc",
                       detail="the RED list answered non-HTML (shape drift, gate, or maintenance)")

    rows = []
    for rm in _ROW_RE.finditer(body):
        block = rm.group(1)
        t = _TIME_RE.search(block)
        a = _REDNODE_RE.search(block)
        if not (t and a):
            continue  # header row and view chrome
        rows.append({
            "datetime": t.group(1),
            "date": t.group(2),
            "name": _clean(a.group(2)),
            "node_path": a.group(1),
        })

    return {"page": p, "count": len(rows), "rows": rows, "params": params, "_meta": r}


def dispositions_raw(*, page=0, cache=None, no_cache=False):
    """→ {page, count, rows[], params, _meta} — the reparations-decisions register
    (complainant v. registrant captions, "David Kaminski v. TradeStation Securities, Inc.").

    46 pages live (0..45) ×10/page ≈456 rows, newest-first. rows carry datetime (ISO Z),
    date (MM/DD/YYYY verbatim), title (the case caption, entity-unescaped), pdf_path
    (site-relative decision PDF under /sites/default/files/YYYY/MM/ — prefix
    https://www.cftc.gov), and docket_no (e.g. 25-R016). Past-the-end pages answer an
    empty table, reported honestly."""
    from ..errors import SdkError
    from ..transport import call_provider

    p = int(page) if page is not None else 0
    if p < 0:
        raise SdkError("usage_error", provider="us_cftc",
                       detail=f"page is 0-based upstream (0..45 live), got {page!r}")
    params = {"page": str(p)}

    r = call_provider(provider, "dispositions", params, cache=cache, no_cache=no_cache,
                      extra_headers=_BROWSER_HEADERS)
    body = r["data"] or ""
    if not isinstance(body, str) or "<html" not in body[:400].lower():
        raise SdkError("upstream_unavailable", provider="us_cftc",
                       detail="the dispositions register answered non-HTML "
                              "(shape drift, gate, or maintenance)")

    rows = []
    for rm in _ROW_RE.finditer(body):
        block = rm.group(1)
        t = _TIME_RE.search(block)
        a = _DISPDF_RE.search(block)
        if not (t and a):
            continue  # header row and view chrome
        dk = _DOCKET_RE.search(_clean(block))
        rows.append({
            "datetime": t.group(1),
            "date": t.group(2),
            "title": _clean(a.group(2)),
            "pdf_path": a.group(1),
            "docket_no": dk.group(1) if dk else None,
        })

    return {"page": p, "count": len(rows), "rows": rows, "params": params, "_meta": r}


def opinions_raw(*, page=0, cache=None, no_cache=False):
    """→ {page, count, rows[], params, _meta} — the OGC Opinions & Adjudicatory Orders
    register (reparations appeals and initial decisions; parties-first captions,
    "Eric Thompson, Jonathan Morse, … v. …").

    9 pages live (0..8) ×10/page, last page 7 rows → ≈87 rows, date-descending
    2012→2025. DUAL-ERA PDF PATHS verbatim: recent rows /sites/default/files/YYYY/MM/,
    older rows the legacy /idc/groups/public/%40lropinionsandadjudicaryorders/
    documents/legalpleading/ path (%40=@, "adjudicary" is the upstream's own
    misspelling — never normalized). Docket rides INLINE in the blurb text
    ("CFTC Docket No. 23-R001"; legacy rows drop the CFTC prefix, NFA pairs ride
    "CRAA 12-03"); the two 2012 rows with none report None honestly.
    Past-the-end pages answer an empty table, reported honestly."""
    from ..errors import SdkError
    from ..transport import call_provider

    p = int(page) if page is not None else 0
    if p < 0:
        raise SdkError("usage_error", provider="us_cftc",
                       detail=f"page is 0-based upstream (0..8 live), got {page!r}")
    params = {"page": str(p)}

    r = call_provider(provider, "opinions", params, cache=cache, no_cache=no_cache,
                      extra_headers=_BROWSER_HEADERS)
    body = r["data"] or ""
    if not isinstance(body, str) or "<html" not in body[:400].lower():
        raise SdkError("upstream_unavailable", provider="us_cftc",
                       detail="the opinions register answered non-HTML "
                              "(shape drift, gate, or maintenance)")

    rows = []
    for rm in _ROW_RE.finditer(body):
        block = rm.group(1)
        t = _TIME_RE.search(block)
        a = _OPPDF_RE.search(block)
        if not (t and a):
            continue  # header row and view chrome
        text = _clean(block)
        dks = _DOCKETS_RE.search(text)          # plural list FIRST (see _DOCKETS_RE note)
        dk = dks or _OPDOCKET_RE.search(text)   # opinions-tolerant singular (see its note)
        rows.append({
            "datetime": t.group(1),
            "date": t.group(2),
            "title": _clean(a.group(2)),
            "pdf_path": a.group(1),
            "docket_no": dk.group(1) if dk else None,
        })

    return {"page": p, "count": len(rows), "rows": rows, "params": params, "_meta": r}
