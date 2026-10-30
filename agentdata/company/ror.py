"""ror — ROR (Research Organization Registry) provider (v2 schema; keyless).

api.ror.org. 2026-10-23 probed shape:
GET /organizations?query=<q> → {number_of_results, time_taken, items:[{id,names[],types[],status,
established,locations[],external_ids[],relationships[],domains[],links[],admin}]};
GET /organizations/{id} (id = the full ror.org URL, path-segment encoded) → **a bare single record** (no items
wrapper, 200 verified).
v2 migration notes: **the top-level name/country keys are gone** — the display name lives in names[] (the entry whose
types includes ror_display has the value), the country in locations[0].geonames_details.country_name; external_ids is
an array ({type,preferred,all[]}) not the v1 dict; relationships[] {label,type:parent|child|related,id(full URL)} is
the parent/child/related edge face.
The search face is fixed at 20 rows per page (upstream has no per_page param, only page) — one page is enough for the
candidate face, pagination is not wired up.
TTL: search 7 days / record 30 days (ROR ships quarterly); politeness tier 1 rps (official no-key guidance is ≤2).
"""
import re

from ..errors import SdkError

provider = {
    "id": "ror",
    "baseUrl": "https://api.ror.org",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "search": {"path": "/organizations"},            # params: query, page, all_status (added in 0.2.9)
        "record": {"path": "/organizations/{id}"},       # id takes the full https://ror.org/<ui> (pre-encoded at build time)
    },
    "ttl": {"search": 7 * 86400, "record": 30 * 86400},
}

_ROR_UI = re.compile(r"^(?:https?://ror\.org/)?(0[a-z0-9]{8})$", re.IGNORECASE)  # ROR id: leading 0 + 8 chars


def display_name(names):
    """v2 display name = the names[] entry whose types includes ror_display (falls back to label / first entry)."""
    if not isinstance(names, list) or not names:
        return None
    for want in ("ror_display", "label"):
        for n in names:
            if want in (n.get("types") or []):
                return n.get("value")
    return names[0].get("value")


def orgs_from_upstream(data):
    """Upstream payload → org candidates (pure function, offline-testable). A bare single record must first be wrapped as {items:[rec]}."""
    items = data if isinstance(data, list) else (data or {}).get("items") or []
    candidates = []
    for o in items:
        loc = ((o.get("locations") or [{}])[0].get("geonames_details") or {})
        parent = next((r for r in (o.get("relationships") or []) if r.get("type") == "parent"), None)
        candidates.append({
            "ror_id": o.get("id", "").replace("https://ror.org/", "").replace("http://ror.org/", "") or None,
            "name": display_name(o.get("names")),                      # v2: the top-level name key is gone
            "aliases": [n.get("value") for n in (o.get("names") or [])
                        if "ror_display" not in (n.get("types") or []) and n.get("value")],
            "type": (o.get("types") or [None])[0],                     # company|education|healthcare|facility|government|nonprofit|archive|other
            "country": loc.get("country_name"),                        # v2: country comes from locations (first address)
            "country_code": loc.get("country_code"),
            "status": o.get("status"),                                 # active|inactive|withdrawn
            "established": o.get("established"),
            "website": next((l.get("value") for l in (o.get("links") or []) if l.get("type") == "website"), None),
            "domains": o.get("domains") or [],
            "parent": ({"name": parent.get("label"),
                        "ror_id": (parent.get("id") or "").replace("https://ror.org/", "") or None}
                       if parent else None),                           # parent-org edge (the research-world counterpart of the GLEIF parent)
            "external_ids": {e.get("type"): (e.get("preferred") or (e.get("all") or [None])[0])
                             for e in (o.get("external_ids") or [])},
        })
    return {
        "candidates": candidates,
        "total": data.get("number_of_results") if isinstance(data, dict) and isinstance(data.get("number_of_results"), int) else (1 if isinstance(data, list) else None),
    }


def search_orgs(q, *, page=None, all_status=None, cache=None, no_cache=False):
    """→ {candidates[], total, _meta}; org-name search candidates (query matches all fields; fixed 20 rows/page, page passes straight through).
    all_status (added in the 0.2.9 audit): an upstream boolean, default false = **only active orgs are returned** —
    inactive/withdrawn are hidden wholesale by default (2026-10-28 probe, AstraZeneca: default 22 rows all active vs
    all_status=true 23 rows including 1 withdrawn); None = param not sent, upstream default applies; True/False passed
    through explicitly. Due-diligence use cases usually want withdrawn rows included explicitly."""
    from ..transport import call_provider

    query = str(q or "").strip()
    if not query:
        raise SdkError("usage_error", provider="ror", detail="search_orgs requires a value (org name or ROR id)")
    params = {"query": query}
    if page is not None:
        params["page"] = int(page)
    if all_status is not None:
        params["all_status"] = "true" if all_status else "false"
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    return {**orgs_from_upstream(r["data"]), "_meta": r}


def lookup_ror(id_, *, cache=None, no_cache=False):
    """→ {candidates[1], total, _meta}; ROR id single-record identity card (accepts either the bare UI or the full https://ror.org/… form)."""
    from ..transport import call_provider

    m = _ROR_UI.match(str(id_ or "").strip())
    if not m:
        raise SdkError("usage_error", provider="ror", detail=f"not a ROR id shape (0 + 8 chars): {id_}")
    r = call_provider(provider, "record", {"id": f"https://ror.org/{m.group(1).lower()}"}, cache=cache, no_cache=no_cache)
    data = r["data"]
    return {**orgs_from_upstream(data if isinstance(data, list) else {"items": [data]}), "_meta": r}
