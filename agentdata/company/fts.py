"""fts — UK Find a Tender Service OCDS provider (UK public procurement; keyless).

GET /api/1.0/ocdsReleasePackages → OCDS 1.1 release package: releases[] (stable ocid key /
buyer.name / awards[].suppliers[{id=GB-FTS-…, name}] / tag / date) + links.next cursor pagination.
Closed parameter set (400 enumerates them): stages, limit, cursor, updatedFrom, updatedTo — no name-search
param exists: name filtering is a client-side contains match (same sense as the lda client_name filter),
pagination continues via cursor.
Date pitfall: updatedFrom/updatedTo require full ISO timestamps ('2026-10-22T00:00:00Z' — bare dates 400);
a single end may be omitted (the server auto-fills now) — norm_win() appends the T timestamp to bare dates.
Note: the old direct Contracts Finder face (www/api.contractsfinder.service.gov.uk) now 404s/000s — CF has
merged into the FTS platform, and the OCP mirror is the historical backfill line; this provider only serves the live face. TTL: 24h.
"""
import re
from urllib.parse import urlparse, parse_qs

from ..errors import SdkError

provider = {
    "id": "fts",
    "baseUrl": "https://www.find-tender.service.gov.uk/api/1.0",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "releases": {"path": "/ocdsReleasePackages", "ttl": 24 * 3600, "timeoutMs": 30000},
    },
    "ttl": {"releases": 24 * 3600},
}

_BARE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def norm_win(v, from_=True):
    """Bare date '2026-10-01' → '2026-10-01T00:00:00Z' (the to end gets 23:59:59); full timestamps pass through."""
    s = str(v or "").strip()
    if not s:
        return None
    if _BARE_DATE.match(s):
        return f"{s}T{'00:00:00' if from_ else '23:59:59'}Z"
    return s


def fts_from_upstream(data, name="", limit=10):
    """Upstream payload → {rows, next_cursor, has_more} (pure function + client-side name filter, offline-testable).
    Match face: buyer.name ∨ awards[].suppliers[].name (a hit on either the buyer or supplier side keeps the row);
    has_more = upstream has a next page (decoupled from the client-side filter — a filtered page that isn't full ≠ no more
    matches; continue with next_cursor)."""
    q = str(name or "").lower().strip()
    hit = (lambda s: not q or q in str(s or "").lower())

    def keep(rel):
        if hit((rel or {}).get("buyer", {}).get("name")):
            return True
        return any(hit(sp.get("name")) for aw in (rel or {}).get("awards") or []
                   for sp in (aw or {}).get("suppliers") or [])

    rows = []
    for rel in [x for x in (data or {}).get("releases") or [] if keep(x)][:limit]:
        rows.append({
            "ocid": rel.get("ocid"),                                  # OCDS stable key (ocds-h6vhtk-…)
            "date": rel.get("date"),
            "tags": rel.get("tag") or [],
            "buyer": (rel.get("buyer") or {}).get("name"),
            "suppliers": sorted({sp.get("name") for aw in rel.get("awards") or []
                                 for sp in aw.get("suppliers") or [] if sp.get("name")}),
            "supplier_ids": sorted({sp.get("id") for aw in rel.get("awards") or []
                                    for sp in aw.get("suppliers") or [] if sp.get("id")}),  # GB-FTS-… registry key
            "award_values": [{"date": aw.get("date"), "amount": (aw.get("value") or {}).get("amount"),
                              "currency": (aw.get("value") or {}).get("currency")}
                             for aw in rel.get("awards") or [] if (aw.get("value") or {}).get("amount") is not None],
            "tender_title": (rel.get("tender") or {}).get("title"),
        })
    nxt = (data or {}).get("links", {}).get("next")
    cursor = (parse_qs(urlparse(nxt).query).get("cursor") or [None])[0] if nxt else None
    return {"rows": rows, "next_cursor": cursor, "has_more": bool(nxt)}


def company_uk_tenders(name, *, stages="award", limit=10, cursor=None,
                       updated_from=None, updated_to=None, cache=None, no_cache=False):
    """→ {rows, next_cursor, has_more, matched_on, _meta}; UK procurement release rows (client-side contains match)."""
    from ..transport import call_provider

    q = str(name or "").strip()
    if not q:
        raise SdkError("usage_error", provider="fts",
                       detail="name is required (the OCDS face has no name-search param — client-side contains match)")
    lim = min(max(1, int(limit) or 10), 100)
    # Fetch strategy: always fetch the full 100-row page (upstream cap) then filter and slice to lim — fetching the
    # original page at lim then filtering is almost guaranteed to come up empty (measured before f5c4f6c)
    p = {"stages": str(stages or "award"), "limit": 100}
    if cursor:
        p["cursor"] = str(cursor)
    wf, wt = norm_win(updated_from, True), norm_win(updated_to, False)
    if wf:
        p["updatedFrom"] = wf
    if wt:
        p["updatedTo"] = wt
    r = call_provider(provider, "releases", p, cache=cache, no_cache=no_cache)
    return {**fts_from_upstream(r["data"], q, lim), "matched_on": "buyer|suppliers contains", "_meta": r}


def releases_raw(*, stages=None, limit=10, cursor=None, updated_from=None, updated_to=None,
                 cache=None, no_cache=False):
    """→ {rows, next_cursor, has_more, params, _meta}; the five OCDS params pass through verbatim (no name filter — upstream has no such param).
    limit 1-100 (upstream page cap — the name-filter line's "always fetch the full 100" is this number); updatedFrom/updatedTo
    get the T timestamp appended to bare dates (bare 400 is empirically proven, same as norm_win). Name-contains filtering is a
    client-layer convenience (uk_fts_tenders name)."""
    from ..transport import call_provider
    from ..errors import SdkError

    lim = int(limit)
    if not 1 <= lim <= 100:
        raise SdkError("usage_error", provider="fts", detail="limit must be 1-100 (upstream page cap)")
    params = {"stages": str(stages or "award"), "limit": lim}
    if cursor:
        params["cursor"] = str(cursor)
    wf, wt = norm_win(updated_from, True), norm_win(updated_to, False)
    if wf:
        params["updatedFrom"] = wf
    if wt:
        params["updatedTo"] = wt
    r = call_provider(provider, "releases", params, cache=cache, no_cache=no_cache)
    return {**fts_from_upstream(r["data"], "", lim), "params": params, "_meta": r}
