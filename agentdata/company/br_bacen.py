"""br_bacen — Banco Central do Brasil Olinda odata registers (olinda.bcb.gov.br; the company
domain's first BR faces; research volume br-bacen-olinda-recipe, 册 236; faces admitted in
0.3.38, probed first-hand 2026-11-04 tmp/probe-br-bacen-0338/ with the SDK's own polite UA,
direct, zero extra headers).

Four faces, all local-scan family (each register ships whole in 1-2 keyless GETs, cached 24h,
filtered locally — Olinda publishes no query surface worth using on these static registers and
$inlinecount=allpages is a 400):

- institutions — the authorised-institutions register (Instituicoes_em_funcionamento), FOUR
  resources merged: SedesBancoComMultCE 154 / SedesCooperativas 752 / SedesSociedades 704 /
  SedesConsorcios 130 = 1,740 rows. CNPJ arrives as the 8-digit ROOT (the 14-digit whole key
  lives on branches/resolution rows). Key variants are the register's own: the banco resource
  carries SEGMENTO + CARTEIRA_COMERCIAL, the cooperativa resource swaps in CLASSE /
  CATEGCOOPSING / FILIACAO / ASSOCIACAO (no SEGMENTO), the sociedade resource carries a
  15-value SEGMENTO (payment institutions, corretoras, SCP...), the consorcio resource is a
  bare address block (no SEGMENTO) — kept verbatim, family derives from the resource.
- branches — Informes_Agencias Agencias: 13,590 branch rows × 20 Segmento × 639 IFs in TWO
  pages ($top=10000 + $skip=10000; $inlinecount unsupported → the total is what you pull).
  CNPJ arrives three-part (CnpjBase 8 / CnpjSequencial 4 / CnpjDv 2) — the face also emits the
  joined 14-digit cnpj_full, the RFB whole-library join key. CodigoCompe (5 digits) is the
  PIX/TED settlement key, empty on 731 rows. Posicao is the panel as-of date (dd/mm/yyyy,
  uniform across rows); DataInicio is the branch's own start date (1949→, dd/mm/yyyy).
- domains — DominiosVerificados: 1,892 rows = 1,740 institutions × verified-domain status
  (534 Dominio próprio + 279 Domínio de intregrante do conglomerado — the upstream typo is
  verbatim — + 1,079 Sem domínio verificado, kept: "no verified domain" is the honest
  negative for anti-phishing screening). CODIGO_DO_CONGLOMERADO (635 codes) is the
  conglomerate lineage key; CNPJ is the 8-digit root with the register's own "00000000"
  placeholder on 2 rows (BB) — kept verbatim.
- dasfn — DASFN Recursos: the open-data/open-finance API participation directory, 10,419 rows
  × 513 CNPJs × 4 API kinds (pilar3 9,885 / canais_atendimento 422 / taxas_cartoes 93 /
  pix_saque 19) × 5 versions, all Situacao=Produção. The upstream serialises null Argumento
  as the literal string "None" — normalised to null (pinned by test). Contato slots are
  institutional role addresses (Ouvidoria/dadosabertos@), not personal data.

Path trap (probed): the DASFN service lives at /olinda/servico/DASFN/versao/v1/... — the
recipe's /DASFN/v1 form answers 403 (Olinda's malformed-service response, NOT a gate: honest
UA + zero extra headers passes on the versao path). $-params survive urlencode as %24top
(probed 2026-11-04). Rate: polite 0.5 rps / burst 4 (reference publication path, the
imf/bis/unsd posture); the host-layer bucket is shared with legal br_bacen_regimes.
TTL: 24h (register posture).
"""
import json

from ..errors import SdkError

_BASE = "https://olinda.bcb.gov.br"
_SEDES = "/olinda/servico/Instituicoes_em_funcionamento/versao/v1/odata"

