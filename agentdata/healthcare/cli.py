"""healthcare cli — domain command face registration (split per domain in 0.2.6, moved in from the root cli.py; purely flat since the 0.3.0 verb-layer + sugar removal).

register(v, g): registers flat commands on the domain subparser (g = the root _leaf_globals factory,
passed in as a parameter to avoid a cli ↔ domain-cli cycle); FLAT = the flat dispatch table, merged by the root cli for main to use.
"""
import argparse

def register(v, g):
    # —— Flat panel commands (healthcare main face: source-qualified names + upstream params under original names + our defaults; the only face family since 0.3.0) ——
    f1 = v.add_parser("au_tga_artg", parents=[g()],
                       help="AU ARTG registered products (TGA eBS; --query raw words)",
                       description="Australian Register of Therapeutic Goods: product×sponsor rows (97,988 entries; sponsor = Australian marketing accountability entity)")
    f1.add_argument("--query", default=None, help="Free-text words, AND across all fields (upstream param: Query; quoted phrase narrows onto the sponsor)")
    f1.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: Count; cap 100, default 20)")
    f1.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: Start; default 0)")

    f2 = v.add_parser("au_tga_manufacturers", parents=[g()],
                       help="AU medical-device manufacturer licences (TGA MIS, single-shot full register)",
                       description="Australian manufacturer licence register (444 licences, one full shot + state filter); licence × manufacturer edge")
    f2.add_argument("--state", default=None, help="State filter, e.g. QLD / NSW / VIC (local post-filter on SiteState)")
    f2.add_argument("--limit", type=int, default=100, help="Rows to return (upstream param: count; cap 500, default 100)")

    # —— 0.3.19 CA + EU product-safety faces (born flat: upstream param original names + closed-set validation; probed 2026-11-02) ——

    f3 = v.add_parser("ca_dpd_companies", parents=[g()],
                      help="CA DPD company register (one full shot; local limit/skip slice)",
                      description="Health Canada Drug Product Database companies: 5,253 DIN owners with company_code join key + postal address (no upstream paging — one cached full register)")
    f3.add_argument("--limit", type=int, default=200, help="Rows to return (local post-slice over the single cached full shot)")
    f3.add_argument("--skip", type=int, default=0, help="Rows to skip (local post-slice)")

    f4 = v.add_parser("ca_dpd_drug_products", parents=[g()],
                      help="CA DPD drug products by market status (status closed set)",
                      description="Drug Product Database products: DIN + brand + company rows, filtered by the Read Me status closed set — status is required (an unknown value is silently ignored upstream and dumps the whole 15MB register)")
    f4.add_argument("--status", type=int, required=True, help="Market status, closed set 1=Approved 2=Marketed 3=Cancelled Pre-Market 4=Cancelled Post-Market 6=Dormant (validated: any other value silently dumps the full 15MB register)")
    f4.add_argument("--limit", type=int, default=200, help="Rows to return (local post-slice)")
    f4.add_argument("--skip", type=int, default=0, help="Rows to skip (local post-slice)")

    f5 = v.add_parser("ca_mdall_companies", parents=[g()],
                      help="CA MDALL medical-device company register (one full shot; local limit/skip slice)",
                      description="Medical Devices Active Licence Listing companies: 7,682 device makers/importers (a two-country register — US rows carry country_cd US) with company_id join key + active/inactive status")
    f5.add_argument("--limit", type=int, default=200, help="Rows to return (local post-slice over the single cached full shot)")
    f5.add_argument("--skip", type=int, default=0, help="Rows to skip (local post-slice)")

    f6 = v.add_parser("ca_mdall_licence", parents=[g()],
                      help="CA MDALL single-licence dossier (LIMH information page)",
                      description="The licence dossier: manufacturer block + Company ID + device class + the device-identifier family — active|archived are separate upstream indexes (ask for inactive licences with --licence-type archived)")
    f6.add_argument("--licence-id", dest="licence_id", required=True, help="Numeric MDALL licence number (upstream param: licenceId; e.g. 111577)")
    f6.add_argument("--licence-type", dest="licence_type", default="active", choices=["active", "archived"], help="Licence index (upstream param: type; default active)")
    f6.add_argument("--lang", default="eng", choices=["eng", "fra"], help="Language (upstream param: lang; default eng)")

    f7 = v.add_parser("ctgov_studies", parents=[g()],
                      help="Clinical-trial search (CT.gov v2; --query.term upstream syntax)",
                      description="Clinical trials: raw syntax via --query.term, structured --query.cond/--filter.advanced combine with either; bare call = first page of all studies (legal upstream)")
    f7.add_argument("--query.term", dest="query_term", default=None, help="Raw query expression (upstream param: query.term; AREA[…] syntax, e.g. 'AREA[LeadSponsorName](\"Pfizer\")')")
    f7.add_argument("--query.titles", dest="query_titles", default=None, help="Title-field search (upstream param: query.titles; combinable; aspirin 2983→967)")
    f7.add_argument("--query.intr", dest="query_intr", default=None, help="Intervention-field search (upstream param: query.intr; combinable; insulin 21109→8229)")
    f7.add_argument("--query.cond", dest="query_cond", default=None, help="Condition search (upstream param: query.cond; combinable)")
    f7.add_argument("--filter.advanced", dest="filter_advanced", default=None, help="Advanced filter, AREA[…] syntax (upstream param: filter.advanced; combinable)")
    f7.add_argument("--agg-filters", dest="agg_filters", default=None, help="Facet filter (upstream param: aggFilters; numeric enum values, e.g. phase:3 — PHASE3 → 0 hits)")
    f7.add_argument("--fields", default=None, help="Row slimming, comma-separated (upstream param: fields; e.g. NCTId,BriefTitle)")
    f7.add_argument("--page-size", dest="page_size", type=int, default=20, help="Rows per page (upstream param: pageSize; default 20, no enforced cap)")
    f7.add_argument("--page-token", dest="page_token", default=None, help="Pagination token (upstream param: pageToken; feed next_page_token)")
    f7.add_argument("--sort", default=None, help="Sort (upstream param: sort; e.g. EnrollmentCount:desc)")
    f7.add_argument("--count-total", dest="count_total", action=argparse.BooleanOptionalAction, default=True,
                    help="Request totalCount (upstream param: countTotal; default on)")

    f8 = v.add_parser("dailymed_spls", parents=[g()],
                      help="Drug labeling SPL metadata (DailyMed spls.json)",
                      description="SPL labeling metadata: setid + title + source URL (full-text XML via the URL); manufacturer/setid filters and page/pagesize/sort pass through upstream verbatim")
    f8.add_argument("--search", default=None, help="Drug name (upstream param: drug_name; raw channel)")
    f8.add_argument("--manufacturer", default=None, help="Labeler filter (upstream param: manufacturer; e.g. Pfizer)")
    f8.add_argument("--setid", default=None, help="Exact SPL setid filter (upstream param: setid)")
    f8.add_argument("--page", type=int, default=None, help="Page number (upstream param: page)")
    f8.add_argument("--pagesize", type=int, default=None, help="Rows per page (upstream param: pagesize; silent clamp at 100 — echoed as elements_per_page)")
    f8.add_argument("--sort", default=None, help="Sort (upstream param: sort; e.g. published_date)")

    f9 = v.add_parser("epmc_search", parents=[g()],
                      help="Literature evidence (Europe PMC; --search upstream syntax)",
                      description="Literature search incl. full PubMed: raw query syntax via --search (AFF: for affiliations); cursor pagination via next_cursor_mark")
    f9.add_argument("--search", default=None, help="Raw query expression (upstream param: query; e.g. 'AFF:\"Novartis\" AND \"psoriasis\"')")
    f9.add_argument("--result-type", dest="result_type", default="lite", choices=["lite", "core", "full", "idlist"],
                    help="Row depth (upstream param: resultType; default lite)")
    f9.add_argument("--page-size", dest="page_size", type=int, default=25, help="Rows per page (upstream param: pageSize; 1-1000, default 25)")
    f9.add_argument("--cursor-mark", dest="cursor_mark", default="*", help="Pagination cursor (upstream param: cursorMark; * = first page)")
    f9.add_argument("--sort", default=None, help="Sort (upstream param: sort; e.g. 'CITED desc')")

    f10 = v.add_parser("eudamed_devices_udi_di_data", parents=[g()],
                      help="EU device master record (EUDAMED primaryDi exact + upstream pagination)",
                      description="EU device record: manufacturer SRN + EU authorised-rep SRN edges (cold ~50s — primaryDi is unindexed upstream)")
    f10.add_argument("--primary-di", dest="primary_di", required=True, help="EU UDI-DI (upstream param: primaryDi)")
    f10.add_argument("--page", type=int, default=0, help="Page number (upstream param: page; default 0)")
    f10.add_argument("--page-size", dest="page_size", type=int, default=5, help="Rows per page (upstream param: pageSize; default 5)")
    f10.add_argument("--iso2-code", dest="iso2_code", default="en", help="Language (upstream param: iso2Code; default en)")

    f11 = v.add_parser("fda_crl_letters", parents=[g()],
                       help="FDA Complete Response Letters (openFDA transparency/crl; upstream-verbatim params)",
                       description="Complete Response Letters: company × negative-approval events (approval_status = application outcome "
                   "after the letter). company_rep (person name, PII) and text (OCR noise) are dropped at the row-shaping layer. "
                   "Zero hits = valid answer (404 NOT_FOUND)")
    f11.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'company_name:\"Firm Name\"' — required)")
    f11.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f11.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f11.add_argument("--sort", default="letter_date:desc", help="Sort (upstream param: sort; our default letter_date:desc)")

    # —— Wave 10b openFDA family, seven faces (2026-10-29; born flat: upstream param original names only, zero sugar, zero deprecation debt) ——

    f12 = v.add_parser("fda_device_510k", parents=[g()],
                       help="FDA device 510(k) clearances (openFDA device/510k; upstream-verbatim params)",
                       description="Premarket notification clearances (176,466 rows): k_number × applicant with decision "
                                   "code/date. contact (person name, PII) and the openfda blob (100+ registration numbers "
                                   "per row) are dropped at the row-shaping layer. Zero hits = valid answer")
    f12.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'applicant:\"Medtronic\"' — required)")
    f12.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f12.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f12.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default decision_date:desc)")

    f13 = v.add_parser("fda_device_classification", parents=[g()],
                       help="FDA device product-code classification (openFDA device/classification; upstream-verbatim params)",
                       description="Product-code taxonomy (device_name × product_code × device_class with 21 CFR regulation "
                                   "number); no date field, so no default sort. product_code joins the 510(k)/PMA/recall "
                                   "faces. Zero hits = valid answer")
    f13.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'device_name:\"syringe\"' — required)")
    f13.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f13.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f13.add_argument("--sort", default=None, help="Sort (upstream param: sort; no default — this face has no date field)")

    f14 = v.add_parser("fda_device_pma", parents=[g()],
                       help="FDA device PMA approvals (openFDA device/pma; upstream-verbatim params)",
                       description="Premarket approvals + supplements (12,896 rows): pma_number × applicant with decision "
                                   "code/date. ao_statement (long text) and street-level address are dropped. "
                                   "Zero hits = valid answer")
    f14.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'applicant:\"Medtronic\"' — required)")
    f14.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f14.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f14.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default decision_date:desc)")

    f15 = v.add_parser("fda_device_recalls", parents=[g()],
                       help="FDA device recalls (openFDA device/recall RES system; upstream-verbatim params)",
                       description="Device recalls from the RES system (incl. Ongoing full lifecycle; a different system from the bulk-loaded "
                   "device/enforcement press releases). Rows carry firm_fei_number + k_numbers hub keys. "
                   "Firm matching uses the phrase form (probed 2026-10-28)")
    f15.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'recalling_firm:\"Firm Name\"' phrase — .exact unprobed; required)")
    f15.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f15.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f15.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default event_date_posted:desc)")

    f16 = v.add_parser("fda_device_registrations", parents=[g()],
                       help="FDA device establishment registrations (openFDA device/registrationlisting; upstream-verbatim params)",
                       description="Establishment registration & listing (336,946 rows, quarterly): registration_number/fei_number "
                                   "× firm_name. All searchable fields live in the registration.* namespace (top-level "
                                   "firm_name/fei_number don't match — probed 2026-10-29). us_agent and "
                                   "official_correspondent (person contacts, PII) are dropped. Zero hits = valid answer")
    f16.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'registration.name:\"Firm Name\"' — required)")
    f16.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f16.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f16.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default registration.reg_expiry_date_year:desc)")

    f17 = v.add_parser("fda_drug_approvals", parents=[g()],
                       help="FDA drug application/approval records (openFDA drug/drugsfda; upstream-verbatim params)",
                       description="Drugs@FDA application dossiers (29,420 applications): application_number × sponsor_name "
                                   "with products[] and submissions[] timelines. Company search uses sponsor_name "
                                   "(applicant_name is a docs illusion — probed 2026-10-29). Zero hits = valid answer")
    f17.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'sponsor_name:\"TEVA\"' — keyword field is case-sensitive, match stored form; required)")
    f17.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f17.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f17.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default submissions.submission_status_date:desc)")

    f18 = v.add_parser("fda_drug_catalog", parents=[g()],
                       help="FDA NDC directory (openFDA drug/ndc; upstream-verbatim params)",
                       description="NDC product catalog (daily refresh): product_ndc × labeler_name with marketing dates and "
                                   "category — NSDE content lives here (the separate /drug/nsde.json endpoint is dead, "
                                   "probed 2026-10-29). Zero hits = valid answer")
    f18.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'labeler_name:\"pfizer\"' — required)")
    f18.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f18.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f18.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default marketing_start_date:desc)")

    f19 = v.add_parser("fda_drug_recalls", parents=[g()],
                       help="FDA drug recalls (openFDA drug/enforcement; upstream-verbatim params)",
                       description="Drug recall/enforcement records 2012+ (press-release source — drug has no separate recall endpoint): "
                                   "recall_number × recalling_firm with class/status/reason. Zero hits = valid answer (404 NOT_FOUND)")
    f19.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'recalling_firm.exact:\"Firm Name\"' — required)")
    f19.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f19.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f19.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default report_date:desc)")

    f20 = v.add_parser("fda_drug_shortages", parents=[g()],
                      help="FDA drug shortages (openFDA; --search upstream syntax)",
                      description="Drug-shortage records: supply-risk event stream (status/availability/reason); limit 1-1000 is an upstream hard wall, deeper via --skip")
    f20.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'generic_name:\"bupivacaine\"' or 'openfda.manufacturer_name.exact:\"Fresenius Kabi USA, LLC\"')")
    f20.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f20.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f20.add_argument("--sort", default="update_date:desc", help="Sort (upstream param: sort; our default update_date:desc)")

    f21 = v.add_parser("fda_food_recalls", parents=[g()],
                       help="FDA food recalls (openFDA food/enforcement; upstream-verbatim params)",
                       description="Food recall/enforcement records 2012+: recall_number × recalling_firm with class/status/reason. "
                                   "Zero hits = valid answer (404 NOT_FOUND)")
    f21.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'recalling_firm.exact:\"Firm Name\"' — required)")
    f21.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f21.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f21.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default report_date:desc)")

    f22 = v.add_parser("fda_orangebook", parents=[g()],
                       help="FDA Orange Book approved drugs (openFDA drug/orangebook; upstream-verbatim params)",
                       description="Orange Book approved-drug products (48,865 rows): approval_date × application holder with "
                                   "RLD/reference-standard flags. Company keys sit inside products[] (application_name / "
                                   "application_full_name — top-level applicant fields don't exist, probed 2026-10-29). "
                                   "Zero hits = valid answer")
    f22.add_argument("--search", default=None, help="Raw query expression (upstream param: search; e.g. 'products.application_full_name:\"Teva\"' — required)")
    f22.add_argument("--limit", type=int, default=20, help="Rows to return (upstream param: limit; 1-1000 hard wall, default 20)")
    f22.add_argument("--skip", type=int, default=0, help="Rows to skip (upstream param: skip; default 0)")
    f22.add_argument("--sort", default=None, help="Sort (upstream param: sort; our default approval_date:desc)")

    # —— 0.3.16 UK MHRA safety-alert twin faces (gov.uk search/content API, same contract family as the gb_cma case chain; stood up from live probing 2026-10-30) ——

    f23 = v.add_parser("gb_mhra_alert", parents=[g()],
                       help="UK MHRA single-alert dossier (gov.uk content API)",
                       description="UK MHRA single safety-alert dossier (keyless): content_id is the stable UUID key; "
                                   "alert_type/issued_date are the MHRA metadata fields (medicines-recall-notification, "
                                   "device-field-safety-notice …); attachments = the notice PDF family. The content API "
                                   "has no .json variant — a trailing .json serves the 404 page (a pasted slug with it "
                                   "gets it stripped); a pasted full base_path (/drug-device-alerts/<slug> or absolute "
                                   "URL) is accepted — the prefix is stripped")
    f23.add_argument("--slug", required=True, help="Alert slug (from gb_mhra_alerts rows; bare tail segment, e.g. class-2-medicines-recall-xeal-pharma-clopidogrel-oral-liquids-all-strengths-el-26-a-slash-43)")

    f24 = v.add_parser("gb_mhra_alerts", parents=[g()],
                       help="UK MHRA medicines & device safety alerts (drug alerts, device alerts, FSN weeklies)",
                       description="UK MHRA safety-alert search (gov.uk search API, keyless): q verbatim over alert "
                                   "titles/bodies — a company-name penetration channel (Abbott → 160 alerts across "
                                   "2019-2026, probed 2026-10-30); count politeness cap 100; start = offset "
                                   "pagination; omit --q to enumerate the full live register (~1,462 alerts). "
                                   "Single-alert detail: gb_mhra_alert with the slug from each row (under a q= query "
                                   "the rows drop link — the row mapper then reads the _id base_path)")
    f24.add_argument("--q", default=None, help="Query term (upstream param: q; company/product names penetrate — e.g. Abbott, recall class)")
    f24.add_argument("--count", type=int, default=20, help="Rows (upstream param: count; 1-100 politeness cap)")
    f24.add_argument("--start", type=int, default=0, help="Offset (upstream param: start)")

    f25 = v.add_parser("gudid_devices", parents=[g()],
                      help="US device master record (AccessGUDID v3, one of di/udi/record_key)",
                      description="US device record: brand/company/product codes (exactly one of --di / --udi / --record-key)")
    f25.add_argument("--di", default=None, help="Device Identifier (upstream param: di)")
    f25.add_argument("--udi", default=None, help="Full UDI (upstream param: udi)")
    f25.add_argument("--record-key", dest="record_key", default=None, help="Record key (upstream param: record_key)")

    f26 = v.add_parser("mesh_descriptor", parents=[g()],
                      help="Term→MeSH descriptor + synonym pool (NLM lookup API)",
                      description="Drug/disease term → MeSH descriptor candidates + top hit's synonym pool (controlled-vocabulary anchor)")
    f26.add_argument("--label", required=True, help="Term to look up (upstream param: label — passing term/descriptor gets 400)")
    f26.add_argument("--match", default="contains", choices=["contains", "exact", "startswith"],
                    help="Match mode (upstream param: match; default contains)")
    f26.add_argument("--limit", type=int, default=10, help="Candidates cap (upstream param: limit; default 10, cap 50)")

    f27 = v.add_parser("rasff_notifications", parents=[g()],
                       help="EU RASFF food-safety alert search (window backend)",
                       description="The consolidated English RASFF window: subject/reference/date-window filters (the proven ones — enum-shaped country filters stay unprobed upstream) + paging; 33k-notification corpus, notifying country × product × risk rows")
    f27.add_argument("--subject", default=None, help="Free text on the alert subject (upstream param: subject; e.g. aflatoxin)")
    f27.add_argument("--notification-reference", dest="notification_reference", default=None, help="Reference number, exact (upstream param: notificationReference; e.g. 2026.9701)")
    f27.add_argument("--ec-valid-date-from", dest="ec_valid_date_from", default=None, help="Window start (upstream param: ecValidDateFrom; format dd-MM-yyyy, e.g. 01-09-2026 — ISO input is rejected upstream)")
    f27.add_argument("--ec-valid-date-to", dest="ec_valid_date_to", default=None, help="Window end (upstream param: ecValidDateTo; format dd-MM-yyyy)")
    f27.add_argument("--page-number", dest="page_number", type=int, default=1, help="Page number, 1-based (upstream param: pageNumber)")
    f27.add_argument("--items-per-page", dest="items_per_page", type=int, default=25, help="Rows per page (upstream param: itemsPerPage; browser default 25, politeness cap 200)")

    f28 = v.add_parser("rxnav_rxcui_atc", parents=[g()],
                      help="RxCUI→ATC class (RxNav property.json?propName=ATC)",
                      description="RxCUI → ATC classification (numeric RxCUI only; resolve names first via rxnav_rxcui_by_name)")
    f28.add_argument("--rxcui", required=True, help="Numeric RxCUI (upstream param: rxcui)")

    f29 = v.add_parser("rxnav_rxcui_by_name", parents=[g()],
                      help="Drug name→RxCUI card (RxNav rxcuiByName)",
                      description="Identity normalization: drug/brand name → RxCUI (single-record face, no pagination)")
    f29.add_argument("--name", required=True, help="Drug or brand name (upstream param: name)")

    f30 = v.add_parser("safety_gate_alerts", parents=[g()],
                       help="EU Safety Gate weekly-report index (one XML, 2005→now)",
                       description="The ex-RAPEX rapid-alert system's weekly-report index: 1,122 reports with report_id join keys; year is a local post-filter (the upstream always serves the whole index)")
    f30.add_argument("--year", default=None, help="Report year, a local post-filter (not an upstream param; e.g. 2026)")
    f30.add_argument("--limit", type=int, default=200, help="Rows to return (local post-slice over the single cached index)")
    f30.add_argument("--skip", type=int, default=0, help="Rows to skip (local post-slice)")

    f31 = v.add_parser("safety_gate_report", parents=[g()],
                       help="EU Safety Gate one weekly report's alerts (detail XML)",
                       description="A single weekly report's alert rows: case number / product / risk type / level / notifying country / country of origin / online trader — the company-relevant edges of the non-food product-safety regime")
    f31.add_argument("--report-id", dest="report_id", required=True, help="Numeric report id (the report_id field echoed by safety_gate_alerts; e.g. 10000329 — a pasted detail URL also works)")
    f31.add_argument("--limit", type=int, default=200, help="Rows to return (local post-slice)")
    f31.add_argument("--skip", type=int, default=0, help="Rows to skip (local post-slice)")

    # —— Wave 10 openFDA family, four faces (2026-10-28; born flat: upstream param original names only, zero sugar, zero deprecation debt) ——

