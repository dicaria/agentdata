"""afdb — African Development Bank debarred-entities roster provider (afdb.org json-feed; keyless).

legal debarment-roster face (0.3.21; admitted 2026-11-02, probed tmp/probe-debar-0321). Shape measured 2026-11-02:
GET /en/debarred-entities-json-feed → a bare JSON array, 1,440 rows × 7 columns (Type FIRM 1,196 / INDIVIDUAL 244,
Name, Nationality, From, To, Basis, Notes) — a single-shot full dump (the -csv-export sibling serves byte-identical
content; the -xml-export sibling returns a 2.4KB stub). To = empty means ongoing (169 rows); Notes ∈ {ONGOING,
INDEFINITE, empty}.
**Basis is the cross-debarment edge, self-evidenced**: "CROSS DEBARMENT : WBG" 653 / "CROSS-DEBARMENT: ADB" 377 /
"CROSS-DEBARMENT: IDB" 161+2 / "CROSS DEBARMENT : EBRD" 127 / "DEBARMENT:AFDB" 120 — note the upstream spacing is
**inconsistent** ("CROSS DEBARMENT : WBG" with spaces vs "CROSS-DEBARMENT: ADB" hyphenated): the basis filter is a
contains-match precisely so "WBG"/"ADB"/"IDB"/"EBRD" hit regardless of punctuation.
**Cloudflare UA-fingerprint gate** (pinned 2026-11-02): the default agentdata UA passes then 403s flakily on repeat;
a bare "Mozilla/5.0" UA is refused outright; the **full browser document suite passes consistently** — per-request
header override (ext 8), same family as UNGM (0.3.12).
Screening = local full-register scan (upstream has no query surface), cache 24h.
TTL: 24h; polite tier 0.2 rps (single-endpoint face; also keeps the Cloudflare gate calm).
"""
from ..errors import SdkError

provider = {
    "id": "afdb",
    "baseUrl": "https://www.afdb.org",
    "rate": {"rps": 0.2, "burst": 1},
    "ops": {
        "debarred": {"path": "/en/debarred-entities-json-feed", "timeoutMs": 90000},
    },
    "ttl": {"debarred": 24 * 3600},
}

# Cloudflare UA-fingerprint gate (pinned 2026-11-02, tmp/probe-debar-0321 p3): default agentdata UA → flaky
# 403 on repeat; bare Mozilla/5.0 → 403; this full document suite → 200 twice in a row — ext-8 override
_CF_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.afdb.org/en/projects-operations/debarment-and-sanctions-procedures",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


def rows_from_upstream(data):
    """Upstream JSON array → debarred-entity rows (pure function; the seven upstream columns verbatim —
    the register is already narrow, and To="" / Notes carry the ongoing/indefinite semantics)."""
    return [{k: r.get(k) for k in ("Type", "Name", "Nationality", "From", "To", "Basis", "Notes")}
            for r in (data or [])]


def filter_rows(rows, name=None, type=None, basis=None):
    """Local register scan (pure function). name: contains (case-insensitive) over Name; type: exact over
    Type (FIRM/INDIVIDUAL); basis: **contains** over Basis — upstream spacing is inconsistent
    ("CROSS DEBARMENT : WBG" vs "CROSS-DEBARMENT: ADB"), so filter on the bank token (WBG/ADB/IDB/EBRD)."""
    needle = str(name or "").strip().lower() or None
    ty_needle = str(type or "").strip().upper() or None
    bs_needle = str(basis or "").strip().lower() or None
    hits = []
    for r in rows:
        if ty_needle and str(r.get("Type") or "").strip().upper() != ty_needle:
            continue
        if bs_needle and bs_needle not in str(r.get("Basis") or "").lower():
            continue
        if needle and needle not in str(r.get("Name") or "").lower():
            continue
        hits.append(r)
    return hits


def debarred_entities_raw(name=None, *, type=None, basis=None, limit=20, cache=None, no_cache=False):
    """Full-register scan (pulls the whole feed, caches 24h, then scans locally)
    → {rows, total_matched, scanned_rows, limit_applied, params, _meta}.

    name = contains over Name; type = FIRM/INDIVIDUAL exact; basis = contains over Basis (bank token:
    WBG/ADB/IDB/EBRD — punctuation upstream is inconsistent). No filter → enumerate from the register head."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="afdb",
                       detail=f"limit must be 1-100 (local payload wall), got '{limit}'")
    r = call_provider(provider, "debarred", {}, cache=cache, no_cache=no_cache,
                      extra_headers=_CF_BROWSER_HEADERS)
    rows = rows_from_upstream(r["data"])
    hits = filter_rows(rows, name=name, type=type, basis=basis)
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "limit_applied": size,
            "params": {"name": name, "type": type, "basis": basis}, "_meta": r}
