# agentdata

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Commands](https://img.shields.io/badge/90_commands-7_domains-teal)](docs/domains/api.md)

One Python client for public-domain company intelligence: registries, sanctions,
procurement, judgments, filings, and research outputs across 10+ countries and
regions — through one consistent interface.

- **Pure standard library** — Python 3.10+, zero third-party dependencies
- **90 flat-panel commands** across 7 domains, one command per upstream dataset
  (`<domain> <source>_<dataset>`), parameters kept under their upstream names
- **Politeness built in** — per-source rate limits are enforced by default
  (see [docs/domains/rate-limits.md](docs/domains/rate-limits.md))

## Two API families

| Family | Where it runs | Credentials | Cost |
|---|---|---|---|
| **Enrichment** | Locally — the SDK calls public government / open-data APIs from your machine | none | free |
| **Corpus** | Hosted service operated by dicaria | credentials issued by dicaria | per service agreement |

Most commands are enrichment: they need no configuration, no keys, no account.
Corpus commands are marked in the docs and require credentials issued by
dicaria under a separate service agreement — contact **contact@dicaria.com**.

## Install

From a release tarball — no git required:

```bash
pip install https://github.com/dicaria/agentdata/archive/refs/tags/v0.3.18.tar.gz
```

Or via git (pin a tag for reproducible installs):

```bash
pip install git+https://github.com/dicaria/agentdata.git@v0.3.18
```

## Quick start (Python)

```python
from agentdata import Client

c = Client()  # zero config: enrichment commands work immediately

# ── healthcare ──
c.healthcare.rxnav_rxcui_by_name(name="atorvastatin")            # drug name -> RxCUI (RxNav)
c.healthcare.mesh_descriptor(label="aspirin")                    # term -> MeSH descriptor (NLM)
c.healthcare.gudid_devices(di="00884858000377")                  # US device master register (AccessGUDID)
c.healthcare.epmc_search(search='AFF:"AstraZeneca"')             # literature evidence (Europe PMC)
c.healthcare.fda_drug_recalls(search='recalling_firm.exact:"SV Labs Toronto Corporation"')

# ── company ──
c.company.gleif_lei_records(lei="5493001KJTIIGC8Y1R12")           # LEI -> entity identity card (GLEIF)
c.company.fdic_institutions(filters="CERT:628")                   # FDIC CERT -> insured bank
c.company.sec_submissions(cik=320193)                             # SEC CIK -> registrant card (EDGAR)
c.company.sec_fulltext_search(q="artificial intelligence", forms="8-K")
c.company.ted_notices_search(query='organisation-name-buyer=Siemens* AND organisation-country-buyer=DEU')

# ── esg ──
c.esg.eiti_payments(name="Equinor")                                # company -> government payments (EITI)
c.esg.climatetrace_sources(owner_ids="E100000001492", year=2023)  # owner -> facility-level emissions

# ── legal ──
c.legal.csl_screening_list(name="VTB BANK")                       # sanctions screening (US CSL)
c.legal.courtlistener_opinions_search(case_name="acme corp", court="calctapp")

# ── research ──
c.research.openalex_works(search="vaccine", ror="01xdqrp08")
c.research.nih_reporter_projects(org_name="Rockefeller University", fiscal_year=2024)

# ── security ──
c.security.osv_vulns(package="lodash", ecosystem="npm", version="4.17.15")

# ── procurement ──
c.procurement.pncp_contracts(data_inicial="20260901", data_final="20260930", pagina=1)
c.procurement.secop_contracts(where="upper(nombre_entidad) like '%MINISTERIO%'", limit=5)
c.procurement.wb_procnotices(notice_type="Major Contract Awards", rows=10)
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
agentdata healthcare ctgov_studies --query.term 'AREA[LeadSponsorName]("Pfizer")' --page-size 3
agentdata company gleif_lei_records --lei 5493001KJTIIGC8Y1R12
agentdata esg climatetrace_sources --owner-ids E100000001492 --year 2023
agentdata legal csl_screening_list --name "VTB BANK"
agentdata research nsf_awards --keyword "lithium battery"
agentdata security cisa_kev_catalog --cve CVE-2021-44228
agentdata procurement pncp_contracts --data-inicial 20260901 --data-final 20260930 --pagina 1
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

## Domains

| Domain | Faces | Examples of sources |
|---|---|---|
| `healthcare` | 24 | RxNav, MeSH, AccessGUDID, EUDAMED, Europe PMC, openFDA, CT.gov, DailyMed, TGA, MHRA alerts |
| `company` | 21 | GLEIF, FDIC, SEC EDGAR, TED, Zefix, Brreg, YTJ, SIRENE, Companies House, RUES (CO), Hometax (KR) |
| `esg` | 11 | EITI, Climate TRACE, Paris MoU, THETIS-MRV |
| `legal` | 15 | US CSL, eCFR, DG COMP, LDA, CourtListener, gazette corpora, TNA judgments, SIC sanctions |
| `research` | 10 | OpenAlex, NIH RePORTER, NSF, Crossref, UKRI GtR, iCite, bioRxiv, COCI |
| `security` | 2 | OSV, CISA KEV |
| `procurement` | 7 | PNCP (BR), SECOP II (CO), UNGM, World Bank Procurement Notices, NY Authorities (US), NY MTA (US) |

## Documentation

- [docs/domains/api.md](docs/domains/api.md) — cross-domain contract: the two API families, request/response envelope, parameter conventions
- [docs/domains/company-api.md](docs/domains/company-api.md) — company-domain integration notes for external parties
- [docs/domains/healthcare-api.md](docs/domains/healthcare-api.md) — healthcare-domain integration notes
- [docs/domains/rate-limits.md](docs/domains/rate-limits.md) — per-source rate-limit facts the SDK enforces

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
