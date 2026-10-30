"""healthcare cli — domain command face registration (split per domain in 0.2.6, moved in from the root cli.py; purely flat since the 0.3.0 verb-layer + sugar removal).

register(v, g): registers flat commands on the domain subparser (g = the root _leaf_globals factory,
passed in as a parameter to avoid a cli ↔ domain-cli cycle); FLAT = the flat dispatch table, merged by the root cli for main to use.
"""
import argparse

def register(v, g):
    # —— Flat panel commands (healthcare main face: source-qualified names + upstream params under original names + our defaults; the only face family since 0.3.0) ——
    f1 = v.add_parser("ctgov_studies", parents=[g()],
                      help="Clinical-trial search (CT.gov v2; --query.term upstream syntax)",
                      description="Clinical trials: raw syntax via --query.term, structured --query.cond/--filter.advanced combine with either; bare call = first page of all studies (legal upstream)")
    f1.add_argument("--query.term", dest="query_term", default=None, help="Raw query expression (upstream param: query.term; AREA[…] syntax, e.g. 'AREA[LeadSponsorName](\"Pfizer\")')")
    f1.add_argument("--query.titles", dest="query_titles", default=None, help="Title-field search (upstream param: query.titles; combinable; aspirin 2983→967)")
    f1.add_argument("--query.intr", dest="query_intr", default=None, help="Intervention-field search (upstream param: query.intr; combinable; insulin 21109→8229)")
    f1.add_argument("--query.cond", dest="query_cond", default=None, help="Condition search (upstream param: query.cond; combinable)")
    f1.add_argument("--filter.advanced", dest="filter_advanced", default=None, help="Advanced filter, AREA[…] syntax (upstream param: filter.advanced; combinable)")
    f1.add_argument("--agg-filters", dest="agg_filters", default=None, help="Facet filter (upstream param: aggFilters; numeric enum values, e.g. phase:3 — PHASE3 → 0 hits)")
    f1.add_argument("--fields", default=None, help="Row slimming, comma-separated (upstream param: fields; e.g. NCTId,BriefTitle)")
    f1.add_argument("--page-size", dest="page_size", type=int, default=20, help="Rows per page (upstream param: pageSize; default 20, no enforced cap)")
    f1.add_argument("--page-token", dest="page_token", default=None, help="Pagination token (upstream param: pageToken; feed next_page_token)")
    f1.add_argument("--sort", default=None, help="Sort (upstream param: sort; e.g. EnrollmentCount:desc)")
    f1.add_argument("--count-total", dest="count_total", action=argparse.BooleanOptionalAction, default=True,
                    help="Request totalCount (upstream param: countTotal; default on)")

    f2 = v.add_parser("dailymed_spls", parents=[g()],
                      help="Drug labeling SPL metadata (DailyMed spls.json)",
                      description="SPL labeling metadata: setid + title + source URL (full-text XML via the URL); manufacturer/setid filters and page/pagesize/sort pass through upstream verbatim")
    f2.add_argument("--search", default=None, help="Drug name (upstream param: drug_name; raw channel)")
    f2.add_argument("--manufacturer", default=None, help="Labeler filter (upstream param: manufacturer; e.g. Pfizer)")
    f2.add_argument("--setid", default=None, help="Exact SPL setid filter (upstream param: setid)")
    f2.add_argument("--page", type=int, default=None, help="Page number (upstream param: page)")
    f2.add_argument("--pagesize", type=int, default=None, help="Rows per page (upstream param: pagesize; silent clamp at 100 — echoed as elements_per_page)")
    f2.add_argument("--sort", default=None, help="Sort (upstream param: sort; e.g. published_date)")

    f3 = v.add_parser("epmc_search", parents=[g()],
                      help="Literature evidence (Europe PMC; --search upstream syntax)",
                      description="Literature search incl. full PubMed: raw query syntax via --search (AFF: for affiliations); cursor pagination via next_cursor_mark")
    f3.add_argument("--search", default=None, help="Raw query expression (upstream param: query; e.g. 'AFF:\"Novartis\" AND \"psoriasis\"')")
    f3.add_argument("--result-type", dest="result_type", default="lite", choices=["lite", "core", "full", "idlist"],
                    help="Row depth (upstream param: resultType; default lite)")
    f3.add_argument("--page-size", dest="page_size", type=int, default=25, help="Rows per page (upstream param: pageSize; 1-1000, default 25)")
    f3.add_argument("--cursor-mark", dest="cursor_mark", default="*", help="Pagination cursor (upstream param: cursorMark; * = first page)")
    f3.add_argument("--sort", default=None, help="Sort (upstream param: sort; e.g. 'CITED desc')")

    f4 = v.add_parser("eudamed_devices_udi_di_data", parents=[g()],
                      help="EU device master record (EUDAMED primaryDi exact + upstream pagination)",
                      description="EU device record: manufacturer SRN + EU authorised-rep SRN edges (cold ~50s — primaryDi is unindexed upstream)")
    f4.add_argument("--primary-di", dest="primary_di", required=True, help="EU UDI-DI (upstream param: primaryDi)")
    f4.add_argument("--page", type=int, default=0, help="Page number (upstream param: page; default 0)")
    f4.add_argument("--page-size", dest="page_size", type=int, default=5, help="Rows per page (upstream param: pageSize; default 5)")
    f4.add_argument("--iso2-code", dest="iso2_code", default="en", help="Language (upstream param: iso2Code; default en)")

    f5 = v.add_parser("fda_crl_letters", parents=[g()],
                       help="FDA Complete Response Letters (openFDA transparency/crl; upstream-verbatim params)",
                       description="Complete Response Letters: company × negative-approval events (approval_status = application outcome "
                   "after the letter). company_rep (person name, PII) and text (OCR noise) are dropped at the row-shaping layer. "
                   "Zero hits = valid answer (404 NOT_FOUND)")
    f5.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'company_name:\"Firm Name\"' — required)")
    f5.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f5.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f5.add_argument("--sort", default="letter_date:desc", help="Sort (upstream param: sort; our default letter_date:desc)")

    # —— Wave 10b openFDA family, seven faces (2026-10-29; born flat: upstream param original names only, zero sugar, zero deprecation debt) ——

    f6 = v.add_parser("fda_device_510k", parents=[g()],
                       help="FDA device 510(k) clearances (openFDA device/510k; upstream-verbatim params)",
                       description="Premarket notification clearances (176,466 rows): k_number × applicant with decision "
                                   "code/date. contact (person name, PII) and the openfda blob (100+ registration numbers "
                                   "per row) are dropped at the row-shaping layer. Zero hits = valid answer")
    f6.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'applicant:\"Medtronic\"' — required)")
    f6.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f6.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f6.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default decision_date:desc)")

    f7 = v.add_parser("fda_device_classification", parents=[g()],
                       help="FDA device product-code classification (openFDA device/classification; upstream-verbatim params)",
                       description="Product-code taxonomy (device_name × product_code × device_class with 21 CFR regulation "
                                   "number); no date field, so no default sort. product_code joins the 510(k)/PMA/recall "
                                   "faces. Zero hits = valid answer")
    f7.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'device_name:\"syringe\"' — required)")
    f7.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f7.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f7.add_argument("--sort", default=None, help="Sort (upstream param: sort; no default — this face has no date field)")

    f8 = v.add_parser("fda_device_pma", parents=[g()],
                       help="FDA device PMA approvals (openFDA device/pma; upstream-verbatim params)",
                       description="Premarket approvals + supplements (12,896 rows): pma_number × applicant with decision "
                                   "code/date. ao_statement (long text) and street-level address are dropped. "
                                   "Zero hits = valid answer")
    f8.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'applicant:\"Medtronic\"' — required)")
    f8.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f8.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f8.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default decision_date:desc)")

    f9 = v.add_parser("fda_device_recalls", parents=[g()],
                       help="FDA device recalls (openFDA device/recall RES system; upstream-verbatim params)",
                       description="Device recalls from the RES system (incl. Ongoing full lifecycle; a different system from the bulk-loaded "
                   "device/enforcement press releases). Rows carry firm_fei_number + k_numbers hub keys. "
                   "Firm matching uses the phrase form (probed 2026-10-28)")
    f9.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'recalling_firm:\"Firm Name\"' phrase — .exact unprobed; required)")
    f9.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f9.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f9.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default event_date_posted:desc)")

    f10 = v.add_parser("fda_device_registrations", parents=[g()],
                       help="FDA device establishment registrations (openFDA device/registrationlisting; upstream-verbatim params)",
                       description="Establishment registration & listing (336,946 rows, quarterly): registration_number/fei_number "
                                   "× firm_name. All searchable fields live in the registration.* namespace (top-level "
                                   "firm_name/fei_number don't match — probed 2026-10-29). us_agent and "
                                   "official_correspondent (person contacts, PII) are dropped. Zero hits = valid answer")
    f10.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'registration.name:\"Firm Name\"' — required)")
    f10.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f10.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f10.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default registration.reg_expiry_date_year:desc)")

    f11 = v.add_parser("fda_drug_approvals", parents=[g()],
                       help="FDA drug application/approval records (openFDA drug/drugsfda; upstream-verbatim params)",
                       description="Drugs@FDA application dossiers (29,420 applications): application_number × sponsor_name "
                                   "with products[] and submissions[] timelines. Company search uses sponsor_name "
                                   "(applicant_name is a docs illusion — probed 2026-10-29). Zero hits = valid answer")
    f11.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'sponsor_name:\"TEVA\"' — keyword field is case-sensitive, match stored form; required)")
    f11.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f11.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f11.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default submissions.submission_status_date:desc)")

    f12 = v.add_parser("fda_drug_catalog", parents=[g()],
                       help="FDA NDC directory (openFDA drug/ndc; upstream-verbatim params)",
                       description="NDC product catalog (daily refresh): product_ndc × labeler_name with marketing dates and "
                                   "category — NSDE content lives here (the separate /drug/nsde.json endpoint is dead, "
                                   "probed 2026-10-29). Zero hits = valid answer")
    f12.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'labeler_name:\"pfizer\"' — required)")
    f12.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f12.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f12.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default marketing_start_date:desc)")

    f13 = v.add_parser("fda_drug_recalls", parents=[g()],
                       help="FDA drug recalls (openFDA drug/enforcement; upstream-verbatim params)",
                       description="Drug recall/enforcement records 2012+ (press-release source — drug has no separate recall endpoint): "
                                   "recall_number × recalling_firm with class/status/reason. Zero hits = valid answer (404 NOT_FOUND)")
    f13.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'recalling_firm.exact:\"Firm Name\"' — required)")
    f13.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f13.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f13.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default report_date:desc)")

    f14 = v.add_parser("fda_drug_shortages", parents=[g()],
                      help="FDA drug shortages (openFDA; --search upstream syntax)",
                      description="Drug-shortage records: supply-risk event stream (status/availability/reason); limit 1-1000 is an upstream hard wall, deeper via --skip")
    f14.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'generic_name:\"bupivacaine\"' or 'openfda.manufacturer_name.exact:\"Fresenius Kabi USA, LLC\"')")
    f14.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f14.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f14.add_argument("--sort", default="update_date:desc", help="Sort (upstream param: sort; our default update_date:desc)")

    f15 = v.add_parser("fda_food_recalls", parents=[g()],
                       help="FDA food recalls (openFDA food/enforcement; upstream-verbatim params)",
                       description="Food recall/enforcement records 2012+: recall_number × recalling_firm with class/status/reason. "
                                   "Zero hits = valid answer (404 NOT_FOUND)")
    f15.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'recalling_firm.exact:\"Firm Name\"' — required)")
    f15.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f15.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f15.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default report_date:desc)")

    f16 = v.add_parser("fda_orangebook", parents=[g()],
                       help="FDA Orange Book approved drugs (openFDA drug/orangebook; upstream-verbatim params)",
                       description="Orange Book approved-drug products (48,865 rows): approval_date × application holder with "
                                   "RLD/reference-standard flags. Company keys sit inside products[] (application_name / "
                                   "application_full_name — top-level applicant fields don't exist, probed 2026-10-29). "
                                   "Zero hits = valid answer")
    f16.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'products.application_full_name:\"Teva\"' — required)")
    f16.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f16.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f16.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default approval_date:desc)")

    f17 = v.add_parser("gudid_devices", parents=[g()],
                      help="US device master record (AccessGUDID v3, one of di/udi/record_key)",
                      description="US device record: brand/company/product codes (exactly one of --di / --udi / --record-key)")
    f17.add_argument("--di", default=None, help="Device Identifier (upstream param: di)")
    f17.add_argument("--udi", default=None, help="Full UDI (upstream param: udi)")
    f17.add_argument("--record-key", dest="record_key", default=None, help="Record key (upstream param: record_key)")

    f18 = v.add_parser("mesh_descriptor", parents=[g()],
                      help="Term→MeSH descriptor + synonym pool (NLM lookup API)",
                      description="Drug/disease term → MeSH descriptor candidates + top hit's synonym pool (controlled-vocabulary anchor)")
    f18.add_argument("--label", required=True, help="Term to look up (upstream param: label — passing term/descriptor gets 400)")
    f18.add_argument("--match", default="contains", choices=["contains", "exact", "startswith"],
                    help="Match mode (upstream param: match; default contains)")
    f18.add_argument("--limit", type=int, default=10, help="Candidates cap (upstream param: limit; default 10, cap 50)")

    f19 = v.add_parser("rxnav_rxcui_atc", parents=[g()],
                      help="RxCUI→ATC class (RxNav property.json?propName=ATC)",
                      description="RxCUI → ATC classification (numeric RxCUI only; resolve names first via rxnav_rxcui_by_name)")
    f19.add_argument("--rxcui", required=True, help="Numeric RxCUI (upstream param: rxcui)")

    f20 = v.add_parser("rxnav_rxcui_by_name", parents=[g()],
                      help="Drug name→RxCUI card (RxNav rxcuiByName)",
                      description="Identity normalization: drug/brand name → RxCUI (single-record face, no pagination)")
    f20.add_argument("--name", required=True, help="Drug or brand name (upstream param: name)")

    f21 = v.add_parser("tga_artg", parents=[g()],
                       help="AU ARTG registered products (TGA eBS; --query raw words)",
                       description="Australian Register of Therapeutic Goods: product×sponsor rows (97,988 entries; sponsor = Australian marketing accountability entity)")
    f21.add_argument("--query", default=None, help="Free-text words, AND across all fields (upstream param: Query; quoted phrase narrows onto the sponsor)")
    f21.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: Count; cap 100, default 20)")
    f21.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: Start; default 0)")

    f22 = v.add_parser("tga_manufacturers", parents=[g()],
                       help="AU medical-device manufacturer licences (TGA MIS, single-shot full register)",
                       description="Australian manufacturer licence register (444 licences, one full shot + state filter); licence × manufacturer edge")
    f22.add_argument("--state", default=None, help="State filter, e.g. QLD / NSW / VIC (local post-filter on SiteState)")
    f22.add_argument("--limit", type=int, default=100, help="Rows to return (upstream param: count; cap 500, default 100)")

    # —— Wave 10 openFDA family, four faces (2026-10-28; born flat: upstream param original names only, zero sugar, zero deprecation debt) ——

