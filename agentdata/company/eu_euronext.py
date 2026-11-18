"""eu_euronext — Euronext live instrument resolver (live.euronext.com searchJSON, keyless).

2026-11-18 probed shape (tmp/probe-e10/p4): GET /en/instrumentSearch/searchJSON?q={ISIN|name|mnemonic}
→ [{value, isin, mic, label(html), link, name}] — keyless, no cookie. One ISIN lists on MULTIPLE
venues (Air Liquide FR0000120073 → XPAR + MTAH with per-venue symbol in label's <span class='symbol'>):
the join key is the ISIN+MIC pair, never the bare ISIN. An empty/unknown q returns a SINGLE
SENTINEL row with label="No results found" and empty isin/mic — zero-hit, not one hit (the engine
drops it). The rich per-face CSV universes (stocks/bonds/etfs × 7 markets) and the AES-encrypted
OHLCV chart face are separate ops (roadmap E11 candidates), not this resolver.
TTL 1 day (instrument reference data); politeness 1 rps (no published quota).
"""
from ..errors import SdkError

provider = {
    "id": "eu_euronext",
    "baseUrl": "https://live.euronext.com",
    "rate": {"rps": 1.0, "burst": 2},
    "ops": {
        # params: q (query string; ISIN / name / mnemonic — the upstream resolves all three)
        "search": {"path": "/en/instrumentSearch/searchJSON", "idempotent": True},
    },
    "ttl": {"search": 86400},
}


def search_instruments(q, *, cache=None, no_cache=False):
    """→ {instruments[], params, _meta}; q → resolver rows across Euronext venues.
    Row keys: isin/mic/name (clean) + link (/en/product/equities/{ISIN}-{MIC} — the detail-page key)
    + symbol parsed out of the html label. The empty-q/unknown-q sentinel row is dropped here."""
    from ..transport import call_provider
    import re as _re

    query = str(q or "").strip()
    if not query:
        raise SdkError("usage_error", provider="eu_euronext",
                       detail="search requires q (ISIN, name or ticker mnemonic)")
    r = call_provider(provider, "search", {"q": query}, cache=cache, no_cache=no_cache)
    rows = r["data"] or []
    out = []
    for row in rows:
        label = row.get("label") or ""
        if not (row.get("isin") or row.get("mic")) and "No results found" in label:
            continue  # sentinel row = zero hits, not an instrument
        m = _re.search(r"class=['\"]symbol['\"]>([^<]+)<", label)
        out.append({
            "isin": row.get("isin") or None,
            "mic": row.get("mic") or None,          # venue — join key is ISIN+MIC, never bare ISIN
            "name": row.get("name") or None,
            "symbol": (m.group(1).strip() if m else None),  # venue-specific ticker, from the html label
            "link": row.get("link") or None,        # /en/product/equities/{ISIN}-{MIC}
        })
    return {"instruments": out, "params": {"q": query}, "_meta": r}
