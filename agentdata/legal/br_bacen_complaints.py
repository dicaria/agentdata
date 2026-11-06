"""br_bacen_complaints — Banco Central do Brasil rdrweb complaint-index ranking (legal face;
research volume br-bacen-olinda-recipe, 册 236; admitted in 0.3.39, probed first-hand
2026-11-04 tmp/probe-br-bacen-0339/ with the SDK's own polite UA, direct).

The RDR (Reclamações - Demandas Reclamadas) ranking consolidates the citizen complaints
against financial institutions that BACEN received, analysed and closed in each reference
period. Two channels, both keyless on www3.bcb.gov.br:

  /rdrweb/rest/ext/ranking              — the period catalog (hal-ish JSON): 13 years,
                                          2014 -> 2026; periodicidades shift across eras
                                          (MENSAL 2014-2015, BIMESTRAL 2016, TRIMESTRAL
                                          banks / SEMESTRAL consortiums from 2017 on); each
                                          (year, periodicidade, periodo) slot lists the tipos
                                          it carries — "Bancos e financeiras" or "Consorcios".
  /rdrweb/rest/ext/ranking/arquivo      — one semicolon CSV per (ano, periodicidade, periodo,
                                          tipo). cp1252, no BOM, trailing ';' -> a phantom
                                          empty column. A combination the catalog does not
                                          list answers HTTP 204 with a 0-byte body — so the
                                          catalog IS the axis: the raw layer validates
                                          (ano, periodicidade, periodo, tipo) against it and
                                          answers usage_error with the available combos
                                          (the dgcomp closed-set posture) rather than ever
                                          firing a ghost request.

Schema drifts by tipo and era — rows keep only the columns the file carries (the
institutions-register precedent: keys vary by resource, values stay verbatim):

  banks 2019+  : Categoria (Top 15 - … / Demais …), Tipo (Conglomerado / Banco/financeira),
                 CNPJ IF = 8-digit root (only on Banco/financeira rows; conglomerate rows
                 carry the conglomerate name instead), Índice (comma decimal; only computed
                 for ranked institutions — 148 of 221 rows in 2026-T3 are honestly blank),
                 answered / upheld / upheld_extrapolated / analyzed, clients CCS+SCR/CCS/SCR.
  banks 2014-18: Categoria by client size (Menos / Mais de dois milhões de clientes), same
                 Tipo/CNPJ shape, but regulated_upheld / regulated_other / unregulated /
                 complaints_total counts, clients + FGC.
  consortiums  : CNPJ AC = the administradora's root on EVERY row (the only kind with full
                 key coverage), regulated_upheld / regulated_other / unregulated /
                 complaints_total, clients = consorciados.

Counts become ints, Índice a float (pt-BR comma), blanks -> None; labels (3º, 1º, Mês values)
stay verbatim. Same registry family as legal br_bacen_regimes / company br_bacen_* but a
different host (www3.bcb.gov.br, not olinda.bcb.gov.br) — its own host-layer bucket, polite
0.5 rps / burst 4. TTL: 24h both ops (period files are final once published; the catalog rolls
when a new period lands).
"""
import csv
import io
import json

from ..errors import SdkError

provider = {
    "id": "br_bacen_complaints",
    "baseUrl": "https://www3.bcb.gov.br",
    "rate": {"rps": 0.5, "burst": 4},
    "ops": {
        "anos": {"path": "/rdrweb/rest/ext/ranking", "timeout": 60.0},
        "arquivo": {"path": "/rdrweb/rest/ext/ranking/arquivo", "accept": "bytes",
                    "timeout": 120.0},
    },
    "ttl": {"anos": 24 * 3600, "arquivo": 24 * 3600},
}

_TIPO = {"banks": "Bancos e financeiras", "consortiums": "Consorcios"}

# the register's own count/client headers -> snake keys (present-only per file era)
_COUNTS = {
    "Quantidade total de reclamações respondidas": "answered",
    "Quantidade de reclamações procedentes": "upheld",
    "Quantidade de reclamações procedentes extrapoladas": "upheld_extrapolated",
    "Quantidade total de reclamações analisadas": "analyzed",
    "Quantidade de reclamações reguladas procedentes": "regulated_upheld",
    "Quantidade de reclamações reguladas - outras": "regulated_other",
    "Quantidade de reclamações não reguladas": "unregulated",
    "Quantidade total de reclamações": "complaints_total",
    "Quantidade total de clientes – CCS e SCR": "clients_total",
    "Quantidade de clientes – CCS": "clients_ccs",
    "Quantidade de clientes – SCR": "clients_scr",
    "Quantidade de clientes – FGC": "clients_fgc",
    "Quantidade de clientes – Consorciados": "clients_consorciados",
}


