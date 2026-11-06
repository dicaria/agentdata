"""legal cli — domain command-face registration (split per domain in 0.2.6, migrated from the root cli.py; purely flat since the 0.3.0 verb-layer + frozen-alias removal).

register(v, g): registers flat commands onto the domain subparser (g = root _leaf_globals factory,
passed in as a parameter to avoid a cli <-> domain-cli cycle); FLAT = flat dispatch table, merged by the root cli for main to use.
"""
import argparse

from . import in_sebi  # the 11-category choice list rides the provider's verbatim map

def register(v, g):
    # Flat commands (2026-10-23 ruling: verb layer abolished across all domains, <domain> <source>_<dataset> direct; new capabilities are born flat)
    # —— 0.3.21 debarment-roster line (afdb/ca_sema/idb/wb, dictionary slots: afdb first, ca_sema second) ——
    fa = v.add_parser("afdb_debarred_entities", parents=[g()],
                      help="African Development Bank debarred entities (afdb.org json-feed, local full-register scan)",
                      description="AfDB debarment register (keyless): the whole 1,440-row feed (FIRM 1,196 / "
                                  "INDIVIDUAL 244) is pulled once, cached 24h and scanned locally. Basis = the "
                                  "cross-debarment edge (CROSS DEBARMENT : WBG / CROSS-DEBARMENT: ADB — upstream "
                                  "spacing inconsistent, so --basis is a contains-match on the bank token: WBG/ADB/"
                                  "IDB/EBRD); To empty = ongoing. Empty result = clean screening (legitimate answer)")
    fa.add_argument("--name", default=None, help="Entity/individual name (substring, case-insensitive, over Name)")
    fa.add_argument("--type", default=None, choices=["FIRM", "INDIVIDUAL"], help="Subject type (upstream value domain, exact: Type column)")
    fa.add_argument("--basis", default=None, help="Debarment basis, substring over Basis — filter on the bank token (WBG/ADB/IDB/EBRD; punctuation upstream is inconsistent)")
    fa.add_argument("--limit", type=int, default=20, help="Rows to return (default 20, ≤100 local payload wall; total_matched echoes the full count)")

    # —— 0.3.47 AT RIS OGD faces (dictionary slot: at_ris between afdb and br_bacen; legal's first AT face) ——
    fa0j = v.add_parser("at_ris_judgments", parents=[g()],
                        help="Austrian case law — RIS Judikatur over the keyless OGD API v2.6 (data.bka.gv.at, ~1.01M documents / 16 court shards)",
                        description="RIS Judikatur (keyless, CC BY 4.0): 16 exact-case court shards — Justiz "
                                    "(OGH/OLG/LG/BG merged, default) 138,516 / Vwgh 357,753 / Bvwg 292,078 / Lvwg "
                                    "78,286 / AsylGH 53,113 / Uvs 25,939 / Vfgh 24,177 / Normenliste 14,676 / Verg "
                                    "8,143 / Dok 4,873 / Ubas 4,052 / Pvak 2,550 / Dsk 1,891 / Gbk 1,067 / Bks 745 / "
                                    "Umse 742 (census 2026-11-03, daily drift). Applikation is CASE-SENSITIVE "
                                    "(Vwgh answers 200; VWGH is answered by a schema-validation Error body; the "
                                    "boolean-flag form ?Vwgh=true is silently ignored and quietly answers Justiz) — "
                                    "the local closed-set wall saves the request. Page size is pinned at 20 upstream "
                                    "(DokumenteProSeite=3/10/50/100 all fail schema validation; --limit is a local "
                                    "slice); beyond the last page the upstream answers HTTP 500, not an empty page — "
                                    "read total and page inside ceil(total/20). Rows carry ECLI verbatim and document "
                                    "coordinates; full texts ride the ogd.ris.bka.gv.at URLs")
    fa0j.add_argument("--court", default="Justiz",
                      choices=["Justiz", "Vwgh", "Bvwg", "Lvwg", "AsylGH", "Uvs", "Vfgh", "Normenliste",
                               "Verg", "Dok", "Ubas", "Pvak", "Dsk", "Gbk", "Bks", "Umse"],
                      help="Court shard, exact upstream case (16-value closed set; default Justiz = OGH/OLG/LG/BG merged)")
    fa0j.add_argument("--q", default=None, help="Suchworte full-text search (GmbH → 1,208 Rechtssatz documents)")
    fa0j.add_argument("--case-number", default=None, help="Geschaeftszahl in the case's own spacing (2 Ob 52/16k → the Rechtssatz family, 27 rows)")
    fa0j.add_argument("--norm", default=None, help="Norm citation axis")
    fa0j.add_argument("--date-from", default=None, help="Entscheidungsdatum window start (YYYY-MM-DD)")
    fa0j.add_argument("--date-to", default=None, help="Entscheidungsdatum window end (YYYY-MM-DD)")
    fa0j.add_argument("--page", type=int, default=1, help="Seitennummer, 1-based (page size pinned at 20 upstream)")
    fa0j.add_argument("--limit", type=int, default=20, help="Rows to return (default 20, 1-100 local slice; the upstream page is pinned at 20)")

    fa0s = v.add_parser("at_ris_statutes", parents=[g()],
                        help="Consolidated Austrian federal law — RIS Bundesrecht/BrKons over the keyless OGD API v2.6 (442,058 documents)",
                        description="RIS Bundesrecht?Applikation=BrKons (keyless, CC BY 4.0): the consolidated "
                                    "federal-law shard, 442,058 documents (census 2026-11-03; Suchworte=GmbH → "
                                    "6,908). Rows are the BrKons projection: NOR id, Kurztitel/Titel, ELI canonical "
                                    "link, Kundmachungsorgan + Stammnorm/Novellen BGBl citation axes, Typ, "
                                    "Art/Paragraph, and the validity window — Ausserkrafttretensdatum is present-only "
                                    "(in-force norms carry none). Page size pinned at 20 upstream; the "
                                    "beyond-last-page HTTP-500 wall matches Judikatur")
    fa0s.add_argument("--q", default=None, help="Suchworte full-text search (GmbH → 6,908 documents)")
    fa0s.add_argument("--page", type=int, default=1, help="Seitennummer, 1-based (page size pinned at 20 upstream)")
    fa0s.add_argument("--limit", type=int, default=20, help="Rows to return (default 20, 1-100 local slice; the upstream page is pinned at 20)")

    # —— 0.3.38 BR BACEN special-regimes face (dictionary slot: br_bacen between afdb and ca_sema) ——
    fb0c = v.add_parser("br_bacen_complaints", parents=[g()],
                        help="Brazil BACEN rdrweb complaint-index ranking — consumer complaints analysed and closed per period (2014→, banks quarterly / consortiums semi-annually)",
                        description="BACEN rdrweb ranking (keyless, www3.bcb.gov.br): the period catalog "
                                    "(/rest/ext/ranking, 2014→2026) is the axis — (ano, periodicidade, periodo, "
                                    "tipo) is validated against it and a ghost combination answers with the "
                                    "available combos (upstream would answer HTTP 204 with a 0-byte body); defaults "
                                    "ride the catalog's latest slot for the tipo. One semicolon CSV per period "
                                    "(cp1252): Índice (comma decimal) is computed only for ranked institutions — "
                                    "honest blanks become null; schema drifts by era, rows keep the columns the "
                                    "file carries. tipo=banks (Bancos e financeiras) or consortiums (Consorcios — "
                                    "CNPJ root on every row)")
    fb0c.add_argument("--name", default=None, help="Institution/administradora name (substring, case-insensitive)")
    fb0c.add_argument("--ano", default=None, help="Reference year (default: the catalog's latest; validated against the catalog)")
    fb0c.add_argument("--periodicidade", default=None, help="Periodicity verbatim from the catalog (TRIMESTRAL/SEMESTRAL/MENSAL/BIMESTRAL), validated WITHIN the resolved year (default: latest slot)")
    fb0c.add_argument("--periodo", default=None, help="Period number within the year (e.g. 3 = Q3 for TRIMESTRAL), validated within the resolved year+periodicidade (default: latest slot)")
    fb0c.add_argument("--tipo", default="banks", choices=["banks", "consortiums"],
                      help="Register branch: banks = Bancos e financeiras, consortiums = Consorcios (default banks)")
    fb0c.add_argument("--cnpj", default=None, help="8-digit CNPJ root or 14-digit whole key (matched on the first 8 digits)")
    fb0c.add_argument("--limit", type=int, default=20, help="Rows to return (default 20, ≤100 local payload wall; total_matched echoes the full count)")

    fb0 = v.add_parser("br_bacen_regimes", parents=[g()],
                       help="Brazil BACEN special-regimes register — institutions under state administration (LIQUIDAÇÃO EXTRAJUDICIAL)",
                       description="BACEN regimes_especiais (keyless, the legal domain's first BR face): the whole "
                                   "25-row register is pulled once, cached 24h and scanned locally — every row is "
                                   "LIQUIDAÇÃO EXTRAJUDICIAL (extrajudicial liquidation), Inicio 2013→2026, with the "
                                   "liquidation's own contact block (responsavel/emails/telefones). cnpj accepts the "
                                   "8-digit root or the 14-digit whole key (both on every row). Empty result = no "
                                   "special regime on record (legitimate answer)")
    fb0.add_argument("--name", default=None, help="Institution name (substring, case-insensitive, over NomeInstituicao)")
    fb0.add_argument("--cnpj", default=None, help="8-digit CNPJ root or 14-digit whole key (exact, matched against both)")
    fb0.add_argument("--uf", default=None, help="2-letter state code (exact, e.g. SP)")
    fb0.add_argument("--limit", type=int, default=20, help="Rows to return (default 20, ≤100 local payload wall; total_matched echoes the full count)")

    fb = v.add_parser("ca_sema_sanctions", parents=[g()],
                      help="Canada SEMA sanctions listings (Global Affairs consolidated list: persons/entities/ships)",
                      description="Canada SEMA sanctions (Consolidated Canadian Autonomous Sanctions List, keyless "
                                  "sema-lmes.xml): 5,708 live listings — persons 3,526 / entities 2,181 of which 731 "
                                  "ships with an IMO number (the join key onto shipping rosters). Bilingual cells "
                                  "verbatim (\"Syria / Syrie\"); name screening contains-matches name + aliases "
                                  "(matched_on echoes the hit face). Empty result = clean screening (legitimate answer)")
    fb.add_argument("--name", default=None, help="Designated name (substring, case-insensitive, over name + aliases)")
    fb.add_argument("--country", default=None, help="Country, substring over the bilingual cell (Syria and Syrie both hit)")
    fb.add_argument("--limit", type=int, default=20, help="Rows to return (default 20, ≤100 local payload wall; total_matched echoes the full count)")

    # —— 0.3.31 CFPB consumer-complaint faces (dictionary slot: cfpb between ca_sema and co_sic) ——
    f_cfpb = v.add_parser("cfpb_complaints", parents=[g()],
                          help="US CFPB consumer complaints search (consumerfinance.gov CCDB, ~18.9M complaints)",
                          description="US CFPB consumer-complaint database search (keyless, CC0; the corpus is "
                                      "re-indexed daily). TWO company channels with different semantics: "
                                      "--search-term is the FUZZY one (with --field company it matches company "
                                      "names loosely), while --company is EXACT and case-sensitive — the corpus' "
                                      "own spelling ('TRANSUNION INTERMEDIATE HOLDINGS, INC.'), not the brand; "
                                      "resolve a brand with cfpb_suggest_company first. Array filters are "
                                      "repeatable (--state TX --state CA). --aggregations opts into the upstream "
                                      "aggregation block (a corpus-wide value census, ~380KB/~20s upstream)")
    f_cfpb.add_argument("--search-term", default=None, help="Full-text term (upstream param: search_term; fuzzy)")
    f_cfpb.add_argument("--field", default=None, choices=["company", "all"], help="Field the search term hits (upstream param: field; only with --search-term)")
    f_cfpb.add_argument("--company", action="append", default=None, help="Company, EXACT + case-sensitive (upstream param: company; repeatable; the corpus' own spelling)")
    f_cfpb.add_argument("--product", action="append", default=None, help="Product (upstream param: product; repeatable; free text)")
    f_cfpb.add_argument("--issue", action="append", default=None, help="Issue (upstream param: issue; repeatable; free text)")
    f_cfpb.add_argument("--state", action="append", default=None, help="State code, e.g. TX (upstream param: state; repeatable; uppercased locally)")
    f_cfpb.add_argument("--zip-code", action="append", default=None, help="ZIP code (upstream param: zip_code; repeatable)")
    f_cfpb.add_argument("--submitted-via", action="append", default=None, help="Submission channel: Web/Referral/Phone/Postal mail/Fax/Email (upstream param: submitted_via; repeatable)")
    f_cfpb.add_argument("--timely", action="append", default=None, help="Timely response: Yes/No (upstream param: timely; repeatable)")
    f_cfpb.add_argument("--company-response", action="append", default=None, help="Company response (upstream param: company_response; repeatable)")
    f_cfpb.add_argument("--company-public-response", action="append", default=None, help="Company public response (upstream param: company_public_response; repeatable)")
    f_cfpb.add_argument("--tags", action="append", default=None, help="Tag (upstream param: tags; repeatable)")
    f_cfpb.add_argument("--date-received-min", default=None, help="Received on/after YYYY-MM-DD (upstream param: date_received_min)")
    f_cfpb.add_argument("--date-received-max", default=None, help="Received on/before YYYY-MM-DD (upstream param: date_received_max)")
    f_cfpb.add_argument("--company-received-min", default=None, help="Company received on/after YYYY-MM-DD (upstream param: company_received_min)")
    f_cfpb.add_argument("--company-received-max", default=None, help="Company received on/before YYYY-MM-DD (upstream param: company_received_max)")
    f_cfpb.add_argument("--frm", type=int, default=None, help="Row offset (upstream param: frm; 0-100000)")
    f_cfpb.add_argument("--size", type=int, default=10, help="Page size (upstream param: size; 1-100, default 10)")
    f_cfpb.add_argument("--sort", default=None, choices=["relevance_desc", "relevance_asc", "created_date_desc", "created_date_asc"], help="Sort (upstream param: sort)")
    f_cfpb.add_argument("--search-after", default=None, help="Pagination token (upstream param: search_after; '<score>_<id>' from break_points)")
    f_cfpb.add_argument("--aggregations", action="store_true", help="Ask for the upstream aggregation block (upstream param: no_aggs=false; corpus-wide value census, ~380KB/~20s upstream)")

    f_cfpb_s = v.add_parser("cfpb_suggest_company", parents=[g()],
                             help="US CFPB company typeahead (consumerfinance.gov — resolves the exact company key)",
                             description="CFPB company typeahead (keyless): resolves a company name to the corpus' "
                                         "own spelling — the key the complaints face's --company filter (exact, "
                                         "case-sensitive) needs. The upstream returns a bare array of company "
                                         "strings. Empty result = the company is not in the complaint corpus")
    f_cfpb_s.add_argument("--text", default=None, help="Company name to resolve (upstream param: text; required)")
    f_cfpb_s.add_argument("--size", type=int, default=10, help="Max suggestions (upstream param: size; 1-100, default 10)")

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

    # —— 0.3.27 gazette face (dictionary slot: gb_gazette between gb_ec_loans and gb_tna_caselaw; registration order == FLAT order) ——
    fg = v.add_parser("gb_gazette_notices", parents=[g()],
                      help="The Gazette notice search (London/Edinburgh/Belfast official record; insolvency preset)",
                      description="The Gazette search face (keyless, OGL; 3.58M notices digitised from 1992): "
                                  "event filtering is by notice code — --noticetypes (+-joined upstream; the "
                                  "noticecode= param is SILENTLY IGNORED, probed 2026-11-03) or --insolvency "
                                  "(the corporate-insolvency chapter: 2404/2408/2410/2411/2414/2421-2424/2431/"
                                  "2432/2607/2702). title = the company name on corporate insolvency codes; "
                                  "placed_by = liquidator/administrator or the edition; geo:Point = the registered "
                                  "office. At least one filter required — a bare search is the 4,887,099-notice "
                                  "bulk wall"
                                  )
    fg.add_argument("--text", default=None, help="Full-text contains (upstream param: text)")
    fg.add_argument("--noticetypes", default=None, help="Notice code(s), +- or comma-joined (upstream param: noticetypes; e.g. 2410+2432 — noticecode= is ignored upstream)")
    fg.add_argument("--insolvency", action="store_true", default=False, help="The corporate-insolvency code chapter preset (union'd with --noticetypes; 2432 liquidator alone = 157,792 live rows)")
    fg.add_argument("--start-date", dest="start_date", default=None, help="Publish window start YYYY-MM-DD (upstream param: start-publish-date)")
    fg.add_argument("--end-date", dest="end_date", default=None, help="Publish window end YYYY-MM-DD (upstream param: end-publish-date)")
    fg.add_argument("--page", type=int, default=1, help="Page (upstream param: results-page)")
    fg.add_argument("--page-size", dest="page_size", type=int, default=20, help="Rows per page (upstream param: results-page-size; 1-100 hard max, probed 2026-11-03)")
    fg.add_argument("--sort", default=None, choices=["latest-date", "oldest-date"], help="Sort (upstream param: sort-by; upstream default latest-date)")

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

    # —— 0.3.21 debarment-roster line cont. (dictionary slot: idb between gb_tna_caselaw_search and lda) ——
    f_idb = v.add_parser("idb_debarred_entities", parents=[g()],
                         help="Inter-American Development Bank sanctioned firms/individuals (data.iadb.org CKAN, server-side)",
                         description="IDB sanctioned-firms register (keyless CKAN DataStore, server-side search; live "
                                     "1,343 rows): q = full-text across all fields, filters = JSON field→value exact "
                                     "matches (e.g. {\"To\": \"Ongoing\"} or {\"Entity\": \"Firm\"}), offset paging, "
                                     "include_total always on. From arrives as nanosecond text kept verbatim "
                                     "(\"2009-07-10 00:00:00.000000000\"); Source carries the cross-debarment markers "
                                     "(ADB/WBG cross debarment). Empty result = clean screening (legitimate answer)")
    f_idb.add_argument("--q", default=None, help="Full-text query across all fields (upstream param: q)")
    f_idb.add_argument("--filters", default=None, help='Field→value exact matches, JSON text — e.g. \'{"To": "Ongoing"}\' (upstream param: filters)')
    f_idb.add_argument("--limit", type=int, default=20, help="Rows (upstream param: limit; 1-100 politeness cap)")
    f_idb.add_argument("--offset", type=int, default=0, help="Row offset (upstream param: offset; total echoes the register size)")
    f_idb.add_argument("--sort", default=None, help="Sort, e.g. 'From desc' (upstream param: sort)")

    # —— 0.3.27 IE defaulters face (dictionary slot: ie_revenue between idb and lda; registration order == FLAT order) ——
    f15 = v.add_parser("ie_revenue_defaulters", parents=[g()],
                       help="Irish Revenue List of Defaulters (statutory quarterly tax-defaulters publication)",
                       description="Irish Revenue defaulters register (keyless): the statutory quarterly "
                                   "publication — TWO row schemas under one list: part 1 = penalties "
                                   "determined by a court (Issue Type/Fine/Sentence/Charges), part 2 = "
                                   "Revenue settlements (Name/Address/County/Occupation + Tax/Interest/"
                                   "Penalties/Total/Unpaid as ints, comma-thousands stripped). One part per "
                                   "call (--part 1|2); --year + --month select the quarter (march/june/"
                                   "september/december, give both or neither) and default to the latest on "
                                   "the index (current year only). Names/addresses are published by statute "
                                   "— the co_sic precedent; CSV carries a UTF-8 BOM and trailing-space "
                                   "headers (normalised)")
    f15.add_argument("--part", type=int, default=1, help="List part, 1 or 2 (1 = court penalties, 2 = Revenue settlements)")
    f15.add_argument("--year", type=int, default=None, help="Publication year (with --month; default = latest quarter on the index)")
    f15.add_argument("--month", default=None, choices=["march", "june", "september", "december"], help="Quarter (with --year; give both or neither)")

    # —— 0.3.35 IN SEBI orders face (dictionary slot: in_sebi between ie_revenue and lda; registration order == FLAT order) ——
    f16 = v.add_parser("in_sebi_orders", parents=[g()],
                       help="SEBI enforcement orders (11 categories; AJAX fragment channel)",
                       description="www.sebi.gov.in/sebiweb enforcement orders: the public listing "
                                   "IGNORES GET paging params — the channel is the stateless AJAX "
                                   "fragment POST (next=n + zero-based doDirect + the site's full "
                                   "16-field body; one uniform shape serves search/dates/categories). "
                                   "11 categories verbatim (default member_orders = Orders of "
                                   "Chairperson/Members, 6,433; ao_orders holds 12,020); --search is "
                                   "the site's own entity filter (Adani → 17); --from-date/--to-date "
                                   "are DD-MM-YYYY (the upstream form's own format); a page past the "
                                   "last answers the CLEAN empty page ('No record(s) available.', "
                                   "nextDel=0) — no snap-back. Rows: date verbatim (Nov 03, 2026) + "
                                   "title + the order PDF url")
    f16.add_argument("--category", default="member_orders", choices=list(in_sebi.CATEGORIES),
                     help="Order category, 11 verbatim (the choice list maps slug→smid; default "
                          "member_orders = Orders of Chairperson/Members)")
    f16.add_argument("--search", default=None,
                     help="Entity filter (upstream param: search; the site's own filter — Adani → 17 records; maxlength 200)")
    f16.add_argument("--from-date", dest="from_date", default=None,
                     help="Window start (upstream param: fromDate; format DD-MM-YYYY — the form's own)")
    f16.add_argument("--to-date", dest="to_date", default=None,
                     help="Window end (upstream param: toDate; format DD-MM-YYYY — the form's own)")
    f16.add_argument("--page", type=int, default=1,
                     help="Page, 1-based (upstream param: doDirect = page-1, zero-based; past the last = the clean empty page)")

    f13 = v.add_parser("lda_filings", parents=[g()],
                      help="US lobbying filings (LDA; client/registrant dual name face)",
                      description="LDA lobbying-disclosure filings: client_name (lobbied company) / registrant_name (lobbying firm) / filing_year all upstream-verbatim (may combine); page_size hard-clamped 25 — upstream silently returns 25 rows for larger asks (probed 2026-10-26); iterate with --page (true offset pagination)")
    f13.add_argument("--client-name", dest="client_name", default=None, help="Lobbied company name (upstream param: client_name; contains-match)")
    f13.add_argument("--registrant-name", dest="registrant_name", default=None, help="Lobbying firm name (upstream param: registrant_name)")
    f13.add_argument("--filing-year", dest="filing_year", type=int, default=None, help="Filing year from 1999 (upstream param: filing_year)")
    f13.add_argument("--page", type=int, default=None, help="Page number (upstream param: page; each page max 25 rows — upstream hard clamp)")
    f13.add_argument("--ordering", default="-dt_posted", help="Sort (upstream param: ordering; default -dt_posted)")
    f13.add_argument("--limit", type=int, default=20, help="Rows (maps to upstream page_size; 1-25 hard wall — larger asks silently yield 25, probed 2026-10-26)")

    # —— 0.3.37 RU CBR warning-list face (dictionary slot: ru_cbr between lda and sipri; registration order == FLAT order) ——
    f_ruw = v.add_parser("ru_cbr_warning_list", parents=[g()],
                         help="Bank of Russia warning list (entities with signs of illegal financial activity)",
                         description="cbr.ru UniDbQuery DownloadExcel export 123126: the WHOLE "
                                     "warning register ships in ONE keyless xlsx GET (~3.1MB, "
                                     "27,635 rows, span 2021-02→, nightly rebuild), cached 24h "
                                     "and scanned locally — upstream publishes no query surface "
                                     "on the export. Rows are the 12 upstream columns verbatim "
                                     "(Excel serials → ISO); the violations column carries SIX "
                                     "canonical kinds (pyramid 14,054 / illegal securities "
                                     "professional 7,356 / illegal lender 2,567 / investment "
                                     "solicitation 116 / platform operator 16 / insurance 57 — "
                                     "rows keep the verbatim Russian wording, --violation splits "
                                     "the cell on commas/newlines); record_type keeps the "
                                     "register's own six-kind vocabulary (Интернет-проект 22,798 "
                                     "/ Юридическое лицо 3,030 / Точка присутствия 924 / Компания "
                                     "818 / ИП 64 / Прочее 1). ИНН present on only ~3,100 rows "
                                     "(internet projects ship none); internet-project rows carry "
                                     "their t.me/*/workers.dev fronts in the ADDRESS column "
                                     "(--site covers both)")
    f_ruw.add_argument("--name", default=None,
                       help="Subject name — substring, case-insensitive (over Название)")
    f_ruw.add_argument("--inn", default=None,
                       help="ИНН digit key, exact match (present on only ~3,100 rows)")
    f_ruw.add_argument("--site", default=None,
                       help="Site/domain — substring, case-insensitive (over Сайт AND Адрес: internet-project rows list their fronts in Адрес)")
    f_ruw.add_argument("--violation", default=None,
                       choices=["pyramid", "illegal_securities_professional", "illegal_lender",
                                "illegal_investment_solicitation", "illegal_platform_operator",
                                "illegal_insurance_activity"],
                       help="Violation kind filter (matched per comma/newline part; rows keep verbatim Russian)")
    f_ruw.add_argument("--type", default=None,
                       choices=["internet_project", "legal_entity", "individual_entrepreneur",
                                "presence_point", "company", "other"],
                       help="Record type (Тип записи: internet_project | legal_entity | individual_entrepreneur | presence_point | company | other)")
    f_ruw.add_argument("--limit", type=int, default=20,
                       help="Rows to return (local payload wall 1-100, default 20; total_matched echoes the full count)")

    f14 = v.add_parser("sipri_trades_search", parents=[g()],
                      help="Arms transfers, country level (SIPRI; delivered/orders)",
                      description="SIPRI arms transfers: supplier/recipient country names (sugar — resolves numeric EntityId via the 30-day cached country table; names in the raw filter value1 upstream → 500) XOR --filters raw JSON ({\"field\": \"Supplier\"|\"Recipient\", \"listData\": [EntityId]}); pageSize cap 100; country-level face, not company-level")
    f14.add_argument("--filters", default=None, help='Raw filter list, JSON text — e.g. \'[{"field": "Recipient", "listData": [8]}]\' (upstream param: filters; numeric EntityIds only)')
    f14.add_argument("--supplier", default=None, help="Supplier country, full English name (sugar — e.g. United States; XOR with --filters)")
    f14.add_argument("--recipient", default=None, help="Recipient country, full English name (sugar — e.g. Angola; XOR with --filters)")
    f14.add_argument("--type", default="delivered", choices=["delivered", "orders"], help="Measure (upstream param: type; delivered=trend-indicator, orders=orders placed)")
    f14.add_argument("--page", type=int, default=1, help="Page number (upstream param: pageNo)")
    f14.add_argument("--limit", type=int, default=20, help="Rows (upstream param: pageSize; 1-100 cap, upstream probed 2026-10-20)")

    # —— 0.3.36 TR SPK enforcement faces (dictionary slot: tr_spk between sipri and us_occ; registration order == FLAT order) ——
    f_tr1 = v.add_parser("tr_spk_bans", parents=[g()],
                         help="SPK capital-market trading bans (persons + companies with banned-ticker edges)",
                         description="ws.spk.gov.tr IslemYasaklari: BOTH walls in one call — "
                                     "persons (295, mkkSicilNo masked '28***449********') + "
                                     "companies (3, mersisNo the 16-digit MERSIS key), each "
                                     "company auto-enriched with its ban edges (pay = the banned "
                                     "equity's issuer, payKodu = the BIST ticker, karar no/date "
                                     "— the substance of the ban; 3 detail GETs on a cold call, "
                                     "then 24h cache). Person rows stay two-column: the person-"
                                     "detail endpoint's key is the UNMASKED MKK number, which "
                                     "the public list masks (pinned 2026-11-04). --name contains-"
                                     "matches person name / company name / the banned issuer "
                                     "(screening the issuer hits the banned party)")
    f_tr1.add_argument("--name", default=None,
                       help="Subject name — substring, case-insensitive (over isimSoyisim / unvani / the banned issuer pay)")
    f_tr1.add_argument("--type", default=None, choices=["person", "company"],
                       help="Wall filter (person | company; default both)")
    f_tr1.add_argument("--limit", type=int, default=20,
                       help="Rows to return (local payload wall 1-100, default 20; total_matched echoes the full count)")

    f_tr2 = v.add_parser("tr_spk_fines", parents=[g()],
                         help="SPK administrative fines (whole register one-shot: 2,281 rows 2016→, local scan)",
                         description="ws.spk.gov.tr TumIdariParaCezalari: the WHOLE fine register "
                                     "ships in ONE keyless GET (1.3MB, 2,281 rows, karar years "
                                     "2016→2026), cached 24h and scanned locally — upstream "
                                     "publishes no query surface (the POST filter body {\"yil\":…} "
                                     "is silently ignored; the by-year GET sibling is redundant). "
                                     "Rows are the 14 upstream columns verbatim; 1,281 of 2,281 "
                                     "subjects are INDIVIDUALS (mkkSicilNo arrives masked — names "
                                     "published in the official register, the co_sic/SEBI PII "
                                     "posture); davaBilgisi Var 682 rides a yargilamaAsamasi "
                                     "lawsuit stage; tutar = the fine in TL (9,321 … "
                                     "362,123,139.86); teblig cites the communiqué clause "
                                     "(yasa/madde near-always null); aciklama carries embedded "
                                     "newlines, verbatim")
    f_tr2.add_argument("--name", default=None,
                       help="Subject name — substring, case-insensitive (over unvan; company or person)")
    f_tr2.add_argument("--year", type=int, default=None,
                       help="Board-decision year, 4 digits (local filter over kurulKararTarihi; 2016-2026 span)")
    f_tr2.add_argument("--limit", type=int, default=20,
                       help="Rows to return (local payload wall 1-100, default 20; total_matched echoes the full count)")

    # —— 0.3.28 OCC enforcement face (dictionary slot: us_occ between sipri and wb; registration order == FLAT order) ——
    f_occ = v.add_parser("us_occ_enforcements", parents=[g()],
                         help="US OCC bank-enforcement releases (monthly news releases; sentence + table schemas)",
                         description="OCC (Office of the Comptroller of the Currency) monthly "
                                     "enforcement-actions news releases (keyless): the by-year "
                                     "news-release listing picks the Enforcement Actions titles "
                                     "(~11-12 a year; listings verified 2005-2026); default = the "
                                     "latest release of the year. TWO body schemas under one face, "
                                     "`form` says which: sentences (2024+) = one row per action with "
                                     "cmp_amount scaled from the '$750 million' wording + docket No. "
                                     "(AA-ENF-YYYY-NN — the official key, joins the EASearch "
                                     "database 1989+, out of SDK scope) + IAP prohibition rows "
                                     "(institution-affiliated parties; names are statutory public "
                                     "disclosures — the co_sic precedent); tables (≤2020) = "
                                     "per-section order rows (No./Name-Bank-City/State/Date). "
                                     "--month selects by month name in any era (2026-era titles carry "
                                     "it, earlier listings' MM/DD/YYYY dates do); --all walks every "
                                     "release of the year")
    f_occ.add_argument("--year", type=int, default=None, help="Listing year, 2005-current (default = the current year)")
    f_occ.add_argument("--month", default=None, help="Release month, full name January..December (default = the latest of the year)")
    f_occ.add_argument("--all", dest="all_year", action="store_true", help="Walk every enforcement release of the year")

    # —— 0.3.21 debarment-roster line cont. (dictionary slot: wb last) ——
    f_wb = v.add_parser("wb_debarred_firms", parents=[g()],
                        help="World Bank debarred firms (SAP gateway full dump, local full-register scan)",
                        description="World Bank debarred-firms register (keyless via the page-embedded public apikey): "
                                    "the whole 1,546-row dump is pulled once, cached 24h and scanned locally (same "
                                    "contract as csl_screening_list). SUPP_ELIG_STAT DEBARRED 890 / X-DEBARRED 656; "
                                    "DEBAR_TO_DATE 2999-12-31 = indefinite; DEBAR_REASON cites the procurement-"
                                    "guidelines clause; China leads at 392 firms. The DNB/REGISTER identifier fields "
                                    "ship empty — name × country is the join channel. Empty result = clean screening "
                                    "(legitimate answer)")
    f_wb.add_argument("--name", default=None, help="Firm name (substring, case-insensitive, over SUPP_NAME)")
    f_wb.add_argument("--country", default=None, help="Country, substring over COUNTRY_NAME or exact LAND1 code (China and CN both hit)")
    f_wb.add_argument("--type", default=None, choices=["F", "I", "U", "C"], help="Supplier type (SUPP_TYPE_CODE: F firm / I individual / U unspecified / C conglomerate)")
    f_wb.add_argument("--limit", type=int, default=20, help="Rows to return (default 20, ≤100 local payload wall; total_matched echoes the full count)")

