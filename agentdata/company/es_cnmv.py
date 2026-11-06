"""es_cnmv — CNMV entidades 正册 (Spanish securities-market licence register, www.cnmv.es; keyless).

One face (0.3.44; probed 2026-11-04, tmp/probe-es-cnmv/ le_0..le_13 + three detail samples;
research volume 册 240 es-cnmv-entidades-registros):

  * entities — the register of entities authorised/supervised by the CNMV, FOURTEEN categories
    behind one endpoint: GET /portal/consultas/listadoentidad.aspx?id=1&tipoent=<0..13> — one
    shot per category, server-rendered, no key, no pagination, no POST (te=10 carries an
    ASP.NET __VIEWSTATE shell but a plain GET already returns the whole list). 1,760 entities
    live 2026-11-04: te=0 securities firms 113 / 1 portfolio managers **0 (the SGC list moved
    to its own ListadoGestorasFTA page)** / 2 financial advisers 92 / 3 EEA investment firms
    with branch 46 / **4 EEA investment firms passported 812** / 5+6 non-EEA 1+11 / 7 Spanish
    credit entities 102 / 8+9 credit branches 50+1 / **10 EU credit entities passported 469** /
    11 EU credit subsidiaries passported **0 (empty category)** / 12 non-EU credit passported 3 /
    13 national financial advisers 60. The two 800-class pages are Spain's view of the European
    financial passport — the detail pages carry País de origen.

The register's own grammar, pinned from the evidence (le_*.bin):

  * the ROW is <li class="blocks-single"> — NOT a table (zero <tr>) and NOT a bare li sweep
    (936-5,243 li per page, 193 of them navigation); inside each row one <a href="…"> wraps a
    <span class="tit-small">NAME</span>. tit-small is 1:1 with rows on every category measured.
  * **the href IS the key**, and there are TEN (endpoint, tipo) kinds across the categories:
    esis.aspx?nif=<NIF> (national) / eafi.aspx?tipo=EAF / esisextranjerassuc.aspx?tipo=CSU|XSU /
    esisextranjeraslp.aspx?tipo=CLP|XLP / esisentcredito.aspx?tipo=ECN|SECC|SECE|ECCLP|ECELP /
    afn.aspx?tipo=AFN. The numero values are official register numbers, NOT enumerable —
    collect them from the list hrefs, never synthesize a walk.
  * **NIF double form**: the national list carries both dashed (A-83217281) and bare
    (B22526768) spellings — normalised here (de-hyphen, upper) for joins, raw form kept as a
    census fact. The NIF keyspace is shared with the CNMV sanctions register (legal 册 134,
    datosentidad.aspx) — roster↔sanctions is the licence-lifecycle join.
  * **the cookie banner occupies <h1>** on the big pages («Aviso de cookies» while te=4 holds
    812 rows) — the page title is read from <title>, never h1; the data verdict is the row
    count, not the banner.
  * case-sensitivity trap: /portal/Consultas.aspx 403s both capitalisations — the live path is
    /portal/consultas/ (lowercase c) exactly as configured here.
  * empty categories (te=1, te=11) return a normal page with a title and ZERO rows — a
    category-level emptiness, reported as such, never retried as an error.

Channel: plain GET HTML, no key, no CAPTCHA, no published rate window → polite 0.5 rps /
burst 2 (registry-search family posture). TTL 24h (register dumps move slowly). The three
detail page families (esis/esisextranjeraslp/esisentcredito, 150-223KB, keyless 200) are the
recipe's 二期 — this face carries each row's own detail href so the detail face can compose.
"""
import html
import re
import unicodedata

from ..transport import call_provider
from ..errors import SdkError

provider = {
    "id": "es_cnmv",
    "baseUrl": "https://www.cnmv.es",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # params: id (fixed 1), tipoent (0..13 — the category, from CATEGORIES)
        # accept=text: a 2xx HTML page is the expected payload, not a WAF challenge
        "list": {"path": "/portal/consultas/listadoentidad.aspx", "accept": "text",
                 "timeout": 90.0},
    },
    "ttl": {"list": 24 * 3600},
}

# the fourteen categories, slug -> tipoent (titles verbatim Spanish from the pages' own <title>)
CATEGORIES = {
    "securities_firms": 0,              # Sociedades y Agencias de Valores — 113
    "portfolio_managers": 1,            # Sociedades Gestoras de Cartera — 0 (moved to ListadoGestorasFTA)
    "financial_advisers": 2,            # Empresas de Asesoramiento Financiero (EAF) — 92
    "eea_investment_firms_branch": 3,   # ESI del EEE con Sucursal — 46
    "eea_investment_firms_passport": 4, # ESI del EEE en Libre Prestación — 812
    "non_eea_investment_firms_branch": 5,    # 1
    "non_eea_investment_firms_passport": 6,  # 11
    "spanish_credit_entities": 7,       # entidades de crédito españolas — 102
    "eu_credit_branches": 8,            # sucursales de entidades de crédito comunitarias — 50
    "non_eu_credit_branches": 9,        # 1
    "eu_credit_passport": 10,           # entidades de crédito comunitarias en libre prestación — 469
    "eu_credit_subsidiaries_passport": 11,   # 0 (empty category)
    "non_eu_credit_passport": 12,       # 3
    "national_financial_advisers": 13,  # EAF Nacional — 60
}

