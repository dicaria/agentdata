"""es_borme — BORME daily gazette (Boletín Oficial del Registro Mercantil, www.boe.es; keyless).

Two faces (0.3.45; probed 2026-11-05, tmp/probe-es-borme-0345/ — day_1104.html 56 rows +
a28.xml (A notice, 756 companies, 1:1 articulo↔parrafo) + c5782.xml (C notice,
CONVOCATORIAS DE JUNTAS) + a 404 Sunday (2026-11-01); research volume
es-mercantile-gazette):

  * day — one publication day's notice inventory: GET /borme/dias/{y}/{m}/{d}/ (the
    canonical URL a browser reaches). Each row is <li class="dispo"> whose <p> is a
    title and whose enlacesDoc sub-list carries BOTH links: puntoPDF (the signed PDF)
    and puntoHTML (txt.php?id=BORME-…). **the id IS the key** and its prefix carries the
    subsection — THREE measured (2026-11-04): BORME-A-* = SECCIÓN PRIMERA Empresarios,
    actos inscritos (the company-life-event register; ids carry the boletin segment,
    BORME-A-2026-212-03), BORME-B-* = SECCIÓN PRIMERA Empresarios, «Otros actos
    publicados en el Registro Mercantil» (h3 sec…B; ids like BORME-B-2026-212-08),
    BORME-C-* = SECCIÓN SEGUNDA (anuncios y avisos legales — junta convocatorias,
    liquidation balances…; ids WITHOUT the boletin segment, BORME-C-2026-5782). The row
    TITLE cannot be kind-guessed: A/B rows are provinces (BARCELONA appears in BOTH
    subsections on the same day) while C rows are usually company names but CAN be
    provinces too — the id prefix is the only authority. The <h3 id="sec212A"> heading
    ids encode <boletin number><kind A|B|C>. There are NO xml.php links on the day
    page — the machine-readable twin of each id is this provider's notice op.

  * notice — one notice parsed: GET /diario_borme/xml.php?id=<id>. <documento
    fecha_actualizacion="…"> → <metadatos> (identificador / titulo / diario_numero /
    seccion codigo / fecha_publicacion / pagina_inicial..pagina_final / url_pdf; C
    notices add <departamento>, e.g. CONVOCATORIAS DE JUNTAS) → <texto>:
      - A notices alternate <p class="articulo">ORDER - NAME.</p> with <p class="parrafo">
        event paragraphs — Constitución (objeto social / domicilio / Capital / Socio
        único), Nombramientos (Adm. Unico), Reelecciones (Auditor), Cambio de domicilio,
        Extinción, Reapertura hoja registral, and the trailing «Datos registrales.
        S 8 , H AB 28113, I/A 2 ( 8.10.26).» sheet string. 1:1 articulo↔parrafo measured
        on MADRID 756/756, but the parser is a state machine: an articulo OPENS a
        company, every following parrafo APPENDS to it — multi-paragraph companies parse
        the same.
      - C notices are parrafo-only (0 articulo measured) free announcement text, kept
        verbatim.

  * **no publication day = HTTP 404**: weekends and gazette holidays answer 404
    (measured 2026-11-01, a Sunday), declared via notFound and mapped to a structured
    published=false answer — never an error, never retried. A FUTURE date is refused
    locally (usage_error) so "not yet published" never masquerades as "no issue".
  * NO NIF / registration number exists anywhere in an A-notice body — company joins
    ride the name plus the «Datos registrales» sheet string (S/H/I/A), both verbatim.
  * BORME-S-* summary ids answer 400 upstream — the id wall validates the
    BORME-[ABC]-YYYY(-N…)+ shape locally so summary ids never reach the wire.
  * upstream discovery page /diario_borme/ultimo.php answers the latest issue; the face
    stays deterministic — an explicit --date (the corpus reaches back to 2005 day by day).

Channel: plain GET, no key, no CAPTCHA, no published rate window → polite 0.5 rps /
burst 2 (gazette family posture). TTL: day 24h (daily publication cadence), notice 7d
(a published notice is frozen; fecha_actualizacion rides the result so a corrected
republication is visible).
"""
import html
import re
import unicodedata
from datetime import date as _date