FLAT = {
    # legal 0.2.0 flat panel (upstream param names verbatim + our defaults; lambdas only shuttle names across namespaces)
    # csl_screening_list was the first flat command (Wave 7), ecfr_* Wave 8 (both merged on the main side) — folded into the same dispatch table
    # 0.3.21 debarment-roster line: afdb/ca_sema head slots, idb/wb tail slots (dictionary order)
    "afdb_debarred_entities": lambda a: {"name": a.name, "type": a.type, "basis": a.basis, "limit": a.limit},
    # 0.3.47 AT RIS OGD faces (dictionary slot: at_ris between afdb and br_bacen; registration order == FLAT order)
    "at_ris_judgments": lambda a: {"court": a.court, "q": a.q, "case_number": a.case_number,
                                   "norm": a.norm, "date_from": a.date_from, "date_to": a.date_to,
                                   "page": a.page, "limit": a.limit},
    "at_ris_statutes": lambda a: {"q": a.q, "page": a.page, "limit": a.limit},
    # 0.3.38 BR BACEN special-regimes face (dictionary slot: br_bacen between afdb and ca_sema)
    "br_bacen_complaints": lambda a: {"name": a.name, "ano": a.ano, "periodicidade": a.periodicidade,
                                      "periodo": a.periodo, "tipo": a.tipo, "cnpj": a.cnpj, "limit": a.limit},
    "br_bacen_regimes": lambda a: {"name": a.name, "cnpj": a.cnpj, "uf": a.uf, "limit": a.limit},
    "ca_sema_sanctions": lambda a: {"name": a.name, "country": a.country, "limit": a.limit},
    # 0.3.31 CFPB consumer-complaint faces (dictionary slot: cfpb between ca_sema and co_sic)
    "cfpb_complaints": lambda a: {"search_term": a.search_term, "field": a.field,
                                   "company": a.company, "product": a.product, "issue": a.issue,
                                   "state": a.state, "zip_code": a.zip_code,
                                   "submitted_via": a.submitted_via, "timely": a.timely,
                                   "company_response": a.company_response,
                                   "company_public_response": a.company_public_response, "tags": a.tags,
                                   "date_received_min": a.date_received_min,
                                   "date_received_max": a.date_received_max,
                                   "company_received_min": a.company_received_min,
                                   "company_received_max": a.company_received_max,
                                   "frm": a.frm, "size": a.size, "sort": a.sort,
                                   "search_after": a.search_after, "aggregations": a.aggregations},
    "cfpb_suggest_company": lambda a: {"text": a.text, "size": a.size},
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
    # 0.3.27 gazette face (dictionary slot: gb_gazette between gb_ec_loans and gb_tna_caselaw)
    "gb_gazette_notices": lambda a: {"text": a.text, "noticetypes": a.noticetypes, "insolvency": a.insolvency,
                                     "start_date": a.start_date, "end_date": a.end_date,
                                     "page": a.page, "page_size": a.page_size, "sort": a.sort},
    # 0.3.8 TNA caselaw two faces (eight upstream-verbatim params; court/tribunal append into lists for explode)
    "gb_tna_caselaw_judgment": lambda a: {"document_uri": a.document_uri},
    "gb_tna_caselaw_search": lambda a: {"query": a.query, "court": a.court, "tribunal": a.tribunal,
                                     "party": a.party, "judge": a.judge, "order": a.order,
                                     "page": a.page, "per_page": a.per_page,
                                     "minimum_availability": a.minimum_availability},
    "idb_debarred_entities": lambda a: {"q": a.q, "filters": a.filters, "limit": a.limit,
                                        "offset": a.offset, "sort": a.sort},
    # 0.3.27 IE defaulters face (dictionary slot: ie_revenue between idb and lda)
    "ie_revenue_defaulters": lambda a: {"part": a.part, "year": a.year, "month": a.month},
    # 0.3.35 IN SEBI orders face (dictionary slot: in_sebi between ie_revenue and lda)
    "in_sebi_orders": lambda a: {"category": a.category, "search": a.search,
                                 "from_date": a.from_date, "to_date": a.to_date, "page": a.page},
    "lda_filings": lambda a: {"client_name": a.client_name, "registrant_name": a.registrant_name,
                              "filing_year": a.filing_year, "limit": a.limit, "page": a.page,
                              "ordering": a.ordering},
    # 0.3.37 RU CBR warning-list face (dictionary slot: ru_cbr between lda and sipri)
    "ru_cbr_warning_list": lambda a: {"name": a.name, "inn": a.inn, "site": a.site,
                                      "violation": a.violation, "type": a.type, "limit": a.limit},
    "sipri_trades_search": lambda a: {"filters": a.filters, "supplier": a.supplier,
                                   "recipient": a.recipient, "type": a.type,
                                   "page": a.page, "limit": a.limit},
    # 0.3.36 TR SPK enforcement faces (dictionary slot: tr_spk between sipri and us_occ)
    "tr_spk_bans": lambda a: {"name": a.name, "type": a.type, "limit": a.limit},
    "tr_spk_fines": lambda a: {"name": a.name, "year": a.year, "limit": a.limit},
    # 0.3.28 OCC enforcement face (dictionary slot: us_occ between sipri and wb)
    "us_occ_enforcements": lambda a: {"year": a.year, "month": a.month, "all_year": a.all_year},
    "wb_debarred_firms": lambda a: {"name": a.name, "country": a.country, "type": a.type, "limit": a.limit},
}


