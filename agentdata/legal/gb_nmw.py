"""gb_nmw — UK National Minimum Wage naming-scheme rounds (gov.uk press releases; keyless).

legal enforcement face (0.3.64, batch E6; admitted from research booklet 101 naming-schemes,
probed live 2026-11-16 tmp/probe-e6/ nmw_s1/s2/h1). The "named and shamed" register: BEIS/
DBT-HMRC publish each round as a press release whose attachment is THE official list
(Round 22 = 492 employers × 15 columns: employer/trading names, postcode + region + local
authority + constituency, three-tier official ONS SIC industry coding, arrears £, workers,
arrears period). The rounds index is the gov.uk search API pinned to the scheme:
GET /api/search.json?q="named and shamed" "minimum wage"&order=-public_timestamp
       &filter_format=press_release
  → 41 results live (Round 22 2026-01-19 newest; the full history 2013→2026 walks back
    through start= offsets — the recipe's Round 1-22 back-trail lives on this same query).
**The content API body is EMPTY for these pages** (attachments only live in the HTML page,
booklet 101 pit) — the round detail op therefore fetches the rendered page and extracts the
asset coordinates: assets.publishing.service.gov.uk/.../Round_22_NMW_Naming_Scheme__List_
of_employers_as_of_16_October.xlsx (91.6KB, 2 sheets). Per the EUASL precedent the SDK face
is the COORDINATE surface — the xlsx bodies ride the batch line, never the JSON face.
Attachment names carry no year suffix (…_16_October.xlsx, not …_16_October_2025.xlsx —
hand-assembling them 404s with a 41B JSON body; only extracted hrefs are truth).
Slug collision pit (booklet 101): gov.uk redirects the 2018 "nearly-200" slug to the older
"nearly-180" release — the search row's link is the truth, never a remembered slug.
TTL: rounds 24h (≈2 rounds/year — the index barely moves) / round 7d; polite rate 1 rps
(gov.uk publishes no search-API quota — conservative, same family as gb_mhra/gb_cma).
"""
import re

from ..errors import SdkError

provider = {
    "id": "gb_nmw",
    "baseUrl": "https://www.gov.uk",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        # q/order/filter_format are fixed for this face; count/start go through verbatim
        "rounds": {"path": "/api/search.json"},
        # slug = the tail of the press-release base_path (the search row's link)
        "round": {"path": "/government/news/{slug}", "accept": "text"},
    },
    "ttl": {"rounds": 24 * 3600, "round": 7 * 86400},
}

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

# the scheme's own discovery query — pinned verbatim (quoted phrases, two terms)
_PINNED_Q = '"named and shamed" "minimum wage"'

_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
_OGTITLE_RE = re.compile(r'property="og:title" content="([^"]*)"')
_DESC_RE = re.compile(r'<meta name="description" content="([^"]*)"')
_PUB_RE = re.compile(r'property="article:published_time" content="([^"]+)"')
_UPD_RE = re.compile(r'property="article:modified_time" content="([^"]+)"')
_XLSX_RE = re.compile(r'(https://assets\.publishing\.service\.gov\.uk/[^"\']+?\.xlsx)', re.I)


def rounds_from_upstream(data, size):
    """Upstream search response → round rows (pure function, offline-testable)."""
    rows = [{
        "slug": ((r.get("link") or r.get("_id") or "").removeprefix("/government/news/") or None),
        # ^ join key into the round detail face (link and _id are both the base_path here)
        "title": r.get("title"),                       # "£6 million repaid to workers as Government cracks down…"
        "public_timestamp": r.get("public_timestamp"),  # the round's publication date
        "description": (r.get("description") or "").strip() or None,
        "organisations": [o.get("title") for o in (r.get("organisations") or []) if o.get("title")],
        "url": ("https://www.gov.uk" + p) if (p := (r.get("link") or r.get("_id"))) else None,
    } for r in ((data or {}).get("results") or [])]
    return {
        "rows": rows, "count": len(rows), "limit_applied": size,
        "total": data.get("total") if isinstance(data, dict) and isinstance(data.get("total"), int) else None,
    }


