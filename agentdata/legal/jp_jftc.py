"""jp_jftc — Japan Fair Trade Commission 審決・判決 database
(snk.jftc.go.jp, Laravel + Akamai edge, keyless but fingerprinted).

JP legal faces (0.3.63; admitted from the research booklet legal-enforcement
3b; probed live 2026-11-16 tmp/probe-e5/): TWO faces over ONE database —
decisions (the DC004 search) and decision (the DC005 full-text page).

LIVE LAWS (measured 2026-11-16, tmp/probe-e5/):
  - HEADER FINGERPRINT GATE: bare urllib UA answers 403 with a 379B stub; the
    pinned Chrome browser-header suite (the afdb ext-8 law) answers 200 and
    the Akamai _abck/bm_sz cookies pass. Every op rides the suite.
  - CSRF + SESSION PAIRING: DC001 embeds <input name="_token" …> (Laravel);
    the token is SESSION-BOUND, so the bootstrap caches {token, cookie}
    TOGETHER under a module session key (cache_key_for('session') — the cache
    key rolls when the session refreshes, the kr_fss daily-edate precedent).
    A stale pair answers 419; the face re-bootstraps once and retries.
  - ONE-FORM SEARCH: DC001's three tabs are ONE form; DC004 reads whichever
    fields arrive. Measured: search_type=1 + dsubject[0]=ソニー → 14 rows;
    the bare sweep → 6,220 rows (2026-11-16). dandOr[] are the AND/OR
    CONNECTOR selects, not subject slots (the first probe's 0-row trap).
  - PAGE IS 1-BASED and 10 rows/page; maxOnePageItem=30 was posted and NOT
    honoured (page 2 still shows ranks 11-20) — page size is not exposed.
  - list-row dates carry HALF-WIDTH era digits (令和07年), the DC005 detail
    FULL-WIDTH (令和７年（行夕）第１９４号) — both normalize through the same
    era table (R=2018+n / H=1988+n / S=1925+n) and stay verbatim alongside.

TERMS 🟢 PDL 1.0 (kiyaku page, verbatim): 「著作権は、特記されていない限り公正
取引委員会に帰属し…「公共データ利用規約（第1.0版）」（PDL1.0）に準拠した利用
条件の下で、利用することができます。」attribution 出典：公正取引委員会.

Politeness: 0.3/1, concurrency 1 (an Akamai-edged government host), TTLs
session 30min / search 6h / detail 72h.
"""
import html as _html
import math
import re

from ..errors import SdkError

provider = {
    "id": "jp_jftc",
    "baseUrl": "https://snk.jftc.go.jp",
    "rate": {"rps": 0.3, "burst": 1},
    "concurrency": 1,
    "ops": {
        "form":   {"path": "/DC001", "accept": "text", "timeout": 45.0},
        "search": {"path": "/DC004", "method": "POST", "urlencoded": True,
                   "idempotent": True, "accept": "text", "timeout": 45.0},
        "detail": {"path": "/DC005/{case_id}", "accept": "text", "timeout": 45.0},
    },
    "ttl": {"search": 6 * 3600, "detail": 72 * 3600},
}
_SESSION_TTL = 30 * 60

# the pinned browser-header suite (the afdb ext-8 law, verbatim) — the JFTC
# host gates on the UA fingerprint (bare urllib = 403 379B stub)
_SUITE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7",
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
}
_XHR = {"Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Referer": "https://snk.jftc.go.jp/DC001"}

_ERA_BASE = {"R": 2018, "H": 1988, "S": 1925}          # 令和 / 平成 / 昭和
_ERA_NAME = {"令和": "R", "平成": "H", "昭和": "S"}
_FW = str.maketrans("０１２３４５６７８９（）", "0123456789()")
_ERA_DATE = re.compile(r"(令和|平成|昭和)(\d{1,2})年(\d{1,2})月(\d{1,2})日")
_TAG = re.compile(r"<[^>]+>")


