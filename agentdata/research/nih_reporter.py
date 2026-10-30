"""nih_reporter — NIH RePORTER API v2 (US NIH funded projects and the funding↔paper bridge; keyless).

No key needed, POST search faces (probed 2026-10-26). The projects face has two shape axes:
criteria only accepts snake_case (org_names/fiscal_years), include_fields only accepts
camelCase (ApplId/ProjectTitle/…) — a wrong shape is **silently ignored** (no error), so
both faces hard-code their fields instead of passing bare params through. The org_names array
semantics = exact match (not fuzzy — re-measured 0.2.9: the abbreviation "NHLBI"→0 rows, the
full name "NATIONAL HEART, LUNG, AND BLOOD INSTITUTE"→173 rows for FY2023); the fiscal_years
array is a set of years. Deep-paging wall: upstream rejects offset+limit > 15,000 (probed);
limit 1-500 is a real documented cap (0.2.9 re-counted limit=500 → all 500 rows returned,
total 85,133 — no silent clamping). The 0.2.9 audit did not adopt two keys (probed 2026-10-28):
core_project_nums is the key of the **publications face** (per the official swagger
classification); sending it on the projects face is silently ignored (total=2,983,713 = the
whole table dumped); advanced_text_search is documented but **behaviourally dead** — all three
inner shapes (search_text/searchtext/all three keys operator+searchfield+searchtext) are
silently ignored both alone and combined (the combined send gives total=173, identical to a
bare org+fy send, with no keyword filtering on the title) — a documented key is not a live key,
do not adopt it.
publications = the funding↔paper bridge table (added to the research domain in 0.2.4):
criteria accepts exactly two keys, pmids/appl_ids.
"""
provider = {
    "id": "nih-reporter",
    "baseUrl": "https://api.reporter.nih.gov",
    # The official "no more than one URL request per second" = spacing semantics (interval ≥1s
    # between requests): burst=1+rps=1 is exactly compliant; the old burst=5 bucket fired 5
    # requests in the first instant and broke the rule (compliance fix; rate-limits.md §7
    # exception log). Declared at provider level: both faces (projects/publications) obey it.
    "rate": {"rps": 1, "burst": 1},
    "ops": {
        "projectsSearch": {"path": "/v2/projects/search", "method": "POST", "idempotent": True},
        "publicationsSearch": {"path": "/v2/publications/search", "method": "POST", "idempotent": True},
    },
    "ttl": {"projectsSearch": 24 * 3600, "publicationsSearch": 24 * 3600},
}

_OFFSET_WALL = 15000  # upstream rejects offset+limit above this (probed 2026-10)


def _project_row(p):
    org = p.get("organization") or {}
    return {
        "appl_id": p.get("appl_id"), "fiscal_year": p.get("fiscal_year"),
        "project_title": p.get("project_title"),
        "org_name": org.get("org_name"), "org_city": org.get("org_city"),
        "org_state": org.get("org_state"), "org_country": org.get("org_country"),
        "org_uei": org.get("primary_uei"), "org_duns": org.get("primary_duns"),
        "pis": [{"full_name": x.get("full_name"), "is_contact_pi": x.get("is_contact_pi"),
                 "profile_id": x.get("profile_id")}
                for x in p.get("principal_investigators") or []],
        "award_amount": p.get("award_amount"),
        "abstract_text": p.get("abstract_text"),
    }


