"""br_cnes — Brazil CNES healthcare-establishment register (apidadosabertos.saude.gov.br,
Departamento de Informática do SUS, keyless).

BR healthcare face (0.3.58; the domain's first BR face; admitted from research booklet
br-datasus-facilities 册 111, probed live 2026-11-13, tmp/probe-sdk-0358/p5+p7). CNES is the
Cadastro Nacional de Estabelecimentos de Saúde — the national facility register every Brazilian
healthcare establishment (public and private) must hold. One GET serves the roster, one GET by
code serves the single card; both answer the SAME 37-field row (verified identical key sets):
codigo_cnes (the register key), numero_cnpj_entidade (the maintaining entity's 14-digit CNPJ —
the company join), numero_cnpj (the facility's own CNPJ, nullable when the establishment is not
a separate taxpayer), nome_razao_social / nome_fantasia, codigo_tipo_unidade + the six
capability flags (centro cirúrgico / obstétrico / neonatal / atendimento hospitalar /
ambulatorial / serviço de apoio), coordinates, codigo_motivo_desabilitacao (the disablement
reason — null = active), data_atualizacao.

FILTER CONTRACT (swagger-extracted — the intuitive spellings are TRAPS): uf=SP and
tipo_unidade=HOSPITAL are SILENTLY IGNORED upstream (measured — unfiltered rows came back);
the real params are codigo_uf (IBGE state code int, SP=35, PE=26) and codigo_tipo_unidade
(int). status: 1=ativo / 0=inativo. data_atualizacao: establishments updated FROM that date
(YYYY-MM-DD — the refresh channel). limit is HARD-CAPPED at 20 upstream (1000 answers 20 —
measured; the cap is silent, so the module walls it locally instead). offset is ROW-based
0-based despite the swagger prose calling it a page number (measured: offset=1 drops one row).
NO total is echoed — a short page is the honest end-of-data signal.

BOUNDARY (deliberate omissions, both measured in the probe round): the bed-inventory panel
(/assistencia-a-saude/cnes-leitos, nu_comp/co_cnes/tp_leito with the double-space
'2  - ESPEC - CLINICO' spelling) is an adjacent surface for a later batch; the professionals
panel carries named individuals — PII, not a face. 0.3/2 polite, concurrency 1, TTL 7d
(data_atualizacao measured 2025-09 — a monthly-refresh cadence).
"""
from ..errors import SdkError

provider = {
    "id": "br_cnes",
    "baseUrl": "https://apidadosabertos.saude.gov.br",
    "rate": {"rps": 0.3, "burst": 2},
    "concurrency": 1,
    "ops": {
        "facilities": {"path": "/cnes/estabelecimentos", "timeout": 30.0},
        # single-card lookup; a bad code answers 404 {"message": "Estabelecimento not found."}
        "facility": {"path": "/cnes/estabelecimentos/{codigo_cnes}", "timeout": 30.0,
                     "notFound": [404]},
    },
    "ttl": {"facilities": 7 * 86400, "facility": 7 * 86400},
}


def _int_param(name, value, *, lo=None, hi=None):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        v = int(str(value).strip())
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="br_cnes",
                       detail=f"{name} must be an integer, got {value!r}")
    if lo is not None and v < lo:
        raise SdkError("usage_error", provider="br_cnes", detail=f"{name} must be >= {lo}, got {v}")
    if hi is not None and v > hi:
        raise SdkError("usage_error", provider="br_cnes", detail=f"{name} must be <= {hi}, got {v}")
    return v


def facilities_raw(*, codigo_uf=None, codigo_municipio=None, codigo_tipo_unidade=None,
                   status=None, centro_cirurgico=None, centro_obstetrico=None,
                   data_atualizacao=None, limit=20, offset=0,
                   cache=None, no_cache=False):
    """→ {count, rows[], params, _meta}. Filters all optional and combinable: codigo_uf = IBGE
    state code int (SP=35 — NOT the 2-letter spelling, that one is silently ignored);
    codigo_municipio = IBGE municipality code; codigo_tipo_unidade; status 1=ativo/0=inativo;
    centro_cirurgico/centro_obstetrico 1/0; data_atualizacao YYYY-MM-DD = updated from that
    date. limit 1-20 (the upstream hard cap — silently clamped, so walled locally); offset is
    row-based. NO total upstream: a short page is the end-of-data signal."""
    from ..transport import call_provider

    try:
        size = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="br_cnes", detail=f"limit must be an integer 1-20, got {limit!r}")
    if not 1 <= size <= 20:
        raise SdkError("usage_error", provider="br_cnes",
                       detail=f"limit must be 1-20 (the upstream hard cap — values above 20 are silently clamped, measured), got {limit!r}")
    off = _int_param("offset", offset, lo=0)
    params = {"limit": size, "offset": off or 0}
    for key, val in (("codigo_uf", _int_param("codigo_uf", codigo_uf, lo=1, hi=99)),
                     ("codigo_municipio", _int_param("codigo_municipio", codigo_municipio, lo=1)),
                     ("codigo_tipo_unidade", _int_param("codigo_tipo_unidade", codigo_tipo_unidade, lo=1)),
                     ("status", _int_param("status", status, lo=0, hi=1)),
                     ("estabelecimento_possui_centro_cirurgico", _int_param("centro_cirurgico", centro_cirurgico, lo=0, hi=1)),
                     ("estabelecimento_possui_centro_obstetrico", _int_param("centro_obstetrico", centro_obstetrico, lo=0, hi=1))):
        if val is not None:
            params[key] = val
    da = str(data_atualizacao or "").strip()
    if da:
        if len(da) != 10 or da[4] != "-" or da[7] != "-":
            raise SdkError("usage_error", provider="br_cnes",
                           detail=f"data_atualizacao must be YYYY-MM-DD, got {data_atualizacao!r}")
        params["data_atualizacao"] = da
    r = call_provider(provider, "facilities", params, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    rows = list(doc.get("estabelecimentos") or [])
    return {"count": len(rows), "rows": rows, "params": params, "_meta": r}


def facility_raw(codigo_cnes, *, cache=None, no_cache=False):
    """→ {row, params, _meta}. The single-establishment card by CNES code (same 37-field shape
    as roster rows); a bad code raises upstream_not_found (the upstream 404 body is
    {"message": "Estabelecimento not found."})."""
    from ..transport import call_provider

    code = _int_param("codigo_cnes", codigo_cnes, lo=1)
    if code is None:
        raise SdkError("usage_error", provider="br_cnes",
                       detail=f"codigo_cnes is required (the register's own integer key), got {codigo_cnes!r}")
    r = call_provider(provider, "facility", {"codigo_cnes": code}, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    if not isinstance(doc, dict) or "codigo_cnes" not in doc:
        raise SdkError("upstream_unavailable", provider="br_cnes",
                       detail="the single-card endpoint answered an unexpected shape (no codigo_cnes key)")
    return {"row": doc, "params": {"codigo_cnes": code}, "_meta": r}
