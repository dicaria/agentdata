"""in_cci — India Competition Commission of India order registers
(www.cci.gov.in, Laravel + DataTables server-side, keyless but CSRF'd).

IN legal faces (0.3.63; admitted from the research booklet 册 legal-enforcement
3d; probed live 2026-11-16 tmp/probe-e5/): TWO faces over TWO registers —
antitrust_orders (POST /antitrust/orders/list, 1,246 rows) and combinations
(GET /combination/orders-section31, 1,491 rows — the POST answers 405, the
DataTables default is GET, the no-type-declaration trap).

LIVE LAWS (measured 2026-11-16, tmp/probe-e5/):
  - TOKEN ATTRIBUTE MISALIGNMENT: the hidden input reads
    name="_token" type="hidden" value="…" — the type attribute sits BETWEEN
    name and value, so a name-value-adjacent regex finds nothing.
  - CSRF + SESSION PAIRING: the token is session-bound; the bootstrap caches
    {token, cookie} TOGETHER under a module session key (the jp_jftc dance).
    A stale pair 419s; the face re-bootstraps once and retries.
  - BYTE-EQUAL PAYLOADS: the antitrust POST carries tab_type=antitrust, 5
    columns[] (case_no/description/section/order_date/pdf) and order dir asc
    exactly as the page's DataTable config fires; the combination GET carries
    9 columns[] + form_type/order_status/searchString/search_type/fromdate/
    todate. The column names are the DATA keys the server maps, not the
    display headers.
  - DESCRIPTION PLACES "XYZ" ON RECENT ROWS — the parties live in the order
    PDF, not the register (rows 02/2026 and 04/2026 both XYZ; 13/2025
    carries real parties). The face keeps description verbatim and never
    guesses the party from the attachment filename.
  - ATTACHMENTS: file_content is an HTML-ESCAPED JSON array
    ([{title, file_name, file_size}]) — unescape then json.loads; the files
    HTML carries the /antitrust/orders/details/{id}/{n} direct links.

TERMS 🔴 NIC prior-permission family (the it_agcm/de_lobbyregister/kr_fss
posture; /contents/copyright verbatim): "Material featured on Competition
Commission of India (CCI) may be reproduced free of charge after taking
proper permission by sending a mail to us. … Authorisation to reproduce such
material must be obtained from the departments/copyright holders concerned."
The faces query live and pass through; no hosted redistribution until 翻案.

Politeness: 0.5/2, concurrency 1, TTLs session 30min / data 6h.
"""
import html as _html
import json
import re

from ..errors import SdkError

provider = {
    "id": "in_cci",
    "baseUrl": "https://www.cci.gov.in",
    "rate": {"rps": 0.5, "burst": 2},
    "concurrency": 1,
    "ops": {
        "orders_form": {"path": "/antitrust/orders", "accept": "text", "timeout": 45.0},
        "orders":      {"path": "/antitrust/orders/list", "method": "POST", "urlencoded": True,
                        "idempotent": True, "timeout": 45.0},
        "comb_form":   {"path": "/combination/orders-section31", "accept": "text", "timeout": 45.0},
        "comb":        {"path": "/combination/orders-section31", "timeout": 45.0},
    },
    "ttl": {"orders": 6 * 3600, "comb": 6 * 3600},
}
_SESSION_TTL = 30 * 60

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
_TOKEN = re.compile(r'name="_token" type="hidden" value="([^"]+)"')
_TAG = re.compile(r"<[^>]+>")

# the DataTables column keys, verbatim from the two pages' configs (the server
# maps THESE names, not the display headers)
_AT_COLS = ["case_no", "description", "section", "order_date", "pdf"]
_CB_COLS = ["DT_RowIndex", "combination_no", "party_name", "form_type",
            "notification_date", "order_status", "decision_date",
            "summary_files", "order_files"]


def _session(op_form, referer, cache, no_cache):
    """The CSRF+cookie pair for one register (each page has its own session;
    bootstrap op + referer distinguish them). Same togetherness law as jp_jftc."""
    from ..transport import cache_key_for, call_provider

    key = cache_key_for("session", {"op_form": op_form}, scope=provider["baseUrl"])
    if not no_cache and cache is not None:
        hit = cache.get(provider["id"], key, _SESSION_TTL)
        if hit and isinstance(hit["payload"], dict) and hit["payload"].get("token"):
            return hit["payload"]
    r = call_provider(provider, op_form, {}, cache=None, no_cache=True,
                      extra_headers={**_SUITE, "Referer": referer})
    tm = _TOKEN.search(r["data"])
    if not tm:
        raise SdkError("upstream_unavailable", provider=provider["id"],
                       detail=f"{op_form} answered without a CSRF _token input — re-probe")
    cookie = "; ".join((c.split(";")[0] or "").strip() for c in (r.get("set_cookie") or []))
    sess = {"token": tm.group(1), "cookie": cookie}
    if not no_cache and cache is not None:
        cache.set(provider["id"], key, sess, _SESSION_TTL)
    return sess


