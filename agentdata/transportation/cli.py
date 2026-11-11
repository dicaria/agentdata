"""transportation cli — domain command face registration (0.3.54 founding: the seven migrated
faces registered verbatim from their esg/company homes + the CA TC CCAR pair; purely flat).

register(v, g): registers flat commands on the domain subparser (g = the root _leaf_globals factory,
passed in as a parameter to avoid a cli ↔ domain-cli cycle); FLAT = the flat dispatch table, merged by the root cli for main to use.
"""
import argparse

def register(v, g):
    # —— 0.3.54 CA TC CCAR live search + per-aircraft record (dictionary head: ca_ccar_* < euasl; registration order == FLAT order) ——
    f1 = v.add_parser("ca_ccar_aircraft", parents=[g()],
                      help="Canadian civil aircraft record by ADet id (Transport Canada CCAR; keyless)",
                      description="The CCAR per-aircraft record (ADet.aspx?id=): four blocks — aircraft "
                                  "(mark/model/serial/category/engine/MTOW/24-bit address/eligibility "
                                  "basis/base of operations), manufacturer (name/country/year), "
                                  "registration (type/owner-since/latest certificate) and the registered "
                                  "owner (name/address/city/postal code) — flattened into one dict; "
                                  "labels outside the mapped vocabulary ride along snake_cased under "
                                  "extra_fields (never dropped, never guessed). The ~500k ADet id space "
                                  "has holes — a not-found id is a legal empty; take ids from "
                                  "ca_ccar_search rows, never guess. Owner name+address are returned "
                                  "verbatim from the public register (public-register precedent: "
                                  "us_fmcsa company_officer_1/2); nothing is enriched on top.")
    f1.add_argument("--id", dest="adet_id", required=True, help="Numeric ADet id (from ca_ccar_search rows, e.g. 538042)")

    f2 = v.add_parser("ca_ccar_search", parents=[g()],
                      help="Canadian civil aircraft register search (Transport Canada CCAR; keyless)",
                      description="The Canadian Civil Aircraft Register (CCARCS-RIACC) contains-search: "
                                  "owner/mark/common-name/model/serial criteria (at least one required, "
                                  "combined = AND), every match a CONTAINS match (the search form's "
                                  "'Anywhere' mode — the Ending/Exact/Beginning modes never surface in "
                                  "the result URL). Measured shape: the POST form 302-redirects to a "
                                  "stateless pipe-wrapped GET (RchSimpRes.aspx?on=|owner|&m=|mark|&…), "
                                  "and print=y carries the WHOLE result set in one page (269 rows for an "
                                  "AIR CANADA anywhere-match, 365KB; the interactive page shows 10/page "
                                  "with no pager links) — no ViewState, no cookies, no paging. Rows: "
                                  "mark/common_name/model_name/serial_number/owner/owner_registered_since "
                                  "+ adet_id (the per-aircraft detail key for ca_ccar_aircraft). "
                                  "Politeness cap 200 rows; total_matched always carries the true count.")
    f2.add_argument("--owner", default=None, help="Owner name substring (upstream slot on=|value|, contains-match)")
    f2.add_argument("--mark", default=None, help="Registration mark substring, e.g. C-F (upstream slot m=|value|)")
    f2.add_argument("--common-name", dest="common_name", default=None, help="Manufacturer common name substring, e.g. Airbus (upstream slot cn=|value|)")
    f2.add_argument("--model-name", dest="model_name", default=None, help="Model name substring, e.g. A321 (upstream slot mn=|value|)")
    f2.add_argument("--serial-number", dest="serial_number", default=None, help="Serial number substring (upstream slot sn=|value|)")
    f2.add_argument("--limit", type=int, default=200, help="Rows (local payload wall 1-500, default 200; total_matched carries the true count)")

    # —— 0.3.22 transport-compliance axis, migrated verbatim from esg at the 0.3.54 founding ——
    f6 = v.add_parser("euasl_datasets", parents=[g()],
                      help="EU Air Safety List download catalog (banned/restricted air carriers)",
                      description="EU Air Safety List official download catalog (keyless): one call returns all files — the machine-readable XLSX master (Annex A = carriers under an operating ban, Annex B = restrictions/conditions) + 24 official-language PDF renditions; the document UUIDs rotate on every republication (reconcile against this listing, never guess file names); zero params upstream; the binary bodies go through the batch pipeline, this face gives coordinates")
    # Upstream takes zero params: no flags (the catalog ships in one shot; clients pick the xlsx master row)

    # —— 0.3.5 port-state emissions/supervision axis, migrated verbatim from esg at the 0.3.54 founding ——
    # esg 0.3.5 port-state emissions/supervision axis (thetis_mrv + paris_mou; upstream param names mirrored) — folded in and seated lexicographically in 0.3.10
    f8 = v.add_parser("paris_mou_bans", parents=[g()],
                      help="Paris MoU banned ships register",
                      description="Paris MoU banned-ships register (keyless): ban date/occurrence/order status/reason/minimum duration/banning authority, with the embedded ISM company flattened to row keys — the official ship x management-company edge (~2/3 of rows carry a company IMO number); zero params upstream")
    # Upstream takes zero params: no flags (the bans list ships in one shot)

    f9 = v.add_parser("paris_mou_detentions", parents=[g()],
                      help="Paris MoU current detentions snapshot",
                      description="Paris MoU (Atlantic/European port state control) currently-detained ships snapshot (keyless): daily-rolling live state — ship IMO number (asset key), detention port+country, reporting authority; historical detentions go through paris_mou_inspections window search; zero params upstream")
    # Upstream takes zero params: no flags (the same-day snapshot ships in one shot)

    f10 = v.add_parser("paris_mou_inspections", parents=[g()],
                      help="Paris MoU historical PSC inspection window search",
                      description="Paris MoU historical port state control inspections (THETIS form-encoded POST, keyless): period_min/period_max are dd/mm/yyyy STRICT (upstream native order day/month/year — wrong order silently returns zero) and the window must be <= 3 years (enforced locally, upstream silently empties beyond); page is the paging switch — the face always sends it (without page upstream ignores limit and dumps the whole window); page+start+limit = start-offset paging (page 1/2 verified zero overlap); ism_company_imo_number / ism_company_name filter straight to the management company (resume window stats ships/inspections/detentions/ISM deficiencies ride along); psc_inspection_regime upstream-verbatim (1 = PSC default regime, only verified value; omitted = upstream 200 empty); zero rows in window = legal empty")
    f10.add_argument("--period-min", dest="period_min", required=True,
                    help="Window start dd/mm/yyyy (upstream param periodMin; STRICT day-first)")
    f10.add_argument("--period-max", dest="period_max", required=True,
                    help="Window end dd/mm/yyyy (upstream param periodMax; window <= 3 years)")
    f10.add_argument("--psc-inspection-regime", dest="psc_inspection_regime", type=int, default=1,
                    help="Inspection regime (upstream param pscInspectionRegime; 1 = PSC default, only verified value)")
    f10.add_argument("--page", type=int, default=1,
                    help="Page number (upstream param page; the paging switch — always sent by this face)")
    f10.add_argument("--start", type=int, default=0,
                    help="Row offset within page (upstream param start; page+start+limit paging)")
    f10.add_argument("--limit", type=int, default=50, help="Rows (politeness cap 500)")
    f10.add_argument("--ism-company-name", dest="ism_company_name", default=None,
                    help="ISM management company name filter (upstream param ismCompanyName)")
    f10.add_argument("--ism-company-imo-number", dest="ism_company_imo_number", default=None,
                    help="ISM company IMO number filter, 7-digit zero-padded (upstream param ismCompanyImoNumber, e.g. 0052193)")

    f11 = v.add_parser("paris_mou_low_performance_companies", parents=[g()],
                       help="Paris MoU low-performance ISM companies",
                       description="Paris MoU low-performance ISM company list (rolling 6-month window, keyless): each row carries an IMO company number (7-digit zero-padded official string), with address/country/performance level (LOW dominant, some MEDIUM)/listing dates — company-risk attribute list; zero params upstream")
    # Upstream takes zero params: no flags (the rolling-window list ships in one shot)

    f12 = v.add_parser("thetis_mrv_datasets", parents=[g()],
                       help="EU shipping MRV emission-report file catalog (THETIS-MRV)",
                       description="THETIS-MRV versioned bulk-file catalog (keyless): reporting periods (2018+) x versioned regenerated XLSX publications (versions roll — reconcile by this list, never guess filenames; generation timestamps are early-morning batch runs); download_path template is served for the batch pipeline, this face gives coordinates; zero params upstream")
    # Upstream takes zero params: no flags (reporting-period × version ledger composed; clients filter rows themselves)

    # —— 0.3.51 US FMCSA carrier census, migrated verbatim from company at the 0.3.54 founding ——
    # —— 0.3.51 US FMCSA carrier census (dictionary slot: us_fmcsa between tx_tdlr and usaspending — '_'<'a'; registration order == FLAT order) ——
    f_fm = v.add_parser("us_fmcsa_carriers", parents=[g()],
                        help="US FMCSA carrier census (data.transportation.gov Socrata az4n-8mr2; keyless)",
                        description="The full-history US motor carrier universe — active AND "
                                    "out-of-service, 4,528,322 rows live 2026-11-09 (the ~400k audit "
                                    "figure was the active face). dot_number hard key (the "
                                    "transport-compliance join key), status_code lifecycle (A active), "
                                    "dun_bradstreet_no = the rare official DUNS cross-key (mind its "
                                    "'0' sentinels), phy_*/carrier_mailing_* dual address blocks, "
                                    "company_officer_1/2 verbatim (public-register precedent), fleet "
                                    "trio truck/power/bus units + mcs150 mileage + hm_ind hazmat + "
                                    "crgo_* cargo flags + classdef; email_address present on some "
                                    "rows. Catalog advertises ~58 columns but Socrata omits null "
                                    "fields per row — a populated row ships 53 keys; unrated carriers "
                                    "simply lack safety_rating (rides in the view, appears only when "
                                    "set). Walk-away: sibling 4a2k-zf79 is a 403 dead single-dataset "
                                    "— az4n is the live set. SoQL verbatim channel — no total echo, "
                                    "none faked. Deterministic forms: dot_number='963305' exact; "
                                    "upper(legal_name) like '%SCHNEIDER%' (3 rows live)")
    f_fm.add_argument("--where", default=None,
                      help="Raw SoQL filter (upstream param: $where; e.g. \"dot_number='963305'\" or \"upper(legal_name) like '%%SCHNEIDER%%'\")")  # %% escaping: argparse help goes through % interpolation
    f_fm.add_argument("--limit", type=int, default=20,
                      help="Rows to return (upstream param: $limit; 1-500 politeness cap, default 20)")
    f_fm.add_argument("--offset", type=int, default=0,
                      help="Row offset (upstream param: $offset; >=0 — Socrata deep-offset friendly)")
    f_fm.add_argument("--order", default=None,
                      help="Sort column [ASC|DESC] (upstream param: $order; rejects NULLS — e.g. dot_number DESC)")