def projects_raw(org_name=None, *, fiscal_year=None, include_fields=None, limit=25, offset=0,
                 cache=None, no_cache=False):
    """→ {total, count, rows, search_url, params, _meta}; /v2/projects/search POST direct, verbatim name.
    At least one of org_name/fiscal_year (local safety wall: a bare scan of the ~4M-project
    corpus is served by the bulk pipeline); a scalar org_name is auto-wrapped into the array
    (org_names array semantics upstream); fiscal_year→fiscal_years; include_fields is a
    camelCase whitelist passed through (a wrong shape is silently ignored upstream — the face
    does not validate spelling, a wrong name just returns more fields); limit 1-500 (upstream API
    doc); offset+limit ≤15,000 (upstream deep-paging wall)."""
    from ..transport import call_provider
    from ..errors import SdkError

    nm = str(org_name or "").strip() or None
    fy = int(fiscal_year) if fiscal_year not in (None, "") else None
    if not nm and fy is None:
        raise SdkError("usage_error", provider="nih-reporter",
                       detail="nih_reporter_projects requires at least one of org_name or fiscal_year"
                              " (local safety wall: a bare whole-corpus scan is served by the bulk pipeline)")
    lim = int(limit)
    if not 1 <= lim <= 500:
        raise SdkError("usage_error", provider="nih-reporter",
                       detail="limit must be 1-500 (upstream API doc page-size cap)")
    off = int(offset)
    if off < 0:
        raise SdkError("usage_error", provider="nih-reporter", detail="offset must be ≥0")
    if off + lim > _OFFSET_WALL:
        raise SdkError("usage_error", provider="nih-reporter",
                       detail=f"offset+limit must be ≤{_OFFSET_WALL:,} (upstream deep-paging wall, confirmed by probing 2026-10)")
    criteria = {}
    if nm:
        criteria["org_names"] = [nm]  # upstream array semantics = exact match (not a fuzzy search)
    if fy is not None:
        criteria["fiscal_years"] = [fy]
    body = {"criteria": criteria, "offset": off, "limit": lim}
    if include_fields:
        body["include_fields"] = [str(x).strip() for x in include_fields if str(x).strip()]
    r = call_provider(provider, "projectsSearch", body, cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    meta = data.get("meta") or {}
    rows = [_project_row(p) for p in data.get("results") or []]
    return {"total": meta.get("total"), "count": len(rows), "rows": rows,
            "search_url": (meta.get("properties") or {}).get("URL"),
            "params": body, "_meta": r}


_PUB_CRITERIA = ("pmids", "appl_ids")  # the only two recognised filter keys (probed 2026-10-26: every other key is silently ignored → 8.3M-row dump)


def publications_raw(pmids=None, *, appl_ids=None, limit=25, offset=0,
                     cache=None, no_cache=False):
    """→ {total, count, rows, params, _meta}; /v2/publications/search POST direct, verbatim name.
    At least one of pmids/appl_ids (local safety wall — with both keys empty upstream dumps the
    whole 8.3M table); the criteria key set is closed and only these two keys are sent:
    fiscal_years/coreprojectnums/org_names etc. are all **silently ignored** upstream (no error,
    no filtering, probed 2026-10-26), so this face passes no other criteria through;
    rows = the 3-key bridge {coreproject, pmid, applid} (funding↔paper bridge table); sparse
    linkage is a real answer (a Yale FY2018 project measured zero linked papers) — 0 rows means
    no linkage on record for that project, not a failed query.
    limit 1-500, offset same convention as the projects face."""
    from ..transport import call_provider
    from ..errors import SdkError

    pm = [int(x) for x in (pmids or []) if str(x).strip()] if pmids else []
    ap = [int(x) for x in (appl_ids or []) if str(x).strip()] if appl_ids else []
    if not pm and not ap:
        raise SdkError("usage_error", provider="nih-reporter",
                       detail="nih_reporter_publications requires at least one of pmids or appl_ids"
                              " (local safety wall: both keys empty = upstream dumps the whole 8.3M table)")
    lim = int(limit)
    if not 1 <= lim <= 500:
        raise SdkError("usage_error", provider="nih-reporter",
                       detail="limit must be 1-500 (upstream API doc page-size cap)")
    off = int(offset)
    if off < 0:
        raise SdkError("usage_error", provider="nih-reporter", detail="offset must be ≥0")
    criteria = {}
    if pm:
        criteria["pmids"] = pm
    if ap:
        criteria["appl_ids"] = ap
    body = {"criteria": criteria, "offset": off, "limit": lim}
    r = call_provider(provider, "publicationsSearch", body, cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    meta = data.get("meta") or {}
    rows = [{"coreproject": x.get("coreproject"), "pmid": x.get("pmid"), "applid": x.get("applid")}
            for x in data.get("results") or []]
    return {"total": meta.get("total"), "count": len(rows), "rows": rows,
            "params": body, "_meta": r}