# (endpoint, tipo) -> one key-kind token; the href space measured across all fourteen categories
_KINDS = {
    ("esis", None): "nif",
    ("eafi", "EAF"): "eaf",
    ("esisextranjerassuc", "CSU"): "csu",
    ("esisextranjerassuc", "XSU"): "xsu",
    ("esisextranjeraslp", "CLP"): "clp",
    ("esisextranjeraslp", "XLP"): "xlp",
    ("esisentcredito", "ECN"): "ecn",
    ("esisentcredito", "SECC"): "secc",
    ("esisentcredito", "SECE"): "sece",
    ("esisentcredito", "ECCLP"): "ecclp",
    ("esisentcredito", "ECELP"): "ecelp",
    ("afn", "AFN"): "afn",
}

_ROW_RE = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>\s*<span[^>]*class="tit-small"[^>]*>(.*?)</span>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)


def _clean(s):
    """tit-small inner HTML → text: strip tags, unescape entities (&#243; ó …), NFKC, collapse."""
    txt = html.unescape(_TAG_RE.sub("", str(s or "")))
    return " ".join(unicodedata.normalize("NFKC", txt).split()) or None


def _norm_nif(v):
    """join-ready NIF: de-hyphen, strip, upper (the register carries dashed AND bare forms)."""
    s = unicodedata.normalize("NFKC", str(v or "")).strip().upper().replace("-", "").replace(" ", "")
    return s or None


def parse_list(body, category_slug, base="https://www.cnmv.es"):
    """the listadoentidad HTML → dict(page_title, rows, empty_category) — pure function.

    Row = the <a href> wrapping the tit-small span (1:1 with blocks-single li's on every
    category measured); the href IS the entity's key. A page with a <title> and zero rows is
    an EMPTY CATEGORY (te=1/te=11); a page with neither title nor rows has drifted.
    """
    if not isinstance(body, str) or not body.strip():
        raise SdkError("upstream_unavailable",
                       detail="es_cnmv list returned an empty body — the page shape drifted")
    tm = _TITLE_RE.search(body)
    page_title = " ".join(html.unescape(tm.group(1)).split()) if tm else None
    rows = []
    for href, inner in _ROW_RE.findall(body):
        name = _clean(inner)
        href = html.unescape(href)
        stem = href.split("?")[0].rsplit("/", 1)[-1].replace(".aspx", "")
        query = href.split("?", 1)[1] if "?" in href else ""
        tipo_m = re.search(r"[?&]tipo=(\w+)", "?" + query)
        tipo = tipo_m.group(1) if tipo_m else None
        kind = _KINDS.get((stem, tipo))
        nif = numero = None
        nif_form = None
        if stem == "esis":
            m = re.search(r"[?&]nif=([^&]+)", "?" + query)
            raw = m.group(1) if m else None
            if raw:
                nif = _norm_nif(raw)
                nif_form = "dashed" if "-" in raw else "bare"
        else:
            m = re.search(r"[?&]numero=([^&]+)", "?" + query)
            numero = m.group(1) if m else None
        rows.append({
            "name": name,
            "key_kind": kind,               # None = an endpoint/tipo pair off the measured map
            "nif": nif,                     # national entities only (normalised)
            "numero": numero,               # official register number (passport/branch families)
            "nif_form": nif_form,           # dashed | bare — the register's own double form
            "detail_path": href,            # the register's own detail link, verbatim
            "detail_url": base.rstrip("/") + "/" + href.lstrip("/"),
        })
    if not rows and not page_title:
        raise SdkError("upstream_unavailable",
                       detail="es_cnmv list page carries no title and no tit-small rows — "
                              "the page shape drifted (the capitalised /portal/Consultas.aspx "
                              "path 403s; the live path is lowercase /portal/consultas/)")
    return {"page_title": page_title, "rows": rows,
            "empty_category": bool(page_title and not rows)}


def entities_raw(*, category, name=None, nif=None, numero=None, limit=20, cache=None,
                 no_cache=False):
    """the roster face's raw core: one category GET + local scan (the upstream has no query
    surface beyond the category)."""
    slug = str(category or "").strip()
    if slug not in CATEGORIES:
        raise SdkError("usage_error",
                       detail=f"unknown category {category!r} — pick one of: "
                              + ", ".join(CATEGORIES))
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    if not 1 <= limit <= 100:
        raise SdkError("usage_error", detail="limit must be 1-100 (local slice wall)")
    tipoent = CATEGORIES[slug]
    res = call_provider(provider, "list", {"id": 1, "tipoent": tipoent},
                        cache=cache, no_cache=no_cache)
    parsed = parse_list(res["data"], slug)
    rows = parsed["rows"]

    nm = " ".join(unicodedata.normalize("NFKC", str(name or "")).casefold().split()) or None
    nf = _norm_nif(nif)
    nu = str(numero or "").strip() or None
    hits = [x for x in rows
            if (not nm or (x["name"] and nm in unicodedata.normalize("NFKC", x["name"]).casefold()))
            and (not nf or x["nif"] == nf)
            and (not nu or x["numero"] == nu)]

    kinds = {}
    dashed = bare = unmapped = 0
    for x in rows:
        kinds[x["key_kind"]] = kinds.get(x["key_kind"], 0) + 1
        if x["nif_form"] == "dashed":
            dashed += 1
        elif x["nif_form"] == "bare":
            bare += 1
        if x["key_kind"] is None:
            unmapped += 1
    census = {
        "category": slug,
        "tipoent": tipoent,
        "page_title": parsed["page_title"],
        "rows_in_category": len(rows),
        "empty_category": parsed["empty_category"],
        "key_kinds": kinds,
        "nif_dashed": dashed,
        "nif_bare": bare,
        "unmapped_key_kinds": unmapped,
    }
    return {
        "rows": hits[:limit],
        "total_matched": len(hits),
        "scanned_rows": len(rows),
        "census": census,
        "limit_applied": limit,
        "params": {"category": slug, "name": name, "nif": nif, "numero": numero},
        "_meta": res,
    }
