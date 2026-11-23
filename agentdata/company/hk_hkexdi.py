"""hk_hkexdi — HKEX Disclosure of Interests (DI, SFO Part XV) keyless faces
(di.hkex.com.hk, 0.3.71 batch E13 — the HK jurisdiction deepening under the
user's HKEX ruling; the harvest-side recipe 册 676 probed the same host
2026-11-16, re-measured for the SDK 2026-11-19, tmp/probe-e13/).

2026-11-19 probed laws:
  - THE BOOTSTRAP IS A POST, AND THE SESSION IS THE KEY. NSSrchCorp.aspx (form
    GET) issues ASP.NET_SessionId (+ BIGip/TS/bm_* edge cookies) and carries
    __VIEWSTATE/__VIEWSTATEGENERATOR/__EVENTVALIDATION. The search POST
    302-redirects to NSSrchCorpList.aspx?sa1=cl&… which RESOLVES the stock to
    the corporation card and emits the seven list links. Without the session
    cookie the list endpoints answer 302; WITH it they answer rows. The
    {viewstate, eventvalidation, generator, cookie} quartet caches TOGETHER
    (the jp_jftc session-bound token law generalized), TTL 30min, and the
    face re-bootstraps once on a dead session.
  - THE SEVEN PER-CORP LISTS are standalone endpoints with their own query
    contract — NOT NSSrchCorpList sa2 params (the recipe's compressed reading;
    the real links read NSNoticeSSList.aspx?sa2=ns&sid={internal corp
    id}&corpn=…&sd=…&ed=…&cid=0&…&pg=N). Codes: as/NSAllSSList (complete SS
    list) · cs/NSConstdSSList (consolidated) · ns/NSNoticeSSList (notices,
    50/page) · ad/NSAllDirList (complete director list) · nd/NSNotice3AList
    (director notices) · an/NSAllFormList (all notices). sid/corpn/sd/ed/cid
    are parsed off the resolution links verbatim — the face never invents sid.
  - C5 IS PURE GET, NO SESSION: NSC5Sum.aspx?pg=N — the market-wide
    "Results of investigations" daily release stream (53 rows/page probe day,
    Total records 281), each row's serial linking NSForm4.aspx?fn=IR….
  - FORM DETAILS ARE PURE GET TOO (fn= hard key, no session): NSForm2 for
    CS/DA serials, NSForm4 for IR. The CS form's table count is per-form
    (12/13/17 across three live CS probes) —
    the Long/Short/LendingPool three-state block, capacity/derivatives code
    legends (2201 = interest of corporation controlled by you; 16021 = §5(4)
    lending agent), the CONTROLLED-CORPORATION CHAIN (name/address/controlling
    person/%control/direct Y/N/shares — the official equity-penetration
    graph), and joint/trust/other/relationship schedules. The face returns
    every table verbatim (header row split when the first row reads as one)
    plus the recognized sections picked out by header signature.
  - THE DATE AXIS IS A CAPTCHA WALL AND STAYS CLOSED: NSSrchDate (the
    market-wide sweep by date) is reCaptcha — the corp/person axes carry the
    same data keyless, so there is nothing behind the wall worth forcing.
  - DION BOUNDARY: the online system only holds notices filed through DION
    since 3 July 2017 (the page states it; earlier date parameters are
    silently clamped — the face refuses them instead, usage_error at the
    floor). Serial key space: {CS|DA|IR}{yyyymmdd}E{seq}.
  - SDW (CCASS participant level) is OUT OF SCOPE BY TERMS (2.3 forbids
    programmatic access — the harvest-side verdict stands); this provider
    only touches the corp/notice/form surfaces.

Politeness 1 rps, concurrency 1 (Radware-edged ASP.NET host; monitors but
does not gate curl — probes all 200). TTLs: session 30min / C5 1h / lists
30min (session-bound links) / forms 24h.
"""
import re
from datetime import date, timedelta
from urllib.parse import parse_qs, urlencode, urlsplit

import html as _html

from ..errors import SdkError

