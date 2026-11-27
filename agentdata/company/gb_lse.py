"""gb_lse — London Stock Exchange universe + per-instrument registers + RNS
disclosure stream (apidata.londonstockexchange.com keyless REST,
www.londonstockexchange.com sitemap/article pages,
cache-api.lsegissuerservices.com issuer profiles; 0.3.76 batch E18).

2026-11-24 probed laws (tmp/probe-e18/; research volume company/uk-lse-apidata-universe.md, probe ancestry
tmp/probe-audit/r542/watch1123/uk/):
  - THE HEADER-FINGERPRINT GATE: the apidata REST family is keyless but the
    2026-11-23 probes showed missing Accept/Referer answering 403 "Missing
    Authentication Token" (the same text as the real key gate — add the
    browser headers BEFORE judging the door). The 2026-11-24 probe answered
    200 to a bare-UA request on the same face: the gate is INTERMITTENT, so
    the headers always ride (zero downside, no shape change either way).
  - THE ENVELOPE LAW: every apidata REST answer is
    {"statusCode": 200, "message": "Query executed successfully", "data": …}
    — the face unwraps `data`; a non-200 statusCode or a null data is surfaced
    honestly (never fabricated).
  - THE 200-EMPTY TRANSIENT LAW: the apidata family occasionally answers 200
    with a ZERO-BYTE body (three certifications on 2026-11-23: nrdp?tidm=0A00
    0B→932B, nrdp?tidm=01GT 0B→955B, securitybonddetails?tidm=01GT
    0B→1,149B — every one recovered on a plain re-visit). The REST faces
    therefore detect an empty payload and re-ask once, no-cache, before
    raising; an empty answer is NEVER read as a coverage boundary.
  - THE WWW DEGRADE-TRANSIENT LAW (live-certified 2026-11-24, probe5): the
    www pages degrade too — the article face answered a 200 page with the
    articleBody ABSENT through the SDK, then the full 165KB page minutes
    later under EVERY header combo incl. the SDK's own UA (the degrade is
    transient, not header-keyed on www). The www faces (universe/news_month/
    article) re-ask once no-cache on a degenerate payload (no <loc> / no
    articleBody) and the fresh answer overwrites a poisoned cache entry; a
    page that stays body-less is a genuinely removed article (honest miss).
  - RED LINE: the quote surfaces (rdp/v1/pricing order-book snapshot,
    instrument-summaries price, trade-summaries daily volumes, cmdf/v1/tmv
    market turnover, the fdc/token→samllogin→tns tick chain and the
    intraday/historical OHLCV bars) are MARKET-DATA surfaces — licensed
    goods, deliberately out of this module. Everything here is company-axis
    identity/index/issuer/disclosure data.
  - UNIVERSE: www sitemap-index declares five security books
    (security-{equity|bonds|etps|others|turquoise}.xml) totalling 62,713 quote
    pages (equity 5,761 on probe day); the quote-page URL
    /en/quote/{book}/{tidm}/{slug} IS the TIDM enumeration (UK tickers like
    BARC plus international 4-digit SEDOL forms like 0A00 — the LSE
    international order book).
  - NRDP MASTER: /nrdp/v1?tidm= carries the join-key card
    (instrumentId/isinCode/sedol/mic XLON|XLOM/issuerCode/firstTradingDate/
    segmentCode/typology/displayissuercode on international rows).
  - INDEX MEMBERSHIP: /cmdf/v1/ftseindexconstituents?tidm= answers THE
    INSTRUMENT's memberships as parallel comma lists (11 indexCode +
    indexName + indexWeight slots; an empty slot = not a member of that
    index) — parse with strict zip alignment, never positional guessing.
  - FUNDAMENTALS are keyed by RIC (BARC.L), hence the ric bridge face;
    international-book cards carry EUR figures.
  - RNS ARCHIVE WINDOW: sitemap-news-{yyyy-MM}.xml exists back to 2024-11
    (older months answer S3 AccessDenied 403) — the rolling ~25-month window
    is the historical-depth ceiling, documented, final. Current month
    35,272 URLs, full months ~44k-49k. The slug before the final hash
    segment is the RNS category (form-8-3 Takeover Code 1%+ disclosures ≈
    2,938/month, form-8-5 EPT ≈ 1,870/month, NAV, own-shares, …) — but the
    slug is a category-company melt ("form-8-3-direct-line-insurance-group-
    plc") and may contain extra path segments; NEVER read it as a company
    name.
  - RNS ARTICLE FULL TEXT: the article page embeds the complete disclosure
    body server-side as a JS string `articleBody="…"` (shadow-DOM render
    source) with \\x22 / \\uXXXX / \\/ escapes — decode before serving. The
    page metadata grid (rowheader/cell RichTextGrid rows) carries Company
    information / Released On / Source / RNS Number. The body carries ISINs
    (UK/IE issuers and NAV notes) — extracted, never guessed; US-target
    form-8-3 bodies carry none (the upstream's own absence, not a parsing
    miss).
  - ISSUER PROFILE: cache-api.lsegissuerservices.com/profile/{code} is the
    issuer's own IR card (instruments[] family with tidm+ISIN+type,
    admissiondate, sector/indices, contacts, reports/events). Coverage is
    ISSUER-OPTED (VOVOD = Vodafone's displayissuercode — NOT the ticker —
    answers 33 instruments; BASDE honest 404 {"message":""}) —
    iterate over nrdp displayissuercode to find carded issuers. The 403
    three-code law: "Forbidden" = unknown route (junk-path contrast),
    "Missing Authentication Token" = route known + face unregistered,
    404 = route known + issuer not registered.

Politeness 1 rps. TTLs: REST identity cards 1h (master/fundamentals/index),
static bridges 24h (ric/address/bond), universe sitemap 1h, news month 1h,
article 24h (immutable), profile 1h.
"""
import json
import re