from ..errors import SdkError
from ..transport import call_provider, now_iso

provider = {
    "id": "es_borme",
    "baseUrl": "https://www.boe.es",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # params: y, m, d (zero-padded strings from the locally validated --date; digits
        # quote as identity under build_url). notFound: weekends / gazette holidays
        # answer 404 — a clean round trip the face maps to published=false.
        "day": {"path": "/borme/dias/{y}/{m}/{d}/", "accept": "text", "notFound": [404],
                "timeout": 60.0},
        # params: id (BORME-[ABC]-YYYY(-N…)+, validated locally — BORME-S summaries 400
        # upstream; A/B ids carry the boletin segment, C ids don't)
        "notice": {"path": "/diario_borme/xml.php", "accept": "text", "notFound": [404],
                   "timeout": 60.0},
    },
    "ttl": {"day": 24 * 3600, "notice": 7 * 24 * 3600},
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# the notice id: kind letter A|B|C, year, then ONE OR MORE numeric segments — the A/B
# ids carry the boletin segment (BORME-A-2026-212-03) while the C ids don't
# (BORME-C-2026-5782); BORME-S-* summaries stay outside this shape (upstream 400s them)
_ID_RE = re.compile(r"^BORME-([ABC])-\d{4}(-\d+)+$")

_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
# the day row: li.dispo → <p>TITLE</p> → enlacesDoc → puntoPDF href → puntoHTML txt id.
# every measured row carries BOTH links (56=56 on 2026-11-04), in this order, inside the li.
# the gaps are TEMPERED (never crossing the next li.dispo) so a drifted row whose link
# block vanished is skipped whole — never stitched together from the next row's links.
_ROW_GAP = r'(?:(?!<li class="dispo">).)*?'
_DAY_ROW_RE = re.compile(
    r'<li class="dispo">\s*<p>(.*?)</p>\s*<div class="enlacesDoc">'
    + _ROW_GAP + r'href="(/borme/dias/\d{4}/\d{2}/\d{2}/pdfs/[^"]+)"'
    + _ROW_GAP + r'txt\.php\?id=(BORME-[ABC]-[\w-]+)', re.S)
_DISPO_RE = re.compile(r'<li class="dispo">')
_SECTION_RE = re.compile(r'<h3 id="sec(\d+)([ABC])"[^>]*>(.*?)</h3>', re.S)
# the notice body: articulo opens a company, parrafo appends — document order matters
_P_RE = re.compile(r'<p class="(articulo|parrafo)">(.*?)</p>', re.S)
_ARTICULO_RE = re.compile(r"^(\d+)\s*-\s*(.+)$")

_META_TAGS = ("identificador", "titulo", "diario", "diario_numero", "departamento",
              "fecha_publicacion", "pagina_inicial", "pagina_final", "url_pdf")


def _clean(s):
    """tag inner HTML → text: strip tags, unescape entities, NFKC, collapse whitespace."""
    txt = html.unescape(_TAG_RE.sub("", str(s or "")))
    return " ".join(unicodedata.normalize("NFKC", txt).split()) or None


def _iso(v):
    """YYYYMMDD → YYYY-MM-DD (None stays None)."""
    s = str(v or "")
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else None


def parse_day(body):
    """the day-summary HTML → dict(title, boletin_number, section_headings, rows, census) — pure.

    A row = {id, kind (A|B|C from the id prefix — never the title), title, pdf_path}. The
    census counts dispo li's SEPARATELY from parsed rows so a row whose link block drifted
    shows up as a gap instead of silently vanishing."""
    title = None
    mt = _TITLE_RE.search(body or "")
    if mt:
        title = _clean(mt.group(1))
    boletin = None
    headings = {}
    for m in _SECTION_RE.finditer(body or ""):
        if boletin is None:
            boletin = int(m.group(1))
        headings[m.group(2)] = _clean(m.group(3))
    rows = []
    for m in _DAY_ROW_RE.finditer(body or ""):
        nid = m.group(3)
        rows.append({"id": nid, "kind": nid[6], "title": _clean(m.group(1)),
                     "pdf_path": m.group(2)})
    li_count = len(_DISPO_RE.findall(body or ""))
    return {
        "title": title,
        "boletin_number": boletin,
        "section_headings": headings,
        "rows": rows,
        "census": {
            "dispo_rows": li_count,
            "parsed_rows": len(rows),
            "a_count": sum(1 for r in rows if r["kind"] == "A"),
            "b_count": sum(1 for r in rows if r["kind"] == "B"),
            "c_count": sum(1 for r in rows if r["kind"] == "C"),
        },
    }