FLAT = {
    "au_tga_artg": lambda a: {"query": a.query, "limit": a.limit, "skip": a.skip},
    "au_tga_manufacturers": lambda a: {"state": a.state, "limit": a.limit},
    # 0.3.19 CA + EU product-safety faces (born flat: upstream params verbatim + closed-set validation; local post-slices marked)
    "ca_dpd_companies": lambda a: {"limit": a.limit, "skip": a.skip},
    "ca_dpd_drug_products": lambda a: {"status": a.status, "limit": a.limit, "skip": a.skip},
    "ca_mdall_companies": lambda a: {"limit": a.limit, "skip": a.skip},
    "ca_mdall_licence": lambda a: {"licence_id": a.licence_id, "licence_type": a.licence_type,
                                   "lang": a.lang},
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
    # 0.3.16 UK MHRA safety-alert twin faces (gov.uk search/content API; upstream param names verbatim + our polite tier)
    "gb_mhra_alert": lambda a: {"slug": a.slug},
    "gb_mhra_alerts": lambda a: {"q": a.q, "count": a.count, "start": a.start},
    "gudid_devices": lambda a: {"di": a.di, "udi": a.udi, "record_key": a.record_key},
    "mesh_descriptor": lambda a: {"label": a.label, "match": a.match, "limit": a.limit},
    "rasff_notifications": lambda a: {"subject": a.subject, "notification_reference": a.notification_reference,
                                      "ec_valid_date_from": a.ec_valid_date_from, "ec_valid_date_to": a.ec_valid_date_to,
                                      "page_number": a.page_number, "items_per_page": a.items_per_page},
    "rxnav_rxcui_atc": lambda a: {"rxcui": a.rxcui},
    "rxnav_rxcui_by_name": lambda a: {"name": a.name},
    "safety_gate_alerts": lambda a: {"year": a.year, "limit": a.limit, "skip": a.skip},
    "safety_gate_report": lambda a: {"report_id": a.report_id, "limit": a.limit, "skip": a.skip},
    # Wave 10 openFDA family, four faces (born flat: upstream param names passed through, no sugar keys)
}


# 0.3.10 jurisdiction chapter: face → jurisdiction (default = the issuing authority's jurisdiction; bodies
# covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2 + EU + GLOBAL) — merged into _JURISDICTION by the root cli.py; success envelopes carry the jurisdiction chapter
COUNTRY = {
    "au_tga_artg": "AU",
    "au_tga_manufacturers": "AU",
    "ca_dpd_companies": "CA",
    "ca_dpd_drug_products": "CA",
    "ca_mdall_companies": "CA",
    "ca_mdall_licence": "CA",
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
    "gb_mhra_alert": "GB",
    "gb_mhra_alerts": "GB",
    "gudid_devices": "US",
    "mesh_descriptor": "GLOBAL",
    "rasff_notifications": "EU",
    "rxnav_rxcui_atc": "US",
    "rxnav_rxcui_by_name": "US",
    "safety_gate_alerts": "EU",
    "safety_gate_report": "EU",
}