def _era_to_iso(text):
    """令和07年02月20日 (half- or full-width digits) → 2026-02-20 (None if no era date)."""
    m = _ERA_DATE.search(str(text).translate(_FW))
    if not m:
        return None
    base = _ERA_BASE[_ERA_NAME[m.group(1)]]
    return f"{base + int(m.group(2)):04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}"


def _clean(fragment):
    """HTML fragment → readable text: <br> → newline, tags dropped, entities unescaped."""
    t = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    t = _TAG.sub(" ", t)
    return "\n".join(re.sub(r"[ \t]+", " ", ln).strip() for ln in _html.unescape(t).splitlines()).strip()


def _session(cache, no_cache):
    """→ {token, cookie} — the CSRF token and its session cookie cached TOGETHER
    (a Laravel token is session-bound; caching the page alone would hand out
    dead tokens on replay). Direct cache-API entry: call_provider only caches
    the response body, never the set-cookie pair that goes with it."""
    from ..transport import cache_key_for, call_provider

    key = cache_key_for("session", {}, scope=provider["baseUrl"])
    if not no_cache and cache is not None:
        hit = cache.get(provider["id"], key, _SESSION_TTL)
        if hit and isinstance(hit["payload"], dict) and hit["payload"].get("token"):
            return hit["payload"]
    r = call_provider(provider, "form", {}, cache=None, no_cache=True,
                      extra_headers=_SUITE)
    tm = re.search(r'name="_token" value="([^"]+)"', r["data"])
    if not tm:
        raise SdkError("upstream_unavailable", provider=provider["id"],
                       detail="DC001 answered without a CSRF _token input — the form may have moved; re-probe")
    cookie = "; ".join((c.split(";")[0] or "").strip() for c in (r.get("set_cookie") or []))
    sess = {"token": tm.group(1), "cookie": cookie}
    if not no_cache and cache is not None:
        cache.set(provider["id"], key, sess, _SESSION_TTL)
    return sess


def _xhr_headers(sess):
    h = dict(_SUITE)
    h.update(_XHR)
    if sess.get("cookie"):
        h["Cookie"] = sess["cookie"]
    return h


_CHUNK = re.compile(r'(?s)<div class="sRes">(.*?)(?=<div class="sRes">|<ul class="pagination__list">)')
_RANK = re.compile(r'<p class="num[^"]*">(\d+)</p>')
_SUBJECT = re.compile(r"<a class=\"subject\" onclick=\"detail\('([^']+)'\)\">([^<]+)</a>")
_TYPE = re.compile(r'<span class="[^"]*">\s*([^<]+?)\s*</span>\s*</h3>')
_COURT = re.compile(r"</h3>\s*<p>([^<]+)</p>")
_DTPAIR = re.compile(r"<dt>([^<]+)</dt>\s*<dd>：([^<]+)</dd>")
_PDF = re.compile(r'<a class="pdf_dl"[^>]*href="([^"]+)"[^>]*>\s*<img[^>]*>\s*<span>([\d.,]+)\s*KB</span>', re.S)
_GAIYO = re.compile(r"(?s)<h4>処分の概要</h4>\s*<dl class=\"remarks\">\s*(.*?)\s*</dl>")
_JIKEN = re.compile(r"(?s)<h4>事案の概要</h4>(.*?)(?:</div>|$)")
_COUNT = re.compile(r"検索結果：([\d,]+)件")
_CUR = re.compile(r'pagination__item--current">\s*(\d+)')


