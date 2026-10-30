"""courtlistener — CourtListener Search API v4 provider (Free Law Project; US federal + state case law; keyless).

Anonymous keyless GET search (probed 2026-10-26, type=o count 8.3M across the whole corpus) — this overturns the
old finding that "the API face needs a token": that held only for the dedicated endpoints. Covers federal +
**state courts** (the first probe hit California Court of Appeal) — the US state case-law face is carried by this
source too. Caselaw Access Project (CAP) api.case.law is retired (301 → case.law/docs SPA shell); its Harvard
case-law history is carried by this source (bulk goes over the S3 monthly archives).
Wall: page_size is silently ignored (always 20/page; only cursor paging is honored) — the param is not exposed.
"""
provider = {
    "id": "courtlistener",
    "baseUrl": "https://www.courtlistener.com",
    "rate": {"rps": 0.5, "burst": 3},  # no rate-limit response headers — conservative tier (anonymous shared pool)
    "ops": {
        "opinionsSearch": {"path": "/api/rest/v4/search/", "method": "GET", "idempotent": True},
    },
    "ttl": {"opinionsSearch": 24 * 3600},
}

_FILTER_PARAMS = ("q", "case_name", "court", "judge", "docket_number",
                  "filed_after", "filed_before")  # faces walled on at-least-one filter (keep copy in sync)


def _opinion_row(o):
    return {
        "cluster_id": o.get("cluster_id"), "docket_id": o.get("docket_id"),
        "case_name": o.get("caseName"), "case_name_full": o.get("caseNameFull"),
        "court": o.get("court"), "court_id": o.get("court_id"),
        "court_citation_string": o.get("court_citation_string"),
        "date_filed": o.get("dateFiled"), "docket_number": o.get("docketNumber"),
        "status": o.get("status"), "judge": o.get("judge"),
        "suit_nature": o.get("suitNature"), "citations": o.get("citation") or [],
        "cite_count": o.get("citeCount"), "neutral_cite": o.get("neutralCite"),
        "absolute_url": o.get("absolute_url"),
        "opinions": [{"id": x.get("id"), "download_url": x.get("download_url"),
                      "local_path": x.get("local_path"), "author_id": x.get("author_id"),
                      "cites": x.get("cites") or []}
                     for x in o.get("opinions") or []],
    }


def opinions_search_raw(*, q=None, case_name=None, court=None, judge=None,
                        docket_number=None, filed_after=None, filed_before=None,
                        order_by=None, cursor=None, cache=None, no_cache=False):
    """→ {total, count, rows, next_cursor, params, _meta}; /api/rest/v4/search/ GET with verbatim param names.
    type is always "o" (opinions); at least one filter param required (local safety wall: a bare scan of the full
    ~8.3M-opinion corpus belongs to the batch line; bulk goes over the S3 monthly archives);
    page_size is not exposed (upstream silently ignores it, always 20/page);
    cursor passes through for paging (next_cursor is recovered from the next URL in the response)."""
    from urllib.parse import parse_qs, urlparse

    from ..transport import call_provider
    from ..errors import SdkError

    given = {"q": q, "case_name": case_name, "court": court, "judge": judge,
             "docket_number": docket_number, "filed_after": filed_after,
             "filed_before": filed_before}
    params = {k: str(v).strip() for k, v in given.items() if v not in (None, "")}
    if not params:
        raise SdkError("usage_error", provider="courtlistener",
                       detail="courtlistener_opinions_search requires at least one of q/case_name/court/judge/"
                              "docket_number/filed_after/filed_before"
                              " (local safety wall: a bare scan of the full ~8.3M-opinion corpus belongs to the batch line)")
    upstream = {"type": "o", **params}
    if order_by not in (None, ""):
        upstream["order_by"] = str(order_by).strip()
    if cursor not in (None, ""):
        upstream["cursor"] = str(cursor).strip()
    r = call_provider(provider, "opinionsSearch", upstream, cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    rows = [_opinion_row(o) for o in data.get("results") or []]
    next_cursor = None
    nxt = data.get("next")
    if nxt:
        next_cursor = (parse_qs(urlparse(nxt).query).get("cursor") or [None])[0]
    return {"total": data.get("count"), "count": len(rows), "rows": rows,
            "next_cursor": next_cursor, "params": upstream, "_meta": r}
