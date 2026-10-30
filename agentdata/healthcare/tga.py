"""tga — Australian TGA eBS public face provider (a Domino .nsf site family; keyless).

Wave 6 of the healthcare domain: related
kind=artg_register / mis_manufacturers — the Australian therapeutic goods register ARTG, 97,988 product × sponsor
company edges, plus the Australian manufacturer licence register MIS with 444 licence × manufacturer rows.
Shapes measured 2026-10-23:
Host gating is split by host: ebs.tga.gov.au is fully open (both the curl and undici stacks), www.tga.gov.au hangs after connecting from this egress (do not probe the main site).
ARTG search: GET /ebs/ANZTPAR/PublicWeb.nsf/luPortalRegisterPublic?SearchView=&Query="Sun Pharma ANZ Pty Ltd"&Count=N&Start=M&charset=utf-8
  — an **HTML surface** (SearchView does not honour outputformat=json, it was measured returning text/html): the op passes the raw text through with accept:'text'.
  Query semantics: a quoted phrase = an exact phrase (measured Sun Pharma ANZ 100/100 hits); bare words = AND across all fields.
  Row columns Name|ARTG|PI/CMI|Type|Sponsor (rows carry an OpenDocument detail link, and the row also starts with a sort-icon td that is not a data column);
  Count=100 gives a 100-row page; Start = the number of rows to skip (skip semantics). Field-level search ([Sponsor] CONTAINS …) is bounced back to the search form — not done.
ARTG enumeration (the raw bulk line): the same view ?ReadViewEntries&outputformat=json&Count≤15000&Start=N (count=100000 → 500 OOM).
MIS licences: GET /ebs/ANZTPAR/PublicWeb.nsf/luPortalManufacturers?ReadViewEntries&outputformat=json&count=500 → JSON,
  @toplevelentries=444; row columns Issue Date|Licence Number|Manufacturer ID|Address|**SiteState**|Manufacturer
  (the state column's real name is SiteState, not the portal config's ColTitles «State» — the column name is the viewentry @name).
TTL: the register is on a daily cadence → 24h; no published quota → polite tier 1 rps.
"""
import re

from ..errors import SdkError

provider = {
    "id": "tga",
    "baseUrl": "https://www.ebs.tga.gov.au/ebs/ANZTPAR/PublicWeb.nsf",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "search": {"path": "/luPortalRegisterPublic", "accept": "text"},  # params: SearchView/Query/Count/Start/charset → HTML
        "manufacturers": {"path": "/luPortalManufacturers"},              # params: ReadViewEntries/outputformat/count/charset → JSON
    },
    "ttl": {"search": 24 * 3600, "manufacturers": 24 * 3600},
}

