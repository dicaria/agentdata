# Healthcare Domain API Reference (external edition)

> **Audience**: external integrators / downstream consumers (pharma companies / medical representatives / CROs / consulting firms, etc.). This document is the external reference for the healthcare domain query interfaces — it covers only the contract and data reality, not pipeline internals.
> The internal design source of truth remains healthcare.md (§1-§8 boundaries/sources/fact model/quality gates, §10-§12 commercial/compliance/backlog) and [api.md](api.md) (the cross-domain contract).
> Transport forms: P1 = CLI (every command in this document runs as-is); P2 = HTTP `/v1/healthcare/*` (request/response semantics unchanged, see api.md §8).
> Domain type: **multi-regime (api.md §7)** — the CN / US / cross sides differ markedly in record_kind sets, field sets, compliance frameworks, and primary user questions; the `side` parameter is a §7.2 contract **designed ahead of wiring — engine/SDK not yet connected** (passages marked 〔planned〕 in this document are in exactly that state).
> Status: 2026-10-19 edition aligned with the implementation — P1 has landed (domain-spec / engine / agentdata SDK in service, staging-scan form); `side` and the multi-regime sub-resource endpoints are contract-first, and until wired every related passage is marked 〔planned〕.
> Split relationship: healthcare.md is the master record (internal source of truth); healthcare-api.md is the external edition (single-page API reference for consumers); healthcare-storage-api-design.md is the storage design draft (parallel to this document).
> Online service layer: **omnihub v2.3 is live** (eight storage tables + HTTP v1 + 29 MCP tools, see §9) — same data source as this document's contract track, separate paradigm track; §9 registers the as-built state truthfully.
> Direct hub REST calls: **production base URL https://hub.omnimay.com with 26 readable faces directly callable** (parameter-level reference in §10) — callers holding a subject token can call directly today per §10; the SDK three-verb path is not yet connected to the medical production store (§10 header status note, to prevent misreading).

---

## 1. What this API covers (coverage statement)

### 1.1 Asset inventory (verified 2026-10-14)

| Asset | Scale | Notes |
|---|---|---|
| raw (healthcare-related) | ~**12.5GB** | openFDA 4.1G · ClinicalTrials 2.8G · CMS 1.2G · NPPES 1.1G · OpenPayments 3.3G · OB 1M · CDE 270M+ (collection ongoing) · hospitals 28M · centralized procurement 4.5M |
| staging | **7,577,069 rows** (2026-10-15) | openFDA (drugsfda / UDI full universe 5.18M / OrangeBook / PurpleBook) + NPPES + OpenPayments + Hubei provincial bureau + centralized procurement — the old per-source distribution snapshot is superseded; the live `--facets qtype` distribution is authoritative |
| `db/leads.db` healthcare rows | **0** | no `fda_*` / `cn_hospital_*` qtypes in the store (P0 ingestion backlog, healthcare.md §12.2-1) |

- **Coverage ≠ completeness**: registry snapshots are not exhaustive — "no such company found" never equals "the company does not exist / carries no risk" (the not-covered ≠ no-risk principle).
- **Zero healthcare rows in db is the current biggest blocker**: P1 adapters run in staging-scan form, querying already-published batches directly (`source.backend=staging` marked honestly); once P0 ingestion lands, the same commands switch to the db main path with unchanged command shape.
- Every result row carries `source.observed_at` (the observation time of that record); coverage statements carry per-source observation times.

### 1.2 Multi-regime partitioning (api.md §7)

healthcare is a **multi-regime domain** — the CN / US / cross sides each carry their own compliance framework and primary user questions (contract-first; see the status note at the top).

| side | Data-outlet basis | Strong keys | Compliance framework | Primary user questions |
|---|---|---|---|---|
| `cn` | NMPA / CDE / SMPAA / NHC / drug administration | uscc (Chinese hospitals **have no USCC — marked as-is**; L3 candidates are not auto-merged) | PIPL + data-export security assessment measures + labeling filing obligations (not ingested) | "Product approvals / centralized-procurement wins / hospital coverage for Chinese pharma companies" |
| `us` | FDA / CMS / OIG / DOJ | cik / lei / npi / ccn (**no uscc**) | HIPAA + Open Payments Sunshine Act + FDA off-label restrictions | "US FDA approvals / procurement / hospital payment flows" |
| `cross` | cross-side aggregation inference | — | alignment ceiling declared honestly (FDA rows have no uscc and are not auto-merged) | "Chinese pharma going-global signals (FDA approvals) / multinational pharma benchmarking" |

**Multi-regime-exclusive sub-resources** 〔planned — not implemented; api.md §7.1 contract; the asymmetry is deliberate, no hollow routes added〕:
- `POST /healthcare/cn/holder/procurement` —— UC-H4 centralized-procurement wins + medical-insurance drug list (CN exclusive)
- `POST /healthcare/us/holder/payment` —— UC-H9 OpenPayments (US exclusive)

---

## 2. Quick start

```bash
# ① US approved-companies roster (UC-H1)
node harvest/shared/domain-export.mjs healthcare search \
  --filter 'qtype=fda_drug_ndc' --filter 'approval_year>=2023' \
  --facets qtype --level tier1 --fmt csv -o usndc.csv

# ② Centralized-procurement wins + nested DSL (UC-H4; --filter-json is the sole authoritative entry)
node harvest/shared/domain-export.mjs healthcare search --filter-json q.json --limit 200
  # q.json = {record_kind:"procurement", project:{any:["第12批"]},
  #           product_name:"复方氨基酸", plan_month:{gte:"2025-01"}}

# ③ Medical institution roster (UC-H5; institutions listed separately, never mixed into company rosters)
node harvest/shared/domain-export.mjs healthcare search \
  --filter 'subject_kind=institution' --filter 'qtype=cn_hospital_grade' \
  --level tier1 --fmt csv -o hospitals.csv

# ④ Subject profile (UC-H7 dual-signal entry)
node harvest/shared/domain-export.mjs healthcare read --target company:<id> --level tier2

# ⑤ Batch list screening (first pass over a going-global list; six states returned per row)
node harvest/shared/domain-export.mjs healthcare search --mode screen --input targets.jsonl \
  --level tier1 --fmt jsonl -o screen.jsonl
```

**Multi-regime `side` parameter** 〔planned — api.md §7.2 contract-first, engine/SDK not yet wired; passing `--side` today fails with unknown parameter〕. Until it is wired, jurisdiction is expressed at the field layer:

```bash
# Current equivalent: jurisdiction carried via qtype prefix (cn_* / us_*) + the row-level country field
node harvest/shared/domain-export.mjs healthcare search \
  --filter 'qtype=cn_drug_trade_license' --filter 'status=有效' --limit 100

node harvest/shared/domain-export.mjs healthcare search \
  --filter 'qtype=us_ob_product' --facets company_registration_country --limit 50

# Once the contract is wired (shape below, not runnable yet): --side cn|us|cross; cross follows the "declare the alignment ceiling honestly" rule and every row carries a side annotation
```

What a returned row looks like (`--fmt jsonl`; the quartet is mandatory: **company + reason + evidence + provenance**):

```json
{"domain":"healthcare","level":"tier1","cursor":"qualification:1","record_kind":"qualification",
 "entity":{"subject_kind":"company","company_id":1476,"company_name":"BARR PHARMA INC","country":"美国",
           "qtype":"fda_drug_ndc","approval_year":"2023","status":"有效","license_no":"ANDA078071"},
 "reason":"命中过滤器: qtype=fda_drug_ndc & approval_year>=2023",
 "evidence":[{"anchor":"drug-drugsfda-0001-of-0001.json.zip:1234",
              "quote":"ANDA078071 | ATORVASTATIN CALCIUM | BARR | 2023-08-15 | approved",
              "url":"https://api.fda.gov/drug/drugsfda.json?search=application_number:ANDA078071"}],
 "source":{"source":"openfda/drugsfda","observed_at":"2026-09-20","backend":"staging"}}
```

---

## 3. Two record kinds (record_kind)

| record_kind | Semantics | Sort/cursor | Applicable side |
|---|---|---|---|
| `qualification` (default) | Drug/device approvals / registrations / licenses / payment aggregates (incl. institution-subject rows) | id ascending | all (`side` 〔planned〕) |
| `procurement` | Centralized-procurement wins (**semantic borrowing** of the government-procurement shared contract; this domain exposes only the procurement semantics) | id ascending | mostly `side=cn` (US procurement is expressed separately) |

**Named but not enabled (request returns 400)**: `clinical_trial` / `product_registration` / `risk_event` — closed-vocabulary changes require an adversarial review (healthcare.md §12.3-1). The current 606,601 CT studies are reused through `qualification` + qtype `ct_study`; rec_type is decided only after its own adversarial review.

Filtering-semantics key point: **multiple fields at the same layer anchor the same row** — `qtype=fda_drug_ndc & approval_year>=2023` hits that company's "approvals from 2023 onward"; its separate 2020 approvals never leak into the result.

---

## 4. Filter field reference

DSL: `eq / any / range(gte,gt,lte,lt) / _not / _or`; **any field not declared in this document returns 400** (to prevent "a mistyped field returning an empty set being read as no data"). CLI: `--filter 'k=v'`, `--filter 'k>=v'`, `--filter 'k=a|b'`; full nesting goes through `--filter-json`. Cross-domain contract: [api.md](api.md) §3.

### 4.1 Controlled dimensions (enabled)

| filter | Type | Applicable record_kind | Notes |
|---|---|---|---|
| `subject_kind` | keyword | all | `company`｜`institution`｜`facility`｜`product`｜`person` (five axes, derived from export.mjs QTYPES: institution rosters / POS·CLIA facilities / ADR product signals / NPPES person rows each listed separately; institutions are not companies, healthcare.md §3) — gate on the institution-roster outlet (UC-H5 delivered as a separate list, not mixed into company rosters); screen input carries the same field |
| `qtype` | keyword | qualification | controlled vocabulary in healthcare.md §5.2 (`fda_*`/`cn_*`/`us_*`, 29 values in use + 9 pending; 2026-10-19 expansion round +10: five Suzhou distribution / two medical-administration lists / two POS·CLIA facility / one ADR bulletin) |
| `status` | keyword | qualification | 有效 / 变更 / 注销 / 负面事件 — **polarity gate**: negative facts must be explicitly 负面事件, never defaulted to 有效 (healthcare.md §5.2) |
| `license_no` | keyword | qualification | fact-key exact anchor: application_number / k_number / pma_number / ndc / acceptance number / certificate number / CCN — not used as a company merge key (healthcare.md §5.3) |
| `product_name` | keyword | qualification, procurement | product/variety (FDA product names, procurement varieties); specifications go to T2 `spec_note` |
| `approval_year` | range | qualification | approval year (fda_* approval-type facts) |
| `effective_from` / `effective_until` | range | qualification | license validity interval (hospital practice / manufacturing licenses) — expired rows never enter the "currently valid" projection (healthcare.md §5.5) |
| `taxonomy_code` | keyword | qualification | NPPES institution-type taxonomy code (same CMS code table, comparable across sources) |
| `hospital_type` / `ownership` | keyword | qualification | hospital type / ownership (CMS hospital-master profiling dimensions; emergency / overall_rating go to T2) |
| `province` | keyword | qualification | province (Chinese province names, Hubei line) |
| `program_year` | range | qualification | OpenPayments program year (3-year window, ruled 2026-10-13) |
| `payment_amount_usd` | range | qualification | OpenPayments annual aggregate amount — range requests must carry `metric_unit:"USD"` (api.md §3.1 value-must-carry-unit) |
| `company_registration_country` | keyword | all | subject registration country — **US line nearly empty**: openFDA/OpenPayments rows have `country_code` all null + `country_code_unresolved` (healthcare.md §5.4/§5.6-H); coverage follows the source, and inferring registration country from the source domain is forbidden |
| `project` / `plan_month` | keyword / range | procurement | procurement batch (incl. `第N批` values) / procurement execution month (YYYY-MM) — `plan_month` is a semantic borrowing, must carry the `procurement_winning_notice` flag, and must not be misread as government procurement's "expected procurement time" (healthcare.md §5.4) |
| `source` / `source_observed_at` | keyword / range | all | source and observation time (snapshot/event/interval — three time semantics, healthcare.md §5.5) 〔planned — not declared in the spec; requests today return 400〕 |