provider = {
    "id": "br_bacen",
    "baseUrl": _BASE,
    "rate": {"rps": 0.5, "burst": 4},
    "ops": {
        "sedes_banco": {"path": _SEDES + "/SedesBancoComMultCE", "timeout": 60.0},
        "sedes_coop": {"path": _SEDES + "/SedesCooperativas", "timeout": 60.0},
        "sedes_soc": {"path": _SEDES + "/SedesSociedades", "timeout": 60.0},
        "sedes_cons": {"path": _SEDES + "/SedesConsorcios", "timeout": 60.0},
        "agencias": {"path": "/olinda/servico/Informes_Agencias/versao/v1/odata/Agencias",
                     "timeout": 120.0},
        "dominios": {"path": _SEDES + "/DominiosVerificados", "timeout": 60.0},
        "dasfn_recursos": {"path": "/olinda/servico/DASFN/versao/v1/odata/Recursos",
                           "timeout": 120.0},
    },
    "ttl": {k: 24 * 3600 for k in
            ("sedes_banco", "sedes_coop", "sedes_soc", "sedes_cons",
             "agencias", "dominios", "dasfn_recursos")},
}

_FAMILIES = ("banco", "cooperativa", "sociedade", "consorcio")
_TIPO_MAP = {"own": "Dominio próprio", "member": "Domínio de intregrante do conglomerado",
             "none": "Sem domínio verificado"}
_DASFN_APIS = ("pilar3", "canais_atendimento", "taxas_cartoes", "pix_saque")


def _v(x):
    """Upstream cell -> verbatim value ('' and the literal 'None' string -> None)."""
    if x is None:
        return None
    s = str(x).strip()
    return s if s and s != "None" else None


def _limit_wall(provider_id, limit):
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider=provider_id,
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    return size


def _pull(op, cache, no_cache, skip=None):
    """One odata page -> rows (params $top=10000&$format=json[&$skip]; $ inlinecount is a 400)."""
    from ..transport import call_provider
    params = {"$top": 10000, "$format": "json"}
    if skip:
        params["$skip"] = skip
    r = call_provider(provider, op, params, cache=cache, no_cache=no_cache)
    data = r["data"]
    if isinstance(data, str):  # a cached/replayed payload may still be the raw string
        data = json.loads(data)
    return r, (data.get("value") or [])


def _pull_pages(op, cache, no_cache):
    """Whole register across pages (page 2 only when page 1 comes back full at 10,000)."""
    r1, rows = _pull(op, cache, no_cache)
    metas = [r1]
    if len(rows) == 10000:
        r2, more = _pull(op, cache, no_cache, skip=10000)
        metas.append(r2)
        rows = rows + more
    return rows, metas


def _addr(r, *pairs):
    """Upstream (UPPER/Mixed-case) address block -> lowercase row keys (pairs = row_key, upstream_key)."""
    return {k: _v(r.get(u)) for k, u in pairs}


# ---------------------------------------------------------------- institutions

