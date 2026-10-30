"""esg cli — domain command face registration (split per domain in 0.2.6, moved in from the root cli.py; purely flat since the 0.3.0 verb-layer removal).

register(v, g): registers flat commands on the domain subparser (g = the root _leaf_globals factory,
passed in as a parameter to avoid a cli ↔ domain-cli cycle); FLAT = the flat dispatch table, merged by the root cli for main to use.
"""
import argparse

def register(v, g):
    f1 = v.add_parser("climatetrace_owners", parents=[g()],
                      help="Emissions-owner candidates (Climate TRACE v7 owners)",
                      description="Climate TRACE emissions-owner candidates: name/limit/offset upstream-verbatim; zero hit = legal empty (upstream 404 JSON mapped); ordering is NOT stable across limits — fetch enough in one go")
    f1.add_argument("--name", required=True, help="Owner name to search (upstream param: name)")
    f1.add_argument("--limit", type=int, default=10, help="Rows (upstream param: limit; politeness cap 50 — upstream tested to 1000)")
    f1.add_argument("--offset", type=int, default=None, help="Skip rows (upstream param: offset; ordering unstable — prefer one large fetch)")

    f2 = v.add_parser("climatetrace_sources", parents=[g()],
                      help="Facility-level GHG sources by owner/filter (Climate TRACE v7)",
                      description="Climate TRACE owner/filter→facility/aggregate emission sources: owner_ids→ownerIds (comma-joined = union & dedup, tested; repeated param = upstream silently first-wins, do not use) XOR --owner-name sugar (resolves first candidate); year no local wall (out-of-window year → upstream null, 2021+ has data); gas verbatim — non-co2e gas switches row key to emissions_quantity (native unit); 0.2.9 audit additions: offset paging, sectors closed-set validated locally (invalid values silently return the WHOLE corpus upstream), subsectors passthrough (upstream 400 self-describes), location family gadm_id/city_id/country_group/continent passthrough (upstream 400 enforces one-at-a-time); owner_ids or at least one filter required (bare corpus scan walled politely)")
    f2.add_argument("--owner-ids", dest="owner_ids", default=None,
                    help="Owner id(s), upstream param ownerIds — E100000001492 or comma-joined for union")
    f2.add_argument("--owner-name", dest="owner_name", default=None,
                    help="Sugar — resolves first owners candidate (XOR with --owner-ids)")
    f2.add_argument("--year", type=int, default=None, help="Emissions year (upstream param: year; default=current year; data window 2021+)")
    f2.add_argument("--gas", default=None, help="Gas (upstream param: gas; default co2e_100yr = tCO2e)")
    f2.add_argument("--limit", type=int, default=50, help="Rows (upstream param: limit; politeness cap 500)")
    f2.add_argument("--offset", type=int, default=None,
                    help="Skip rows (upstream param: offset; real paging tested 2026-10-28 — ordering unstable across limits, prefer one big fetch)")
    f2.add_argument("--sectors", default=None,
                    help="Sector slug, closed set validated locally: agriculture/buildings/fluorinated-gases/forestry-and-land-use/fossil-fuel-operations/manufacturing/mineral-extraction/power/transportation/waste + special all_no_forest (invalid values silently return the whole corpus upstream)")
    f2.add_argument("--subsectors", default=None,
                    help="Subsector slug(s) passthrough (68 values, GET /v7/definitions/subsectors; invalid value → upstream 400 'invalid subsector provided', self-describing)")
    f2.add_argument("--gadm-id", dest="gadm_id", default=None, help="GADM region id (upstream param: gadmId)")
    f2.add_argument("--city-id", dest="city_id", default=None, help="Metro area id (upstream param: cityId)")
    f2.add_argument("--country-group", dest="country_group", default=None,
                    help="Country-group slug, upstream param countryGroup — e.g. eu/aosis/g20 (values from GET /v7/definitions/countrygroups)")
    f2.add_argument("--continent", default=None,
                    help="Continent name (upstream param: continent; tested Europe/Asia 2026-10-28 — RUS counts as Europe)")

    f3 = v.add_parser("eiti_companies", parents=[g()],
                      help="Extractives filing companies (EITI Datasette; name candidates)",
                      description="EITI extractives filing-company candidates: company_name__like is the upstream Datasette magic param verbatim (%/_ metachars yours to manage); --name sugar wraps %contains% (same slot, XOR); zero hit = legal empty")
    f3.add_argument("--company-name__like", dest="company_name__like", default=None,
                    help="Upstream param verbatim (SQL LIKE; %%/_ metachars passthrough)")
    f3.add_argument("--name", default=None, help="Company name — sugar for company_name__like=%%name%% (same slot, XOR with --company-name__like)")
    f3.add_argument("--size", type=int, default=10, help="Rows (upstream param: _size; politeness cap 1000 — upstream tested to 11000+)")

    f4 = v.add_parser("eiti_payments", parents=[g()],
                      help="Company→government payment lines (EITI; GFS-classified)",
                      description="EITI company→government payment lines: id channel (eiti_id_company__exact verbatim XOR --eiti-id sugar adding the eiti_id_company: prefix) + name channel (company_name__like verbatim XOR --name sugar); channels may combine; at least one required (bare scan walled locally)")
    f4.add_argument("--eiti-id-company__exact", dest="eiti_id_company__exact", default=None,
                    help="Upstream param verbatim — full value incl. eiti_id_company: prefix")
    f4.add_argument("--eiti-id", dest="eiti_id", default=None,
                    help="Sugar — bare UUID, prefix auto-added (same slot, XOR with --eiti-id-company__exact)")
    f4.add_argument("--company-name__like", dest="company_name__like", default=None,
                    help="Upstream param verbatim (SQL LIKE)")
    f4.add_argument("--name", default=None, help="Sugar — %%contains%% (same slot, XOR with --company-name__like)")
    f4.add_argument("--size", type=int, default=50, help="Rows (upstream param: _size; politeness cap 1000)")

    f5 = v.add_parser("epa_frs_facilities", parents=[g()],
                      help="EPA facility master lookup (FRS frs_facility_site)",
                      description="EPA FRS facility registry point query: four filter columns upstream-verbatim (registry_id / primary_name / state_code / city_name — ALL exact '=' match, combinable = AND; the upstream contains/~ operators silently return 0, fuzzy facility names go through ECHO) + start/size paging (ROWS closed interval start:end, computed locally — an omitted/inverted ROWS segment makes the upstream dump the whole table); at least one filter required (bare 5.6M-row scan walled politely, batch pipeline serves that); each call = rows + count (total_matches)")
    f5.add_argument("--registry-id", dest="registry_id", default=None,
                    help="FRS Registry ID — authoritative facility key (ECHO/TRI/GHGRP join anchor)")
    f5.add_argument("--primary-name", dest="primary_name", default=None,
                    help="Facility primary name — EXACT match incl. spaces (contains/~ operators return 0 upstream)")
    f5.add_argument("--state-code", dest="state_code", default=None,
                    help="State code, 2-letter (lowercase input uppercased locally, e.g. DE)")
    f5.add_argument("--city-name", dest="city_name", default=None, help="City name (exact)")
    f5.add_argument("--start", type=int, default=0, help="Paging offset (upstream ROWS start, closed interval)")
    f5.add_argument("--size", type=int, default=50, help="Rows (politeness cap 500)")

    f6 = v.add_parser("eutl_datasets", parents=[g()],
                      help="EU carbon registry bulk-download catalog (EUTL)",
                      description="EUTL official bulk-download catalog (keyless): one call returns all datasets — Azure daily extracts (accounts/operators/holdings csv.gz) + climate.ec.europa.eu yearly files (compliance/verified emissions 2021-2025); zero params upstream; file downloads themselves go through the batch pipeline, this face gives coordinates")
    # Upstream takes zero params: no flags (the catalog ships in one shot; clients filter rows themselves)

    # esg 0.3.5 port-state emissions/supervision axis (thetis_mrv + paris_mou; upstream param names mirrored) — folded in and seated lexicographically in 0.3.10
    f7 = v.add_parser("paris_mou_bans", parents=[g()],
                      help="Paris MoU banned ships register",
                      description="Paris MoU banned-ships register (keyless): ban date/occurrence/order status/reason/minimum duration/banning authority, with the embedded ISM company flattened to row keys — the official ship x management-company edge (~2/3 of rows carry a company IMO number); zero params upstream")
    # Upstream takes zero params: no flags (the bans list ships in one shot)

    f8 = v.add_parser("paris_mou_detentions", parents=[g()],
                      help="Paris MoU current detentions snapshot",
                      description="Paris MoU (Atlantic/European port state control) currently-detained ships snapshot (keyless): daily-rolling live state — ship IMO number (asset key), detention port+country, reporting authority; historical detentions go through paris_mou_inspections window search; zero params upstream")
    # Upstream takes zero params: no flags (the same-day snapshot ships in one shot)

    f9 = v.add_parser("paris_mou_inspections", parents=[g()],
                      help="Paris MoU historical PSC inspection window search",
                      description="Paris MoU historical port state control inspections (THETIS form-encoded POST, keyless): period_min/period_max are dd/mm/yyyy STRICT (upstream native order day/month/year — wrong order silently returns zero) and the window must be <= 3 years (enforced locally, upstream silently empties beyond); page is the paging switch — the face always sends it (without page upstream ignores limit and dumps the whole window); page+start+limit = start-offset paging (page 1/2 verified zero overlap); ism_company_imo_number / ism_company_name filter straight to the management company (resume window stats ships/inspections/detentions/ISM deficiencies ride along); psc_inspection_regime upstream-verbatim (1 = PSC default regime, only verified value; omitted = upstream 200 empty); zero rows in window = legal empty")
    f9.add_argument("--period-min", dest="period_min", required=True,
                    help="Window start dd/mm/yyyy (upstream param periodMin; STRICT day-first)")
    f9.add_argument("--period-max", dest="period_max", required=True,
                    help="Window end dd/mm/yyyy (upstream param periodMax; window <= 3 years)")
    f9.add_argument("--psc-inspection-regime", dest="psc_inspection_regime", type=int, default=1,
                    help="Inspection regime (upstream param pscInspectionRegime; 1 = PSC default, only verified value)")
    f9.add_argument("--page", type=int, default=1,
                    help="Page number (upstream param page; the paging switch — always sent by this face)")
    f9.add_argument("--start", type=int, default=0,
                    help="Row offset within page (upstream param start; page+start+limit paging)")
    f9.add_argument("--limit", type=int, default=50, help="Rows (politeness cap 500)")
    f9.add_argument("--ism-company-name", dest="ism_company_name", default=None,
                    help="ISM management company name filter (upstream param ismCompanyName)")
    f9.add_argument("--ism-company-imo-number", dest="ism_company_imo_number", default=None,
                    help="ISM company IMO number filter, 7-digit zero-padded (upstream param ismCompanyImoNumber, e.g. 0052193)")

    f10 = v.add_parser("paris_mou_low_performance_companies", parents=[g()],
                       help="Paris MoU low-performance ISM companies",
                       description="Paris MoU low-performance ISM company list (rolling 6-month window, keyless): each row carries an IMO company number (7-digit zero-padded official string), with address/country/performance level (LOW dominant, some MEDIUM)/listing dates — company-risk attribute list; zero params upstream")
    # Upstream takes zero params: no flags (the rolling-window list ships in one shot)

    f11 = v.add_parser("thetis_mrv_datasets", parents=[g()],
                       help="EU shipping MRV emission-report file catalog (THETIS-MRV)",
                       description="THETIS-MRV versioned bulk-file catalog (keyless): reporting periods (2018+) x versioned regenerated XLSX publications (versions roll — reconcile by this list, never guess filenames; generation timestamps are early-morning batch runs); download_path template is served for the batch pipeline, this face gives coordinates; zero params upstream")
    # Upstream takes zero params: no flags (reporting-period × version ledger composed; clients filter rows themselves)

