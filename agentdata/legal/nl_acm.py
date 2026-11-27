"""nl_acm — Netherlands Authority for Consumers & Markets publication register
(www.acm.nl, keyless Drupal).

NL legal faces (0.3.62; admitted from the research booklet 132, 7.5 P0;
re-probed live 2026-11-16 tmp/probe-e4/ with the SDK's own polite UA — the
host serves the default Accept: application/json too, NO Accept wall):

CONTRACT:
  1. publications — the /nl/publicaties/ corpus BY SITEMAP (13,368 URLs,
     2003→2026). The list page's JS window does not widen (measured), so the
     sitemap IS the channel: /sitemap.xml is a 9-page index of itself
     (?page=1..9, ~2,000 URLs each, Drupal simple_sitemap urlset shape with
     per-URL <lastmod>). Rows carry doc_id (the /publicatie/{id}/ numeric),
     slug, url, lastmod; the slug taxonomy gives category tokens (concentratie
     2,263 / boete 457 / onderzoek 457 / kartel 175 / cbb ~159 / rechtbank
     ~118 — research-count pin, a heuristic word-boundary match over the
     slug, not an upstream field).
  2. publication — ONE publication detail page: the content-block field
     family Publicatiedatum / Publicatietype / Beslisdatum / Zaak (Zaaknummer
     + the /nl/zaak/{id} case link) / Partijen / Trefwoorden / Onderwerpen,
     Dutch labels verbatim + pdf_urls. doc_id = the numeric id from
     publications rows (resolved to its URL through the cached sitemap set);
     a full URL is also accepted.

LIVE LAWS (measured 2026-11-16, tmp/probe-e4/):
  - Partijen is a NESTED second <h3> INSIDE the Zaak content-block (the
    block carries <h3>Zaak</h3><div>Zaaknummer: <a /nl/zaak/{id}>…</a></div>
    <h3>Partijen</h3><div>…</div>): the parser pairs EVERY h3 in a block with
    the span up to the next h3, not just the first.
  - old publications ride /nl/publicaties/old_publication/{name}.pdf paths;
    pdf hrefs are collected verbatim from the detail body.
  - sitemap submap rows may lack <lastmod> (940 of 2,000 pairs matched in
    submap ?page=1) — a missing lastmod is a legal shape, kept null.

Politeness: 0.5/2 (a list call sweeps index + 9 submaps, all cached), TTL
12h sitemap / 72h detail (publications are append-mostly).
"""
import html as _html
import re

from ..errors import SdkError

provider = {
    "id": "nl_acm",
    "baseUrl": "https://www.acm.nl",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "sitemap": {"path": "/sitemap.xml", "accept": "text", "timeout": 45.0},
        "detail": {"path": "{url}", "accept": "text", "timeout": 45.0},
    },
    "ttl": {"sitemap": 12 * 3600, "detail": 72 * 3600},
}

_ACCEPT = {"Accept": "text/html,application/xhtml+xml,application/xml,*/*"}

# slug-token taxonomy (research booklet 132 pin; heuristic word-boundary match over the
# hyphen-joined slug — NOT an upstream field)
_CATEGORIES = {
    "concentratie": "concentratie", "boete": "boete", "onderzoek": "onderzoek",
    "kartel": "kartel", "cbb": "cbb", "rechtbank": "rechtbank",
}
_LOC = re.compile(r"<loc>(https://www\.acm\.nl/nl/publicaties/[^<]+)</loc>", re.S)
_LASTMOD = re.compile(r"<lastmod>([^<]+)</lastmod>", re.S)
_ID = re.compile(r"/publicatie/(\d+)/")


def parse_sitemap(text):
    """One submap page → [(url, lastmod|None)] for the /nl/publicaties/ corpus (pure function).

    The lastmod search window is CUT at the entry boundary (</url>) — a fixed
    400-char tail would bleed the NEXT entry's <lastmod> onto an entry that
    lacks one (the 0362 nail caught the bleed)."""
    out = []
    for m in _LOC.finditer(text):
        url = _html.unescape(m.group(1))
        tail = text[m.end():m.end() + 400]
        cut = tail.find("</url>")
        if cut != -1:
            tail = tail[:cut]
        lm = _LASTMOD.search(tail)
        out.append((url, lm.group(1) if lm else None))
    return out


def _submap_urls(index_text):
    """The index page's own submap list (sitemap.xml?page=1..N)."""
    urls = re.findall(r"<loc>(https://www\.acm\.nl/sitemap\.xml\?page=\d+)</loc>", index_text)
    return urls or ["https://www.acm.nl/sitemap.xml?page=1"]


def _fetch_all_publications(*, cache=None, no_cache=False):
    """Index + every submap → the whole publications corpus, newest-first. -> (rows, metas, n_submaps)."""
    from ..transport import call_provider

    r0 = call_provider(provider, "sitemap", {}, cache=cache, no_cache=no_cache,
                       extra_headers=_ACCEPT)
    subs = _submap_urls(r0["data"])
    rows, metas = [], [r0["_meta"] if "_meta" in r0 else r0]
    for sub in subs:
        page = re.search(r"page=(\d+)", sub)
        rs = call_provider(provider, "sitemap", {"page": page.group(1) if page else "1"},
                           cache=cache, no_cache=no_cache, extra_headers=_ACCEPT)
        for url, lm in parse_sitemap(rs["data"]):
            m = _ID.search(url)
            slug = url.rstrip("/").rpartition("/")[2]
            rows.append({"doc_id": m.group(1) if m else None, "slug": slug,
                         "url": url, "lastmod": (lm or None)})
        metas.append(rs["_meta"] if "_meta" in rs else rs)
    rows = {r["url"]: r for r in rows}.values()   # submap overlap guard
    rows = sorted(rows, key=lambda r: (r["lastmod"] or "", r["url"]), reverse=True)
    return list(rows), metas, len(subs)


