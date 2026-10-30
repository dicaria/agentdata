"""crossref — Crossref REST API (DOI registry paper search; keyless).

No key needed (the polite pool officially recommends a mailto in the User-Agent; self-imposed
5 rps = 1/10 of the documented cap of 50, same high-volume tier as edgar/openalex). works face
(probed 2026-10-26): filter=funder:<funder DOI> collects funder output (NSF 10.13039/100000001
→ 462,059 works, rows carry the award number in funder[].award[]); award.number:<number> combined
with funder narrows exactly (OAC-1730655 → 10 works); query= with filter= is legal
(funder×query=graphene → 2,962).
Three traps: select=award reports select-not-available (awards live only inside rows, they
cannot be selected); the deep-paging offset has a documented upstream wall at 10,000 (not probed
point by point — documented figure) — **the proper way around it is cursor** (deep-pager, probed
2026-10-28: cursor=*&filter=from-pub-date:2026-06-01 → 5 rows + next-cursor, all good).
"""
provider = {
    "id": "crossref",
    "baseUrl": "https://api.crossref.org",
    "rate": {"rps": 5, "burst": 10},  # high-volume tier (edgar also 5rps; official cap 50 rps, quota semantics 10+5=15 ≤ 50, comfortable)
    "ops": {
        "works": {"path": "/works", "method": "GET", "idempotent": True},
    },
    "ttl": {"works": 24 * 3600},
}

_ROWS_CAP = 100        # default page-size cap (upstream doc allows up to 1000, politeness tier tightens it)
_OFFSET_WALL = 10000   # upstream documented deep-paging wall (not probed point by point, documented figure; the cursor channel is not subject to it)


def _work_row(it):
    issued = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
    return {
        "doi": it.get("DOI"),
        "title": (it.get("title") or [None])[0],
        "container_title": (it.get("container-title") or [None])[0],
        "type": it.get("type"),
        "publisher": it.get("publisher"),
        "year": issued[0] if issued else None,
        "authors": [{"given": a.get("given"), "family": a.get("family"),
                     "affiliation": [x.get("name") for x in a.get("affiliation") or []]}
                    for a in it.get("author") or []],
        "funders": [{"doi": f.get("DOI"), "name": f.get("name"), "award": f.get("award") or []}
                    for f in it.get("funder") or []],
        "is_referenced_by_count": it.get("is-referenced-by-count"),
        "url": it.get("URL"),
    }


def works_raw(query=None, *, funder=None, award_number=None, rows=25, offset=0,
              cursor=None, from_pub_date=None, to_pub_date=None,
              cache=None, no_cache=False):
    """→ {total, count, rows, next_cursor, params, _meta}; /works direct, verbatim name.
    query full-text × funder (funder DOI→filter=funder:) × award_number (→filter=award.number:,
    only meaningful when funder is given too) × from_pub_date/to_pub_date (→filter=from/until-pub-date:
    bare date; from=2026-10-28 probed, until is the same family per the docs) can be combined;
    **constraint = at least one of query/funder/award_number** (local wall: a bare whole-corpus
    scan is served by the bulk pipeline — a date pair only narrows, it does not count as a
    constraint, from_pub_date alone still scans the whole corpus and is blocked all the same);
    rows 1-100 (politeness tightening, upstream doc cap 1000); offset+rows ≤10,000 (upstream doc wall).
    **cursor (adopted in the 0.2.9 audit)**: deep-pager is the proper deep-paging channel — send
    `cursor="*"` for the first page, feed back `next_cursor` for the next; mutually exclusive with
    offset (the cursor channel is not subject to the 10,000 wall); next_cursor is echoed back
    (null on the last page).
    Award numbers live only inside funder[].award[] on the row, the select face cannot fetch
    them (probe 2026-10-26: select-not-available)."""
    from ..transport import call_provider
    from ..errors import SdkError
    import re

    q = str(query or "").strip() or None
    f_v = str(funder or "").strip() or None
    a_v = str(award_number or "").strip() or None
    cur = str(cursor or "").strip() or None
    if not (q or f_v or a_v):
        raise SdkError("usage_error", provider="crossref",
                       detail="crossref_works requires at least one of query/funder/award_number"
                              " (local safety wall: a bare whole-corpus scan is served by the bulk "
                              "pipeline; from/to_pub_date is a narrowing pair, not a constraint)")
    if a_v and not f_v:
        raise SdkError("usage_error", provider="crossref",
                       detail="award_number requires funder (the upstream award.number filter only "
                              "makes sense combined with funder) — pass --funder as well")
    n = int(rows)
    if not 1 <= n <= _ROWS_CAP:
        raise SdkError("usage_error", provider="crossref",
                       detail=f"rows must be 1-{_ROWS_CAP} (politeness tightening; upstream doc cap 1000)")
    params = {"rows": n}
    if cur is not None:
        params["cursor"] = cur
    else:
        off = int(offset)
        if off < 0:
            raise SdkError("usage_error", provider="crossref", detail="offset must be ≥0")
        if off + n > _OFFSET_WALL:
            raise SdkError("usage_error", provider="crossref",
                           detail=f"offset+rows must be ≤{_OFFSET_WALL:,} (upstream documented "
                                  "deep-paging wall) — deep paging goes through the cursor channel "
                                  "(cursor=\"*\" first, then next_cursor)")
        params["offset"] = off
    if q:
        params["query"] = q
    filters = []
    if f_v:
        filters.append(f"funder:{f_v}")
    if a_v:
        filters.append(f"award.number:{a_v}")
    for key, label, v in (("from_pub_date", "from-pub-date", from_pub_date),
                          ("to_pub_date", "until-pub-date", to_pub_date)):
        if v in (None, ""):
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)):
            raise SdkError("usage_error", provider="crossref",
                           detail=f"{key} must be a bare date YYYY-MM-DD (e.g. 2026-06-01)")
        filters.append(f"{label}:{v}")
    if filters:
        params["filter"] = ",".join(filters)
    r = call_provider(provider, "works", params, cache=cache, no_cache=no_cache)
    msg = (r["data"] or {}).get("message") or {}
    items = msg.get("items") or []
    rows_out = [_work_row(it) for it in items]
    return {"total": msg.get("total-results"), "count": len(rows_out), "rows": rows_out,
            "next_cursor": msg.get("next-cursor") if cur is not None else None,
            "params": params, "_meta": r}