from ..errors import SdkError

provider = {
    "id": "gb-lse",
    "baseUrl": "https://apidata.londonstockexchange.com",
    "rate": {"rps": 1.0, "burst": 1},
    "ops": {
        "nrdp": {"path": "/nrdp/v1?tidm={tidm}", "idempotent": True,
                 "accept": "text", "timeout": 60.0},
        "ric": {"path": "/rdp/v1/ric?tidm={tidm}", "idempotent": True,
                "accept": "text", "timeout": 60.0},
        "ftse": {"path": "/cmdf/v1/ftseindexconstituents?tidm={tidm}",
                 "idempotent": True, "accept": "text", "timeout": 60.0},
        "fundamentals": {"path": "/fundamentals/v1/lookup?ric={ric}",
                         "idempotent": True, "accept": "text", "timeout": 60.0},
        "address": {"path": "/issuer-address-website/v1?issuerCode={issuer_code}",
                    "idempotent": True, "accept": "text", "timeout": 60.0},
        "bond": {"path": "/cmdf/v1/securitybonddetails?tidm={tidm}",
                 "idempotent": True, "accept": "text", "timeout": 60.0,
                 "notFound": [404]},
        "universe": {"path": "https://www.londonstockexchange.com/en/sitemap-security-{book}.xml",
                     "idempotent": True, "accept": "text", "timeout": 120.0},
        "news_month": {"path": "https://www.londonstockexchange.com/en/sitemap-news-{month}.xml",
                       "idempotent": True, "accept": "text", "timeout": 120.0,
                       "notFound": [404]},
        "article": {"path": "https://www.londonstockexchange.com/en/news/article/{url}",
                    "idempotent": True, "accept": "text", "timeout": 90.0,
                    "path_safe": "/",  # the {url} tail carries category/hash slashes — quoting mangles the path (the TNA document_uri law, 0.3.7)
                    "notFound": [404]},
        "profile": {"path": "https://cache-api.lsegissuerservices.com/profile/{code}",
                    "idempotent": True, "accept": "text", "timeout": 60.0,
                    "notFound": [404]},
    },
    "ttl": {"nrdp": 3600, "ric": 86400, "ftse": 3600, "fundamentals": 3600,
            "address": 86400, "bond": 86400, "universe": 3600,
            "news_month": 3600, "article": 86400, "profile": 3600},
}

