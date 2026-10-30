"""gleif — GLEIF LEI API (LEI → entity identity card normalization + reverse name search + parent-company control chain; keyless).

Politeness tier 1 rps/burst 2; TTL: lookup/search 7 days, parents 30 days (ownership chains change infrequently).
Positioning boundary: exact LEI normalization — an LEI in, an entity identity card out; reverse name search is a
legal-name contains match (not fuzzy tolerance), and candidates are not an authoritative normalization.
2026-10-21: parents moved to the dedicated endpoints /lei-records/{lei}/direct-parent|ultimate-parent
(each returns the full parent card; no parent → 404) — the old include= route, when a firm self-reports "no parent",
pointed relationships at reporting-exceptions and the exception id got laid into the result as if it were an LEI;
the dedicated endpoints are naturally honest nulls and the N+1 follow-up lookups disappeared.
"""
import re

provider = {
    "id": "gleif",
    "baseUrl": "https://api.gleif.org/api/v1",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "lookup": {"path": "/lei-records/{lei}", "notFound": [404]},   # params: lei (path template)
        "search": {"path": "/lei-records"},                            # params: name, limit (query assembled as filter[entity.legalName]/page[size])
        "direct_parent": {"path": "/lei-records/{lei}/direct-parent", "notFound": [404]},     # dedicated endpoint returns the full parent card; 404 = none
        "ultimate_parent": {"path": "/lei-records/{lei}/ultimate-parent", "notFound": [404]}, # same (ultimate sense)
    },
    "ttl": {"lookup": 7 * 86400, "search": 7 * 86400, "direct_parent": 30 * 86400, "ultimate_parent": 30 * 86400},
}

LEI_RE = re.compile(r"^[A-Z0-9]{20}$")


def lookup_lei(lei: str, cache=None, no_cache: bool = False) -> dict:
    from ..transport import call_provider
    from ..errors import SdkError

    norm = str(lei).strip().upper()
    if not LEI_RE.match(norm):
        raise SdkError("usage_error", provider="gleif",
                       detail=f"invalid LEI shape (ISO 17442: 20 alphanumeric chars): {lei}")
    r = call_provider(provider, "lookup", {"lei": norm}, cache=cache, no_cache=no_cache)
    a = ((r["data"] or {}).get("data") or {}).get("attributes") or {}
    ent, reg = a.get("entity") or {}, a.get("registration") or {}
    creation = ent.get("creationDate")
    return {
        "lei": a.get("lei") or norm,
        "legal_name": (ent.get("legalName") or {}).get("name"),
        "name_language": (ent.get("legalName") or {}).get("language"),
        "entity_status": ent.get("status"),
        "jurisdiction": ent.get("jurisdiction"),
        "registration_country": (ent.get("legalAddress") or {}).get("country"),
        "hq_country": (ent.get("headquartersAddress") or {}).get("country"),
        "hq_city": (ent.get("headquartersAddress") or {}).get("city"),
        "entity_category": ent.get("category"),
        "creation_date": creation[:10] if creation else None,
        "registration": {
            "status": reg.get("status"),  # ISSUED / LAPSED / RETIRED… (issuance sense)
            "last_update": reg.get("lastUpdateDate"),  # upstream key lastUpdateDate (2026-10-21: the old read of lastUpdate was permanently null)
            "next_renewal_date": reg.get("nextRenewalDate"),
            "registrar_id": (ent.get("registeredAt") or {}).get("id"),
            "registered_as": ent.get("registeredAs"),
        },
        "_meta": r,
    }


