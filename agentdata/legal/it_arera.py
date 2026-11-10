"""it_arera — Italian ARERA regulated-sector decision register (www.arera.it atti e provvedimenti; keyless).

legal regulatory-decisions face (0.3.51; admitted from research 册 281 it-arera-provvedimenti,
probed live 2026-11-09, tmp/probe-sdk0350/l5/ p03). ARERA (Autorità di Regolazione per Energia
Reti e Ambiente) regulates Italy's five networks — electricity, gas, water, waste, district
heating — and its TYPO3 decision library spans 1996→today (1,560 pages × 15,599 documents live
2026-11-09, up +3 from the 2026-11-05 recipe probe; the pager is the count: "Numero pagine:
<b>1560</b> per <b>15599 risultati</b>").

GET query surface: anno + numero + tipologia + settore (+ pagina, 10 documents per page) — all
optional, all combinable, and the single-document form is deterministic (anno=2022 & numero=312
& tipologia=Delibera answers exactly one card, verified live). Walls are local:
tipologia is the register's own ten-word vocabulary (measured door-by-door in the recipe probe:
Delibera 11,851 / Determina 2,125 / Consultazione 1,056 / Parere 227 / Memoria 174 / Relazione
59 / Rapporto 41 / Segnalazione 36 / Altro 27 — exact match, not a prefix game), anno is the
register's floor 1996→current year (the filter dropdown carries 32 options, no gap years).
The hidden settore field passes through verbatim (its code space is the form's own, unpinned —
the sigla's sector letter rides every row anyway: E electricity / R waste / gas / idr water /
eel energy / com communications-era files).

Rows are the server-rendered list cards: detail path (the /dettaglio/<YY>/<NNN>-<YY> anchor),
tipologia, publication date DD/MM/YYYY verbatim, sigla "NNN/YYYY/SETTORE" (the register's hard
key), and the oggetto subject line. The PDF path is NOT assembled from the sigla — the
fileadmin naming drifts by era (2026: 398-2026-A.pdf; 1996: 3-96.pdf) — the detail page carries
the real paths (out of SDK scope; the face ships the detail anchor).
No gate, no WAF (bare TYPO3 — cleaner than ARCEP/CRE, the 册 277 cousins). 0.5/2 polite, TTL 12h.
"""
import html
import re

provider = {
    "id": "it_arera",
    "baseUrl": "https://www.arera.it",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "list": {"path": "/atti-e-provvedimenti", "accept": "text", "timeout": 60.0},
    },
    "ttl": {"list": 12 * 3600},
}

# The register's own tipologia vocabulary (recipe door-by-door counts, 2026-11-05; exact match)
TIPOLOGIE = ("Delibera", "Determina", "Consultazione", "Parere", "Memoria",
             "Relazione", "Rapporto", "Segnalazione", "Altro")
ANNO_FLOOR = 1996

_CARD_RE = re.compile(r'<a id="atto" href="([^"]+)">(.*?)</a>', re.S)
_TIP_RE = re.compile(r"title-lista-atti[^>]*>\s*([A-Za-z]+)")
_DATE_RE = re.compile(r"data-atto\">([\d/]+)")
_SIGLA_RE = re.compile(r"sigla-atto\">([^<]+)")
_OGGETTO_RE = re.compile(r"testo-atto\">\s*<p class=\"testo-atto\">([^<]+)")
_COUNT_RE = re.compile(r"Numero pagine:\s*<b>(\d+)</b>\s*per\s*<b>([\d.]+)")


def list_raw(anno=None, numero=None, tipologia=None, settore=None, *, page=1,
             cache=None, no_cache=False):
    """→ {total_pages, total_results, page, count, rows[], params, _meta}.

    All filters optional and combinable; an all-empty query is the register's own default
    listing (newest first). rows carry detail (the site-relative anchor — prefix
    https://www.arera.it), tipologia, date (DD/MM/YYYY verbatim), sigla and oggetto.
    """
    import datetime
    from ..errors import SdkError
    from ..transport import call_provider

    params = {}
    if anno is not None and str(anno).strip():
        try:
            a = int(str(anno).strip())
        except ValueError:
            raise SdkError("usage_error", provider="it_arera",
                           detail=f"anno must be an integer year, got {anno!r}")
        if a < ANNO_FLOOR or a > datetime.date.today().year:
            raise SdkError("usage_error", provider="it_arera",
                           detail=f"anno must be {ANNO_FLOOR}→{datetime.date.today().year} "
                                  f"(the register's own dropdown span), got {a}")
        params["anno"] = str(a)
    if numero is not None and str(numero).strip():
        params["numero"] = str(numero).strip()
    if tipologia is not None and str(tipologia).strip():
        t = str(tipologia).strip()
        if t not in TIPOLOGIE:
            raise SdkError("usage_error", provider="it_arera",
                           detail=f"tipologia must be one of the register's own ten-value "
                                  f"vocabulary {', '.join(TIPOLOGIE)} (exact match), got '{t}'")
        params["tipologia"] = t
    if settore is not None and str(settore).strip():
        params["settore"] = str(settore).strip()
    p = int(page) if page is not None else 1
    if p < 1:
        raise SdkError("usage_error", provider="it_arera", detail=f"page is 1-based, got {page!r}")
    params["pagina"] = str(p)

    r = call_provider(provider, "list", params, cache=cache, no_cache=no_cache)
    body = r["data"] or ""
    if not isinstance(body, str) or "<html" not in body[:400].lower():
        raise SdkError("upstream_unavailable", provider="it_arera",
                       detail="the list endpoint answered non-HTML (shape drift or maintenance)")

    total_pages = total_results = None
    m = _COUNT_RE.search(body)
    if m:
        total_pages = int(m.group(1))
        total_results = int(m.group(2).replace(".", ""))

    rows = []
    for am in _CARD_RE.finditer(body):
        block = am.group(2)
        tip = _TIP_RE.search(block)
        date = _DATE_RE.search(block)
        sigla = _SIGLA_RE.search(block)
        ogg = _OGGETTO_RE.search(block)
        rows.append({
            "detail": am.group(1),
            "tipologia": tip.group(1) if tip else None,
            "date": date.group(1) if date else None,
            "sigla": sigla.group(1).strip() if sigla else None,
            "oggetto": html.unescape(ogg.group(1)).strip() if ogg else None,
        })

    return {"total_pages": total_pages, "total_results": total_results, "page": p,
            "count": len(rows), "rows": rows, "params": params, "_meta": r}
