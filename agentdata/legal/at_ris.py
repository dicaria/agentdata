"""at_ris — Austrian RIS Rechtsinformationssystem OGD API v2.6 (data.bka.gv.at; Bundeskanzleramt, keyless, CC BY 4.0).

The legal domain's first AT face (2026-11-05). Three hosts are split: www.ris.bka.gv.at is the
MyraCloud-WAF web shell (never touched), data.bka.gv.at is this keyless JSON API, ogd.ris.bka.gv.at
serves full-text documents (the API rows already carry the URLs — this module is metadata +
coordinates only, the 1.45M-document corpus body rides the batch line).

Judikatur (case law, ~1.01M documents across 16 court shards, census 2026-11-03 researcher round +
2026-11-05 live): Vwgh 357,753→357,857 (live drift = daily refresh) / Bvwg 292,078 / Justiz 138,516
(OGH/OLG/LG/BG four court levels merged — the default shard) / Lvwg 78,286 / AsylGH 53,113 / Uvs
25,939 / Vfgh 24,177 / Normenliste 14,676 / Verg 8,143 / Dok 4,873 / Ubas 4,052 / Pvak 2,550 /
Dsk 1,891 / Gbk 1,067 / Bks 745 / Umse 742. Bundesrecht?Applikation=BrKons = 442,058 consolidated
federal-law documents (Kundmachungsorgan/BGBl citation axes + in-force/out-of-force dates).

Probed truths: only ?page-style params are honoured via exact names — Applikation is CASE-SENSITIVE
(Vwgh 200s; VWGH answers HTTP 200 with an OgdSearchResult.Error body whose Message self-exposes the
whole schema dictionary — the local closed-set wall saves the request and quotes the posture);
DokumenteProSeite is enumerated to the default 20 only (3/10/50/100 all fail schema validation —
page size is pinned, --limit is a local slice); Seitennummer is the page key; Suchworte is full
text (GmbH → 1,208 Rechtssatz documents); Geschaeftszahl matches the squeezed-joined cell
("2 Ob 52/16k" → 27 rows of the Rechtssatz family that aggregates the case); EntscheidungsdatumVon/
Bis are the date window (YYYY-MM-DD). Beyond the last page the upstream answers HTTP 500 "Die
Seitennummer ist höher als die Anzahl der verfügbaren Seiten". '+' and '%20' encode spaces
identically. The JSON is a XML→JSON cast: single values arrive as {"item": v}, lists as
{"item": [..]}, numbers-in-strings in Hits {"@pageNumber","@pageSize","#text"}.
"""
from ..errors import SdkError

provider = {
    "id": "at_ris",
    "baseUrl": "https://data.bka.gv.at",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "judikatur": {"path": "/ris/api/v2.6/Judikatur", "accept": "json"},
        "bundesrecht": {"path": "/ris/api/v2.6/Bundesrecht", "accept": "json"},
    },
    "ttl": {"judikatur": 86400, "bundesrecht": 86400},
}

# Court shards, exact upstream case (first-upper-rest-lower mostly; AsylGH irregular) — the
# researcher's 2026-11-03 census round (a11 probes echo Applikation verbatim) + 2026-11-05 live.
JUDIKATUR_APPS = {
    "Justiz": 138516,   # OGH/OLG/LG/BG ordinary courts merged — the default shard
    "Vwgh": 357753, "Bvwg": 292078, "Lvwg": 78286, "AsylGH": 53113,
    "Uvs": 25939, "Vfgh": 24177, "Normenliste": 14676, "Verg": 8143,
    "Dok": 4873, "Ubas": 4052, "Pvak": 2550, "Dsk": 1891, "Gbk": 1067,
    "Bks": 745, "Umse": 742,
}
STATUTE_TOTAL = 442058   # Bundesrecht/BrKons, 2026-11-03


def _items(node):
    """XML→JSON cast: a wrapped {"item": v} — single value → [v], list stays a list, absent → []."""
    if not isinstance(node, dict):
        return []
    v = node.get("item")
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _dates(date_from, date_to):
    out = {}
    for key, val in (("EntscheidungsdatumVon", date_from), ("EntscheidungsdatumBis", date_to)):
        if val is None:
            continue
        s = str(val).strip()
        if len(s) != 10 or s[4] != "-" or s[7] != "-" or not s.replace("-", "").isdigit():
            raise SdkError("usage_error", provider="at_ris",
                           detail=f"{key} wants YYYY-MM-DD (got \"{val}\")")
        import datetime
        try:
            datetime.date.fromisoformat(s)   # calendar range: 2026-13-01 is not a date either
        except ValueError:
            raise SdkError("usage_error", provider="at_ris",
                           detail=f"{key} is not a real calendar date (got \"{s}\")")
        out[key] = s
    if len(out) == 2 and out["EntscheidungsdatumVon"] > out["EntscheidungsdatumBis"]:
        raise SdkError("usage_error", provider="at_ris",
                       detail=f"date_from ({date_from}) is after date_to ({date_to})")
    return out