def _attach(file_content):
    """HTML-escaped JSON attachment array → [{title, file_name, file_size}] (None on junk).
    file_name rides backslash-slash artifacts ('images\\/antitrustorder\\/en\\/')
    measured in the wire — normalized before the URL is assembled."""
    if not file_content:
        return None
    try:
        arr = json.loads(_html.unescape(str(file_content)))
        out = []
        for a in arr:
            if not isinstance(a, dict):
                continue
            # hoisted out of the f-string: a backslash inside an f-string
            # expression is a PEP-701 relaxation (3.12+ only) — the pre-3.12
            # floor gate (tests/test_floor_compile.py) rejects it.
            name = str(a.get("file_name") or "").replace("\\/", "/").lstrip("/")
            out.append({"title": a.get("title"),
                        "file_url": f"{provider['baseUrl']}/{name}",
                        "file_size": a.get("file_size")})
        return out or None
    except (ValueError, TypeError):
        return None


def _detail_urls(files_html):
    """The files cell → the /orders/details/{id}/{n} direct links (first)."""
    if not files_html:
        return None
    urls = [f"https://www.cci.gov.in{u}" if u.startswith("/") else u
            for u in re.findall(r'href="([^"]+)"', str(files_html))]
    return urls or None


def _dt_frame(q, start, length, token, cols, extra):
    """The byte-equal DataTables frame (the eu_cijeu DSL law: replay the page's
    own shape or the server answers wrong)."""
    p = {"_token": token, "draw": "1", "start": str(start), "length": str(length),
         "search[value]": q or "", "order[0][column]": "0", "order[0][dir]": "desc"}
    for i, c in enumerate(cols):
        p[f"columns[{i}][data]"] = c
        p[f"columns[{i}][name]"] = c
        p[f"columns[{i}][searchable]"] = "true"
        p[f"columns[{i}][orderable]"] = "true"
        p[f"columns[{i}][search][value]"] = ""
    p.update(extra)
    return p


def _xhr_headers(sess, accept_json=False):
    h = dict(_SUITE)
    h.update({"X-Requested-With": "XMLHttpRequest",
              "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors",
              "Sec-Fetch-Site": "same-origin"})
    if accept_json:
        h["Accept"] = "application/json"
    if sess.get("cookie"):
        h["Cookie"] = sess["cookie"]
    return h


def _strip(label):
    return re.sub(r"\s+", " ", _TAG.sub(" ", _html.unescape(str(label)))).strip() or None


def _parse_rows(data):
    """One DataTables data array → rows (verbatim columns + the parsed
    attachments/links; description stays verbatim INCLUDING 'XYZ' placeholders)."""
    rows = []
    for d in data or []:
        rows.append({
            "id": d.get("id"),
            "case_no": d.get("case_no"),
            "section": _strip(d.get("title")) or d.get("section"),
            "type": d.get("type") or d.get("order_type"),
            "description": d.get("description"),
            "party_name": d.get("party_name"),
            "form_type": d.get("form_type"),
            "combination_no": d.get("combination_no"),
            "order_status": d.get("order_status"),
            "order_date": d.get("order_date"),
            "main_order_date": d.get("main_order_date"),
            "notification_date": d.get("notification_date"),
            "decision_date": d.get("decision_date"),
            "attachments": _attach(d.get("file_content") or d.get("order_file_content")),
            "summary_attachments": _attach(d.get("summary_file_content")),
            "detail_urls": _detail_urls(d.get("files") or d.get("order_file_content")
                                        or d.get("summary_file_content")),
        })
    return rows


