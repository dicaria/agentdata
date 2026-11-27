"""edgar_arch — SEC EDGAR Archives document fetch (www.sec.gov/Archives, keyless).

2026-11-18 probed (tmp/probe-e11/p1-fetch.py + p2-shapes.py): the body-fetch channel the filings
line lacked — every prior us_sec face is index/structured (submissions = filing index, fts =
full-text HIT metadata, xbrl = facts); the document bytes themselves were only reachable as
doc_url links. Archives serves them keyless under the declared-UA fair access; provider bucket
5/5 and the shared www.sec.gov host bucket (5 rps) keep the family inside the official 10 req/s.

ENVELOPE, TWO SHAPES (p10/p13): older filings serve documents SGML-wrapped —
"<DOCUMENT>\\n<TYPE>EX-99.1\\n<SEQUENCE>2\\n<FILENAME>radnet_8k-ex9901.htm\\n<DESCRIPTION>...
\\n<TEXT>" ... inner ... "</TEXT>\\n</DOCUMENT>" — while modern filings (Apple 2026 10-K) serve
bare iXBRL XML (<?xml ...?> first byte). Detection: body starts with "<DOCUMENT>" -> header
fields parsed (each value runs to end of line; TYPE/SEQUENCE/FILENAME/DESCRIPTION), inner =
between the first "<TEXT>" and the LAST "</TEXT>" (greedy: an inner literal "</TEXT>" in quoted
content still leaves the true outer close last); otherwise verbatim bare, envelope=False.

INDEX.JSON IS A PURE DIRECTORY LISTING, EVERY ERA (p2/p9): items carry name / type(icon: text.gif,
compressed.gif — NOT a document type) / size / last-modified. No isPrimaryDocument field even on
2026 filings. Every dir also lists scaffold rows: {adsh}-index-headers.html, {adsh}-index.html,
{adsh}.txt (+ {adsh}-xbrl.zip on XBRL filings) — auto-generated navigation, not filed content.
XML-ONLY DIRS ARE REAL (0.3.75 E17 collision): 13F-HR accessions carry ONLY the information table
and primary_doc.xml — a directory can be all-xml with no .htm at all; is_document counts .xml
since the fix-forward (the htm/html/txt-only regex had scored a real filing as scaffold-only).

BOGUS ACCESSION = 200 SCAFFOLD (p11): index.json on a nonexistent accession answers 200 with a
scaffold-only listing that includes a ghost "filename1.htm" placeholder row. Engine raises
upstream_not_found on scaffold-only; a DOCUMENT fetch on a bogus accession 404s (honest path).

CIK PATH SEGMENT MANDATORY (p3): /Archives/edgar/data/{adsh_nodash}/... without the cik segment
403s — the face always builds the two-segment path.

AUTO-PRIMARY (p6): with --cik + --accession and no filename, the submissions recent window
(edgar_cik provider, shared cache — the fts->cik cross-module resolution precedent) supplies the
authoritative primaryDocument; accessions older than the ~1000-row recent window must pass
--filename / --url / --list explicitly (usage_error names the boundary).

BYTES + DECODE (p13): accept='bytes' (ext 9) -> exact bytes via latin-1 round-trip; sha256 over
raw bytes; decode chain = declared charset -> utf-8 strict -> cp1252 (legacy EDGAR encoding) ->
utf-8 replace. --text strips HTML with a stdlib HTMLParser (script/style skipped, block tags
newline, charrefs decoded) — zero dependency.
"""
import hashlib
import re
from html.parser import HTMLParser

from ..errors import SdkError

provider = {
    "id": "edgar_arch",
    "baseUrl": "https://www.sec.gov",
    "rate": {"rps": 5, "burst": 5},  # shares the www.sec.gov host bucket (5 rps) with edgar_xbrl's tickers op
    "ops": {
        # two-segment path (cik + accession) is mandatory upstream: the accession-only path 403s (p3)
        "index": {"path": "/Archives/edgar/data/{cik}/{adsh}/index.json", "timeout": 30.0},
        "doc": {"path": "/Archives/edgar/data/{cik}/{adsh}/{filename}", "accept": "bytes",
                "notFound": [404], "timeout": 60.0},
    },
    "ttl": {"index": 7 * 86400, "doc": 7 * 86400},  # filed documents are frozen — fetch once, valid for good
}

