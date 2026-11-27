"""eu_cijeu — CJEU (Court of Justice of the European Union) jurisprudence search, the
InfoCuria elastic connector (infocuriaws.curia.europa.eu/elastic-connector/search, keyless).

EU legal face (0.3.59; admitted from research booklet judgments-corpus, the working DSL
replays the SPA's own XHR — captured live in tmp/probe-cdp-r7 (netclick bodies) and re-shot
2026-11-13 in tmp/probe-sdk-0359/r2_cjeu*.json). The register: ~7,630 jurisprudence search
hits for a bare empty-term browse; 'insurance' → 5,049. The affair index carries METADATA
only — contentLength is 0 on every hit and there is no full text here; full text rides the
CELEX → EUR-Lex Cellar bridge (celex '62023TJ0070' → eur-lex.europa.eu).

CONTRACT (POST JSON — the body must match the SPA shape or the gateway answers 500):
{"searchTerm", "multiSearchTerms": [], "pagination": {"pageNumber" (0-based), "pageSize",
"from", "to" (1-based display window: from = page*size+1, to = (page+1)*size — a missing or
mismatched pair 500s just like a lowercase language)}, "language": "EN" (uppercase),
"tabName": "jurisprudence", "isAllTabsRequest": true, "ecli": "", "publishedId": "",
"usualName": "", "logicDocId": "", "repJurExpand": true, "advancedFiltersValue": [],
"isSearchExact": true, "searchSources": ["document", "metadata"]}.
Response {totalHits, maxScore, searchHits[], aggregatesMap}; hit = {index, id, score,
sortValues, content{logicDocId 'id_NNNNNN', idProcedure 'T/0070/23/…', idPublished 'T-70/23',
docType 'Arrêt (extraits)', docTypeCode ARRET_EXT, docDate, docFormats, contentLength: 0,
celex, ecli, pubNum, published, recueil, affairJurisdiction, groupByLogicalId[…], …}}.
The groupByLogicalId array (24 members on the sample hit) keys the language versions of the
same logical case. The face replays the measured SPA defaults verbatim — exact-mode search
(isSearchExact true), tab jurisprudence, source document+metadata — and exposes only what was
measured: the term, the language (uppercased), the window. pageSize wall 1-100 (100 shot
live, page 2 verified). 0.25/2 polite (AWS API gateway upstream), TTL 24h.
"""
import re

from ..errors import SdkError

provider = {
    "id": "eu_cijeu",
    "baseUrl": "https://infocuriaws.curia.europa.eu",
    "rate": {"rps": 0.25, "burst": 2},
    "concurrency": 1,
    "ops": {
        "search": {"path": "/elastic-connector/search", "method": "POST",
                   "idempotent": True, "timeout": 45.0},
    },
    "ttl": {"search": 24 * 3600},
}

_ROW_KEYS = ("logicDocId", "idProcedure", "idPublished", "docType", "docTypeCode", "docDate",
             "docFormats", "contentLength", "celex", "ecli", "pubNum", "published", "recueil",
             "affairJurisdiction", "affairJurisdictionCode")


def row_from_upstream(h):
    """searchHit → flat metadata card (pure function — split out for offline testing)."""
    c = h.get("content") or {}
    row = {"score": h.get("score"), "sort_values": h.get("sortValues")}
    for k in _ROW_KEYS:
        row[_camel(k)] = c.get(k)
    grp = c.get("groupByLogicalId")
    row["group_members"] = len(grp) if isinstance(grp, list) else None
    return row


def _camel(k):
    """logicDocId → logic_doc_id (single lowercase-run split; docDate → doc_date)."""
    return re.sub(r"([A-Z]+)", lambda m: "_" + m.group(1).lower(), k).lstrip("_")


def search_raw(q=None, *, lang="EN", limit=20, page=0, cache=None, no_cache=False):
    """→ {total, rows[], params, _meta}. q = free term (empty/None = bare browse of the whole
    tab — the SPA's own landing shape); lang = ISO code, uppercased (only EN measured; other
    codes ride through — an unsupported code answers upstream 500, surfaced as
    upstream_unavailable); limit = pageSize wall 1-100; page 0-based (the window from/to pair
    is derived: page p → from p*size+1, to (p+1)*size)."""
    term = str(q or "").strip()
    language = str(lang or "EN").strip().upper() or "EN"
    try:
        size = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="eu_cijeu",
                       detail=f"limit must be an integer 1-100, got {limit!r}")
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="eu_cijeu",
                       detail=f"limit must be 1-100 (the SPA pages at 10/20; 100 shot live), got {limit!r}")
    try:
        pg = int(page) if page else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="eu_cijeu",
                       detail=f"page must be an integer >=0, got {page!r}")
    if pg < 0:
        raise SdkError("usage_error", provider="eu_cijeu",
                       detail=f"page is 0-based (pageNumber), got {pg}")
    body = {
        "searchTerm": term,
        "multiSearchTerms": [],
        "pagination": {"pageNumber": pg, "pageSize": size,
                       "from": pg * size + 1, "to": (pg + 1) * size},
        "language": language,
        "tabName": "jurisprudence",
        "isAllTabsRequest": True,
        "ecli": "",
        "publishedId": "",
        "usualName": "",
        "logicDocId": "",
        "repJurExpand": True,
        "advancedFiltersValue": [],
        "isSearchExact": True,
        "searchSources": ["document", "metadata"],
    }
    from ..transport import call_provider
    r = call_provider(provider, "search", body, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    if not isinstance(doc, dict) or "searchHits" not in doc:
        raise SdkError("upstream_unavailable", provider="eu_cijeu",
                       detail="elastic-connector answered an unexpected shape (no searchHits — "
                              "a 78-byte 'An error occurred' body means the DSL shape drifted; "
                              "keep it byte-equal to the SPA payload)")
    return {"total": doc.get("totalHits"),
            "rows": [row_from_upstream(h) for h in doc.get("searchHits") or []],
            "params": {"q": term or None, "lang": language, "limit": size, "page": pg},
            "_meta": r}
