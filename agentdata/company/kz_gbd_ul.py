"""kz_gbd_ul — Kazakhstan GBD_UL legal-entities master register (data.egov.kz; the company
master register's 19th jurisdiction and first Central-Asian one; research volume kz-egov-gbd-ul,
册 209; face admitted in 0.3.34, probed first-hand 2026-11-04 tmp/probe-company-0334/).

One face — companies. GET /datasets/getdata?index=gbd_ul&version=v1&page=N&count=M[&text=…]
answers {"elements": [13-column rows], "totalCount", "totalPages", "currentPage"}; the columns
come in bilingual pairs (nameru/namekz, okedru/okedkz, statusru/statuskz, addressru/addresskz)
plus bin, datereg, director, id. bin is the 12-digit hard key (the register's own BIN); the
first ~1997 rows (the pre-BIN era, page 1 by datereg) carry bin "" — mapped to null, the
register's own statement. director is the register's public officer name (statutorily public,
same PII posture as co_rues representante_legal). Missing values arrive as "" (never null) —
all "" map to null.

Channel (pinned 2026-11-04, four probe rounds): **getdata answers an HTTP 404 stub without a
portal session** — a cookieless GET, cookies alone, or the header pair alone all 404 (t1-t13);
the working channel is GET /datasets/view?index=gbd_ul first (mints OPENDATA_PORTAL_SESSION +
cookiesession1), then getdata carrying the Cookie + X-Requested-With + Accept + Referer header
set (t12/t21). The session pairing is cached 15 minutes and reused; a 404 on getdata = the
pairing expired, re-collected once automatically.

Behaviours (pinned 2026-11-04): **count is hard-clamped to 20** (count=100 answers 20 rows —
walled here at 1-20 so the page math never lies); **column/order sort params are silently
ignored** (identical rows to the unsorted baseline, no error — not shipped); **a page past the
last silently snaps to the last page** (page=200199 at count=5 answered currentPage=200198 —
no empty-page signal; has_more therefore reads the ECHOED currentPage); **datereg is tri-modal**
("1997-05-26" bare / "2015-12-03+06:00" pre-2024 Almaty offset / "2026-11-03+05:00" post-2024
unified KZ offset — kept verbatim); duplicate rows with the same bin exist mid-corpus (the
register's own doubles). version=v1 is mandatory (missing = a Play 500 "null" — sent always).
totalCount drifts with the live register (1,000,786 at research time, 1,000,989 at probe time).

Rate: data.egov.kz publishes no window -> polite 0.5 rps / burst 2 (the registry-search family
posture). TTL: search 12h (the register is a live mirror of registration events).
"""
from ..errors import SdkError

provider = {
    "id": "kz_gbd_ul",
    "baseUrl": "https://data.egov.kz",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # the session bootstrap: an HTML page whose Set-Cookie pair is the getdata gate
        "dataset_page": {"path": "/datasets/view", "accept": "text", "timeout": 40.0},
        "search": {"path": "/datasets/getdata", "timeout": 40.0},
    },
    "ttl": {"search": 12 * 3600},
}

_COUNT_CAP = 20  # the upstream's own hard clamp (count=100 answers 20 rows — pinned live)
_SESSION_TTL = 15 * 60  # the portal-session pairing reuse window (ungm antiforgery posture)

_DATASET_URL = "https://data.egov.kz/datasets/view?index=gbd_ul"

# the header set the portal's own XHR carries (t12: cookies WITHOUT these still 404)
_XHR_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": _DATASET_URL,
}


