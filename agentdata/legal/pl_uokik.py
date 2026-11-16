"""pl_uokik — Poland's competition & consumer authority (UOKiK) decisions of the President
(decyzje.uokik.gov.pl, the Domino "dec_prez" database, keyless).

PL legal faces (0.3.60; admitted from the research booklet pl-uokik-decyzje, re-probed live
2026-11-13):

CONTRACT (two surfaces):
  1. index — GET /bp/dec_prez.nsf/0b335ee1820a0883c1257876002d1521?ReadViewEntries&Count=99999&ExpandView
     The answer is one XML document (15.1 MB measured) carrying the whole decision register as
     a flat list of <viewentry> elements:
       <viewentry position="1" ...>            → the practice (Rodzaj praktyki)   [12 of them]
       <viewentry position="1.1" ...>          → the year                          [216 of them]
       <viewentry position="1.1.1" unid="…">   → one decision                     [22,344 of them]
     A decision row's <text> is XML-escaped HTML carrying three things: the decision number
     ("Numer decyzji: DIH-II-39/2026"), the decision date ("Data decyzji: 06.11.2026") and
     the parties (each an anchor whose href carries act=decyzjekontr).
     There is NO server-side filter on this surface (it is a view enumeration, not a search) —
     the face enumerates and filters locally, exactly like the LV KNAB party register.
  2. detail — GET /bp/dec_prez.nsf/1/{unid}?editDocument&act=Decyzja
     The answer is the decision card: a two-column table whose rows are
     <td><b>LABEL:</b></td><td>VALUE</td> — Numer decyzji / Data wydania decyzji /
     Sygnatura akt / Uczestnicy postępowania / Rodzaj praktyki / Kara / Branża / Region /
     Decyzja (the PDF link) / Odwołanie do sądu / Orzecznictwo. The PDF link shape is
     /bp/dec_prez.nsf/43104c28a7a1be23c1257eac006d8dd4/{unid-lower}/$FILE/{name}.pdf.

LIVE LAWS (measured 2026-11-13):
  - the host RESETS the TLS connection on roughly half the requests from this machine
    (urllib URLError); the transport's retry (2 retries, exponential backoff) absorbs it.
    The index answer therefore needs a longer timeout than the default (120 s here).
  - the index is a 15 MB payload — it is cached whole (TTL 12 h); the face never re-fetches
    it per row.

Politeness: 0.25/2, concurrency 1, TTL 12h (the register is appended to daily).
"""
import html
import re

from ..errors import SdkError

provider = {
    "id": "pl_uokik",
    "baseUrl": "https://decyzje.uokik.gov.pl",
    "rate": {"rps": 0.25, "burst": 2},
    "concurrency": 1,
    "ops": {
        # the whole register in one XML document (15.1 MB measured) — no server-side filter
        "index": {"path": "/bp/dec_prez.nsf/0b335ee1820a0883c1257876002d1521"
                          "?ReadViewEntries&Count=99999&ExpandView",
                  "accept": "text", "timeout": 120.0},
        # one decision card (the nine structured fields + the PDF link)
        "detail": {"path": "/bp/dec_prez.nsf/1/{unid}?editDocument&act=Decyzja",
                   "accept": "text", "timeout": 60.0},
    },
    "ttl": {"index": 12 * 3600, "detail": 24 * 3600},
}

_VIEWENTRY = re.compile(r'<viewentry position="([^"]*)"([^>]*)>(.*?)</viewentry>', re.S)
_UNID = re.compile(r'unid="([0-9A-Fa-f]{32})"')
_TEXT = re.compile(r"<text>(.*?)</text>", re.S)
_NUMBER = re.compile(r"Numer decyzji:\s*[\[\]]*\s*([A-Za-z0-9\-/.]+)")
_DATE = re.compile(r"Data decyzji:\s*[\[\]]*\s*(\d{2}\.\d{2}\.\d{4})")
_PARTY = re.compile(r"<a[^>]*decyzjekontr[^>]*>(.*?)</a>", re.S | re.I)
# the detail card rows: <td …><b>LABEL:</b></td><td …>VALUE</td>
_DETAIL_ROW = re.compile(r"<td[^>]*>\s*<b>(.*?)</b>\s*</td>\s*<td[^>]*>(.*?)</td>", re.S)
_DETAIL_PDF = re.compile(r'href="([^"]*\$FILE/[^"]*\.pdf)"', re.I)
_TITLE = re.compile(r'<h3 class="page-title[^"]*"[^>]*>(.*?)</h3>', re.S)


