# Third-Party Source Rate-Limit Research Ledger v1.6 (66 providers / 97 faces)

> **Edition**: this copy is versioned with the SDK release that carries it — it
> records the upstream rate-limit facts and the polite settings that release
> enforces.

> v1.5→v1.6 (2026-11-02): 0.3.19 healthcare CA+EU product-safety round — +4 providers (ca_dpd, ca_mdall, rasff, safety_gate) +7 faces (ca_dpd_companies, ca_dpd_drug_products, ca_mdall_companies, ca_mdall_licence, rasff_notifications, safety_gate_alerts, safety_gate_report); built on main's v1.5 (the naming-alignment sweep landed first while this batch was in flight — same yield-and-follow sequence as v1.4→v1.5).
> v1.4→v1.5 (2026-10-30): naming-alignment sweep, no number changes — v1.4 (the 0.3.16 SIC/MHRA round) landed first, so this sweep follows it as v1.5 per the in-review-face-batch-keeps-its-number rule. Five provider labels re-keyed to the code provider ids the 0.3.13 ISO renames left behind (tga→au_tga, gtr→gb_gtr, pncp→br_pncp, secop→co_secop, kev→cisa-kev; the v1.3 catch-up fixed uk_cma→gb_cma and missed these); the §3 heading count caught up to the actual row count (56→60 at the pre-merge base, 62 after the v1.4 round); the procurement section count 4→5; the datos.gov.co Socrata family (co_rues, co_sic, co_secop) recorded as one shared origin — per-IP anonymous-tier note on all three rows; §5-6 gains a host-bucket precision clause (the default host bucket at 5rps = 300/min also sits above the openFDA keyless 240/min line, so the group entry is the correct fix).
> v1.3→v1.4 (2026-10-30): 0.3.16 legal/healthcare round — +2 providers (co_sic, gb_mhra) +3 faces (co_sic_sanctions, gb_mhra_alerts, gb_mhra_alert); the §3 header count also caught up (56→62 — missed by the v1.2/v1.3 rounds).
> v1.2→v1.3 (2026-10-30): 0.3.14 company CO/KR round — +2 providers (co_rues, kr_hometax) +2 faces; plus two catch-ups from earlier waves: the 0.3.13 rename missed here (uk_cma→gb_cma) and the 0.3.8 TNA provider row (gb_tna_caselaw; official 1000 req / rolling 5 min) — the ledger is now flush with the 87-face roster.
> v1.1→v1.2 (2026-10-30): 0.3.12 collection round — +1 provider (ungm) +2 faces (ungm_contract_awards, ny_ogs_payments); the ny_open_data row extends to the OGS third face (same Socrata anonymous tier).
> v1.0→v1.1 (2026-10-30): aligned to the 0.3.10 81-face roster — +17 providers/+31 faces (openFDA family, EU registries, esg four, uk_cma, the procurement domain); openFDA family A-tier verified on the primary page.

> Position: **the source of truth for upstream rate-limit facts** — each source's official limits, window types, evidence and verification dates, plus the ledger of deviations from our own declared settings.
> The source of truth for our own declared settings = `sdk/python/agentdata/<domain>/<provider>.py` (`rate`/`ttl` fields; per-domain packages since 0.2.6); the source of truth for the execution mechanism = `transport.py` (the 0.2.0 six-piece rate-limit/anti-block set). Where this ledger and the code disagree: **upstream facts defer to this ledger, our own values defer to the code, and deviations go to the §5 todo list**.
> Ledger established 2026-10-26 (user ruling: "get every source's rate limits researched clearly, then design the rate limiting"). Maintenance rules in §6.

## 1. Execution-Side Status Quo (the factual baseline for the design debate)