_TR_RE = re.compile(r"<tr[\s\S]*?</tr>", re.I)
_TD_RE = re.compile(r"<td[^>]*>([\s\S]*?)</td>", re.I)
_DOC_RE = re.compile(r'href="([^"]*OpenDocument[^"]*)"', re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_IMG_RE = re.compile(r"<img", re.I)
_A_RE = re.compile(r"<a[\s>]", re.I)


def _cell_text(h):
    s = _TAG_RE.sub(" ", str(h or ""))
    s = (s.replace("&amp;", "&").replace("&quot;", '"')
          .replace("&#39;", "'").replace("&rsquo;", "'").replace("&nbsp;", " "))
    return re.sub(r"\s+", " ", s).strip()


def rows_from_search_html(html):
    """SearchView HTML → ARTG rows (pure function, testable offline): only rows with an OpenDocument detail link count; pure icon tds are stripped (measured 6 td → 5 data tds)."""
    rows = []
    for m in _TR_RE.finditer(str(html or "")):
        tr = m.group(0)
        if "OpenDocument" not in tr:
            continue
        cells = [c for c in _TD_RE.findall(tr)
                 if not (_IMG_RE.search(c) and not _A_RE.search(c) and not _TAG_RE.sub("", c).strip())]
        if len(cells) < 5:
            continue
        href = _DOC_RE.search(tr)
        rows.append({
            "product_name": _cell_text(cells[0]) or None,
            "artg_id": _cell_text(cells[1]) or None,
            "pi_cmi": _cell_text(cells[2]) or None,
            "product_type": _cell_text(cells[3]) or None,
            "sponsor": _cell_text(cells[4]) or None,   # company edge, primary column (the registrant = the entity accountable for the Australian market)
            "doc_url": ("https://www.ebs.tga.gov.au" + href.group(1).replace("&amp;", "&")) if href else None,
        })
    return rows


def _entry_val(d):
    if not d:
        return None
    # Domino value-object shape {"0": "..."} (mirrors the d.text[0] property access on the Node side)
    if d.get("text"):
        return d["text"].get("0") or None
    if d.get("number") is not None:
        return str(d["number"].get("0"))
    if d.get("datetime") is not None:
        return re.sub(r"^(\d{4})(\d{2})(\d{2}).*$", r"\1-\2-\3", str(d["datetime"].get("0")))
    return None


def rows_from_view_json(data):
    """ReadViewEntries JSON (the Domino viewentry shape) → MIS licence rows (pure function, testable offline); datetime→YYYY-MM-DD, the state column's real name is SiteState."""
    out = []
    for e in (data or {}).get("viewentry") or []:
        col = {d.get("@name"): d for d in e.get("entrydata") or []}
        out.append({
            "issue_date": _entry_val(col.get("Issue Date")),
            "licence_number": _entry_val(col.get("Licence Number")),
            "manufacturer_id": _entry_val(col.get("Manufacturer ID")),
            "address": _entry_val(col.get("Address")),
            "state": _entry_val(col.get("SiteState")),
            "manufacturer": _entry_val(col.get("Manufacturer")),  # company edge, primary column (the licence holder)
        })
    return out


def build_search_query(sponsor=None, query=None):
    """Domino Query assembly (pure function, testable offline): sponsor → a quoted phrase (measured exact);
    query → passed through as given (a quoted phrase is upstream-native syntax; since 0.3.0 the quotes are not stripped — stripping them would make the exact Sponsor match unreachable)."""
    sp, q = str(sponsor or "").strip(), str(query or "").strip()
    if not sp and not q:
        raise SdkError("usage_error", provider="tga", detail="sponsor or query is required (a bare query would enumerate the whole 98,000-row register, so it is refused)")
    if sp:
        return '"' + sp.replace('"', "") + '"'
    return q


def search_art_register(sponsor=None, query=None, *, limit=20, skip=0, cache=None, no_cache=False):
    """→ {rows[], count, skip, limit_applied, has_more, query, _meta}; has_more is a full-page heuristic (Domino does not return the hit total)."""
    from ..transport import call_provider

    q = build_search_query(sponsor, query)
    size = min(max(1, int(limit or 20)), 100)  # SearchView Count measured 100/page
    sk = max(0, int(skip or 0))
    params = {"SearchView": "", "Query": q, "Count": size, "charset": "utf-8"}
    if sk:
        params["Start"] = sk  # Start = the number of rows to skip (skip semantics; measured Start=100 continues onto the next page)
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    rows = rows_from_search_html(r.get("data"))
    return {"rows": rows, "count": len(rows), "skip": sk, "limit_applied": size,
            "has_more": len(rows) == size, "query": q, "_meta": r}


def list_manufacturers(state=None, *, limit=100, cache=None, no_cache=False):
    """→ {rows[], total, count, limit_applied, _meta} — the MIS licence register: 444 licences in one full shot (count=500 on a single page) + the state filter."""
    from ..transport import call_provider

    size = min(max(1, int(limit or 100)), 500)
    r = call_provider(provider, "manufacturers",
                      {"ReadViewEntries": "", "outputformat": "json", "count": 500, "charset": "utf-8"},
                      cache=cache, no_cache=no_cache)
    data = r.get("data") or {}
    total = int(data.get("@toplevelentries") or 0)
    rows = rows_from_view_json(data)
    if state:
        rows = [x for x in rows if (x.get("state") or "").upper() == str(state).strip().upper()]
    return {"rows": rows[:size], "total": total, "count": min(len(rows), size),
            "limit_applied": size, "_meta": r}
