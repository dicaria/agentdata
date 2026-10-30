# Healthcare Domain API Reference (external edition)

> **Audience**: external integrators / downstream consumers (pharma companies / medical representatives / CROs / consulting firms, etc.). This document is the external reference for the healthcare domain query interfaces — it covers only the contract and data reality, not pipeline internals.
> The internal design source of truth remains healthcare.md (§1-§8 boundaries/sources/fact model/quality gates, §10-§12 commercial/compliance/backlog) and [api.md](api.md) (the cross-domain contract).
> Transport forms: P1 = CLI (every command in this document runs as-is); P2 = HTTP `/v1/healthcare/*` (request/response semantics unchanged, see api.md §8).
> Domain type: **multi-regime (api.md §7)** — the CN / US / cross sides differ markedly in record_kind sets, field sets, compliance frameworks, and primary user questions; the `side` parameter is a §7.2 contract **designed ahead of wiring — engine/SDK not yet connected** (passages marked 〔planned〕 in this document are in exactly that state).
> Status: 2026-10-19 edition aligned with the implementation — P1 has landed (domain-spec / engine / agentdata SDK in service, staging-scan form); `side` and the multi-regime sub-resource endpoints are contract-first, and until wired every related passage is marked 〔planned〕.
> Split relationship: healthcare.md is the master record (internal source of truth); healthcare-api.md is the external edition (single-page API reference for consumers); healthcare-storage-api-design.md is the storage design draft (parallel to this document).
> Online service channels: this domain's hosted data travels two channels — the **corpus face** (SDK `search`/`read`; contract in §1-§8 + api.md §8; PAT credentials issued by dicaria) and the **hub REST read faces** (§10; production base `https://hub.omnimay.com`; subject-token credentials, callable today by token holders). §10 is the parameter-level direct-call reference.

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
agentdata healthcare search \
  --filter 'qtype=fda_drug_ndc' --filter 'approval_year>=2023' \
  --facets qtype --level tier1

# ② Centralized-procurement wins (UC-H4; the nested-DSL form goes through the HTTP body / Client.search(filters=…))
agentdata healthcare search --record-kind procurement \
  --filter 'project=第12批' --filter 'product_name=复方氨基酸' \
  --filter 'plan_month>=2025-01' --limit 200

# ③ Medical institution roster (UC-H5; institutions listed separately, never mixed into company rosters)
agentdata healthcare search \
  --filter 'subject_kind=institution' --filter 'qtype=cn_hospital_grade' \
  --level tier1

# ④ Subject profile (UC-H7 dual-signal entry; Client.read(target=…) carries the company:<id> form)
agentdata healthcare read --id <subject_id> --level tier2

# ⑤ Batch list screening (first pass over a going-global list; six states returned per row)
agentdata healthcare search --mode screen --input targets.jsonl --level tier1
```

**Multi-regime `side` parameter** 〔planned — api.md §7.2 contract-first, engine/SDK not yet wired; passing `--side` today fails with unknown parameter〕. Until it is wired, jurisdiction is expressed at the field layer:

```bash
# Current equivalent: jurisdiction carried via qtype prefix (cn_* / us_*) + the row-level country field
agentdata healthcare search \
  --filter 'qtype=cn_drug_trade_license' --filter 'status=有效' --limit 100

agentdata healthcare search \
  --filter 'qtype=us_ob_product' --facets company_registration_country --limit 50

# Once the contract is wired (shape below, not runnable yet): --side cn|us|cross; cross follows the "declare the alignment ceiling honestly" rule and every row carries a side annotation
```

What a returned row looks like (the quartet is mandatory: **company + reason + evidence + provenance**):

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

## 9. Hosted channels (as-built)

> **Positioning statement**: §1-§8 are the retrieval contract for this domain's corpus (SDK `search`/`read` + the HTTP search/read of api.md §8). Two hosted channels serve the data; both are live:

| Channel | What it serves | Contract |
|---|---|---|
| **Corpus face** | lead-discovery retrieval: search / read (T1-T3) / screen across the cn/us field partitions of §2 | this document §1-§8 + api.md §8 (endpoints, envelope, PAT auth, error codes) |
| **Hub REST** | resource-style read faces over the medical production store (drug/device approvals, pricing/procurement, risk events, institutions, clinical trials, monthly aggregates), cn/us symmetric | §10 (parameter-level direct-call reference, base `https://hub.omnimay.com`) |

