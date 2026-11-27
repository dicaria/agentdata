"""es_cnmv_sanctions — Spanish CNMV securities-market sanction register
(www.cnmv.es Portal/Consultas/RegistroSanciones, keyless ASP.NET WebForms).

ES legal face (0.3.62; admitted from the research booklet 134, 7 P0;
re-probed live 2026-11-16 tmp/probe-e4/ with the SDK's own polite UA + a
Referer — the host serves it, no UA-fingerprint gate at this section):
the provider id is the SECOND CNMV id (the company-domain es_cnmv entidades
register took the bare stem in 0.3.44 — the wb/wb_proc precedent).

The register (Ley del Mercado de Valores art. 32.3 publicity duty): a rolling
FIVE-YEAR statutory window, ~90 entries on 18 five-row pages (page=0..17 on
2026-11-16; the 2026-10-19 pin had 19 pages — the window SLIDES, the tail
page count is discovered from the page links, never hardcoded). Columns:
Fecha de incorporación (dd/mm/yyyy) | Resolución prose (the full Spanish
resolution sentence — severity tokens muy graves/graves/grave, the parties
with company suffixes S.V./SA/SGIIC/S.L. and don/doña persons, and the
"(BOE de {date})" gazette reference) | per-row PDF
(https://www.cnmv.es/webservices/verdocumento/ver?e={opaque-token}).

LIVE LAWS (measured 2026-11-16, tmp/probe-e4/):
  - a page beyond the window tail answers 302 → 400 (page=18 on 2026-11-16);
    the face validates the requested page against the discovered tail and
    reports not_found locally instead of eating the 400.
  - the pagination hrefs ride the LOWERCASE path
    /portal/consultas/registrosanciones/verregsanciones.aspx?page=N (the
    canonical URL is CamelCase; both serve).
  - ?lang=en mirrors the register in English (th "Date of incorporation into
    the register") — exposed verbatim.
  - /portal/ bare directory 403 is a red herring (the ASP.NET section is
    keyless; no sitemap, no bulk — scraping the HTML table IS the channel).

Politeness: 0.5/2 (an --all sweep walks every page, each cached 24h), TTL 24h
(register posture).
"""
import html as _html
import re

from ..errors import SdkError

provider = {
    "id": "es_cnmv_sanctions",
    "baseUrl": "https://www.cnmv.es",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "list": {"path": "/Portal/Consultas/RegistroSanciones/verRegSanciones.aspx",
                 "accept": "text", "timeout": 45.0},
    },
    "ttl": {"list": 24 * 3600},
}

_HEADERS = {"Accept": "text/html,*/*",
            "Referer": "https://www.cnmv.es/Portal/Consultas/RegistroSanciones/IniRegSanciones.aspx"}

_SEVERITIES = ("muy_graves", "graves")
_SEV_ES = {"muy_graves": "muy graves", "graves": "graves"}
_DATE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_PDF = re.compile(r'https://www\.cnmv\.es/webservices/verdocumento/ver\?e=[^"\']+')
_BOE = re.compile(r"\(BOE de ([^)]+)\)")
_TAG = re.compile(r"<[^>]+>")
# company forms in the resolution prose: a capitalized-word chain (lowercase
# connectors de/del/la/el/y/en/and/of/the allowed) then a suffix — the LIVE
# shapes carry COMMA-CHAIN suffixes the first regex missed (measured 0/5 rows
# on the captured 2026-11-16 page): "Sapiens Markets EU, S.V., SA" and
# "Gesconsult, SA, SGIIC" — the comma before the suffix and the ", SGIIC"
# continuation are both legal; persons ride the honorifics don / doña
_SUFFIX = r"(?:S\.?\s?L\.?|S\.?\s?A\.?|S\.?\s?V\.?|SGIIC|S\.?\s?A\.?\s?U\.?|S\.?\s?L\.?\s?U\.?|S\.?\s?E\.?|S\.?\s?A\.?\s?B\.?)"
_COMPANY = re.compile(
    r"([A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑ&.\-]*(?:\s+(?:de\s+|del\s+|la\s+|el\s+|y\s+|en\s+|and\s+|of\s+|the\s+)?[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑ&.\-]*)*"
    r"\s*,?\s*" + _SUFFIX + r"(?:\s*,\s*" + _SUFFIX + r")*)\b")
_PERSON = re.compile(r"\b(?:don|doña|D\.)\s+([A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑ]+(?:\s+[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑ]+){1,3})")


