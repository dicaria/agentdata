"""jp_navii — Japan 医療機能情報 (NAVII, 厚労省 statutory publication system,
www.iryou.teikyouseido.mhlw.go.jp, keyless). Register 2026-11-03 (册 149), re-verified live
2026-11-12 (probes tmp/probe-sdk-0356/p4_*). The JP pillar of healthcare facility directories
(~105k 医療機関 + ~61k 薬局; 内科 59,281 measured 2026-11-12, 薬局 60,634).

SESSION-FIRST CHAIN (the transport keeps no cookie jar — the UNGM pairing pattern):
  1. GET /znk-web/juminkanja/S2300/initialize (547KB server-rendered page) mints the jar
     (AWSALB + AWSALBCORS + SESSION). The pair is cached 20min under a dedicated cache entry;
     the 検索ID it produces is SESSION-BOUND (S2400.jsx onBusinessError reloads on expiry), so
     a stale session just means a fresh search — never replay a cached id.
  2. GET /znk-web/juminkanja/S2300/iryoSearch?XCHARSET=utf-8&XPARAM=keyword&iyakuKbn=1&lang=ja
     &keywordType=<1-4>&keyword=<enc> with headers `ajaxFlag: true` + `X-Requested-With:
     XMLHttpRequest` → {"code":"0","result":{"id":"<検索ID>"}}. WITHOUT the jar/headers the
     plain form POST path is a fake 404 (every button is type=button; the real path is the JS
     ajax call). Pharmacy faces: initializeYakk warm + yakkyokuSearch + iyakuKbn=2 —
     VERIFIED riding the SAME S2400 results page (kikanKbn=5 rows, live 2026-11-12).
     keywordType 1=自由語/2=施設名/3=診療科目 (内科 → 59,281)/4=所在地.
  3. GET /znk-web/juminkanja/S2400/initialize?id=<検索ID>&page=<0-BASED>&sortNo=1 → the
     results page, TRUE 20-row pagination (page0∩page1 kikanCd overlap = 0 measured; deep
     pages reachable). Rows are <div class="item"> blocks: the S2430 detail link carries the
     three-key grain prefCd×kikanCd (9-10 digit 保険医療機関コード)×kikanKbn (1/2=医療機関,
     5=薬局), plus name, 〒 address, (昼)/(夜) telephone, website, departments, hours and
     外来特記事項 notes in the details dl-rows. The face flattens the verified fields and
     keeps the residual dl-row text lines verbatim (details_text).

The S2430 detail page (732KB / 1,375 fields) is a second surface, out of this face's scope —
rows carry the exact detail URL. Search and results ops are NEVER cached (session-bound
ids); only the session pair is cached. TTL 20min on the pair, rps 0.3 politeness.
"""
import json as _json
import re as _re
import urllib.parse as _uparse

from ..errors import SdkError

provider = {
    "id": "jp_navii",
    "baseUrl": "https://www.iryou.teikyouseido.mhlw.go.jp",
    "rate": {"rps": 0.3, "burst": 2},
    "concurrency": 1,
    "ops": {
        "warm": {"path": "/znk-web/juminkanja/S2300/initialize", "accept": "text", "timeout": 60.0},
        "warm_yakkyoku": {"path": "/znk-web/juminkanja/S2300/initializeYakk", "accept": "text", "timeout": 60.0},
        # session-bound: never cached (search_raw passes cache=None)
        "search": {"path": "/znk-web/juminkanja/S2300/iryoSearch", "accept": "text", "timeout": 60.0, "idempotent": True},
        "search_yakkyoku": {"path": "/znk-web/juminkanja/S2300/yakkyokuSearch", "accept": "text", "timeout": 60.0, "idempotent": True},
        "results": {"path": "/znk-web/juminkanja/S2400/initialize", "accept": "text", "timeout": 90.0, "idempotent": True},
    },
    "ttl": {},
}

