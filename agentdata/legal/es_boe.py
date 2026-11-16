"""es_boe — BOE daily gazette table of contents (Boletín Oficial del Estado,
www.boe.es/datosabiertos; keyless; the legal domain's BOE face — the company domain's
es_borme already rides the same host for the mercantile register's own gazette).

One face (0.3.57; probed 2026-11-12, tmp/probe-sdk-0357/ — boe-sumario.json (2026-11-10,
259 items, 8 sections) + boe-sumario-T20261112.json (210 items incl. section T) + a 404
Saturday (2026-11-14) + a 1965-01-05 depth hit (164KB — the API serves the archive back
to the 1960s); research volume es-boe-sumario-api, 册 271):

  * sumario — one publication day's full table of contents:
    GET /datosabiertos/api/boe/sumario/{YYYYMMDD}. **Content negotiation is the channel
    wall**: with Accept: application/json the day answers 200 JSON (~344KB on a full
    weekday); with no Accept header it answers 400 + a 181-byte XML error (measured
    2026-11-12) — the SDK's default header set already sends the right Accept. The
    api.boe.es subdomain is egress-dead from this machine; www.boe.es is the live host.
    The tree: data.sumario{metadatos{publicacion, fecha_publicacion}, diario[1]{numero,
    sumario_diario{identificador "BOE-S-…", url_pdf}, seccion[]}}. **Every container level
    arrives dict-OR-list** (the singleton-collapse family — a one-departamento section
    ships it as a dict, iterating it yields its KEYS): seccion → departamento → item,
    with two deeper variants measured: departamento.epigrafe[].item (section 1's ministerial
    epigraphes) and departamento.texto{item | epigrafe[].item} (section 5C ships texto.item
    directly; section T — TRIBUNAL CONSTITUCIONAL, Sentencias/Declaraciones — nests its
    items under texto.epigrafe[].item). The walker collects every item row under a
    departamento subtree regardless of depth.
  * the item row, verbatim: identificador (BOE-A-2026-23528 — THE key), control
    (2026/17323 the ministry's own docket), titulo, url_xml / url_html (the machine twins
    of the item — NOTE: the item-level xml.php serves XML whatever the Accept header, it
    ignores content negotiation, so item FULL TEXT is a second surface out of this face's
    scope — the kr_law ruling), url_pdf{szBytes, szKBytes (STRINGS upstream — int-coerced
    with fallback), pagina_inicial, pagina_final, texto=the PDF url}.
  * sections are the BOE's own codes: 1 Disposiciones generales, 2A/2B Autoridades y
    personal, 3 Otras disposiciones, 4 Administración de Justicia, 5A/5B/5C Anuncios (5C
    is where departamento.texto was measured), T Tribunal Constitucional (not every day —
    2026-11-10 carries no T; 2026-11-12 does, Sala Segunda Sentencia 65/2026 amparo
    BOE-A-2026-23751).
  * **no publication day = HTTP 404**: Saturday 2026-11-14 answers 404 + XML "La
    información solicitada no existe" — declared notFound and mapped to a structured
    published=false answer, never an error (the es_borme day posture). A FUTURE date is
    refused locally so "not yet published" never masquerades as "no issue".

Channel: plain GET, no key, no published rate window → polite 0.5 rps / burst 2 (the
www.boe.es host-layer bucket is shared with es_borme — two providers, one host quota).
TTL 24h (a published day is frozen; today's issue lands early morning).
"""
from datetime import date as _date

from ..errors import SdkError
from ..transport import call_provider, now_iso

provider = {
    "id": "es_boe",
    "baseUrl": "https://www.boe.es",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # params: ymd (YYYYMMDD from the locally validated --date). The JSON channel rides
        # the SDK's default Accept: application/json — the upstream negotiates on it (no
        # Accept → 400 XML, measured 2026-11-12). notFound: weekends / gazette holidays →
        # 404 "La información solicitada no existe" (a clean round trip the face maps to
        # published=false).
        "sumario": {"path": "/datosabiertos/api/boe/sumario/{ymd}", "notFound": [404],
                    "timeout": 60.0},
    },
    "ttl": {"sumario": 24 * 3600},
}

