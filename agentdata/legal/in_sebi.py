"""in_sebi — Securities and Exchange Board of India enforcement orders (www.sebi.gov.in/sebiweb;
the legal domain's first IN face; research volume in-sebi-orders, 册 231; face admitted in 0.3.35,
probed first-hand 2026-11-04 tmp/probe-legal-0335/ with the SDK's own polite UA, direct).

One face — orders. The public listing (GET HomeAction.do?doListing=yes) renders 25 rows/page but
IGNORES GET paging params — the working channel is the stateless AJAX fragment the page itself
uses: POST /sebiweb/ajax/home/getnewslistinfo.jsp with the site's full 16-field form body
(missing fields were claimed to break it; pinned 2026-11-04: dropping smText still answers the
same 25 rows — the body is sent complete regardless, belt and braces). One uniform channel shape
serves every case: next="n" + doDirect=<zero-based page> + the filter set in the same body
(ip1 i1/i2/i3/i4/i7, ip2 r1/r1b, ip3 r3 — next="s" is the site's fresh-search marker and IGNORES
doDirect; it is never needed). The fragment answers: hidden inputs first (totalpage UNQUOTED
value=258, nextDel = page size 25 or 0, nextValue = the 1-based echo), the footer
"<p>&nbsp;1 to 25 of 6433 records</p>", <tr role='row'> rows (Date + Title/href), then #@# and
a breadcrumb whose active page re-states the category name.

Behaviours (pinned 2026-11-04): 11 category walls (smid 1/2/3/146/4/5/6/7/77/133/138, official
names verbatim — routing proven on smid 2 = 6,433 and smid 6 = 12,020); search is the site's own
entity filter ("Adani" → 17 records); fromDate/toDate are DD-MM-YYYY (a 2026-10 window → 5
records); a page past the last answers the clean empty page "<p>No record(s) available.</p>"
with nextDel=0 (NOT a snap-back — unlike kz_gbd_ul); rows are date (verbatim "Nov 03, 2026") +
title + the order PDF url.

Rate: sebi.gov.in publishes no window -> polite 0.5 rps / burst 2 (the registry-search family
posture; the same host is shared with in_sebi_intm via the host-layer bucket). TTL: 12h.
"""
import html
import re

from ..errors import SdkError

provider = {
    "id": "in_sebi",
    "baseUrl": "https://www.sebi.gov.in",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # the AJAX fragment channel: form-urlencoded POST, the HTML fragment parsed here
        "search": {"path": "/sebiweb/ajax/home/getnewslistinfo.jsp", "method": "POST",
                   "urlencoded": True, "accept": "text", "idempotent": True, "timeout": 60.0},
    },
    "ttl": {"search": 12 * 3600},
}

# the 11 order categories (the listing page's own links, labels verbatim — orders.html)
# slug -> (smid, official category name that must ride smText)
CATEGORIES = {
    "sat_orders": (1, "Orders of SAT"),
    "member_orders": (2, "Orders of Chairperson/Members"),
    "settlement_board": (3, "Settlement Orders passed by the Board"),
    "settlement_court": (146, "Settlement Orders passed by the Tribunal or Court"),
    "rti_aa": (4, "Orders of AA under the RTI Act"),
    "schemes": (5, "Orders of Corporatisation / Demutualisation Scheme"),
    "ao_orders": (6, "Orders of AO"),
    "court_orders": (7, "Orders of Courts"),
    "special_courts": (77, "Orders Of Special Courts"),
    "quasi_judicial": (133, "Orders of ED / CGM (Quasi-Judicial Authorities)"),
    "regulation_30a": (138, "Orders under Regulation 30A of the SEBI (Intermediaries) Regulations, 2008"),
}

_LISTING_URL = ("https://www.sebi.gov.in/sebiweb/home/HomeAction.do"
                "?doListing=yes&sid=2&ssid=9&smid=2")

_AJAX_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": _LISTING_URL,
    "Origin": "https://www.sebi.gov.in",
}

_DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")   # upstream format: DD-MM-YYYY
_ROW_RE = re.compile(r"<tr role='row' class='(?:odd|even)'>\s*<td>([^<]+)</td>\s*<td>\s*"
                     r"<a href='([^']+)'[^>]*class='points'[^>]*>\s*([^<]*)</a>")
_FOOTER_RE = re.compile(r"<p>&nbsp;(\d+) to (\d+) of (\d+) records</p>")
_TOTALPAGE_RE = re.compile(r"name='totalpage'\s+value=[\"']?(\d+)")
_EMPTY_RE = re.compile(r"<p>No record\(s\) available\.</p>")


def _norm(category, search, from_date, to_date, page):
    if category not in CATEGORIES:
        raise SdkError("usage_error", provider="in_sebi",
                       detail=f"category must be one of {sorted(CATEGORIES)} (the 11 order "
                              f"categories of sebi.gov.in/sebiweb), got {category!r}")
    q = str(search).strip() if search not in (None, "") else None
    if q and len(q) > 200:
        raise SdkError("usage_error", provider="in_sebi",
                       detail=f"search is the site's own entity filter with maxlength 200, got {len(q)} chars")
    dates = {}
    for name, v in (("fromDate", from_date), ("toDate", to_date)):
        if v in (None, ""):
            continue
        s = str(v).strip()
        if not _DATE_RE.match(s):
            raise SdkError("usage_error", provider="in_sebi",
                           detail=f"{name} must be DD-MM-YYYY (the upstream form's own format), got {v!r}")
        dates[name] = s
    try:
        p = int(page)
    except (TypeError, ValueError):
        p = 0
    if p < 1:
        raise SdkError("usage_error", provider="in_sebi",
                       detail=f"page must be >=1 (1-based; upstream doDirect = page-1), got {page!r}")
    return q, dates, p


def orders_raw(category="member_orders", *, search=None, from_date=None, to_date=None,
               page=1, cache=None, no_cache=False):
    """-> {rows, total, pages, page, count, has_more, category, category_name, params, _meta};
    rows are {date (verbatim "Nov 03, 2026"), title, url (the order PDF)}.

    One stateless POST per page (next="n" + doDirect=page-1 + the full 16-field body — the
    channel the site's own pager uses). A page past the last answers the clean empty page
    ("No record(s) available.", nextDel=0) — total is then None, has_more False."""
    from ..transport import call_provider

    q, dates, p = _norm(category, search, from_date, to_date, page)
    smid, sm_text = CATEGORIES[category]
    params = {
        "nextValue": "1", "search": q or "", "fromDate": dates.get("fromDate", ""),
        "toDate": dates.get("toDate", ""), "fromYear": "", "toYear": "",
        "deptId": "0", "sid": "2", "ssid": "9", "smid": str(smid), "ssidhidden": "9",
        "intmid": "-1", "sText": "Enforcement", "ssText": "Orders", "smText": sm_text,
        "next": "n", "doDirect": str(p - 1),
    }
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache,
                      extra_headers=_AJAX_HEADERS)
    text = r["data"] or ""
    rows = [{"date": d.strip(), "title": html.unescape(t).strip(), "url": u}
            for d, u, t in _ROW_RE.findall(text)]
    foot = _FOOTER_RE.search(text)
    total = int(foot.group(3)) if foot else None
    tp = _TOTALPAGE_RE.search(text)
    pages = int(tp.group(1)) if tp else None
    if not foot and not _EMPTY_RE.search(text) and "<tr role='row'" not in text:
        raise SdkError("upstream_unavailable", provider="in_sebi",
                       detail="the AJAX fragment carried neither rows nor the empty marker nor the "
                              "records footer — the upstream shape may have changed")
    return {
        "rows": rows,
        "total": total,
        "pages": pages,
        "page": p,
        "count": len(rows),
        "has_more": bool(pages is not None and p < pages),
        "category": category,
        "category_name": sm_text,
        "params": params,
        "_meta": r,
    }
