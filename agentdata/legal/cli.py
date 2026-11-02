"""legal cli — domain command-face registration (split per domain in 0.2.6, migrated from the root cli.py; purely flat since the 0.3.0 verb-layer + frozen-alias removal).

register(v, g): registers flat commands onto the domain subparser (g = root _leaf_globals factory,
passed in as a parameter to avoid a cli <-> domain-cli cycle); FLAT = flat dispatch table, merged by the root cli for main to use.
"""
import argparse

def register(v, g):
    # Flat commands (2026-10-23 ruling: verb layer abolished across all domains, <domain> <source>_<dataset> direct; new capabilities are born flat)
    f0 = v.add_parser("co_sic_sanctions", parents=[g()],
                      help="Colombia SIC firm sanctions (datos.gov.co Socrata 73dx-n59j)",
                      description="Colombia SIC sanctions register (keyless): firm sanctions imposed "
                                  "in firme by the Superintendencia de Industria y Comercio — multado (the sanctioned "
                                  "party) × valor (fine, COP) × conducta (the violation) × sector, 3,938 rows 2013→. "
                                  "Socrata $-parameter channel verbatim: --where raw SoQL, --limit 1-500, --offset, "
                                  "--order column[ ASC|DESC] (same contract as co_secop_contracts; name-only key — no "
                                  "NIT column, a name join onto co_rues_companies is the corpus line's job)")
    f0.add_argument("--where", default=None, help="Raw SoQL filter (upstream param: $where; e.g. \"upper(multado) like '%%ECOPETROL%%'\")")  # %% escaping: argparse help goes through % interpolation
    f0.add_argument("--limit", type=int, default=20, help="Rows (upstream param: $limit; 1-500 politeness cap)")
    f0.add_argument("--offset", type=int, default=0, help="Row offset (upstream param: $offset; Socrata sends no total echo)")
    f0.add_argument("--order", default=None, help="Sort (upstream param: $order; e.g. 'fecha_emitida DESC'; no NULLS syntax — SoQL 400s)")

    f1 = v.add_parser("courtlistener_opinions_search", parents=[g()],
                      help="US federal + state opinions search (CourtListener Search API v4)",
                      description="CourtListener opinions search (federal + state courts; CAP/api.case.law retired into this source): at least one filter required (full corpus ~8.3M bulk is served by the S3 batch line); upstream fixes page size at 20 — page via --cursor (next_cursor is echoed back). 0.2.9 audit snapshot (2026-10-28): the search endpoint now returns 401 for anonymous traffic (worked 2026-10-26) while other v4 endpoints stay open — face on watch per the keyless-only ruling; authenticated tiers are 5/min·50/hr·125/day, anonymous numbers unpublished upstream")
    f1.add_argument("--q", default=None, help="Full-text query (upstream param: q)")
    f1.add_argument("--case-name", default=None, help="Case-name filter (upstream param: case_name)")
    f1.add_argument("--court", default=None, help="Court id, e.g. calctapp/scotus (upstream param: court)")
    f1.add_argument("--judge", default=None, help="Judge name filter (upstream param: judge)")
    f1.add_argument("--docket-number", default=None, help="Docket number filter (upstream param: docket_number)")
    f1.add_argument("--filed-after", default=None, help="Filed on/after YYYY-MM-DD (upstream param: filed_after)")
    f1.add_argument("--filed-before", default=None, help="Filed on/before YYYY-MM-DD (upstream param: filed_before)")
    f1.add_argument("--order-by", default=None, help="Sort, e.g. 'score desc' (upstream param: order_by)")
    f1.add_argument("--cursor", default=None, help="Opaque cursor from next_cursor (upstream param: cursor)")

    # —— 0.2.11 legal new faces: UK CMA twin faces (search/content API, stood up from live probing 2026-10-29) ——

    f2 = v.add_parser("csl_screening_list", parents=[g()],
                      help="Sanctions screening (US CSL — 12 list families, one CSV, local full-register scan)",
                      description="Name screening against the US Consolidated Screening List (realtime, local execution): "
                                  "SDN / Entity List / DPL / ITAR / SSI … 12 list families, 26k rows in one keyless CSV, "
                                  "cached 24h and scanned locally (matched_on shows which face hit: name or alt_names). "
                                  "Empty result = clean screening (a legitimate answer)")
    f2.add_argument("--name", default=None, help="Subject name (substring, case-insensitive; matches name + alt_names; required — the client gate returns a JSON usage_error envelope)")
    f2.add_argument("--source", default=None, help="List-family filter, substring (e.g. \"Entity List\", \"SDN\", \"Sectoral\")")
    f2.add_argument("--type", default=None, help="Subject type: Entity / Individual / Vessel / Aircraft (many rows carry no type)")
    f2.add_argument("--limit", type=int, default=20, help="Rows to return (default 20, ≤100; total_matched echoes the full count)")

    f3 = v.add_parser("dgcomp_cases_search", parents=[g()],
                      help="EU competition cases (DG COMP; aid/antitrust/merger/DMA)",
                      description="DG COMP case search: --query raw ES bool DSL (JSON text, XOR with sugar) XOR --name/--instrument sugar (assembles the SPA's three-field text query / caseInstrument term); pageSize hard cap 100 — upstream silently returns 100 rows for larger asks (probed 2026-10-26)")
    f3.add_argument("--query", default=None, help='Raw ES bool DSL, JSON text — e.g. \'{"bool": {"must": [{"term": {"caseInstrument": "SA"}}]}}\' (upstream param: query)')
    f3.add_argument("--name", default=None, help="Sugar — party/case-name text query over caseTitle/caseCompanies/caseOriginalTitle (XOR with --query)")
    f3.add_argument("--instrument", default=None, help="Case-type filter: AT antitrust / M merger / SA state aid / DMA Digital Markets Act (sugar channel)")
    f3.add_argument("--text", default="", help="Extra full-text condition (upstream param: text; empty = none)")
    f3.add_argument("--page", type=int, default=1, help="Page number (upstream param: pageNumber)")
    f3.add_argument("--limit", type=int, default=20, help="Rows (upstream param: pageSize; 1-100 hard wall — 200 silently yields 100, probed 2026-10-26)")

    f4 = v.add_parser("ecfr_search", parents=[g()],
                      help="US Code of Federal Regulations current-state section search (eCFR)",
                      description="eCFR current-code section search (keyless, realtime): where a topic lives in the "
                                  "codified CFR today — counterpart of fulltext (Federal Register = what changed today). "
                                  "coords = seven-level citation; starts_on~ends_on = that version's effective window. "
                                  "0.2.9 audit: --date = point-in-time retrieval (section versions in force on that date; "
                                  "probed 2026-10-28 asbestos 1,436 current vs 339 at 2024-01-01)")
    f4.add_argument("--q", default=None, help="Topic term (required — the client gate returns a JSON usage_error envelope)")
    f4.add_argument("--page", type=int, default=1, help="Page number (default 1)")
    f4.add_argument("--limit", type=int, default=20, help="Rows to return (default 20, ≤100)")
    f4.add_argument("--date", default=None,
                    help="Point-in-time date YYYY-MM-DD (upstream param: date; section versions in force on that date — omit for current state)")

    f5 = v.add_parser("ecfr_titles", parents=[g()],
                      help="CFR title catalog (eCFR: 50 titles + daily currency watermark)",
                      description="eCFR title catalog (keyless): the 50 CFR titles with latest amendment/issue dates "
                                  "and the library-wide as_of watermark (eCFR integrates daily)")

    # —— 0.2.0 flat panel commands (legal main faces: source-qualified names + upstream param names verbatim + our defaults) ——

    f6 = v.add_parser("federalregister_documents", parents=[g()],
                      help="Federal Register docs search (1994+ daily release stream)",
                      description="Federal Register document search: q → conditions[term] verbatim; startdt/enddt auto-completed to a full window when either end is given (a single end is silently ignored upstream); document_number is the stable key, single-doc raw_text_url feeds the corpus batch line. 0.2.9 audit additions: --doc-type closed set validated locally (invalid values silently return 0 rows upstream — false-negative trap), --agencies slug filter, --cfr-title/--cfr-part CFR-anchored narrowing (part requires title), --order gains executive_order_number")
    f6.add_argument("--q", required=True, help="Query term (upstream param: conditions[term]; quoted phrases go exact)")
    f6.add_argument("--startdt", default=None, help="Start date YYYY-MM-DD (upstream param: conditions[publication_date][gte]; bare end auto-completed to 1994-01-01)")
    f6.add_argument("--enddt", default=None, help="End date YYYY-MM-DD (upstream param: conditions[publication_date][lte]; bare start auto-completed to today)")
    f6.add_argument("--order", default="relevance", choices=["relevance", "newest", "oldest", "executive_order_number"],
                    help="Result order (upstream param: order; fourth value executive_order_number audited in 2026-10-28)")
    f6.add_argument("--doc-type", dest="doc_type", default=None, choices=["RULE", "PRORULE", "NOTICE", "PRESDOCU"],
                    help="Document type (upstream param: conditions[type][]; closed set — invalid values silently return 0 rows upstream, validated locally)")
    f6.add_argument("--agencies", default=None,
                    help="Agency slug, e.g. environmental-protection-agency (upstream param: conditions[agencies][]; value domain from GET /api/v1/agencies)")
    f6.add_argument("--cfr-title", dest="cfr_title", default=None, help="CFR title number, e.g. 40 (upstream param: conditions[cfr][title])")
    f6.add_argument("--cfr-part", dest="cfr_part", default=None,
                    help="CFR part or part range, e.g. 763 or 1-50 (upstream param: conditions[cfr][part]; requires --cfr-title)")
    f6.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    f6.add_argument("--limit", type=int, default=20, help="Rows (maps to upstream per_page; politeness cap 50 — upstream cap 1000)")

    f7 = v.add_parser("gb_cma_case", parents=[g()],
                      help="UK CMA single-case dossier (gov.uk content API)",
                      description="UK CMA single-case dossier (keyless): content_id is the stable UUID key; "
                                  "change_history = case evolution newest→oldest ([0] = latest, last = First published); attachments = decision/notice PDF family; "
                                  "body_html = case-page summary. A pasted full base_path (/cma-cases/<slug> or absolute URL) "
                                  "is accepted — the prefix is stripped")
    f7.add_argument("--slug", required=True, help="Case slug (from gb_cma_cases rows; bare tail segment, e.g. nexfibre-slash-substantial-merger-inquiry)")

    f8 = v.add_parser("gb_cma_cases", parents=[g()],
                      help="UK competition cases (CMA; merger/market/investigation case list)",
                      description="UK CMA case search (gov.uk search API, keyless): q verbatim over case titles "
                                  "(case name = party pair 'A / B'); count politeness cap 100 (upstream has no wall — "
                                  "count=1000 yields the full 1000, probed 2026-10-29); start = offset pagination; "
                                  "omit --q to enumerate the full live register (~2,591 cases). Single-case detail: gb_cma_case "
                                  "with the slug from each row")
    f8.add_argument("--q", default=None, help="Query term (upstream param: q; searches case titles/descriptions)")
    f8.add_argument("--count", type=int, default=20, help="Rows (upstream param: count; 1-100 politeness cap — upstream wall-free, probed 2026-10-29)")
    f8.add_argument("--start", type=int, default=0, help="Offset (upstream param: start)")

    f9 = v.add_parser("gb_ec_donations", parents=[g()],
                      help="UK political donations (Electoral Commission /donations endpoint)",
                      description="UK EC donations face: query verbatim (donor/regulated-entity name); from/to window auto-completed when missing (missing window → upstream Total=-1 fake success); rows hard cap 50 (probed 2026-10-26)")
    f9.add_argument("--query", required=True, help="Donor/regulated-entity name (upstream param: query; contains-match)")
    f9.add_argument("--from", dest="from_", default=None, help="Window start YYYY-MM-DD (upstream param: from; default=register origin 2001-02-16)")
    f9.add_argument("--to", default=None, help="Window end YYYY-MM-DD (upstream param: to; default=today)")
    f9.add_argument("--start", type=int, default=None, help="Offset (upstream param: start)")
    f9.add_argument("--limit", type=int, default=20, help="Rows (maps to upstream rows; 1-50 hard wall — 51/200 silently yield 50, probed 2026-10-26)")

    f10 = v.add_parser("gb_ec_loans", parents=[g()],
                       help="UK political loans (Electoral Commission /loans endpoint)",
                       description="UK EC loans face: query verbatim (lender/borrower name); upstream loans endpoint takes no date-window params; rows hard cap 50 (probed 2026-10-26)")
    f10.add_argument("--query", required=True, help="Lender/borrower name (upstream param: query; contains-match)")
    f10.add_argument("--start", type=int, default=None, help="Offset (upstream param: start)")
    f10.add_argument("--limit", type=int, default=20, help="Rows (maps to upstream rows; 1-50 hard wall — 51/200 silently yield 50, probed 2026-10-26)")

    # —— 0.3.8 legal caselaw line: TNA Find Case Law two faces (atom search + Akoma Ntoso single record, live-probed 2026-10-29; dictionary-order slots between gb_ec_loans and lda; ISO-prefixed 0.3.13) ——

    f11 = v.add_parser("gb_tna_caselaw_judgment", parents=[g()],
                       help="UK single-judgment dossier (Akoma Ntoso XML from Find Case Law)",
                       description="UK single-judgment dossier (keyless): neutral_citation is the official key; parties = "
                                   "[{name, role}] official party-to-role edges (claimant/defendant, companies and individuals); "
                                   "judges; text = plain-text body. document_uri takes all three forms — legacy ewhc/admin/2026/2298, "
                                   "new-style d-<uuid>, tna.<fclid> — the uri field of gb_tna_caselaw_search rows; a pasted full URL "
                                   "is accepted (prefix and /data.xml suffix stripped)")
    f11.add_argument("--document-uri", dest="document_uri", required=True,
                     help="Document URI (from gb_tna_caselaw_search rows; e.g. ewhc/admin/2026/2298, d-<uuid> or tna.<fclid>)")

    f12 = v.add_parser("gb_tna_caselaw_search", parents=[g()],
                      help="UK court judgments search (The National Archives Find Case Law; keyless)",
                      description="UK judgment search (TNA Find Case Law /atom.xml, keyless): eight upstream params verbatim — "
                                  "party/judge are full-word matches over party/judge names, query is full text, court/tribunal are "
                                  "court codes (repeatable, exploded); order in ±date/±updated/±transformation; per_page politeness "
                                  "cap 50 (=upstream default). Rows carry neutral_citation (e.g. [2026] EWHC 2298 (Admin)), uri "
                                  "(machine key for gb_tna_caselaw_judgment) and contenthash. Open Justice Licence: commercial reuse OK, "
                                  "bulk computational analysis forbidden without a (free) licence — keep this a targeted search face")
    f12.add_argument("--query", default=None, help="Full-text search (upstream param: query; quoted phrase matches words in order)")
    f12.add_argument("--court", action="append", default=[], metavar="CODE",
                    help="Court code, repeatable (upstream param: court; e.g. uksc ewhc — explode form)")
    f12.add_argument("--tribunal", action="append", default=[], metavar="CODE",
                    help="Tribunal code, repeatable (upstream param: tribunal; alias of court, e.g. eat)")
    f12.add_argument("--party", default=None, help="Party-name word, full match (upstream param: party; e.g. Barclays)")
    f12.add_argument("--judge", default=None, help="Judge-name word, full match (upstream param: judge)")
    f12.add_argument("--order", default=None, choices=["date", "-date", "updated", "-updated", "transformation", "-transformation"],
                    help="Sort (upstream param: order; leading - = newest first; default -date)")
    f12.add_argument("--page", type=int, default=1, help="Page number (upstream param: page; >=1)")
    f12.add_argument("--per-page", dest="per_page", type=int, default=50,
                    help="Rows per page (upstream param: per_page; 1-50 politeness cap = upstream default)")
    f12.add_argument("--minimum-availability", dest="minimum_availability", default=None,
                    choices=["metadata", "document", "full-text"],
                    help="Minimum representation level (upstream param: minimum_availability; default full-text)")

    f13 = v.add_parser("lda_filings", parents=[g()],
                      help="US lobbying filings (LDA; client/registrant dual name face)",
                      description="LDA lobbying-disclosure filings: client_name (lobbied company) / registrant_name (lobbying firm) / filing_year all upstream-verbatim (may combine); page_size hard-clamped 25 — upstream silently returns 25 rows for larger asks (probed 2026-10-26); iterate with --page (true offset pagination)")
    f13.add_argument("--client-name", dest="client_name", default=None, help="Lobbied company name (upstream param: client_name; contains-match)")
    f13.add_argument("--registrant-name", dest="registrant_name", default=None, help="Lobbying firm name (upstream param: registrant_name)")
    f13.add_argument("--filing-year", dest="filing_year", type=int, default=None, help="Filing year from 1999 (upstream param: filing_year)")
    f13.add_argument("--page", type=int, default=None, help="Page number (upstream param: page; each page max 25 rows — upstream hard clamp)")
    f13.add_argument("--ordering", default="-dt_posted", help="Sort (upstream param: ordering; default -dt_posted)")
    f13.add_argument("--limit", type=int, default=20, help="Rows (maps to upstream page_size; 1-25 hard wall — larger asks silently yield 25, probed 2026-10-26)")

    f14 = v.add_parser("sipri_trades_search", parents=[g()],
                      help="Arms transfers, country level (SIPRI; delivered/orders)",
                      description="SIPRI arms transfers: supplier/recipient country names (sugar — resolves numeric EntityId via the 30-day cached country table; names in the raw filter value1 upstream → 500) XOR --filters raw JSON ({\"field\": \"Supplier\"|\"Recipient\", \"listData\": [EntityId]}); pageSize cap 100; country-level face, not company-level")
    f14.add_argument("--filters", default=None, help='Raw filter list, JSON text — e.g. \'[{"field": "Recipient", "listData": [8]}]\' (upstream param: filters; numeric EntityIds only)')
    f14.add_argument("--supplier", default=None, help="Supplier country, full English name (sugar — e.g. United States; XOR with --filters)")
    f14.add_argument("--recipient", default=None, help="Recipient country, full English name (sugar — e.g. Angola; XOR with --filters)")
    f14.add_argument("--type", default="delivered", choices=["delivered", "orders"], help="Measure (upstream param: type; delivered=trend-indicator, orders=orders placed)")
    f14.add_argument("--page", type=int, default=1, help="Page number (upstream param: pageNo)")
    f14.add_argument("--limit", type=int, default=20, help="Rows (upstream param: pageSize; 1-100 cap, upstream probed 2026-10-20)")

