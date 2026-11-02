"""gb_gtr — UKRI Gateway to Research API (UK public funding projects; keyless).

No key needed (gtr.ukri.org/gb_gtr/api; no stated quota — self-imposed polite 1 rps tier).
projects face (probed 2026-10-26): GET /projects?q=&s=&p=; s<10 gets an upstream 400
"Page size cannot be less than 10" (a friendly error, not a block — enforced locally as
s≥10); response shell {"project": [...]}.
The organisation edge is a second hop into detail: list rows carry only href; following it,
links.link[] entries with rel=LEAD_ORG/PM_PER hold the participating-institution/PI edges
(same two-hop shape as climatetrace) — this face is the list only; the second hop is left
to a future face.
"""
provider = {
    "id": "gb_gtr",
    "baseUrl": "https://gtr.ukri.org/gb_gtr/api",
    "rate": {"rps": 1, "burst": 5},
    "ops": {
        "projects": {"path": "/projects", "method": "GET", "idempotent": True},
    },
    "ttl": {"projects": 24 * 3600},
}

_SIZE_FLOOR = 10  # s<10 gets an upstream 400 "Page size cannot be less than 10" (probe 2026-10-26)


def _project_row(p):
    return {
        "id": p.get("id"), "title": p.get("title"), "status": p.get("status"),
        "start": p.get("start"), "end": p.get("end"),
        "grant_category": p.get("grantCategory"),
        "lead_funder": p.get("leadFunder"),
        "href": p.get("href"),
    }


def projects_raw(q, *, s=20, p=1, cache=None, no_cache=False):
    """→ {total, count, rows, has_more, params, _meta}; /projects?q= direct, verbatim name.
    q required (local wall: browsing the whole corpus is not this face's use case); s≥10
    (upstream 400 wall); p≥1; upstream sends no total — a full page signals more via
    has_more (len(rows)==s, same pattern as nsf)."""
    from ..transport import call_provider
    from ..errors import SdkError

    query = str(q or "").strip()
    if not query:
        raise SdkError("usage_error", provider="gb_gtr", detail="gb_gtr_projects requires q (search term)")
    size = int(s)
    if size < _SIZE_FLOOR:
        raise SdkError("usage_error", provider="gb_gtr",
                       detail=f"s must be ≥{_SIZE_FLOOR} (upstream 400 wall: \"Page size cannot be less than 10\", probed 2026-10-26)")
    page = int(p)
    if page < 1:
        raise SdkError("usage_error", provider="gb_gtr", detail="p must be ≥1")
    params = {"q": query, "s": size, "p": page}
    r = call_provider(provider, "projects", params, cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    rows = [_project_row(x) for x in data.get("project") or []]
    return {"total": None, "count": len(rows), "rows": rows,
            "has_more": len(rows) == size, "params": params, "_meta": r}
