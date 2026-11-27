# Cross-Domain External API Master Contract (api)

> **Positioning**: the cross-domain shared external interface contract — the **source of truth** for the operation model, layered reads, and filter/matching semantics.
> Each domain master document (esg.md / legal.md / …) covers only its domain-specific parts (filters / facets / use cases / T-layer content) and references this document;
> row contracts and vocabulary registration belong to `staging-schema.md` and are not repeated here.
> Basis: peer-API paradigm benchmarking (three verbs / facets first / undeclared fields 400 / `_enrich` — all already adjudicated)
> + 2026-10-13, converged after two rounds of external-agent adversarial review (codex/agy). **The primary key is the company, not the document**; this document governs every domain under domains/, and later domains such as healthcare copy it as-is.
> Established 2026-10-13 (user ruling: interfaces and use cases merged into the domain master documents; the cross-domain contract written up as a standalone document).

> **Edition**: this copy is versioned with the SDK release that carries it —
> it documents the contract of the release you have installed.

## 1. Operation model: three verbs (the only ones)

| Verb | Form | Description |
|---|---|---|
| `search` | `POST /{domain}/search` | Retrieval + filtering + facets; **batch list screening = `mode:"screen"`**; event/public-notice streams = `record_kind` + cursor |
| `read` | `POST /{domain}/read` | `target:{type:"company"\|"facility", id}` + `level=tier1\|tier2\|tier3` |
| `ask` | `POST /{domain}/ask` | P2. Explicitly **not enabled** in P1 — must not pass off evidence-free Q&A as delivery |

- No fourth verb. screening / notices are modes of `search`, not new operations (adversarial-review ruling: subscription is a **delivery mechanism**, not a query model).
- **The three verbs operate on the in-repo corpus** (2026-10-16 codex adversarial-review narrowing ruling): the semantic boundary of search/read/ask is the self-built corpus (db/staging). Third-party real-time queries (`resolve`/`evidence`) are the **domain capability (enrichment capability) axis**, a separate axis — not a fourth/fifth operation verb, and they do not map back onto corpus retrieval semantics; the mechanism is in §9, and each domain document registers its own capability list.
- The HTTP layer may offer integrators **semantic aliases** (P2, optional): `/{domain}/screening` = `search(mode=screen)`;
  `/legal/notices` = a GET read-only form of `search(record_kind=public_notice)`. Aliases must not fork the request/result contract or the permission logic.
- Unified company profile entry `GET /company/{id}/facts?domain=…&level=…`: **delegates to each domain's read levels** and defines no fields of its own — not a second read contract.

## 2. Layered reads (T1/T2/T3) and the four-part output

- The four-part output is never omitted: **company + reason + evidence + source**. T1 also carries short evidence anchors, just not full-text citations.
- **T1**: a one-line summary card — hit reasons (1-3), metric/event summary, source coverage, and the **"not covered ≠ no risk" notice**. Missing sources must never be written up as "no emissions / no incidents / no sanctions".
- **T2**: atomic fact detail + evidence citations (200-500 character snippet + document/table anchor). Facility→company aggregation must spell out the **included/excluded facility roster**; weak-key (PARENT name) attachment must not be passed off as group-level fact.
- **T3**: the evidence package — `raw_path` + official URL + `sha256` + fetch time + source batch + table/row/XML path. `doc_tokens` is meaningful only for the document/text layer; metric rows use `evidence_tokens` or 0 — **never fabricate document tokens**.
- Model-generated fields must carry `_enrich` (confidence annotations, one_liner, etc.) and never enter the evidence chain.

## 3. Filtering: Filter DSL and facets