def parse_results(text):
    """DC004 HTML → {rows, total, page} (pure function; rows carry the rank, the
    DC005 case id, type/court/event_no verbatim, the era date as ISO + verbatim,
    the law, the pdf_url + KB, and the two inline 概要 blocks)."""
    cm = _COUNT.search(text)
    total = int(cm.group(1).replace(",", "")) if cm else None
    cur = _CUR.search(text)
    page = int(cur.group(1)) if cur else 1
    rows = []
    for chunk in _CHUNK.finditer(text):
        c = chunk.group(1)
        sm = _SUBJECT.search(c)
        if not sm:
            continue
        det_url = sm.group(1)
        case_id = det_url.rsplit("/", 1)[-1]
        fields = dict((_html.unescape(k).strip(), _html.unescape(v).strip())
                      for k, v in _DTPAIR.findall(c))
        disposal = fields.get("処分年月日")
        pm = _PDF.search(c)
        rows.append({
            "rank": int(_RANK.search(c).group(1)) if _RANK.search(c) else None,
            "case_id": case_id,
            "url": det_url,
            "title": _html.unescape(sm.group(2)).strip(),
            "type": _TYPE.search(c).group(1) if _TYPE.search(c) else None,
            "court": _COURT.search(c).group(1).strip() if _COURT.search(c) else None,
            "event_no": fields.get("事件番号"),
            "disposal_date": disposal,
            "disposal_date_iso": _era_to_iso(disposal) if disposal else None,
            "law": fields.get("適用法条"),
            "pdf_url": _html.unescape(pm.group(1)) if pm else None,
            "pdf_kb": float(pm.group(2).replace(",", "")) if pm else None,
            "disposal_summary": _clean(_GAIYO.search(c).group(1)) if _GAIYO.search(c) else None,
            "case_summary": _clean(_JIKEN.search(c).group(1)) if _JIKEN.search(c) else None,
        })
    return {"rows": rows, "total": total, "page": page}


def decisions_raw(subject=None, branch=None, year=None, number=None, era="R",
                  page=1, *, limit=20, cache=None, no_cache=False):
    """→ {rows, total_matched, pages, page, scanned_rows, params, _meta}.

    subject = 被審人 company-name slot(s) (1-5; upstream dsubject[0-4], ANDed);
    branch = the case-class select token (e.g. J01 判 / J03 納 / J05 訟);
    year/number = the 事件番号 event number (era-year + running no., era defaults
    R = 令和); page is 1-BASED, 10 rows per page upstream (maxOnePageItem is
    NOT honoured — measured); limit slices locally. The face walks one page
    per call — the bare sweep is 6,220 rows over 622 pages, no all-pages mode."""
    if era not in _ERA_BASE:
        raise SdkError("usage_error", provider="jp_jftc",
                       detail=f"era must be one of {'|'.join(_ERA_BASE)}, got {era!r}")
    subjects = [s.strip() for s in (subject or []) if str(s).strip()]
    if len(subjects) > 5:
        raise SdkError("usage_error", provider="jp_jftc",
                       detail=f"at most 5 subject slots (upstream dsubject[0-4]), got {len(subjects)}")
    page_i = int(page) if page not in (None, "") else 1
    if page_i < 1:
        raise SdkError("usage_error", provider="jp_jftc",
                       detail=f"page is 1-based, got {page!r}")
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="jp_jftc",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    if year not in (None, "") and not 1 <= int(year) <= 99:
        raise SdkError("usage_error", provider="jp_jftc",
                       detail=f"year must be the era year 1-99, got {year!r}")
    from ..transport import call_provider

    def _fire(sess):
        p = {"_token": sess["token"], "search_type": "1"}
        for i, s in enumerate(subjects):
            p[f"dsubject[{i}]"] = s
        if branch not in (None, ""):
            p["branch"] = branch
        if year not in (None, ""):
            p["era"] = era
            p["year"] = str(year)
        if number not in (None, ""):
            p["number"] = str(number)
        p["page"] = str(page_i)
        return call_provider(provider, "search", p, cache=cache, no_cache=no_cache,
                             extra_headers=_xhr_headers(sess))

    try:
        r = _fire(_session(cache, no_cache))
    except SdkError as e:            # 419 = the cached token/cookie pair expired
        if getattr(e, "status", None) != 419:
            raise
        r = _fire(_session(cache, no_cache=True))
    parsed = parse_results(r["data"])
    total = parsed["total"] or 0
    return {
        "rows": parsed["rows"][:size],
        "total_matched": total,
        "pages": math.ceil(total / 10) if total else None,
        "page": parsed["page"],
        "scanned_rows": len(parsed["rows"]),
        "params": {"subject": subjects or None, "branch": branch or None,
                   "year": int(year) if year not in (None, "") else None,
                   "number": number or None, "era": era, "page": page_i,
                   "limit": size},
        "_meta": r,
    }


