"""fr_recherche — French annuaire-entreprises official aggregate search (recherche-entreprises.api.gouv.fr; etalab/DINUM, keyless).

2026-10-29 probed shape: GET /search?q=&page=&per_page=&etat_administratif=
(the API behind the etalab annuaire-entreprises search engine — api.insee.fr needs a key, this face is the keyless
search front door).
q takes company name / officer name / SIREN alike (BERNARD DE SAINT AFFRIQUE → 37 companies with mandates;
q=552032534 → total 1 exact); **per_page has an explicit wall of 1-25** (default 10; beyond it the upstream answers with a
self-describing French erreur — the local precheck saves one request); pagination is closed-form
page+total_pages+total_results. Rows are a rich 30-key shape: dirigeants with two slots (physique = person name +
year-month-granularity birth date; morale = {siren,denomination} company×company director edges)
+ finances{year:{ca,resultat_net}} + tva + siren_conserve (predecessor key) + complements (est_* flag family).
Rate limiting is real: burst-style 429s with plain-text bodies and intermittent connection resets — backing off gets
through, politeness tier 0.5 rps. TTL: 7 days (registry current values; date_mise_a_jour measured updating at T-1).
"""
from ..errors import SdkError

provider = {
    "id": "fr_recherche",
    "baseUrl": "https://recherche-entreprises.api.gouv.fr",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/search"},   # params: q/page/per_page/etat_administratif (A active / C ceased)
    },
    "ttl": {"search": 7 * 86400},
}


def search(q, *, page=None, per_page=10, etat_administratif=None, cache=None, no_cache=False):
    """→ {total_results, total_pages, page, per_page, results[], params, _meta}.
    q takes company name / officer name / SIREN alike (officer name = cross-company mandate search, SIREN = exact direct
    lookup); per_page upstream hard wall 1-25 (default 10, prechecked locally); etat_administratif A/C is a true filter.
    Zero hits is a legal answer (total_results:0)."""
    from ..transport import call_provider

    q = str(q or "").strip()
    if not q:
        raise SdkError("usage_error", provider="fr_recherche",
                       detail="search requires q (company name / officer name / SIREN)")
    pp = int(per_page if per_page is not None else 10)
    if not 1 <= pp <= 25:
        raise SdkError("usage_error", provider="fr_recherche",
                       detail=f"per_page upstream hard wall is 1-25 (got {pp}; default 10 — beyond the wall upstream answers with a French erreur)")
    params = {"q": q, "per_page": pp}
    if page is not None:
        pg = int(page)
        if pg < 1:
            raise SdkError("usage_error", provider="fr_recherche",
                           detail=f"page is 1-based (got {pg})")
        params["page"] = pg
    if etat_administratif is not None:
        ea = str(etat_administratif).strip().upper()
        if ea not in ("A", "C"):
            raise SdkError("usage_error", provider="fr_recherche",
                           detail=f"etat_administratif only accepts A (active) / C (ceased), got \"{etat_administratif}\"")
        params["etat_administratif"] = ea
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    return {"total_results": d.get("total_results"),
            "total_pages": d.get("total_pages"),
            "page": d.get("page"), "per_page": d.get("per_page"),
            "results": [_norm(x) for x in d.get("results") or []],
            "params": params, "_meta": r}


def _norm_dir(d):
    """dirigeants two slots: physique = person name + year-month-granularity birth date (public registry sense, no national
    id number); morale = siren+denomination (company×company director edge; the statutory auditor slot has the same shape)."""
    return {"type_dirigeant": d.get("type_dirigeant"),
            "nom": d.get("nom"), "prenoms": d.get("prenoms"),
            "date_de_naissance": d.get("date_de_naissance"),   # year-month granularity ("1964-12")
            "annee_de_naissance": d.get("annee_de_naissance"),
            "nationalite": d.get("nationalite"),
            "siren": d.get("siren"),                           # morale slot only
            "denomination": d.get("denomination"),
            "qualite": d.get("qualite")}


def _norm_etab(e):
    """etablissement card (shared by siege/matching_etablissements): keeps the master/geographic/activity core columns."""
    e = e or {}
    return {"siret": e.get("siret"), "est_siege": e.get("est_siege"),
            "ancien_siege": e.get("ancien_siege"),
            "etat_administratif": e.get("etat_administratif"),
            "adresse": e.get("adresse"), "code_postal": e.get("code_postal"),
            "libelle_commune": e.get("libelle_commune"), "departement": e.get("departement"),
            "region": e.get("region"), "latitude": e.get("latitude"), "longitude": e.get("longitude"),
            "nom_commercial": e.get("nom_commercial"), "liste_enseignes": e.get("liste_enseignes"),
            "activite_principale": e.get("activite_principale"),
            "date_creation": e.get("date_creation"),
            "date_debut_activite": e.get("date_debut_activite"),
            "date_fermeture": e.get("date_fermeture")}


def _norm(r):
    """Row projection, 30 keys: SIREN primary key + dirigeants two slots + finances yearly panel + tva + siren_conserve predecessor key."""
    fin = r.get("finances") or {}
    return {
        "siren": r.get("siren"),
        "nom_complet": r.get("nom_complet"), "nom_raison_sociale": r.get("nom_raison_sociale"),
        "sigle": r.get("sigle"),
        "etat_administratif": r.get("etat_administratif"),   # A active / C ceased
        "date_creation": r.get("date_creation"), "date_fermeture": r.get("date_fermeture"),
        "nature_juridique": r.get("nature_juridique"),       # legal form code (5599=SA)
        "categorie_entreprise": r.get("categorie_entreprise"),          # PME/ETI/GE
        "annee_categorie_entreprise": r.get("annee_categorie_entreprise"),
        "tranche_effectif_salarie": r.get("tranche_effectif_salarie"),
        "caractere_employeur": r.get("caractere_employeur"),
        "activite_principale": r.get("activite_principale"),           # NAF code
        "activite_principale_naf25": r.get("activite_principale_naf25"),
        "section_activite_principale": r.get("section_activite_principale"),
        "tva": (r.get("tva") or [None])[0],                  # "FR…" (the monthly corpus file lacks this column)
        "dirigeants": [_norm_dir(x) for x in r.get("dirigeants") or []],
        "finances": {y: {"ca": v.get("ca"), "resultat_net": v.get("resultat_net")}
                     for y, v in fin.items()},               # {year:{ca,resultat_net}}
        "siege": _norm_etab(r.get("siege")),
        "siren_conserve": r.get("siren_conserve"),           # predecessor SIREN (surviving key after a merger)
        "nombre_etablissements": r.get("nombre_etablissements"),
        "nombre_etablissements_ouverts": r.get("nombre_etablissements_ouverts"),
        "matching_etablissements": [_norm_etab(x) for x in r.get("matching_etablissements") or []],
        "complements": r.get("complements"),                 # est_* flag family + liste_finess etc. (passed through)
        "statut_diffusion": r.get("statut_diffusion"),       # O=public / P=partially protected (name and address redacted)
        "date_mise_a_jour": r.get("date_mise_a_jour"),
        "date_mise_a_jour_rne": r.get("date_mise_a_jour_rne"),
    }
