"""wb — World Bank Open Data provider (api.worldbank.org; keyless).

Three faces born flat: wdi_values (country x indicator x year window), wdi_indicators (the
indicator catalog), countries (the ISO3/ISO2 + income-level + region reference).

Shapes verified by first-hand live probing 2026-11-02 (tmp/probe-economy/):
GET /v2/country/{country}/indicator/{indicator}?format=json&date=YYYY:YYYY&per_page=N
  -> [meta, rows]; meta = {page, pages, per_page, total, sourceid, lastupdated}
  -> rows = {indicator:{id,value}, country:{id,value}, countryiso3code, date, value, unit,
             obs_status, decimal}
  * several countries in one call via the `;` separator (CHN;JPN over 2020:2023 -> 8 rows);
  * several indicators via `;` is REJECTED upstream ("120 Invalid value") -> one indicator per
    call, enforced locally (the mirror of an upstream wall, not a local invention);
  * `date` takes "YYYY" or "YYYY:YYYY" (the upstream range form); `value` is null for a missing
    observation — null is kept as null (a gap is a fact, never fabricated);
  * sourceid=2 is the WDI source.
GET /v2/indicator?format=json&source=2&per_page=500
  -> the 1,445 WDI indicators in one page (572 KB). WITHOUT source= the catalog is every World
    Bank source at once (29,544 rows / 5,909 pages) -> source=2 is the default here.
  -> row = {id, name, unit, source:{id,value}, sourceNote, sourceOrganization, topics[]}
GET /v2/country?format=json&per_page=N
  -> rows = {id (ISO3), iso2Code, name, region{}, adminregion{}, incomeLevel{}, lendingType{},
             capitalCity, longitude, latitude} — the country reference table (income group =
     the CLASS grouping used as a buyer screen).
Rate: no official limit published -> polite tier 1 rps / burst 2. TTL: values 24h (quarterly
cadence, the meta carries lastupdated), catalogs 7 days.
"""
from ..errors import SdkError

provider = {
    "id": "wb",
    "baseUrl": "https://api.worldbank.org",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "wdi_values": {"path": "/v2/country/{country}/indicator/{indicator}",
                       "notFound": [404]},          # params: date/per_page
        "wdi_indicators": {"path": "/v2/indicator", "notFound": [404]},   # params: source/page/per_page
        "countries": {"path": "/v2/country", "notFound": [404]},          # params: page/per_page
    },
    "ttl": {"wdi_values": 24 * 3600, "wdi_indicators": 7 * 86400,
            "countries": 7 * 86400},
}

_PER_PAGE_CAP = 1000  # upstream accepts large pages; 1,000 keeps one catalog page a sane payload


def _iso3_list(country):
    """Country argument -> the upstream path form. Accepts a single ISO3 code or a list;
    the upstream separator is `;` (verified: CHN;JPN in one path segment)."""
    if isinstance(country, (list, tuple)):
        items = [str(x).strip().upper() for x in country if str(x).strip()]
    else:
        items = [x.strip().upper() for x in str(country or "").split(";") if x.strip()]
    if not items:
        raise SdkError("usage_error", provider="wb",
                       detail="wb_wdi_values requires --country (ISO3 code, e.g. CHN; several codes may be joined with ';')")
    return ";".join(items)


def _split_payload(payload):
    """The API answers [meta, rows] — an error answer is a single [{message:[...]}] object."""
    if isinstance(payload, list) and payload and isinstance(payload[0], dict) and "message" in payload[0]:
        msg = payload[0]["message"]
        raise SdkError("upstream_unavailable", provider="wb",
                       detail=f"World Bank API error {msg[0].get('id') if msg else '?'}: "
                              f"{msg[0].get('value') if msg else payload}")
    if not isinstance(payload, list) or len(payload) < 2:
        raise SdkError("upstream_unavailable", provider="wb",
                       detail=f"Unexpected World Bank payload shape: {str(payload)[:160]!r}")
    return payload[0] or {}, payload[1] or []


def _value_row(r):
    ind = r.get("indicator") or {}
    ctry = r.get("country") or {}
    return {
        "indicator_code": ind.get("id"),
        "indicator_name": ind.get("value"),
        "country_iso3": r.get("countryiso3code") or ctry.get("id"),
        "country_name": ctry.get("value"),
        "year": r.get("date"),
        "value": r.get("value"),
        "unit": r.get("unit") or None,
        "obs_status": r.get("obs_status") or None,
        "decimal": r.get("decimal"),
    }


