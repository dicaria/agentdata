"""ungm — UN Global Marketplace contract-award search provider (www.ungm.org/Public/ContractAward; keyless).

procurement register (admitted in 0.3.12; shapes verified by first-hand live probing). Probed live 2026-10-30
(the XHR contract reverse-engineered from bundles/ungmcommon; the two-step pairing walked end to end):
GET /Public/ContractAward (**a browser UA is mandatory** — the default agentdata UA is refused with a 403
(a 134-byte 403 stub; same UA-fingerprint gate family as FAA; any full browser UA passes)) → two Set-Cookie
pieces (the __RequestVerificationToken session cookie + GCLB) + the same-named token in a hidden field on
the page (the pairing key).
POST /Public/ContractAward/PublicSearch (JSON body = the browser buildOptions() **full 15-field shape**;
carries the Cookie + RequestVerificationToken header pair) → HTML row family back (each row keyed by
data-contractawardid + six slots: title/vendor/award_date/agency/reference/supplier_country) + a trailing
script `#searchTotal").html(N)` total echo. A bare POST without the pairing = 400; **a null SortField = 500
server crash** (pinned live 2026-10-30 — the request body must be the full shape and SortField never empty).
Full corpus ~50,035 awards (Supplier/AwardFrom/AwardTo/Countries/Agencies/UNSPSCs filters;
PageSize 1-100 with the browser at 15/page, PageIndex 1-based paging).
The anti-forgery pairing (cookie × token) is cached 15 minutes and reused; 400 = the pairing expired —
re-collected once automatically.
TTL: published awards are immutable — 7d; polite tier 0.5 rps (conservative pick; the UN portal publishes no quota).
"""
import html as _html
import re

from ..errors import SdkError

provider = {
    "id": "ungm",
    "baseUrl": "https://www.ungm.org",
    "rate": {"rps": 0.5, "burst": 1},
    "ops": {
        "search_page": {"path": "/Public/ContractAward", "accept": "text"},
        "search": {"path": "/Public/ContractAward/PublicSearch", "method": "POST",
                   "idempotent": True, "accept": "text"},
    },
    "ttl": {"search": 7 * 24 * 3600},
}

# UA fingerprint gate (pinned live 2026-10-30): curl/python default UAs get 403; full browser UAs get 200 — per-request header override (ext 8)
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

_SESSION_TTL = 15 * 60  # anti-forgery pairing reuse window (the same pairing is reusable within the ASP.NET session lifetime)

_TOKEN_FIELD = re.compile(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"')
_ROW_SPLIT = re.compile(r'<div role="row"[^>]*data-contractawardid="(\d+)"')
_SPAN = re.compile(r"<span[^>]*>(.*?)</span>", re.S)
_TAGWS = re.compile(r"<[^>]+>|\s+")
_TOTAL = re.compile(r'#searchTotal"\)\.html\((\d+)\)')


def _cell_text(chunk):
    """cell block -> the first span's text (tags stripped + entities unescaped + whitespace collapsed; an empty slot = None — e.g. rows carrying no reference)."""
    m = _SPAN.search(chunk)
    if not m:
        return None
    return _html.unescape(_TAGWS.sub(" ", m.group(1))).strip() or None


def awards_from_upstream(text):
    """search-page HTML -> {rows[], total, count} (a pure function, testable offline).

    The row's six slots (stable role=cell order): title/vendor/award_date/agency/reference/supplier_country."""
    rows = []
    parts = _ROW_SPLIT.split(text or "")
    for rid, block in zip(parts[1::2], parts[2::2]):
        cells = [_cell_text(c) for c in block.split('<div role="cell"')[1:]]
        c = (cells + [None] * 6)[:6]
        rows.append({"id": rid, "title": c[0], "vendor": c[1], "award_date": c[2],
                     "agency": c[3], "reference": c[4], "supplier_country": c[5]})
    m = _TOTAL.search(text or "")
    return {"rows": rows, "total": int(m.group(1)) if m else None, "count": len(rows)}


def _session(cache, no_cache=False):
    """-> (cookie_hdr, token): the anti-forgery pairing — cached 15 minutes and reused; on miss, collected by GETting the search page."""
    if not no_cache and cache is not None:
        hit = cache.get("ungm", "antiforgery_session", _SESSION_TTL)
        if hit:
            return hit["payload"]["cookie"], hit["payload"]["token"]
    from ..transport import call_provider
    r = call_provider(provider, "search_page", {}, cache=cache, no_cache=True,
                      extra_headers={"User-Agent": _BROWSER_UA,
                                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    m = _TOKEN_FIELD.search(r["data"] or "")
    if not m or not r.get("set_cookie"):
        raise SdkError("upstream_unavailable", provider="ungm",
                       detail="bootstrap did not obtain the anti-forgery pairing (page token/session cookie missing) — the upstream page shape may have changed")
    pair = {"cookie": "; ".join(sc.split(";", 1)[0].strip() for sc in r["set_cookie"]),
            "token": m.group(1)}
    if cache is not None:
        cache.set("ungm", "antiforgery_session", pair, _SESSION_TTL)
    return pair["cookie"], pair["token"]


def awards_raw(supplier=None, *, title=None, reference=None, award_from=None, award_to=None,
               countries=None, agencies=None, unspscs=None, page_index=1, page_size=15,
               sort_field="AwardDate", sort_ascending=False, cache=None, no_cache=False):
    """-> {rows[], total, count, params, _meta} (params = the JSON body actually sent — replayable).

    Filter params mirror the upstream names (Supplier/Title/Reference/AwardFrom/AwardTo/Countries/Agencies/UNSPSCs);
    page_index is 1-based / page_size 1-100 (the browser uses 15/page); sort_field defaults to AwardDate
    (null = upstream 500, never empty)."""
    from ..transport import call_provider

    idx = int(page_index) if page_index is not None else 1
    if idx < 1:
        raise SdkError("usage_error", provider="ungm",
                       detail=f"page_index must be >=1 (1-based), got {page_index!r}")
    size = int(page_size) if page_size is not None else 15
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="ungm",
                       detail=f"page_size must be 1-100 (politeness cap; the browser uses 15/page), got {page_size!r}")
    # request body = the browser buildOptions() full shape: missing keys/empty values can each trigger a
    # server-side exception (pinned: a null SortField = 500)
    params = {
        "PageIndex": idx, "PageSize": size,
        "Title": title or "", "Description": "", "Reference": reference or "",
        "Supplier": supplier or "", "UngmNumber": "",
        "AwardFrom": award_from or "", "AwardTo": award_to or "",
        "Countries": list(countries or []), "SupplierCountries": [],
        "Agencies": list(agencies or []), "UNSPSCs": list(unspscs or []),
        "SortField": sort_field or "AwardDate", "SortAscending": bool(sort_ascending),
    }
    cookie, token = _session(cache, no_cache)
    hdrs = {"User-Agent": _BROWSER_UA, "Cookie": cookie, "RequestVerificationToken": token}
    try:
        r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache,
                          extra_headers=hdrs)
    except SdkError as e:
        # 400 = the anti-forgery pairing expired (session cookie invalidated) — drop the cached pairing,
        # re-collect once and resend; still 400 → raise as-is
        if e.status != 400 or no_cache:
            raise
        cookie, token = _session(None)  # force re-collection (bypassing the cached pairing)
        r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache,
                          extra_headers={"User-Agent": _BROWSER_UA, "Cookie": cookie,
                                         "RequestVerificationToken": token})
    return {**awards_from_upstream(r["data"]), "params": params, "_meta": r}
