"""gb_tna_caselaw — UK National Archives caselaw library provider (caselaw.nationalarchives.gov.uk; keyless).

The legal register's judgment line P0 (roadmapped 2026-10-29; born 0.3.8, ISO-prefixed 0.3.13, Englished in the
0.3.14 collection round). Shapes verified by first-hand live probing 2026-10-29 (tmp/probe-tna/):
GET /atom.xml?party=&judge=&court=&tribunal=&query=&order=&page=&per_page=&minimum_availability=
  → Atom feed (official OpenAPI: the feed header's rel=service-desc links nationalarchives/ds-find-caselaw-docs)
  — entries carry tna:uri (the machine-stable document URI) / tna:identifier (ukncn = the neutral-citation
    human-readable key + fclid, a dual key) / tna:contenthash (body SHA256, cross-format change detection) /
    author=name = the court name; link rel=last = total pages.
  per_page defaults to 50 (polite tier 1-50); order enum ±date/±updated/±transformation;
  court/tribunal are arrays with explode=true (repeated keys); minimum_availability enum metadata/document/full-text.
GET /{document_uri}/data.xml → Akoma Ntoso (LegalDocML):
  meta/proprietary = court/year/number/cite/caseNumber/hash; FRBRWork = FRBRname case name + FRBRdate handed-down date;
  header/<party as="#claimant|#defendant" refersTo="#eId"> = the official party→role edge (companies + individuals);
  judgmentBody = the body (~32k chars per document).
Two document-URI generations coexist (per the official contract, never parse attributes out of the URI): before
2025-04 court/year/seq (with slashes), after that d-<uuid>; identifiers additionally carry an fclid slug form
(tna.xxxx) — all three forms are accepted by the judgment face.
Rate: official 1000 req/rolling 5 min (≈3.3 rps) — polite tier 0.5 rps.
**The licence gate (first case of keyless-but-licence)**: the Open Justice Licence allows commercial reuse and
expressly forbids bulk computational analysis (free on application) — this face is directed search /
single-document reading (rolling-monitor compliant); do not enumerate-harvest the corpus.
TTL: search 24h (the feed drifts at daily cadence) / judgment 7 days (judgments are slow-moving; the contenthash
detects text changes).
"""
import re
import xml.etree.ElementTree as ET

from ..errors import SdkError

_ATOM = "{http://www.w3.org/2005/Atom}"
_TNA = "{https://caselaw.nationalarchives.gov.uk}"
_AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"

_ORDERS = ("date", "-date", "updated", "-updated", "transformation", "-transformation")
_AVAILABILITY = ("metadata", "document", "full-text")

provider = {
    "id": "gb_tna_caselaw",
    "baseUrl": "https://caselaw.nationalarchives.gov.uk",
    "rate": {"rps": 0.5, "burst": 1},
    "ops": {
        "search": {"path": "/atom.xml", "accept": "text"},   # params: query/court/tribunal/party/judge/order/page/per_page/minimum_availability
        "judgment": {"path": "/{document_uri}/data.xml", "accept": "text",
                     "path_safe": "/"},                       # document_uri contains slashes (ewhc/admin/2026/2298) — keep / in path params
    },
    "ttl": {"search": 24 * 3600, "judgment": 7 * 86400},
}


def _as_list(v):
    """court/tribunal explode arrays: a str is treated as a single element (a CLI --court repeat builds a list passed straight through)."""
    if v is None:
        return None
    return v if isinstance(v, (list, tuple)) else [v]


