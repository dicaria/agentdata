# agentdata

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Commands](https://img.shields.io/badge/97_commands-7_domains-teal)](docs/domains/api.md)

Government registries, sanctions lists, procurement portals, and health-agency
databases hold the decisive facts about companies — scattered across 60+ public
APIs, each with its own pagination, rate limits, and undocumented quirks.

**agentdata puts 97 of those datasets behind one interface**: a
pure-standard-library Python client and CLI across 13 jurisdictions. No API
keys, no accounts — politeness and caching are built in, and every upstream
gotcha we hit live is already pinned.

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
| Is this company sanctioned? | `legal csl_screening_list` · `legal co_sic_sanctions` |
| Who owns or controls it? | `company gleif_direct_parent` · `company no_brreg_roller` · `company fr_recherche_search` |
| Did it win public contracts? | `procurement br_pncp_contracts` · `procurement ungm_contract_awards` · `procurement wb_procnotices` |
| Is its drug or device approved — or recalled? | `healthcare fda_drug_approvals` · `healthcare gb_mhra_alerts` · `healthcare fda_drug_recalls` |
| What does this facility or fleet emit? | `esg climatetrace_sources` · `esg thetis_mrv_datasets` · `esg paris_mou_detentions` |
| Pull a company card from a national registry | `company ch_zefix_firm` · `company co_rues_companies` · `company kr_hometax_biz_status` |

## Why not just call the APIs yourself?

You can — and then you get to rediscover what is already pinned here:

- **Quirks are pre-solved, not rediscovered.** Every command encodes traps we
  hit against the live API: the UN Global Marketplace search behind an
  anti-forgery token dance; Socrata endpoints that silently ignore documented
  parameters; the gov.uk content API that 404s when you append `.json`;
  registries that clamp your page size without an error.
- **One envelope across all 97 commands.** Query echo, a plain-language
  `reason`, `evidence` rows with a checkable quote and source URL, source
  metadata, and a `jurisdiction` chapter — your code parses one shape.
- **Upstream parameter names, verbatim.** What the official API docs call a
  parameter is what the SDK takes — no invented vocabulary to unlearn.
- **Polite by default.** Per-source rate limits are enforced before every
  request ([rate-limits ledger](docs/domains/rate-limits.md)); responses are
  cached locally, and a cache hit costs no rate budget.
- **Zero dependencies.** Python 3.10+ standard library only.

## Coverage

**97 datasets · 66 upstream providers · 13 jurisdictions:** US 36 · global 24 · UK 11 · EU 9 · Canada 4 · Colombia 3 · Australia 2 · Switzerland 2 · Norway 2 · Brazil 1 · Finland 1 · France 1 · Korea 1.

| Domain | Commands | Sources |
|---|---|---|
| `healthcare` | 31 | US FDA approvals & recalls, ClinicalTrials.gov, RxNav, DailyMed, AccessGUDID, UK MHRA alerts, Health Canada DPD & MDALL, EUDAMED, RASFF & Safety Gate (EU), TGA (AU), Europe PMC, MeSH |
| `company` | 21 | GLEIF, SEC EDGAR, FDIC, USAspending, TED, VIES, UK Contracts Finder & FTS, Zefix (CH), Brreg (NO), YTJ (FI), recherche-entreprises (FR), RUES (CO), Hometax (KR), ROR |
| `esg` | 11 | Climate TRACE, EITI, EU ETS (EUTL), THETIS-MRV (EU shipping), EPA FRS, Paris MoU |
| `legal` | 15 | US consolidated screening list, eCFR, Federal Register, LDA filings, CourtListener, DG COMP, UK CMA cases, UK Electoral Commission, TNA case law, SIPRI, SIC sanctions (CO) |
| `research` | 10 | OpenAlex, NIH RePORTER, NSF, Crossref, UKRI GtR, iCite, bioRxiv, OpenCitations |
| `procurement` | 7 | PNCP (BR), SECOP II (CO), UNGM, World Bank, New York Authorities / MTA / OGS (US) |
| `security` | 2 | OSV, CISA KEV |

## Show me a response

Real output of `agentdata healthcare rxnav_rxcui_by_name --name atorvastatin` —
every command returns this shape:

```json
{
  "ok": true,
  "domain": "healthcare",
  "tool": "rxnav_rxcui_by_name",
  "input": {
    "name": "atorvastatin"
  },
  "from_cache": false,
  "reason": "RxNav normalization: drug name 'atorvastatin' → RxCUI 83367 (ingredient level)",
  "result": {
    "rxcui": "83367",
    "normalized_name": "atorvastatin",
    "synonym": null,
    "tty": "IN",
    "suppress": "N"
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
    "from_cache": false,
    "observed_at": "2026-11-02T03:28:22.213Z"
  },
  "request_id": "3f343e2f-3b08-46e8-ac69-8ee05adce548",
  "query": {
    "source": "raw",
    "upstream": {
      "name": "atorvastatin"
    }
  },
  "jurisdiction": "US"
}
```

## Install

From a release tarball — no git required:

```bash
pip install https://github.com/dicaria/agentdata/archive/refs/tags/v0.3.19.tar.gz
```

Or via git (pin a tag for reproducible installs):

```bash
pip install git+https://github.com/dicaria/agentdata.git@v0.3.19
```

## Quick start (Python)

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
```

Corpus commands use the same shape with hosted credentials:

```python
c2 = Client(base_url="https://…", api_key="mk_live_…")  # PAT issued by dicaria
c2.company.read(id=1476, level="tier2")
```

## Quick start (CLI)

Eight entry points — `agentdata` plus one command per domain:

```bash
agentdata healthcare rxnav_rxcui_by_name --name atorvastatin
agentdata company gleif_lei_records_search --filter-entity-legal-name "Siemens" --page-size 3
agentdata legal csl_screening_list --name "VTB BANK"
agentdata esg climatetrace_sources --owner-ids E100000001492 --year 2023
agentdata procurement br_pncp_contracts --data-inicial 20260901 --data-final 20260930 --pagina 1
```

## Caching

Every response is cached in a per-user SQLite cache shared across virtual
environments and processes — cache hits cost no rate budget (see
[docs/domains/rate-limits.md](docs/domains/rate-limits.md)). A fresh install
in a new virtual environment will therefore hit entries written by earlier
runs on the same machine; that is by design.

| | |
|---|---|
| Default location | `%LOCALAPPDATA%\agentdata\cache.db` on Windows; `~/.cache/agentdata/cache.db` on macOS/Linux |
| Override | `AGENTDATA_CACHE_DIR` environment variable (CLI: `--cache-dir`) |
| Bypass | `--no-cache` (CLI) / `no_cache=True` (Python) |
| Clear | delete the file — every entry re-fetches on demand |

Entry lifetimes follow the per-source TTL table in the rate-limits ledger;
immutable lookups (e.g. drug name → RxCUI) are cached permanently.

## Documentation

- [docs/domains/api.md](docs/domains/api.md) — the API contract of the release
  you installed: the two families, request/response envelope, parameter
  conventions
- [docs/domains/rate-limits.md](docs/domains/rate-limits.md) — per-source
  rate-limit facts this release enforces
- Hosted-corpus per-domain guides: contact **contact@dicaria.com**

## License and terms

- The **code** in this repository is licensed under the license in
  [LICENSE](LICENSE).
- The **data** returned by the SDK is governed by the terms of each upstream
  source; the SDK grants no data rights. See [TERMS.md](TERMS.md).

## Contact

- Questions, bug reports, and data-coverage requests:
  [GitHub issues](https://github.com/dicaria/agentdata/issues) or
  **contact@dicaria.com** (see [CONTRIBUTING.md](CONTRIBUTING.md))
- Hosted-corpus credentials and service inquiries: **contact@dicaria.com**
- Security reports: **contact@dicaria.com** — please don't open a public
  issue; see [SECURITY.md](SECURITY.md)
- Conduct issues: **contact@dicaria.com** (see
  [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md))
