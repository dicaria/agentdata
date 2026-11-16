"""ch_finma — FINMA (Swiss Financial Market Supervisory Authority) news & enforcement
search, the Sitecore CMS search API (www.finma.ch/{lang}/api/search/getresult, keyless).

CH legal face (0.3.59; admitted from research booklet ch-finma 册 146, re-probed live
2026-11-13, tmp/probe-sdk-0359/r2_finma*.json — two live-law changes vs the booklet's
2026-11 probes are baked in: (1) the query term is now MANDATORY — an empty query or a
Thema-GUID-only body answers Count: 0 where the old probes counted; (2) pagination rides
the URL query string, body Skip is ignored). Search spans FINMA's whole news surface:
press releases, enforcement news, publications — 'enforcement' → 125 hits live.

CONTRACT (form-urlencoded POST — the JSON channel is not this endpoint's dialect):
POST /{lang}/api/search/getresult?Skip=<n>, body ds={0FA14E55-5B20-4578-8910-BBCD590DE3AD}
(the site's own data-source GUID, embedded in the news page HTML and stable — a public page
constant, kept as a module constant per the wb_debarred/dgcomp precedent) &Order=4&query=
<term>. Headers: Referer/Origin on www.finma.ch. lang ∈ {en, de} (the CMS language tree;
'en' measured). The response: {Items[...], Count, Skip, SkipNext, ResultsPerPage, ...
MaxResultCount: 1000, Facets[...]}; Item = {Id, Title, Description, Link (/en/news/yyyy/mm/
slug), Category ('Press release,2026'), Type ('News'), Date ('29 September 2026'),
DateMobile, Timestamp, Tab, Panel}.

Walls: query non-empty (the live law above); the page window is upstream-fixed at 20 rows
(ResultsPerPage — limit wall 1-20); MaxResultCount 1000 means a term matching >1000 needs
date-window partitioning — the face surfaces Count so the caller can see the ceiling.
Skip paging verified (?Skip=20 → SkipNext 40, 100-shot window math 101-200 equivalent on
the cjeu twin). The module normalizes Date → ISO (hand-rolled month map — %b is
locale-sensitive) and absolutizes Link against https://www.finma.ch. Facets ride along
inertly (the measured facet vocabulary — 'Publiziert als' etc.). 0.25/2 polite, TTL 24h.
"""
import re

from ..errors import SdkError

provider = {
    "id": "ch_finma",
    "baseUrl": "https://www.finma.ch",
    "rate": {"rps": 0.25, "burst": 2},
    "concurrency": 1,
    "ops": {
        "search": {"path": "/{lang}/api/search/getresult?Skip={skip}", "method": "POST",
                   "urlencoded": True, "idempotent": True, "timeout": 30.0},
    },
    "ttl": {"search": 24 * 3600},
}

# the site's own data-source GUID (public page constant — data-source attribute on the
# news page markup; not a credential)
_DS = "{0FA14E55-5B20-4578-8910-BBCD590DE3AD}"
_ORDER = "4"

_LANGS = ("en", "de")
_MON = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12}

_MON_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$")


def _date_to_iso(v):
    """'29 September 2026' → '2026-09-29' (hand-rolled month map — strptime %b is
    locale-sensitive; unparseable strings pass back as None with the raw kept)."""
    if not isinstance(v, str):
        return None
    m = _MON_RE.match(v.strip())
    if m and m.group(2).capitalize() in _MON:
        return f"{int(m.group(3)):04d}-{_MON[m.group(2).capitalize()]:02d}-{int(m.group(1)):02d}"
    return None


def row_from_upstream(d):
    """News item card (pure function — split out for offline testing)."""
    link = d.get("Link")
    return {
        "id": d.get("Id"),
        "title": d.get("Title"),
        "description": d.get("Description"),
        "url": provider["baseUrl"] + link if link and not link.startswith("http") else link,
        "category": d.get("Category"),
        "type": d.get("Type"),
        "date": _date_to_iso(d.get("Date")),
        "date_raw": d.get("Date"),
        "timestamp": d.get("Timestamp"),
    }


def search_raw(q, *, lang="en", limit=20, offset=0, cache=None, no_cache=False):
    """→ {count, skip_next, results_per_page, rows[], facets, params, _meta}. q = the term
    (REQUIRED — live law: empty query answers Count 0); lang ∈ {en, de}; limit wall 1-20
    (upstream page window fixed); offset = Skip (URL query — body Skip is ignored, measured).
    count is the term's total (MaxResultCount 1000 upstream — a bigger term needs
    date-window partitioning)."""
    term = str(q or "").strip()
    if not term:
        raise SdkError("usage_error", provider="ch_finma",
                       detail="ch_finma_enforcement_news requires q — the empty query answers "
                              "Count 0 (live law measured 2026-11-13; the old GUID-only body is dead)")
    language = str(lang or "en").strip().lower() or "en"
    if language not in _LANGS:
        raise SdkError("usage_error", provider="ch_finma",
                       detail=f"lang must be one of {', '.join(_LANGS)}, got {lang!r}")
    try:
        size = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ch_finma",
                       detail=f"limit must be an integer 1-20 (upstream page window fixed), got {limit!r}")
    if not 1 <= size <= 20:
        raise SdkError("usage_error", provider="ch_finma",
                       detail=f"limit must be 1-20 (ResultsPerPage is upstream-fixed at 20), got {limit!r}")
    try:
        skip = int(offset) if offset else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ch_finma",
                       detail=f"offset must be an integer >=0 (Skip), got {offset!r}")
    if skip < 0:
        raise SdkError("usage_error", provider="ch_finma",
                       detail=f"offset must be >=0, got {skip}")
    from ..transport import call_provider
    r = call_provider(provider, "search",
                      {"lang": language, "skip": skip,
                       "ds": _DS, "Order": _ORDER, "query": term},
                      cache=cache, no_cache=no_cache,
                      extra_headers={"Referer": f"https://www.finma.ch/{language}/news/",
                                     "Origin": "https://www.finma.ch"})
    doc = r["data"] or {}
    if not isinstance(doc, dict) or "Items" not in doc:
        raise SdkError("upstream_unavailable", provider="ch_finma",
                       detail="getresult answered an unexpected shape (no Items — the ds GUID "
                              "or form dialect may have drifted; re-probe the news page's data-source)")
    return {"count": doc.get("Count"),
            "skip_next": doc.get("SkipNext"),
            "results_per_page": doc.get("ResultsPerPage"),
            "rows": [row_from_upstream(x) for x in doc.get("Items") or []][:size],
            "facets": doc.get("Facets"),
            "params": {"q": term, "lang": language, "limit": size, "offset": skip},
            "_meta": r}