_REFERER = "https://www.londonstockexchange.com/en"
_HEADERS_REST = {"Referer": _REFERER}  # Accept: application/json rides the transport default
_HEADERS_PAGE = {"Referer": _REFERER, "Accept": "*/*"}

BOOKS = ("equity", "bonds", "etps", "others", "turquoise")
_LOC = re.compile(r"<loc>([^<]+)</loc>")
_QUOTE_PAGE = re.compile(r"/en/quote/([a-z]+)/([^/]+)/([^/]+)/?$")
_MONTH_FLOOR = (2024, 11)  # the archive-depth ceiling: older months answer S3 AccessDenied
_ARTICLE_BODY = re.compile(r'articleBody="((?:[^"\\]|\\.)*)"')
_HEX_ESC = re.compile(r"\\x([0-9a-fA-F]{2})")
_UNI_ESC = re.compile(r"\\u([0-9a-fA-F]{4})")
_GRID_ROW = re.compile(r'role="rowheader"[^>]*>\s*<div>([^<]+)</div>.*?role="cell"[^>]*>(.*?)</div>',
                       re.S)
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}\d")
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _tidm_arg(tidm):
    t = str(tidm or "").strip().upper()
    if not t or len(t) > 8 or not re.fullmatch(r"[A-Z0-9.\-]+", t):
        raise SdkError("usage_error", provider="gb-lse",
                       detail=f"tidm must be the LSE ticker symbol (UK form BARC/VOD, international SEDOL form 0A00), got \"{tidm}\"")
    return t


def _month_arg(month):
    m = str(month or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}", m):
        raise SdkError("usage_error", provider="gb-lse",
                       detail=f"month must be yyyy-MM (e.g. 2026-10), got \"{month}\"")
    y, mo = int(m[:4]), int(m[5:7])
    if not 1 <= mo <= 12:
        raise SdkError("usage_error", provider="gb-lse",
                       detail=f"month must be yyyy-MM (e.g. 2026-10), got \"{month}\"")
    if (y, mo) < _MONTH_FLOOR:
        raise SdkError("usage_error", provider="gb-lse",
                       detail=(f"month {m} is behind the archive floor 2024-11 — the sitemap-news "
                               f"archive answers S3 AccessDenied 403 for older months; the rolling "
                               f"~25-month window is the historical-depth ceiling"))
    return m


def _decode_article_body(raw):
    s = _HEX_ESC.sub(lambda m: chr(int(m.group(1), 16)), raw)
    s = _UNI_ESC.sub(lambda m: chr(int(m.group(1), 16)), s)
    for esc, ch in (("\\/", "/"), ("\\n", "\n"), ("\\t", "\t"), ('\\"', '"'), ("\\'", "'")):
        s = s.replace(esc, ch)
    return s


def _observed_meta(note):
    """honest-404 meta: no response body, so the meta IS the observation
    (the nz_nzx law — observed_at the moment the 404 was seen, never fabricated)."""
    from datetime import datetime, timezone
    return {"from_cache": False, "fetched_at": datetime.now(timezone.utc).isoformat(),
            "note": note}


