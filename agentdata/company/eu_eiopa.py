"""eu_eiopa — EIOPA register of occupational pension schemes (IORPs), the public data
exchange API (registers.eiopa.europa.eu/publicdataexchange-api-prod/api/iorps, keyless).

EU company face (0.3.59; admitted from research booklet eu-eiopa-iorps 册 465 — the IORP
register's 6,099 occupational pension schemes (and institutions) were already harvested as
raw (eu-eiopa-iorps-pensions); this is the LIVE query channel, re-probed 2026-11-13,
tmp/probe-sdk-0359/r2_eiopa*.json). One face: the IORP register — per scheme the official
name, home/operating country, NCA, address, managing entity, registration window,
cross-border status, LEI, id code, website — the pension-supervisor view of who may operate.

CONTRACT (POST JSON — GET answers 404; the body is a data-table query):
{"page" (1-BASED — page 0 answers 400, measured), "pageSize" (≤100), "sortField": "id"
(mandatory — an invalid sortField silently clamps to totalItems: 0), "sortOrder": "asc",
"filters": {}}. Response {items[], totalItems: 6099, populatedColumns: [18 keys]}.
Item keys (18, all measured non-null-capable): ncaName, officialName, homeCountry,
euOperationCountry, typeOfIorp, streetName, streetNumber, postCode, city,
legalNameOfManagingEntity, addressOfManagingEntity, registrationStartDate (DD/MM/YYYY),
registrationEndDate, crossBorderStatus, crossBorderActivity, lei, idCode, websiteAddress.
The face replays the measured envelope: sortField/sortOrder hardcoded (the silent-zero trap
makes sort sugar a footgun), filters exposed as nothing (the filter vocabulary is the data
table's own — unmeasured shapes unexposed). Enumeration face: page through 6,099 rows.
snake_case rows, dates passed verbatim (DD/MM/YYYY is the upstream contract). 0.5/2 polite,
TTL 24h.
"""
from ..errors import SdkError

provider = {
    "id": "eu_eiopa",
    "baseUrl": "https://registers.eiopa.europa.eu",
    "rate": {"rps": 0.5, "burst": 2},
    "concurrency": 2,
    "ops": {
        "iorps": {"path": "/publicdataexchange-api-prod/api/iorps", "method": "POST",
                  "idempotent": True, "timeout": 45.0},
    },
    "ttl": {"iorps": 24 * 3600},
}

_SNAKE = {
    "ncaName": "nca", "officialName": "official_name", "homeCountry": "home_country",
    "euOperationCountry": "operating_country", "typeOfIorp": "type",
    "streetName": "street", "streetNumber": "street_number", "postCode": "post_code",
    "city": "city", "legalNameOfManagingEntity": "managing_entity",
    "addressOfManagingEntity": "managing_entity_address",
    "registrationStartDate": "registration_start", "registrationEndDate": "registration_end",
    "crossBorderStatus": "cross_border_status", "crossBorderActivity": "cross_border_activity",
    "lei": "lei", "idCode": "id_code", "websiteAddress": "website",
}


def row_from_upstream(d):
    """IORP card (pure function — split out for offline testing)."""
    return {v: d.get(k) for k, v in _SNAKE.items()}


def iorps_raw(limit=100, page=1, *, cache=None, no_cache=False):
    """→ {total, rows[], params, populated_columns, _meta}. limit = pageSize wall 1-100
    (>100 unmeasured — walled); page 1-based (0 = upstream 400). Enumeration face —
    no term filter (the register's own data-table filter vocabulary is unmeasured and
    stays unexposed); 6,099 rows live."""
    try:
        size = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="eu_eiopa",
                       detail=f"limit must be an integer 1-100, got {limit!r}")
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="eu_eiopa",
                       detail=f"limit must be 1-100 (pageSize; >100 unmeasured), got {limit!r}")
    try:
        pg = int(page) if page is not None else 1
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="eu_eiopa",
                       detail=f"page must be an integer >=1, got {page!r}")
    if pg < 1:
        raise SdkError("usage_error", provider="eu_eiopa",
                       detail=f"page is 1-BASED (page 0 answers upstream 400, measured), got {pg}")
    from ..transport import call_provider
    body = {"page": pg, "pageSize": size, "sortField": "id", "sortOrder": "asc", "filters": {}}
    r = call_provider(provider, "iorps", body, cache=cache, no_cache=no_cache)
    doc = r["data"]
    if not isinstance(doc, dict) or "items" not in doc:
        raise SdkError("upstream_unavailable", provider="eu_eiopa",
                       detail="iorps answered an unexpected shape (no items — a "
                              "totalItems-0-shaped body means sortField drifted from 'id')")
    return {"total": doc.get("totalItems"),
            "rows": [row_from_upstream(x) for x in doc.get("items") or []],
            "populated_columns": doc.get("populatedColumns"),
            "params": {"limit": size, "page": pg}, "_meta": r}