FLAT = {
    "ctgov_studies": lambda a: {"query_term": a.query_term, "query_titles": a.query_titles,
                               "query_intr": a.query_intr, "query_cond": a.query_cond,
                               "filter_advanced": a.filter_advanced, "agg_filters": a.agg_filters,
                               "fields": a.fields,
                               "page_size": a.page_size, "page_token": a.page_token,
                               "sort": a.sort, "count_total": a.count_total},
    "dailymed_spls": lambda a: {"search": a.search, "manufacturer": a.manufacturer,
                                 "setid": a.setid, "page": a.page, "pagesize": a.pagesize, "sort": a.sort},
    "epmc_search": lambda a: {"search": a.search, "result_type": a.result_type,
                                "page_size": a.page_size, "cursor_mark": a.cursor_mark, "sort": a.sort},
    "eudamed_devices_udi_di_data": lambda a: {"primary_di": a.primary_di, "page": a.page,
                                 "page_size": a.page_size, "iso2_code": a.iso2_code},
    "fda_crl_letters": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    # Wave 10b openFDA family, seven faces (born flat: upstream param names passed through, no sugar keys)
    "fda_device_510k": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "fda_device_classification": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "fda_device_pma": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "fda_device_recalls": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "fda_device_registrations": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "fda_drug_approvals": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "fda_drug_catalog": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "fda_drug_recalls": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "fda_drug_shortages": lambda a: {"search": a.search,
                                     "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "fda_food_recalls": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "fda_orangebook": lambda a: {"search": a.search, "limit": a.limit, "skip": a.skip, "sort": a.sort},
    "gudid_devices": lambda a: {"di": a.di, "udi": a.udi, "record_key": a.record_key},
    "mesh_descriptor": lambda a: {"label": a.label, "match": a.match, "limit": a.limit},
    "rxnav_rxcui_atc": lambda a: {"rxcui": a.rxcui},
    "rxnav_rxcui_by_name": lambda a: {"name": a.name},
    "tga_artg": lambda a: {"query": a.query, "limit": a.limit, "skip": a.skip},
    "tga_manufacturers": lambda a: {"state": a.state, "limit": a.limit},
    # Wave 10 openFDA family, four faces (born flat: upstream param names passed through, no sugar keys)
}


# 0.3.10 jurisdiction chapter: face → jurisdiction (default = the issuing authority's jurisdiction; bodies
# covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2 + EU + GLOBAL) — merged into _JURISDICTION by the root cli.py; success envelopes carry the jurisdiction chapter
COUNTRY = {
    "ctgov_studies": "US",
    "dailymed_spls": "US",
    "epmc_search": "GLOBAL",
    "eudamed_devices_udi_di_data": "EU",
    "fda_crl_letters": "US",
    "fda_device_510k": "US",
    "fda_device_classification": "US",
    "fda_device_pma": "US",
    "fda_device_recalls": "US",
    "fda_device_registrations": "US",
    "fda_drug_approvals": "US",
    "fda_drug_catalog": "US",
    "fda_drug_recalls": "US",
    "fda_drug_shortages": "US",
    "fda_food_recalls": "US",
    "fda_orangebook": "US",
    "gudid_devices": "US",
    "mesh_descriptor": "GLOBAL",
    "rxnav_rxcui_atc": "US",
    "rxnav_rxcui_by_name": "US",
    "tga_artg": "AU",
    "tga_manufacturers": "AU",
}