FLAT = {
    # 0.3.54 CA TC CCAR (dictionary head)
    "ca_ccar_aircraft": lambda a: {"adet_id": a.adet_id},
    "ca_ccar_search": lambda a: {"owner": a.owner, "mark": a.mark,
                                 "common_name": a.common_name, "model_name": a.model_name,
                                 "serial_number": a.serial_number, "limit": a.limit},
    "euasl_datasets": lambda a: {},  # upstream zero params (download catalog in one shot; 0.3.22)
    # 0.3.5 port-state emissions/supervision axis (migrated from esg 0.3.54)
    # esg 0.3.5 port-state emissions/supervision axis (thetis_mrv + paris_mou; upstream param names mirrored)
    "paris_mou_bans": lambda a: {},        # upstream zero params (bans list in one shot)
    "paris_mou_detentions": lambda a: {},  # upstream zero params (same-day snapshot in one shot)
    "paris_mou_inspections": lambda a: {"period_min": a.period_min,
                                        "period_max": a.period_max,
                                        "psc_inspection_regime": a.psc_inspection_regime,
                                        "page": a.page, "start": a.start, "limit": a.limit,
                                        "ism_company_name": a.ism_company_name,
                                        "ism_company_imo_number": a.ism_company_imo_number},
    "paris_mou_low_performance_companies": lambda a: {},  # upstream zero params (rolling-window list in one shot)
    "thetis_mrv_datasets": lambda a: {},  # upstream zero params (reporting-period × version ledger composed)
    # 0.3.51 US FMCSA carrier census (migrated from company 0.3.54)
    "us_fmcsa_carriers": lambda a: {"where": a.where, "limit": a.limit, "offset": a.offset,
                                    "order": a.order},
}


# 0.3.10 jurisdiction chapter: face → jurisdiction (default = the issuing authority's jurisdiction; bodies
# covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2 + EU + GLOBAL) — merged into _JURISDICTION by the root cli.py
COUNTRY = {
    # 0.3.54 CA TC CCAR (dictionary head)
    "ca_ccar_aircraft": "CA",
    "ca_ccar_search": "CA",
    "euasl_datasets": "EU",
    "paris_mou_bans": "GLOBAL",
    "paris_mou_detentions": "GLOBAL",
    "paris_mou_inspections": "GLOBAL",
    "paris_mou_low_performance_companies": "GLOBAL",
    "thetis_mrv_datasets": "EU",
    "us_fmcsa_carriers": "US",
}