_ACCESSION_RE = re.compile(r"^(\d{2,10})-(\d{2})-(\d{6})$")
_ADSH_NODASH_RE = re.compile(r"^\d{10,18}$")
_URL_HOSTS = re.compile(r"^https://(?:www\.)?sec\.gov/Archives/edgar/data/(\d{1,10})/(\d{10,18})/([^/?#]+)$")
_SCAFFOLD = ("filename1.htm",)  # the ghost placeholder row of a scaffold-only dir (p11)


def normalize_accession(value):
    """→ (adsh_dashed, adsh_nodash); accepts 0001683168-20-000837 or 000168316820000837."""
    s = str(value or "").strip()
    m = _ACCESSION_RE.match(s)
    if m:
        dashed = s
    else:
        if not _ADSH_NODASH_RE.match(s):
            raise SdkError("usage_error", provider="edgar_arch",
                           detail="accession must look like 0001683168-20-000837 (or the same 14-18 digits "
                                  f"without dashes), got \"{value}\"")
        dashed = f"{s[:-8]}-{s[-8:-6]}-{s[-6:]}"
    return dashed, dashed.replace("-", "")


def parse_archive_url(url):
    """--url form (the doc_url us_sec_fulltext_search already hands back): parse (cik, adsh_dashed,
    filename). Prefix wall: ONLY https://www.sec.gov/Archives/edgar/data/... passes — any other
    host is a usage_error before a byte leaves the process."""
    m = _URL_HOSTS.match(str(url or "").strip())
    if not m:
        raise SdkError("usage_error", provider="edgar_arch",
                       detail="--url must be a www.sec.gov/Archives/edgar/data/... document URL "
                              "(the shape us_sec_fulltext_search returns as doc_url), got "
                              f"\"{url}\"")
    cik, nodash, filename = m.group(1), m.group(2), m.group(3)
    dashed = f"{nodash[:-8]}-{nodash[-8:-6]}-{nodash[-6:]}" if len(nodash) > 10 else nodash
    return cik.zfill(10), dashed, filename


def split_envelope(raw):
    """→ (meta | None, inner_bytes, envelope: bool). SGML-wrapped docs (older filings) get their
    header fields parsed and the <TEXT> wrapper stripped; bare docs (modern iXBRL, index pages)
    pass through untouched."""
    head = raw.lstrip()[:40].decode("latin-1", "replace")
    if not head.startswith("<DOCUMENT>"):
        return None, raw, False
    text = raw.decode("latin-1", "replace")
    meta = {}
    for key in ("TYPE", "SEQUENCE", "FILENAME", "DESCRIPTION"):
        m = re.search(rf"<{key}>([^\n\r<]*)", text)
        meta[key.lower()] = m.group(1).strip() if m else None
    start = text.find("<TEXT>")
    end = text.rfind("</TEXT>")
    inner = text[start + len("<TEXT>"):end] if (start != -1 and end > start) else text
    return meta, inner.encode("latin-1", "replace"), True


def decode_bytes(raw, content_charset=None):
    """→ (text, encoding_used): declared charset first, then utf-8 strict, then cp1252, then
    utf-8 replace (last resort never raises)."""
    if content_charset:
        try:
            return raw.decode(content_charset, "strict"), content_charset
        except (UnicodeDecodeError, LookupError):
            pass
    try:
        return raw.decode("utf-8", "strict"), "utf-8"
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1252", "strict"), "cp1252"
        except UnicodeDecodeError:
            return raw.decode("utf-8", "replace"), "utf-8(replace)"


class _TextX(HTMLParser):
    _BLOCK = ("p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
              "table", "thead", "tbody", "section", "article")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in self._BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if not self._skip:
            self.out.append(data)