| Mechanism | Form | Boundary |
|---|---|---|
| provider token bucket | per-source self-set rps/burst; empty-bucket wait capped at 30s → `rate_limited` | **seconds-tier only**; state is in-process (a one-shot CLI starts with a full bucket; it only matters for library use/pagination) |
| host token bucket | shared per host, default 5rps/burst10 (`hostRate` override) | same as above |
| host concurrency gate | semaphore default 2 (`concurrency` override; eudamed pinned to 1) | concurrency ≠ rate |
| backoff | 429/503 → Retry-After first + exponential + jitter, capped at 30s | 401/403 not retried (retrying into a WAF/permission gate harms yourself) |
| circuit breaker | 3 consecutive failures or 5 failures in a 60s window → 60s cooldown → half-open 1 probe → repeated failure 5min | in-process; open = local rejection, no request sent |
| cache | TTL hit means zero network, **before token deduction** (a hit consumes no rate) | persisted, shared across processes |

**Gap**: zero accounting for minute/hour/day window quotas (the token bucket is completely blind to windows like 15/min, 1000/hr, 125/day).

## 2. Evidence Tiers

- **A** = official primary page/ToS/API documentation verified, numbers + links in hand (verification date noted)
- **B** = official documentation read, states a soft policy / no numbers (a throttling mechanism exists but no figures)
- **C** = primary page not verified; presumed unpublished based on the nature of the service (upgraded when the six-step audit passes)

## 3. Master Table of 66 Sources (by domain)

### healthcare (18)

