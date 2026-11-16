"""de_register — German Unternehmensregister live register search (www.unternehmensregister.de,
Bundesanzeiger Verlag, keyless).

DE live company-register search face (0.3.56; register 2026-11-02 break-in, re-verified live
2026-11-12, probes tmp/probe-sdk-0356/p1_*). THREE-HOP KEYLESS PROTOCOL, all plain curl/urllib:

  1. GET /api/search-token → JSON body {"token": "<231-char>", "status": 200}. The token is
     valid 1h upstream; the face caches it 45min (safely inside the window). A 423/451 here is
     the geo/IP gate code, not an auth failure.
  2. GET /de/suche?companyName=<name>&companyNameExactMatch=true&searchToken=<token> (307
     redirect follows; header `RSC: 1` asked for the React Server Component stream,
     text/x-component — plain HTML comes back without it). The stream is NOT pure JSON: the
     result object is EMBEDDED in the RSC line protocol with escaped strings. The face locates
     `"searchResults":` and brace-matches the JSON (string-aware, escapes respected), then
     json.loads it — verified on exact (1 company + its 30-publication event stream) and fuzzy
     (15 companies) shapes 2026-11-12.
  3. (out of face scope) GET /api/publication-download?payload=<encryptedPayload> serves the
     free announcement PDF; rows carry encrypted_payload verbatim, binaries stay a
     batch-pipeline concern.

searchResults carries {elasticSearchDtos[], currentPage, totalPages, drilldown,
hasReachedResultsLimit, isRestrictedSearch}. Each dto = {entityType, companyDto,
publicationDto, branchDto}: entityType "1-company" rows are register entries (companyDto with
encryptedId / name / location / euid ("DED2601V.HRB6684" — the EU interconnection key, court
code + form code + number) / registerType / registerCourt{courtCode} / state / legalForm /
registerNumber / changeFlag / deletedFlag (the struck-off flag!) / lastUpdate / hasBranches /
companyHistory / formerCourt / tempGuid), entityType "2-publication" rows are the event stream
(publicationDto with title / sourceName (Bundesanzeiger|…) / sourceDate / publicationCategory
/ publicationPart / encryptedPayload (→ free PDF) / language / translationLanguages). The face
returns companies as rows and publications separately.

SEARCH SEMANTICS (measured): exact channel = companyName + companyNameExactMatch=true; fuzzy
channel = companySearchTerm (both verified — exact "Siemens AG" 1 company hit, fuzzy
"Bayerische Motoren" 15 companies across 34 pages). Exactness is BEST-EFFORT: the same
companyName that returned Siemens AG HRB 6684 on 2026-11-02 returned Siemens Energy AG
HRB 252581 on 2026-11-12 (live-register churn; rows carry the full companyDto for caller-side
filtering). 1,000-hit cap per query ("Suchergebnis auf 1.000 Treffer begrenzt"), 60 rows/page,
from=<offset> paging. lastUpdate ticks weekly (2026-10-13 measured). DE HRB numbers are only
unique together with the court code — join on court_code+register_number, never the bare
number; euid is the strong key.

CACHE RULING: the search op is NEVER cached — the searchToken rides the URL, so a cache keyed
on the full param set would fork per token hour (mx_cnv header-paging ruling); the token op IS
cached (45min TTL). Politeness tier 0.3 rps (no published quota; token reuse measured across
three searches).
"""
from ..errors import SdkError

provider = {
    "id": "de_register",
    "baseUrl": "https://www.unternehmensregister.de",
    "rate": {"rps": 0.3, "burst": 2},
    "concurrency": 1,
    "ops": {
        # JSON body {"token": "<231 chars>", "status": 200} — cached 45min (upstream validity 1h)
        "token": {"path": "/api/search-token"},
        # GET + query params, RSC: 1 header → text/x-component stream (accept:text — the provider
        # parses the embedded JSON itself); never cached (search_raw passes cache=None — the token
        # rides the URL, so a cache keyed on the full param set would fork per token hour)
        "search": {"path": "/de/suche", "accept": "text", "timeout": 60.0, "idempotent": True},
    },
    "ttl": {"token": 45 * 60},
}

_RESULTS_CAP = 1000          # "Suchergebnis auf 1.000 Treffer begrenzt"
_PAGE_SIZE = 60              # measured rows/page (fuzzy page 1 von 34 at ~2k hits)


