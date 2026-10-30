"""cf — UK Contracts Finder OCDS provider (UK below-threshold public procurement; keyless).

2026-10-23 probing chain: bare path /api/1.0/ocdsReleasePackages 404s, host api.contractsfinder
gives 000 — the real working face is
www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search (verified 2026-10-20, re-verified
alive 2026-10-23). Division of labor with FTS: FTS = WTO-line above-threshold, CF = below-threshold
small contracts — the two faces complement each other.
Parameter face: publishedFrom/publishedTo (bare dates are legal here — opposite of FTS's full
timestamp requirement) + limit(≤100) + cursor + stages(tender|award, added in the 0.2.9 audit —
symmetric with the FTS face);
without a window releases are always empty — default falls back to a rolling "last 7 days" window.
Identifier face: suppliers[].id is GB-COH-<Companies House number> (same key as the companies-house
batch corpus line). TTL: 24h.
"""
import re
from datetime import timedelta, datetime, timezone
from urllib.parse import urlparse, parse_qs

from ..errors import SdkError

provider = {
    "id": "cf",
    "baseUrl": "https://www.contractsfinder.service.gov.uk",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/Published/Notices/OCDS/Search", "ttl": 24 * 3600, "timeoutMs": 30000},
    },
    "ttl": {"search": 24 * 3600},
}

_BARE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def cf_from_upstream(data, name="", limit=10):
    """Upstream payload → {rows, next_cursor, has_more} (pure function + client-side name filter, offline-testable; same shape as fts)."""
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
            "ocid": rel.get("ocid"),
            "date": rel.get("date"),
            "tags": rel.get("tag") or [],
            "buyer": (rel.get("buyer") or {}).get("name"),
            "suppliers": sorted({sp.get("name") for aw in rel.get("awards") or []
                                 for sp in aw.get("suppliers") or [] if sp.get("name")}),
            "supplier_ids": sorted({sp.get("id") for aw in rel.get("awards") or []
                                    for sp in aw.get("suppliers") or [] if sp.get("id")}),  # GB-COH-… (CH number) / GB-CFS-… (CF registry key), two forms
            "award_values": [{"date": aw.get("date"), "amount": (aw.get("value") or {}).get("amount"),
                              "currency": (aw.get("value") or {}).get("currency")}
                             for aw in rel.get("awards") or [] if (aw.get("value") or {}).get("amount") is not None],
            "tender_title": (rel.get("tender") or {}).get("title"),
        })
    nxt = (data or {}).get("links", {}).get("next")
    cursor = (parse_qs(urlparse(nxt).query).get("cursor") or [None])[0] if nxt else None
    return {"rows": rows, "next_cursor": cursor, "has_more": bool(nxt)}


def company_uk_cf_tenders(name, *, limit=10, cursor=None, published_from=None, published_to=None,
                          cache=None, no_cache=False):
    """→ {rows, next_cursor, has_more, window, matched_on, _meta}; CF release rows (client-side contains match).
    Always fetches the full 100-row page then filters and slices to limit; window default = rolling last 7 days (upstream is always empty without one)."""
    from ..transport import call_provider

    q = str(name or "").strip()
    if not q:
        raise SdkError("usage_error", provider="cf",
                       detail="name is required (the OCDS face has no name-search param — client-side contains match)")
    lim = min(max(1, int(limit) or 10), 100)
    p = {"limit": 100}
    if cursor:
        p["cursor"] = str(cursor)

    def iso(s):
        s = str(s or "").strip()
        return s if _BARE_DATE.match(s) else None

    today = datetime.now(timezone.utc).date()

    def d(n):
        return (today + timedelta(days=n)).isoformat()

    frm, to = iso(published_from), iso(published_to)
    if not frm and not to:
        frm, to = d(-7), d(0)      # both default: rolling 7-day window
    elif not frm:
        frm = d(-7)                # single end: the other end filled from the 7-day window
    elif not to:
        to = d(0)
    p["publishedFrom"], p["publishedTo"] = frm, to
    r = call_provider(provider, "search", p, cache=cache, no_cache=no_cache)
    return {**cf_from_upstream(r["data"], q, lim),
            "window": {"published_from": frm, "published_to": to},
            "matched_on": "buyer|suppliers contains", "_meta": r}


def search_raw(*, published_from=None, published_to=None, limit=100, cursor=None,
               stages=None, cache=None, no_cache=False):
    """→ {rows, next_cursor, has_more, window, params, _meta}; CF upstream-verbatim params (no name filter).
    publishedFrom/publishedTo accept bare dates (opposite of FTS's full-timestamp requirement — evidence the two faces differ);
    both-default = rolling 7-day window (**our default, not upstream's** — upstream is always empty without a window); limit 1-100.
    stages (0.2.9 audit addition): tender|award passed through verbatim — invalid values get a self-describing upstream 400
    (2026-10-28 probe: stages=BOGUS → code 3200 "BOGUS is not a valid OCDS stage", self-validating, so no local wall on this param);
    absent = not sent → mixed feed (same-window baseline 100 rows = award 88 + tender 2 + planning 3; stages=tender gives 59 pure
    tender/tenderAmendment rows, stages=award 100 pure award/awardUpdate rows — a real filter, not an echo)."""
    from ..transport import call_provider
    from ..errors import SdkError

    lim = int(limit)
    if not 1 <= lim <= 100:
        raise SdkError("usage_error", provider="cf", detail="limit must be 1-100 (upstream page cap)")
    params = {"limit": lim}
    if cursor:
        params["cursor"] = str(cursor)
    if stages:
        params["stages"] = str(stages).strip()

    def iso(v):
        s = str(v or "").strip()
        return s if _BARE_DATE.match(s) else None

    today = datetime.now(timezone.utc).date()

    def d(n):
        return (today + timedelta(days=n)).isoformat()

    frm, to = iso(published_from), iso(published_to)
    if not frm and not to:
        frm, to = d(-7), d(0)   # our default: upstream is always empty without a window (probed), rolling 7-day fallback
    elif not frm:
        frm = d(-7)
    elif not to:
        to = d(0)
    params["publishedFrom"], params["publishedTo"] = frm, to
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    return {**cf_from_upstream(r["data"], "", lim),
            "window": {"published_from": frm, "published_to": to},
            "params": params, "_meta": r}