def wdi_values_raw(country, indicator, *, date=None, per_page=100, cache=None, no_cache=False):
    """-> {total, count, rows, params, last_updated, _meta}; /v2/country/{c}/indicator/{i}.
    country = ISO3 code or a list (upstream `;` separator); indicator = one WDI code (the
    upstream rejects several codes in one path segment -> one per call); date = "YYYY" or
    "YYYY:YYYY" (upstream range form); per_page 1-1000. A null value is a missing
    observation and stays null."""
    from ..transport import call_provider

    ctry = _iso3_list(country)
    ind = str(indicator or "").strip()
    if not ind:
        raise SdkError("usage_error", provider="wb",
                       detail="wb_wdi_values requires --indicator (a WDI code, e.g. NY.GDP.MKTP.CD)")
    if ";" in ind:
        raise SdkError("usage_error", provider="wb",
                       detail="The World Bank API rejects several indicator codes in one call "
                              "(upstream \"120 Invalid value\") — pass one --indicator per call")
    pp = int(per_page or 100)
    if not 1 <= pp <= _PER_PAGE_CAP:
        raise SdkError("usage_error", provider="wb", detail=f"per_page must be 1-{_PER_PAGE_CAP}")
    params = {"format": "json", "per_page": pp}
    if date:
        params["date"] = str(date).strip()
    r = call_provider(provider, "wdi_values", dict(params, country=ctry, indicator=ind),
                      cache=cache, no_cache=no_cache)
    meta, rows = _split_payload(r["data"])
    return {"total": meta.get("total"), "count": len(rows),
            "rows": [_value_row(x) for x in rows],
            "pages": meta.get("pages"), "page": meta.get("page"),
            "last_updated": meta.get("lastupdated"),
            "params": {"country": ctry, "indicator": ind, "date": params.get("date"),
                       "per_page": pp},
            "_meta": r}


def _indicator_row(x):
    src = x.get("source") or {}
    return {
        "indicator_code": x.get("id"),
        "name": x.get("name"),
        "unit": x.get("unit") or None,
        "source_id": src.get("id"),
        "source_name": src.get("value"),
        "source_note": x.get("sourceNote"),
        "source_organization": x.get("sourceOrganization"),
        "topics": [t.get("value") for t in (x.get("topics") or []) if isinstance(t, dict)],
    }


def wdi_indicators_raw(*, source=2, page=1, per_page=500, search=None,
                       cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /v2/indicator?format=json&source=..
    source = the World Bank source id (2 = WDI, the default here; without it the catalog is
    every source at once — 29,544 rows). search = a local keyword scan over the returned page
    (name / sourceOrganization / sourceNote), never an upstream filter."""
    from ..transport import call_provider

    src = str(source if source is not None else 2).strip() or "2"
    pp = int(per_page or 500)
    if not 1 <= pp <= _PER_PAGE_CAP:
        raise SdkError("usage_error", provider="wb", detail=f"per_page must be 1-{_PER_PAGE_CAP}")
    pg = int(page or 1)
    if pg < 1:
        raise SdkError("usage_error", provider="wb", detail="page must be >= 1")
    params = {"format": "json", "source": src, "per_page": pp, "page": pg}
    r = call_provider(provider, "wdi_indicators", params, cache=cache, no_cache=no_cache)
    meta, rows = _split_payload(r["data"])
    out = [_indicator_row(x) for x in rows]
    q = str(search or "").strip().lower()
    if q:
        out = [x for x in out
               if q in (x["indicator_code"] or "").lower() or q in (x["name"] or "").lower()
               or q in (x["source_organization"] or "").lower() or q in (x["source_note"] or "").lower()]
    return {"total": meta.get("total"), "count": len(out), "rows": out,
            "page": meta.get("page"), "pages": meta.get("pages"),
            "params": {"source": src, "page": pg, "per_page": pp, "search": q or None},
            "_meta": r}


def _country_row(x):
    region = x.get("region") or {}
    income = x.get("incomeLevel") or {}
    lending = x.get("lendingType") or {}
    admin = x.get("adminregion") or {}
    return {
        "iso3": x.get("id"),
        "iso2": x.get("iso2Code"),
        "name": x.get("name"),
        "region_id": region.get("id") or None,
        "region_name": region.get("value") or None,
        "admin_region": admin.get("value") or None,
        "income_level_id": income.get("id") or None,
        "income_level": income.get("value") or None,
        "lending_type_id": lending.get("id") or None,
        "lending_type": lending.get("value") or None,
        "capital_city": x.get("capitalCity"),
        "longitude": x.get("longitude"),
        "latitude": x.get("latitude"),
    }


def countries_raw(*, page=1, per_page=100, cache=None, no_cache=False):
    """-> {total, count, rows, params, _meta}; /v2/country?format=json
    The country reference: ISO3 / ISO2 / region / income level / lending type / coordinates
    (the buyer-screen dimension; income level = the World Bank CLASS grouping)."""
    from ..transport import call_provider

    pp = int(per_page or 100)
    if not 1 <= pp <= _PER_PAGE_CAP:
        raise SdkError("usage_error", provider="wb", detail=f"per_page must be 1-{_PER_PAGE_CAP}")
    pg = int(page or 1)
    if pg < 1:
        raise SdkError("usage_error", provider="wb", detail="page must be >= 1")
    params = {"format": "json", "per_page": pp, "page": pg}
    r = call_provider(provider, "countries", params, cache=cache, no_cache=no_cache)
    meta, rows = _split_payload(r["data"])
    return {"total": meta.get("total"), "count": len(rows),
            "rows": [_country_row(x) for x in rows],
            "page": meta.get("page"), "pages": meta.get("pages"),
            "params": {"page": pg, "per_page": pp}, "_meta": r}
