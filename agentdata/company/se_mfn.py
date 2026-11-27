"""se_mfn — MFN.se Nordic disclosure wire (mfn.se canonical paths, JSON Feed face;
0.3.77 batch E20). The aggregated announcement/PDMR wire for SE/DK/FI/NO issuers:
Modular Finance's news + IR distribution front — the harvestable representative
of the "exchange-line" disclosure family (the NewsWeb API obns-api.dev.
euronext.cloud stays egress-blocked: ECONNRESET on 2026-11-23 across three
stacks AND on the 2026-11-24 one-shot curl re-test — out of scope by probe
discipline, do not force).

2026-11-24 probed laws (tmp/probe-e20/mfn.sh + the SDK live smoke, same day;
research volume company/mfn-se-nordic-disclosure-wire.md,
probe ancestry tmp/probe-audit/r542/watch1123/mfn1/):

  - THE CONTENT-NEGOTIATION LAW (live reversal of the probe-day HTML-parse plan):
    the canonical disclosure paths /all/s/{market} and /all/a/{slug} and the
    article paths /{channel}/a/{issuer}/{title} answer the JSON Feed spec
    (version https://www.mfn.se/feed/version/1) to Accept: application/json
    clients — the SDK's deterministic stance on both channels — and HTML to
    browsers. The SDK pins the JSON face: every op declares accept="text" and
    json-parses in-module (content-type tolerant), so a revert to HTML answers
    surfaces as a shape-drift error, never as a silent parse failure.
  - THE ROBOTS LAW: robots.txt Disallows /assets + /manage-subscription +
    /health + /authr and the machine-feed URL SUFFIXES *.xml$ *.rss$ *.atom$
    *.json$. The faces here ride the bare canonical paths (no suffix) — the
    negotiation happens on the HTML page URLs themselves; no feed URL is ever
    touched.
  - THE SOFT-404 LAW: an unknown issuer slug answers 200 with an EMPTY-items
    JSON feed (honest empty, not 404) — returned as an empty entries list; an
    unknown article path answers a real 404 (notFound declared) → found=false;
    a 200 article feed carrying zero items is answered the same way.
  - THE PAGINATION LAW: the feed carries next_url (?limit=48&offset=N) —
    48 entries/page, offset-paginated to the full archive (Ambu p1 2026-11→
    2025-12, p2 (offset=48) 2025-12→, verified seamless on probe day). Deep
    history = offset stepping at the caller.
  - THE ENTRY CARD: each item carries the join keys the HTML page hid —
    author {slug, name, isins[], leis[], tickers[]} (subjects[] repeats it for
    multi-issuer disclosures), properties {lang, tags, type, scopes[]} (the
    regulatory tag + country scope) and content {title, publish_date (UTC ISO
    — the authority; the HTML list dates were site-local CET), html, text}.
    The wire/feed faces keep entries lean (no body text); the article face
    returns the full card.
  - RED LINE: the JSON feed carries no quote metadata at all (the HTML page's
    tooltip Open/High/Low/Close never enters the JSON face) — nothing to strip.
"""
import json
import re

from ..errors import SdkError

provider = {
    "id": "se-mfn",
    "baseUrl": "https://mfn.se",
    "rate": {"rps": 1.0, "burst": 1},
    "ops": {
        "wire":    {"path": "/all/s/{market}", "accept": "text"},
        "feed":    {"path": "/all/a/{slug}", "accept": "text"},
        "article": {"path": "/{path}", "accept": "text", "path_safe": "/",
                    "notFound": [404]},
    },
    "ttl": {"wire": 3600, "feed": 3600, "article": 86400},
}

MARKETS = ("nordic", "sweden", "denmark", "finland", "norway")

_PATH_RE = re.compile(r"^/[a-z]{2,4}/a/[a-z0-9-]+/[a-z0-9-]+$")
_SLUG_RE = re.compile(r"^[a-z0-9-]{1,80}$")
_ORIGIN = "https://mfn.se"


def _feed(r):
    """json-parse the negotiated body (accept:'text' hands the raw string; the
    JSON Feed spec is the expected shape — anything else is shape drift)."""
    body = r.get("data") or ""
    if isinstance(body, dict):
        return body
    try:
        return json.loads(body)
    except ValueError:
        raise SdkError("upstream_unavailable", provider="se-mfn",
                       detail=("the response is not the JSON Feed spec — the content "
                               "negotiation may have flipped back to HTML; re-probe"))


def _issuer_ref(a):
    """author/subject → the compact join-key card (slug/name/isins/leis/tickers)."""
    if not isinstance(a, dict):
        return None
    return {"slug": a.get("slug"), "name": a.get("name"),
            "isins": a.get("isins") or [], "leis": a.get("leis") or [],
            "tickers": a.get("tickers") or []}


