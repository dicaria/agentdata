"""fr_regafi — French ACPR financial-sector register (regafi.fr Opendatasoft Explore API v2.1; keyless).

company qualification face pair (0.3.53; admitted from research 册 113 fr-regafi-finance-licences,
probed live 2026-11-10, tmp/probe-sdk0352/). Regafi is the official register of financial agents
kept by the ACPR (Autorité de Contrôle Prudentiel et de Résolution) — the regafi.fr React/huwise
shell's real backend is the ODS Explore API v2.1, fully open. Two datasets ship as two ops:

- prd-banque-entites 25,890 rows (live 2026-11-10; the recipe probe counted 25,693 on 11-02 —
  the register grows): the supervised-entity roster. id_referentiel is the official key;
  lei + siren are the dual hard keys (SIREN joins the FR company master directly, LEI joins
  GLEIF); id_entite_parente / denomination_entite_parente carry the parent edge; nom_commerciaux
  rides as a JSON string (renaming history); categorie is multi-valued (24-value vocabulary,
  facet-measured: Agent PSP 22,485 / Établissement de Crédit 941 / Entreprise d'Investissement
  1,009 / Établissement de Monnaie Électronique 320 / Etablissement de paiement 584 …).
- prd-banque-autorisations 31,107 rows: the per-authorisation timeline (id_autorisation key,
  id_referentiel foreign key into entities). date_debut runs 1946→today (the row probed carries
  1977-05-27); nature_autorisation is a seven-word vocabulary (Agrément / Autorisation /
  Habilitation / Enregistrement / Approbation / Inscription liste / Exemption d'agrément);
  situation ∈ {ACTIF, MANDAT} (facet-measured closed pair); the *_json columns carry the
  per-service authorisation blocks with their own date_debut (cautions réglementées, services
  de paiement, cryptos …) — parsed in place when they are JSON strings.

ODSQL where assembly is LOCAL and additive (field="value" equality terms joined with AND, plus
search(denomination, …) for the name channel); values containing a double quote are refused
(honest wall — never interpolated around). limit is the ODS v2.1 ceiling 100; total_count is
echoed by the API and passed through verbatim. No gate, no WAF (honest agentdata UA + direct
egress = 200, pinned live 2026-11-10). 0.5/2 polite, TTL 24h (register-refresh posture).
"""
import json

provider = {
    "id": "fr_regafi",
    "baseUrl": "https://regafi.fr",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "entities": {"path": "/api/explore/v2.1/catalog/datasets/prd-banque-entites/records",
                     "timeout": 30.0},
        "authorisations": {"path": "/api/explore/v2.1/catalog/datasets/prd-banque-autorisations/records",
                           "timeout": 30.0},
    },
    "ttl": {"entities": 24 * 3600, "authorisations": 24 * 3600},
}

# facet-measured 2026-11-10 (group_by); situation is a closed pair, nature is the register's
# own seven-word vocabulary — both wallable; entities categorie stays open (24 values and
# the ACPR adds regimes — pass-through verbatim)
SITUATIONS = ("ACTIF", "MANDAT")
NATURES = ("Agrément", "Autorisation", "Habilitation", "Enregistrement",
           "Approbation", "Inscription liste", "Exemption d'agrément")


def _term(field, value, *, quoted=True):
    from ..errors import SdkError
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if '"' in v:
        raise SdkError("usage_error", provider="fr_regafi",
                       detail=f"{field} must not contain double quotes (the ODSQL literal is assembled locally), got {value!r}")
    return f'{field}="{v}"' if quoted else f"{field}={v}"


def _limit_offset(limit, offset):
    from ..errors import SdkError
    size = 20
    if limit is not None:
        try:
            size = int(limit)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="fr_regafi",
                           detail=f"limit must be an integer 1-100, got {limit!r}")
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="fr_regafi",
                       detail=f"limit must be 1-100 (the ODS Explore v2.1 ceiling), got {limit!r}")
    off = 0
    if offset is not None:
        try:
            off = int(offset)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="fr_regafi",
                           detail=f"offset must be an integer >=0, got {offset!r}")
    if off < 0:
        raise SdkError("usage_error", provider="fr_regafi", detail=f"offset must be >=0, got {offset!r}")
    return size, off


