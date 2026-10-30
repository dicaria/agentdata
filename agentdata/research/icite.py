"""icite — NIH iCite API (PubMed paper citation-impact card; keyless).

No key needed (icite.od.nih.gov/api/pubs?pmids=; query-parameter style, re-probed 2026-10-26 —
api.ncbi.nlm.nih.gov/ihdb/pubs/v3/* is 404, do not trust the documented path). Probe (pmid
26017442, "Deep learning", LeCun): RCR 737.5, citation_count 18,319, cited_by_clin clinical
citations present.
Two traps: `cited_by`/`cited_by_clin` are **pmid arrays** (the source of ten-thousand-element
envelope explosions) — reshaped down into counts (citation_count taken directly + len of
cited_by_clin); the count key is citation_count, not cited_by.
Single-record face (the impact hop after nih_reporter_publications hands you a pmid).
"""
provider = {
    "id": "icite",
    "baseUrl": "https://icite.od.nih.gov/api",
    "rate": {"rps": 2, "burst": 4},  # NCBI family tier (epmc/rxnav/ctgov/dailymed also 2/4)
    "ops": {
        "pubs": {"path": "/pubs", "method": "GET", "idempotent": True},
    },
    "ttl": {"pubs": 24 * 3600},
}


def pub_raw(pmid, *, cache=None, no_cache=False):
    """→ {pmid, …impact card, params, _meta}; /pubs?pmids= direct, verbatim name (pmid required,
    digits only, single-record card).
    The pmid arrays of cited_by/cited_by_clin are reduced to counts (cited_by_count/
    cited_by_clin_count) — ten-thousand-element arrays never enter the envelope."""
    from ..transport import call_provider
    from ..errors import SdkError

    v = str(pmid or "").strip()
    if not v:
        raise SdkError("usage_error", provider="icite", detail="icite_pubs requires pmid (PubMed id)")
    if not v.isdigit():
        raise SdkError("usage_error", provider="icite", detail="pmid must be digits only (PubMed id like 26017442)")
    r = call_provider(provider, "pubs", {"pmids": v}, cache=cache, no_cache=no_cache)
    data = (r["data"] or {}).get("data") or []
    row = data[0] if data else {}
    return {"pmid": row.get("pmid") or int(v),
            "doi": row.get("doi"), "title": row.get("title"),
            "journal": row.get("journal"), "year": row.get("year"),
            "authors": [a.get("fullName") for a in row.get("authors") or []][:20],
            "relative_citation_ratio": row.get("relative_citation_ratio"),
            "field_citation_rate": row.get("field_citation_rate"),
            "expected_citations_per_year": row.get("expected_citations_per_year"),
            "cited_by_count": row.get("citation_count"),
            "cited_by_clin_count": len(row.get("cited_by_clin") or []),
            "citations_per_year": row.get("citations_per_year"),
            "is_clinical": row.get("is_clinical"),
            "is_research_article": row.get("is_research_article"),
            "nih_percentile": row.get("nih_percentile"),
            "params": {"pmids": v}, "_meta": r}