FLAT = {
    # legal 0.2.0 flat panel (upstream param names verbatim + our defaults; lambdas only shuttle names across namespaces)
    # csl_screening_list was the first flat command (Wave 7), ecfr_* Wave 8 (both merged on the main side) — folded into the same dispatch table
    "co_sic_sanctions": lambda a: {"where": a.where, "limit": a.limit, "offset": a.offset, "order": a.order},
    "courtlistener_opinions_search": lambda a: {"q": a.q, "case_name": a.case_name,
                                                "court": a.court, "judge": a.judge,
                                                "docket_number": a.docket_number,
                                                "filed_after": a.filed_after,
                                                "filed_before": a.filed_before,
                                                "order_by": a.order_by, "cursor": a.cursor},
    # 0.2.11 UK CMA twin faces (gov.uk search/content API; upstream param names verbatim + our polite tier)
    "csl_screening_list": lambda a: {"name": a.name, "source": a.source, "type": a.type, "limit": a.limit},
    "dgcomp_cases_search": lambda a: {"query": a.query, "name": a.name, "instrument": a.instrument,
                               "text": a.text, "limit": a.limit, "page": a.page},
    "ecfr_search": lambda a: {"q": a.q, "page": a.page, "limit": a.limit, "date": a.date},
    "ecfr_titles": lambda a: {},
    "federalregister_documents": lambda a: {"q": a.q, "startdt": a.startdt, "enddt": a.enddt,
                                       "order": a.order, "page": a.page, "limit": a.limit,
                                       "doc_type": a.doc_type, "agencies": a.agencies,
                                       "cfr_title": a.cfr_title, "cfr_part": a.cfr_part},
    "gb_cma_case": lambda a: {"slug": a.slug},
    "gb_cma_cases": lambda a: {"q": a.q, "count": a.count, "start": a.start},
    "gb_ec_donations": lambda a: {"query": a.query, "from_": a.from_, "to": a.to,
                                  "limit": a.limit, "start": a.start},
    "gb_ec_loans": lambda a: {"query": a.query, "limit": a.limit, "start": a.start},
    # 0.3.8 TNA caselaw two faces (eight upstream-verbatim params; court/tribunal append into lists for explode)
    "gb_tna_caselaw_judgment": lambda a: {"document_uri": a.document_uri},
    "gb_tna_caselaw_search": lambda a: {"query": a.query, "court": a.court, "tribunal": a.tribunal,
                                     "party": a.party, "judge": a.judge, "order": a.order,
                                     "page": a.page, "per_page": a.per_page,
                                     "minimum_availability": a.minimum_availability},
    "lda_filings": lambda a: {"client_name": a.client_name, "registrant_name": a.registrant_name,
                              "filing_year": a.filing_year, "limit": a.limit, "page": a.page,
                              "ordering": a.ordering},
    "sipri_trades_search": lambda a: {"filters": a.filters, "supplier": a.supplier,
                                   "recipient": a.recipient, "type": a.type,
                                   "page": a.page, "limit": a.limit},
}


# 0.3.10 jurisdiction chapter: face → jurisdiction (default = issuing authority's jurisdiction; institutions
# covering global phenomena = GLOBAL; vocabulary ISO-3166 alpha-2 + EU + GLOBAL) —— merged by the root cli.py
# into _JURISDICTION, the success envelope carries a jurisdiction chapter
COUNTRY = {
    "co_sic_sanctions": "CO",
    "courtlistener_opinions_search": "US",
    "csl_screening_list": "US",
    "dgcomp_cases_search": "EU",
    "ecfr_search": "US",
    "ecfr_titles": "US",
    "federalregister_documents": "US",
    "gb_cma_case": "GB",
    "gb_cma_cases": "GB",
    "gb_ec_donations": "GB",
    "gb_ec_loans": "GB",
    "gb_tna_caselaw_judgment": "GB",
    "gb_tna_caselaw_search": "GB",
    "lda_filings": "US",
    "sipri_trades_search": "GLOBAL",
}
