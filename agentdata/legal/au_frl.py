"""au_frl — Australian Federal Register of Legislation (api.prod.legislation.gov.au/v1,
the Office of Parliamentary Counsel's OData v1 service, keyless).

AU legal face (0.3.60; admitted from the research booklet au-frl-comlaw-statutes, re-probed
live 2026-11-13):

CONTRACT (OData v1, JSON):
  1. titles — GET /titles?$top=<n>&$count=true&$format=json&$orderby=name%20asc[&$filter=…]
     The answer is {value: [...], "@odata.count": N, "@odata.context": …}.
     `$filter=collection eq 'Act'` → 13,754 acts (measured); other collections are
     "Notifiable Legislation" (≈ 700) and "Compilation" (≈ 1,600).
  2. search — GET /titles?$search=<term>&$top=<n>&$count=true&$format=json
     The OData full-text search (the term is matched against the title text; a quoted phrase
     is honoured).
  3. versions — GET /versions/find(titleId='<id>',asAtSpecification='latest')?$format=json
     The current compilation of one title (the id is the C2004A00375-style title id).

LIVE LAWS (measured 2026-11-13):
  - the `$`-prefixed OData options must NOT be percent-encoded: the gateway answers 400 on an
    encoded option name ($top → %24top). The SDK bakes the option names into the op path
    template (the transport substitutes only the VALUE tokens), so they stay literal.
  - the bare host api.legislation.gov.au resets the TLS connection; the service lives on
    api.prod.legislation.gov.au — the base URL is pinned to the prod host.
  - values (the $filter expression, the $search term) are percent-encoded by the transport —
    that is correct for values and the upstream accepts it.

A title row: {id, name, makingDate, collection, subCollection, isPrincipal, isInForce,
status, year, number, seriesType, nameHistory[], statusHistory[]}.

Politeness: 0.5/4, concurrency 2, TTL 24h (the register is updated as Acts are made).
"""
from ..errors import SdkError

provider = {
    "id": "au_frl",
    "baseUrl": "https://api.prod.legislation.gov.au/v1",
    "rate": {"rps": 0.5, "burst": 4},
    "concurrency": 2,
    "ops": {
        # the $ option names are baked into the path (they must not be percent-encoded)
        "titles": {"path": "/titles?$top={top}&$count=true&$format=json&$orderby=name%20asc",
                   "timeout": 40.0},
        "titles_filtered": {"path": "/titles?$top={top}&$count=true&$format=json"
                                  "&$filter={filter}&$orderby=name%20asc",
                            "timeout": 40.0},
        "search": {"path": "/titles?$search={q}&$top={top}&$count=true&$format=json",
                   "timeout": 40.0},
        "versions": {"path": "/versions/find(titleId='{title_id}',asAtSpecification='latest')"
                            "?$format=json",
                     "timeout": 40.0},
    },
    "ttl": {"titles": 24 * 3600, "titles_filtered": 24 * 3600, "search": 24 * 3600,
            "versions": 24 * 3600},
}

COLLECTIONS = ("Act", "Notifiable Legislation", "Compilation")


def _rows(doc):
    if not isinstance(doc, dict) or "value" not in doc:
        raise SdkError("upstream_unavailable", provider="au_frl",
                       detail="the OData service answered an unexpected shape (no value array)")
    return doc.get("value") or [], doc.get("@odata.count")


def titles_raw(*, collection=None, top=20, cache=None, no_cache=False):
    """→ {total, rows[], params, _meta}. collection = the register collection
    ("Act" → 13,754 rows live; "Notifiable Legislation"; "Compilation"); top = $top."""
    from ..transport import call_provider

    try:
        n = int(top)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="au_frl", detail=f"top must be an integer, got {top!r}")
    if not 1 <= n <= 1000:
        raise SdkError("usage_error", provider="au_frl", detail=f"top must be 1..1000, got {n}")

    coll = str(collection).strip() if collection else None
    if coll:
        if coll not in COLLECTIONS:
            raise SdkError("usage_error", provider="au_frl",
                           detail=f"unknown collection {collection!r} — known: {list(COLLECTIONS)}")
        r = call_provider(provider, "titles_filtered",
                          {"top": n, "filter": f"collection eq '{coll}'"},
                          cache=cache, no_cache=no_cache)
    else:
        r = call_provider(provider, "titles", {"top": n}, cache=cache, no_cache=no_cache)
    rows, count = _rows(r["data"] or {})
    return {
        "total": count,
        "rows": rows,
        "params": {"collection": coll, "top": n},
        "_meta": r,
    }


def search_raw(term, *, top=20, cache=None, no_cache=False):
    """→ {total, rows[], params, _meta}. term = the OData $search full-text query
    (a quoted phrase is honoured upstream)."""
    from ..transport import call_provider

    q = str(term or "").strip()
    if not q:
        raise SdkError("usage_error", provider="au_frl", detail="the search term is required")
    try:
        n = int(top)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="au_frl", detail=f"top must be an integer, got {top!r}")
    if not 1 <= n <= 1000:
        raise SdkError("usage_error", provider="au_frl", detail=f"top must be 1..1000, got {n}")
    r = call_provider(provider, "search", {"q": q, "top": n}, cache=cache, no_cache=no_cache)
    rows, count = _rows(r["data"] or {})
    return {
        "total": count,
        "rows": rows,
        "params": {"q": q, "top": n},
        "_meta": r,
    }


def versions_raw(title_id, *, cache=None, no_cache=False):
    """→ {versions[], params, _meta}. The current compilation of one title."""
    from ..transport import call_provider

    t = str(title_id or "").strip()
    if not t:
        raise SdkError("usage_error", provider="au_frl", detail="title_id is required")
    r = call_provider(provider, "versions", {"title_id": t}, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    # the service answers a single version entity (not a value array) for find(titleId=…)
    versions = doc.get("value") if isinstance(doc, dict) else None
    if versions is None:
        versions = [doc] if isinstance(doc, dict) and doc.get("titleId") else []
    return {
        "total": len(versions or []),
        "versions": versions or [],
        "params": {"title_id": t},
        "_meta": r,
    }