- DSL: `eq` / `any` / `range` / `_not` / `_or`; **undeclared fields always return 400** (to prevent "a misspelled vocabulary term returns empty and gets read as absent").
- facets are `search` parameters: `facets:[field…]` (contextual counts under the current filters) and `facets_only:true` (distribution only); facets first, then filtering. `GET /{domain}/facets` serves at most as a P2 cached alias for the unconditional distribution.
- **country must never be a single field**: split into `company_registration_country` (the entity's country of registration) / `facility_country` (esg, country of physical occurrence) / `notice_jurisdiction` (legal); the response additionally provides `source_jurisdiction`, preventing the "US source = US company" misreading.

### 3.1 Unit constraint (v2.1.7) — `metric_value` must be paired with `metric_unit`

`metric_value` and `metric_unit` are a bound pair; neither may appear alone:

- Request body: `metric_value` and `metric_unit` must appear under the same key; either one missing → **400** (same root as "undeclared field 400": to prevent "`metric_value>0` without a unit being misread as tCO2e").
- Response body: every `facility_metric` must carry `metric_unit`; a missing unit = a data defect, blocked at the staging stage by qa 13 (`metric_value present && metric_unit missing → block`).
- **Whitelist** (v2.1.7 closed set):

  | Domain | Whitelist units |
  |---|---|
  | Emissions/carbon | `tCO2e`, `metric_tons_co2e`, `metric_tons_ch4`, `metric_tons_n2o`, `lbs`, `kg`, `HFC_kg_co2e`, `PFC_kg_co2e`, `SF6_kg_co2e` |
  | Counts | `count`, `case_count` |
  | OSHA rate | `rate_per_200k_hours` (rate metrics **must** carry this unit; numerator×200000/denominator is fixed as the formula) |
  | OSHA denominator | `hours` (`total_hours_worked`), `persons` (`annual_average_employees`) — the denominator atoms for rate derivation (registered in v2.1.9; formula input in esg §4) |
  | Amounts | `USD` (fines etc.) |
  | Days | `day_away_from_work`, `job_restricted_days` (OSHA raw count) |

- **Cross-unit comparison is forbidden**: a `metric_value` range filter must first declare `metric_unit` in the request body, and the server **compares only same-unit values** (letting different units into arithmetic comparison = a silent error, forbidden); if the T1/T2 rendering finds the two sides' units inconsistent, the rendering layer **degrades** to a "declared incomparable" placeholder.
- **Undeclared unit or unit not on the whitelist → 400** (set down in v2.1.7, same root as esg §3.1 non-emitted fields / legal §3 ids_freeform kept out of FTS — implicit defaults are the greatest enemy of integrity).

## 4. Matching and non-matches (screen mode)

- `match_status` has six states (underlying mechanics, audit semantics):

| State | Meaning | Auto-determinable? |
|---|---|---|
| `exact_identifier` | Exact hit on an official identifier (LEI/registration number/FRS…) | Yes |
| `exact_normalized_name` | Exact match on the normalized full name (suffixes/stopwords removed, constrained by entity type + country) | Yes, the basis must be returned |
| `candidate_name_match` | Fuzzy match on name/alias | No, for manual review |
| `ambiguous` | Multiple indistinguishable candidates | No |
| `no_match_in_coverage` | No hit within the declared list/version/rules/observation window | Yes |
| `not_covered` | Input country/entity type/identifier outside the screenable scope | Yes |

- `confidence` (HIGH/MEDIUM/LOW) only describes the presentation-layer mapping of **hit candidates** and must not swallow the six states.
- A non-match returns `coverage_assertion`: `{scope(list/version/entity type), observed_at(per source), source_versions, matching_rule_version, legal_clearance:false}` — it is **a coverage assertion, not proof of no risk**. The esg wording is one notch weaker: "no signal under ingested sources + current facility matching".
- Output **returns one row per input row** (non-match rows included), otherwise there is no audit loop. P1 input is JSONL; P2 synchronous ≤1,000 rows/batch, async jobs ≤10,000.

## 5. CLI foundation (P1)

```text
agentdata <domain> search
  [--filter 'k=v'] [--record-kind K] [--facets f1,f2]
  [--level tier1|tier2|tier3] [--limit N] [--cursor C]
  [--mode screen --input suppliers.jsonl]
agentdata <domain> read --id <id> [--level tier1|tier2|tier3]
```

- The CLI `--filter 'k=v'` covers equality plus the shorthands `k>=v`/`k<=v` (normalized to range) and `v` containing `|` (normalized to any); the **full DSL** (nested `_or`/`_not`, bare-scalar/bare-array json shorthand) maps directly to the search body via the HTTP API or `Client.search(filters=…)`.
- `--limit` is mandatory + stable sort + cursor, and unbounded export is forbidden; parameter spelling and output shape follow the contract in this document — no second convention invented.

**Implementation status**: the corpus engine and per-domain adapters are in service — company domain with full db functionality (search across three record layers / read three levels / screen six states), healthcare served from the hosted corpus during the ingest-prelude period (`source.backend` annotated), and undeclared filter fields always 400 (closed-set gate). This contract document governs.

## 6. Evolution and constraint recap

- P1 = CLI (search/read; ask not enabled) → P2 = HTTP + MCP (one server exposing all domains + semantic aliases + ask + subscription delivery).
- **Channel scope (user ruling 2026-11-19)**: the free API is the wrapped OSS SDK (`agentdata`, keyless) — the MCP is the managed paid channel, its key issued on provisioning and never a free face; this contract's P2 refers to that paid managed channel.
- Subscription (L-04 class): built on search cursors (`since`/`observed_since`), with P2 adding webhook/jobs — **no new query verb**.
- One `domain-spec.json` per domain (controlled filter/facet tables + T-layer content + use-case commands), generated from or reverse-checked against the domain master document §4/§5 — **the domain master document is the source of truth**.

## 7. Domain structure and regulatory regime partition

A domain's internal structure falls into three types according to whether its data schema forks across regulators/jurisdictions. **The criterion is schema consistency, not source count**.

### 7.1 Criteria for the three types

| Type | Criterion | How jurisdiction participates in the API | Examples |
|---|---|---|---|
| **Multi-regime partition** | record_kind sets, field sets, compliance frameworks, and users' primary questions differ across jurisdictions | Top-level URL branching + mandatory `side` filter | `healthcare` (CN / US / cross), `esg` (US shipped / CN planned), `legal` (US / UK / EU / global)|
| **Multi-country filtering** | Different countries produce the same record_kind, the schema is consistent, and the differences live in field values | Jurisdiction as a filter, not top-level branching | `company` (55 sources, 12+ countries, `country_registration` is a field value)|
| **Single regime** | Only one regulator/jurisdiction has data | No axis | `procurement` (CN-only)|

### 7.2 URL conventions for multi-regime partitions

- **Top-level sub-resources**: `/{domain}/<side>/<sub-resource>` is established only when that side uniquely owns a resource (e.g. `/healthcare/cn/holder/procurement` corresponds to centralized procurement, with no US counterpart) — **the asymmetry is deliberate; no empty shells added**
- **Unified search**: `POST /{domain}/search` with `side` mandatory (for multi-regime domains); `side=any` / `side=all` allow cross-side assembly
- **read does not split by side**: `POST /{domain}/read` aggregates across sides via `target.id` (the same id usually lands on only one side; cross-side entities are not mixed)
- **screen adds a side field**: `mode:"screen"` output adds `side:cn|us|cross`; a same-name cross-border question itself requires choosing a side first (a screen hitting A in cn and A' in us counts as two candidates, each returned with its own match_status)
- **Cross-side alignment does not bypass the ceiling**: each returned row carries `side` + alignment basis (healthcare §5.3: FDA rows without uscc have no automatic-alignment solution; the UC-H2 outbound signal is **not promised to resolve automatically**)

### 7.3 Per-side compliance declaration (compliance envelope)

Every multi-regime domain's §1 / §2 must carry `compliance_envelope`: `{source_jurisdiction, framework, identifier_schema, exit_restrictions}`. healthcare is the first example:

| side | Data export basis | Strong keys | Exit restrictions |
|---|---|---|---|
| `cn` | NMPA / CDE / SMPAA / National Health Commission (NHC) / drug regulator (NMPA) | uscc (Chinese hospitals **truthfully marked as having no USCC**; L3 candidates not auto-merged)| PIPL + Data Export Security Assessment Measures + labeling filing obligations (not ingested)|
| `us` | FDA / CMS / OIG / DOJ | cik / lei / npi / ccn (**no uscc**)| HIPAA + Open Payments Sunshine Act + FDA off-label restrictions |
| `cross` | Cross-side aggregation inference | — | Alignment ceiling declared truthfully; does not bypass §7.2 "cross-side alignment does not bypass the ceiling" |

### 7.4 Domain type registration

`docs/domains/registry.json`'s `domains[code]` gains a `partition` field (`multi-regime` | `multi-country` | `single-region`); each domain master document §1 explicitly declares its type — preventing later contributors from writing against the wrong template (healthcare = the multi-regime example, see §2.1).

## 8. P2 HTTP contract (implemented, 2026-10-16)

The CLI is the first shell of the same contract; the HTTP shell only does transport mapping and **does not fork request/result semantics**. The shells do not proxy each other; each executes the same spec directly:

- **Public gateway** — the customer-facing edge layer: Bearer PAT + per-key token bucket + server-side `request_id` + a self-description including an enrichment capability summary; auth / rate limiting / the customer-facing error contract live only in this layer. The CLI reaches it with `--base-url`/`--api-key` (env `AGENTDATA_BASE_URL` / `AGENTDATA_API_KEY`).
- Upstream text errors map transitionally to contract codes (400 text mapping only, misses map to `bad_value`, 500 always internal, with the single exception read-miss→404 `unknown_target`).

### 8.1 Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/v1/{domain}/search` | POST | body = `{filters?, facets?, mode?, level?, limit?, cursor?, input?}`; for `mode:"screen"`, `input` is an array (≤1,000 synchronous) |
| `/v1/{domain}/read` | POST | body = `{target:{type:"company"\|"facility", id}, level}` |
| `/v1/company/{id}/facts` | GET | Unified profile entry: `?domain=…&level=…` delegates to each domain's read, defines no fields of its own |
| `/v1/{domain}/facets` | GET | keyless static snapshot (unconditional distribution, refreshed per batch; see "keyless trial layer" below); on the inner shell still an unimplemented cached alias |
| `/v1/{domain}/free_samples` | GET | keyless samples (3 tier1 rows per domain, snapshot refreshed per batch) |
| Semantic aliases (optional) | GET | `/{domain}/screening`, `/legal/notices`, etc. = read-only forms of search; permissions and contract share the same origin |

**keyless trial layer (landed 2026-10-20, positioned against the competitor's free tier)**: `GET /v1/{domain}/facets` and `GET /v1/{domain}/free_samples` are PAT-exempt — alongside `/v1/domains` and `GET /v1/{domain}` they form the discovery/trial layer. Design rulings:

- **Static snapshot, not real-time**: `service/<domain>/free-snapshot.json` is a single file atomically carrying facets+samples, regenerated per batch (`node service/shared/gateway/gen-free-snapshot.mjs <domain>|--all`, requires DATA_ROOT pointing at the data root; zero rows = hard refusal, no fake snapshot written); the response carries `generated_at` and a not-real-time disclaimer, while real-time facets still go through search's `facets` parameter (PAT).
- **Redaction boundary = tier1**: samples take only the public-layer field set (tier2/3 never enter the snapshot); neither the snapshot nor the response copy contains internal paths.
- **facet field selection**: low-cardinality fields (the record_kind/qtype/province/qualification_year families); high-cardinality fields (stock_code/license_no) do not enter the free distribution layer.
- **No rate limiting**: static files cost near zero, so no per-IP bucket (external deployments handle reverse proxy/TLS themselves); corpus verbs remain PAT + per-key bucket, and keyless does not spill over (regression `tests/gateway-free-layer.test.mjs`).
- Snapshot absent = 404, the honest posture (no samples fabricated for unpublished domains).

### 8.2 Response envelope

```json
{ "domain":"company", "backend":"db", "coverage":"…",
  "rows":[ {"cursor":"company:123", "record_kind":"company",
             "entity":{…}, "reason":"…", "evidence":[{anchor,quote,url,raw_path,sha256}],
             "source":{source, observed_at}} ],
  "facets":{"qtype":[{"value":"…","count":123}]},
  "total_matched":1968, "next_cursor":"company:456", "notes":["…"] }
```

- The row-level four-part output (§2) is unchanged; `next_cursor` is an opaque string (each domain's `spec.sort` declares the stable order); `total_matched` must be the true value (no hand-waving estimates).
- `limit` 1..1000, default 50; out of range → 400. The screen response = `{screen:[one row per input row, non-matches included]}` (§4 audit loop).

### 8.3 Error model (closed code set; CLI and HTTP share the same code table)

| HTTP | code | Trigger |
|---|---|---|
| 400 | `undeclared_field` | filter/facets field not in the domain-spec closed set |
| 400 | `bad_operator` / `bad_value` | Malformed DSL shape / value not coercible |
| 400 | `unit_missing` / `unit_not_whitelisted` | §3.1 unit constraint |
| 400 | `record_kind_unknown` / `cursor_invalid` / `limit_out_of_range` | Self-explanatory by name |
| 404 | `unknown_target` | read id not in the domain (returns coverage_assertion hinting not covered ≠ does not exist) |
| 401/403 | `unauthenticated` / `forbidden` | Invalid Bearer PAT / domain not in the token's allow list |
| 429 | `rate_limited` | Over 60 req/min (token bucket), carries `Retry-After` |

- The CLI layer prints `400 <code>: message`, exit 2; the HTTP layer `{"error":{"code","message","field?"}}` — **one validation implementation, two shells**, preventing drift between them.
- The four third-party capability error codes join the same closed set: `thirdparty_upstream_unavailable`(502) / `thirdparty_rate_limited`(503, Retry-After passes through the upstream value — **429 is always reserved for this table's `rate_limited`, our own bucket**; upstream rate limiting does not reuse 429) / `capability_unavailable`(503) / `resolve_kind_unknown`(400) — semantics and mapping rules in §9.4.
- search/read are idempotent and read-only; no side-effecting verbs, so no CSRF/write paths.

### 8.4 Authentication and deployment

- Bearer PAT (issued via `.env`, never stored in the db); a token is bound to an allowed-domain list + a rate-limit bucket.
- A single-instance read-only service suffices to start P2 (read-only db connection / staging-scan same as CLI); the MCP server reuses the same adapter layer.

## 9. Third-party real-time queries (enrichment capability axis, cross-domain contract)

> Established 2026-10-16 (codex, two rounds of adversarial review converged; user ruling: "do not make users feel they are calling a third party; users query locally, and the rate limiting is the user's own"). This shared chapter establishes only the **mechanism**; each domain document registers its own **capability list** (provider / kind / TTL / inputs and outputs) — on conflict, this chapter governs.

### 9.1 Definition and the "invisible" boundary

- **What it is**: incremental questions the domain corpus (list snapshots) cannot answer (identity normalization / literature evidence, etc.), served by calling third-party public APIs on the spot, then returned under the same contract with our normalization and caching layered on. It is a domain capability axis, not an operation verb (§1 narrowing ruling).
- **"Users don't notice the third party" = invisible at the operation layer** (three promises written into the contract):
  1. **Zero credentials** — users never apply for / bring their own key (the BYOK rejection ruling still stands);
  2. **Zero URL assembly** — unified client/CLI forms; upstream endpoints are never exposed to caller code;
  3. **Zero rate-limit tuning** — politeness levels are built into the SDK, with the default locked to the most polite; users can only turn them down.
- **Not provenance concealment**: the source still truthfully carries the upstream official URL (§2 four-part iron rule), and external docs name the upstream (RxNav/GUDID/EPMC/GLEIF/CT.gov/DailyMed) — auditability takes precedence over abstraction.

### 9.2 Execution-location dichotomy (execution)

| execution | Semantics | Rate-limit semantics | Credentials |
|---|---|---|---|
| `local` | keyless capabilities sink into the SDK and execute on the spot on the **user's machine** (user's network egress + user's local cache) | **The rate limiting is the user's own** — upstream fair-use quotas keyed on source IP are naturally apportioned per user; the SDK locks the default to the most polite level, adjustable only downward | No key of any kind needed |
| `hosted` | Capabilities requiring our central key go through P2 HTTP, executed by our proxy | Our central bucket (`rate_limited`, 429) | Our `.env` holds the key, **never shipped down to the SDK** |

- A request may carry `execution:"local"|"hosted"|"auto"` (default `auto`). **auto rule** (documented, no silent rerouting): capability keyless and built into the SDK → `local`; capability needs our central key → `hosted`; neither side reachable → error `capability_unavailable` (503).
- The response's `source.execution` reports the **actual** execution location (§9.3).
- Relation to the BYOK rejection ruling: what was rejected is "users bring their own key"; the entire local-execution family (RxNav/EPMC/GUDID/GLEIF/CT.gov/DailyMed) is keyless — going local does not resurrect the key question, and the wrapper's value (normalization/caching/unified contract) is preserved.

### 9.3 Row shape and cache annotation

- **Corpus rows unchanged**: `source = {source, observed_at, backend:"db"|"staging"}` (§8.2 — `backend` says "where it lives").
- **New enrichment row shape**: `source = {provider, execution:"local"|"hosted", from_cache, observed_at pass-through time | fetched_at cache time}` — `execution` says "where it executed"; **cache is not a backend** (no `backend:"cache"`, adversarial-review ruling).
- `provider` is a stable, enumerable identifier (`rxnav`/`epmc`/`gudid`/`gleif`/`ctgov`/`dailymed`…).
- **Cache TTL is declaration-based**: declared per provider+op entry (immutable keys may be permanent, mutable records get short TTLs); the mechanism is in this chapter, actual values are registered in each domain's capability table. A hit returns `from_cache:true`; TTL = our guarantee of "how stale a result may be at most".

### 9.4 Error codes (merged into the §8.3 closed set)

| HTTP | code | Trigger |
|---|---|---|
| 502 | `thirdparty_upstream_unavailable` | Upstream unreachable / 5xx / network failure |
| 503 | `thirdparty_rate_limited` | **Upstream** rate limiting — `Retry-After` passes through the upstream value; **429 is always reserved for our own `rate_limited`** (the status code is consumed by HTTP clients/gateways/monitoring before the body; upstream rate limiting reusing 429 would recreate ambiguity) |
| 503 | `capability_unavailable` | Under auto, the capability is reachable on neither side (an availability problem, not a request error; does not belong to 400) |
| 400 | `resolve_kind_unknown` | kind not in the domain's capability closed set |

- CLI mapping: the upstream family (502/503) exits 1, the usage family (400) exits 2, same convention as §8.3; error outflows are correlated via `request_id` (§9.5).

### 9.5 SDK shape and response metadata

- Two external shapes: SDK (programmatic) + CLI (instant use), same contract, same code table; `request_id` enters the contract — an opaque correlation ID (generated SDK-side for local execution) threading through success/error outflows and log-based troubleshooting; `latency_ms` is diagnostic-only and optional (local/hosted, cache hits, and differing transport channels distort measurement boundaries; not a business dependency).
- **Single authoritative implementation** (adversarial-review ruling; 2026-10-26 user ruling converged on a single stack): Python `sdk/python/agentdata` (stdlib-only, zero dependencies) is the **sole authoritative implementation** (CLI=`agentdata`) — the former Node `service/` twin baseline was withdrawn (consumer inventory = a self-referential loop with no external users; the 0.1.6 behavior / 0.2.1 naming divergences falsified dual-stack maintainability). The acceptance bar is unchanged = per-provider capability/error/cache vectors + **real-transport verification** (the lesson of GUDID blocking undici by TLS fingerprint: golden vectors cannot replace verification against live transport). Future HTTP/MCP serving of real-time queries wraps the client.py implementation in a thin shell; no second implementation will be created.
- **Face order and jurisdiction (from 0.3.10, dual ruling)**: command faces are double-sorted — across domains by `DOMAIN_ORDER` dictionary order (company/esg/healthcare/legal/procurement/research/security), within a domain by face-name dictionary order (under the two-segment `<source>_<dataset>` naming this groups by source automatically); **the ordering source of truth = the English identifier** (zh pages translate the copy only and never drive the ordering). The CLI success envelope carries a `jurisdiction` chapter (same source as the §9.6 jurisdiction column): semantics = the issuing authority's jurisdiction, with institutions covering global phenomena (GLEIF/ROR/EITI/ClimateTRACE/SIPRI/MeSH/EPMC/Crossref/OpenAlex/bioRxiv/OpenCitations/OSV/Paris MoU) = `GLOBAL`; the vocabulary is ISO-3166 alpha-2 + `EU` + `GLOBAL`. The jurisdiction source of truth = each domain's cli.py `COUNTRY` (same face set as FLAT), synchronized in capabilities.mjs — guarded by the seven tests of `tests/test_face_order_jurisdiction.py` (dual order / COUNTRY coverage / vocabulary / mjs sync). The corpus faces search/read are hosted mixed-jurisdiction services and carry no chapter.

### 9.6 Domain capability registry (current state)

> Per-face rows below were maintained through 0.3.39; from 0.3.40 onward the authoritative
> increment log is the version roll at the end of this section plus the §Changelog. The table is
> a historical snapshot, not the face census — runtime truth is `agentdata capabilities` (and
> `tests/test_readme_counts.py` gates the published headline counts against the runtime).

| Domain | Flat command | Jurisdiction | Old verb face (frozen for compatibility, **removed in 0.3.0**) | provider | execution | Cache TTL | First shipped |
|---|---|---|---|---|---|---|---|
| healthcare | `rxnav_rxcui_by_name` | US | `resolve kind=drug_name` | `rxnav` | local | permanent (RxCUI immutable) | P0 ✅ |
| healthcare | `rxnav_rxcui_atc` | US | `resolve kind=atc` | `rxnav` | local | permanent (ATC hierarchy immutable) | Wave 1 ✅ |
| healthcare | `epmc_search` | GLOBAL | `evidence` | `epmc` | local | search page 24h | P0 ✅ |
| healthcare | `gudid_devices` | US | `resolve kind=device_di` | `gudid` | local | 7 days (records can be revised) | P1 ✅ |
| healthcare | `eudamed_devices_udi_di_data` | EU | `resolve kind=device_eu` | `eudamed` | local | 7 days (master records change slowly; empty pages not booked) | Wave 2 ✅ |
| healthcare | `mesh_descriptor` | GLOBAL | `resolve kind=mesh_term` | `mesh` | local | 30 days (vocabulary released annually) | Wave 3 ✅ |
| healthcare | `ctgov_studies` | US | `trials` | `ctgov` | local | 7 days (trial status/recruitment can change) | Wave 1 ✅ |
| healthcare | `dailymed_spls` | US | `label` | `dailymed` | local | 7 days (SPL versions roll monthly) | Wave 1 ✅ |
| healthcare | `fda_drug_shortages` | US | `related kind=drug_shortages` | `shortages` | local | 24h (shortage list updates daily) | Wave 5 ✅ |
| healthcare | `au_tga_artg` | AU | `related kind=artg_register` | `au_tga` | local | 24h (register updates daily) | Wave 6 ✅ |
| healthcare | `au_tga_manufacturers` | AU | `related kind=mis_manufacturers` | `au_tga` | local | 24h (license register changes slowly; same provider shares TTL) | Wave 6 ✅ |
| healthcare | `ca_dpd_companies` | CA | —— (born flat) | `ca_dpd` | local | 7 days (monthly static extract; one full shot, local post-slice) | 0.3.19 ✅ |
| healthcare | `ca_dpd_drug_products` | CA | —— (born flat) | `ca_dpd` | local | 7 days (status closed set 1\|2\|3\|4\|6 — unknown values are silently ignored upstream and dump the whole 15MB register, SDK-side wall) | 0.3.19 ✅ |
| healthcare | `ca_mdall_companies` | CA | —— (born flat) | `ca_mdall` | local | 7 days (register changes slowly; two-country register) | 0.3.19 ✅ |
| healthcare | `ca_mdall_licence` | CA | —— (born flat) | `ca_mdall` | local | 7 days (LIMH dossier point lookup; active/archived are separate upstream indexes) | 0.3.19 ✅ |
| healthcare | `rasff_notifications` | EU | —— (born flat) | `rasff` | local | 24h (two-step session handshake; the three proven filters only — enum-shaped filters unproven, unexposed) | 0.3.19 ✅ |
| healthcare | `safety_gate_alerts` | EU | —— (born flat) | `safety_gate` | local | 24h (weekly-report index XML; year filter is a local post-filter) | 0.3.19 ✅ |
| healthcare | `safety_gate_report` | EU | —— (born flat) | `safety_gate` | local | 7 days (published weekly reports are immutable) | 0.3.19 ✅ |
| healthcare | `gb_mhra_alerts` | GB | —— (born flat) | `gb_mhra` | local | 24 hours (the alert stream lands at daily-to-weekly cadence) | 0.3.16 ✅ |
| healthcare | `gb_mhra_alert` | GB | —— (born flat) | `gb_mhra` | local | 7 days (alert pages change slowly; change_history records the evolution) | 0.3.16 ✅ |
| healthcare | `fda_drug_recalls` | US | —— (born flat) | `fda_recalls` | local | 24h (weekly cadence) | Wave 10 ✅ |
| healthcare | `fda_device_recalls` | US | —— (born flat) | `fda_recalls` | local | 24h (RES weekly cadence) | Wave 10 ✅ |
| healthcare | `fda_food_recalls` | US | —— (born flat) | `fda_recalls` | local | 24h (weekly cadence) | Wave 10 ✅ |
| healthcare | `fda_crl_letters` | US | —— (born flat) | `fda_crl` | local | 30 days (458 rows, quasi-static) | Wave 10 ✅ |
| healthcare | `fda_drug_approvals` | US | —— (born flat) | `fda_drugs` | local | 24h (drugsfda weekly cadence) | Wave 10b ✅ |
| healthcare | `fda_drug_catalog` | US | —— (born flat) | `fda_drugs` | local | 24h (ndc updates daily; NSDE merged into this face) | Wave 10b ✅ |
| healthcare | `fda_orangebook` | US | —— (born flat) | `fda_drugs` | local | 24h (Orange Book monthly cadence) | Wave 10b ✅ (replaces the dead nsde endpoint) |
| healthcare | `fda_device_510k` | US | —— (born flat) | `fda_devices` | local | 24h | Wave 10b ✅ |
| healthcare | `fda_device_pma` | US | —— (born flat) | `fda_devices` | local | 24h | Wave 10b ✅ |
| healthcare | `fda_device_registrations` | US | —— (born flat) | `fda_devices` | local | 7 days (registrationlisting quarterly cadence) | Wave 10b ✅ |
| healthcare | `fda_device_classification` | US | —— (born flat) | `fda_devices` | local | 30 days (taxonomy nearly static) | Wave 10b ✅ |
| company | `gleif_lei_records` | GLOBAL | `resolve kind=lei` | `gleif` | local | 7 days (LEI status/renewal can change) | P1 ✅ |
| company | `gleif_lei_records_search` | GLOBAL | `resolve kind=name` | `gleif` | local | 7 days | Wave 1 ✅ |
| company | `gleif_direct_parent` | GLOBAL | `related kind=parent` (merged face, split in two in 0.2.1) | `gleif` | local | 30 days (ownership chains change rarely) | Wave 1 ✅ |
| company | `gleif_ultimate_parent` | GLOBAL | `related kind=parent` (merged face, split in two in 0.2.1) | `gleif` | local | 30 days (ownership chains change rarely) | Wave 1 ✅ |
| company | `fdic_institutions` | US | `resolve kind=cert` | `fdic-bankfind` | local | 30 days (registration master changes slowly) | Wave 1 ✅ |
| company | `us_sec_submissions` | US | `resolve kind=cik` | `edgar-cik` | local | 7 days (identity current values/filing counts can change) | Wave 2 ✅ |
| company | `ror_organizations` | GLOBAL | `resolve kind=ror` | `ror` | local | search 7 days / single record 30 days (quarterly releases) | Wave 3 ✅ |
| company | `vies_vat` | EU | `resolve kind=vat` | `vies` | local | 7 days (validation verdict; masked name/address recorded as null) | Wave 4 ✅ |
| company | `usaspending_spending_by_award` | US | `related kind=fed_awards` | `usaspending` | local | 24 hours | Wave 1 ✅ |
| company | `ted_notices_search` | EU | `related kind=eu_tenders` | `ted` | local | 24 hours (notice stream updates daily) | Wave 4 ✅ |
| company | `gb_fts_release_packages` | GB | `related kind=uk_tenders` | `fts` | local | 24 hours (releases roll continuously) | Wave 4 ✅ |
| company | `gb_contracts_finder_published_notices` | GB | `related kind=uk_cf_tenders` | `cf` | local | 24 hours (releases roll continuously) | Wave 4 ✅ |
| company | `us_sec_fulltext_search` | US | `fulltext` | `edgar-fts` | local | 24 hours | Wave 1 ✅ |
| company | `ch_zefix_firm_search` | CH | —— (born flat) | `ch_zefix` | local | 7 days (current-value query) | 0.3.3 ✅ |
| company | `ch_zefix_firm` | CH | —— (born flat) | `ch_zefix` | local | 30 days (profiles/M&A edges change slowly) | 0.3.3 ✅ |
| company | `no_brreg_enheter` | NO | —— (born flat) | `no_brreg` | local | 7 days (current-value query) | 0.3.3 ✅ |
| company | `no_brreg_roller` | NO | —— (born flat) | `no_brreg` | local | 30 days (role sequences change slowly) | 0.3.3 ✅ |
| company | `fi_ytj_companies` | FI | —— (born flat) | `fi_ytj` | local | 7 days (registration current values) | 0.3.3 ✅ |
| company | `fr_recherche_search` | FR | —— (born flat) | `fr_recherche` | local | 7 days (registration current values) | 0.3.4 ✅ |
| company | `co_rues_companies` | CO | —— (born flat) | `co_rues` | local | 7 days (registry changes slowly) | 0.3.14 ✅ |
| company | `kr_hometax_biz_status` | KR | —— (born flat) | `kr_hometax` | local | 7 days (휴폐업 current values) | 0.3.14 ✅ |
| company | `nzco_companies` | NZ | —— (born flat) | `nzco` | local | 12 hours (new incorporations land in the index) | 0.3.30 ✅ |
| company | `nzco_directors` | NZ | —— (born flat) | `nzco` | local | 24 hours (appointments change less often than the index) | 0.3.30 ✅ |
| company | `cz_ares_ekonomicke_subjekty` | CZ | —— (born flat) | `cz_ares` | local | 7 days (the register's own datumAktualizace moves slowly) | 0.3.32 ✅ |
| company | `cz_ares_ekonomicke_subjekty_vyhledat` | CZ | —— (born flat) | `cz_ares` | local | 12 hours (new entities land in the index) | 0.3.32 ✅ |
| company | `gg_gfsc_registered_businesses` | GG | —— (born flat) | `gg_gfsc` | local | 24 hours (register dump, one-shot feed + local scan) | 0.3.33 ✅ |
| company | `gg_gfsc_regulated_entities` | GG | —— (born flat) | `gg_gfsc` | local | 24 hours (register dump, one-shot feed + local scan; one row per licence group, entities counted separately) | 0.3.33 ✅ |
| company | `in_sebi_default_brokers` | IN | —— (born flat) | `in_sebi_intm` | local | 24 hours (the defaulters & expelled brokers register is one 1.24MB page — 445 cards, no paging, no search; Status = Defaulter 80 / Expelled 215 / Defaulter and expelled 150) | 0.3.35 ✅ |
| company | `in_sebi_intermediaries` | IN | —— (born flat) | `in_sebi_intm` | local | 12 hours (37 recognised-intermediary categories verbatim, daily-stamped; search XOR regno is a hard local wall — an empty search over a full category times out server-side; card field sets vary by category, every title/value pair rides with unknown labels verbatim) | 0.3.35 ✅ |
| company | `tr_spk_listed` | TR | —— (born flat) | `tr_spk_borsa` | local | 24h (both walls 628+121 one-shot, register posture; the lifecycle state rides INLINE in unvani — İFLAS/TASFİYE prefixes, no separate column; the single-record channel's sirketVarmi flag lies (an off-register MERSIS also answers true with an all-null shell) — found mirrors unvani being set) | 0.3.36 ✅ |
| company | `ru_cbr_credit_orgs` | RU | —— (born flat) | `ru_cbr_credit` | local | 24h (ONE 790KB HTML page = the whole 1,897-row × 9-col register, no paging no query surface, nightly rebuild — as-of stamp rides the census; four statuses verbatim Действующая 358/Отозванная 282/Аннулированная 2/Ликвидация 1,255 — the liquidation wall is the largest segment; kind null on the 1,746 universal banks (the register's own empty-cell convention); ОГРН = the ЕГРЮЛ join key, empty on 188 legacy rows; foinfo_path = the register's own per-entity edge) | 0.3.37 ✅ (the SDK's first RU jurisdiction; shares host www.cbr.ru with legal ru_cbr_warning) |
| company | `br_bacen_institutions` | BR | —— (born flat) | `br_bacen` | local | 24h (FOUR one-shot Sedes* resources merged = the whole 1,740-row authorised-institutions register: banco 154 + cooperativa 752 + sociedade 704 + consorcio 130, local scan; the key sets are the register's own per-family variants — banco SEGMENTO+CARTEIRA_COMERCIAL, cooperativa swaps in CLASSE/CATEGCOOPSING/FILIACAO/ASSOCIACAO with NO SEGMENTO, sociedade a 15-value SEGMENTO, consorcio a bare address block; CNPJ is the 8-digit ROOT — the 14-digit whole key lives on the branches/dasfn faces) | 0.3.38 ✅ (the SDK's first BR jurisdiction; shares host olinda.bcb.gov.br with legal br_bacen_regimes) |
| company | `br_bacen_branches` | BR | —— (born flat) | `br_bacen` | local | 24h (the whole 13,590-row branch panel across TWO pages $top=10000+$skip=10000 — Olinda's $inlinecount answers 400 so the register size is what you pull; CNPJ three-part + the joined 14-digit cnpj_full = the RFB whole-library join key; COMPE = the PIX/TED settlement key, empty on 731 rows → null; posicao = the panel as-of, data_inicio 1949→ dd/mm/yyyy verbatim) | 0.3.38 ✅ |
| company | `br_bacen_domains` | BR | —— (born flat) | `br_bacen` | local | 24h (the whole 1,892-row verified-domains register = 1,740 institutions × verified-domain status: own 534 / member 279 (the upstream typo 'intregrante' kept verbatim) / no-verified-domain 1,079 — the honest negatives STAY in the scan, the anti-phishing edge; conglomerado = the 635-code lineage key; BB's two rows keep the register's own CNPJ 00000000 placeholder) | 0.3.38 ✅ |
| company | `br_bacen_dasfn` | BR | —— (born flat) | `br_bacen` | local | 24h (the whole 10,419-row open-data/open-finance participation directory across TWO pages × 513 institution CNPJs × 4 API kinds (pilar3 9,885 / canais_atendimento 422 / taxas_cartoes 93 / pix_saque 19), all Situacao=Produção; rows are per-endpoint; the upstream serialises null Argumento as the literal string 'None' — normalised to null; PATH TRAP: the live service is /DASFN/versao/v1/ — the recipe's /DASFN/v1 form answers 403) | 0.3.38 ✅ |
| company | `tr_bddk_institutions` | TR | —— (born flat) | `tr_bddk` | local | 24h (TWELVE server-rendered category pages, each carrying its whole category — 640 cards live 2026-11-04: banks 67 / financial-leasing 86 / factoring 118 / financing 31 / financial-holding 3 / asset-management 44 / foreign-bank representatives 36 / independent audit 73 / valuation 169 / credit-rating 1 / professional associations 3 / savings-financing 9; no paging, no query surface — one fetch per category per TTL window, local scan; **the cards are NOT in the table** — the page shows four contact lines and the register lives in the detayliGor popup button's 13 data-* attributes (ad / aciklama / isFaaliyette / eftKodu / isDijital / telefon / faks / adres / webadresi / sektordenCikisTarihi / kurulKarari); **"-" is the upstream placeholder, not a value** (426 exit dates, 79 decisions, 2 descriptions carry it → honest null); **a lifetime book** — 418 in operation / 222 exited cards (the exited cards are the screening surface; 8 carry no exit date, 79 no decision number); the board decision number lives in kurulKarari (two date/number separators in the wild) or in the prose of aciklama ("N sayılı Kararı"); **same-name cards are NOT collapsed** (640 cards = 631 category+name pairs, 9 duplicate groups — kept as published, the census reports them); eftKodu = the EFT routing code on 343 cards; no registration number, MERSIS key or tax id on the cards) | 0.3.40 ✅ (its OWN host bucket www.bddk.org.tr — not the SPK family; the name filter folds Turkish diacritics so ASCII "ISBANK" finds "İŞ BANKASI") |
| company | `je_jfsc_regulated_entities` | JE | —— (born flat) | `je_jfsc` | local | 24 hours (site-search backing the register page; NoResults is a result count) | 0.3.33 ✅ |
| company | `kz_gbd_ul_companies` | KZ | —— (born flat) | `kz_gbd_ul` | local | 12 hours (the register is a live mirror of registration events) | 0.3.34 ✅ |
| company | `de_inso_search` | DE | —— (born flat) | `de_inso` | local | 12h (1h while the window includes today — the courts publish during the working day; a window that closed before today is settled) | 0.3.41 ✅ (the SDK's first DE jurisdiction; a Jakarta Faces POSTBACK portal, not a query API — one GET for the ViewState + the form action that carries the session in the path ("/ap/suche.jsf;jsessionid=…", echoed verbatim because the SDK keeps no cookie jar) + one form-urlencoded POST with Origin + Referer; the ViewState is a one-shot token, so the pair is always re-bootstrapped; the ROW GRAIN IS THE ANNOUNCEMENT, not the case (one case carries several announcements on one day — the rows are never deduped); the name field matches the surname / company designation EXACTLY, case-insensitively; the Insolvenzgericht select is INERT (asking for Aachen returned rows from eight other courts) so it is not exposed; the upstream refuses a window above its own cap ("maximale Trefferzahl beträgt 1000") — that answer is a structured state with the upstream's verbatim German sentence, NOT an error, and the working grain is ONE STATE x ONE DAY; the announcement full text needs a real browser click and is out of scope) |
| company | `de_inso_register_lookup` | DE | —— (born flat) | `de_inso` | local | 12h (same window rule as the search face) | 0.3.41 ✅ (the register point lookup — the hard join key against the commercial registers: the upstream demands court + type + number all three ("Der Registereintrag muss eindeutig belegt sein"), refused locally before the wire; the 149 register courts are embedded, so the court may be given as the upstream code (R1101) or as the court name ("Düsseldorf"); the Register cell "Düsseldorf, HRB 101036" rides only ~9% of the announcement rows (NW 2026-11-02 = 98 of 1,077) — an empty cell is an honest gap, never a dash) |
| company | `jp_fsa_licensed` | JP | —— (born flat) | `jp_fsa` | local | 24 hours per file (register posture — each file's own as-of rides the census so the FROZEN registers never masquerade as live) | 0.3.42 ✅ (the SDK's first JP jurisdiction; THIRTY-ONE keyless XLSX registers behind one hub /en/regulated/licensed/{stem}.xlsx, ~4,082 entities live 2026-11-05, ONE local-scan family face over the farm — --category 31-slug closed set, --name/--jcn local filters because the upstream has NO query surface; the channel is transport ext-9 bytes again — xlsx as lossless latin-1, stdlib unzip, sharedStrings this time; JCN/Corporate Number/法人番号 are ONE key under three spellings with '―'/'－' as honest nulls; the 'Total N banks' subtotal cells ride ON data rows (row stays, class does not change); four date decodes coexist (Excel serial / 平成·令和 era / d-m-yyyy strings / 'Aug 7, 2008（Dec 6, 2024）'); the two sintaku registers carry concatenated furigana readings stripped positionally (only those files); fafia is an ACCUMULATING register (545 sheet rows fold into 104 firms); several registers are FROZEN years back with their own as-of stamps) |
| company | `ca_ccaa_records` | CA | —— (born flat) | `ca_osb` | local | 24 hours both ops (register posture — the quarterly resource-URL rollover is itself a fresh cache key) | 0.3.43 ✅ (the OSB CCAA large-company restructuring roster: ELEVEN year-named CUMULATIVE XLSX snapshots behind one open.canada.ca CKAN package, the face resolves the LATEST at call time and fetches ONLY it — 2026 Q2 = 730 proceedings spanning 2009→2026 — then scans locally because the upstream has NO query surface; --name/--monitor local fold filters, --osb exact, --province a 13-code closed set; header-era drift by NAME anchors (2016 files 17 columns with "Monitor's Representation", current 21 — both parse); three date forms coexist (Excel serial / ISO / dd-mm-yyyy) with the source's own 5-digit-year typo decoded to null, never guessed; province = the OSB File Number suffix with the '-2201-'/'-7201-' year typos kept verbatim and counted; the employees column doubles as the '*Sealing Order' court-sealed marker (12 rows); amounts keep commas and Excel float tails; 'Ernst & Young Inc.' vs 'ERNST & YOUNG INC.' folded in the census ranking; NO corporate-number column → join by name+province; the channel is transport ext-10 (absolute-URL path op, raw substitution — quoting would mangle the ic.gc.ca archives' '.../$file/...') + ext-9 bytes xlsx; TWO hosts ONE provider bucket: catalog open.canada.ca, file ised-isde.canada.ca rolling quarterly; the 1978→today full-estate Federal Insolvency Records Search is a PAID wall, not this face — disclosed in the reason) |
| company | `es_cnmv_entities` | ES | —— (born flat) | `es_cnmv` | local | 24 hours (register posture — the roster moves slowly) | 0.3.44 ✅ (the CNMV supervised-entity register — the company domain's first ES face: FOURTEEN categories behind ONE endpoint (/portal/consultas/listadoentidad.aspx?id=1&tipoent=0..13), one keyless shot per category, scanned locally because the upstream has NO query surface — 1,760 entities live 2026-11-04 (eea_investment_firms_passport 812 + eu_credit_passport 469 = Spain's view of the European financial passport); the row is `<li class="blocks-single">` with the entity's own detail href as its key — TEN (endpoint,tipo) key kinds measured (esis?nif / eafi?EAF / esisextranjerassuc CSU\|XSU / esisextranjeraslp CLP\|XLP / esisentcredito ECN\|SECC\|SECE\|ECCLP\|ECELP / afn?AFN), a kind off the map COUNTED in the census never guessed; NIF double form (dashed A-83217281 / bare B22526768) normalised for joins, --nif accepts both spellings; the cookie banner occupies `<h1>` on the big pages so the title is read from `<title>`; empty categories (SGC moved to ListadoGestorasFTA; te=11) = a titled page with ZERO rows — honest emptiness, never an error; the capitalised /portal/Consultas.aspx path 403s — a title-less row-less page is a shape drift; the NIF keyspace is shared with the CNMV sanctions register (datosentidad.aspx) — roster-to-sanctions is the licence-lifecycle join) |
| esg | `eiti_companies` | GLOBAL | `resolve kind=eiti_name` | `eiti` | local | 7 days (declaration candidates refresh per batch) | Wave 1 ✅ |
| esg | `eiti_payments` | GLOBAL | `related kind=eiti_payments` | `eiti` | local | 7 days | Wave 1 ✅ |
| esg | `climatetrace_owners` | GLOBAL | `resolve kind=trace_owner` | `climatetrace` | local | 30 days (stable-key face) | Wave 3 ✅ |
| esg | `climatetrace_sources` | GLOBAL | `related kind=trace_sources` | `climatetrace` | local | 30 days (annual data rolls slowly) | Wave 3 ✅ |
| esg | `eutl_datasets` | EU | —— (born flat) | `eutl` | local | 24h (catalog file set rolls slowly) | 0.3.2 ✅ |
| esg | `epa_frs_facilities` | US | —— (born flat) | `epa_frs` | local | 24h (master records change slowly) | 0.3.2 ✅ |
| esg | `thetis_mrv_datasets` | EU | —— (born flat) | `thetis_mrv` | local | 24h (version ledger rolls in daily batches) | 0.3.5 ✅ |
| esg | `paris_mou_detentions` | GLOBAL | —— (born flat) | `paris_mou` | local | 1h (current state rolls within the day) | 0.3.5 ✅ |
| esg | `paris_mou_bans` | GLOBAL | —— (born flat) | `paris_mou` | local | 6h | 0.3.5 ✅ |
| esg | `paris_mou_low_performance_companies` | GLOBAL | —— (born flat) | `paris_mou` | local | 6h (rolling 6-month window) | 0.3.5 ✅ |
| esg | `paris_mou_inspections` | GLOBAL | —— (born flat) | `paris_mou` | local | 30min (window-query replay) | 0.3.5 ✅ |
| esg | `euasl_datasets` | EU | —— (born flat) | `euasl` | local | 24h (republication rotates the download UUIDs) | 0.3.22 ✅ |
| legal | `csl_screening_list` | US | (born flat; 0.1.16 shipped the old name `csl_screening` as a frozen alias) | `csl` | local | 24 hours (the full 16.8MB list fetched and cached once daily; screening afterwards needs zero network) | Wave 7 ✅ |
| legal | `lda_filings` | US | `related kind=us_lobbying` | `lda` | local | 7 days (filings) / 30 days (entity card) | Wave 1 ✅ |
| legal | `dgcomp_cases_search` | EU | `related kind=eu_competition` | `dgcomp` | local | 7 days | Wave 1 ✅ |
| legal | `gb_ec_donations` | GB | `related kind=uk_political_funds` (merged face, split in two in 0.2.1) | `ukec` | local | 24 hours | Wave 1 ✅ |
| legal | `gb_ec_loans` | GB | `related kind=uk_political_funds` (merged face, split in two in 0.2.1) | `ukec` | local | 24 hours | Wave 1 ✅ |
| legal | `sipri_trades_search` | GLOBAL | `related kind=arms_trade` | `sipri` | local | 30 days | Wave 1 ✅ |
| legal | `federalregister_documents` | US | `fulltext` | `federalregister` | local | search 24h (daily stream) / single record 30 days | Wave 3 ✅ |
| legal | `ecfr_search` | US | (born flat, Wave 8) | `ecfr` | local | 24 hours (code-updates-daily cadence) | Wave 8 ✅ |
| legal | `ecfr_titles` | US | (born flat, Wave 8) | `ecfr` | local | 24 hours (daily refresh watermark; same provider shares TTL) | Wave 8 ✅ |
| legal | `courtlistener_opinions_search` | US | (born flat, 0.2.3) | `courtlistener` | local | 24 hours | 0.2.3 ✅ |
| legal | `gb_cma_cases` | GB | —— (born flat) | `gb_cma` | local | 24 hours (case list drifts at daily cadence) | 0.2.11 ✅ |
| legal | `gb_cma_case` | GB | —— (born flat) | `gb_cma` | local | 7 days (case cards change slowly; change_history records the evolution) | 0.2.11 ✅ |
| legal | `gb_tna_caselaw_search` | GB | —— (born flat) | `gb_tna_caselaw` | local | 24 hours (feed drifts at daily cadence; the licence forbids bulk = targeted-retrieval face) | 0.3.8 ✅ |
| legal | `gb_tna_caselaw_judgment` | GB | —— (born flat) | `gb_tna_caselaw` | local | 7 days (judgments change slowly; contenthash detects text drift) | 0.3.8 ✅ |
| legal | `co_sic_sanctions` | CO | —— (born flat) | `co_sic` | local | 24 hours (append-mostly firm-sanctions register; Socrata $-channel verbatim as co_secop) | 0.3.16 ✅ |
| legal | `afdb_debarred_entities` | GLOBAL | —— (born flat) | `afdb` | local | 24 hours (one-shot full feed 1,440 rows cached once daily; local contains-scan afterwards needs zero network; Cloudflare UA-fingerprint gate = ext-8 full browser-suite override) | 0.3.21 ✅ |
| legal | `ca_sema_sanctions` | CA | —— (born flat) | `ca_sema` | local | 24 hours (the 2.9MB consolidated XML cached once daily; local screening afterwards; 731 ships carry an IMO number = the shipping-roster join key) | 0.3.21 ✅ |
| legal | `idb_debarred_entities` | GLOBAL | —— (born flat) | `idb` | local | 24 hours (server-side CKAN DataStore search: q/filters/offset/sort upstream-verbatim, include_total always) | 0.3.21 ✅ |
| legal | `wb_debarred_firms` | GLOBAL | —— (born flat) | `wb` | local | 24 hours (one-shot full dump cached once daily — the SAP gateway refreshes every 3h, a day-old screening register is fine; the gateway apikey is the page-embedded browser-public constant) | 0.3.21 ✅ |
| legal | `gb_gazette_notices` | GB | —— (born flat) | `gazette` | local | 12h (the three editions roll daily; noticetypes is the only live event filter — noticecode/categorycode are dead upstream; the corporate-insolvency chapter preset expands 13 codes; a bare search is the 4.89M bulk wall, walled locally behind at-least-one-filter) | 0.3.27 ✅ |
| legal | `ie_revenue_defaulters` | IE | —— (born flat) | `ie_revenue` | local | index 24h (quarterly publication) / defaulters csv 7d (the current-year index links the latest quarters only; older years are archive pages the face deliberately does not walk) | 0.3.27 ✅ |
| legal | `us_occ_enforcements` | US | —— (born flat) | `occ` | local | listing 12h (the by-year news-release listing grows monthly) / release 30d (a published release is immutable; docket No. AA-ENF-\* is the official key joining EASearch 1989+, out of SDK scope; parses both the 2024+ sentence schema and the ≤2020 table schema; no gate of any kind) | 0.3.28 ✅ |
| legal | `cfpb_complaints` | US | —— (born flat) | `cfpb` | local | 6h (the complaint corpus is re-indexed daily — `_meta.last_updated`; the search defaults to the lean path `no_aggs=true`, the upstream default `no_aggs=false` costs ~380KB/~20s per call; the `company=` filter is exact and case-sensitive — the corpus' own spelling, resolved with cfpb_suggest_company) | 0.3.31 ✅ |
| legal | `cfpb_suggest_company` | US | —— (born flat) | `cfpb` | local | 24h (the company typeahead's spellings change only with the corpus) | 0.3.31 ✅ |
| legal | `in_sebi_orders` | IN | —— (born flat) | `in_sebi` | local | 12h (the enforcement-orders corpus grows daily; 11 categories verbatim — member_orders 6,433 / ao_orders 12,020; one stateless AJAX-fragment channel serves paging+search+DD-MM-YYYY date windows; a page past the last answers the CLEAN empty page, no snap-back) | 0.3.35 ✅ |
| legal | `tr_spk_bans` | TR | —— (born flat) | `tr_spk` | local | 24h (both ban walls 295 persons + 3 companies, each company auto-enriched with its banned-equity edges — the BIST ticker is the substance; person rows stay two-column: the detail endpoint keys on the UNMASKED MKK number the public list masks) | 0.3.36 ✅ |
| legal | `tr_spk_fines` | TR | —— (born flat) | `tr_spk` | local | 24h (the whole 2,281-row fine register in ONE 1.3MB GET, 14 columns verbatim 2016→; upstream publishes no query surface — the POST yil body is silently ignored — so name/year filter locally; 1,281 subjects are individuals with masked mkkSicilNo) | 0.3.36 ✅ |
| legal | `ru_cbr_warning_list` | RU | —— (born flat) | `ru_cbr_warning` | local | 24h (ONE 3.1MB xlsx = the whole 27,635-row × 12-col warning register (span 2021-02→, nightly rebuild — ToDate=today-UTC rolls the cache key); six violation kinds verbatim Russian (pyramid 14,054 / illegal securities professional 7,356 / illegal lender 2,567 / investment solicitation 116 / platform operator 16 / insurance 57 — rows keep the wording, the filter splits comma/newline parts, two rows carry raw CRLF (kept verbatim — the register's own embedded line breaks, never normalised)); six record types (Интернет-проект 22,798 / Юридическое лицо 3,030 / Точка присутствия 924 / Компания 818 / ИП 64 / Прочее 1); ИНН on only 3,094 rows; internet-project fronts ride the address column (--site covers both); the FIRST accept:'bytes' consumer (transport extension 9 — lossless latin-1, stdlib zipfile, curl intercepted) | 0.3.37 ✅ (the SDK's first RU jurisdiction; FZ 115 statutory public register — the co_sic PII posture; shares host www.cbr.ru with company ru_cbr_credit) |
| legal | `br_bacen_regimes` | BR | —— (born flat) | `br_bacen_regimes` | local | 24h (the whole 25-row special-regimes register, one keyless GET — today a single regime, LIQUIDAÇÃO EXTRAJUDICIAL on all 25 rows (the extrajudicial-liquidation track), Inicio 02/08/2013→30/04/2026; the liquidation's own contact block (responsavel/emails/telefones) rides every row; --cnpj accepts the 8-digit root OR the 14-digit whole key — both sit on every row) | 0.3.38 ✅ (the legal domain's first BR face; shares host olinda.bcb.gov.br with company br_bacen) |
| legal | `br_bacen_complaints` | BR | —— (born flat) | `br_bacen_complaints` | local | 24h (the RDR complaint-index ranking, TWO ops: catalog `GET /rdrweb/rest/ext/ranking` (13 years 2014→2026, periodicidades drift MENSAL 2014-15 → BIMESTRAL 2016 → TRIMESTRAL banks / SEMESTRAL consortiums from 2017) + one period file `/rdrweb/rest/ext/ranking/arquivo?ano=&periodicidade=&periodo=&tipo=` — ';' cp1252 CSV, the 2nd accept:'bytes' consumer; **catalog-as-axis**: ghost (ano, periodicidade, periodo, tipo) combos answer HTTP 204 with a 0-byte body, so the raw layer validates against the catalog BEFORE the wire and answers usage_error with the available combos; **resolution order = year FIRST** (the live `--periodo 4` lesson: cross-year slot resolution silently landed on 2016 BIMESTRAL p4 panels — periodicidade/periodo validate WITHIN the resolved year, default = the latest year carrying the tipo, plus an "older panels: pass an explicit --ano" hint); schema drifts by era, keys present-only: banks 2019+ (Top 15/Demais, Conglomerado rows carry no CNPJ, Índice pt-BR comma decimal honestly blank on unranked rows, answered/upheld/upheld_extrapolated/analyzed + CCS/SCR client families) / banks 2014-18 (size-band Categoria, regulated_upheld/regulated_other/unregulated/complaints_total + FGC clients, Mês period) / consortiums (CNPJ AC 8-digit root on EVERY row — the only full-key branch, clients = consorciados); live anchors banks 2026-T3 221 rows 73 with Índice max 859.383,75 (MW IP) / consortiums 2026-S1 85 rows) | 0.3.39 ✅ (its OWN host bucket www3.bcb.gov.br — NOT the olinda family; probed tmp/probe-br-bacen-0339/) |
| research | `nsf_awards` | US | (born flat) | `nsf` | local | 24 hours | 0.2.2 ✅ (renamed with the domain in 0.2.4; formerly grants) |
| research | `nih_reporter_projects` | US | (born flat) | `nih-reporter` | local | 24 hours | 0.2.2 ✅ (renamed with the domain in 0.2.4; formerly grants) |
| research | `nih_reporter_publications` | US | (born flat) | `nih-reporter` | local | 24 hours | 0.2.4 ✅ |
| research | `openalex_works` | GLOBAL | (born flat) | `openalex` | local | 24 hours | 0.2.4 ✅ |
| research | `openalex_institutions` | GLOBAL | (born flat) | `openalex` | local | 24 hours | 0.2.4 ✅ |
| research | `crossref_works` | GLOBAL | (born flat) | `crossref` | local | 24 hours | 0.2.4 ✅ |
| research | `gb_gtr_projects` | GB | (born flat) | `gb_gtr` | local | 24 hours | 0.2.4 ✅ |
| research | `icite_pubs` | US | (born flat) | `icite` | local | 24 hours | 0.2.4 ✅ |
| research | `biorxiv_details` | GLOBAL | (born flat) | `biorxiv` | local | 24 hours | 0.2.4 ✅ |
| research | `opencitations_citations` | GLOBAL | (born flat) | `opencitations` | local | 24 hours | 0.2.4 ✅ |
| security | `osv_vulns` | GLOBAL | (born flat) | `osv` | local | 24 hours | 0.2.2 ✅ |
| security | `cisa_kev_catalog` | US | (born flat) | `cisa-kev` | local | 24 hours (the full ~1,756-entry catalog fetched and cached once daily; screening afterwards needs zero network; same pattern as csl) | 0.2.2 ✅ |
| security | `euvd_exploited` | EU | —— (born flat) | `euvd` | local | 24 hours (the rolling window is small today but grows continuously; one call returns the whole window, --limit is a local slice) | 0.3.25 ✅ |
| security | `euvd_vulnerability` | EU | —— (born flat) | `euvd` | local | 24 hours (point lookup by CVE or EUVD code; unknown id = HTTP 404 carried as upstream_not_found) | 0.3.25 ✅ |
| procurement | `ny_abo_contracts` | US | —— (born flat) | `ny_open_data` | local | 24 hours (contract rows change slowly) | 0.3.6 ✅ |
| procurement | `ny_mta_procurements` | US | —— (born flat) | `ny_open_data` | local | 24 hours (contract rows change slowly) | 0.3.6 ✅ |
| procurement | `ny_ogs_payments` | US | —— (born flat) | `ny_open_data` | local | 7 days (payment rows are historical fact; ABO/MTA rows stay 24h) | 0.3.12 ✅ |
| procurement | `br_pncp_contracts` | BR | —— (born flat) | `br_pncp` | local | 7 days (historical contract windows stable monthly; recent windows change slowly) | 0.3.0 ✅ |
| procurement | `co_secop_contracts` | CO | —— (born flat) | `co_secop` | local | 24 hours (contract rows change slowly with ultima_actualizacion) | 0.3.0 ✅ |
| procurement | `ungm_contract_awards` | GLOBAL | —— (born flat) | `ungm` | local | 7 days (awards are settled facts; the anti-forgery pairing caches 15 minutes independently) | 0.3.12 ✅ |
| procurement | `wb_procnotices` | GLOBAL | —— (born flat) | `wb_proc` | local | 7 days (immutable after Published) | 0.3.6 ✅ |
| economy | `bis_sdmx_series` | GLOBAL | —— (born flat) | `bis` | local | 24h (the WS_* family refreshes on mixed monthly/quarterly cadences; the key must carry ≥2 dot segments — a one-segment key is every area at once) | 0.3.24 ✅ |
| economy | `bls_series` | US | —— (born flat) | `bls` | local | 12h (monthly/quarterly refresh; the keyless default window shifts monthly) | 0.3.29 ✅ |
| economy | `comext_flows` | EU | —— (born flat) | `comext` | local | 24h (the annual HS mirror on the DEDICATED comext dissemination root — the plain Eurostat root 404s the ds- datasets; at least one filter is required: the filterless mirror is a 413 with a 5-million-cell single-query cap; flow 1 imports / 2 exports; the EU27_2020 aggregate sits alongside country reporters) | 0.3.26 ✅ |
| economy | `ecb_fx_rates` | EU | —— (born flat) | `ecb` | local | 12h (the reference rate republishes every working day; the historical eurofxref CSV is a stale 2010 snapshot and is not used) | 0.3.23 ✅ |
| economy | `eurostat_table` | EU | —— (born flat) | `eurostat` | local | 12h (Eurostat rolls quarterly; multi-value filters must repeat the parameter) | 0.3.23 ✅ |
| economy | `fred_series` | US | —— (born flat) | `fred` | local | 12h (one series per call — several ids answer a ZIP archive the JSON transport cannot carry) | 0.3.23 ✅ |
| economy | `ilo_stat_indicator` | GLOBAL | —— (born flat) | `ilo_stat` | local | 24h (the country reference is required — the world-wide answer is orders of magnitude bigger) | 0.3.23 ✅ |
| economy | `imf_sdmx_series` | GLOBAL | —— (born flat) | `imf_sdmx` | local | 24h (the SDMX 2.1 CSV channel; country AND indicator are both required — a single-segment key is the every-country multi-megabyte wall) | 0.3.24 ✅ |
| economy | `oecd_sdmx_series` | GLOBAL | —— (born flat) | `oecd_sdmx` | local | structure 7 days (DSDs are near-static) / data 24h (EO rolls quarterly, NAAG annually; the flow ref must be the catalog form agency,DSD@DF[,version] — the bare DF id is a 404 — and the key segment count is validated against the DSD dimension list BEFORE the data call, so the short-key 403 never forms; an empty segment is the wildcard) | 0.3.26 ✅ |
| economy | `un_comtrade_trade` | GLOBAL | —— (born flat) | `un_comtrade` | local | 12h (the preview mirror refreshes monthly; the area reference is 7 days) | 0.3.23 ✅ |
| economy | `unsd_sdg_indicators` | GLOBAL | —— (born flat) | `unsd_sdg` | local | 7 days (the 251-indicator catalog; --search is a local scan of the whole catalog, never an upstream query) | 0.3.24 ✅ |
| economy | `unsd_sdg_series` | GLOBAL | —— (born flat) | `unsd_sdg` | local | 24h (seriesCode-only granularity; the geo filter is local — the upstream area parameter is decorative) | 0.3.24 ✅ |
| economy | `wb_countries` | GLOBAL | —— (born flat) | `wb` | local | 7 days (the reference table carries the income band = the buyer-screen dimension) | 0.3.23 ✅ |
| economy | `wb_ids_indicators` | GLOBAL | —— (born flat) | `wb` | local | 7 days (source=6 pins the 577-indicator IDS debt catalog; the DT.* values are served by wb_wdi_values WITHOUT --source) | 0.3.24 ✅ |
| economy | `wb_wdi_indicators` | GLOBAL | —— (born flat) | `wb` | local | 7 days (source=2 is WDI — without it the catalog is every World Bank source at once) | 0.3.23 ✅ |
| economy | `wb_wdi_values` | GLOBAL | —— (born flat) | `wb` | local | 24h (one indicator code per call — the upstream rejects several codes at once) | 0.3.23 ✅ |
| economy | `who_xmart_indicators` | GLOBAL | —— (born flat) | `who_xmart` | local | 24h (the 1,561-row directory carries IND_URI_API, the per-indicator entity set) | 0.3.23 ✅ |
| economy | `who_xmart_values` | GLOBAL | —— (born flat) | `who_xmart` | local | 24h (the geography key is the M49 code; a multi-entity-set indicator is never auto-picked) | 0.3.23 ✅ |

- On-trigger (opened only when a question touches them, no pre-provisioning): WHO GHO / Canada DPD / Japan e-Stat (healthcare); other domains register in this table as they open.
- **Flat main-face lineage** (2026-10-23 ruling: main face = `<domain> <source>_<dataset>` + upstream
  parameter names verbatim; **Python single stack as the sole implementation**; since the 2026-10-27
  registration-convention flip, **the table above is the complete roster of flat faces — 163 faces** — with
  the `service/shared/gateway/capabilities.mjs` snapshot flipped in sync): 0.2.0, 35 faces → 0.2.1 naming
  convention v1.0 finalized, 37 faces (26 renamed / 9 kept + two splits; the Node twin was withdrawn
  2026-10-26) → 0.2.2 domain expansion, 41 faces (grants domain established, security domain established) →
  0.2.3, 42 faces (legal +case-law face) → 0.2.4, 50 faces (**grants→research domain rename** + 8 new faces) →
  0.2.10, 54 faces (healthcare +openFDA four faces, Wave 10) → 0.2.11, 56 faces (legal +UK CMA two faces) →
  **0.3.0, 58 faces / seven domains** (procurement domain established +2 faces; **the verb layer
  (resolve/related/fulltext/trials/label/evidence), frozen aliases (`csl_screening`/`grants`), and 18
  sugar/legacy-alias parameters all removed** — the "removed in 0.3.0" contract honored; from this point on
  the "old verb face" column is pure historical reference, and client/CLI no longer carries that dispatch) →
  0.3.1, 65 faces (healthcare openFDA Wave 10b seven query faces:
  approvals/catalog/orangebook/510k/pma/registrations/classification) → 0.3.2, 67 faces (esg +EUTL catalog
  face +EPA FRS facilities face) → 0.3.3, 72 faces (company European registries five faces) → 0.3.4, 73 faces
  (FR recherche real-time search) → 0.3.5, 78 faces (esg +THETIS-MRV version-ledger catalog +Paris MoU
  port-state-control four faces — first use of the transport extension ⑦ form-urlencoded channel) → 0.3.6, 81
  faces (procurement +World Bank notice stream + NY Socrata two faces:
  wb_procnotices/ny_abo_contracts/ny_mta_procurements) → **0.3.10 face-order dictionary sort + jurisdiction
  chapter** (no new faces; the three World Bank/NY procurement faces are absorbed into the order and stamped
  78→81: within-domain face-name dictionary sort + the success envelope's jurisdiction chapter visible on four
  channels) → **0.3.12, 83 faces** (procurement +UNGM award search/NY OGS third face:
  ungm_contract_awards/ny_ogs_payments — the batch originally numbered 0.3.9 landing via the collection round,
  having yielded twice to 0.3.12: the two faces enter their dictionary-order slots + jurisdiction stamps
  GLOBAL/US; first use of the transport extension ⑧ extra_headers+set_cookie channel) → **0.3.13, 85 faces**
  (0 new faces — nine-face ISO 3166-1 alpha-2 country-prefix unification: uk_cma_*→gb_cma_*,
  tna_caselaw_*→gb_tna_caselaw_*, gtr→gb_gtr, tga_*→au_tga_*, pncp→br_pncp, secop→co_secop; provider
  ids/module names/envelope source.provider in sync, no alias transition; jurisdiction chapter unchanged,
  already ISO) plus the stacked 0.3.8 legal TNA caselaw two faces (gb_tna_caselaw_search/judgment — the first
  keyless-but-licence gate: Open Justice Licence, targeted retrieval only, no bulk computational analysis) →
  **0.3.14, 87 faces** (company +CO RUES master/KR hometax status: co_rues_companies/kr_hometax_biz_status —
  the batch originally claimed 0.3.11 (the UNGM/OGS batch yielded to it and renumbered 0.3.12) and lands as
  0.3.14 after 0.3.12/0.3.13 merged first, renumbered to keep the release version monotonic; PII double gate
  on the CO face, anonymous four-state single-shot on the KR face; jurisdiction stamps CO/KR). → **0.3.15, 87
  faces** (0 new — the TNA English-truth collection round landing after the seventh and eighth collisions: the
  0.3.13 ISO batch stacked directly on the 0.3.8 tip and merged first, so the TNA faces reached main with the
  gb_ prefix and their original Chinese public strings; the 0.3.14 renumber was then overtaken by this CO/KR
  batch; the round re-bases those strings onto the English truth and fixes !154's ungm/ny_ogs docstring leak —
  the gb_tna_caselaw rate-limits row itself landed via the CO/KR batch's ledger catch-up). → **0.3.16, 90
  faces** (legal +`co_sic_sanctions` — the Colombia SIC firm-sanctions register, Socrata $-channel same
  contract as co_secop; healthcare +`gb_mhra_alerts`/`gb_mhra_alert` — the UK MHRA medicines & device
  safety-alert twin, the same gov.uk search/content contract family as gb_cma with two pits nailed: q-mode
  rows drop link (base_path then lives in _id) and the content API has no .json variant; originally claimed
  0.3.14, then 0.3.15 — both landed on main first (the CO/KR company round and this TNA English-truth
  collection round), so the landing number moves to 0.3.16; the TNA-anglicization rider originally attached
  was dropped as redundant — main's 0.3.15 landed the same content) → **0.3.19, 97 faces** (healthcare +CA
  DPD/MDALL four faces +EU RASFF/Safety Gate three faces — the CA+EU product-safety cluster from the
  researched inventory, implemented per the user's split-of-duties ruling (research in a dedicated session,
  implementation here); four keyless providers ca_dpd/ca_mdall/rasff/safety_gate, probe corpus
  tmp/probe-ca-eu-faces/; the number follows main's merged 0.3.18 GLEIF round as the sequential next, R6 still
  owing 0.3.17 (skipped numbers harmless per the 0.3.12 precedent); pits nailed: DPD status closed set
  1|2|3|4|6 with unknown values silently ignored upstream = full 15MB dump, walled SDK-side; MDALL device
  endpoint has no working server-side filter so the licence face is the LIMH stateless point lookup; RASFF
  path needs language segment + trailing slash, dates in the SPA's own dd-MM-yyyy 00:00:00 shape, the
  enum-shaped filters stay unexposed (every probed object shape → the same generic [ERR-1003]); Safety Gate
  report_id hides in the index URLs while detail rows carry the alertDetail path shape — two different regexes
  — and the detail query string is byte-baked into the path per the ukec precedent) → **0.3.20, 97 faces** (0
  new faces — the esg param-fidelity audit round + FDA family rate-group rider: EPA FRS +3 filter columns (`--country-name`
  unlocking the non-US slice / `--site-type-name` / `--epa-region-code`), Paris MoU regime wall (only
  `psc_inspection_regime=1` is live) + limit-cap reversal pinned, the five api.fda.gov faces share
  `rate.group="fda"` (3.9rps/6burst minute-quota, 240/min family line) closing the rate-limits §5-6 ledger
  debt) → **0.3.21, 101 faces** (legal +the debarment-roster line four faces — `afdb_debarred_entities`/`ca_sema_sanctions`/`idb_debarred_entities`/`wb_debarred_firms`:
  the MDB debarment trio (WB global 1,546-row SAP dump / AfDB 1,440-row json-feed / IDB 1,343-row CKAN
  DataStore) + the Canada SEMA consolidated sanctions list 5,708 records; three local full-register scans (csl
  contract, no quartet — nothing upstream to replay) + one server-side face (idb, quartet raw with the full
  sent params); three gates pinned live: AfDB Cloudflare UA-fingerprint (full browser-document suite via
  ext-8, the UNGM family) / CA SEMA Accept content-negotiation (406 to application/json → op `accept:'text'` +
  Accept override text/xml) / WB no UA gate (page-embedded public apikey, the dgcomp public-config-key class);
  jurisdictions GLOBAL×3 + CA; the cross-debarment edge corroborated live across two registers — the wb face's
  China Railway 20th Bureau row "Cross Debarment: AfDB" 2026-10-16→2027-10-23 matches the afdb face's
  same-name row To=2027-10-23; number 0.3.20 / entry 51 / v1.8 reserved for !169 and fulfilled — !169 merged
  first (ce2157be), this batch landed as 0.3.21 per the reservation) → **0.3.22, 102 faces** (esg +the
  transport-compliance single face `euasl_datasets` — the EU Air Safety List's official download catalog on
  transport.ec.europa.eu/transport-themes/eu-air-safety-list_en (the pre-migration /aviation-policy path is
  dead 404): 25 files across 24 official languages — one machine-readable XLSX master (Annex A = ~188
  third-country carriers under an operating ban; Annex B = restrictions/conditions, AIR KORYO / IRAN AIR) + 24
  language PDF renditions; **binary-wall ruling**: the SDK transport is JSON-only (lossy utf-8 decode +
  json.dumps cache would corrupt the xlsx body), so the face is a coordinates/catalog face (the
  eutl_datasets/thetis_mrv_datasets posture — the roster itself travels the batch pipeline; the sheet's ~71
  self-closing `<c/>` cells mean the batch parser must read cell references, not positions); **the document
  UUIDs are publish-time content ids that rotate on every republication** — reconcile against the listing,
  never guess filenames; the hr rendition's `_2` suffix lives on the filename only while the language token
  stays the path segment — the parser splits the query off before the language split. **Same-batch exclusion:
  Tokyo MoU APCIS** (Asia-Pacific PSC inspections) — three independent time budgets (90s/180s/590s) all stall
  at the same ~48.8KB byte wall with the connection held silently; no paging; filter codes undiscoverable (the
  live form's selects ship only placeholder options) → any month with ≥40 rows would be silently truncated in
  an SDK face; the research note's slow-server attribution is hereby corrected to a byte wall) → **0.3.23, 112
  faces** (economy +the domain-founding ten-face batch — the eighth domain `sdk/python/agentdata/economy/`
  stood up as the **country-level denominator layer** (the subject is the country, never the company: these
  faces emit no company fact, occupy no rec_type, and never enter the db main ledger — the raw layer keeps the
  reference-layer posture per the 2026-10-13 ruling); seven keyless provider modules
  (wb/eurostat/ecb/fred/who_xmart/un_comtrade/ilo_stat), probe corpus sdk/tmp/probe-economy/ (2026-11-02);
  faces wb_wdi_values/wb_wdi_indicators/wb_countries (World Bank — the cross-country comparable development
  baseline), eurostat_table (EU official statistics), ecb_fx_rates (the single base-currency conversion
  factor), fred_series (the US series leg), who_xmart_indicators/who_xmart_values (WHO health baselines),
  un_comtrade_trade (the bilateral trade mirror), ilo_stat_indicator (the labour-market baseline);
  jurisdictions GLOBAL×7 + EU×2 + US×1; pits nailed: the World Bank rejects several indicator codes in one
  call (a `120 Invalid value` message inside the body, not an HTTP error); Eurostat multi-value filters must
  repeat the parameter (the `+` form is a 400, the comma form silently returns zero cells) and a geo outside
  the table returns zero cells with no upstream error; the ECB's historical eurofxref CSV is a stale 2010
  snapshot (the live SDMX csvdata endpoint is used instead, and the value means units of {CCY} per 1 EUR);
  FRED answers several series ids with a ZIP archive (binary wall — one series per call, locally walled) and
  an unknown series id with an HTML error page (magic-number check → not-found); WHO's geography key is the
  M49 code, not ISO-3 (translated through the multilingual REF_GEO_WIDE table) and a multi-entity-set
  indicator is never auto-picked (the candidate list goes to the caller); Comtrade's reporter/partner must be
  the numeric area code (ISO-3 is translated through a reference table whose historical and duplicate rows
  make a naive map wrong — USA is 842, not 840 or 841); ILOSTAT's `format=json` is a query parameter, and the
  local curl stack answers an empty 200 while the urllib channel is fine every time — a client-stack issue,
  not an upstream one) Envelope quartet `query={source: raw|assembled, upstream, assembled_from?}` (upstream =
  the echoed source of truth of the parameters actually sent, replayable) → **0.3.24, 117 faces** (economy
  +the five-face expansion batch — `imf_sdmx_series`/`bis_sdmx_series` (two more SDMX 2.1 rides on the ecb
  generic-CSV idiom — Accept `application/vnd.sdmx.data+csv;version=1.0.0`, because a JSON Accept is silently
  answered as XML), `unsd_sdg_indicators`/`unsd_sdg_series` (the UNSD SDG API), and `wb_ids_indicators` (the
  World Bank IDS debt-statistics catalog riding the existing wb provider); three new providers
  imf_sdmx/bis/unsd_sdg, all keyless, all polite 0.5 rps; probe corpus tmp/probe-economy-0324/ (2026-11-03);
  jurisdictions GLOBAL×5; pits nailed: IMF requires country AND indicator in the series key (a single-segment
  key is the every-country multi-megabyte wall) and the dimension columns are the ones between DATAFLOW and
  TIME_PERIOD — they differ per dataflow; BIS requires ≥2 key segments for the same reason, a wrong key is not
  a block but HTTP 404 with an SDMX code-100 error inside (carried not-found), and the DSD id is not the
  flow-id prefix (WS_XRU→BIS_XR — the CSV columns carry the dimensions, no DSD call needed); the UNSD geo
  filter is local — the upstream `area` parameter is decorative (byte-identical answers) and the series
  granularity is seriesCode-only (the Indicator/Data cut is the 3.2M-row beast, never called); the IDS catalog
  pins source=6 (the 577 DT.* indicators) while the DT.* values are served by wb_wdi_values WITHOUT --source —
  with source=6 the value endpoint falls back to source 2 and answers a 175 indicator-was-not-found body) →
  **0.3.25, 119 faces** (security +the EUVD two-face expansion — `euvd_vulnerability` (ENISA EUVD point lookup
  by CVE or EUVD code: the real API host euvdservices.enisa.europa.eu hides behind the SPA shell — /api/v1/*
  on the public host answers shell HTML, the base came out of the SPA main.js; record richer than the NVD
  public face — CVSS vector+score+version, EPSS inline, exploitedSince, CVE+GHSA aliases,
  vendor×product×version ranges, EU member-state CSAF advisories) and `euvd_exploited` (the EU KEV rolling
  window, --limit a local slice, cisa-kev posture; the 399,311-row mapping dump stays raw-side); one new
  keyless provider euvd at 0.5/2; probe corpus tmp/probe-euvd-0325/ (2026-11-03); jurisdictions EU×2; pits
  nailed: Java "MMM d, yyyy, h:mm:ss AM" dates ISO-normalized locally with a fixed month table (strptime %b is
  locale-bound — the GBK console broke on it), unknown id = HTTP 404 with {"error":"EUVD not found"} carried
  as upstream_not_found, references/aliases arrive as newline-joined single strings and are split locally; the
  same batch corrects booklet 91's stale "registry not initiated — no face" ruling — security was already standing since 0.2.2, EUVD
  is an existing-domain expansion) → **0.3.26, 121 faces** (economy +the two-overturn expansion batch —
  `comext_flows` (the Eurostat Comext annual HS2-4-6 trade mirror on the **dedicated comext dissemination
  root**: the URL must insert the `comext/` segment, a plain-root call for ds-/DS- datasets is a 404 "not
  available for dissemination"; JSON-stat 2.0 with the same grid contract as eurostat so the decoder is
  imported from the sibling; **this overturns booklet 84's "doc-only, no API face" ruling**, which predated the
  economy domain — the same overturn pattern as booklet 91; the filterless mirror is a 413 "Full extraction
  forbidden" — 31.3 billion cells with a 5M single-query cap — walled locally behind at-least-one-filter; flow
  1 imports / 2 exports; the EU27_2020 aggregate sits alongside country reporters; live anchor DE×CN×HS85×2024
  imports = 29,698,131,086 EUR) and `oecd_sdmx_series` (the OECD SDMX public REST — **this overturns the
  design book §5 "OECD needs a key" misdiagnosis**: the service is fully keyless, the wall was request form —
  the flow reference must be the catalog spelling `agency,DSD@DF[,version]` the catalog itself carries (the
  bare DF id answers 404 "Could not find Dataflow and/or DSD"), and the key must carry EXACTLY one
  dot-separated segment per DSD dimension (a short key is a 403 "Not enough key values in query, expecting 12
  got 6"; an empty segment is the wildcard) — so the face walks the structure first
  (/datastructure/{agency}/{DSD}/{version}?references=none, SDMX-JSON, cached 7 days) and validates the
  segment count locally with the dimension list in the error, converting both walls into usage_error before
  any data call; data rides the SDMX generic-CSV channel shared with imf_sdmx/bis; live anchors EO 119 `DEU..`
  2024-2027 = 238,358 B and NAAG_I B1GQ_R_POP DEU 2025 = 61,900.5 USD_PPP_PS); two new keyless providers
  comext/oecd_sdmx at 0.5/2; probe corpus tmp/probe-economy-0326/ (2026-11-03); jurisdictions EU + GLOBAL;
  **the batch also starts the per-face offline-test debt paydown** — the 0.3.23/24 economy faces shipped with
  structural gates only, this batch adds test_flat_economy_comext_oecd.py (8 tests: the 413 wall,
  repeated-parameter mirror, comma→repeated normalization, flow-form walls, segment-count validated
  structure-first with the data call never formed, the two-call URL shape, CSV row shaping, 404 carried
  not-found); same-batch exclusion: UN WPP — the catalogs answer keyless but the data endpoint is a 401 with
  zero bytes across all path shapes, excluded under the keyless-only ruling (the population denominator stays
  with wb_wdi_values SP.POP.TOTL)) → **0.3.27, 123 faces** (legal +the gazette/IE-defaulters pair — the legal
  screening round's first implemented batch: `gb_gazette_notices` (The Gazette official-record search, the
  London/Edinburgh/Belfast official journal since digitization, OGL licence — the gazette recipe's noticeCode
  2404-2432 insolvency filter made an SDK face; **two dead upstream params pinned**: `noticecode=` is silently
  ignored (the real filter is `noticetypes`, +-joined) and `categorycode=` returns empty; on the
  corporate-insolvency codes `title` = the company name and `f:name`+`f:familyName` = the placing party (the
  liquidator, or the edition when filed centrally); `geo:Point` = registered-office coordinates; `f:total`
  arrives as a STRING; the `--insolvency` preset expands the 13-code chapter, unioned with any explicit
  noticetypes; a bare search is the 4,887,099-notice bulk wall walled locally; page-size hard cap 100 with
  arbitrary values honored) and `ie_revenue_defaulters` (the Irish Revenue statutory quarterly tax-defaulters
  publication — the index→CSV two-step: the index links the current year only (quarters × parts ×
  pdf/xlsx/xls/csv siblings, locally only the .csv matches; March part 1 ships .xls as a one-off), the quarter
  defaults to the latest on the index; **Accept 406 gate pinned live**: the transport's default
  application/json is refused on BOTH endpoints, the ext-8 "text/html, */*" override passes — the ca_sema
  content-negotiation family's fourth member; **the two parts are two different tables** (a live-acceptance
  overturn of the pre-implementation probe, which had captured only the part-2 shape): part 1 = penalties
  determined by a court (Issue Type / Fine Amount € / Sentence Imposed / No. of Charges — the header's € byte
  arrives as the U+FFFD replacement char, the file's own mojibake, collapsed in header normalization; fines
  carry trailing .00), part 2 = Revenue settlements (the five money columns), a `kind` field echoing which
  schema the rows follow; the CSV carries a UTF-8 BOM and trailing-space headers, amounts are quoted
  comma-thousands with surcharge annotations dropped to the leading number, empty Unpaid = settled None vs a
  plain 0 fact; individuals and companies share one list; the PII stance follows the co_sic precedent — a
  statutory court-settled publication, names and addresses carried verbatim); two new keyless providers
  gazette/ie_revenue at 0.5/2 and 0.2/1; probe corpus tmp/probe-legal-0327/ (2026-11-03); jurisdictions GB +
  IE; v1.15; per-face offline pins test_flat_legal_0327.py, 11 tests; live anchors: gazette
  text=acme+insolvency = 25 notices / 5 rows, noticetypes=2432 = 157,792; IE june 2026 part 1 = 55 court rows,
  part 2 = 20 settlement rows (3 ROCKECO LIMITED Total €1,266,198)) → **0.3.28, 124 faces** (legal +OCC
  bank-enforcement face `us_occ_enforcements`: the OCC monthly bank-enforcement news releases, a
  listing→release two-hop over occ.gov — the by-year news-release listing (structured `data-column` rows
  Date/ID "NR 2026-93"/Title, verified live 2005-2026, which is the year floor; actions back to 1989 live in
  the EASearch database, deliberately out of SDK scope with docket No. AA-ENF-* as the official join key) →
  the releases whose title carries "Enforcement Actions" (~10-12 a year) → the release body, which comes in
  TWO SCHEMAS both parsed (a `form` field echoes which: sentence form 2024+ — "Actions taken against banks
  are:" + one `<li>` per action, action-type words anchoring the order PDFs, CMP sentences scale their own
  wording "$750 million"→750000000, and an IAP section after the "actions against IAPs" marker holds
  individual prohibition orders parsed through the ", for "/", based on " dual hinge with the docket tail cut
  — names published by statute, the co_sic precedent; table form ≤2020 — `<h2>` sections over 4-column tables
  No./Name-Bank-City/State/Date, the who cell split at the LAST comma so bank names carrying their own commas
  ("M.Y. Safra Bank, FSB, New York") survive intact, the No. cell anchoring the PDF = action_docs parity);
  month selection crosses eras (2026+ titles carry "for October 2026", 2020/2010 titles carry no month and
  fall back to the listing date column; a missing month is upstream_not_found listing what each release
  actually covers); the multi-entity variant ("against three subsidiary banks of X : B1 ; B2 ; and B3" sharing
  one allegations sentence) explodes to one row per bank with holder/holder_city/holder_state carrying the
  parent and abbreviated dockets ("55, 56, and 57") kept verbatim; --all walks every enforcement release of
  the year with release_nr on each row; NO gate of any kind — plain urllib + default headers = 200 pinned
  live; probe corpus tmp/probe-legal-0328/ (2026-11-03); jurisdiction US; v1.16; per-face offline pins
  test_flat_legal_0328.py, 10 tests; live anchors: October 2026 sentence form = 4 rows (Amex CMP $350M dockets
  46+47, BoA CMP $750M docket 41, two IAP prohibition orders), February 2020 table form = 20 orders (M.Y.
  Safra Bank, FSB intact through the comma split)) → **0.3.29, 125 faces** (economy +BLS statistical-series
  face `bls_series`: POST JSON channel over api.bls.gov/publicAPI/v2/timeseries/data/ — the US federal
  statistical-series face symmetrical with fred_series (anchors CPI-U CUUR0000SA0 / unemployment LNS14000000 /
  nonfarm payrolls CES0000000001); documented keyless caps 25 series × 10-year window × 500 queries/day pinned
  live; the INVERTED CLAMP walled locally — upstream silently keeps the EARLIEST ten years (2010..2026
  answered 2010..2019, pinned), the face refuses >10-year windows with evidence before the wire; bogus ids
  ride inside a 200 and surface as series_without_data; key-gated options (catalog family) never sent; string
  values → float, "." = null; newest-first upstream sorted ascending; live anchor: three anchor series,
  default window = 99 observations (33 × 3, 2024..2026, CPI-U 2026-09 = 336.940 latest, nonfarm 159,044 latest
  P=preliminary); probe corpus tmp/probe-economy-0329/ (2026-11-03); jurisdiction US; v1.17; per-face offline
  pins test_flat_economy_bls.py, 15 tests) → **0.3.30, 127 faces** (company +the NZ Companies Office register
  pair `nzco_companies`/`nzco_directors` — the company master register in its 15th country and the first
  South-Pacific jurisdiction: the register UI search on the canonical parameter set
  mode=standard&type=entities&q&advancedPanel=true&entityTypes=ALL (a bare ?q= answers the empty-match page —
  the full set is REQUIRED, pinned in the research probe), rows carrying the DUAL official keys (company
  number + the 16-digit NZBN cross-government join key) and the register's own status words Registered/Removed
  verbatim (NOT "Active"), paging in the pager's own vocabulary start×limit with BOTH observed sizes {5, 15}
  shipped and every other size walled as unpinned, entityTypes closed to the filter form's own checkbox codes
  (LTD/UNLTD/COOP=NZ, ASIC/NON_ASIC=overseas), has_next derived from the pager's own offsets, zero-hit = an
  empty page not an error; the directors tab with the H1 triple confirmation (a number mismatch refuses to
  attribute rows across companies), current appointments only (the ceased section renders in different markup
  and never enters the td.director blocks), whitespace-collapsed full legal names, the statutory-public
  residential address carried verbatim whatever the register shows, and the appointment date in the register's
  own wording; no gate of any kind — the honest agentdata UA passes (the occ.gov posture); research volume
  self-scored P1 7/7; probe corpora tmp/probe-nzco/ + tmp/probe-company-0330/ (2026-11-03); jurisdictions
  NZ×2; v1.18; per-face offline pins test_flat_company_nzco.py, 13 tests; live acceptance one shot per face
  2026-11-03: "air new zealand" = 15 rows page 1 + more pages (116030 Removed / 102153 Registered, both
  NZBN-keyed), 104799 = AIR NEW ZEALAND LIMITED (Registered) 8 current directors) → **0.3.31, 129 faces**
  (legal +the CFPB consumer-complaint pair — `cfpb_complaints`/`cfpb_suggest_company`: the US Consumer
  Financial Protection Bureau's Consumer Complaint Database (consumerfinance.gov, keyless, CC0, ~18,879,284
  complaints re-indexed daily), the OpenSearch envelope parsed into total/relation/rows + the _meta block
  (license, last_updated, total_record_count, break_points) with the 15 official complaint fields as the row
  whitelist; one new provider cfpb at 0.5/2; probe corpus tmp/probe-0331/ (2026-11-03); jurisdiction US×2;
  **four upstream traps pinned live**: (1) `company=` is EXACT and case-sensitive — `company=TRANSUNION` = 0
  hits while the corpus' own spelling "TRANSUNION INTERMEDIATE HOLDINGS, INC." = 2,591,659, so the typeahead
  is the resolution channel (a brand name is NOT the corpus key); (2) `term=` is a DEAD parameter — accepted
  and silently ignored, `field=company&term=Discover` answers the whole corpus (18,879,284 hits, every score
  1.0) — the live name is `search_term`; (3) `no_aggs=false` (the upstream default) costs ~380KB and ~20s per
  call — the face takes the lean path (`no_aggs=true`) unless `--aggregations` opts in; (4) the aggregation
  block's per-field doc_count is NOT reliably filter-scoped (a 0-hit filter collapsed product/state to 0 while
  company still reported the whole corpus; a 2.6M-hit filter left state at 18,879,284) — it is a corpus-wide
  value census, not a facet count, and the face says so; closed sets measured corpus-wide from the aggregation
  census of 2026-11-03 (the bucket counts sum to the whole corpus, so the value domain is complete): timely
  {Yes,No} / submitted_via {Web,Referral,Phone,Postal mail,Fax,Email} / company_response 8 values / state 63
  codes — `issue` (179 values), `company_public_response` (10 buckets, ~55% coverage), `tags` and `zip_code`
  are deliberately NOT walled; `--field` without `--search-term` is refused as the silent no-op it is; the
  array filters explode into repeated keys upstream and a string value is never comma-split (the corpus'
  company names carry commas); v1.19; per-face offline pins test_flat_legal_cfpb.py, 23 tests; live acceptance
  one shot per face 2026-11-03: search_term=Discover+field=company = 44,503 matches / 3 rows (DISCOVER BANK —
  Mortgage/CA-Debt-collection/VA-Credit-card), the typeahead = 3 spellings (DISCOVER BANK / Account Discovery
  Systems, LLC / Discovery Auto Sales LLC); **this overturns the design book §5 'CFPB complaints API — excluded wrap (API-domain
  egress-block family)' ruling** — the search API is keyless and ungated from this egress, the ban was about the API
  *domain* house, not the CCDB host) → **0.3.32, 131 faces** (company +the CZ ARES economic-entities register
  pair — `cz_ares_ekonomicke_subjekty`/`cz_ares_ekonomicke_subjekty_vyhledat`: the Czech ARES official JSON
  REST (ares.gov.cz/ekonomicke-subjekty-v-be/rest, keyless, no registration), **the company master register's
  16th country and the first Central-European jurisdiction**; research volume cz-ares-registry self-scored P1
  7/7; the single-record face GET /ekonomicke-subjekty/{ico} with the IČO validated against the upstream's own
  regex [0-9]{8} (a malformed one is refused locally with the upstream's 400 teaching body
  CHYBA_VSTUPU/VSTUP_NEVALIDNI_FORMAT_ICO never reaching the wire; the ARES surrogate "ARES_00358750" is NOT
  an IČO and is refused by the same validator), an unknown-but-well-formed IČO answering HTTP 404 NENALEZENO
  carried as upstream_not_found, and the record carrying the structured address with the full administrative
  code ladder (**kodAdresnihoMista = the RUIÁN address-point code**, the address-graph join key), the legal
  form in two slots (pravniForma/pravniFormaRos), the VAT key dic=CZ<ico>, the founding/last-update dates, the
  CZ-NACE 2008 list beside the coarser czNace list, the **16-register status matrix** seznamRegistraci (each
  register's own state — one register being ZANIKLY is not a dissolved company, never collapsed into one
  status) and dalsiUdaje projected into sources[] (the same subject's per-register variant, the court source
  carrying its file number spisovaZnacka); the name-search face POST /ekonomicke-subjekty/vyhledat
  (**POST-only**, GET answers 400) with the upstream's camelCase body keys {obchodniJmeno,pocet,start} and
  pocetCelkem as the real total; **the upstream folds the record names to ASCII but not the query** — "ČEZ"
  verbatim answers the 30 "EZ …" names while the ASCII "cez" answers the 46 names containing ČEZ (both
  measured live), so the face folds the query itself and echoes both forms; **the rows do not share one join
  key** — `ico` is present only on rows whose primary source carries the trade-register identifier, an
  RZP-primary row carries only the ARES surrogate icoId which the single-record face refuses, so ico is null
  for those rows and the reason states how many rows of the page are joinable; pocet walled to 1-100 as our
  politeness cap (the upstream publishes no maximum); one new provider cz_ares at 0.5/2; probe corpus
  tmp/probe-company-0332/ (2026-11-03); jurisdiction CZ×2; v1.20; per-face offline pins
  test_flat_company_cz_ares.py, 14 tests; live acceptance one shot per face 2026-11-03: 45274649 = ČEZ, a. s.
  (6/16 registers active, address point 25583697, 29 NACE-2008 codes, the court file number B 1581/MSPH),
  "ČEZ" = 46 matches with the fold echoed) → **0.3.33, 134 faces** (company +the offshore Channel-Islands
  regulated-registers trio — `gg_gfsc_regulated_entities`/`gg_gfsc_registered_businesses`/`je_jfsc_regulated_entities`:
  the Guernsey GFSC and Jersey JFSC financial-services registers, **the company master register's 17th and
  18th jurisdictions and the first offshore financial-centre jurisdictions (Crown Dependencies)**; two new
  keyless providers gg_gfsc/je_jfsc at 0.5/2; probe corpus tmp/probe-company-0333/ (2026-11-04); the GFSC
  faces are one-shot full-feed local scans (the afdb debarment posture — the feed is the site search's own
  backing store): the regulated feed ships 3,795 rows × 2.4MB with **HTML-embedded display fields**
  (name/GFSC_x0020_Ref/Licences/View each arrive as `<a href="…">text</a>`, name even carrying a leading tab —
  stripped locally with the href rescued as the register's own detail path), **one row per licence group** so
  the same entity appears on 2+ rows when its groups sit in different states (26 such refs; 1818 Venture
  Capital = an Investment Licensee row surrendered=0 + a revoked Primary Licensee row surrendered=1 — the
  envelope counts total_matched rows AND entities_matched distinct refs side by side), surrendered is a
  "0"/"1" **string** on the wire → bool, licence labels embed commas ("Secondary Licensee, Pension Provider"
  is ONE combined group of 43 rows, not two licences — the filter is contains), Status is null on 1,571 rows
  (the register states nothing, not missing data) beside Active 1,579 / Inactive 645, **refs are not uniformly
  7-digit** (legacy 5-6-digit refs 16020/80277/134767 — the ref filter matches exactly with no length
  assumption), GreenFund/Natural_Capital_Fund "Yes" → bool; the registered-business feed is the same shape
  minus status/surrendered (133 rows; Accountant 74 / Estate Agent 22 / Money Service Providers 20 / Legal
  Professional 17; 23 refs dual-listed on the regulated feed); the JFSC face is a POST site-search (Umbraco
  RegulatedEntitiesSearch/GetResults with {"Keyword","PageSize","PageNumber","Refiners":[]}) where **NoResults
  is a RESULT COUNT, not a zero flag** (Keyword "Barclays" → NoResults=1 with one row — the total lives in a
  key that reads like an error state), the rows are site-search rows (Title/Url/Rank) with the official
  licence text verbatim in Properties[0].LawSection parsed into law/code/ref triplets (raw kept alongside;
  Barclays = five sections Banking DC0076 … MSB0107) and the entity id the numeric tail of the register Url;
  **Refiners are not exposed** (the facet option values are space-joined lowercase keys — a lossy spelling
  that would break on any reword, the rasff precedent); keyword is required locally (the empty-keyword POST
  enumerates the whole register — unpinned, harvest-side); PageSize walled 1-100 as our politeness cap;
  licence gates: the GFSC /copyright page sets no reuse restriction, the JFSC privacy policy acknowledges
  third-party access to the public register) → **0.3.34, 135 faces** (company +the KZ GBD_UL master-register
  face `kz_gbd_ul_companies`: the Kazakhstan data.egov.kz GBD_UL legal-entities register (research volume
  kz-egov-gbd-ul, booklet 209), **the company master register's 19th jurisdiction and the first Central-Asian one**;
  the getdata endpoint is a real-time server-side search (not a feed dump) at GET
  /datasets/getdata?index=gbd_ul&version=v1&page=&count=&text= answering {elements, totalPages, totalCount,
  currentPage} with 13 columns in bilingual pairs (nameru/namekz, okedru/okedkz, statusru/statuskz,
  addressru/addresskz) plus bin (the 12-digit hard key), datereg, director and id; **a portal-session cookie
  gate discovered and cracked across four probe rounds, falsifying the research volume's same-day
  "cookie-free" claim**: a cookieless getdata, cookies alone, and the XHR header pair alone all answer an HTTP
  404 stub — the working channel bootstraps via the dataset page GET (minting OPENDATA_PORTAL_SESSION +
  cookiesession1) then carries Cookie + X-Requested-With + Accept + Referer; the SDK caches the pairing 15
  minutes (the ungm anti-forgery posture) and a 404 on getdata = pairing expired, re-collected once
  automatically; **count is hard-clamped to 20 upstream** (count=100 answers 20 rows with totalPages
  recomputed on the clamped value — walled locally 1-20 with the evidence so the page math never lies);
  **column/order sort params are silently ignored** (byte-identical rows to the unsorted baseline, no error —
  not shipped, overturning the research volume's sort claim); **a page past the last silently snaps to the
  last page** (page 200199 at count=5 answered currentPage 200198 with the last page's 4 rows — no empty-page
  signal, so has_more reads the ECHOED currentPage); **datereg is tri-modal** (bare date / +06:00 pre-2024
  Almaty offset / +05:00 post-2024 unified-KZ offset, mixed within one page — carried verbatim); missing
  values arrive as "" (never null) and map to null; the pre-BIN-era rows (page 1's 1995-1999 registrants)
  carry bin="" — the register's own statement; duplicate rows with the same bin exist mid-corpus; totalCount
  drifts with the live register (1,000,786 at research time → 1,000,989 at probe time); director is the
  register's public officer name (the co_rues representante_legal PII posture); version=v1 is mandatory
  (missing = a Play 500 "null") and always sent; text is the server-side name filter (total reflects the
  filtered count: ВЕЛЛЕТ → 2); one new provider kz_gbd_ul at 0.5/2 (no published quota — the registry-search
  family posture); probe corpus tmp/probe-company-0334/ (2026-11-04); jurisdiction KZ; v1.22; per-face offline
  pins test_flat_company_kz_gbd_ul.py, 22 tests) → **0.3.35, 138 faces** (legal +company pair +the IN SEBI
  trio — `in_sebi_orders`/`in_sebi_intermediaries`/`in_sebi_default_brokers`: **the SDK's first
  India-jurisdiction faces** (legal's first IN face + the company master register's 20th jurisdiction), two
  new keyless providers in_sebi (legal) + in_sebi_intm (company) — the same-org-across-domains wb/wb_proc
  precedent; all three surfaces ride www.sebi.gov.in AJAX-fragment POSTs parsed at the provider layer; see
  changelog entry 68 for the trap ledger) → **0.3.36, 141 faces** (legal +company pair +the TR SPK trio —
  `tr_spk_fines`/`tr_spk_bans`/`tr_spk_listed`: **the SDK's first Turkey-jurisdiction faces** (the 21st
  jurisdiction), two new keyless providers tr_spk (legal) + tr_spk_borsa (company) — the
  same-org-across-domains in_sebi/in_sebi_intm precedent repeated on one host (ws.spk.gov.tr shares the
  host-layer bucket); the research volume's Chrome-UA+proxy+Referer channel was falsified at the SDK layer —
  honest agentdata UA + direct egress + zero extra headers = 200 on all seven endpoints; see changelog entry
  69 for the trap ledger) → **0.3.37, 143 faces** (legal +company pair +the RU CBR duo — `ru_cbr_warning_list`/`ru_cbr_credit_orgs`:
  **the SDK's first Russia-jurisdiction faces** (the 22nd jurisdiction), two new keyless providers
  ru_cbr_warning (legal) + ru_cbr_credit (company) — the same-org-across-domains pair precedent repeated on
  one host (www.cbr.ru shares the host-layer bucket, 0.2/1 the static-heavy-file posture); the warning face is
  the FIRST consumer of transport extension 9 (accept:'bytes' — the binary xlsx ships as a lossless latin-1
  string, re-encoded and unzipped with stdlib zipfile); see changelog entry 70 for the trap ledger) →
  **0.3.38, 148 faces** (legal +company pair +the BR BACEN Olinda quintet — `br_bacen_regimes`/`br_bacen_institutions`/`br_bacen_branches`/`br_bacen_domains`/`br_bacen_dasfn`:
  **the SDK's first Brazil-jurisdiction faces** (the 23rd jurisdiction), two new keyless providers br_bacen
  (company ×4) + br_bacen_regimes (legal) — the same-org-across-domains pair precedent repeated on one host
  (olinda.bcb.gov.br shares the host-layer bucket, 0.5/4 the polite publication posture); the DASFN path trap:
  the recipe's /DASFN/v1 form answers 403 — the live path is /DASFN/versao/v1/ (a malformed-service response,
  not a gate); see changelog entry 71 for the trap ledger) → **0.3.39, 149 faces** (legal +`br_bacen_complaints`:
  the BR BACEN rdrweb complaint-index ranking — provider on its OWN host bucket (www3.bcb.gov.br, not olinda),
  the catalog-as-axis posture (ghost period combos answer HTTP 204 with a 0-byte body, so the wall sits before
  the wire) and the year-first resolution order; see changelog entry 72 for the trap ledger) → **0.3.40, 150
  faces** (company +`tr_bddk_institutions`: the TR BDDK authorised-institution card register — twelve category
  pages, 640 cards, on its OWN host bucket (www.bddk.org.tr, not the SPK family); the cards live in the popup
  button's data-* attributes, not in the table, and "-" is the upstream placeholder, not a value; see
  changelog entry 73 for the trap ledger)  → **0.3.41, 152 faces** (company +`de_inso_search`/`de_inso_register_lookup`: the German federal
  insolvency announcements — a Jakarta Faces postback portal, not a query API; the SDK's first DE
  jurisdiction; see changelog entry 77 for the trap ledger) → **0.3.42, 153 faces** (company
  +`jp_fsa_licensed`: the JP FSA licensed-institution farm — thirty-one keyless XLSX registers
  behind one hub, one local-scan family face; the SDK's first JP jurisdiction; see changelog entry
  78 for the trap ledger) → **0.3.43, 154 faces** (company +`ca_ccaa_records`: the CA OSB CCAA
  restructuring roster — a CKAN-catalogued cumulative XLSX resolved latest at call time; transport
  extension 10 absolute-URL path ops; see changelog entry 79) → **0.3.44, 155 faces** (company
  +`es_cnmv_entities`: the ES CNMV entidades register — fourteen categories behind one endpoint,
  local scan, ten key kinds counted never guessed; see changelog entry 80) → **0.3.45, 157 faces**
  (company +`es_borme_day`/`es_borme_notice`: the ES BORME daily gazette pair — one day page + one
  notice XML, the no-publication day a structured published=false; see changelog entry 81) →
  **0.3.46, 159 faces** (company +`sg_datagovsg_datasets`/`sg_datagovsg_dataset_download`: the SG
  data.gov.sg platform pair — the SDK's first SG jurisdiction; catalog one-page walk + two-step S3
  mint, coordinates-only; see changelog entry 82) → **0.3.47, 161 faces** (legal
  +`at_ris_judgments`/`at_ris_statutes`: the AT RIS OGD pair — the SDK's first AT jurisdiction,
  sixteen Judikatur shards + consolidated Bundesrecht; see changelog entry 83) → **0.3.48, 163
  faces** (company +`tx_tdlr_licenses`/`wa_doh_credentials`: the US state-license Socrata twin — the
  SDK's first US sub-national state-axis faces on state-code prefixes; see changelog entry 84)
  → **0.3.49, 166 faces** (company +`chi_bacp_licenses`/`lacity_registrations`/`nyc_dcwp_licenses`:
  the US city-license Socrata trio — the 0.3.48 state-axis ruling extended to the city axis, faces
  named on the host/locality stem (`lacity` deliberately not `la_` — LA is ISO-3166 alpha-2 Laos and
  SDK prefixes are country codes); see changelog entry 85) → **0.3.50, 172 faces** (legal
  +`us_ferc_elibrary`/`ie_sipo_lobbying`/`ee_erjk_quarterly_reports`/`ee_erjk_election_reports`/
  `ua_nazk_parties`/`ua_nazk_party_reports`: the enforcement/party-assets realtime tier-one sextet
  — **the SDK's first EE and UA jurisdictions** (27→29); see changelog entry 86)
  → **0.3.51, 176 faces** (legal +`fr_adlc_sanctions`/`it_arera_decisions`/`us_cftc_enforcement`,
  company +`us_fmcsa_carriers`: the enforcement tier-2 trio + the FMCSA carrier census — **the
  SDK's first IT jurisdiction** (29→30), fr_adlc the legal domain's first FR face (FR itself
  pre-existing via company fr_recherche); see changelog entry 87
  → **0.3.52, 176 faces (0 new)**: the discovery-surface machinery batch — the reflection-based
  `agentdata capabilities` + three CLI repairs + cache keys pinned to the upstream host; see
  changelog entry 88)
  → **0.3.53, 180 faces** (company +`fr_regafi_authorisations`/`fr_regafi_entities` — FR's second
  company axis, the ACPR register pair; esg +`uk_fhrs_establishments` — **the esg domain's first GB
  face**; healthcare +`us_npi_organizations` — the NPPES registry pinned to NPI-2; no new
  jurisdiction); see changelog entry 89)
  → **0.3.54, 182 faces** (**the transportation domain founded — the ninth domain**: seven faces
  migrated unrenamed — euasl + paris_mou x4 + thetis_mrv from esg (13→7, back to E+S proper) and
  us_fmcsa from company (55→54); +`ca_ccar_search`/`ca_ccar_aircraft` new, the Transport Canada
  CCAR pair — the CA transport axis; no new jurisdiction vocabulary entry); see changelog entry 90)
  → **0.3.55, 186 faces** (legal +`mx_cnv_sanctions`/`mx_sabg_sanctioned_servants`/
  `nl_rechtspraak_search`, esg +`mx_sgm_concesiones`: the API-expansion batch A quartet — **the
  SDK's first NL-legal and first MX legal/esg jurisdictions** (30→32; MX debuts in legal and esg
  the same day); see changelog entry 92)
  → **0.3.56, 194 faces** (company +`de_register_search`, the J-PlatPat IP trio
  `jp_trademark_search`/`jp_patent_search`/`jp_design_search` + `kr_kipris_patents`, healthcare
  +`jp_navii_facilities`, legal +`kr_law_statutes`/`kr_law_precedents`: the API-expansion batch B
  major-power axis I — no new jurisdictions (31 held), DE/JP/KR deepened only; see changelog
  entry 93)

  → **0.3.57, 198 faces** (company +`es_oepm_bopi` + the KAP pair `tr_kap_members`/
  `tr_kap_disclosures`, legal +`es_boe_sumario`: the API-expansion batch C major-power axis II —
  no new jurisdictions (31 held), ES/TR deepened only; `tr_ekap` deferred at the verify gate (the
  human-verification gate came ON); see changelog entry 94)

  → **0.3.58, 207 faces** (company +the FDIC BankFind sibling quartet `fdic_failures`/
  `fdic_financials`/`fdic_history`/`fdic_locations` + the INPI accounting pair `fr_inpi_ratios`/
  `fr_inpi_ratios_sectors`, legal +`ca_asc_enforcement`/`ca_bcsc_disciplined`, healthcare
  +`br_cnes_facilities` (the domain's first BR face): the API-expansion batch D same-stack widening —
  no new jurisdictions (31 held), US/FR/CA/BR deepened only; `ca_amf` deferred at the verify gate
  (lautorite.qc.ca CF-403s non-browser clients); the urlencoded channel gains doseq list→repeated-key
  encoding (inert to every existing scalar op); see changelog entry 95)

  → **0.3.59, 216 faces** (company +`eu_eiopa_iorps` (the EIOPA IORP pension register's POST-only
  live query channel — the dual-track twin of the raw eu-eiopa-iorps-pensions harvest), legal
  +`fr_amf_sanction`/`fr_amf_transaction`/`eu_cijeu_search`/`lv_knab_parties`/
  `lv_knab_payments`/`ch_efk_party_financings`/`in_indiacode_search`/`ch_finma_enforcement_news`:
  the API-expansion batch E1 enforcement/party-finance cluster first slice — the legal domain's
  first CH, EU and LV faces (LV new to the whole ledger, 32→33), FR's second legal authority and
  IN's second legal face; see changelog entry 96)

  → **0.3.60, 230 faces** (legal +`au_frl_titles`/`br_cade_pesquisa_avancada`/`ca_cbsa_rulings`/
  `ca_cbsa_ruling`/`de_lobbyregister_entries`/`dk_ft_inspektionsredegoerelser_og_afgoerelser`/
  `it_agcm_ricerca_provvedimenti`/`it_agcm_rating`/`it_agcm_dettaglio`/`pl_uokik_decisions`/
  `pl_uokik_decision`/`us_cbp_ruling`/`us_cbp_stat`, company +`br_bndes_financiamento`: the
  API-expansion batch E2 rulings/registers cluster — **the legal domain's first AU, DE, DK and PL
  faces** (AU and DE pre-exist through healthcare/company; **DK and PL are new to the ledger —
  33→35**; this roll line originally claimed "zero new countries (33 held)" and was corrected by
  the 0.3.62 count audit, which derived 35 jurisdictions from the runtime `COUNTRY` truth); see
  changelog entry 97)

  → **0.3.61, 233 faces** (legal +`fr_court_judgments`/`fr_court_judgment`/`us_occ_ea_search`:
  the API-expansion batch E3 judgment/enforcement pair-of-providers — the FR administrative-courts
  portal's monthly zip archives (/DCE Conseil d'État + /DCA appeal courts; the CAA archives carry
  no Numero_ECLI, ecli=None is the legal shape) and the OCC EASearch structured database under a
  second provider id (`occ` keeps the 0.3.28 news face; the twin rides `us_occ`, wb/wb_proc
  precedent); FR/US deepened only, zero new jurisdictions (35 held); see changelog entry 98)

  → **0.3.62, 237 faces** (legal +`nl_acm_publications`/`nl_acm_publication`/
  `es_cnmv_sanctions`/`kr_fss_sanctions`: the API-expansion batch E4 depth wave — the NL ACM
  sitemap-channel publications pair (13,401 URLs, slug-substring taxonomy), the ES CNMV
  sliding-window sanction register under a second provider id (the 0.3.44 company face keeps
  `es_cnmv`), and the KR FSS xlsx POST×bytes register (letter-keyed cells, 1,245 PDF-carried
  rows answer honest nulls); NL/ES/KR deepened only, zero new jurisdictions (35 held); see
  changelog entry 99) → **0.3.63, 242 faces** (legal +`jp_jftc_decisions`/`jp_jftc_decision`/
  `in_cci_antitrust_orders`/`in_cci_combinations`/`au_accc_actions`: the API-expansion
  batch E5 depth wave — the JFTC decision pair behind the UA gate and the CSRF token/cookie
  pair dance (era tables R/H/S, full-width event numbers — JP's first legal faces), the CCI
  token-misalignment registers pair (DataTables POST channel with the GET-405 twin trap, XYZ
  masking kept verbatim), and the ACCC lazy-views actions feed (/views/ajax two-hop, f[]
  array form, WAF rows-window cooldown self-heals in ~25 min); AU/IN/JP deepened only, zero
  new jurisdictions (35 held); see changelog entry 100) → **0.3.64, 246 faces** (legal
  +`gb_nmw_rounds`/`gb_nmw_round`/`us_cftc_redlist`/`us_cftc_dispositions`: the API-expansion
  batch E6 — the negative-list batch; the UK NMW "named and shamed" pair (the search API
  pinned to the register's own query as the discovery face, the press-release HTML as the
  dossier face because the content API body is empty for these pages — attachments live only
  in the HTML, names carry no year suffix) and the CFTC pair extending us_cftc in place (the
  RED List's 284 unregistered entities alphabetical with items_per_page decorative, the
  reparation decisions anchoring the PDF itself with dockets riding the blurb); GB/US
  deepened only, zero new jurisdictions (35 held); same-day re-probes negative — uk_ico's
  Cloudflare challenge now covers the sitemap, us_fcc still the 387B stub; see changelog
  entry 101) → **0.3.65, 247 faces** (legal
  +`us_cftc_opinions`: batch E7 single-face deepening — the OGC Opinions & Adjudicatory
  Orders register, the appeals layer above the dispositions court; dual-era PDF paths kept
  verbatim (recent /sites/default/files/YYYY/MM/ + the legacy /idc/groups/public/
  %40lropinionsandadjudicaryorders/ — %40 is the encoded @ and "adjudicary" the upstream's
  own misspelling, never normalized), multi-docket rows' "CFTC Docket Nos. …; and …" list
  captured whole as one docket_no, and the legacy docket shapes tolerated (CFTC prefix
  dropped / non-R numbering / NFA space pairs) while dispositions' shared regex stays
  CFTC-anchored; US deepened only, zero new jurisdictions (35 held); survey negatives —
  kr_ftc reorganized off its boards, TED v3 search 429s with key risk, and Climate TRACE
  turned out already shipped since the 0.2.6 era (a stale roadmap row, not a candidate);
  see changelog entry 102) → **0.3.66, 251 faces** (company
  +`us_sec_companyconcept`/`us_sec_companyfacts`/`us_sec_frames`/`us_sec_tickers`: batch E8 — the
  2026-10-19 deferral REOPENED by the 2026-11-17 user ruling (the local XBRL bulk the ruling
  leaned on was lost with the E: drive; the MCP/OmniHub PATH_ALLOWLIST surface carries no
  financial-data paths); one keyless provider `edgar_xbrl` on data.sec.gov with the tickers
  op riding an ABSOLUTE path to www.sec.gov (one provider id, two hosts, each with its own
  polite bucket); three live laws baked in — concept drift (Revenues dead after 2018 →
  RevenueFromContractWithCustomerExcludingAssessedTax, Apple lacks EarningsPerShareDiluted,
  tags verbatim, absence a legal answer), fy/fp stamps the FILING not the fact period, and
  the CY frame closed set; rate 5/5 with edgar_cik 5 = the official 10 req/s (§7 exception
  register's third member); US deepened only, zero new jurisdictions (35 held); see changelog
  entry 103)
→ **0.3.67, 251 faces** (company `us_sec_fulltext_search` --census: batch E9 — the premium
  §9.6 fix ticket; faces/providers/jurisdictions all held (a mode on an existing face); the
  full-window sweep — date bisection until every leaf exact, every page harvested
  (from-offset/100-page; the upstream ignores page/offset/start), _id/adsh dedup, plus
  --census-entity (local whole-word entity post-filter — company:"..." is not a
  server-side field filter) and --census-max-requests (default 400, loud exhaustion);
  reference-date anchors 87/37/54 = strict supersets of the hand 47/33/43 with transparent
  composition; see changelog entry 104)
→ **0.3.68, 256 faces** (company +`ch_six_fqs_search`/`eu_euronext_instrument_search`/
  `it_borsa_quote`/`jp_jpx_stock_detail`/`jp_jpx_stock_list`: batch E10 — the developed-economy
  exchange faces, +4 providers, 35 jurisdictions held, the first Italian company face; SIX FQS
  column oracle (invalid select names 400-rejected — refused locally; price columns opt-in under
  the SIX commercial-use caveat), the Euronext venue resolver (one ISIN many MICs, join on
  ISIN+MIC, zero-hit sentinel row dropped), the Borsa ISIN card (slug decorative, lang pinned
  it, silent generic-page shape → found=false never fabricated, IT number parsing, and the
  breadcrumb-bridge extraction law that falsified the content-negotiation theory), the JPX
  qjsonp pair behind its Referer door (4,490-name universe with board + 33-sector industry,
  57-field issue card with embedded OHLCV/EPS history); two same-day upstream flips deferred
  with probe evidence — Wiener Börse TLS (a *.factsetdigitalsolutions.com cert on both hosts)
  and TMX (tsx.com flipped to an AWS WAF JS challenge after the morning's green probes; urllib
  cannot execute challenge JS); see changelog entry 105)
→ **0.3.69, 257 faces** (company +`us_sec_filing_document`: batch E11 — the SEC Archives
  body fetch, +1 provider `edgar_arch`, 35 jurisdictions held, the body layer under the
  filings line (submissions = index, fts = hit metadata, xbrl = facts — the document
  bytes were only reachable as doc_url links); --url (a doc_url, prefix-walled to
  sec.gov/Archives) XOR --cik + --accession; auto-primary via the submissions
  recent-window primaryDocument (index single-candidate rule / usage_error naming
  candidates beyond); the SGML-envelope two-shape law (older filings wrapped — inner =
  first <TEXT> to LAST </TEXT> greedy — vs modern bare iXBRL passthrough), index.json a
  pure directory listing on every era (the type column is an ICON name, no
  isPrimaryDocument even on 2026 filings), scaffold rows flagged and a scaffold-only dir
  = bogus accession → upstream_not_found (the upstream answers 200 with a ghost
  filename1.htm listing — never laundered as an empty dir); bytes via the latin-1
  round-trip, sha256 over raw, decode chain charset→utf-8→cp1252→replace, --text a
  stdlib HTMLParser; see changelog entry 106)

- openFDA query faces **deferred by user ruling** (2026-10-16: FAERS/MAUDE are already harvested and ingested locally, so queries consume the local corpus first; third-party real-time faces wait until an incremental question touches them) — the deferral covers **only the locally ingested FAERS/MAUDE faces**; the `drug/shortages.json` face opened in Wave 5 is an event-stream face not harvested locally, outside the deferral's scope (opened 2026-10-23 as soon as the incremental need arose, see changelog entry 23). The first hosted case awaits a keyed-tool proposal — keys are never shipped down to the SDK (§9.2).

### 9.7 Capability discovery surface (0.3.52 CLI; server-side = P2 byproduct)

- The CLI renders its own capability table from the command tree (reflection — the §9.6 registry
  and the CLI `--help` catalogs are all views of the same argparse tree, no second source to
  drift). A server-side capability document is a **byproduct of the P2 hosted realtime
  thin-shell**, not a separately designed or separately released API: when the P2 HTTP shell
  wraps the same client.py implementation (§9.5 single authoritative implementation), it renders
  the same reflection with each caller's entitlement depth resolved. Three clauses govern that
  step:
  - **Discovery is never paywalled (the form-B front gate)**: the face / jurisdiction / execution
    listing is open to any caller; only execution depth (rate-limit budget, corpus T-layers) is
    entitled. The compliance trigger (compliance register §1.3) is *re-provisioning*, not
    charging — a free discovery listing keeps that boundary honest, and premium is what the
    listing shows as entitlement depth, never the listing itself.
  - **Anti-skew `min_client_version`**: the server document carries the minimum client version it
    describes; a client older than that refreshes its baked-in table instead of mixing. The
    rendered table is stamped with the release it shipped in (`sdk_version` field), so
    client-table vs server-table skew is detectable, never silent.
  - **Zero extra release cadence**: the reflection ships with every SDK release and the server
    document inherits it by construction — there is no capability-list release apart from the
    SDK release.

→ **0.3.70, 262 faces** (company +the E12 five: `at_wiener_borse_listed` /
  `au_asx_listed` / `hk_hkex_securities` / `hk_hkexnews_search` / `hk_hkexnews_document`
  — the developed-economy exchange universes + the HKEX deep, +3 providers
  `at_wiener`/`au_asx`/`hk_hkex`, 36 jurisdictions (HK new SDK-wide — the user's HKEX-deep ruling), company 80→85, **AU's first
  company face**; live-probed 2026-11-18 tmp/probe-e12/): at_wiener is the E10 TLS
  deferral REVIVED same-day (the morning's *.factsetdigitalsolutions.com mis-chain was
  upstream's own; the afternoon re-probe got the clean DigiCert chain — the
  same-day-reversal law: re-probe before any verdict) — the two Austrian segment
  tables carry the SPAN-STACK law (one td stacks values in nested spans/divs/<br>;
  split on element boundaries span/a/b/small/div/p/br or date+time glue into
  "18.11.202612:03:29"), the ISIN rides the company-page slug with a TRAILING SLASH
  (tail-anchored regex must tolerate /?), and German numbers (comma decimals, dot
  thousands, Mio.×1e6 / Mrd.×1e9) parse into *_num with verbatim strings alongside;
  au_asx is the THREE-PART CSV (line 0 banner as-at anchor / blank / header / data;
  2,060 rows live) where GICS Not Applic (303) and Class Pend (19) are LEGAL values,
  not dirty data; hk_hkex is ONE provider over TWO hosts (www.hkex.com.hk universe
  xlsx + www1.hkexnews.hk announcements, each its own polite bucket — the edgar_xbrl
  precedent): the xlsx parses with stdlib zip+xml alone (values ride per-cell <x:v>
  t="str"; the 18-column header row verified verbatim — column P's header is a
  MULTILINE spread-table legend, the probe's stray-"4" reading was a probe artifact
  the header wall caught on first live call; the DIMENSION LIE — <x:dimension
  ref="A1:R8"> understates reality, rows are the truth; column R carries the paired
  RMB counter code); titleSearchServlet.do answers DOUBLE-ENCODED JSON (two
  json.loads) with three mutually-exclusive modes (stock via prefix.do JSONP →
  stockId / title keyword / one of the six eds codebooks — codebook lengths GROW:
  tierone_e 15 probe → 20 live, never pin them) and TWO ERAS (t1/t2/t2g headline
  categories from 2007-06-25, document_type before that — announcements back to
  1999-04-01); hk_hkexnews_document reuses the E11 body-fetch pattern (sha256 +
  content_latin1 lossless round-trip, 748,377B anchor byte-identical with curl) and
  is where the PATH_SAFE law was born: an op whose {link} substitution carries
  slashes MUST declare path_safe="/" or build_url quotes the path into the HOST
  (www1.hkexnews.hk%2Flistedco…) and the proxy answers 400 Tunnel connection
  failed — a host-shaped URL bug, not a proxy bug; /listedco/ SSRF prefix walls on
  both entry forms; rate-limits v1.57; see changelog entry 107)

→ **0.3.71, 267 faces** (company +the E13 five: `ca_cse_listed` / `ca_cse_company` /
  `hk_hkexdi_corp_list` / `hk_hkexdi_form` / `hk_hkexdi_ir_summaries` — the CSE exchange
  pair + the HKEX Disclosure-of-Interests deep, +2 providers `ca_cse`/`hk_hkexdi`,
  36 jurisdictions (CA/HK held — zero new), company 85→90; live-probed end-to-end
  2026-11-19 tmp/probe-e13/): ca_cse is a NEXT.JS HEAD OVER WORDPRESS whose data rides
  the site's own /api/* JSON (discovered via the build manifest — no screen-scraping);
  /en prefix + trailing slash MANDATORY (the bare path 308s and the slashless target
  404s — pin both, never ride); a bad symbol answers 200 with a ZERO-BYTE body (the
  silent-empty law — found=false, never fabricated); `metatdata` [sic] is the upstream
  dead key (removal_date 2022-07-01 — read `metadata` only); the universe is 739 rows
  one array with every selector client-side (Active 628 / Suspended 85 / Halted Pending
  Fundamental Change 23 / Delisted 3 — the status filter IS the negative list);
  trading_date is PER-ROW last trade, not an as-at anchor; hk_hkexdi carries the
  SESSION QUARTET law ({__VIEWSTATE/__EVENTVALIDATION/__VIEWSTATEGENERATOR/cookie}
  cached TOGETHER 30min — the jp_jftc session-bound law generalized), corpn rides the
  six list links' params (the resolution page echoes only the stock code —
  lblSCCriteria), the per-corp list CAPTION RIDES THE HEADER ROW'S FIRST CELL ("Complete
  list of…" glued ahead of the real columns — anchor the first KNOWN header cell, never
  cells[0]), leading zeros are DIGITS (digits+lstrip("0") both sides — "00700"≠"700"
  plain), the C5 date-banner rides its own row (the serial-shape guard drops it), the
  positions block's header signature "Total number of shares" runs BEFORE the generic
  split (its first DATA row reads Long/Short/Lending — the generic rule refuses), and
  the DION floor 2017-07-03 is refused locally (upstream silently clamps earlier asks);
  the date-axis captcha wall (NSSrchDate — market-level anti-abuse) and SDW/CCASS
  (terms §2.3 forbid programmatic access) stay out on principle; TMX re-probed
  2026-11-19 — still the AWS WAF challenge, stays deferred; rate-limits v1.58; see
  changelog entry 108)

→ **0.3.72, 272 faces** (company +the E14 five: `nz_nzx_listed` / `nz_nzx_company` /
  `nz_nzx_announcements` / `ch_six_official_notices` / `ch_six_notice_detail` — the NZX
  dehydrated-state trio + the SIX official-notices pair, +2 providers
  `nz_nzx`/`ch_six_onot`, 36 jurisdictions (NZ/CH held — zero new), company 90→95;
  live-probed end-to-end 2026-11-19 tmp/probe-e14/): nz_nzx rides the Next.js SSR
  DEHYDRATED STATE (robots disallows /api/ and /search — the SDK touches SSR pages
  only, the compliant surface IS the whole surface); the whole-exchange master q0
  ["activeInstruments"] is IDENTICAL on the NZSX/NZDX pages (427 rows ×16 keys; the
  board picks only the quote panel — 178 equities / 135 bonds), lastListedDate
  3000-01-01 is the CURRENT sentinel (the master is the ACTIVE set — delisted
  instruments vanish, snapshot-diffing is harvest-side), the four company panels are
  labelled by their queryKey tails ("instruments" for the instruments panel — the
  label-collision fix), a bad code is an HONEST 404 with EMPTY queries (found=false —
  the meta is the observation, never a body), and ?page=2 on announcements is IGNORED
  upstream so NEWEST-200 is the whole SSR surface (the boundary is documented, not
  worked around); the SIX pair rides sheldon v2: the show* switches are DEAD
  (noticeType filters the fetched page locally, show* never sent), issuerWords is a
  PAGE-1 SNAPSHOT (a partial page 43/143 + deeper issuer pages garble persistently),
  pageSize pinned 100 (200 breaks paging; 1000 answers an empty itemList while
  totalCount still echoes — the silent-over-cap shape; reachable ceiling ~5
  pages/window), transient failures BOTH ways (garbled 200s retried after 4s and 502s
  after 8s — one patient no-cache retry each, a garbled body never cached as good),
  and DD-MM-YYYY dates are REFUSED (dash-stripping would swap day/year into a
  legal-looking 8-digit string — found by the module's own test); FL titles are bare
  date strings, the semantics live in the detail text; rate-limits v1.59; see changelog
  entry 109)

→ **0.3.73, 277 faces** (company +the E15 five: `de_xetra_instruments` /
  `de_xetra_newsboard` / `de_xetra_newsboard_search` / `kr_krx_listed` / `kr_krx_indices`
  — the Deutsche Börse T7 universe trio + the KRX Global pair, +2 providers
  `de_xetra`/`kr_krx`, 36 jurisdictions (DE/KR held — zero new), company 95→100, and the
  G7 exchange-universe axis reaches five of seven with Germany (US/JP/FR/IT/DE — GB has
  no exchange feed, CA is CSE-only with TMX WAF-gated; "CLOSES" was an overclaim,
  corrected in 0.3.74); live-probed end-to-end 2026-11-20
  tmp/probe-e15/): de_xetra rides cashmarket.deutsche-boerse.com (the site
  self-describes "formerly xetra.com"; robots zero Disallow) — the T7
  allTradableInstruments CSV lives at a BLOB-HASH path that VERSIONS on every upload, so
  the link is re-parsed from its landing page on EVERY fetch (the Frankfurt variant hangs
  UNDER the Xetra section while /Tradable-Instruments-Frankfurt/Downloads is a 404 decoy);
  rows 1-2 carry Market + Date Last Update (the snapshot anchor), 153 columns verbatim,
  counts drift DAILY (never pinned); api.live.deutsche-boerse.com is a catch-all {}
  shell — negative, never touched; the Newsboard is a 100-item RSS ROLLING window (~15h —
  hourly polling is the no-loss cadence) with venue-prefixed titles, and the search face
  is FULL HISTORY with pageNum riding statelessly (each hit an anchor-wrapped
  href/date/tagline/text quad); kr_krx rides global.krx.co.kr — the OPEN portal of the
  three-sister gate family (data.krx member wall + Akamai, kind.krx WAF, global robots
  `Allow: /` verbatim) — the listed universe runs the OTP DOUBLE-STEP (a one-shot base64
  code, posted back 2s later with market_gubun 0/1/2/6) to fetch the whole universe
  ONE-SHOT (~2,769 rows; All reconciles with the kospi/kosdaq/konex splits); the bld is
  the FULL path form GLB/03/0308/0308010000/glb0308010000 (the endpoint name is the form
  action — a wrong pair answers 200 with ZERO bytes, the silent-empty law); the one-shot
  code NEVER enters the cache key (hand-rolled code-less key — repeat calls are cache
  hits with zero OTP mints); indices is the free-OTP family with cmpr_rt kept as
  upstream's raw scientific-notation string verbatim; rate-limits v1.60; see changelog
  entry 110)

→ **0.3.74, 283 faces** (company +the E16 six: `eu_esef_facts` / `eu_esef_filings` /
  `gb_fca_firds_search` / `gb_fca_nsm_search` / `gb_fca_official_list` /
  `gb_fca_official_list_activity` — the UK FCA data-API family + the EU ESEF register,
  +2 providers `gb_fca`/`eu_esef`, 36 jurisdictions (GB/EU held — zero new), company
  100→106, and the G7 exchange-universe axis stands at six of seven (GB rides the FCA
  regulator's Official List/NSM/FIRDS — not an LSE exchange feed; CA is CSE-only, TMX
  WAF-gated); live-probed end-to-end 2026-11-23 tmp/probe-e16/): gb_fca rides
  api.data.fca.org.uk — POST /search?index=<idx> over four indexes (nsm-search
  5,570,535 regulatory notices / official-list-main 15,160 /
  official-list-daily-activity 119,810 / firds-view 169.6M reference-data records)
  behind a shared ERROR-SHAPE law (a malformed body = 404 "Unable to search the data"
  re-raised upstream_unavailable; a wrong facet value = silent 200 total 0 — filters
  validated locally against the measured vocabularies); per-index date laws (NSM and
  activity take full ISO `YYYY-MM-DDTHH:mm:ssZ` while OL/FIRDS take dd/MM/yyyy, and
  FIRDS REQUIRES a to-bound — the SDK fills 31/12/2099 FAR_FUTURE); the 10,000 window
  law (from+size ≤ 10,000 checked locally; SDK page cap 5,000); rows carry populated
  fields only (nulls omitted per row); NSM is TWO-PATH (text needs latestFlag:"Y" +
  primarySearch document_content×headline while criteriaObj members are LIST-typed);
  activity takes its date criteria as the OBJECT securityActivityDateCriteria;
  FIRDS is keyword XOR criteria, always carries techattrbts_nvrpblshd=false
  (never-published records stay unexposed) and active_flag=Y by default; MIC/LEI/ISIN/
  CFI uppercased with shape validation; artefact links absolutized under
  data.fca.org.uk/artefacts/; the SPA's collectAnalytics endpoint and its honeypot
  URL are NEVER called, and a Range header is NEVER sent to data.fca.org.uk (10054
  connection reset — measured); eu_esef rides filings.xbrl.org (27,817 filings /
  7,505 issuers / 28 countries; GB 2,982/806, DE/IE absent) as a JSON:API with
  filter=[{name,op,val}] + a mandatory sort, page[size] ≤ 1000, beyond-last-page =
  200 with an empty data[] (honest empty); fxo_id shape
  {LEI}-{YYYY-MM-DD}-ESEF-{CC}-{seq} (-0 original, -1+ amended); the facts face rides
  the filing's ABSOLUTE json_url (host-guarded) with the XBRL-JSON period law
  (durations end-exclusive; a midnight instant = the day after → inclusive end =
  raw −1 day) and a wildcard concept filter matching the taxonomy-agnostic local
  name (Revenue* catches ifrs-full:Revenue); `published` is null on every GB row
  (not exposed); rate-limits v1.61; see changelog entry 111)

→ **0.3.75, 286 faces** (company +the E17 three: `us_sec_13dg_stakes` /
  `us_sec_13f_holdings` / `us_sec_form4_transactions` — the EDGAR holdings-disclosure
  family (13F institutional holdings / Form 4 insider transactions / Schedule 13D·G
  large-stake cards), +0 providers (the family REUSES `edgar_cik` submissions +
  `edgar_arch` Archives index/doc — zero new buckets; `edgar_ownership` is the
  module id, not a quota), 36 jurisdictions (US held — zero new), company 106→109;
  live-probed end-to-end 2026-11-23 tmp/probe-e17/): the enumeration filters the
  submissions recent window by exact form strings (13F-HR(/A); 4/4-A/5/5-A; the 13DG
  EIGHT-STRING UNION — submissions carries both families, structured
  "SCHEDULE 13D/G(/A)" AND legacy "SC 13D/G(/A)"); the XSL-SHELL LAW (submissions
  primaryDocument for 13F-HR AND Schedule 13D/G points at the HUMAN-RENDERED cover
  "xslForm13F_X02/primary_doc.xml" — a rendering shell ElementTree dies on; the raw
  XMLs sit at the accession ROOT, resolved via the edgar_arch index op, never via
  primaryDocument; Form 4's primaryDocument IS root-level); the ROOT-XML PICK LAW
  (13F table = root-level *.xml minus primary_doc.xml — 'info'-named preferred,
  ambiguous → usage_error naming candidates); the NAMESPACE LAW (three schemas,
  three regimes — 13F informationTable default-ns thirteenf/informationtable, 13D/G
  default-ns schedule13d OR schedule13g — TWIN namespaces and TWIN filer layouts:
  13D reportingPersons blocks carry a filer CIK, 13G coverPageHeaderReportingPerson
  Details blocks don't, and the issuer element spells issuerCik vs issuerCIK → card
  lookups case-insensitive — Form 4 ownershipDocument namespace-free; localname
  matching throughout); the VALUE-UNITS LAW (13F value switched thousands→whole USD
  at 2023-Q1, judged on reportDate, value_units rides every card); the
  GRANDCHILD-VALUE LAW (Form 4 wraps transaction fields <X><value>…</value></X> and
  postTransactionAmounts TWICE — sharesOwnedFollowingTransaction → <value> — a
  middle-element probe answers its empty text and the field silently vanishes;
  natureOfOwnership likewise value-wrapped, never direct text); STOCK Act PTR
  resolved NOT in EDGAR (forms PD/PTXA/PTR answer zero — the House/Senate disclosure
  systems, out of this batch); two fix-forwards rode the batch: the shared
  edgar_arch.index_rows is_document regex widened to count .xml (13F accessions are
  XML-ONLY directories — the htm/txt-only regex had misclassified a REAL filing as
  the bogus-accession scaffold shape; the scaffold gate is unaffected, ghost rows
  are .htm/.txt), and the Form 4 parser's post_shares read one level short of the
  grandchild value (the live smoke row0 had silently carried neither post_shares
  nor nature_of_ownership — caught by the test_flat_0375 fixture run, re-verified
  live post-fix: post_shares 38,963 on the Upstart row); volume pins 2026-10-01..11-23: 13F-HR 9,606 / SCHEDULE 13D 496 +
  13D/A 366 + 13G 2,545 + 13G/A 1,826 / Form 4 ~270 per trading day; rate-limits
  v1.62 (no new bucket — the edition bump carries the face counts only); offline nails
  `tests/test_flat_0375.py`; see changelog entry 112)

→ **0.3.76, 296 faces** (company +the E18 ten: `gb_lse_universe` /
  `gb_lse_security_master` / `gb_lse_ric_lookup` / `gb_lse_index_membership` /
  `gb_lse_fundamentals` / `gb_lse_issuer_address` / `gb_lse_bond_details` /
  `gb_lse_rns_archive` / `gb_lse_rns_article` / `gb_lse_issuer_profile` — the LSE
  exchange-universe family, +1 provider `gb_lse` (ONE id over THREE hosts —
  apidata.londonstockexchange.com REST baseUrl + www.londonstockexchange.com
  absolute-path ops + cache-api.lsegissuerservices.com absolute-path op, the
  ext-10 multi-host precedent; all keyless), 36 jurisdictions (GB held — zero new),
  company 109→119, and the G7 exchange-universe axis COMPLETES SEVEN OF SEVEN (LSE
  was the last holdout — the 0.3.74 "GB rides the regulator's Official List, not an
  LSE exchange feed" wording is superseded; the quote surfaces — instrument-summaries,
  trade-summaries, rdp/v1/pricing, cmdf/v1/tmv, tradingstatus, validate, AIM
  advisers, the fdc→saml→tns tick chain, OHLCV bars — are MARKET-DATA, licensed
  goods, deliberately OUT, the red line); live-probed end-to-end 2026-11-24
  tmp/probe-e18/): the ENVELOPE LAW (every apidata answer is
  {"statusCode":200,"message":…,"data":…} — the SDK unwraps data, non-200 surfaced
  honest), the 200-EMPTY TRANSIENT law (an empty apidata payload re-asks once
  no-cache before an honest upstream_unavailable — never read as a coverage
  boundary) and the WWW DEGRADE-TRANSIENT law (www pages occasionally answer a
  degraded 200 with articleBody absent — the same URL answered the full 165KB page
  minutes later under EVERY header combo incl. the SDK's own UA, so the www faces
  re-ask once no-cache and the fresh answer overwrites a poisoned cache entry; a
  page that stays body-less is a genuinely removed article); the header-fingerprint
  gate is INTERMITTENT (bare UA answered 200 where the 2026-11-23 probe demanded
  Accept+Referer — headers ride anyway, zero downside); TWO LIVE REVERSALS:
  securitybonddetails is the GENERIC security card (BARC answers a full card with
  maturityDate null — the research doc's "equities answer 404" was wrong; unknown
  tidm = honest 404 → found=false), and the issuer-profile code is the nrdp
  displayissuercode NOT the ticker (VOVOD = Vodafone — 33 instruments,
  admissiondate 1988-10-26; VOD/BASDE honest misses, never fabricated); universe =
  five sitemap books ~62,713 quote pages (probe-day split: equity 5,761 / bonds
  45,455 / etps 5,471 / others 2,032 / turquoise 3,993) — the quote-page URL IS the
  tidm enumeration (UK ticker BARC + international SEDOL 0A00 forms); index
  membership = indexCode/Name/Weight parallel comma lists strict-zipped (BARC 9/11
  slots, UKX 2.23% — weights drift daily); RNS archive floor 2024-11 (older months
  = S3 AccessDenied 403, refused LOCALLY, never sent; form-8-3 ≈5,077/month live
  2026-10); the article slug is the category-company melt (rpartition) behind the
  PATH_SAFE law (the {url} template carries category/hash slashes — default quoting
  mangles the path into %2F → a 200 shell without articleBody; op-level
  path_safe:"/", the TNA document_uri law) with articleBody as a JS-string regex
  (\x22/\uXXXX/\/ decode) and RichTextGrid metadata (Company information / RNS
  Number / Released On / Source); META-THREADING law (every face return carries a
  truthy `_meta` — _flat_env filters None but an EMPTY metas list crashes
  enrich_source, so honest-404 returns carry _observed_meta, the nz_nzx law); a
  docs fix-forward rode the batch: the 0.3.75 §9.6 roll had shipped as a DUPLICATE
  (a compressed draft between 0.3.73 and 0.3.74 + the full block — the draft
  removed here); rate-limits v1.63; see changelog entry 113)

## 10. The ask verb (P2 design boundary, not implemented)

- Input `{question, domain, scope_filters?}`; output `{answer, evidence_rows:[row cursor anchors], coverage_assertion, refused?}`.
- **Hard constraints**: the answer must be supported by this domain's search/read results, with every sentence anchored to a row `cursor`; no evidence in the store → `refused:"not_in_coverage"`, and **negative conclusions of the form "no X" must never be generated** (same root as "not covered ≠ no risk"); no cross-domain, no external calls, nothing enters fields outside the evidence chain.
- Implementation layers: P2a templated Q&A (facets + fixed question patterns, zero LLM); P2b LLM restricted to the **rewriting layer** (one_liner summaries, sentence-by-sentence anchoring + `_enrich` annotation) — the LLM never produces fact rows.

## 11. Subscription delivery (P2 design)

- Subscription = `{domain, filters, last_cursor, deliver_to(webhook|poll)}`; change granularity = staging batch landing / db promote completion events.
- The pull form `POST /v1/{domain}/search {filters, cursor, observed_since}` is the subscription's degenerate polling form — **no new query verb** (establishment ruling).
- webhook delivery carries a signature header + at-least-once semantics; consumers reconcile and dedupe by cursor.

## 12. Versioning and compatibility policy

- Paths carry `/v1`; **specs only grow, never shrink**: deprecating a filters field = `deprecated:true`, retained ≥6 months (still filterable); the 400 code closed set may grow but codes never change meaning.
- `domain-spec.json` carries `version`; CLI `--help` and HTTP `GET /v1/{domain}` expose the spec version; breaking changes bump to `/v2`, running in parallel ≥3 months.
- Freshness transparency: row-level `source.observed_at` + response-level `coverage_assertion.observed_at` (per source) — freshness judgment is the consumer's responsibility, but the data must be sufficient.

## 13. API documentation publishing (docs site design)

- **docs-as-code, no second source of truth**: the source of truth = domain master documents (filters/use cases/T layers) + this document + `domain-spec.json`; the site is a pure rendering artifact, generated from spec at build time, never hand-copied.
- Two content layers: ① tutorial/use-case layer (domain master document §use cases → scenario pages); ② API reference layer (domain-spec.json → endpoint/field/facets tables).
- Open-source tool selection (2026-10 ruling lean, not yet implemented):

| Purpose | Candidates (all open source) | Trade-offs |
|---|---|---|
| Docs site framework | VitePress (Vue family) / Docusaurus (Meta) / Starlight (Astro) / Nextra (Next.js) | This repo carries no React/Vue dependency burden and `site/` is already zero-framework static output → **start with VitePress or Starlight**; move to Docusaurus if heavy versioning/multilingual needs emerge |
| API reference | Redoc / Swagger UI (rendered from OpenAPI) | When P2 HTTP lands, aggregate `openapi.yaml` from each domain's spec → embed as a single Redoc page; in the CLI era, Markdown tables (rendered straight from spec) |
| Hosting | Any static host + CI push builds | The docs directory lives in the repo; build artifacts stay out of it |

- No closed-source SaaS (Mintlify/GitBook/ReadMe) — the same root constraint as "credentials never sent out, data never to third parties".
- Landing order (from P2): first ② (API reference, single-page Redoc/static tables, together with P2 HTTP) → then ① (tutorial layer, exported from domain master documents). In P1 the docs stay in-repo (this document + each domain's §12); no site built prematurely.