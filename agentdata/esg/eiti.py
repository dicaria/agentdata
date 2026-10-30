"""eiti — EITI extractives transparency database provider (Datasette instance; keyless).

Counterpart to the Node implementation (esg domain Wave 3, P0). eiti-database.eiti.org.
2026-10-20 measured shape: view path /eiti_database/{view}.json?_size=N&_shape=objects&<col>__like=<pattern>
(**the SQL face ?sql= errors out on views — unusable** — a view is not a table; filtering goes through
the Datasette magic params __like/__exact);
real column names: eiti_id_company values look like "eiti_id_company:<UUID>" (with the prefix!),
hq_country_name, first_year_reported/last_year_reported; with _shape=objects the rows are already
dicts (do not zip columns again).
view_payments_detailed has 104,484 rows, view_companies has 10,200 companies; companies carry no local
registration number (the UUID is the stable key).
2026-10-21 audit batch B probe (gates 1-2):
**_size has no 100 cap** (the earlier note "upstream really caps at 100" was a 0.1.8 mis-recording) —
measured 11,000 rows per call sent as-is, not clamped;
our politeness cap is 1,000 (the realtime single-query face does not chase bulk; bulk goes through the
corpus batch pipeline). `_extra=count` is officially supported:
it returns count = total matching rows ignoring paging, but **count itself is capped at 10,001**
(count_truncated=true means ">=10,001").
__like= is SQL LIKE (%/_ metacharacters apply to user input verbatim; ASCII case-insensitive as measured),
__exact = equality.
Column fill rates (Equinor slice, 358 rows measured): gov_entity_name 100% / gfs_code 92.5% /
payment_value_usd 88.3% (in-kind payments etc. have no USD) / project_name 50.6% (across the whole
surface, not 23%).
companies face: hq_country_name fill rate is only 62/10,201 (hq_country is mostly null); estma_id has
90 companies = ESTMA (Extractive Industries Transparency Standard) filers, **including foreign-owned
companies operating in Canada** (AngloGold Ghana etc.), not "Canadian companies only".
TTL 7 days (last_updated rolls slowly); politeness tier 0.5 rps.
"""
from ..errors import SdkError

provider = {
    "id": "eiti",
    "baseUrl": "https://eiti-database.eiti.org",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "companies": {"path": "/eiti_database/view_companies.json"},        # params: company_name__like + _size/_shape/_extra
        "payments": {"path": "/eiti_database/view_payments_detailed.json"},  # params: eiti_id_company__exact | company_name__like + _size/_shape/_extra
    },
    "ttl": {"companies": 7 * 86400, "payments": 7 * 86400},
}


def _rows_of(data):
    return (data or {}).get("rows") if isinstance(data, dict) else (data if isinstance(data, list) else [])


def _norm_id(v):
    """eiti_id_company official values carry the "eiti_id_company:" prefix — add it when the caller passes a bare UUID."""
    s = str(v or "").strip()
    if not s:
        return ""
    return s if s.startswith("eiti_id_company:") else f"eiti_id_company:{s}"


def _polite_size(v, dflt):
    """Our politeness cap is 1,000 (the realtime single-query face does not chase bulk) — upstream has no hard 100 limit as measured (probe 2026-10-21, >=11,000 per call)."""
    return min(max(1, int(v or dflt)), 1000)


def total_display(n, capped):
    """Display form of the upstream count: count_truncated=true means count itself is capped at 10,001 -> display ">10000"."""
    if n is None:
        return "?"
    return f">{n - 1}" if capped else str(n)


def companies_from_upstream(data, size):
    """Upstream response -> companies face result (pure function, offline-testable)."""
    candidates = [{
        "eiti_id_company": _norm_id(c.get("eiti_id_company")),  # own stable UUID (no local registration number)
        "company_name": c.get("company_name"),
        "hq_country": c.get("hq_country_name"),                 # fill rate only 62/10,201 (measured 2026-10-21) — mostly null
        "sectors": c.get("sectors"),
        "countries_of_operation": c.get("countries_of_operation"),
        "estma_id": c.get("estma_id"),                          # ESTMA filer id; filers include foreign-owned companies operating in Canada
        "first_year_reported": c.get("first_year_reported"),
        "last_year_reported": c.get("last_year_reported"),
    } for c in _rows_of(data)]
    return {
        "candidates": candidates,
        "limit_applied": size,                                  # truncation visible (limit contract)
        "total_matches": data.get("count") if isinstance(data, dict) and isinstance(data.get("count"), int) else None,
        "total_matches_capped": bool(isinstance(data, dict) and data.get("count_truncated")),
    }