_DATE_RE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$")

# the BOE's own section codes (measured on 2026-11-10: 8 sections; T only on
# Constitutional-Court days like 2026-11-12) — the closed set for --section
SECTIONS = ("1", "2A", "2B", "3", "4", "5A", "5B", "5C", "T")


def _as_list(v):
    """the singleton-collapse normaliser: every container level (seccion / departamento /
    epigrafe / item / texto) arrives dict-OR-list upstream — a one-child container ships
    the dict directly and iterating it would yield its KEYS."""
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _int(v):
    """szBytes & friends arrive as STRINGS ("438096") — int with fallback (never a crash
    on a drifted shape)."""
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return None


def _walk_items(container, out):
    """collect every item dict under a departamento/epigrafe/texto subtree (pure).

    Departamento variants measured: item directly (2A…5B), epigrafe[].item (section 1's
    ministerial epigraphes), texto.item (5C), texto.epigrafe[].item (T — one level
    deeper). An item row's own subtree (url_pdf…) never nests further items, so the walk
    stops at a collected row."""
    for node in _as_list(container):
        if not isinstance(node, dict):
            continue
        if "item" in node:
            out.extend(_as_list(node["item"]))
        for k in ("epigrafe", "texto"):
            if k in node:
                _walk_items(node[k], out)


def _pdf(it):
    p = it.get("url_pdf") or {}
    return {
        "url": p.get("texto"),
        "bytes": _int(p.get("szBytes")),
        "kbytes": _int(p.get("szKBytes")),
        "pagina_inicial": _int(p.get("pagina_inicial")),
        "pagina_final": _int(p.get("pagina_final")),
    }


def parse_sumario(data):
    """the sumario JSON → {identificador, boletin_number, fecha_publicacion, sections[],
    items[], census} — pure. sections = the day's census (code, nombre, departamento
    count, item count); items = every row with its seccion/departamento/epigrafe
    breadcrumb. census.walked_items is the depth-blind recursive count (any nesting,
    any depth) alongside the breadcrumb-parsed len(items) — a drifted shape shows up as
    a gap instead of silently vanishing rows."""
    sm = ((data or {}).get("data") or {}).get("sumario") or {}
    meta = sm.get("metadatos") or {}
    dias = _as_list(sm.get("diario"))
    fecha = str(meta.get("fecha_publicacion") or "")
    fecha_iso = f"{fecha[0:4]}-{fecha[4:6]}-{fecha[6:8]}" if len(fecha) == 8 and fecha.isdigit() else None
    sections, items, walked = [], [], 0
    for dia in dias:
        for sec in _as_list(dia.get("seccion")):
            codigo, nombre = sec.get("codigo"), sec.get("nombre")
            deps = _as_list(sec.get("departamento"))
            sec_items, sec_walked = [], 0
            for dep in deps:
                if not isinstance(dep, dict):
                    continue
                dep_nombre = dep.get("nombre")

                def _take(it, epi_nombre):
                    if isinstance(it, dict):
                        sec_items.append((dep_nombre, epi_nombre, it))
                # the four measured nesting shapes:
                for it in _as_list(dep.get("item")):            # departamento.item (2A…5B)
                    _take(it, None)
                for ep in _as_list(dep.get("epigrafe")):        # departamento.epigrafe[].item (1)
                    if isinstance(ep, dict):
                        for it in _as_list(ep.get("item")):
                            _take(it, ep.get("nombre"))
                for tx in _as_list(dep.get("texto")):           # departamento.texto (5C, T)
                    if isinstance(tx, dict):
                        for it in _as_list(tx.get("item")):     #   texto.item (5C)
                            _take(it, None)
                        for ep in _as_list(tx.get("epigrafe")): #   texto.epigrafe[].item (T)
                            if isinstance(ep, dict):
                                for it in _as_list(ep.get("item")):
                                    _take(it, ep.get("nombre"))
                w = []
                _walk_items(dep, w)  # depth-blind census over the same subtree
                sec_walked += len(w)
            sections.append({"codigo": codigo, "nombre": nombre,
                             "departamentos": len(deps), "items": len(sec_items)})
            walked += sec_walked
            for dep_nombre, epi_nombre, it in sec_items:
                items.append({
                    "id": it.get("identificador"),
                    "control": it.get("control"),
                    "titulo": it.get("titulo"),
                    "seccion": codigo,
                    "seccion_nombre": nombre,
                    "departamento": dep_nombre,
                    "epigrafe": epi_nombre,
                    "url_xml": it.get("url_xml"),
                    "url_html": it.get("url_html"),
                    "pdf": _pdf(it),
                })
    dia0 = dias[0] if dias else {}
    sum_diag = dia0.get("sumario_diario") or {}
    return {
        "identificador": sum_diag.get("identificador"),
        "boletin_number": _int(dia0.get("numero")),
        "fecha_publicacion": fecha_iso,
        "sections": sections,
        "items": items,
        "census": {"sections": len(sections), "items": len(items), "walked_items": walked},
    }


