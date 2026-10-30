"""rxnav — NLM RxNav (drug name → RxCUI normalization + ATC property; keyless; official 20/s per IP — 0.2.8 sped up to 10 rps into the nlm group bucket).

TTL: drug name → RxCUI and the properties are permanent (concepts are immutable, the monthly release is a fallback replay).
Note: the interaction API is retired (on 2026-10-16 both list/interaction endpoints were measured 404 Not found, including the ONCHigh source) —
drug interactions are **not in the capability set**; the honest negative result is recorded.
"""

provider = {
    "id": "rxnav",
    "baseUrl": "https://rxnav.nlm.nih.gov/REST",
    # Official 20/s (RxNav ToS tier A); 10/4 per source (the window's upper bound 14<=20), and over-subscription inside the family is absorbed by the nlm group bucket (10+10=20) as a fallback
    "rate": {"rps": 10, "burst": 4, "group": "nlm"},
    "ops": {
        "rxcuiByName": {"path": "/rxcui.json"},
        "rxcuiProps": {"path": "/rxcui/{rxcui}/properties.json"},
        "rxcuiAtc": {"path": "/rxcui/{rxcui}/property.json"},
    },
    "ttl": {"rxcuiByName": None, "rxcuiProps": None, "rxcuiAtc": None},
}


def card_from_props(p: dict = None) -> dict:
    """Probed and confirmed (2026-10-22): synonym is often an empty string rather than null (Lipitor 153165 synonym:"") — an empty string becomes None;
    tty is the concept-level key (BN=brand name / IN=ingredient name), suppress is the quality flag (N=normal) — tty is the gate on ATC semantics (see get_atc)."""
    p = p or {}
    return {
        "normalized_name": p.get("name"),
        "synonym": p.get("synonym") or None,
        "tty": p.get("tty"),
        "suppress": p.get("suppress"),
    }


def atc_from_upstream(data: dict = None) -> list:
    """Probed and confirmed: ATC only attaches to ingredient-level (IN) concepts — querying ATC for Lipitor 153165(BN) returns {} with the whole propConceptGroup missing,
    while atorvastatin 83367(IN) gives C10AA05; a brand-name hit must be lowered to the ingredient level and queried again (the client layer hints at this in reason)."""
    data = data or {}
    concepts = ((data.get("propConceptGroup") or {}).get("propConcept")) or []
    return [c.get("propValue") for c in concepts if c.get("propName") == "ATC" and c.get("propValue")]


def get_atc(rxcui: str, cache=None, no_cache: bool = False) -> dict:
    """RxCUI → the list of ATC codes (a cross-jurisdiction drug name key, the two-key model «RxCUI(US)+ATC(global)»).
    A concept with no ATC (typically a brand-name level BN concept) returns an empty list — an honest empty set, not an error."""
    from ..transport import call_provider

    r = call_provider(provider, "rxcuiAtc", {"rxcui": str(rxcui), "propName": "ATC"},
                      cache=cache, no_cache=no_cache)
    return {"atc": atc_from_upstream(r.get("data")), "_meta": r}


def resolve_drug_name(name: str, cache=None, no_cache: bool = False) -> dict:
    from ..transport import call_provider
    from ..errors import SdkError

    ids = call_provider(provider, "rxcuiByName", {"name": name}, cache=cache, no_cache=no_cache)
    rxcuis = ((ids["data"] or {}).get("idGroup") or {}).get("rxnormId") or []
    if not rxcuis:
        raise SdkError("upstream_not_found", provider="rxnav", detail=f"RxNav has no RxCUI for this drug name: {name}")
    rxcui = rxcuis[0]
    props = call_provider(provider, "rxcuiProps", {"rxcui": rxcui}, cache=cache, no_cache=no_cache)
    return {
        "rxcui": rxcui,
        **card_from_props((props["data"] or {}).get("properties")),
        **({"all_matches": rxcuis} if len(rxcuis) > 1 else {}),
        "_meta": {"lookup": ids, "props": props},
    }
