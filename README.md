# agentdata

[![PyPI](https://img.shields.io/pypi/v/agentdata)](https://pypi.org/project/agentdata/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/dicaria/agentdata/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Commands](https://img.shields.io/badge/141_commands-8_domains-teal)](https://github.com/dicaria/agentdata/blob/main/docs/domains/api.md)

**One Python client and CLI over 141 public datasets — company registries,
sanctions lists, procurement awards, drug approvals — with no API keys and no
accounts.**

Government data holds the decisive facts about companies, but it is scattered
across nearly a hundred public APIs, each with its own pagination, rate
limits, and undocumented quirks. **agentdata puts 141 of those datasets behind
one interface**: a pure-standard-library client and CLI across 21
jurisdictions. Every upstream gotcha we hit live is already pinned — politeness
and caching are built in.

## Install

```bash
python -m pip install agentdata
```

For a reproducible install, pin the release: `python -m pip install agentdata==0.3.36`.

Prefer not to touch PyPI? Install straight from a release tarball:

```bash
python -m pip install https://github.com/dicaria/agentdata/archive/refs/tags/v0.3.36.tar.gz
```

Or via git (pin a tag for reproducible installs):

```bash
python -m pip install git+https://github.com/dicaria/agentdata.git@v0.3.36
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
| Is this company sanctioned? | `legal csl_screening_list` · `legal co_sic_sanctions` · `legal wb_debarred_firms` · `legal ca_sema_sanctions` |
| Do consumers complain about this company? | `legal cfpb_complaints` · `legal cfpb_suggest_company` |
| Who owns or controls it? | `company gleif_direct_parent` · `company no_brreg_roller` · `company fr_recherche_search` |
| Did it win public contracts? | `procurement br_pncp_contracts` · `procurement ungm_contract_awards` · `procurement wb_procnotices` |
| Is its drug or device approved — or recalled? | `healthcare fda_drug_approvals` · `healthcare gb_mhra_alerts` · `healthcare fda_drug_recalls` |
| What does this facility or fleet emit? | `esg climatetrace_sources` · `esg thetis_mrv_datasets` · `esg paris_mou_detentions` |
| Pull a company card from a national registry | `company ch_zefix_firm` · `company co_rues_companies` · `company kr_hometax_biz_status` · `company kz_gbd_ul_companies` · `company cz_ares_ekonomicke_subjekty` · `company in_sebi_intermediaries` |
| Has its broker been expelled, or its regulator fined it? | `legal in_sebi_orders` · `company in_sebi_default_brokers` |
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
c.legal.csl_screening_list(name="VTB BANK")                       # sanctions screening (US CSL)
c.research.openalex_works(search="vaccine", ror="01xdqrp08")
c.procurement.br_pncp_contracts(data_inicial="20260901", data_final="20260930", pagina=1)
c.security.osv_vulns(package="lodash", ecosystem="npm", version="4.17.15")
c.economy.wb_wdi_values(country="CHN", indicator="NY.GDP.MKTP.CD", date="2020:2023")  # World Bank indicator values
c.economy.ecb_fx_rates(currency="USD", start="2026-10-01", end="2026-10-31")  # euro reference rate (1 EUR = X)
```

The same commands from the shell — nine entry points, `agentdata` plus one
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
- **One envelope across all 141 commands.** Query echo, `reason`, `evidence`,
  source metadata, `jurisdiction` — your code parses one shape.
- **Upstream parameter names, verbatim.** What the official API docs call a
  parameter is what the SDK takes — no invented vocabulary to unlearn.
- **Polite by default.** Per-source rate limits are enforced before every
  request ([rate-limits ledger](https://github.com/dicaria/agentdata/blob/main/docs/domains/rate-limits.md)),
  and a cache hit costs no rate budget.
- **Zero dependencies.** Python 3.10+ standard library only.

## Coverage

**141 datasets · 97 upstream providers · 21 jurisdictions:** US 41 · global 40 · EU 15 · UK 12 · Canada 5 · Colombia 3 · India 3 · Türkiye 3 · Australia 2 · Switzerland 2 · Czechia 2 · Guernsey 2 · Norway 2 · New Zealand 2 · Brazil 1 · Finland 1 · France 1 · Ireland 1 · Jersey 1 · Korea 1 · Kazakhstan 1.

| Domain | Commands | Sources |
|---|---|---|
| `company` | 32 | GLEIF, SEC EDGAR, FDIC, USAspending, TED, VIES, Zefix (CH), Brreg (NO), YTJ (FI), RUES (CO), Hometax (KR), ARES (CZ), SEBI intermediaries (IN), GBD_UL (KZ), GFSC (GG), JFSC (JE), ROR |
| `healthcare` | 31 | FDA approvals, recalls & shortages, ClinicalTrials.gov, RxNav, DailyMed, UK MHRA, Health Canada, EUDAMED, RASFF & Safety Gate (EU), TGA (AU), Europe PMC, MeSH |
| `legal` | 27 | US sanctions (CSL, OCC), eCFR, Federal Register, CourtListener, LDA filings, DG COMP, UK CMA & Electoral Commission, The Gazette, SEBI orders (IN), MDB debarment (WB/AfDB/IDB), Canada SEMA, CFPB complaints, SIPRI |
| `economy` | 18 | World Bank WDI, Eurostat, ECB rates, FRED, BLS, WHO xMart, UN Comtrade, ILOSTAT, BIS, IMF, OECD, EU Comext |
| `esg` | 12 | Climate TRACE, EITI, EU ETS (EUTL), THETIS-MRV, EPA FRS, Paris MoU, EU Air Safety List |
| `research` | 10 | OpenAlex, NIH RePORTER, NSF, Crossref, UKRI GtR, iCite, bioRxiv, OpenCitations |
| `procurement` | 7 | PNCP (BR), SECOP II (CO), UNGM, World Bank, NY Authorities / MTA / OGS (US) |
| `security` | 4 | OSV, CISA KEV, ENISA EUVD |

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

## License and terms

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
- Hosted-corpus credentials and service inquiries: **contact@dicaria.com**
- Security reports: **contact@dicaria.com** — please don't open a public
  issue; see [SECURITY.md](https://github.com/dicaria/agentdata/blob/main/SECURITY.md)
- Conduct issues: **contact@dicaria.com** (see
  [CODE_OF_CONDUCT.md](https://github.com/dicaria/agentdata/blob/main/CODE_OF_CONDUCT.md))