The two channels share the same data lineage but run separate interface paradigms: the hub faces are resource-style GET + query-parameter filters + cursor pagination and do not implement the three verbs / Filter DSL / T-layer aggregation. Whether the two channels converge is a later decision.

---

## 10. Direct hub REST call reference (26 production read faces, parameter level)

> **Positioning**: a **parameter-level reference for direct production calls** to the hosted hub channel's read faces (§9) — base URL, auth, per-endpoint query parameters, response envelope, error shapes, known limits. §10.1 is the face list; this section is the parameter-level expansion; where the two disagree, this section prevails (verified face by face against the live service).
> **Truth source**: the live hub service — routes/parameters/envelope/auth always follow the service's actual behavior; every table in this section was verified against the production faces.
> **Production-contact statement**: writing this section added zero new production requests; the recorded live probes are only 3 read-only GETs (`/health` 200 ×1, uncredentialed read-face 401 shapes ×2, probes on record 2026-10-21). Any example response body below not marked "verified live on record" is derived from source-code semantics (not replayed against production).
> **Credential discipline**: examples always use the environment variable `$HUB_SUBJECT_TOKEN` as a placeholder; token acquisition/storage belongs to the caller; this document carries no real credentials.

> **SDK status statement (read first to avoid misreading)**: the agentdata Python SDK's search/read three-verb path is **not yet connected to the medical production store** — this section describes **direct calls** to the hub REST and does not change the SDK's status; connecting the SDK to the real store and gateway deployment are a separate future project (unscheduled), and this section leaves an anchor for that future integration. Callers holding a subject token can call the hub.omnimay.com read faces **directly today** per this section.

### 10.1 Read-face list (26 faces) and base URL

Base URL (production): `https://hub.omnimay.com`. The cn/us faces are fully isomorphic in parameters/envelope/errors/auth shape; the only differences: the path prefix (`/v1/cn` or `/v1/us`), the row filter `country_code` (`CN`/`US`), and the `country_code` values in response rows.

| # | Domain | list endpoint (one each for cn/us) | get endpoint (one each for cn/us) |
|---|---|---|---|
| 1-4 | Drug approvals | `GET /v1/{c}/drug/approvals` | `GET /v1/{c}/drug/approvals/{uuid}` |
| 5-8 | Device approvals (product_kind=device) | `GET /v1/{c}/device/approvals` | `GET /v1/{c}/device/approvals/{uuid}` |
| 9-12 | Risk events | `GET /v1/{c}/risk/events` | `GET /v1/{c}/risk/events/{uuid}` |
| 13-16 | Medical institutions | `GET /v1/{c}/hospital/institutions` | `GET /v1/{c}/hospital/institutions/{uuid}` |
| 17-20 | Clinical trials | `GET /v1/{c}/clinical-trials/studies` | `GET /v1/{c}/clinical-trials/studies/{uuid}` |
| 21-24 | Pricing/procurement | `GET /v1/{c}/pricing/rows` | `GET /v1/{c}/pricing/rows/{uuid}` |
| 25-26 | Monthly aggregates | `GET /v1/{c}/aggregate/timelines` (no get) | — |

(`{c}` ∈ `cn`/`us`; each row ×2 countries = 26 faces.)

**Faces excluded from this section**:

- The three `/v1/import/*` import endpoints (synchronous batch / async jobs / job status) are **operations import faces** and carry no external read-face semantics. Note: any temporary public-exposure switch on the import faces **acts only on the import faces**; the cn/us read faces are structurally unaffected by that flag, and their 401 shape is undisturbed by it.
- Legacy-name compat: `GET /v1/drug/*` → **301** → `/v1/cn/drug/*` (query string preserved; six-month transition window), same auth as the read faces. New integrations must go straight to `/v1/cn/`; do not rely on the legacy name.
- `GET /health` (composite root path, not under `/v1`): unauthenticated health check; the verified on-record response is `{"status":"ok","components":{...,"healthcare":"ok"}}`.

### 10.2 Authentication (common to all 26 faces)

The cn/us read faces share one auth assembly and one signature-verification configuration — a single source of truth for auth semantics.

**Usage**: every request carries `Authorization: Bearer <subject JWT>`.

**Token requirements**:

