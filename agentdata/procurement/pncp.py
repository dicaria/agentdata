"""pncp — Brazil national procurement portal contract face provider (pncp.gov.br /api/consulta;
operated by Serpro, keyless).

procurement domain (0.3.0 founding; admitted 2026-10-29, probed). Shape measured 2026-10-29:
GET /api/consulta/v1/contratos?dataInicial=20260901&dataFinal=20260930&pagina=1[&cnpjOrgao=…]
  → {data:[…500 rows…], totalRegistros, totalPaginas, numeroPagina, paginasRestantes, empty}
  — the SpringDoc spec is public (/v3/api-docs): dataInicial/dataFinal/pagina are required,
  cnpjOrgao is an optional buyer filter; tamanhoPagina is a trap, do not invent it (the default
  500 is fine — the spec has the parameter but a self-made value 400s).
Row-level golden fields (2026-09 single-month window: 175,533 contracts over 352 pages, measured):
  orgaoEntidade.cnpj×razaoSocial (buyer) × niFornecedor+nomeRazaoSocialFornecedor (supplier)
  × the four amount columns valorInicial/Parcela/Global/Acumulado × dataAssinatura/Vigencia family
  × numeroControlePNCP as the stable key × objetoContrato full text × esfera (federal/state/municipal)
  × the subcontracting field family.
PII red line (precedent: fda_crl): on tipoPessoa=PF rows the niFornecedor (CPF) and the
supplier's personal name are not returned — set to None + fornecedorMascarado:true stated
explicitly; tipoPessoa=PJ (incl. MEI) is returned as upstream has it (CNPJ = public business
registry key).
Date format: compact YYYYMMDD (the dashed YYYY-MM-DD form is accepted and normalized to
compact before sending — both forms measured 200 on 2026-10-29).
TTL: contract-window history months are stable, recent windows change slowly — 7 days; polite
tier 1 rps (Serpro publishes no quota, so take the conservative value).
"""
from ..errors import SdkError

provider = {
    "id": "pncp",
    "baseUrl": "https://pncp.gov.br",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "contracts": {"path": "/api/consulta/v1/contratos"},  # params: dataInicial/dataFinal/pagina (cnpjOrgao optional)
    },
    "ttl": {"contracts": 7 * 86400},
}


def _mask_supplier(row, tipo_pessoa, ni_key, nome_key):
    """PII red line: mask the document number and the personal name on PF (individual) rows;
    PJ rows are returned as-is. Sets None + an explicit flag (never silent)."""
    masked = str(tipo_pessoa or "").strip().upper() == "PF"
    if masked:
        row[ni_key] = None
        row[nome_key] = None
    row["fornecedorMascarado"] = masked
    return row


def contracts_from_upstream(data):
    """Upstream contratos response → contract rows (pure function, offline-testable; PII masking
    happens at this layer)."""
    rows = []
    for r in (data or {}).get("data") or []:
        org = r.get("orgaoEntidade") or {}
        unidade = r.get("unidadeOrgao") or {}
        row = {
            "numeroControlePNCP": r.get("numeroControlePNCP"),          # stable key (the portal's contract identifier)
            "anoContrato": r.get("anoContrato"),
            "categoria": (r.get("categoriaProcesso") or {}).get("nome"),
            "tipoContrato": (r.get("tipoContrato") or {}).get("nome"),
            "orgaoEntidade": {"cnpj": org.get("cnpj"), "razaoSocial": org.get("razaoSocial"),
                              "esfera": org.get("esferaId"), "poder": org.get("poderId")},
            "unidadeOrgao": {"uf": unidade.get("ufSigla"), "municipio": unidade.get("municipioNome")},
            "tipoPessoa": r.get("tipoPessoa"),                          # PJ/PF (PF = supplier is an individual)
            "niFornecedor": r.get("niFornecedor"),                      # supplier CNPJ/CPF (masked for PF)
            "nomeRazaoSocialFornecedor": r.get("nomeRazaoSocialFornecedor"),  # supplier name (masked for PF)
            "valorInicial": r.get("valorInicial"),
            "valorParcela": r.get("valorParcela"),
            "valorGlobal": r.get("valorGlobal"),
            "valorAcumulado": r.get("valorAcumulado"),
            "dataAssinatura": r.get("dataAssinatura"),
            "dataVigenciaInicio": r.get("dataVigenciaInicio"),
            "dataVigenciaFim": r.get("dataVigenciaFim"),
            "dataPublicacaoPncp": r.get("dataPublicacaoPncp"),
            "numeroRetificacao": r.get("numeroRetificacao"),
            "objetoContrato": r.get("objetoContrato"),                  # full text of the contract subject
        }
        _mask_supplier(row, r.get("tipoPessoa"), "niFornecedor", "nomeRazaoSocialFornecedor")
        sub_tipo = r.get("tipoPessoaSubContratada")
        if sub_tipo or r.get("niFornecedorSubContratado") or r.get("nomeFornecedorSubContratado"):
            row["subContratado"] = _mask_supplier(
                {"tipoPessoa": sub_tipo, "niFornecedor": r.get("niFornecedorSubContratado"),
                 "nomeFornecedor": r.get("nomeFornecedorSubContratado")},
                sub_tipo, "niFornecedor", "nomeFornecedor")
        rows.append(row)
    return {
        "rows": rows, "count": len(rows),
        "total": data.get("totalRegistros") if isinstance(data, dict) else None,
        "total_paginas": data.get("totalPaginas") if isinstance(data, dict) else None,
        "paginas_restantes": data.get("paginasRestantes") if isinstance(data, dict) else None,
    }


def _norm_date(v, field):
    s = str(v or "").strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        s = s.replace("-", "")           # YYYY-MM-DD → compact (both forms measured 200, compact is what gets sent)
    if len(s) != 8 or not s.isdigit():
        raise SdkError("usage_error", provider="pncp",
                       detail=f"{field} must be YYYYMMDD or YYYY-MM-DD (contract publication-window endpoint), got '{v}'")
    return s


def contracts_raw(data_inicial, data_final, *, pagina=1, cnpj_orgao=None, cache=None, no_cache=False):
    """→ {rows[], count, total, total_paginas, paginas_restantes, params, _meta}.

    data_inicial/data_final = the publication window (required, upstream names verbatim);
    pagina pages from 1 (500 rows per page = the upstream default); cnpj_orgao = buyer CNPJ
    14-digit filter (optional)."""
    from ..transport import call_provider

    di, df = _norm_date(data_inicial, "data_inicial"), _norm_date(data_final, "data_final")
    if di > df:
        raise SdkError("usage_error", provider="pncp",
                       detail=f"data_inicial ({di}) must not be later than data_final ({df})")
    pg = int(pagina) if pagina is not None else 1
    if pg < 1:
        raise SdkError("usage_error", provider="pncp", detail=f"pagina must be a page number ≥1, got '{pagina}'")
    params = {"dataInicial": di, "dataFinal": df, "pagina": pg}
    orgao = str(cnpj_orgao or "").strip().replace("/", "").replace(".", "").replace("-", "") or None
    if orgao:
        if len(orgao) != 14 or not orgao.isdigit():
            raise SdkError("usage_error", provider="pncp",
                           detail=f"cnpj_orgao must be the buyer's 14-digit CNPJ, got '{cnpj_orgao}'")
        params["cnpjOrgao"] = orgao
    r = call_provider(provider, "contracts", params, cache=cache, no_cache=no_cache)
    return {**contracts_from_upstream(r["data"]), "params": params, "_meta": r}
