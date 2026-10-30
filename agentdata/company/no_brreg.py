"""no_brreg — Norwegian Enhetsregisteret (Brønnøysund registry master) provider (HAL JSON front door; keyless).

2026-10-29 probed shape: the real param is **?navn=** (?name= gives 400 valideringsfeil — the parameter takes
the Norwegian spelling); pagination ?size=&page= (0-based) → HAL page{number,size,totalElements,totalPages};
single record GET /enheter/{orgnr} (404 = no such number); roles face GET /enheter/{orgnr}/roller →
rollegrupper[] (DAGL CEO / STYR board / REVI auditor groups), rows = person{navn{fornavn,etternavn},
fodselsdato, erDoed} or enhet{organisasjonsnummer} (auditors are often companies) + the avregistrert retirement flag.
PII line: the public face exposes only birth dates, no national id numbers (fnr is not on this face) — name + birth
date are collectible.
TTL: enheter/enhet 7 days (current-value queries) / roller 30 days (role sequences change slowly); politeness tier 0.5 rps.
"""
import re

from ..errors import SdkError

provider = {
    "id": "no_brreg",
    "baseUrl": "https://data.brreg.no/enhetsregisteret/api",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "enheter": {"path": "/enheter"},                                              # params: navn/size/page (query)
        "enhet": {"path": "/enheter/{organisasjonsnummer}", "notFound": [404]},       # params: organisasjonsnummer (path)
        "roller": {"path": "/enheter/{organisasjonsnummer}/roller", "notFound": [404]},  # same (roles face)
    },
    "ttl": {"enheter": 7 * 86400, "enhet": 7 * 86400, "roller": 30 * 86400},
}

_ORGNR_RE = re.compile(r"^\d{9}$")


def _orgnr(v):
    norm = str(v or "").replace(" ", "").strip()
    if not _ORGNR_RE.match(norm):
        raise SdkError("usage_error", provider="no_brreg",
                       detail=f"organisasjonsnummer must be 9 digits (Norwegian organization number), got \"{v}\"")
    return norm


def _norm_enhet(e):
    """Full 40-key record → due-diligence core projection (industry/flags/address/headcount); historical names passed through."""
    addr = e.get("forretningsadresse") or {}
    return {
        "organisasjonsnummer": e.get("organisasjonsnummer"),
        "navn": e.get("navn"),
        "organisasjonsform": {"kode": (e.get("organisasjonsform") or {}).get("kode"),
                              "beskrivelse": (e.get("organisasjonsform") or {}).get("beskrivelse")},
        "naeringskode1": {"kode": (e.get("naeringskode1") or {}).get("kode"),
                          "beskrivelse": (e.get("naeringskode1") or {}).get("beskrivelse")},  # NACE main industry
        "antall_ansatte": e.get("antallAnsatte"),
        "registreringsdato_enhetsregisteret": e.get("registreringsdatoEnhetsregisteret"),
        "stiftelsesdato": e.get("stiftelsesdato"),
        "hjemmeside": e.get("hjemmeside"),
        "konkurs": e.get("konkurs"),
        "under_avvikling": e.get("underAvvikling"),
        "under_tvangsavvikling": e.get("underTvangsavviklingEllerTvangsopplosning"),
        "registrert_i_mva_registeret": e.get("registrertIMvaregisteret"),   # VAT register flag
        "registrert_i_foretaksregisteret": e.get("registrertIForetaksregisteret"),
        "overordnet_enhet": e.get("overordnetEnhet"),                        # parent org number (subsidiary edge)
        "forretningsadresse": {"adresse": (addr.get("adresse") or [None])[0],
                               "poststed": addr.get("poststed"), "kommune": addr.get("kommune"),
                               "landkode": addr.get("landkode")},
        "historiske_navn": e.get("historiskeNavn"),                          # former names passed through (upstream shape)
    }


def search_enheter(navn, *, page=0, size=20, cache=None, no_cache=False):
    """→ {enheter[], page{}, params, _meta}; name search (navn verbatim channel; size/page 0-based HAL pagination)."""
    from ..transport import call_provider

    q = str(navn or "").strip()
    if not q:
        raise SdkError("usage_error", provider="no_brreg", detail="search requires navn (name search, the ?navn= verbatim channel)")
    p, s = max(0, int(page or 0)), min(max(1, int(size or 20)), 100)  # 1-100 = our politeness cap
    r = call_provider(provider, "enheter", {"navn": q, "page": p, "size": s},
                      cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    rows = [_norm_enhet(e) for e in (d.get("_embedded") or {}).get("enheter") or []]
    pg = d.get("page") or {}
    return {"enheter": rows,
            "page": {"number": pg.get("number"), "size": pg.get("size"),
                     "total_elements": pg.get("totalElements"), "total_pages": pg.get("totalPages")},
            "params": {"navn": q, "page": p, "size": s}, "_meta": r}


def get_enhet(organisasjonsnummer, *, cache=None, no_cache=False):
    """→ {enhet, _meta}; single record by 9-digit org number (404 = no such number, honestly reported)."""
    from ..transport import call_provider

    v = _orgnr(organisasjonsnummer)
    r = call_provider(provider, "enhet", {"organisasjonsnummer": v}, cache=cache, no_cache=no_cache)
    return {"enhet": _norm_enhet(r["data"] or {}), "_meta": r}


def get_roller(organisasjonsnummer, *, cache=None, no_cache=False):
    """→ {organisasjonsnummer, rollegrupper[], _meta}; roles face (DAGL/STYR/REVI groups).
    Person rows = name + birth date (no national id number on the public face); corporate rows (auditors, typically) =
    org number. avregistrert=true = retired."""
    from ..transport import call_provider

    v = _orgnr(organisasjonsnummer)
    r = call_provider(provider, "roller", {"organisasjonsnummer": v}, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    groups = [{
        "type_kode": (g.get("type") or {}).get("kode"),
        "type_beskrivelse": (g.get("type") or {}).get("beskrivelse"),
        "sist_endret": g.get("sistEndret"),
        "roller": [{
            "kode": (m.get("type") or {}).get("kode"),
            "beskrivelse": (m.get("type") or {}).get("beskrivelse"),
            "person": _person(m.get("person")),
            "enhet_organisasjonsnummer": ((m.get("enhet") or {}).get("organisasjonsnummer")),
            "avregistrert": m.get("avregistrert"),
            "rekkefolge": m.get("rekkefolge"),          # order within the group
        } for m in g.get("roller") or []],
    } for g in d.get("rollegrupper") or []]
    return {"organisasjonsnummer": v, "rollegrupper": groups, "_meta": r}


def _person(p):
    if not p:
        return None
    navn = p.get("navn") or {}
    full = " ".join(x for x in (navn.get("fornavn"), navn.get("etternavn")) if x) or None
    return {"navn": full, "fodselsdato": p.get("fodselsdato"), "er_doed": p.get("erDoed")}