def _search(op, params, cache, no_cache):
    """One API call + the Error-body wall: upstream answers HTTP 200 with OgdSearchResult.Error
    for bad param shapes (soap:Client schema validation, Message = the schema dictionary)."""
    from ..transport import call_provider
    r = call_provider(provider, op, params, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    og = d.get("OgdSearchResult") or {}
    if "Error" in og:
        err = og["Error"] or {}
        msg = str(err.get("Message") or "")[:220]
        raise SdkError("usage_error", provider="at_ris",
                       detail=f"upstream rejected the parameter shape (soap:Client schema validation, "
                              f"Applikation={err.get('Applikation')!r}): {msg}")
    res = og.get("OgdDocumentResults") or {}
    hits = res.get("Hits") or {}
    refs = res.get("OgdDocumentReference") or []
    try:
        total = int(hits.get("#text"))
    except (TypeError, ValueError):
        total = None
    try:
        page_echo = int(hits.get("@pageNumber"))
    except (TypeError, ValueError):
        page_echo = None
    return {"total": total, "page_echo": page_echo, "page_size": 20, "refs": refs, "_meta": r}


def judgments_raw(court="Justiz", *, q=None, case_number=None, norm=None,
                  date_from=None, date_to=None, page=1, limit=20, cache=None, no_cache=False):
    """→ {court, page, page_size, total, rows[], census{}, params, _meta}.
    Court shards are the 16-value exact-case closed set (wrong case would be answered upstream by
    an Error body quoting the schema dictionary); page size is pinned at 20 upstream (--limit is a
    local slice); rows are the Metadaten projection with ECLI verbatim; Entscheidungstexte long
    annotations are dropped — each text keeps its coordinates (Geschaeftszahl/DokumentUrl).
    Beyond the last page (ceil(total/20)) the upstream answers HTTP 500 "Die Seitennummer ist
    höher als die Anzahl der verfügbaren Seiten" — retried then surfaced as upstream_unavailable;
    read total from any response and stay inside the window."""
    app = str(court or "Justiz").strip() or "Justiz"
    if app not in JUDIKATUR_APPS:
        raise SdkError("usage_error", provider="at_ris",
                       detail=f"court is the exact-case 16-value closed set {sorted(JUDIKATUR_APPS)} "
                              f"(got \"{court}\" — e.g. Vwgh answers 200, VWGH is rejected upstream with a "
                              f"schema-validation Error body; the boolean-flag form ?Vwgh=true is silently "
                              f"ignored and quietly answers the Justiz shard)")
    try:
        pg = int(page)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="at_ris", detail=f"page must be an integer (got {page!r})")
    if pg < 1:
        raise SdkError("usage_error", provider="at_ris",
                       detail=f"page is 1-based (got {pg})")
    try:
        lm = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="at_ris", detail=f"limit must be an integer (got {limit!r})")
    if not 1 <= lm <= 100:
        raise SdkError("usage_error", provider="at_ris",
                       detail=f"limit is a local slice, 1-100 (got {lm}; the upstream page is pinned at 20 — "
                              f"DokumenteProSeite=3/10/50/100 all fail schema validation)")
    params = {"Applikation": app, "Seitennummer": pg}
    q = str(q or "").strip() or None
    if q:
        params["Suchworte"] = q
    gz = str(case_number or "").strip() or None
    if gz:
        params["Geschaeftszahl"] = gz
    nm = str(norm or "").strip() or None
    if nm:
        params["Norm"] = nm
    params.update(_dates(date_from, date_to))
    out = _search("judikatur", params, cache, no_cache)
    rows = [_judgment_row(x) for x in out["refs"]]
    return {"court": app, "page": out["page_echo"] if out["page_echo"] is not None else pg,
            "page_size": out["page_size"], "total": out["total"], "rows": rows[:lm],
            "census": {"corpus_apps": 16, "corpus_documents": 1008601,
                       "shard_census_2026_11_03": dict(JUDIKATUR_APPS)},
            "params": params, "_meta": out["_meta"]}


