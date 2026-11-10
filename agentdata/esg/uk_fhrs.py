"""uk_fhrs — UK Food Hygiene Rating Scheme live search (api.ratings.food.gov.uk; keyless).

esg food-safety face (0.3.53; admitted from research 册 290 uk-fsa-fhrs, probed live 2026-11-10,
tmp/probe-sdk0352/). The FSA FHRS/FHIS combined register is ~615,098 establishments live
2026-11-10 (meta.totalCount, unfiltered walk) — England/Wales/NI hygiene ratings 0-5 plus the
Scottish Pass/FHIS scheme in one corpus, refreshed daily (the bulk CSV blob rolls daily;
the API is the live query face). FHRSID is the hard key across all three publication channels
(bulk CSV, 385 local-authority XML files, this API); the company join is BusinessName+PostCode —
a weak key, no CH number rides the register.

The face rides the FULL /establishments search endpoint (ElasticSearch-backed, ~1s live), not
the /establishments/basic pager — the basic channel is a slow legacy path (45-50s per page from
this egress, measured live) and ships only 7 fields. The full endpoint ships 26-field rows:
address lines + PostCode, geocode, the three sub-scores (scores.confidence_in_management /
hygiene / structural), RatingValue + RatingKey + RatingDate, RightToReply, SchemeType
(FHRS/FHIS), NewRatingPending, business type and the local-authority block.

Walls (measured live 2026-11-10): the postcode= query parameter answers 403 on this endpoint —
for ANY value shape (SW1A 1AA encoded three ways, bare W1D3QU) while name/address/ratingKey/
localAuthorityId all answer 200 — so postcode is NOT a query parameter here (the PostCode FIELD
rides every row; filter client-side). The API demands the x-api-version: 2 header (extra_headers
channel). pagesize: 1-200 politeness cap (upstream tolerates 1000 — measured, not pinned).
Accept: application/json + honest agentdata UA = 200 (no UA gate).
No published quota → 1/2 polite, TTL 12h (daily-refresh register).
"""
provider = {
    "id": "uk_fhrs",
    "baseUrl": "https://api.ratings.food.gov.uk",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "establishments": {"path": "/establishments", "timeout": 45.0},
    },
    "ttl": {"establishments": 12 * 3600},
}


def establishments_raw(name=None, address=None, rating_key=None, local_authority_id=None,
                       *, page=1, pagesize=20, cache=None, no_cache=False):
    """→ {total_count, total_pages, page, page_size, count, rows[], params, _meta}.
    All filters optional and combinable (name/address are substring channels; rating_key is the
    scheme's own key e.g. fhrs_5_en-gb; local_authority_id the FSA's numeric authority id);
    rows are the 26-field establishment records verbatim."""
    from ..errors import SdkError
    from ..transport import call_provider

    params = {}
    for key, val in (("name", name), ("address", address),
                     ("ratingKey", rating_key), ("localAuthorityId", local_authority_id)):
        v = str(val or "").strip()
        if v:
            params[key] = v
    if local_authority_id is not None and not str(local_authority_id).isdigit():
        raise SdkError("usage_error", provider="uk_fhrs",
                       detail=f"local_authority_id must be the FSA's numeric authority id (e.g. 131), got {local_authority_id!r}")
    p = 1
    if page is not None:
        try:
            p = int(page)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="uk_fhrs", detail=f"page is 1-based, got {page!r}")
    if p < 1:
        raise SdkError("usage_error", provider="uk_fhrs", detail=f"page is 1-based, got {page!r}")
    params["page"] = p
    size = 20
    if pagesize is not None:
        try:
            size = int(pagesize)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="uk_fhrs",
                           detail=f"pagesize must be an integer 1-200, got {pagesize!r}")
    if not 1 <= size <= 200:
        raise SdkError("usage_error", provider="uk_fhrs",
                       detail=f"pagesize must be 1-200 (politeness cap; upstream tolerates 1000), got {pagesize!r}")
    params["pagesize"] = size

    r = call_provider(provider, "establishments", params, cache=cache, no_cache=no_cache,
                      extra_headers={"x-api-version": "2"})
    doc = r["data"] or {}
    meta = doc.get("meta") or {}
    if "establishments" not in doc:
        raise SdkError("upstream_unavailable", provider="uk_fhrs",
                       detail="the FHRS API answered an unexpected shape (no establishments key — maintenance or shape drift)")
    return {"total_count": meta.get("totalCount"), "total_pages": meta.get("totalPages"),
            "page": meta.get("pageNumber", p), "page_size": meta.get("pageSize", size),
            "count": len(doc["establishments"]), "rows": doc["establishments"],
            "params": params, "_meta": r}
