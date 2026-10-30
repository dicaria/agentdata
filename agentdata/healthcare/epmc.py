"""epmc — Europe PMC (literature evidence layer; keyless; polite tier 2 rps).

TTL: search result pages 24h. Query construction: company→AFF:"…" (author affiliation field search; do not use AUTH=author name —
company names via AUTH collapse the hit count — an external review on 2026-10-16 ruled 2 vs 37,108); focus appends an AND all-field term.
The real upstream pageSize limit is 1-1000 (1001 → errCode 404 «Invalid page size»; probed and confirmed) — polite tier 50, truncation visible via hitCount.
"""

provider = {
    "id": "epmc",
    "baseUrl": "https://www.ebi.ac.uk/europepmc/webservices/rest",
    "rate": {"rps": 2, "burst": 4},
    "ops": {
        "search": {"path": "/search", "ttl": 24 * 3600},
    },
}


def row_from_upstream(x: dict) -> dict:
    """Probed and confirmed (2026-10-22, three-source diff + self-describing core fullTextUrlList reconciliation):
    the old url only recognised pmid → PMC-only rows (pmcid present, pmid null) and PPR preprint rows (id only) all came back null, breaking the evidence chain;
    the official self-describing URLs: pmcid rows = articles/{pmcid} (same shape for MED/PMC), PPR = article/PPR/{id},
    PAT has no EPMC page (it only gives SureChembl/EPO outbound links) → an honest None.
    For new PMC-only records pubYear can be null while firstPublicationDate has a value → year fallback."""
    year_fallback = (str(x.get("firstPublicationDate") or ""))[:4] or None
    if x.get("pmcid"):
        url = f"https://europepmc.org/articles/{x['pmcid']}"
    elif x.get("pmid"):
        url = f"https://europepmc.org/article/{x.get('source') or 'MED'}/{x['pmid']}"
    elif x.get("source") and x.get("id") and x.get("source") != "PAT":
        url = f"https://europepmc.org/article/{x['source']}/{x['id']}"
    else:
        url = None
    return {
        "id": x.get("id"),  # a PPR preprint row only has this key filled in (both pmid and pmcid are null) — the evidence chain never breaks
        "pmid": x.get("pmid"),
        "source": x.get("source"),
        "title": x.get("title"),
        "authors": x.get("authorString"),
        "journal": x.get("journalTitle"),
        "pub_year": x.get("pubYear") or year_fallback,
        "cited_by": x.get("citedByCount", 0),
        "url": url,
    }


def search_evidence(query=None, company=None, focus=None, limit=10, cache=None, no_cache=False) -> dict:
    from ..transport import call_provider
    from ..errors import SdkError

    q = query
    if not q and company:
        q = f'AFF:"{company}"'
        if focus:
            q += f' AND "{focus}"'
    if not q:
        raise SdkError("op_unknown", provider="epmc", detail="evidence needs query or company (focus may be added)")
    r = call_provider(provider, "search",
                      {"query": q, "format": "json", "resultType": "lite",
                       "pageSize": min(50, max(1, int(limit)))},
                      cache=cache, no_cache=no_cache)
    rows = ((r["data"] or {}).get("resultList") or {}).get("result") or []
    return {
        "hitCount": (r["data"] or {}).get("hitCount", len(rows)),
        "rows": [row_from_upstream(x) for x in rows],
        "_meta": r,
    }


def search_raw(query, *, result_type="lite", page_size=25, cursor_mark="*", sort=None,
               fmt="json", cache=None, no_cache=False) -> dict:
    """0.2.0 mirror face: upstream param names (query/resultType/pageSize/cursorMark/sort/format) + our defaults.

    Hard limit (protocol, confirmed by probing on 2026-10-23): pageSize 1-1000 — 1001 → errCode 404 «Invalid page size»;
    format supports only json (this stack parses JSON — a local safety gate; for the xml face the agent fetches along the evidence url itself).
    resultType is the closed set lite|core|full|idlist; a free sort string passes through (measured "CITED desc" works, echoed back in nextPageUrl).
    Defaults follow the upstream defaults: pageSize=25, cursorMark="*" (the first-page sentinel), sort=None (relevance).
    → {hitCount, rows[], next_cursor_mark, page_size, query, _meta}.
    """
    from ..transport import call_provider
    from ..errors import SdkError

    q = str(query or "").strip()
    if not q:
        raise SdkError("usage_error", provider="epmc", detail="query requires a search expression (Europe PMC all-field syntax)")
    rt = str(result_type or "lite").strip()
    if rt not in ("lite", "core", "full", "idlist"):
        raise SdkError("usage_error", provider="epmc",
                       detail=f"the resultType closed set is lite|core|full|idlist, got '{rt}'")
    if str(fmt or "json").strip() != "json":
        raise SdkError("usage_error", provider="epmc",
                       detail="format supports only json (this stack parses JSON; for the xml face fetch it yourself along the evidence url)")
    ps = int(page_size)
    if not 1 <= ps <= 1000:
        raise SdkError("usage_error", provider="epmc",
                       detail=f"pageSize must be 1-1000 (upstream 1001 → errCode 404 Invalid page size, measured 2026-10-23), got {ps}")
    params = {"query": q, "format": "json", "resultType": rt,
              "pageSize": ps, "cursorMark": str(cursor_mark or "*")}
    if sort:
        params["sort"] = str(sort)
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    rows = ((r["data"] or {}).get("resultList") or {}).get("result") or []
    return {
        "hitCount": (r["data"] or {}).get("hitCount", len(rows)),
        "rows": [row_from_upstream(x) for x in rows],
        "next_cursor_mark": (r["data"] or {}).get("nextCursorMark"),
        "page_size": ps, "query": q,
        "_meta": r,
    }