def _cell(x):
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None


def _num(x):
    """digits-only cell -> int; comma-decimal -> float; blank/None -> None (never a guess)."""
    s = _cell(x)
    if s is None:
        return None
    if s.isdigit():
        return int(s)
    try:
        return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)
    except ValueError:
        return s  # verbatim fallback — the register's own wording wins over coercion


def _periodo_column(header):
    for name in ("Trimestre", "Mês", "Semestre"):
        if name in header:
            return name
    return None


def rows_from_upstream(text):
    """accept='bytes' payload (latin-1 string) -> normalised rows (pure function; re-encodes
    .encode('latin-1') to recover the exact bytes and decodes cp1252 — Índice/– depend on it)."""
    body = text.encode("latin-1").decode("cp1252")
    rdr = csv.reader(io.StringIO(body), delimiter=";")
    try:
        header = next(rdr)
    except StopIteration:
        return []
    per_col = _periodo_column(header)
    per_idx = header.index(per_col) if per_col else None
    name_idx = header.index("Administradora de consórcio") if "Administradora de consórcio" in header \
        else header.index("Instituição financeira")
    cnpj_idx = header.index("CNPJ AC") if "CNPJ AC" in header else header.index("CNPJ IF")
    cat_idx = header.index("Categoria") if "Categoria" in header else None
    tipo_idx = header.index("Tipo") if "Tipo" in header else None
    idx_idx = header.index("Índice")
    count_plan = [(header.index(k), v) for k, v in _COUNTS.items() if k in header]

    rows = []
    for raw in rdr:
        if not any(_cell(c) for c in raw):
            continue
        row = {
            "ano": _cell(raw[0]),
            "periodo": _cell(raw[per_idx]) if per_idx is not None else None,
            "cnpj_root": _cell(raw[cnpj_idx]),
            "name": _cell(raw[name_idx]),
            "indice": _num(raw[idx_idx]),
        }
        if cat_idx is not None:
            row["categoria"] = _cell(raw[cat_idx])
        if tipo_idx is not None:
            row["tipo"] = _cell(raw[tipo_idx])
        for i, key in count_plan:
            row[key] = _num(raw[i])
        rows.append(row)
    return rows


def _catalog_axes(anos):
    """catalog list -> {(tipo, ano, periodicidade, periodo)} + ordered period slots per tipo."""
    slots = {"banks": [], "consortiums": []}
    for a in anos:
        year = a.get("ano")
        for p in a.get("periodicidades") or []:
            per = p.get("periodicidade")
            for s in p.get("periodos") or []:
                for t in s.get("tipos") or []:
                    key = {"Bancos e financeiras": "banks", "Consorcios": "consortiums"}.get(
                        t.get("tipo"))
                    if key:
                        slots[key].append((year, per, s.get("periodo")))
    return slots


def _combo_help(slots, tipo, ano=None):
    """compact catalog listing for usage_error messages (the closed set, straight from upstream)."""
    seen = []
    for year, per, periodo in slots[tipo]:
        if ano is not None and year != ano:
            continue
        if seen and seen[-1][0] == year and seen[-1][1] == per:
            seen[-1][2].append(periodo)
        else:
            seen.append([year, per, [periodo]])
    return "; ".join(f"{y} {p} " + "/".join(str(x) for x in ps) for y, p, ps in seen)


