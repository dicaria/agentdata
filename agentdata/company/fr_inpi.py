"""fr_inpi — INPI accounting ratios open data (data.economie.gouv.fr Opendatasoft Explore API
v2.1, keyless; the same ODS stack as fr_regafi).

FR financial-depth face pair (0.3.58; admitted from research booklet — INPI 官方再分发 is the
only keyless financial surface over RNE accounts: data.inpi.fr itself sits behind an account
gate + Cloudflare WAF, while the Ministry's data.economie.gouv.fr mirror of the same datasets
is fully open). Two datasets ship as two ops:

- ratios_inpi_bce 23 fields: per-SIREN per-fiscal-year accounting ratios. siren + date_cloture_
  exercice are the keys; chiffre_d_affaires / marge_brute / ebe / ebit / resultat_net carry the
  levels, taux_d_endettement / ratio_de_liquidite / autonomie_financiere / credit_clients_jours /
  credit_fournisseurs_jours / rotation_des_stocks_jours … the ratios; type_bilan ∈ {C, S…} is
  the balance-sheet kind (C = complet, S = simplifié); confidentiality is the register's own
  disclosure tier — group_by-measured closed four-value vocabulary (Public 5,141,324 /
  Partiellement confidentiel 1,612,087 / RAPCAC 57,045 / Publication simplifiee 2,689 over
  ~6.8M rows live 2026-11-13). Values are € thousands (the INPI convention) — pass through
  verbatim, never rescaled.
- ratios_inpi_bce_sectors 94 fields / 22,159 rows: the sector benchmark panel. classe_naf (NAF
  rev.2 class code, e.g. 1102) × classe_ca (turnover band, '<2M' spelling verbatim) × exercice
  is the key; every ratio rides five quantiles q10/q25/q50/q75/q90 (part_ca_marge_brute_q50 …),
  plus cohorte. This is the benchmark an individual company's ratios compare against — the
  pairing IS the product (company face: ratio vs sector median).

ODSQL where assembly is LOCAL and additive (field="value" equality terms joined with AND — the
fr_regafi law); values containing a double quote are refused. SIREN MUST be quoted upstream
(where=siren="844516393" — unquoted is a syntax error, measured); the module assembles the
quotes itself after walling the value to 9 digits. limit is the ODS v2.1 ceiling 100;
total_count echoed and passed through. The datasets also expose export endpoints but the Range
header is silently ignored there — records paging is the only honest channel. No gate, no WAF
(measured live 2026-11-13, tmp/probe-sdk-0358/p2_inpi.py). 0.5/2 polite, TTL 24h.
"""
provider = {
    "id": "fr_inpi",
    "baseUrl": "https://data.economie.gouv.fr",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "ratios": {"path": "/api/explore/v2.1/catalog/datasets/ratios_inpi_bce/records",
                   "timeout": 30.0},
        "sectors": {"path": "/api/explore/v2.1/catalog/datasets/ratios_inpi_bce_sectors/records",
                    "timeout": 30.0},
    },
    "ttl": {"ratios": 24 * 3600, "sectors": 24 * 3600},
}

# group_by-measured 2026-11-13 — the register's own closed disclosure-tier vocabulary
CONFIDENTIALITY = ("Public", "Partiellement confidentiel", "RAPCAC", "Publication simplifiee")


def _term(field, value, *, quoted=True):
    from ..errors import SdkError
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if '"' in v:
        raise SdkError("usage_error", provider="fr_inpi",
                       detail=f"{field} must not contain double quotes (the ODSQL literal is assembled locally), got {value!r}")
    return f'{field}="{v}"' if quoted else f"{field}={v}"


