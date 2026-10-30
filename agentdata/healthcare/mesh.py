"""mesh — MeSH controlled-vocabulary provider (id.nlm.nih.gov RDF lookup API; keyless; NLM/UMLS family 20/s — 0.2.8 sped up to 10 rps into the nlm group bucket).

Wave 3 of the healthcare domain: resolve kind=mesh_term
— drug/disease name → the MeSH descriptor master record, the control-term anchor for literature search and corpus normalization. Shapes measured 2026-10-23 (the param names are very easy to get wrong):
GET /mesh/lookup/descriptor?label=<q>&match=contains&limit=N
  → [{resource:"http://id.nlm.nih.gov/mesh/D001241", label:"Aspirin"}, …]
**the search param is label** (passing term/descriptor just gets a 400 {"label":["must not be empty"]});
the match closed set is contains|exact|startswith (an illegal value such as word gets a 400 listing the closed set).
GET /mesh/lookup/details?descriptor=D001241
  → {descriptor, qualifiers[], seealso[], terms:[{resource,label,preferred}]}
  — terms is the synonym-entry pool of that descriptor (the preferred:true slot is the authoritative name); qualifiers are the qualifier sub-anchors.
Every term resolution is a fixed two hops (search + details of the preferred record); on a miss "zero hits is a legal answer" — it is not treated as an error.
TTL: MeSH releases yearly → 30 days; polite tier 1 rps (NLM's keyless guidance says ≤3).
"""
import re

from ..errors import SdkError

provider = {
    "id": "mesh",
    "baseUrl": "https://id.nlm.nih.gov",
    # NLM/UMLS family 20/s (tier B, MeSH lookup is not listed separately); 0.2.8 sped up to 10/4 into the nlm group bucket (same note as rxnav)
    "rate": {"rps": 10, "burst": 4, "group": "nlm"},
    "ops": {
        "lookup": {"path": "/mesh/lookup/descriptor"},   # params: label, match, limit
        "details": {"path": "/mesh/lookup/details"},     # params: descriptor
    },
    "ttl": {"lookup": 30 * 86400, "details": 30 * 86400},
}

_UI = re.compile(r"([A-Z]\d{6})$")


def _ui_of(resource):
    m = _UI.search(str(resource or ""))
    return m.group(1) if m else None


def descriptors_from_upstream(data, size):
    """Upstream payload → descriptor candidates (pure function, testable offline; upstream echoes no total — lookup returns a truncated list)."""
    items = data if isinstance(data, list) else []
    return {
        "candidates": [{"mesh_ui": _ui_of(d.get("resource")),
                        "descriptor_uri": d.get("resource"),
                        "label": d.get("label")} for d in items],
        "limit_applied": size,
    }


def terms_from_upstream(details):
    """details payload → the synonym pool (pure function, testable offline): the preferred entry comes first."""
    terms = [{"mesh_ui": _ui_of(t.get("resource")), "label": t.get("label"), "preferred": t.get("preferred") is True}
             for t in ((details or {}).get("terms") or [])]
    preferred = next((t["label"] for t in terms if t["preferred"]), None) or (terms[0]["label"] if terms else None)
    return {
        "terms": terms,
        "preferred_term": preferred,
        "synonyms": [t["label"] for t in terms if not t["preferred"]],
    }


def search_descriptors(q, *, match="contains", limit=10, cache=None, no_cache=False):
    """→ {candidates[], limit_applied, _meta}; descriptor candidates (the match closed set is contains|exact|startswith)."""
    from ..transport import call_provider

    label = str(q or "").strip()
    if not label:
        raise SdkError("usage_error", provider="mesh", detail="search_descriptors needs value (a drug/disease name, etc.)")
    if match not in ("contains", "exact", "startswith"):
        raise SdkError("usage_error", provider="mesh", detail=f"match must be contains|exact|startswith, got '{match}'")
    size = min(max(1, int(limit or 10)), 50)
    r = call_provider(provider, "lookup", {"label": label, "match": match, "limit": size}, cache=cache, no_cache=no_cache)
    return {**descriptors_from_upstream(r["data"], size), "_meta": r}


def descriptor_details(ui, *, cache=None, no_cache=False):
    """→ {terms[], preferred_term, synonyms[], descriptor, qualifiers[], seealso[], _meta}; the descriptor master record."""
    from ..transport import call_provider

    descriptor = str(ui or "").strip()
    if not re.fullmatch(r"[A-Z]\d{6}", descriptor):
        raise SdkError("usage_error", provider="mesh", detail=f"not a MeSH UI shape (a letter + 6 digits): {ui}")
    r = call_provider(provider, "details", {"descriptor": descriptor}, cache=cache, no_cache=no_cache)
    d = r["data"][0] if isinstance(r["data"], list) and r["data"] else r["data"]  # guard against array wrapping
    return {**terms_from_upstream(d),
            "descriptor": descriptor,
            "qualifiers": [_ui_of(q) for q in ((d or {}).get("qualifiers") or [])],
            "seealso": [_ui_of(s) for s in ((d or {}).get("seealso") or [])],
            "_meta": r}