| provider (face) | Self-set rps/burst | Upstream official limit | Evidence | Verdict |
|---|---|---|---|---|
| rxnav (rxcui_by_name/rxcui_atc) | 10/4 + nlm group bucket | **20/s per IP** (NLM family policy; UTS key→100/s) | A [RxNav ToS](https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html) 2026-10-26 | ✅0.2.8 speed-up flush to the group (single-source window 14≤20; intra-family stacking backstopped by the group bucket 10+10=20) |
| dailymed (spls) | 10/4 + nlm group bucket | NLM family 20/s (DailyMed page does not list separately; per NLM policy) | B [DailyMed WS](https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm) | ✅0.2.8 speed-up flush to the group (same as above) |
| mesh (descriptor) | 10/4 + nlm group bucket | NLM/UMLS family 20/s (MeSH lookup not listed separately) | B [UMLS ToS](https://documentation.uts.nlm.nih.gov/terms-of-service.html) | ✅0.2.8 speed-up flush to the group (same as above) |
| epmc (search) | 2/4 | no published figure | B [EPMC REST](https://europepmc.org/RestfulWebService) (pageSize 1000 = pagination, not a rate cap) | polite tier |
| ctgov (studies) | 2/4 | no hard number (soft policy; a 429+Retry-After mechanism exists) | B [CT.gov v2](https://clinicaltrials.gov/data-api/api) | polite tier |
| gudid (devices) | 2/4 | **no official figure** (the rumored 20/s is a misattribution from UMLS) | B [accessgudid v3](https://accessgudid.nlm.nih.gov/api/v3/); gating verified live = TLS-fingerprint WAF keyed on the client stack | polite tier |
| eudamed (devices_udi_di_data) | 1/2 + concurrency pinned to 1 | none published (cold-query ~50s is performance, not throttling) | B [EUDAMED public REST](https://ec.europa.eu/eudamed/) | aligned (the concurrency gate is the real constraint) |
| shortages (fda_drug_shortages) | 2/5 | static JSON fetched in one shot; no rate-limit surface | B | n/a (TTL 1d backstop) |
| au_tga (artg/manufacturers) | 1/2 | none published | C (government portal, no figures on record) | polite tier |
| gb_mhra (alerts/alert) | 1/2 | none published (gov.uk search/content API — no quota figure for the search endpoint; same host as gb_cma, same politeness tier) | B (live probe 2026-10-30, tmp/probe-uk-mhra/; 1,462-alert register measured) | polite tier |
| ca_dpd (companies/drug_products) | 1/2 | none published (the Read Me page documents the data model, not a quota; one-shot registers — the full-shot faces amortize to one request per TTL window) | B (live probe 2026-11-02, tmp/probe-ca-eu-faces/; 5,253-row company register + status=3 → 4,116 measured) | polite tier |
| ca_mdall (companies/licence) | 1/2 | none published; **same host as ca_dpd — the two providers share one host bucket** (the politeness tier is deliberately conservative to cover the pair) | B (live probe 2026-11-02, same corpus; 7,682-row register + LIMH dossier shapes verified) | polite tier |
| rasff (notifications) | 1/2 | none published for the window backend (the portal publishes no quota; the two-step handshake means each search costs 1 shell GET per 15-min session + 1 POST) | B (live probe 2026-11-02, same corpus; 33,256-notification corpus / 11,086 pages measured) | polite tier |
| safety_gate (alerts/report) | 1/2 | none published (static XML downloads off the notifications portal CDN; the weekly index is one request per TTL window) | B (live probe 2026-11-02, same corpus; 1,120 weekly reports, detail 10000329 = 67 notifications) | polite tier |
| fda_recalls (drug/device/food) | 2/5 | **keyless 240 req/min + 1,000/day per IP; key 240/min + 120k/day** | A [openFDA Authentication](https://open.fda.gov/apis/authentication/) 2026-10-30 primary-page verification | minute window compliant (5+120=125≤240); the keyless 1,000/day cap is window-quota type — **bucket blind to it** (§4-2); provider docstring already self-notes the family total ~4 rps |
| fda_drugs (approvals/catalog/orange_book) | 2/5 | openFDA family limit — **one shared bucket per IP across all endpoints** | A (same source as above) | same as above; api.fda.gov hosts five providers (incl. shortages) at 2rps each = 10rps sustained potential > 240/min family line → intra-family stacking (§5-6, the 0.2.8 `rate.group` pattern) |
| fda_devices (510k/pma/registrations/classification) | 2/5 | same as above | A (same source as above) | same as above |
| fda_crl (search) | 2/5 | same as above | A (same source as above) | same as above; quasi-static corpus (TTL 30d) — live exposure minimal |

### company (16)

| provider (face) | Self-set rps/burst | Upstream official limit | Evidence | Verdict |
|---|---|---|---|---|
| gleif (lei_records/_search/direct_parent/ultimate_parent) | 1/2 | fair-use, no published quota (API requires no registration, no key) | A [GLEIF API](https://api.gleif.org/api/v1/) | polite tier |
| edgar_cik (submissions) | 5/5 (formerly 5/10; realigned 0.2.7) | **10 req/s, UA mandatory** | A (SEC access statement, verified 2026-10-19) | ✅ 0.2.7 fixed, flush to the line (quota semantics 5+5=10≤10; §7 exception register) |
| edgar_fts (fulltext_search) | 5/5 (formerly 5/10; realigned 0.2.7) | same as above (same domain, same limit) | A | ✅ 0.2.7 fixed, flush to the line (same as above) |
| fdic_bankfind (institutions) | 0.25/5 | no published figure (responses carry rate-limit headers = throttling exists) | B [BankFind](https://banks.data.fdic.gov/bankfind-suite/bulkdata) | overly-strict candidate (header values still to be probed live) |
| usaspending (spending_by_award) | 0.25/5 | **≈1000/hr/IP keyless** | A (official documentation, verified in the design volume) | window-quota type: 0.25rps≈900/hr flush to the ceiling, bucket blind to it (§5) |
| ror (organizations) | 1/2 | **2000 requests/5min/IP, registration-free** (≈6.7/s average) | A [ROR REST](https://ror.readme.io/docs/rest-api) 2026-10-26 primary-page verification (the search summary's "anonymous 50/5min" was a misreport) | overly strict ~7× (5min window-quota type, ample quota) |
| vies (vat) | 0.5/2 | none published (an aggressive-throttling black box, no figures) | B (probing tradition) | polite tier reasonable |
| ted (notices_search) | 0.5/2 | a formal fair-use policy exists (figure table on the developer portal) | B [TED policy page](https://ted.europa.eu/en/news/fair-usage-policy-on-ted) (the policy page itself 429'd on 2026-10-26, **figures pending verification**) | pending verification |
| fts (gb_fts_release_packages) | 0.5/2 | none published (pagination 1–100 is the effective throttle) | B [FTS OCDS guide](https://www.gov.uk/government/collections/find-a-tender-api-and-specifications) | polite tier |
| cf (gb_contracts_finder_published_notices) | 0.5/2 | none published (same as above) | B [CF API](https://www.contractsfinder.service.gov.uk/apidocumentation) | polite tier |
| ch_zefix (search/firm) | 0.5/2 | none published (official same-origin REST) | C (admission probe 2026-10-29, EU-registries batch: "限流三源均无公布限额，礼貌档 0.5 rps / burst 2") | polite tier |
| no_brreg (enheter/enhet/roller) | 0.5/2 | none published | C (same probe batch) | polite tier |
| fi_ytj (companies) | 0.5/2 | none published | C (same probe batch) | polite tier |
| fr_recherche (search) | 0.5/2 | none published (the per_page 1-25 wall = the effective throttle) | C | polite tier |
| co_rues (companies) | 1/2 | none published (Socrata anonymous tier; the $limit 1-500 politeness cap is self-imposed); **shares the datos.gov.co origin with the other Socrata providers in this ledger (co_sic in legal, co_secop in procurement)** — the anonymous tier is per IP across them all, and the in-process host-layer bucket binds them at one shared quota | B [datos.gov.co](https://datos.gov.co/) (Socrata platform, same anonymous tier as data.ny.gov) | polite tier |
| kr_hometax (biz_status) | 0.5/2 | none published (anonymous single-shot action, no figures) | C (admission probe 2026-10-30, tmp/probe-co-kr/) | polite tier |

### esg (6)

| provider | Self-set | Upstream | Evidence | Verdict |
|---|---|---|---|---|
| eiti (companies/payments) | 0.5/2 | none published (Datasette community service) | C | polite tier |
| climatetrace (owners/sources) | 1/3 | none published | C [Climate TRACE API](https://api.climatetrace.org/) | polite tier |
| eutl (datasets) | 0.5/2 | none published (official bulk-download catalog; static files behind it) | C (design volume §7, 2026-10-29 politeness batch) | n/a-leaning (catalog TTL 1d) |
| epa_frs (facilities/count) | 1/2 | none published (two requests per call: rows+COUNT; size politeness cap 500) | C (same as above) | polite tier |
| thetis_mrv (periods/files) | 0.5/2 | none published (version-ledger catalog, daily roll) | C (same as above) | polite tier |
| paris_mou (detentions/bans/low_performance/inspections) | 0.5/2 | none published (EMSA portlet) | C (same as above; bans face ~1MB in one response, timeout 45s as measured) | polite tier |

### legal (11)

| provider | Self-set rps/burst | Upstream official limit | Evidence | Verdict |
|---|---|---|---|---|
| federalregister (documents) | 1/2 | soft policy with no figures (keyless; the official site has a rate-limiting section but no values) | B [FR API v1](https://www.federalregister.gov/developers/documentation/api/v1) | polite tier |
| dgcomp (cases_search) | 0.5/2 | none published (webgate internal ES face) | C | polite tier reasonable |
| lda (filings) | 14/60 / 1 | **anonymous 15/min; API key 120/min** (we are keyless = anonymous tier) | A [LDA ToS](https://lda.gov/api/tos/) 2026-10-26 primary-page verification | ✅ 0.2.5 fixed, flush to the line (quota semantics 1+14=15≤15, exception register §7) |
| ukec (gb_ec_donations/loans) | 0.5/2 | none published | C | polite tier |
| sipri (trades_search) | 0.5/2 | none published | C | polite tier |
| csl (screening_list) | 0.2/1 | static download fetched in one shot; no rate-limit surface | B | n/a (TTL 1d daily-pull pattern) |
| ecfr (search/titles) | 0.5/1 | no figures; soft IP anti-scraping gate | B [eCFR API](https://www.ecfr.gov/developers/documentation/api/v1) | polite tier |
| courtlistener (opinions_search) | 0.5/3 | **authenticated 5/min+50/hr+125/day; anonymous tighter** (third-party figure ~60/day) | A [CL v4.7](https://wiki.free.law/courtlistener/help/api/rest/v4/rest-api-v47); anonymous tier = B | **day-tier quota type: bucket blind to it (§5)** |
| gb_cma (search/case) | 1/2 | none published (count has no upstream wall — live-verified count=1000 full send 2026-10-29; the wall is our own politeness cap; gov.uk parameter minimalism, unprobed combos 422) | B (live probe 2026-10-29, design volume §uk_cma_cases) | polite tier |
| gb_tna_caselaw (search/judgment) | 0.5/1 | **1000 req / rolling 5 min (≈3.3 rps)** | A (official API docs, caselaw.nationalarchives.gov.uk; provider verified 2026-10-29) | polite tier (~6× under; the Open Justice Licence bars bulk anyway — targeted retrieval face) |
| co_sic (sanctions) | 1/2 | none published (Socrata anonymous tier — **shares the datos.gov.co origin with co_rues (company) and co_secop (procurement): the anonymous tier is per IP across all three, and the in-process host-layer bucket binds them at one shared quota**; the $limit 1-500 cap is our own politeness wall) | B [datos.gov.co](https://datos.gov.co/) (Socrata platform; live probe 2026-10-30, tmp/probe-co-sicoex/) | polite tier |

### research (8; 0.2.4 grants→research migration 2) / security (2)

| provider | Self-set rps/burst | Upstream official limit | Evidence | Verdict |
|---|---|---|---|---|
| nsf (awards) | 1/5 | none published (3000 records/query = result-set cap, not a rate limit) | B [NSF API](https://resources.research.gov/common/webapi/awardapisearch-v1.htm) 2026-10-26 | overly-strict candidate (an unlimited source) |
| nih_reporter (projects/publications) | 1/1 | **1 req/s** (official wording) + 10,000 records/result set | A [RePORTER](https://api.reporter.nih.gov/) 2026-10-26 | ✅ 0.2.5 fixed (spacing semantics burst=1; §7 exception register); the 10k result set vs the 15k live wall comparison is still in audit |
| openalex (works/institutions) | 5/5 (formerly 5/10) | **10 req/s + 100,000 requests/day** (polite pool: User-Agent+mailto gets the faster pool) | A [OpenAlex rate limits](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-premature-banned-ips) 2026-10-27 primary-page verification | ✅ 0.2.4 re-review fixed, flush to the line (quota semantics 5+5=10≤10; at burst 10 it was 10+5=15, a violation); **polite-pool switch = env `AGENTDATA_CONTACT` (mailto: form) injected into the UA (transport._ua())** — closed 0.2.9: no hardcoding identity into the repo (same family as the secrets ruling); without the env set, the standard pool works as usual |
| crossref (works) | 5/10 (formerly 3/6; realigned to the high-capacity tier 0.2.4) | **50 req/s** (polite pool: with mailto; deep-pager has its own dedicated recommendation) | A [Crossref REST API](https://github.com/CrossRef/rest-api-doc) 2026-10-27 primary-page verification | ✅ compliant (10+5=15≤50, ample); **polite-pool switch same as openalex = AGENTDATA_CONTACT env injected into the UA (closed 0.2.9)**; deep-pager = the SDK adopted the cursor channel in 0.2.9 |
| icite (pubs) | 2/4 (formerly 3/6; realigned to the NCBI family tier 0.2.4) | none published | C | family-tier self-review (epmc/rxnav/ctgov/dailymed same 2/4) |
| opencitations (citations) | 1/5 (formerly 3/6; realigned 0.2.4) | none published | C | small-academic-service tier self-review (osv/nsf same 1 rps) |
| gb_gtr (projects) | 1/5 | none published | C | research-service tier self-review |
| biorxiv (details) | 1/5 | none published | C | research-service tier self-review |
| osv (vulns) | 1/5 | **officially stated unlimited** (the 32MiB response cap is not a rate) | A [OSV API](https://google.github.io/osv.dev/api/)/[FAQ](https://osv.dev/faq/) 2026-10-26 | overly-strict candidate (pure politeness) |
| cisa-kev (catalog) | 0.25/2 | static CDN feed, single fetch | B | n/a |

### procurement (5; 0.3.x new domain, first registered here)

| provider | Self-set rps/burst | Upstream official limit | Evidence | Verdict |
|---|---|---|---|---|
| br_pncp (contracts) | 1/2 | none published (the 500-row page cap = the effective throttle; non-upstream params rejected 400) | C (admission probes, design volume §6) | polite tier |
| co_secop (contracts) | 1/2 | Socrata anonymous tier; domain-configured figures not published; **shares the datos.gov.co origin with the other Socrata providers in this ledger (co_rues in company, co_sic in legal)** — the anonymous tier is per IP across them all, and the in-process host-layer bucket binds them at one shared quota | B (Socrata platform, [datos.gov.co](https://www.datos.gov.co/)) | polite tier |
| ny_open_data (abo_contracts/mta_procurements/ogs_dc_payments) | 1/2 | Socrata anonymous tier; same as above ($limit cap 1-500 self-imposed) | B (Socrata platform, [data.ny.gov](https://data.ny.gov/)) | polite tier |
| wb_proc (procnotices) | 1/2 | none published (rows 1-100 politeness cap self-imposed) | C (design volume §6) | polite tier |
| ungm (contract_awards) | 0.5/1 | none published (browser UA mandatory behind a UA fingerprint gate; ASP.NET anti-forgery session pairing; PageSize 1-100 politeness cap self-imposed — the browser itself uses 15) | C (admission probes 2026-10-30) | polite tier |

## 4. Three-Type Layered Conclusions

1. **Rate type (seconds)**: SEC, NIH, the NLM family (RxNav/DailyMed/MesH), ROR (5min window but ≈6.7/s, ample), TED (pending verification) — the token bucket is the right tool; the current mechanism already covers them.
2. **Window-quota type (min/hr/day)**: **LDA anonymous 15/min**, USAspending ≈1000/hr, CourtListener 125/day (anonymous tighter), **openFDA keyless 1,000/day per IP (fda_recalls/fda_drugs/fda_devices/fda_crl + shortages family-shared, verified 2026-10-30)** — **the token bucket is blind to all of them**, and LDA is the only case of our own setting exceeding the limit (a deviation in the opposite direction).
3. **Nothing published / static files**: the remaining ~46 sources — self-set values = pure polite tier; "overly strict" here is a product question, not a compliance question (§5).

## 5. Deviation Ledger and Todos (input list for the design debate)

**Compliance (ruled on → §7; 0.2.5 landed 2026-10-27)**:
1. **lda**: ~~self-set 0.5 rps=30/min > anonymous 15/min, 2× over~~ → fixed to 14/60/1 (flush to the line)
2. **nih_reporter**: ~~burst=5, 5 requests in the first instant > the "no more than one per second" semantics~~ → fixed to 1/1 (spacing)

**Product-level**:
3. Overly-strict list: ~~NLM family (2 vs 20)~~ → **cleared (2026-10-28: 0.2.8 speed-up rxnav/dailymed 2→10, mesh 1→10 + transport family group bucket `rate.group` (nlm group 10+10=20 flush to the official line; the 0.2.6 design batch's "registration-only" guardrail upgraded to runtime))**, ROR (1 vs 6.7), OSV/NSF (1 vs unlimited), fdic (0.25 vs unknown)
4. User-tunable surface, quota-type accounting mechanism (→ §7 ruling)
5. Pending verification: TED figures (policy page 429, to be probed); FDIC throttle headers collected passively; CL anonymous-tier black-box live test; ~~research six-source official rate-limit evidence registration~~ → **cleared (0.2.4 re-review MR)**: openalex/crossref promoted to A (primary-page verification 2026-10-27; openalex also fixed burst 10→5 flush to the line); icite/opencitations/gtr/biorxiv have no official published face, C = end state, not a debt; ~~**edgar quota-semantics candidate re-review** (5/10 vs the official 10 req/s: 15>10, the same lda-type violation; currently judged "aligned (half speed)" per the old 2026-10-19 framing, without passing the §7 general formula — if SEC soft-throttling is tolerable, add an exception registration; otherwise realign to 5/5; assigned to the 0.2.5 case owner for re-review, not moved in this MR)~~ → **cleared (2026-10-28, 0.2.7 realigned to 5/5)**: no betting on "SEC soft-throttling is tolerable"; general formula flush to the line 5+5=10≤10 (§7 exception registration; two regression nails); **lda egress-block re-verification** (since 2026-10-27, Akamai empty-body 403, direct + proxy egress both blocked; immediately following the 2026-10-26 two acceptance-gate rounds that hit lda repeatedly at the 0.5 rps over-limit setting (=30/min, 2× over the anonymous tier) — suspected over-speed triggering an IP-level block; live proof of the motive for the 0.2.5 compliance fix; re-run the two live probes once access recovers)
6. **openFDA family minute+day accounting (2026-10-30 ledger add)**: five api.fda.gov providers (fda_recalls/fda_drugs/fda_devices/fda_crl + shortages) × 2rps each = **10rps sustained potential > the keyless 240/min family line** (one bucket per IP across all endpoints) — the same intra-family stacking shape the NLM group bucket solved in 0.2.8 (`rate.group` mechanism already exists; an `fda` group entry is mechanical); the keyless 1,000/day cap is additionally bucket-blind (§4-2). Page faces + TTL caches keep live exposure far under both lines today; register the group entry + a day-quota stance before any bulk sweep through the SDK surface. **Host-bucket precision (v1.5)**: the host-layer bucket that binds the five providers defaults to 5rps = 300/min, itself above the 240/min keyless line — the host layer mitigates but does not solve this; the group entry (quota ≤4rps) is the correct fix.

## 6. Maintenance Rules

- **A new source must have its upstream rate limits researched and registered in this ledger first** (mandatory item ① of the six-step audit, 2026-10-26 ruling) — a provider without a row in this ledger does not get merged
- Evidence is accepted only from official primary pages/ToS/official documentation; search summaries do not count as A/B-tier evidence (the ROR misreport case, 2026-10-26)
- Any number change in this ledger must trigger a synchronized review of the provider's self-set values (run through §5); verification dates are noted on the row
- Reconcile against the rate column in `capabilities.mjs` (literal-snapshot basis; for publicity, the Python declaration prevails)

## 7. Rate-Limit Design Ruling v1.0 (2026-10-26 self-review + codex R2 debate, converged)

**Principles (after codex corrections)**: default budget = official figure ×50%; flush-to-the-line exceptions must be registered as `{value, pct, scope, window_kind, auth_tier, evidence, date, rationale}` (an official figure's scope of application matters more than the figure itself); officially stated unlimited → polite default of 2 (not a derived safe ceiling); nothing published → per-source status quo + **the passive-evidence route** (rate-limit headers are used only for downward adjustment and diagnosis; upward adjustment requires official documentation or manual multi-sample review — no active load testing).

**The "bucket = window" correction (codex broke it, then rebuilt it)**: a token bucket's maximum admissions over any window W is `burst + rps×W` ≠ a rolling-window counter; the bucket is a smoother, not a window. The flush-to-the-line compliant solution = count burst into the budget.

**0.2.5 compliance fix (an independent early release; landed 2026-10-27 — regression nails in `sdk/python/tests/test_rate_compliance.py`, three layers: live-declaration invariants / virtual-clock sliding-window simulation / all-provider sanity scan. Version-collision note: this batch was originally slated as 0.2.4; the version number yielded to the research-domain expansion batch (d2af49e) merged the same day, renumbered 0.2.5)**:
- lda: 0.5/2 → **14/60≈0.2333 rps / burst 1** (exception registration: quota-semantics flush to the line, 1+14=15≤15)
- nih_reporter: 1/5 → **1/1** (exception registration: spacing semantics — the official wording "no more than one per second" = adjacent interval ≥1s, which burst=1 plus rps=1 exactly satisfies; 60s-count semantics do not apply)
- usaspending 0.25/5 kept (exception registration: `5+900=905 ≤ 1000` compliant by the same formula)
- Offline unit tests: mock-clock assertions that any 60s sliding window is ≤15 (LDA), adjacent requests ≥1.0s apart (NIH), plus a full-bucket-start edge case; the release note declares the deliberate tightening

**0.2.7 supplementary realignment (landed 2026-10-28; executing §5's pre-authorized "otherwise realign to 5/5")**:
- edgar_cik / edgar_fts: 5/10 → **5/5** (exception registration: quota-semantics flush to the line `5+5×1s=10≤10`; an lda-type violation (burst counted into the budget) — no betting on upstream leniency; regression nails = `test_edgar_window_budget_inline` + `test_edgar_any_1s_window_at_most_10`)

**0.2.6 design batch**:
- The machine-readable `limit` declaration (including scope/window_kind/auth_tier/evidence_date) becomes the **single configuration source** (capabilities.mjs/docs derive from it)
- Quota rolling-window mechanism: persistence + atomic reservation + file lock + corruption recovery + monotonic clock; cache hits are not metered (check order: cache → quota → token → network); error code `quota_exhausted` + earliest recovery time (not "resets tomorrow")
- courtlistener anonymous tier: rps 0.5/3 kept + **quota 30/day as a self-set conservative tier** (**rewritten by the 0.2.9 audit**: the official site does not publish anonymous-tier figures — the api-usage page says verbatim "CourtListener has other throttles, for anonymous traffic among others, but they are not reported here"; the authenticated tier is officially on record at 5/min·50/hr·125/day, and anonymous does not inherit it; 429+Retry-After is the only live signal. Same-batch snapshot: the search endpoint returns 401 to anonymous (live-tested 2026-10-28; still usable on 2026-10-26; the rest of the v4 endpoints remain anonymous-200) — under the keyless-only ruling this face is demoted to watch)
- Two env knobs: `AGENTDATA_RATE_SCALE` (scales rps/burst/quota across all dimensions, clamped per-dimension to limit) + `AGENTDATA_RATE_UNSAFE_<PROVIDER>` (explicit dangerous name, startup warning, must not bypass quota)
- osv/nsf 1→2 (polite tier); NLM provider-group metadata guardrail (registration only, no runtime bucket: three sources totaling 5<20, already safe) → **upgraded and landed in 0.2.8**: once the three sources were sped up to 10 rps, "total 5<20" no longer held, and transport gained family group buckets (`rate.group` declaration → `GROUP_LIMITS` registry group quota, nlm=10/10; an unregistered group = declaration error, rejected on the spot)
- LDA optional migration to an exact rolling quota, restoring the full 15/min

**Adjudication record** (12 codex attacks: 9 accepted / 3 rejected):
- Accepted: 50% reworked into default budget + exception registration; scope/window_kind/auth_tier metadata; the "bucket = window" claim falsified (burst counted into the budget); CL anonymous does not inherit the authenticated quota; quota_exhausted as an independent code + earliest recovery time; the quota concurrency-atomicity/persistence-robustness checklist; scale across all dimensions + per-dimension clamping; override requires an explicit unsafe name + warning; the passive-evidence route; NLM metadata grouping
- Rejected: ① lowering NIH to 0.5 — the official wording is spacing semantics, not window counting; 1/1 is exactly compliant, and halving would double the cost of grants batches; ② lowering USAspending to 0.125 — codex's own formula `5+900=905≤1000` proves the current value compliant; ③ CL anonymous 1/min — an unverified third-party figure is not worth cutting an interactive face to one request per minute; 30/day quota is the compromise
