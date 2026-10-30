# company Domain API Reference (External Edition)

> **Audience**: external integrators / downstream consumers. This document is the external reference for the company domain's query interface — contract and data reality only, no pipeline internals.
> The internal design source of truth remains company.md (§9 controlled fields / §10 use cases / §12 CLI) and [api.md](api.md) (cross-domain contract); where this document conflicts with them, the internal source of truth prevails and the conflict is treated as a defect of this document.
> Transport forms: P1 = CLI (every command in this document runs as-is); P2 = HTTP `/v1/company/*` (request/response semantics unchanged, see api.md §8).
> Status: since 2026-10-14. Implementation version pending review (local branch `feat/domain-api-p1`); this document is delivered contract-first.

---

## 1. What This API Covers (Coverage Statement)

| Asset | Scale (verified 2026-10-14) | Notes |
|---|---|---|
| Company entities | **297,973** | Multi-source merge; China registration layer + listing and registry sources across 12 countries/regions |
| Qualification records | **475,298** | China MIIT/MOST system lists (专精特新/小巨人/企业技术中心… 43 types) |
| Disclosure documents | **3,639** | Mainly cninfo prospectuses/annual reports; **inquiry-letter/penalty categories not yet ingested** (§4 honesty boundary) |
| Securities codes | 15,443 | A-share/HK/TW/KR listing mappings (`company_listing`) |
| Company identifiers | 82,232 | Strong keys such as uscc/cik/tw_uscc/us_ticker/kr_brn |

- **Coverage ≠ completeness**: 55 first-seen sources (`first_source` available via facets); registry snapshots are not exhaustive — "company not found" never equals "this company does not exist / carries no risk" (not-covered ≠ no-risk principle).
- Every result row carries `source.observed_at` (when that record was observed); the coverage statement carries per-source observation times.

## 2. Quick Start

```bash
# ① List "专精特新小巨人" enterprises in Hunan, writing CSV to disk (evidence and source columns included)
node harvest/shared/domain-export.mjs company search \
  --filter qtype=专精特新小巨人 --filter province=湖南 --limit 200 --fmt csv -o out.csv

# ② Pull a single company profile (three-tier depth)
node harvest/shared/domain-export.mjs company read --id 1 --level tier2

# ③ Batch-screen a list against the corpus (each line {name, identifiers[], country?})
node harvest/shared/domain-export.mjs company search --mode screen --input leads.jsonl
```

What a returned row looks like (`--fmt jsonl`; the four-tuple is mandatory: **company + reason + evidence + source**):

```json
{"domain":"company","level":"tier1","cursor":"qualification:1","record_kind":"qualification",
 "entity":{"company_id":1476,"company_name":"安诺优达基因科技（北京）有限公司","country":"中国",
           "qtype":"专精特新小巨人","year":"2024","status":"有效","province":"北京","license_no":null},
 "reason":"命中过滤器: qtype=专精特新小巨人 & province=北京",
 "evidence":[{"anchor":"batch=第三批复核(2024)","quote":"安诺优达基因科技（北京）有限公司｜专精特新小巨人｜2024｜有效",
              "url":"https://www.ncsti.gov.cn/kjdt/tzgg/…docx"}],
 "source":{"source":"第三批复核(2024)","observed_at":"2026-09-20"}}
```

## 3. Three Record Types (record_kind)

| record_kind | Semantics | Ordering/cursor |
|---|---|---|
| `company` (default) | Company-entity row; qualification/disclosure conditions are semi-joined onto the entity | id ascending |
| `qualification` | Qualification detail row (one row per qualification, anchored to the entity) | id ascending |
| `disclosure_document` | Disclosure document row | id ascending |

Key point of filter semantics: **multiple fields at the same layer anchor the same row** — `qtype=专精特新小巨人 & province=湖南` hits the little-giant qualification where the enterprise itself is in Hunan; a row is never dragged in merely because the enterprise holds other Hunan qualifications.

## 4. Filter Field Reference