provider = {
    "id": "hk_hkexdi",
    "baseUrl": "https://di.hkex.com.hk",
    "rate": {"rps": 1.0, "burst": 1},
    "concurrency": 1,
    "ops": {
        "c5": {"path": "/di/NSC5Sum.aspx", "idempotent": True, "accept": "text",
               "timeout": 45.0},
        "form2": {"path": "/di/NSForm2.aspx", "idempotent": True, "accept": "text",
                  "timeout": 45.0},
        "form4": {"path": "/di/NSForm4.aspx", "idempotent": True, "accept": "text",
                  "timeout": 45.0},
        # the bootstrap form GET — called with cache=None (session quartet caches
        # TOGETHER at the module level, never the bare page)
        "corpform": {"path": "/di/NSSrchCorp.aspx", "idempotent": True, "accept": "text",
                     "timeout": 45.0},
        # the search POST — urlencoded ASP.NET fields; src/lang/g_lang ride the
        # QUERY (baked in the path template) so the 302 Location carries them,
        # exactly as the browser posts them
        "corppost": {"path": "/di/NSSrchCorp.aspx?src={src}&lang={lang}&g_lang={g_lang}",
                     "method": "POST", "urlencoded": True, "idempotent": True,
                     "accept": "text", "timeout": 45.0},
        # the seven per-corp lists — {which} is the endpoint name parsed off the
        # resolution links (as/cs/ns/ad/nd/an → NSAllSSList/…), never client-invented
        "corplist": {"path": "/di/{which}.aspx", "idempotent": True, "accept": "text",
                     "timeout": 45.0},
    },
    "ttl": {"c5": 3600, "form2": 86400, "form4": 86400, "corplist": 1800},
}
_SESSION_TTL = 30 * 60

_FORM_URL = "https://di.hkex.com.hk/di/NSSrchCorp.aspx?src=MAIN&lang=EN&g_lang=en"
_DION_FLOOR = (2017, 7, 3)          # DION-only since 3 July 2017 (page-stated)
_SERIAL_RE = re.compile(r"^(CS|DA|IR)\d{8}E\d{4,}$")
_LISTS = {"as": "NSAllSSList", "cs": "NSConstdSSList", "ns": "NSNoticeSSList",
          "ad": "NSAllDirList", "nd": "NSNotice3AList", "an": "NSAllFormList"}
_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_TC = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_FN_RE = re.compile(r"NSForm[24]\.aspx\?fn=([A-Za-z0-9]+)")
_LINK_RE = re.compile(r'<a[^>]*href="((?:NS(?:AllSS|ConstdSS|NoticeSS|AllDir|Notice3A|AllForm)List)\.aspx\?[^"]*)"[^>]*>(.*?)</a>', re.S)
_TITLE_RE = re.compile(r'pageDefaultTitle\s*=\s*"([^"]*)"')


def _cell(raw):
    """One <td> → readable text (tags dropped, entities unescaped, whitespace collapsed)."""
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def _table_rows(fragment):
    """→ [[cell, …]] for one <table> fragment; empty/&nbsp;-only rows dropped."""
    rows = []
    for rm in _TR.finditer(fragment):
        cells = [_cell(c) for c in _TC.findall(rm.group(1))]
        if any(c for c in cells):
            rows.append(cells)
    return rows


# ---------------------------------------------------------------- session

def _session(cache, no_cache):
    """→ {viewstate, eventvalidation, generator, cookie} — the ASP.NET anti-
    forgery quartet and its session cookie cached TOGETHER (the jp_jftc
    session-bound law: caching the page alone hands out dead states). Direct
    cache-API entry: call_provider only caches response bodies, never the
    set-cookie pair that goes with them."""
    from ..transport import cache_key_for, call_provider

    key = cache_key_for("session", {}, scope=provider["baseUrl"])
    if not no_cache and cache is not None:
        hit = cache.get(provider["id"], key, _SESSION_TTL)
        if hit and isinstance(hit["payload"], dict) and hit["payload"].get("cookie"):
            return hit["payload"]
    r = call_provider(provider, "corpform", {"src": "MAIN", "lang": "EN", "g_lang": "en"},
                      cache=None, no_cache=True)
    t = r["data"]
    quad = {}
    for field, name in (("viewstate", "__VIEWSTATE"),
                        ("eventvalidation", "__EVENTVALIDATION"),
                        ("generator", "__VIEWSTATEGENERATOR")):
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % name, t)
        if not m:
            raise SdkError("upstream_unavailable", provider="hk_hkexdi",
                           detail=f"the DI search form answered without {name} — "
                                  "the portal may have moved; re-probe")
        quad[field] = m.group(1)
    quad["cookie"] = "; ".join((c.split(";")[0] or "").strip()
                               for c in (r.get("set_cookie") or []))
    if not quad["cookie"]:
        raise SdkError("upstream_unavailable", provider="hk_hkexdi",
                       detail="the DI form issued no session cookie — the list "
                              "endpoints need it; re-probe")
    if not no_cache and cache is not None:
        cache.set(provider["id"], key, quad, _SESSION_TTL)
    return quad