def _call_rest(op, params, what, *, cache, no_cache):
    """apidata REST round trip with the 200-empty transient retry: an empty
    payload is re-asked once no-cache before raising (the three-certification
    law — an empty 200 is a transient, never a coverage boundary). Returns
    (unwrapped data, transport meta) so the faces thread from_cache/fetched_at."""
    from ..transport import call_provider

    def ask(**kw):
        nc = kw.pop("no_cache", no_cache)  # the retry passes no_cache=True — pop, never double-bind
        return call_provider(provider, op, params, cache=cache, no_cache=nc, **kw)

    r = ask(extra_headers=_HEADERS_REST)
    text = r["data"] if isinstance(r.get("data"), str) else ""
    if not text.strip():
        r = ask(no_cache=True, extra_headers=_HEADERS_REST)
        text = r["data"] if isinstance(r.get("data"), str) else ""
    if not text.strip():
        raise SdkError("upstream_unavailable", provider="gb-lse",
                       detail=(f"the {what} answer came back EMPTY twice — the apidata family "
                               f"occasionally answers 200 with a zero-byte body (a transient, "
                               f"three times certified 2026-11-23, all recovered on re-visit); "
                               f"retry, never read it as a coverage boundary"))
    try:
        env = json.loads(text)
    except ValueError:
        raise SdkError("upstream_unavailable", provider="gb-lse",
                       detail=f"the {what} answer is not valid JSON — the envelope shape may have moved; re-probe")
    status = env.get("statusCode")
    if status != 200:
        raise SdkError("upstream_unavailable", provider="gb-lse", status=status,
                       detail=f"the {what} envelope carries statusCode {status}: {env.get('message') or '—'}")
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    return env.get("data"), meta


def _sitemap_locs(url, op, params, *, cache, no_cache, what):
    from ..transport import call_provider

    r = call_provider(provider, op, params, cache=cache, no_cache=no_cache,
                      extra_headers=_HEADERS_PAGE)
    text = r["data"] if isinstance(r.get("data"), str) else ""
    locs = _LOC.findall(text or "")
    if not locs:
        raise SdkError("upstream_unavailable", provider="gb-lse",
                       detail=f"the {what} sitemap carries no <loc> entries — the shape may have moved; re-probe")
    return locs


# ---------- faces ----------

def universe(*, book="equity", limit=None, cache=None, no_cache=False):
    """→ {book, total, rows[], params, _meta}; the quote-page sitemap is the
    TIDM enumeration (rows {book, tidm, slug, url}). --book one of
    equity|bonds|etps|others|turquoise (Σ62,713 pages across the five books;
    equity 5,761 probe day). --limit slices the display; the full count
    always rides result.total."""
    from ..transport import call_provider

    b = str(book or "equity").strip().lower()
    if b not in BOOKS:
        raise SdkError("usage_error", provider="gb-lse",
                       detail=f"book must be one of {'/'.join(BOOKS)}, got \"{book}\"")
    r = call_provider(provider, "universe", {"book": b}, cache=cache, no_cache=no_cache,
                      extra_headers=_HEADERS_PAGE)
    text = r["data"] if isinstance(r.get("data"), str) else ""
    locs = _LOC.findall(text or "")
    if not locs:
        # THE WWW DEGRADE-TRANSIENT LAW (live-certified on the article face
        # 2026-11-24): the www pages occasionally answer a degraded 200 —
        # re-ask once no-cache before judging (an empty sitemap is a transient,
        # never a coverage boundary)
        r = call_provider(provider, "universe", {"book": b}, cache=cache, no_cache=True,
                          extra_headers=_HEADERS_PAGE)
        text = r["data"] if isinstance(r.get("data"), str) else ""
        locs = _LOC.findall(text or "")
    if not locs:
        raise SdkError("upstream_unavailable", provider="gb-lse",
                       detail=(f"the {b} security sitemap carries no <loc> entries twice — "
                               f"a transient degrade or a shape move; retry, then re-probe"))
    rows = []
    for u in locs:
        m = _QUOTE_PAGE.search(u)
        if not m:
            continue  # a non-quote page inside the security book — keep the count honest, skip the row
        rows.append({"book": m.group(1), "tidm": m.group(2).upper(),
                     "slug": m.group(3), "url": u})
    out = {"book": b, "total": len(rows), "rows": rows, "params": {"book": b, "limit": limit},
           "_meta": {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}}
    if limit is not None:
        out["rows"] = rows[:int(limit)]
    return out


