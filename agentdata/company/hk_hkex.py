"""hk_hkex — HKEX listed universe + HKEXnews announcements (two hosts, keyless; 0.3.69 batch E12).

2026-11-18 probed laws (tmp/probe-e12/):
UNIVERSE (www.hkex.com.hk ListOfSecurities.xlsx, 1,361,604B):
  xlsx = zip + xml parsed with stdlib alone; the real values ride per-cell <x:v> (t="str") —
  sharedStrings holds only the 5 template strings. THREE-HEADER ROWS: row 1 title, row 2
  "Updated as at 18/11/2026" (the AS-AT anchor), row 3 the 18-column header, rows 4+ data
  (17,336 securities: DW 6,908 / CBBC 5,830 / Equity 2,812 / Debt 1,322 / ETP 453 / REIT 11),
  trailing formatting rows carry no values and are skipped. DIMENSION LIE: <x:dimension
  ref="A1:R8"> understates reality — rows are the truth, never the dimension. Column P's header
  is a MULTILINE legend ("Spread Table\n1 = Part A\n3 = Part B\n5 = Part D\n4 & 6 = Part E" —
  the probe's stray-literal-4 reading was a probe artifact, caught by the header wall on first
  live call 2026-11-18; data rows carry the part codes 1/3/5/4/6); column R carries the PAIRED
  RMB counter stock code (e.g. 82805) where a dual-counter exists.
ANNOUNCEMENTS (www1.hkexnews.hk):
  titleSearchServlet.do answers DOUBLE-ENCODED JSON — {"result": "<escaped array>"} needs two
  json.loads; TOTAL_COUNT rides every row (Nov 18 days = 11,189 market-wide). TWO MODES:
  searchType=1 by stock (stockId resolved via prefix.do JSONP) / searchType=0 by title keyword.
  market closed set SEHK|GEM (GEM 691 items in the same window). Paging: first= offset,
  rowRange honored up to 1000 (measured). DATE_TIME is HK-shaped DD/MM/YYYY HH:MM — verbatim.
  TWO ERAS (config.js anchors): HeadlineCategoryStart 2007-06-25 (t1/t2 codes; tierone 20
  categories live 2026-11-18 — the probe snapshot read 15, the live codebook grows / tiertwo
  300 codes / tiertwogrp 12 groups) vs DocumentTypeStart 1999-03-31 →
  2007-06-24 (documentType codes, doc_e.json 17 types) — announcements search back to
  1999-04-01. Six codebooks under /ncms/script/eds/: tierone_e/tiertwo_e/tiertwogrp_e/doc_e +
  activestock_sehk_e (17,652 {i,c,n,s=stockId} — the resolve map) and inactivestock_sehk_e
  (894 delisted). prefix.do answers JSONP cb({...stockInfo:[{stockId,code,name}]}) — the
  callback wrapper is stripped, not parsed around.
DOCUMENT BYTES: FILE_LINK paths (/listedco/listconews/...) serve PDFs 200 keyless — the E11
  body-fetch pattern minus --text (PDF is not HTML; text extraction stays on the harvest line).
One provider id, two hosts (www.hkex.com.hk + www1.hkexnews.hk — each keeps its own polite
bucket, the edgar_xbrl precedent). TTL: securities 1d / search+codebooks 1h / documents 7d
(frozen once published). Politeness 2 rps (no published limit; probes all 200, no wall).
"""
import hashlib
import io
import json
import re
import zipfile
from xml.etree import ElementTree as ET

from ..errors import SdkError

provider = {
    "id": "hk_hkex",
    "baseUrl": "https://www.hkex.com.hk",
    "rate": {"rps": 2.0, "burst": 2},
    "ops": {
        "securities": {"path": "/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx",
                       "idempotent": True, "accept": "bytes", "timeout": 60.0},
        # the www1.hkexnews.hk ops ride ABSOLUTE paths — build_url passes them through
        # unprefixed; www1 keeps its own host bucket (edgar_xbrl dual-host precedent)
        "search": {"path": "https://www1.hkexnews.hk/search/titleSearchServlet.do",
                   "idempotent": True, "timeout": 30.0},
        "resolve": {"path": "https://www1.hkexnews.hk/search/prefix.do",
                    "idempotent": True, "accept": "text", "timeout": 30.0},
        "document": {"path": "https://www1.hkexnews.hk{link}",
                     "idempotent": True, "accept": "bytes", "timeout": 60.0, "notFound": [404],
                     "path_safe": "/"},  # link carries slashes — without this the quote glues the
        # path into the host (www1.hkexnews.hk%2Flistedco…) and the proxy CONNECT 400s (live-caught)
        "codebook": {"path": "https://www1.hkexnews.hk/ncms/script/eds/{which}.json",
                     "idempotent": True, "timeout": 30.0},
    },
    "ttl": {"securities": 86400, "search": 3600, "resolve": 86400,
            "document": 604800, "codebook": 3600},
}

_XLNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# the 18 columns by letter (row-3 headers as probed — P's header is the multiline spread-table legend)
_COLS = [
    ("A", "stock_code"), ("B", "name"), ("C", "category"), ("D", "sub_category"),
    ("E", "board_lot"), ("F", "isin"), ("G", "expiry_date"), ("H", "subject_to_stamp_duty"),
    ("I", "shortsell_eligible"), ("J", "cas_eligible"), ("K", "vcm_eligible"),
    ("L", "admitted_to_ccass"), ("M", "debt_board_lot_nominal"), ("N", "debt_investor_type"),
    ("O", "pos_eligible"), ("P", "spread_table"), ("Q", "trading_currency"), ("R", "rmb_counter"),
]
_EXPECTED_HEADER = ["Stock Code", "Name of Securities", "Category", "Sub-Category", "Board Lot",
                    "ISIN", "Expiry Date", "Subject to Stamp Duty", "Shortsell Eligible",
                    "CAS Eligible", "VCM Eligible", "Admitted to CCASS",
                    "Debt Securities Board Lot (Nominal)", "Debt Securities Investor Type",
                    "POS Eligible",
                    "Spread Table\n1 = Part A\n3 = Part B\n5 = Part D\n4 & 6 = Part E",
                    "Trading Currency", "RMB Counter"]
_CODEBOOKS = ("tierone_e", "tiertwo_e", "tiertwogrp_e", "doc_e",
              "activestock_sehk_e", "inactivestock_sehk_e")
_DOC_HOST_RE = re.compile(r"^https://www1\.hkexnews\.hk(/listedco/.+)$")
_JSONP_RE = re.compile(r"^[a-zA-Z_$][\w$]*\((.*)\)\s*;?\s*$", re.S)
_DATE_RE = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})$")


# ---------------------------------------------------------------- universe (xlsx)

def _cell_values(row_elem, sst):
    """→ {col_letter: str} for one <x:row> — t="s" rides the shared-string table, else <x:v> text."""
    out = {}
    for c in row_elem.iter(_XLNS + "c"):
        ref = c.get("r") or ""
        col = re.match(r"[A-Z]+", ref)
        if not col:
            continue
        v = c.find(_XLNS + "v")
        if v is None or v.text is None:
            continue
        if c.get("t") == "s":
            try:
                out[col.group(0)] = sst[int(v.text)]
            except (ValueError, IndexError):
                continue
        else:
            out[col.group(0)] = v.text
    return out