def _session(cache, no_cache=False):
    """-> the Cookie header value: the portal-session pairing, cached 15 minutes and reused;
    on miss, collected by GETting the dataset page (its Set-Cookie pair is the getdata gate)."""
    if not no_cache and cache is not None:
        hit = cache.get("kz_gbd_ul", "portal_session", _SESSION_TTL)
        if hit:
            return hit["payload"]["cookie"]
    from ..transport import call_provider
    r = call_provider(provider, "dataset_page", {"index": "gbd_ul"},
                      cache=cache, no_cache=True, extra_headers={"Accept": "text/html"})
    if not r.get("set_cookie"):
        raise SdkError("upstream_unavailable", provider="kz_gbd_ul",
                       detail="bootstrap did not obtain the portal session (no Set-Cookie on the "
                              "dataset page) — the upstream page shape may have changed")
    cookie = "; ".join(sc.split(";", 1)[0].strip() for sc in r["set_cookie"])
    if cache is not None:
        cache.set("kz_gbd_ul", "portal_session", {"cookie": cookie}, _SESSION_TTL)
    return cookie


def _norm_paging(page, count):
    p = 1 if page in (None, "") else int(page)
    n = 20 if count in (None, "") else int(count)
    if p < 1:
        raise SdkError("usage_error", provider="kz_gbd_ul",
                       detail=f"page must be >=1 (1-based), got {page!r}")
    if n < 1 or n > _COUNT_CAP:
        raise SdkError("usage_error", provider="kz_gbd_ul",
                       detail=f"count must be 1-{_COUNT_CAP} (the upstream's own hard clamp: "
                              f"count=100 answers 20 rows — pinned live 2026-11-04), got {count!r}")
    return p, n


def _map_row(raw):
    """One register row -> the flat row. The upstream's bilingual column names travel verbatim
    (nameru/ namekz/ okedru/ okedkz/ statusru/ statuskz/ addressru/ addresskz); missing values
    arrive as "" and map to null — nothing is invented."""
    def s(k):
        v = raw.get(k)
        return v if v not in (None, "") else None
    return {
        "bin": s("bin"),
        "nameru": s("nameru"),
        "namekz": s("namekz"),
        "okedru": s("okedru"),
        "okedkz": s("okedkz"),
        "statusru": s("statusru"),
        "statuskz": s("statuskz"),
        "addressru": s("addressru"),
        "addresskz": s("addresskz"),
        "director": s("director"),
        "datereg": s("datereg"),   # verbatim: bare date | +06:00 (pre-2024) | +05:00 (unified KZ)
        "id": s("id"),
    }


def companies_raw(text=None, *, page=1, count=20, cache=None, no_cache=False):
    """-> {rows, total, pages, page, count, has_more, params, _meta}; rows are flat records.

    text is the register's own server-side name filter (upstream param: text; total reflects the
    filtered count); omit it for the whole register. A page past the last silently snaps to the
    last page upstream — has_more reads the echoed currentPage, so page is the page the register
    actually served."""
    from ..transport import call_provider

    p, n = _norm_paging(page, count)
    q = str(text).strip() if text is not None else None
    params = {"index": "gbd_ul", "version": "v1", "page": p, "count": n}
    if q:
        params["text"] = q
    cookie = _session(cache, no_cache)
    try:
        r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache,
                          extra_headers={**_XHR_HEADERS, "Cookie": cookie})
    except SdkError as e:
        # 404 = the session pairing expired (the cookieless stub answer — t1/t13) — drop the
        # cached pairing, re-collect once and resend; still 404 -> raise as-is
        if e.status != 404 or no_cache:
            raise
        cookie = _session(None)
        r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache,
                          extra_headers={**_XHR_HEADERS, "Cookie": cookie})
    doc = r["data"] or {}
    rows = [_map_row(x) for x in (doc.get("elements") or []) if isinstance(x, dict)]
    pages = doc.get("totalPages")
    cur = doc.get("currentPage")
    total = doc.get("totalCount")
    return {
        "rows": rows,
        "total": int(total) if isinstance(total, (int, float)) else None,
        "pages": int(pages) if isinstance(pages, (int, float)) else None,
        "page": int(cur) if isinstance(cur, (int, float)) else None,
        "count": len(rows),
        "has_more": bool(isinstance(cur, int) and isinstance(pages, int) and cur < pages),
        "text": q,
        "params": params,
        "_meta": r,
    }
