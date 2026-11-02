"""procurement cli — domain command-face registration (seventh package, stood up in 0.3.0, born flat — no verb layer).

register(v, g): registers flat commands onto the domain subparser (g = root _leaf_globals factory); FLAT = flat dispatch
table, merged by the root cli for main to use (same shape as the 0.2.6 per-domain split). Face order = lexicographic by
face name (sorting source of truth = the English identifier).
"""
import argparse

def register(v, g):
    # procurement 0.3.0 founding pair (pncp_contracts/co_secop_contracts) + 0.3.6 World Bank + New York State batch
    # (wb_proc/ny_open_data; upstream param names mirrored) — all folded in lexicographically by 0.3.10; 0.3.12 collection
    # round adds the UNGM/NY OGS batch (ungm/ny_open_data) under the same law; 0.3.13 ISO country-prefix machine batch
    # renames pncp_contracts -> br_pncp_contracts and secop_contracts -> co_secop_contracts (provider ids follow the module names)

    f1 = v.add_parser("br_pncp_contracts", parents=[g()],
                      help="Brazil public-procurement contracts (PNCP, keyless)",
                      description="Brazil national procurement contracts (Portal Nacional de Contratações Públicas, "
                                  "keyless): publication-window search over /api/consulta/v1/contratos — every row is "
                                  "buyer CNPJ × supplier CNPJ with the four valor columns; join straight onto the RFB "
                                  "register. data_inicial/data_final (YYYYMMDD or YYYY-MM-DD) and pagina are upstream "
                                  "verbatim (500 rows/page); cnpj_orgao narrows to one buyer. PF (individual) supplier "
                                  "rows carry their identifier and name masked per the PII rule")
    f1.add_argument("--data-inicial", required=True, help="Publication-window start (upstream param: dataInicial; YYYYMMDD or YYYY-MM-DD)")
    f1.add_argument("--data-final", required=True, help="Publication-window end (upstream param: dataFinal)")
    f1.add_argument("--pagina", type=int, default=1, help="Page number (upstream param: pagina, 1-based; 500 rows/page)")
    f1.add_argument("--cnpj-orgao", default=None, help="Buyer CNPJ 14-digit filter (upstream param: cnpjOrgao)")

    f2 = v.add_parser("co_secop_contracts", parents=[g()],
                      help="Colombia SECOP II electronic contracts (keyless)",
                      description="Colombia SECOP II electronic contracts (datos.gov.co Socrata dataset jbjy-vk9h, "
                                  "keyless): 5.6M+ contracts — buyer NIT × supplier NIT/CC with the valor family; join "
                                  "straight onto the RUES register. where is the raw SoQL $where channel (verbatim "
                                  "pass-through); limit/offset/order mirror $limit/$offset/$order. No total echo — page "
                                  "with offset. Personal-document (Cédula etc.) supplier rows carry their identifier "
                                  "and name masked per the PII rule")
    f2.add_argument("--where", default=None, help="Raw SoQL filter (upstream param: $where; e.g. \"upper(nombre_entidad) like '%%MINISTERIO%%'\")")  # %% escaping: argparse help goes through % interpolation
    f2.add_argument("--limit", type=int, default=20, help="Rows (upstream param: $limit; 1-500 politeness cap)")
    f2.add_argument("--offset", type=int, default=0, help="Row offset (upstream param: $offset; Socrata has no total echo)")
    f2.add_argument("--order", default=None, help="Sort (upstream param: $order; column [ASC|DESC] — no NULLS syntax)")

    f3 = v.add_parser("ny_abo_contracts", parents=[g()],
                      help="New York State authority contracts (ABO, keyless)",
                      description="New York State authority contracts (data.ny.gov Socrata dataset ehig-g5x3, "
                                  "keyless): 275k+ rows from the Authorities Budget Office universe — buyer "
                                  "authority_name × vendor_name + full address (no UEI/DUNS; name+address walk), "
                                  "four value columns plus MWBE / NYS-business preference flags. where is the raw SoQL "
                                  "$where channel; limit/offset/order mirror $limit/$offset/$order. No total echo — "
                                  "page with offset")
    f3.add_argument("--where", default=None, help="Raw SoQL filter (upstream param: $where; e.g. \"upper(vendor_name) like '%%DELTA%%'\")")
    f3.add_argument("--limit", type=int, default=20, help="Rows (upstream param: $limit; 1-500 politeness cap)")
    f3.add_argument("--offset", type=int, default=0, help="Row offset (upstream param: $offset; Socrata has no total echo)")
    f3.add_argument("--order", default=None, help="Sort (upstream param: $order; column [ASC|DESC] — no NULLS syntax)")

    f4 = v.add_parser("ny_mta_procurements", parents=[g()],
                      help="New York MTA procurements (keyless)",
                      description="New York MTA procurements (data.ny.gov Socrata dataset twsw-2mqa, keyless): "
                                  "107k+ rows — buyer is always the MTA; vendor_name + value family + "
                                  "vendor_is_nys_or_fbe preference flag. where is the raw SoQL $where channel; "
                                  "limit/offset/order mirror $limit/$offset/$order. No total echo — page with offset")
    f4.add_argument("--where", default=None, help="Raw SoQL filter (upstream param: $where; e.g. \"upper(vendor_name) like '%%SKANSKA%%'\")")
    f4.add_argument("--limit", type=int, default=20, help="Rows (upstream param: $limit; 1-500 politeness cap)")
    f4.add_argument("--offset", type=int, default=0, help="Row offset (upstream param: $offset; Socrata has no total echo)")
    f4.add_argument("--order", default=None, help="Sort (upstream param: $order; column [ASC|DESC] — no NULLS syntax)")

    f5 = v.add_parser("ny_ogs_payments", parents=[g()],
                      help="New York OGS design & construction payments (keyless)",
                      description="New York State Office of General Services design & construction payments "
                                  "(data.ny.gov Socrata dataset rb9h-9fit, keyless): 69k+ payment rows — "
                                  "buyer is always OGS; each row is contractnumber × vendor × paymentamount "
                                  "with fiscalyear/quarter/county (no address columns — name walk). Completes "
                                  "the New York trio (ABO authorities / MTA transport / OGS construction) "
                                  "buyer universe. where is the raw SoQL $where channel; limit/offset/order "
                                  "mirror $limit/$offset/$order. No total echo — page with offset")
    f5.add_argument("--where", default=None, help="Raw SoQL filter (upstream param: $where; e.g. \"upper(vendor) like '%%HIGHLAND%%'\")")
    f5.add_argument("--limit", type=int, default=20, help="Rows (upstream param: $limit; 1-500 politeness cap)")
    f5.add_argument("--offset", type=int, default=0, help="Row offset (upstream param: $offset; Socrata has no total echo)")
    f5.add_argument("--order", default=None, help="Sort (upstream param: $order; column [ASC|DESC] — no NULLS syntax)")

    f6 = v.add_parser("ungm_contract_awards", parents=[g()],
                      help="UN Global Marketplace contract-award search (keyless)",
                      description="United Nations Global Marketplace contract awards (www.ungm.org public "
                                  "search, keyless): ~50k awards across the UN-agency buyer universe "
                                  "(UNDP/UNFPA/ILO/UNOPS...) × global vendors — each row is award id + "
                                  "title/vendor/award date/agency/reference/supplier country. supplier/title/"
                                  "reference/award_from/award_to/countries/agencies/unspscs are upstream "
                                  "verbatim; page_index (1-based) and page_size (1-100, site default 15) "
                                  "page through; newest first by default (sort_field=AwardDate, "
                                  "sort_ascending=false). The ASP.NET anti-forgery session pairing is "
                                  "handled internally (15-minute reuse, auto re-bootstrap on expiry)")
    f6.add_argument("--supplier", default=None, help="Vendor name filter (upstream param: Supplier; e.g. DELTA)")
    f6.add_argument("--title", default=None, help="Title text filter (upstream param: Title)")
    f6.add_argument("--reference", default=None, help="Reference filter (upstream param: Reference; e.g. rfx_11130_ROAP)")
    f6.add_argument("--award-from", default=None, help="Award date window start (upstream param: AwardFrom; site picker format dd-MMM-yyyy)")
    f6.add_argument("--award-to", default=None, help="Award date window end (upstream param: AwardTo)")
    f6.add_argument("--countries", nargs="+", default=None, help="Project-country filter list (upstream param: Countries[])")
    f6.add_argument("--agencies", nargs="+", default=None, help="UN-agency filter list (upstream param: Agencies[]; e.g. UNDP ILO)")
    f6.add_argument("--unspscs", nargs="+", default=None, help="UNSPSC code filter list (upstream param: UNSPSCs[])")
    f6.add_argument("--page-index", type=int, default=1, help="Page number (upstream param: PageIndex, 1-based)")
    f6.add_argument("--page-size", type=int, default=15, help="Page size (upstream param: PageSize; 1-100 politeness cap, site default 15)")
    f6.add_argument("--sort-field", default="AwardDate", help="Sort field (upstream param: SortField; default AwardDate — never empty: null makes the upstream 500)")
    f6.add_argument("--sort-ascending", action="store_true", help="Sort ascending (upstream param: SortAscending; default false = newest first)")

    f7 = v.add_parser("wb_procnotices", parents=[g()],
                      help="World Bank procurement notices (keyless)",
                      description="World Bank procurement notice stream (search.worldbank.org /api/v2/procnotices, "
                                  "keyless): 313k+ notices across the MDB buyer universe (IBRD/IDA projects in 100+ "
                                  "countries). notice_type/rows/os are upstream verbatim (default: Contract Award); "
                                  "supplier keys are extracted from the embedded award section into "
                                  "awarded_firms[]{name, supp_id} — firm name + WB supplier id, joinable onto the WB "
                                  "debarred list. notice_text itself is not returned (embedded contact details stay "
                                  "out of the face)")
    f7.add_argument("--notice-type", default="Contract Award", help="Notice type (upstream param: notice_type; e.g. Contract Award, General Procurement Notice)")
    f7.add_argument("--rows", type=int, default=10, help="Page size (upstream param: rows; 1-100 politeness cap)")
    f7.add_argument("--os", type=int, default=0, help="Offset (upstream param: os)")