def _parse_securities_xlsx(raw):
    """→ (as_at, [row dicts]) — stdlib zip+xml streaming; the DIMENSION LIE is ignored (rows rule)."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        sst_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in sst_root.iter(_XLNS + "si"):
            sst.append("".join(t.text or "" for t in si.iter(_XLNS + "t")))
    as_at = None
    headers = None
    rows = []
    for _ev, elem in ET.iterparse(io.BytesIO(z.read("xl/worksheets/sheet1.xml")),
                                   events=("end",)):
        if elem.tag != _XLNS + "row":
            continue
        try:
            rnum = int(elem.get("r") or "0")
        except ValueError:
            rnum = 0
        vals = _cell_values(elem, sst)
        if rnum == 2 and vals.get("A", "").startswith("Updated as at"):
            as_at = vals["A"].replace("Updated as at", "").strip()
        elif rnum == 3:
            headers = [vals.get(col, "") for col, _ in _COLS]
        elif rnum >= 4 and any((v or "").strip() for v in vals.values()):
            row = {}
            for col, key in _COLS:
                v = (vals.get(col) or "").strip()
                row[key] = v if v else None
            row["stock_code"] = row["stock_code"] or None
            rows.append(row)
        elem.clear()
    if headers is not None and headers != _EXPECTED_HEADER:
        raise SdkError("upstream_changed", provider="hk_hkex",
                       detail=f"ListOfSecurities header row drifted from the 2026-11-18 probe "
                              f"(tmp/probe-e12/): {headers!r}")
    return as_at, rows


def securities(*, code=None, name=None, category=None, sub_category=None, limit=None,
               cache=None, no_cache=False):
    """→ {as_at, total, rows[], params, _meta}; the HKEX listed-securities universe
    (17,336 rows probe day — equities 2,812, but also 6,908 derivative warrants and 5,830
    CBBC: filter with --category or the universe dwarfs the equities). Client-side selectors:
    --code exact (00005, leading zeros optional both ways), --name substring, --category/
    --sub-category exact (case-insensitive); --limit slices the display."""
    from ..transport import call_provider

    r = call_provider(provider, "securities", {}, cache=cache, no_cache=no_cache)
    raw = r["data"].encode("latin-1")  # ext-9 bytes channel: lossless round-trip
    as_at, all_rows = _parse_securities_xlsx(raw)
    q_code = re.sub(r"\D", "", str(code)) if code else None

    def _digits_eq(row_code):
        rd = re.sub(r"\D", "", row_code or "")
        if not q_code or not rd:
            return False
        return rd == q_code or (rd.isdigit() and q_code.isdigit()
                                and int(rd) == int(q_code))  # leading zeros optional both ways

    q_name = str(name).strip().lower() if name else None
    q_cat = str(category).strip().lower() if category else None
    q_sub = str(sub_category).strip().lower() if sub_category else None
    rows = []
    for row in all_rows:
        if q_code and not _digits_eq(row["stock_code"]):
            continue
        if q_name and q_name not in (row["name"] or "").lower():
            continue
        if q_cat and (row["category"] or "").lower() != q_cat:
            continue
        if q_sub and (row["sub_category"] or "").lower() != q_sub:
            continue
        rows.append(row)
    total = len(rows)
    if limit is not None and int(limit) >= 0:
        rows = rows[: int(limit)]
    return {"as_at": as_at, "total": total, "rows": rows,
            "params": {"code": code, "name": name, "category": category,
                       "sub_category": sub_category, "limit": limit},
            "_meta": r}


# ---------------------------------------------------------------- announcements

def _norm_date(v, field):
    m = _DATE_RE.match(str(v or "").strip())
    if not m:
        raise SdkError("usage_error", provider="hk_hkex",
                       detail=f"{field} must be YYYY-MM-DD or YYYYMMDD (got \"{v}\")")
    return "".join(m.groups())


def resolve_stock(query, *, cache=None, no_cache=False):
    """→ (stock dict | None, meta); prefix.do JSONP → stockInfo candidates for a code/name."""
    from ..transport import call_provider

    q = str(query or "").strip()
    if not q:
        raise SdkError("usage_error", provider="hk_hkex", detail="stock query is empty")
    r = call_provider(provider, "resolve",
                      {"callback": "cb", "lang": "EN", "type": "A", "name": q, "market": "SEHK"},
                      cache=cache, no_cache=no_cache)
    text = r["data"]
    m = _JSONP_RE.match(text.strip())
    payload = json.loads(m.group(1)) if m else json.loads(text)
    info = (payload or {}).get("stockInfo") or []
    digits = re.sub(r"\D", "", q)
    pick = None
    if digits:
        for it in info:
            if re.sub(r"\D", "", str(it.get("code", ""))) == digits:
                pick = it
                break
    if pick is None and info:
        pick = info[0]
    return pick, r


def search(*, stock=None, title=None, market="SEHK", from_date=None, to_date=None,
           t1=None, t2=None, t2g=None, document_type=None, row_range=100, first=0,
           codebook=None, cache=None, no_cache=False):
    """→ {mode, market, stock, total, rows[] | codebook, params, _meta, _resolve_meta}.
    THREE mutually-exclusive modes: --stock (code or name — resolved to stockId via prefix.do,
    searchType=1) XOR --title (keyword, searchType=0) XOR --codebook (one of the six eds
    codebooks verbatim). market SEHK|GEM. Dates YYYY-MM-DD or YYYYMMDD (both optional — the
    upstream window applies when empty). t1/t2/t2g are the post-2007-06-25 headline-category
    codes; document_type is the pre-2007 era's code (back to 1999-04-01). row_range ≤1000,
    first = offset. Rows are verbatim (DATE_TIME keeps the HK DD/MM/YYYY HH:MM shape) plus a
    full_url joined for the document face."""
    from ..transport import call_provider

    if sum(1 for x in (stock, title, codebook) if x) != 1:
        raise SdkError("usage_error", provider="hk_hkex",
                       detail="exactly one of --stock / --title / --codebook — call the face "
                              "once per mode (mode walls are cheap, fetches aren't)")
    if str(market) not in ("SEHK", "GEM"):
        raise SdkError("usage_error", provider="hk_hkex",
                       detail=f"market must be SEHK or GEM (got \"{market}\")")
    if codebook:
        which = str(codebook).strip()
        if which not in _CODEBOOKS:
            raise SdkError("usage_error", provider="hk_hkex",
                           detail=f"codebook must be one of {', '.join(_CODEBOOKS)} (got \"{codebook}\")")
        r = call_provider(provider, "codebook", {"which": which}, cache=cache, no_cache=no_cache)
        data = r["data"]
        return {"mode": "codebook", "codebook": which, "total": len(data) if isinstance(data, list) else None,
                "rows": data, "params": {"which": which}, "_meta": r, "_resolve_meta": None}

    rr = min(max(1, int(row_range or 100)), 1000)
    off = max(0, int(first or 0))
    params = {"sortDir": "0", "sortByOptions": "DateTime", "category": "0", "market": str(market),
              "stockId": "-1", "documentType": str(document_type).strip() if document_type else "-1",
              "fromDate": _norm_date(from_date, "from_date") if from_date else "",
              "toDate": _norm_date(to_date, "to_date") if to_date else "",
              "title": "", "searchType": "0",
              "t1code": str(t1).strip() if t1 else "-2",
              "t2Gcode": str(t2g).strip() if t2g else "-2",
              "t2code": str(t2).strip() if t2 else "-2",
              "rowRange": rr, "first": off, "lang": "E"}
    stock_pick = None
    rmeta = None
    if stock:
        stock_pick, rmeta = resolve_stock(stock, cache=cache, no_cache=no_cache)
        if stock_pick is None:
            raise SdkError("upstream_not_found", provider="hk_hkex",
                           detail=f"prefix.do resolved \"{stock}\" to nothing (no stockInfo rows)")
        params["stockId"] = str(stock_pick["stockId"])
        params["searchType"] = "1"
    else:
        params["title"] = str(title).strip()
        params["searchType"] = "0"
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    # DOUBLE-ENCODED: {"result": "<escaped array>"} — two json.loads
    inner = (r["data"] or {}).get("result")
    rows = json.loads(inner) if isinstance(inner, str) and inner else (inner or [])
    total = int(rows[0].get("TOTAL_COUNT", 0)) if rows else 0
    for row in rows:
        link = row.get("FILE_LINK") or ""
        if link:
            row["full_url"] = "https://www1.hkexnews.hk" + link
    return {"mode": "stock" if stock else "title", "market": str(market),
            "stock": {"code": stock_pick.get("code"), "name": stock_pick.get("name"),
                      "stock_id": stock_pick.get("stockId")} if stock_pick else None,
            "total": total, "rows": rows, "params": params,
            "_meta": r, "_resolve_meta": rmeta}


# ---------------------------------------------------------------- document bytes

def document(*, url=None, link=None, cache=None, no_cache=False):
    """→ {file_name, url, size_bytes, sha256, file_type, content_latin1, params, _meta};
    the announcement PDF bytes verbatim (E11's body-fetch pattern; no --text — PDF is not HTML,
    text extraction stays on the harvest line). --url (a full_url the search face returns) XOR
    --link (the FILE_LINK path). Wall: www1.hkexnews.hk/listedco/… only. content_latin1
    round-trips: content_latin1.encode("latin-1") == the original bytes."""
    from ..transport import call_provider

    if bool(url) == bool(link):
        raise SdkError("usage_error", provider="hk_hkex",
                       detail="exactly one of --url / --link (url = the search face's full_url)")
    path = None
    if url:
        m = _DOC_HOST_RE.match(str(url).strip())
        if not m:
            raise SdkError("usage_error", provider="hk_hkex",
                           detail="url must be https://www1.hkexnews.hk/listedco/… (the search "
                                  "face's full_url) — anything else never leaves the process")
        path = m.group(1)
    else:
        path = str(link).strip()
        if not path.startswith("/listedco/") or len(path) <= len("/listedco/"):
            raise SdkError("usage_error", provider="hk_hkex",
                           detail=f"link must be a /listedco/… FILE_LINK path (got \"{link}\")")
    r = call_provider(provider, "document", {"link": path}, cache=cache, no_cache=no_cache)
    raw = r["data"].encode("latin-1")  # ext-9 lossless round-trip
    head = raw[:5]
    return {"file_name": path.rsplit("/", 1)[-1],
            "url": "https://www1.hkexnews.hk" + path,
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "file_type": "PDF" if head.startswith(b"%PDF") else "unknown",
            "content_latin1": r["data"],
            "params": {"link": path}, "_meta": r}