def _category_of(slug):
    """Slug → the matched category token(s) (substring over the lowercased slug —
    the research taxonomy's own counting method, compounds included:
    kartelafspraken counts as kartel)."""
    low = slug.lower()
    return [c for c in _CATEGORIES if c in low]


def publications_raw(category=None, q=None, *, limit=20, cache=None, no_cache=False):
    """→ {rows[], total_matched, total_corpus, by_category, lastmod_min/max, submaps, params, _meta}."""
    if category not in (None, "") and category not in _CATEGORIES:
        raise SdkError("usage_error", provider="nl_acm",
                       detail=f"category must be one of {sorted(_CATEGORIES)} (slug-token heuristic), got {category!r}")
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="nl_acm",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    rows, metas, n_submaps = _fetch_all_publications(cache=cache, no_cache=no_cache)
    needle = str(q or "").strip().lower() or None
    by_cat = {}
    lm_all = []
    for r in rows:
        cats = _category_of(r["slug"])
        r["categories"] = cats
        for c in cats:
            by_cat[c] = by_cat.get(c, 0) + 1
        if r["lastmod"]:
            lm_all.append(r["lastmod"])
    hits = [r for r in rows
            if (not category or category in r["categories"])
            and (not needle or needle in r["slug"].lower())]
    return {
        "rows": hits[:size],
        "total_matched": len(hits),
        "total_corpus": len(rows),
        "by_category": by_cat,
        "lastmod_min": min(lm_all) if lm_all else None,
        "lastmod_max": max(lm_all) if lm_all else None,
        "submaps": n_submaps,
        "params": {"category": category or None, "q": needle, "limit": size},
        "_meta": metas[0],
    }


_BLOCK = '<div class="content-block">'
_H3 = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S)
_TAG = re.compile(r"<[^>]+>")


def _clean(s):
    return re.sub(r"\s+", " ", _html.unescape(_TAG.sub(" ", s))).strip()


def parse_detail(text):
    """Detail page → {title, fields{Dutch label → value}, zaak_id, pdf_urls} (pure function).
    Every h3 inside a content-block pairs with the span up to the next h3 (the
    Partijen-inside-Zaak nesting)."""
    title = None
    m = re.search(r"<title>(.*?)</title>", text, re.S)
    if m:
        title = _clean(m.group(1)).removesuffix(" | ACM").removesuffix(" | Autoriteit Consument & Markt")
    fields = {}
    for blk in text.split(_BLOCK)[1:]:
        chunk = blk.split("</section>")[0].split("<footer")[0]
        h3s = list(_H3.finditer(chunk))
        for i, h in enumerate(h3s):
            label = _clean(h.group(1))
            span = chunk[h.end(): h3s[i + 1].start() if i + 1 < len(h3s) else len(chunk)]
            val = _clean(span)
            if label and val:
                fields.setdefault(label, val)
    zaak = None
    m = re.search(r'href="/nl/zaak/(\d+)/?"', text)   # trailing slash tolerated
    if m:
        zaak = m.group(1)
    pdfs = sorted(set(_html.unescape(u) for u in re.findall(r'href="([^"]+\.pdf[^"]*)"', text)))
    return {"title": title, "fields": fields, "zaak_id": zaak, "pdf_urls": pdfs}


def publication_raw(doc_id=None, url=None, *, cache=None, no_cache=False):
    """→ {doc_id, url, title, fields, zaak_id, pdf_urls, params, _meta}. One publication.

    doc_id = the numeric id (resolved to its URL through the cached sitemap set);
    url = the full publication URL (accepted directly, prefix-stripped when pasted)."""
    from ..transport import call_provider

    key = str(doc_id or "").strip()
    direct = str(url or "").strip()
    if not key and not direct:
        raise SdkError("usage_error", provider="nl_acm",
                       detail="doc_id (numeric, from nl_acm_publications rows) or url is required")
    m = re.match(r"https?://www\.acm\.nl(/nl/publicaties/.+)$", direct)
    if m:
        direct = m.group(1)
    if not direct and key.isdigit():
        rows, _metas, _n = _fetch_all_publications(cache=cache, no_cache=no_cache)
        hit = next((r for r in rows if r["doc_id"] == key), None)
        if hit is None:
            raise SdkError("not_found", provider="nl_acm",
                           detail=f"doc_id {key} is not in the sitemap corpus (13k+ URLs, 2003→)")
        direct = hit["url"]
    elif not direct:
        raise SdkError("usage_error", provider="nl_acm",
                       detail=f"doc_id must be the numeric id from nl_acm_publications rows, got {key!r}")
    r = call_provider(provider, "detail", {"url": f"https://www.acm.nl{direct}"
                             if direct.startswith("/") else direct},
                      cache=cache, no_cache=no_cache, extra_headers=_ACCEPT)
    d = parse_detail(r["data"])
    d.update({"doc_id": key or (_ID.search(direct).group(1) if _ID.search(direct) else None),
              "url": direct if direct.startswith("http") else f"https://www.acm.nl{direct}",
              "params": {"doc_id": key or None, "url": direct},
              "_meta": r})
    return d