def payments_from_upstream(data, size):
    """Upstream response -> payments face result (pure function, offline-testable)."""
    rows = [{
        "eiti_id_company": _norm_id(p.get("eiti_id_company")),
        "company_name": p.get("company_name"),
        "year": p.get("year"),
        "country_iso3": p.get("country_iso3"),              # country where the payment happened (resource country)
        "project_name": p.get("project_name"),              # fill rate about half (Equinor slice 50.6%, measured 2026-10-21)
        "gov_entity": p.get("gov_entity_name"),             # receiving government body (named down to bureau level; 100% non-null in the slice)
        "revenue_stream": p.get("revenue_stream_name"),     # tax type, upstream verbatim name
        "gfs_code": p.get("gfs_code"), "gfs_name": p.get("gfs_name"),  # IMF GFS standard classification (92.5% non-null in the slice)
        "payment_value": p.get("payment_value"),            # local currency
        "payment_value_usd": p.get("payment_value_usd"),    # official conversion (basis varies across filing batches; 88.3% non-null in the slice)
        "payment_in_kind": p.get("payment_in_kind"),        # in-kind payment flag
    } for p in _rows_of(data)]
    return {
        "rows": rows, "count": len(rows),
        "limit_applied": size,                              # truncation visible (limit contract)
        "total_rows": data.get("count") if isinstance(data, dict) and isinstance(data.get("count"), int) else None,
        "total_rows_capped": bool(isinstance(data, dict) and data.get("count_truncated")),
    }


def search_companies(name, *, limit=10, cache=None, no_cache=False):
    """-> {candidates[], limit_applied, total_matches, _meta}; extractives company candidates
    (name LIKE search, ASCII case-insensitive; %/_ metacharacters apply verbatim; candidates are not authoritative normalization)."""
    from ..transport import call_provider

    q = str(name or "").strip()
    if not q:
        raise SdkError("usage_error", provider="eiti", detail="search_companies requires name")
    size = _polite_size(limit, 10)
    r = call_provider(provider, "companies", {
        "company_name__like": f"%{q}%",
        "_size": size,
        "_shape": "objects",
        "_extra": "count",  # total matches ignoring paging (capped at 10,001, flagged by total_matches_capped)
    }, cache=cache, no_cache=no_cache)
    return {**companies_from_upstream(r["data"], size), "_meta": r}


def company_payments(eiti_id=None, name=None, *, limit=50, cache=None, no_cache=False):
    """-> {rows[], count, limit_applied, total_rows, _meta}; company->government payment rows (eiti_id is the authoritative anchor; name is fallback only).
    Rich row keys: gov_entity_name named down to bureau level + gfs_code (IMF GFS standard revenue classification — the key for cross-country comparability).
    total_rows = upstream _extra=count (capped at 10,001, flagged by total_rows_capped) — the in-page sum is only a subtotal, not the company's total (lesson P1-3)."""
    from ..transport import call_provider

    eid = _norm_id(eiti_id)
    q = str(name or "").strip()
    if not eid and not q:
        raise SdkError("usage_error", provider="eiti", detail="company_payments requires eiti_id or name")
    params = {"eiti_id_company__exact": eid} if eid else {"company_name__like": f"%{q}%"}
    size = _polite_size(limit, 50)
    r = call_provider(provider, "payments", {
        **params,
        "_size": size,
        "_shape": "objects",
        "_extra": "count",  # total rows ignoring paging (capped at 10,001, flagged by total_rows_capped)
    }, cache=cache, no_cache=no_cache)
    return {**payments_from_upstream(r["data"], size), "_meta": r}


def companies_raw(company_name__like, *, size=10, cache=None, no_cache=False):
    """0.2.0 flat face internals: company_name__like straight to upstream under its own name (%/_ metacharacters yours to manage).

    -> {candidates[], limit_applied, total_matches, total_matches_capped, params, _meta}
    — params are exactly the params sent upstream (including the _size/_shape/_extra magic params)."""
    from ..transport import call_provider

    like = str(company_name__like or "").strip()
    if not like:
        raise SdkError("usage_error", provider="eiti",
                       detail="companies_raw requires company_name__like (Datasette magic param, upstream name; %/_ yours to manage)")
    sz = _polite_size(size, 10)
    params = {"company_name__like": like, "_size": sz, "_shape": "objects", "_extra": "count"}
    r = call_provider(provider, "companies", params, cache=cache, no_cache=no_cache)
    return {**companies_from_upstream(r["data"], sz), "params": params, "_meta": r}


def payments_raw(eiti_id_company__exact=None, company_name__like=None, *, size=50,
                 cache=None, no_cache=False):
    """0.2.0 flat face internals: eiti_id_company__exact / company_name__like straight to upstream under their own names.

    Both filters may be combined (AND across different upstream columns); at least one is required by a client-layer wall
    (a bare scan of all 104,484 rows belongs to the batch pipeline).
    -> {rows[], count, limit_applied, total_rows, total_rows_capped, params, _meta}."""
    from ..transport import call_provider

    eid = str(eiti_id_company__exact or "").strip() or None
    like = str(company_name__like or "").strip() or None
    if not eid and not like:
        raise SdkError("usage_error", provider="eiti",
                       detail="payments_raw requires at least one of eiti_id_company__exact or company_name__like")
    sz = _polite_size(size, 50)
    params = {"_size": sz, "_shape": "objects", "_extra": "count"}
    if eid:
        params["eiti_id_company__exact"] = eid
    if like:
        params["company_name__like"] = like
    r = call_provider(provider, "payments", params, cache=cache, no_cache=no_cache)
    return {**payments_from_upstream(r["data"], sz), "params": params, "_meta": r}
