"""agentdata.cli — the dual command-line entry (console_scripts `agentdata` + `python -m agentdata`).

Exit-code contract: 0 success / 1 upstream-availability family / 2 usage family (api.md section 9.4).
enrichment works with zero config; the corpus family needs --base-url/--api-key (or env
AGENTDATA_BASE_URL / AGENTDATA_API_KEY).
"""
import argparse
import json
import sys
import uuid

from . import __version__
from . import capabilities as capabilities_mod
from .client import Client
from .company import cli as company_cli
from .economy import cli as economy_cli
from .esg import cli as esg_cli
from .healthcare import cli as healthcare_cli
from .legal import cli as legal_cli
from .procurement import cli as procurement_cli
from .research import cli as research_cli
from .security import cli as security_cli
from .transportation import cli as transportation_cli

# 0.2.6 per-domain split: the domain command registrars (register(v, g)) live in each domain's cli.py;
# the root keeps only the shared parts plus the search/read dispatch
# 0.3.10 domain order = lexicographic (DOMAIN_ORDER is the source of truth — the build_parser loop, per-domain face order, and site navigation all follow it; the sort key is the English identifier)
DOMAIN_ORDER = ("company", "economy", "esg", "healthcare", "legal", "procurement", "research", "security", "transportation")
_CLI = {"company": company_cli, "economy": economy_cli, "esg": esg_cli,
        "healthcare": healthcare_cli, "legal": legal_cli, "procurement": procurement_cli,
        "research": research_cli, "security": security_cli,
        "transportation": transportation_cli}
from .errors import SdkError


def _filter_arg(pairs):
    """--filter 'k=v' / 'k=v1|v2' / 'k>=v' / 'k>v' / 'k<=v' / 'k<v' -> a DSL node."""
    filters = {}
    for raw in pairs or []:
        for op_key, op in ((">=", "gte"), ("<=", "lte"), (">", "gt"), ("<", "lt")):
            if op_key in raw:
                k, _, v = raw.partition(op_key)
                filters.setdefault(k, {"range": {}})["range"][op] = _cast(v)
                break
        else:
            k, _, v = raw.partition("=")
            if "|" in v:
                filters[k] = {"any": v.split("|")}
            else:
                filters[k] = {"eq": _cast(v)}
    return filters


def _cast(v):
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        return v


def _leaf_globals():
    """Global flags placed after a subcommand (the README example shape `agentdata company search … --api-key x`).
    The dest gets a sub_ prefix + default=argparse.SUPPRESS: when argparse enters a subparser it opens
    a separate namespace, parses there and writes the whole thing back into the parent namespace, so a
    dest that carries a default overwrites the value the parent just parsed —
    a global flag between the domain and the verb (`agentdata healthcare --no-cache epmc_search …`)
    is therefore swallowed silently (reproduced by measurement on 2026-10-20). Under SUPPRESS a dest
    that never appeared does not land in the namespace, so the parent's value survives; every read
    uses getattr(…, default)."""
    g = argparse.ArgumentParser(add_help=False)
    g.add_argument("--base-url", dest="sub_base_url", default=argparse.SUPPRESS, metavar="URL", help="Hosted API base URL (env AGENTDATA_BASE_URL)")
    g.add_argument("--api-key", dest="sub_api_key", default=argparse.SUPPRESS, metavar="PAT", help="Bearer PAT (env AGENTDATA_API_KEY)")
    g.add_argument("--cache-dir", dest="sub_cache_dir", default=argparse.SUPPRESS, metavar="DIR", help="Cache directory (env AGENTDATA_CACHE_DIR)")
    g.add_argument("--no-cache", dest="sub_no_cache", action="store_true", default=argparse.SUPPRESS, help="Bypass the cache for this call")
    g.add_argument("--execution", dest="sub_execution", default=argparse.SUPPRESS, choices=["local", "hosted", "auto"], help="Realtime execution location (default auto -> local; realtime faces support local execution only — the hosted corpus uses --base-url/--api-key)")
    return g


def _no_abbrev(v):
    """Turn off argument abbreviation for every subparser registered on this verb parser.

    argparse does NOT inherit allow_abbrev into a subparser: the root's setting would leave every
    face parser at the default True, where `--api-k` silently becomes `--api-key` and a mistyped
    flag is accepted as a prefix of a real one. Wrapping the registrar once per domain is far
    cheaper than touching 172 call sites."""
    orig = v.add_parser

    def add_parser(name, **kw):
        kw.setdefault("allow_abbrev", False)
        return orig(name, **kw)

    v.add_parser = add_parser