def sumario_raw(date, section=None, limit=20, cache=None, no_cache=False):
    """one publication day's full table of contents. 404 (weekend / gazette holiday / not
    out yet) → a structured published=false answer, never an error. --section (a BOE
    section code) and --limit are local (the upstream has one shape: the whole day)."""
    if not _DATE_RE.match(str(date or "")):
        raise SdkError("usage_error", provider="es_boe",
                       detail="--date must be YYYY-MM-DD (zero-padded), e.g. 2026-11-10")
    y, m, d = str(date).split("-")
    try:
        _date(int(y), int(m), int(d))
    except ValueError:
        raise SdkError("usage_error", provider="es_boe",
                       detail=f"--date {date} is not a real calendar date")
    if str(date) > _date.today().isoformat():
        raise SdkError("usage_error", provider="es_boe",
                       detail=(f"--date {date} is in the future — the gazette has not reached that "
                               "day; use a date up to today (the archive reaches back to the 1960s)"))
    sec = str(section).strip().upper() if section else None
    if sec not in (None,) + SECTIONS:
        raise SdkError("usage_error", provider="es_boe",
                       detail=("--section is one of the BOE's own codes: " + ", ".join(SECTIONS) +
                               " (T = Tribunal Constitucional, not every day)"))
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    if not 1 <= limit <= 100:
        raise SdkError("usage_error", provider="es_boe",
                       detail="limit must be 1-100 (local slice wall)")
    wall = limit
    ymd = str(date).replace("-", "")
    try:
        res = call_provider(provider, "sumario", {"ymd": ymd}, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.status == 404:
            # weekend / gazette holiday — a legitimate no-publication day, structured as
            # such (never retried upstream; the es_borme day posture)
            return {"date": str(date), "published": False, "identificador": None,
                    "boletin_number": None, "fecha_publicacion": None, "sections": [],
                    "rows": [], "total_matched": 0, "scanned_rows": 0,
                    "census": {"sections": 0, "items": 0},
                    "limit_applied": 0, "params": {"date": str(date), "section": sec},
                    "_meta": {"status": 404, "fetched_at": now_iso()}}
        raise
    parsed = parse_sumario(res["data"])
    rows = parsed["items"] if sec is None else [r for r in parsed["items"] if r["seccion"] == sec]
    total_matched = len(rows)
    return {
        "date": str(date), "published": True,
        "identificador": parsed["identificador"],
        "boletin_number": parsed["boletin_number"],
        "fecha_publicacion": parsed["fecha_publicacion"],
        "sections": parsed["sections"],
        "rows": rows[:wall], "total_matched": total_matched,
        "scanned_rows": len(parsed["items"]),
        "census": parsed["census"],
        "limit_applied": min(wall, total_matched),
        "params": {"date": str(date), "section": sec}, "_meta": res,
    }