def security_master(*, tidm, cache=None, no_cache=False):
    """→ {found, tidm, card, _meta}; the nrdp join-key card
    (instrumentId/isinCode/sedol/mic/issuerCode/firstTradingDate/typology —
    the issuerCode feeds gb_lse_issuer_address, the displayissuercode feeds
    gb_lse_issuer_profile, the tidm feeds the ric bridge)."""
    from ..transport import call_provider

    t = _tidm_arg(tidm)
    data, meta = _call_rest("nrdp", {"tidm": t}, f"nrdp master {t}", cache=cache, no_cache=no_cache)
    if not data:
        return {"found": False, "tidm": t, "card": None, "params": {"tidm": t},
                "_meta": meta}
    card = dict(data) if isinstance(data, dict) else {"data": data}
    card["tidm"] = card.get("tidm") or t
    return {"found": True, "tidm": t, "card": card, "params": {"tidm": t},
            "_meta": meta}


def ric_lookup(*, tidm, cache=None, no_cache=False):
    """→ {found, tidm, ric, rrpsric, _meta}; the tidm→RIC bridge
    (BARC→BARC.L) that keys gb_lse_fundamentals."""
    from ..transport import call_provider

    t = _tidm_arg(tidm)
    data, meta = _call_rest("ric", {"tidm": t}, f"ric bridge {t}", cache=cache, no_cache=no_cache)
    ric = (data or {}).get("ric") if isinstance(data, dict) else None
    return {"found": bool(ric), "tidm": t, "ric": ric,
            "rrpsric": (data or {}).get("rrpsric") if isinstance(data, dict) else None,
            "params": {"tidm": t}, "_meta": meta}


def index_membership(*, tidm, cache=None, no_cache=False):
    """→ {found, tidm, total, rows[], card, _meta}; the instrument's FTSE
    memberships — indexCode/indexName/indexWeight are PARALLEL comma lists
    (an empty slot = not a member of that index); strict zip alignment, rows
    only for slots with a weight (the membership set). The full card rides
    result.card (primaryIndexName/constituentCode/countryOfRegistration)."""
    from ..transport import call_provider

    t = _tidm_arg(tidm)
    data, meta = _call_rest("ftse", {"tidm": t}, f"FTSE constituents {t}", cache=cache, no_cache=no_cache)
    if not data:
        return {"found": False, "tidm": t, "total": 0, "rows": [], "card": None,
                "params": {"tidm": t}, "_meta": meta}
    card = dict(data)
    codes = [c.strip() for c in str(card.get("indexCode") or "").split(",")]
    names = [c.strip() for c in str(card.get("indexName") or "").split(",")]
    weights = [c.strip() for c in str(card.get("indexWeight") or "").split(",")]
    n = max(len(codes), len(names), len(weights))
    if not (len(codes) == len(names) == len(weights)):
        raise SdkError("upstream_unavailable", provider="gb-lse",
                       detail=(f"indexCode/indexName/indexWeight length mismatch "
                               f"{len(codes)}/{len(names)}/{len(weights)} — the parallel-list "
                               f"shape may have moved; re-probe"))
    rows = [{"index_code": codes[i], "index_name": names[i] if i < len(names) else "",
             "index_weight": weights[i] if i < len(weights) else ""}
            for i in range(n) if i < len(codes) and codes[i]
            and i < len(weights) and weights[i]]
    return {"found": True, "tidm": t, "total": len(rows), "rows": rows,
            "card": card, "params": {"tidm": t}, "_meta": meta}


