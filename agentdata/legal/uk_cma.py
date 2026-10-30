"""uk_cma — UK Competition and Markets Authority case face provider (www.gov.uk content/search API; keyless).

Shape verified 2026-10-29:
GET /api/search.json?filter_format=cma_case&q=&count=&start=
  → {results:[{title,link:'/cma-cases/<slug>',_id=content_id,public_timestamp,description,
     organisations:[…],format:'cma_case',…}], total, start, aggregates, …}
  — filter_format=cma_case is this face's semantics (a fixed param, not a user param); q/count/start go through
  with upstream verbatim names.
  count has no upstream wall (verified 2026-10-29: count=1000 → the full 1000 rows/76KB in one shot) — this face
  uses a politeness cap of 100.
GET /api/content/cma-cases/{slug}
  → {content_id(UUID stable key), title, first_published_at, public_updated_at, updated_at,
     withdrawn_notice, details:{body(HTML), change_history:[{note,public_timestamp}],
     attachments:[{title,url,content_type,content_id,…}]}, links:{organisations,…}}
Param-minimalism pitfall: combined params like organisations/order → 422 — this face accepts only q/count/start,
do not widen it.
atom incremental feed: /cma-cases.atom (the increment anchor for the corpus batch line; not used by this realtime face).
TTL: search 24h (the case list drifts at daily cadence) / case 7 days (case cards change slowly; change_history
records the evolution); polite rate 1 rps (gov.uk publishes no search-API quota — conservative).
"""
from ..errors import SdkError

provider = {
    "id": "uk_cma",
    "baseUrl": "https://www.gov.uk",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "search": {"path": "/api/search.json"},          # params: q, count, start (filter_format is fixed for this face)
        "case": {"path": "/api/content/cma-cases/{slug}"},  # slug = the tail segment of the case-page base_path (the search row's link field)
    },
    "ttl": {"search": 24 * 3600, "case": 7 * 86400},
}


def cases_from_upstream(data, size):
    """Upstream search response → case rows (pure function, offline-testable)."""
    rows = [{
        "slug": (r.get("link") or "").removeprefix("/cma-cases/") or None,  # join key into the detail face (link=/cma-cases/<slug>;
                                                                           # the search row's _id ≡ base_path, not a UUID — do not pass it off as content_id)
        "title": r.get("title"),                       # case name = the party pair "A / B" form
        "public_timestamp": r.get("public_timestamp"),
        "description": r.get("description") or None,
        "organisations": [o.get("title") for o in (r.get("organisations") or []) if o.get("title")],
        "url": ("https://www.gov.uk" + r["link"]) if r.get("link") else None,
    } for r in ((data or {}).get("results") or [])]
    return {
        "rows": rows, "count": len(rows), "limit_applied": size,
        "total": data.get("total") if isinstance(data, dict) and isinstance(data.get("total"), int) else None,
    }


def search_raw(q=None, *, count=20, start=0, cache=None, no_cache=False):
    """Flat-panel low-level face: q/count/start go through with verbatim names (filter_format=cma_case fixed).

    → {rows[], count, limit_applied, total, params, _meta}. A missing q = full-register enumeration (2,591 live
    cases counted 2026-10-29); count politeness wall 1-100 (upstream has no wall — count=1000 was verified to
    deliver in full); start = offset paging."""
    from ..transport import call_provider

    term = str(q or "").strip() or None
    size = int(count) if count is not None else 20  # explicit None check — 0 being swallowed by `or` was a same-type bug caught by a test
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="uk_cma",
                       detail=f"count must be 1-100 (politeness cap; upstream has no wall — verified 2026-10-29, count=1000 delivers in full), got \"{count}\"")
    off = int(start) if start is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="uk_cma", detail=f"start must be an offset ≥0, got \"{start}\"")
    params = {"filter_format": "cma_case", "count": size, "start": off}
    if term:
        params["q"] = term
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    return {**cases_from_upstream(r["data"], size), "params": params, "_meta": r}


def _clean_slug(slug):
    s = str(slug or "").strip()
    # Tolerance: a pasted full base_path (/cma-cases/<slug> or https://www.gov.uk/cma-cases/<slug>) gets its prefix stripped
    for pre in ("https://www.gov.uk/cma-cases/", "http://www.gov.uk/cma-cases/", "/cma-cases/"):
        if s.startswith(pre):
            s = s[len(pre):]
    s = s.strip("/")
    if not s or "/" in s:
        raise SdkError("usage_error", provider="uk_cma",
                       detail=f"slug must be the case-page tail segment (e.g. nexfibre-slash-substantial-merger-inquiry, "
                              f"echoed verbatim from the search row's link field): {slug}")
    return s


def case_raw(slug, *, cache=None, no_cache=False):
    """→ the full single-case dossier (content API; content_id = the UUID stable key).
    attachments = the decision/notice PDF family."""
    from ..transport import call_provider

    s = _clean_slug(slug)
    r = call_provider(provider, "case", {"slug": s}, cache=cache, no_cache=no_cache)
    x = r["data"] or {}
    det = x.get("details") or {}
    return {
        "slug": s,
        "content_id": x.get("content_id"),
        "title": x.get("title"),
        "description": x.get("description") or None,
        "document_type": x.get("document_type"),
        "first_published_at": x.get("first_published_at"),
        "public_updated_at": x.get("public_updated_at"),
        "updated_at": x.get("updated_at"),
        "withdrawn": bool(x.get("withdrawn_notice")),
        "change_history": det.get("change_history") or [],      # [{note, public_timestamp}] newest→oldest (last = First published)
        "attachments": [{"title": a.get("title"), "url": a.get("url"),
                         "content_type": a.get("content_type"), "content_id": a.get("content_id")}
                        for a in (det.get("attachments") or [])],
        "body_html": det.get("body") or "",                     # the case-page body HTML (investigation/decision summary)
        "organisations": [o.get("title") for o in ((x.get("links") or {}).get("organisations") or [])
                          if o.get("title")],
        "url": f"https://www.gov.uk/cma-cases/{s}",
        "_meta": r,
    }
