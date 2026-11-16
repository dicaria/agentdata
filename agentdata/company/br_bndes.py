"""br_bndes — BNDES financing operations (the "Operações" gateway, gateway.apis.bndes.gov.br,
keyless Solr gateway).

BR company face (0.3.60; admitted from the research booklet br-bndes-operacoes, re-probed live
2026-11-13):

CONTRACT (one Solr query through the public gateway):
  GET /operacoes/web/select?q=<term>&defType=edismax&qf=cliente_t_p&tdoc=tipoDocumento:cnpj
      &omitHeader=false&rows=<n>&start=<offset>&wt=json[&fq=<filter>][&facet=true&facet.field=<field>]
  → {response: {numFound, docs: [...68 fields…]}, facet_counts, responseHeader}
  q is the CLIENT NAME (the search runs over the cliente_t_p field — the client-name index);
  qf=cliente_t_p is the query field (the boost form cliente_t_p^20000 also works);
  tdoc=tipoDocumento:cnpj restricts the document type to the CNPJ-contracted operations.

A financing row (68 fields) carries: cliente (the beneficiary company), documentoCliente (the
CNPJ, MASKED — "XXXXXXXXX00146", only the last five digits), cnpjAgenteFinanceiro (the BNDES
FINANCING AGENT's full CNPJ — e.g. 00000000000191 = Banco do Brasil), naturezaCliente
(PRIVADA / PÚBLICA DIRETA / PÚBLICA INDIRETA — the state-owned-vs-private dimension),
uf, municipio, anoPosicao, valorContratacao, valorDesembolsado, taxaJuros,
prazoAmortizacao, instrumentoBndes, produtoBndes, setorApoiado, cnae, porteCliente,
liquidada, fr, subcreditos (the XML sub-credit block).

LIVE LAWS (measured 2026-11-13 — the booklet carried only part of this):
  - the gateway's Tomcat REJECTS the characters that are invalid in an RFC 3986 request
    target: a raw json.facet JSON body answers 400 "Invalid character found in the request
    target", and so does an fq with raw parentheses/quotes. Percent-encoded values are
    accepted — so the facets ride the CLASSIC form (facet=true&facet.field=…) and the fq
    filter is percent-encoded by the transport.
  - the client's CNPJ is MASKED in the index (documentoCliente = "XXXXXXXXX00146"), so a raw
    CNPJ query against documentoClienteIndex answers 0 hits — the join key onto a company
    register is the client NAME (plus the uf/municipio pair), not the CNPJ. The financing
    agent's CNPJ (cnpjAgenteFinanceiro) is NOT masked.
  - the wildcard / *:* enumeration is refused (403): the face always asks for a named term.
  - the fq filter works on the multi-valued fields with the quoted form
    (uf:("SP"), naturezaCliente:("PÚBLICA INDIRETA"), anoPosicao:("2013")) — the accents are
    percent-encoded by the transport and the upstream decodes them correctly.

Politeness: 0.2/2, concurrency 1, TTL 12h.
"""
from ..errors import SdkError

provider = {
    "id": "br_bndes",
    "baseUrl": "https://gateway.apis.bndes.gov.br",
    "rate": {"rps": 0.2, "burst": 2},
    "concurrency": 1,
    "ops": {
        # the $ names are literal here; the VALUES are substituted by the transport
        "search": {"path": "/operacoes/web/select?q={q}&defType=edismax&qf={qf}"
                         "&tdoc={tdoc}&omitHeader=false&rows={rows}&start={start}&wt=json",
                   "timeout": 60.0},
    },
    "ttl": {"search": 12 * 3600},
}

# the upstream's own field names for the filters the face exposes
FILTER_FIELDS = {
    "uf": "uf",
    "natureza": "naturezaCliente",
    "ano": "anoPosicao",
    "municipio": "municipio_sfm",
    "setor": "setorApoiado",
}


def _first(v):
    """The upstream's multi-valued fields are arrays (or a bare scalar)."""
    if isinstance(v, list):
        return v[0] if v else None
    return v