def fundamentals(*, ric, cache=None, no_cache=False):
    """→ {found, ric, row, _meta}; PE/EPS/free-float/outstanding/market-cap
    verbatim (market cap in m GBP for UK cards, m EUR for international-book
    cards — figures are the upstream's own strings, never re-unit-ed)."""
    from ..transport import call_provider

    r = str(ric or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9.\-]{2,20}", r):
        raise SdkError("usage_error", provider="gb-lse",
                       detail=f"ric must be the LSE RIC (BARC.L / 0A00.L; from gb_lse_ric_lookup), got \"{ric}\"")
    data, meta = _call_rest("fundamentals", {"ric": r}, f"fundamentals {r}", cache=cache, no_cache=no_cache)
    if not data:
        return {"found": False, "ric": r, "row": None, "params": {"ric": r}, "_meta": meta}
    return {"found": True, "ric": r, "row": dict(data), "params": {"ric": r}, "_meta": meta}


def issuer_address(*, issuer_code, cache=None, no_cache=False):
    """→ {found, issuer_code, row, _meta}; the issuer's registered address and
    website (issuerCode from the nrdp master card)."""
    from ..transport import call_provider

    c = str(issuer_code or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,10}", c):
        raise SdkError("usage_error", provider="gb-lse",
                       detail=f"issuer_code must be the nrdp issuerCode (e.g. BASDE), got \"{issuer_code}\"")
    data, meta = _call_rest("address", {"issuer_code": c}, f"issuer address {c}", cache=cache, no_cache=no_cache)
    if not data:
        return {"found": False, "issuer_code": c, "row": None,
                "params": {"issuer_code": c}, "_meta": meta}
    return {"found": True, "issuer_code": c, "row": dict(data),
            "params": {"issuer_code": c}, "_meta": meta}


