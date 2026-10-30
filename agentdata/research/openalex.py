"""openalex — OpenAlex API (global scholarly output and institution profiles; keyless).

No key needed (official polite pool 10 rps, self-imposed polite tier of 5 rps). Two faces
(probed 2026-10-26): works = paper rows (filter=institutions.ror: reaches the institution
edge; rows link back through authorships[].institutions[].ror); institutions = institution
candidates (search= is a fuzzy name search, same-name clones in different countries coexist —
the candidate list is never auto-picked, pick the ROR explicitly and then query output on the
works face, adversarial-review constraint 1).
Three traps: per-page>200 is an explicit 400 (an honest wall, enforced locally); select must
force-merge the core fields (stripping them drops the edges, adversarial-review constraint 2);
the cursor (meta.next_cursor) encodes paging only, not the conditions — when continuing you
must re-send the constraint parameters unchanged (adversarial-review constraint 3; this
wrapper satisfies it naturally by requiring at least one constraint).
"""
provider = {
    "id": "openalex",
    "baseUrl": "https://api.openalex.org",
    "rate": {"rps": 5, "burst": 5},  # quota semantics 5+5=10 ≤ the official 10 req/s (with burst 10 the 10+5=15 would exceed the cap, fixed on re-check in 0.2.5)
    "ops": {
        "works": {"path": "/works", "method": "GET", "idempotent": True},
        "institutions": {"path": "/institutions", "method": "GET", "idempotent": True},
    },
    "ttl": {"works": 24 * 3600, "institutions": 24 * 3600},
}

_PER_PAGE_CAP = 200  # per-page>200 gets an explicit upstream 400 (probe 2026-10-26)
_CORE_FIELDS = "id,doi,display_name,publication_year,type,cited_by_count,open_access,authorships"


def _norm_ror(ror):
    """ROR normalization: both the bare 15-char form (01xdqrp08) and the full URL
    (https://ror.org/01xdqrp08) are accepted, both normalize to the full URL."""
    v = str(ror or "").strip()
    if not v:
        return None
    if v.startswith("https://ror.org/"):
        return v
    if v.startswith("ror.org/"):
        return "https://" + v
    return f"https://ror.org/{v}"


def _work_row(w):
    return {
        "id": w.get("id"), "doi": w.get("doi"), "display_name": w.get("display_name"),
        "publication_year": w.get("publication_year"), "type": w.get("type"),
        "cited_by_count": w.get("cited_by_count"),
        "open_access": w.get("open_access") or {},
        "authorships": [{"position": a.get("author_position"),
                         "author": (a.get("author") or {}).get("display_name"),
                         "raw_author_name": a.get("raw_author_name"),
                         "is_corresponding": a.get("is_corresponding"),
                         "institutions": [{"ror": i.get("ror"), "display_name": i.get("display_name"),
                                           "country_code": i.get("country_code")}
                                          for i in a.get("institutions") or []],
                         "countries": a.get("countries")}
                        for a in w.get("authorships") or []],
    }


def works_raw(search=None, *, ror=None, doi=None, title_search=None,
              per_page=25, cursor=None, select=None, cache=None, no_cache=False):
    """→ {total, count, rows, next_cursor, params, _meta}; /works direct, verbatim name.
    search full-text × ror (exact institutions.ror) × doi × title_search (title.search) — the
    four constraints combine with AND into filter; at least one constraint (local wall: a
    cursor is not a constraint, a bare whole-corpus scan is served by the bulk pipeline);
    per_page 1-200 (explicit upstream 400 wall); cursor=meta.next_cursor to continue (it
    encodes paging only, the constraint parameters must be re-sent unchanged); select is
    force-merged with the core fields."""
    from ..transport import call_provider
    from ..errors import SdkError

    q = str(search or "").strip() or None
    r_v = _norm_ror(ror)
    d_v = str(doi or "").strip() or None
    t_v = str(title_search or "").strip() or None
    if not (q or r_v or d_v or t_v):
        raise SdkError("usage_error", provider="openalex",
                       detail="openalex_works requires at least one of search/ror/doi/title_search"
                              " (a cursor is not a constraint; local safety wall: a bare whole-corpus "
                              "scan is served by the bulk pipeline)")
    pp = int(per_page)
    if not 1 <= pp <= _PER_PAGE_CAP:
        raise SdkError("usage_error", provider="openalex",
                       detail=f"per_page must be 1-{_PER_PAGE_CAP} (explicit upstream 400 wall, confirmed by probing 2026-10-26)")
    filters = []
    if r_v:
        filters.append(f"institutions.ror:{r_v}")
    if d_v:
        filters.append(f"doi:{d_v}")
    if t_v:
        filters.append(f"title.search:{t_v}")
    params = {"per-page": pp}
    if q:
        params["search"] = q
    if filters:
        params["filter"] = ",".join(filters)
    cur = str(cursor or "").strip() or None
    if cur:
        params["cursor"] = cur
    sel = {x.strip() for x in (select if isinstance(select, (list, tuple))
                               else str(select or "").split(",")) if x and str(x).strip()}
    params["select"] = ",".join(sorted(sel | set(_CORE_FIELDS.split(","))))
    r = call_provider(provider, "works", params, cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    meta = data.get("meta") or {}
    rows = [_work_row(w) for w in data.get("results") or []]
    return {"total": meta.get("count"), "count": len(rows), "rows": rows,
            "next_cursor": meta.get("next_cursor"), "params": params, "_meta": r}


def _institution_row(i):
    return {
        "id": i.get("id"), "ror": i.get("ror"), "display_name": i.get("display_name"),
        "country_code": i.get("country_code"), "type": i.get("type"),
        "works_count": i.get("works_count"), "cited_by_count": i.get("cited_by_count"),
        "relevance_score": i.get("relevance_score"),
        "homepage_url": i.get("homepage_url"),
    }


def institutions_raw(search, *, per_page=25, cache=None, no_cache=False):
    """→ {total, count, rows, params, _meta}; /institutions?search= direct, verbatim name.
    search required (local wall); per_page 1-200 (same wall as works).
    Rows = institution candidate cards (ror/type/works_count); same-name clones in different
    countries coexist (a pfizer probe returned 24 candidates incl. US/UK/FR) — the first one is
    never auto-picked; pick the ROR explicitly and then query output via openalex_works
    (adversarial-review constraint 1)."""
    from ..transport import call_provider
    from ..errors import SdkError

    q = str(search or "").strip()
    if not q:
        raise SdkError("usage_error", provider="openalex", detail="openalex_institutions requires search (institution name)")
    pp = int(per_page)
    if not 1 <= pp <= _PER_PAGE_CAP:
        raise SdkError("usage_error", provider="openalex",
                       detail=f"per_page must be 1-{_PER_PAGE_CAP} (explicit upstream 400 wall)")
    params = {"search": q, "per-page": pp}
    r = call_provider(provider, "institutions", params, cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    meta = data.get("meta") or {}
    rows = [_institution_row(i) for i in data.get("results") or []]
    return {"total": meta.get("count"), "count": len(rows), "rows": rows,
            "params": params, "_meta": r}