def rows_from_upstream(sr):
    """searchResults dict → {rows (companies, flattened companyDto), publications (verbatim
    publicationDto list), current_page, total_pages, has_reached_results_limit,
    is_restricted_search} (pure function)."""
    rows, pubs = [], []
    for d in sr.get("elasticSearchDtos") or []:
        et = d.get("entityType")
        if et == "1-company":
            c = dict(d.get("companyDto") or {})
            rf = c.get("registerCourt") or {}
            row = dict(c)
            row["register_court_code"] = rf.get("courtCode")
            row["register_court_name"] = rf.get("name")
            row["register_type"] = (c.get("registerType") or {}).get("name") \
                if isinstance(c.get("registerType"), dict) else c.get("registerType")
            row["legal_form_id"] = (c.get("legalForm") or {}).get("id") \
                if isinstance(c.get("legalForm"), dict) else c.get("legalForm")
            row["state_name"] = (c.get("state") or {}).get("name") \
                if isinstance(c.get("state"), dict) else c.get("state")
            row["company_history_len"] = len(c.get("companyHistory") or [])
            rows.append(row)
        elif et == "2-publication":
            pubs.append(dict(d.get("publicationDto") or {}))
    return {"rows": rows, "publications": pubs,
            "current_page": sr.get("currentPage"), "total_pages": sr.get("totalPages"),
            "has_reached_results_limit": sr.get("hasReachedResultsLimit"),
            "is_restricted_search": sr.get("isRestrictedSearch")}


def _extract_search_results(text):
    """RSC text/x-component stream → the embedded `searchResults` JSON (string-aware brace
    match; the stream is line-protocol text with escaped JSON, not a pure JSON document)."""
    i = text.find('"searchResults":')
    if i < 0:
        return None
    j = text.index("{", i + len('"searchResults":'))
    depth, k, in_str, esc = 0, j, False, False
    while k < len(text):
        c = text[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    import json as _json
                    return _json.loads(text[j:k + 1])
        k += 1
    return None


def _search_token(cache, no_cache):
    """→ the 231-char search token (cached 45min; upstream validity 1h)."""
    from ..transport import call_provider
    r = call_provider(provider, "token", {}, cache=cache, no_cache=no_cache)
    d = r["data"]
    token = (d or {}).get("token") if isinstance(d, dict) else None
    if not token:
        raise SdkError("upstream_unavailable", provider="de_register",
                       detail="search-token endpoint returned no token (a 423/451 here is the "
                              "geo/IP gate, not an auth failure — the upstream page shape may have changed)")
    return token


def search_raw(name=None, *, exact=True, q=None, offset=0, cache=None, no_cache=False):
    """→ rows_from_upstream(...) + params + _meta. name = the exact channel
    (companyName + companyNameExactMatch=true); q = the fuzzy channel (companySearchTerm);
    exactly one required. offset = `from` row offset (60/page upstream)."""
    from ..transport import call_provider

    nm = str(name or "").strip() or None
    fuzzy = str(q or "").strip() or None
    if not nm and not fuzzy:
        raise SdkError("usage_error", provider="de_register",
                       detail="search requires name (exact channel) or q (fuzzy companySearchTerm)")
    if nm and fuzzy:
        raise SdkError("usage_error", provider="de_register",
                       detail="name (exact) and q (fuzzy) are mutually exclusive — give only one")
    try:
        off = int(offset) if offset is not None else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="de_register",
                       detail=f"offset must be an integer >=0 (rows), got {offset!r}")
    if off < 0:
        raise SdkError("usage_error", provider="de_register",
                       detail=f"offset must be >=0, got {off}")
    params = {"from": off} if off else {}
    if nm:
        params["companyName"] = nm
        if exact:
            params["companyNameExactMatch"] = "true"
    else:
        params["companySearchTerm"] = fuzzy
    params["searchToken"] = _search_token(cache, no_cache)
    r = call_provider(provider, "search", params, cache=None, no_cache=True,
                      extra_headers={"RSC": "1", "Accept": "text/x-component"})
    text = r["data"]
    if not isinstance(text, str):
        raise SdkError("upstream_unavailable", provider="de_register",
                       detail="search answered with a non-text payload (the RSC stream contract may have changed)")
    sr = _extract_search_results(text)
    if sr is None:
        raise SdkError("upstream_unavailable", provider="de_register",
                       detail='no "searchResults" object in the RSC stream — the query may have been '
                              "rejected silently (token expired mid-flight is possible; retry refreshes it)")
    out = rows_from_upstream(sr)
    out["params"] = {k: v for k, v in params.items() if k != "searchToken"}
    out["_meta"] = r
    return out
