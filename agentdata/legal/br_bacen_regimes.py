"""br_bacen_regimes — Banco Central do Brasil Olinda special-regimes register (legal face;
research volume br-bacen-olinda-recipe, 册 236; admitted in 0.3.38, probed first-hand
2026-11-04 tmp/probe-br-bacen-0338/ with the SDK's own polite UA, direct).

The regimes_especiais register is BACEN's public record of financial institutions under
special administration by the state — today one Tipo, LIQUIDAÇÃO EXTRAJUDICIAL (all 25 rows;
extrajudicial liquidation, the Receita/CGU-adjacent wind-down track), Inicio 02/08/2013 →
30/04/2026. Small register, shipped whole in one keyless GET ($top=10000&$format=json),
cached 24h, filtered locally — a screening face: match an entity's CNPJ root and you know it
is being wound down, with the liquidation's own contact block (Responsavel, Emails, Telefones)
for verification. CnpjInstituicao is the 14-digit whole key, CnpjRaiz the 8-digit root (both
kept; the institutions face joins on the root). Dates are the register's own dd/mm/yyyy,
verbatim. Same host as company br_bacen (olinda.bcb.gov.br) — host-layer bucket shared, polite
0.5 rps / burst 4. TTL: 24h.
"""
import json

from ..errors import SdkError

provider = {
    "id": "br_bacen_regimes",
    "baseUrl": "https://olinda.bcb.gov.br",
    "rate": {"rps": 0.5, "burst": 4},
    "ops": {
        "regimes": {"path": "/olinda/servico/regimes_especiais/versao/v1/odata/Regimes",
                    "timeout": 60.0},
    },
    "ttl": {"regimes": 24 * 3600},
}


def _v(x):
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None


def _rows(value):
    """Row-iterable -> normalised rows (verbatim register vocabulary, dd/mm/yyyy dates)."""
    return [
        {"cnpj": _v(r.get("CnpjInstituicao")), "cnpj_root": _v(r.get("CnpjRaiz")),
         "name": _v(r.get("NomeInstituicao")), "tipo": _v(r.get("Tipo")),
         "inicio": _v(r.get("Inicio")), "responsavel": _v(r.get("Responsavel")),
         "endereco": _v(r.get("Endereco")), "municipio": _v(r.get("Municipio")),
         "uf": _v(r.get("UF")), "cep": _v(r.get("CEP")),
         "emails": _v(r.get("Emails")), "telefones": _v(r.get("Telefones"))}
        for r in value
    ]


def rows_from_upstream(text):
    """OData JSON text -> normalised rows (the pure parser; call_provider usually hands back
    the parsed dict — regimes_raw routes that straight to _rows)."""
    return _rows(json.loads(text).get("value") or [])


def regimes_raw(name=None, *, cnpj=None, uf=None, limit=20, cache=None, no_cache=False):
    """Whole register (25 rows) -> {rows, total_matched, scanned_rows, census, limit_applied,
    params, _meta}. cnpj accepts the 8-digit root (matched against CnpjRaiz) or the 14-digit
    whole key (matched against CnpjInstituicao) — both are on every row."""
    from ..transport import call_provider
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="br_bacen_regimes",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    c = str(cnpj).strip() if cnpj not in (None, "") else None
    if c is not None and not (c.isdigit() and len(c) in (8, 14)):
        raise SdkError("usage_error", provider="br_bacen_regimes",
                       detail=f"cnpj must be the 8-digit root or the 14-digit whole key, "
                              f"got {cnpj!r}")
    u = str(uf).strip().upper() if uf not in (None, "") else None
    if u is not None and not (len(u) == 2 and u.isalpha()):
        raise SdkError("usage_error", provider="br_bacen_regimes",
                       detail=f"uf must be a 2-letter state code (e.g. SP), got {uf!r}")
    needle = str(name or "").strip().lower() or None

    r = call_provider(provider, "regimes", {"$top": 10000, "$format": "json"},
                      cache=cache, no_cache=no_cache)
    data = r["data"]
    rows = rows_from_upstream(data) if isinstance(data, str) else _rows(data.get("value") or [])

    hits = []
    for x in rows:
        if needle and needle not in str(x.get("name") or "").lower():
            continue
        if c and x.get("cnpj") != c and x.get("cnpj_root") != c:
            continue
        if u and x.get("uf") != u:
            continue
        hits.append(x)

    by_tipo = {}
    for x in rows:
        by_tipo[x["tipo"]] = by_tipo.get(x["tipo"], 0) + 1
    years = sorted({x["inicio"][-4:] for x in rows if x.get("inicio")})
    census = {
        "total": len(rows),
        "by_tipo": by_tipo,
        "with_responsavel": sum(1 for x in rows if x.get("responsavel")),
        "start_date_min": min((x["inicio"] for x in rows if x.get("inicio")), default=None),
        "start_date_max": max((x["inicio"] for x in rows if x.get("inicio")), default=None),
        "start_year_min": years[0] if years else None,
        "start_year_max": years[-1] if years else None,
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"name": name or None, "cnpj": c, "uf": u},
            "_meta": r, "_metas": [r]}