def flat_operation(doc):
    """One Solr document → the flat row (the 68-field document is reduced to the
    compliance-relevant columns)."""
    return {
        "client": doc.get("cliente"),
        "client_cnpj_masked": doc.get("documentoCliente"),
        "financing_agent": _first(doc.get("agenteFinanceiro")),
        "financing_agent_cnpj": _first(doc.get("cnpjAgenteFinanceiro")),
        "client_nature": _first(doc.get("naturezaCliente")),
        "client_size": _first(doc.get("porteCliente")),
        "uf": _first(doc.get("uf")),
        "municipality": _first(doc.get("municipio")),
        "year": doc.get("anoPosicao"),
        "contract_date": doc.get("dataContratacao"),
        "contract_value": doc.get("valorContratacao"),
        "disbursed_value": doc.get("valorDesembolsado"),
        "currency": _first(doc.get("moeda")),
        "interest_rate": _first(doc.get("taxaJuros")),
        "amortization_term": _first(doc.get("prazoAmortizacao")),
        "grace_term": _first(doc.get("prazoCarencia")),
        "instrument": _first(doc.get("instrumentoBndes")),
        "product": _first(doc.get("produtoBndes")),
        "sector": _first(doc.get("setorApoiado")),
        "subsector": _first(doc.get("subsetorApoiado")),
        "cnae": _first(doc.get("cnae")),
        "operation_type": _first(doc.get("tipoOperacao")),
        "direct_operation": _first(doc.get("operacaoDireta")),
        "settled": _first(doc.get("liquidada")),
        "contract_number": doc.get("numeroContrato"),
        "reimbursable": _first(doc.get("reembolsavel")),
        "free_resources": _first(doc.get("fonteRecursos")),
        "id": doc.get("id"),
    }


def operations_raw(name, *, uf=None, natureza=None, ano=None, municipio=None,
                   rows=20, start=0, facet=False, facet_field="cliente_t_p",
                   cache=None, no_cache=False):
    """→ {total, rows[], facets{}, params, _meta}. name = the CLIENT NAME (the query runs
    over the cliente-name index — the wildcard enumeration is refused upstream); uf /
    natureza / ano / municipio are the upstream fq filters (server-side)."""
    from ..transport import call_provider

    q = str(name or "").strip()
    if not q:
        raise SdkError("usage_error", provider="br_bndes",
                       detail="a client name is required — the gateway refuses the wildcard "
                              "enumeration (*:* answers 403)")
    try:
        n = int(rows)
        st = int(start)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="br_bndes",
                       detail=f"rows/start must be integers, got rows={rows!r} start={start!r}")
    if not 1 <= n <= 500:
        raise SdkError("usage_error", provider="br_bndes", detail=f"rows must be 1..500, got {n}")
    if st < 0:
        raise SdkError("usage_error", provider="br_bndes", detail=f"start must be >= 0, got {st}")

    filters = []
    for key, value in (("uf", uf), ("natureza", natureza), ("ano", ano), ("municipio", municipio)):
        if value in (None, ""):
            continue
        field = FILTER_FIELDS[key]
        filters.append(f'{field}:("{value}")')
    params = {"q": q, "qf": "cliente_t_p", "tdoc": "tipoDocumento:cnpj",
              "rows": n, "start": st}
    if filters:
        params["fq"] = " AND ".join(filters)
    if facet:
        params["facet"] = "true"
        params["facet.field"] = facet_field

    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    resp = doc.get("response") or {}
    rows_out = [flat_operation(x) for x in (resp.get("docs") or [])]
    facets = {}
    for field, values in ((doc.get("facet_counts") or {}).get("facet_fields") or {}).items():
        facets[field] = list(zip(values[0::2], values[1::2]))
    return {
        "total": resp.get("numFound"),
        "rows": rows_out,
        "facets": facets,
        "params": {"q": q, "uf": uf, "natureza": natureza, "ano": ano, "municipio": municipio,
                   "rows": n, "start": st, "facet": bool(facet), "facet_field": facet_field},
        "_meta": r,
    }