FLAT = {
    # esg 0.2.0 flat panel (upstream params under original names + our defaults; the lambda only ferries names across namespaces)
    "climatetrace_owners": lambda a: {"name": a.name, "limit": a.limit, "offset": a.offset},
    "climatetrace_sources": lambda a: {"owner_ids": a.owner_ids, "owner_name": a.owner_name,
                                       "year": a.year, "gas": a.gas, "limit": a.limit,
                                       "offset": a.offset, "sectors": a.sectors,
                                       "subsectors": a.subsectors, "gadm_id": a.gadm_id,
                                       "city_id": a.city_id, "country_group": a.country_group,
                                       "continent": a.continent},
    "eiti_companies": lambda a: {"company_name__like": a.company_name__like,
                                 "name": a.name, "size": a.size},
    "eiti_payments": lambda a: {"eiti_id_company__exact": a.eiti_id_company__exact,
                                "eiti_id": a.eiti_id, "company_name__like": a.company_name__like,
                                "name": a.name, "size": a.size},
    "epa_frs_facilities": lambda a: {"registry_id": a.registry_id,
                                     "primary_name": a.primary_name,
                                     "state_code": a.state_code, "city_name": a.city_name,
                                     "start": a.start, "size": a.size},
    "eutl_datasets": lambda a: {},  # upstream zero params (catalog in one shot)
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
}


# 0.3.10 jurisdiction chapter: face → jurisdiction (default = the issuing authority's jurisdiction; bodies
# covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2 + EU + GLOBAL) — merged into _JURISDICTION by the root cli.py; success envelopes carry the jurisdiction chapter
COUNTRY = {
    "climatetrace_owners": "GLOBAL",
    "climatetrace_sources": "GLOBAL",
    "eiti_companies": "GLOBAL",
    "eiti_payments": "GLOBAL",
    "epa_frs_facilities": "US",
    "eutl_datasets": "EU",
    "paris_mou_bans": "GLOBAL",
    "paris_mou_detentions": "GLOBAL",
    "paris_mou_inspections": "GLOBAL",
    "paris_mou_low_performance_companies": "GLOBAL",
    "thetis_mrv_datasets": "EU",
}