def _limit_offset(limit, offset):
    from ..errors import SdkError
    size = 20
    if limit is not None:
        try:
            size = int(limit)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="fr_inpi",
                           detail=f"limit must be an integer 1-100, got {limit!r}")
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="fr_inpi",
                       detail=f"limit must be 1-100 (the ODS Explore v2.1 ceiling), got {limit!r}")
    off = 0
    if offset is not None:
        try:
            off = int(offset)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="fr_inpi",
                           detail=f"offset must be an integer >=0, got {offset!r}")
    if off < 0:
        raise SdkError("usage_error", provider="fr_inpi", detail=f"offset must be >=0, got {offset!r}")
    return size, off


def _call(op, params, cache, no_cache):
    from ..errors import SdkError
    from ..transport import call_provider
    r = call_provider(provider, op, params, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    if not isinstance(doc, dict) or "results" not in doc:
        raise SdkError("upstream_unavailable", provider="fr_inpi",
                       detail="the ODS Explore API answered an unexpected shape (no results key — maintenance or shape drift)")
    return {"total_count": doc.get("total_count"), "count": len(doc["results"]),
            "rows": [dict(x) for x in doc["results"]], "_meta": r}


def ratios_raw(siren=None, *, type_bilan=None, confidentiality=None, date_cloture=None,
               limit=20, offset=0, cache=None, no_cache=False):
    """→ {total_count, count, rows[], params, _meta}. siren = the 9-digit FR company key (exact,
    quoted by the module — the one spelling the upstream accepts); type_bilan the balance-sheet
    kind (C/S…, verbatim); confidentiality walled to the register's own four-value vocabulary;
    date_cloture an exact fiscal-year-close date YYYY-MM-DD. All optional and combinable."""
    from ..errors import SdkError
    terms = []
    if siren is not None and str(siren).strip():
        s = str(siren).strip()
        if not (s.isdigit() and len(s) == 9):
            raise SdkError("usage_error", provider="fr_inpi",
                           detail=f"siren must be exactly 9 digits (SIRET roots and prefixed keys are refused), got {siren!r}")
        terms.append(f'siren="{s}"')
    t = _term("type_bilan", type_bilan)
    if t:
        terms.append(t)
    if confidentiality is not None and str(confidentiality).strip():
        c = str(confidentiality).strip()
        if c not in CONFIDENTIALITY:
            raise SdkError("usage_error", provider="fr_inpi",
                           detail=f"confidentiality must be one of the register's own disclosure tiers {', '.join(CONFIDENTIALITY)} (group_by-measured), got '{c}'")
        terms.append(f'confidentiality="{c}"')
    t = _term("date_cloture_exercice", date_cloture)
    if t:
        terms.append(t)
    size, off = _limit_offset(limit, offset)
    params = {"limit": size, "offset": off}
    if terms:
        params["where"] = " AND ".join(terms)
    out = _call("ratios", params, cache, no_cache)
    out["params"] = params
    return out


def sectors_raw(classe_naf=None, *, classe_ca=None, exercice=None,
                limit=20, offset=0, cache=None, no_cache=False):
    """→ {total_count, count, rows[], params, _meta}. The sector benchmark panel: classe_naf =
    NAF rev.2 class code (e.g. 1102), classe_ca = turnover band (upstream spelling '<2M' — pass
    verbatim), exercice = fiscal year. Each row carries every ratio at q10/q25/q50/q75/q90."""
    terms = []
    t = _term("classe_naf", classe_naf)
    if t:
        terms.append(t)
    t = _term("classe_ca", classe_ca)
    if t:
        terms.append(t)
    if exercice is not None and str(exercice).strip():
        e = str(exercice).strip()
        if not (e.isdigit() and len(e) == 4):
            from ..errors import SdkError
            raise SdkError("usage_error", provider="fr_inpi",
                           detail=f"exercice must be a 4-digit year, got {exercice!r}")
        terms.append(f'exercice="{e}"')
    size, off = _limit_offset(limit, offset)
    params = {"limit": size, "offset": off}
    if terms:
        params["where"] = " AND ".join(terms)
    out = _call("sectors", params, cache, no_cache)
    out["params"] = params
    return out