def bond_details(*, tidm, cache=None, no_cache=False):
    """→ {found, tidm, card, _meta}; the security-details card
    (isin/sedol/listingDate/fullName/currencyCode/mifirIdentifierCode/
    maturityDate). LIVE REVERSAL 2026-11-24: the face answers EQUITY tidms
    too — BARC returns a full card with maturityDate null (the research
    doc's "equities answer 404" was wrong; securitybonddetails is the
    generic security card, not bonds-only). An unknown tidm answers the
    honest 404 → found=false."""
    from ..transport import call_provider

    t = _tidm_arg(tidm)
    try:
        data, meta = _call_rest("bond", {"tidm": t}, f"bond details {t}", cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code != "upstream_not_found":
            raise
        # honest 404: an unknown tidm answers 404 — the card is never fabricated
        data, meta = None, _observed_meta("honest 404 — no such instrument upstream")
    if not data:
        return {"found": False, "tidm": t, "card": None, "params": {"tidm": t}, "_meta": meta}
    return {"found": True, "tidm": t, "card": dict(data), "params": {"tidm": t}, "_meta": meta}


def rns_archive(*, month, category=None, limit=None, cache=None, no_cache=False):
    """→ {month, total, rows[], params, _meta}; one month's RNS article index
    (rows {url, category, hash}). The slug before the final hash segment is
    the RNS category (form-8-3 Takeover Code 1%+ disclosures ≈ 2,938/month,
    form-8-5 EPT ≈ 1,870/month, net-asset-value-s, transaction-in-own-shares,
    …) but it is a category-company MELT that may carry extra path segments —
    never read it as a company name. Archive floor 2024-11 (older months
    answer S3 AccessDenied 403 — refused locally before the request).
    --category substring-filter, --limit slices; the full count rides
    result.total."""
    from ..transport import call_provider

    m = _month_arg(month)
    try:
        r = call_provider(provider, "news_month", {"month": m}, cache=cache, no_cache=no_cache,
                          extra_headers=_HEADERS_PAGE)
    except SdkError as e:
        if e.code != "upstream_not_found":
            raise
        # honest 404: a future/gap month carries no sitemap — zero rows, never fabricated
        return {"month": m, "total": 0, "rows": [],
                "params": {"month": m, "category": category, "limit": limit},
                "_meta": _observed_meta(f"sitemap-news-{m} answers 404 — the month is not on the archive")}
    text = r["data"] if isinstance(r.get("data"), str) else ""
    locs = _LOC.findall(text or "")
    if not locs:
        # the www degrade-transient law (see universe) — re-ask once no-cache
        r = call_provider(provider, "news_month", {"month": m}, cache=cache, no_cache=True,
                          extra_headers=_HEADERS_PAGE)
        text = r["data"] if isinstance(r.get("data"), str) else ""
        locs = _LOC.findall(text or "")
    if not locs:
        raise SdkError("upstream_unavailable", provider="gb-lse",
                       detail=(f"sitemap-news-{m} carries no <loc> entries twice — a transient "
                               f"degrade or a shape move; retry, then re-probe"))
    prefix = "https://www.londonstockexchange.com/en/news/article/"
    rows = []
    for u in locs:
        if not u.startswith(prefix):
            continue
        tail = u[len(prefix):]
        cat, _, h = tail.rpartition("/")
        if not cat:
            continue
        rows.append({"url": u, "category": cat, "hash": h})
    if category:
        c = str(category).strip().lower()
        rows = [x for x in rows if c in x["category"].lower()]
    out = {"month": m, "total": len(rows), "rows": rows,
           "params": {"month": m, "category": category, "limit": limit},
           "_meta": {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}}
    if limit is not None:
        out["rows"] = rows[:int(limit)]
    return out


def rns_article(*, url, cache=None, no_cache=False):
    """→ {found, url, category, hash, metadata{}, title, body_html, body_chars,
    isins[], _meta}; the article page's server-embedded full disclosure body.
    --url the article URL verbatim from gb_lse_rns_archive rows (a bare
    category/hash tail also parses). The JS-string articleBody is decoded
    (\\x22/\\uXXXX/\\/ escapes); the metadata grid (Company information /
    Released On / Source / RNS Number) is parsed from the RichTextGrid
    rows; ISINs are extracted from the decoded body (UK/IE issuers and NAV
    notes carry them; US-target form-8-3 bodies legitimately carry none)."""
    from ..transport import call_provider

    u = str(url or "").strip()
    if u.startswith(("http://", "https://")):
        if "/en/news/article/" not in u:
            raise SdkError("usage_error", provider="gb-lse",
                           detail=f"url must be an LSE news article URL (from gb_lse_rns_archive), got \"{url}\"")
        tail = u.split("/en/news/article/", 1)[1]
    else:
        tail = u.lstrip("/")
        u = f"https://www.londonstockexchange.com/en/news/article/{tail}"
    if not tail or "/" not in tail:
        raise SdkError("usage_error", provider="gb-lse",
                       detail=f"url must be the article path \"{'{category}/{hash}'}\" (from gb_lse_rns_archive), got \"{url}\"")

    cat, _, h = tail.rpartition("/")
    try:
        r = call_provider(provider, "article", {"url": tail}, cache=cache, no_cache=no_cache,
                          extra_headers={"Referer": _REFERER, "Accept": "text/html"})
    except SdkError as e:
        if e.code != "upstream_not_found":
            raise
        # honest 404: a bad/removed url answers no page — the same miss shape as
        # a body-less 200, never fabricated
        return {"found": False, "url": u, "category": cat, "hash": h,
                "metadata": {}, "title": None, "body_html": None, "body_chars": 0,
                "isins": [], "params": {"url": url},
                "_meta": _observed_meta("honest 404 — no article page for this url")}
    text = r["data"] if isinstance(r.get("data"), str) else ""
    mb = _ARTICLE_BODY.search(text or "")
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    if not mb:
        # LIVE CERT 2026-11-24: the www article page occasionally answers a
        # degraded 200 with the articleBody absent (the probe minutes later
        # answered the full 165KB page under EVERY header combo incl. the SDK's
        # own UA — the degrade is transient, not header-keyed). Re-ask once
        # no-cache; the fresh answer overwrites a poisoned cache entry. A page
        # that stays body-less is a genuinely removed article (honest miss).
        r = call_provider(provider, "article", {"url": tail}, cache=cache, no_cache=True,
                          extra_headers={"Referer": _REFERER, "Accept": "text/html"})
        text = r["data"] if isinstance(r.get("data"), str) else ""
        mb = _ARTICLE_BODY.search(text or "")
        meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    if not mb:
        return {"found": False, "url": u, "category": cat, "hash": h,
                "metadata": {}, "title": None, "body_html": None, "body_chars": 0,
                "isins": [], "params": {"url": url}, "_meta": meta}
    body = _decode_article_body(mb.group(1))
    metadata = {}
    for lab, cell in _GRID_ROW.findall(text):
        val = _WS.sub(" ", _TAG.sub("", cell)).strip()
        metadata[_WS.sub(" ", lab).strip()] = val
    mt = re.search(r"<title>(.*?)</title>", body, re.S)
    title = _WS.sub(" ", mt.group(1)).strip() if mt else None
    return {"found": True, "url": u, "category": cat, "hash": h,
            "metadata": metadata, "title": title, "body_html": body,
            "body_chars": len(body), "isins": sorted(set(_ISIN.findall(body))),
            "params": {"url": url}, "_meta": meta}


def issuer_profile(*, code, cache=None, no_cache=False):
    """→ {found, code, profile, instruments, _meta}; the issuer's own IR card
    on cache-api.lsegissuerservices.com (instruments[] family with
    tidm+ISIN+type, admissiondate, sector/indices, contacts, reports/events).
    Coverage is ISSUER-OPTED: carded issuers (VOVOD = Vodafone — the
    displayissuercode is NOT the ticker) answer the full card, uncarded ones
    (BASDE) answer an honest 404 → found=false, never fabricated. --code the
    nrdp displayissuercode (VOVOD/AKXRM form)."""
    from ..transport import call_provider

    c = str(code or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,10}", c):
        raise SdkError("usage_error", provider="gb-lse",
                       detail=f"code must be the nrdp displayissuercode (e.g. VOD), got \"{code}\"")
    try:
        r = call_provider(provider, "profile", {"code": c}, cache=cache, no_cache=no_cache,
                          extra_headers=_HEADERS_REST)
    except SdkError as e:
        if e.code != "upstream_not_found":
            raise
        # honest 404: coverage is issuer-opted — an uncarded issuer answers 404
        # {"message":""}, never fabricated
        return {"found": False, "code": c, "profile": None, "instruments": [],
                "params": {"code": c},
                "_meta": _observed_meta("honest 404 — issuer not registered on the issuer-services cache")}
    text = (r.get("data") or "").strip() if isinstance(r.get("data"), str) else ""
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    if not text:
        # a genuinely uncarded issuer answers 404 (BASDE) — a 200 with an empty
        # body is the degrade-transient (the apidata law; re-ask once no-cache)
        r = call_provider(provider, "profile", {"code": c}, cache=cache, no_cache=True,
                          extra_headers=_HEADERS_REST)
        text = (r.get("data") or "").strip() if isinstance(r.get("data"), str) else ""
        meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    if not text:
        return {"found": False, "code": c, "profile": None, "instruments": [],
                "params": {"code": c}, "_meta": meta}
    try:
        prof = json.loads(text)
    except ValueError:
        raise SdkError("upstream_unavailable", provider="gb-lse",
                       detail="the issuer-profile answer is not valid JSON — the shape may have moved; re-probe")
    inst = prof.get("instruments") or []
    return {"found": True, "code": c, "profile": prof, "instruments": inst,
            "params": {"code": c}, "_meta": meta}