def statutes_raw(*, q=None, page=1, limit=20, cache=None, no_cache=False):
    """→ {page, page_size, total, rows[], census{}, params, _meta}.
    Bundesrecht?Applikation=BrKons — the consolidated federal-law shard (442,058 documents; the
    only Bundesrecht sub-app, fixed here). NOR id + BGBl citation axes + in-force/out-of-force
    dates; Ausserkrafttretensdatum is present-only (in-force norms carry none). Beyond the last
    page the upstream answers the same HTTP-500 page wall as Judikatur."""
    try:
        pg = int(page)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="at_ris", detail=f"page must be an integer (got {page!r})")
    if pg < 1:
        raise SdkError("usage_error", provider="at_ris", detail=f"page is 1-based (got {pg})")
    try:
        lm = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="at_ris", detail=f"limit must be an integer (got {limit!r})")
    if not 1 <= lm <= 100:
        raise SdkError("usage_error", provider="at_ris",
                       detail=f"limit is a local slice, 1-100 (got {lm}; the upstream page is pinned at 20)")
    params = {"Applikation": "BrKons", "Seitennummer": pg}
    q = str(q or "").strip() or None
    if q:
        params["Suchworte"] = q
    out = _search("bundesrecht", params, cache, no_cache)
    rows = [_statute_row(x) for x in out["refs"]]
    return {"page": out["page_echo"] if out["page_echo"] is not None else pg,
            "page_size": out["page_size"], "total": out["total"], "rows": rows[:lm],
            "census": {"shard": "BrKons", "corpus_documents_2026_11_03": STATUTE_TOTAL},
            "params": params, "_meta": out["_meta"]}


def _judgment_row(ref):
    """Metadaten projection: Technisch/Allgemein/Judikatur with the Justiz extras present-only;
    ECLI verbatim; Entscheidungstexte keep coordinates only (the long Beisatz annotations ride the
    DokumentUrl, not this face)."""
    md = ((ref or {}).get("Data") or {}).get("Metadaten") or {}
    tech = md.get("Technisch") or {}
    gen = md.get("Allgemein") or {}
    jd = md.get("Judikatur") or {}
    just = jd.get("Justiz") or {}
    gz_raw = jd.get("Geschaeftszahl")
    gz_items = _items(gz_raw) if isinstance(gz_raw, dict) else ([gz_raw] if gz_raw else [])
    gz = []
    for cell in gz_items:
        gz.extend(p.strip() for p in str(cell).split(";") if p.strip())
    texts = []
    for t in _items(just.get("Entscheidungstexte")):
        texts.append({"geschaeftszahl": t.get("Geschaeftszahl"), "dokumenttyp": t.get("Dokumenttyp"),
                      "gericht": t.get("Gericht"), "entscheidungsdatum": t.get("Entscheidungsdatum"),
                      "dokument_url": t.get("DokumentUrl")})
    return {"ris_id": tech.get("ID"), "organ": tech.get("Organ"),
            "dokumenttyp": jd.get("Dokumenttyp"),
            "geschaeftszahlen": gz,
            "normen": [str(n) for n in _items(jd.get("Normen"))],
            "entscheidungsdatum": jd.get("Entscheidungsdatum"),
            "ecli": jd.get("EuropeanCaseLawIdentifier"),
            "gericht": just.get("Gericht"),
            "rechtsgebiete": [str(r) for r in _items(just.get("Rechtsgebiete"))],
            "rechtssatznummern": [str(r) for r in _items(just.get("Rechtssatznummern"))],
            "texts": texts,
            "veroeffentlicht": gen.get("Veroeffentlicht"), "geaendert": gen.get("Geaendert"),
            "dokument_url": gen.get("DokumentUrl")}


def _statute_row(ref):
    """Bundesrecht/BrKons projection: NOR id + BGBl citation axes + validity window (out-of-force
    date present-only) + ELI canonical link."""
    md = ((ref or {}).get("Data") or {}).get("Metadaten") or {}
    tech = md.get("Technisch") or {}
    gen = md.get("Allgemein") or {}
    br = (md.get("Bundesrecht") or {}).get("BrKons") or {}
    md_br = md.get("Bundesrecht") or {}
    return {"nor_id": tech.get("ID"), "organ": tech.get("Organ"),
            "kurztitel": md_br.get("Kurztitel"), "titel": md_br.get("Titel"),
            "eli": md_br.get("Eli"),
            "kundmachungsorgan": br.get("Kundmachungsorgan"),
            "typ": br.get("Typ"), "dokumenttyp": br.get("Dokumenttyp"),
            "artikel_paragraph_anlage": br.get("ArtikelParagraphAnlage"),
            "paragraphnummer": br.get("Paragraphnummer"),
            "stammnorm_publikationsorgan": br.get("StammnormPublikationsorgan"),
            "stammnorm_bgblnummer": br.get("StammnormBgblnummer"),
            "novellen_beziehung": br.get("NovellenBeziehung"),
            "novellen_bgblnummer": br.get("NovellenBgblnummer"),
            "inkrafttretensdatum": br.get("Inkrafttretensdatum"),
            "ausserkrafttretensdatum": br.get("Ausserkrafttretensdatum"),
            "geaendert": gen.get("Geaendert"),
            "dokument_url": gen.get("DokumentUrl")}
