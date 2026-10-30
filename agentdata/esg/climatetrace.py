"""climatetrace — Climate TRACE v7 provider (api.climatetrace.org; keyless).

Counterpart to the Node implementation (esg domain Wave 3: trace_owner + trace_sources — the
facility/asset-level GHG emissions two-hop chain). 2026-10-23 measured shape
(v7 = the geo-aggregation rework; the openapi.json endpoint serves YAML not JSON — do not json.load it):
GET /v7/owners?name=<q>&limit=N → [{id:"E100000001492", name:"Gazprom PJSC"}] — **bare array, only id+name**,
a LIKE-style candidate face (the E-prefixed id is the stable company key; same pattern as EITI eiti_name:
candidates are not authoritative normalization);
GET /v7/sources?ownerIds=<E…>&year=YYYY → bare array: {id,name,sector,subsector,sourceType(point-source|aggregate),
country,emissionsQuantity(tCO2e),gas,year,capacity,capacityUnits,activity,activityUnits,assetType,
centroid:{latitude,longitude}} — 19 columns all verified by probing.
Parameter window: year data window 2021–current year (default current year), gas defaults to co2e_100yr.
2026-10-23 wall-probing batch:
**owners zero hits = 404 JSON** ({"detail":"No owners matched…"}) not a 200 empty array — after the op declares
notFound it maps to a legal empty candidate list (previously mis-raised as upstream_unavailable); limit has no cap
(1000 really returned 991 rows), **ordering is unstable across limits** (limit=5 first 5 ≠ limit=1000 first 5 —
offset paging may skip or duplicate; on the candidate face fetch enough in one go);
**sources does not error on out-of-window years**: year=2020 → 200 with a null body (data-window guidance, not a block);
**gas goes straight through by name**: gas=ch4 returns the same shape, the gas field echoes ch4, and
emissionsQuantity is that gas's native unit, not tCO2e;
**multiple ownerIds comma-joined = union with dedup** (12∪2→13, a source shared across owners appears once);
a repeated param = silent first-wins (only the first ownerIds counts, the rest are dropped — a trap shape, do not use).
v7 dropped v6's assets endpoint (/v6/assets still 200 for backwards compatibility); EUTL is the EU statutory registry,
TRACE covers global point sources — complementary, not substitutes.
TTL: owners 30 days (stable-key face) / sources 30 days (annual data rolls slowly); politeness tier 1 rps.
"""
import re
from datetime import datetime, timezone

from ..errors import SdkError

provider = {
    "id": "climatetrace",
    "baseUrl": "https://api.climatetrace.org",
    "rate": {"rps": 1, "burst": 3},
    "ops": {
        # zero hits = 404 JSON "No owners matched" (measured 2026-10-23) → declared notFound, then mapped to a legal empty set
        "owners": {"path": "/v7/owners", "notFound": [404]},    # params: name, limit, offset
        "sources": {"path": "/v7/sources"},  # params: ownerIds (comma = union), year, gas, limit
    },
    "ttl": {"owners": 30 * 86400, "sources": 30 * 86400},
}

_E_ID = re.compile(r"^E\d+$")

# sectors closed set (probed 2026-10-28 at /v7/definitions/sectors, 10 values + the special value all_no_forest).
# The closed set comes from probing upstream — do not generalize from first-seen samples; invalid values make the
# upstream **silently return the WHOLE corpus** (sectors=electricity returns a row set bit-for-bit identical to the
# unfiltered one — a false-negative trap), so it is intercepted locally (same discipline as osv ecosystem).
SECTORS = {
    "agriculture", "buildings", "fluorinated-gases", "forestry-and-land-use",
    "fossil-fuel-operations", "manufacturing", "mineral-extraction",
    "power", "transportation", "waste",
}
SECTORS_SPECIAL = {"all_no_forest"}  # excludes forestry-and-land-use (openapi description verbatim; verified live 2026-10-28)