def rounds_raw(*, count=20, start=0, cache=None, no_cache=False):
    """Flat-panel low-level face: the naming-scheme rounds index, newest round first
    (q/order/filter_format pinned — this is the register's own discovery query).

    → {rows[], count, limit_applied, total, params, _meta}. count politeness wall 1-100
    (gov.uk family cap); start = offset paging — Round 1 (2013) walks back at start=30+.
    41 results live 2026-11-16; not every hit is a numbered round (spring-rate reminders
    and underpayment-statistics releases ride the same query — the titles tell them apart,
    recorded verbatim rather than guessed)."""
    from ..transport import call_provider

    size = int(count) if count is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="gb_nmw",
                       detail=f"count must be 1-100 (politeness cap; the gov.uk search API publishes "
                              f"no quota — same family cap as gb_mhra/gb_cma), got \"{count}\"")
    off = int(start) if start is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="gb_nmw", detail=f"start must be an offset ≥0, got \"{start}\"")
    params = {"q": _PINNED_Q, "order": "-public_timestamp",
              "filter_format": "press_release", "count": size, "start": off}
    r = call_provider(provider, "rounds", params, cache=cache, no_cache=no_cache)
    return {**rounds_from_upstream(r["data"], size), "params": params, "_meta": r}


def _clean_slug(slug):
    s = str(slug or "").strip()
    # Tolerance: a pasted full base_path or URL gets its prefix stripped
    for pre in ("https://www.gov.uk/government/news/", "http://www.gov.uk/government/news/",
                "/government/news/"):
        if s.startswith(pre):
            s = s[len(pre):]
    s = s.strip("/")
    if not s or "/" in s:
        raise SdkError("usage_error", provider="gb_nmw",
                       detail=f"slug must be the press-release tail segment (e.g. 6-million-repaid-to-workers-"
                              f"as-government-cracks-down-on-employers-underpaying-their-staff, echoed verbatim "
                              f"from the rounds row's slug field — a remembered slug may collide with gov.uk's "
                              f"own redirects): {slug}")
    return s


def round_raw(slug, *, cache=None, no_cache=False):
    """→ the single-round dossier: the press-release page and its attachment coordinates.

    The named-employers list itself is an xlsx attachment — per the EUASL precedent this
    face returns its URL (assets.publishing.service.gov.uk), never the bytes. rows:
    {slug, title, description, published, updated, xlsx_urls[] (unique, page order),
    body_xlsx_count, url}. A round page with no xlsx (rate-reminder releases) answers
    xlsx_urls=[] honestly — the numbered-round lists are the ones that carry one."""
    from ..transport import call_provider

    s = _clean_slug(slug)
    r = call_provider(provider, "round", {"slug": s}, cache=cache, no_cache=no_cache,
                      extra_headers=_BROWSER_HEADERS)
    body = r["data"] or ""
    if not isinstance(body, str) or "<html" not in body[:400].lower():
        raise SdkError("upstream_unavailable", provider="gb_nmw",
                       detail="the press-release page answered non-HTML "
                              "(shape drift, or the slug missed)")

    xlsx = []
    for m in _XLSX_RE.finditer(body):
        if m.group(1) not in xlsx:
            xlsx.append(m.group(1))
    title = (_OGTITLE_RE.search(body) or _TITLE_RE.search(body))
    desc = _DESC_RE.search(body)
    pub = _PUB_RE.search(body)
    upd = _UPD_RE.search(body)

    return {
        "slug": s,
        "title": title.group(1).strip() if title else None,
        "description": desc.group(1).strip() if desc else None,
        "published": pub.group(1) if pub else None,
        "updated": upd.group(1) if upd else None,
        "xlsx_urls": xlsx,              # the official named-employers list(s) — Round_XX_NMW_Naming_Scheme…xlsx
        "url": f"https://www.gov.uk/government/news/{s}",
        "_meta": r,
    }