def _parse_json_strings(row):
    """ODS serialises nested objects as JSON strings in *_json / cib / nom_commerciaux / evenements —
    parse them in place (the key keeps its upstream name, the value becomes the object it names)."""
    for k, v in list(row.items()):
        if isinstance(v, str) and v[:1] in ("{", "["):
            try:
                row[k] = json.loads(v)
            except ValueError:
                pass
    return row


def _call(op, params, cache, no_cache):
    from ..errors import SdkError
    from ..transport import call_provider
    r = call_provider(provider, op, params, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    if not isinstance(doc, dict) or "results" not in doc:
        raise SdkError("upstream_unavailable", provider="fr_regafi",
                       detail="the ODS Explore API answered an unexpected shape (no results key — maintenance or shape drift)")
    return {"total_count": doc.get("total_count"), "count": len(doc["results"]),
            "rows": [_parse_json_strings(x) for x in doc["results"]], "_meta": r}


def entities_raw(siren=None, lei=None, categorie=None, pays=None, q=None,
                 *, limit=20, offset=0, cache=None, no_cache=False):
    """→ {total_count, count, rows[], params, _meta}. All filters optional and combinable;
    siren/lei are exact-equality lookups (the dual hard keys), categorie/pays exact terms
    (categorie is multi-valued upstream — an OR membership), q is full-text over denomination."""
    terms = []
    t = _term("siren", siren)
    if t:
        terms.append(t)
    t = _term("lei", lei)
    if t:
        terms.append(t)
    t = _term("categorie", categorie)
    if t:
        terms.append(t)
    t = _term("pays", pays)
    if t:
        terms.append(t)
    qs = str(q or "").strip()
    if qs:
        from ..errors import SdkError
        if '"' in qs:
            raise SdkError("usage_error", provider="fr_regafi",
                           detail=f"q must not contain double quotes (assembled into search(denomination, …) locally), got {q!r}")
        terms.append(f'search(denomination, "{qs}")')
    size, off = _limit_offset(limit, offset)
    params = {"limit": size, "offset": off}
    if terms:
        params["where"] = " AND ".join(terms)
    out = _call("entities", params, cache, no_cache)
    out["params"] = params
    return out


def authorisations_raw(id_referentiel=None, categorie=None, nature=None, situation=None,
                       *, limit=20, offset=0, cache=None, no_cache=False):
    """→ {total_count, count, rows[], params, _meta}. id_referentiel joins the entities op (the
    register's own key, unquoted integer term); nature/situation are the register's own closed
    vocabularies (facet-measured, exact match); categorie passes through verbatim."""
    from ..errors import SdkError
    terms = []
    if id_referentiel is not None and str(id_referentiel).strip():
        try:
            ir = int(str(id_referentiel).strip())
        except ValueError:
            raise SdkError("usage_error", provider="fr_regafi",
                           detail=f"id_referentiel must be an integer (the register's own entity key), got {id_referentiel!r}")
        terms.append(f"id_referentiel={ir}")
    t = _term("categorie", categorie)
    if t:
        terms.append(t)
    if nature is not None and str(nature).strip():
        n = str(nature).strip()
        if n not in NATURES:
            raise SdkError("usage_error", provider="fr_regafi",
                           detail=f"nature must be one of the register's own seven-word vocabulary {', '.join(NATURES)} (exact match), got '{n}'")
        terms.append(f'nature_autorisation="{n}"')
    if situation is not None and str(situation).strip():
        s = str(situation).strip()
        if s not in SITUATIONS:
            raise SdkError("usage_error", provider="fr_regafi",
                           detail=f"situation must be one of the closed pair {', '.join(SITUATIONS)} (facet-measured), got '{s}'")
        terms.append(f'situation="{s}"')
    size, off = _limit_offset(limit, offset)
    params = {"limit": size, "offset": off}
    if terms:
        params["where"] = " AND ".join(terms)
    out = _call("authorisations", params, cache, no_cache)
    out["params"] = params
    return out
