# agentdata

[![PyPI](https://img.shields.io/pypi/v/agentdata)](https://pypi.org/project/agentdata/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/dicaria/agentdata/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Commands](https://img.shields.io/badge/322_commands-9_domains-teal)](https://github.com/dicaria/agentdata/blob/main/docs/domains/api.md)

**One Python client and CLI over 322 public datasets — company registries,
sanctions lists, procurement awards, drug approvals — with no API keys and no
accounts.**

Government data holds the decisive facts about companies, but it is scattered
across 189 public APIs, each with its own pagination, rate
limits, and undocumented quirks. **agentdata puts 322 of those datasets behind
one interface**: a pure-standard-library client and CLI across 37 jurisdictions. Every upstream gotcha we hit live is already pinned — politeness
and caching are built in.

## Install

```bash
python -m pip install agentdata
```

For a reproducible install, pin the release: `python -m pip install agentdata==0.3.78`.

Prefer not to touch PyPI? Install straight from a release tarball:

```bash
python -m pip install https://github.com/dicaria/agentdata/archive/refs/tags/v0.3.78.tar.gz
```

Or via git (pin a tag for reproducible installs):

```bash
python -m pip install git+https://github.com/dicaria/agentdata.git@v0.3.78
```

Or track the latest release (convenience for agents and scripts — a fresh
release does not trigger a reinstall under the same URL, so pass
`--force-reinstall` when you want the new one):

```bash
python -m pip install --force-reinstall https://github.com/dicaria/agentdata/releases/latest/download/agentdata-latest.tar.gz
```

## Two API families

| Family | Where it runs | Credentials | Cost |
|---|---|---|---|
| **Enrichment** | Locally — the SDK calls public government / open-data APIs from your machine | none | free |
| **Corpus** | Hosted service operated by dicaria | credentials issued by dicaria | per service agreement |

Most commands are enrichment: they need no configuration, no keys, no account.
Corpus commands are marked in the docs and require credentials issued by
dicaria under a separate service agreement — contact **contact@dicaria.com**.

## What can you ask it?

Commands follow `<domain> <source>_<dataset>` — one command per upstream
dataset, parameters kept under their upstream names. Every row below works as
`agentdata <domain> <command> …` from the shell, or
`c.<domain>.<command>(…)` from Python.

| Question | Commands |
|---|---|
| Is this company sanctioned? | `legal csl_screening_list` · `legal co_sic_sanctions` · `legal wb_debarred_firms` · `legal ca_sema_sanctions` · `legal ru_cbr_warning_list` |
| Do consumers complain about this company? | `legal cfpb_complaints` · `legal cfpb_suggest_company` · `legal br_bacen_complaints` |
| Who owns or controls it? | `company gleif_direct_parent` · `company no_brreg_roller` · `company fr_recherche_search` |
| Did it win public contracts? | `procurement br_pncp_contracts` · `procurement ungm_contract_awards` · `procurement wb_procnotices` |
| Is its drug or device approved — or recalled? | `healthcare fda_drug_approvals` · `healthcare gb_mhra_alerts` · `healthcare fda_drug_recalls` |
| What does this facility or fleet emit? | `esg climatetrace_sources` · `transportation thetis_mrv_datasets` · `transportation paris_mou_detentions` |
| Which aircraft does this registration mark belong to? | `transportation ca_ccar_search` · `transportation ca_ccar_aircraft` |
| Pull a company card from a national registry | `company ch_zefix_firm` · `company co_rues_companies` · `company kr_hometax_biz_status` · `company kz_gbd_ul_companies` · `company cz_ares_ekonomicke_subjekty` · `company in_sebi_intermediaries` · `company tr_spk_listed` · `company tr_bddk_institutions` · `company ru_cbr_credit_orgs` · `company br_bacen_institutions` · `company br_bacen_branches` · `company br_bacen_domains` · `company br_bacen_dasfn` |
| Has its broker been expelled, or its regulator fined it? | `legal in_sebi_orders` · `company in_sebi_default_brokers` |
| Has the regulator fined it, banned it, or put it under a special regime? | `legal tr_spk_fines` · `legal tr_spk_bans` · `legal br_bacen_regimes` |
| How big is the country it operates in? | `economy wb_wdi_values` · `economy eurostat_table` · `economy fred_series` |
| Convert an EUR amount, or read a bilateral trade flow | `economy ecb_fx_rates` · `economy un_comtrade_trade` |

## Quick start

```python
from agentdata import Client

c = Client()  # zero config: enrichment commands work immediately

c.healthcare.fda_drug_recalls(search='recalling_firm.exact:"SV Labs Toronto Corporation"')
c.company.gleif_lei_records(lei="5493001KJTIIGC8Y1R12")           # LEI -> entity identity card (GLEIF)
c.company.ch_zefix_firm_search(name="siemens")                    # Swiss commercial registry (Zefix)
c.esg.climatetrace_sources(owner_ids="E100000001492", year=2023)  # owner -> facility-level emissions
c.transportation.paris_mou_inspections(period_min="01/12/2025", period_max="31/12/2025", ism_company_imo_number="0052193")  # port-state inspection flow by management company (Paris MoU; dd/mm/yyyy window up to 3 years)
c.legal.csl_screening_list(name="VTB BANK")                       # sanctions screening (US CSL)
c.research.openalex_works(search="vaccine", ror="01xdqrp08")
c.procurement.br_pncp_contracts(data_inicial="20260901", data_final="20260930", pagina=1)
c.security.osv_vulns(package="lodash", ecosystem="npm", version="4.17.15")
c.economy.wb_wdi_values(country="CHN", indicator="NY.GDP.MKTP.CD", date="2020:2023")  # World Bank indicator values
c.economy.ecb_fx_rates(currency="USD", start="2026-10-01", end="2026-10-31")  # euro reference rate (1 EUR = X)
```

The same commands from the shell — ten entry points, `agentdata` plus one
per domain:

```bash
agentdata healthcare rxnav_rxcui_by_name --name atorvastatin
agentdata company gleif_lei_records_search --filter-entity-legal-name "Siemens" --page-size 3
agentdata legal csl_screening_list --name "VTB BANK"
agentdata esg climatetrace_sources --owner-ids E100000001492 --year 2023
agentdata procurement br_pncp_contracts --data-inicial 20260901 --data-final 20260930 --pagina 1
agentdata economy wb_wdi_values --country CHN --indicator NY.GDP.MKTP.CD --date 2020:2023
```

If a domain entry-point command (`company`, `legal`, …) collides with another
tool on your machine, `python -m agentdata <domain> …` is the equivalent
invocation.

Corpus commands use the same shape with hosted credentials:

```python
c2 = Client(base_url="https://…", api_key="mk_live_…")  # PAT issued by dicaria
c2.company.read(id=1476, level="tier2")
```

## Show me a response

Real output of `agentdata healthcare rxnav_rxcui_by_name --name atorvastatin` —
every command returns this shape:

```json
{
  "ok": true,
  "domain": "healthcare",
  "tool": "rxnav_rxcui_by_name",
  "input": { "name": "atorvastatin" },
  "from_cache": false,
  "reason": "RxNav normalization: drug name 'atorvastatin' → RxCUI 83367 (ingredient level)",
  "result": {
    "rxcui": "83367",
    "normalized_name": "atorvastatin",
    "tty": "IN"
  },
  "evidence": [
    {
      "quote": "RxCUI 83367 = atorvastatin",
      "url": "https://rxnav.nlm.nih.gov/REST/rxcui/83367/properties.json"
    }
  ],
  "source": {
    "provider": "rxnav",
    "execution": "local",
    "observed_at": "2026-11-02T03:28:22.213Z"
  },
  "request_id": "3f343e2f-3b08-46e8-ac69-8ee05adce548",
  "jurisdiction": "US"
}
```

A plain-language `reason`, `evidence` rows with a checkable quote and source
URL, provenance in `source`, the issuing authority in `jurisdiction`, and a
`request_id` for support — your code parses one shape across all datasets.
Cached responses are identical, with `from_cache: true`.

## Why not just call the APIs yourself?

You can — and then you get to rediscover what is already pinned here:

- **Quirks are pre-solved, not rediscovered.** Every command encodes traps we
  hit against the live API: anti-forgery token dances, Socrata parameters that
  are silently ignored, registries that clamp your page size without an error.
- **One envelope across all 322 commands.** Query echo, `reason`, `evidence`,
  source metadata, `jurisdiction` — your code parses one shape.
- **Upstream parameter names, verbatim.** What the official API docs call a
  parameter is what the SDK takes — no invented vocabulary to unlearn.
- **Polite by default.** Per-source rate limits are enforced before every
  request ([rate-limits ledger](https://github.com/dicaria/agentdata/blob/main/docs/domains/rate-limits.md)),
  and a cache hit costs no rate budget.
- **Zero dependencies.** Python 3.10+ standard library only.

## Coverage

**322 datasets · 189 upstream providers · 37 jurisdictions:** US 68 · global 40 · EU 30 · UK 29 · Canada 27 · Brazil 10 · France 10 · JP 9 · Switzerland 7 · DE 7 · Korea 7 · ES 6 · HK 6 · India 6 · Türkiye 6 · Australia 5 · IT 5 · New Zealand 5 · AT 3 · Colombia 3 · MX 3 · NL 3 · SE 3 · Czechia 2 · EE 2 · Guernsey 2 · Ireland 2 · LV 2 · Norway 2 · PL 2 · RU 2 · SG 2 · UA 2 · DK 1 · Finland 1 · Jersey 1 · Kazakhstan 1.

| Domain | Commands | Sources |
|---|---|---|
| `company` | 145 | GLEIF, SEC EDGAR (registry, full-text search, the XBRL structured-facts family, the filing-document body fetch & the holdings-disclosure trio: 13F institutional holdings, Form 4 insider transactions, Schedule 13D/G activist stakes), FDIC, USAspending, TED, VIES, UK Contracts Finder & FTS, Zefix (CH), Brreg (NO), YTJ (FI), recherche-entreprises (FR), RUES (CO), Hometax (KR), ROR, NZ Companies Office, ARES (CZ), GFSC (GG), JFSC (JE), GBD_UL (KZ), SEBI intermediaries (IN), SPK public-company register (TR), BDDK licensed institutions (TR), CBR credit institutions (RU), BACEN institutions, branches, verified domains & open-finance API directory (BR), federal insolvency announcements (DE), FSA licensed-institution registers (JP), CCAA restructuring roster (CA), CNMV supervised entities & BORME gazette (ES), data.gov.sg platform (SG), TDLR licenses (TX) & DOH credentials (WA), Chicago BACP business licenses, LA City business register, NYC DCWP licenses, ACPR Regafi financial-sector register (FR), J-PlatPat IP trio & KIPRIS patents (JP/KR), Unternehmensregister register search (DE), KAP members & disclosures (TR), OEPM BOPI gazette index (ES), INPI accounting ratios (FR), EIOPA IORP pension register (EU), BNDES financing operations (BR), NZX SSR listed/issuer/announcements trio (NZ), SIX official notices & detail (CH), Deutsche Börse T7 universe & Newsboard (DE), KRX Global universe & indices (KR), FCA data-API family: NSM search, Official List + daily activity, FIRDS instruments (GB), ESEF filings & facts (EU), the LSE exchange-universe family: sitemap universe, nrdp master, bond/security card, RIC bridge, FTSE index membership, fundamentals, issuer address & IR profile, RNS archive & full-text articles (GB), the TMX Canada family: directory prefix search + recent/delisted/suspended registers (www.tsx.com JSON) + the GraphQL gateway (company profile 41-field selection, short interest, insider ledger & aggregate, index constituents, WSH events, filings metadata, dividends, instrument search) (CA) |
| `economy` | 18 | World Bank WDI, Eurostat, ECB reference rates, FRED, WHO xMart, UN Comtrade, ILOSTAT, BLS, BIS, IMF, OECD, Comext |
| `esg` | 8 | Climate TRACE, EITI, EU ETS (EUTL), EPA FRS, UK FSA food-hygiene ratings (FHRS), SGM mining concessions (MX) |
| `healthcare` | 34 | US FDA approvals & recalls, ClinicalTrials.gov, RxNav, DailyMed, AccessGUDID, UK MHRA alerts, Health Canada DPD & MDALL, EUDAMED, RASFF & Safety Gate (EU), TGA (AU), Europe PMC, MeSH, US NPPES provider organizations, NAVII facility search (JP), CNES facility register (BR) |
| `legal` | 87 | US consolidated screening list, eCFR, Federal Register, LDA filings, CourtListener, DG COMP, UK CMA cases, UK Electoral Commission, The Gazette, Irish Revenue defaulters, US OCC enforcement, TNA case law, SIPRI, SIC sanctions (CO), MDB debarment rosters (WB/AfDB/IDB), Canada SEMA, CFPB consumer complaints, SEBI enforcement orders (IN), SPK administrative fines & trading bans (TR), CBR illegal-finance warning register (RU), BACEN special regimes & complaint rankings (BR), RIS case law & consolidated federal law (AT), FERC eLibrary (US), French competition-authority fines (FR), Italian ARERA decisions (IT), CFTC enforcement actions (US), Irish lobbying register (IE), Estonian party-finance disclosures (EE), Ukrainian party-asset register (UA), CNBV sanctions & disciplined servants (MX), Rechtspraak case law (NL), KR statutes & court precedents, BOE gazette table of contents (ES), ASC enforcement & BCSC disciplined (CA), AMF sanctions & transactions (FR), CJEU case-law search (EU), KNAB party finance (LV), EFK party financings & FINMA enforcement news (CH), India Code (IN), Federal Register of Legislation (AU), CADE competition cases (BR), CBSA advance rulings (CA), Bundestag lobby register (DE), Danish FSA supervision archive, AGCM proceedings trio (IT), UOKiK decisions (PL), CBP CROSS rulings (US), administrative-courts judgment archives (FR), OCC EASearch enforcement database (US), ACM publications (NL), CNMV sanctions (ES), FSS sanctions (KR), JFTC decision database (JP), CCI antitrust orders & combinations registers (IN), ACCC actions feed (AU), NMW naming-scheme rounds & single-round dossiers (UK), CFTC RED List & reparation decisions (US), CFTC OGC opinions & adjudicatory orders (US) |
| `procurement` | 7 | PNCP (BR), SECOP II (CO), UNGM, World Bank, New York Authorities / MTA / OGS (US) |
| `research` | 10 | OpenAlex, NIH RePORTER, NSF, Crossref, UKRI GtR, iCite, bioRxiv, OpenCitations |
| `security` | 4 | OSV, CISA KEV, ENISA EUVD |
| `transportation` | 9 | Canada TC civil aircraft register (CCAR), EU Air Safety List, Paris MoU port-state control, THETIS-MRV (EU shipping), US FMCSA motor-carrier census |

## Full command index

Ten entry points — `agentdata` plus one command per domain — and 322 dataset
commands under them: one command per upstream dataset, parameters kept under
their upstream names. The block below is the complete index, grouped by domain
in `DOMAIN_ORDER` — the order the CLI registers the domains in (the 0.3.10
ordering ruling).
Every line is a runnable command.

Above them sit two meta-commands that are not dataset faces:
`agentdata capabilities` (discovery, since 0.3.52 — renders the full face table
from the command tree: `--format json|md`, `--domain-filter`, `--face`; no key,
works offline) and the `agentdata hub` family (PAT → short-lived subject JWT,
see above).

```bash
agentdata capabilities --format md

# company (145)
agentdata company gleif_lei_records --lei 5493001KJTIIGC8Y1R12
agentdata company gleif_lei_records_search --filter-entity-legal-name Nestle --filter-entity-jurisdiction CH --page-size 5
agentdata company gleif_direct_parent --lei 5493001KJTIIGC8Y1R12
agentdata company gleif_ultimate_parent --lei 5493001KJTIIGC8Y1R12
agentdata company eu_eiopa_iorps --limit 5
agentdata company fdic_failures --filters PSTALP:TX --limit 5
agentdata company fdic_financials --filters CERT:628 --sort-by REPDTE --sort-order desc
agentdata company fdic_history --filters CERT:628 --limit 3
agentdata company fdic_institutions --filters CERT:628
agentdata company fdic_locations --filters STALP:TX --limit 5
agentdata company us_sec_submissions --cik 320193
agentdata company us_sec_companyconcept --cik 320193 --concept RevenueFromContractWithCustomerExcludingAssessedTax
agentdata company us_sec_companyfacts --cik 320193
agentdata company us_sec_filing_document --cik 790526 --accession 0001683168-20-000837 --filename radnet_8k-ex9901.htm --text
agentdata company us_sec_frames --concept NetIncomeLoss --frame CY2024
agentdata company us_sec_tickers --ticker AAPL
agentdata company ror_organizations --query EMBL
agentdata company vies_vat --vat DE811907980
agentdata company usaspending_spending_by_award --recipient-search-text "Lockheed Martin" --start-date 2024-01-01 --end-date 2024-12-31 --limit 3
agentdata company ted_notices_search --query 'organisation-name-buyer=Siemens* AND organisation-country-buyer=DEU' --limit 5
agentdata company gb_fts_release_packages --name nhs --updated-from 2026-10-01 --updated-to 2026-10-27 --limit 5
agentdata company gb_contracts_finder_published_notices --name council --published-from 2026-10-20 --published-to 2026-10-27 --limit 5
agentdata company us_sec_fulltext_search --q "artificial intelligence" --forms 8-K --limit 5
agentdata company ch_zefix_firm_search --name "Nestle" --max-entries 3
agentdata company ch_zefix_firm --ehraid 347554
agentdata company no_brreg_enheter --navn equinor --size 2
agentdata company no_brreg_roller --organisasjonsnummer 923609016
agentdata company nzco_companies --q "air new zealand" --limit 15
agentdata company nzco_directors --company-number 104799
agentdata company fi_ytj_companies --name nokia
agentdata company fr_inpi_ratios --siren 844516393 --limit 5
agentdata company fr_inpi_ratios_sectors --classe-naf 1102 --exercice 2019
agentdata company fr_recherche_search --q danone
agentdata company fr_recherche_search --q "552032534" --per-page 25 --etat-administratif A
agentdata company fr_regafi_entities --q Lille --limit 3
agentdata company fr_regafi_entities --siren 265907741
agentdata company fr_regafi_authorisations --id-referentiel 79 --limit 3
agentdata company co_rues_companies --where "razon_social like '%BANCOL%'" --limit 5
agentdata company kr_hometax_biz_status --biz-no 124-81-00998
agentdata company kr_kipris_patents --q 삼성전자 --page-size 3
agentdata company kz_gbd_ul_companies --text "ВЕЛЛЕТ" --count 5
agentdata company cz_ares_ekonomicke_subjekty --ico 45274649
agentdata company cz_ares_ekonomicke_subjekty_vyhledat --obchodni-jmeno "ČEZ" --pocet 5
agentdata company gg_gfsc_registered_businesses --category accountant --limit 5
agentdata company gg_gfsc_regulated_entities --licence "Investment Licensee" --status active --limit 5
agentdata company je_jfsc_regulated_entities --keyword Barclays --page-size 5
agentdata company in_sebi_intermediaries --category sb_equity --search MOTILAL
agentdata company in_sebi_default_brokers
agentdata company tr_spk_listed --segment borsadisi --name AKSEL
agentdata company tr_spk_listed --mersis 0470003286100012
agentdata company ru_cbr_credit_orgs --name "ДЕМО" --status active --limit 5
agentdata company ru_cbr_credit_orgs --ogrn 1037700000001
agentdata company br_bacen_institutions --family banco --segmento múltiplo --limit 5
agentdata company br_bacen_branches --if-name CAIXA --uf SP --limit 5
agentdata company br_bacen_domains --tipo none --limit 5
agentdata company br_bacen_dasfn --api pix_saque --limit 5
agentdata company br_bndes_financiamento --name PETROBRAS --rows 5
agentdata company tr_bddk_institutions --category bankalar --limit 5
agentdata company tr_bddk_institutions --status exited --limit 5
agentdata company tr_kap_members --type IGS --state A
agentdata company tr_kap_disclosures --from 2026-11-01 --to 2026-11-10 --limit 5
agentdata company de_inso_search --state NW --date-from 2026-11-02 --date-to 2026-11-02 --limit 5
agentdata company de_inso_register_lookup --register-court "Düsseldorf" --register-type HRB --register-number 101036 --date-from 2026-11-02 --date-to 2026-11-02 --limit 5
agentdata company de_register_search --q "Siemens Energy AG"
agentdata company jp_fsa_licensed --category crypto_exchanges --limit 5
agentdata company jp_fsa_licensed --category trust_agents --name 北洋 --limit 5
agentdata company jp_design_search --q ソニー
agentdata company jp_patent_search --q ソニー --year 2024 --year-sign ">="
agentdata company jp_trademark_search --q ソニー
agentdata company ca_ccaa_records --province QC --limit 5
agentdata company ca_ccaa_records --name "MTE Logistix"
agentdata company ca_ccaa_records --monitor KPMG --province AB --limit 5
agentdata company es_borme_day --date 2026-11-04 --limit 5
agentdata company es_borme_day --date 2026-11-04 --kind A --limit 3
agentdata company es_borme_notice --id BORME-A-2026-181 --order 2
agentdata company es_borme_notice --id BORME-C-2026-5782
agentdata company es_cnmv_entities --category securities_firms --limit 5
agentdata company es_cnmv_entities --category securities_firms --nif A-83217281
agentdata company es_cnmv_entities --category eea_investment_firms_passport --name Goldman --limit 3
agentdata company es_oepm_bopi --tomo 1 --date 2026-11-04
agentdata company sg_datagovsg_datasets --limit 5
agentdata company sg_datagovsg_datasets --q ACRA --limit 5
agentdata company sg_datagovsg_dataset_download --id d_3f960c10fed6145404ca7b821f263b87
agentdata company sg_datagovsg_dataset_download --id d_b1d2b840ab9e993570c037b706b39bb8
agentdata company tx_tdlr_licenses --limit 3
agentdata company tx_tdlr_licenses --where "license_type='Cosmetology Operator' and business_county='TRAVIS'" --limit 3
agentdata company wa_doh_credentials --limit 3
agentdata company wa_doh_credentials --where "credentialtype='Physician And Surgeon License' and status='Active'" --limit 3
agentdata company chi_bacp_licenses --where "license_description='Consumption on Premises - Incidental Activity' and license_status='AAI'" --limit 3
agentdata company lacity_registrations --where "naics like '7213%' and council_district='10'" --limit 3
agentdata company nyc_dcwp_licenses --where "business_category='Secondhand Dealer - General' and license_status='Active'" --limit 3
agentdata company ch_six_fqs_search --segment EQ --pagesize 5
agentdata company eu_euronext_instrument_search --q "air liquide"
agentdata company it_borsa_quote --isin IT0003132476
agentdata company jp_jpx_stock_detail --qcode 7203
agentdata company jp_jpx_stock_list --section 1 --maxdisp 50
agentdata company at_wiener_borse_listed --segment prime --isin AT000AGRANA3
agentdata company au_asx_listed --code BHP
agentdata company hk_hkex_securities --category Equity --code 700
agentdata company hk_hkexnews_search --stock 00700 --row-range 20
agentdata company hk_hkexnews_document --url https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1118/2026111800448.pdf
agentdata company ca_cse_listed --status Active --limit 20
agentdata company ca_cse_company --symbol PAU
agentdata company ca_tmx_directory_search --exchange tsx --q bank
agentdata company ca_tmx_recent_listings --exchange tsx
agentdata company ca_tmx_delisted --exchange tsx
agentdata company ca_tmx_suspended --exchange tsxv
agentdata company ca_tmx_company_profile --symbol RY
agentdata company ca_tmx_short_interest --symbol RY
agentdata company ca_tmx_insider_transactions --symbol RY --month-duration 12
agentdata company ca_tmx_insider_activities --symbol RY
agentdata company ca_tmx_index_constituents --index-symbol ^TSX
agentdata company ca_tmx_wsh_events --symbol RY
agentdata company ca_tmx_filings --symbol RY --limit 10
agentdata company ca_tmx_dividends --symbol RY --page 1 --batch 10
agentdata company ca_tmx_instrument_search --keywords bank
agentdata company hk_hkexdi_corp_list --stock-code 00700 --list an --from-date 2025-01-01
agentdata company hk_hkexdi_form --fn IR20261118E00140
agentdata company hk_hkexdi_ir_summaries --stock-code 02656
agentdata company ch_six_official_notices --type EX --limit 5
agentdata company ch_six_notice_detail --notice-id 371045
agentdata company nz_nzx_listed --board NZSX --code TRA --quotes
agentdata company nz_nzx_company --code TRA
agentdata company nz_nzx_announcements --code MFT --price-sensitive true --limit 5
agentdata company de_xetra_instruments --instrument-type ETC --limit 5
agentdata company de_xetra_newsboard --venue XFRA
agentdata company de_xetra_newsboard_search --query Aussetzung --page 2
agentdata company kr_krx_listed --board kosdaq --limit 5
agentdata company kr_krx_indices
agentdata company eu_esef_filings --country GB --limit 5
agentdata company eu_esef_facts --lei 2138002P5RNKC5W2JZ46 --concept "Revenue*"
agentdata company gb_fca_firds_search --isin-sngl-noindx GB0008847096
agentdata company gb_fca_nsm_search --company "GRAINGER PLC" --limit 5
agentdata company gb_fca_official_list --security-isin GB0031348658
agentdata company gb_fca_official_list_activity --security-activity Admission --limit 5
agentdata company us_sec_13dg_stakes --cik 1022652
agentdata company us_sec_13f_holdings --cik 1067983
agentdata company us_sec_form4_transactions --cik 1833851
agentdata company gb_lse_universe --book equity --limit 5
agentdata company gb_lse_security_master --tidm BARC
agentdata company gb_lse_bond_details --tidm BARC
agentdata company gb_lse_ric_lookup --tidm BARC
agentdata company gb_lse_fundamentals --ric BARC.L
agentdata company gb_lse_index_membership --tidm BARC
agentdata company gb_lse_issuer_address --issuer-code BASDE
agentdata company gb_lse_issuer_profile --code VOVOD
agentdata company gb_lse_rns_archive --month 2026-10 --category form-8-3 --limit 5
agentdata company gb_lse_rns_article --url https://www.londonstockexchange.com/en/news/article/form-8-3-easyjet-plc/aa77-b0-c2-4e-8b-441fb9
agentdata company nasdaq_nordic_universe --market CPH --segment LARGE_CAP
agentdata company nasdaq_nordic_universe --category FIRST_NORTH
agentdata company nasdaq_nordic_indexes
agentdata company nasdaq_nordic_index_members --index-id IX447
agentdata company nasdaq_nordic_instrument_info --instrument-id TX2195
agentdata company nasdaq_nordic_instrument_summary --instrument-id TX2195
agentdata company nasdaq_nordic_fundamentals --instrument-id TX2195
agentdata company nasdaq_nordic_company_details --instrument-id TX2195
agentdata company nasdaq_nordic_trading_halt
agentdata company nasdaq_nordic_etf
agentdata company nasdaq_nordic_lookup --q Ericsson
agentdata company se_mfn_wire --market sweden
agentdata company se_mfn_issuer_feed --slug ambu --offset 48
agentdata company se_mfn_article --path /nir/a/ambu/transactions-under-ambus-share-buyback-program-eccc77cf

# economy (18)
agentdata economy bis_sdmx_series --flow WS_CBPOL --key M.US --start 2026-01-01
agentdata economy bls_series --series CUUR0000SA0,LNS14000000,CES0000000001 --start-year 2025 --end-year 2026
agentdata economy comext_flows --reporter DE --partner CN --product 85 --time 2024
agentdata economy ecb_fx_rates --currency USD --start 2026-10-01 --end 2026-10-31
agentdata economy eurostat_table --table nama_10_a64 --geo DE --time 2023
agentdata economy fred_series --series GDP --start 2024-01-01 --end 2026-11-01
agentdata economy ilo_stat_indicator --indicator EMP_TEMP_SEX_ECO_NB_A --ref-area USA --time-from 2020 --time-until 2024
agentdata economy imf_sdmx_series --flow WEO --country USA --indicator NGDP_RPCH --start 2023 --end 2026
agentdata economy oecd_sdmx_series --flow OECD.ECO.MAD,DSD_EO@DF_EO,1.5 --key DEU.. --start 2024 --end 2027
agentdata economy un_comtrade_trade --reporter USA --period 2023 --partner DEU --cmd TOTAL --flow X
agentdata economy unsd_sdg_indicators --search poverty
agentdata economy unsd_sdg_series --series DC_ODA_POVLG --geo China --time 2020
agentdata economy wb_countries --per-page 300
agentdata economy wb_ids_indicators --search "external debt"
agentdata economy wb_wdi_indicators --source 2 --search GDP
agentdata economy wb_wdi_values --country CHN --indicator NY.GDP.MKTP.CD --date 2020:2023
agentdata economy who_xmart_indicators --search tuberculosis --top 20
agentdata economy who_xmart_values --indicator TB_ppm_enrol_tx_prct --geo PAK --year 2023

# esg (8)
agentdata esg eiti_companies --name Equinor
agentdata esg eiti_payments --name Equinor
agentdata esg climatetrace_owners --name Gazprom
agentdata esg climatetrace_sources --owner-ids E100000001492 --year 2023 --limit 20
agentdata esg epa_frs_facilities --state-code DE --city-name MILTON --size 3
agentdata esg eutl_datasets
agentdata esg mx_sgm_concesiones --titulo 214536
agentdata esg uk_fhrs_establishments --name "pret a manger" --address london --pagesize 3

# healthcare (34)
agentdata healthcare rxnav_rxcui_by_name --name atorvastatin
agentdata healthcare rxnav_rxcui_atc --rxcui 83367
agentdata healthcare mesh_descriptor --label aspirin
agentdata healthcare gudid_devices --di 10198459305313
agentdata healthcare eudamed_devices_udi_di_data --primary-di 00191506004682
agentdata healthcare epmc_search --search 'AFF:"AstraZeneca"' --page-size 40
agentdata healthcare ctgov_studies --query.term 'AREA[LeadSponsorName]("Pfizer")' --page-size 3
agentdata healthcare ctgov_studies --query.titles aspirin --agg-filters phase:3 --page-size 3
agentdata healthcare dailymed_spls --search atorvastatin
agentdata healthcare fda_drug_shortages --search 'openfda.manufacturer_name.exact:"Fresenius Kabi USA, LLC" AND status:Current' --limit 3
agentdata healthcare fda_drug_recalls --search 'recalling_firm.exact:"SV Labs Toronto Corporation"'
agentdata healthcare fda_device_recalls --search 'recalling_firm:"Sedecal"' --limit 5
agentdata healthcare fda_food_recalls --search 'classification:"Class I" AND status:Ongoing' --limit 5
agentdata healthcare fda_crl_letters --search 'company_name:"InnoPharma"'
agentdata healthcare fda_drug_approvals --search 'sponsor_name:"TEVA"' --limit 5
agentdata healthcare fda_drug_catalog --search 'labeler_name:"pfizer"' --limit 5
agentdata healthcare fda_orangebook --search 'products.application_full_name:"Teva"' --limit 5
agentdata healthcare fda_device_510k --search 'applicant:"Medtronic"' --limit 5
agentdata healthcare fda_device_pma --search 'applicant:"Medtronic"' --limit 5
agentdata healthcare fda_device_registrations --search 'registration.name:"PLANET (ANHUI) INTERNATIONAL"' --limit 5
agentdata healthcare fda_device_classification --search 'device_name:"syringe"' --limit 5
agentdata healthcare gb_mhra_alerts --q Abbott --count 3
agentdata healthcare gb_mhra_alert --slug class-2-medicines-recall-xeal-pharma-clopidogrel-oral-liquids-all-strengths-el-26-a-slash-43
agentdata healthcare au_tga_artg --query '"Sun Pharma ANZ Pty Ltd"' --limit 5

agentdata healthcare au_tga_manufacturers --state QLD
agentdata healthcare br_cnes_facilities --codigo-uf 35 --limit 5
agentdata healthcare ca_dpd_companies --limit 5
agentdata healthcare ca_dpd_drug_products --status 3 --limit 5
agentdata healthcare ca_mdall_companies --limit 5
agentdata healthcare ca_mdall_licence --licence-id 111577
agentdata healthcare rasff_notifications --subject aflatoxin --items-per-page 5
agentdata healthcare safety_gate_alerts --year 2026 --limit 5
agentdata healthcare safety_gate_report --report-id 10000329 --limit 5
agentdata healthcare us_npi_organizations --organization-name "Mayo Clinic" --state MN --limit 3
agentdata healthcare jp_navii_facilities --q 内科

# legal (87)
agentdata legal afdb_debarred_entities --name "CHINA RAILWAY" --limit 3
agentdata legal ca_asc_enforcement --q Thomson --limit 5
agentdata legal ca_bcsc_disciplined --q Posen --limit 3
agentdata legal ca_cbsa_ruling --rulings-id 8000001670
agentdata legal ca_cbsa_rulings --limit 5
agentdata legal ca_sema_sanctions --country Syria --limit 3
agentdata legal ch_efk_party_financings --lang de --year 2025
agentdata legal ch_finma_enforcement_news --q "Julius Bär"
agentdata legal co_sic_sanctions --limit 3 --order "fecha_emitida DESC"
agentdata legal csl_screening_list --name "VTB BANK" --limit 3
agentdata legal de_lobbyregister_entries --identity ORGANIZATION --limit 5
agentdata legal ecfr_search --q asbestos --limit 5
agentdata legal ecfr_titles
agentdata legal dgcomp_cases_search --name Google --instrument SA
agentdata legal dk_ft_inspektionsredegoerelser_og_afgoerelser --year 2025 --page 1
agentdata legal idb_debarred_entities --q SHANDONG --limit 3
agentdata legal lda_filings --client-name "Google LLC" --limit 25
agentdata legal gb_ec_donations --query Sainsbury --limit 3
agentdata legal gb_ec_loans --query bank --limit 2
agentdata legal sipri_trades_search --supplier "United States" --type delivered --limit 3
agentdata legal eu_cijeu_search --q "state aid"
agentdata legal federalregister_documents --q asbestos --startdt 2026-01-01 --enddt 2026-09-30 --limit 3
agentdata legal courtlistener_opinions_search --q asbestos
agentdata legal fr_amf_sanction --theme all
agentdata legal fr_amf_transaction --theme all
agentdata legal gb_cma_cases --q google --count 5
agentdata legal gb_cma_case --slug nexfibre-slash-substantial-merger-inquiry
agentdata legal gb_tna_caselaw_search --party Barclays --per-page 3
agentdata legal gb_tna_caselaw_judgment --document-uri ewhc/admin/2026/2298
agentdata legal wb_debarred_firms --name "CHINA RAILWAY" --country CN --limit 3
agentdata legal gb_gazette_notices --insolvency --text "acme" --page-size 5
agentdata legal gb_nmw_round --slug 6-million-repaid-to-workers-as-government-cracks-down-on-employers-underpaying-their-staff
agentdata legal gb_nmw_rounds --count 5
agentdata legal ie_revenue_defaulters --part 1
agentdata legal us_occ_enforcements --year 2026 --month October
agentdata legal cfpb_complaints --search-term Discover --field company --size 3
agentdata legal cfpb_suggest_company --text Discover
agentdata legal in_indiacode_search --q "companies act"
agentdata legal in_sebi_orders --search Adani
agentdata legal tr_spk_fines --name "FERUDUN" --year 2025
agentdata legal tr_spk_bans --type company
agentdata legal ru_cbr_warning_list --violation pyramid --limit 5
agentdata legal ru_cbr_warning_list --site t.me --type internet_project --limit 5
agentdata legal br_bacen_regimes --cnpj 33171211
agentdata legal br_bacen_complaints --name ITAU --limit 5
agentdata legal br_bacen_complaints --tipo consortiums --name ADEMICON
agentdata legal br_cade_pesquisa_avancada --name PETROBRAS --limit 5
agentdata legal at_ris_judgments --court Justiz --case-number "2 Ob 52/16k" --limit 3
agentdata legal at_ris_statutes --q GmbH --limit 3
agentdata legal au_frl_titles --collection Act --top 5
agentdata legal ee_erjk_quarterly_reports --party-id 162 --limit 5
agentdata legal ee_erjk_election_reports --report-id 494641 --limit 10
agentdata legal es_boe_sumario --date 2026-11-10 --limit 5
agentdata legal ie_sipo_lobbying --query-text energy --limit 5
agentdata legal ua_nazk_parties --limit 5
agentdata legal ua_nazk_party_reports --party-id d0f1e224-e3de-45a2-8d12-43e4e9faee92 --limit 5
agentdata legal us_ferc_elibrary --docket CP17-101 --limit 5
agentdata legal fr_adlc_sanctions --id-decision 26-D-05 --limit 5
agentdata legal it_agcm_dettaglio --uid 0636576186F0C551C1258D5B0054C6E8 --replica dbconc
agentdata legal it_agcm_rating --words Telecom --maxresults 5
agentdata legal it_agcm_ricerca_provvedimenti --words Telecom --maxresults 5
agentdata legal it_arera_decisions --anno 2022 --numero 312
agentdata legal us_cbp_ruling --ruling-number 954699
agentdata legal us_cbp_stat
agentdata legal us_cftc_dispositions --page 0
agentdata legal us_cftc_enforcement --year 1995 --page 260
agentdata legal us_cftc_opinions --page 0
agentdata legal us_cftc_redlist --page 0
agentdata legal lv_knab_parties --limit 100
agentdata legal lv_knab_payments --party-public-id <public_id>
agentdata legal mx_cnv_sanctions --page-size 3 --order-field imposedOn --order-type DESC
agentdata legal mx_sabg_sanctioned_servants --q Abuso --limit 3
agentdata legal nl_rechtspraak_search --q onrechtmatige --page-size 3
agentdata legal pl_uokik_decision --unid EA4EB25AA6D1956FC1258EA3003605A7
agentdata legal pl_uokik_decisions --year 2026 --limit 5
agentdata legal kr_law_precedents --q 부가가치세 --page-size 3
agentdata legal kr_law_statutes --q 상속세 --page-size 3
agentdata legal fr_court_judgments --year 2026 --month 10 --court ce
agentdata legal fr_court_judgment --doc-id ECLI:FR:CECHR:2026:503183.20261001
agentdata legal us_occ_ea_search --q "Wells Fargo" --start-dte-min 2020-01-01
agentdata legal nl_acm_publications --category kartel --limit 5
agentdata legal nl_acm_publication --doc-id 896
agentdata legal es_cnmv_sanctions --party Sapiens
agentdata legal kr_fss_sanctions --layer institution --limit 5
agentdata legal au_accc_actions --limit 5
agentdata legal in_cci_antitrust_orders --q electricity --limit 5
agentdata legal in_cci_combinations --status Approved --form-type I --limit 5
agentdata legal jp_jftc_decision --case-id R080220R07G05000194K
agentdata legal jp_jftc_decisions --subject ソニー --limit 5

# procurement (7)
agentdata procurement br_pncp_contracts --data-inicial 20260901 --data-final 20260930 --pagina 1
agentdata procurement co_secop_contracts --where "upper(nombre_entidad) like '%MINISTERIO%'" --limit 5
agentdata procurement wb_procnotices --rows 5
agentdata procurement ny_abo_contracts --where "upper(vendor_name) like '%DELTA%'" --limit 5
agentdata procurement ny_mta_procurements --where "upper(vendor_name) like '%SKANSKA%'" --limit 5
agentdata procurement ungm_contract_awards --supplier DELTA
agentdata procurement ny_ogs_payments --where "upper(vendor) like '%HIGHLAND%'" --limit 5

# research (10)
agentdata research nih_reporter_projects --org-name "Stanford University" --fiscal-year 2024 --limit 3
agentdata research nih_reporter_publications --appl-ids 10491636
agentdata research nsf_awards --keyword "rare earth" --rpp 3
agentdata research openalex_institutions --search pfizer --per-page 3
agentdata research openalex_works --search aspirin --per-page 3
agentdata research crossref_works --funder 10.13039/100000001 --award-number OAC-1730655
agentdata research gb_gtr_projects --q lithium --s 10
agentdata research icite_pubs --pmid 26017442
agentdata research biorxiv_details --from-date 2026-10-01 --to-date 2026-10-07
agentdata research opencitations_citations --doi 10.1038/nature12373

# security (4)
agentdata security cisa_kev_catalog --limit 5
agentdata security euvd_exploited --limit 5
agentdata security euvd_vulnerability --id CVE-2024-3400
agentdata security osv_vulns --package lodash --ecosystem npm

# transportation (9)
agentdata transportation ca_ccar_aircraft --id 538042
agentdata transportation ca_ccar_search --owner "AIR CANADA" --limit 3
agentdata transportation euasl_datasets
agentdata transportation paris_mou_bans
agentdata transportation paris_mou_detentions
agentdata transportation paris_mou_inspections --period-min 01/12/2025 --period-max 31/12/2025 --ism-company-imo-number 0052193
agentdata transportation paris_mou_low_performance_companies
agentdata transportation thetis_mrv_datasets
agentdata transportation us_fmcsa_carriers --where "dot_number='963305'" --limit 3
```

## Caching

Every response is cached in a per-user SQLite cache shared across processes —
cache hits cost no rate budget, and entry lifetimes follow the per-source TTL
table in the [rate-limits ledger](https://github.com/dicaria/agentdata/blob/main/docs/domains/rate-limits.md);
immutable lookups (e.g. drug name → RxCUI) are cached permanently. A fresh
install in a new virtual environment will reuse entries written by earlier
runs on the same machine — that is by design.

| | |
|---|---|
| Default | `%LOCALAPPDATA%\agentdata\cache.db` (Windows) · `~/.cache/agentdata/cache.db` (macOS/Linux) |
| Override | `AGENTDATA_CACHE_DIR` env var · `--cache-dir` (CLI) |
| Bypass / clear | `--no-cache` (CLI) · `no_cache=True` (Python) · delete the file |

## Documentation

- [docs/domains/api.md](https://github.com/dicaria/agentdata/blob/main/docs/domains/api.md) —
  the API contract of the release you installed: the two families,
  request/response envelope, parameter conventions
- [docs/domains/rate-limits.md](https://github.com/dicaria/agentdata/blob/main/docs/domains/rate-limits.md) —
  per-source rate-limit facts this release enforces
- [docs/publishing.md](https://github.com/dicaria/agentdata/blob/main/docs/publishing.md) —
  maintainer setup, package checks, and PyPI releases
- Hosted-corpus per-domain guides: contact **contact@dicaria.com**

## Releases

The complete batch log — every release back to 0.1.0 — lives in the source
repo's Chinese README; this public README carries the most recent batches:

**0.3.78 — Batch E21, the TMX Canada directory + GraphQL gateway family: thirteen
faces (+13 born flat, 309→322; company 132→145; +1 provider `ca-tmx`, keyless; CA
pure deepening — zero new jurisdictions, the 37-stamp set holds; live-probed
end-to-end 2026-11-27 tmp/probe-e21/).** ONE provider over TWO hosts: the four
directory faces (`ca_tmx_directory_search` / `_recent_listings` / `_delisted` /
`_suspended`) ride www.tsx.com `/json/company-directory/*` keyless JSON while the
nine gateway faces ride app-money.tmx.com Apollo GraphQL POST (absolute-path ops,
the hk_hkex/edgar_xbrl/gb_lse precedent; Origin/Referer ride only on the gateway;
introspection is production-OFF — the contracts were excavated from the site's
webpack chunks). **The E10 deferral CLOSES**: tsx.com's 2026-11-18 AWS WAF JS
challenge keyed on EXIT-IP REPUTATION WINDOWS, not headers — the 2026-11-23 and
2026-11-27 egresses answered clean 14/14, and the dual-stack probe passed bare-UA
urllib on BOTH hosts, so NOTHING is curl-pinned (the nasdaq-nordic contrast).
Laws per family: the directory prefix law is NAME-OR-SYMBOL (single-letter scans
carry ~10% name-only rows; rows are company-level with multi-instrument children —
.U variants and AB classes, 17 of 140 TSX "a" rows; the envelope is
{last_updated,length,results,isHttpError} with length authoritative and
last_updated the census instant shared by all four ops); recent/delisted are
ROLLING ~12-week windows with NO pagination (?page byte-identical — monthly sweep
is the archival duty) while suspended is a PRESENT-STATE register (name/symbol
only, the nasdaq_nordic_trading_halt analogue); the profile face pins a 41-field
selection with the quote block STRIPPED AT THE QUERY LEVEL (prices/volumes/ranges/
52-week/moving-averages never enter the request — WORD-level law,
priceToBook/priceToCashFlow are kept fields; RY 39 live keys + 2 null); short
interest rides the bi-weekly register (RY 2026-11-25: 11,960,786 shares);
insiders run monthDuration 1..120 (12 ≈ 480 rows, 120 ≈ 4,177 rows ≈ ten years,
the SEDI ceiling) plus the three-window activity aggregate; index constituents
take ^-prefixed symbols (^TSX 215 members with the keyData ratio card — index
price history stays out); WSH events keep the data.quote.data event-LIST shape
with MM/DD/YYYY dates verbatim (Wall Street Horizon upstream, ISIN aboard);
filings are METADATA-ONLY (urlToPdf lands on app.quotemedia.com whose robots bans
/data/ — the pointer is kept, never fetched); dividends paginate page
1..500/batch 1..100; instrument search is the cross-exchange resolver (keywords
1..80, includes US cross-listings). **Carried fix disclosed**: E20's
nasdaq_nordic engine dropped cache/no_cache on every call — the ten faces' TTLs
never engaged; threading is fixed in this batch for BOTH modules and pinned by
the cache-threading law test.** Rate limits ca-tmx 1/1 one row; TTLs
profile/dir_search/dividends/insider/insider_activities/constituents/instr_search
24h, delisted/recent/suspended/short_interest/filings/wsh 1h; rate-limits v1.65
(189 providers / 322 faces); offline pins tests/test_flat_0378.py + engine laws
tests/test_ca_tmx.py; company-thirdparty-api-design.md §4.55; command-naming rows
310-322; mapping/company.md 13 booklets.

**0.3.77 — Batch E20, the Nasdaq Nordic four-venue screener family + the MFN
Nordic disclosure wire: thirteen faces (+13 born flat, 296→309; company
119→132; +2 providers `nasdaq-nordic` (api.nasdaq.com/api/nordic — the
five-venue census DK/SE/NO/FI/IS served by ONE host) and `se-mfn` (mfn.se —
the JSON Feed disclosure wire), both keyless; SE is jurisdiction #37 — the
first new stamp since E15 (nasdaq_nordic_* = EU multi-venue, se_mfn_* = SE);
live-probed end-to-end 2026-11-24 tmp/probe-e20/).**
The nasdaq family: `nasdaq_nordic_universe` (the four-venue screener census,
Σ=1,112: Main 255 CPH + 238 STO + 210 HEL + 0 ICE + First North 409; the
DEFAULT-SEGMENT TRAP — MAIN_MARKET without segment answers ONLY Large Cap,
segment required, FIRST_NORTH takes none), `nasdaq_nordic_indexes` (86
IX-prefixed indexes), `nasdaq_nordic_index_members` (IX447 = OMXS30 walks
clean at exactly 30; the 100-ROW WINDOW law — the upstream answers the first
100 and ignores offset/size, Nordic 120 IX10282 truncates with window_note),
`nasdaq_nordic_instrument_info` (the qdHeader master card; assetClass=SHARES
mandatory — 400 10001 without), `nasdaq_nordic_instrument_summary` (the
share-base card — Maersk TX2195: 9,586,488 shares, DKK 188.6bn series cap;
the summary strip is a LIVE KEY CENSUS: the sharePriceChange×6 return family
+ priceNotation + the day/52-week/volume blocks stripped, the red line),
`nasdaq_nordic_fundamentals` (the family-unique Morningstar nine-ratio card
— TX2195 PE 10.59), `nasdaq_nordic_company_details` (the five-card
Morningstar profile), `nasdaq_nordic_trading_halt` (a present-state register,
16 rows probe day — not an event stream), `nasdaq_nordic_etf` (category=ETF
true enumeration, 32 funds — the settings-default 'ETP' answers 400),
`nasdaq_nordic_lookup` (the group resolver — Ericsson B answers ERIC B/SEK +
ERIBR/EUR; the join key is the orderbookId). The mfn family: `se_mfn_wire`
(/all/s/{market}, five markets, the stream-segment law — bare /all/s 301s to
/all/s/nordic, an explicit market always rides), `se_mfn_issuer_feed`
(48/offset pages to full depth — Ambu p1 2026-11 → p2 2025-12 seamless;
unknown slug = 200 empty-items soft-404, returned honestly empty),
`se_mfn_article` (the single-item feed full card — publish_date UTC
authority, issuer isins/leis/tickers aboard; unknown path = honest 404).**
The channel laws: THE CURL CHANNEL IS LOAD-BEARING FOR THE FIRST TIME
(api.nasdaq.com is an Akamai JA3 fingerprint gate — urllib 403 under every
header combo, curl bare-UA 200, same-hour dual-stack measured; all ten
nasdaq ops pin transport="curl"), the ENVELOPE law ({data,messages,status}
unwrap), the 400-10003 law (unknown instrument = 400 "Instrument not found",
NOT 404 — notFound=[400], a ledger first), the STAR-SHELL law (unknown
star/index id = 200 Drupal HTML shell → found=false), the 42-KEY SUPERSET
ROW law (one row shape across all four screeners — 23 quote/volume columns
stripped, the red line; strikePrice/couponRate/contractSize/expirationDate/
totalExpenseRatio are instrument TERMS, kept), and the CONTENT-NEGOTIATION
law (mfn.se canonical paths answer the JSON Feed spec to Accept:
application/json and HTML to browsers — the probe-day HTML-parse plan killed
live same-day; the SDK pins the JSON face, shape drift raises; robots bans
URL SUFFIXES only — bare canonical paths carry none). Rate limits
nasdaq-nordic 1/1 · se-mfn 1/1; TTLs universe/indexes/halt/etf/cards 1h,
children/lookup/company/articles 1d (mfn wire/feed 1h, article 1d);
rate-limits v1.64 (188 providers / 309 faces); offline pins
tests/test_flat_0377.py (15) + engine-law tests/test_nasdaq_nordic.py +
tests/test_se_mfn.py (37).

**0.3.76 — Batch E18, the LSE exchange-universe family: ten faces (+10 born
flat, 286→296; company 109→119; +1 provider `gb-lse` over THREE hosts —
apidata.londonstockexchange.com keyless REST + www.londonstockexchange.com
sitemap/article pages + cache-api.lsegissuerservices.com issuer IR cards (the
hk_hkex / edgar_xbrl absolute-path precedent); GB pure deepening — 36
jurisdictions; the G7 exchange-universe axis COMPLETES SEVEN OF SEVEN (US/
JP/DE/FR via eu_euronext/IT/CA via CSE + GB direct on LSE this batch — the
0.3.74 "GB rides the FCA Official List" wording is superseded; old blocks
stay, corrected in the new); the market-data red line holds —
instrument/trade summaries, rdp pricing, tmv, tradingstatus, validate, AIM
advisers, the fdc-token→samllogin→tns tick chain and OHLCV bars are licensed
goods, deliberately OUT — the SDK wraps the universe/master/profile/RNS
corpus layer only; live-probed end-to-end 2026-11-24 tmp/probe-e18/).**
The family: `gb_lse_universe` (five security sitemap books
equity/bonds/etps/others/turquoise, 62,713 pages — the quote-page URL IS the
TIDM universe), `gb_lse_security_master` (the NRDP join-key card:
instrumentId/isinCode/sedol/mic/issuerCode — BARC 4753/GB0031348658/3134865/
XLON/BASDE), `gb_lse_bond_details` (LIVE REVERSAL 1: the GENERIC security
card, not bonds-only — BARC equity answers a full card with maturityDate
null), `gb_lse_ric_lookup` (the TIDM→RIC bridge, BARC→BARC.L — the
fundamentals key), `gb_lse_index_membership` (FTSE constituents as parallel
comma lists — strict zip, mismatch raises before guessing),
`gb_lse_fundamentals` (the RIC-keyed card, snake_case keys verbatim — BARC
PE 8.13 / mcap 52,831.47 m GBP), `gb_lse_issuer_address` (issuerCode-keyed
address+website — BASDE: 1 Churchill Place, Canary Wharf E14 5HP +
www.barclays.com), `gb_lse_issuer_profile` (LIVE REVERSAL 2: the code is the
nrdp displayissuercode, NOT the ticker — VOVOD = Vodafone's 33-instrument
card admitted 1988-10-26 while BASDE honest-404s though it is Barclays' OWN
issuerCode: coverage is issuer-opted, double-proven), `gb_lse_rns_archive`
(the RNS monthly sitemaps — slug melt "form-8-3-easyjet-plc" never a company
name; archive floor 2024-11, the ~25-month window is the depth ceiling,
refused locally below it; census: current month 35,272 URLs, full months
~44k-49k, form-8-3 ≈2,938 / form-8-5 ≈1,870 / NAV ≈2,545 per month — ≈130k
form-8-* filings across the window), `gb_lse_rns_article` (full RNS text
from the server-embedded articleBody — the easyJet form-8-3 runs 54,674
chars, filer Hudson Bay Capital; the PATH_SAFE law: the {url} tail carries
category/hash slashes, path_safe="/" — quoting → %2F → a 200 shell page).
The channel laws: the ENVELOPE law ({"statusCode":200,…,"data":…} unwrap),
the 200-EMPTY TRANSIENT law (one no-cache re-ask before "EMPTY twice" —
never a coverage boundary), the WWW DEGRADE-TRANSIENT law (a 200 page
without articleBody re-asks no-cache, the fresh answer overwrites a poisoned
cache entry, body-less forever = genuine miss), the intermittent
HEADER-FINGERPRINT gate (2026-11-23 demanded Accept/Referer, 2026-11-24
answered a bare UA — the headers ride anyway), the PARALLEL-LIST law, and
the SLUG-MELT + ARCHIVE-FLOOR laws. Fix-forwards disclosed: the module's
_call_rest retry wrapper double-bound no_cache (closure + kwarg → TypeError
— the empty-200 re-ask had never actually run; the probes were all non-empty
so it never fired live; the test_flat_0376 fixture run caught it, kw.pop
fixed), the §9.6 duplicate roll (the 0.3.75 entry had shipped twice — a
compressed draft between 0.3.73/0.3.74 plus the full block — removed this
batch; changelog entry 113), and the dead form-8-3 ≈5,077/month census (the
research doc's full-month census prevails).** Rate limit gb-lse 1/1 (one
provider, three hosts, each its own polite bucket); TTLs bond/ric/address/
article 1d, the rest 1h; rate-limits v1.63 (186 providers / 296 faces);
offline pins tests/test_flat_0376.py (12).

**0.3.75 — Batch E17, the EDGAR holdings-disclosure trio: three faces (+3 born
flat, 283→286; company 106→109; +0 providers — the family's first ZERO-bucket
batch: module `edgar_ownership` rides the existing `edgar_cik` submissions +
`edgar_arch` Archives index/doc buckets, no new host, no new polite tier; US
held — 36 jurisdictions; live-probed end-to-end 2026-11-23 tmp/probe-e17/).**
The trio completes the SEC holdings-disclosure pillar:
`us_sec_13f_holdings` (institutional quarterly holdings — the whole
information table per filing; value switched thousands→whole USD with the
2023-Q1 reporting periods, the card always carries value_units — Berkshire's
Q3-2026 card sums 89 positions to $304,196,581,325 usd),
`us_sec_form4_transactions` (insider transactions — non-derivative +
derivative rows with post_shares; Upstart's 2026-11-20 filing: 562 shares
sold @ $16.2925, 38,963 held after),
`us_sec_13dg_stakes` (Schedule 13D/G activist stakes — issuer OR filer CIK;
Inseego carries both shapes live: Royce's 13G/A at 30,000 shares 0.18% and
the Nokia-group 13D at 2,721,196 shares 14.2%). The laws are channel walls:
the XSL-SHELL law (13F AND 13D/G submissions primaryDocument points at the
human rendering shell — the raw XML sits at the accession root, resolved via
the index op, never via primaryDocument; Form 4 is the sole exception — its
primaryDocument IS the root wk-form4 XML), the ROOT-XML PICK law (the 13F
table = root-level *.xml minus primary_doc.xml, 'info'-named preferred,
ambiguity → usage_error naming candidates), the NAMESPACE law (13F
informationTable and 13G schedule13g carry default namespaces since
2014/2022, Form 4 ownershipDocument is namespace-free — localname matching
throughout, a bare findall("infoTable") answers ZERO rows), the FORM-STRING
law (submissions carries BOTH the structured SCHEDULE 13D/G(/A) era and the
legacy SC 13D/G(/A) HTML era — the enumeration filter is the eight-string
union; legacy rides parsed=False + doc_url, never a fabricated stake), the
TWIN-LAYOUT law (13D reportingPersons blocks with filer CIK vs 13G
coverPageHeaderReportingPersonDetails blocks with the four powers inside the
ownership wrapper and no CIK; issuerCik/issuerCIK case-insensitive card
lookups), and the PTR negative (STOCK Act forms PD/PTXA/PTR answer zero in
EDGAR — congressional PTRs live in the House/Senate systems, out of this
batch). Fix-forwards disclosed: the shared edgar_arch.index_rows document
gate widened to .xml (13F accessions are XML-only directories — the scaffold
gate itself untouched), and the Form 4 post_shares probe re-aimed at the
grandchild <value> under sharesOwnedFollowingTransaction (the middle
element's own text is empty — the field had silently vanished on live rows;
caught by the test_flat_0375 fixture, re-verified live post-fix).** No new
rate-limit rows (the 5/5 www.sec.gov fair-access buckets ride on, inside the
official 10 req/s declared-UA budget); TTLs 7d across the family (filed
documents and the window index are frozen history); rate-limits v1.62 (185
providers / 286 faces); offline pins tests/test_flat_0375.py (41).

**0.3.74 — Batch E16, the UK FCA data-API family + the EU ESEF register: six faces (+6 born flat, 277→283; company 100→106; +2 providers `gb_fca` + `eu_esef`, both keyless; GB/EU held — 36 jurisdictions; live-probed end-to-end 2026-11-23 tmp/probe-e16/).** `gb_fca` rides api.data.fca.org.uk (POST /search?index=…, four indexes: nsm-search 5,570,535 / official-list-main 15,160 / daily-activity 119,810 / firds-view 169.6M) and fills the GB seat of the G7 exchange-universe axis — six of seven now held, but as a REGULATOR register (the Official List), not an exchange feed (CA remains CSE-only, TMX WAF-gated). ERROR-SHAPE law: a malformed body 404s "Unable to search the data" (→ upstream_unavailable) while a WRONG facet value silently 200s total 0 — every vocabulary is validated locally before sending. Per-index date laws (NSM/activity want full ISO seconds; OL/FIRDS want dd/MM/yyyy and FIRDS demands a to-bound — the SDK fills 31/12/2099); the 10,000 window law (from+size ≤ 10,000 checked locally, page cap 5,000); rows carry populated fields only. NSM is TWO-PATH (text needs latestFlag:"Y" + primarySearch over document_content×headline, TEXT_MODES=match_all_words/exact_match, criteriaObj members are LIST-typed) with artefact links absolutized under data.fca.org.uk/artefacts/; activity takes securityActivityDateCriteria as an OBJECT with the closed ACTIVITIES set Admission/Suspension/Restoration/Cancellation; FIRDS is keyword-XOR-criteria ({from,size,keyword} only), always filters techattrbts_nvrpblshd=false (never-published records stay invisible) with active_flag=Y default and the 11 long-form LISTING_CATEGORIES closed set. robots Content-Signals: search=yes / ai-train=no / use=reference — the SPA's collectAnalytics endpoint and its honeypot are NEVER called, and a Range header is NEVER sent (10054 reset). The NSM web UI's click-through notice is UI-only and does not gate the keyless API. `eu_esef` rides filings.xbrl.org (JSON:API): filings take filter=[{name,op,val}] compact + a mandatory sort, page[size]≤1000, and beyond-last-page is an honest 200 with empty data[] and unchanged meta.count; fxo_id is really {LEI}-{YYYY-MM-DD}-ESEF-{CC}-{seq} (trailing 0=original, 1+=amendment); the corpus is 27,817 filings / 7,505 issuers / 28 countries (GB 2,982/806 — published is null on every GB row; DE/IE absent). facts-by-LEI picks the latest-processed same-period filing WITH a json_url (≤5 pages, sort -period_end); XBRL-JSON periods are end-exclusive with midnight instants landing on the next day — inclusive end = raw −1 day; concept matching is wildcard local-name ("Revenue*" catches ifrs-full:Revenue).** Rate limits gb_fca 0.5/2, eu_esef 0.1/2 concurrency 1 (filings.xbrl.org clamps ~10/min with 429s — the SDK stays at 0.1 rps; upstream suggests a contact UA, the SDK default stays agentdata/<version>, end users may set AGENTDATA_CONTACT); TTLs nsm 15min / official_list 6h / activity 1h / firds 6h / filings 6h / filing 1h / facts 7d; rate-limits v1.61 (185 providers / 283 faces); offline pins tests/test_flat_0374.py (28).

**0.3.73 — Batch E15, the Xetra/Frankfurt T7 universe trio + the KRX Global pair: five faces (+5 born flat, 272→277; company 95→100; +2 providers `de_xetra` + `kr_krx`, both keyless; DE/KR held — 36 jurisdictions; live-probed end-to-end 2026-11-20 tmp/probe-e15/).** `de_xetra` rides cashmarket.deutsche-boerse.com (the site self-describes as "formerly xetra.com"; robots: zero Disallow) and takes Germany through the G7 exchange-universe axis' door (not a closure — 0.3.74 adds GB via the FCA regulator's register, six of seven; CA still CSE-only, TMX WAF-gated). The T7 allTradableInstruments CSV lives at a BLOB-HASH path that versions on every upload — the link is re-parsed from its landing page on EVERY fetch (the Frankfurt variant hangs under the Xetra section at boersefrankfurt while /Tradable-Instruments-Frankfurt/Downloads is a 404 decoy); rows 1-2 carry Market + Date Last Update, row 3 is the header, 153 columns verbatim, counts drift DAILY (never pinned); api.live.deutsche-boerse.com is a catch-all {} shell — negative. The Newsboard is a 100-item RSS ROLLING window (~15h — hourly polling is the no-loss cadence) with venue-prefixed titles; the search face is FULL HISTORY (delisting notices back to the 2020 number block; pageNum rides statelessly, each hit an anchor-wrapped href/date/tagline/text quad). `kr_krx` rides global.krx.co.kr — the OPEN portal of the three-sister gate family (data.krx member wall + Akamai, kind.krx WAF, global robots Allow:/ verbatim). The listed universe runs the OTP double-step (GenerateOTP.jspx mints a one-shot base64 code, posted back 2s later with market_gubun 0/1/2/6) → block1 = the whole universe ONE-SHOT (~2,769 rows ×10 cols; All reconciles with the kospi/kosdaq/konex splits); the bld is the FULL path form GLB/03/0308/0308010000/glb0308010000 (the endpoint name is NOT the bld — a wrong pair answers 200 with zero bytes, the silent-empty law); the one-shot code NEVER enters the cache key (hand-rolled code-less key — repeat calls are cache hits with zero OTP mints); numbers keep comma strings + *_num int companions; indices is the free-OTP family (main.jspx?bld=index_list plain GET; cmpr_rt keeps upstream's raw scientific-notation string verbatim).** Rate limits de_xetra 1/1, kr_krx 1/1 concurrency 1; TTLs CSV 6h / landing 1h / RSS 30min / search 1h / grid 6h / indices 15min; rate-limits v1.60 (183 providers / 277 faces); offline pins tests/test_flat_0373.py (27).

**0.3.72 — Batch E14, the NZX dehydrated-state trio + the SIX official-notices
pair: five faces (+5 born flat, 267→272; company 90→95; +2 providers `nz_nzx` +
`ch_six_onot`, both keyless; NZ/CH held — 36 jurisdictions; live-probed end-to-end
2026-11-19 tmp/probe-e14/).** `nz_nzx_*`: the New Zealand exchange rides the Next.js
SSR DEHYDRATED STATE (robots disallows /api/ and /search — the compliant surface IS
the whole surface); the whole-exchange master is byte-identical on the NZSX/NZDX
pages (427 rows ×16 keys; the board picks only the quote panel — 178 equities /
135 bonds), lastListedDate 3000-01-01 is the CURRENT sentinel (the master is the
ACTIVE set — delisted instruments drop out), the four company panels are labelled
by their queryKey tails (contact/summary/directors + instruments — the
label-collision fix; summary carries FYE + auditor + solicitor + registry + venue),
a bad code is an honest 404 with EMPTY queries (found=false — the meta is the
observation, never a body), and ?page=2 on announcements is IGNORED upstream so
newest-200 is the whole SSR surface (the boundary is documented, not worked
around). `ch_six_*`: the sheldon v2 pipeline — the show* switches are DEAD (an
8-combination matrix answered identically; noticeType filters the fetched page
locally), issuerWords is a PAGE-1 SNAPSHOT (a partial 43/143 page + persistent
deeper-page garble), pageSize pinned 100 (200 breaks paging; 1000 answers an empty
itemList while totalCount still echoes — the silent-over-cap shape; reachable
ceiling ~5 pages/window → one-week windows cover fully), transient failures both
ways (garbled 200s retried after 4s and 502s after 8s — one patient no-cache retry
each, a garbled body never cached as good), and DD-MM-YYYY dates are REFUSED
(dash-stripping would swap day/year into a legal-looking string); FL titles are
bare date strings, the semantics live in the detail text.

**0.3.71 — Batch E13, the CSE exchange pair + the HKEX Disclosure-of-Interests
deep: five faces (+5 born flat, 262→267; company 85→90; +2 providers `ca_cse` +
`hk_hkexdi`, both keyless; CA/HK held — 36 jurisdictions; live-probed end-to-end
2026-11-19 tmp/probe-e13/).** `ca_cse_listed`/`ca_cse_company`: the Canadian
Securities Exchange — a Next.js head over WordPress whose data rides the site's
own /api/* JSON; /en prefix + trailing slash mandatory; a bad symbol answers 200
with a ZERO-BYTE body → found=false (the silent-empty law); the universe is 739
rows with every selector client-side (the status filter IS the negative list);
trading_date is per-row last trade. `hk_hkexdi_*`: the SESSION QUARTET cached
together 30min (the jp_jftc law generalized); corpn rides the six list links; the
caption rides the header row's first cell (anchor the first known header cell);
leading zeros are digits (lstrip both sides); positions signature "Total number
of shares" before the generic split; the DION floor 2017-07-03 refused locally.
The date-axis captcha wall and SDW/CCASS stay out (upstream terms §2.3); TMX
re-probed 2026-11-19 — still AWS WAF, stays deferred.

**0.3.70 — Batch E12, the developed-economy exchange universes + the HKEX deep-dive (+3 providers
`at_wiener` / `au_asx` / `hk_hkex`, +5 faces, 257→262; 174→177 providers; 35→36 jurisdictions —
Hong Kong joins as the 36th; company 80→85 — Australia's first company face).** `at_wiener_borse_listed`
— the Wiener Börse market-segment universe, reviving the E10 TLS deferral (the morning's mislinked
`*.factsetdigitalsolutions.com` certificate was upstream's own; the afternoon DigiCert chain answers
green — same-day flips get re-probed before being written off); multi-value cells split on span
element boundaries, ISIN rides the company-page slug with a tolerated trailing slash, German numbers
(decimal comma, thousands dot, Mio./Mrd. multipliers) carry a parsed `*_num` beside the raw string.
`au_asx_listed` — the ASX three-band CSV (banner with the as-at anchor, header band, 2,060 live rows
anchored on BHP); the GICS 27-group closed set keeps "Not Applic"/"Class Pending" verbatim as
legitimate values. `hk_hkex_securities` — the HKEX ListOfSecurities.xlsx, 17,336 rows (stocks 2,812,
warrants 6,908, CBBC 5,830, debt 1,322, ETP 453, REIT 11 — not equities-only, hence "securities"),
parsed with pure stdlib zip+xml; the eighteen-column header is a verbatim wall (the sheet's
`<x:dimension>` under-reports — the rows are the truth), and the R column pairs RMB-counter codes
(00700↔80700). `hk_hkexnews_search` — the titleSearchServlet JSON double-encoded inside a string
(two `json.loads` passes), three mutually exclusive modes (`--stock` via the prefix.do JSONP unwrap,
`--title`, or one of six local `--codebook` dictionaries), HK-style DD/MM/YYYY HH:MM timestamps
verbatim, every row carrying the `full_url` for the document face. `hk_hkexnews_document` — the
`/listedco/{link}` PDF bytes reusing E11's body-fetch mode (sha256 + size_bytes + lossless latin-1
round-trip; the live anchor matched curl byte-for-byte) behind SSRF double walls (`--url` pinned to
the www1.hkexnews.hk/listedco/ host, `--link` requiring a non-empty /listedco/ prefix); the batch's
headline transport law: `{link}` carries slashes, so the op declares `path_safe="/"` — without it
build_url's quoting glues the path into the host name (www1.hkexnews.hk%2Flistedco…, fingerprinted
by a proxy CONNECT 400 "Tunnel connection failed" while curl on the same URL answers green).
One provider, two hosts (www.hkex.com.hk universe + www1.hkexnews.hk announcements, separate polite
buckets); offline nails in tests/test_flat_0370.py (38).

**0.3.69 — Batch E11, the SEC Archives body fetch: `us_sec_filing_document` (+1 face,
256→257; company 79→80; +1 provider `edgar_arch` — the fair-access family's fourth
member at 5/5 sharing the www.sec.gov host bucket; 35 jurisdictions held; live-probed
2026-11-18 tmp/probe-e11/)** — the body layer under the filings line (submissions =
index, fts = hit metadata, xbrl = facts; 8-K bodies, EX-99 exhibits, 10-K iXBRL — the
bytes were only reachable as doc_url links). Forms: --url (a doc_url from
us_sec_fulltext_search, prefix-walled to sec.gov/Archives before a byte leaves the
process) XOR --cik + --accession; without --filename the submissions primaryDocument
is the auto-primary (older-than-recent-window accessions fall to the index
single-candidate rule or a usage_error naming the candidates); --list is the directory
mode of the same face. Laws: the SGML envelope two shapes (older filings wrapped —
fields run to end of line, inner = first <TEXT> to the LAST </TEXT> greedy; modern
filings bare iXBRL passthrough); index.json a pure directory listing on every era (the
type column is an icon name, no isPrimaryDocument — scaffold rows flagged, never
counted; a scaffold-only dir = bogus accession → upstream_not_found, the ghost
filename1.htm listing never laundered as an empty dir); the CIK path segment mandatory
(accession-only 403s); bytes via the latin-1 round-trip + sha256 over raw, decode
chain charset→utf-8→cp1252→replace; --text a zero-dependency stdlib HTMLParser; TTL 7d
(filed documents freeze). Offline pins tests/test_flat_0369.py (40 pins).

**0.3.68 — Batch E10, the developed-economy exchange faces: five listed-universe/quote faces
(+5 faces, 251→256; 169→173 providers; 35 jurisdictions held; company 74→79 — first Italian
company face, zero new jurisdictions).** `ch_six_fqs_search` — the SIX Swiss Exchange FQS
command API (column oracle pinned: invalid select names are 400-rejected verbatim, so the
engine refuses them locally; price columns are opt-in under SIX's commercial-use caveat).
`eu_euronext_instrument_search` — the live Euronext venue resolver: one ISIN lists on many
MICs, the join key is ISIN+MIC, and the zero-hit sentinel row is dropped rather than counted.
`it_borsa_quote` — the Borsa Italiana dati-completi card by ISIN (market cap parsed from
Italian number format; an unknown ISIN or mismatched MIC serves a generic page silently —
reported `found=false`, never a fabricated card). `jp_jpx_stock_list` + `jp_jpx_stock_detail`
— the JPX qjsonp gateway behind its Referer door: the 4,490-name listed universe page by page
(board + 33-sector industry on every row) and the 57-field issue card (ISIN, market cap JPY,
shares, embedded daily OHLCV, EPS history). Two same-day upstream flips deferred with probe
evidence: Wiener Börse (TLS serving a `*.factsetdigitalsolutions.com` certificate on both
hosts) and TMX (tsx.com flipped to an AWS WAF JS challenge between the morning's green probes
and the afternoon smoke — a urllib client cannot execute the challenge; re-probe later).

**0.3.67 — Batch E9, the reliability fix: `us_sec_fulltext_search --census` (+0 faces, 251/169/35
held — a mode on an existing face).** The plain mode returns one 100-hit page and post-filtering it
systematically undercounts; census sweeps the whole window — date bisection until every leaf window
is exact, every page harvested, deduped by filing accession. `--census-entity` is the local
whole-word entity filter (the upstream does not parse company:"..." — the quoted prefix is just a
search term; "IREN" never hits "Siren"); a single-day window still over the 10,000 floor is reported
in overflow_windows, never dropped; the request budget (default 400) fails loudly with progress.
Reference-date anchors, all complete and equal to manual windowed re-runs: IREN×Nvidia 87 filings
(50 current-name + 37 old-name Iris Energy — one issuer), CoreWeave×OpenAI 37 (34 issuer + 3
co-filed 425), APLD×Nvidia 54 (the hand count of 43 had dropped the S-1 registration family) —
strict supersets with transparent composition.

**0.3.66 — Batch E8, the deferral reopening: the SEC XBRL structured-facts family (+4 faces on one new provider, 247→251; 168→169 providers and 35 jurisdictions held; company 70→74 — US deepened only).**

One keyless provider `edgar_xbrl` on data.sec.gov, live-probed 2026-11-17 — the quantitative
layer under the `edgar_cik` registry layer, reopening the 2026-10-19 deferral (the local XBRL
bulk that ruling leaned on was lost with the E: drive, and the MCP/OmniHub surface carries no
financial-data paths). `us_sec_companyconcept` is the cheap server-side point query (18 KB vs the
4 MB dump), `us_sec_companyfacts` is the issuer dump in inventory mode (taxonomy → concept-name
list — the drift-discovery face) XOR concept mode, `us_sec_frames` answers one concept × unit ×
period cross-section for the whole market (NetIncomeLoss CY2024 = 6,084 entities), and
`us_sec_tickers` is the ticker↔CIK directory riding an ABSOLUTE path to www.sec.gov (one provider
id, two hosts, each with its own polite bucket; exactly one selector — bare enumeration
refused, rows 10,404 ↔ 7,997 CIKs because share classes share a CIK). Three live laws baked
in: the CONCEPT-DRIFT LAW (us-gaap tags drift across taxonomy versions — Revenues is dead
after 2018 → RevenueFromContractWithCustomerExcludingAssessedTax; issuers simply lack
concepts — Apple has no EarningsPerShareDiluted; tags pass through verbatim, absence is a
legal answer); the FY/FP LAW (a fact's fy/fp stamp the FILING, not the fact period — Apple's
FY2026 10-K carries the FY2025 comparison period stamped fy=2026; period membership reads
off start/end); and the FRAME LAW (CY<year> / CY<year>Q<n> / CY<year>Q<n>I only). Rate 5/5 —
edgar_cik 5 + edgar_xbrl 5 = 10 ≤ the official 10 req/s with a declared UA (the §7 exception
register's third member); TTL companyfacts/companyconcept/frames 7d, tickers 24h; rate-limits
v1.54 (169 providers / 251 faces); pinned by `tests/test_flat_0366.py`.

**0.3.65 — Batch E7, single-face deepening: US CFTC OGC Opinions & Adjudicatory Orders (+1 face born flat, 246→247; 168 providers and 35 jurisdictions held; legal 86→87 — US deepened only).**

One keyless face on the extended-in-place `us_cftc` provider, live-probed 2026-11-17. `us_cftc_opinions`
reads the Office of the General Counsel's reparations-appeals register — the layer above the
dispositions court: parties-first captions ("Eric Thompson, … v. …"), ≈87 decisions over 9 pages
(0..8), date-descending 2012→2025. Three live laws baked in: the register anchors DUAL-ERA PDF
paths (recent `/sites/default/files/YYYY/MM/` plus the legacy
`/idc/groups/public/%40lropinionsandadjudicaryorders/documents/legalpleading/` kept verbatim —
%40 is the encoded @ and "adjudicary" is the upstream's own misspelling, never normalized);
multi-docket rows caption the plural "CFTC Docket Nos. 20-R007; …; and 20-R025" — the whole
semicolon list captured as one `docket_no` string; and legacy-era docket captions scatter across
tolerance shapes (the "CFTC " prefix dropped, non-R numbering "11-E-01", NFA arbitration pairs
"CRAA 12-03"), while the two 2012 rows with no caption at all report None honestly. Same host
browser-suite gate as the other three views; TTL 24h; rate-limits v1.53 (168 providers / 247
faces); pinned by `tests/test_flat_0365.py`.

**0.3.64 — Batch E6, the negative-list batch: UK NMW naming-scheme pair + US CFTC RED List & reparation decisions (+4 faces born flat, 242→246; 167→168 providers; legal 82→86 — GB/US deepened only, zero new jurisdictions).**

Two keyless providers, live-probed 2026-11-16. `gb_nmw_rounds`/`gb_nmw_round` read the
government's "named and shamed" underpayment register: the discovery face pins the gov.uk
search API to the scheme's own query (41 releases, Round 22 newest), and the dossier face
fetches the press-release HTML because the content API answers an EMPTY body for these pages
(attachments live only in the HTML) — the named-employers xlsx coordinates come out per round,
with the no-year-suffix law (hand-assembling `…_16_October_2025.xlsx` 404s; the real file has
no year). On the US side `us_cftc_redlist`/`us_cftc_dispositions` extend the CFTC provider in
place: the RED List's 284 unregistered foreign entities are ALPHABETICAL with dates scattered
(widening `items_per_page` answers zero rows — the views setting is decorative), and the
reparation decisions anchor IS the decision PDF with the docket riding the blurb cell.
Re-probes the same day: uk_ico's Cloudflare managed challenge now covers the main-site sitemap
(was keyless 2026-10-30) and us_fcc still answers the 387B Access-Denied stub — both stay
deferred. Polite tiers: gb_nmw 1 rps / us_cftc stays 0.5 rps (the two new ops ride the
provider's existing tier); rate-limits ledger
v1.52 (168 providers / 246 faces); compliance booklet v2.6 (🔴16/🟡23/🟢92/⚪37); pinned by
tests/test_flat_0364.py.

**0.3.63 — Batch E5 depth wave: JP JFTC decision pair + IN CCI register pair + AU ACCC actions feed (+5 faces born flat, 237→242; 164→167 providers; legal 77→82 — AU/IN/JP deepened only, zero new jurisdictions; Japan's first legal faces).**

Three keyless providers, live-probed 2026-11-16. `jp_jftc_decisions`/`jp_jftc_decision`
read the JFTC decision database behind a UA gate and the CSRF token/cookie pair dance
(token scraped per session, both must ride together); the era tables (R/H/S → 2019-… mapping)
and full-width event numbers are kept verbatim, and `case_id` is the hard key across the
pair. The CCI registers pair (`in_cci_antitrust_orders`/`in_cci_combinations`) rides the
DataTables POST channel — the GET twin answers 405 (the pair trap) — and tokens MISALIGN
across the two registers, so column offsets never transfer; the XYZ placeholder party names
ship verbatim (upstream's own masking), and combination rows keep their raw HTML soup
byte-exact. `au_accc_actions` rides the lazy-views two-hop (GET /views/ajax with
view_path=/node/162342, `f[]` array form, bare JSON command envelope, 0-based page): the
rows window is WAF-gated — ~50 rapid calls close it (even an exact replay answers the 64KB
shell) and it self-heals after ~25 minutes; the RSS feed was rejected (no topic/type
filters).

**0.3.62 — Batch E4 depth wave: NL ACM publications pair + ES CNMV sanctions + KR FSS sanctions (+4 faces born flat, 233→237; 161→164 providers; legal 73→77 — NL/ES/KR deepened only, zero new jurisdictions).**

Three keyless providers, live-probed 2026-11-16. `nl_acm_publications`/`nl_acm_publication`
read the Dutch competition authority's decision archive through the channel that actually
scales: the list page's JS window does not widen (measured), so the SITEMAP is the channel —
one list call sweeps the 9-page sitemap index plus all submaps, 13,401 URLs back to 2003; the
category taxonomy is a slug-substring heuristic (word-boundary matching false-negatives
compounds: kartelafspraken counts as kartel), and the detail page's Parties block rides a
nested second `<h3>` inside the case content block. `es_cnmv_sanctions` serves the Spanish
securities regulator's sanction register behind a Referer contract, and its five-year window
SLIDES (19 pages pinned 2026-10-19 → 18 on 2026-11-16) — the tail page is always discovered
from page-0 links, never hardcoded, and `boe_ref` rows join the ES BOE gazette face; it rides a
second provider id beside the 0.3.44 company face (the wb/wb_proc precedent). `kr_fss_sanctions`
is the tree's first POST × bytes combination (urlencoded excelDown POST → 270 KB xlsx, 5,804
rows) with the header-misalignment law: cells are LETTER-keyed in the sheet XML, never
order-keyed — and 1,245 rows carry their substance in a PDF attachment, answering honest nulls,
not fabricated values.

**0.3.61 — Batch E3: FR administrative-courts judgment archives + US OCC enforcement database (+3 faces born flat, 230→233; 159→161 providers; legal 70→73 — FR/US deepened only, zero new jurisdictions).**

Two keyless providers, live-probed 2026-11-16. `fr_court_judgments`/`fr_court_judgment` read the
administrative-courts portal's MONTHLY zip archives at fixed directory paths (/DCE/{yyyy}/{mm}
for Conseil d'État, /DCA/ for appeal courts) — a dead-looking dataset page is not a dead source:
the archive zips stay live while the data.gouv dataset page lags years behind. The zip rides the
bytes channel (an Accept wall that only takes `*/*`) and unrolls one namespace-free XML per
judgment via stdlib zipfile; the 2026-10 measured census was CE 791 / CAA 2,340. The CAA
archives carry NO ECLI element (measured 0/24) — `ecli` answers None on CAA rows and the
single-judgment face keys on the archive file stem, where a CE ECLI maps onto the same stem. A
month with no zip answers upstream_unavailable, never a fabricated empty. `us_occ_ea_search` is
the OCC's EASearch structured database — the 0.3.28 enforcement news face's twin under a second
provider id (that face name was taken; the new face takes the upstream portal name). The FULL
history 1989→2026 (~6,072 actions) answers UNFILTERED in one 1.2 MB shot, so the face refuses
filter-less calls locally (bulk stays bulk); rows carry CharterNumber (the bank-register join
key) and AA-ENF-YYYY-NN dockets — the same docket key the 0.3.28 face parses out of prose.

**0.3.60 — Batch E2 rulings/registers cluster: AU FRL legislation titles + BR CADE cases + CA CBSA advance-rulings pair + DE Bundestag lobby register + DK FSA supervision archive + IT AGCM trio + PL UOKiK decisions pair + US CBP CROSS rulings pair + BR BNDES financing (+14 faces born flat, 216→230; legal 57→70, company 69→70; nine keyless providers).**

The sixth deepen-only batch: the legal domain gains its first AU, DE, DK and PL faces — AU and
DE pre-exist the ledger through other domains, but **DK and PL are new to the ledger (33→35;
the batch's own registry line claimed "zero new countries (33 held)" and was measured wrong —
corrected here by the 0.3.62 audit)**. Highlights: the AU OData channel forbids percent-encoding
the $-prefixed option names (%24top → 400); BR CADE answers every scalar base64-wrapped in
mixed UTF-8/cp1252 and a no-match is an EMPTY answer, not a failure; CA CBSA rulings require
`lang=en` (absent = 400) and answer the whole 1,234-ruling register in one shot; the DE lobby
register takes the 18 MB keyless JSON export (the official REST is ApiKey-gated → off route
under the keyless-only ruling); DK FSA requires a Referer header and a nested-object userInput;
IT AGCM sits behind an IP-bound Cloudflare gate and refuses multi-word search tokens locally;
US CBP CROSS details key on string ruling ids.

**0.3.59 — Batch E1 enforcement/party-finance first slice (+8 legal faces born flat, 207→216; legal 49→57 — FR AMF sanctions/transactions pair, EU CJEU case-law search, LV KNAB party-finance pair, CH EFK party financings + FINMA enforcement news, IN India Code search; Latvia new to the ledger, 32→33).**

Eight keyless faces across six providers, live-probed 2026-11-13. `eu_cijeu_search` reads the
EU Court of Justice's Curia search; the FR AMF pair rides the sanction Commission's portal; LV
KNAB carries Latvia into the ledger with the party-annual-report pair; CH EFK reads party
financings and FINMA's enforcement-news feed; IN India Code opens the statute text line. All
polite-tier keyless with no published quotas — walls are channel walls, not rate lines.

**0.3.58 — Batch D same-stack widening: FDIC BankFind sibling quartet + FR INPI accounting-ratio pair + CA ASC enforcement + BCSC disciplined + BR CNES facilities (+9 faces born flat, 198→207; company 62→68, legal 47→49, healthcare 33→34 — healthcare's first BR face; `ca_amf` deferred at the verify gate, CF-403 on non-browser clients).**

Same-stack widening of existing deepeners: the FDIC quartet rides the BankFind suite's sibling
endpoints (failures / financials / history / locations), the INPI pair brings FR company
accounting ratios (one of the hardest-to-reach French datasets, now keyless), and BR CNES opens
healthcare's BR axis. The urlencoded channel gains doseq list→repeated-key encoding (inert to
every existing scalar op).

**0.3.57 — Batch C major-power axis II: ES BOE daily gazette table of contents + ES OEPM IP gazette index + TR KAP member/disclosure pair (194→198 faces, 136→139 providers; company 59→62, legal 46→47 — jurisdiction count unchanged at 31, existing countries deepened only).**

Three keyless providers, live-probed 2026-11-12 (tmp/probe-sdk-0357/). `es_boe_sumario` reads
one publication day's full BOE table of contents (www.boe.es/datosabiertos — the JSON channel
rides content negotiation, which the SDK's default Accept header already sends; the same
www.boe.es host bucket is shared with es_borme across domains): every container level arrives
dict-OR-list (singleton-collapse) and items nest in four measured shapes, all collected with a
seccion/departamento/epigrafe breadcrumb plus a depth-blind census that reconciles against the
parsed rows — a drifted shape surfaces as a warning, not vanishing rows. No-publication days
answer 404 XML and surface as published=false; the archive reaches back to the 1960s.
`es_oepm_bopi` is the industrial-property gazette issue index (sede.oepm.gob.es/apibopiweb):
the no-issue negative is a 200 with a ZERO-BYTE body (weekend AND pre-1995 both measured) —
carried as "" through the accept:'text' channel and structured as published=false; the UCM
artifact keys are the real keys (id/fechaPublicacion arrive null upstream by design). The
`tr_kap_members`/`tr_kap_disclosures` pair covers the Turkish public disclosure platform
(www.kap.org.tr — the gate measured open all four ways, bare client shipped): the member
register carries the TR company triple taxNo+tradeRegNo+tradeRegOffice with the W-state fake
placeholder row filtered and counted, and the disclosure stream caps at EXACTLY 2,000 rows
per window with no total echo — likely_truncated flags it and the window is walled at 31 days
locally. tr_ekap deferred at the verify gate (the human-verification gate came ON).

**0.3.56 — Batch B major-power axis I: DE register search + JP IP trio + KR patents + JP NAVII facilities + KR statutes/precedents (186→194 faces, 131→136 providers; company 54→59, legal 44→46, healthcare 32→33 — jurisdiction count unchanged at 31, this batch deepens existing countries only).**

Five keyless providers, live-probed 2026-11-12 (tmp/probe-sdk-0356/). `de_register_search`
queries the German Unternehmensregister through a three-hop token chain (POST landing mints
a 231-char token cached 45min → GET /de/suche with RSC:1 + Accept: text/x-component → a
React server-component stream parsed by a string-aware brace matcher; the companyDto row's
`euid` (DED2601V.HRB252581 — state + court + register type + number) is the strong join key,
a bare HRB number needs its court code; searchTerm "exact" is a phrase match; the search hop
is never cached). `jp_trademark_search` / `jp_patent_search` / `jp_design_search` break
J-PlatPat with the client-side hash gate — the SPA serves no cookies, the client mints
U/L/D/S/T itself and signs Z = sha256 over the ECRL bit scheme (ECRL=105 = 0b1101001 → bits
1,3,6 ride: sha256(U + "ja" + ECKY), bit4 D does NOT); one cached ECRL/ECKY pair boots all
three faces; the year slice (FILTER_INFO ITEM/COND/COMPAR_COND_SIGN) is the enumeration key
and the SIGN is mandatory (a bare COND is silently ignored — measured); 3,000-row per-call
cap with no paging keys; AUTO_NARROW_FLG=1 gives free counting via the pre-narrow total;
the patent face sends no OTID (a null is stripped by the transport and ≡ key absent,
A/B-verified back-to-back 2026-11-12); RSLT_CD=8 is the captcha gate — raise, never retry
through it. `kr_kipris_patents` reads KIPRIS (form-urlencoded GET; AN+APC row keys, TL keeps
the <!HS>/<!HE> highlight anchors verbatim, "98" = zero hits, page cap 255 / page-size cap
2000). `jp_navii_facilities` walks the MHLW NAVII statutory facility directory through a
three-hop session chain (initialize mints the AWSALB/SESSION jar cached 20min → iryoSearch
with the ajax headers returns the session-bound 検索ID, never cached → S2400 with 0-BASED
pages of true 20-row pagination; keyword_type 3=診療科目 enumerates 内科 59,281 live;
pharmacy=True rides initializeYakk/yakkyokuSearch onto the same S2400 page, kikanKbn=5;
~105k 医療機関 + ~61k 薬局). `kr_law_statutes` / `kr_law_precedents` read law.go.kr
(keyless urlencoded POST; the HTML fragment IS the payload — accept:"text", the
nl_rechtspraak precedent; statutes ride the lawNm form family with the efYd 99990101
pending sentinel, live fragments echo NO total and none is fabricated; precedents carry
the [대법원 date 선고 caseNo 판결] metadata on javascript: anchors). Rate tiers:
de_register/jp_navii 0.3 rps, jp_jplatpat/kr_kipris/kr_law 0.25 rps (the 4s cadence is the
captcha discipline); rate-limits v1.44 (136 providers / 194 faces); offline pins
tests/test_flat_0356.py (39 cases — it caught four real bugs: the missing accept:"text" on
kr_law ops, the missing cache-payload unwrap in jp_navii._session, the missing no_cache
parameter on the jp IP face helpers, and the DE reason/evidence reading the wrong
registerNumber key). Verified: full offline suite + one live shot per face (2026-11-12).

**0.3.55 — MX legal pair + NL Rechtspraak + MX SGM mining cadastre (182→186 faces, 131 providers; legal 41→44, esg 7→8 — the SDK's first NL legal and first MX legal/esg jurisdictions, 30→32).**
Four keyless providers, live-probed 2026-11-12. `mx_cnv_sanctions` reads the
CNBV financial-sanctions register through Azure APIM — keyless by publication
(the subscription key ships hardcoded in the public React bundle, the AU ACMA
family; the OpenAI key leaked in the same bundle is someone else's credential
and is deliberately not carried). The pagination lives in the RESPONSE
headers — the body is a bare row list and x-total-items/x-total-pages carry the
totals, which is why transport extension 11 (resp_headers) exists; the entire
paging state rides request headers (X-Page-Number 0-based, X-Page-Size,
X-Order-Field/X-Order-Type — imposedOn verified both directions), so the op is
never cached by design: the URL is identical for every page and a cache replay
carries no headers (totals answer None, never fabricated). 11,593 rows live.
Coverage since the 2014 Lineamientos INCLUDES the non-regulated AML faces
(centros cambiarios / transmisores de dinero / SOFOMES E.N.R.) that no other
MX register carries; obligatedSubject is the company join key. `mx_sabg_sanctioned_servants`
rides the CKAN datastore bypass (the direct CSV is Akamai-403 on every stack;
the datastore inlines the whole 435-row in-force register as JSON): the 13
statutory columns verbatim with inicio→fin the live barring window; q is
full-text (Abuso → 78), filters JSON exact-match (LFRASP → 364). `nl_rechtspraak_search`
is a strict-shape POST (~479k published cases, the register reaches 1847):
every PascalCase body key must ride and Field must stay zt0 or the upstream
answers 200 with an Angular error page instead of JSON; TitelEmphasis IS the
ECLI, CorrelationId is the deterministic md5 digest of the request itself so
the cache key stays stable, and pdf_url is derived per row without fetching.
`mx_sgm_concesiones` reads the SGM mining-concession cadastre (ArcGIS
FeatureServer layer 49, 19,840 concessions): ctithomolo the holder-company
join key, an at-least-one-filter wall (a bare scan is batch-pipeline
territory), and inicio_de_ an Excel-base epoch-ms whose NEGATIVE values are
legal (titulo 76659 → 1829-12-28).

**0.3.54 — transportation domain chartered (ninth domain, 180→182 faces, 127 providers) — seven faces migrated prefix-only + Canada TC CCAR pair new.**
Per the 0.3.54 ruling the transport-compliance faces move out of esg/company in
one cut: `euasl_datasets`, the four `paris_mou_*` faces and
`thetis_mrv_datasets` leave esg (13→7 — esg is environment + social again),
`us_fmcsa_carriers` leaves company (55→54 — a USDOT number is a carrier-census
key). Names, parameters and jurisdictions are unchanged; only the command
prefix moves to `agentdata transportation …`, and a wrong-domain call raises
usage_error naming the right domain (the guard fires at call time). Two new
faces: `ca_ccar_search` reads Transport Canada's Civil Aircraft Register
(CCARCS-RIACC — the POST form's 302 lands on a stateless bare GET
`RchSimpRes.aspx`, a five-slot contains pipeline (cn/mn/sn/on/m) wrapped with
print=y answering one full page: AIR CANADA 269 rows / 365KB live; contains is
case-sensitive against the register's stored form, pinned live 2026-11-11 —
owner="Air Canada" answers 0 rows, owner="AIR CANADA" answers 269; total_matched
is the honest upstream total and limit 1-500 is a local cap; at least one slot
is required locally; adet_id is the join key into the aircraft face).
`ca_ccar_aircraft` reads the single-aircraft dossier (ADet.aspx?id=) — four
blocks (aircraft / manufacturer / registration / registered owner) flattened
into one dict; unmapped labels land snake_case in extra_fields rather than
being dropped (mail_recipient proven); the ~500k id space has holes — a
not-found is a legal empty, and ids come from search rows, never guessed;
natural-person owner names and addresses are recorded verbatim (us_fmcsa
company_officer_1/2 public-register precedent; the raw harvest line strips
contact details — domain red line). Both keyless, no gate and no WAF (probe
tmp/probe-ca-ccar/ 2026-11-10); ca_ccar at 0.5/2; rate-limits v1.42 (127
providers / 182 faces) + compliance register v1.6 (canada.ca GC umbrella terms
🟡: non-commercial reuse is free, commercial redistribution needs prior written
permission); command-naming rows 181-182; offline pins
test_flat_transportation.py. Verified: full offline suite plus one live call
per new face (2026-11-11).

**0.3.53 — FR Regafi pair + UK FHRS + US NPPES (+4 faces, 176→180; company 53→55, esg 12→13, healthcare 31→32).**
Four keyless providers, probes pinned 2026-11-10 under tmp/probe-sdk0352/.
`fr_regafi_entities` / `fr_regafi_authorisations` read the ACPR's official
financial-sector register (regafi.fr — the React shell's real backend is the
Opendatasoft Explore API v2.1): a 25,890-row supervised-entity roster (SIREN +
LEI dual hard keys, the parent edge rides every row, nom_commerciaux carries
renaming history as JSON) and its 31,107-row per-authorisation timeline
(date_debut runs 1946→today; the ~40 *_json columns carry per-service
authorisation blocks with their own effective dates — ODS serialises them
sometimes as strings, sometimes pre-parsed, and the face normalises in place).
`uk_fhrs_establishments` searches the FSA Food Hygiene Rating Scheme live
(~615,098 establishments; the x-api-version: 2 header is the only gate;
postcode is 403-walled as a query param on this endpoint — the PostCode field
rides every row instead). `us_npi_organizations` reads the NPPES registry
pinned to NPI-2 organizational records: org-name search is exact-phrase
("Mayo" answers zero, "Mayo Clinic" answers 2), limit>200 is silently clamped
upstream (measured: 250 → result_count 200) so 1-200 is a local wall, and
NPI-1 rows still mix in under enumerationType=Organizational — filtered
client-side with the result_count/count pair shipped honestly.

**0.3.52 — discovery surface machinery batch (0 new faces, 176 unchanged).**
`agentdata capabilities` renders the complete face table — every realtime face
with its one-line summary, jurisdiction, execution plane, key requirement, and
per-parameter closed sets — straight from the argparse command tree, so it
cannot drift and ships with every release for free (`--format json|md`,
`--domain-filter`, `--face`; runs offline, no PAT). Three CLI repairs ride
along: 32 faces in economy/research/security regained their `help=` catalog
lines (their domain `--help` used to list nothing), the verb layer takes
`metavar=FACE` (the legal usage line no longer spells 38 face names), and
`allow_abbrev=False` now covers the whole tree (a mistyped `--api-k` used to
silently become `--api-key`). Cache keys are pinned to the provider's base URL
(`cache_key_for(scope=...)`): a provider id repointed at another upstream —
Comext's dedicated root vs plain Eurostat — can no longer answer from the old
host's cache entry. Offline pins: test_capabilities.py (20 tests); full suite
1497 passed. The server-side capability document is a P2 byproduct — three
clauses recorded in docs/domains/api.md §9.7.

**0.3.51 — legal enforcement tier-two trio + company FMCSA carrier census (+4 faces, 172→176; legal 38→41, company 52→53).**
The SDK's first IT jurisdiction (29→30; FR enters the legal domain for the
first time — fr_recherche lives in company); four keyless providers
(fr_adlc / it_arera / us_cftc / us_fmcsa), probes pinned 2026-11-09 under
tmp/probe-sdk0350/l5/. `fr_adlc_sanctions` reads the French competition
authority's company-fine ledger through its official data.gouv.fr mirror
(the authority's own domain egress-blocks this exit) via a two-hop chain:
the datasets API resolves the latest CSV resource, whose build-stamped URL
rolls on every update (dataset TTL 1h + CSV TTL 24h; transport extension 10
absolute-URL fetch). 1,208 rows × 5 columns; amounts arrive as decimal
strings and cast to float locally; case total ≠ sum of individuel rows —
both figures are upstream-published and shipped verbatim, never reconciled
(26-D-05: rows sum 15,260,000 vs the register's own 12,670,000; 15-D-19
ships €672,332,000 case-level). `it_arera_decisions` reads the Italian ARERA
regulated-sector decision library on bare TYPO3 — no gate, no WAF, 15,599
decisions back to 1996 with the count living in the pager; tipologia is a
nine-word exact-match closed set, and the PDF path is never assembled from
the sigla (fileadmin naming drifts by era — the face ships the detail
anchor). `us_cftc_enforcement` reads the CFTC enforcement-actions Drupal
views table — the one live surface (solr sits behind Cloudflare,
publicreporting is a resold domain, data.cftc.gov resets) — with a UA gate
that drifted the same day (bare UA passed in the morning probe, 403'd in the
afternoon one; the ext-8 browser suite is permanent). Pages are the epochs:
?page=0..260 ends at the register's 1995 floor (~2,610 actions), 1998 is
absent from the register's own year filter and the wall records it as-is.
`us_fmcsa_carriers` reads the FMCSA Company Census File (data.transportation.gov
`az4n-8mr2`, the tx_tdlr SoQL-verbatim contract): 4,528,322 rows of FULL
history ($select=count(*) — the ~400k audit figure was the active face, an
order of magnitude off); Socrata omits null fields per row (53 keys on a
populated row vs ~58 catalog columns); dot_number is the CSA/SMS join key
and dun_bradstreet_no is the rare official DUNS cross-key ("0" sentinels
kept verbatim, suppressed from evidence quotes); sibling set 4a2k-zf79 is a
403 dead single-dataset — az4n is the live set. fr_adlc/it_arera/us_cftc at
0.5/2, us_fmcsa at 1/2; rate-limits v1.40 (123 providers / 176 faces);
offline pins test_flat_legal_0351.py + test_flat_company_us_fmcsa.py.
**0.3.50 — legal enforcement/party-assets realtime sextet (+6 faces, 166→172; legal 32→38).**
The SDK's first EE and UA jurisdictions (27→29); four keyless providers
(us_ferc / ie_sipo / ee_erjk / ua_nazk), probes pinned 2026-11-09 under
tmp/probe-sdk0350/. `us_ferc_elibrary` is a POST AdvancedSearch behind a
Cloudflare UA-fingerprint gate (polite agentdata UA = 403; the browser-suite
header set passes) — totalHits 4,722,924 back to 1980, resultsPerPage ceiling
1000 verified, and the upstream's own triple-s `acesssionNumber` spelling is
recorded verbatim as the official key (TTL 12h). `ie_sipo_lobbying` takes 13
mandatory params where an explicit empty string is required (one missing =
404), dates are DD-MM-YYYY (ISO = 500), Total = 123,591, and
`Lobbyist.CompanyRegistrationNumber` is the CRO join key. The ERJK pair rides
the erjk.ee `/et/` prefix wall (bare `/api` is a 301): the quarterly-receipts
matrix (455 rows) plus the party register (18) and person-keyed report bodies
(reg_code = the RIK key). The NAZK pair is all-POST on politdata
(GET = 404) with a server-side pageSize clamp (10→20 — the local default is
20 and never pretends otherwise) and `public_summary` embedded per report.
All four at the 0.5/2 polite tier; rate-limits v1.39 (119 providers /
172 faces); offline pin test_flat_legal_0350.py.
**0.3.49 — company US city-license Socrata trio (+3 faces, 163→166; company 49→52).**
`chi_bacp_licenses` reads the Chicago business-licensing register
(data.cityofchicago.org `r5kz-chrr`: 1,210,956 rows, full history back to
1997), `lacity_registrations` reads the LA City register (data.lacity.org
`6rrh-rzua`: 632,799 rows), and `nyc_dcwp_licenses` reads the NYC DCWP
consumer-affairs license book (data.cityofnewyork.us `w7w3-xahh`: 72,452
rows). All three are SoQL verbatim channels — the `co_rues` contract — and
the state-axis ruling of 0.3.48 extends to the city axis: faces are named on
the host/locality stem, and `lacity` is deliberately not `la_` (LA is
ISO-3166 Laos; SDK prefixes are country codes). Chicago refreshes daily via
payment_date (TTL 24h); NYC's book lags ~2.5 months (TTL 7d); the LA table
is a registration book, not a license book. Socrata system columns
(`:@computed_region_*`) pass through verbatim — and drift per row on the LA
host (5↔6), while the NYC host ships none.
**0.3.48 — company US state-license Socrata twin (+2 faces, 161→163; company 47→49).**
`tx_tdlr_licenses` reads the Texas TDLR all-licenses register (data.texas.gov
`7358-krk7`: 966,778 rows × 26 view columns — 18 real + 8 Socrata
`:@computed_region_*` system columns) and `wa_doh_credentials` reads the
Washington DOH health-care credential register (data.wa.gov `qxh8-f4bd`:
2,468,860 rows, refreshed daily — the count moved +1 past the research probe
the same day). Both are SoQL verbatim channels (raw `$where`, `$limit`
1-500, `$order` without NULLS, no total echo and none faked) — the `co_rues`
contract — and the SDK's first US sub-national state-axis faces, named on
state-code prefixes. Socrata omits null fields per row, so a bare individual
row ships 9 keys while an establishment row carries the whole
business-address family — the individual-vs-establishment duality lives in
the data, not the schema. The WA birthyear column is stripped from every row
(the PII red line: birth year + full name is exactly the combination the
house rules rule out — names stay, birth years do not).
**0.3.47 — legal AT RIS OGD pair (+2 faces, 159→161; legal 30→32).**
`at_ris_judgments` / `at_ris_statutes` read the Austrian federal legal
information system's open-data API (data.bka.gv.at, OGD API v2.6) — the
SDK's first AT jurisdiction: sixteen Judikatur shards (1,008,601 documents;
Vwgh alone 357,857 and drifting daily) plus the consolidated Bundesrecht
(442,058 documents). The gate is a parameter wall, not a rate line:
`Applikation` is case-sensitive (VWGH is answered by an HTTP 200 whose error
body self-exposes the schema dictionary, and the boolean-flag form is
silently ignored and quietly answers the Justiz shard — the deadliest of the
three postures, so an exact-case 16-value closed set sits before the wire),
page size is an upstream constant (20), and beyond the last page the
upstream answers HTTP 500 rather than an empty page.

- The **code** in this repository is licensed under the license in
  [LICENSE](https://github.com/dicaria/agentdata/blob/main/LICENSE).
- The **data** returned by the SDK is governed by the terms of each upstream
  source; the SDK grants no data rights. See
  [TERMS.md](https://github.com/dicaria/agentdata/blob/main/TERMS.md).

## Contact

- Questions, bug reports, and data-coverage requests:
  [GitHub issues](https://github.com/dicaria/agentdata/issues) or
  **contact@dicaria.com** (see
  [CONTRIBUTING.md](https://github.com/dicaria/agentdata/blob/main/CONTRIBUTING.md))
- Hosted-corpus credentials: self-serve — sign up at <https://dicaria.com/console> and
  create an API key; service inquiries: **contact@dicaria.com**
- Security reports: **contact@dicaria.com** — please don't open a public
  issue; see [SECURITY.md](https://github.com/dicaria/agentdata/blob/main/SECURITY.md)
- Conduct issues: **contact@dicaria.com** (see
  [CODE_OF_CONDUCT.md](https://github.com/dicaria/agentdata/blob/main/CODE_OF_CONDUCT.md))