def _entry(item):
    """item → the lean disclosure card (no body text — the article face carries that)."""
    content = item.get("content") or {}
    props = item.get("properties") or {}
    url = item.get("url") or ""
    path = url[len(_ORIGIN):] if url.startswith(_ORIGIN) else (url or None)
    author = _issuer_ref(item.get("author"))
    return {
        "path": path,
        "news_id": item.get("news_id"),
        "date": content.get("publish_date"),  # UTC ISO — the authority
        "title": content.get("title"),
        "issuer": author,
        "subjects": [_issuer_ref(s) for s in (item.get("subjects") or [])],
        "lang": props.get("lang"),
        "tags": props.get("tags") or [],
        "type": props.get("type"),
        "scopes": props.get("scopes") or [],
        "channel": item.get("source"),
    }


def wire(*, market="nordic", cache=None, no_cache=False):
    """→ {entries, market, params, _meta}; the full stream page for one market segment
    (48 entries — the newest announcements/PDMR reports across SE/DK/FI/NO issuers,
    no pagination here; per-issuer deep history goes through issuer_feed).
    --market nordic|sweden|denmark|finland|norway (default nordic; the bare /all/s
    path 301s — always pass a segment)."""
    mkt = str(market or "").strip().lower()
    if mkt not in MARKETS:
        raise SdkError("usage_error", provider="se-mfn",
                       detail=f"market must be one of {MARKETS}, got {market!r}")
    from ..transport import call_provider
    r = call_provider(provider, "wire", {"market": mkt}, cache=cache, no_cache=no_cache)
    feed = _feed(r)
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    return {"entries": [_entry(x) for x in (feed.get("items") or [])],
            "market": mkt, "params": {"market": mkt}, "_meta": meta}


def issuer_feed(*, slug, offset=0, cache=None, no_cache=False):
    """→ {entries, slug, offset, params, _meta}; one issuer's announcement feed,
    48 entries/page, offset-paginated to the full archive (Ambu p1 2026-11→
    2025-12, p2 2025-12→ seamless on probe day). An unknown slug answers the
    SOFT-404 (200, empty-items feed) — returned as an empty entries list, never
    an error. --slug ambu --offset 0."""
    s = str(slug or "").strip().lower()
    if not _SLUG_RE.fullmatch(s):
        raise SdkError("usage_error", provider="se-mfn",
                       detail=f"slug must be the MFN issuer slug ([a-z0-9-], e.g. ambu), got {slug!r}")
    off = int(offset or 0)
    if off < 0:
        raise SdkError("usage_error", provider="se-mfn",
                       detail=f"offset must be >= 0, got {offset!r}")
    params = {"slug": s}
    if off:
        params["offset"] = str(off)
    from ..transport import call_provider
    r = call_provider(provider, "feed", params, cache=cache, no_cache=no_cache)
    feed = _feed(r)
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    return {"entries": [_entry(x) for x in (feed.get("items") or [])],
            "slug": s, "offset": off, "params": params, "_meta": meta}


def article(*, path, cache=None, no_cache=False):
    """→ {found, path, article, params, _meta}; one disclosure's full card — the
    single-item JSON feed (date = the UTC publish_date authority; title/issuer
    (slug/name/isins/leis/tickers)/subjects/properties (lang/tags/type/scopes) +
    the body text and html verbatim). An unknown path answers the honest 404 →
    found=false. --path
    /nir/a/ambu/transactions-under-ambus-share-buyback-program-eccc77cf."""
    p = str(path or "").strip()
    if not _PATH_RE.fullmatch(p):
        raise SdkError("usage_error", provider="se-mfn",
                       detail=(f"path must be the article path handed out by the wire/issuer_feed "
                               f"faces (/channel/a/issuer/title-uuid8), got {path!r}"))
    from ..transport import call_provider
    try:
        r = call_provider(provider, "article", {"path": p}, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_not_found":
            return {"found": False, "path": p, "article": None,
                    "params": {"path": p},
                    "_meta": {"from_cache": False, "fetched_at": None,
                              "note": "honest 404 — no such article path"}}
        raise
    feed = _feed(r)
    meta = {"from_cache": r["from_cache"], "fetched_at": r["fetched_at"]}
    items = feed.get("items") or []
    if not items:
        # a 200 article feed with zero items = the soft-404 family answered on the
        # JSON face — honest miss, never fabricated
        return {"found": False, "path": p, "article": None,
                "params": {"path": p},
                "_meta": {**meta, "note": "200 feed with zero items — no such article path"}}
    item = items[0]
    content = item.get("content") or {}
    art = {"path": p, "news_id": item.get("news_id"),
           "date": content.get("publish_date"),
           "title": content.get("title"),
           "issuer": _issuer_ref(item.get("author")),
           "subjects": [_issuer_ref(s) for s in (item.get("subjects") or [])],
           "properties": item.get("properties") or {},
           "html": content.get("html"), "text": content.get("text")}
    return {"found": True, "path": p, "article": art, "params": {"path": p},
            "_meta": meta}