DSL: `eq / any / range(gte,gt,lte,lt) / _not / _or`; **any field not declared in this document returns 400** (to prevent "a typo'd field returning an empty set being mistaken for no data"). CLI: `--filter 'k=v'`, `--filter 'k>=v'`, `--filter 'k=a|b'`; full nesting goes through `--filter-json`.

### 4.1 Entity Layer (record_kind=company)

| Field | Operators | Values and coverage (data reality) |
|---|---|---|
| `company_registration_country` | eq/any | **Raw-value direct match**; three forms currently coexist: Chinese (`中国` 230,277 / `美国` 9,100) + ISO2 (`TW` 42,689 / `KR` 3,966 / `KY` 1,557 / `CN` 534 / `BM` / `HK`…) + English names (`United Kingdom`/`Germany`…). Known dirty value `'` (212 rows, legacy from SEC EX-21 headers). **Recommended: run `--facets company_registration_country` first to see the real distribution before choosing values**; form normalization is on the roadmap |
| `registration_status` | eq/any | Currently **two states**: `active` (263,686, confirmed by registry/authoritative source) / `unverified` (34,287, candidate created from a list or weak source only, entity identity pending verification). **Deregistered/revoked/operating subdivisions are not ingested** — registry-layer snapshots are not exhaustive; do not treat this as an authority on operating status |
| `industry_cn` | eq (contains) | Industry classification: Chinese taxonomy for China-listed entities (金融业/制造业…), SEC SIC English for US-listed entities (`Pharmaceutical Preparations`…); mostly empty for non-listed companies |
| `stock_code` | eq | Securities code → entity (A-share/HK/TW/KR, 15,443 mappings) |
| `us_ticker` | eq | US ticker → entity (7,638 mappings) |
| `established_year` | range | Year of establishment, via attribute `established_on` (12,088 entities currently carry values) |
| `source` | eq | First-seen source code (55 values; `--facets source` for the full set) |

### 4.2 Qualification Layer (record_kind=qualification, or semi-join at the company layer)

| Field | Operators | Values and coverage |
|---|---|---|
| `qtype` | eq/any | **Not a closed set** (expands as new lists are ingested); 43 values currently. Major ones: `专项资金项目`(269,000) `专精特新中小企业(市级)`(72,000) `创新型中小企业(市级)`(47,000) `企业技术中心`(37,000) `专精特新小巨人`(18,000) `先进级智能工厂` `绿色工厂` `制造业单项冠军` `首台套`/`首套件` `零碳工厂`… the full set is whatever `--facets qtype` returns in real time |
| `province` | eq | Province the qualification belongs to (Chinese province names; note uneven list-source coverage — Beijing 12,164 / Hunan 3,212 / Hubei 0 is the current source-coverage picture, not proof those provinces lack companies) |
| `qualification_year` | eq/range | Year string `'2005'`—`'2026'`; range compares lexicographically, which equals chronological order |
| `license_no` | eq | License number (non-empty only for license-carrying list types) |

### 4.3 Disclosure Layer (record_kind=disclosure_document)

| Field | Operators | Values and coverage |
|---|---|---|
| `doc_class` | eq/any | 4 values currently: `招股书`(3,314) `年报`(239) `10-K EX-21`(85) `重大资产重组报告书`(1). **Inquiry-letter/administrative-penalty/market-ban categories are not ingested** — if you need them, do not wait on this layer; the legal domain line is in planning |
| `doc_date` | eq/range | Publication date, ISO (`--filter 'doc_date>=2024-01-01'`) |
| `disclosed_company_id` | eq | Look up disclosures by entity id |
| `kw` | eq | Title keyword (contains). **Currently = title matching**; a full-text layer (FTS5) is on the roadmap |

### 4.4 Planned but Not Yet Open (querying returns 400, by design against misreading)

