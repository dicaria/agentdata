# agentdata

[![PyPI](https://img.shields.io/pypi/v/agentdata)](https://pypi.org/project/agentdata/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/dicaria/agentdata/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Commands](https://img.shields.io/badge/182_commands-9_domains-teal)](https://github.com/dicaria/agentdata/blob/main/docs/domains/api.md)

**One Python client and CLI over 182 public datasets — company registries,
sanctions lists, procurement awards, drug approvals — with no API keys and no
accounts.**

Government data holds the decisive facts about companies, but it is scattered
across 112 public APIs, each with its own pagination, rate
limits, and undocumented quirks. **agentdata puts 182 of those datasets behind
one interface**: a pure-standard-library client and CLI across 30 jurisdictions. Every upstream gotcha we hit live is already pinned — politeness
and caching are built in.

## Install

```bash
python -m pip install agentdata
```

For a reproducible install, pin the release: `python -m pip install agentdata==0.3.54`.

Prefer not to touch PyPI? Install straight from a release tarball:

```bash
python -m pip install https://github.com/dicaria/agentdata/archive/refs/tags/v0.3.54.tar.gz
```

Or via git (pin a tag for reproducible installs):

```bash
python -m pip install git+https://github.com/dicaria/agentdata.git@v0.3.54
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
agentdata transportation ca_ccar_search --owner "AIR CANADA" --limit 3
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
- **One envelope across all 182 commands.** Query echo, `reason`, `evidence`,
  source metadata, `jurisdiction` — your code parses one shape.
- **Upstream parameter names, verbatim.** What the official API docs call a
  parameter is what the SDK takes — no invented vocabulary to unlearn.
- **Polite by default.** Per-source rate limits are enforced before every
  request ([rate-limits ledger](https://github.com/dicaria/agentdata/blob/main/docs/domains/rate-limits.md)),
  and a cache hit costs no rate budget.
- **Zero dependencies.** Python 3.10+ standard library only.

## Coverage

**182 datasets · 127 upstream providers · 30 jurisdictions:** US 50 · global 40 · EU 15 · UK 13 · Canada 8 · Brazil 7 · France 4 · Türkiye 4 · Colombia 3 · ES 3 · India 3 · AT 2 · Australia 2 · Switzerland 2 · Czechia 2 · DE 2 · EE 2 · Guernsey 2 · Ireland 2 · Norway 2 · New Zealand 2 · RU 2 · SG 2 · UA 2 · Finland 1 · IT 1 · Jersey 1 · JP 1 · Korea 1 · Kazakhstan 1.

| Domain | Commands | Sources |
|---|---|---|
| `healthcare` | 32 | US FDA approvals & recalls, ClinicalTrials.gov, RxNav, DailyMed, AccessGUDID, UK MHRA alerts, Health Canada DPD & MDALL, EUDAMED, RASFF & Safety Gate (EU), TGA (AU), Europe PMC, MeSH |
| `legal` | 41 | US consolidated screening list, eCFR, Federal Register, LDA filings, CourtListener, DG COMP, UK CMA cases, UK Electoral Commission, The Gazette, Irish Revenue defaulters, US OCC enforcement, TNA case law, SIPRI, SIC sanctions (CO), MDB debarment rosters (WB/AfDB/IDB), Canada SEMA, CFPB consumer complaints, SEBI enforcement orders (IN), SPK administrative fines & trading bans (TR), CBR illegal-finance warning register (RU), BACEN special regimes & complaint rankings (BR), RIS case law & consolidated federal law (AT) |
| `company` | 54 | GLEIF, SEC EDGAR, FDIC, USAspending, TED, VIES, UK Contracts Finder & FTS, Zefix (CH), Brreg (NO), YTJ (FI), recherche-entreprises (FR), RUES (CO), Hometax (KR), ROR, NZ Companies Office, ARES (CZ), GFSC (GG), JFSC (JE), GBD_UL (KZ), SEBI intermediaries (IN), SPK public-company register (TR), BDDK licensed institutions (TR), CBR credit institutions (RU), BACEN institutions, branches, verified domains & open-finance API directory (BR), federal insolvency announcements (DE), FSA licensed-institution registers (JP), CCAA restructuring roster (CA), CNMV supervised entities & BORME gazette (ES), data.gov.sg platform (SG), TDLR licenses (TX) & DOH credentials (WA), Chicago BACP business licenses, LA City business register, NYC DCWP licenses |
| `economy` | 18 | World Bank WDI, Eurostat, ECB reference rates, FRED, WHO xMart, UN Comtrade, ILOSTAT, BLS, BIS, IMF, OECD, Comext |
| `esg` | 7 | Climate TRACE, EITI, EU ETS (EUTL), THETIS-MRV (EU shipping), EPA FRS, Paris MoU, EU Air Safety List |
| `research` | 10 | OpenAlex, NIH RePORTER, NSF, Crossref, UKRI GtR, iCite, bioRxiv, OpenCitations |
| `procurement` | 7 | PNCP (BR), SECOP II (CO), UNGM, World Bank, New York Authorities / MTA / OGS (US) |
| `security` | 4 | OSV, CISA KEV, ENISA EUVD |

## Full command index

Ten entry points — `agentdata` plus one command per domain — and 182 dataset
commands under them: one command per upstream dataset, parameters kept under
their upstream names. The block below is the complete index, grouped by domain
in the same order as the Chinese [README.md](README.md). Every line is a
runnable command.

Above them sit two meta-commands that are not dataset faces:
`agentdata capabilities` (discovery, since 0.3.52 — renders the full face table
from the command tree: `--format json|md`, `--domain-filter`, `--face`; no key,
works offline) and the `agentdata hub` family (PAT → short-lived subject JWT,
see above).

```bash
agentdata capabilities --format md
# healthcare (32)
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
agentdata healthcare ca_dpd_companies --limit 5
agentdata healthcare ca_dpd_drug_products --status 3 --limit 5
agentdata healthcare ca_mdall_companies --limit 5
agentdata healthcare ca_mdall_licence --licence-id 111577
agentdata healthcare rasff_notifications --subject aflatoxin --items-per-page 5
agentdata healthcare safety_gate_alerts --year 2026 --limit 5
agentdata healthcare safety_gate_report --report-id 10000329 --limit 5
agentdata healthcare us_npi_organizations --organization-name "Mayo Clinic" --state MN --limit 3

# company (54)
agentdata company gleif_lei_records --lei 5493001KJTIIGC8Y1R12
agentdata company gleif_lei_records_search --filter-entity-legal-name Nestle --filter-entity-jurisdiction CH --page-size 5
agentdata company gleif_direct_parent --lei 5493001KJTIIGC8Y1R12
agentdata company gleif_ultimate_parent --lei 5493001KJTIIGC8Y1R12
agentdata company fdic_institutions --filters CERT:628
agentdata company sec_submissions --cik 320193
agentdata company ror_organizations --query EMBL
agentdata company vies_vat --vat DE811907980
agentdata company usaspending_spending_by_award --recipient-search-text "Lockheed Martin" --start-date 2024-01-01 --end-date 2024-12-31 --limit 3
agentdata company ted_notices_search --query 'organisation-name-buyer=Siemens* AND organisation-country-buyer=DEU' --limit 5
agentdata company gb_fts_release_packages --name nhs --updated-from 2026-10-01 --updated-to 2026-10-27 --limit 5
agentdata company gb_contracts_finder_published_notices --name council --published-from 2026-10-20 --published-to 2026-10-27 --limit 5
agentdata company sec_fulltext_search --q "artificial intelligence" --forms 8-K --limit 5
agentdata company ch_zefix_firm_search --name "Nestle" --max-entries 3
agentdata company ch_zefix_firm --ehraid 347554
agentdata company no_brreg_enheter --navn equinor --size 2
agentdata company no_brreg_roller --organisasjonsnummer 923609016
agentdata company nzco_companies --q "air new zealand" --limit 15
agentdata company nzco_directors --company-number 104799
agentdata company fi_ytj_companies --name nokia
agentdata company fr_recherche_search --q danone
agentdata company fr_recherche_search --q "552032534" --per-page 25 --etat-administratif A
agentdata company fr_regafi_entities --q Lille --limit 3
agentdata company fr_regafi_entities --siren 265907741
agentdata company fr_regafi_authorisations --id-referentiel 79 --limit 3
agentdata company co_rues_companies --where "razon_social like '%BANCOL%'" --limit 5
agentdata company kr_hometax_biz_status --biz-no 124-81-00998
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
agentdata company tr_bddk_institutions --category bankalar --limit 5
agentdata company tr_bddk_institutions --status exited --limit 5
agentdata company de_inso_search --state NW --date-from 2026-11-02 --date-to 2026-11-02 --limit 5
agentdata company de_inso_register_lookup --register-court "Düsseldorf" --register-type HRB --register-number 101036 --date-from 2026-11-02 --date-to 2026-11-02 --limit 5
agentdata company jp_fsa_licensed --category crypto_exchanges --limit 5
agentdata company jp_fsa_licensed --category trust_agents --name 北洋 --limit 5
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

# esg (7)
agentdata esg eiti_companies --name Equinor
agentdata esg eiti_payments --name Equinor
agentdata esg climatetrace_owners --name Gazprom
agentdata esg climatetrace_sources --owner-ids E100000001492 --year 2023 --limit 20
agentdata esg epa_frs_facilities --state-code DE --city-name MILTON --size 3
agentdata esg eutl_datasets
agentdata esg uk_fhrs_establishments --name "pret a manger" --address london --pagesize 3

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

# legal (38)
agentdata legal afdb_debarred_entities --name "CHINA RAILWAY" --limit 3
agentdata legal ca_sema_sanctions --country Syria --limit 3
agentdata legal co_sic_sanctions --limit 3 --order "fecha_emitida DESC"
agentdata legal csl_screening_list --name "VTB BANK" --limit 3
agentdata legal ecfr_search --q asbestos --limit 5
agentdata legal ecfr_titles
agentdata legal dgcomp_cases_search --name Google --instrument SA
agentdata legal idb_debarred_entities --q SHANDONG --limit 3
agentdata legal lda_filings --client-name "Google LLC" --limit 25
agentdata legal gb_ec_donations --query Sainsbury --limit 3
agentdata legal gb_ec_loans --query bank --limit 2
agentdata legal sipri_trades_search --supplier "United States" --type delivered --limit 3
agentdata legal federalregister_documents --q asbestos --startdt 2026-01-01 --enddt 2026-09-30 --limit 3
agentdata legal courtlistener_opinions_search --q asbestos
agentdata legal gb_cma_cases --q google --count 5
agentdata legal gb_cma_case --slug nexfibre-slash-substantial-merger-inquiry
agentdata legal gb_tna_caselaw_search --party Barclays --per-page 3
agentdata legal gb_tna_caselaw_judgment --document-uri ewhc/admin/2026/2298
agentdata legal wb_debarred_firms --name "CHINA RAILWAY" --country CN --limit 3
agentdata legal gb_gazette_notices --insolvency --text "acme" --page-size 5
agentdata legal ie_revenue_defaulters --part 1
agentdata legal us_occ_enforcements --year 2026 --month October
agentdata legal cfpb_complaints --search-term Discover --field company --size 3
agentdata legal cfpb_suggest_company --text Discover
agentdata legal in_sebi_orders --search Adani
agentdata legal tr_spk_fines --name "FERUDUN" --year 2025
agentdata legal tr_spk_bans --type company
agentdata legal ru_cbr_warning_list --violation pyramid --limit 5
agentdata legal ru_cbr_warning_list --site t.me --type internet_project --limit 5
agentdata legal br_bacen_regimes --cnpj 33171211
agentdata legal br_bacen_complaints --name ITAU --limit 5
agentdata legal br_bacen_complaints --tipo consortiums --name ADEMICON
agentdata legal at_ris_judgments --court Justiz --case-number "2 Ob 52/16k" --limit 3
agentdata legal at_ris_statutes --q GmbH --limit 3
agentdata legal ee_erjk_quarterly_reports --party-id 162 --limit 5
agentdata legal ee_erjk_election_reports --report-id 494641 --limit 10
agentdata legal ie_sipo_lobbying --query-text energy --limit 5
agentdata legal ua_nazk_parties --limit 5
agentdata legal ua_nazk_party_reports --party-id d0f1e224-e3de-45a2-8d12-43e4e9faee92 --limit 5
agentdata legal us_ferc_elibrary --docket CP17-101 --limit 5
agentdata legal fr_adlc_sanctions --id-decision 26-D-05 --limit 5
agentdata legal it_arera_decisions --anno 2022 --numero 312
agentdata legal us_cftc_enforcement --year 1995 --page 260

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

# procurement (7)
agentdata procurement br_pncp_contracts --data-inicial 20260901 --data-final 20260930 --pagina 1
agentdata procurement co_secop_contracts --where "upper(nombre_entidad) like '%MINISTERIO%'" --limit 5
agentdata procurement wb_procnotices --rows 5
agentdata procurement ny_abo_contracts --where "upper(vendor_name) like '%DELTA%'" --limit 5
agentdata procurement ny_mta_procurements --where "upper(vendor_name) like '%SKANSKA%'" --limit 5
agentdata procurement ungm_contract_awards --supplier DELTA
agentdata procurement ny_ogs_payments --where "upper(vendor) like '%HIGHLAND%'" --limit 5
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

The complete batch log — every release back to 0.1.0 — is kept in the Chinese
[README.md](README.md#版本). The five most recent batches:

**0.3.54 — transportation domain founding (+2 faces, 180→182; ninth domain — esg 13→7, company 55→54).**
Seven faces moved zero-rename into the new domain (euasl, thetis_mrv and the
Paris MoU quartet from esg; us_fmcsa_carriers from company) — same names,
parameters and jurisdictions, only the prefix becomes `agentdata
transportation …`; a wrong-domain call gets a usage_error naming the right
domain. New: the Transport Canada CCAR pair reads the Canadian civil aircraft
register (CCARCS-RIACC) keyless — the interactive POST form 302s to a
stateless bare GET (`RchSimpRes.aspx`: five pipe-wrapped contains slots +
`print=y`, which ships the whole result set in one page); contains matching is
case-sensitive as stored ("AIR CANADA" 269 rows vs "Air Canada" 0, ruled live
2026-11-11); the per-aircraft face flattens the four ADet blocks into one dict
with unmapped labels kept under `extra_fields`; the ~500k id space has holes —
a miss is a legal empty. Probe pinned 2026-11-10 under tmp/probe-ca-ccar/;
rate-limits v1.42. Acceptance: full offline suite + one live call per new face
(2026-11-11).

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