def search_lei_by_name(name, *, limit=10, cache=None, no_cache=False):
    """→ {total, candidates[], _meta}; name → LEI reverse search. Legal-name contains match, not fuzzy tolerance —
    candidates are not an authoritative normalization; re-verify with lookup_lei before persisting."""
    from ..transport import call_provider
    from ..errors import SdkError

    q = str(name or "").strip()
    if not q:
        raise SdkError("usage_error", provider="gleif", detail="search requires --name")
    r = call_provider(provider, "search", {
        "filter[entity.legalName]": q,
        "page[size]": min(max(1, int(limit) or 10), 200),  # real upstream limit 200 (probed: 201→400, 200 served in full; the earlier 100 clamp was a misrecord)
    }, cache=cache, no_cache=no_cache)
    rows = [{
        "lei": (e.get("attributes") or {}).get("lei") or e.get("id"),
        "legal_name": ((e.get("attributes") or {}).get("entity") or {}).get("legalName", {}).get("name"),
        "entity_status": ((e.get("attributes") or {}).get("entity") or {}).get("status"),
        "jurisdiction": ((e.get("attributes") or {}).get("entity") or {}).get("jurisdiction"),
        "registration_country": (((e.get("attributes") or {}).get("entity") or {}).get("legalAddress") or {}).get("country"),
    } for e in (r["data"] or {}).get("data") or []]
    total = (((r["data"] or {}).get("meta") or {}).get("pagination") or {}).get("total")
    return {"total": total if total is not None else len(rows), "candidates": rows, "_meta": r}


def _norm_lei(lei):
    from ..errors import SdkError

    norm = str(lei).strip().upper()
    if not LEI_RE.match(norm):
        raise SdkError("usage_error", provider="gleif",
                       detail=f"invalid LEI shape (ISO 17442: 20 alphanumeric chars): {lei}")
    return norm


def _card(norm, op, cache, no_cache):
    """Single-endpoint parent card extraction → (card|None, meta). 404 = no parent, honest null (including the self-reported
    reporting-exception face). The dedicated endpoints /direct-parent|/ultimate-parent return the parent card directly — the old
    include= route laid the exception id into the result as if it were an LEI."""
    from ..transport import call_provider
    from ..errors import SdkError
    from datetime import datetime, timezone

    try:
        r = call_provider(provider, op, {"lei": norm}, cache=cache, no_cache=no_cache)
        a = (((r["data"] or {}).get("data") or {}).get("attributes")) or {}
        lei_id = a.get("lei")
        if not lei_id:
            return None, r  # empty-face fallback
        ent = a.get("entity") or {}
        return ({"lei": lei_id,
                 "legal_name": (ent.get("legalName") or {}).get("name"),
                 "entity_status": ent.get("status"),
                 "jurisdiction": ent.get("jurisdiction")}), r
    except SdkError as e:
        if e.code == "upstream_not_found":
            # 404 = no such parent — honest null; notFound is not cached, the meta is minted on the spot
            return None, {"from_cache": False,
                          "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        raise


def get_direct_parent(lei, *, cache=None, no_cache=False):
    """→ {lei, parent, _meta}; /lei-records/{lei}/direct-parent single-endpoint face (0.2.0 naming split: one command, one endpoint)."""
    norm = _norm_lei(lei)
    card, meta = _card(norm, "direct_parent", cache, no_cache)
    return {"lei": norm, "parent": card, "_meta": meta}


def get_ultimate_parent(lei, *, cache=None, no_cache=False):
    """→ {lei, parent, _meta}; /lei-records/{lei}/ultimate-parent single-endpoint face (ultimate sense)."""
    norm = _norm_lei(lei)
    card, meta = _card(norm, "ultimate_parent", cache, no_cache)
    return {"lei": norm, "parent": card, "_meta": meta}


def get_parents(lei, *, cache=None, no_cache=False):
    """→ {lei, direct_parent, ultimate_parent, _meta, _metas}; no parent = honest null, not an error.
    (internal merge face: used by the related kind=parent internals; the command face is already split into the
    gleif_direct_parent / gleif_ultimate_parent two endpoints.)"""
    d = get_direct_parent(lei, cache=cache, no_cache=no_cache)
    u = get_ultimate_parent(lei, cache=cache, no_cache=no_cache)
    return {"lei": d["lei"], "direct_parent": d["parent"], "ultimate_parent": u["parent"],
            "_meta": d["_meta"],
            "_metas": [d["_meta"], u["_meta"]]}  # full-chain metas (one per dedicated endpoint) — the client layer's enrich_source consumes them one by one