def build_parser():
    p = argparse.ArgumentParser(prog="agentdata", allow_abbrev=False,
                                description="AgentData SDK CLI (corpus queries via the hosted API + realtime queries executed locally)")
    p.add_argument("--version", action="version", version=f"agentdata {__version__}")
    p.add_argument("--base-url", default=None, metavar="URL", help="Hosted API base URL (env AGENTDATA_BASE_URL)")
    p.add_argument("--api-key", default=None, metavar="PAT", help="Bearer PAT (env AGENTDATA_API_KEY)")
    p.add_argument("--cache-dir", default=None, metavar="DIR", help="Cache directory (env AGENTDATA_CACHE_DIR)")
    p.add_argument("--no-cache", action="store_true", help="Bypass the cache for this call")
    p.add_argument("--execution", default="auto", choices=["local", "hosted", "auto"],
                   help="Realtime execution location (default auto -> local; realtime faces support local execution only — the hosted corpus uses --base-url/--api-key)")
    sub = p.add_subparsers(dest="domain", required=True)
    for domain in DOMAIN_ORDER:
        d = sub.add_parser(domain, parents=[_leaf_globals()], allow_abbrev=False)
        # metavar="FACE": the usage line stops listing every face name (the legal domain alone
        # spelled 38 of them across three lines) while the per-face catalog below stays intact —
        # argparse lists a subcommand individually as long as it was registered with a help= line.
        v = d.add_subparsers(dest="verb", required=True, metavar="FACE")
        _no_abbrev(v)
        _CLI[domain].register(v, _leaf_globals)

        s = v.add_parser("search", parents=[_leaf_globals()], help="Corpus search (hosted)",
                         description="Corpus search (hosted, PAT required): filters/record_kind/level/pagination")
        s.add_argument("--filter", action="append", default=[], metavar="K=V", help="Filter K=V (repeatable)")
        s.add_argument("--record-kind", default=None, help="Record kind (closed set from the domain spec)")
        s.add_argument("--facets", default=None, help="Comma-separated fields (facet counts)")
        s.add_argument("--level", default="tier1", choices=["tier1", "tier2", "tier3"], help="T-layer depth (default tier1)")
        s.add_argument("--limit", type=int, default=50, help="Page size (default 50, ≤1000)")
        s.add_argument("--cursor", default=None, help="Pagination cursor (feed next_cursor from the response)")
        s.add_argument("--mode", default=None, choices=["screen"], help="Special mode (screen: batch screening; requires --input)")
        s.add_argument("--input", default=None, help="Input JSONL file for batch-screening mode (--mode screen)")

        rd = v.add_parser("read", parents=[_leaf_globals()], help="Corpus record (hosted)",
                          description="Corpus single-record read (hosted): id + T-layer depth")
        rd.add_argument("--id", required=True, help="Subject id")
        rd.add_argument("--level", default="tier1", choices=["tier1", "tier2", "tier3"], help="T-layer depth (default tier1)")

    # hub family (RFC-002 §3.4/3.5): PAT -> short-lived subject JWT -> allowlisted GET; a command
    # group of its own so the eight domain dispatch tables above stay untouched
    h = sub.add_parser("hub", parents=[_leaf_globals()], help="Hub family (PAT to short-lived JWT to allowlisted GET)",
                       description="Hub family (RFC-002): exchange the PAT for a short-lived subject JWT, then GET allowlisted OmniHub paths. The PAT is never printed.")
    hv = h.add_subparsers(dest="hub_verb", required=True)
    ht = hv.add_parser("token", parents=[_leaf_globals()],
                       help="Exchange the PAT for a short-lived Hub subject JWT (prints the access_token envelope, never the PAT)")
    ht.add_argument("--token-url", default=None, help="Downstream-token endpoint (env AGENTDATA_TOKEN_URL)")
    hg = hv.add_parser("get", parents=[_leaf_globals()],
                       help="Allowlisted GET against the Hub (query built only from --param)")
    hg.add_argument("--path", required=True, help="Allowlisted path (RFC-002 §3.5, e.g. /v1/company/companies:search)")
    hg.add_argument("--param", action="append", default=[], metavar="K=V", help="Query parameter K=V (repeatable; strings verbatim)")
    hg.add_argument("--token-url", default=None, help="Downstream-token endpoint (env AGENTDATA_TOKEN_URL)")
    hg.add_argument("--hub-base-url", default=None, help="Hub base URL (env AGENTDATA_HUB_BASE_URL)")

    # The discovery surface (0.3.52): the face table rendered from the command tree. It needs no
    # base URL and no PAT — it describes what this installed package can run.
    cap = sub.add_parser("capabilities", allow_abbrev=False,
                          help="Face table (discovery: every face, its summary and its parameters)",
                          description="The face table rendered from the command tree: every realtime face with "
                                      "its one-line summary, its parameters (closed sets, required flags) and its "
                                      "jurisdiction, plus the hosted corpus family. Generated, not maintained by "
                                      "hand — it cannot drift from the commands it describes.")
    cap.add_argument("--format", choices=["json", "md"], default="json", help="Output format (default json)")
    cap.add_argument("--domain-filter", dest="domain_filter", default=None, choices=list(DOMAIN_ORDER),
                     help="Limit the listing to one domain")
    cap.add_argument("--face", dest="face_filter", default=None, help="Limit the listing to one face (exact name)")
    cap.add_argument("--remote", action="store_true",
                     help="Pull the hosted meta layer (premium family) instead of the local table: "
                          "without --face, the keyless index plus a local↔hosted drift report; with --face, "
                          "the full hosted record (Bearer PAT via env AGENTDATA_API_KEY). "
                          "Gateway = env AGENTDATA_META_BASE_URL. JSON output only.")
    return p


# 0.2.6 per-domain split: the source of truth for the flat dispatch table is each domain's cli.FLAT,
# merged here (the search/read dispatch stays in this module's main)
_FLAT_DISPATCH = {}
for _m in _CLI.values():
    _FLAT_DISPATCH.update(_m.FLAT)
