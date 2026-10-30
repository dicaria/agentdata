"""biorxiv — bioRxiv/medRxiv details API (preprint metadata stream; keyless).

No key needed (api.biorxiv.org; no stated quota — self-imposed polite 1 rps tier; for heavy
loads use the upstream S3 bulk files). details face, interval stream (probed 2026-10-26:
2026-10-01→20 total 4,619): GET /details/biorxiv/{from}/{to}/{cursor}; response
{messages:[{status,count,total,…}], collection:[…]}.
Three traps: count/total inside messages are strings ('30'/'4619') and must be normalized
to int; the per-row authors field is a semicolon-joined string ("Balch, J. K.; McIntosh,
T. L.; …"), not an array; jatsxml is a URL to the full-text XML (not inline) — full-text
bulk belongs on the jatsxml links, this face is metadata only.
"""
provider = {
    "id": "biorxiv",
    "baseUrl": "https://api.biorxiv.org",
    "rate": {"rps": 1, "burst": 5},
    "ops": {
        "details": {"path": "/details/biorxiv/{from_date}/{to_date}/{cursor}", "method": "GET", "idempotent": True},
    },
    "ttl": {"details": 24 * 3600},
}


def _int_or_none(v):
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return None


def _detail_row(c):
    return {
        "doi": c.get("doi"), "title": c.get("title"), "category": c.get("category"),
        "date": c.get("date"), "version": c.get("version"),
        "authors": c.get("authors"),  # semicolon-joined string (upstream verbatim)
        "author_corresponding": c.get("author_corresponding"),
        "author_corresponding_institution": c.get("author_corresponding_institution"),
        "jatsxml_url": c.get("jatsxml"),  # full-text XML link (URL string, not inline)
    }


def details_raw(from_date, to_date, *, cursor=0, cache=None, no_cache=False):
    """→ {total, count, rows, has_more, params, _meta}; /details/biorxiv/{from}/{to}/{cursor} direct.
    from_date/to_date required (YYYY-MM-DD interval); cursor=page index (0-based, upstream also
    accepts 1 in practice); total=total papers in the interval (string normalized to int); upstream
    does not echo the page size — has_more judges the boundary conservatively (a non-empty page may
    not be the end; an empty page certainly is)."""
    from ..transport import call_provider
    from ..errors import SdkError

    fd = str(from_date or "").strip()
    td = str(to_date or "").strip()
    if not fd or not td:
        raise SdkError("usage_error", provider="biorxiv",
                       detail="biorxiv_details requires from_date and to_date (YYYY-MM-DD interval)")
    cur = int(cursor)
    if cur < 0:
        raise SdkError("usage_error", provider="biorxiv", detail="cursor must be ≥0 (page index)")
    params = {"from_date": fd, "to_date": td, "cursor": cur}
    r = call_provider(provider, "details", params, cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    m0 = (data.get("messages") or [{}])[0] or {}
    rows = [_detail_row(c) for c in data.get("collection") or []]
    total = _int_or_none(m0.get("total"))
    count = _int_or_none(m0.get("count"))
    return {"total": total, "count": count if count is not None else len(rows),
            "rows": rows, "has_more": bool(rows), "params": params, "_meta": r}
