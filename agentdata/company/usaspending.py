"""usaspending — USAspending API (US federal contracts/grants by recipient; keyless).

Keyless at ~1,000 req/hr/IP plus 30 req/5s bursts — we set 0.25 rps/burst 5 (≈900/hr, comfortably inside) so no
daily-quota ledger is needed.
First use of POST read semantics: spending_by_award is a POST JSON body, ops declare idempotent=True to join the
retry path. Live-shape check: the whole tree sits under the /api/v2/ prefix (/v2/ is now 404);
autocomplete returns {count, results[{recipient_name, uei, duns}]};
spending_by_award's recipient_search_text must be an **array** (422 measured).
"""
provider = {
    "id": "usaspending",
    "baseUrl": "https://api.usaspending.gov",
    "rate": {"rps": 0.25, "burst": 5},
    "ops": {
        "recipientAutocomplete": {"path": "/api/v2/autocomplete/recipient/", "method": "POST", "idempotent": True},
        "spendingByAward": {"path": "/api/v2/search/spending_by_award/", "method": "POST", "idempotent": True},
    },
    "ttl": {"recipientAutocomplete": 7 * 86400, "spendingByAward": 24 * 3600},
}


def find_recipient(name, *, limit=5, cache=None, no_cache=False):
    """→ {candidates[{recipient_name,uei,duns}], _meta}; uei is often null — the authoritative UEI anchor is the SAM.gov card (watch list); this serves only as a candidate hint."""
    from ..transport import call_provider
    from ..errors import SdkError

    q = str(name or "").strip()
    if not q:
        raise SdkError("usage_error", provider="usaspending", detail="--name is required")
    r = call_provider(provider, "recipientAutocomplete",
                      {"search_text": q, "limit": min(max(1, int(limit) or 5), 20)},
                      cache=cache, no_cache=no_cache)
    rows = [{"recipient_name": e.get("recipient_name"), "uei": e.get("uei"), "duns": e.get("duns")}
            for e in (r["data"] or {}).get("results") or []]  # duns = legacy key, trending permanently null as of 2026
    return {"candidates": rows, "_meta": r}


def _awards_from_upstream(data):
    """Upstream payload → awards rows (pure function, offline-testable; shared by company_fed_awards and awards_raw)."""
    return [{
        "award_id": a.get("Award ID"),
        "recipient_name": a.get("Recipient Name"),
        "award_amount": a.get("Award Amount"),
        "start_date": a.get("Start Date"),
        "end_date": a.get("End Date"),
        "awarding_agency": a.get("Awarding Agency"),
        "generated_internal_id": a.get("generated_internal_id"),  # official detail key (CONT_AWD_…), composes the USAspending human page
    } for a in (data or {}).get("results") or []]


def company_fed_awards(name, *, limit=10, startdt=None, enddt=None, cache=None, no_cache=False):
    """→ {page_metadata, has_more, awards[], date_range, _meta}; the four contract types A/B/C/D (grant types come in a later wave).
    page_metadata has no total (only hasNext/last_record_* pagination cursors — the endpoint gives no counts) — the old name
    total_estimate is fully removed; the window semantics = the award period intersects the window (long-running contracts that
    span it are included), not "started inside the window".
    Join discipline: no blind name concatenation — the caller narrows by CIK/LEI first, then this face yields the numbers."""
    from ..transport import call_provider
    from ..errors import SdkError

    q = str(name or "").strip()
    if not q:
        raise SdkError("usage_error", provider="usaspending", detail="related kind=fed_awards requires --name")
    filters = {
        "award_type_codes": ["A", "B", "C", "D"],
        "recipient_search_text": [q],  # measured 2026-10-19: must be an array, a string gets 422
    }
    date_range = None
    if startdt or enddt:  # either end given → fill the other into a complete window; date_range echoes the values actually in effect (guards against "sent but silently swallowed" look-alikes)
        from ..daterange import resolve as _range
        _start, _end, date_range = _range(startdt, enddt, default_start="2007-10-01",
                                          provider=provider["id"], label="recipient award period")
        filters["time_period"] = [{"start_date": _start, "end_date": _end}]
    r = call_provider(provider, "spendingByAward", {
        "filters": filters,
        "fields": ["Award ID", "Recipient Name", "Award Amount", "Start Date", "End Date", "Awarding Agency"],
        "limit": min(max(1, int(limit) or 10), 100),
        "page": 1,
        "subawards": False,
    }, cache=cache, no_cache=no_cache)
    rows = _awards_from_upstream(r["data"])
    # page_metadata has no total — truncation visibility rides on has_more (hasNext)
    pm = (r["data"] or {}).get("page_metadata")
    return {"page_metadata": pm, "has_more": bool(pm and pm.get("hasNext")), "awards": rows,
            "date_range": date_range, "_meta": r}


def awards_raw(recipient_search_text, *, award_type_codes=None, start_date=None, end_date=None,
               fields=None, limit=10, page=1, subawards=False, cache=None, no_cache=False):
    """→ {page_metadata, has_more, awards[], date_range, params, _meta}; spending_by_award params pass through verbatim.
    recipient_search_text must be an array upstream (a string 422s, measured 2026-10-19) — a scalar is auto-wrapped;
    award_type_codes comma string → array (default A,B,C,D the four contract types; grants 02/03 etc. can override);
    time_period auto-fills the missing end (upstream silently swallows single-ended windows — same EDGAR guard), date_range
    echoes the window actually in effect; fields comma string → array (default six columns); limit 1-100 (upstream API docs);
    subawards passes straight through upstream."""
    from ..transport import call_provider
    from ..errors import SdkError

    q = str(recipient_search_text or "").strip()
    if not q:
        raise SdkError("usage_error", provider="usaspending",
                       detail="usaspending_spending_by_award requires recipient_search_text (recipient name, upstream array semantics — a scalar is auto-wrapped)")
    lim = int(limit)
    if not 1 <= lim <= 100:
        raise SdkError("usage_error", provider="usaspending",
                       detail="limit must be 1-100 (upstream API docs spending_by_award page-size cap)")
    types = ([t.strip() for t in str(award_type_codes).split(",") if t.strip()]
             if award_type_codes else ["A", "B", "C", "D"])
    filters = {"award_type_codes": types, "recipient_search_text": [q]}
    date_range = None
    if start_date or end_date:
        from ..daterange import resolve as _range
        _start, _end, date_range = _range(start_date, end_date, default_start="2007-10-01",
                                          provider=provider["id"], label="recipient award period")
        filters["time_period"] = [{"start_date": _start, "end_date": _end}]
    flds = ([f.strip() for f in str(fields).split(",") if f.strip()]
            if fields else ["Award ID", "Recipient Name", "Award Amount",
                            "Start Date", "End Date", "Awarding Agency"])
    params = {"filters": filters, "fields": flds, "limit": lim,
              "page": int(page), "subawards": bool(subawards)}
    r = call_provider(provider, "spendingByAward", params, cache=cache, no_cache=no_cache)
    pm = (r["data"] or {}).get("page_metadata")
    return {"page_metadata": pm, "has_more": bool(pm and pm.get("hasNext")),
            "awards": _awards_from_upstream(r["data"]), "date_range": date_range,
            "params": params, "_meta": r}