def _strip(s):
    """HTML fragment → plain text. The index XML carries HTML ESCAPED inside the XML text
    nodes (the tags arrive as &lt;p …&gt;), so the unescape has to come BEFORE the tag
    removal — otherwise the escaped markup survives as literal text."""
    t = html.unescape(s or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def _flat(s):
    """HTML fragment → text with the tags removed and NO separator inserted.

    The upstream wraps every value in square brackets ON THE INSIDE of the markup
    ("[&lt;B&gt;]Jakość paliw[&lt;/B&gt;]"), so the brackets survive the tag removal and
    the label is the text BETWEEN them — a separator would break that ("[ ] Jakość paliw").
    """
    t = html.unescape(s or "")
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _label(text):
    """The label of a category/year entry: the bracketed, HTML-escaped text."""
    return _flat(text).strip("[]").strip()


def parse_index(xml_text):
    """The index XML → {categories[], years[], rows[]} (pure function — offline testable).
    Each row: {category, year, decision_number, decision_date, parties[], unid, url}."""
    categories, years, rows = [], [], []
    cat_by_pos, year_by_pos = {}, {}
    for pos, attrs, body in _VIEWENTRY.findall(xml_text or ""):
        tm = _TEXT.search(body)
        raw = tm.group(1) if tm else ""
        plain = html.unescape(raw)
        flat = _flat(raw)
        depth = pos.count(".") + 1
        if depth == 1:
            name = _label(raw)
            cat_by_pos[pos] = name
            categories.append(name)
            continue
        if depth == 2:
            name = _label(raw)
            year_by_pos[pos] = name
            years.append(name)
            continue
        um = _UNID.search(attrs)
        if not um:
            continue
        unid = um.group(1)
        number = _NUMBER.search(flat)
        date = _DATE.search(flat)
        parties = [_strip(p) for p in _PARTY.findall(plain)]
        parties = [p for p in parties if p]
        parent = pos.rsplit(".", 1)[0]
        rows.append({
            "category": cat_by_pos.get(parent.rsplit(".", 1)[0] if "." in parent else parent)
                        or cat_by_pos.get(parent),
            "year": year_by_pos.get(parent),
            "decision_number": number.group(1) if number else None,
            "decision_date": date.group(1) if date else None,
            "parties": parties,
            "unid": unid,
            "url": f"https://decyzje.uokik.gov.pl/bp/dec_prez.nsf/1/{unid}?editDocument&act=Decyzja",
        })
    return {"categories": categories, "years": years, "rows": rows}


def parse_detail(html_text):
    """The decision card → {fields{}, parties[], pdf_url, title} (pure function)."""
    fields = {}
    for label, value in _DETAIL_ROW.findall(html_text or ""):
        key = _strip(label).rstrip(":").strip()
        if key and key not in fields:
            fields[key] = _strip(value)
    pdf = _DETAIL_PDF.search(html_text or "")
    title = _TITLE.search(html_text or "")
    parties = [_strip(p) for p in _PARTY.findall(html_text or "")]
    return {
        "fields": fields,
        "parties": [p for p in parties if p],
        "pdf_url": ("https://decyzje.uokik.gov.pl" + pdf.group(1)) if pdf else None,
        "title": _strip(title.group(1)) if title else None,
    }


def _call(op, params, cache, no_cache):
    from ..transport import call_provider
    return call_provider(provider, op, params, cache=cache, no_cache=no_cache)


def decisions_raw(*, year=None, practice=None, party=None, limit=50, offset=0,
                  cache=None, no_cache=False):
    """→ {total, rows[], categories[], years[], params, _meta}. The register has no
    server-side filter — the whole index is read once (cached) and filtered locally."""
    from ..transport import call_provider  # noqa: F401  (kept for symmetry with the other modules)

    try:
        lim = int(limit)
        off = int(offset)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="pl_uokik",
                       detail=f"limit/offset must be integers, got limit={limit!r} offset={offset!r}")
    if lim < 1:
        raise SdkError("usage_error", provider="pl_uokik", detail=f"limit must be >= 1, got {lim}")
    if off < 0:
        raise SdkError("usage_error", provider="pl_uokik", detail=f"offset must be >= 0, got {off}")

    res = _call("index", {}, cache, no_cache)
    doc = parse_index(res.get("data") or "")
    rows = doc["rows"]
    y = str(year).strip() if year not in (None, "") else None
    p = str(practice).strip().lower() if practice else None
    party_q = str(party).strip().lower() if party else None
    if y:
        rows = [r for r in rows if (r.get("year") or "") == y]
    if p:
        rows = [r for r in rows if p in (r.get("category") or "").lower()]
    if party_q:
        rows = [r for r in rows
                if any(party_q in (x or "").lower() for x in (r.get("parties") or []))]
    total = len(rows)
    page = rows[off:off + lim]
    return {
        "total": total,
        "rows": page,
        "categories": doc["categories"],
        "years": doc["years"],
        "params": {"year": y, "practice": practice, "party": party,
                   "limit": lim, "offset": off},
        "_meta": res,
    }


def decision_raw(unid="", *, cache=None, no_cache=False):
    """→ {fields{}, parties[], pdf_url, title, params, _meta}. One decision card
    (unid = the 32-hex id the index rows carry)."""
    u = str(unid or "").strip()
    if not u:
        raise SdkError("usage_error", provider="pl_uokik",
                       detail="unid is required (the 32-hex id from an index row)")
    if not re.fullmatch(r"[0-9A-Fa-f]{32}", u):
        raise SdkError("usage_error", provider="pl_uokik",
                       detail=f"unid must be 32 hex characters, got {u!r}")
    res = _call("detail", {"unid": u}, cache, no_cache)
    doc = parse_detail(res.get("data") or "")
    if not doc["fields"]:
        raise SdkError("upstream_not_found", provider="pl_uokik",
                       detail=f"the decision card for unid {u} is empty — the id may be stale")
    doc["params"] = {"unid": u}
    doc["_meta"] = res
    return doc
