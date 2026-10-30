"""epa_frs — EPA FRS facility master registry Envirofacts efservice provider (keyless).

FRS (Facility Registry Service) = the authoritative key source of the shared facility master registry in the
esg domain (ECHO/TRI/GHGRP converge on the Registry ID); this face opens a facility point query:
the frs_facility_site table has 5,602,878 rows and 52 columns.
Measured shape (probed 2026-10-29):
- Real host **data.epa.gov/efservice** (enviro.epa.gov redirects 301 to the same path; the old
  ofmpub.epa.gov is 404).
- Filter syntax = **column/operator/value as three separate path segments**: `/STATE_CODE/=/DE/` — a
  single segment `/=DE/` silently returns []; the table name must be lowercase (FRS_FACILITY_SITE in
  uppercase = silent empty result, not an error); multiple filters chain into AND
  (STATE_CODE+City_NAME hit as measured); values are URL-encoded (space->%20, exact names verified).
- Paging `/ROWS/{start}:{end}/` is a **closed interval** (0:2 = 3 rows); **when end<start the upstream
  silently degrades to offset=start with an unbounded dump** (ROWS/3:2 measured 18,791 rows = DE
  18,794−3) — this face pins end=start+size−1, which is always valid, and never omits the ROWS segment
  (omitting it dumps the whole 5.6M-row table).
- Operator lineage: the `=` family works; **`~`/`!~`/LIKE silently return 0** (do not use); **a value
  containing % gives nginx 403** (WAF).
- Name search is therefore an **exact match** (PRIMARY_NAME/=/MILTON RIVERFRONT LLC/ verified) —
  fuzzy facility-name search goes through the ECHO face (a separate line); this face adds no sugar.
- Total `/COUNT/JSON` -> [{TOTALQUERYRESULTS}] (same syntax in filtered state, DE=18,794 as measured).
  52 columns of note: registry_id (authoritative key) /primary_name/std_name/address family
  (location_address·city·county·state·postal·std_* standardized family)/site_type_name/
  interest_status_code/operating_status/epa_region_code/parent_registry_id/fips_code. This table has
  **no coordinate columns** (lat/long live in other FRS tables).
Politeness tier: size<=500, rate 1rps; every call = rows + count (two requests) (total_matches contract).
"""
from ..errors import SdkError

provider = {
    "id": "epa_frs",
    "baseUrl": "https://data.epa.gov/efservice",
    "rate": {"rps": 1.0, "burst": 2},
    # ops are dynamic: the paths of facilities/count are assembled at call time from the effective filter columns (_op_for) —
    # the build_url {token} template eats the filter values (quoted, space->%20 is exactly the verified form).
    # ttl at the top level must be a dict (transport's fallback lookup is eager) — the real values hang on the dynamic opdef.
    "ops": {},
    "ttl": {},
}

_FILTERS = ("registry_id", "primary_name", "state_code", "city_name")  # order = URL segment order (stable, replayable)
TTL = 86400


def _op_for(cols, *, count=False):
    """Effective filter columns -> efservice path template (three-segment separated operator form; count=True takes /COUNT/JSON)."""
    segs = "".join(f"/{c.upper()}/=/{{{c}}}" for c in cols)
    tail = "/COUNT/JSON" if count else "/ROWS/{start}:{end}/JSON"
    return {"path": f"/frs_facility_site{segs}{tail}", "ttl": TTL}


def _polite_size(v, dflt):
    """Politeness tier 500 (rows average ~1.5KB across 52 fat columns; upstream has no hard limit, but an invalid ROWS segment = the unbounded-dump trap)."""
    return min(max(1, int(v or dflt)), 500)


def facilities_from_upstream(data, size, start):
    """Upstream response -> facilities face result (pure function, offline-testable; projects 18 of the 52 columns)."""
    rows = [{
        "registry_id": f.get("registry_id"),            # authoritative FRS facility key (ECHO/TRI/GHGRP convergence anchor)
        "primary_name": f.get("primary_name"),
        "std_name": f.get("std_name"),
        "location_address": f.get("location_address"),
        "city_name": f.get("city_name"),
        "county_name": f.get("county_name"),
        "state_code": f.get("state_code"),
        "state_name": f.get("state_name"),              # dirty upstream (measured: empty strings and the 'DE' abbreviation form)
        "postal_code": f.get("postal_code"),
        "country_name": f.get("country_name"),
        "std_full_address": f.get("std_full_address"),  # USPS standardized full address
        "site_type_name": f.get("site_type_name"),
        "interest_status_code": f.get("interest_status_code"),
        "operating_status": f.get("operating_status"),
        "epa_region_code": f.get("epa_region_code"),
        "parent_registry_id": f.get("parent_registry_id"),  # parent facility key (not the corporate parent)
        "fips_code": f.get("fips_code"),
        "create_date": f.get("create_date"),
    } for f in (data or []) if isinstance(f, dict)]
    return {"rows": rows, "count": len(rows), "limit_applied": size, "offset": start}


def _norm_filters(registry_id, primary_name, state_code, city_name):
    out = {}
    for k, v in (("registry_id", registry_id), ("primary_name", primary_name),
                 ("state_code", state_code), ("city_name", city_name)):
        v = str(v or "").strip()
        if k == "state_code" and v:
            v = v.upper()  # upstream uses the two-letter abbreviation form; tolerate lowercase input
        if v:
            out[k] = v
    return out


def facilities_raw(registry_id=None, primary_name=None, state_code=None, city_name=None, *,
                   start=0, size=50, cache=None, no_cache=False):
    """0.3.2 flat face internals: four filter columns (all `=` exact, combinable = AND) + start/size paging.

    Every call makes two requests: rows (ROWS/{start}:{end} closed interval, end always computed locally)
    + count (TOTALQUERYRESULTS).
    -> {rows[], count, limit_applied, offset, total_matches, params, _meta, _count_meta}.
    Local safety wall: at least one of the four filters (a bare scan of all 5,602,878 rows is served by
    the batch pipeline as national_single.zip)."""
    from ..transport import call_provider

    filters = _norm_filters(registry_id, primary_name, state_code, city_name)
    if not filters:
        raise SdkError("usage_error", provider="epa_frs",
                       detail="facilities_raw requires at least one of registry_id / primary_name / state_code / "
                              "city_name (local safety wall: a bare scan of all 5,602,878 rows is served by the "
                              "batch pipeline as national_single.zip)")
    cols = [c for c in _FILTERS if c in filters]
    sz = _polite_size(size, 50)
    st = max(0, int(start or 0))
    end = st + sz - 1  # right end of the closed interval; always >= start — an invalid ROWS segment = unbounded upstream dump (trap noted in the header)
    params = {**filters, "start": st, "end": end}
    dyn = {**provider, "ops": {"facilities": _op_for(cols)}}
    r = call_provider(dyn, "facilities", params, cache=cache, no_cache=no_cache)
    dync = {**provider, "ops": {"count": _op_for(cols, count=True)}}
    rc = call_provider(dync, "count", dict(filters), cache=cache, no_cache=no_cache)
    total = None
    if isinstance(rc["data"], list) and rc["data"]:
        total = rc["data"][0].get("TOTALQUERYRESULTS")
    out = facilities_from_upstream(r["data"], sz, st)
    return {**out, "total_matches": total, "filters": filters,
            "params": params, "_meta": r, "_count_meta": rc}
