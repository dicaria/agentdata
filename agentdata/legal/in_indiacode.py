"""in_indiacode — India Code (indiacode.gov.in) central & state acts search, the DSpace 7
REST discovery API (/server/api/discover/search/objects, keyless).

IN legal face (0.3.59; admitted from research booklet in-indiacode 册, probed live
2026-11-13, tmp/probe-sdk-0359/r2_indiacode*.json). India Code is the official repository of
Central and State Acts — 'companies act' alone hits 13,530 items (6,765 pages at size=2;
136 pages at size=100 — the upstream honors size verbatim to at least 100).

CONTRACT (GET, query params): /server/api/discover/search/objects?query=<term>&size=<n>&page=<p>
- page is 0-based (DSpace convention; page.number echoes it). size = page size (100 honored;
  the local wall is 1-100).
- response nesting: _embedded.searchResult{page: {number, size, totalPages, totalElements},
  _embedded: {objects: [...]}} — each object wraps an indexableObject:
  {hitHighlights, type: 'discover', _embedded: {indexableObject: item}}.
- item = {id, uuid, name, handle, metadata (22 dc.* keys), inArchive, discoverable,
  lastModified, type, _links: {bundles, self, ...}} — metadata carries the act's own
  catalogue fields: dc.identifier.act_id, dc.identifier.act_number, dc.date.act_year,
  dc.date.enact_date, dc.date.entry_date, dc.date.issued, dc.identifier.collection,
  dc.identifier.department_name, dc.identifier.ministry_name, dc.identifier.no_of_chapter,
  dc.identifier.no_of_section, dc.identifier.refact, dc.identifier.repealed,
  dc.identifier.state_name, dc.identifier.uri, keyword_count.
- full document: item._links.bundles → bundles → bitstreams → content (a 3-hop chain the
  search face keys via uuid + the bundles href — download faces are a later extension).
Row mapping keeps every metadata key (list-of-{value} → first value), renames to snake_case,
and echoes hitHighlights (the <em>-wrapped match snippets). 0.5/2 polite, TTL 24h.
"""
import re

from ..errors import SdkError

provider = {
    "id": "in_indiacode",
    "baseUrl": "https://indiacode.gov.in",
    "rate": {"rps": 0.5, "burst": 2},
    "concurrency": 2,
    "ops": {
        "search": {"path": "/server/api/discover/search/objects", "method": "GET",
                   "idempotent": True, "timeout": 45.0},
    },
    "ttl": {"search": 24 * 3600},
}

# metadata key → row key (snake_case of the dc suffix; kept explicit — 22 keys measured,
# unknown keys are flattened by the generic fallback below)
_META_KEYS = [
    ("dc.identifier.act_id", "act_id"),
    ("dc.identifier.act_number", "act_number"),
    ("dc.date.act_year", "act_year"),
    ("dc.date.enact_date", "enact_date"),
    ("dc.date.entry_date", "entry_date"),
    ("dc.date.issued", "issued"),
    ("dc.identifier.collection", "collection"),
    ("dc.identifier.department_id", "department_id"),
    ("dc.identifier.department_name", "department"),
    ("dc.identifier.ministry_id", "ministry_id"),
    ("dc.identifier.ministry_name", "ministry"),
    ("dc.identifier.no_of_chapter", "chapters"),
    ("dc.identifier.no_of_section", "sections"),
    ("dc.identifier.refact", "ref_act"),
    ("dc.identifier.repealed", "repealed"),
    ("dc.identifier.state_id", "state_id"),
    ("dc.identifier.state_name", "state"),
    ("dc.identifier.uri", "uri"),
    ("dc.identifier.givenid", "given_id"),
    ("dc.title", "title"),
    ("keyword_count", "keyword_count"),
]


def _first(v):
    """DSpace metadata value: list of {value, ...} → first value string."""
    if isinstance(v, list) and v:
        first = v[0]
        return first.get("value") if isinstance(first, dict) else first
    return v


def item_from_upstream(obj):
    """discover object → flat act card (pure function — split out for offline testing)."""
    it = (obj.get("_embedded") or {}).get("indexableObject") or {}
    md = it.get("metadata") or {}
    row = {"uuid": it.get("uuid"), "handle": it.get("handle"), "name": it.get("name"),
           "in_archive": it.get("inArchive"), "last_modified": it.get("lastModified")}
    for src, dst in _META_KEYS:
        row[dst] = _first(md.get(src))
    links = it.get("_links") or {}
    row["bundles_url"] = (links.get("bundles") or {}).get("href")
    row["self_url"] = (links.get("self") or {}).get("href")
    hl = obj.get("hitHighlights") or {}
    row["highlights"] = {k: _first(v) for k, v in hl.items()} or None
    return row


def search_raw(q, *, limit=20, page=0, cache=None, no_cache=False):
    """→ {total, total_pages, rows[], params, _meta}. q = the search term (required — an empty
    term is the repository browse, not a face answer; the wall keeps the batch line's lane).
    limit = size wall 1-100 (upstream honors it verbatim); page 0-based."""
    term = str(q or "").strip()
    if not term:
        raise SdkError("usage_error", provider="in_indiacode",
                       detail="in_indiacode_search requires q (an act-name term, e.g. 'companies act') "
                              "— the bare repository browse is not a face answer")
    try:
        size = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="in_indiacode",
                       detail=f"limit must be an integer 1-100, got {limit!r}")
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="in_indiacode",
                       detail=f"limit must be 1-100 (upstream honors size verbatim), got {limit!r}")
    try:
        pg = int(page) if page else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="in_indiacode",
                       detail=f"page must be an integer >=0, got {page!r}")
    if pg < 0:
        raise SdkError("usage_error", provider="in_indiacode",
                       detail=f"page is 0-based (DSpace page.number), got {pg}")
    from ..transport import call_provider
    r = call_provider(provider, "search", {"query": term, "size": size, "page": pg},
                      cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    try:
        sr = doc["_embedded"]["searchResult"]
        objects = sr["_embedded"]["objects"]
        page_meta = sr["page"]
    except (KeyError, TypeError):
        raise SdkError("upstream_unavailable", provider="in_indiacode",
                       detail="discover/search/objects answered an unexpected shape (no "
                              "_embedded.searchResult — the DSpace 7 API may have moved)")
    return {"total": page_meta.get("totalElements"),
            "total_pages": page_meta.get("totalPages"),
            "rows": [item_from_upstream(o) for o in objects or []],
            "params": {"q": term, "limit": size, "page": pg}, "_meta": r}