_HCONT = re.compile(r"(?s)<div class=\"h_cont\">(.*?)<!--h_cont")
_DIV = re.compile(r"(?s)<div>(.*?)</div>")
_H3 = re.compile(r"(?s)<h3[^>]*>(.*?)</h3>")
_P = re.compile(r"(?s)<p>(.*?)</p>")
_PARTY_MARK = re.compile(r"(申立人|被審人|相手方|処分命令|請求人)")
_CASEID_OK = re.compile(r"^[A-Z0-9]{16,24}$")


def parse_detail(text, case_id):
    """DC005 HTML → the structured header + full 本文 (pure function; the h_cont
    children are FLAT divs — first = law+court, then the event-no block, the
    h3 section block, the parties block, the 主文+事実及び理由 text block, the
    judges block; full-width digits normalize, everything stays verbatim too)."""
    hm = _HCONT.search(text)
    title_m = re.search(r"(?s)<h2[^>]*>([^<]+)</h2>", hm.group(1) if hm else text)
    if not hm or not title_m:
        return None
    blocks = [m.group(1) for m in _DIV.finditer(hm.group(1))]
    out = {"case_id": case_id, "url": f"{provider['baseUrl']}/DC005/{case_id}",
           "title": _html.unescape(title_m.group(1)).strip(),
           "law": None, "court": None, "event_no": None, "section": None,
           "section_date": None, "section_date_iso": None,
           "parties": None, "text": None, "judges": None}
    for b in blocks:
        plain = _clean(b)
        h3 = _H3.search(b)
        if h3:
            out["section"] = _html.unescape(re.sub(r"<[^>]+>", "", h3.group(1))).strip()
            for ps in _P.finditer(b[h3.end():]):
                seg = _clean(ps.group(1))
                if seg:
                    out["section_date"] = seg
                    out["section_date_iso"] = _era_to_iso(seg)
                    break
            continue
        if out["law"] is None and "<br" in b:
            ps = _P.search(b)
            if ps:
                lines = [ln for ln in _clean(ps.group(1)).splitlines() if ln]
                if len(lines) >= 2:
                    out["law"], out["court"] = lines[0], lines[1]
                    continue
        if "第" in plain.translate(_FW) and "号" in plain.translate(_FW) and not _PARTY_MARK.search(plain):
            if out["event_no"] is None:
                out["event_no"] = plain
            continue
        if _PARTY_MARK.search(plain) and out["parties"] is None:
            out["parties"] = plain
            continue
        if plain.startswith("主文") and out["text"] is None:
            out["text"] = plain
            continue
        if "裁判長裁判官" in plain:
            out["judges"] = plain
    return out


def decision_raw(case_id, *, cache=None, no_cache=False):
    """→ {…DC005 fields…, params, _meta}. case_id = the token from
    jp_jftc_decisions rows (the DC005 path segment, e.g.
    R080220R07G05000194K). The detail page carries no PDF links — the
    document lives on the list row's a.pdf_dl; 別紙 attachments are stubbed
    〈略〉 upstream."""
    cid = str(case_id or "").strip()
    if not _CASEID_OK.match(cid):
        raise SdkError("usage_error", provider="jp_jftc",
                       detail=f"case_id must be the DC005 path token from jp_jftc_decisions rows, got {cid!r}")
    from ..transport import call_provider

    r = call_provider(provider, "detail", {"case_id": cid}, cache=cache,
                      no_cache=no_cache,
                      extra_headers={**_SUITE, "Referer": "https://snk.jftc.go.jp/DC001"})
    doc = parse_detail(r["data"], cid)
    if not doc:
        raise SdkError("not_found", provider="jp_jftc",
                       detail=f"DC005 answered but carries no h_cont case block for {cid}")
    doc["params"] = {"case_id": cid}
    doc["_meta"] = r
    return doc