# 0.3.10 jurisdiction chapter: face → jurisdiction (default = issuing authority's jurisdiction; institutions
# covering global phenomena = GLOBAL; vocabulary ISO-3166 alpha-2 + EU + GLOBAL) —— merged by the root cli.py
# into _JURISDICTION, the success envelope carries a jurisdiction chapter
COUNTRY = {
    # 0.3.21: MDB debarment rosters = GLOBAL (cross-national registers, wb_procnotices precedent); CA SEMA = CA
    "afdb_debarred_entities": "GLOBAL",
    # 0.3.47 AT RIS OGD: data.bka.gv.at is Austria's federal legal register
    "at_ris_judgments": "AT",
    "at_ris_statutes": "AT",
    "br_bacen_complaints": "BR",
    "br_bacen_regimes": "BR",
    "ca_sema_sanctions": "CA",
    "cfpb_complaints": "US",
    "cfpb_suggest_company": "US",
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
    "gb_gazette_notices": "GB",
    "gb_tna_caselaw_judgment": "GB",
    "gb_tna_caselaw_search": "GB",
    "idb_debarred_entities": "GLOBAL",
    "ie_revenue_defaulters": "IE",
    "in_sebi_orders": "IN",
    "lda_filings": "US",
    "ru_cbr_warning_list": "RU",
    "sipri_trades_search": "GLOBAL",
    "tr_spk_bans": "TR",
    "tr_spk_fines": "TR",
    "us_occ_enforcements": "US",
    "wb_debarred_firms": "GLOBAL",
}