def parse_page(text):
    """One register page → (rows[], page_links) (pure function; severity/parties/BOE heuristics
    ride the verbatim resolution_text — the prose stays the source of truth)."""
    rows = []
    for rm in _ROW.finditer(text):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", rm.group(1), re.S)
        if len(cells) < 2:
            continue
        c0 = _html.unescape(_TAG.sub(" ", cells[0]))
        dm = _DATE.search(c0)
        if not dm:
            continue   # header row (Fecha de incorporación…) and nav rows
        prose = re.sub(r"\s+", " ", _html.unescape(_TAG.sub(" ", cells[1]))).strip()
        pm = _PDF.search(cells[-1] + " " + rm.group(1))
        boe = _BOE.search(prose)
        low = prose.lower()
        rows.append({
            "date_iso": f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}",
            "resolution_text": prose,
            "severity": next((s for s in _SEVERITIES if _SEV_ES[s] in low), None),
            "parties_companies": sorted(set(m.group(1).strip(" ,.") for m in _COMPANY.finditer(prose))) or None,
            "parties_persons": sorted(set(m.group(1) for m in _PERSON.finditer(prose))) or None,
            "boe_ref": f"BOE de {boe.group(1).strip()}" if boe else None,
            "pdf_url": _html.unescape(pm.group(0)) if pm else None,
        })
    links = sorted({int(p) for p in re.findall(r"[?&]page=(\d+)", text)})
    return rows, links


def _fetch(page, lang, *, cache=None, no_cache=False):
    from ..transport import call_provider

    params = {"page": str(page)} if page else {}
    if lang and lang != "es":
        params["lang"] = lang
    r = call_provider(provider, "list", params, cache=cache, no_cache=no_cache,
                      extra_headers=_HEADERS)
    return r


def sanctions_raw(page=None, *, all_pages=False, party=None, severity=None,
                  lang="es", limit=20, cache=None, no_cache=False):
    """→ {rows[], total_matched, scanned_rows, pages, max_page, window, params, _meta}.

    Default = page 0 (five freshest entries + the discovered pagination census).
    page = N (0-based) fetches that one page; all_pages/party/severity sweep
    every page (each cached 24h — the second sweep is free). party = substring
    over the resolution prose (company or person tokens alike); severity =
    muy_graves|graves (token over the prose, verbatim-law family)."""
    if severity not in (None, "") and severity not in _SEVERITIES:
        raise SdkError("usage_error", provider="es_cnmv_sanctions",
                       detail=f"severity must be one of {'|'.join(_SEVERITIES)}, got {severity!r}")
    if lang not in ("es", "en"):
        raise SdkError("usage_error", provider="es_cnmv_sanctions",
                       detail=f"lang must be es|en (the upstream mirror), got {lang!r}")
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="es_cnmv_sanctions",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    sweep = bool(all_pages or party or severity)
    r0 = _fetch(None, lang, cache=cache, no_cache=no_cache) if (page is None or sweep) else None
    if sweep:
        links = parse_page(r0["data"])[1]
        max_page = max(links) if links else 0
        rows = []
        for p in range(0, max_page + 1):
            rp = r0 if p == 0 else _fetch(p, lang, cache=cache, no_cache=no_cache)
            rows.extend(parse_page(rp["data"])[0])
        meta = r0
        pages = f"0..{max_page}"
    else:
        want = int(page) if page not in (None, "") else 0
        if want < 0:
            raise SdkError("usage_error", provider="es_cnmv_sanctions",
                           detail=f"page must be ≥0 (0-based), got {page!r}")
        r0 = r0 or _fetch(None, lang, cache=cache, no_cache=no_cache)
        links = parse_page(r0["data"])[1]
        max_page = max(links) if links else 0
        if want > max_page:
            raise SdkError("not_found", provider="es_cnmv_sanctions",
                           detail=f"page {want} is beyond the register tail (0..{max_page}; the "
                                  f"five-year statutory window slides — re-check page 0)")
        if want == 0:
            rows, meta = parse_page(r0["data"])[0], r0
        else:
            rp = _fetch(want, lang, cache=cache, no_cache=no_cache)
            rows, meta = parse_page(rp["data"])[0], rp
        pages = f"0..{max_page}"
    needle = str(party or "").strip().lower() or None
    sev_es = _SEV_ES.get(severity) if severity else None
    hits = [x for x in rows
            if (not needle or needle in x["resolution_text"].lower())
            and (not sev_es or sev_es in x["resolution_text"].lower())]
    return {
        "rows": hits[:size],
        "total_matched": len(hits),
        "scanned_rows": len(rows),
        "pages": pages,
        "max_page": max_page,
        "window": "rolling five-year statutory window (Ley del Mercado de Valores art. 32.3)",
        "params": {"page": page, "all_pages": sweep, "party": needle, "severity": severity or None,
                   "lang": lang, "limit": size},
        "_meta": meta,
    }