def owners_from_upstream(data, size):
    """Upstream response -> company candidates (pure function, offline-testable; owners echoes no total — a truncated list)."""
    items = data if isinstance(data, list) else []
    return {
        "candidates": [{"trace_owner_id": o.get("id"),    # E-prefixed stable company key (anchor for the subsequent sources query)
                        "owner_name": o.get("name")} for o in items],
        "limit_applied": size,
    }


def sources_from_upstream(data, *, tco2e=True):
    """Upstream response -> emission-source rows (pure function, offline-testable).

    tco2e=True (default, gas=co2e_100yr basis): row key emissions_tco2e / total emissions_tco2e_sum —
    the frozen face name stays; tco2e=False (explicit non-co2e gas): row key switches to
    emissions_quantity / emissions_quantity_sum — that unit is the gas's native unit, not tCO2e
    (measured 2026-10-23, gas=ch4, same shape); a key name that lies is worse than a switched key."""
    qkey = "emissions_tco2e" if tco2e else "emissions_quantity"
    rows = [{
        "source_id": s.get("id"),                        # stable key of the facility/aggregate source
        "name": s.get("name"),
        "sector": s.get("sector"), "subsector": s.get("subsector"),
        "source_type": s.get("sourceType"),              # point-source = single facility / non-point = aggregate
        "country": s.get("country"),
        "year": s.get("year"), "gas": s.get("gas"),      # gas defaults to co2e_100yr (100-year GWP basis)
        qkey: s.get("emissionsQuantity"),                # emissions (basis follows gas; key name follows basis)
        "capacity": s.get("capacity"), "capacity_units": s.get("capacityUnits"),
        "capacity_factor": s.get("capacityFactor"),      # 0.2.9 audit addition (SourceSummary 19-column alignment)
        "emissions_factor": s.get("emissionsFactor"),    # 0.2.9 audit addition
        "emissions_factor_units": s.get("emissionsFactorUnits"),  # 0.2.9 audit addition
        "activity": s.get("activity"), "activity_units": s.get("activityUnits"),
        "asset_type": s.get("assetType"),
        "location": ({"lat": (s.get("centroid") or {}).get("latitude"),
                      "lon": (s.get("centroid") or {}).get("longitude"),  # SRID 4326
                      "srid": (s.get("centroid") or {}).get("srid")}
                     if s.get("centroid") else None),
    } for s in (data if isinstance(data, list) else [])]
    total = sum(r[qkey] for r in rows if isinstance(r[qkey], (int, float)))
    return {"rows": rows, "count": len(rows),
            f"{qkey}_sum": round(total, 2) if rows else None}