def html_to_text(html_text):
    """--text channel: stdlib parser only (script/style skipped, block tags newline,
    whitespace collapsed). Zero dependency by design."""
    p = _TextX()
    p.feed(html_text)
    text = re.sub(r"[ \t\xa0]+", " ", "".join(p.out))
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _is_scaffold(adsh_dashed, name):
    return name in (f"{adsh_dashed}-index-headers.html", f"{adsh_dashed}-index.html",
                    f"{adsh_dashed}.txt") or name in _SCAFFOLD


def index_rows(data, adsh_dashed):
    """index.json → rows [{name, size, last_modified, scaffold, is_document}] (verbatim order).
    Scaffold-only dir (bogus accession, p11) → upstream_not_found: the upstream answers 200 with
    a ghost listing, and answering an empty dir as a legal zero would launder a wrong accession."""
    items = ((data or {}).get("directory") or {}).get("item") or []
    rows = []
    for it in items:
        name = it.get("name") or ""
        scaffold = _is_scaffold(adsh_dashed, name)
        # .xml is filed content too (0.3.75 fix-forward: 13F-HR accessions carry ONLY xml —
        # information table + primary_doc — and the htm/html/txt-only regex misclassified a REAL
        # filing as the bogus-accession scaffold shape; the ghost/scaffold rows are .htm/.txt, so
        # the gate itself never weakens)
        is_doc = (not scaffold and bool(re.search(r"\.(htm|html|txt|xml)$", name, re.I)))
        rows.append({"name": name, "size": it.get("size") or None,
                     "last_modified": it.get("last-modified") or None,
                     "scaffold": scaffold,
                     "is_document": is_doc})
    if items and not any(r["is_document"] for r in rows):
        raise SdkError("upstream_not_found", provider="edgar_arch",
                       detail=f"no filed documents under accession {adsh_dashed} — the upstream answered a "
                              "scaffold-only directory (placeholder rows, no real documents); this is the "
                              "bogus-accession shape, not an empty filing")
    return rows


def primary_doc_from_submissions(cik10, adsh_dashed, *, cache=None, no_cache=False):
    """auto-primary: scan the submissions recent window for the accession → primaryDocument.
    → (filename | None, meta) — meta rides back to the face for budget transparency.
    None = older than the ~1000-row recent window → the caller must disambiguate."""
    from ..transport import call_provider
    from . import edgar_cik

    r = call_provider(edgar_cik.provider, "submissions", {"cik10": cik10},
                      cache=cache, no_cache=no_cache)
    recent = ((r.get("data") or {}).get("filings") or {}).get("recent") or {}
    for i, adsh in enumerate(recent.get("accessionNumber") or []):
        if str(adsh) == adsh_dashed:
            prim = (recent.get("primaryDocument") or [None] * len(recent.get("accessionNumber") or []))[i]
            return (str(prim) if prim else None), r
    return None, r


def candidates_from_rows(rows):
    return [r["name"] for r in rows if r["is_document"]]