assert len(_FLAT_DISPATCH) == 322, f"flat dispatch {len(_FLAT_DISPATCH)} != 322 (237 faces; 0.3.2 esg +2 + 0.3.3 European registries +5 + 0.3.4 FR recherche +1 + 0.3.5 esg port-state +5 + 0.3.6 World Bank/NY +3 + 0.3.8 legal TNA caselaw +2 + 0.3.12 UNGM/NY OGS collection +2 + 0.3.14 CO RUES/KR hometax +2 + 0.3.16 legal co_sic +1 + healthcare gb_mhra +2 + 0.3.19 healthcare CA DPD/MDALL +4 + rasff/safety_gate +3 + 0.3.21 legal debarment rosters afdb/ca_sema/idb/wb +4 + 0.3.22 transport compliance euasl_datasets +1 + 0.3.23 economy domain (wb/eurostat/ecb/fred/who_xmart/un_comtrade/ilo_stat) +10 + 0.3.24 economy expansion (imf_sdmx/bis/unsd_sdg/wb_ids) +5 + 0.3.25 security EUVD (euvd) +2 + 0.3.26 economy expansion (comext/oecd_sdmx) +2 + 0.3.27 legal gazette/ie_revenue +2 + 0.3.28 legal us_occ +1 + 0.3.29 economy bls_series +1 + 0.3.30 company NZ Companies Office nzco_companies/nzco_directors +2 + 0.3.31 legal CFPB cfpb_complaints/cfpb_suggest_company +2 + 0.3.32 company CZ ARES cz_ares_ekonomicke_subjekty/cz_ares_ekonomicke_subjekty_vyhledat +2 + 0.3.33 company offshore Channel Islands gg_gfsc_regulated_entities/gg_gfsc_registered_businesses/je_jfsc_regulated_entities +3 + 0.3.34 company KZ GBD_UL kz_gbd_ul_companies +1 + 0.3.35 IN SEBI legal in_sebi_orders/company in_sebi_intermediaries+in_sebi_default_brokers +3 + 0.3.36 TR SPK legal tr_spk_fines+tr_spk_bans/company tr_spk_listed +3 + 0.3.37 RU CBR legal ru_cbr_warning_list/company ru_cbr_credit_orgs +2 (first RU jurisdiction) + 0.3.38 BR BACEN legal br_bacen_regimes/company br_bacen_institutions+br_bacen_branches+br_bacen_domains+br_bacen_dasfn +5 (first BR jurisdiction) + 0.3.39 legal br_bacen_complaints rdrweb +1 + 0.3.40 company tr_bddk_institutions BDDK cards +1 + 0.3.41 company DE federal insolvency announcements de_inso_search/de_inso_register_lookup +2 (first DE jurisdiction) + 0.3.42 company JP FSA licensed farm jp_fsa_licensed +1 (first JP jurisdiction) + 0.3.43 company CA OSB CCAA roster ca_ccaa_records +1 + 0.3.44 company ES CNMV entidades register es_cnmv_entities +1 (first ES jurisdiction) + 0.3.45 company ES BORME daily gazette es_borme_day+es_borme_notice +2 (ES jurisdiction #2) + 0.3.46 company SG data.gov.sg open-data platform sg_datagovsg_datasets+sg_datagovsg_dataset_download +2 (first SG jurisdiction — the ACRA register of record rides the national platform) + 0.3.47 legal AT RIS OGD at_ris_judgments+at_ris_statutes +2 (first AT jurisdiction) + 0.3.48 company US state licenses tx_tdlr_licenses+wa_doh_credentials +2 (Socrata twin) + 0.3.49 company US city licenses chi_bacp_licenses+lacity_registrations+nyc_dcwp_licenses +3 (Socrata city trio) + 0.3.50 legal enforcement/party-finance tier us_ferc_elibrary+ie_sipo_lobbying+ee_erjk_quarterly_reports+ee_erjk_election_reports+ua_nazk_parties+ua_nazk_party_reports +6 (first EE and UA jurisdictions) + 0.3.51 legal enforcement tier-two fr_adlc_sanctions+it_arera_decisions+us_cftc_enforcement + company us_fmcsa_carriers +4 (first FR and IT legal jurisdictions) + 0.3.53 company fr_regafi_authorisations+fr_regafi_entities + esg uk_fhrs_establishments + healthcare us_npi_organizations +4 + 0.3.54 transportation domain founding (euasl+paris_mou x4+thetis_mrv from esg + us_fmcsa from company migrated, zero renames; ca_ccar_search+ca_ccar_aircraft new) +2 + 0.3.55 legal NL Rechtspraak zoek+MX CNV sanctions+MX SABG sanctioned servants + esg MX SGM concesiones +4 (first NL and MX legal jurisdictions, first MX esg jurisdiction) + 0.3.56 company DE Unternehmensregister live search + J-PlatPat three-face IP search + KIPRIS patent search (de_register_search/jp_design_search/jp_patent_search/jp_trademark_search/kr_kipris_patents) + legal KR law.go.kr dual-pillar (kr_law_statutes/kr_law_precedents) + healthcare JP NAVII facility search (jp_navii_facilities) +8 (batch B major-economy axis I — pure deepening, zero new jurisdictions) + 0.3.57 legal ES BOE sumario (es_boe_sumario) + company ES OEPM BOPI index (es_oepm_bopi) + TR KAP registers (tr_kap_disclosures/tr_kap_members) +4 (batch C major-economy axis II — pure deepening, zero new jurisdictions; tr_ekap deferred at verify: the human-verification gate came ON) + 0.3.58 company FDIC BankFind suite siblings (fdic_failures/fdic_financials/fdic_history/fdic_locations) + fr_inpi_ratios/fr_inpi_ratios_sectors + legal ca_asc_enforcement/ca_bcsc_disciplined + healthcare br_cnes_facilities +9 (batch D same-stack expansion — pure US/FR/CA/BR deepening, zero new jurisdictions; ca_amf deferred at verify: lautorite.qc.ca CF-403s non-browser clients) + 0.3.59 legal enforcement/party-finance cluster first slice (fr_amf_sanction/fr_amf_transaction/eu_cijeu_search/lv_knab_parties/lv_knab_payments/ch_efk_party_financings/in_indiacode_search/ch_finma_enforcement_news) + company eu_eiopa_iorps +9 (batch E1 — enforcement/party-finance cluster first slice: seven keyless providers across FR/EU/LV/CH/IN; two live-law changes baked in: fr_amf infos-nesting, ch_finma query-mandatory; first LV legal jurisdiction) + 0.3.60 legal API-faces depth wave (au_frl_titles/br_cade_pesquisa_avancada/ca_cbsa_ruling+ca_cbsa_rulings/de_lobbyregister_entries/dk_ft_inspektionsredegoerelser_og_afgoerelser/it_agcm_dettaglio+it_agcm_rating+it_agcm_ricerca_provvedimenti/pl_uokik_decision+pl_uokik_decisions/us_cbp_ruling+us_cbp_stat) + company br_bndes_financiamento +14 (batch E2 — 13 legal + 1 company; four NEW legal jurisdictions AU/DE/DK/PL, zero new countries; eight live-law changes baked in: AU $-options unencoded, CA lang=en mandatory, DE export-only (no server-side filter), DK nested userInput + Referer, IT single-token words, PL TLS-reset retries, US CBP reCAPTCHA-gated search; the csl_screening alias was removed in 0.3.0) + 0.3.61 legal fr_court_judgment+fr_court_judgments+us_occ_ea_search +3 (batch E3 — FR/US pure deepening, zero new jurisdictions; live laws baked in: CAA archives carry NO Numero_ECLI, the monthly-zip directory paths are live though the data.gouv page lags, the OCC export answers the full history filter-less — refused locally) + 0.3.62 legal nl_acm_publication+nl_acm_publication+es_cnmv_sanctions+kr_fss_sanctions +4 (batch E4 — NL/ES/KR pure deepening, zero new jurisdictions; the transport's first POST × bytes combination rides kr_fss; two re-checks stayed deferred: tr_ekap human-verification gate still ON and ca_amf CF still blocking, both re-measured 2026-11-16) + 0.3.63 legal jp_jftc_decisions+jp_jftc_decision+in_cci_antitrust_orders+in_cci_combinations+au_accc_actions +5 (batch E5 — JP/IN/AU pure deepening, zero new jurisdictions, JP's first legal faces; three live-law changes baked in: JFTC is UA-fingerprint-gated with a session-bound Laravel token (the {token, cookie} pair cached together, stale 419s re-bootstrap), CCI's DataTables registers replay byte-equal (antitrust POST / combination GET — the POST answers 405) and its token input carries type BETWEEN name and value, ACCC news-centre is Drupal lazy views (only _wrapper_format=drupal_ajax renders, pages 0-based, pager hrefs entity-escaped); uk_ico and us_fcc went deferred at probe (Cloudflare managed challenge) — E6 re-probe queue) + 0.3.64 legal gb_nmw_rounds+gb_nmw_round+us_cftc_redlist+us_cftc_dispositions +4 (batch E6 — negative-list batch, GB/US pure deepening, zero new jurisdictions; live laws baked in: the gov.uk content API body is empty for NMW press releases so the round detail fetches the HTML and returns the xlsx asset coordinates only (EUASL precedent, list bodies ride the batch line), the CFTC RED List orders alphabetically with scattered entry dates and its ?items_per_page is decorative (widened asks answer zero rows), and the dispositions blurb cell carries the docket number after a <br/>; the two queued re-probes both re-measured negative 2026-11-16: uk_ico's Cloudflare managed challenge now covers the main-site sitemap (was keyless 2026-10-30) and us_fcc still answers the 387B Access-Denied stub — both stay deferred) + 0.3.65 legal us_cftc_opinions +1 (batch E7 — US pure deepening, zero new jurisdictions; the OGC Opinions & Adjudicatory Orders register ≈87 rows 2012→2025 over 9 pages 0..8, three live laws baked in: dual-era PDF paths (recent /sites/default/files/YYYY/MM/ + legacy /idc/groups/public/%40lropinionsandadjudicaryorders/documents/legalpleading/ verbatim — %40=@ and 'adjudicary' is the upstream's own misspelling), the plural-docket list law (multi-docket rows caption 'CFTC Docket Nos. 20-R007; …; and 20-R025' — the whole semicolon list captured as one docket_no), and dockets riding inline in the blurb (unlike dispositions' <br/> placement); survey negatives: kr_ftc reorganized off its boards, CFTC staff-letters is JS-rendered, TED v3 search 429s + key-risk, climate TRACE already shipped since 0.2.6 era — roadmap row stale) + 0.3.66 company us_sec_companyfacts/us_sec_companyconcept/us_sec_frames/us_sec_tickers +4 (batch E8 — the SEC XBRL structured-facts family: US pure deepening, zero new jurisdictions, the 2026-10-19 deferral REOPENED 2026-11-17 (its premise — the local XBRL bulk — was lost with the E: drive, and the MCP/OmniHub PATH_ALLOWLIST surface carries no financial-data paths; user ruling to build it keyless like the rest); one new provider edgar_xbrl on data.sec.gov with the tickers op riding an ABSOLUTE path to www.sec.gov/files/company_tickers.json (build_url passes absolute paths through — one provider id, two hosts); live laws baked in: the concept-drift law (Revenues dead after 2018 -> RevenueFromContractWithCustomerExcludingAssessedTax; Apple lacks EarningsPerShareDiluted — tag names pass through verbatim, never guessed), the fy/fp law (a fact's fy/fp are the FILING's fiscal year, never the fact period's — read periods off start/end), and the frame law (CY<year>/CY<year>Q<n>/CY<year>Q<n>I only); the 10,404-row directory resolves to 7,997 CIKs) + 0.3.68 company E10 developed-economy exchange faces (ch_six_fqs_search/eu_euronext_instrument_search/it_borsa_quote/jp_jpx_stock_detail/jp_jpx_stock_list) +5 — first IT company-domain jurisdiction face, zero new jurisdictions (35 held; two same-day upstream flips deferred: at_wiener_borse TLS serves *.factsetdigitalsolutions.com p1b/p1c; ca_tmx tsx.com AWS WAF JS challenge p2c-p2e — probed green the same morning, challenged by afternoon on every UA incl. the morning's working one; urllib cannot execute challenge JS) + 0.3.69 company us_sec_filing_document +1 (batch E11 — the EDGAR Archives body-fetch face: US pure deepening, zero new jurisdictions; the body layer under the filings line — submissions=index, fts=hit metadata, xbrl=facts, Archives=bytes; one new provider edgar_arch on www.sec.gov/Archives keyless (declared-UA fair access; shared www.sec.gov host bucket with edgar_xbrl tickers); live laws baked in: the SGML-envelope two-shape law (older filings wrap <DOCUMENT><TYPE>…<TEXT>, modern serve bare iXBRL — envelope split with greedy-to-last-</TEXT>), the index.json pure-directory law (icon-typed, no isPrimaryDocument on ANY era; scaffold rows flagged; bogus accession answers 200 scaffold-only with a ghost filename1.htm row -> upstream_not_found, document fetch on bogus 404s honestly), the mandatory cik-path-segment law (accession-only path 403s), auto-primary via the submissions recent window (primaryDocument; older accessions must pass --filename/--url/--list), and --text via stdlib HTMLParser zero-dep) + 0.3.70 company E12 developed-economy exchange universes + HKEX deep (at_wiener_borse_listed/au_asx_listed/hk_hkex_securities/hk_hkexnews_search/hk_hkexnews_document) +5 (batch E12 — AT/AU pure deepening; HK is the SDK's 36th jurisdiction (the user's HKEX-deep ruling); at_wiener is the E10 TLS-reversal revival (the factsetdigital cert misconfig was upstream's, fixed same-day); hk_hkex is ONE provider id over TWO hosts (www.hkex.com.hk xlsx universe + www1.hkexnews.hk servlet/JSONP/document — absolute-path ops, each host its own polite bucket); live laws baked in: the dimension-lie (xlsx <x:dimension A1:R8> understates 17,349 rows — rows are the truth), the column-P multiline spread-table-legend header (the probe stray-4 reading was a probe artifact, caught by the header wall on first live call), double-encoded search JSON (two json.loads), prefix.do JSONP resolve to stockId, two-era codes (t1/t2/t2g post-2007-06-25 / document_type pre-2007, searchable to 1999-04-01), DATE_TIME HK-shaped DD/MM/YYYY HH:MM verbatim, span-stack + German-number laws on wienerborse.at, ASX three-part CSV with legal Not Applic/Class Pend GICS values) + 0.3.71 company E13 keyless faces: CSE universe + issuer card, HKEX DI disclosure-of-interests (ca_cse_listed/ca_cse_company/hk_hkexdi_corp_list/hk_hkexdi_form/hk_hkexdi_ir_summaries) +5 (batch E13 — CA deepening + HK deepening under the user's hkex deep-dive ruling, zero new jurisdictions (36 held; faces 262→267, providers 177→179, company 85→90); ca_cse rides thecse.com's own /api/webapi/* JSON (Next.js head over WordPress, discovered via the build manifest — no screen-scraping): /en prefix + trailing slash PINNED (bare path 308s to a slashless 404 target), bad symbol = 200 with a ZERO-BYTE body → found=false silent-empty (never fabricated), metatdata [sic] dropped (upstream deprecated 2022-07-01; metadata is live), trading_date is per-row last trade not an as-at anchor; hk_hkexdi = di.hkex.com.hk SFO Part XV: ASP.NET session law (VIEWSTATE/EVENTVALIDATION/GENERATOR + session cookie cached TOGETHER 30min — the jp_jftc bound-pair law generalized; the recipe's 'pure GET corp lists' reading was corrected by probe — sessionless GET 302s), the search POST bakes src/lang/g_lang into the path template so the 302 Location carries them (tokens excluded from the body), the seven per-corp lists ride short sa2 codes (as/cs/ns/ad/nd/an) with sid/cid/sd/ed parsed verbatim off the resolution links (never invented), C5 investigation-results stream + NSForm2/NSForm4 details are pure GET sessionless (fn= hard keys {CS|DA|IR}{yyyymmdd}E{seq}; a CS form is 17 tables — Long/Short/LendingPool three-state + controlled-corporation chain + capacity/derivative legends), DION floor 2017-07-03 refused locally (upstream silently clamps earlier asks), the NSSrchDate date-axis captcha wall stays closed (corp/form axes carry the same data keyless), SDW/CCASS out of scope by upstream terms §2.3; ca_tmx re-probed 2026-11-19 — still the AWS WAF challenge, stays deferred) + 0.3.72 company E14 NZX + SIX official notices (nz_nzx_announcements/nz_nzx_company/nz_nzx_listed + ch_six_notice_detail/ch_six_official_notices) +5 (batch E14 — NZ/CH pure deepening, zero new jurisdictions (36 held; faces 267→272, providers 179→181, company 90→95); nz_nzx rides www.nzx.com Next.js SSR dehydrated state (__NEXT_DATA__ props.pageProps.dehydratedState.queries — robots allows the SSR pages only, /api/ and /search never touched): /markets/{board} carries the whole-exchange activeInstruments master 427 rows × 16 keys IDENTICAL on the NZSX/NZDX pages (the board picks the quote panel — 178 equities / 135 bonds type F securityClass W), lastListedDate 3000-01-01 is the listed sentinel (the master is the ACTIVE set, delisted drop out), /companies/{code} carries four panels (summary: financialYearEnd{month,day}+auditor+solicitor+primaryRegistry+primaryListingVenue; directors: the official register verbatim), bad code = an honest 404 whose queries list is EMPTY → found=false, /markets/{board}/announcements = newest-200 id-desc with the ?page param IGNORED server-side (page 2 dehydrates page 1 — 200 rows is the whole SSR surface, final boundary); ch_six_onot = its own provider on the six-group.com host (the sheldon notice pipeline vs the FQS reference query — the edgar per-service precedent): find.json show* type switches DEAD (8-combo matrix identical — noticeType filters locally), issuerWords ALIVE (server-side — but a PAGE-1 SNAPSHOT: partial page, deeper issuer pages garble persistently), pageSize pinned 100 (200 breaks paging, 1000 answers empty — the silent-over-cap shape), reachable ceiling ~5 pages/window (totalCount 515 vs 415 reachable — keep windows ~1 week), transient garbled 200s + issuerWords 502s → one patient no-cache retry (a garbled body is never cached as good), details/{noticeId}.json itemList[0] = 11 keys with FL titles bare date strings (the semantics live in text))"
# 0.3.73 +5: company E15 DE Xetra/Frankfurt T7 universe + Newsboard + KR KRX Global (de_xetra_instruments/de_xetra_newsboard/de_xetra_newsboard_search + kr_krx_indices/kr_krx_listed) (batch E15 — DE/KR pure deepening, zero new jurisdictions (36 held; faces 272→277, providers 181→183, company 95→100); de_xetra rides cashmarket.deutsche-boerse.com (the former xetra.com host, robots zero-Disallow): the T7 allTradableInstruments CSV link re-resolves from the landing page on EVERY fetch (blob {id}/{hash} versions on upload — never hard-coded; the frankfurt variant hangs at /Tradable-Instruments-Xetra/boersefrankfurt while /Tradable-Instruments-Frankfurt/Downloads is a 404 decoy), rows 1-2 carry Market + Date Last Update, 153 columns verbatim with ISIN+WKN on every row and counts drifting DAILY; the Newsboard is a 100-item RSS rolling window (~15h — hourly polling is the no-loss cadence) with full history at 4091644!search (pageNum stateless, 100 hits/page, delisting notices back to the 2020 number block ride ISINs); api.live.deutsche-boerse.com is a catch-all {} shell (null-path contrast law — negative, never touched); kr_krx rides the OPEN portal of the three-sister gate family (data.krx member-wall + Akamai, kind.krx WAF, global.krx robots Allow:/): the OTP double-step grid mints a one-shot base64 code (name=form × the FULL-path bld GLB/03/0308/0308010000/glb0308010000 — the endpoint name GLB99000001 is NOT the bld; a wrong pair answers 200 zero-byte, the silent-empty law) posted back 2s later with market_gubun (0/1/2/6 = all/kospi/kosdaq/konex, All=2,769 reconciles with the splits) — block1 is the whole universe one-shot × 10 cols (isu_cd/eng_cor_nm/std_ind_cd 2+2+2 hierarchy/lst_stk_vl/cpt/par_pr comma strings + *_num int companions); the OTP code NEVER enters the cache key (one-shot — the grid caches under a code-less hand-rolled key); the free-OTP family main.jspx?bld=index_list answers plain GET (KOSPI/KOSDAQ/KOSPI 200/KRX 300/Korea Value-up, cmpr_rt keeps upstream's raw scientific-notation string verbatim))
# 0.3.74 +6: company E16 UK FCA data-API family + EU ESEF register (gb_fca_firds_search/gb_fca_nsm_search/gb_fca_official_list/gb_fca_official_list_activity + eu_esef_filings/eu_esef_facts) (batch E16 — GB/EU pure deepening, zero new jurisdictions (36 held; faces 277→283, providers 183→185, company 100→106); gb_fca rides ONE keyless endpoint api.data.fca.org.uk/search?index=… over FOUR indexes measured 2026-11-23: the error-shape law (malformed query = 404 plain text 'Unable to search the data', re-raised upstream_unavailable; a wrong facet VALUE = silent 200 total 0 — vocabularies are mapped case-insensitively to stored casing, unknown values pass through verbatim), the per-index date law (NSM + activity demand full ISO datetimes, OL + FIRDS dd/MM/yyyy; FIRDS REQUIRES the to-bound — a bare from-date gets the measured far-future 31/12/2099 fill), the 10,000 window law on all four indexes (checked locally BEFORE the request), rows = populated fields only (OL placeholder records carry 5 keys, settled 8 — nulls are omitted, never faked), the NSM two-path law (criteriaObj.criteria AND + full-text primarySearch which ALSO needs latestFlag 'Y' + LIST-typed criteriaObj members — None dateCriteria 404s), activity's OBJECT-shaped securityActivityDateCriteria (a list 404s; security_activity validated locally because an unknown value is IGNORED upstream), FIRDS single-string criteria + keyword XOR criteria + never-published records always excluded, artefact links absolute under data.fca.org.uk/artefacts/ (NEVER a Range header — it resets the connection) and the SPA's analytics/honeypot endpoints never called; eu_esef rides filings.xbrl.org JSON:API (27,817 filings / 7,505 issuers / 28 countries; filter=[{name,op,val}] + a mandatory sort; page[size] ≤1000; GB 2,982/806, DE+IE absent): the facts op follows the filing's ABSOLUTE json_url (the edgar_arch absolute-path precedent) into the XBRL-JSON document (durations END-EXCLUSIVE — midnight instants mean the day before, inclusive end = raw −1 day; published is null on EVERY GB row — not exposed; ~10/min 429 clamp → SDK 0.1 rps; issuers tag revenue variously → concept filter carries the trailing-'*' wildcard form 'Revenue*')
# 0.3.75 +3: company E17 EDGAR holdings-disclosure family (us_sec_13dg_stakes/us_sec_13f_holdings/us_sec_form4_transactions) (batch E17 — US pure deepening, zero new jurisdictions (36 held; faces 283→286, providers 185→185, company 106→109); zero new provider buckets — edgar_cik submissions enumeration + edgar_arch Archives index/doc ride again; live-probed 2026-11-23 tmp/probe-e17: the XSL-SHELL LAW (13F AND Schedule 13D/G submissions primaryDocument points at the human rendering xslForm13F_X02|xslSCHEDULE_13G_X02/primary_doc.xml — ElementTree dies on it; raw XMLs sit at the accession root, resolved via the index op, never via primaryDocument; Form 4's primaryDocument IS root-level wk-form4_*.xml), the ROOT-XML PICK LAW (13F table = root-level xml minus primary_doc.xml, 'info' preferred, ambiguous → usage_error naming candidates; 13DG prefer primary_doc.xml else htm legacy; Form4 primaryDocument-else-form4-named), the NAMESPACE LAW (13F informationTable default ns since 2014 + 13DG schedule13g default ns since 2022 + Form4 ownershipDocument namespace-free — localname() matching throughout, bare findall("infoTable") answers ZERO rows), the VALUE-UNITS LAW (13F value switched thousands→whole USD with 2023-Q1 reporting periods — reportDate-based, the card always carries value_units; Berkshire Q3-2026 ALLY 472,572,546 = 12.56M sh x ~$37.6 dollar-consistent), the FORM-STRING LAW (submissions carries BOTH families: SCHEDULE 13D/G(/A) structured era AND SC 13D/G(/A) legacy HTML era — the 13DG enumeration filter is the eight-string union; legacy rides parsed=False + doc_url, never a fabricated stake), and the PTR NEGATIVE (STOCK Act forms PD/PTXA/PTR answer zero in EDGAR FTS — congressional PTRs live in the House PDPC/Senate EFD systems, out of this batch); FTS volume pins 2026-10-01..11-23: 13F-HR 9,606 / SCHEDULE 13D 496 + 13D/A 366 + 13G 2,545 + 13G/A 1,826 / Form 4 ~270 per trading-day (q-token sensitive: "common stock" 544 vs "transfer" 8 on the same 2-day window)
# 0.3.76 +10: company E18 LSE exchange universe (gb_lse_universe/gb_lse_security_master/gb_lse_ric_lookup/gb_lse_index_membership/gb_lse_fundamentals/gb_lse_issuer_address/gb_lse_bond_details/gb_lse_rns_archive/gb_lse_rns_article/gb_lse_issuer_profile) (batch E18 — GB pure deepening, zero new jurisdictions (36 held; faces 286→296, providers 185→186, company 109→119); ONE new provider gb-lse over THREE hosts (apidata.londonstockexchange.com keyless REST + www.londonstockexchange.com sitemap/RNS pages + cache-api.lsegissuerservices.com issuer profiles — the hk_hkex/edgar_xbrl absolute-path precedent); the quote surfaces (instrument-summaries/trade-summaries/rdp pricing/tmv/tradingstatus/validate/AIM advisers/fdc-token-samllogin-tns ticks/OHLCV bars) are MARKET-DATA — licensed goods, deliberately out (the red line); live-probed 2026-11-24 tmp/probe-e18: the header-fingerprint gate is INTERMITTENT (bare UA answered 200 on nrdp where 2026-11-23 demanded Accept+Referer — the headers always ride anyway, zero downside), the envelope law (every apidata REST answer is {"statusCode":200,"message":…,"data":…} — the SDK unwraps data; the research doc's bare-data samples were pre-envelope), the 200-empty transient law (apidata answers 200 with a zero-byte body on some reads; three certifications 2026-11-23 (nrdp 0A00/01GT + securitybonddetails 01GT) all recovered on re-visit — REST faces re-ask once no-cache before raising, an empty answer is never read as a coverage boundary; plus the WWW DEGRADE-TRANSIENT live cert 2026-11-24: the article face answered a degraded 200 with articleBody ABSENT, probe5 answered the full 165KB page minutes later under every header combo incl. the SDK's own UA — the www faces re-ask once no-cache on a degenerate payload, overwriting the poisoned cache entry), the parallel-list law (ftseindexconstituents indexCode/indexName/indexWeight strict zip alignment with a length-mismatch guard — an empty slot = not a member), the articleBody JS-string law (the full disclosure body is server-embedded with \x22/\uXXXX/\/ escapes, decoded before serving; the RichTextGrid metadata carries Company information/RNS Number/Released On/Source; US-target form-8-3 bodies legitimately carry no ISIN), the slug-melt law (the RNS slug is a category-company melt that can carry extra path segments — parsed via rpartition, never a company name), the archive-floor law (sitemap-news exists back to 2024-11 — older months answer S3 AccessDenied 403, refused locally; the ~25-month window is the depth ceiling; current month in-progress ~35k URLs vs full months 44k-49k), and the issuer-opted profile law (cache-api profile coverage is issuer-opted — VOD 200 33 instruments, BASDE honest 404; 403 Forbidden=unknown route vs Missing Authentication Token=face unregistered vs 404=issuer unregistered))
# 0.3.78 +13: company E21 TMX Canada directory + GraphQL gateway (ca_tmx_company_profile/ca_tmx_delisted/ca_tmx_directory_search/ca_tmx_dividends/ca_tmx_filings/ca_tmx_index_constituents/ca_tmx_insider_activities/ca_tmx_insider_transactions/ca_tmx_instrument_search/ca_tmx_recent_listings/ca_tmx_short_interest/ca_tmx_suspended/ca_tmx_wsh_events) (batch E21 — CA pure deepening, zero new jurisdictions (37 held; faces 309->322, providers 188->189, company 132->145); ONE provider over TWO hosts — www.tsx.com /json/company-directory/* keyless JSON (search prefix law: NAME-OR-SUFFIX match, single-letter scans carry ~10% name-only rows; recent/delisted ROLLING ~12-week windows with NO pagination — monthly sweep is the archival duty; suspended PRESENT-STATE name/symbol only) + app-money.tmx.com Apollo GraphQL POST (introspection OFF — contracts excavated from webpack chunks, probe-e21 14/14 live 2026-11-27; profile 41-field selection — the quote block stripped at the QUERY level; WSH data.quote.data = event LIST with MM/DD/YYYY dates verbatim; filings METADATA-ONLY — urlToPdf lands on app.quotemedia.com, robots bans /data/, pointer kept never fetched; insiders monthDuration 1..120 — 120 ≈ ten years the SEDI ceiling); the E10 AWS WAF deferral is CLOSED — the 2026-11-18 JS challenge keyed on EXIT-IP REPUTATION WINDOWS, not headers (2026-11-23 + 2026-11-27 egress clean 14/14; dual-stack urllib passes bare-UA — NO curl pin, the nasdaq-nordic contrast)
# 0.3.10 jurisdiction chapter: face -> jurisdiction (default = the issuing authority's jurisdiction; institutions covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2 + EU + GLOBAL).
# The per-domain source of truth is each domain cli.py's COUNTRY (same face set as FLAT); the root only merges them; the success envelope carries a jurisdiction chapter (search/read are hosted mixed-jurisdiction corpus services — unstamped)
_JURISDICTION = {f: cc for _m in _CLI.values() for f, cc in _m.COUNTRY.items()}
assert set(_JURISDICTION) == set(_FLAT_DISPATCH), f"jurisdiction coverage {len(_JURISDICTION)} != dispatch faces {len(_FLAT_DISPATCH)}"
# Deprecated flat-face aliases (us_ prefix rename pre-release 2026-11-17): legacy command names
# still parse (suppressed parsers) and route here — stderr warning + rewrite to the canonical
# verb before dispatch. Removal slated 0.4.x (the parsers, this map and the two gate exclusions go together).
_FLAT_ALIAS = {
    "sec_submissions": "us_sec_submissions",
    "sec_fulltext_search": "us_sec_fulltext_search",
}
def _merge_globals(a):
    """Merge global flags: the ones placed after the subcommand (sub_*) win, the top level is the
    fallback — both placements work (the README example shape). sub_* are all SUPPRESS: if one never
    appeared the attribute does not exist, so every read falls back via getattr."""
    a.base_url = getattr(a, "sub_base_url", None) or a.base_url
    a.api_key = getattr(a, "sub_api_key", None) or a.api_key
    a.cache_dir = getattr(a, "sub_cache_dir", None) or a.cache_dir
    a.no_cache = a.no_cache or getattr(a, "sub_no_cache", False)
    a.execution = getattr(a, "sub_execution", None) or a.execution
    for k in ("sub_base_url", "sub_api_key", "sub_cache_dir", "sub_no_cache", "sub_execution"):
        if hasattr(a, k):
            delattr(a, k)
    return a