def entries_from_atom(text):
    """Upstream Atom feed → judgment rows + feed-level ledger (pure function, offline-testable)."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise SdkError("upstream_error", provider="gb_tna_caselaw",
                       detail=f"atom feed XML parse failed: {e}")
    if root.tag != _ATOM + "feed":
        raise SdkError("upstream_error", provider="gb_tna_caselaw",
                       detail=f"unexpected root element {root.tag} (expected an Atom feed)")

    def _page(href):
        m = re.search(r"[?&]page=(\d+)", href or "")
        return int(m.group(1)) if m else None

    total_pages, feed_updated, license_url = None, None, None
    for el in root:
        if el.tag == _ATOM + "link" and el.get("rel") == "last":
            total_pages = _page(el.get("href"))
        elif el.tag == _ATOM + "updated":
            feed_updated = (el.text or "").strip() or None
        elif el.tag == _ATOM + "rights":
            license_url = (el.text or "").strip() or None

    rows = []
    for e in root.findall(_ATOM + "entry"):
        neutral_citation = fcid = None
        for ident in e.findall(_TNA + "identifier"):
            if ident.get("type") == "ukncn":
                neutral_citation = (ident.text or "").strip() or None
            elif ident.get("type") == "fclid":
                fcid = (ident.text or "").strip() or None
        links = {((l.get("rel") or ""), (l.get("type") or "")): l.get("href") for l in e.findall(_ATOM + "link")}
        rows.append({
            "uri": next((t.text.strip() for t in e.findall(_TNA + "uri") if t.text), None),
            "neutral_citation": neutral_citation,          # ukncn human-readable official key ([2026] EWHC 2298 (Admin))
            "fcid": fcid,                                   # Find Case Law Identifier (source of the tna.xxxx slug)
            "title": (e.findtext(_ATOM + "title") or "").strip() or None,   # case name = the party string
            "court": (e.findtext(_ATOM + "author/" + _ATOM + "name") or "").strip() or None,
            "published": e.findtext(_ATOM + "published"),   # handed-down date
            "updated": e.findtext(_ATOM + "updated"),       # XML last-updated (includes markup touch-ups)
            "contenthash": next((t.text.strip() for t in e.findall(_TNA + "contenthash") if t.text), None),
            "html_url": links.get(("alternate", "")),
            "data_url": links.get(("alternate", "application/akn+xml")),
            "pdf_url": links.get(("alternate", "application/pdf")),
        })
    return {"rows": rows, "count": len(rows), "total_pages": total_pages,
            "feed_updated": feed_updated, "license": license_url}


def search_raw(query=None, *, court=None, tribunal=None, party=None, judge=None,
               order=None, page=1, per_page=50, minimum_availability=None,
               cache=None, no_cache=False):
    """Flat-panel plumbing: eight params under their upstream names, straight through (GET /atom.xml).

    → {rows[], count, page, per_page, total_pages, feed_updated, params, _meta}.
    party/judge = party/judge names with whole-word matching; court/tribunal = court codes (repeatable, explode);
    query = full-text search; total_pages comes straight from the feed header's link rel=last.
    The licence forbids bulk — a directed-search face."""
    from ..transport import call_provider

    params = {}
    if query is not None and str(query).strip():
        params["query"] = str(query).strip()
    for k, v in (("party", party), ("judge", judge)):
        if v is not None and str(v).strip():
            params[k] = str(v).strip()
    for k, v in (("court", _as_list(court)), ("tribunal", _as_list(tribunal))):
        if v:
            params[k] = [str(x).strip() for x in v if str(x).strip()]
            if not params[k]:
                del params[k]
    if order is not None:
        if order not in _ORDERS:
            raise SdkError("usage_error", provider="gb_tna_caselaw",
                           detail=f"order must be one of {'/'.join(_ORDERS)}, got {order!r}")
        params["order"] = order
    pg = int(page) if page is not None else 1
    if pg < 1:
        raise SdkError("usage_error", provider="gb_tna_caselaw", detail=f"page must be >=1, got {page!r}")
    size = int(per_page) if per_page is not None else 50
    if not 1 <= size <= 50:
        raise SdkError("usage_error", provider="gb_tna_caselaw",
                       detail=f"per_page must be 1-50 (polite tier = the upstream default page size; the licence "
                              f"forbids bulk — do not pull larger pages), got {per_page!r}")
    params["page"], params["per_page"] = pg, size
    if minimum_availability is not None:
        if minimum_availability not in _AVAILABILITY:
            raise SdkError("usage_error", provider="gb_tna_caselaw",
                           detail=f"minimum_availability must be one of {'/'.join(_AVAILABILITY)}, got "
                                  f"{minimum_availability!r}")
        params["minimum_availability"] = minimum_availability
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    out = entries_from_atom(r["data"])
    return {**out, "page": pg, "per_page": size, "params": params, "_meta": r}


_URI_CHARS = re.compile(r"^[a-z0-9][a-z0-9/.\-]*$")


def _clean_uri(document_uri):
    s = str(document_uri or "").strip()
    # tolerance: a pasted full URL (…/<uri> or …/<uri>/data.xml) is shelled; all three forms accepted —
    # the tna.xxxx slug, the modern d-uuid, and the legacy court/year/seq
    for pre in ("https://caselaw.nationalarchives.gov.uk/", "http://caselaw.nationalarchives.gov.uk/", "/"):
        if s.startswith(pre):
            s = s[len(pre):]
    if s.endswith("/data.xml"):
        s = s[: -len("/data.xml")]
    s = s.strip("/")
    if not s or not _URI_CHARS.match(s):
        raise SdkError("usage_error", provider="gb_tna_caselaw",
                       detail=f"document_uri must be a document URI (legacy ewhc/admin/2026/2298, modern d-<uuid>, "
                              f"or tna.<fclid>; the search rows' uri/neutral_citation slugs carry them verbatim): "
                              f"{document_uri}")
    return s


def _txt(el):
    return " ".join((el.text or "").split()) if el is not None and el.text else None


def judgment_from_akn(text):
    """Akoma Ntoso data.xml → a single structured judgment dossier (pure function, offline-testable)."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise SdkError("upstream_error", provider="gb_tna_caselaw",
                       detail=f"judgment XML parse failed: {e}")
    j = root.find(_AKN + "judgment")   # an Element with no children is falsy — always test `is not None`, never an `or` chain
    if j is None:
        j = root.find(_AKN + "doc")
    if j is None:
        raise SdkError("upstream_error", provider="gb_tna_caselaw",
                       detail=f"unexpected root structure (expected an Akoma Ntoso judgment, got {root.tag})")
    prop = {}
    p = j.find(_AKN + "meta/" + _AKN + "proprietary")
    if p is not None:
        for el in p:
            tag = el.tag.split("}")[-1]
            if tag in ("court", "year", "number", "cite", "caseNumber", "hash"):
                prop[tag] = (el.text or "").strip() or None
    frbr = j.find(_AKN + "meta/" + _AKN + "identification/" + _AKN + "FRBRWork")
    name = date = frbr_uri = None
    if frbr is not None:
        n = frbr.find(_AKN + "FRBRname")          # the case name lives in the value attribute, not element text (Akn attribute-bearing convention)
        name = n.get("value") if n is not None else None
        d = frbr.find(_AKN + "FRBRdate")
        date = d.get("date") if d is not None else None
        this = frbr.find(_AKN + "FRBRthis")
        frbr_uri = this.get("value") if this is not None else None
    # the official party→role edge: header/<party as="#claimant" refersTo="#eId">NAME</party>
    parties = []
    hdr = j.find(_AKN + "header")
    if hdr is not None:
        for pty in hdr.iter(_AKN + "party"):
            parties.append({"name": _txt(pty),
                            "role": ((pty.get("as") or "").lstrip("#") or None)})
    judges = []
    for jd in (hdr.iter(_AKN + "judge") if hdr is not None else []):
        nm = _txt(jd)
        if nm and nm not in judges:
            judges.append(nm)
    body = j.find(_AKN + "judgmentBody")
    text_out = " ".join(body.itertext()).strip() if body is not None else None
    return {
        "neutral_citation": prop.get("cite"),
        "court_code": prop.get("court"),                    # EWHC-KBD-Admin (a proprietary code)
        "case_number": prop.get("caseNumber"),              # docket number (e.g. AC-2024-LON-003318)
        "title": name,                                      # FRBRname = the case name (the party string)
        "date": date,                                       # FRBRdate = handed-down date
        "judges": judges,
        "parties": parties,                                 # [{name, role}] the official edge for company + individual parties
        "contenthash": prop.get("hash"),
        "frbr_uri": frbr_uri,                               # canonical document URI (id/ form)
        "text": text_out,                                   # judgment body (plain-text extraction)
        "text_length": len(text_out) if text_out else 0,
    }


def judgment_raw(document_uri, *, cache=None, no_cache=False):
    """→ a single judgment's full dossier (Akoma Ntoso structured: citation/court/party-role edges/judges/body)."""
    from ..transport import call_provider

    s = _clean_uri(document_uri)
    r = call_provider(provider, "judgment", {"document_uri": s}, cache=cache, no_cache=no_cache)
    out = judgment_from_akn(r["data"])
    return {"uri": s, "url": f"https://caselaw.nationalarchives.gov.uk/{s}", **out, "_meta": r}