_KEYWORD_TYPES = ("1", "2", "3", "4")   # 1=自由語 2=施設名 3=診療科目 4=所在地
_SESSION_TTL = 20 * 60
_AJAX_HEADERS = {"ajaxFlag": "true", "X-Requested-With": "XMLHttpRequest"}


def _clean(text):
    """strip tags, collapse whitespace/pipe artifacts, unescape entities."""
    from html import unescape
    t = _re.sub(r"<[^>]+>", " ", text)
    t = _re.sub(r"\s+", " ", unescape(t)).strip()
    return t


def rows_from_upstream(html):
    """S2400 page HTML → {rows, total, shown_from, shown_to} (pure function; regex row walk —
    no bs4 dependency)."""
    m = _re.search(r"([\d,]+)\s*件中\s*([\d,]+)\s*〜\s*([\d,]+)\s*件を表示", html)
    total, s_from, s_to = (int(x.replace(",", "")) for x in m.groups()) if m else (None, None, None)
    rows = []
    for part in html.split('<div class="item">')[1:]:
        link = _re.search(r'href="(/znk-web/juminkanja/S2430/initialize\?prefCd=(\d+)&kikanCd=(\d+)&kikanKbn=(\d+))"', part)
        if not link:
            continue
        name = _re.search(r'<h2 class="name">\s*<a[^>]*>\s*(.+?)\s*</a>', part, _re.S)
        det = part.split("</h2>")[1] if "</h2>" in part else ""
        dls = _re.findall(r'<div class="dl-row[^"]*"[^>]*>(.*?)(?=<div class="dl-row|<div class="readmore|<!--)', det, _re.S)
        texts = [_clean(x) for x in dls]
        # (昼)/(夜) share one dl-row — split at (夜) when both ride together
        split = []
        for t in texts:
            if "(昼)" in t and "(夜)" in t:
                i = t.index("(夜)")
                split.extend([t[:i].strip(), t[i:].strip()])
            else:
                split.append(t)
        tel_day = tel_night = website = address = notes = None
        for t in split:
            if "〒" in t and not address:
                address = t.replace("Googleマップで見る", "").strip()
            elif t.startswith("http"):
                website = t.split(" ")[0]
            elif "(昼)" in t:
                tel_day = t
            elif "(夜)" in t:
                tel_night = t
            elif "特記事項" in t and not notes:
                notes = t
        rows.append({
            "pref_cd": link.group(2), "kikan_cd": link.group(3), "kikan_kbn": link.group(4),
            "name": _clean(name.group(1)) if name else None,
            "detail_url": provider["baseUrl"] + link.group(1),
            "address": address, "tel_day": tel_day, "tel_night": tel_night,
            "website": website, "notes": notes,
            "details_text": " | ".join(x for x in texts if x) or None,
        })
    return {"rows": rows, "total": total, "shown_from": s_from, "shown_to": s_to}


def _session(cache, no_cache, pharmacy=False):
    """→ Cookie header value for the current session (cached 20min; the jar mints AWSALB +
    AWSALBCORS + SESSION). The warm page follows the branch: initialize for 医療機関,
    initializeYakk for 薬局 (both mint the same jar shape)."""
    from ..transport import call_provider
    scope = "session_yakkyoku" if pharmacy else "session"
    if cache is not None and not no_cache:
        # the cache.get wrapper carries {"payload": ..., "fetched_at_iso": ...} — unwrap payload
        hit = (cache.get("jp_navii", scope, _SESSION_TTL) or {}).get("payload") or {}
        if hit.get("cookie"):
            return hit["cookie"]
    r = call_provider(provider, "warm_yakkyoku" if pharmacy else "warm", {}, cache=None, no_cache=True)
    sc = r.get("set_cookie") or []
    if not sc:
        raise SdkError("upstream_unavailable", provider="jp_navii",
                       detail="initialize minted no session cookies (the AWSALB/SESSION contract may have changed)")
    cookie = "; ".join(s.split(";", 1)[0].strip() for s in sc)
    if cache is not None and not no_cache:
        cache.set("jp_navii", scope, {"cookie": cookie}, _SESSION_TTL)
    return cookie