`revenue_latest`, `employee_count` (financial-scale line retired and being rebuilt), `industry_naics`, `isin`, `issuer_agency`, `issuing_authority`, `effective_from/until`, `risk_*` (inquiry/penalty counts, P2). These fields are named in the internal design document, but the data is not ready — **the 400 is a feature, not a defect**.

## 5. Pagination

- `--limit` 1..1000 (default 50), forcibly bounded; stable ordering + keyset cursor:
  ```bash
  node … company search --filter qtype=企业技术中心 --limit 200
  # → stderr: next_cursor=qualification:20818
  node … company search --filter qtype=企业技术中心 --limit 200 --cursor qualification:20818
  ```
- `total_matched` is an exact count (not an estimate); `next_cursor` is opaque — just pass it through.

## 6. read (Company Profile, Three Tiers)

`node harvest/shared/domain-export.mjs company read --id <company_id> --level tier1|tier2|tier3`

| Tier | Contents |
|---|---|
| tier1 | Business card: name/country/status/industry/securities codes + per-asset counts + evidence anchors + coverage statement |
| tier2 | + all identifiers, listing codes, qualification details (≤200), disclosure details (≤200), attribute facts, aliases |
| tier3 | + full evidence pack (qualification source_url / disclosure url / attribute value_json raw values and provenance, ≤1000) |

## 7. screen (Batch List Screening, Six States)

Input JSONL, one object per line: `{"name":"…", "identifiers":[{"type":"uscc","id":"…"}], "country":"中国" (optional)}`.
identifiers.type is currently a closed set: `uscc / tw_uscc / cik / us_ticker / stock_code / dart_corp_code / kr_brn / kr_jurir_no / ticker`.

| match_status | Meaning | Trigger |
|---|---|---|
| `exact_identifier` | Strong-key exact hit (highest confirmation) | one of identifiers hits an identifier in the corpus |
| `exact_normalized_name` | Normalized full name + country, two-element hit | country given and unique hit |
| `candidate_name_match` | Name candidate (**manual review**) | unique hit with no country given |
| `ambiguous` | Multiple candidates, indistinguishable | several companies share the name |
| `no_match_in_coverage` | No hit within the covered range | country is covered but no match found |
| `not_covered` | Input country outside coverage | that country has 0 records in the corpus |

- A name hit without `country` is **always a candidate** (name + country is what confirms, preventing cross-country mis-merges).
- Every output row carries `coverage_assertion` — **it is a coverage statement, not proof of zero risk**.

## 8. Third-Party Real-Time Queries (enrichment capabilities)

Mechanism source of truth: [api.md](api.md) §9 (domain-capability classification / the `execution` dichotomy / row shape / error codes / the "transparent third-party" boundary) — this section registers this domain's capability list. "Transparent third-party" = uniform at the operation layer (zero credentials / zero URLs / zero rate-limit tuning), truthful at the provenance layer (the official upstream URL is still given); under `local` execution **the rate limit is the user's own** (the SDK locks the default to the highest polite tier; it can only be lowered).

```
POST /company/resolve   {kind:"lei"|"name"|"cert"|"cik"|"ror"|"vat", value, execution?} → LEI identity card / LEI candidates / bank card / SEC registrant card / research-organization record / EU VAT validation
POST /company/related   {kind:"parent"|"fed_awards"|"eu_tenders"|"uk_tenders"|"uk_cf_tenders", value|name, execution?} → ownership control chain / federal award rows / EU TED notices / UK FTS·CF procurement rows
POST /company/fulltext  {q, forms?, dateRange?, execution?}            → filing full-text search hits
```

CLI (`agentdata` — the only CLI since the Node twin was withdrawn on 2026-10-26; three verbs, six examples, all implemented and live-tested):