**Recommended first-run facets**: `qtype`, `subject_kind`, `company_registration_country`, `program_year`, `province` (`record_kind` attached by default).

### 4.2 Dimensions pending enablement (enter the spec after adversarial review; all requests currently return 400)

`condition_mesh` / `phase` / `sponsor_class` (clinical_trial line not yet published; indications must be MeSH controlled terms, healthcare.md §12.2-8); `device_class` / `medical_specialty` (FDA 510(k)/PMA line not yet published — the current openfda batch = drug-ndc); `establishment_type` (fda-inspections line not yet published); `facility_address_country` (facility address country ≠ registration country, registrationlisting); recall/inspection/quality-notice negative dimensions (rec_type home, healthcare.md §12.3-2).

### 4.3 screen mode input

`{name, identifiers[], subject_kind}` — name approximate hits return the **current five states** (exact_identifier / candidate_name_match / ambiguous / no_match_in_coverage / not_covered; staging has no subject-merge layer, so every name hit is a candidate; after P0 ingestion this upgrades to the full six states, api.md §4). `identifiers=[]` is a statement of coverage reality, not a data defect; coverage_assertion reports it as-is.

The current closed set for screen `identifiers.type`: **uscc / ccn / npi / fda_application_number / openpayments_mfr_id** etc. — matched verbatim against staging `subject.identifiers` (domain-spec screen section).

---

## 5. Use-case matrix and acceptance criteria