def institutions_raw(name=None, *, family=None, segmento=None, uf=None, cnpj_root=None,
                     limit=20, cache=None, no_cache=False):
    """Four Sedes* resources merged -> {rows, total_matched, scanned_rows, census,
    limit_applied, params, _meta}. family=banco|cooperativa|sociedade|consorcio (the resource
    boundary); segmento = contains (case-insensitive, only bites banco/sociedade rows); uf =
    2-letter exact; cnpj_root = 8-digit exact."""
    size = _limit_wall("br_bacen", limit)
    if family not in (None, "") and family not in _FAMILIES:
        raise SdkError("usage_error", provider="br_bacen",
                       detail=f"family must be one of {'|'.join(_FAMILIES)} (the four "
                              f"Sedes* resources), got {family!r}")
    root = str(cnpj_root).strip() if cnpj_root not in (None, "") else None
    if root is not None and not (root.isdigit() and len(root) == 8):
        raise SdkError("usage_error", provider="br_bacen",
                       detail=f"cnpj_root must be the 8-digit CNPJ root, got {cnpj_root!r}")
    u = str(uf).strip().upper() if uf not in (None, "") else None
    if u is not None and not (len(u) == 2 and u.isalpha()):
        raise SdkError("usage_error", provider="br_bacen",
                       detail=f"uf must be a 2-letter state code (e.g. SP), got {uf!r}")
    needle = str(name or "").strip().lower() or None
    seg = str(segmento or "").strip().lower() or None

    rows, metas = [], []
    per_family = {}
    for op, fam, extra in (("sedes_banco", "banco", ("CARTEIRA_COMERCIAL",)),
                           ("sedes_coop", "cooperativa", ("CLASSE", "CATEGCOOPSING", "FILIACAO", "ASSOCIACAO")),
                           ("sedes_soc", "sociedade", ()),
                           ("sedes_cons", "consorcio", ())):
        fam_rows, fam_metas = _pull_pages(op, cache, no_cache)
        metas.extend(fam_metas)
        per_family[fam] = len(fam_rows)
        for r in fam_rows:
            row = {"cnpj_root": _v(r.get("CNPJ")), "name": _v(r.get("NOME_INSTITUICAO")),
                   "family": fam, "segmento": _v(r.get("SEGMENTO")),
                   "email": _v(r.get("E_MAIL")), "sitio": _v(r.get("SITIO_NA_INTERNET")),
                   "ddd": _v(r.get("DDD")), "telefone": _v(r.get("TELEFONE"))}
            row.update(_addr(r, ("endereco", "ENDERECO"), ("complemento", "COMPLEMENTO"),
                             ("bairro", "BAIRRO"), ("municipio", "MUNICIPIO"),
                             ("municipio_ibge", "MUNICIPIO_IBGE"), ("uf", "UF"),
                             ("cep", "CEP")))
            for k in extra:
                row[k.lower()] = _v(r.get(k))
            rows.append(row)

    hits = []
    for x in rows:
        if family and x["family"] != family:
            continue
        if seg and seg not in str(x.get("segmento") or "").lower():
            continue
        if u and x.get("uf") != u:
            continue
        if root and x.get("cnpj_root") != root:
            continue
        if needle and needle not in str(x.get("name") or "").lower():
            continue
        hits.append(x)

    by_segmento = {}
    for x in rows:
        if x.get("segmento"):
            by_segmento[x["segmento"]] = by_segmento.get(x["segmento"], 0) + 1
    census = {
        "total": len(rows),
        "by_family": per_family,
        "by_segmento": by_segmento,
        "with_email": sum(1 for x in rows if x.get("email")),
        "with_site": sum(1 for x in rows if x.get("sitio")),
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"name": name, "family": family or None, "segmento": segmento or None,
                       "uf": u, "cnpj_root": root},
            "_meta": metas[0], "_metas": metas}


# ---------------------------------------------------------------- branches

