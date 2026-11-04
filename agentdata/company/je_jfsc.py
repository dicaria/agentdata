"""je_jfsc — Jersey JFSC regulated-entities register (www.jerseyfsc.org Umbraco search API; keyless POST).

One face (0.3.33; probed 2026-11-04, tmp/probe-company-0333/; research volume je-jfsc-registry,
offshore Channel-Islands regulated-registers batch):

  je_jfsc_regulated_entities — POST /umbraco/api/RegulatedEntitiesSearch/GetResults with the JSON
  body {"Keyword": k, "PageSize": n, "PageNumber": m, "Refiners": []}. Envelope keys:
  NoResults / PageNumber / Pages / Refiners / Results / SuggestedTerm. **NoResults is a RESULT
  COUNT, not a zero flag** (pinned live: Keyword "Barclays" → NoResults=1 with exactly one row,
  Barclays Bank plc, Jersey Branch — the total lives in a key that reads like an error state);
  zero hits is NoResults=0 with an empty Results list, a legal answer.
  The row is a site-search row, not a register record: Title = entity name, Url =
  /industry/regulated-entities/entity/<id> (the register's own entity page — the numeric tail is
  the entity id), and Properties[0] (Name="LawSection") carries the official licence text
  verbatim: "Banking (DC) (ref. DC0076), Fund Services Business (FSB) (ref. FSB2190), …" — parsed
  into law/code/ref triplets (the raw text is kept alongside; the parse is a best-effort regex
  over the stable "Name (CODE) (ref. REF)" shape).
  **Refiners are not exposed** (rasff precedent): the facet option values are space-joined
  lowercase keys ("bankingdc fundservicesbusinessfsb …") — a lossy spelling that would break on
  any upstream reword; not a stable contract.
  Licence (gate 6): the JFSC privacy policy acknowledges the public-register information may be
  used by third parties who access it — no reuse restriction found on the keyless public face.

keyword is REQUIRED: the empty-keyword POST is the register's full enumeration (unpinned —
harvest-side territory, not a face default). PageSize 1-100 is our politeness cap (upstream
publishes no maximum; PageSize 5 measured). PageNumber is 1-based; has_more = PageNumber < Pages.

Channel: plain POST JSON, no key, no CAPTCHA, no published rate window → polite 0.5 rps /
burst 2 (registry-search family posture). TTL 24h (the register moves slowly; the search is the
register page's own backing store).
"""
import re

from ..errors import SdkError

provider = {
    "id": "je_jfsc",
    "baseUrl": "https://www.jerseyfsc.org",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/umbraco/api/RegulatedEntitiesSearch/GetResults", "method": "POST",
                   "idempotent": True, "timeout": 40.0},
    },
    "ttl": {"search": 24 * 3600},
}

# the official licence text shape: "Banking (DC) (ref. DC0076), Fund Services Business (FSB) (ref. FSB2190)"
_LAW_RE = re.compile(r"([^(,]+?)\s*\(([A-Z]{2,6})\)\s*\(ref\.\s*([A-Za-z0-9]+)\)")
_ENTITY_ID_RE = re.compile(r"/(\d+)/?$")

_PAGE_SIZE_CAP = 100  # our politeness cap; the upstream publishes no maximum for PageSize


def _norm_keyword(keyword):
    v = str(keyword or "").strip()
    if not v:
        raise SdkError("usage_error", provider="je_jfsc",
                       detail="je_jfsc_regulated_entities requires keyword (entity name). An empty "
                              "keyword is refused locally — upstream it would answer the whole "
                              "register's enumeration (unpinned; harvest-side, not a face default)")
    return v


def _norm_paging(page_size, page):
    size = 20 if page_size in (None, "") else int(page_size)
    pg = 1 if page in (None, "") else int(page)
    if size < 1 or size > _PAGE_SIZE_CAP:
        raise SdkError("usage_error", provider="je_jfsc",
                       detail=f"page_size must be 1-{_PAGE_SIZE_CAP} (our politeness cap; the "
                              f"upstream publishes no maximum), got {page_size!r}")
    if pg < 1:
        raise SdkError("usage_error", provider="je_jfsc",
                       detail=f"page must be a 1-based page number (upstream param: PageNumber), got {page!r}")
    return size, pg


def _map_row(raw):
    """One site-search row → the flat row: the entity id is the numeric tail of the register Url;
    the licence text is kept raw AND parsed into law/code/ref triplets (the parse is best-effort —
    the raw text is the contract, the triplets the convenience)."""
    url = raw.get("Url") or None
    m = _ENTITY_ID_RE.search(str(url or ""))
    props = {p.get("Name"): p.get("Value") for p in (raw.get("Properties") or [])
             if isinstance(p, dict)}
    law_text = props.get("LawSection") or None
    return {
        "entity_id": m.group(1) if m else None,
        "name": raw.get("Title") or None,
        "type": raw.get("Type") or None,
        "url": f"https://www.jerseyfsc.org{url}" if url else None,
        "law_section_text": law_text,
        "law_sections": [{"law": a.strip(), "code": b, "ref": c}
                         for a, b, c in _LAW_RE.findall(law_text or "")],
        "rank": raw.get("Rank"),
    }


def _int_or_none(v):
    return int(v) if isinstance(v, (int, float)) else None


def regulated_entities_raw(keyword, *, page_size=None, page=None, cache=None, no_cache=False):
    """-> {rows, total, pages, page, has_more, suggested_term, params, _meta}; total is the
    envelope's NoResults — **a result count, not a zero flag** (Barclays → NoResults=1)."""
    from ..transport import call_provider

    k = _norm_keyword(keyword)
    size, pg = _norm_paging(page_size, page)
    r = call_provider(provider, "search",
                      {"Keyword": k, "PageSize": size, "PageNumber": pg, "Refiners": []},
                      cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    rows = [_map_row(x) for x in (doc.get("Results") or []) if isinstance(x, dict)]
    total, pages, page_no = (_int_or_none(doc.get(k_)) for k_ in ("NoResults", "Pages", "PageNumber"))
    return {
        "rows": rows,
        "total": total,                      # NoResults on the wire — a count, not a zero flag
        "pages": pages,
        "page": page_no if page_no is not None else pg,
        "has_more": bool(pages is not None and page_no is not None and page_no < pages),
        "suggested_term": doc.get("SuggestedTerm") or None,
        "params": {"Keyword": k, "PageSize": size, "PageNumber": pg},
        "_meta": r,
    }
