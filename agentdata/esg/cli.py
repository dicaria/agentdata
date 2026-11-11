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
                      description="EPA FRS facility registry point query: seven filter columns upstream-verbatim (registry_id / primary_name / state_code / city_name + the 0.3.20 audit trio country_name / site_type_name / epa_region_code — ALL exact '=' match, combinable = AND; the upstream contains/~ operators silently return 0, fuzzy facility names go through ECHO; country_name unlocks the non-US facility slice, GERMANY=110 measured) + start/size paging (ROWS closed interval start:end, computed locally — an omitted/inverted ROWS segment makes the upstream dump the whole table); at least one filter required (bare 5.6M-row scan walled politely, batch pipeline serves that); each call = rows + count (total_matches)")
    f5.add_argument("--registry-id", dest="registry_id", default=None,
                    help="FRS Registry ID — authoritative facility key (ECHO/TRI/GHGRP join anchor)")
    f5.add_argument("--primary-name", dest="primary_name", default=None,
                    help="Facility primary name — EXACT match incl. spaces (contains/~ operators return 0 upstream)")
    f5.add_argument("--state-code", dest="state_code", default=None,
                    help="State code, 2-letter (lowercase input uppercased locally, e.g. DE)")
    f5.add_argument("--city-name", dest="city_name", default=None, help="City name (exact)")
    f5.add_argument("--country-name", dest="country_name", default=None,
                    help="Country name (exact uppercase form, lowercase input uppercased locally — GERMANY=110 / "
                         "UNITED STATES=3,129,491 measured; the non-US facility slice)")
    f5.add_argument("--site-type-name", dest="site_type_name", default=None,
                    help="Site type (exact uppercase, e.g. STATIONARY — 4,725,914 of 5,602,878 measured)")
    f5.add_argument("--epa-region-code", dest="epa_region_code", default=None,
                    help="EPA region (zero-padded two-digit string form '03'; region 10 = 214,197 measured)")
    f5.add_argument("--start", type=int, default=0, help="Paging offset (upstream ROWS start, closed interval)")
    f5.add_argument("--size", type=int, default=50, help="Rows (politeness cap 500)")

    f7 = v.add_parser("eutl_datasets", parents=[g()],
                      help="EU carbon registry bulk-download catalog (EUTL)",
                      description="EUTL official bulk-download catalog (keyless): one call returns all datasets — Azure daily extracts (accounts/operators/holdings csv.gz) + climate.ec.europa.eu yearly files (compliance/verified emissions 2021-2025); zero params upstream; file downloads themselves go through the batch pipeline, this face gives coordinates")
    # Upstream takes zero params: no flags (the catalog ships in one shot; clients filter rows themselves)

    # —— 0.3.53 UK FHRS food-hygiene live search (dictionary slot: thetis_mrv_* < uk_fhrs — tail; registration order == FLAT order) ——
    f13 = v.add_parser("uk_fhrs_establishments", parents=[g()],
                       help="UK food-hygiene establishment search (FSA FHRS/FHIS; keyless x-api-version 2)",
                       description="~615,098 rated establishments live 2026-11-10 — England/Wales/NI "
                                   "0-5 ratings plus the Scottish Pass/FHIS scheme, daily refresh. "
                                   "FHRSID is the hard key; the company join is BusinessName+PostCode "
                                   "(weak — no CH number rides the register). Rows carry 26 fields: "
                                   "address+PostCode, geocode, the three sub-scores, "
                                   "RatingValue/Key/Date, RightToReply, SchemeType. Wall (measured "
                                   "live): the postcode= query param answers 403 on this endpoint — "
                                   "postcode is NOT a query parameter here (the PostCode field rides "
                                   "every row, filter locally). Rides the fast ElasticSearch endpoint, "
                                   "not the slow legacy basic pager.")
    f13.add_argument("--name", default=None,
                     help="Business-name substring (upstream param: name; e.g. pret → 806 hits)")
    f13.add_argument("--address", default=None,
                     help="Address substring (upstream param: address; e.g. Oxford → 2,935)")
    f13.add_argument("--rating-key", dest="rating_key", default=None,
                     help="Rating key (upstream param: ratingKey; the scheme's own vocabulary, e.g. fhrs_5_en-gb, fhis_pass_en-gb)")
    f13.add_argument("--local-authority-id", dest="local_authority_id", default=None,
                     help="FSA numeric authority id (upstream param: localAuthorityId; e.g. 131)")
    f13.add_argument("--page", type=int, default=1,
                     help="Page, 1-based (upstream param: page; totalPages echoes for arithmetic)")
    f13.add_argument("--pagesize", type=int, default=20,
                     help="Rows per page (upstream param: pagesize; 1-200 politeness cap — upstream tolerates 1000, default 20)")

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
                                     "country_name": a.country_name, "site_type_name": a.site_type_name,
                                     "epa_region_code": a.epa_region_code,
                                     "start": a.start, "size": a.size},
    "eutl_datasets": lambda a: {},  # upstream zero params (catalog in one shot)
    # 0.3.53 UK FHRS food-hygiene live search (tail slot after the 0.3.54 transportation migration)
    "uk_fhrs_establishments": lambda a: {"name": a.name, "address": a.address,
                                         "rating_key": a.rating_key,
                                         "local_authority_id": a.local_authority_id,
                                         "page": a.page, "pagesize": a.pagesize},
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
    # 0.3.53 UK FHRS food-hygiene live search (tail slot after the 0.3.54 transportation migration)
    "uk_fhrs_establishments": "GB",
}