def branches_raw(if_name=None, *, agency=None, compe=None, uf=None, cnpj_root=None,
                 limit=20, cache=None, no_cache=False):
    """Informes_Agencias whole register (two pages) -> same envelope. Rows keep the three-part
    CNPJ and emit the joined 14-digit cnpj_full (the RFB join key); compe = 5-digit settlement
    code (empty on 731 rows -> None)."""
    size = _limit_wall("br_bacen", limit)
    root = str(cnpj_root).strip() if cnpj_root not in (None, "") else None
    if root is not None and not (root.isdigit() and len(root) == 8):
        raise SdkError("usage_error", provider="br_bacen",
                       detail=f"cnpj_root must be the 8-digit CnpjBase, got {cnpj_root!r}")
    cp = str(compe).strip() if compe not in (None, "") else None
    if cp is not None and not (cp.isdigit() and 3 <= len(cp) <= 5):
        raise SdkError("usage_error", provider="br_bacen",
                       detail=f"compe must be the 3-5 digit settlement code, got {compe!r}")
    u = str(uf).strip().upper() if uf not in (None, "") else None
    if u is not None and not (len(u) == 2 and u.isalpha()):
        raise SdkError("usage_error", provider="br_bacen",
                       detail=f"uf must be a 2-letter state code (e.g. SP), got {uf!r}")
    ifn = str(if_name or "").strip().lower() or None
    ag = str(agency or "").strip().lower() or None

    raw, metas = _pull_pages("agencias", cache, no_cache)
    rows = []
    for r in raw:
        base, seq, dv = _v(r.get("CnpjBase")), _v(r.get("CnpjSequencial")), _v(r.get("CnpjDv"))
        row = {"cnpj_root": base, "cnpj_sequencial": seq, "cnpj_dv": dv,
               "cnpj_full": (base + seq + dv) if base and seq and dv else None,
               "compe": _v(r.get("CodigoCompe")), "if_name": _v(r.get("NomeIf")),
               "agency_name": _v(r.get("NomeAgencia")), "segmento": _v(r.get("Segmento")),
               "data_inicio": _v(r.get("DataInicio")), "posicao": _v(r.get("Posicao")),
               "ddd": _v(r.get("DDD")), "telefone": _v(r.get("Telefone"))}
        row.update(_addr(r, ("endereco", "Endereco"), ("numero", "Numero"),
                         ("complemento", "Complemento"), ("bairro", "Bairro"),
                         ("municipio", "Municipio"), ("municipio_ibge", "MunicipioIbge"),
                         ("uf", "UF"), ("cep", "Cep")))
        rows.append(row)

    hits = []
    for x in rows:
        if ifn and ifn not in str(x.get("if_name") or "").lower():
            continue
        if ag and ag not in str(x.get("agency_name") or "").lower():
            continue
        if cp and (x.get("compe") or "").lstrip("0") != cp.lstrip("0"):
            continue
        if u and x.get("uf") != u:
            continue
        if root and x.get("cnpj_root") != root:
            continue
        hits.append(x)

    years = sorted({x["data_inicio"][-4:] for x in rows if x.get("data_inicio")})
    census = {
        "total": len(rows),
        "ifs": len({x["if_name"] for x in rows if x.get("if_name")}),
        "segmento_n": len({x["segmento"] for x in rows if x.get("segmento")}),
        "as_of": rows[0]["posicao"] if rows else None,
        "compe_missing": sum(1 for x in rows if not x.get("compe")),
        "start_year_min": years[0] if years else None,
        "start_year_max": years[-1] if years else None,
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"if_name": if_name, "agency": agency or None, "compe": cp, "uf": u,
                       "cnpj_root": root},
            "_meta": metas[0], "_metas": metas}


# ---------------------------------------------------------------- domains

def domains_raw(domain=None, *, name=None, tipo=None, conglomerado=None,
                limit=20, cache=None, no_cache=False):
    """DominiosVerificados whole register -> same envelope. tipo=own|member|none translates the
    register's own three-value vocabulary (rows keep it verbatim, including the upstream typo);
    the 1,079 'Sem domínio verificado' rows ARE the honest negative and stay in the scan."""
    size = _limit_wall("br_bacen", limit)
    if tipo not in (None, "") and tipo not in _TIPO_MAP:
        raise SdkError("usage_error", provider="br_bacen",
                       detail=f"tipo must be one of own|member|none (the register's three-value "
                              f"vocabulary), got {tipo!r}")
    dom = str(domain or "").strip().lower() or None
    needle = str(name or "").strip().lower() or None
    cong = str(conglomerado or "").strip() or None

    raw, metas = _pull_pages("dominios", cache, no_cache)
    rows = []
    for r in raw:
        row = {"cnpj_root": _v(r.get("CNPJ")), "inst": _v(r.get("INSTITUICAO_FINANCEIRA")),
               "domain": _v(r.get("DOMINIO")), "tipo": _v(r.get("TIPO_DE_DOMINIO")),
               "conglomerado_code": _v(r.get("CODIGO_DO_CONGLOMERADO")),
               "conglomerado": _v(r.get("CONGLOMERADO")),
               "owner": _v(r.get("PROPRIETARIO_DO_DOMINIO")),
               "cnpj_no_registro": _v(r.get("CNPJ_NO_REGISTRO_DO_DOMINIO"))}
        rows.append(row)

    want = _TIPO_MAP.get(tipo) if tipo else None
    hits = []
    for x in rows:
        if dom and dom not in str(x.get("domain") or "").lower():
            continue
        if needle and needle not in str(x.get("inst") or "").lower():
            continue
        if want and x.get("tipo") != want:
            continue
        if cong and x.get("conglomerado_code") != cong:
            continue
        hits.append(x)

    by_tipo = {}
    for x in rows:
        by_tipo[x["tipo"]] = by_tipo.get(x["tipo"], 0) + 1
    census = {
        "total": len(rows),
        "by_tipo": by_tipo,
        "with_domain": sum(1 for x in rows if x.get("domain")),
        "conglomerado_n": len({x["conglomerado_code"] for x in rows if x.get("conglomerado_code")}),
        "inst_n": len({x["inst"] for x in rows if x.get("inst")}),
        "cnpj_root_placeholder": sum(1 for x in rows if x.get("cnpj_root") == "00000000"),
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"domain": domain or None, "name": name or None, "tipo": tipo or None,
                       "conglomerado": cong},
            "_meta": metas[0], "_metas": metas}


