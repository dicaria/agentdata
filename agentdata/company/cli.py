"""company cli — domain command face registration (split per domain in 0.2.6, moved in from the root cli.py; purely flat since the 0.3.0 verb-layer + sugar removal).

register(v, g): registers flat commands on the domain subparser (g = the root _leaf_globals factory,
passed in as a parameter to avoid a cli ↔ domain-cli cycle); FLAT = the flat dispatch table, merged by the root cli for main to use.
"""
import argparse

def register(v, g):
    # —— Flat panel commands (company main face: source-qualified names + upstream params under original names + our defaults; the only face family since 0.3.0) ——
    f1 = v.add_parser("ch_zefix_firm", parents=[g()],
                       help="Swiss firm full profile by ehraid (Zefix /firm/{ehraid}.json)",
                       description="Zefix single record: purpose full text, oldNames history, hasTakenOver/takenOverBy M&A edges with ehraid/uid/chid cross-references (precedessor/successor)")
    f1.add_argument("--ehraid", required=True, help="Registry master id (upstream path param: ehraid; from search rows)")
    # —— 0.3.3 European country registry realtime faces (CH Zefix / NO Brreg / FI YTJ) ——
    f2 = v.add_parser("ch_zefix_firm_search", parents=[g()],
                       help="Swiss commercial register name search (Zefix POST search.json)",
                       description="Zefix firm search: name contains-match (hits historical names too); three registry keys (ehraid/uid/chid) per row; maxEntries/offset honored upstream (echoed back)")
    f2.add_argument("--name", required=True, help="Company name (upstream param: name; contains-match, non-authoritative)")
    f2.add_argument("--max-entries", dest="max_entries", type=int, default=100,
                     help="Rows per page (upstream param: maxEntries; honored upstream; 1-100 our politeness cap)")
    f2.add_argument("--offset", type=int, default=0, help="Offset (upstream param: offset; walk with --offset, cap ~540k upstream maxOffset)")
    f3 = v.add_parser("fdic_institutions", parents=[g()],
                      help="US insured-bank master record (FDIC BankFind; --search/--filters raw channels)",
                      description="FDIC institutions: ES search × structured filters are combinable raw channels (search 'NAME:\"…\"' / filters 'CERT:n'); no upstream limit wall (10,000 verified)")
    f3.add_argument("--search", default=None, help="ES full-text (upstream param: search; e.g. 'NAME:\"First National\" AND ST:TX')")
    f3.add_argument("--filters", default=None, help="Structured filter (upstream param: filters; e.g. 'CERT:628' or 'ST:TX AND CITY:Dallas')")
    f3.add_argument("--limit", type=int, default=5, help="Rows to return (upstream param: limit; no wall verified ≤10000, default 5)")
    f4 = v.add_parser("fi_ytj_companies", parents=[g()],
                       help="Finnish business register records (PRH YTJ v3; --name search XOR --business-id direct)",
                       description="YTJ v3 companies: name contains-match hits historical/branch names; businessId direct lookup; pagination params are silently ignored upstream — fixed ~63-row pages, totalResults is the real total")
    f4.add_argument("--name", default=None, help="Company name (upstream param: name; contains-match incl. historical names)")
    f4.add_argument("--business-id", dest="business_id", default=None,
                     help="Business id, 0194099-3 form (upstream param: businessId; spaces ok)")
    # —— 0.3.4 FR annuaire realtime search face (recherche-entreprises) ——
    # —— 0.3.4 FR annuaire realtime search face (recherche-entreprises) ——
    f5 = v.add_parser("fr_recherche_search", parents=[g()],
                       help="French registry aggregate search (annuaire-entreprises; --q name/officer-name/SIREN)",
                       description="etalab recherche-entreprises: one q for company name, officer name (cross-company mandate search) or SIREN direct lookup; rich rows with dirigeants (person + corporate slots), finances, tva; etat_administratif A=active/C=ceased true filter")
    f5.add_argument("--q", required=True,
                     help="Query: company name / officer name / SIREN (upstream param: q; name search hits historical names, officer names give cross-company mandates)")
    f5.add_argument("--page", type=int, default=None, help="Page, 1-based (upstream param: page; walk while page<=total_pages)")
    f5.add_argument("--per-page", dest="per_page", type=int, default=10,
                     help="Rows per page (upstream param: per_page; hard wall 1-25 upstream-verified, default 10)")
    f5.add_argument("--etat-administratif", dest="etat_administratif", default=None,
                     help="Lifecycle filter (upstream param: etat_administratif; A=active, C=ceased — true filter, ceased rows carry date_fermeture)")
    f6 = v.add_parser("gb_contracts_finder_published_notices", parents=[g()],
                       help="UK below-threshold contracts (Contracts Finder OCDS; bare dates legal here)",
                       description="Sub-threshold UK contracts: publishedFrom/publishedTo are bare dates (opposite of FTS); no window → our rolling 7-day default (upstream returns empty without one); --stages filters tender|award (upstream 400 self-validates); --name = client-side contains filter")
    f6.add_argument("--name", default=None, help="Company name — client-side contains filter (no upstream name-search param exists)")
    f6.add_argument("--stages", default=None,
                     help="OCDS stage filter (upstream param: stages; tender|award — invalid → upstream 400 self-describing; absent = mixed feed; 0.2.9 audit)")
    f6.add_argument("--published-from", dest="published_from", default=None,
                     help="Window start YYYY-MM-DD, bare (upstream param: publishedFrom; default 7 days back)")
    f6.add_argument("--published-to", dest="published_to", default=None,
                     help="Window end YYYY-MM-DD, bare (upstream param: publishedTo; default today)")
    f6.add_argument("--limit", type=int, default=10, help="Rows (upstream param: limit; 1-100; with --name = matches cap, fetch stays 100)")
    f6.add_argument("--cursor", default=None, help="Pagination cursor (upstream param: cursor; pass the same window when walking)")
    f7 = v.add_parser("gb_fts_release_packages", parents=[g()],
                       help="UK above-threshold tenders (Find a Tender OCDS; upstream has no name-search param)",
                       description="WTO-line UK procurement releases: stages/limit/cursor/updatedFrom/updatedTo upstream-verbatim; --name is a client-side contains filter (forces fetch of the full 100-row page, matches buyer or suppliers)")
    f7.add_argument("--name", default=None, help="Company name — client-side contains filter (no upstream name-search param exists)")
    f7.add_argument("--stages", default="award", help="OCDS stage (upstream param: stages; award|tender, default award)")
    f7.add_argument("--limit", type=int, default=10, help="Rows (upstream param: limit; 1-100; with --name = matches cap, fetch stays 100)")
    f7.add_argument("--cursor", default=None, help="Pagination cursor (upstream param: cursor; feed next_cursor)")
    f7.add_argument("--updated-from", dest="updated_from", default=None,
                     help="Window start YYYY-MM-DD or full ISO datetime (upstream param: updatedFrom; bare date gets T00:00:00Z)")
    f7.add_argument("--updated-to", dest="updated_to", default=None,
                     help="Window end (upstream param: updatedTo; bare date gets T23:59:59Z)")
    f8 = v.add_parser("gleif_direct_parent", parents=[g()],
                      help="LEI→direct parent (GLEIF dedicated endpoint)",
                      description="Direct parent card; 404 = honestly no parent (not an error)")
    f8.add_argument("--lei", required=True, help="LEI, 20 chars ISO 17442 (upstream path param: lei)")
    f9 = v.add_parser("gleif_lei_records", parents=[g()],
                      help="LEI→entity profile (GLEIF single-record face)",
                      description="Legal Entity Identifier → entity card (legal name, status, jurisdiction, registration)")
    f9.add_argument("--lei", required=True, help="LEI, 20 chars ISO 17442 (upstream path param: lei)")
    f10 = v.add_parser("gleif_lei_records_search", parents=[g()],
                      help="Company name→LEI candidates (GLEIF legalName contains)",
                      description="Name → LEI candidates (non-authoritative; verify with gleif_lei_records before persisting)")
    f10.add_argument("--filter-entity-legal-name", dest="filter_entity_legal_name", required=True,
                    help="Company name (upstream param: filter[entity.legalName], bracket-transcribed)")
    f10.add_argument("--page-size", dest="page_size", type=int, default=10,
                    help="Candidates cap (upstream param: page[size]; 1-200 hard wall, default 10)")
    f11 = v.add_parser("gleif_ultimate_parent", parents=[g()],
                       help="LEI→ultimate parent (GLEIF dedicated endpoint)",
                       description="Ultimate parent card (top of the control chain); 404 = honestly no parent (not an error)")
    f11.add_argument("--lei", required=True, help="LEI, 20 chars ISO 17442 (upstream path param: lei)")
    f12 = v.add_parser("no_brreg_enheter", parents=[g()],
                       help="Norwegian registry master record (Enhetsregisteret; --navn search XOR --organisasjonsnummer single)",
                       description="Brønnøysund Enhetsregisteret: navn search with HAL pagination (page/size, 0-based) or orgnr single record; navn is the Norwegian upstream param (?name= 400s)")
    f12.add_argument("--navn", default=None, help="Name search (upstream param: navn — Norwegian, not 'name')")
    f12.add_argument("--organisasjonsnummer", dest="organisasjonsnummer", default=None,
                     help="9-digit org number (upstream path param; spaces ok)")
    f12.add_argument("--page", type=int, default=0, help="Page, 0-based (upstream param: page; search face only)")
    f12.add_argument("--size", type=int, default=20, help="Rows per page (upstream param: size; 1-100 our politeness cap)")
    f13 = v.add_parser("no_brreg_roller", parents=[g()],
                       help="Norwegian registry roles by org number (Enhetsregisteret /roller)",
                       description="Role groups (DAGL CEO / STYR board / REVI auditor): persons carry name+birth date (no national id in the public face), corporate roles (auditors) carry org number; avregistrert=true = retired")
    f13.add_argument("--organisasjonsnummer", dest="organisasjonsnummer", required=True,
                     help="9-digit org number (upstream path param; spaces ok)")
    f14 = v.add_parser("ror_organizations", parents=[g()],
                      help="Research-org record (ROR v2; --query search XOR --ror-id single record)",
                      description="Research Organization Registry: query → candidates (fixed 20/page, --page walks), or ror_id → authoritative single record")
    f14.add_argument("--query", default=None, help="Org name search (upstream param: query)")
    f14.add_argument("--ror-id", dest="ror_id", default=None, help="ROR id, 0+8 chars (upstream path: /organizations/{id}; bare or full URL)")
    f14.add_argument("--page", type=int, default=None, help="Page number for --query (upstream param: page; fixed 20 rows/page)")
    f14.add_argument("--all-status", dest="all_status", action="store_true", default=None,
                    help="Include inactive/withdrawn orgs (upstream param: all_status; default upstream=false hides them — 0.2.9 audit)")
    f15 = v.add_parser("sec_fulltext_search", parents=[g()],
                       help="SEC filing full-text search 2001+ (EDGAR FTS)",
                       description="EDGAR full-text search: q/forms/startdt/enddt upstream-verbatim; a single date end is auto-completed (silently ignored upstream), dateRange=custom always two-ended; total_relation gte = capped at 10k")
    f15.add_argument("--q", required=True, help="Query term (upstream param: q; EDGAR FTS syntax)")
    f15.add_argument("--forms", default=None, help="Form-type filter (upstream param: forms; e.g. 8-K,10-K)")
    f15.add_argument("--startdt", default=None, help="Start date YYYY-MM-DD (upstream param: startdt; single end auto-completed to 2001-01-01)")
    f15.add_argument("--enddt", default=None, help="End date YYYY-MM-DD (upstream param: enddt; single end auto-completed to today)")
    f15.add_argument("--limit", type=int, default=10, help="Rows to return (client-side slice of the 100-hit page; ≤100)")
    f16 = v.add_parser("sec_submissions", parents=[g()],
                      help="SEC CIK→registrant card (data.sec.gov submissions)",
                      description="Registrant identity card: legal/former names, tickers·exchanges, EIN, SIC, filing totals (accepts bare/zero-padded/CIK-prefixed input)")
    f16.add_argument("--cik", required=True, help="CIK, 1-10 digits (upstream path param: CIK{cik10}.json)")
    f17 = v.add_parser("ted_notices_search", parents=[g()],
                      help="EU procurement notices (TED v3 expert search; --query expert syntax)",
                      description="Tenders Electronic Daily: expert-syntax query via --query (e.g. 'organisation-name-buyer=Siemens* AND organisation-country-buyer=DEU' / classification-cpv=33100000); limit 1-250 is an upstream hard wall")
    f17.add_argument("--query", required=True, help="Expert syntax (upstream param: query; trailing wildcard = prefix match; buyer facets organisation-name-buyer / organisation-country-buyer, CPV via classification-cpv)")
    f17.add_argument("--fields", default=None, help="Comma list of eForms fields (upstream param: fields; wrong names 400 with the full 1,833-field dump)")
    f17.add_argument("--limit", type=int, default=10, help="Notices per page (upstream param: limit; 1-250 hard wall, default 10)")
    f17.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    f18 = v.add_parser("usaspending_spending_by_award", parents=[g()],
                      help="US federal awards by recipient (USAspending spending_by_award POST)",
                      description="Federal contracts/grants: recipient name (array upstream, scalar auto-wrapped); award-type codes, time window (single end auto-completed), fields all upstream-verbatim")
    f18.add_argument("--recipient-search-text", dest="recipient_search_text", required=True,
                    help="Recipient name (upstream param: recipient_search_text; array semantics — scalar auto-wrapped)")
    f18.add_argument("--award-type-codes", dest="award_type_codes", default=None,
                    help="Comma list (upstream param: award_type_codes; default A,B,C,D contracts — grants 02/03 etc.)")
    f18.add_argument("--start-date", dest="start_date", default=None,
                    help="Window start YYYY-MM-DD (upstream param: time_period[].start_date; single end auto-completed)")
    f18.add_argument("--end-date", dest="end_date", default=None,
                    help="Window end YYYY-MM-DD (upstream param: time_period[].end_date; single end auto-completed)")
    f18.add_argument("--fields", default=None, help="Comma list of columns (upstream param: fields; default 6 columns)")
    f18.add_argument("--limit", type=int, default=10, help="Rows per page (upstream param: limit; 1-100, default 10)")
    f18.add_argument("--page", type=int, default=1, help="Page number (upstream param: page; walk while has_more)")
    f18.add_argument("--subawards", action=argparse.BooleanOptionalAction, default=False,
                    help="Include subawards (upstream param: subawards; default off)")
    f19 = v.add_parser("vies_vat", parents=[g()],
                      help="EU VAT number check (VIES; INVALID is a valid answer)",
                      description="Official EU VAT validation: member-state prefixed number; INVALID → ok:true with valid=false; '---' masking → null (not missing data)")
    f19.add_argument("--vat", required=True, help="VAT with member-state prefix (upstream path: /ms/{cc}/vat/{number}; e.g. DE811907980)")
    # —— 0.3.3 European country registry realtime faces (CH Zefix / NO Brreg / FI YTJ) ——