def parse_notice(body):
    """the notice XML → metadatos + texto parse — pure. A notices: companies[] with
    events[] (articulo opens, parrafo appends). C notices: paragraphs[] verbatim."""
    body = body or ""
    meta = {}
    for tag in _META_TAGS:
        m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), body, re.S)
        meta[tag] = _clean(m.group(1)) if m else None
    doc_m = re.search(r'<documento[^>]*fecha_actualizacion="([^"]+)"', body)
    sec_m = re.search(r'<seccion codigo="(\w)">(.*?)</seccion>', body, re.S)
    seccion = {"codigo": sec_m.group(1), "titulo": _clean(sec_m.group(2))} if sec_m else None

    companies, paragraphs = [], []
    unparsed_articulo = 0
    orphan_parrafo = 0
    tx = re.search(r"<texto>(.*?)</texto>", body, re.S)
    if tx:
        for m in _P_RE.finditer(tx.group(1)):
            kind, raw = m.group(1), _clean(m.group(2))
            if kind == "articulo":
                am = _ARTICULO_RE.match(raw or "")
                if am:
                    companies.append({"order": int(am.group(1)), "name": am.group(2).strip(),
                                      "events": []})
                else:
                    # an articulo without the ORDER - NAME shape is kept as a row, never dropped
                    companies.append({"order": None, "name": raw, "events": []})
                    unparsed_articulo += 1
            elif companies:
                companies[-1]["events"].append(raw)
            else:
                paragraphs.append(raw)
                orphan_parrafo += 1
    id_kind = _ID_RE.match(meta["identificador"] or "")
    return {
        **meta,
        "diario_numero": int(meta["diario_numero"]) if (meta["diario_numero"] or "").isdigit() else None,
        "fecha_publicacion": _iso(meta["fecha_publicacion"]),
        "pagina_inicial": int(meta["pagina_inicial"]) if (meta["pagina_inicial"] or "").isdigit() else None,
        "pagina_final": int(meta["pagina_final"]) if (meta["pagina_final"] or "").isdigit() else None,
        "fecha_actualizacion": doc_m.group(1) if doc_m else None,
        "seccion": seccion,
        "companies": companies,
        "paragraphs": paragraphs,
        "census": {
            "kind": seccion["codigo"] if seccion else None,
            "id_kind": id_kind.group(1) if id_kind else None,
            "companies": len(companies),
            "events": sum(len(c["events"]) for c in companies),
            "paragraphs": len(paragraphs),
            "unparsed_articulo": unparsed_articulo,
            "orphan_parrafo": orphan_parrafo,
        },
    }


