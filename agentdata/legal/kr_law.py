"""kr_law — Korea 국가법령정보센터 dual-pillar list search (www.law.go.kr, keyless; the
KR statutes + case-law double gap closed in one source). Register 2026-11-04 (booklet 265), core
contract re-verified live 2026-11-12 with the SDK's own polite UA (probes
tmp/probe-sdk-0356/p5_* — INCLUDING the negative: the register-note's "session trio"
(GET homepage warm cookie + Referer + X-Requested-With) turned out to be the successful probe
PATH, not a hard requirement — a plain urlencoded POST answers the same 40KB fragment with
zero warm-up and zero extra headers, measured all three ways).

TWO PILLARS, one POST contract (form-urlencoded):
  statutes POST /LSW/lsScListR.do {q, outmax<=100, pg, section="lawNm", p9="2,4", p18="0",
    p19="1,3"} — the last four ride the verified "current statutes" filter combo; q="*" is
    the FULL-ENUMERATION channel (the JS fills * on an empty query). The ceiling sits at
    pg≈300-350 × 20 (≈6-7k 現行 법령 under this filter; the full corpus incl. 자치법규 is
    ~24k). Rows: onclick lsViewWideAll('<lsiSeq>','<efYd>') — the DOUBLE numeric key (statute
    version serial × effective date); the title attr carries 법령명 + [시행 <date>] +
    [법률 제<N>호, <promulgation date>, <amendment kind>]. efYd="99990101" is the 시행미정
    (not-yet-in-force) sentinel — the face maps it to effective_date=None + pending=True
    (never treat it as a date).
  precedents POST /LSW/precScListR.do {q, outmax, pg} — q="*" ≈ 119,970 판례 (pg 1,199×100
    + a 70-row tail, bisected to certainty 2026-11-04). Rows: onclick precView('<precSeq>')
    single numeric key; the title attr carries 사건명 + [법원 <Y. M. D.> 선고 <사건번호>
    판결|결정] (court × decision date × case number, parseable from one string).

The detail bodies (statute full text lsInfoR.do ≈MB-grade HTML; precedent full text
precInfoR.do/precHwpSave.do) are second surfaces out of this face's scope — rows carry the
keys. Rows are parsed from the HTML fragment by regex (no bs4 dependency), fields verbatim.
TTL 12h; rps 0.25.
"""
import re as _re
from html import unescape as _unescape

from ..errors import SdkError

provider = {
    "id": "kr_law",
    "baseUrl": "https://www.law.go.kr",
    "rate": {"rps": 0.25, "burst": 2},
    "concurrency": 1,
    "ops": {
        # accept:"text" — the payload is an HTML fragment; without it call_provider's JSON
        # success-condition (r["json"] is not None) mis-flags every 2xx fragment as a WAF
        # challenge (nl_rechtspraak precedent: accept:'text' = "the HTML page IS the payload")
        "statutes": {"path": "/LSW/lsScListR.do", "method": "POST", "urlencoded": True,
                     "idempotent": True, "timeout": 60.0, "accept": "text"},
        "precedents": {"path": "/LSW/precScListR.do", "method": "POST", "urlencoded": True,
                       "idempotent": True, "timeout": 60.0, "accept": "text"},
    },
    "ttl": {"statutes": 12 * 3600, "precedents": 12 * 3600},
}

_EF_SENTINEL = "99990101"   # 시행미정 (effective-date-undecided) sentinel


def _clean(text):
    return _re.sub(r"\s+", " ", _unescape(text or "")).strip()


def rows_from_statutes(html):
    """lsScListR fragment → {rows, total} (pure function). Each row carries TWO anchors in the
    fragment (left list + main list) — deduped on (lsi_seq, effective_date), first wins."""
    rows, seen = [], set()
    for m in _re.finditer(r"lsViewWideAll\('(\d+)','(\d+)'[^>]*title=\"([^\"]*)\"", html):
        lsi_seq, ef_yd, title = m.group(1), m.group(2), _clean(m.group(3))
        if (lsi_seq, ef_yd) in seen:
            continue
        seen.add((lsi_seq, ef_yd))
        pending = ef_yd == _EF_SENTINEL
        law_number = _re.search(r"법률 제(\d+)호", title)
        rows.append({
            "lsi_seq": lsi_seq,
            "effective_date": None if pending else f"{ef_yd[:4]}-{ef_yd[4:6]}-{ef_yd[6:]}",
            "pending": pending,                      # 시행미정 sentinel (never a real date)
            "title": title,
            "law_number": (law_number.group(1) if law_number else None),
        })
    total = _re.search(r"총\s*([\d,]+)\s*건", html)
    return {"rows": rows, "total": int(total.group(1).replace(",", "")) if total else None}