Use-case numbering carries over the **UC-H1~H8** already referenced in the healthcare.md §2 sub-line table (the number is the user task; data gaps go to the healthcare.md §4/§4.4 matrix and delivery formats to this document's §6 T-layer contract — neither consumes use-case numbers), plus the new UC-H9. The stage column is marked honestly: staging ✓ but `db` healthcare rows = 0 (healthcare.md §12.1); all P1 use cases await P0 ingestion (healthcare.md §12.2-1). **Row counts are a 2026-10-14 snapshot; the live `--facets` distribution is authoritative** (the §1.1 totals have since been updated).

| # | Use case | Acceptance essentials | Stage |
|---|---|---|---|
| UC-H1 | **US approved-companies roster** (by category/product/year) | qtype/product_name/approval_year combinations; one company with multiple approvals **must yield multiple rows** (healthcare.md §5.5 idempotency key); `identifiers=[]` name alignment declared honestly | **P1** (staging ✓ 770k rows; awaiting P0) |
| UC-H2 | **Chinese pharma going-global signals** (CN-US cross, side=cross) | alignment ceiling — FDA rows have no strong key, automatic alignment is unsolvable (healthcare.md §5.3); usable only after the alias bridge (EDGAR subsidiary English names 47,362 / NPPES othername) or L2 on-demand completion — no automatic resolution promised | P2 |
| UC-H3 | **Device manufacturer → channel distributor** | US side 510(k)/PMA/listing filterable (side=us); CN side trade license `cn_medical_device_trade_license` not yet harvested (gsxt-identical template, zero reverse engineering) — the channel profile closes only after harvesting; business scope goes into fact, never dropped | US side P1 (awaiting P0); CN side awaiting harvest |
| UC-H4 | **Centralized-procurement wins** (by batch/variety/company, side=cn, **`/healthcare/cn/holder/procurement`** 〔planned〕) | project/product_name/plan_month; **the winning subject = subject** (mapped `winner_id`, healthcare.md §12.2-4); the `procurement_winning_notice` flag distinguishes the semantic borrowing; win-table PDF row quotes + `pdf_table_extract` | **P1** (staging ✓; awaiting P0) |
| UC-H5 | **Medical institution roster** (end buyers, side=cn/us each) | `subject_kind=institution` delivered as a separate list, not mixed into company rosters; `valid_to`-expired rows never enter "currently valid"; license content (new departments = procurement signals) goes to T2 | **P1** (staging ✓ Hubei 1,973 + CMS 5,419; awaiting P0) |
| UC-H6 | **Clinical and review timing line** (CRO/CDMO) | CDE implied approvals pending (~25k rows); CT 606,601 studies pending — indications **must be MeSH controlled terms**; storing free text only and filtering on it does not hold (healthcare.md §12.2-8); `companys` multi-subject rows split | P1 pending |
| UC-H7 | **Dual-signal overlay** (supply-chain relationships × medical qualifications) | cross-source linkage + traceable evidence = the differentiation moat (Yaozhi/Mosheng are consolidated libraries without this); 4,775 companies with 3+ qualifications on record | P2 (awaiting ingestion + relationship channel) |
| UC-H8 | **Risk line** (recalls/violations/procurement-win revocations) | polarity gate: negatives are never defaulted to 有效; historical negatives never expire but the outlet carries dates (a three-year-old recall is not a hot lead); rec_type home adversarial review comes first | P2 (after review) |
| UC-H9 | **Pharma KOL investment intensity** (OpenPayments company side, side=us, **`/healthcare/us/holder/payment`** 〔planned〕) | program_year/payment_amount_usd (with unit:USD) cross-year comparison = increments; **individual detail rows never leave the store** (healthcare.md §11-4 red line); OWNRSHP has no mfr_id and relies on L2 name alignment | **P1** (staging ✓; awaiting P0) |

---

## 6. External interfaces (this domain)

The cross-domain contract (three verbs / T-layer quartet / Filter DSL / six match states) is in [api.md](api.md); only the healthcare-specific parts are written here:

```
POST /healthcare/search   filters=§4; facets/facets_only; mode:"screen" (batch list screening)
                          record_kind = qualification | procurement
                          (clinical_trial / negative events named but not enabled: healthcare.md §12.3 adversarial-review position, not in domain-spec)
                          〔planned〕side=cn|us|cross (api.md §7.2 contract-first, engine/SDK not wired — passing side today fails with unknown parameter)
POST /healthcare/read     target:{type:"company"|"institution", id} + level=tier1|tier2|tier3
                          (institution subjects are directly readable — npi/ccn are anchors, not merge keys, healthcare.md §5.3; Chinese hospitals with identifiers=[] align via name + address + license number, L3 candidates not auto-merged)
                          side does not participate: read aggregates across sides via target.id
POST /healthcare/ask      not enabled in P1
GET  /company/{id}/facts?domain=healthcare&side=cn|us   unified company-profile entry: delegates to this domain's read levels (api.md §1), defines no fields of its own 〔planned — not implemented〕

# Multi-regime-exclusive sub-resources 〔planned — not implemented〕 (asymmetry deliberate, api.md §7.1; no hollow routes added)
POST /healthcare/cn/holder/procurement   UC-H4 centralized-procurement wins + medical-insurance drug list (CN exclusive)
POST /healthcare/us/holder/payment       UC-H9 OpenPayments (US exclusive)
```

**T-layer content** (aggregated by company/institution primary key; T1 also carries short evidence anchors; the output quartet is mandatory):

| Layer | healthcare content |
|---|---|
| T1 | Subject card: name / subject type (company\|institution) / strong keys (uscc when present) / country (unresolved US-line values must be stated) / qualification summary (approval count · latest approval · license status) + risk-signal counts (after adversarial review) + source coverage + "not covered ≠ no risk" (side annotation added when §7.2 is wired) |
| T2 | qualification detail (qtype/product/fact key/approval or validity dates/status/evidence quote — approval rows carry openFDA source-row quotes, procurement rows carry win-table PDF row quotes); institution profile (hospital_type/ownership/taxonomy_code/emergency/overall_rating); OpenPayments annual aggregate (program_year/total USD/nature distribution top-N/recipient-state distribution) |
| T3 | Evidence package: raw_path + official URL + sha256 + fetch time + source batch + shard:row (source_row_key, e.g. `drug-drugsfda-0001-of-0001.json.zip:0`); Hubei xlsx carries table/row anchors; **the payload has no personal-contact columns** (red line healthcare.md §11-4; NPPES/CT contacts stripped) |

`name_match_log.method` stays at the `cross_jurisdiction_candidate` candidate state — cross-side name approximate hits are always candidates, resolved by human review (healthcare.md §5.3 strong-key-first principle).

### 6.1 Third-party real-time queries (enrichment capabilities, external)

**The mechanism source of truth has been promoted to the public chapter**: [api.md](api.md) §9 (domain-capability classification / the `execution` dichotomy / row shape / error codes / declarative caching / the "invisible third party" boundary) — this section registers only **this domain's capability list**; where it conflicts with the public chapter, the public chapter prevails. Internal sourcing/rate-limiting/cache design source of truth: healthcare-thirdparty-api-design.md (SDK landing design in its §8.1).

```
POST /healthcare/resolve   {kind:"drug_name"|"device_di"|"device_eu"|"atc", value, execution?}   → normalized identity card / ATC code
POST /healthcare/evidence  {query} | {company, focus?}                                 → literature evidence rows
POST /healthcare/trials    {company?|query?|status?}                                   → clinical trial rows (CT.gov v2)
POST /healthcare/label     {drug}                                                      → SPL label metadata (DailyMed)
```

Capability register (this domain's rows of the full api.md §9.6 table):

| Capability | Upstream | provider | execution | Cache TTL | First shipped |
|---|---|---|---|---|---|
| `resolve kind=drug_name` | RxNav (NLM, keyless) | `rxnav` | local | permanent (RxCUI immutable) | **P0** (verified live) |
| `evidence` | Europe PMC (EBI, keyless; incl. full PubMed + MeSH indexing) | `epmc` | local | search pages 24h | **P0** (verified live) |
| `resolve kind=device_di` | AccessGUDID v3 (FDA/NLM, keyless) | `gudid` | local | 7 days (records revisable) | **P1** (verified live) |
| `resolve kind=device_eu` | EUDAMED public device catalogue (EC, keyless; SPA same-origin REST) | `eudamed` | local | 7 days (master slowly changing) | **Wave 2** (verified live; endpoint stability under two-point observation: 2026-10-17 recipe-book probe + 2026-10-20 recheck) |
| `resolve kind=atc` | RxNav property (NLM, keyless) | `rxnav` | local | permanent (ATC classification immutable) | **Wave 1** (verified live) |
| `resolve kind=mesh_term` | MeSH RDF lookup (id.nlm.nih.gov, keyless) | `mesh` | local | 30 days (vocabulary ships annually) | **Wave 3** (verified live 2026-10-23) |
| `trials` | ClinicalTrials.gov API v2 (keyless) | `ctgov` | local | 7 days (trial records slowly changing) | **Wave 1** (verified live) |
| `label` | DailyMed v2 (NLM, keyless) | `dailymed` | local | 7 days (setid immutable, lists slowly changing) | **Wave 1** (verified live) |
| `related kind=drug_shortages` | openFDA drug/shortages (FDA, keyless) | `shortages` | local | 24h (shortage records update daily) | **Wave 5** (verified live 2026-10-23) |
| `related kind=artg_register` | TGA eBS ARTG register (AU, keyless, HTML SearchView) | `tga` | local | 24h (register updates daily) | **Wave 6** (verified live 2026-10-23) |
| `related kind=mis_manufacturers` | TGA eBS MIS licence register (AU, keyless, JSON view) | `tga` | local | 24h (licence register slowly changing) | **Wave 6** (verified live 2026-10-23) |
| Macro indicators (WHO GHO) / Canada DPD / Japan e-Stat | — | on-trigger | local (all keyless) | registered when opened | on-trigger |

- `resolve kind=drug_name`: any drug-name spelling → canonical RxCUI ID — the shared key for joining CN procurement/insurance drug names ↔ US Orange Book.
- `evidence`: company/compound → literature evidence rows (quartet: provenance = the official EPMC URL; affiliation search via the `AFF:` field).
- `resolve kind=device_di`: device DI → GUDID master record (manufacturer/brand/model + productCodes regulatory classification).
- `resolve kind=device_eu`: EU DI → EUDAMED master record (GUDID's EU counterpart: manufacturer SRN `XX-MF-…` + authorised-representative SRN `XX-AR-…` edges, risk class/market status). The upstream `primaryDi` exact search is unindexed — cold path up to ~50s (op timeout 90s, no retries burned), a resolve single-query face only, not bulk; the endpoint is SPA same-origin REST (not an officially documented face), stability registered under two-point observation (2026-10-17/10-20), breakage goes through the exit mechanism (design doc §4.8).
- `resolve kind=atc`: drug name or RxCUI → ATC code (WHO anatomical therapeutic chemical) — the cross-jurisdiction half of the "RxCUI(US) + ATC(global)" dual key; a concept with no ATC level → an honest empty list.
- `trials`: sponsor/status/free-form → clinical trial rows (NCT id/phase/status/start-end; a **fresh single query** layered on top of the batch full harvest).
- `label`: drug name → SPL label list (setid + title + source URL, incl. each labeler's dosage-form versions; XML full text not parsed — the agent fetches it via the URL).
- `related kind=drug_shortages`: manufacturer/drug name/status → FDA drug-shortage record rows (status/availability/shortage reason/first posted — a supply-risk event stream, closing the pipeline × safety × supply trio). Manufacturer search goes through the openFDA normalized layer as an exact phrase (`openfda.manufacturer_name.exact`); **zero hits = HTTP 404 is a valid answer** (openFDA convention) converted to an empty set; both company-edge columns are kept (registered manufacturer vs normalized manufacturer).
- `related kind=artg_register`: Sponsor (the Australian marketing accountability entity, quoted-phrase exact) / product term (AND across all fields) → ARTG register rows (97,988-entry register: product name × ARTG id × PI/CMI × type × Sponsor, rows carry OpenDocument detail links). HTML SearchView face (first case of the core `accept:'text'` channel); Count=100/page, `--skip` continues; a full page = possibly more (Domino does not emit a hit total; has_more is a heuristic). Zero hits is a valid answer.
- `related kind=mis_manufacturers`: the Australian manufacturer licence register in one shot, all 444 licences (Licence Number × Manufacturer ID dual keys + address/state/issue date), `--state` state filter (QLD/NSW/VIC…).

**Contract essentials** (details in public chapter §9):
- All providers are **keyless with `execution=local`** — the SDK runs them on the **user's machine**, and **rate limiting is the user's own** (the upstream fair-use quota per source IP naturally accrues per user; the SDK lock default = the highest politeness tier, downward-adjustable only); zero credentials for users (**not BYOK**, api.md §9.2).
- enrichment row provenance shape: `source = {provider, execution, from_cache, observed_at pass-through instant | fetched_at cache instant}` (api.md §9.3); corpus rows keep the `backend:"db"|"staging"` shape unchanged.
- Four error codes: `thirdparty_upstream_unavailable`(502) / `thirdparty_rate_limited`(**503**, Retry-After passed through from upstream; 429 is reserved for our own buckets) / `capability_unavailable`(503) / `resolve_kind_unknown`(400) (api.md §9.4).
- "Invisible third party" boundary: uniform at the operations layer (zero credentials / zero URLs / zero rate-limit tuning); **truthful at the provenance layer** — the upstream name and official URL are given as-is (api.md §9.1).

CLI: `agentdata healthcare resolve --kind drug_name --value "atorvastatin"` / `agentdata healthcare evidence --company "<company name>" --focus "<compound>"` (`--execution local|hosted|auto` defaults to auto; `request_id` emitted with both success and error) — after the 2026-10-26 user ruling retired the Node twin, CLI = the `agentdata` single stack (the former `service/cli.mjs` was removed with that layer); the domain-export.mjs entry for search/read stays put, unified migration at a chosen time.

**Honesty statement**: under local execution, upstream availability and fair-use quotas are not guaranteed by this domain (each third-party public API has its own policy); the SDK politeness tier + the user's local cache as fallback is our responsibility boundary; result freshness = the TTL positions in the table above.

### 6.2 Use cases (enrichment)

> One row per capability for **user question / verified example / boundary**, complementing the corpus-face §5 use-case matrix (UC-H1~H9). The examples are all real-machine values from the verification records of the design doc; CLI forms are above in this section (Node `service/cli.mjs` / Python `agentdata`, same contract).

**Use cases:**

| Capability | User question | Verified example | Boundary |
|---|---|---|---|
| `resolve kind=drug_name` | The same drug is spelled three ways across an FDA approval, an NDC label and a CN procurement batch — normalize to one key before joining. | `atorvastatin` → RxCUI `83367`; `metformin` → `6809`; `aspirin` → `1191`. Cached permanently (RxCUI is immutable). | English lexicon only — a Chinese drug name honestly returns `not_found`; cross-language bridging goes through the ATC key, never fuzzy name-guessing. |
| `resolve kind=atc` | Bridge a US-normalized drug into the global WHO ATC class so EU/JP/KR name spaces can join on it. | RxCUI `83367` (atorvastatin) → ATC `C10AA05`. TTL permanent. | A concept with no ATC level returns an honest empty list, not a guess. RxCUI(US) + ATC(global) is the dual key — half a key joins nothing. |
| `resolve kind=mesh_term` | A drug or disease term → the MeSH descriptor it belongs to: descriptor UI, preferred term, synonym pool, qualifier anchors — the controlled-vocabulary key for literature search and corpus normalization. | `aspirin` → D001241 Aspirin (17 synonyms, preferred "Aspirin"; qualifiers/seealso anchors). | Lookup takes the **label** parameter — passing term/descriptor is a 400 upstream. Zero hits is an honest answer (brand names should retry with the generic). Vocabulary ships annually → 30-day TTL. |
| `resolve kind=device_di` | A DI/UDI off a device label or an adverse-event report → master record: manufacturer, brand, model, product codes with device class. | DI taken from openFDA `device/udi.json` primary identifiers → full GUDID v2 record (`productCodes` carry deviceClass / regulationNumber / medicalSpecialty). | Records revise → 7-day TTL. Upstream WAF gates by client stack and egress IP — affected environments get an explicit `upstream_unavailable` (environment fact, not an outage; openFDA UDI is the data fallback). |
| `resolve kind=device_eu` | A DI on an EU-market device → EUDAMED master record: manufacturer SRN + authorised-representative SRN edges, risk class, market status — the EU counterpart of GUDID for EU vigilance/registration joins. | DI `00889024163300` → `CLS®, MIS` (Zimmer Switzerland Manufacturing, SRN `CH-MF-000008793`; EU rep Biomet, SRN `NL-AR-000000422`, class IIa, on-the-market). | `primaryDi` exact search is unindexed upstream — cold path up to ~50s (90s timeout, no retries); a resolve single-query face, not bulk. Endpoint is SPA same-origin REST (undocumented) under two-point stability watch (2026-10-17/10-20); empty pages are never cached as authoritative (transient server-side miss → purge-and-refetch once). |
| `evidence` | What published evidence exists around this company or compound, anchored to affiliations? | `AstraZeneca` via affiliation search (`AFF:`) → 37,108 records; free-text mode for compounds. | Zero hits is an honest empty set, not an error. PMID records cache permanently; search pages 24h. |
| `trials` | What trials does this sponsor run, and how many are recruiting right now? | `AREA[LeadSponsorName]("AstraZeneca")` + RECRUITING → totalCount 247. | Sponsor match is exact against the registered legal name — a trade name (e.g. Moderna) can return 0 with an explicit rerun hint; 0 ≠ no trials. Status drifts → 7-day TTL. |
| `label` | The label as filed: which SPL versions exist for this drug, by which labelers? | `atorvastatin` → SPL list incl. NUCARE setid `5d5977a5` (version + published date + human URL). | List-level metadata only — SPL XML full text is fetched by the caller via URL. 7-day TTL. |
| `related kind=drug_shortages` | Which of this manufacturer's drugs are in shortage right now — status, availability, reason, first posted? | manufacturer `Fresenius Kabi USA, LLC` + status=Current → 146 records (update_date desc; availability per presentation). | Company match goes through openFDA's normalized layer (`manufacturer_name.exact` phrase); parent/subsidiary not merged — narrow by NDC/application_number before persisting. Zero hits is a valid answer (upstream 404 → empty set). Daily-grade → 24h TTL. |
| `related kind=artg_register` | Which therapeutic products does this sponsor hold on the Australian register — product name, ARTG id, type, PI/CMI docs? | sponsor `Sun Pharma ANZ Pty Ltd` → 100+ ARTG entries (first page, OpenDocument detail links). | Sponsor is the Australian marketing accountability entity (quoted-phrase exact match); name-only edge — cross-source joins need name normalization. HTML SearchView face (first `accept:'text'` provider); page cap 100, `--skip` continues; has_more is a full-page heuristic. Zero hits is a valid answer. 24h TTL. |
| `related kind=mis_manufacturers` | Which Australian manufacturing sites hold a TGA licence, and since when? | state `QLD` → licence list (Alphapharm Pty Ltd, MI-26112004-LI-000238-1, issued 1991-10-21). | One-shot 444-licence register (single JSON view); Licence Number × Manufacturer ID dual keys; state filter client-side. 24h TTL. |

---

## 7. Errors

The CLI form emits `400 <explanation>` with exit code 2; the HTTP form maps onto the closed error-code set of [api.md](api.md) §8 (`undeclared_field` / `bad_operator` / `bad_value` / `record_kind_unknown` / `cursor_invalid` / `limit_out_of_range`…), the same code table on both sides. The four third-party capability error codes (`thirdparty_*` / `capability_unavailable` / `resolve_kind_unknown`) are in api.md §9.4 — the upstream family exits 1, the usage family exits 2.

healthcare-specific errors 〔planned — to land with the side wiring / red-line outlet implementation; not in effect today〕:
- `side_required` (search called without `side`) — in a multi-regime domain, side is mandatory, not optional
- `side_value_conflict` (identifier type does not match the side, e.g. `npi` under side=cn) — strong keys have a side affiliation
- `personal_data_redacted` (a requested field hits the §11-4 red line) — returned after the payload is auto-stripped (the stripping behavior already runs at the pipeline layer; the error code is not implemented)

---

## 8. Data freshness and honesty statements

- Row-level `source.observed_at` = the observation time of that record; qualifications are **list snapshots** (a given year's list is in the store, not a live qualification status).
- `qualification.status='有效'` is a **list-scope statement** (on the current list), with no annual inspection and no follow-up — expiry/revocation dynamics are not tracked.
- **Zero healthcare rows in db**: before P0 ingestion, all P1 endpoints run in staging-scan form with `source.backend=staging` marked honestly (do not misread it as the production store).
- **Side boundaries stated honestly**: the fact that CN hospitals have no USCC is marked as-is, with no auto-alignment; US subjects having no uscc is a non-ingestion, not a data defect; cross follows the "declare the alignment ceiling honestly" rule with **no bypass** — FDA rows have no uscc and are not auto-merged (healthcare.md §5.3).
- Coverage numbers evolve with collection; the live `--facets` distribution is authoritative, and this document's snapshots carry their dates.

---

## 9. Online service layer (omnihub v2.3, live)

> **Positioning statement**: §1-§8 are this repository's lead-discovery retrieval contract (P1 CLI / P2 HTTP design draft); this section records **another service track already live** — the omnihub-side v2.3 healthcare domain (storage + HTTP + MCP). The two tracks share **the same data source** (this repository's lake source files → the omnihub import face) but run **separate interface paradigms**: the omnihub faces are resource-style read faces (GET + query-parameter filters + cursor pagination) plus an async import face, and do not implement the three verbs / Filter DSL / T-layer aggregation; they target agent/MCP consumption scenarios. Whether the two tracks converge is a later decision; this document only registers the as-built state truthfully.

### 9.1 Topology and authentication

| Layer | As-built (2026-10-16) |
|---|---|
| Service | omnihub (healthcare sub-domain mounted in-process; released to the test environment) |
| HTTP face | `/v1/{cn,us}/*` read faces + `/v1/import/*` import faces (§9.3/§9.4); subject JWT auth (caller subject token) |
| MCP face | test environment `https://mcp.test.omnimay.com/mcp` (streamable-HTTP, OAuth browser authorization), 29 healthcare tools (§9.5), tools/list totals 112 (incl. other domains such as company/dealcenter) |
| Legacy-name compat | `/v1/drug/*` → 301 permanent redirect to `/v1/cn/drug/*` (query string preserved; withdrawn after a six-month window) |

### 9.2 Eight storage tables (DDL summary, omnihub_db)

**Common column group** (every table except import_job):

| Column | Type | Notes |
|---|---|---|
| `uuid` | BINARY(16) PK | row identity (presented as hex externally by MCP/HTTP) |
| `source_id` + `source_row_key` | VARCHAR(64)/VARCHAR(255), **UNIQUE(source_id, source_row_key)** | idempotent dual key: re-importing the same key counts as duplicated, no rewrite |
| `raw_payload` / `raw_provenance` | JSON | full source-site fields + provenance (batch/file/anchor) — the "evidence is traceable" storage layer |
| `valid_from` / `valid_to` / `status` | DATE/DATE/VARCHAR(32) | row lifecycle |
| `created_at` / `updated_at` | DATETIME | |

Table by table (only typed columns specific to each table are listed; indexes in parentheses):

| Table | Semantics | Typed specific columns | Indexes |
|---|---|---|---|
| `healthcare_institution` | Medical institution subject (single table; license/rating current values typed, change history in raw) | `country_code` CHAR(2) · `name` VARCHAR(512) · `institution_kind` VARCHAR(32) · `region` · `license_no` · `rating_level` · `address` | (institution_kind, region) |
| `fact_approval_row` | Regulatory issuance facts, **3-in-1** (drug approval + device registration certificate + device trade license) | `country_code` · `license_no` · `product_kind` VARCHAR(16) (drug/device) · `qtype` (approval/clearance…) · `holder_uuid` BINARY(16)? · `applicant_name` · `product_name` · `approve_date` · `expire_date` · `license_status` | (country_code, product_kind, qtype); license_no |
| `fact_pricing_row` | Pricing and procurement facts, **3-in-1** (drug price + device price + procurement win) | `country_code` · `qtype` five kinds (nrdl/neml/procurement/medicare/…) · `product_ref`/`product_name` · `subject_uuid`?↔`subject_name` (dual-column anchor in pairs) · `project_name` (procurement batch; UC-H4's three axes all land as columns) · `region` · `price` NUMERIC(20,4) · `currency` CHAR(3) | (country_code, qtype); subject_uuid; project_name |
| `fact_trial_row` | Clinical trial study level (locations stored as a JSON array, no separate table; facility alignment writes back locations[*].facility_uuid) | `country_code` · `nct_id` · `title` VARCHAR(1024) · `phase` · `trial_status` (trial business status, a separate column from the row-lifecycle status) · `sponsor_uuid`?↔`sponsor_name` · `conditions` JSON (array of raw indication text) · `start_date` · `locations` JSON | (country_code, trial_status); nct_id; **MySQL 8.0.17+ multi-valued index** (locations->'$[*].facility_uuid' CAST ARRAY, guard-rebuilt at database creation) |
| `risk_event_row` | Negative events, **single table** | `country_code` · `qtype` seven kinds (recall / administrative_penalty / disqualified / judgement / adverse_event_summary / sanctions / inspection) · `scope` VARCHAR(16) · `event_date` · `subject_uuid`?↔`subject_name` · `product_ref`↔`product_name` · `severity` · `region` | (country_code, qtype, event_date) |
| `subject_identifier` | Subject external-identifier historical snapshots (NPI/USCC/registration-number cross-year trajectory; L1 merge anchor) | `country_code` · `subject_uuid`? · `id_type` · `id_value` | (id_type, id_value); subject_uuid |
| `edge_row` | Relationship assertion edges, **2-in-1** (subject↔subject + product↔subject) | `country_code` · `left_uuid`? · `object_type` VARCHAR(16) · `right_uuid`? · `rel_type` VARCHAR(64) (clinical_trial_sponsor / research_funding / payment…; payment detail kept only in raw) | (left_uuid, rel_type); (right_uuid, rel_type) |
| `import_job` | Async import job ledger (**no uk_src_row**, id BIGINT auto-increment PK) | `status` (queued/running/done/failed) · `source_id` · `sub` · `country_code` · `payload` (raw NDJSON, resumable on restart; no separate queue table) · `total_lines`/`accepted`/`duplicated`/`rejected` · `error_summary` JSON | (status, id) |

### 9.3 HTTP v1 read faces (cn/us built symmetrically, `/v1/{c}` prefix)

> For the parameter-level reference for direct production calls (base URL/auth/per-endpoint parameter tables/envelope/error codes/known limits), see §10.

| Endpoint | operation_id | Filter parameters (besides cursor/limit, default 20) |
|---|---|---|
| `GET /v1/{c}/drug/approvals` (+`/{uuid}`) | `{c}.healthcare.drug.approvals.list/get` | qtype · license_no (exact) · holder_uuid (hex) · applicant_name (contains) · product_name (contains) |
| `GET /v1/{c}/device/approvals` (+`/{uuid}`) | `{c}.healthcare.device.approvals.list/get` | same as above (product_kind=device fixed) |
| `GET /v1/{c}/pricing/rows` (+`/{uuid}`) | `{c}.healthcare.pricing.list/get` | qtype · region · product_name · subject_name (contains) · project_name (equality) · subject_uuid (hex) |
| `GET /v1/{c}/risk/events` (+`/{uuid}`) | `{c}.healthcare.risk.events.list/get` | qtype · subject_uuid · subject_name · product_name · date_from/date_to |
| `GET /v1/{c}/hospital/institutions` (+`/{uuid}`) | `{c}.healthcare.hospital.list/get` | kind (hospital/pharmacy) · region · name (contains) |
| `GET /v1/{c}/clinical-trials/studies` (+`/{uuid}`) | `{c}.healthcare.trials.list/get` | trial_status · nct_id · sponsor_uuid · sponsor_name · condition (contains, matched against the conditions JSON array) |
| `GET /v1/{c}/aggregate/timelines` | `{c}.healthcare.aggregate.timelines` | **only** date_from/date_to (no limit/filters); counts aggregated by month × table × qtype — doubles as a data-freshness inspection face |

Unified response envelope: `{"items":[…], "limit":N, "next_cursor":"…|null"}`; rows carry all typed columns + `raw` (the raw_payload verbatim).

### 9.4 Import contract (write face)

```
POST /v1/import/batch?source=<source id>&sub=<optional subset>   synchronous: body=NDJSON, one {"source_row_key":"…","raw_payload":{…}} per line
                                                      returns accepted/duplicated/rejected counts + per-line receipts
POST /v1/import/jobs?source=&sub=                     async: same body; 201 → {"job_id":N,"status":"queued"}
GET  /v1/import/jobs/{job_id}                         poll for the terminal state (done/failed + four counts + error_summary)
```

- **Server-side typed extraction**: `config/field_mappings/<source (/ → __)>.json` gives, per column, a candidate list of `$`-paths + type coercion (decimal/date); raw_payload lands in the store verbatim. Example (cn/smpaa): `product_name←$.item/$.品名`, `subject_name←$.winner/$.中选企业`, `price←$.amount (decimal)`, `valid_from←$.publish_date (date)`.
- **Routing source of truth** `config/import-routes.json` (source → table/qtype/country; sub sub-routes divert and sub enters the source_row_key prefix):

| source | Table | qtype / notes |
|---|---|---|
| `cn/cde` | fact_approval_row | approval (drug); sub `cde-clin` → fact_trial_row |
| `cn/nhsa` | fact_pricing_row | nrdl (2025-edition medical-insurance drug list) |
| `cn/neml` | fact_pricing_row | neml (essential-medicines list; **no typed price** — the list itself carries no price semantics) |
| `cn/smpaa` | fact_pricing_row | procurement (centralized-procurement win) |
| `cn/nmpa-approval` | fact_approval_row | approval (drug) |
| `us/clinicaltrials` | fact_trial_row | — |
| `us/fda-inspections` | risk_event_row | inspection |
| `us/cms` | fact_pricing_row | medicare; sub `pdc-quality` → healthcare_institution |
| `us/nih-reporter` | edge_row | rel_type=research_funding |
| `us/nppes` | healthcare_institution | — |
| `us/openfda` | risk_event_row | main route recall; sub: core/recall=recall, enforcement=administrative_penalty, extra/drug-event=adverse_event_summary, maude-summary=adverse_event_summary (scope=device) |
| `us/openpayments` | edge_row | rel_type=payment (detail kept only in raw, red line) |
| `us/orangebook` | fact_approval_row | clearance (drug) |
| `us/purplebook` | fact_approval_row | clearance (drug) |

- **Hard red-line gates** (code layer): the openfda `label`/`maude` subs are rejected wholesale (labeling filing obligations, healthcare.md §11-2); pricing-face rows with dac:/fa: prefixes are excluded at the storage layer.
- **Idempotency**: UNIQUE(source_id, source_row_key) — re-importing the same key counts as duplicated; the `sub` prefix (e.g. `enforcement:d216rd-…`) participates in the key.

### 9.5 MCP tool face (29 tools, registered in the test environment)

**24 country faces** (cn/us symmetric, `{c}.healthcare.` prefix): drug/device approvals × list/get, pricing × list/get, risk.events × list/get, hospital × list/get, trials × list/get, aggregate.timelines — all 13 for us; **11 for cn** (cn's drug.approvals.\* is deliberately unregistered, covered by the legacy-name pair, see below). **3 import faces**: `import.healthcare.batch` / `import.healthcare.jobs.create` (MCP adapter single-item form) / `import.healthcare.jobs.get`. **2 legacy-name pairs**: `drug.approval.search` / `drug.approval.get` — equivalent coverage of the CN drug-approval read faces (avoiding a same-name semantic fork with `cn.healthcare.drug.approvals.*`); the current search parameter surface = qtype/license_no/product_name/cursor/limit (**applicant_name not registered** — company-based queries need paginated local filtering or the HTTP face; known gap).

### 9.6 Data state and known boundaries (2026-10-16)

- **All real data, the test generation zeroed out**: Σ ~2,146 rows = 1,596 pre-existing (trial 100 / pricing 535 / institution 200 / risk 191 / approval 370 / edge 200) + 550 from the five new lake-source files added 10-16 (pricing 330: nhsa/neml/smpaa 110 each; approval 220: nmpa-approval/orangebook 110 each). source_row_key generations: `d215:N` (migration generation) / `d216rd-*` (lake-source generation).
- **The empty CN institution face is by design**: the source list has no CN institution source; the US institution face (nppes+cms) has a real 200 rows.
- Medical-insurance (nrdl) / essential-medicines (neml) list rows carry no price column value — the lists carry no price semantics; the centralized-procurement (procurement) price is joined from the win-results table × appendix-2 demand-quantity table on "product name + company prefix".
- `subject_uuid` alignment is not fully backfilled (the name column lands first); cross-side alignment still follows the §8 ceiling position.
- The delta versus this repository's staging (2.84M rows) = a publish/ingest cadence difference: the omnihub side is precision-fed source by source per use case, not a full mirror.

---

## 10. Direct hub REST call reference (26 production read faces, parameter level)

> **Positioning**: a **parameter-level reference for direct production calls** to the read faces of the omnihub service track registered in §9 (v2.3) — base URL, auth, per-endpoint query parameters, response envelope, error shapes, known limits. §9.3 is the endpoint summary table; this section is the expanded version; where the two disagree, this section prevails (it is the product of a line-by-line check against source-code anchors).
> **Truth source**: the omnihub `origin/develop` (=bdf0b92, the d216 live face) source code — routes/parameters/envelope/auth always follow the source; every `file:line` anchor in this section was re-checked read-only against that version's git objects.
> **Production-contact statement**: writing this section added zero new production requests; the recorded live probes are only 3 read-only GETs (`/health` 200 ×1, uncredentialed read-face 401 shapes ×2, probes on record 2026-10-21). Any example response body below not marked "verified live on record" is derived from source-code semantics (not replayed against production).
> **Credential discipline**: examples always use the environment variable `$HUB_SUBJECT_TOKEN` as a placeholder; token acquisition/storage belongs to the caller; this document carries no real credentials.

> **SDK status statement (read first to avoid misreading)**: the agentdata Python SDK's search/read three-verb path is **not yet connected to the medical production store** — this section describes **direct calls** to the hub REST and does not change the SDK's status; connecting the SDK to the real store and gateway deployment are a separate future project (unscheduled), and this section leaves an anchor for that future integration. Callers holding a subject token can call the hub.omnimay.com read faces **directly today** per this section.

### 10.1 Read-face list (26 faces) and base URL

Base URL (production): `https://hub.omnimay.com`. The cn/us faces are generated by the same route factory (country.py:26-30) and are **fully isomorphic in parameters/envelope/errors/auth shape**; the only differences: the path prefix (`/v1/cn` or `/v1/us`), the row filter `country_code` (`CN`/`US`, country.py:20,29), and the `country_code` values in response rows.

| # | Domain | list endpoint (one each for cn/us) | get endpoint (one each for cn/us) | Source anchor |
|---|---|---|---|---|
| 1-4 | Drug approvals | `GET /v1/{c}/drug/approvals` | `GET /v1/{c}/drug/approvals/{uuid}` | country.py:36-82 |
| 5-8 | Device approvals | `GET /v1/{c}/device/approvals` | `GET /v1/{c}/device/approvals/{uuid}` | same as above (product_kind=device) |
| 9-12 | Risk events | `GET /v1/{c}/risk/events` | `GET /v1/{c}/risk/events/{uuid}` | country.py:88-118 |
| 13-16 | Medical institutions | `GET /v1/{c}/hospital/institutions` | `GET /v1/{c}/hospital/institutions/{uuid}` | country.py:124-143 |
| 17-20 | Clinical trials | `GET /v1/{c}/clinical-trials/studies` | `GET /v1/{c}/clinical-trials/studies/{uuid}` | country.py:149-179 |
| 21-24 | Pricing/procurement | `GET /v1/{c}/pricing/rows` | `GET /v1/{c}/pricing/rows/{uuid}` | country.py:186-224 |
| 25-26 | Monthly aggregates | `GET /v1/{c}/aggregate/timelines` (no get) | — | country.py:230-237 |

(`{c}` ∈ `cn`/`us`; each row ×2 countries = 26 faces.)

**Faces excluded from this section**:

- The three `/v1/import/*` import endpoints (synchronous batch / async jobs / job status, §9.4) are **operations import faces** and carry no external read-face semantics. Note: the `import_face_public` temporary public switch **acts only on the import faces** (app.py:135-136); the cn/us read faces are structurally unaffected by that flag (app.py:127-133 assembly comments make this explicit), and their 401 shape is undisturbed by it.
- Legacy-name compat: `GET /v1/drug/*` → **301** → `/v1/cn/drug/*` (query string preserved; redirects.py:16-21; six-month transition window), same auth as the read faces (app.py:241-253). New integrations must go straight to `/v1/cn/`; do not rely on the legacy name.
- `GET /health` (composite root path, not under `/v1`): unauthenticated health check (app.py:220); the verified on-record response is `{"status":"ok","components":{...,"healthcare":"ok"}}`.

### 10.2 Authentication (common to all 26 faces)

The cn/us read faces are assembled wrapped in `CompanyAuthMiddleware` (app.py:118-145 `_healthcare_face_app`; mounted at `/v1/cn`, `/v1/us`, app.py:266-286), sharing the same settings and signature-verification key as the company domain — **a single source of truth for auth semantics** (deps.py:1-5).

**Usage**: every request carries `Authorization: Bearer <subject JWT>`.

**Token requirements** (company/auth.py:185-253 validation chain):

| Item | Requirement | Source anchor |
|---|---|---|
| Algorithm | RS256 (deployments may configure ES256/EdDSA) | company/config.py:61 |
| Required claims | `iss`/`aud`/`sub`/`iat`/`exp`/`jti` — all six present; any one missing is a 401 | auth.py:206 |
| Issuer/audience | `iss`, `aud` (=company-domain audience) compared against deployment-side configuration | auth.py:203-204 |
| Clock drift | ±60s leeway (**this is drift tolerance, not token duration**) | auth.py:39,205 |
| Token duration | `exp-iat ≤ subject_max_ttl_seconds`: **default 300s, configurable cap 3600s** | company/config.py:62 `Field(default=300, ge=1, le=3600)` |
| Subject shape | `<namespace>:<org>:<user>` (user subject; namespace is deployment-configured) | auth.py:35 |
| Length | `sub`/`jti` ≤128 characters | auth.py:38,227-230 |
| Duplicate claim names | rejected (401) | auth.py:198 |
| service subjects | `service:`-prefixed subjects **always 403** (the company domain has no machine contract face; deny-by-default) | auth.py:158-161,278-284 |

**Rate limiting**: read methods (GET/HEAD) are not subject to the rate limiter — only write methods (POST/PATCH/PUT) go through the per-subject token bucket + body cap (auth.py:164-181); all 26 faces in this section are GET.

**Token acquisition**: belongs to the caller side (the omnimay ecosystem OAuth exchange chain); this section constrains only the hub-side validation semantics and makes no promises about the issuance flow.

**401/403 shapes** (the caller's troubleshooting baseline):

- 401: `{"error":"unauthorized","message":"A valid Bearer token is required."}` — missing/bad/expired Bearer, missing claims, over TTL, duplicate claim names (**verified live on record with uncredentialed direct calls**, 2 cases); carries the response header `www-authenticate: Bearer realm="company"` (auth.py:268-275).
- 403: `{"error":"forbidden","message":"Service subjects are not accepted."}` — `service:`-prefixed subjects (source-code semantics, auth.py:278-284).

### 10.3 Pagination and response envelope (common to the six-domain lists)

- **Envelope**: `{"items": [...], "limit": <int>, "next_cursor": <string|null>}` (repo `_envelope`:139-146; serialization `_wrap` read_service.py:114-120). `limit` echoes the request value; `next_cursor=null` means the last page.
- **Ordering**: `(created_at DESC, uuid DESC)` dual-key keyset descending (repo:133) — **descending by ingestion time, not by business date**.
- **limit**: int, 1..100, **default 20** (country.py:22,52 etc.); out of range (0 or >100) → 422 (see §10.6).
- **cursor**: an opaque string = base64url(json `{"v":1,"c":<created_at iso>,"u":<uuid hex>}`) (repo:42-47); to page, pass the `cursor` parameter back verbatim — no parsing needed. A malformed string/version mismatch/empty string → 400 `CURSOR_INVALID` (repo:50-60; errors.py:42-45). A cursor pointing at a deleted row is harmless (strict less-than comparison, repo:63-71).
- **get endpoints have no envelope**: they return the single row object directly (country.py:70-79 etc.).
- **timelines has no pagination**: just `{"items":[...]}` (read_service.py:170-171); undeclared parameters (incl. limit/cursor) are silently ignored (see §10.12).

### 10.4 Common row-object skeleton (six domains)

Every row (items elements in lists and get response bodies are isomorphic) always carries the following skeleton fields in addition to domain-specific fields (read_service.serialize_row:78-105):

| Field | Type | Notes |
|---|---|---|
| `uuid` | string (32-hex) | row primary key; the get path segment and the cursor `u` segment |
| `source_id` | string | data-source identifier (e.g. `us/orangebook`, `cn/smpaa`; source list in the §9.4 routing table) |
| `source_row_key` | string | within-source row key (combined with source_id as the ingestion idempotency key) |
| `country_code` | string | `"CN"`/`"US"` (jurisdiction-side country, **not the subject's registration country**) |
| `status` | string | row lifecycle status (each source's raw value, not a business state machine — business status is in each domain's specific columns) |
| `valid_from`/`valid_to` | string|null | ISO dates (`YYYY-MM-DD`) |
| `created_at`/`updated_at` | string|null | ISO timestamps |
| `raw` | object | source-payload projection: recursively strips person-name/contact keys (red line ⑤); where a source-level whitelist exists, only whitelisted keys pass through (red line ⑥, redlines.py:116-137). The OpenPayments source is strictly whitelisted (only nine keys: record_id/program_year/payment_amount/total_amount_of_payment_usdollars/number_of_payments_included_in_total/date_of_payment/form_of_payment_or_nature_of_payment/teaching_hospital_name/applicable_manufacturer_name); all other sources default to raw passthrough with PII stripped only (import_router.py:144-154) |

### 10.5 Controlled vocabularies (data-side value domains, vocab.py)

| Vocabulary | Value domain | Source anchor |
|---|---|---|
| APPROVAL_QTYPES (approval qtype) | `approval` / `clearance` / `listing` | vocab.py:35 |
| PRICING_QTYPES (pricing qtype) | `hangwang` / `nrdl` / `neml` / `procurement` / `medicare` | vocab.py:39 |
| RISK_QTYPES (risk qtype, seven kinds) | `recall` / `administrative_penalty` / `disqualified` / `judgement` / `adverse_event_summary` / `sanctions` / `inspection` | vocab.py:22-32 |
| Institution kind (served set) | `hospital` / `clinic` / `pharmacy` / `laboratory` / `regulator` / `other` (`individual` never served as a category, red line ②) | vocab.py:13-15 + redlines.py:46 |
| Risk scope | `drug` / `device` / `subject` | vocab.py:42 |
| severity | `high` / `medium` / `low` | vocab.py:68 |

> **Query-side semantics (important)**: the vocabularies are **data-side value domains** (write-boundary validation); read-face queries do **not** vocabulary-validate `qtype`/`kind` etc. — they execute as plain equality filters (the repo list clauses); an out-of-domain value returns an **empty set**, not a 422. Business-side code should discipline itself to the value domains above.

### 10.6 Error-code master table (shape common to all 26 faces)

The HealthcareError family's response body is uniformly `{"code","message","hints":[],"details":{}}` (errors.py:27-33; exception_handlers.py:20-24).

| HTTP | code / shape | Trigger | Response-body shape |
|---|---|---|---|
| 401 | `{"error":"unauthorized","message":"A valid Bearer token is required."}` | missing/bad/expired Bearer, missing claims, over TTL, duplicate claim names | **verified live on record**; carries the response header `www-authenticate: Bearer realm="company"` (auth.py:268-275) |
| 403 | `{"error":"forbidden","message":"Service subjects are not accepted."}` | `service:`-prefixed subject | source-code semantics (auth.py:278-284) |
| 404 | `HEALTHCARE_NOT_FOUND` | get: uuid does not exist / path uuid not hex / uuid belongs to the other country's face / (institutions) individual-category rows / (pricing) us/cms `dac:`/`fa:` red-line rows | `{"code":"HEALTHCARE_NOT_FOUND","message":"<资源> 不存在: <uuid>","hints":[],"details":{}}`; per face `<资源>` is approval/risk event/institution/study/pricing row (country.py:73,117,142,178,223) |
| 400 | `CURSOR_INVALID` | cursor malformed string / version mismatch / empty string / cursor uuid segment not hex | `{"code":"CURSOR_INVALID","message":"cursor 无效或已过期"（或"cursor uuid 段无效"）,"hints":[],"details":{}}` (repo:50-70) |
| 400 | `PARAM_INVALID` (raised directly) | a query-side hex-uuid parameter is not hex (holder_uuid/subject_uuid/sponsor_uuid) | `{"code":"PARAM_INVALID","message":"<参数名> 须为 32 位 hex uuid","hints":[],"details":{}}` (repo:81-87). Note: hex but not 32 characters does not error — it returns an empty set as no match |
| 422 | `PARAM_INVALID` (validator) | a **declared parameter** fails validation: limit outside 1..100, a date parameter not an ISO date | `{"code":"PARAM_INVALID","message":"请求参数校验失败","hints":[],"details":{"errors":[{"loc":["query","limit"],"type":"...","msg":"..."}]}}` (exception_handlers.py:26-43) |
| 422 | `PRODUCT_KIND_MISMATCH` | approvals get only: the uuid exists but does not belong to that product_kind face (a drug row hit on the device face or vice versa) | `{"code":"PRODUCT_KIND_MISMATCH","message":"approval uuid 存在但不属于该 product_kind 面: <uuid>","hints":[],"details":{}}` (country.py:74-78; errors.py:54-59). The client can retry on the other face |
| 500 | nested error shape | unclassified server-side exception | `{"error":{"code":"INTERNAL_ERROR","message":"internal error"}}` (exception_handlers.py:45-51 — note the envelope shape differs from the other codes) |

### 10.7 Drug/device approvals `/v1/{c}/{drug|device}/approvals`

Same table `fact_approval_row`, with the face fixed by `product_kind` (drug/device); source anchors country.py:36-82 (routes), repo list_approvals:188-219 (filter clauses).

**list endpoint** (`GET /v1/{c}/drug/approvals`, `GET /v1/{c}/device/approvals`; operation_id `{c}.healthcare.{drug|device}.approvals.list`) query parameters (country.py:44-52):

| Parameter | Type | Default | Semantics / controlled vocabulary |
|---|---|---|---|
| `qtype` | string | none | equality filter; value domain = APPROVAL_QTYPES (approval/clearance/listing, §10.5; out-of-domain value = empty set) |
| `license_no` | string | none | approval/registration number **exact equality** (repo:208-209) |
| `holder_uuid` | string (32-hex) | none | holder-subject uuid equality; non-hex → 400 PARAM_INVALID (repo:81-87,210-213) |
| `applicant_name` | string | none | holder raw text **contains** (repo:214-215; `%`/`_` taken literally, wildcard injection prevented) |
| `product_name` | string | none | product name raw text **contains** (repo:216-217) |
| `cursor` | string | none | §10.3 common cursor |
| `limit` | int 1..100 | 20 | §10.3 common pagination |

Response row fields = §10.4 skeleton + the following specific columns (read_service.py:28-38):

| Field | Type | Notes |
|---|---|---|
| `license_no` | string|null | approval/registration number |
| `product_kind` | string | `"drug"`/`"device"` |
| `qtype` | string | §10.5 vocabulary |
| `holder_uuid` | string|null (32 hex) | holder-subject anchor (null until alignment is backfilled; then applicant_name is the name anchor) |
| `applicant_name` | string|null | holder raw text |
| `product_name` | string|null | product name raw text |
| `approve_date` | string|null | ISO date |
| `expire_date` | string|null | ISO date |
| `license_status` | string|null | license status raw text (**readable but not filterable** — no corresponding query parameter, see §10.14) |

Error codes: the full common table in §10.6; this domain's get additionally has 422 `PRODUCT_KIND_MISMATCH` (cross-face). Example:

```bash
# list (from page 2 on, pass back the previous page's next_cursor)
curl -sS "https://hub.omnimay.com/v1/cn/drug/approvals?qtype=approval&limit=20" \
  -H "Authorization: Bearer $HUB_SUBJECT_TOKEN"
```

**get endpoint** (`GET /v1/{c}/{drug|device}/approvals/{uuid}`; operation_id `{c}.healthcare.{drug|device}.approvals.get`; country.py:66-79): no query parameters (extra parameters silently ignored); **no envelope** — returns the single row object directly (fields as above); 404 `HEALTHCARE_NOT_FOUND` (message=`approval 不存在: <uuid>`; a non-hex uuid / a uuid belonging to the other country's face is likewise 404) + the 422 cross-face code. Example: `curl -sS "https://hub.omnimay.com/v1/us/drug/approvals/<uuid32hex>" -H "Authorization: Bearer $HUB_SUBJECT_TOKEN"`.

### 10.8 Risk events `/v1/{c}/risk/events`

Table `risk_event_row` (seven qtypes in one table); source anchors country.py:88-118, repo list_risks:313-344 (date clauses :339-342).

**list endpoint** (operation_id `{c}.healthcare.risk.events.list`) query parameters (country.py:92-99):

| Parameter | Type | Default | Semantics / controlled vocabulary |
|---|---|---|---|
| `qtype` | string | none | equality; value domain = RISK_QTYPES seven kinds (§10.5) |
| `subject_uuid` | string (32-hex) | none | involved-subject uuid equality; non-hex → 400 |
| `subject_name` | string | none | involved subject raw text contains |
| `product_name` | string | none | involved product raw text contains |
| `date_from` | date (`YYYY-MM-DD`) | none | `event_date >= date_from` (closed interval, repo:339-340) |
| `date_to` | date (`YYYY-MM-DD`) | none | `event_date <= date_to` (closed interval, repo:341-342) |
| `cursor`/`limit` | — | — | §10.3 common |

> date_from/date_to are the **only date-interval parameters among the 26 faces** (no other domain has any date filtering, see §10.14).

Response row fields = skeleton + specific columns (read_service.py:61-71):

| Field | Type | Notes |
|---|---|---|
| `qtype` | string | seven-kind vocabulary |
| `scope` | string | `drug`/`device`/`subject` |
| `event_date` | string|null | ISO date |
| `subject_uuid` | string|null (32 hex) | involved-subject anchor |
| `subject_name` | string|null | involved subject raw text |
| `product_ref` | string|null | product reference key |
| `product_name` | string|null | involved product raw text |
| `severity` | string|null | `high`/`medium`/`low` (un-normalized raw values stay in raw) |
| `region` | string|null | region raw text |

Error codes: §10.6 common (this domain's get has no 422-specific code). Example:

```bash
# uncredentialed shape (verified live on record):
# GET /v1/us/risk/events?limit=1 → 401
# {"error":"unauthorized","message":"A valid Bearer token is required."}

# with credentials (derived from source-code semantics):
curl -sS "https://hub.omnimay.com/v1/us/risk/events?qtype=recall&date_from=2024-01-01&date_to=2024-12-31&limit=50" \
  -H "Authorization: Bearer $HUB_SUBJECT_TOKEN"
```

**get endpoint** (`GET /v1/{c}/risk/events/{uuid}`; country.py:113-118): no query parameters; single row object without envelope; 404 (message=`risk event 不存在: <uuid>`).

### 10.9 Medical institutions `/v1/{c}/hospital/institutions`

Table `healthcare_institution`; source anchors country.py:124-143, repo list_institutions:148-168. **Red line ②**: `individual` (NPPES Type-1 individual practitioners) is never served as a category — the list filter and the get 404 use the same criterion (repo:74-78 `_served_institution_clause`).

**list endpoint** (operation_id `{c}.healthcare.hospital.list`) query parameters (country.py:128-132):

| Parameter | Type | Default | Semantics / controlled vocabulary |
|---|---|---|---|
| `kind` | string | none | equality; served value domain = hospital/clinic/pharmacy/laboratory/regulator/other (§10.5; passing `individual` = empty set — that category is never served) |
| `region` | string | none | equality; **value = source raw text** (CN side: Chinese province names verbatim; US side: state names as-is; non-matches honestly return an empty set) |
| `name` | string | none | institution name contains |
| `cursor`/`limit` | — | — | §10.3 common |

Response row fields = skeleton + specific columns (read_service.py:20-27):

| Field | Type | Notes |
|---|---|---|
| `name` | string | institution name |
| `institution_kind` | string | §10.5 value-domain raw text |
| `region` | string|null | region raw text |
| `license_no` | string|null | license number |
| `rating_level` | string|null | rating |
| `address` | string|null | address (structured address detail is in raw, e.g. the NPPES address segments) |

Error codes: §10.6 common; get returns 404 for individual-category rows (red line ② semantics — not the misleading "does not exist"; that category is unserved by design). Example:

```bash
curl -sS "https://hub.omnimay.com/v1/us/hospital/institutions?kind=hospital&region=California&limit=100" \
  -H "Authorization: Bearer $HUB_SUBJECT_TOKEN"
```

**get endpoint** (`GET /v1/{c}/hospital/institutions/{uuid}`; country.py:138-143): no query parameters; single row object without envelope; 404 (message=`institution 不存在: <uuid>`; individual-category rows take the same shape).

### 10.10 Clinical trials `/v1/{c}/clinical-trials/studies`

Table `fact_trial_row` (study level); source anchors country.py:149-179, repo list_trials:277-306.

**list endpoint** (operation_id `{c}.healthcare.trials.list`) query parameters (country.py:153-161):

| Parameter | Type | Default | Semantics / controlled vocabulary |
|---|---|---|---|
| `trial_status` | string | none | trial business status equality (source raw status words, e.g. recruiting; the hub imposes no vocabulary constraint) |
| `nct_id` | string | none | NCT id exact equality (e.g. `NCT01234567`) |
| `sponsor_uuid` | string (32-hex) | none | sponsor uuid equality; non-hex → 400 |
| `sponsor_name` | string | none | sponsor raw text contains |
| `condition` | string | none | indication contains — **substring match against the conditions JSON column text** (repo:302-304; not a controlled-vocabulary match — controlled terms (e.g. MeSH) are not guaranteed to hit) |
| `cursor`/`limit` | — | — | §10.3 common |

> No `phase` parameter (known limitation, §10.14).

Response row fields = skeleton + specific columns (read_service.py:50-60):

| Field | Type | Notes |
|---|---|---|
| `nct_id` | string|null | ClinicalTrials.gov identifier |
| `title` | string|null | trial title |
| `phase` | string|null | phase raw text (readable but not filterable) |
| `trial_status` | string|null | trial business status (a separate column from the skeleton `status` — the latter is the row lifecycle) |
| `sponsor_uuid` | string|null (32 hex) | sponsor anchor |
| `sponsor_name` | string|null | sponsor raw text |
| `conditions` | array|null | indication raw-text array |
| `start_date` | string|null | ISO date |
| `locations` | array|null | trial-site JSON array (includes facility_uuid anchors after alignment) |

Error codes: §10.6 common. Example:

```bash
curl -sS "https://hub.omnimay.com/v1/us/clinical-trials/studies?condition=diabetes&trial_status=recruiting&limit=20" \
  -H "Authorization: Bearer $HUB_SUBJECT_TOKEN"
```

**get endpoint** (`GET /v1/{c}/clinical-trials/studies/{uuid}`; country.py:174-179): no query parameters; single row object without envelope; 404 (message=`study 不存在: <uuid>`).

### 10.11 Pricing/procurement `/v1/{c}/pricing/rows`

Table `fact_pricing_row` (five qtypes; UC-H4's three procurement-axis filters); source anchors country.py:186-224, repo list_pricing:226-257. **Red line ③**: `dac:`/`fa:`-prefixed rows of the `us/cms` source are never served (repo:96-105 `_served_pricing_clause`; list + get share the criterion).

**list endpoint** (operation_id `{c}.healthcare.pricing.list`) query parameters (country.py:190-205):

| Parameter | Type | Default | Semantics / controlled vocabulary |
|---|---|---|---|
| `qtype` | string | none | equality; value domain = PRICING_QTYPES (hangwang/nrdl/neml/procurement/medicare, §10.5; `neml` = essential-medicines list admission, price left empty) |
| `region` | string | none | equality; **value = source raw text** (CN side: Chinese province names verbatim) |
| `product_name` | string | none | variety raw text contains (variety axis) |
| `subject_name` | string | none | winning/pricing company raw text contains (company axis) |
| `project_name` | string | none | procurement batch **equality** (batch axis; unlike the name-type parameters, not contains) |
| `subject_uuid` | string (32-hex) | none | winning-company uuid equality (the post-alignment query channel); non-hex → 400 |
| `cursor`/`limit` | — | — | §10.3 common |

> No date parameters at all (`valid_from`/`valid_to` readable but not filterable, see §10.14).

Response row fields = skeleton + specific columns (read_service.py:39-49):

| Field | Type | Notes |
|---|---|---|
| `qtype` | string | five-kind vocabulary |
| `product_ref` | string|null | variety reference key |
| `product_name` | string|null | variety raw text |
| `subject_uuid` | string|null (32 hex) | winning/pricing subject anchor |
| `subject_name` | string|null | winning/pricing company raw text |
| `project_name` | string|null | procurement batch |
| `region` | string|null | region raw text |
| `price` | string|null | **a string** (Decimal→str to avoid JSON floating-point distortion, read_service.py:92-93; empty-price list-type rows such as neml are null) |
| `currency` | string|null | three-letter currency |

Error codes: §10.6 common. Example:

```bash
curl -sS "https://hub.omnimay.com/v1/cn/pricing/rows?qtype=hangwang&project_name=<batch name raw text>&limit=100" \
  -H "Authorization: Bearer $HUB_SUBJECT_TOKEN"
```

**get endpoint** (`GET /v1/{c}/pricing/rows/{uuid}`; country.py:219-224): no query parameters; single row object without envelope; 404 (message=`pricing row 不存在: <uuid>`; red-line-③ excluded rows take the same shape).

### 10.12 Monthly aggregates `/v1/{c}/aggregate/timelines`

Monthly counts over the four fact tables by their primary date column; source anchors country.py:230-237, repo timelines:376-421 (date-column mapping :369-374).

**Endpoint** (operation_id `{c}.healthcare.aggregate.timelines`) query parameters (country.py:234-235, **only these two**):

| Parameter | Type | Default | Semantics |
|---|---|---|---|
| `date_from` | date (`YYYY-MM-DD`) | none | lower bound of the count window (against the effective date, ≥) |
| `date_to` | date (`YYYY-MM-DD`) | none | upper bound of the count window (against the effective date, ≤) |

> **Undeclared parameters are silently ignored**: this endpoint declares no `limit`/`cursor`/any filter parameter — passing them neither errors nor takes effect (FastAPI silently ignores undeclared query parameters; a 422 occurs only when a declared parameter fails validation, e.g. the six faces' `limit>100`).

Response (no pagination envelope, items only; read_service.py:170-171):

```json
{
  "items": [
    { "month": "2024-06", "table": "fact_approval_row", "qtype": "approval", "count": 1234 },
    { "month": "2024-06", "table": "fact_trial_row", "qtype": null, "count": 56 }
  ]
}
```

| Field | Notes |
|---|---|
| `month` | `"YYYY-MM"` (MySQL date_format / SQLite strftime same shape, repo:487-492) |
| `table` | one of the four fact tables: `fact_approval_row`/`fact_pricing_row`/`fact_trial_row`/`risk_event_row` |
| `qtype` | count for that month, table and qtype; `fact_trial_row` has no qtype column and is **always null** (a single monthly row) |
| `count` | row count |

Counting basis: each table's primary date column = approvals→`approve_date`, pricing→`valid_from`, trials→`start_date`, risk→`event_date`; **when the primary date column is empty, fall back to the ingestion date** (the date value of `created_at`, repo:392); ordering by (month, table, qtype) (repo:420). The country is fixed by the path prefix. Error codes: §10.6 common (invalid date format → 422). Example:

```bash
curl -sS "https://hub.omnimay.com/v1/cn/aggregate/timelines?date_from=2024-01-01&date_to=2024-12-31" \
  -H "Authorization: Bearer $HUB_SUBJECT_TOKEN"
```

### 10.13 Coverage matrix for the 26 faces (per-endpoint declaration that all seven elements are present)

The seven elements = path / method / query-parameter table (incl. type/default/controlled vocabulary) / response envelope and per-endpoint fields / error shapes / auth requirements / examples. For cn/us isomorphic endpoints the seven elements are carried by their section (factory-isomorphic, §10.1); the matrix checks each endpoint as follows:

| # | Endpoint | Path | Method | Parameter table | Envelope/fields | Error shape | Auth | Example | Section |
|---|---|---|---|---|---|---|---|---|---|
| 1 | cn drug approvals list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.7 |
| 2 | cn drug approvals get | ✓ | ✓ | ✓ (no parameters declared) | ✓ | ✓ | ✓ | ✓ | §10.7 |
| 3 | us drug approvals list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.7 |
| 4 | us drug approvals get | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.7 |
| 5 | cn device approvals list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.7 |
| 6 | cn device approvals get | ✓ | ✓ | ✓ | ✓ | ✓ (incl. cross-face 422) | ✓ | ✓ | §10.7 |
| 7 | us device approvals list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.7 |
| 8 | us device approvals get | ✓ | ✓ | ✓ | ✓ | ✓ (incl. cross-face 422) | ✓ | ✓ | §10.7 |
| 9 | cn risk events list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (incl. on-record 401) | §10.8 |
| 10 | cn risk events get | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.8 |
| 11 | us risk events list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (incl. on-record 401) | §10.8 |
| 12 | us risk events get | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.8 |
| 13 | cn institutions list | ✓ | ✓ | ✓ | ✓ | ✓ (incl. red-line-② 404) | ✓ | ✓ | §10.9 |
| 14 | cn institutions get | ✓ | ✓ | ✓ | ✓ | ✓ (incl. red-line-② 404) | ✓ | ✓ | §10.9 |
| 15 | us institutions list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.9 |
| 16 | us institutions get | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.9 |
| 17 | cn trials list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.10 |
| 18 | cn trials get | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.10 |
| 19 | us trials list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.10 |
| 20 | us trials get | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.10 |
| 21 | cn pricing list | ✓ | ✓ | ✓ | ✓ | ✓ (incl. red-line-③ 404) | ✓ | ✓ | §10.11 |
| 22 | cn pricing get | ✓ | ✓ | ✓ | ✓ | ✓ (incl. red-line-③ 404) | ✓ | ✓ | §10.11 |
| 23 | us pricing list | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.11 |
| 24 | us pricing get | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.11 |
| 25 | cn timelines | ✓ | ✓ | ✓ (only two parameters + silent-ignore declaration) | ✓ (items shape) | ✓ | ✓ | ✓ (incl. on-record 401) | §10.12 |
| 26 | us timelines | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | §10.12 |

### 10.14 Known limitations (filter gaps presented as-is)

The gaps below are the hub's state presented truthfully (**no omnihub changes, no client-side fallbacks, zero invented parameters**). Integrators should work around them per the table; never append any "not filterable" dimension from the table to the URL (undeclared parameters are silently ignored and yield unfiltered full results — see §10.12).

| Category | Gap | Caller workaround |
|---|---|---|
| Combinators | no `_or` (OR) / `_not` (NOT) combinations — all parameters AND together | when a union is needed, issue multiple requests and merge yourself |
| Multi-value | no multi-value parameters (`any` semantics) | same as above — request per value and merge; note there is no count endpoint (next row) |
| Counting | **no count endpoint** — the list envelope has no `total_matched`, only the `next_cursor` chain | for totals, paginate fully and accumulate, or approximate with timelines monthly counts (month × table × qtype granularity only) |
| facets | no distribution/aggregate filter endpoint (facets-type parameters unservable) | approximate the time dimension with timelines |
| Date ranges | only the risk face has `date_from`/`date_to`; approvals (approve_date), pricing (valid_from/valid_to), trials (start_date) are **all not date-filterable** | filter client-side after retrieval |
| Amounts | pricing-face `price` is not filterable (no range parameter) | filter yourself after retrieval |
| Status | license statuses other than `license_status`/skeleton `status`/trial `trial_status` are not filterable (trial_status itself is) | judge yourself after reading rows |
| Source dimension | `source_id` is not filterable (multiple sources merged under one qtype, e.g. clearance=orangebook+purplebook) | filter yourself on the row-level `source_id` field |
| Institution profile | institution `taxonomy`/`ownership` have no parameters (visible in raw, not filterable) | read raw and filter yourself |
| Trial phase | `phase` has no parameter (rows readable, not filterable) | filter after retrieval |
| Subject dimensions | no person/product subject rows (red lines ②④ by design); no subjects read endpoint, no strong-key (npi/uscc) lookup endpoint | reach subject dimensions via the fact faces' `*_uuid`/`*_name` anchors |
| Edge data | `edge_row` (OpenPayments payments / NIH funding) has **no read face** (import write channel only) | annual-aggregate-type needs are currently unservable |
| Provenance projection | `raw_provenance` (batch/file anchors/sha256) does not enter read responses; `observed_at` can only be approximated by `updated_at` | evidence-traceability needs to be assessed separately |
| Registration country | no "subject registration country" filter (country = jurisdiction-side country ≠ registration country) | judge yourself after reading rows |

### 10.15 Source-code anchor index (for per-endpoint verification)

| Fact | Source anchor (omnihub@origin/develop bdf0b92, git objects read-only) |
|---|---|
| 26-face routes/parameters/defaults | src/healthcare/transport/http/country.py:20-239 |
| cn/us face assembly and auth wrapping | src/healthcare/transport/http/cn.py / us.py (7 lines each); src/omnihub/app.py:118-145,266-286 |
| Filter clauses (six domains) | src/healthcare/repositories/healthcare_repository.py:148-344 |
| Cursor/keyset/envelope | same file:42-60 (`_CURSOR_VERSION=1` at :39),63-71,133,139-146 |
| timelines aggregation | same file:369-374 (date-column mapping),376-421 (aggregation body),487-492 (monthly expression) |
| Row serialization/raw projection | src/healthcare/services/read_service.py:19-120 |
| Red lines ②③ / PII / whitelist | src/healthcare/domain/redlines.py (SERVED_INSTITUTION_KINDS:46/CMS_BANNED_*:47-48/PERSON_PII_*:53-100/project_raw_for_api:116-137) |
| Controlled vocabularies | src/healthcare/domain/vocab.py (per-table anchors in §10.5) |
| Error codes / HTTP mapping | src/healthcare/domain/errors.py:8-91 (file is 91 lines long); exception_handlers.py:20-51 |
| Auth (incl. service 403 / TTL) | src/company/auth.py:35-39,158-161,185-253,268-284; src/company/config.py:57-62 |
| OpenPayments whitelist nine keys | src/healthcare/config/field_mappings/us__openpayments.json (raw_projection_whitelist) |
| Legacy-name 301 | src/healthcare/transport/http/redirects.py:16-21 |

---

## Changelog

- **2026-10-23 (5)**: **§6.1 adds `related kind=artg_register` / `mis_manufacturers` (Wave 6, the Australian TGA eBS public faces)** — the ARTG drug/device register's 97,988 product rows × **the Sponsor company edge** (the Australian marketing accountability entity) + the MIS manufacturer licence register's 444 licences. Upstream `ebs.tga.gov.au/ebs/ANZTPAR/PublicWeb.nsf` keyless (a Domino .nsf site cluster); the search face SearchView is an **HTML surface** (first case of the core's new `accept:'text'` channel — a 2xx HTML body is the expected payload, not a WAF challenge; the provider layer parses it itself); a Query quoted phrase = exact (Sun Pharma ANZ verified 100/100), a bare term = AND across all fields; the sort-icon td at the head of each row is not a data column and must be stripped; Count=100/page, Start=skip continues. The MIS face JSON view (`?ReadViewEntries&outputformat=json`) — the state column's real name is **SiteState** (the portal's ColTitles is a false front). Host split: ebs fully reachable, www.tga.gov.au dead from this egress (gating is per host, not per domain). The enumeration face (raw bulk line) Count≤15000 (100k → 500 OOM). §6.2 bilingual use cases gained two rows. Design card: healthcare-thirdparty-api-design.md §4.10.
- **2026-10-23 (4)**: **§6.1 adds `related kind=drug_shortages` (Wave 5, the openFDA drug-shortage face)** — manufacturer/drug name/status → FDA shortage record rows (a supply-risk event stream, closing the pipeline × safety × supply trio); upstream `api.fda.gov/drug/shortages.json` keyless, the search face's three segments AND-combinable (manufacturer `openfda.manufacturer_name.exact:"…"` normalized-layer exact phrase — a bare token scatters / drug name `generic_name:"…"` phrase / `status:` verified enum Current|Resolved|To Be Discontinued); **zero hits = HTTP 404 `No matches found!` is a valid answer** (openFDA convention; the op's `notFound:[404]` is converted to an empty set at this layer, not cached); limit cap 100, `sort=update_date:desc`; both company-edge columns kept (`company_name` the registered manufacturer vs `manufacturers` the normalized manufacturer). **The openFDA deferral ruling does not apply** (the 2026-10-16 deferral covers only the locally ingested FAERS/MAUDE faces — shortages is not harvested locally, a positive example of "open when an incremental need touches it"). §6.2 bilingual use cases gained a row (Fresenius Kabi Current 146 records, real-machine values). Design card: healthcare-thirdparty-api-design.md §4.9.
- **2026-10-23 (3)**: **§6.1 adds `resolve kind=mesh_term` (Wave 3, the MeSH controlled-vocabulary face)** — drug/disease name → MeSH descriptor master record (UI + preferred term + synonym pool + qualifiers/seealso anchors); upstream id.nlm.nih.gov RDF lookup API keyless; the search parameter verified live as **label** (passing term/descriptor both just gets 400 "label must not be empty" — this round's real-machine pitfall is on record), match closed set contains|exact|startswith; each term resolves in a fixed two hops (lookup + preferred-record details); the vocabulary ships annually → 30-day TTL; zero hits = an honest answer (brand-name → generic-name retry hint). Both stacks landed the same day (Python 0.1.12); §6.2 bilingual use cases gained a row (aspirin→D001241 real-machine values).

- **2026-10-21 (3)**: **adds §10 "Direct hub REST call reference" (d217, AC2)** — a parameter-level reference for direct production calls to the omnihub service-track (§9) read faces: base URL `https://hub.omnimay.com`, 26 read faces (six-domain list/get + timelines) with per-face query-parameter tables, auth (subject Bearer six claims/RS256/TTL default 300s cap 3600s/service subjects 403), the pagination envelope (limit 1..100 default 20/dual-key keyset/cursor shape), the row skeleton (uuid/source_id/country_code/raw PII stripping and whitelist projection), controlled vocabularies (approvals/pricing/risk seven kinds/institution kind), the error-code master table (401/403/404/400 CURSOR_INVALID/400+422 PARAM_INVALID/422 PRODUCT_KIND_MISMATCH/500), the per-endpoint coverage matrix and 14 known-limitation rows (no _or/_not, no multi-value, no count endpoint, no facets, dates only on the risk face, price not filterable, etc.) + the source-code anchor index (omnihub@bdf0b92 verified per file:line); the chapter opens with the **SDK three-verb-not-yet-connected status statement** (to prevent misreading, and to leave an anchor for future integration) — callers holding a subject token can call directly today per §10. The header note and §9.3 gained §10 pointers; `docs/domains/api.md` unchanged (the hub REST resource-style read faces and the three-verb contract run on separate tracks, no conflict).
- **2026-10-20 (2)**: **§6.1 adds `resolve kind=device_eu` (Wave 2, the EUDAMED EU-counterpart face)** — EU DI → EUDAMED public device catalogue master record (manufacturer SRN + authorised-representative SRN edges, risk class, market status; keyless, execution=local, TTL 7 days); the endpoint is SPA same-origin REST (undocumented), stability registered under two-point observation (2026-10-17 recipe-book probe + 2026-10-20 recheck) with an exit mechanism attached; the upstream `primaryDi` unindexed cold path ~50s (op timeout 90s/retries 0) entered the boundary column as-is; **empty pages are not cached as authoritative** (a transient server-side miss that poisoned the 7-day TTL — real harm on 2026-10-20 → the provider discards the entry and refetches once on an empty read; landed in both stacks); §6.2 bilingual use cases gained the row in sync (DI 00889024163300 → Zimmer/Biomet SRN edge real-machine values).
- **2026-10-20**: **adds §6.2 enrichment use cases (English truth source + Chinese derived translation — per the 2026-10-20 "English truth source for API/docs faces, Chinese derived" ruling, new domain-page content goes bilingual first)** — six capabilities, each with user question/verified example/boundary; the examples are all real-machine values from the design doc's verification records (atorvastatin→RxCUI 83367, ATC C10AA05, AFF 37,108, RECRUITING totalCount 247, NUCARE setid 5d5977a5); the GUDID egress WAF environment fact and the trials zero-hit rerun hint (0 ≠ no trials) entered the boundary column. Complements the §5 corpus-face use cases (UC-H1~H9); consumes no UC numbers.
- **2026-10-19**: **aligned with the implementation (user ruling: documentation follows the implementation)** — the header status note now reads "P1 has landed (domain-spec/engine/agentdata SDK in service)"; `side` is marked 〔planned〕 throughout (api.md §7.2 contract-first, engine/SDK not wired — §2 gained a runnable-today equivalent example: jurisdiction carried via the qtype prefix + the row-level country field); the multi-regime sub-resource endpoints `/healthcare/{cn,us}/holder/*`, `GET /company/{id}/facts`, and the three specific error codes (side_required/side_value_conflict/personal_data_redacted) are marked 〔planned〕; §4.1 aligned with the spec — `hospital_ownership`→`ownership`, `announced_month`→`plan_month`, a `province` row added, `source/source_observed_at` marked 〔planned〕, `device_class`/`medical_specialty`/`establishment_type`/`facility_address_country` moved to §4.2 pending enablement; the facets recommendation now follows the spec's facets_fields; §4.3 screen now reflects the current five states (six after P0) + the identifiers.type closed set aligned with the spec; §1.1 staging total refreshed to 7,577,069 (2026-10-15, the old per-source snapshot superseded after the 5.18M UDI batch entered); §2/§5 example qtypes switched to the current closed value set (fda_drug_ndc/us_ob_product/cn_drug_trade_license/cn_hospital_grade), and the returned sample dropped the side key; §5 gained a row-count snapshot-period note.
- **2026-10-16 (2)**: **§6.1 rewritten to follow the public-chapter upgrade (converged over two codex adversarial rounds)** — the mechanism source of truth promoted to [api.md](api.md) §9 (domain-capability axis / execution dichotomy / row shape / error codes / declarative caching), and this section became **this domain's capability register** (provider/execution/TTL per row; all providers keyless and local — **rate limiting is the user's own**, the SDK lock default = the highest politeness tier, downward-adjustable only); the enrichment row provenance switched to the new shape `source={provider, execution, from_cache, observed_at|fetched_at}` (dropping `backend:"cache"` per the api.md §9.3 ruling); the error codes expanded to four with their HTTP mappings fixed (`thirdparty_upstream_unavailable` 502 / `thirdparty_rate_limited` **503** not 429 / `capability_unavailable` 503 / `resolve_kind_unknown` 400); `request_id` emitted with the CLI; the §7 error section gained the third-party-code pointer.
- **2026-10-16 (3)**: **adds §9 online service layer (the omnihub v2.3 live face)** — eight-table storage DDL summary (common column group + per-table typed columns/indexes/MySQL multi-valued index note), the HTTP v1 read-face seven-endpoint table (cn/us symmetric + filter parameters), the import contract (batch/jobs dual forms + field_mappings server-side extraction + the import-routes fourteen-source routing table + hard red-line gates), the MCP 29-tool face (24 country + 3 import + 2 legacy-name pairs; cn drug.approvals deliberately unregistered, search missing applicant_name a known gap), the data state (real Σ≈2,146, test generation zeroed, empty CN institutions = by design); §9 opens with the two-track positioning statement (lead-discovery retrieval contract vs the omnihub resource-style service track, same data source, separate paradigms, convergence to be decided later).
- **2026-10-16**: **establishes the third-party real-time-query external section §6.1** — `resolve` (drug name→RxCUI **P0** / device DI→GUDID P1) + `evidence` (Europe PMC literature evidence **P0**), two domain-level extension endpoints entering the external contract; zero-credential statement (not BYOK, users need bring no key); cache TTLs marked honestly (immutable keys permanent / device DI 7 days / `from_cache:true`); error codes expanded by three (`thirdparty_upstream_unavailable` / `thirdparty_rate_limited` / `resolve_kind_unknown`); the on-trigger family (WHO GHO / Canada DPD / Japan e-Stat) enters the table in the same shape when opened. Internal design source of truth healthcare-thirdparty-api-design.md v3 (same-day three-round endpoint live tests: GUDID v2 200 / DPD 200 / GHO 200 / e-Stat auth gate consistent).
- **2026-10-15**: **cross-reference section numbers aligned to the post-split master structure** (fixing reference drift from the MR!30 split, 14 places): `§13-§15`→`§10-§12`, `§14.4 red line`→`§11-4 red line`, `§15.1/§15.2-x/§15.3-x`→`§12.1/§12.2-x/§12.3-x`; one straggler in the master's §1.6 fixed in sync (`§11 external interfaces`→`§9 external API reference`). Historical changelog entries keep the old numbers (established convention).
- **2026-10-14 (24)**: **establishes the external-edition API reference healthcare-api.md** — consumer-facing content extracted from healthcare.md §9-§12 into its own document: controlled filter fields (§4) / the use-case matrix (§5) / external interfaces and the T-layer contract (§6); §1 gained the multi-regime partition statement (CN / US / cross three-side compliance frameworks + primary user questions, api.md §7); §2 quick start gained the `--side` mandatory example and the multi-regime-exclusive sub-resources (`/healthcare/cn/holder/procurement` UC-H4 / `/healthcare/us/holder/payment` UC-H9) — the asymmetry deliberate, read ignores side and aggregates across sides via target.id; §7 error codes gained the healthcare-specific ones (`side_required` / `side_value_conflict` / `personal_data_redacted`); §8 gained the db-zero-healthcare-rows and side-boundary honesty statements. healthcare.md master trimmed §9-§12 in sync, with a pointer to healthcare-api.md and this changelog entry added (twenty-three → twenty-four shifted).