```
agentdata company resolve --kind lei  --value 5493001KJTIIGC8Y1R12
agentdata company resolve --kind name --value "Bloomberg Finance"
agentdata company resolve --kind cert --value 3510
agentdata company resolve --kind cik  --value 320193
agentdata company related --kind parent     --value 5493001KJTIIGC8Y1R12
agentdata company related --kind fed_awards --name "Lockheed Martin" --limit 5
agentdata company resolve --kind vat --value DE811907980
agentdata company related --kind eu_tenders  --name Siemens --country DEU --limit 5
agentdata company related --kind uk_tenders  --name nhs --updated-from 2026-10-20 --limit 5
agentdata company related --kind uk_cf_tenders --name council --limit 5
agentdata company fulltext --q "rare earth" --forms 10-K --limit 5
```

Installation (wheel, private distribution; CLI and SDK are the same package `agentdata`, the single implementation — single-stack since the Node twin was withdrawn on 2026-10-26; contract in [api.md](api.md) §9):

```bash
pip install agentdata-0.2.1-py3-none-any.whl
```

| Capability | Upstream | provider | execution | Cache TTL | Positioning boundary |
|---|---|---|---|---|---|
| `resolve kind=lei` | GLEIF LEI API (the official distribution of the global LEI system, keyless) | `gleif` | local | 7 days (LEI status/renewal can change) | **Exact LEI normalization** — input an LEI, get the entity identity card (legal name/status/country of registration/managing LOU); **not** name→globally-unique resolution, **not** a company-database substitute |
| `resolve kind=name` | GLEIF (`filter[entity.legalName]`, keyless) | `gleif` | local | 7 days | Name→LEI **candidate reverse lookup** (contains match on legal name, no fuzzy tolerance) — candidates are not authoritative normalization; re-verify with kind=lei before persisting |
| `resolve kind=cert` | FDIC BankFind (api.fdic.gov, keyless) | `fdic-bankfind` | local | 30 days | CERT→US insured-bank institution card (operating/resolved); the financial face goes through the fdic-edos batch line; this face only handles identity current values |
| `resolve kind=cik` | SEC EDGAR submissions (data.sec.gov, keyless) | `edgar-cik` | local | 7 days | CIK→registrant identity card (legal name/former names/ticker·exchange/EIN/SIC industry/filer category); a `fulltext` hit's `ciks[0]` closes here into an identity card — same upstream as edgar-fts but a different face (FTS handles search, this one handles normalization); CIK input is fault-tolerant (bare digits / leading zeros / `CIK` prefix all accepted) |
| `resolve kind=ror` | ROR v2 (api.ror.org, keyless) | `ror` | local | search 7 days / single record 30 days (quarterly releases) | Institution name→research-organization candidates / ROR id→authoritative single record (v2 schema: display name lives in names[ror_display], country goes through locations, top-level name/country are gone; relationships directly exposes parent-institution edges — the research-world counterpart of GLEIF); id fault-tolerant (bare UI / full https://ror.org/… both accepted); ROR only registers research-relevant entities — purely commercial entities go through GLEIF/name |
| `related kind=parent` | GLEIF relationship chains (direct/ultimate parent, keyless) | `gleif` | local | 30 days | The only free official global parent-subsidiary control chain on the web; no declared parent = honest null, not an error |
| `related kind=fed_awards` | USAspending (api/v2, keyless) | `usaspending` | local | 24 hours | Name-matched recipients — **parent-subsidiary groups are not merged**; same-name false hits are for the caller to narrow via CIK/UEI; a correlation lead only, not a contract ledger |
| `resolve kind=vat` | EU VIES (European Commission official VAT validation, keyless) | `vies` | local | 7 days | Whole-string validation with a member-state prefix (EL, not GR); `isValid:false+INVALID` is the legal answer "number invalid", not an error; member states may mask name/address with `---` (honestly recorded as null); `requestIdentifier` is the official audit-trail key; no re-query within TTL (audits needing a fresh trail must use `--no-cache`) |
| `related kind=eu_tenders` | EU TED v3 expert search (keyless) | `ted` | local | 24 hours | buyer prefix match (trailing wildcard; upstream forbids leading wildcards) + ISO-3 country / 8-digit CPV filters; text fields' language dictionaries flattened (eng preferred); the old face's 429 closure does not apply to the v3 search face (overturned 2026-10-23); parent-subsidiary groups are not merged — narrow via VAT/LEI before persisting |
| `related kind=uk_tenders` | UK Find a Tender OCDS (keyless) | `fts` | local | 24 hours | Above the WTO online threshold; the OCDS face has no name-search parameter → **client-side buyer/seller two-sided contains matching is the defined behavior, not a defect** (always fetch a full page of 100, then filter); the window must be whole ISO instants (the SDK auto-completes bare dates); cursor continuation |
| `related kind=uk_cf_tenders` | UK Contracts Finder OCDS (keyless) | `cf` | local | 24 hours | Below-threshold small contracts (complements FTS into the full UK picture); windowless → upstream always empty → default rolling window of the last 7 days; supplier id dual forms GB-COH- (Companies House number, plugs directly into our UK batch line) / GB-CFS-; the real working face is `/Published/Notices/OCDS/Search` (the bare `/api/1.0` path 404s) |
| `fulltext` | SEC EDGAR FTS (efts.sec.gov, keyless) | `edgar-fts` | local | 24 hours | 2001+ filing **full-body** occasional search (the first case admitted under the "full-text search exception"); adsh shares its key with the sec batch-line corpus; not a substitute for bulk harvesting |

- local = executes inside the SDK on the user's machine; no user credentials currently required, still bound by upstream availability and fair-use policies (api.md §9.2).
- The four error codes and their HTTP/CLI mapping: api.md §9.4 (`thirdparty_upstream_unavailable` 502 / `thirdparty_rate_limited` 503 / `capability_unavailable` 503 / `resolve_kind_unknown` 400).
- Follow-up (2026-10-19 keyless-only ruling, design volume §5): **sources requiring account registration/keys do not enter the roadmap** (SAM.gov/FCA/PatentsView/DOL all demoted to watch) — this domain's third-party faces do M1 keyless only; trigger-based follow-ups (wikidata/openownership) are in the same volume. The "keyed tools go hosted" statement no longer applies to this domain (the api.md §9.2 mechanism is retained for the healthcare M2 family).

### 8.1 Use cases (enrichment)

> For each of §8's six capabilities — **user question / live-tested example / boundary** — complementary to the corpus-face use cases (master register company.md §10 C-01~06), not taking C numbers. All examples are values verified on real machines in the design volume/changelog; for the CLI form see the three-verb six examples above (`agentdata` — the only CLI since the Node twin was withdrawn on 2026-10-26).

**Use cases:**

| Capability | User question | Verified example | Boundary |
|---|---|---|---|
| `resolve kind=lei` | One exact key for a regulated counterparty — LEI → legal name, status, country, LOU. | `5493001KJTIIGC8Y1R12` → Bloomberg Finance L.P. (ACTIVE). | Exact-LEI normalization only — not a name→identity oracle, not a company-database substitute. Status/renewal drift → 7-day TTL. |
| `resolve kind=name` | All I have is a name — give me LEI candidates to confirm. | `"Bloomberg Finance"` → candidate legal entities (contains match on legal name). | Candidates, not authoritative identity — confirm via `kind=lei` before persisting; no fuzzy tolerance. |
| `resolve kind=cert` | Is this US bank FDIC-insured, and alive? | CERT `3510` → Bank of America N.A. institution card. | Identity/current-status face only — financial statements live in the fdic-edos batch line. 30-day TTL. |
| `resolve kind=cik` | A CIK off an SEC filing or a fulltext hit → the registrant's identity card: legal & former names, tickers/exchanges, EIN, SIC industry, filer category. | `320193` → Apple Inc. (AAPL·Nasdaq, Large accelerated filer, EIN 942404110, SIC 3571). | Input is fault-tolerant (bare digits / leading zeros / `CIK` prefix all normalize to the 10-digit form). Same upstream as `fulltext` but the normalization face — search goes to edgar-fts, identity closes here. 7-day TTL. |
| `resolve kind=ror` | A research organization by name or ROR id — which institution is this, where, and who is its parent? | `"Huawei"` → 9 candidates, top Huawei Technologies (Poland) (PL, company, parent Huawei Technologies (China)); id `007a2ta87` → authoritative single record. | v2 schema: display name lives in names[ror_display], country in locations — top-level name/country are gone. id input tolerant (bare UI or full https://ror.org/…). ROR only registers research-relevant entities — pure commercial bodies go GLEIF/name. Search 7d / record 30d TTL. |
| `related kind=parent` | Who ultimately controls this entity? | `5493001KJTIIGC8Y1R12` → Bloomberg Finance L.P. → Bloomberg L.P. → Bloomberg Inc. (direct → ultimate). | The only free official global ownership chain. No declared parent = honest `null`, not an error. 30-day TTL. |
| `related kind=fed_awards` | Is this company a live US federal contractor, on which awards? | `"Lockheed Martin"` → award rows (buyer × recipient × amount). | Name-matched recipient — group members are NOT merged; same-name collisions are the caller's to narrow (LEI/UEI). A lead, not a contract ledger. Date window auto-completed to 2007-10-01→today and echoed as `date_range`; 24h TTL. |
| `fulltext` | A one-off full-text question over SEC filings since 2001 — "who discloses rare earth in a 10-K?" | `"rare earth"` + forms `10-K` → 3,144 hits. | Upstream applies a date window only with both ends — give one end and the SDK completes the other (echoed as `date_range`); totals cap at 10,000, flagged via `total_relation:"gte"`. Occasional lookups, not bulk harvest — that is the sec batch line. |

## 9. Errors

CLI form: `400 <message>` with exit code 2; the HTTP form will map to the closed error-code set of api.md §8.3 (`undeclared_field`/`bad_operator`/`bad_value`/`record_kind_unknown`/`cursor_invalid`/`limit_out_of_range`…), both sides sharing the same code table; the four third-party capability error codes are in api.md §9.4.

## 10. Data Timeliness and Honesty Statement

- Row-level `source.observed_at` = when that record was observed; qualifications are **list snapshots** (a given year's list is in the corpus, not a real-time qualification status).
- `qualification.status='有效'` is the **list framing** (on the current list); it is not annually re-examined, not re-visited — expiry/revocation dynamics are not tracked.
- Coverage numbers evolve with harvesting; trust the real-time `--facets` distribution; this document's snapshot is date-stamped.

## Changelog

- 2026-10-23 (7): **§8 adds four Wave 4 capabilities (`resolve kind=vat` + `related kind=eu_tenders/uk_tenders/uk_cf_tenders`, Python 0.1.13)** — the user-named six-source evaluation landed: VIES official VAT validation (INVALID = legal answer, not an error; DE-masked name/address `---` normalized to null; Greece EL not GR passed through); TED v3 expert search **overturned** (the old 429 closure applies only to the old face; POST-only, fields must be eForms enums, leading wildcards forbidden, text fields' language dictionaries flattened with eng preferred); UK FTS OCDS (above the WTO GPA online threshold; dates must be whole ISO instants, auto-completed by the SDK; no name-search parameter → always fetch a full page of 100, client-side buyer/seller two-sided matching); UK CF OCDS (below-threshold, complements FTS; the real working face is `/Published/Notices/OCDS/Search` — the bare `/api/1.0` path 404s, not a block; windowless releases always empty → default rolling window of the last 7 days; supplier id GB-COH/GB-CFS dual forms). The three procurement faces follow the same join discipline as fed_awards (name matching, groups not merged, narrowed via VAT/LEI/GB-COH). Two evaluation items left open: Comext (macro, no entity key → the trade-flows volume, doc-only) and the CH bulk API face (requires a key; the bulk-files face is already on the harvest line, unaffected).
- 2026-10-23 (6): **§8 adds `resolve kind=ror` (Wave 3, ROR research-organization master register)** — institution name→candidates / ROR id→authoritative single record; api.ror.org v2 schema, three pitfalls found live: **top-level name/country are gone** (display name from names[ror_display], country from locations[0].geonames_details), external_ids is an **array**, not a dictionary, and **the single-record endpoint returns a bare record** (no items wrapper; the adapter wraps it to reuse the same mapping); id fault-tolerant in two forms (bare UI `007a2ta87` / full URL); the search face is fixed at 20 per page (no per_page parameter); relationships directly exposes parent-institution edges (the research-world counterpart of GLEIF kind=parent). Dual-stack same-day landing (Python 0.1.12); §8.1 bilingual use-case row added (Huawei 9-candidate live value).

- 2026-10-22 (5): **P1-1 folded in — cik business-address code/readable-name slots (agentdata 0.1.11, fixed on both stacks)** — `state` key renamed `state_or_country` (code slot: CA/P7, foreignStateTerritory merged into the slot) + new `state_or_country_name` (readable-name slot: `stateOrCountryDescription`, ASML P7→Netherlands; foreign rows fall back to `country`=United Kingdom); new `filings_total` (recent is always capped at ~1000 + the sum of `files[].filingCount` historical pages — do not confuse the two numbers with `recent_filings_count`). **Three-entity live correction of the esglegal draft framing** (Shell/Apple/ASML business keys, full table): the `country` key really exists and foreign rows carry real values (Shell=United Kingdom, countryCode X0), so "countryCode always null, drop country" does not hold — country stays. verify.py cik probe upgraded to two slots with dual assertions; master register [api.md](api.md) changelog (20).
- 2026-10-22 (4): **`resolve kind=cik` audit batch C #11 (agentdata 0.1.10, fixed on both stacks)** — ① **P2-9 fixed**: business-address state key corrected — the real upstream key is `stateOrCountry` (the old read of `state` was always null; US company states were lost wholesale, Apple=CA confirmed as real damage); foreign-address state semantics live in `foreignStateTerritory` (Shell plc=DC), and the state slot takes `stateOrCountry ?? foreignStateTerritory`. ② **P3-15 fixed**: `ein='000000000'` foreign-no-EIN sentinel → null; the natural-person face's empty-string value domains (`sic`/`category`/`stateOfIncorporation` `''`) normalized to null. ③ Value domain settled: `entityType` has only the two values {operating, other} — natural persons are also other, not a separate value; `fiscalYearEnd` is MMDD format ('0926'=September quarter end). The pure-mapping split `cardFromUpstream`/`card_from_upstream` is offline-testable (+1 test on each stack); verify live probe "state: CA". (The P1-1 registered-readable-name patch is in flight on a parallel worktree; not re-fixed in this batch.)
- 2026-10-20 (3): **§8 adds `resolve kind=cik` (Wave 2, SEC normalization face)** — CIK→registrant identity card (legal name/former names/ticker·exchange/EIN/SIC industry/filer category/business address + recent filing count and latest filing date); upstream data.sec.gov submissions (keyless, execution=local, TTL 7 days, fair-access 10 req/s with a self-imposed half tier of 5 rps); same upstream as edgar-fts, different face (FTS handles search, this one handles normalization; a `fulltext` hit's `ciks[0]` closes here); CIK input fault-tolerant in three forms (bare digits/leading zeros/`CIK` prefix); Python SDK bumped to 0.1.7 (dual-stack same-day landing, CLI/SDK examples and §8.1 bilingual use-case rows synced — Apple Inc. live value; 0.1.6 had already been taken by the esg/legal twin MR !69 merged earlier, skipped from 0.1.5).
- 2026-10-20 (2): **New §8.1 enrichment use cases (English truth source + derived translation — under the 2026-10-20 ruling "API/docs faces: English truth source, Chinese derived", new content on domain pages goes bilingual first)** — for each of §8's six capabilities: user question/live-tested example/boundary, all examples values verified on real machines (LEI→Bloomberg Finance L.P., CERT 3510→Bank of America N.A., GLEIF three-tier control chain, USAspending Lockheed Martin, EDGAR "rare earth" 10-K 3,144 hits); EDGAR both-ends date completion and the `total_relation` cap, fed_awards `date_range` echo (0.1.4 semantics) added to the boundary column. Complementary to the master register §10 corpus-face use cases (C-01~06), not taking C numbers.
- 2026-10-20: **Three fixes from WorkBuddy live testing (agentdata 0.1.4, fixed on both stacks)** — `fulltext` single-end date completion now effective (the EDGAR upstream only honors both-ends intervals and silently ignored single ends; rows echo `date_range` for the effective interval + the `total_relation` cap marker); `related kind=fed_awards` gained the `date_range` echo; Python CLI global options in mid-position are no longer swallowed (argparse SUPPRESS); the EDGAR date-window pure function `dateWindow` was extracted (offline-testable on Node). Master register [api.md](api.md) changelog same-day entry.
- 2026-10-19 (2): **§8 dual-stack convergence — Python SDK 0.1.3 ports the six capabilities (externally authoritative)** — `resolve kind=lei/name/cert`, `related kind=parent/fed_awards`, `fulltext`, all fully aligned with the Node baseline (agentdata: providers/gleif extended with search·parents + new edgar_fts/usaspending/fdic_bankfind; client/cli gained the related·fulltext verbs and the closed kind set); transport gained POST-read semantics (idempotency-declared retry gate + POST·curl channel pre-intercept, USAspending first use). 60 offline tests all green + six live probes (GLEIF reverse lookup/control chain, FDIC CERT 628, USAspending POST, EDGAR FTS) verified; master register [api.md](api.md) §9.6 registration synced (Wave 1 had been missed that day).
- 2026-10-19: **§8 expanded to the full Wave 1 (three verbs, six capabilities, all four vendors M1 keyless) and landed in code** (design volume §8 roadmap P0) — added `resolve kind=name/cert` (GLEIF name candidate reverse lookup / FDIC CERT→institution card), `related kind=parent/fed_awards` (GLEIF direct/ultimate parent control chain — the web's only free official face / USAspending federal award rows), `fulltext` (EDGAR FTS 2001+ full-text search, the first case admitted under the "full-text search exception"). Three core additions (daily-quota ledger/block cooldown/POST-read semantics) landed with `service/shared/thirdparty/`; six live verifications + offline regression all green. Same day, the keyless-only ruling: key-registration sources (SAM.gov/FCA/PatentsView/DOL) demoted to watch, off the roadmap; the earlier "keyed goes hosted" statement is void for this domain.
- 2026-10-16: **New §8 third-party real-time queries (enrichment capabilities), coded the same day** (chapter established with [api.md](api.md) §9 as a shared chapter, converged over two rounds of codex debate) — debut capability `resolve kind=lei` (GLEIF, keyless, local, TTL 7 days, P1 ✅ live-tested: LEI 5493001KJTIIGC8Y1R12→Bloomberg Finance L.P., both cache directions, shape error exit 2), positioning narrowed: **exact LEI normalization, not name→global-unique resolution, not a company-database substitute**; the wording "no user credentials currently required, still bound by upstream availability and fair-use policies" (no unlimited-rate guarantee claimed). Service layer `service/company/thirdparty/` newly created (gleif.mjs + index.mjs routing + README `> domain:` line) — execution/src assembly promoted to `service/shared/thirdparty/core.mjs` shared (same mechanism as healthcare). Former §8 errors→§9, §9 timeliness→§10 shifted down; incidentally fixed two stale references (header P2 HTTP `api.md §7`→§8; §9 closed error-code set `api.md §7.3`→§8.3 — missed in the 2026-10-14 shift).
- 2026-10-14: External-edition reference established. Vocabulary synced with the internal source of truth (43 qtype/4 doc_class/2 status/country three forms + dirty value `'`); "planned but not yet open" fields listed separately (400 semantics).