def complaints_raw(name=None, *, ano=None, periodicidade=None, periodo=None, tipo="banks",
                   cnpj=None, limit=20, cache=None, no_cache=False):
    """One period's CSV -> {rows, total_matched, scanned_rows, census, limit_applied, params,
    _meta, _metas}. (ano, periodicidade, periodo) default to the catalog's LATEST slot for the
    tipo; explicit values are validated against the catalog — a ghost combination is answered
    with the available combos instead of a 0-byte request (upstream answers those HTTP 204)."""
    from ..transport import call_provider
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="br_bacen_complaints",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    if tipo not in _TIPO:
        raise SdkError("usage_error", provider="br_bacen_complaints",
                       detail=f"tipo must be one of {sorted(_TIPO)} (banks=Bancos e financeiras, "
                              f"consortiums=Consorcios), got {tipo!r}")
    c = str(cnpj).strip() if cnpj not in (None, "") else None
    if c is not None and not (c.isdigit() and len(c) in (8, 14)):
        raise SdkError("usage_error", provider="br_bacen_complaints",
                       detail=f"cnpj must be the 8-digit root or the 14-digit whole key "
                              f"(matched on the first 8 digits), got {cnpj!r}")
    needle = str(name or "").strip().lower() or None

    r_cat = call_provider(provider, "anos", {}, cache=cache, no_cache=no_cache)
    cat = r_cat["data"]
    anos = (cat.get("anos") if isinstance(cat, dict) else None) or \
        (json.loads(cat).get("anos") if isinstance(cat, str) else [])
    slots = _catalog_axes(anos)

    want_year = str(ano).strip() if ano not in (None, "") else None
    if want_year is not None and not (want_year.isdigit() and 2014 <= int(want_year) <= 2100):
        raise SdkError("usage_error", provider="br_bacen_complaints",
                       detail=f"ano must be a catalog year (2014-2026 live), got {ano!r}")
    years = sorted({s[0] for s in slots[tipo]})
    if not years:
        raise SdkError("usage_error", provider="br_bacen_complaints",
                       detail=f"the catalog carries no {tipo} periods; available: "
                              f"{_combo_help(slots, 'banks' if tipo == 'consortiums' else 'consortiums')}")
    # resolution order (the live --periodo 4 lesson): year FIRST — defaults to the latest year
    # with periods for the tipo; periodicidade/periodo are then validated WITHIN that year.
    # (Resolving a pinned periodo across all years would silently land on an old-year panel.)
    year = want_year or years[-1]
    pick = [s for s in slots[tipo] if s[0] == year]
    if not pick:
        raise SdkError("usage_error", provider="br_bacen_complaints",
                       detail=f"no {tipo} periods for ano={year!r} in the catalog; "
                              f"available: {_combo_help(slots, tipo)}")
    if periodicidade is not None:
        pp = [s for s in pick if s[1] == periodicidade]
        if not pp:
            raise SdkError("usage_error", provider="br_bacen_complaints",
                           detail=f"periodicidade {periodicidade!r} not published for ano={year} "
                                  f"tipo={tipo!r}; available for {year}: "
                                  f"{_combo_help(slots, tipo, year)}"
                                  + (" — older panels: pass an explicit --ano" if year == years[-1] else ""))
        pick = pp
    if periodo is not None:
        try:
            pnum = int(periodo)
        except (TypeError, ValueError):
            pnum = None
        pp = [s for s in pick if s[2] == pnum]
        if not pp:
            raise SdkError("usage_error", provider="br_bacen_complaints",
                           detail=f"periodo {periodo!r} not published for ano={year} tipo={tipo!r} "
                                  f"periodicidade={periodicidade or pick[-1][1]}; available for "
                                  f"{year}: {_combo_help(slots, tipo, year)}"
                                  + (" — older panels: pass an explicit --ano" if year == years[-1] else ""))
        pick = pp
    year, per, pnum = pick[-1]  # catalog order — the latest slot within the resolved year

    r_csv = call_provider(provider, "arquivo",
                          {"ano": year, "periodicidade": per, "periodo": pnum,
                           "tipo": _TIPO[tipo]}, cache=cache, no_cache=no_cache)
    rows = rows_from_upstream(r_csv["data"])

    hits = []
    for x in rows:
        if needle and needle not in str(x.get("name") or "").lower():
            continue
        if c and (x.get("cnpj_root") or "")[:8] != c[:8]:
            continue
        hits.append(x)

    by_tipo, by_cat = {}, {}
    for x in rows:
        if x.get("tipo"):
            by_tipo[x["tipo"]] = by_tipo.get(x["tipo"], 0) + 1
        if x.get("categoria"):
            by_cat[x["categoria"]] = by_cat.get(x["categoria"], 0) + 1
    indices = [x["indice"] for x in rows if isinstance(x.get("indice"), (int, float))]
    census = {
        "total": len(rows),
        "by_tipo": by_tipo,
        "by_categoria": by_cat,
        "with_cnpj_root": sum(1 for x in rows if x.get("cnpj_root")),
        "with_indice": len(indices),
        "indice_max": max(indices) if indices else None,
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"name": name or None, "ano": year, "periodicidade": per,
                       "periodo": pnum, "tipo": tipo, "cnpj": c},
            "_meta": r_cat, "_metas": [r_cat, r_csv]}
