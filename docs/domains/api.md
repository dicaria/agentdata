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
| `read` | `POST /{domain}/read` | `target:{type:"company"|"facility", id}` + `level=tier1\|tier2\|tier3` |
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
| `cn` | NMPA / CDE / SMPAA / 卫健委 (National Health Commission) / 药监 (drug regulator) | uscc (Chinese hospitals **truthfully marked as having no USCC**; L3 candidates not auto-merged)| PIPL + Data Export Security Assessment Measures + labeling filing obligations (not ingested)|
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
| `/v1/{domain}/read` | POST | body = `{target:{type:"company"|"facility", id}, level}` |
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
| company | `sec_submissions` | US | `resolve kind=cik` | `edgar-cik` | local | 7 days (identity current values/filing counts can change) | Wave 2 ✅ |
| company | `ror_organizations` | GLOBAL | `resolve kind=ror` | `ror` | local | search 7 days / single record 30 days (quarterly releases) | Wave 3 ✅ |
| company | `vies_vat` | EU | `resolve kind=vat` | `vies` | local | 7 days (validation verdict; masked name/address recorded as null) | Wave 4 ✅ |
| company | `usaspending_spending_by_award` | US | `related kind=fed_awards` | `usaspending` | local | 24 hours | Wave 1 ✅ |
| company | `ted_notices_search` | EU | `related kind=eu_tenders` | `ted` | local | 24 hours (notice stream updates daily) | Wave 4 ✅ |
| company | `gb_fts_release_packages` | GB | `related kind=uk_tenders` | `fts` | local | 24 hours (releases roll continuously) | Wave 4 ✅ |
| company | `gb_contracts_finder_published_notices` | GB | `related kind=uk_cf_tenders` | `cf` | local | 24 hours (releases roll continuously) | Wave 4 ✅ |
| company | `sec_fulltext_search` | US | `fulltext` | `edgar-fts` | local | 24 hours | Wave 1 ✅ |
| company | `ch_zefix_firm_search` | CH | —— (born flat) | `ch_zefix` | local | 7 days (current-value query) | 0.3.3 ✅ |
| company | `ch_zefix_firm` | CH | —— (born flat) | `ch_zefix` | local | 30 days (profiles/M&A edges change slowly) | 0.3.3 ✅ |
| company | `no_brreg_enheter` | NO | —— (born flat) | `no_brreg` | local | 7 days (current-value query) | 0.3.3 ✅ |
| company | `no_brreg_roller` | NO | —— (born flat) | `no_brreg` | local | 30 days (role sequences change slowly) | 0.3.3 ✅ |
| company | `fi_ytj_companies` | FI | —— (born flat) | `fi_ytj` | local | 7 days (registration current values) | 0.3.3 ✅ |
| company | `fr_recherche_search` | FR | —— (born flat) | `fr_recherche` | local | 7 days (registration current values) | 0.3.4 ✅ |
| company | `co_rues_companies` | CO | —— (born flat) | `co_rues` | local | 7 days (registry changes slowly) | 0.3.14 ✅ |
| company | `kr_hometax_biz_status` | KR | —— (born flat) | `kr_hometax` | local | 7 days (휴폐업 current values) | 0.3.14 ✅ |
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
| procurement | `ny_abo_contracts` | US | —— (born flat) | `ny_open_data` | local | 24 hours (contract rows change slowly) | 0.3.6 ✅ |
| procurement | `ny_mta_procurements` | US | —— (born flat) | `ny_open_data` | local | 24 hours (contract rows change slowly) | 0.3.6 ✅ |
| procurement | `ny_ogs_payments` | US | —— (born flat) | `ny_open_data` | local | 7 days (payment rows are historical fact; ABO/MTA rows stay 24h) | 0.3.12 ✅ |
| procurement | `br_pncp_contracts` | BR | —— (born flat) | `br_pncp` | local | 7 days (historical contract windows stable monthly; recent windows change slowly) | 0.3.0 ✅ |
| procurement | `co_secop_contracts` | CO | —— (born flat) | `co_secop` | local | 24 hours (contract rows change slowly with ultima_actualizacion) | 0.3.0 ✅ |
| procurement | `ungm_contract_awards` | GLOBAL | —— (born flat) | `ungm` | local | 7 days (awards are settled facts; the anti-forgery pairing caches 15 minutes independently) | 0.3.12 ✅ |
| procurement | `wb_procnotices` | GLOBAL | —— (born flat) | `wb_proc` | local | 7 days (immutable after Published) | 0.3.6 ✅ |