# ---------------------------------------------------------------- dasfn

def dasfn_raw(cnpj=None, *, name=None, api=None, recurso=None,
              limit=20, cache=None, no_cache=False):
    """DASFN Recursos whole register (two pages) -> same envelope. api=pilar3|canais_atendimento|
    taxas_cartoes|pix_saque (the register's four API kinds); cnpj = exact 14-digit key (the
    whole key — this register carries CnpjInstituicao full, unlike the Sedes roots)."""
    size = _limit_wall("br_bacen", limit)
    if api not in (None, "") and api not in _DASFN_APIS:
        raise SdkError("usage_error", provider="br_bacen",
                       detail=f"api must be one of {'|'.join(_DASFN_APIS)} (the register's four "
                              f"API kinds), got {api!r}")
    c = str(cnpj).strip() if cnpj not in (None, "") else None
    if c is not None and not (c.isdigit() and len(c) == 14):
        raise SdkError("usage_error", provider="br_bacen",
                       detail=f"cnpj must be the 14-digit whole key, got {cnpj!r}")
    needle = str(name or "").strip().lower() or None
    rec = str(recurso or "").strip().lower() or None

    raw, metas = _pull_pages("dasfn_recursos", cache, no_cache)
    rows = []
    for r in raw:
        row = {"api": _v(r.get("Api")), "versao": _v(r.get("Versao")),
               "cnpj": _v(r.get("CnpjInstituicao")), "name": _v(r.get("NomeInstituicao")),
               "recurso": _v(r.get("Recurso")), "argumento": _v(r.get("Argumento")),
               "situacao": _v(r.get("Situacao")), "url_dados": _v(r.get("URLDados")),
               "url_consulta": _v(r.get("URLConsulta")),
               "contato_nome": _v(r.get("NomeContato")), "contato_email": _v(r.get("EmailContato"))}
        rows.append(row)

    hits = []
    for x in rows:
        if c and x.get("cnpj") != c:
            continue
        if api and x.get("api") != api:
            continue
        if rec and rec not in str(x.get("recurso") or "").lower():
            continue
        if needle and needle not in str(x.get("name") or "").lower():
            continue
        hits.append(x)

    by_api, by_versao = {}, {}
    for x in rows:
        by_api[x["api"]] = by_api.get(x["api"], 0) + 1
        by_versao[x["versao"]] = by_versao.get(x["versao"], 0) + 1
    census = {
        "total": len(rows),
        "by_api": by_api,
        "by_versao": by_versao,
        "cnpj_n": len({x["cnpj"] for x in rows if x.get("cnpj")}),
        "by_situacao": {s: sum(1 for x in rows if x["situacao"] == s)
                        for s in {x["situacao"] for x in rows}},
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"cnpj": c, "name": name or None, "api": api or None,
                       "recurso": recurso or None},
            "_meta": metas[0], "_metas": metas}