FLAT = {
    # procurement flat panel (upstream param names verbatim + our defaults; lambdas only shuttle names across namespaces).
    # 0.3.6 additions: the World Bank notice stream + the NY Socrata twin faces; 0.3.12 collection additions: the UNGM award
    # search + the NY OGS third face; 0.3.13 renames pncp_contracts -> br_pncp_contracts, secop_contracts -> co_secop_contracts
    # — all folded in lexicographically
    "br_pncp_contracts": lambda a: {"data_inicial": a.data_inicial, "data_final": a.data_final,
                                 "pagina": a.pagina, "cnpj_orgao": a.cnpj_orgao},
    "co_secop_contracts": lambda a: {"where": a.where, "limit": a.limit,
                                  "offset": a.offset, "order": a.order},
    "ny_abo_contracts": lambda a: {"where": a.where, "limit": a.limit,
                                   "offset": a.offset, "order": a.order},
    "ny_mta_procurements": lambda a: {"where": a.where, "limit": a.limit,
                                      "offset": a.offset, "order": a.order},
    "ny_ogs_payments": lambda a: {"where": a.where, "limit": a.limit,
                                  "offset": a.offset, "order": a.order},
    "ungm_contract_awards": lambda a: {"supplier": a.supplier, "title": a.title,
                                       "reference": a.reference, "award_from": a.award_from,
                                       "award_to": a.award_to, "countries": a.countries,
                                       "agencies": a.agencies, "unspscs": a.unspscs,
                                       "page_index": a.page_index, "page_size": a.page_size,
                                       "sort_field": a.sort_field, "sort_ascending": a.sort_ascending},
    "wb_procnotices": lambda a: {"notice_type": a.notice_type, "rows": a.rows, "os": a.os},
}


# 0.3.10 jurisdiction chapter: face -> jurisdiction (default = the issuing authority's jurisdiction; institutions
# covering global phenomena = GLOBAL; vocabulary ISO-3166 alpha-2 + EU + GLOBAL) — merged by the root cli.py
# into _JURISDICTION, the success envelope carries a jurisdiction chapter;
# 0.3.12 collection: +ungm_contract_awards=GLOBAL (a global UN institution), +ny_ogs_payments=US;
# 0.3.13 renames pncp_contracts -> br_pncp_contracts, secop_contracts -> co_secop_contracts (jurisdictions unchanged)
COUNTRY = {
    "br_pncp_contracts": "BR",
    "co_secop_contracts": "CO",
    "ny_abo_contracts": "US",
    "ny_mta_procurements": "US",
    "ny_ogs_payments": "US",
    "ungm_contract_awards": "GLOBAL",
    "wb_procnotices": "GLOBAL",
}