def _search_id(cookie, pharmacy, q, keyword_type, cache, no_cache):
    """→ the 検索ID (session-bound; live call, never cached)."""
    from ..transport import call_provider
    op = "search_yakkyoku" if pharmacy else "search"
    params = {"XCHARSET": "utf-8", "XPARAM": "keyword", "iyakuKbn": "2" if pharmacy else "1",
              "lang": "ja", "keywordType": str(keyword_type), "keyword": q}
    r = call_provider(provider, op, params, cache=None, no_cache=True,
                      extra_headers={"Cookie": cookie, **_AJAX_HEADERS})
    try:
        doc = _json.loads(r["data"])
    except (TypeError, ValueError):
        raise SdkError("upstream_unavailable", provider="jp_navii",
                       detail="iryoSearch answered non-JSON (the ajax-flag contract may have changed)")
    if str(doc.get("code")) != "0" or not (doc.get("result") or {}).get("id"):
        raise SdkError("upstream_unavailable", provider="jp_navii",
                       detail=f"search rejected (code={doc.get('code')!r}) — keyword/keywordType combo invalid")
    return str(doc["result"]["id"])


def search_raw(q, *, keyword_type="3", pharmacy=False, page=0, cache=None, no_cache=False):
    """→ rows_from_upstream(S2400 page) + search_id + params + _meta.

    q = keyword (required); keyword_type 1=自由語/2=施設名/3=診療科目/4=所在地 (default 3 —
    the 診療科目 walk is the enumeration channel); pharmacy=True → 薬局 corpus
    (initializeYakk/yakkyokuSearch/iyakuKbn=2 — VERIFIED on the shared S2400 page, rows
    kikanKbn=5); page is 0-BASED (upstream semantics), 20 rows/page true pagination. Each call
    runs a fresh session-bound search (2 live requests; the warm session is cached 20min)."""
    from ..transport import call_provider

    qq = str(q or "").strip()
    if not qq:
        raise SdkError("usage_error", provider="jp_navii",
                       detail="search requires q (e.g. keyword_type=3 内科 | keyword_type=2 施設名 | "
                              "keyword_type=4 所在地)")
    kt = str(keyword_type)
    if kt not in _KEYWORD_TYPES:
        raise SdkError("usage_error", provider="jp_navii",
                       detail=f"keyword_type must be one of {'|'.join(_KEYWORD_TYPES)} "
                              "(1=自由語 2=施設名 3=診療科目 4=所在地), got '{kt}'")
    try:
        pg = int(page) if page is not None else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="jp_navii",
                       detail=f"page must be an integer >=0 (0-based upstream), got {page!r}")
    if pg < 0:
        raise SdkError("usage_error", provider="jp_navii",
                       detail=f"page is 0-BASED (upstream S2400 semantics), got {pg}")
    cookie = _session(cache, no_cache, pharmacy=pharmacy)
    sid = _search_id(cookie, pharmacy, qq, kt, cache, no_cache)
    r = call_provider(provider, "results",
                      {"id": _uparse.quote(sid), "page": str(pg), "sortNo": "1"},
                      cache=None, no_cache=True, extra_headers={"Cookie": cookie})
    html = r["data"]
    if not isinstance(html, str) or '<div class="item">' not in html:
        raise SdkError("upstream_unavailable", provider="jp_navii",
                       detail="S2400 answered without result items — the 検索ID is session-bound; "
                              "a stale session dies here (retry runs a fresh search)")
    out = rows_from_upstream(html)
    out["search_id"] = sid
    out["params"] = {"q": qq, "keyword_type": kt, "pharmacy": bool(pharmacy), "page": pg}
    out["_meta"] = r
    return out
