"""gazette — The Gazette (London/Edinburgh/Belfast official public record) notice-search provider
(thegazette.co.uk all-notices data.json; keyless, Open Government Licence).

legal gazette face (0.3.27; admitted 2026-11-03, probed tmp/probe-legal-0327). Shape measured 2026-11-03:
GET /all-notices/notice/data.json → JSON with f:total (STRING upstream — 4,887,099 unfiltered, 157,792 for
noticetypes=2432), f:page-number/f:page-size/f:page-start/f:page-stop (strings), entry[] where title = the
notice headline (the company name on corporate insolvency codes, a person name elsewhere), f:notice-code,
category.@term = the code's plain name, f:name + f:familyName = the placing party ("Lee Barmby") or the
edition when filed centrally ("London Gazette"), published/updated, geo:Point = registered-office
coordinates, content = HTML snippet, 11 link alternates incl. /notice/<id>/data.json?view=linked-data.

**The two parameter traps (pinned 2026-11-03)**: `noticecode=` is SILENTLY IGNORED — the working filter param
is `noticetypes`, +-joined (noticetypes=2410%2B2432); `categorycode=` likewise returns empty (2026-10-19
recipe probe) — event filtering is by notice code only. results-page-size accepts arbitrary values (5 probed)
with a hard max 100; sort-by ∈ {latest-date, oldest-date} (upstream default latest-date).

**Insolvency preset**: the corporate-insolvency code chapter (code table at /noticecodes; 2026-10-19 recipe):
2404 cross-border / 2408 other corporate / 2410 administrator appointment / 2411 administrative order /
2414+2424 deemed consent / 2421-2423 receiver / 2431 cessation resolution / 2432 liquidator / 2607 insolvency
practitioner / 2702 partnership dissolution — insolvency=True sugar unions these onto --noticetypes.

The register: 3.58M notices, digitised from 1992, three editions, daily. Licence OGL.
TTL: 12h; polite tier 0.5 rps (search surface; page-size hard cap 100).
"""
import re

from ..errors import SdkError

provider = {
    "id": "gazette",
    "baseUrl": "https://www.thegazette.co.uk",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/all-notices/notice/data.json", "notFound": [404], "timeoutMs": 60000},
    },
    "ttl": {"search": 12 * 3600},
}

# The corporate-insolvency code chapter (2026-10-19 recipe + the /noticecodes table) — winding-up /
# administration / liquidation / partnership-dissolution events; everything else (grants, honours,
# planning notices) is outside the preset and reachable via --noticetypes.
INSOLVENCY_CODES = ("2404", "2408", "2410", "2411", "2414",
                    "2421", "2422", "2423", "2424", "2431", "2432", "2607", "2702")

_SORTS = ("latest-date", "oldest-date")


def _codes(value):
    """noticetypes input → the ordered code list. Accepts one code, a +- or comma-joined string, or a
    list (a comma-joined string would filter to nothing upstream — split locally, the Eurostat defense)."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else re.split(r"[+,]", str(value))
    out = []
    for x in items:
        c = str(x or "").strip()
        if c and c not in out:
            out.append(c)
    return out


def rows_from_upstream(data):
    """Upstream entry[] → notice rows (pure function). title = the notice headline — the company name on
    corporate insolvency codes, a person name elsewhere; placed_by = f:name + f:familyName (the placing
    party, or the edition when filed centrally: "London Gazette"); url = the human notice page."""
    rows = []
    for e in (data or {}).get("entry") or []:
        links = e.get("link") or []
        self_url = next((l.get("@href") for l in links if l.get("@rel") == "self"), None)
        notice_url = next((l.get("@href") for l in links if not l.get("@rel")), None)
        pt = e.get("geo:Point") or {}
        placed = " ".join(p for p in (e.get("f:name"), e.get("f:familyName")) if p) or None
        rows.append({
            "notice_id": str(e.get("id") or "").rstrip("/").rsplit("/", 1)[-1] or None,
            "notice_code": e.get("f:notice-code"),
            "category": (e.get("category") or {}).get("@term"),
            "title": e.get("title"),
            "placed_by": placed,
            "status": e.get("f:status"),
            "published": e.get("published"),
            "place_lat": pt.get("geo:lat"),
            "place_long": pt.get("geo:long"),
            "url": notice_url or self_url,
            "content": e.get("content"),
        })
    return rows


def notices_raw(text=None, *, noticetypes=None, insolvency=None, start_date=None, end_date=None,
                page=1, page_size=20, sort=None, cache=None, no_cache=False):
    """Search the notice register → {total, count, page, page_size, rows, params, _meta}.

    text = full-text contains; noticetypes = notice code(s) — one code, a +- or comma-joined string or a
    list; insolvency = the corporate-insolvency chapter preset (union'd with the explicit codes);
    start_date/end_date = YYYY-MM-DD publish window; sort = latest-date|oldest-date.
    At least one filter is REQUIRED — a bare search enumerates the whole register (the bulk wall)."""
    from ..transport import call_provider

    txt = str(text or "").strip() or None
    codes = _codes(noticetypes)
    if insolvency:
        for c in INSOLVENCY_CODES:
            if c not in codes:
                codes.append(c)
    if not (txt or codes or start_date or end_date):
        raise SdkError("usage_error", provider="gazette",
                       detail="at least one filter is required (--text, --noticetypes, --insolvency or "
                              "--start-date/--end-date): a bare search enumerates the whole register "
                              "(4,887,099 notices, probed 2026-11-03) — the bulk-download wall")
    if sort is not None and sort not in _SORTS:
        raise SdkError("usage_error", provider="gazette",
                       detail=f"sort must be one of {' / '.join(_SORTS)} (upstream param: sort-by), got '{sort}'")
    pg = int(page or 1)
    if pg < 1:
        raise SdkError("usage_error", provider="gazette",
                       detail=f"page must be >= 1, got '{page}'")
    size = int(page_size or 20)
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="gazette",
                       detail=f"page_size must be 1-100 (upstream results-page-size hard max, probed "
                              f"2026-11-03), got '{page_size}'")
    qs = {"text": txt, "results-page": pg, "results-page-size": size}
    if codes:
        qs["noticetypes"] = "+".join(codes)          # +-joined — noticecode= is silently ignored upstream
    if start_date:
        qs["start-publish-date"] = start_date
    if end_date:
        qs["end-publish-date"] = end_date
    if sort:
        qs["sort-by"] = sort
    r = call_provider(provider, "search", qs, cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    try:
        total = int(data.get("f:total") or 0)         # STRING upstream
    except (TypeError, ValueError):
        total = 0
    rows = rows_from_upstream(data)
    return {"total": total, "count": len(rows), "page": pg, "page_size": size, "rows": rows,
            "params": qs, "_meta": r}