def search_owners(name, *, limit=10, cache=None, no_cache=False):
    """-> {candidates[], limit_applied, _meta}; company candidates (LIKE search).

    Zero hits = upstream 404 JSON (measured 2026-10-23) — after the notFound declaration this becomes
    a legal empty candidate list (not an error)."""
    from ..transport import call_provider

    q = str(name or "").strip()
    if not q:
        raise SdkError("usage_error", provider="climatetrace", detail="search_owners requires name (company name)")
    size = min(max(1, int(limit or 10)), 50)
    try:
        r = call_provider(provider, "owners", {"name": q, "limit": size}, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_not_found":
            # 404="No owners matched": legal empty (notFound is not cached, meta minted on the spot — same convention as the gleif parent-company face)
            return {"candidates": [], "limit_applied": size, "_meta": {
                "from_cache": False,
                "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}}
        raise
    return {**owners_from_upstream(r["data"], size), "_meta": r}


def owners_raw(name, *, limit=10, offset=None, cache=None, no_cache=False):
    """0.2.0 flat face internals: name/limit/offset straight to upstream under their own names (zero hits -> empty candidates).

    -> {candidates[], limit_applied, params, _meta} — params are exactly the params sent upstream (echoed, replayable).
    Ordering is unstable across limits with offset (measured 2026-10-23), paging may skip or
    duplicate — on the candidate face fetch enough in one go."""
    from ..transport import call_provider

    q = str(name or "").strip()
    if not q:
        raise SdkError("usage_error", provider="climatetrace", detail="owners_raw requires name (company name, upstream param name)")
    size = min(max(1, int(limit or 10)), 50)  # politeness tier 50 (upstream has no cap; measured 2026-10-23, limit=1000 really returned 991 rows)
    params = {"name": q, "limit": size}
    if offset is not None:
        params["offset"] = int(offset)
    try:
        r = call_provider(provider, "owners", params, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_not_found":
            return {"candidates": [], "limit_applied": size, "params": params, "_meta": {
                "from_cache": False,
                "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}}
        raise
    return {**owners_from_upstream(r["data"], size), "params": params, "_meta": r}


def sources_raw(owner_ids=None, *, year=None, gas=None, limit=50, offset=None,
                sectors=None, subsectors=None, gadm_id=None, city_id=None,
                country_group=None, continent=None, cache=None, no_cache=False):
    """0.2.0 flat face internals; 0.2.9 audit parameter expansion: offset/sectors/subsectors/four location
    params folded in (2026-10-28 openapi + live probing).

    -> {rows[], count, <emissions_*_sum>, resolved_owner, year, gas, params, _meta}.
    owner_ids: a single E key or comma-joined multiples (comma = union with dedup, measured 2026-10-23
    12∪2→13; a repeated param = upstream silent first-wins trap, do not use); year has no local wall —
    an out-of-window year makes upstream return null, not an error (measured 2026-10-23 year=2020→200 null,
    data window starts 2021); gas defaults to co2e_100yr (row key emissions_tco2e), an explicit non-co2e
    gas switches the row key to emissions_quantity (native unit, measured 2026-10-23 gas=ch4, same shape).
    0.2.9 new params (all upstream names):
    - offset: real paging (probed 2026-10-28, offset=0/5 row sets have zero overlap; also effective within
      the ownerIds domain) — note ordering is unstable across limits (0.2.3 wall), offset paging may skip
      or duplicate; on the audit face fetch enough in one go.
    - sectors: 10-value closed set validated locally (SECTORS; + the special value all_no_forest =
      excludes forestry) — invalid values make the upstream **silently return the WHOLE corpus**
      (sectors=electricity returns a row set bit-for-bit identical to the unfiltered one, a
      false-negative trap, probed 2026-10-28); valid values really filter (forestry-and-land-use 5/5
      hits, all_no_forest top 10 has no forestry).
    - subsectors: pass-through, no local closed set (68-value enum at /v7/definitions/subsectors;
      invalid values get an upstream 400 self-describing "invalid subsector provided", not silent —
      probed 2026-10-28, upstream self-validation suffices).
    - four location params gadm_id/city_id/country_group/continent: pass-through (continent=Europe/Asia
      probed, filtering effective — RUS counts as Europe, not Asia; countryGroup takes a group slug from
      /v7/definitions/countrygroups, e.g. eu; eu probed, 5/5 rows in the EU list); upstream answers two
      concurrent location params with a 400 self-describing the four-param enum ("choose no more than
      one of: gadmId, countryGroup, continent, cityId") — mutual exclusion is upstream-proven, no local
      wall is set.
    - soft wall: at least one of owner_ids x sectors x subsectors x a location param — upstream allows a
      bare whole-corpus query (year alone already returns a 200 with the whole corpus), bulk corpus scans
      go through the batch pipeline service; this face's politeness tier intercepts.
    Row shape completed in 0.2.9: capacity_factor/emissions_factor/emissions_factor_units +
    location.srid (SourceSummary 19-column alignment, probed 2026-10-28, 18 keys all present)."""
    from ..transport import call_provider

    oid = str(owner_ids or "").strip()
    parts = []
    if oid:
        parts = [p.strip() for p in oid.split(",") if p.strip()]
        for p in parts:
            if not _E_ID.match(p):
                raise SdkError("usage_error", provider="climatetrace",
                               detail=f"owner_ids looks like E100000001492 (comma-separated for multiple owners; got {p!r})")
    sec = str(sectors).strip() if sectors is not None else None
    if sec is not None and sec not in SECTORS | SECTORS_SPECIAL:
        raise SdkError("usage_error", provider="climatetrace",
                       detail=f"sectors {sec!r} not in the closed set ("
                              + ", ".join(sorted(SECTORS | SECTORS_SPECIAL)) +
                              "; invalid values make the upstream silently return the whole corpus — the false-negative trap is intercepted here; enum = /v7/definitions/sectors, probed 2026-10-28)")
    try:
        want_year = int(year) if year is not None else datetime.now(timezone.utc).year
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="climatetrace", detail=f"year must be an integer year (got {year!r})")
    g = str(gas).strip() if gas is not None else None
    size = min(max(1, int(limit or 50)), 500)  # politeness tier 500 (upstream documents no paging param)
    loc = {"gadmId": gadm_id, "cityId": city_id, "countryGroup": country_group, "continent": continent}
    loc_params = {k: str(v).strip() for k, v in loc.items() if v not in (None, "")}
    if not parts and not sec and subsectors in (None, "") and not loc_params:
        raise SdkError("usage_error", provider="climatetrace",
                       detail="sources_raw requires at least one of owner_ids (E key), sectors/subsectors, "
                              "or a location param (gadm_id/city_id/country_group/continent) — a bare "
                              "whole-corpus scan goes through the batch pipeline service "
                              "(upstream allows it, but this face's politeness tier intercepts bulk corpus scans)")
    params = {"year": want_year, "limit": size}
    if parts:
        params["ownerIds"] = ",".join(parts)
    if offset is not None:
        params["offset"] = int(offset)
    if sec is not None:
        params["sectors"] = sec
    if subsectors not in (None, ""):
        params["subsectors"] = str(subsectors).strip()
    params.update(loc_params)
    if g is not None:
        params["gas"] = g
    r = call_provider(provider, "sources", params, cache=cache, no_cache=no_cache)
    tco2e = g in (None, "co2e_100yr")
    out = {**sources_from_upstream(r["data"], tco2e=tco2e),
           "year": want_year, "gas": g or "co2e_100yr", "params": params, "_meta": r}
    if parts:
        out["resolved_owner"] = {"trace_owner_ids": parts}
    return out


def owner_sources(owner_id=None, owner_name=None, *, year=None, limit=50, cache=None, no_cache=False):
    """-> {rows[], count, emissions_tco2e_sum, resolved_owner, year, _meta}; company emission-source rows.
    owner_id (E key) is the authoritative anchor; owner_name is fallback only, resolving to an id first
    (first candidate — same fallback semantics as eiti name: not authoritative normalization)."""
    from ..transport import call_provider

    oid = str(owner_id or "").strip()
    want_year = int(year) if year else datetime.now(timezone.utc).year
    if want_year < 2021:
        raise SdkError("usage_error", provider="climatetrace", detail="year must be a year >= 2021")
    if not oid:
        name = str(owner_name or "").strip()
        if not name:
            raise SdkError("usage_error", provider="climatetrace",
                           detail="owner_sources requires trace_owner_id (E key) or name (fallback: resolve to an id first)")
        s = search_owners(name, limit=5, cache=cache, no_cache=no_cache)
        if not s["candidates"]:
            return {**sources_from_upstream([]), "resolved_owner": None, "_meta": s["_meta"]}
        oid = s["candidates"][0]["trace_owner_id"]
    if not _E_ID.match(oid):
        raise SdkError("usage_error", provider="climatetrace", detail=f"trace_owner_id looks like E100000001492 (got {oid!r})")
    size = min(max(1, int(limit or 50)), 500)  # upstream exposes no explicit paging param — politeness tier truncates at 500
    r = call_provider(provider, "sources", {"ownerIds": oid, "year": want_year, "limit": size},
                      cache=cache, no_cache=no_cache)
    return {**sources_from_upstream(r["data"]), "resolved_owner": {"trace_owner_id": oid},
            "year": want_year, "_meta": r}