def day_raw(date, kind=None, limit=20, cache=None, no_cache=False):
    """one publication day's inventory. 404 (weekend / gazette holiday / not out yet) →
    a structured published=false answer, never an error. --kind A|C and --limit are local
    (the upstream has no query surface); the census always reports the WHOLE day."""
    if not _DATE_RE.match(str(date or "")):
        raise SdkError("usage_error", provider="es_borme",
                       detail="--date must be YYYY-MM-DD (zero-padded), e.g. 2026-11-04")
    y, m, d = str(date).split("-")
    try:
        _date(int(y), int(m), int(d))
    except ValueError:
        raise SdkError("usage_error", provider="es_borme",
                       detail=f"--date {date} is not a real calendar date")
    if str(date) > _date.today().isoformat():
        raise SdkError("usage_error", provider="es_borme",
                       detail=(f"--date {date} is in the future — the gazette has not reached "
                               "that day; use a date up to today (UTC)"))
    k = str(kind).strip().upper() if kind else None
    if k not in (None, "A", "B", "C"):
        raise SdkError("usage_error", provider="es_borme",
                       detail=("--kind is A (SECCIÓN PRIMERA actos inscritos), B (SECCIÓN "
                               "PRIMERA otros actos publicados), C (SECCIÓN SEGUNDA anuncios "
                               "y avisos legales), or omitted"))
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    if not 1 <= limit <= 100:
        raise SdkError("usage_error", provider="es_borme",
                       detail="limit must be 1-100 (local slice wall)")
    wall = limit
    try:
        res = call_provider(provider, "day", {"y": y, "m": m, "d": d},
                            cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.status == 404:
            # weekends / gazette holidays (and today's issue before it is out) — a
            # legitimate no-publication day, structured as such (never retried upstream)
            return {"date": str(date), "published": False, "title": None,
                    "boletin_number": None, "section_headings": {}, "rows": [],
                    "total_matched": 0, "scanned_rows": 0,
                    "census": {"dispo_rows": 0, "parsed_rows": 0, "a_count": 0,
                               "b_count": 0, "c_count": 0},
                    "limit_applied": 0, "params": {"date": str(date), "kind": k},
                    # a synthetic meta: _flat_env/enrich_source require at least one meta
                    # with fetched_at, and a 404 clean round trip carries no fetched page
                    "_meta": {"status": 404, "fetched_at": now_iso()}}
        raise
    parsed = parse_day(res["data"])
    rows = parsed["rows"]
    if k:
        rows = [x for x in rows if x["kind"] == k]
    total_matched = len(rows)
    return {
        "date": str(date), "published": True,
        "title": parsed["title"], "boletin_number": parsed["boletin_number"],
        "section_headings": parsed["section_headings"],
        "rows": rows[:wall], "total_matched": total_matched,
        "scanned_rows": parsed["census"]["parsed_rows"],
        "census": parsed["census"], "limit_applied": min(wall, total_matched),
        "params": {"date": str(date), "kind": k}, "_meta": res,
    }


def notice_raw(notice_id, name=None, order=None, limit=20, cache=None, no_cache=False):
    """one notice, machine-readable. --name (NFKC+casefold contains over company names)
    and --order (exact articulo number) are local (the upstream has no query surface);
    paragraphs pass through untouched. 404 (unknown id) propagates as
    upstream_not_found — a caller error, the cz_ares posture."""
    nid = str(notice_id or "").strip()
    if not _ID_RE.match(nid):
        raise SdkError("usage_error", provider="es_borme",
                       detail=("--id must be a BORME-A/B/C id as issued (e.g. "
                               "BORME-A-2026-212-03 with the boletin segment or "
                               "BORME-C-2026-5782 without); BORME-S-* summary ids answer "
                               "400 upstream and are refused here — take ids from the "
                               "es_borme_day face (the puntoHTML link)"))
    if order is not None:
        try:
            order = int(order)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="es_borme",
                           detail="--order must be an integer (the articulo ORDER number)")
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    if not 1 <= limit <= 100:
        raise SdkError("usage_error", provider="es_borme",
                       detail="limit must be 1-100 (local slice wall)")
    wall = limit
    res = call_provider(provider, "notice", {"id": nid}, cache=cache, no_cache=no_cache)
    parsed = parse_notice(res["data"])
    comps = parsed["companies"]

    def _fold(s):
        return " ".join(unicodedata.normalize("NFKC", str(s or "")).split()).casefold()
    q = _fold(name) if name else None
    rows = [c for c in comps
            if (q is None or q in _fold(c["name"]))
            and (order is None or c["order"] == order)]
    total_matched = len(rows)
    return {
        **{k: v for k, v in parsed.items() if k not in ("companies", "census")},
        "companies": rows[:wall], "total_matched": total_matched,
        "scanned_companies": len(comps),
        "census": parsed["census"], "limit_applied": min(wall, total_matched),
        "params": {"id": nid, "name": name, "order": order}, "_meta": res,
    }