def _post_headers(sess):
    h = {"Cookie": sess["cookie"], "Referer": _FORM_URL,
         "Origin": "https://di.hkex.com.hk",
         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    return h


# ---------------------------------------------------------------- parsing

def _resolve_links(resolution_html):
    """The resolution page's seven list links → [{sa2, which, params(dict)}].
    corpn is unescaped; sd/ed/sid/cid ride verbatim from the upstream href."""
    out = []
    seen = set()
    for m in _LINK_RE.finditer(resolution_html):
        href = _html.unescape(m.group(1))
        label = _cell(m.group(2))
        which = href.split(".aspx", 1)[0].rsplit("/", 1)[-1]
        qs = {k: v[0] for k, v in parse_qs(urlsplit("?" + href.split("?", 1)[1]).query,
                                           keep_blank_values=True).items()}
        sa2 = qs.get("sa2")
        if sa2 and sa2 not in seen:
            seen.add(sa2)
            out.append({"sa2": sa2, "which": which, "label": label, "params": qs})
    return out


def _resolve_corp(resolution_html):
    """→ (stock_code, corp_name) off the resolution page's echoed search header."""
    m = re.search(r"Stock code:\s*</[^>]+>\s*(?:<[^>]*>\s*)*([0-9]{4,6})", resolution_html)
    code = m.group(1) if m else None
    n = re.search(r"Name of listed corporation:\s*</[^>]+>\s*(?:<[^>]*>\s*)*([^<]+?)\s*<",
                  resolution_html)
    name = _cell(n.group(1)) if n else None
    return code, name


def _dict_rows(rows, header):
    """[[cell…]] → [dict] keyed by the verbatim header row (+ form_fn/form_url
    when a cell carried an NSForm link — parsed from the RAW row html, so this
    needs the raw fragments; kept simple: _FN_RE rides the joined raw row)."""
    out = []
    for cells in rows:
        row = {}
        for i, key in enumerate(header):
            if i < len(cells):
                row[key] = cells[i]
        out.append(row)
    return out


def _fn_from_raw(raw_row_html):
    m = _FN_RE.search(raw_row_html)
    return m.group(1) if m else None


# ---------------------------------------------------------------- faces

def ir_summaries(*, pg=1, stock_code=None, cache=None, no_cache=False):
    """→ {page, total, rows[], params, _meta}; the C5 market-wide "Results of
    investigations" daily release stream (NSC5Sum.aspx — pure GET, no
    session). 53 rows/page probe day, Total records 281; each row's serial is
    a hard NSForm4 fn= key feeding hk_hkexdi_form. --stock-code filters
    client-side; --pg pages (1-based)."""
    from ..transport import call_provider

    page = max(1, int(pg or 1))
    r = call_provider(provider, "c5", {"pg": page, "src": "MAIN", "lang": "EN",
                                       "g_lang": "en"},
                      cache=cache, no_cache=no_cache)
    t = r["data"]
    total = None
    tm = re.search(r"Total records?:?\s*(?:<[^>]*>\s*)*([0-9,]+)", t)
    if tm:
        total = int(tm.group(1).replace(",", ""))
    tables = re.findall(r"<table.*?</table>", t, re.S)
    rows = []
    for tb in tables:
        raws = _TR.findall(tb)
        for raw in raws:
            cells = [_cell(c) for c in _TC.findall(raw)]
            if not any(cells) or cells[0].startswith("//"):
                continue
            if cells[0] == "Form Serial Number":   # the header row
                continue
            if not _SERIAL_RE.match(cells[0] or ""):
                continue   # the page's date-banner caption rides the table — not a data row
            fn = _fn_from_raw(raw)
            rows.append({
                "form_fn": fn,
                "form_url": (f"https://di.hkex.com.hk/di/NSForm4.aspx?fn={fn}"
                             f"&src=MAIN&lang=EN&g_lang=en") if fn else None,
                "serial": cells[0] if cells else None,
                "release_date": cells[1] if len(cells) > 1 else None,
                "specified_date": cells[2] if len(cells) > 2 else None,
                "stock_code": cells[3] if len(cells) > 3 else None,
                "report_name": cells[4] if len(cells) > 4 else None,
            })
    q_code = re.sub(r"\D", "", str(stock_code)).lstrip("0") if stock_code else None
    if q_code:
        rows = [x for x in rows
                if x["stock_code"]
                and re.sub(r"\D", "", x["stock_code"]).lstrip("0") == q_code]
    return {"page": page, "total": total, "rows": rows,
            "params": {"pg": page, "stock_code": stock_code}, "_meta": r}


def form(*, fn, cache=None, no_cache=False):
    """→ {fn, form_kind, form_title, positions, controlled_corporations,
    tables[], params, _meta}; one DI form's full detail (fn= hard key, pure
    GET, no session). IR serials ride NSForm4, CS/DA ride NSForm2 (routed by
    prefix, never guessed). tables carries EVERY table verbatim (header row
    split off when the first row reads as a header); positions picks the
    Long/Short/LendingPool three-state block by its header signature;
    controlled_corporations picks the controlled-company chain (the official
    equity-penetration graph)."""
    from ..transport import call_provider

    key = str(fn or "").strip().upper()
    if not _SERIAL_RE.match(key):
        raise SdkError("usage_error", provider="hk_hkexdi",
                       detail=f"fn must be a DI serial {key!r} shaped "
                              "CS{yyyymmdd}E{seq} / DA… / IR… (got \"" + str(fn) + "\")")
    op = "form4" if key.startswith("IR") else "form2"
    r = call_provider(provider, op, {"fn": key, "src": "MAIN", "lang": "EN",
                                     "g_lang": "en"},
                      cache=cache, no_cache=no_cache)
    t = r["data"]
    tm = _TITLE_RE.search(t)
    form_title = _cell(tm.group(1)) if tm else None
    kind = key[:2]
    tables = []
    positions = None
    controlled = []
    for i, tb in enumerate(re.findall(r"<table.*?</table>", t, re.S)):
        rows = _table_rows(tb)
        if not rows:
            continue
        header = None
        body = rows
        flat0 = " ".join(rows[0])
        head = [c for c in rows[0] if c]
        if "Total number of shares" in flat0:
            # the three-state block's real header — even though its first DATA row
            # reads Long/Short/Lending (the generic rule would refuse to split it)
            header = rows[0]
            body = rows[1:]
        elif len(rows) > 1 and len(head) >= 2 \
                and not re.match(r"^(?:Long|Short|Lending)", rows[1][0] or ""):
            header = rows[0]
            body = rows[1:]
        entry = {"index": i, "header": header, "rows": body}
        tables.append(entry)
        flat_head = " ".join(header or [])
        if "Total number of shares" in flat_head and header:
            positions = {}
            for cells in body:
                if cells and cells[0] in ("Long position", "Short position", "Lending Pool"):
                    positions[cells[0]] = {
                        "total_number_of_shares": cells[1] if len(cells) > 1 else None,
                        "percentage_figure": cells[2] if len(cells) > 2 else None,
                    }
        if header and header[0].startswith("Name of controlled corporati"):
            controlled = _dict_rows(body, header)
    return {"fn": key, "form_kind": kind, "form_title": form_title,
            "positions": positions, "controlled_corporations": controlled,
            "tables": tables,
            "params": {"fn": key, "op": op}, "_meta": r}


def corp_list(*, stock_code, list_code="ns", from_date=None, to_date=None, pg=1,
              cache=None, no_cache=False):
    """→ {stock_code, corp_name, list_code, list_label, page, total, rows[],
    params, _meta, _session_refreshed}; the per-corporation DI lists (the
    seven sa2 faces behind the resolution page). The face bootstraps the
    ASP.NET session (form GET → VIEWSTATE quartet + cookie, cached together
    30min), POSTs the search once, parses the seven list links (sid/cid/sd/ed
    verbatim off the upstream href — never invented), then GETs the chosen
    list WITH the session cookie. A dead session (link-less resolution page)
    re-bootstraps once and retries. Dates dd/mm/yyyy upstream, ISO accepted;
    from_date < 2017-07-03 refused (the DION floor — earlier asks are
    silently clamped upstream). list codes: as/cs/ns/ad/nd/an (default ns)."""
    from ..transport import call_provider

    code = re.sub(r"\D", "", str(stock_code or ""))
    if not code:
        raise SdkError("usage_error", provider="hk_hkexdi",
                       detail="--stock-code is required (e.g. 00700)")
    if list_code not in _LISTS:
        raise SdkError("usage_error", provider="hk_hkexdi",
                       detail=f"list must be one of {', '.join(_LISTS)} (got \"{list_code}\")")
    today = date.today()
    frm = _to_dmY(from_date) if from_date else today - timedelta(days=90)
    to = _to_dmY(to_date) if to_date else today
    if frm < date(*_DION_FLOOR):
        raise SdkError("usage_error", provider="hk_hkexdi",
                       detail=f"from_date {from_date} predates the DION floor 2017-07-03 "
                              "(the online system only holds DION-filed notices — "
                              "earlier asks are silently clamped upstream; refused here)")
    if to < frm:
        raise SdkError("usage_error", provider="hk_hkexdi",
                       detail="to_date is before from_date")
    page = max(1, int(pg or 1))

    sess = _session(cache, no_cache)
    refreshed = False
    links = None
    for attempt in (0, 1):
        fields = {
            "__EVENTTARGET": "", "__EVENTARGUMENT": "",
            "__VIEWSTATE": sess["viewstate"],
            "__VIEWSTATEGENERATOR": sess["generator"],
            "__EVENTVALIDATION": sess["eventvalidation"],
            "txtStockCode": code, "txtCorpName": "",
            "ddlStartDateDD": f"{frm.day:02d}", "ddlStartDateMM": f"{frm.month:02d}",
            "ddlStartDateYYYY": str(frm.year),
            "ddlEndDateDD": f"{to.day:02d}", "ddlEndDateMM": f"{to.month:02d}",
            "ddlEndDateYYYY": str(to.year),
            "cmdSearch": "Search",
        }
        r = call_provider(provider, "corppost",
                          {**fields, "src": "MAIN", "lang": "EN", "g_lang": "en"},
                          cache=None, no_cache=True, extra_headers=_post_headers(sess))
        links = _resolve_links(r["data"])
        if links:
            break
        if attempt == 0:   # dead session — re-bootstrap once and retry
            sess = _session(cache, no_cache=True)
            refreshed = True
    if not links:
        raise SdkError("upstream_unavailable", provider="hk_hkexdi",
                       detail="the search POST answered no list links (empty resolution "
                              "page after a fresh session) — the portal may have moved; re-probe")
    code_m, name = _resolve_corp(r["data"])
    pick = None
    for lnk in links:
        if lnk["sa2"] == list_code:
            pick = lnk
            break
    if pick is None:
        raise SdkError("upstream_unavailable", provider="hk_hkexdi",
                       detail=f"the resolution page carried no {list_code} link "
                              f"(carried: {', '.join(x['sa2'] for x in links)})")
    name = pick["params"].get("corpn") or name   # the links carry the corp name (no page echo)
    qs = dict(pick["params"])
    qs["pg"] = page
    rl = call_provider(provider, "corplist", {**qs, "which": pick["which"]},
                       cache=cache, no_cache=no_cache, extra_headers={"Cookie": sess["cookie"]})
    lt = rl["data"]
    total = None
    tm = re.search(r"Total records?:?\s*(?:<[^>]*>\s*)*([0-9,]+)", lt)
    if tm:
        total = int(tm.group(1).replace(",", ""))
    rows = []
    header = None
    _HEADER_ANCHORS = {"Form Serial Number", "Name of director",
                       "Name of substantial shareholder", "Date of notice",
                       "Date of change"}
    for tb in re.findall(r"<table.*?</table>", lt, re.S):
        for raw in _TR.findall(tb):
            cells = [_cell(c) for c in _TC.findall(raw)]
            if not any(cells) or cells[0].startswith("//"):
                continue
            fn = _fn_from_raw(raw)
            # the caption RIDES the header row's first cell ("Complete list of … -->"
            # glued ahead of the real columns) — anchor on the first known header
            # cell wherever it sits in the row, never on cells[0]
            hidx = next((i for i, c in enumerate(cells) if c in _HEADER_ANCHORS), None)
            if hidx is not None:
                if header is None:
                    header = cells[hidx:]
                continue   # the header row (or its repeat) is never data
            if header is None:
                continue   # banner/caption rows above the table header — not data
            row = {k: (cells[i] if i < len(cells) else None) for i, k in enumerate(header)}
            if fn:
                row["form_fn"] = fn
                row["form_url"] = (f"https://di.hkex.com.hk/di/"
                                   f"{'NSForm4' if fn.startswith('IR') else 'NSForm2'}.aspx"
                                   f"?fn={fn}&src=MAIN&lang=EN&g_lang=en")
            rows.append(row)
    return {"stock_code": code_m or code, "corp_name": name,
            "list_code": list_code, "list_label": pick["label"],
            "page": page, "total": total, "rows": rows,
            "params": {"stock_code": code, "list_code": list_code,
                       "from_date": frm.isoformat(), "to_date": to.isoformat(),
                       "pg": page},
            "_meta": rl, "_session_refreshed": refreshed}


def _to_dmY(v):
    """ISO (YYYY-MM-DD / YYYYMMDD) or dd/mm/yyyy → date."""
    s = str(v).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s) or re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    raise SdkError("usage_error", provider="hk_hkexdi",
                   detail=f"date must be YYYY-MM-DD, YYYYMMDD or DD/MM/YYYY (got \"{v}\")")
