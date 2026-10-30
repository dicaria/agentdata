"""procurement faces — flat face-method mixin (0.3.0 seventh package, born flat).

Mixes into the root _Domain (assembled via MRO, see client.py); discipline: no __init__,
depend only on root internals (_flat_env/_c/_request…), method names globally unique across
domains (a collision would shadow another domain's face).
"""
from . import ny_open_data, pncp, secop, ungm, wb_proc
from ..errors import SdkError


class ProcurementFaces:
    def _pr_only(self, tool: str):
        if self.name != "procurement":
            raise SdkError("usage_error", detail=f"{tool} is a procurement-domain capability (not available on the {self.name} domain)")

    def pncp_contracts(self, data_inicial, data_final, *, pagina=1, cnpj_orgao=None,
                       execution=None, no_cache=None):
        """procurement pncp_contracts: Brazil national procurement contract window
        (PNCP /api/consulta/v1/contratos; data_inicial/data_final/pagina mirrored verbatim,
        cnpj_orgao optional buyer filter — pinned by the SpringDoc spec).
        Rows = buyer CNPJ × supplier CNPJ bilateral + the four amount columns; PF supplier rows
        are masked per the PII red line."""
        self._pr_only("pncp_contracts")
        r = pncp.contracts_raw(data_inicial, data_final, pagina=pagina, cnpj_orgao=cnpj_orgao,
                               cache=self._c._cache, no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        n_masked = sum(1 for x in rows if x.get("fornecedorMascarado"))
        org = rows[0]["orgaoEntidade"] if rows else {}
        w = f"{r['params']['dataInicial']}–{r['params']['dataFinal']}"
        if rows:
            reason = (f"PNCP contract window {w}: {res['total']:,} contracts in the window over "
                      f"{res['total_paginas']} pages (500 rows/page), page {pagina} returned {len(rows)} rows "
                      f"(sample buyer {org.get('razaoSocial') or '—'}) — buyer × supplier CNPJ joins straight onto the RFB register"
                      + (f"; {n_masked} PF (individual) supplier rows masked per the PII red line" if n_masked else ""))
        else:
            reason = f"PNCP contract window {w}: page {pagina} returned 0 rows — an empty window or an out-of-range page is a legitimate answer (total={res['total']})"
        ev = [{"quote": f"{x['numeroControlePNCP']} — {x['orgaoEntidade'].get('razaoSocial') or '—'} × "
                        f"{x.get('nomeRazaoSocialFornecedor') or '(PF masked)'} — "
                        f"{x.get('valorGlobal')} BRL",
               "url": "https://pncp.gov.br/api/consulta/v1/contratos"}
              for x in rows[:3] if x.get("numeroControlePNCP")]
        return self._flat_env(tool="pncp_contracts",
                              input={"data_inicial": data_inicial, "data_final": data_final,
                                     "pagina": pagina, "cnpj_orgao": cnpj_orgao},
                              reason=reason, result=res, evidence=ev, provider_id="pncp",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    def secop_contracts(self, where=None, *, limit=20, offset=0, order=None,
                        execution=None, no_cache=None):
        """procurement secop_contracts: Colombia SECOP II electronic contracts (datos.gov.co
        Socrata jbjy-vk9h; where→$where raw SoQL verbatim channel, limit/offset/order mirrored
        by the same names). 5.66M contracts corpus-wide; rows = buyer NIT × supplier NIT
        bilateral + the amount family; personal-document supplier rows are masked per the PII
        red line."""
        self._pr_only("secop_contracts")
        r = secop.contracts_raw(where, limit=limit, offset=offset, order=order,
                                cache=self._c._cache, no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        n_masked = sum(1 for x in rows if x.get("proveedorMascarado"))
        if rows:
            reason = (f"SECOP II electronic contracts: {len(rows)} rows returned (from offset={offset}; "
                      f"Socrata sends no total echo) — buyer NIT × supplier NIT joins straight onto "
                      f"the RUES register (sample {rows[0].get('nombre_entidad') or '—'})"
                      + (f"; {n_masked} personal-document (CC etc.) supplier rows masked per the PII red line" if n_masked else ""))
        else:
            reason = "SECOP II: 0 rows — either the where filter has no match or offset is past the end; both are legitimate answers (not errors)"
        ev = [{"quote": f"{x.get('id_contrato')} — {x.get('nombre_entidad') or '—'} × "
                        f"{x.get('proveedor_adjudicado') or '(personal masked)'} — "
                        f"{x.get('valor_del_contrato')} COP",
               "url": "https://datos.gov.co/resource/jbjy-vk9h.json"}
              for x in rows[:3] if x.get("id_contrato")]
        return self._flat_env(tool="secop_contracts",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="secop",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    def wb_procnotices(self, notice_type="Contract Award", *, rows=10, os=0,
                       execution=None, no_cache=None):
        """procurement wb_procnotices: World Bank procurement notice stream (search.worldbank.org /api/v2/procnotices;
        notice_type/rows/os mirrored verbatim, default = award notices). 313k notices in full — the MDB buyer universe
        (IBRD/IDA development projects in 100+ countries); supplier keys are extracted from the embedded notice_text
        section (awarded_firms[]{name, supp_id} — firm name + WB supplier id), notice_text itself is not returned
        (embedded contact addresses/phones stay out of the face)."""
        self._pr_only("wb_procnotices")
        r = wb_proc.procnotices_raw(notice_type, rows=rows, os_=os,
                                    cache=self._c._cache, no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        prows = res["rows"]
        n_firms = sum(len(x["awarded_firms"]) for x in prows)
        if prows:
            total_str = f"{res['total']:,}" if res["total"] is not None else "not echoed upstream"
            reason = (f"World Bank procurement notices ({r['params']['notice_type']}): {total_str} notices in full, "
                      f"offset {os} returned {len(prows)} rows — this page extracted {n_firms} awarded suppliers "
                      f"(firm name + WB supplier id supp_id, cross-checkable against the WB debarred list on the same key)")
        else:
            reason = (f"World Bank procurement notices ({r['params']['notice_type']}): 0 rows — "
                      f"an out-of-range os or a notice_type with no such value is a legitimate answer (total={res['total']})")
        ev = [{"quote": f"{x['id']} — {x['project_ctry_name']} — {x['project_id']} — "
                        f"{' / '.join(f['name'] + ' (' + f['supp_id'] + ')' for f in x['awarded_firms']) or '(no award section in notice)'}",
               "url": "https://search.worldbank.org/api/v2/procnotices"}
              for x in prows[:3] if x.get("id")]
        return self._flat_env(tool="wb_procnotices",
                              input={"notice_type": notice_type, "rows": rows, "os": os},
                              reason=reason, result=res, evidence=ev, provider_id="wb_proc",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    def ny_abo_contracts(self, where=None, *, limit=20, offset=0, order=None,
                         execution=None, no_cache=None):
        """procurement ny_abo_contracts: New York State authority contracts (data.ny.gov Socrata ehig-g5x3;
        where→$where raw SoQL verbatim channel, limit/offset/order mirrored by the same names). 276k rows corpus-wide —
        authority_name buyer authority × vendor_name + full-address supplier (no UEI/DUNS, name walk),
        four value columns + the MWBE/NYS procurement-preference flag family."""
        self._pr_only("ny_abo_contracts")
        r = ny_open_data.abo_contracts_raw(where, limit=limit, offset=offset, order=order,
                                           cache=self._c._cache, no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        if rows:
            reason = (f"NY State authority contracts (ABO): returned {len(rows)} rows (from offset={offset}; Socrata sends no total echo)"
                      f" — buyer authority_name × supplier vendor_name + full address (name+address walk)"
                      f" (sample {rows[0].get('authority_name') or '—'} × {rows[0].get('vendor_name') or '—'})")
        else:
            reason = "NY ABO: 0 rows — either the where filter has no match or offset is past the end; both are legitimate answers (not errors)"
        ev = [{"quote": f"{x.get('authority_name') or '—'} × {x.get('vendor_name') or '—'} — "
                        f"{x.get('contract_amount') or '—'} USD (awarded {x.get('award_date') or '—'})",
               "url": "https://data.ny.gov/resource/ehig-g5x3.json"}
              for x in rows[:3] if x.get("vendor_name")]
        return self._flat_env(tool="ny_abo_contracts",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="ny_open_data",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    def ny_mta_procurements(self, where=None, *, limit=20, offset=0, order=None,
                            execution=None, no_cache=None):
        """procurement ny_mta_procurements: New York MTA procurements (data.ny.gov Socrata twsw-2mqa;
        where→$where raw SoQL verbatim channel, limit/offset/order mirrored by the same names). 107k rows corpus-wide —
        buyer is always the MTA, vendor_name supplier + value family + vendor_is_nys_or_fbe preference flag."""
        self._pr_only("ny_mta_procurements")
        r = ny_open_data.mta_procurements_raw(where, limit=limit, offset=offset, order=order,
                                              cache=self._c._cache, no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        if rows:
            reason = (f"NY MTA procurements: returned {len(rows)} rows (from offset={offset}; Socrata sends no total echo)"
                      f" — supplier vendor_name + full address (buyer is always the MTA)"
                      f" (sample {rows[0].get('vendor_name') or '—'} — {rows[0].get('contract_amount') or '—'} USD)")
        else:
            reason = "NY MTA: 0 rows — either the where filter has no match or offset is past the end; both are legitimate answers (not errors)"
        ev = [{"quote": f"MTA × {x.get('vendor_name') or '—'} — {x.get('contract_amount') or '—'} USD"
                        f" (awarded {x.get('award_date') or '—'}, {x.get('status') or '—'})",
               "url": "https://data.ny.gov/resource/twsw-2mqa.json"}
              for x in rows[:3] if x.get("vendor_name")]
        return self._flat_env(tool="ny_mta_procurements",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="ny_open_data",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    def ungm_contract_awards(self, supplier=None, *, title=None, reference=None,
                             award_from=None, award_to=None, countries=None, agencies=None,
                             unspscs=None, page_index=1, page_size=15, sort_field="AwardDate",
                             sort_ascending=False, execution=None, no_cache=None):
        """procurement ungm_contract_awards：联合国全球市场授标搜索（www.ungm.org/Public/ContractAward
        PublicSearch；Supplier/Title/Reference/AwardFrom/AwardTo/Countries/Agencies/UNSPSCs
        上游原名，page_index/page_size 翻页）。全库 ~5 万条——UN 机构买方宇宙（UNDP/UNFPA/ILO/
        UNOPS…）×全球供方（vendor 名+供应商国家）；行=id（授标键）+六槽。反伪造配对会话
        15 分钟自动复用，400 即重采；浏览器 UA 门控在 provider 层已内建。"""
        self._pr_only("ungm_contract_awards")
        r = ungm.awards_raw(supplier, title=title, reference=reference, award_from=award_from,
                            award_to=award_to, countries=countries, agencies=agencies,
                            unspscs=unspscs, page_index=page_index, page_size=page_size,
                            sort_field=sort_field, sort_ascending=sort_ascending,
                            cache=self._c._cache,
                            no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        n_vendor = sum(1 for x in rows if x.get("vendor"))
        if rows:
            reason = (f"UNGM 授标搜索：全量 {res['total']:,} 条命中，第 {page_index} 页返回 {len(rows)} 行"
                      f"（{n_vendor} 行带供方名）——UN 机构买方 × 全球供方"
                      + (f"，supplier=「{supplier}」" if supplier else "")
                      + f"（样例 {rows[0].get('agency') or '—'} × {rows[0].get('vendor') or '—'}，"
                        f"{rows[0].get('award_date') or '—'} 授标）")
        else:
            reason = (f"UNGM 授标搜索：0 行——过滤无命中或页号越界均为合法答案"
                      f"（total={res['total']}）")
        ev = [{"quote": f"{x['id']} — {x.get('agency') or '—'} × {x.get('vendor') or '—'} — "
                        f"{x.get('supplier_country') or '—'}（{x.get('award_date') or '—'}）",
               "url": f"https://www.ungm.org/Public/ContractAward/{x['id']}"}
              for x in rows[:3] if x.get("id")]
        return self._flat_env(tool="ungm_contract_awards",
                              input={"supplier": supplier, "title": title, "reference": reference,
                                     "award_from": award_from, "award_to": award_to,
                                     "countries": countries, "agencies": agencies,
                                     "unspscs": unspscs, "page_index": page_index,
                                     "page_size": page_size, "sort_field": sort_field,
                                     "sort_ascending": sort_ascending},
                              reason=reason, result=res, evidence=ev, provider_id="ungm",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    def ny_ogs_payments(self, where=None, *, limit=20, offset=0, order=None,
                        execution=None, no_cache=None):
        """procurement ny_ogs_payments：纽约州总务署 D&C 付款（data.ny.gov Socrata rb9h-9fit；
        where→$where 裸 SoQL 原名通道、limit/offset/order 同名镜像）。全库 6.9 万行——买方恒
        OGS，行=contractnumber×vendor×paymentamount+fiscalyear/quarter/county（无地址列，
        name walk 单键标识）；与 ABO/MTA 双面拼齐纽约州三买方宇宙。"""
        self._pr_only("ny_ogs_payments")
        r = ny_open_data.ogs_dc_payments_raw(where, limit=limit, offset=offset, order=order,
                                             cache=self._c._cache,
                                             no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        if rows:
            reason = (f"NY OGS D&C 付款：返回 {len(rows)} 行（offset={offset} 起；Socrata 无 total 回显）"
                      f"——买方恒 OGS，contractnumber×vendor×paymentamount 三柱"
                      f"（样例 {rows[0].get('vendor') or '—'} — {rows[0].get('paymentamount') or '—'} USD，"
                      f"{rows[0].get('fiscalyear') or '—'} Q{rows[0].get('quarter') or '—'}）")
        else:
            reason = "NY OGS：0 行——where 过滤无命中或 offset 越界，均为合法答案（非错误）"
        ev = [{"quote": f"OGS × {x.get('vendor') or '—'} — {x.get('paymentamount') or '—'} USD"
                        f"（{x.get('contractnumber') or '—'}，{x.get('fiscalyear') or '—'} Q{x.get('quarter') or '—'}）",
               "url": "https://data.ny.gov/resource/rb9h-9fit.json"}
              for x in rows[:3] if x.get("vendor")]
        return self._flat_env(tool="ny_ogs_payments",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="ny_open_data",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})