def fetch_document(cik=None, accession=None, filename=None, url=None, *, want_text=False,
                   cache=None, no_cache=False):
    """→ verbatim/decoded document payload for the face layer:
    {cik, accession, filename, url, envelope{type,sequence,filename,description}|None,
     content(charset-decoded verbatim; str), text|None, size_bytes, sha256, encoding_used}."""
    from ..transport import call_provider

    if url:
        cik_u, adsh_d, fn_u = parse_archive_url(url)
        if cik or accession:
            # both forms given: they must agree (cheap catch of copy-paste drift)
            from .edgar_cik import normalize_cik
            if cik and normalize_cik(cik) != cik_u.zfill(10):
                raise SdkError("usage_error", provider="edgar_arch",
                               detail=f"--cik {cik} disagrees with the CIK in --url ({cik_u}) — pass exactly one form")
            if accession:
                adsh_g, _ = normalize_accession(accession)
                if adsh_g != adsh_d:
                    raise SdkError("usage_error", provider="edgar_arch",
                                   detail=f"--accession {accession} disagrees with the accession in --url ({adsh_d}) — pass exactly one form")
        cik10, adsh_dashed, fname = cik_u.zfill(10), adsh_d, fn_u
    else:
        if not cik or not accession:
            raise SdkError("usage_error", provider="edgar_arch",
                           detail="us_sec_filing_document needs --url, or --cik + --accession "
                                  "(--filename optional — without it the submissions primaryDocument "
                                  "is used; unknown accessions fall back to --list)")
        from .edgar_cik import normalize_cik
        cik10 = normalize_cik(cik)
        adsh_dashed, adsh_nodash = normalize_accession(accession)
        fname = str(filename).strip() if filename else None

    # ---- filename resolution (body mode): explicit > submissions primary > index disambiguation
    via = "given" if fname else None
    index_r = None
    rows = None
    subs_meta = None
    if not fname:
        index_r = call_provider(provider, "index", {"cik": cik10, "adsh": adsh_dashed.replace("-", "")},
                                cache=cache, no_cache=no_cache)
        rows = index_rows(index_r["data"], adsh_dashed)
        fname, subs_meta = primary_doc_from_submissions(cik10, adsh_dashed, cache=cache, no_cache=no_cache)
        if fname:
            via = "submissions_primary"
        else:
            cands = candidates_from_rows(rows)
            if len(cands) == 1:
                fname, via = cands[0], "index_single"
            else:  # cands >= 2 — index_rows already guarantees at least one document
                raise SdkError("usage_error", provider="edgar_arch",
                               detail=f"accession {adsh_dashed} carries {len(cands)} documents and the "
                                      "submissions recent window does not name its primary — pick one via "
                                      "--filename (candidates: " + ", ".join(cands[:6])
                                      + (f" … +{len(cands) - 6} more" if len(cands) > 6 else "")
                                      + ") or inspect --list")

    r = call_provider(provider, "doc", {"cik": cik10, "adsh": adsh_dashed.replace("-", ""),
                                        "filename": fname},
                      cache=cache, no_cache=no_cache)
    raw = r["data"].encode("latin-1")  # ext-9 lossless recovery
    meta, inner, envelope = split_envelope(raw)
    text_dec, enc = decode_bytes(inner)
    out = {
        "cik": cik10, "accession": adsh_dashed, "filename": fname,
        "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{adsh_dashed.replace('-', '')}/{fname}",
        "envelope": meta, "envelope_split": envelope,
        "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "encoding_used": enc, "content": text_dec,
        "text": html_to_text(text_dec) if want_text else None,
        "filename_via": via, "params": {"cik": cik10, "accession": adsh_dashed, "filename": fname,
                                        "url": url, "text": bool(want_text)},
        "_meta": r, "_index_meta": index_r, "_submissions_meta": subs_meta,
    }
    return out


def fetch_index(cik=None, accession=None, url=None, *, cache=None, no_cache=False):
    """--list mode: the directory table. --url form allowed (dir derived from a doc_url)."""
    from ..transport import call_provider

    if url:
        cik10, adsh_dashed, _fn = parse_archive_url(url)
    else:
        if not cik or not accession:
            raise SdkError("usage_error", provider="edgar_arch",
                           detail="--list needs --cik + --accession (or --url)")
        from .edgar_cik import normalize_cik
        cik10 = normalize_cik(cik)
        adsh_dashed, _nodash = normalize_accession(accession)
    r = call_provider(provider, "index", {"cik": cik10, "adsh": adsh_dashed.replace("-", "")},
                      cache=cache, no_cache=no_cache)
    rows = index_rows(r["data"], adsh_dashed)
    docs = [x for x in rows if x["is_document"]]
    return {
        "cik": cik10, "accession": adsh_dashed,
        "total": len(rows), "documents": len(docs),
        "rows": rows,
        "dir_url": f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{adsh_dashed.replace('-', '')}/",
        "params": {"cik": cik10, "accession": adsh_dashed, "url": url}, "_meta": r,
    }
