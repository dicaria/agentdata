"""opencitations — OpenCitations COCI (open citation index; keyless).

No key needed (migrated to the new host api.opencitations.net/index/v1/ — the old
opencitations.org paths 301 here). citations face (probed 2026-10-26): GET /citations/{doi}
(the DOI carries **no** doi: prefix; with it you get a 400 whose error body reports the
correct format); **the limit parameter is silently ignored** (?limit=3 still returns all 217
rows — one more case of an upstream silent clamp), so this face sets no limit and returns the
full list plus a count.
Row keys: oci/citing/cited/creation/timespan/journal_sc/author_sc.
"""
provider = {
    "id": "opencitations",
    "baseUrl": "https://api.opencitations.net",
    "rate": {"rps": 1, "burst": 5},  # small academic-service tier (same as osv/nsf; COCI is single-shot with no paging, naturally low traffic)
    "ops": {
        "citations": {"path": "/index/v1/citations/{doi}", "method": "GET", "idempotent": True},
    },
    "ttl": {"citations": 24 * 3600},
}


def _norm_doi(doi):
    """DOI normalization: strip the doi: prefix (upstream 400 wall — the error body itself
    reports the prefix-less format)."""
    v = str(doi or "").strip().lower()
    if v.startswith("doi:"):
        v = v[4:].strip()
    if v.startswith("https://doi.org/"):
        v = v[len("https://doi.org/"):]
    if v.startswith("doi.org/"):
        v = v[len("doi.org/"):]
    return v or None


def citations_raw(doi, *, cache=None, no_cache=False):
    """→ {doi, count, rows, params, _meta}; /index/v1/citations/{doi} direct, verbatim name
    (full list). doi required (doi: prefix/doi.org URL normalized away automatically); the
    upstream limit parameter is silently ignored (probe: ?limit=3 still returned all 217
    rows) — no fake pagination, the full list comes back."""
    from ..transport import call_provider
    from ..errors import SdkError

    v = _norm_doi(doi)
    if not v:
        raise SdkError("usage_error", provider="opencitations",
                       detail="opencitations_citations requires doi (the cited DOI; the doi: prefix is auto-stripped)")
    params = {"doi": v}
    r = call_provider(provider, "citations", params, cache=cache, no_cache=no_cache)
    rows = r["data"] or []
    return {"doi": v, "count": len(rows), "rows": rows, "params": params, "_meta": r}