- On-trigger (opened only when a question touches them, no pre-provisioning): WHO GHO / Canada DPD / Japan e-Stat (healthcare); other domains register in this table as they open.
- **Flat main-face lineage** (2026-10-23 ruling: main face = `<domain> <source>_<dataset>` + upstream parameter names verbatim; **Python single stack as the sole implementation**; since the 2026-10-27 registration-convention flip, **the table above is the complete roster of flat faces — 97 faces** — with the `service/shared/gateway/capabilities.mjs` snapshot flipped in sync): 0.2.0, 35 faces → 0.2.1 naming convention v1.0 finalized, 37 faces (26 renamed / 9 kept + two splits; the Node twin was withdrawn 2026-10-26) → 0.2.2 domain expansion, 41 faces (grants domain established, security domain established) → 0.2.3, 42 faces (legal +case-law face) → 0.2.4, 50 faces (**grants→research domain rename** + 8 new faces) → 0.2.10, 54 faces (healthcare +openFDA four faces, Wave 10) → 0.2.11, 56 faces (legal +UK CMA two faces) → **0.3.0, 58 faces / seven domains** (procurement domain established +2 faces; **the verb layer (resolve/related/fulltext/trials/label/evidence), frozen aliases (`csl_screening`/`grants`), and 18 sugar/legacy-alias parameters all removed** — the "removed in 0.3.0" contract honored; from this point on the "old verb face" column is pure historical reference, and client/CLI no longer carries that dispatch) → 0.3.1, 65 faces (healthcare openFDA Wave 10b seven query faces: approvals/catalog/orangebook/510k/pma/registrations/classification) → 0.3.2, 67 faces (esg +EUTL catalog face +EPA FRS facilities face) → 0.3.3, 72 faces (company European registries five faces) → 0.3.4, 73 faces (FR recherche real-time search) → 0.3.5, 78 faces (esg +THETIS-MRV version-ledger catalog +Paris MoU port-state-control four faces — first use of the transport extension ⑦ form-urlencoded channel) → 0.3.6, 81 faces (procurement +World Bank notice stream + NY Socrata two faces: wb_procnotices/ny_abo_contracts/ny_mta_procurements) → **0.3.10 face-order dictionary sort + jurisdiction chapter** (no new faces; the three World Bank/NY procurement faces are absorbed into the order and stamped 78→81: within-domain face-name dictionary sort + the success envelope's jurisdiction chapter visible on four channels) → **0.3.12, 83 faces** (procurement +UNGM award search/NY OGS third face: ungm_contract_awards/ny_ogs_payments — the batch originally numbered 0.3.9 landing via the collection round, having yielded twice to 0.3.12: the two faces enter their dictionary-order slots + jurisdiction stamps GLOBAL/US; first use of the transport extension ⑧ extra_headers+set_cookie channel) → **0.3.13, 85 faces** (0 new faces — nine-face ISO 3166-1 alpha-2 country-prefix unification: uk_cma_*→gb_cma_*, tna_caselaw_*→gb_tna_caselaw_*, gtr→gb_gtr, tga_*→au_tga_*, pncp→br_pncp, secop→co_secop; provider ids/module names/envelope source.provider in sync, no alias transition; jurisdiction chapter unchanged, already ISO) plus the stacked 0.3.8 legal TNA caselaw two faces (gb_tna_caselaw_search/judgment — the first keyless-but-licence gate: Open Justice Licence, targeted retrieval only, no bulk computational analysis) → **0.3.14, 87 faces** (company +CO RUES master/KR hometax status: co_rues_companies/kr_hometax_biz_status — the batch originally claimed 0.3.11 (the UNGM/OGS batch yielded to it and renumbered 0.3.12) and lands as 0.3.14 after 0.3.12/0.3.13 merged first, renumbered to keep the release version monotonic; PII double gate on the CO face, anonymous four-state single-shot on the KR face; jurisdiction stamps CO/KR). → **0.3.15, 87 faces** (0 new — the TNA English-truth collection round landing after the seventh and eighth collisions: the 0.3.13 ISO batch stacked directly on the 0.3.8 tip and merged first, so the TNA faces reached main with the gb_ prefix and their original Chinese public strings; the 0.3.14 renumber was then overtaken by this CO/KR batch; the round re-bases those strings onto the English truth and fixes !154's ungm/ny_ogs docstring leak — the gb_tna_caselaw rate-limits row itself landed via the CO/KR batch's ledger catch-up). → **0.3.16, 90 faces** (legal +`co_sic_sanctions` — the Colombia SIC firm-sanctions register, Socrata $-channel same contract as co_secop; healthcare +`gb_mhra_alerts`/`gb_mhra_alert` — the UK MHRA medicines & device safety-alert twin, the same gov.uk search/content contract family as gb_cma with two pits nailed: q-mode rows drop link (base_path then lives in _id) and the content API has no .json variant; originally claimed 0.3.14, then 0.3.15 — both landed on main first (the CO/KR company round and this TNA English-truth collection round), so the landing number moves to 0.3.16; the TNA-anglicization rider originally attached was dropped as redundant — main's 0.3.15 landed the same content) → **0.3.19, 97 faces** (healthcare +CA DPD/MDALL four faces +EU RASFF/Safety Gate three faces — the CA+EU product-safety cluster from the researched inventory, implemented per the user's split-of-duties ruling (research in a dedicated session, implementation here); four keyless providers ca_dpd/ca_mdall/rasff/safety_gate, probe corpus tmp/probe-ca-eu-faces/; the number follows main's merged 0.3.18 GLEIF round as the sequential next, R6 still owing 0.3.17 (skipped numbers harmless per the 0.3.12 precedent); pits nailed: DPD status closed set 1|2|3|4|6 with unknown values silently ignored upstream = full 15MB dump, walled SDK-side; MDALL device endpoint has no working server-side filter so the licence face is the LIMH stateless point lookup; RASFF path needs language segment + trailing slash, dates in the SPA's own dd-MM-yyyy 00:00:00 shape, the enum-shaped filters stay unexposed (every probed object shape → the same generic [ERR-1003]); Safety Gate report_id hides in the index URLs while detail rows carry the alertDetail path shape — two different regexes — and the detail query string is byte-baked into the path per the ukec precedent) Envelope quartet `query={source: raw|assembled, upstream, assembled_from?}` (upstream = the echoed source of truth of the parameters actually sent, replayable).
- openFDA query faces **deferred by user ruling** (2026-10-16: FAERS/MAUDE are already harvested and ingested locally, so queries consume the local corpus first; third-party real-time faces wait until an incremental question touches them) — the deferral covers **only the locally ingested FAERS/MAUDE faces**; the `drug/shortages.json` face opened in Wave 5 is an event-stream face not harvested locally, outside the deferral's scope (opened 2026-10-23 as soon as the incremental need arose, see changelog entry 23). The first hosted case awaits a keyed-tool proposal — keys are never shipped down to the SDK (§9.2).

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