"""nl_rechtspraak — Netherlands judiciary published-case search (uitspraken.rechtspraak.nl, keyless).

legal judgment-corpus face (0.3.55; register 2026-11-02 break-in, re-verified live 2026-11-12,
probes tmp/probe-sdk-0355/). Shape measured 2026-11-12:
POST /api/zoek with a PascalCase body where EVERY key must ride — missing Instanties/Datum*/
Advanced/CorrelationId any one, an empty SearchTerms, a non-zt0 Field value, or a non-empty
Contentsoorten array is answered by the Angular mededeling error page (HTTP 200 + HTML, not JSON —
the IIS-302 of the 2026-11-02 notes now lands as an SPA route). The body the face assembles is the
one verified shape; response = {ResultCount, Results[], FacetCounts?} with ResultCount 478,767 on
the published corpus ("verzoek", zt0). Results rows carry 17 keys: Titel (the human case title) /
TitelEmphasis (THE ECLI — "ECLI:NL:RBGEL:2026:2322") / DeeplinkUrl (?id=ECLI:…) / InterneUrl /
Uitspraakdatum+Publicatiedatum (DD-MM-YYYY text) / GerechtelijkProductType (uitspraak|conclusie —
conclusie = the advocate-general opinion stream, 18k rows) / Tekstfragment / Rechtsgebieden /
Proceduresoorten / Vindplaatsen / Publicatiestatus / IsInactief / RelatieVerwijzingen.
Sort orders verified live: Relevance / PublicatieDatumDesc / UitspraakDatumDesc (head 11-11-2026) /
UitspraakDatumAsc (head 19-03-1847 — the register reaches the 1840s). PageSize 150 answered 150
rows (no 100 clamp observed; the face caps at 200 locally). StartRow offset paging works.
Full texts: GET /api/pdfdownload/{ECLI with colons → underscores} answers application/pdf
(%PDF-1.7 verified); the face derives pdf_url per row without fetching (binary stays a batch-
pipeline concern). The old OAI data.rechtspraak.nl face stays retired (404).
TTL: 24h; polite tier 0.5 rps (no published quota).
"""
from ..errors import SdkError

provider = {
    "id": "nl_rechtspraak",
    "baseUrl": "https://uitspraken.rechtspraak.nl",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "zoek": {"path": "/api/zoek", "method": "POST", "idempotent": True, "timeoutMs": 45000},
    },
    "ttl": {"zoek": 24 * 3600},
}

_SORT_ORDERS = ("Relevance", "PublicatieDatumDesc", "UitspraakDatumDesc", "UitspraakDatumAsc")


def rows_from_upstream(data):
    """ zoek response → case rows (pure function). TitelEmphasis is the ECLI; pdf_url is derived
    from it (colons → underscores) without fetching — the PDF endpoint is the verified full-text
    channel, details pages are 3.9KB SPA shells (never scrape those)."""
    rows = []
    for r in (data or {}).get("Results") or []:
        ecli = r.get("TitelEmphasis") or None
        row = dict(r)
        row["ecli"] = ecli
        row["pdf_url"] = ("https://uitspraken.rechtspraak.nl/api/pdfdownload/" + ecli.replace(":", "_")) \
            if (isinstance(ecli, str) and ecli.startswith("ECLI:")) else None
        rows.append(row)
    return rows, (data or {}).get("ResultCount")


def zoek_raw(q=None, *, sort_order="Relevance", start_row=0, page_size=20,
             facets=False, cache=None, no_cache=False):
    """→ {rows, total, start_row, page_size_applied, sort_order, body, _meta} (server-side search;
    the full PascalCase body is assembled here — the one shape the upstream accepts).

    q = the free search term (required; an empty SearchTerms array is rejected by the upstream);
    sort_order = Relevance|PublicatieDatumDesc|UitspraakDatumDesc|UitspraakDatumAsc (all four
    verified live); start_row offset paging; page_size 1-200 local politeness cap (150 verified
    upstream, no clamp observed); facets = ShouldCountFacets (the six-axis FacetCounts —
    Contentsoorten/Rechtsgebieden/Instanties/Proceduresoorten/DatumPublicatie/DatumUitspraak —
    rides the same call instead of a second round trip)."""
    from ..transport import call_provider

    qq = str(q or "").strip()
    if not qq:
        raise SdkError("usage_error", provider="nl_rechtspraak",
                       detail="q is required (an empty SearchTerms array is rejected by the upstream "
                              "with the mededeling error page — the empty-corpus walk is a batch concern, not a face)")
    if sort_order not in _SORT_ORDERS:
        raise SdkError("usage_error", provider="nl_rechtspraak",
                       detail=f"sort_order must be one of {'|'.join(_SORT_ORDERS)}, got '{sort_order}'")
    try:
        size = int(page_size) if page_size is not None else 20
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="nl_rechtspraak",
                       detail=f"page_size must be an integer 1-200, got {page_size!r}")
    if not 1 <= size <= 200:
        raise SdkError("usage_error", provider="nl_rechtspraak",
                       detail=f"page_size must be 1-200 (local politeness cap; 150 verified upstream), got '{page_size}'")
    try:
        start = int(start_row) if start_row is not None else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="nl_rechtspraak",
                       detail=f"start_row must be an integer >=0, got {start_row!r}")
    if start < 0:
        raise SdkError("usage_error", provider="nl_rechtspraak",
                       detail=f"start_row must be ≥0, got '{start_row}'")
    body = {
        "StartRow": start, "PageSize": size, "ShouldReturnHighlights": False,
        "ShouldCountFacets": bool(facets), "SortOrder": sort_order,
        "SearchTerms": [{"Term": qq, "Field": "zt0"}],
        "Contentsoorten": [], "Rechtsgebieden": [], "Instanties": [],
        "DatumPublicatie": [], "DatumUitspraak": [],
        "Advanced": {"PublicatieStatus": "AlleenGepubliceerd"},
        "CorrelationId": "", "Proceduresoorten": [],
    }
    # CorrelationId is client telemetry the upstream wants present (a missing key = the mededeling
    # error page) but does not correlate — a per-call uuid would shred the cache key, so it is a
    # deterministic 32-hex digest of the request itself (same shape, stable key).
    import hashlib as _hashlib
    import json as _json
    body["CorrelationId"] = _hashlib.md5(
        _json.dumps({k: v for k, v in body.items() if k != "CorrelationId"},
                    ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    # POST read semantics: the params dict IS the wire body (call_provider routes non-path
    # parameters of a method=POST op into the JSON body) — the full PascalCase shape rides along
    r = call_provider(provider, "zoek", body, cache=cache, no_cache=no_cache)
    rows, total = rows_from_upstream(r["data"])
    return {"rows": rows, "total": total, "start_row": start, "page_size_applied": size,
            "sort_order": sort_order, "q": qq, "facets": (r["data"] or {}).get("FacetCounts"),
            "body": body, "_meta": r}