def _hub_params(pairs):
    """--param 'k=v' (repeatable) -> query dict; values stay verbatim strings."""
    params = {}
    for raw in pairs or []:
        k, _, v = raw.partition("=")
        if not k:
            raise SdkError("usage_error", detail=f"--param expects K=V, got {raw!r}")
        params[k] = v
    return params




def main(argv=None) -> int:
    # Force UTF-8 for piped/redirected output: on Chinese Windows the pipe defaults to CP936 and agents
    # or redirected consumers would receive bad bytes; the interactive console is already UTF-8 under
    # PEP 528, so reconfigure is imperceptible there. Guarded: replaced/captured stdout (tests) may
    # not be a TextIOWrapper.
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    parser = build_parser()
    a = _merge_globals(parser.parse_args(argv))
    if a.domain == "capabilities":
        # The discovery surface needs no credentials and no network: it is the command tree itself.
        caps = capabilities_mod.collect(parser, flat_faces=set(_FLAT_DISPATCH),
                                         jurisdiction=_JURISDICTION)
        if getattr(a, "remote", False):
            # Hosted meta (premium family): index+drift keyless, single-face full record takes a PAT.
            # (SdkError comes from the module-level import — a branch-local import here would
            # shadow it into a function-local name and blow up the outer `except SdkError`
            # with UnboundLocalError on every non-remote error path; caught live 2026-11-16.)
            import os as _os
            try:
                if a.face_filter:
                    doc = capabilities_mod.hosted_meta_fetch(
                        f"/v1/meta/faces/{a.face_filter}",
                        api_key=_os.environ.get("AGENTDATA_API_KEY", "").strip() or None)
                else:
                    hosted = capabilities_mod.hosted_meta_fetch("/v1/meta/faces")
                    doc = {"hosted": hosted, "drift": capabilities_mod.hosted_drift(caps, hosted)}
                print(json.dumps(doc, ensure_ascii=False, indent=2))
                return 0
            except SdkError as e:
                print(json.dumps({"request_id": str(uuid.uuid4()), **e.to_dict()}, ensure_ascii=False, indent=2),
                      file=sys.stderr)
                return e.exit_code
        caps = capabilities_mod.filter_caps(caps, domain=a.domain_filter, face=a.face_filter)
        print(capabilities_mod.render(caps, a.format))
        return 0
    try:
        c = Client(a.base_url, a.api_key, cache_dir=a.cache_dir, no_cache=a.no_cache,
                   execution=a.execution,
                   token_url=getattr(a, "token_url", None),
                   hub_base_url=getattr(a, "hub_base_url", None))
        if a.domain == "hub":
            if a.hub_verb == "token":
                out = c.hub.token_payload()
            else:  # argparse required=True leaves only "get"
                out = c.hub_get(a.path, _hub_params(a.param))
        else:
            d = getattr(c, a.domain)
            alias = _FLAT_ALIAS.get(a.verb)  # deprecated sec_* legacy names: warn + reroute (0.4.x removes)
            if alias is not None:
                print(f"WARN: {a.domain} {a.verb} is deprecated — use {a.domain} {alias} (removal slated 0.4.x)",
                      file=sys.stderr)
                a.verb = alias
            flat = _FLAT_DISPATCH.get(a.verb)
            if flat is not None:
                out = getattr(d, a.verb)(**flat(a))
                out["jurisdiction"] = _JURISDICTION[a.verb]  # 0.3.10 jurisdiction chapter: downstream can route by country without digging through docs
            elif a.verb == "search":
                screen_inputs = None
                if a.mode == "screen":
                    if not a.input:
                        raise SdkError("usage_error", detail="--mode screen requires --input x.jsonl")
                    with open(a.input, encoding="utf-8") as f:
                        screen_inputs = [json.loads(line) for line in f if line.strip()]
                out = d.search(filters=_filter_arg(a.filter), record_kind=a.record_kind,
                               facets=a.facets.split(",") if a.facets else None, level=a.level,
                               limit=a.limit, cursor=a.cursor, mode=a.mode, screen_inputs=screen_inputs)
            else:
                out = d.read(a.id, level=a.level)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except SdkError as e:
        # api.md section 9.5: request_id runs through both the success and error states (mirroring the
        # Node cli.mjs randomUUID emitted in both states)
        print(json.dumps({"request_id": str(uuid.uuid4()), **e.to_dict()}, ensure_ascii=False, indent=2), file=sys.stderr)
        return e.exit_code
    except RuntimeError as e:  # actionable config errors such as an unwritable cache directory
        print(f"Config error: {e}", file=sys.stderr)
        return 2