FLAT = {
    # company 0.2.0 flat panel (upstream params under original names + our defaults; the lambda only ferries names across namespaces)
    "ch_zefix_firm": lambda a: {"ehraid": a.ehraid},
    # 0.3.3 European country registry realtime faces (five)
    "ch_zefix_firm_search": lambda a: {"name": a.name, "max_entries": a.max_entries, "offset": a.offset},
    "fdic_institutions": lambda a: {"search": a.search, "filters": a.filters,
                            "limit": a.limit},
    "fi_ytj_companies": lambda a: {"name": a.name, "business_id": a.business_id},
    "fr_recherche_search": lambda a: {"q": a.q, "page": a.page, "per_page": a.per_page,
                            "etat_administratif": a.etat_administratif},
    "gb_contracts_finder_published_notices": lambda a: {"name": a.name, "published_from": a.published_from,
                                      "published_to": a.published_to, "stages": a.stages,
                                      "limit": a.limit, "cursor": a.cursor},
    "gb_fts_release_packages": lambda a: {"name": a.name, "stages": a.stages, "limit": a.limit,
                                 "cursor": a.cursor, "updated_from": a.updated_from,
                                 "updated_to": a.updated_to},
    "gleif_direct_parent": lambda a: {"lei": a.lei},
    "gleif_lei_records": lambda a: {"lei": a.lei},
    "gleif_lei_records_search": lambda a: {"filter_entity_legal_name": a.filter_entity_legal_name,
                                           "page_size": a.page_size},
    "gleif_ultimate_parent": lambda a: {"lei": a.lei},
    "no_brreg_enheter": lambda a: {"navn": a.navn, "organisasjonsnummer": a.organisasjonsnummer,
                          "page": a.page, "size": a.size},
    "no_brreg_roller": lambda a: {"organisasjonsnummer": a.organisasjonsnummer},
    "ror_organizations": lambda a: {"query": a.query, "ror_id": a.ror_id, "page": a.page,
                                    "all_status": a.all_status},
    "sec_fulltext_search": lambda a: {"q": a.q, "forms": a.forms, "startdt": a.startdt,
                          "enddt": a.enddt, "limit": a.limit},
    "sec_submissions": lambda a: {"cik": a.cik},
    "ted_notices_search": lambda a: {"query": a.query,
                              "fields": a.fields, "limit": a.limit, "page": a.page},
    "usaspending_spending_by_award": lambda a: {"recipient_search_text": a.recipient_search_text,
                                     "award_type_codes": a.award_type_codes,
                                     "start_date": a.start_date, "end_date": a.end_date,
                                     "fields": a.fields, "limit": a.limit, "page": a.page,
                                     "subawards": a.subawards},
    "vies_vat": lambda a: {"vat": a.vat},
}


# 0.3.10 jurisdiction chapter: face → jurisdiction (default = the issuing authority's jurisdiction; bodies
# covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2 + EU + GLOBAL) — merged into _JURISDICTION by the root cli.py; success envelopes carry the jurisdiction chapter
COUNTRY = {
    "ch_zefix_firm": "CH",
    "ch_zefix_firm_search": "CH",
    "fdic_institutions": "US",
    "fi_ytj_companies": "FI",
    "fr_recherche_search": "FR",
    "gb_contracts_finder_published_notices": "GB",
    "gb_fts_release_packages": "GB",
    "gleif_direct_parent": "GLOBAL",
    "gleif_lei_records": "GLOBAL",
    "gleif_lei_records_search": "GLOBAL",
    "gleif_ultimate_parent": "GLOBAL",
    "no_brreg_enheter": "NO",
    "no_brreg_roller": "NO",
    "ror_organizations": "GLOBAL",
    "sec_fulltext_search": "US",
    "sec_submissions": "US",
    "ted_notices_search": "EU",
    "usaspending_spending_by_award": "US",
    "vies_vat": "EU",
}
