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

    # —— 0.3.60 AU FRL titles face (dictionary slot: au_frl between at_ris and br_bacen; legal's first AU face) ——
    f_aufrl = v.add_parser("au_frl_titles", parents=[g()],
                           help="Australian Federal Register of Legislation titles (OPC OData v1, keyless — 13,754 Acts)",
                           description="AU Federal Register of Legislation (keyless, the Office of Parliamentary "
                                       "Counsel's OData v1 service api.prod.legislation.gov.au/v1): the register of "
                                       "Commonwealth Acts (13,754 titles live, measured 2026-11-13) plus Notifiable "
                                       "Legislation and Compilations. --collection filters on the register's own "
                                       "collection; --term rides the OData $search full-text query (a quoted phrase is "
                                       "honoured). Rows carry the title id (the canonical FRL key), the making date, "
                                       "the in-force flag and the status history with the amending/repealing titles "
                                       "named. LIVE LAW: the $-prefixed OData option names must NOT be percent-encoded "
                                       "(the gateway answers 400 on %24top) and the bare host api.legislation.gov.au "
                                       "resets TLS — the prod host is pinned")
    f_aufrl.add_argument("--collection", default=None, choices=["Act", "Notifiable Legislation", "Compilation"],
                         help="Register collection (the upstream's own vocabulary; omit for the whole register)")
    f_aufrl.add_argument("--term", default=None, help="Full-text search term (upstream $search; a quoted phrase is honoured)")
    f_aufrl.add_argument("--top", type=int, default=20, help="Rows to return (upstream $top; 1-1000)")

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

    # —— 0.3.60 BR CADE pesquisa avançada face (dictionary slot: br_cade between br_bacen and ca_asc) ——
    f_cade = v.add_parser("br_cade_pesquisa_avancada", parents=[g()],
                          help="Brazil CADE case register (the council's own Pesquisa Avançada proxy, keyless form POST)",
                          description="CADE pesquisa avançada (keyless, pesquisaavancada.cade.gov.br): one form POST per "
                                      "module — apac = Ato de Concentração (90 proceedings), tcc = Requerimento de TCC "
                                      "(476), consulta = the general consultation surface (74); sizes measured live "
                                      "2026-11-13. --name is the upstream party filter (txtInteressado, server-side: "
                                      "\"JBS\" → 2 rows), --protocol the process number (txtProtocoloPesquisa). LIVE "
                                      "LAWS: every scalar in the answer is BASE64 with MIXED UTF-8/cp1252 bytes (the "
                                      "decoder tries UTF-8 strict first, falls back to cp1252, keeps only printable "
                                      "results); the upstream's date fields are DECORATIVE (a fixed window is echoed "
                                      "back whatever is sent) so they are not sent as filters and no date filtering "
                                      "is claimed")
    f_cade.add_argument("--name", default=None, help="Party name filter (upstream field: txtInteressado; server-side)")
    f_cade.add_argument("--module", default="apac", choices=["apac", "tcc", "consulta"],
                        help="Register module (apac = Ato de Concentração, tcc = Requerimento de TCC, consulta = general consultation)")
    f_cade.add_argument("--protocol", default=None, help="Process protocol number (upstream field: txtProtocoloPesquisa)")
    f_cade.add_argument("--limit", type=int, default=50, help="Rows to return (default 50; the upstream page is capped at 500)")

    # —— 0.3.58 CA provincial securities pair (dictionary slot: ca_asc_enforcement < ca_bcsc_disciplined < ca_sema_sanctions; the AMF sibling is DEFERRED — lautorite.qc.ca CF-403s non-browser clients) ——
    fa = v.add_parser("ca_asc_enforcement", parents=[g()],
                      help="Alberta Securities Commission enforcement library (notices/decisions/orders, keyless Coveo chain)",
                      description="ASC enforcement library (7,304 documents 2001→today, keyless): the site's "
                                  "own headless chain — a fresh Coveo token, then the cloud query with the "
                                  "noticesdecisionsordersenforcement pipeline. Every document is answered 3× "
                                  "per page; rows are DEDUPED by document URL (duplicates_dropped counts the "
                                  "copies). Legacy rows carry raw file-path titles (kept verbatim, flagged); "
                                  "cm.asc.ca PDFs answer 403 to non-browser clients — metadata + link only. "
                                  "Issuer (z95xefissuer) is the company channel")
    fa.add_argument("--q", default=None, help="Full-text term (upstream body: q; empty = browse the whole library, newest first)")
    fa.add_argument("--limit", type=int, default=20, help="Documents to return (upstream body: numberOfResults; local wall 100 — Coveo's own is 1000)")

    fbq = v.add_parser("ca_bcsc_disciplined", parents=[g()],
                       help="BC Securities Commission Disciplined Parties (form-POST SearchTable; --q party name)",
                       description="BCSC Disciplined List (1,834 rows live, keyless): parties sanctioned "
                                   "under the Securities Act (BC). --q searches title + item name + other "
                                   "names (three SearchFields upstream); --party-type facets on the site's "
                                   "own dimension ('Company' → 532); date desc fixed. Date normalized "
                                   "'Nov 2, 2026'→ISO; detail/PDF links absolutized to www.bcsc.bc.ca. "
                                   "Zero hits = clean screening (a legal answer)")
    fbq.add_argument("--q", default=None, help="Party-name term (upstream form: search[value]; empty = the full library)")
    fbq.add_argument("--party-type", dest="party_type", default=None, help="Party-type facet (upstream form: Facets[0][SelectedValues]; 'Company' measured → 532 — the vocabulary is the site's own facet, not enumerable from the endpoint)")
    fbq.add_argument("--limit", type=int, default=20, help="Rows to return (upstream form: length; Datatables page size, wall 100)")
    fbq.add_argument("--offset", type=int, default=0, help="Row offset (upstream form: start)")

    # —— 0.3.60 CA CBSA advance-ruling pair (dictionary slot: ca_asc_enforcement < ca_bcsc_disciplined < ca_cbsa_ruling < ca_cbsa_rulings < ca_sema_sanctions) ——
    f_cbsad = v.add_parser("ca_cbsa_ruling", parents=[g()],
                            help="One CBSA national tariff-classification advance ruling (CARM ruling details, keyless)",
                            description="CBSA advance-ruling detail (keyless, ccp-pcc.cbsa-asfc.cloud-nuage.canada.ca): one "
                                        "ruling by its rulingsId (from the ca_cbsa_rulings list face). LIVE LAW: lang=en is "
                                        "MANDATORY (the service answers 400 without it) — it is baked into the op path; the "
                                        "text fields carry \"&&\" as the line separator and HTML entities (the parser turns "
                                        "\"&&\" into newlines and unescapes them). The applicant block names the importer: "
                                        "the first line is the contact person, the second the company (the company join "
                                        "surface)")
    f_cbsad.add_argument("--rulings-id", dest="rulings_id", required=True,
                         help="Ruling id from ca_cbsa_rulings (e.g. 8000001670)")

    f_cbsal = v.add_parser("ca_cbsa_rulings", parents=[g()],
                            help="CBSA national tariff-classification advance rulings (1,234 live, keyless)",
                            description="CBSA national advance rulings (keyless, the CARM public-rulings list): 1,234 rulings "
                                        "live, measured 2026-11-13. LIVE LAW: the lang query parameter is MANDATORY (400 "
                                        "without it) — it is baked into the op path. The list is the whole register; the "
                                        "face pages it locally. Rows carry the rulingsId (the key into the detail face), the "
                                        "HS classification number, the date, the product and the ruling type")
    f_cbsal.add_argument("--limit", type=int, default=50, help="Rows to return (default 50; local slice of the whole register)")
    f_cbsal.add_argument("--offset", type=int, default=0, help="Row offset (local slice of the whole register)")

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

    # —— 0.3.59 执法党产簇 first slice: CH pair (dictionary slot: cfpb < ch_efk < ch_finma < co_sic) ——
    f_efk = v.add_parser("ch_efk_party_financings", parents=[g()],
                         help="Swiss EFK party financing disclosure tree (politikfinanzierung.efk.admin.ch)",
                         description="Swiss political party financing disclosure (keyless, Federal Finance "
                                     "Administration): per year × party × disclosure form — annual income "
                                     "disclosure and individual grants over CHF 15,000 — with the campaign "
                                     "download URL. Language tree walled de/fr/it (no segment 404s); "
                                     "year/actor filters run client-side (the tree is small)")
    f_efk.add_argument("--lang", default="de", choices=["de", "fr", "it"], help="Language tree (path segment; 'de' measured)")
    f_efk.add_argument("--year", default=None, help="Year label filter, e.g. 2025 (client-side, exact)")
    f_efk.add_argument("--actor", default=None, help="Party-name substring filter (client-side)")

    f_finma = v.add_parser("ch_finma_enforcement_news", parents=[g()],
                           help="FINMA news & enforcement search (Sitecore CMS form-POST; --q required)",
                           description="FINMA news search (keyless): press releases, enforcement news, "
                                       "publications — 'enforcement' → 125 hits live. The query term is "
                                       "MANDATORY (empty query answers Count 0 — live law 2026-11-13); "
                                       "the page window is upstream-fixed at 20 rows (--offset = Skip in "
                                       "the URL query; body Skip is ignored); MaxResultCount 1000 — bigger "
                                       "terms need date-window partitioning")
    f_finma.add_argument("--q", required=True, help="Search term (upstream form: query; non-empty is live law)")
    f_finma.add_argument("--lang", default="en", choices=["en", "de"], help="CMS language tree ('en' measured)")
    f_finma.add_argument("--limit", type=int, default=20, help="Rows to return (local slice of the 20-row upstream window; wall 1-20)")
    f_finma.add_argument("--offset", type=int, default=0, help="Row offset (URL query Skip; body Skip ignored upstream)")

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

    # —— 0.3.60 DE lobby-register face (dictionary slot: de_lobbyregister between csl_screening_list and dgcomp_cases_search; legal's first DE face) ——
    f_lob = v.add_parser("de_lobbyregister_entries", parents=[g()],
                          help="German Bundestag lobby register (keyless JSON export — 7,044 entries, money columns)",
                          description="Lobbyregister des Deutschen Bundestages (keyless, the /sucheJson export): 7,044 "
                                      "register entries live, measured 2026-11-13. The official REST API (v1/v2) is "
                                      "ApiKey-gated, so it is NOT on the route — this export is the machine-readable "
                                      "surface. LIVE LAW: the export carries NO server-side filter, so the whole 18 MB "
                                      "register is read once (cached 24 h) and filtered locally. Rows carry the register "
                                      "number, the identity (ORGANIZATION | PERSON), the active flag, the codex-violations "
                                      "flag, the employee FTE and — the compliance-grade part — the money columns "
                                      "(financialExpensesEuro / totalDonationsEuro / totalMembershipFees) and the "
                                      "project/statement/contract counts")
    f_lob.add_argument("--name", default=None, help="Lobbyist name (substring, case-insensitive; local scan)")
    f_lob.add_argument("--active", default=None, choices=["true", "false"],
                        help="Active-lobbyist flag (the register's own accountDetails.activeLobbyist; local scan)")
    f_lob.add_argument("--identity", default=None, choices=["ORGANIZATION", "PERSON"],
                        help="Identity kind (the register's own lobbyistIdentity.identity; local scan)")
    f_lob.add_argument("--codex-violations", dest="codex_violations", default=None, choices=["true", "false"],
                        help="Codex-violations flag (the register's own accountHasCodexViolations; local scan)")
    f_lob.add_argument("--legislation", default=None, help="Legislation reference (the register's own registerEntryDetails.legislation; exact)")
    f_lob.add_argument("--limit", type=int, default=50, help="Rows to return (default 50; local slice)")
    f_lob.add_argument("--offset", type=int, default=0, help="Row offset (local slice)")

    f3 = v.add_parser("dgcomp_cases_search", parents=[g()],
                      help="EU competition cases (DG COMP; aid/antitrust/merger/DMA)",
                      description="DG COMP case search: --query raw ES bool DSL (JSON text, XOR with sugar) XOR --name/--instrument sugar (assembles the SPA's three-field text query / caseInstrument term); pageSize hard cap 100 — upstream silently returns 100 rows for larger asks (probed 2026-10-26)")
    f3.add_argument("--query", default=None, help='Raw ES bool DSL, JSON text — e.g. \'{"bool": {"must": [{"term": {"caseInstrument": "SA"}}]}}\' (upstream param: query)')
    f3.add_argument("--name", default=None, help="Sugar — party/case-name text query over caseTitle/caseCompanies/caseOriginalTitle (XOR with --query)")
    f3.add_argument("--instrument", default=None, help="Case-type filter: AT antitrust / M merger / SA state aid / DMA Digital Markets Act (sugar channel)")
    f3.add_argument("--text", default="", help="Extra full-text condition (upstream param: text; empty = none)")
    f3.add_argument("--page", type=int, default=1, help="Page number (upstream param: pageNumber)")
    f3.add_argument("--limit", type=int, default=20, help="Rows (upstream param: pageSize; 1-100 hard wall — 200 silently yields 100, probed 2026-10-26)")

    # —— 0.3.60 DK Finanstilsynet supervision-archive face (dictionary slot: dk_ft between dgcomp_cases_search and ecfr_search; legal's first DK face) ——
    f_dkft = v.add_parser("dk_ft_inspektionsredegoerelser_og_afgoerelser", parents=[g()],
                           help="Denmark Finanstilsynet supervision archive — inspection reports and decisions (4,038 items, keyless gbapi)",
                           description="Finanstilsynet's supervision archive (keyless, the gbapi search service on "
                                       "www.finanstilsynet.dk): 4,038 items live (measured 2026-11-13; \"Danske "
                                       "Bank\" → 1,651, year 2025 → 214) — the archive mixes inspection reports "
                                       "(Redegørelse), injunctions (Påbud) and reprimands (Påtale). LIVE LAWS: the POST "
                                       "REQUIRES a Referer header (without it the API answers 400 \"Incorrect request "
                                       "referer header\") and the body carries a NESTED userInput OBJECT "
                                       "{query, months, categorizations, additionalFilters, template} — a string "
                                       "userInput answers 400; the archive page's data-config attribute "
                                       "(HTML-escaped JSON) is echoed back verbatim in the body")
    f_dkft.add_argument("--q", default=None, help="Free-text query (upstream userInput.query; server-side)")
    f_dkft.add_argument("--year", type=int, default=None, help="Year window (upstream userInput.from/to; server-side, e.g. 2025 → 214 items)")
    f_dkft.add_argument("--page", type=int, default=1, help="Page, 1-based (upstream body: page; 10 items per page)")
    f_dkft.add_argument("--exact-match", dest="exact_match", default=None, choices=["true", "false"],
                        help="Exact-match flag (upstream userInput.exactMatch)")

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

    # —— 0.3.50 EE ERJK party-finance faces (dictionary slot: ee_erjk between ecfr and federalregister; legal's first EE face) ——
    fe1 = v.add_parser("ee_erjk_election_reports", parents=[g()],
                       help="EE election/candidate receipts report (erjk.ee — the register's company-hard-key layer)",
                       description="ERJK election report (keyless, one report per call): the layer where "
                                   "corporate money enters Estonian politics — party donations are "
                                   "natural-persons-only by law, and these candidate/election entries carry "
                                   "payer + reg_code, a DIRECT RIK äriregister registry code when the payer is a "
                                   "legal person. Two entry forms: --report-id directly (exact slot), or "
                                   "--event-id + --organisation-id (the discovery pair — resolves the "
                                   "organisation's report slots and takes the main report Põhiaruanne; every "
                                   "slot rides available_reports). Rows flatten the register's "
                                   "{person: [entries]} shape: person + birthdate (DD.MM.YYYY, the key's own "
                                   "form, verbatim) + payment_date + receipt_group + payer + reg_code + amount. "
                                   "API paths are language-prefixed (/et/api/…)")
    fe1.add_argument("--event-id", dest="event_id", type=int, default=None,
                     help="Election event id (with --organisation-id; e.g. 8345 = KOV 2025 — /et/api/events lists them)")
    fe1.add_argument("--organisation-id", dest="organisation_id", type=int, default=None,
                     help="Organisation (party/candidate) id within the event (with --event-id; 233 orgs under KOV 2025)")
    fe1.add_argument("--report-id", dest="report_id", default=None,
                     help="Exact report slot id (from a previous call's available_reports) — bypasses the discovery step")
    fe1.add_argument("--limit", type=int, default=500, help="Rows to return (local slice; the full report is a few hundred entries)")

    fe2 = v.add_parser("ee_erjk_quarterly_reports", parents=[g()],
                       help="EE party-finance receipts matrix (erjk.ee — party × period × donation category)",
                       description="ERJK quarterly-reports receipts matrix (keyless one-shot): the whole "
                                   "party × period × category aggregate (455 rows 2013→2026 live 2026-11-09) "
                                   "in one call — --party-id narrows to one party (163 Keskerakond / 158 "
                                   "Reformierakond; default all), --period to one year (\"2025\"; default "
                                   "show_all = full history). Rows are the upstream's own aggregates "
                                   "verbatim: party_id/party_name/_party_short + period + category_id/"
                                   "category_name (Rahaline annetus = cash donation…) + amount (decimal "
                                   "string → float). The corporate-money edge lives in "
                                   "ee_erjk_election_reports, not here (natural-persons-only by law)")
    fe2.add_argument("--party-id", dest="party_id", default=None,
                     help="Party id from the register (163 Keskerakond, 158 Reformierakond; default all)")
    fe2.add_argument("--period", default=None, help="One year like 2025 (default show_all = 2013→ full history)")
    fe2.add_argument("--limit", type=int, default=100, help="Rows to return (local slice over the few-hundred-row matrix)")

    # —— 0.3.57 ES BOE daily gazette table of contents (dictionary slot: es_boe_sumario between ee_erjk and federalregister) ——
    f_boe = v.add_parser("es_boe_sumario", parents=[g()],
                         help="BOE daily gazette table of contents (one publication day; no-publication day = published:false)",
                         description="www.boe.es/datosabiertos/api/boe/sumario/{YYYYMMDD}: the day's "
                                     "full inventory — sections 1/2A/2B/3/4/5A/5B/5C (and T on "
                                     "Constitutional-Court days). The JSON channel rides content "
                                     "negotiation (Accept: application/json — a bare request answers "
                                     "400 XML). Every container level arrives dict-OR-list "
                                     "(singleton-collapse) and items nest in FOUR measured shapes "
                                     "(departamento.item / epigrafe[].item / texto.item / "
                                     "texto.epigrafe[].item — T nests deepest), all collected with a "
                                     "seccion/departamento/epigrafe breadcrumb; a depth-blind census "
                                     "rides alongside so shape drift shows as a gap. Rows keep the "
                                     "BOE's own keys (identificador BOE-A-…, control, titulo, "
                                     "url_xml/url_html/url_pdf) — item FULL TEXT is a second surface "
                                     "(the item-level xml.php serves XML whatever the Accept header, "
                                     "out of scope). Weekends / gazette holidays answer 404 → "
                                     "published:false, never an error; future dates refused locally; "
                                     "the archive reaches back to the 1960s (1965 measured)")
    f_boe.add_argument("--date", required=True,
                       help="Publication day YYYY-MM-DD (REQUIRED, zero-padded; e.g. 2026-11-10 = 259 items across 8 sections)")
    f_boe.add_argument("--section", default=None,
                       help="Filter to one BOE section code (1, 2A, 2B, 3, 4, 5A, 5B, 5C, T — T = Tribunal Constitucional, not every day; local filter)")
    f_boe.add_argument("--limit", type=int, default=20,
                       help="Rows to return (local slice wall 1-100, default 20; total_matched echoes the full day)")

    # —— 0.3.62 ES CNMV sanction register (dictionary slot: es_boe < es_cnmv_sanctions < eu_cijeu; the SECOND cnmv provider id beside the 0.3.44 company entidades register) ——
    f_csanc = v.add_parser("es_cnmv_sanctions", parents=[g()],
                           help="CNMV securities sanction register (rolling 5-year window, ~90 entries)",
                           description="Spanish CNMV sanciones register (www.cnmv.es/Portal/Consultas/"
                                       "RegistroSanciones, keyless ASP.NET): the statutory publicity "
                                       "register (LMV art. 32.3) — a rolling FIVE-YEAR window, five-row "
                                       "pages, the tail page DISCOVERED from the page links (18 pages on "
                                       "2026-11-16; 19 on the 2026-10-19 pin — the window slides, never "
                                       "hardcoded). Rows: date + the full Spanish resolución prose "
                                       "verbatim (severity tokens muy graves/graves, the parties — "
                                       "company-suffix forms S.V./SA/SGIIC vs don/doña persons, parsed "
                                       "heuristically beside the prose — and the '(BOE de …)' gazette "
                                       "ref) + the per-row PDF (verdocumento?e={opaque token}). Default "
                                       "= page 0; --page N fetches one page; --party/--severity/--all "
                                       "sweep every page (each cached 24h — the second sweep is free); "
                                       "--lang en mirrors the register in English")
    f_csanc.add_argument("--page", type=int, default=None,
                         help="One page, 0-based (default page 0 = the five freshest entries)")
    f_csanc.add_argument("--all", dest="all_pages", action="store_true", default=False,
                         help="Sweep every page in the window (~18 pages × 5 rows; each cached 24h)")
    f_csanc.add_argument("--party", default=None,
                         help="Substring over the resolution prose (implies the full sweep)")
    f_csanc.add_argument("--severity", default=None, choices=["muy_graves", "graves"],
                         help="Severity token over the prose (implies the full sweep; 'grave' singular is not a filterable closed-set token — use --party grave)")
    f_csanc.add_argument("--lang", default="es", choices=["es", "en"],
                         help="Register language (the upstream ?lang= mirror)")
    f_csanc.add_argument("--limit", type=int, default=20,
                         help="Rows to return (local slice wall 1-100, default 20; total_matched echoes the sweep)")

    # —— 0.2.0 flat panel commands (legal main faces: source-qualified names + upstream param names verbatim + our defaults) ——

    # —— 0.3.59 CJEU jurisprudence search (dictionary slot: es_boe < eu_cijeu < federalregister; the SPA's own elastic DSL) ——
    f_cjeu = v.add_parser("eu_cijeu_search", parents=[g()],
                          help="CJEU jurisprudence search (InfoCuria elastic connector, POST DSL)",
                          description="Court of Justice of the EU jurisprudence search (keyless): the SPA's "
                                      "own XHR payload replayed — exact-mode term over the jurisprudence "
                                      "tab, metadata rows (idPublished/celex/ecli/docDate). 'insurance' → "
                                      "5,049 hits, bare browse 7,630. The affair index is metadata-only "
                                      "(contentLength 0) — key the full text by CELEX on EUR-Lex. The DSL "
                                      "shape must stay byte-equal to the SPA's or the gateway 500s")
    f_cjeu.add_argument("--q", default=None, help="Search term (upstream body: searchTerm; empty = bare tab browse)")
    f_cjeu.add_argument("--lang", default="EN", help="Search language, uppercased (only EN measured)")
    f_cjeu.add_argument("--limit", type=int, default=20, help="pageSize (wall 1-100; 100 shot live)")
    f_cjeu.add_argument("--page", type=int, default=0, help="pageNumber, 0-based (from/to window derived)")

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

    # —— 0.3.51 FR ADLC sanctions face (dictionary slot: fr_adlc between federalregister and gb_cma; registration order == FLAT order) ——
    f_fd = v.add_parser("fr_adlc_sanctions", parents=[g()],
                        help="FR Autorité de la concurrence fine register (data.gouv mirror — 1,208 rows 2009→)",
                        description="The French competition authority's company-level sanctions ledger "
                                    "(keyless via the official data.gouv.fr mirror — the authority's own "
                                    "domain egress-blocks some networks, the mirror is the same "
                                    "publication): id_decision is the case key — a case's per-company "
                                    "Montant individuel rows sum into its repeated Montant total (sum the "
                                    "individuel column, not the total column, to recompute a case). "
                                    "Filters are local and combinable: --entreprise case-insensitive "
                                    "substring, --id-decision exact ('26-D-05'), --year (the register "
                                    "covers 2009→). The stamped CSV resource URL rolls on every monthly "
                                    "build — the face resolves the latest resource through the datasets "
                                    "API at call time (dataset TTL 1h, CSV TTL 24h) and never hardcodes "
                                    "the path. Live build 2026-11-08: 1,208 rows; the 2015 parcel-"
                                    "delivery cartel 15-D-19 ships €672,332,000 case-level (Geodis/SNCF "
                                    "€196M each)")
    f_fd.add_argument("--entreprise", default=None, help="Company name, case-insensitive substring (Entreprise column)")
    f_fd.add_argument("--id-decision", dest="id_decision", default=None,
                      help="Case id, exact case-insensitive (id_decision column, e.g. 26-D-05)")
    f_fd.add_argument("--year", type=int, default=None, help="Sanction year (Annee column; register covers 2009→)")
    f_fd.add_argument("--limit", type=int, default=20, help="Rows to return 1-200 (default 20; whole build is 1,208 rows)")

    # —— 0.3.59 FR AMF sanctions/transactions REST pair (dictionary slot: fr_adlc < fr_amf < gb_cma; single-shot full JSON) ——
    f_amfs = v.add_parser("fr_amf_sanction", parents=[g()],
                          help="AMF disciplinary sanctions REST stream (454 rows, single-shot)",
                          description="AMF (FR markets authority) Commission des sanctions decisions "
                                      "(keyless): SAN-… id, decision date, violation theme, the parties "
                                      "(text_egard split), the amount/penalty text, the appeal flag "
                                      "(recours oui/non) and the decision-PDF direct link — amount/party/"
                                      "PDF coverage 454/454. Single-shot: the whole matching set in one "
                                      "body; narrow with --theme (tid or exact French name) and the ISO "
                                      "date window")
    f_amfs.add_argument("--theme", default=None, help="Violation theme: taxonomy tid or exact French name (12-value measured map; 'all' default)")
    f_amfs.add_argument("--date-from", dest="date_from", default=None, help="Window start YYYY-MM-DD (unix upstream; 'all' ≡ 0)")
    f_amfs.add_argument("--date-to", dest="date_to", default=None, help="Window end YYYY-MM-DD")

    f_amft = v.add_parser("fr_amf_transaction", parents=[g()],
                          help="AMF homologated settlement transactions REST stream (138 rows, single-shot)",
                          description="AMF settlement transactions homologuées (keyless): TRA-… id, actor "
                                      "(text_acteur), amount text + numeric total (134/137 cards carry "
                                      "it), decision-PDF link; 138 rows — richer than the sitemap's 121. "
                                      "Same theme/date contract as fr_amf_sanction")
    f_amft.add_argument("--theme", default=None, help="Violation theme: taxonomy tid or exact French name")
    f_amft.add_argument("--date-from", dest="date_from", default=None, help="Window start YYYY-MM-DD")
    f_amft.add_argument("--date-to", dest="date_to", default=None, help="Window end YYYY-MM-DD")

    # —— 0.3.61 FR administrative courts monthly archive pair (dictionary slot: fr_amf_transaction < fr_court_judgment < fr_court_judgments < gb_cma_case; registration order == FLAT order) ——
    f_frct1 = v.add_parser("fr_court_judgment", parents=[g()],
                           help="One FR administrative judgment, full text (CE/CAA monthly archive XML)",
                           description="French administrative courts (opendata.justice-administrative."
                                       "fr, keyless): ONE judgment's metadata plus texte_integral (the "
                                       "body, upstream HTML verbatim). doc_id = the archive stem the "
                                       "fr_court_judgments rows carry (DCE_503183_20261001 / "
                                       "DCA_20BX01837_20261007) or a CE ECLI "
                                       "(ECLI:FR:CECHR:2026:503183.20261001 — the dossier+date tail "
                                       "maps onto the same stem); the year+month route to the one "
                                       "monthly zip that holds it")
    f_frct1.add_argument("--doc-id", dest="doc_id", required=True,
                         help="Archive stem (DCE_…/DCA_…) or CE ECLI")

    f_frct2 = v.add_parser("fr_court_judgments", parents=[g()],
                           help="FR administrative courts monthly judgment archive (CE 791 / CAA 2,340 rows in 2026-10)",
                           description="French administrative courts (opendata.justice-administrative."
                                       "fr, keyless): one court-month archive zip → the metadata rows "
                                       "of EVERY judgment — Conseil d'État (--court ce) or the cours "
                                       "administratives d'appel (--court caa); history 2021-06→. Rows "
                                       "carry ecli (CE zips only — the CAA archives have no "
                                       "Numero_ECLI element, measured 0/24), dossier_number, "
                                       "jurisdiction code+name, lecture_date, decision/appeal type, "
                                       "publication_code, solution (the outcome verbatim) and doc_id "
                                       "(the full-text face's key)")
    f_frct2.add_argument("--year", type=int, required=True, help="Archive year (e.g. 2026)")
    f_frct2.add_argument("--month", type=int, required=True, help="Archive month 1-12 (e.g. 10)")
    f_frct2.add_argument("--court", default="ce", choices=["ce", "caa"],
                         help="ce = Conseil d'État (/DCE zips), caa = cours administratives d'appel (/DCA zips)")

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

    # —— 0.3.50 IE SIPO lobbying face (dictionary slot: ie_sipo between ie_revenue and in_sebi; registration order == FLAT order) ——
    f_sp = v.add_parser("ie_sipo_lobbying", parents=[g()],
                        help="Irish SIPO lobbying register search (api.lobbying.ie — returns × three-party shape)",
                        description="Regulation of Lobbying register (keyless): 123,591 lobbying returns "
                                    "live 2026-11-09, each embedding the three parties VERBATIM — Lobbyist "
                                    "(carrying CompanyRegistrationNumber, the CRO key, on 43.6% of "
                                    "registrants) × Clients (carrying Cro) × Dpos (the lobbied officials). "
                                    "THE 13-PARAM WALL: /api/Search 404s unless every parameter rides the "
                                    "query string with explicit empties — the face assembles the full set. "
                                    "--return-date-from/--return-date-to are DD-MM-YYYY, the register "
                                    "form's own shape (ISO is answered HTTP 500; the wall is local)")
    f_sp.add_argument("--query-text", dest="query_text", default=None,
                      help="Free search phrase (upstream param: queryText)")
    f_sp.add_argument("--client", default=None, help="The lobbied-for side (upstream param: client)")
    f_sp.add_argument("--dpo", default=None, help="Designated public official (upstream param: dpo)")
    f_sp.add_argument("--public-bodys", dest="public_bodys", default=None,
                      help="Office lobbied (upstream param: publicBodys — upstream's own plural spelling)")
    f_sp.add_argument("--period", default=None, help="Return period (upstream param: period)")
    f_sp.add_argument("--return-date-from", dest="return_date_from", default=None,
                      help="Submission window start, DD-MM-YYYY (upstream param: returnDateFrom)")
    f_sp.add_argument("--return-date-to", dest="return_date_to", default=None,
                      help="Submission window end, DD-MM-YYYY (upstream param: returnDateTo)")
    f_sp.add_argument("--page", type=int, default=1, help="Page, 1-based (upstream param: currentPage)")
    f_sp.add_argument("--limit", type=int, default=20,
                      help="Rows per page (upstream param: pageSize; 1-1000 honoured, probed)")

    # —— 0.3.59 India Code acts search (dictionary slot: ie_sipo < in_indiacode < in_sebi; DSpace 7 discovery API) ——
    f_ic = v.add_parser("in_indiacode_search", parents=[g()],
                        help="India Code act repository search (indiacode.gov.in DSpace 7 REST)",
                        description="India Code — the official repository of Central and State Acts "
                                    "(keyless): 'companies act' → 13,530 items. Rows carry the "
                                    "catalogue metadata verbatim (act_id/act_number/act_year/"
                                    "enact_date/state/chapters/sections/repealed) plus hitHighlights "
                                    "match snippets. Page 0-based; limit = size, honored to 100; the "
                                    "full document is a 3-hop bundles→bitstreams chain keyed by uuid")
    f_ic.add_argument("--q", required=True, help="Act-name term (upstream param: query; required)")
    f_ic.add_argument("--limit", type=int, default=20, help="Page size (upstream param: size; wall 1-100, honored verbatim)")
    f_ic.add_argument("--page", type=int, default=0, help="Page, 0-based (upstream param: page)")

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

    # —— 0.3.60 IT AGCM trio (dictionary slot: it_agcm_dettaglio < it_agcm_rating < it_agcm_ricerca_provvedimenti, all between in_sebi_orders and it_arera_decisions) ——
    f_agcmd = v.add_parser("it_agcm_dettaglio", parents=[g()],
                            help="One AGCM case card (the /dettaglio detail surface, keyless Domino custom endpoint)",
                            description="AGCM case card (keyless, www.agcm.it — the /dotcmsCustom/getDominoDetail "
                                        "endpoint): one case by the 32-hex uid carried in the list rows' /dettaglio "
                                        "link. The card's field skeleton is a bold label div + a value div, grouped "
                                        "under the band headers DATI GENERALI / ISTRUTTORIA / DECISIONE / "
                                        "PROVVEDIMENTI COLLEGATI; the linked provvedimenti (the measures) come as the "
                                        "card's list items. LIVE LAW: the Cloudflare gate is IP-BOUND, not "
                                        "fingerprint-bound — on direct egress every path answers 403 with "
                                        "\"Cf-Mitigated: challenge\" whatever the UA is; through this machine's proxy "
                                        "egress the same URLs answer 200")
    f_agcmd.add_argument("--uid", required=True, help="Case uid from the AGCM list rows (the 32-hex id in the /dettaglio link)")
    f_agcmd.add_argument("--replica", default="dbconc", choices=["dbconc", "dbcons", "dbrating"],
                         help="Replica the uid belongs to (dbconc = concentrations/abuses, dbcons = consumer protection, dbrating = rating)")

    f_agcmr = v.add_parser("it_agcm_rating", parents=[g()],
                           help="AGCM credit-rating register (17,669 rows — company name + tax code + legal seat)",
                           description="AGCM credit-rating register (keyless, the \"Rating: elenco imprese\" view of the "
                                       "dbrating replica on www.agcm.it): 17,669 rows live, measured 2026-11-13. Rows "
                                       "carry the company's name, its codice fiscale, the legal seat, the decision date, "
                                       "the outcome and the rating — the company-name → Italian tax-code join "
                                       "surface. LIVE LAW: the upstream words filter is a SINGLE TOKEN (a multi-word "
                                       "name answers HTTP 5000 upstream), so the face refuses it up front")
    f_agcmr.add_argument("--words", default=None, help="Company-name filter (upstream field: words; SINGLE TOKEN only)")
    f_agcmr.add_argument("--start", type=int, default=0, help="Row offset (upstream field: start)")
    f_agcmr.add_argument("--maxresults", type=int, default=10, help="Rows per page (upstream field: maxresults; 1-200)")

    f_agcmc = v.add_parser("it_agcm_ricerca_provvedimenti", parents=[g()],
                           help="AGCM case register — the authority's decision search (dbconc 12,878 / dbcons 8,508, keyless)",
                           description="AGCM decision search (keyless, www.agcm.it — the /dotcmsCustom/getDomino endpoint): "
                                       "the authority's own registers — dbconc/vw0401 concentrations 12,878, "
                                       "dbconc/vw0301 abuse of dominance 944, dbconc/vw0201 unfair terms 1,132, "
                                       "dbcons/vw0301 consumer protection 8,508 (measured 2026-11-13). The case cell "
                                       "carries the /dettaglio link, the key into the detail face. LIVE LAW: the "
                                       "Cloudflare gate is IP-BOUND (403 \"Cf-Mitigated: challenge\" on direct egress; "
                                       "200 through this machine's proxy egress) and the words filter is a SINGLE TOKEN "
                                       "(a multi-word name answers HTTP 5000 upstream)")
    f_agcmc.add_argument("--words", default=None, help="Company-name filter (upstream field: words; SINGLE TOKEN only)")
    f_agcmc.add_argument("--replica", default="dbconc", choices=["dbconc", "dbcons"],
                         help="Register replica (dbconc = concentrations/abuses, dbcons = consumer protection)")
    f_agcmc.add_argument("--view", default="vw0401",
                         help="Register view (dbconc: vw0401 concentrations, vw0301 abuse of dominance, vw0201 unfair terms; dbcons: vw0301)")
    f_agcmc.add_argument("--start", type=int, default=0, help="Row offset (upstream field: start)")
    f_agcmc.add_argument("--maxresults", type=int, default=10, help="Rows per page (upstream field: maxresults; 1-200)")

    # —— 0.3.51 IT ARERA decisions face (dictionary slot: it_arera between in_sebi and lda; registration order == FLAT order) ——
    f_ia = v.add_parser("it_arera_decisions", parents=[g()],
                        help="IT ARERA decision register (atti e provvedimenti — 15,599 docs 1996→)",
                        description="The Italian energy/networks regulator's TYPO3 decision library "
                                    "(keyless): electricity, gas, water, waste and district-heating "
                                    "regulation 1996→today, 1,560 pages × 15,599 documents (live "
                                    "2026-11-09). All filters optional and combinable: --anno + "
                                    "--numero + --tipologia (the register's own nine-word vocabulary, "
                                    "exact match) + --settore (the form's own sector code — unpinned, "
                                    "the sigla carries the sector letter anyway). The single-document "
                                    "form is deterministic (anno=2022 & numero=312 & tipologia=Delibera "
                                    "answers exactly one card). Rows: sigla (hard key NNN/YYYY/SETTORE), "
                                    "detail anchor (the real PDF paths live on the detail page — "
                                    "fileadmin naming drifts by era and is never assembled from the "
                                    "sigla), date DD/MM/YYYY verbatim, oggetto (entity-unescaped). "
                                    "10 documents per page upstream")
    f_ia.add_argument("--anno", type=int, default=None, help="Year 1996-current (the register's own dropdown span)")
    f_ia.add_argument("--numero", default=None, help="Document number (pair with --anno — bare numero is ambiguous across years)")
    f_ia.add_argument("--tipologia", default=None,
                      choices=["Delibera", "Determina", "Consultazione", "Parere", "Memoria",
                               "Relazione", "Rapporto", "Segnalazione", "Altro"],
                      help="Document type (the register's own vocabulary, exact match)")
    f_ia.add_argument("--settore", default=None, help="Sector code verbatim (the form's own hidden field; sigla carries the sector letter anyway)")
    f_ia.add_argument("--page", type=int, default=1, help="Page, 1-based (upstream param: pagina, 10 docs per page)")

    # —— 0.3.62 KR FSS sanctions one-shot excel register (dictionary slot: kr_fss between it_arera and kr_law; POST × bytes first combination) ——
    f_kfss = v.add_parser("kr_fss_sanctions", parents=[g()],
                          help="Korea FSS sanction register, one-shot excel (5,804 rows 2008→today; 제재 정보)",
                          description="Financial Supervisory Service 제재 정보 (www.fss.or.kr, keyless): "
                                      "the register's ONE-SHOT channel — POST excelDown.uxls answers the "
                                      "whole corpus as one ~270KB xlsx (5,804 rows 2008-10-02→2026-11-09 "
                                      "live; the list page's default window shows only 303). MEASURED "
                                      "column shape (the header row MISALIGNS — A = the sanctioned/"
                                      "inspected entity, B = the date, C/D/E = the sanction content "
                                      "split institution/executive/employee, F = the FSS department; "
                                      "columns letter-keyed, never order-keyed). 1,245 rows carry no "
                                      "inline content — recent rows' content is a PDF attachment on the "
                                      "view.do detail page (keyless /fss.hpdownload direct download, the "
                                      "2026-11-03 翻案) — kept with null content and counted in the "
                                      "census; the PDF walk is a batch concern, not this face. The "
                                      "transport's FIRST POST × bytes combination (extension 7 × 9)"
                          )
    f_kfss.add_argument("--org", default=None,
                        help="Entity name substring, case-insensitive (local scan over column A)")
    f_kfss.add_argument("--date-from", dest="date_from", default=None,
                        help="Sanction-date window start YYYY-MM-DD (local scan over column B)")
    f_kfss.add_argument("--date-to", dest="date_to", default=None,
                        help="Sanction-date window end YYYY-MM-DD (local scan over column B)")
    f_kfss.add_argument("--layer", default=None,
                        choices=["institution", "executive", "employee"],
                        help="Only rows with sanction content in that layer column (C/D/E)")
    f_kfss.add_argument("--limit", type=int, default=20,
                        help="Rows to return (local payload wall 1-100, default 20; register runs newest-first)")

    # —— 0.3.56 KR 국가법령정보센터 dual-pillar list search (dictionary slot: kr_law between it_arera and lda) ——
    f_krlp = v.add_parser("kr_law_precedents", parents=[g()],
                          help="Korean Supreme Court precedent list search (law.go.kr 판례; q='*' full enumeration ≈119,970)",
                          description="law.go.kr precScListR form-POST (keyless; the register-note's "
                                      "'session trio' warm+Referer+XHR turned out to be the successful "
                                      "probe PATH, not a requirement — a plain POST answers the same "
                                      "fragment, measured all three ways). q = case-name keyword, or "
                                      "* for the full walk (≈119,970 판례, bisected to certainty). Rows: "
                                      "prec_seq (the precView() numeric key into the full-text detail "
                                      "page — a second surface out of scope), case_name, and the "
                                      "decision struct parsed from the title attr: court × decided "
                                      "('2023. 7. 20.' verbatim) × case_number × kind (판결|결정). "
                                      "page_size 1-100 (outmax), true pagination. Cached 12h")
    f_krlp.add_argument("--q", default="*", help="Case-name keyword, or * for full enumeration (the JS fills * on an empty query — same semantics)")
    f_krlp.add_argument("--page", type=int, default=1, help="Page, 1-based (upstream param: pg)")
    f_krlp.add_argument("--page-size", dest="page_size", type=int, default=20,
                        help="Rows per page (upstream param: outmax; 1-100 hard ceiling)")
    f_krls = v.add_parser("kr_law_statutes", parents=[g()],
                          help="Korean statute list search (law.go.kr 법령; q='*' full enumeration under the current-statutes filter)",
                          description="law.go.kr lsScListR form-POST (keyless; same plain-POST law as "
                                      "kr_law_precedents) riding the verified 'current statutes' filter "
                                      "combo (section=lawNm + p9='2,4' + p18='0' + p19='1,3'; ≈6-7k "
                                      "現行 법령 — the full corpus incl. 자치법규 is ~24k and needs its "
                                      "own filter set, not shipped). q = 법령 name keyword, or * for the "
                                      "full walk. Rows carry the DOUBLE key (lsi_seq, effective_date) "
                                      "from lsViewWideAll('<lsiSeq>','<efYd>') — the statute-version "
                                      "serial × effective date, both needed to address one version; "
                                      "law_number (법률 제<N>호) parses from the title. efYd='99990101' "
                                      "is the 시행미정 (not-yet-in-force) sentinel — mapped to "
                                      "effective_date=None + pending=True, never a date. The deep-page "
                                      "ceiling sits at pg≈300-350 × 20 under this filter. Cached 12h")
    f_krls.add_argument("--q", default="*", help="법령 name keyword, or * for full enumeration under the current-statutes filter")
    f_krls.add_argument("--page", type=int, default=1, help="Page, 1-based (upstream param: pg; ceiling ≈300-350 under this filter)")
    f_krls.add_argument("--page-size", dest="page_size", type=int, default=20,
                        help="Rows per page (upstream param: outmax; 1-100 hard ceiling)")

    f13 = v.add_parser("lda_filings", parents=[g()],
                      help="US lobbying filings (LDA; client/registrant dual name face)",
                      description="LDA lobbying-disclosure filings: client_name (lobbied company) / registrant_name (lobbying firm) / filing_year all upstream-verbatim (may combine); page_size hard-clamped 25 — upstream silently returns 25 rows for larger asks (probed 2026-10-26); iterate with --page (true offset pagination)")
    f13.add_argument("--client-name", dest="client_name", default=None, help="Lobbied company name (upstream param: client_name; contains-match)")
    f13.add_argument("--registrant-name", dest="registrant_name", default=None, help="Lobbying firm name (upstream param: registrant_name)")
    f13.add_argument("--filing-year", dest="filing_year", type=int, default=None, help="Filing year from 1999 (upstream param: filing_year)")
    f13.add_argument("--page", type=int, default=None, help="Page number (upstream param: page; each page max 25 rows — upstream hard clamp)")
    f13.add_argument("--ordering", default="-dt_posted", help="Sort (upstream param: ordering; default -dt_posted)")
    f13.add_argument("--limit", type=int, default=20, help="Rows (maps to upstream page_size; 1-25 hard wall — larger asks silently yield 25, probed 2026-10-26)")

    # —— 0.3.59 LV KNAB party-finance pair (dictionary slot: lda < lv_knab < mx_cnv; the party-finance family's 18th pillar) ——
    f_knabp = v.add_parser("lv_knab_parties", parents=[g()],
                           help="Latvia KNAB party register (112 parties; registry-code join key)",
                           description="KNAB (Latvia's integrity bureau) political party register "
                                       "(keyless): registrationNumber is the LV company-registry "
                                       "code — the hard join key onto company registers; founded "
                                       "DD.MM.YYYY; liquidated flag. No server-side term filter "
                                       "(the SPA searches client-side) — enumerate and filter "
                                       "locally; limit echoed verbatim upstream")
    f_knabp.add_argument("--limit", type=int, default=100, help="Rows (upstream param: limit; echoed verbatim, no clamp)")
    f_knabp.add_argument("--page", type=int, default=1, help="Page, 1-based")

    f_knabt = v.add_parser("lv_knab_payments", parents=[g()],
                           help="Latvia KNAB donation ledger, transaction level (78,081 rows, daily-rolled)",
                           description="KNAB named-donation ledger (keyless): transaction-level rows "
                                       "with the donor named by statute (firstName/lastName/person) "
                                       "and the state-masked personCode ('211186*****' — passed "
                                       "through verbatim, never de-masked); amountDisplay negative "
                                       "= expenditure direction; date rolls to yesterday. "
                                       "--party-public-id filters server-side (from lv_knab_parties)")
    f_knabt.add_argument("--limit", type=int, default=100, help="Rows (upstream param: limit)")
    f_knabt.add_argument("--page", type=int, default=1, help="Page, 1-based")
    f_knabt.add_argument("--party-public-id", dest="party_public_id", default=None, help="Server-side party filter (payments' party_public_id; value from lv_knab_parties rows)")

    # —— 0.3.55 API-faces batch A (dictionary slots: mx_cnv/mx_sabg/nl_rechtspraak between lda and ru_cbr; registration order == FLAT order) ——
    f_cnv = v.add_parser("mx_cnv_sanctions", parents=[g()],
                         help="CNBV financial-sanctions register (Azure APIM; keyless by publication)",
                         description="CNBV sanctions ledger (11,593 rows live 2026-11-12; everything "
                                     "since the 2014-01-10 Lineamientos INCLUDING the non-regulated AML "
                                     "faces — Centros Cambiarios / Transmisores de Dinero / SOFOMES "
                                     "E.N.R.). HEADER PAGINATION: the body is a bare row list; totals "
                                     "ride x-total-items/x-total-pages (surfaced via transport ext 11); "
                                     "--page-number is 0-BASED (the upstream's own semantics), "
                                     "--page-size 1-1000 (12 calls walk the whole register); "
                                     "--order-field/--order-type (ASC|DESC; imposedOn verified both "
                                     "ways) sort server-side. Rows carry obligatedSubject (the company "
                                     "join key), sector/subSector, type, NUMERIC amount (MXN), conduct, "
                                     "imposedOn/publishedOn, pagado (paid flag), officeNumber. The APIM "
                                     "subscription key is hardcoded in the public frontend (the AU ACMA "
                                     "family — keyless by publication, not a credential). The op is "
                                     "never cached: the paging state rides headers, so a cache keyed on "
                                     "the URL would hand page N page 0's body")
    f_cnv.add_argument("--page-number", dest="page_number", type=int, default=0,
                       help="Page, 0-BASED (upstream header: X-Page-Number; 0..x-total-pages-1)")
    f_cnv.add_argument("--page-size", dest="page_size", type=int, default=1000,
                       help="Rows per page (upstream header: X-Page-Size; 1-1000, the bundle's own ceiling)")
    f_cnv.add_argument("--order-field", dest="order_field", default=None,
                       help="Sort field (upstream header: X-Order-Field; imposedOn verified)")
    f_cnv.add_argument("--order-type", dest="order_type", default=None, choices=["ASC", "DESC"],
                       help="Sort direction (upstream header: X-Order-Type; requires --order-field)")

    f_sabg = v.add_parser("mx_sabg_sanctioned_servants", parents=[g()],
                          help="Mexican sanctioned public servants, in-force register (SABG via datos.gob.mx datastore)",
                          description="Servidores públicos sancionados VIGENTES (435 rows live "
                                      "2026-11-12, monthly snapshot): the statutory public-integrity "
                                      "register read through the CKAN DATASTORE BYPASS — the direct CSV "
                                      "sits behind an Akamai gate (repodatos 403 on every stack) while "
                                      "datastore_search inlines the whole dataset as JSON, keyless. "
                                      "Rows are the 13 columns verbatim: expediente / the person's "
                                      "three name parts / autoridad / dependencia / sancion_impuesta "
                                      "(Inhabilitación) / causa (Abuso de autoridad…) / inicio→fin "
                                      "THE BARRING WINDOW (fin past = the row leaves the register) / "
                                      "ley (LFRASP). q full-text, filters JSON exact (e.g. "
                                      '{"ley": "LFRASP"} → 364), offset paging, sort '
                                      "'fecha_resolucion desc' style — the idb CKAN contract. The "
                                      "historical archive lives behind the PDN S3 challenge gate "
                                      "(not this face). Statutory publication recorded verbatim — "
                                      "no person-level entities are built from it")
    f_sabg.add_argument("--q", default=None, help="Full-text query across all fields (upstream param: q; q=Abuso → 78 rows)")
    f_sabg.add_argument("--filters", default=None, help='Field→value exact matches, JSON text — e.g. \'{"ley": "LFRASP"}\' (upstream param: filters)')
    f_sabg.add_argument("--limit", type=int, default=100, help="Rows (upstream param: limit; 1-1000 politeness cap — the whole register is ~435 rows)")
    f_sabg.add_argument("--offset", type=int, default=0, help="Row offset (upstream param: offset; total echoes the register size)")
    f_sabg.add_argument("--sort", default=None, help="Sort, e.g. 'fecha_resolucion desc' (upstream param: sort)")

    # —— 0.3.62 NL ACM publication register pair (dictionary slot: mx_sabg < nl_acm_publication < nl_acm_publications < nl_rechtspraak; the sitemap IS the channel) ——
    f_acm1 = v.add_parser("nl_acm_publication", parents=[g()],
                          help="One ACM publication detail (parties, case number, decision date; acm.nl)",
                          description="Netherlands ACM (Autoriteit Consument & Markt) ONE publication "
                                      "(www.acm.nl, keyless Drupal): the content-block field family — "
                                      "Publicatiedatum / Publicatietype / Beslisdatum / Zaak (Zaaknummer "
                                      "+ the /nl/zaak/{id} case link) / Partijen (a NESTED second h3 "
                                      "inside the Zaak block, paired h3-by-h3) / Trefwoorden / "
                                      "Onderwerpen, Dutch labels verbatim + pdf_urls. doc_id = the "
                                      "numeric id from nl_acm_publications rows (resolved through the "
                                      "cached sitemap set); a full URL is also accepted"
                          )
    f_acm1.add_argument("--doc-id", dest="doc_id", default=None,
                        help="Numeric publication id (from nl_acm_publications rows, e.g. 896)")
    f_acm1.add_argument("--url", default=None,
                        help="Full publication URL or /nl/publicaties/… path (alternative to --doc-id)")
    f_acm2 = v.add_parser("nl_acm_publications", parents=[g()],
                          help="ACM publication register by sitemap (13,368 URLs 2003→; decisions/boetes/investigations)",
                          description="Netherlands ACM publication register (www.acm.nl, keyless): the "
                                      "/nl/publicaties/ corpus read BY SITEMAP — the list page's JS "
                                      "window does not widen (measured), /sitemap.xml is a 9-page index "
                                      "of itself (?page=1..9) with per-URL lastmod, 13,368 publication "
                                      "URLs 2003→2026. Rows: doc_id (the /publicatie/{id}/ numeric), "
                                      "slug, url, lastmod. --category is a SLUG-TOKEN heuristic "
                                      "(concentratie/boete/onderzoek/kartel/cbb/rechtbank — research-"
                                      "counted 2,263/457/457/175/159/118), not an upstream field; "
                                      "--q is a slug substring. Newest-lastmod first; a list call "
                                      "sweeps index + 9 submaps, all cached 12h"
                          )
    f_acm2.add_argument("--category", default=None,
                        choices=["boete", "concentratie", "onderzoek", "kartel", "cbb", "rechtbank"],
                        help="Slug-token category filter (heuristic word-boundary match over the slug)")
    f_acm2.add_argument("--q", default=None, help="Slug substring (case-insensitive)")
    f_acm2.add_argument("--limit", type=int, default=20,
                        help="Rows to return (local slice wall 1-100, default 20; total_matched echoes the filter)")

    f_nlr = v.add_parser("nl_rechtspraak_search", parents=[g()],
                         help="Netherlands judiciary published-case search (uitspraken.rechtspraak.nl, keyless)",
                         description="Rechtspraak published-case corpus (~479k live 2026-11-12; the "
                                     "register reaches 1847). POST /api/zoek with a strict PascalCase "
                                     "body — the face assembles the one verified shape (a missing key, "
                                     "an empty SearchTerms, a non-zt0 Field or a non-empty Contentsoorten "
                                     "is answered by the mededeling SPA error page, HTTP 200 + HTML). "
                                     "TitelEmphasis IS the ECLI (the join key); Titel is the human case "
                                     "title; GerechtelijkProductType splits uitspraak vs conclusie (the "
                                     "advocate-general stream, 18k rows); dates are DD-MM-YYYY text; "
                                     "pdf_url is derived per row (colons→underscores — the verified "
                                     "full-text channel, %PDF-1.7) without fetching. --facets rides "
                                     "the six-axis FacetCounts (Contentsoorten/Rechtsgebieden/"
                                     "Instanties/Proceduresoorten/DatumPublicatie/DatumUitspraak) on "
                                     "the same call. The old OAI face stays retired")
    f_nlr.add_argument("--q", required=True, help="Free search term (upstream body: SearchTerms[0].Term, Field zt0 AlleVelden — the only verified field)")
    f_nlr.add_argument("--sort-order", dest="sort_order", default="Relevance",
                       choices=["Relevance", "PublicatieDatumDesc", "UitspraakDatumDesc", "UitspraakDatumAsc"],
                       help="Sort (upstream body: SortOrder; all four verified — UitspraakDatumAsc head is 19-03-1847)")
    f_nlr.add_argument("--start-row", dest="start_row", type=int, default=0,
                       help="Offset paging (upstream body: StartRow; 9900+ no wall)")
    f_nlr.add_argument("--page-size", dest="page_size", type=int, default=20,
                       help="Rows (upstream body: PageSize; 1-200 local politeness cap — 150 verified, no clamp observed)")
    f_nlr.add_argument("--facets", action="store_true",
                       help="Count the six facet axes on the same call (upstream body: ShouldCountFacets)")

    # —— 0.3.60 PL UOKiK pair (dictionary slot: pl_uokik_decision < pl_uokik_decisions, both between nl_rechtspraak_search and ru_cbr_warning_list; legal's first PL face) ——
    f_uokd = v.add_parser("pl_uokik_decision", parents=[g()],
                          help="One UOKiK decision card (Poland's competition & consumer authority, keyless)",
                          description="UOKiK decision card (keyless, decyzje.uokik.gov.pl — the ?act=Decyzja detail "
                                      "surface): one decision by the 32-hex unid the index rows carry. The card is a "
                                      "two-column table whose rows are <td><b>LABEL:</b></td><td>VALUE</td> — Numer "
                                      "decyzji / Data wydania decyzji / Sygnatura akt / Uczestnicy postępowania / "
                                      "Rodzaj praktyki / Kara (the penalty) / Branża / Region / Odwołanie do sądu, plus "
                                      "the decision PDF link. LIVE LAW: the host resets the TLS connection on roughly "
                                      "half the requests from this machine — the transport's retry absorbs it")
    f_uokd.add_argument("--unid", required=True, help="Decision id from pl_uokik_decisions (32 hex characters)")

    f_uokl = v.add_parser("pl_uokik_decisions", parents=[g()],
                          help="UOKiK decisions of the President (22,344 decisions under 12 practices, keyless)",
                          description="UOKiK decisions of the President (keyless, decyzje.uokik.gov.pl — the Domino "
                                      "\"dec_prez\" view enumeration): 22,344 decisions under 12 practices and 216 years "
                                      "(measured 2026-11-13). LIVE LAWS: the host resets TLS on roughly half the requests "
                                      "from this machine (the transport's retry absorbs it) and the index is a 15.1 MB "
                                      "payload — it is cached whole (TTL 12 h) and NEVER re-fetched per row. The surface "
                                      "has NO server-side filter (it is a view enumeration, not a search), so the year / "
                                      "practice / party filters are applied LOCALLY — exactly like the LV KNAB party "
                                      "register")
    f_uokl.add_argument("--year", default=None, help="Decision year (local filter over the register's year axis)")
    f_uokl.add_argument("--practice", default=None, help="Practice (Rodzaj praktyki; local filter, case-insensitive)")
    f_uokl.add_argument("--party", default=None, help="Party name (Uczestnicy postępowania; local filter, case-insensitive)")
    f_uokl.add_argument("--limit", type=int, default=50, help="Rows to return (default 50; local slice)")
    f_uokl.add_argument("--offset", type=int, default=0, help="Row offset (local slice)")


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

    # —— 0.3.50 UA NAZK party-finance faces (dictionary slot: ua_nazk between tr_spk and us_occ; legal's first UA face) ——
    f_ua1 = v.add_parser("ua_nazk_parties", parents=[g()],
                         help="UA political-party register (politdata.nazk.gov.ua — 321 parties, all-POST)",
                         description="NACP politdata party register (keyless): 321 registered parties "
                                     "(count echo, live 2026-11-09) with the register's own keys — code "
                                     "(the registration number), head_info (named leadership), "
                                     "register_address, contacts; id = the party uuid that keys "
                                     "ua_nazk_party_reports. ALL-POST contract: every endpoint answers "
                                     "GET with 404; the body is {page, pageSize, draw}. pageSize is "
                                     "SERVER-CLAMPED (send 10, 20 return) — the face asks verbatim and "
                                     "reports the clamped reality via count. NOT data.nazk.gov.ua (the "
                                     "declarations host is egress-blocked from this network, watched "
                                     "separately)")
    f_ua1.add_argument("--page", type=int, default=1, help="Page, 1-based")
    f_ua1.add_argument("--limit", type=int, default=20,
                       help="Rows to ask for (pageSize; the upstream clamps to its own preference — read count)")

    f_ua2 = v.add_parser("ua_nazk_party_reports", parents=[g()],
                         help="UA party report inventory (politdata.nazk.gov.ua — public_summary rides every row)",
                         description="One party's report inventory (keyless all-POST; 2021→2026Q3): rows "
                                     "verbatim with the EMBEDDED public_summary — the aggregated "
                                     "receipts/expenses per category (sums + row_counts) the upstream "
                                     "computed, zero extra calls. id = the report uuid that keys the "
                                     "follow-up payment faces (monetary_contributions carries "
                                     "payer_name/payer_type; payer_code is masked upstream). Regional-"
                                     "office reports sit in the same inventory (is_party_office=true)")
    f_ua2.add_argument("--party-id", dest="party_id", required=True,
                       help="Party uuid from ua_nazk_parties (required)")
    f_ua2.add_argument("--page", type=int, default=1, help="Page, 1-based")
    f_ua2.add_argument("--limit", type=int, default=20,
                       help="Rows to ask for (pageSize; server-clamped — read count)")

    # —— 0.3.60 US CBP CROSS pair (dictionary slot: us_cbp_ruling < us_cbp_stat, both between ua_nazk_party_reports and us_cftc_enforcement) ——
    f_cbp = v.add_parser("us_cbp_ruling", parents=[g()],
                          help="One CBP CROSS customs ruling (tariff classification, by ruling number — keyless)",
                          description="CBP CROSS ruling (keyless, rulings.cbp.gov — the /api/ruling/{n} detail endpoint): "
                                      "one tariff-classification ruling by its numeric ruling number (e.g. 954699). The "
                                      "body is CRLF-padded plain text with a header block; the importer name is the "
                                      "line after the contact line (the company join surface). LIVE LAW: the upstream's "
                                      "SEARCH endpoint (/api/search) is behind a reCAPTCHA Enterprise gate and answers "
                                      "403 — only the detail-by-number surface is on the route")
    f_cbp.add_argument("--ruling-number", dest="ruling_number", required=True,
                       help="Ruling number (the numeric CROSS ruling number, e.g. 954699)")

    f_cbps = v.add_parser("us_cbp_stat", parents=[g()],
                          help="CBP CROSS register census (222,344 searchable rulings + last-update stamp, keyless)",
                          description="CBP CROSS register census (keyless, rulings.cbp.gov — the /api/stat/lastupdate "
                                      "endpoint): the number of searchable rulings (222,344 live, measured 2026-11-13) "
                                      "and the register's last-update stamp. This is the register-level surface: the "
                                      "upstream's search endpoint is reCAPTCHA-gated, so the corpus is reachable by "
                                      "ruling number only")

    # —— 0.3.51 US CFTC enforcement face (dictionary slot: us_cftc between ua_nazk and us_ferc; registration order == FLAT order) ——
    f_fc = v.add_parser("us_cftc_enforcement", parents=[g()],
                        help="CFTC enforcement-actions index (1995→2026, ~2,610 actions, 0-based pages)",
                        description="The CFTC's full enforcement history as one Drupal views table "
                                    "(keyless): ~10 rows per page, ?page=0..260 — page 260 ends at the "
                                    "1995 floor (MG Refining and Marketing $2.25M, 07/27/1995), ≈2,610 "
                                    "actions total. Optional --year filter (the register's own dropdown "
                                    "1995→current — 1998 is ABSENT from it, a historical broken year, "
                                    "walled as such). Rows: datetime ISO + date MM/DD/YYYY verbatim, "
                                    "release_path (the /PressRoom/PressReleases/ anchor — prefix "
                                    "https://www.cftc.gov), release_number (the anchor tail, e.g. "
                                    "9320-26), title (entity-unescaped, whitespace-normalized) and "
                                    "related_docs — the judgment/consent-order attachments under "
                                    "/media/ with their labels. Bare UA 403'd live 2026-11-09; the face "
                                    "ships the full browser header suite (the ferc/afdb ext-8 family). "
                                    "Walk-aways: solr-search sits behind Cloudflare; "
                                    "publicreporting/data.cftc.gov are dead exits")
    f_fc.add_argument("--year", type=int, default=None, help="Year 1995-current, except 1998 (not offered by the register's own dropdown)")
    f_fc.add_argument("--page", type=int, default=0, help="Page, 0-based upstream verbatim (live range 0..260, ~10 rows per page)")

    # —— 0.3.50 US FERC eLibrary face (dictionary slot: us_ferc between ua_nazk and us_occ; registration order == FLAT order) ——
    f_fr = v.add_parser("us_ferc_elibrary", parents=[g()],
                        help="FERC eLibrary document search (4.7M docs 1980→ — dockets, orders, comments)",
                        description="elibrary.ferc.gov AdvancedSearch (keyless behind a Cloudflare "
                                    "UA-fingerprint gate — the full browser header suite passes, the afdb "
                                    "ext-8 family): the 4.7M-document 1980→ corpus over the whole "
                                    "FERC-regulated energy lifecycle (pipeline certificates CP-*, hydro "
                                    "licenses P-*, tariffs, rate cases). Filters combinable: --docket "
                                    "(with sub-docket suffix verbatim, CP17-101 or CP17-101-007), --text "
                                    "(full-text phrase), one date facet --date-type "
                                    "(filed_date|issued_date|posted_date|created_date) + --date-from/--"
                                    "date-to (YYYY-MM-DD, both bounds together); no filter = the "
                                    "upstream's own \"*\" wildcard, newest first. Rows verbatim minus the "
                                    "internal reference pair-key; acesssionNumber keeps the upstream's "
                                    "own triple-s and is the official key (the PDF rides the download "
                                    "endpoint, out of SDK scope)")
    f_fr.add_argument("--text", default=None, help="Full-text phrase (upstream param: searchText; default = the upstream's \"*\" wildcard)")
    f_fr.add_argument("--docket", default=None, help="Docket number, sub-docket suffix verbatim (upstream: docketSearches[].docketNumber)")
    f_fr.add_argument("--date-type", dest="date_type", default=None,
                      choices=["filed_date", "issued_date", "posted_date", "created_date"],
                      help="Date facet (with --date-from/--date-to; upstream: dateSearches[].dateType)")
    f_fr.add_argument("--date-from", dest="date_from", default=None,
                      help="Facet window start YYYY-MM-DD (upstream: startDate)")
    f_fr.add_argument("--date-to", dest="date_to", default=None, help="Facet window end YYYY-MM-DD (upstream: endDate)")
    f_fr.add_argument("--page", type=int, default=1, help="Page, 1-based (upstream param: curPage)")
    f_fr.add_argument("--limit", type=int, default=20,
                      help="Rows per page 1-1000 (upstream param: resultsPerPage, probed ceiling)")

    # —— 0.3.61 OCC enforcement-actions database face (dictionary slot: us_ferc_elibrary < us_occ_ea_search < us_occ_enforcements; registration order == FLAT order) ——
    f_eas = v.add_parser("us_occ_ea_search", parents=[g()],
                         help="OCC enforcement-actions DATABASE search (full history 1989→, 14 structured fields)",
                         description="OCC EASearch database (apps.occ.gov, keyless) — the structured "
                                     "twin of the 0.3.28 news-release face: the FULL HISTORY 1989→"
                                     "today (~6,072 actions) in one endpoint. Filters combinable: "
                                     "--q (institution-name substring, 'Wells Fargo'→164 rows incl. "
                                     "National City Bank), --start-dte-min/--start-dte-max (ISO "
                                     "YYYY-MM-DD, though the UI renders MM/DD/YYYY), --active-only/"
                                     "--terminated-only (terminated=true→2,344 rows)/--ind-only/"
                                     "--inst-only. At least one filter required — the unfiltered "
                                     "call is the whole 6,000-row history (bulk path). Rows carry "
                                     "Institution / CharterNumber (the bank-register join key) / "
                                     "Company / Individual / TypeCode+Description / Amount (numeric) "
                                     "/ StartDocuments (AA-ENF-YYYY-NN docket ids → ea{docket}.pdf) "
                                     "/ Termination pair / DocketNumber / SubjectMatters codes")
    f_eas.add_argument("--q", default=None, help="Institution-name substring (upstream param: q)")
    f_eas.add_argument("--start-dte-min", dest="start_dte_min", default=None,
                       help="Start-date window lower bound YYYY-MM-DD (upstream param: startDteMin)")
    f_eas.add_argument("--start-dte-max", dest="start_dte_max", default=None,
                       help="Start-date window upper bound YYYY-MM-DD (upstream param: startDteMax)")
    f_eas.add_argument("--active-only", dest="active_only", action="store_true",
                       help="Unterminated actions only (upstream flag: activeOnly)")
    f_eas.add_argument("--terminated-only", dest="terminated_only", action="store_true",
                       help="Terminated actions only (upstream flag: terminatedOnly; →2,344 rows)")
    f_eas.add_argument("--ind-only", dest="ind_only", action="store_true",
                       help="Actions against individuals/IAPs only (upstream flag: indOnly)")
    f_eas.add_argument("--inst-only", dest="inst_only", action="store_true",
                       help="Actions against institutions only (upstream flag: instOnly)")
    f_eas.add_argument("--limit", type=int, default=None,
                       help="Row cap (local; the upstream answers the full matching set in one shot)")

    # —— 0.3.28 OCC enforcement face (dictionary slot: us_occ between us_ferc and wb; registration order == FLAT order) ——
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
    # 0.3.60 batch E2 — API-faces depth wave (AU/BR/CA/DE/DK/IT/PL/US; zero new countries, four new legal jurisdictions)
    "au_frl_titles": lambda a: {"collection": a.collection, "term": a.term, "top": a.top},
    # 0.3.38 BR BACEN special-regimes face (dictionary slot: br_bacen between afdb and ca_sema)
    "br_bacen_complaints": lambda a: {"name": a.name, "ano": a.ano, "periodicidade": a.periodicidade,
                                      "periodo": a.periodo, "tipo": a.tipo, "cnpj": a.cnpj, "limit": a.limit},
    "br_bacen_regimes": lambda a: {"name": a.name, "cnpj": a.cnpj, "uf": a.uf, "limit": a.limit},
    "br_cade_pesquisa_avancada": lambda a: {"name": a.name, "module": a.module, "protocol": a.protocol,
                                            "limit": a.limit},
    # 0.3.58 CA provincial securities pair (slot: br_bacen_regimes < ca_asc_enforcement < ca_bcsc_disciplined < ca_sema_sanctions)
    "ca_asc_enforcement": lambda a: {"q": a.q, "limit": a.limit},
    "ca_bcsc_disciplined": lambda a: {"q": a.q, "party_type": a.party_type,
                                      "limit": a.limit, "offset": a.offset},
    # 0.3.60 CA CBSA advance-ruling pair (slot: ca_bcsc_disciplined < ca_cbsa_ruling < ca_cbsa_rulings < ca_sema_sanctions)
    "ca_cbsa_ruling": lambda a: {"rulings_id": a.rulings_id},
    "ca_cbsa_rulings": lambda a: {"limit": a.limit, "offset": a.offset},
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
    # 0.3.59 执法党产簇 first slice (registration order == FLAT order; slots noted at the parsers)
    "ch_efk_party_financings": lambda a: {"lang": a.lang, "year": a.year, "actor": a.actor},
    "ch_finma_enforcement_news": lambda a: {"q": a.q, "lang": a.lang, "limit": a.limit, "offset": a.offset},
    "co_sic_sanctions": lambda a: {"where": a.where, "limit": a.limit, "offset": a.offset, "order": a.order},
    "courtlistener_opinions_search": lambda a: {"q": a.q, "case_name": a.case_name,
                                                "court": a.court, "judge": a.judge,
                                                "docket_number": a.docket_number,
                                                "filed_after": a.filed_after,
                                                "filed_before": a.filed_before,
                                                "order_by": a.order_by, "cursor": a.cursor},
    # 0.2.11 UK CMA twin faces (gov.uk search/content API; upstream param names verbatim + our polite tier)
    "csl_screening_list": lambda a: {"name": a.name, "source": a.source, "type": a.type, "limit": a.limit},
    "de_lobbyregister_entries": lambda a: {"name": a.name, "active": a.active, "identity": a.identity,
                                           "codex_violations": a.codex_violations,
                                           "legislation": a.legislation, "limit": a.limit,
                                           "offset": a.offset},
    "dgcomp_cases_search": lambda a: {"query": a.query, "name": a.name, "instrument": a.instrument,
                               "text": a.text, "limit": a.limit, "page": a.page},
    "dk_ft_inspektionsredegoerelser_og_afgoerelser": lambda a: {"q": a.q, "year": a.year,
                                                              "page": a.page,
                                                              "exact_match": a.exact_match},
    "ecfr_search": lambda a: {"q": a.q, "page": a.page, "limit": a.limit, "date": a.date},
    "ecfr_titles": lambda a: {},
    # 0.3.50 EE ERJK party-finance faces (dictionary slot: ee_erjk between ecfr and federalregister; registration order == FLAT order)
    "ee_erjk_election_reports": lambda a: {"event_id": a.event_id, "organisation_id": a.organisation_id,
                                           "report_id": a.report_id, "limit": a.limit},
    "ee_erjk_quarterly_reports": lambda a: {"party_id": a.party_id, "period": a.period, "limit": a.limit},
    # 0.3.57 ES BOE daily gazette (dictionary slot: es_boe_sumario between ee_erjk and federalregister)
    "es_boe_sumario": lambda a: {"date": a.date, "section": a.section, "limit": a.limit},
    # 0.3.62 ES CNMV sanction register (dictionary slot: es_boe < es_cnmv_sanctions < eu_cijeu; second cnmv id)
    "es_cnmv_sanctions": lambda a: {"page": a.page, "all_pages": a.all_pages, "party": a.party,
                                    "severity": a.severity, "lang": a.lang, "limit": a.limit},
    "eu_cijeu_search": lambda a: {"q": a.q, "lang": a.lang, "limit": a.limit, "page": a.page},
    "federalregister_documents": lambda a: {"q": a.q, "startdt": a.startdt, "enddt": a.enddt,
                                       "order": a.order, "page": a.page, "limit": a.limit,
                                       "doc_type": a.doc_type, "agencies": a.agencies,
                                       "cfr_title": a.cfr_title, "cfr_part": a.cfr_part},
    # 0.3.51 FR ADLC sanctions face (dictionary slot: fr_adlc between federalregister and gb_cma)
    "fr_adlc_sanctions": lambda a: {"entreprise": a.entreprise, "id_decision": a.id_decision,
                                    "year": a.year, "limit": a.limit},
    "fr_amf_sanction": lambda a: {"theme": a.theme, "date_from": a.date_from, "date_to": a.date_to},
    "fr_amf_transaction": lambda a: {"theme": a.theme, "date_from": a.date_from, "date_to": a.date_to},
    # 0.3.61 FR administrative courts pair (dictionary slot: fr_amf_transaction < fr_court_* < gb_cma_case)
    "fr_court_judgment": lambda a: {"doc_id": a.doc_id},
    "fr_court_judgments": lambda a: {"year": a.year, "month": a.month, "court": a.court},
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
    # 0.3.50 IE SIPO lobbying face (dictionary slot: ie_sipo between ie_revenue and in_sebi)
    "ie_sipo_lobbying": lambda a: {"query_text": a.query_text, "client": a.client, "dpo": a.dpo,
                                   "public_bodys": a.public_bodys, "period": a.period,
                                   "return_date_from": a.return_date_from,
                                   "return_date_to": a.return_date_to,
                                   "page": a.page, "limit": a.limit},
    # 0.3.35 IN SEBI orders face (dictionary slot: in_sebi between ie_revenue and lda)
    "in_indiacode_search": lambda a: {"q": a.q, "limit": a.limit, "page": a.page},
    "in_sebi_orders": lambda a: {"category": a.category, "search": a.search,
                                 "from_date": a.from_date, "to_date": a.to_date, "page": a.page},
    # 0.3.60 IT AGCM trio (dictionary slot: it_agcm_* between in_sebi_orders and it_arera_decisions)
    "it_agcm_dettaglio": lambda a: {"uid": a.uid, "replica": a.replica},
    "it_agcm_rating": lambda a: {"words": a.words, "start": a.start, "maxresults": a.maxresults},
    "it_agcm_ricerca_provvedimenti": lambda a: {"words": a.words, "replica": a.replica,
                                                 "view": a.view, "start": a.start,
                                                 "maxresults": a.maxresults},
    # 0.3.51 IT ARERA decisions face (dictionary slot: it_arera between in_sebi and lda)
    "it_arera_decisions": lambda a: {"anno": a.anno, "numero": a.numero, "tipologia": a.tipologia,
                                     "settore": a.settore, "page": a.page},
    # 0.3.56 KR 국가법령정보센터 dual-pillar list search (slot: it_arera_decisions < kr_fss_sanctions < kr_law_{precedents,statutes} < lda_filings)
    "kr_fss_sanctions": lambda a: {"org": a.org, "date_from": a.date_from, "date_to": a.date_to,
                                   "layer": a.layer, "limit": a.limit},
    "kr_law_precedents": lambda a: {"q": a.q, "page": a.page, "page_size": a.page_size},
    "kr_law_statutes": lambda a: {"q": a.q, "page": a.page, "page_size": a.page_size},
    "lda_filings": lambda a: {"client_name": a.client_name, "registrant_name": a.registrant_name,
                              "filing_year": a.filing_year, "limit": a.limit, "page": a.page,
                              "ordering": a.ordering},
    # 0.3.55 API-faces batch A (dictionary slots: mx_cnv/mx_sabg/nl_rechtspraak between lda and ru_cbr)
    "lv_knab_parties": lambda a: {"limit": a.limit, "page": a.page},
    "lv_knab_payments": lambda a: {"limit": a.limit, "page": a.page, "party_public_id": a.party_public_id},
    "mx_cnv_sanctions": lambda a: {"page_number": a.page_number, "page_size": a.page_size,
                                   "order_field": a.order_field, "order_type": a.order_type},
    "mx_sabg_sanctioned_servants": lambda a: {"q": a.q, "filters": a.filters, "limit": a.limit,
                                              "offset": a.offset, "sort": a.sort},
    # 0.3.62 NL ACM publication pair (dictionary slot: mx_sabg < nl_acm_{publication,publications} < nl_rechtspraak)
    "nl_acm_publication": lambda a: {"doc_id": a.doc_id, "url": a.url},
    "nl_acm_publications": lambda a: {"category": a.category, "q": a.q, "limit": a.limit},
    "nl_rechtspraak_search": lambda a: {"q": a.q, "sort_order": a.sort_order,
                                        "start_row": a.start_row, "page_size": a.page_size,
                                        "facets": a.facets},
    # 0.3.60 PL UOKiK pair (dictionary slot: pl_uokik_* between nl_rechtspraak_search and ru_cbr_warning_list)
    "pl_uokik_decision": lambda a: {"unid": a.unid},
    "pl_uokik_decisions": lambda a: {"year": a.year, "practice": a.practice, "party": a.party,
                                     "limit": a.limit, "offset": a.offset},
    # 0.3.37 RU CBR warning-list face (dictionary slot: ru_cbr between lda and sipri)
    "ru_cbr_warning_list": lambda a: {"name": a.name, "inn": a.inn, "site": a.site,
                                      "violation": a.violation, "type": a.type, "limit": a.limit},
    "sipri_trades_search": lambda a: {"filters": a.filters, "supplier": a.supplier,
                                   "recipient": a.recipient, "type": a.type,
                                   "page": a.page, "limit": a.limit},
    # 0.3.36 TR SPK enforcement faces (dictionary slot: tr_spk between sipri and us_occ)
    "tr_spk_bans": lambda a: {"name": a.name, "type": a.type, "limit": a.limit},
    "tr_spk_fines": lambda a: {"name": a.name, "year": a.year, "limit": a.limit},
    # 0.3.50 UA NAZK party-finance faces (dictionary slot: ua_nazk between tr_spk and us_occ)
    "ua_nazk_parties": lambda a: {"page": a.page, "limit": a.limit},
    "ua_nazk_party_reports": lambda a: {"party_id": a.party_id, "page": a.page, "limit": a.limit},
    # 0.3.60 US CBP CROSS pair (dictionary slot: us_cbp_* between ua_nazk_party_reports and us_cftc_enforcement)
    "us_cbp_ruling": lambda a: {"ruling_number": a.ruling_number},
    "us_cbp_stat": lambda a: {},
    # 0.3.51 US CFTC enforcement face (dictionary slot: us_cftc between ua_nazk and us_ferc)
    "us_cftc_enforcement": lambda a: {"year": a.year, "page": a.page},
    # 0.3.50 US FERC eLibrary face (dictionary slot: us_ferc between ua_nazk and us_occ)
    "us_ferc_elibrary": lambda a: {"text": a.text, "docket": a.docket, "date_type": a.date_type,
                                   "date_from": a.date_from, "date_to": a.date_to,
                                   "page": a.page, "limit": a.limit},
    # 0.3.61 OCC enforcement-actions database face (dictionary slot: us_ferc_elibrary < us_occ_ea_search < us_occ_enforcements)
    "us_occ_ea_search": lambda a: {"q": a.q, "start_dte_min": a.start_dte_min,
                                   "start_dte_max": a.start_dte_max, "active_only": a.active_only,
                                   "terminated_only": a.terminated_only, "ind_only": a.ind_only,
                                   "inst_only": a.inst_only, "limit": a.limit},
    # 0.3.28 OCC enforcement face (dictionary slot: us_occ between us_ferc and wb)
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
    # 0.3.60 AU Federal Register of Legislation (slot: at_ris_statutes < au_frl_titles < br_bacen_complaints)
    "au_frl_titles": "AU",
    "br_bacen_complaints": "BR",
    "br_bacen_regimes": "BR",
    # 0.3.60 BR CADE advanced search (slot: br_bacen_regimes < br_cade_pesquisa_avancada < ca_asc_enforcement)
    "br_cade_pesquisa_avancada": "BR",
    # 0.3.58 CA provincial securities pair (slot: br_bacen_regimes < ca_asc_enforcement < ca_bcsc_disciplined < ca_sema_sanctions)
    "ca_asc_enforcement": "CA",
    "ca_bcsc_disciplined": "CA",
    # 0.3.60 CA CBSA rulings pair (slot: ca_bcsc_disciplined < ca_cbsa_* < ca_sema_sanctions)
    "ca_cbsa_ruling": "CA",
    "ca_cbsa_rulings": "CA",
    "ca_sema_sanctions": "CA",
    "cfpb_complaints": "US",
    "cfpb_suggest_company": "US",    "ch_efk_party_financings": "CH",
    "ch_finma_enforcement_news": "CH",

    "co_sic_sanctions": "CO",
    "courtlistener_opinions_search": "US",
    "csl_screening_list": "US",
    # 0.3.60 DE lobby register (slot: csl_screening_list < de_lobbyregister_entries < dgcomp_cases_search)
    "de_lobbyregister_entries": "DE",
    "dgcomp_cases_search": "EU",
    # 0.3.60 DK Finanstilsynet inspections (slot: dgcomp_cases_search < dk_ft_* < ecfr_search)
    "dk_ft_inspektionsredegoerelser_og_afgoerelser": "DK",
    "ecfr_search": "US",
    "ecfr_titles": "US",
    "ee_erjk_election_reports": "EE",
    "ee_erjk_quarterly_reports": "EE",
    "es_boe_sumario": "ES",
    "es_cnmv_sanctions": "ES",
    "eu_cijeu_search": "EU",
    "federalregister_documents": "US",
    "fr_adlc_sanctions": "FR",
    "fr_amf_sanction": "FR",
    "fr_amf_transaction": "FR",
    # 0.3.61 FR administrative courts pair (dictionary slot: fr_amf_transaction < fr_court_* < gb_cma_case)
    "fr_court_judgment": "FR",
    "fr_court_judgments": "FR",
    "gb_cma_case": "GB",
    "gb_cma_cases": "GB",
    "gb_ec_donations": "GB",
    "gb_ec_loans": "GB",
    "gb_gazette_notices": "GB",
    "gb_tna_caselaw_judgment": "GB",
    "gb_tna_caselaw_search": "GB",
    "idb_debarred_entities": "GLOBAL",
    "ie_revenue_defaulters": "IE",
    "ie_sipo_lobbying": "IE",
    "in_indiacode_search": "IN",
    "in_sebi_orders": "IN",
    # 0.3.60 IT AGCM triplet (slot: in_sebi_orders < it_agcm_* < it_arera_decisions)
    "it_agcm_dettaglio": "IT",
    "it_agcm_rating": "IT",
    "it_agcm_ricerca_provvedimenti": "IT",
    "it_arera_decisions": "IT",
    # 0.3.56 KR 국가법령정보센터 dual-pillar list search (slot: it_arera_decisions < kr_fss_sanctions < kr_law_{precedents,statutes} < lda_filings)
    "kr_fss_sanctions": "KR",
    "kr_law_precedents": "KR",
    "kr_law_statutes": "KR",
    "lda_filings": "US",
    "lv_knab_parties": "LV",
    "lv_knab_payments": "LV",
    # 0.3.55 API-faces batch A: MX enforcement pair + NL judgment corpus
    "mx_cnv_sanctions": "MX",
    "mx_sabg_sanctioned_servants": "MX",
    "nl_acm_publication": "NL",
    "nl_acm_publications": "NL",
    "nl_rechtspraak_search": "NL",
    # 0.3.60 PL UOKiK decisions pair (slot: nl_rechtspraak_search < pl_uokik_* < ru_cbr_warning_list)
    "pl_uokik_decision": "PL",
    "pl_uokik_decisions": "PL",
    "ru_cbr_warning_list": "RU",
    "sipri_trades_search": "GLOBAL",
    "tr_spk_bans": "TR",
    "tr_spk_fines": "TR",
    "ua_nazk_parties": "UA",
    "ua_nazk_party_reports": "UA",
    # 0.3.60 US CBP CROSS pair (slot: ua_nazk_party_reports < us_cbp_* < us_cftc_enforcement)
    "us_cbp_ruling": "US",
    "us_cbp_stat": "US",
    "us_cftc_enforcement": "US",
    "us_ferc_elibrary": "US",
    "us_occ_ea_search": "US",
    "us_occ_enforcements": "US",
    "wb_debarred_firms": "GLOBAL",
}