| Item | Requirement |
|---|---|
| Algorithm | RS256 |
| Required claims | `iss`/`aud`/`sub`/`iat`/`exp`/`jti` — all six present; any one missing is a 401 |
| Issuer/audience | `iss`, `aud` (compared against the deployment's configured audience) |
| Clock drift | ±60s leeway (**this is drift tolerance, not token duration**) |
| Token duration | `exp - iat` ≤ the configured maximum TTL: **default 300s, configurable cap 3600s** |
| Subject shape | `<namespace>:<org>:<user>` (user subject; namespace is deployment-configured) |
| Length | `sub`/`jti` ≤128 characters |
| Duplicate claim names | rejected (401) |
| service subjects | `service:`-prefixed subjects **always 403** (deny-by-default) |

**Rate limiting**: read methods (GET/HEAD) are not subject to the rate limiter — only write methods (POST/PATCH/PUT) go through the per-subject token bucket + body cap; all 26 faces in this section are GET.

**Token acquisition**: tokens are issued by dicaria under the service agreement; this section constrains only the hub-side validation semantics and makes no promises about the issuance flow.

**401/403 shapes** (the caller's troubleshooting baseline):

- 401: `{"error":"unauthorized","message":"A valid Bearer token is required."}` — missing/bad/expired Bearer, missing claims, over TTL, duplicate claim names (**verified live on record with uncredentialed direct calls**, 2 cases); carries the response header `www-authenticate: Bearer realm="company"`.
- 403: `{"error":"forbidden","message":"Service subjects are not accepted."}` — `service:`-prefixed subjects.

### 10.3 Pagination and response envelope (common to the six-domain lists)

- **Envelope**: `{"items": [...], "limit": <int>, "next_cursor": <string|null>}`. `limit` echoes the request value; `next_cursor=null` means the last page.
- **Ordering**: `(created_at DESC, uuid DESC)` dual-key keyset descending — **descending by ingestion time, not by business date**.
- **limit**: int, 1..100, **default 20**; out of range (0 or >100) → 422 (see §10.6).
- **cursor**: an opaque string = base64url(json `{"v":1,"c":<created_at iso>,"u":<uuid hex>}`); to page, pass the `cursor` parameter back verbatim — no parsing needed. A malformed string/version mismatch/empty string → 400 `CURSOR_INVALID`. A cursor pointing at a deleted row is harmless (strict less-than comparison).
- **get endpoints have no envelope**: they return the single row object directly.
- **timelines has no pagination**: just `{"items":[...]}`; undeclared parameters (incl. limit/cursor) are silently ignored (see §10.12).

### 10.4 Common row-object skeleton (six domains)

Every row (items elements in lists and get response bodies are isomorphic) always carries the following skeleton fields in addition to domain-specific fields:

| Field | Type | Notes |
|---|---|---|
| `uuid` | string (32-hex) | row primary key; the get path segment and the cursor `u` segment |
| `source_id` | string | data-source identifier (e.g. `us/orangebook`, `cn/smpaa`) |
| `source_row_key` | string | within-source row key (combined with source_id as the ingestion idempotency key) |
| `country_code` | string | `"CN"`/`"US"` (jurisdiction-side country, **not the subject's registration country**) |
| `status` | string | row lifecycle status (each source's raw value, not a business state machine — business status is in each domain's specific columns) |
| `valid_from`/`valid_to` | string|null | ISO dates (`YYYY-MM-DD`) |
| `created_at`/`updated_at` | string|null | ISO timestamps |
| `raw` | object | source-payload projection: recursively strips person-name/contact keys (PII red line); where a source-level whitelist exists, only whitelisted keys pass through. The OpenPayments source is strictly whitelisted (only nine keys: record_id/program_year/payment_amount/total_amount_of_payment_usdollars/number_of_payments_included_in_total/date_of_payment/form_of_payment_or_nature_of_payment/teaching_hospital_name/applicable_manufacturer_name); all other sources default to raw passthrough with PII stripped only |

### 10.5 Controlled vocabularies (data-side value domains)

| Vocabulary | Value domain |
|---|---|
| APPROVAL_QTYPES (approval qtype) | `approval` / `clearance` / `listing` |
| PRICING_QTYPES (pricing qtype) | `hangwang` / `nrdl` / `neml` / `procurement` / `medicare` |
| RISK_QTYPES (risk qtype, seven kinds) | `recall` / `administrative_penalty` / `disqualified` / `judgement` / `adverse_event_summary` / `sanctions` / `inspection` |
| Institution kind (served set) | `hospital` / `clinic` / `pharmacy` / `laboratory` / `regulator` / `other` (`individual` never served as a category, red line ②) |
| Risk scope | `drug` / `device` / `subject` |
| severity | `high` / `medium` / `low` |

> **Query-side semantics (important)**: the vocabularies are **data-side value domains** (write-boundary validation); read-face queries do **not** vocabulary-validate `qtype`/`kind` etc. — they execute as plain equality filters; an out-of-domain value returns an **empty set**, not a 422. Business-side code should discipline itself to the value domains above.

### 10.6 Error-code master table (shape common to all 26 faces)

Every error that carries a `code` field shares the response body shape `{"code","message","hints":[],"details":{}}`.

| HTTP | code / shape | Trigger | Response-body shape |
|---|---|---|---|
| 401 | `{"error":"unauthorized","message":"A valid Bearer token is required."}` | missing/bad/expired Bearer, missing claims, over TTL, duplicate claim names | **verified live on record**; carries the response header `www-authenticate: Bearer realm="company"` |
| 403 | `{"error":"forbidden","message":"Service subjects are not accepted."}` | `service:`-prefixed subject | not live-verified; body as shown |
| 404 | `HEALTHCARE_NOT_FOUND` | get: uuid does not exist / path uuid not hex / uuid belongs to the other country's face / (institutions) individual-category rows / (pricing) us/cms `dac:`/`fa:` red-line rows | `{"code":"HEALTHCARE_NOT_FOUND","message":"<资源> 不存在: <uuid>","hints":[],"details":{}}`; per face `<资源>` is approval/risk event/institution/study/pricing row |
| 400 | `CURSOR_INVALID` | cursor malformed string / version mismatch / empty string / cursor uuid segment not hex | `{"code":"CURSOR_INVALID","message":"cursor 无效或已过期"（或"cursor uuid 段无效"）,"hints":[],"details":{}}` |
| 400 | `PARAM_INVALID` (raised directly) | a query-side hex-uuid parameter is not hex (holder_uuid/subject_uuid/sponsor_uuid) | `{"code":"PARAM_INVALID","message":"<参数名> 须为 32 位 hex uuid","hints":[],"details":{}}`. Note: hex but not 32 characters does not error — it returns an empty set as no match |
| 422 | `PARAM_INVALID` (validator) | a **declared parameter** fails validation: limit outside 1..100, a date parameter not an ISO date | `{"code":"PARAM_INVALID","message":"请求参数校验失败","hints":[],"details":{"errors":[{"loc":["query","limit"],"type":"...","msg":"..."}]}}` |
| 422 | `PRODUCT_KIND_MISMATCH` | approvals get only: the uuid exists but does not belong to that product_kind face (a drug row hit on the device face or vice versa) | `{"code":"PRODUCT_KIND_MISMATCH","message":"approval uuid 存在但不属于该 product_kind 面: <uuid>","hints":[],"details":{}}`. The client can retry on the other face |
| 500 | nested error shape | unclassified server-side exception | `{"error":{"code":"INTERNAL_ERROR","message":"internal error"}}` (note the envelope shape differs from the other codes) |

### 10.7 Drug/device approvals `/v1/{c}/{drug|device}/approvals`

Same table `fact_approval_row`, with the face fixed by `product_kind` (drug/device).

**list endpoint** (`GET /v1/{c}/drug/approvals`, `GET /v1/{c}/device/approvals`; operation_id `{c}.healthcare.{drug|device}.approvals.list`) query parameters:

| Parameter | Type | Default | Semantics / controlled vocabulary |
|---|---|---|---|
| `qtype` | string | none | equality filter; value domain = APPROVAL_QTYPES (approval/clearance/listing, §10.5; out-of-domain value = empty set) |
| `license_no` | string | none | approval/registration number **exact equality** |
| `holder_uuid` | string (32-hex) | none | holder-subject uuid equality; non-hex → 400 PARAM_INVALID |
| `applicant_name` | string | none | holder raw text **contains** (`%`/`_` taken literally, wildcard injection prevented) |
| `product_name` | string | none | product name raw text **contains** |
| `cursor` | string | none | §10.3 common cursor |
| `limit` | int 1..100 | 20 | §10.3 common pagination |

Response row fields = §10.4 skeleton + the following specific columns:

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

**get endpoint** (`GET /v1/{c}/{drug|device}/approvals/{uuid}`; operation_id `{c}.healthcare.{drug|device}.approvals.get`): no query parameters (extra parameters silently ignored); **no envelope** — returns the single row object directly (fields as above); 404 `HEALTHCARE_NOT_FOUND` (message=`approval 不存在: <uuid>`; a non-hex uuid / a uuid belonging to the other country's face is likewise 404) + the 422 cross-face code. Example: `curl -sS "https://hub.omnimay.com/v1/us/drug/approvals/<uuid32hex>" -H "Authorization: Bearer $HUB_SUBJECT_TOKEN"`.

### 10.8 Risk events `/v1/{c}/risk/events`

Table `risk_event_row` (seven qtypes in one table).

**list endpoint** (operation_id `{c}.healthcare.risk.events.list`) query parameters:

| Parameter | Type | Default | Semantics / controlled vocabulary |
|---|---|---|---|
| `qtype` | string | none | equality; value domain = RISK_QTYPES seven kinds (§10.5) |
| `subject_uuid` | string (32-hex) | none | involved-subject uuid equality; non-hex → 400 |
| `subject_name` | string | none | involved subject raw text contains |
| `product_name` | string | none | involved product raw text contains |
| `date_from` | date (`YYYY-MM-DD`) | none | `event_date >= date_from` (closed interval) |
| `date_to` | date (`YYYY-MM-DD`) | none | `event_date <= date_to` (closed interval) |
| `cursor`/`limit` | — | — | §10.3 common |

> date_from/date_to are the **only date-interval parameters among the 26 faces** (no other domain has any date filtering, see §10.14).

Response row fields = skeleton + specific columns:

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

**get endpoint** (`GET /v1/{c}/risk/events/{uuid}`): no query parameters; single row object without envelope; 404 (message=`risk event 不存在: <uuid>`).

### 10.9 Medical institutions `/v1/{c}/hospital/institutions`

Table `healthcare_institution`. **Red line ②**: `individual` (NPPES Type-1 individual practitioners) is never served as a category — the list filter and the get 404 use the same criterion.

**list endpoint** (operation_id `{c}.healthcare.hospital.list`) query parameters:

| Parameter | Type | Default | Semantics / controlled vocabulary |
|---|---|---|---|
| `kind` | string | none | equality; served value domain = hospital/clinic/pharmacy/laboratory/regulator/other (§10.5; passing `individual` = empty set — that category is never served) |
| `region` | string | none | equality; **value = source raw text** (CN side: Chinese province names verbatim; US side: state names as-is; non-matches honestly return an empty set) |
| `name` | string | none | institution name contains |
| `cursor`/`limit` | — | — | §10.3 common |

Response row fields = skeleton + specific columns:

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

**get endpoint** (`GET /v1/{c}/hospital/institutions/{uuid}`): no query parameters; single row object without envelope; 404 (message=`institution 不存在: <uuid>`; individual-category rows take the same shape).

### 10.10 Clinical trials `/v1/{c}/clinical-trials/studies`

Table `fact_trial_row` (study level).

**list endpoint** (operation_id `{c}.healthcare.trials.list`) query parameters:

| Parameter | Type | Default | Semantics / controlled vocabulary |
|---|---|---|---|
| `trial_status` | string | none | trial business status equality (source raw status words, e.g. recruiting; the hub imposes no vocabulary constraint) |
| `nct_id` | string | none | NCT id exact equality (e.g. `NCT01234567`) |
| `sponsor_uuid` | string (32-hex) | none | sponsor uuid equality; non-hex → 400 |
| `sponsor_name` | string | none | sponsor raw text contains |
| `condition` | string | none | indication contains — **substring match against the conditions JSON column text** (not a controlled-vocabulary match — controlled terms (e.g. MeSH) are not guaranteed to hit) |
| `cursor`/`limit` | — | — | §10.3 common |

> No `phase` parameter (known limitation, §10.14).

Response row fields = skeleton + specific columns:

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

**get endpoint** (`GET /v1/{c}/clinical-trials/studies/{uuid}`): no query parameters; single row object without envelope; 404 (message=`study 不存在: <uuid>`).

### 10.11 Pricing/procurement `/v1/{c}/pricing/rows`

Table `fact_pricing_row` (five qtypes, three procurement-axis filters). **Red line ③**: `dac:`/`fa:`-prefixed rows of the `us/cms` source are never served (list + get share the criterion).

**list endpoint** (operation_id `{c}.healthcare.pricing.list`) query parameters:

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

Response row fields = skeleton + specific columns:

| Field | Type | Notes |
|---|---|---|
| `qtype` | string | five-kind vocabulary |
| `product_ref` | string|null | variety reference key |
| `product_name` | string|null | variety raw text |
| `subject_uuid` | string|null (32 hex) | winning/pricing subject anchor |
| `subject_name` | string|null | winning/pricing company raw text |
| `project_name` | string|null | procurement batch |
| `region` | string|null | region raw text |
| `price` | string|null | **a string** (string-encoded to avoid JSON floating-point distortion; empty-price list-type rows such as neml are null) |
| `currency` | string|null | three-letter currency |

Error codes: §10.6 common. Example:

```bash
curl -sS "https://hub.omnimay.com/v1/cn/pricing/rows?qtype=hangwang&project_name=<batch name raw text>&limit=100" \
  -H "Authorization: Bearer $HUB_SUBJECT_TOKEN"
```

**get endpoint** (`GET /v1/{c}/pricing/rows/{uuid}`): no query parameters; single row object without envelope; 404 (message=`pricing row 不存在: <uuid>`; red-line-③ excluded rows take the same shape).

### 10.12 Monthly aggregates `/v1/{c}/aggregate/timelines`

Monthly counts over the four fact tables by their primary date column.

**Endpoint** (operation_id `{c}.healthcare.aggregate.timelines`) query parameters (**only these two**):

| Parameter | Type | Default | Semantics |
|---|---|---|---|
| `date_from` | date (`YYYY-MM-DD`) | none | lower bound of the count window (against the effective date, ≥) |
| `date_to` | date (`YYYY-MM-DD`) | none | upper bound of the count window (against the effective date, ≤) |

> **Undeclared parameters are silently ignored**: this endpoint declares no `limit`/`cursor`/any filter parameter — passing them neither errors nor takes effect (FastAPI silently ignores undeclared query parameters; a 422 occurs only when a declared parameter fails validation, e.g. the six faces' `limit>100`).

Response (no pagination envelope, items only):

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
| `month` | `"YYYY-MM"` (MySQL date_format / SQLite strftime same shape) |
| `table` | one of the four fact tables: `fact_approval_row`/`fact_pricing_row`/`fact_trial_row`/`risk_event_row` |
| `qtype` | count for that month, table and qtype; `fact_trial_row` has no qtype column and is **always null** (a single monthly row) |
| `count` | row count |

Counting basis: each table's primary date column = approvals→`approve_date`, pricing→`valid_from`, trials→`start_date`, risk→`event_date`; **when the primary date column is empty, fall back to the ingestion date** (the date value of `created_at`); ordering by (month, table, qtype). The country is fixed by the path prefix. Error codes: §10.6 common (invalid date format → 422). Example:

```bash
curl -sS "https://hub.omnimay.com/v1/cn/aggregate/timelines?date_from=2024-01-01&date_to=2024-12-31" \
  -H "Authorization: Bearer $HUB_SUBJECT_TOKEN"
```

### 10.13 Coverage matrix for the 26 faces (per-endpoint declaration that all seven elements are present)

The seven elements = path / method / query-parameter table (incl. type/default/controlled vocabulary) / response envelope and per-endpoint fields / error shapes / auth requirements / examples. For cn/us isomorphic endpoints the seven elements are carried by their section (§10.1); the matrix checks each endpoint as follows:

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

The gaps below are the hub's state presented truthfully (**no server-side changes, no client-side fallbacks, zero invented parameters**). Integrators should work around them per the table; never append any "not filterable" dimension from the table to the URL (undeclared parameters are silently ignored and yield unfiltered full results — see §10.12).

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
| Subject dimensions | no person/product subject rows (person-level rows are never served, by design); no subjects read endpoint, no strong-key (npi/uscc) lookup endpoint | reach subject dimensions via the fact faces' `*_uuid`/`*_name` anchors |
| Edge data | `edge_row` (OpenPayments payments / NIH funding) has **no read face** (import write channel only) | annual-aggregate-type needs are currently unservable |
| Provenance projection | `raw_provenance` (batch/file anchors/sha256) does not enter read responses; `observed_at` can only be approximated by `updated_at` | evidence-traceability needs to be assessed separately |
| Registration country | no "subject registration country" filter (country = jurisdiction-side country ≠ registration country) | judge yourself after reading rows |