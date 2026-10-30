"""federalregister — Federal Register API provider (federalregister.gov; keyless).

Federal regulations/notices full-text search over the daily release stream (rules, proposed rules, notices).
Shape verified 2026-10-23:
GET /api/v1/documents.json?conditions[term]=<q>&conditions[publication_date][gte|lte]=YYYY-MM-DD
  &per_page=N&page=1&order=newest|relevance
  → {count, total_pages, next_page_url, results:[{document_number, type:RULE|PRORULE|NOTICE|PRESDOCU,
     title, abstract, publication_date, agencies:[{name,raw_name,url}], citation, comments_close_on, …}]}
— omitting fields[] returns every field (a few KB per record; no problem observed at per_page 50 this round).
GET /api/v1/documents/{document_number}.json → a single record with raw_text_url/body_html_url (full-text anchors,
used by the corpus batch line to fetch documents).
The date range must carry both ends to actually filter (the EDGAR FTS trap of the same kind: a single end is
silently ignored — this provider always sends both ends).
TTL: search 24h (daily release stream) / single record 30 days; polite rate 1 rps (official no-key guidance ≤5,
we take the conservative value).
"""
import re
from datetime import date

from ..errors import SdkError

provider = {
    "id": "federalregister",
    "baseUrl": "https://www.federalregister.gov",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "search": {"path": "/api/v1/documents.json"},     # params: conditions[term], conditions[publication_date][gte/lte], per_page, page, order
        "document": {"path": "/api/v1/documents/{doc}.json"},  # doc = document_number (e.g. 2026-12345)
    },
    "ttl": {"search": 24 * 3600, "document": 30 * 86400},
}

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 0.2.9 audit (2026-10-28): order has a fourth official value executive_order_number (listed in the official
# documentation.json, verified 200 in a live probe) — the old whitelist missed it and blocked it locally by mistake.
# The type closed set has four values (official enumeration); **an invalid type silently returns
# 0 rows upstream** (conditions[type][]=BOGUS → 200 count=0, no 400 — a false-negative trap), so it is blocked
# locally here (osv/sectors have the same shape).
ORDERS = ("relevance", "newest", "oldest", "executive_order_number")
DOC_TYPES = ("RULE", "PRORULE", "NOTICE", "PRESDOCU")


def docs_from_upstream(data, size):
    """Upstream response → hit rows (pure function, offline-testable)."""
    rows = [{
        "document_number": d.get("document_number"),     # stable key (used by the corpus batch line to fetch full text)
        "title": d.get("title"),
        "type": d.get("type"),                           # RULE|PRORULE|NOTICE|PRESDOCU
        "publication_date": d.get("publication_date"),
        "abstract": d.get("abstract") or None,           # upstream often returns an empty string — normalize to None
        "citation": d.get("citation"),
        "agencies": [a.get("name") or a.get("raw_name") for a in (d.get("agencies") or [])
                     if a.get("name") or a.get("raw_name")],
        "docket_ids": d.get("docket_ids") or [],
        "comments_close_on": d.get("comments_close_on") or None,
        "url": d.get("html_url"),
    } for d in ((data or {}).get("results") or [])]
    return {
        "rows": rows, "count": len(rows),
        "limit_applied": size,
        "total": data.get("count") if isinstance(data, dict) and isinstance(data.get("count"), int) else None,
        "total_pages": data.get("total_pages") if isinstance(data, dict) and isinstance(data.get("total_pages"), int) else None,
    }


def search_docs(q=None, *, startdt=None, enddt=None, order="relevance", page=1, limit=20,
                cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, total, total_pages, _meta}; full-text search hits (q goes through
    conditions[term] at full-text level).
    The date range requires startdt/enddt as a pair (a single end is silently ignored upstream — reject it
    outright rather than pass it silently)."""
    from ..transport import call_provider

    term = str(q or "").strip()
    if not term:
        raise SdkError("usage_error", provider="federalregister",
                       detail="search_docs requires q (quote phrases for exact-phrase matching)")
    if (startdt is None) != (enddt is None):
        raise SdkError("usage_error", provider="federalregister",
                       detail="the date range requires startdt and enddt as a pair (a single end is silently ignored upstream)")
    for d in (startdt, enddt):
        if d is not None and not _DATE.match(d):
            raise SdkError("usage_error", provider="federalregister", detail=f"date must be YYYY-MM-DD: {d}")
    if order not in ORDERS:
        raise SdkError("usage_error", provider="federalregister", detail=f"order must be one of {'|'.join(ORDERS)}, got \"{order}\"")
    size = min(max(1, int(limit or 20)), 50)  # upstream per_page ceiling is 1000 — our polite cap is 50 (realtime face)
    params = {"conditions[term]": term, "per_page": size, "page": max(1, int(page or 1)), "order": order}
    if startdt:
        params["conditions[publication_date][gte]"] = startdt
        params["conditions[publication_date][lte]"] = enddt
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    return {**docs_from_upstream(r["data"], size), "_meta": r}


DATA_START = "1994-01-01"  # Federal Register data start (1994+ daily release stream) — the default when one end is missing


def search_raw(q, *, startdt=None, enddt=None, order="relevance", page=1, limit=20,
               doc_type=None, agencies=None, cfr_title=None, cfr_part=None,
               cache=None, no_cache=False):
    """Flat-panel low-level face + 0.2.9 audit param additions: conditions[term]/[publication_date][gte|lte]/
    [type][]/[agencies][]/[cfr][title|part]/per_page/page/order go through with verbatim names.

    → {rows[], count, limit_applied, total, total_pages, date_range, params, _meta}.
    Missing end is auto-completed (same semantics as the full-text face): giving either end completes the other
    (missing startdt → 1994-01-01, missing enddt → today), after which both ends are always sent — a single end is
    silently ignored upstream (verified 2026-10-23). limit polite cap 50 (upstream per_page ceiling 1000).
    0.2.9 new params (reconciled against the official documentation.json and probed live 2026-10-28):
    - order's fourth value executive_order_number (listed officially, verified 200) — the old whitelist's false block is fixed.
    - doc_type→conditions[type][]: the closed set of four values RULE/PRORULE/NOTICE/PRESDOCU is validated locally —
      **an invalid value silently returns 0 rows upstream** (type=BOGUS → 200 count=0, no 400 — a false-negative trap);
      valid values really filter (asbestos+PRORULE=426 vs 2551 unfiltered, the response description says
      "of type Proposed Rule"). Single value/param (upstream array members need repeated keys, the transport dict does
      not support repeated keys — the multi-value OR is not exposed for now, recorded).
    - agencies→conditions[agencies][]: agency slug (value domain from GET /api/v1/agencies; environmental-protection-agency
      verified working, the description says "from Environmental Protection Agency").
    - cfr_title/cfr_part→conditions[cfr][title]/[part]: code-anchored search (part may be a range form "763" or "1-50"
      per the official wording, and the official text states that part requires the CFR title — this face rejects cp
      without ct; title=40&part=763 verified count=33, all Rules — the TSCA section; cfr alone (no term) also works,
      while q is required here because that is the search-face semantics, not an upstream restriction)."""
    from ..transport import call_provider

    term = str(q or "").strip()
    if not term:
        raise SdkError("usage_error", provider="federalregister",
                       detail="search_raw requires q (quote phrases for exact-phrase matching)")
    for d in (startdt, enddt):
        if d is not None and not _DATE.match(d):
            raise SdkError("usage_error", provider="federalregister", detail=f"date must be YYYY-MM-DD: {d}")
    if order not in ORDERS:
        raise SdkError("usage_error", provider="federalregister",
                       detail=f"order must be one of {'|'.join(ORDERS)}, got \"{order}\"")
    dt = str(doc_type or "").strip() or None
    if dt is not None and dt not in DOC_TYPES:
        raise SdkError("usage_error", provider="federalregister",
                       detail=f"doc_type \"{dt}\" is not in the closed set ({'|'.join(DOC_TYPES)}; "
                              "invalid values silently return 0 rows upstream — the false-negative guard lives here; "
                              "official enumeration documentation.json reconciled 2026-10-28)")
    ag = str(agencies or "").strip() or None
    ct = str(cfr_title or "").strip() or None
    cp = str(cfr_part or "").strip() or None
    if cp and not ct:
        raise SdkError("usage_error", provider="federalregister",
                       detail="cfr_part must be used together with cfr_title (official semantics: part requires the title anchor)")
    size = min(max(1, int(limit or 20)), 50)  # polite cap 50 (upstream ceiling 1000) — realtime single-query face
    dr = None
    if startdt or enddt:
        s = startdt or DATA_START
        e = enddt or date.today().isoformat()
        dr = {"startdt": s, "enddt": e}
    params = {"conditions[term]": term, "per_page": size, "page": max(1, int(page or 1)), "order": order}
    if dr:
        params["conditions[publication_date][gte]"] = dr["startdt"]
        params["conditions[publication_date][lte]"] = dr["enddt"]
    if dt:
        params["conditions[type][]"] = dt
    if ag:
        params["conditions[agencies][]"] = ag
    if ct:
        params["conditions[cfr][title]"] = ct
    if cp:
        params["conditions[cfr][part]"] = cp
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    return {**docs_from_upstream(r["data"], size), "date_range": dr, "params": params, "_meta": r}


def get_document(doc, *, cache=None, no_cache=False):
    """→ a single record with all fields (including the raw_text_url / body_html_url full-text anchors)."""
    from ..transport import call_provider

    d = str(doc or "").strip()
    if not re.fullmatch(r"\d{2,4}-\d{1,6}", d):
        raise SdkError("usage_error", provider="federalregister",
                       detail=f"not in document_number form (e.g. 2026-12345): {doc}")
    r = call_provider(provider, "document", {"doc": d}, cache=cache, no_cache=no_cache)
    x = r["data"] or {}
    return {
        "document_number": x.get("document_number") or d, "title": x.get("title"), "type": x.get("type"),
        "publication_date": x.get("publication_date"), "abstract": x.get("abstract") or None,
        "citation": x.get("citation"),
        "agencies": [a.get("name") or a.get("raw_name") for a in (x.get("agencies") or [])
                     if a.get("name") or a.get("raw_name")],
        "docket_ids": x.get("docket_ids") or [],
        "body_html_url": x.get("body_html_url"), "raw_text_url": x.get("raw_text_url"),
        "comments_close_on": x.get("comments_close_on") or None, "url": x.get("html_url"),
        "_meta": r,
    }
