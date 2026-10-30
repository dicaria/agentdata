"""ctgov — ClinicalTrials.gov API v2 (clinical-trial lookup face; keyless; polite tier 2 rps).

Positioning: fresh single lookups on top of the bulk line (us/clinicaltrials full harvest) — sponsor search / status filter / single-NCT semantics.
TTL: search 7 days (trial records change slowly; the published results page is authoritative).
Query construction: company → AREA[LeadSponsorName]("…"); status → AREA[OverallStatus](…); a free query expression is AND-joined.
"""

provider = {
    "id": "ctgov",
    "baseUrl": "https://clinicaltrials.gov/api/v2",
    "rate": {"rps": 2, "burst": 4},
    "ops": {
        "search": {"path": "/studies", "ttl": 7 * 86400},
    },
}


def _row_from_study(s: dict) -> dict:
    p = s.get("protocolSection") or {}
    ident = p.get("identificationModule") or {}
    st = s.get("statusModule") or {}
    sponsor = ((p.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}).get("name")
    phases = (p.get("designModule") or {}).get("phases") or []
    nct = ident.get("nctId")
    return {
        "nct_id": nct,
        "title": ident.get("briefTitle"),
        "status": st.get("overallStatus"),
        "phase": " + ".join(phases) or None,
        "sponsor": sponsor,
        "start_date": (st.get("startDateStruct") or {}).get("date"),
        "url": f"https://clinicaltrials.gov/study/{nct}" if nct else None,
    }


def search_trials(company=None, query=None, status=None, limit=10, cache=None, no_cache: bool = False) -> dict:
    from ..transport import call_provider
    from ..errors import SdkError

    terms = []
    if company:
        terms.append(f'AREA[LeadSponsorName]("{company}")')
    if status:
        terms.append(f"AREA[OverallStatus]({status})")
    if query:
        terms.append(query)
    if not terms:
        raise SdkError("op_unknown", provider="ctgov", detail="trials needs at least one of company / query / status")
    r = call_provider(provider, "search",
                      {"query.term": " AND ".join(terms),
                       "pageSize": min(50, max(1, int(limit))), "countTotal": "true"},
                      cache=cache, no_cache=no_cache)
    studies = (r["data"] or {}).get("studies") or []
    return {"total": (r["data"] or {}).get("totalCount"),
            "rows": [_row_from_study(s) for s in studies], "_meta": r}


def search_raw(*, query_term=None, query_titles=None, query_intr=None, query_cond=None,
               filter_advanced=None, agg_filters=None, fields=None, page_size=20,
               page_token=None, sort=None, count_total=True, cache=None, no_cache: bool = False) -> dict:
    """0.2.0 mirror face: upstream param names verbatim (query.term/query.titles/query.intr/query.cond/filter.advanced/
    aggFilters/fields/pageSize/pageToken/sort/countTotal).

    No cap: the pageSize docs say <=1000 but 1001 was measured returning all 200 rows (probed 2026-10-23, the limit is not enforced) — we only guarantee >=1;
    a bare call is legal (the upstream default = page 1 of the whole database, countTotal gives the total); a free sort string passes through (measured EnrollmentCount:desc works).
    0.2.8 added four params (all verified by probing on 2026-10-28): query.titles = title-field search (aspirin 2983→967),
    query.intr = intervention field (insulin 21109→8229), aggFilters = facet filter (phase:3 → 583; **the value domain is a numeric enum**,
    spelling PHASE3 gives 0 hits, not an error), fields = row slimming (NCTId,BriefTitle → rows keep only those two keys).
    → {total, rows[], next_page_token, page_size, params, _meta}.
    """
    from ..transport import call_provider
    from ..errors import SdkError

    ps = int(page_size)
    if ps < 1:
        raise SdkError("usage_error", provider="ctgov", detail=f"page_size must be >= 1, got {ps}")
    params = {"pageSize": ps, "countTotal": "true" if count_total else "false"}
    if query_term:
        params["query.term"] = str(query_term)
    if query_titles:
        params["query.titles"] = str(query_titles)
    if query_intr:
        params["query.intr"] = str(query_intr)
    if query_cond:
        params["query.cond"] = str(query_cond)
    if filter_advanced:
        params["filter.advanced"] = str(filter_advanced)
    if agg_filters:
        params["aggFilters"] = str(agg_filters)
    if fields:
        params["fields"] = str(fields)
    if page_token:
        params["pageToken"] = str(page_token)
    if sort:
        params["sort"] = str(sort)
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    studies = (r["data"] or {}).get("studies") or []
    return {"total": (r["data"] or {}).get("totalCount"),
            "rows": [_row_from_study(s) for s in studies],
            "next_page_token": (r["data"] or {}).get("nextPageToken"),
            "page_size": ps, "params": params, "_meta": r}