def antitrust_orders_raw(q=None, case_no=None, order_type=None, page=1, *,
                         limit=20, cache=None, no_cache=False):
    """→ {rows, total_matched, total_records, pages, page, params, _meta}.

    q rides search[value] (upstream-global); case_no/order_type are LOCAL
    page-local substrings (the upstream exposes no case-number param — walk
    pages or narrow with q). Dates are dd/mm/yyyy upstream verbatim. The
    description column carries 'XYZ' placeholders on recent rows — the party
    is inside the order PDF (measured 2026-11-16)."""
    page_i = int(page) if page not in (None, "") else 1
    if page_i < 1:
        raise SdkError("usage_error", provider="in_cci",
                       detail=f"page is 1-based, got {page!r}")
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="in_cci",
                       detail=f"limit must be 1-100 (upstream DataTables length), got {limit!r}")
    from ..transport import call_provider

    start = (page_i - 1) * size

    def _fire(sess):
        p = _dt_frame(q, start, size, sess["token"], _AT_COLS,
                      {"tab_type": "antitrust", "order[0][dir]": "asc"})
        return call_provider(provider, "orders", p, cache=cache, no_cache=no_cache,
                             extra_headers=_xhr_headers(sess))

    sess_key = ("orders_form", "https://www.cci.gov.in/antitrust/orders")
    try:
        r = _fire(_session(*sess_key, cache, no_cache))
    except SdkError as e:
        if getattr(e, "status", None) != 419:
            raise
        r = _fire(_session(*sess_key, cache, no_cache=True))
    doc = r["data"] or {}
    rows = _parse_rows(doc.get("data"))
    needle_no = str(case_no or "").strip().lower() or None
    needle_ty = str(order_type or "").strip().lower() or None
    hits = [x for x in rows
            if (not needle_no or needle_no in str(x.get("case_no") or "").lower())
            and (not needle_ty or needle_ty in str(x.get("type") or "").lower())]
    total = int(doc.get("recordsTotal") or 0)
    return {
        "rows": hits[:size],
        "total_matched": len(hits),
        "total_records": total,
        "pages": (total + size - 1) // size or None,
        "page": page_i,
        "register": "antitrust orders under Competition Act 2002 s.19-27 (1,246 rows on 2026-11-16)",
        "params": {"q": q or None, "case_no": case_no or None, "order_type": order_type or None,
                   "page": page_i, "limit": size},
        "_meta": r,
    }


def combinations_raw(party=None, status=None, form_type=None, q=None, page=1, *,
                     limit=20, cache=None, no_cache=False):
    """→ {rows, total_matched, total_records, pages, page, params, _meta}.

    party rides the upstream searchString, q the global search[value];
    status/form_type pass through verbatim (order_status/form_type params;
    form I/II/III are the notification forms). GET — the POST answers 405
    (the DataTables default is GET here). 1,491 rows on 2026-11-16."""
    page_i = int(page) if page not in (None, "") else 1
    if page_i < 1:
        raise SdkError("usage_error", provider="in_cci",
                       detail=f"page is 1-based, got {page!r}")
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="in_cci",
                       detail=f"limit must be 1-100 (upstream DataTables length), got {limit!r}")
    from ..transport import call_provider

    start = (page_i - 1) * size

    def _fire(sess):
        p = _dt_frame(q, start, size, sess["token"], _CB_COLS,
                      {"form_type": form_type or "", "order_status": status or "",
                       "searchString": party or "", "search_type": "",
                       "fromdate": "", "todate": ""})
        return call_provider(provider, "comb", p, cache=cache, no_cache=no_cache,
                             extra_headers=_xhr_headers(sess, accept_json=True))

    sess_key = ("comb_form", "https://www.cci.gov.in/combination/orders-section31")
    try:
        r = _fire(_session(*sess_key, cache, no_cache))
    except SdkError as e:
        if getattr(e, "status", None) != 419:
            raise
        r = _fire(_session(*sess_key, cache, no_cache=True))
    doc = r["data"] or {}
    rows = _parse_rows(doc.get("data"))
    needle = str(party or "").strip().lower() or None
    needle_st = str(status or "").strip().lower() or None
    needle_ft = str(form_type or "").strip().upper() or None
    hits = [x for x in rows
            if (not needle or needle in str(x.get("party_name") or "").lower())
            and (not needle_st or needle_st in str(x.get("order_status") or "").lower())
            and (not needle_ft or needle_ft == str(x.get("form_type") or "").upper())]
    total = int(doc.get("recordsTotal") or 0)
    return {
        "rows": hits[:size],
        "total_matched": len(hits),
        "total_records": total,
        "pages": (total + size - 1) // size or None,
        "page": page_i,
        "register": "combination notifications under Competition Act 2002 s.6(2) / s.31 (1,491 rows on 2026-11-16)",
        "params": {"party": party or None, "status": status or None,
                   "form_type": form_type or None, "q": q or None,
                   "page": page_i, "limit": size},
        "_meta": r,
    }
