"""company cli — domain command face registration (split per domain in 0.2.6, moved in from the root cli.py; purely flat since the 0.3.0 verb-layer + sugar removal).

register(v, g): registers flat commands on the domain subparser (g = the root _leaf_globals factory,
passed in as a parameter to avoid a cli ↔ domain-cli cycle); FLAT = the flat dispatch table, merged by the root cli for main to use.
"""
import argparse

from . import in_sebi_intm  # the 37-category choice list rides the provider's verbatim map

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
    # —— 0.3.11 CO RUES + KR hometax dual-country batch ——
    f_co = v.add_parser("co_rues_companies", parents=[g()],
                       help="Colombian business registry master (RUES via datos.gov.co Socrata; --where SoQL)",
                       description="RUES registro mercantil master, 9.4M rows: matricula registry key x NIT tax id x CIIU industry x legal form x representante_legal name edge; base filter keeps NIT-identified (tax entity) rows only — persona natural rows whose id columns are cedulas stay out of the face, and the RL cedula-number column is stripped (names kept)")
    f_co.add_argument("--where", default=None,
                     help="Raw SoQL filter (upstream param: $where; merged with base filter clase_identificacion='NIT' by AND)")
    f_co.add_argument("--limit", type=int, default=20, help="Rows per page (upstream param: $limit; 1-500 our politeness cap)")
    f_co.add_argument("--offset", type=int, default=0, help="Row offset (upstream param: $offset; >=0)")
    f_co.add_argument("--order", default=None, help="Order clause (upstream param: $order; column [ASC|DESC], no NULLS syntax)")
    # —— 0.3.32 CZ ARES economic-entities register batch ——
    f_cz = v.add_parser("cz_ares_ekonomicke_subjekty", parents=[g()],
                        help="Czech economic-entities register record by IČO (ARES; --ico eight digits)",
                        description="ARES single record: IČO [0-9]{8} (validated locally, upstream 400s anything else); structured address with the RUIÁN address-point code, legal form, VAT key (CZ<ico>), NACE-2008 codes and the 16-register status matrix; unknown-but-well-formed IČO → 404 = upstream_not_found")
    f_cz.add_argument("--ico", required=True,
                      help="IČO, exactly eight digits (upstream path param: ico; the ARES surrogate id 'ARES_…' is NOT an IČO)")
    f_cz2 = v.add_parser("cz_ares_ekonomicke_subjekty_vyhledat", parents=[g()],
                         help="Czech economic-entities register name search (ARES POST vyhledat)",
                         description="ARES name search (POST-only): the upstream folds record names to ASCII but not the query — the query is folded here so the match set is the upstream's own; the rows are heterogeneous (ico present only on ROS-family rows, RZP-primary rows carry the unjoinable ARES surrogate icoId)")
    f_cz2.add_argument("--obchodni-jmeno", dest="obchodni_jmeno", required=True,
                       help="Name word to search (upstream body param: obchodniJmeno; folded to ASCII for the upstream index)")
    f_cz2.add_argument("--pocet", type=int, default=10,
                       help="Rows per page (upstream body param: pocet; 1-100 our politeness cap, default 10)")
    f_cz2.add_argument("--start", type=int, default=0,
                       help="Row offset (upstream body param: start; >=0)")
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
    # —— 0.3.33 offshore Channel-Islands registers batch (GG GFSC + JE JFSC) ——
    f_gg2 = v.add_parser("gg_gfsc_registered_businesses", parents=[g()],
                         help="Guernsey registered (prescribed) businesses (GFSC full feed, local scan)",
                         description="GFSC Registration of Prescribed Businesses (133 rows): Accountant 74 / Estate Agent 22 / Money Service Providers 20 / Legal Professional 17; 23 refs also appear on the regulated feed (dual-listed entities); same HTML-strip + detail-path rescue as the regulated face")
    f_gg2.add_argument("--name", default=None, help="Business name — client-side contains filter")
    f_gg2.add_argument("--category", default=None,
                       help="Prescribed-business category — contains filter (Accountant / Estate Agent / Money Service Providers / Legal Professional)")
    f_gg2.add_argument("--ref", default=None, help="GFSC ref, digits — exact match (no length assumption)")
    f_gg2.add_argument("--limit", type=int, default=20, help="Rows to return (local payload wall 1-100; default 20)")
    f_gg = v.add_parser("gg_gfsc_regulated_entities", parents=[g()],
                        help="Guernsey regulated-entities register (GFSC full feed, local scan; --licence contains)",
                        description="GFSC regulated entities: the feed ships display fields as HTML links — stripped to ref/name/licence + the register's own detail path. One row per licence group (the same entity on 2+ rows when its groups sit in different states: 26 such refs — entities_matched counts distinct refs); licence labels embed commas ('Secondary Licensee, Pension Provider' is ONE group); surrendered is a '0'/'1' string on the wire → bool; Status null = the register states nothing (1,571 rows); refs not uniformly 7-digit (legacy 5-6-digit)")
    f_gg.add_argument("--name", default=None, help="Entity name — client-side contains filter (the feed has no query surface)")
    f_gg.add_argument("--licence", default=None,
                      help="Licence-group label — contains filter over Filters (labels embed commas: filter on the token, e.g. 'Insurer' or 'Pension Provider')")
    f_gg.add_argument("--status", default=None, choices=["active", "inactive"],
                      help="Register status — exact filter (null-status rows, 41 percent of the feed, match neither)")
    f_gg.add_argument("--surrendered", action=argparse.BooleanOptionalAction, default=None,
                      help="Surrendered flag filter (the revoked/surrendered licence-group rows)")
    f_gg.add_argument("--ref", default=None,
                      help="GFSC ref, digits — exact match, no length assumption (legacy refs are 5-6 digits)")
    f_gg.add_argument("--limit", type=int, default=20,
                      help="Rows to return (local payload wall 1-100 after the full-feed scan; default 20)")
    f8 = v.add_parser("gleif_direct_parent", parents=[g()],
                      help="LEI→direct parent (GLEIF dedicated endpoint)",
                      description="Direct parent card; 404 = honestly no parent (not an error)")
    f8.add_argument("--lei", required=True, help="LEI, 20 chars ISO 17442 (upstream path param: lei)")
    f9 = v.add_parser("gleif_lei_records", parents=[g()],
                      help="LEI→entity profile (GLEIF single-record face)",
                      description="Legal Entity Identifier → entity card (legal name, status, jurisdiction, registration; "
                                  "+ successor LEIs (M&A edge), expiration, legal form, BIC/MIC)")
    f9.add_argument("--lei", required=True, help="LEI, 20 chars ISO 17442 (upstream path param: lei)")
    f10 = v.add_parser("gleif_lei_records_search", parents=[g()],
                      help="Company name→LEI candidates (GLEIF legalName contains; --filter-entity-jurisdiction/--filter-entity-status narrow)",
                      description="Name → LEI candidates (non-authoritative; verify with gleif_lei_records before persisting); "
                                  "jurisdiction/status filters and page[number] walking upstream-verbatim; rows carry registered_as (cross-registry join key)")
    f10.add_argument("--filter-entity-legal-name", dest="filter_entity_legal_name", required=True,
                    help="Company name (upstream param: filter[entity.legalName], bracket-transcribed)")
    f10.add_argument("--filter-entity-jurisdiction", dest="filter_entity_jurisdiction", default=None,
                    help="Jurisdiction filter (upstream param: filter[entity.jurisdiction]; ISO 3166 country or region code, e.g. CH or US-MO — probed US-MO→1 hit; jurisdictionCountry is whitelist-rejected upstream, not mirrored)")
    f10.add_argument("--filter-entity-status", dest="filter_entity_status", default=None,
                    help="Entity status filter (upstream param: filter[entity.status]; ACTIVE/INACTIVE/NULL — entity lifecycle, not registration.status ISSUED/LAPSED/RETIRED)")
    f10.add_argument("--page-number", dest="page_number", type=int, default=None,
                    help="Page, 1-based (upstream param: page[number]; walk while page ≤ result page.lastPage)")
    f10.add_argument("--page-size", dest="page_size", type=int, default=10,
                    help="Candidates cap (upstream param: page[size]; 1-200 hard wall, default 10)")
    f11 = v.add_parser("gleif_ultimate_parent", parents=[g()],
                       help="LEI→ultimate parent (GLEIF dedicated endpoint)",
                       description="Ultimate parent card (top of the control chain); 404 = honestly no parent (not an error)")
    f11.add_argument("--lei", required=True, help="LEI, 20 chars ISO 17442 (upstream path param: lei)")
    # —— 0.3.35 IN SEBI registers batch (dictionary slot: in_sebi_* between gg_gfsc and je_jfsc) ——
    f_in1 = v.add_parser("in_sebi_default_brokers", parents=[g()],
                         help="SEBI defaulters & expelled stock brokers (the whole negative register, one page)",
                         description="sebi.gov.in/sebiweb BrokerAction: ONE 1.2MB page, 445 cards, no "
                                     "paging, no search. Cards: Name/Trade Name/Registration No. (INB…)/"
                                     "Exchange Name/Status (Defaulter 80 | Expelled 215 | Defaulter and "
                                     "expelled 150, pinned 2026-11-04); one entity may span multiple "
                                     "cards (one per exchange)")
    f_in2 = v.add_parser("in_sebi_intermediaries", parents=[g()],
                         help="SEBI registered intermediaries by category (--search XOR --regno)",
                         description="sebi.gov.in/sebiweb recognised-intermediaries register: 37 "
                                     "categories verbatim (default = equity-segment stock brokers). "
                                     "Exactly one of --search (substring over names; MOTILAL → 7 cards) "
                                     "or --regno (exact registration-number lookup, INB030484617 → the "
                                     "multi-exchange row set) — an empty search over a full category "
                                     "TIMES OUT server-side (5,011 equity brokers). Card field set "
                                     "varies by category (CRA cards carry Contact Person/Correspondence "
                                     "Address, no Exchange; regno formats differ per class — INB…/INZ…/"
                                     "IN/CRA/…); every title/value pair rides, unknown labels verbatim")
    f_in2.add_argument("--category", default="sb_equity",
                       choices=list(in_sebi_intm.CATEGORIES),
                       help="Intermediary category, 37 verbatim (default sb_equity = Registered Stock "
                            "Brokers in equity segment; the choice list maps slug→intmId)")
    f_in2.add_argument("--search", default=None,
                       help="Name substring over the category (upstream param: search; e.g. MOTILAL → 7 cards)")
    f_in2.add_argument("--regno", default=None,
                       help="Exact registration-number lookup (upstream param: regNo; e.g. INB030484617 → the multi-exchange rows)")
    f_jf = v.add_parser("je_jfsc_regulated_entities", parents=[g()],
                        help="Jersey regulated-entities register search (JFSC Umbraco API POST)",
                        description="JFSC regulated entities: site-search rows (Title/Url/Rank) + the official licence text verbatim in LawSection ('Banking (DC) (ref. DC0076), …' → law/code/ref triplets, raw kept). NoResults is a RESULT COUNT, not a zero flag (Keyword Barclays → NoResults=1); Refiners not exposed (space-joined lowercase keys — unstable, rasff precedent); keyword required (empty keyword = whole-register enumeration, unpinned)")
    f_jf.add_argument("--keyword", required=True,
                      help="Entity-name keyword (upstream body param: Keyword; required — the empty-keyword POST enumerates the whole register)")
    f_jf.add_argument("--page-size", dest="page_size", type=int, default=20,
                      help="Rows per page (upstream body param: PageSize; 1-100 our politeness cap, default 20)")
    f_jf.add_argument("--page", type=int, default=1,
                      help="Page, 1-based (upstream body param: PageNumber; walk while page < pages)")
    f_kr = v.add_parser("kr_hometax_biz_status", parents=[g()],
                       help="Korean biz registration status, single lookup (hometax 휴폐업/과세유형; --biz-no)",
                       description="NTS hometax anonymous single-BRN status: four states all legal answers — active (일반/간이/과세특례 taxpayer), closed (ISO closure date extracted), unregistered (result=S, not an error), error; txprNm is always null upstream (no owner-name leak)")
    f_kr.add_argument("--biz-no", dest="biz_no", required=True,
                     help="10-digit business registration number (사업자등록번호; 3-2-5 hyphens optional, e.g. 124-81-00998)")
    # —— 0.3.34 KZ GBD_UL master register (data.egov.kz portal-session face) ——
    f_kz = v.add_parser("kz_gbd_ul_companies", parents=[g()],
                        help="Kazakhstan legal-entities master register (GBD_UL; --text server-side name filter)",
                        description="data.egov.kz GBD_UL: bilingual column pairs verbatim (nameru/namekz, okedru/okedkz, statusru/statuskz, addressru/addresskz); bin = the 12-digit hard key but page 1's pre-BIN-era rows (1995-1999) carry bin=null; datereg is tri-modal (bare / +06:00 pre-2024 / +05:00 unified KZ) and verbatim; count is hard-clamped to 20 upstream (walled here); column/order sorts are silently ignored (not shipped); a page past the last silently snaps to the last page — has_more reads the echoed page; the channel needs a portal-session cookie (bootstrapped transparently, reused 15 min)")
    f_kz.add_argument("--text", default=None,
                     help="Name filter — server-side substring over nameru (upstream param: text; omit = the whole register, 1M+ entities)")
    f_kz.add_argument("--page", type=int, default=1, help="Page, 1-based (upstream param: page; past-the-last snaps to the last page — no empty-page signal)")
    f_kz.add_argument("--count", type=int, default=20,
                     help="Rows per page (upstream param: count; 1-20 — the upstream's own hard clamp: count=100 answers 20 rows)")
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
    # —— 0.3.30 NZ Companies Office register faces (nzco_companies search + nzco_directors) ——
    f20 = v.add_parser("nzco_companies", parents=[g()],
                       help="NZ Companies Register search (Companies Office; dual keys: company number + NZBN)",
                       description="Name substring over the register index — the canonical parameter set is required (a bare ?q= answers an empty match, pinned). Rows: company number + 16-digit NZBN + the register's own status word (Registered/Removed, not 'Active') + entity type + registered address. Paging = the pager's own start=<row offset> + limit 5|15 (both observed live; other sizes unpinned, not shipped); has_next reads the pager offsets")
    f20.add_argument("--q", required=True, help="Name substring (the register also matches by company number inside the name index)")
    f20.add_argument("--entity-types", dest="entity_types", default="ALL",
                     choices=["ALL", "LTD", "UNLTD", "COOP", "ASIC", "NON_ASIC"],
                     help="Filter form's own checkbox codes: LTD/UNLTD/COOP = NZ companies, ASIC/NON_ASIC = overseas (default ALL)")
    f20.add_argument("--start", type=int, default=0, help="Row offset (the pager's own start=; page N = (N-1)*limit)")
    f20.add_argument("--limit", type=int, default=15, choices=[5, 15],
                     help="Rows per page (both observed in the live pager; other sizes unpinned and not shipped)")
    f21 = v.add_parser("nzco_directors", parents=[g()],
                       help="NZ company current directors by company number (Companies Office directors tab)",
                       description="Current appointments: full legal name + residential address (statutorily public in NZ, partially masked since the privacy-law change — captured verbatim) + appointment date in the register's wording. The page H1 confirms the company (name+number+status; a mismatch refuses to attribute rows). Ceased/former appointments render in a different section and stay out; find the number with nzco_companies (e.g. 104799 = Air New Zealand Limited)")
    f21.add_argument("--company-number", dest="company_number", required=True,
                     help="NZ company number, digits only (from nzco_companies rows)")
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
    # —— 0.3.36 TR SPK listed-companies directory (dictionary slot: tr_spk_listed between ted and usaspending) ——
    f_tr = v.add_parser("tr_spk_listed", parents=[g()],
                        help="SPK publicly-listed companies (Borsa 628 + BorsaDisi 121 one-shot walls, local scan)",
                        description="ws.spk.gov.tr HalkaAcikSirket: two one-shot walls — Borsa "
                                    "(exchange-traded, 628) + BorsaDisi (non-exchange, 121), "
                                    "cached 24h and scanned locally. mersisNo = the 16-digit "
                                    "MERSIS join key (a few rows ship it null); the lifecycle "
                                    "status rides INLINE in unvani ('(İFLAS NEDENİYLE) TASFİYE "
                                    "HALİNDE …' on 16 rows — no separate status column); "
                                    "mkkSicilNo joins the MKK register (arrives as '' or null "
                                    "inconsistently — both null here). --mersis switches to the "
                                    "single-record channel (tur/faaliyetDurumu/street adres, "
                                    "which the lists lack) — sirketVarmi LIES: a MERSIS outside "
                                    "the register also answers true with an all-null shell "
                                    "(pinned 2026-11-04); 'found' mirrors unvani instead")
    f_tr.add_argument("--name", default=None,
                      help="Company name — substring, case-insensitive (over unvani; no upstream query surface)")
    f_tr.add_argument("--segment", default="all", choices=["all", "borsa", "borsadisi"],
                      help="Wall filter (all = both one-shot lists, default; borsa = exchange-traded 628; borsadisi = 121)")
    f_tr.add_argument("--mersis", default=None,
                      help="MERSIS number, exactly 16 digits — the single-record channel (XOR with --name/--segment)")
    f_tr.add_argument("--limit", type=int, default=20,
                      help="Rows to return (local payload wall 1-100, default 20; total_matched echoes the full count)")
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
    # 0.3.11 CO RUES + KR hometax dual-country batch
    "co_rues_companies": lambda a: {"where": a.where, "limit": a.limit, "offset": a.offset,
                          "order": a.order},
    # 0.3.32 CZ ARES economic-entities register batch
    "cz_ares_ekonomicke_subjekty": lambda a: {"ico": a.ico},
    "cz_ares_ekonomicke_subjekty_vyhledat": lambda a: {"obchodni_jmeno": a.obchodni_jmeno,
                                          "pocet": a.pocet, "start": a.start},
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
    # 0.3.33 offshore Channel-Islands registers batch
    "gg_gfsc_registered_businesses": lambda a: {"name": a.name, "category": a.category,
                                                "ref": a.ref, "limit": a.limit},
    "gg_gfsc_regulated_entities": lambda a: {"name": a.name, "licence": a.licence,
                                             "status": a.status, "surrendered": a.surrendered,
                                             "ref": a.ref, "limit": a.limit},
    "gleif_direct_parent": lambda a: {"lei": a.lei},
    "gleif_lei_records": lambda a: {"lei": a.lei},
    "gleif_lei_records_search": lambda a: {"filter_entity_legal_name": a.filter_entity_legal_name,
                                           "page_size": a.page_size,
                                           "filter_entity_jurisdiction": a.filter_entity_jurisdiction,
                                           "filter_entity_status": a.filter_entity_status,
                                           "page_number": a.page_number},
    "gleif_ultimate_parent": lambda a: {"lei": a.lei},
    # 0.3.35 IN SEBI registers batch
    "in_sebi_default_brokers": lambda a: {},
    "in_sebi_intermediaries": lambda a: {"category": a.category, "search": a.search,
                                         "regno": a.regno},
    "je_jfsc_regulated_entities": lambda a: {"keyword": a.keyword, "page_size": a.page_size,
                                             "page": a.page},
    "kr_hometax_biz_status": lambda a: {"biz_no": a.biz_no},
    # 0.3.34 KZ GBD_UL master register batch
    "kz_gbd_ul_companies": lambda a: {"text": a.text, "page": a.page, "count": a.count},
    "no_brreg_enheter": lambda a: {"navn": a.navn, "organisasjonsnummer": a.organisasjonsnummer,
                          "page": a.page, "size": a.size},
    "no_brreg_roller": lambda a: {"organisasjonsnummer": a.organisasjonsnummer},
    "nzco_companies": lambda a: {"q": a.q, "entity_types": a.entity_types,
                                 "start": a.start, "limit": a.limit},
    "nzco_directors": lambda a: {"company_number": a.company_number},
    "ror_organizations": lambda a: {"query": a.query, "ror_id": a.ror_id, "page": a.page,
                                    "all_status": a.all_status},
    "sec_fulltext_search": lambda a: {"q": a.q, "forms": a.forms, "startdt": a.startdt,
                          "enddt": a.enddt, "limit": a.limit},
    "sec_submissions": lambda a: {"cik": a.cik},
    "ted_notices_search": lambda a: {"query": a.query,
                              "fields": a.fields, "limit": a.limit, "page": a.page},
    # 0.3.36 TR SPK listed-companies directory (dictionary slot: tr_spk_listed between ted and usaspending)
    "tr_spk_listed": lambda a: {"name": a.name, "segment": a.segment,
                                "mersis": a.mersis, "limit": a.limit},
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
    "co_rues_companies": "CO",
    "cz_ares_ekonomicke_subjekty": "CZ",
    "cz_ares_ekonomicke_subjekty_vyhledat": "CZ",
    "fdic_institutions": "US",
    "fi_ytj_companies": "FI",
    "fr_recherche_search": "FR",
    "gb_contracts_finder_published_notices": "GB",
    "gb_fts_release_packages": "GB",
    "gg_gfsc_registered_businesses": "GG",
    "gg_gfsc_regulated_entities": "GG",
    "gleif_direct_parent": "GLOBAL",
    "gleif_lei_records": "GLOBAL",
    "gleif_lei_records_search": "GLOBAL",
    "gleif_ultimate_parent": "GLOBAL",
    "in_sebi_default_brokers": "IN",
    "in_sebi_intermediaries": "IN",
    "je_jfsc_regulated_entities": "JE",
    "kr_hometax_biz_status": "KR",
    "kz_gbd_ul_companies": "KZ",
    "no_brreg_enheter": "NO",
    "no_brreg_roller": "NO",
    "nzco_companies": "NZ",
    "nzco_directors": "NZ",
    "ror_organizations": "GLOBAL",
    "sec_fulltext_search": "US",
    "sec_submissions": "US",
    "ted_notices_search": "EU",
    "tr_spk_listed": "TR",
    "usaspending_spending_by_award": "US",
    "vies_vat": "EU",
}