def rows_from_precedents(html):
    """precScListR fragment → {rows, total} (pure function)."""
    rows = []
    for m in _re.finditer(r'onclick="javascript:precView\(\'(\d+)\'\)[^>]*title="([^"]*)"', html):
        prec_seq, title = m.group(1), _clean(m.group(2))
        mm = _re.match(r"(.+?)\s*\[([^\[\]]+선고[^\[\]]+)\]\s*$", title)
        case_name, case_meta = (mm.group(1).strip(), mm.group(2).strip()) if mm else (title, None)
        dec = None
        if case_meta:
            dm = _re.match(r"(\S+)\s+([\d. ]+?)\s*선고\s+(\S+)\s+(판결|결정)$", case_meta)
            if dm:
                dec = {"court": dm.group(1), "decided": dm.group(2).strip(),
                       "case_number": dm.group(3), "kind": dm.group(4)}
        rows.append({"prec_seq": prec_seq, "case_name": case_name,
                     "case_meta": case_meta, "decision": dec})
    total = _re.search(r"총\s*([\d,]+)\s*건", html)
    return {"rows": rows, "total": int(total.group(1).replace(",", "")) if total else None}


def statutes_raw(q="*", *, page=1, page_size=20, cache=None, no_cache=False):
    """→ rows_from_statutes(...) + params + _meta. q = 법령 name keyword (or "*" full
    enumeration under the current-statutes filter); page 1-based; page_size 1-100 (outmax,
    upstream cap). Ceiling note: under the verified filter combo the walk dies around pg
    300-350 at page_size 20 (≈6-7k current statutes) — a wider census is a batch concern."""
    return _list_raw("statutes", rows_from_statutes, q, page, page_size,
                     {"section": "lawNm", "p9": "2,4", "p18": "0", "p19": "1,3"},
                     "kr_law_statutes", cache, no_cache)


def precedents_raw(q="*", *, page=1, page_size=20, cache=None, no_cache=False):
    """→ rows_from_precedents(...) + params + _meta. q = case-name keyword (or "*" full
    enumeration ≈119,970 precedents at page_size 100 → ~1,200 pages)."""
    return _list_raw("precedents", rows_from_precedents, q, page, page_size, {},
                     "kr_law_precedents", cache, no_cache)


def _list_raw(op, parser, q, page, page_size, extra_form, tool, cache, no_cache):
    from ..transport import call_provider

    qq = str(q or "").strip() or "*"
    if qq == "":
        qq = "*"          # the JS fills * on an empty query — same semantics
    try:
        pg = int(page) if page is not None else 1
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="kr_law",
                       detail=f"page must be an integer >=1, got {page!r}")
    if pg < 1:
        raise SdkError("usage_error", provider="kr_law",
                       detail=f"page is 1-based (got {pg})")
    try:
        size = int(page_size) if page_size is not None else 20
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="kr_law",
                       detail=f"page_size must be an integer 1-100 (outmax upstream cap), got {page_size!r}")
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="kr_law",
                       detail=f"page_size must be 1-100 (outmax upstream cap), got '{page_size}'")
    form = {"q": qq, "outmax": str(size), "pg": str(pg), **extra_form}
    r = call_provider(provider, op, form, cache=cache, no_cache=no_cache)
    html = r["data"]
    if not isinstance(html, str):
        raise SdkError("upstream_unavailable", provider="kr_law",
                       detail=f"{op} answered a non-text payload (the fragment contract may have changed)")
    out = parser(html)
    out["params"] = {"q": qq, "page": pg, "page_size": size, "tool": tool}
    out["_meta"] = r
    return out
