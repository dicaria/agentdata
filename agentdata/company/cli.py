"""company cli — domain command face registration (split per domain in 0.2.6, moved in from the root cli.py; purely flat since the 0.3.0 verb-layer + sugar removal).

register(v, g): registers flat commands on the domain subparser (g = the root _leaf_globals factory,
passed in as a parameter to avoid a cli ↔ domain-cli cycle); FLAT = the flat dispatch table, merged by the root cli for main to use.
"""
import argparse

from . import in_sebi_intm  # the 37-category choice list rides the provider's verbatim map
from . import es_cnmv  # the 14-category choice list rides the provider's own map
from .jp_fsa import FAMILIES as jp_fsa_categories  # the 31-register choice list rides the provider's farm map

def register(v, g):
    # —— Flat panel commands (company main face: source-qualified names + upstream params under original names + our defaults; the only face family since 0.3.0) ——
    # —— 0.3.38 BR BACEN Olinda registers batch (dictionary slot: br_bacen at the FLAT head, before ch) ——
    f_b1 = v.add_parser("br_bacen_branches", parents=[g()],
                        help="Brazil branch register, whole 13,590-row panel (BACEN Olinda Informes_Agencias)",
                        description="BACEN branch register: 639 IFs x 20 segmentos, two keyless pages pulled whole and scanned locally; CNPJ three-part + joined 14-digit cnpj_full (the RFB whole-library join key), COMPE settlement code (null on 731 rows), posicao panel as-of, data_inicio 1949->")
    f_b1.add_argument("--if-name", dest="if_name", default=None,
                      help="Institution name contains-match (local scan over NomeIf)")
    f_b1.add_argument("--agency", default=None, help="Agency name contains-match (local scan over NomeAgencia)")
    f_b1.add_argument("--compe", default=None, help="3-5 digit COMPE settlement code (exact, leading-zero-tolerant)")
    f_b1.add_argument("--uf", default=None, help="2-letter state code (exact, e.g. SP)")
    f_b1.add_argument("--cnpj-root", dest="cnpj_root", default=None, help="8-digit CNPJ root (exact, = CnpjBase)")
    f_b1.add_argument("--limit", type=int, default=20, help="Rows back (local payload wall; 1-100)")
    f_b2 = v.add_parser("br_bacen_dasfn", parents=[g()],
                        help="Brazil open-data/open-finance API participation directory (BACEN Olinda DASFN)",
                        description="BACEN DASFN directory: 10,419 endpoint rows x 513 institution CNPJs x 4 API kinds (pilar3/canais_atendimento/taxas_cartoes/pix_saque), two keyless pages pulled whole and scanned locally; cnpj is the exact 14-digit whole key; upstream nulls serialised as the literal string None are normalised to null")
    f_b2.add_argument("--cnpj", default=None, help="14-digit whole CNPJ (exact)")
    f_b2.add_argument("--name", default=None, help="Institution name contains-match (local scan)")
    f_b2.add_argument("--api", default=None, choices=["pilar3", "canais_atendimento", "taxas_cartoes", "pix_saque"],
                      help="API kind (the register's own four)")
    f_b2.add_argument("--recurso", default=None, help="Endpoint path contains-match (local scan)")
    f_b2.add_argument("--limit", type=int, default=20, help="Rows back (local payload wall; 1-100)")
    f_b3 = v.add_parser("br_bacen_domains", parents=[g()],
                        help="Brazil verified-domains register — the anti-phishing edge (BACEN Olinda DominiosVerificados)",
                        description="BACEN verified-domains register: 1,892 rows = 1,740 institutions x verified-domain status (own 534 / conglomerate-member 279 — the upstream typo 'intregrante' kept verbatim — / no-verified-domain 1,079 honest negatives stay in the scan); conglomerado = the 635-code conglomerate lineage key")
    f_b3.add_argument("--domain", dest="dominio", default=None,
                      help="Domain contains-match (local scan; no-verified rows never match) — dest dominio, NOT domain: the root parser owns the a.domain slot (the domain selector)")
    f_b3.add_argument("--name", default=None, help="Institution name contains-match (local scan)")
    f_b3.add_argument("--tipo", default=None, choices=["own", "member", "none"],
                      help="Verified-domain status: own|member|none (translates the register's three-value vocabulary)")
    f_b3.add_argument("--conglomerado", default=None, help="Conglomerate code (exact, = CODIGO_DO_CONGLOMERADO)")
    f_b3.add_argument("--limit", type=int, default=20, help="Rows back (local payload wall; 1-100)")
    f_b4 = v.add_parser("br_bacen_institutions", parents=[g()],
                        help="Brazil authorised-institutions register, four families merged (BACEN Olinda Instituicoes_em_funcionamento)",
                        description="BACEN authorised-institutions register: banco 154 / cooperativa 752 / sociedade 704 / consorcio 130 = 1,740 rows, four keyless resources pulled whole and scanned locally; key variants are the register's own (banco SEGMENTO+CARTEIRA_COMERCIAL, cooperativa CLASSE/CATEGCOOPSING/FILIACAO/ASSOCIACAO with no SEGMENTO, sociedade 15-value SEGMENTO, consorcio bare); CNPJ is the 8-digit root")
    f_b4.add_argument("--name", default=None, help="Institution name contains-match (local scan)")
    f_b4.add_argument("--family", default=None, choices=["banco", "cooperativa", "sociedade", "consorcio"],
                      help="Resource family (the four Sedes* resources)")
    f_b4.add_argument("--segmento", default=None, help="Segmento contains-match (local scan; only bites banco/sociedade rows)")
    f_b4.add_argument("--uf", default=None, help="2-letter state code (exact, e.g. SP)")
    f_b4.add_argument("--cnpj-root", dest="cnpj_root", default=None, help="8-digit CNPJ root (exact)")
    f_b4.add_argument("--limit", type=int, default=20, help="Rows back (local payload wall; 1-100)")
    # —— 0.3.43 CA OSB CCAA restructuring roster (dictionary slot: ca_osb between br_bacen and ch_zefix) ——
    f_caosb = v.add_parser("ca_ccaa_records", parents=[g()],
                           help="Canada CCAA large-company restructuring roster — cumulative 2009→2026, 730 proceedings (OSB open data)",
                           description="OSB CCAA records list (keyless XLSX behind an open.canada.ca CKAN "
                                       "package): the LATEST year resource is resolved at call time (the "
                                       "URL rolls quarterly) and scanned locally — one cumulative snapshot "
                                       "per year, 730 proceedings 2009→2026. Each row: court, OSB File "
                                       "Number (the estate key — province in its suffix), initial order "
                                       "date, head office, the full court-appointed-monitor block "
                                       "(KPMG/FTI/PwC/EY/Deloitte with representative, email, employees) "
                                       "and filing amounts where disclosed. NO corporate-number column — "
                                       "join by company name + province. The 1978→today full estate "
                                       "library (Federal Insolvency Records Search) is a paid wall and is "
                                       "NOT this face")
    f_caosb.add_argument("--name", default=None,
                         help="Debtor company name contains-match (local scan; also searches the other-names column)")
    f_caosb.add_argument("--province", default=None,
                         help="CA subnational code from the OSB File Number suffix (AB/BC/MB/NB/NL/NS/NT/NU/ON/PE/QC/SK/YT)")
    f_caosb.add_argument("--monitor", default=None,
                         help="Court-appointed monitor contains-match, e.g. KPMG (local scan)")
    f_caosb.add_argument("--osb", default=None,
                         help="OSB File Number exact match, e.g. 0000875-2026-AB (the estate key)")
    f_caosb.add_argument("--limit", type=int, default=20, help="Rows back (local payload wall; 1-100)")
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
    # —— 0.3.49 US city-license Socrata trio (dictionary slot: chi_bacp between ch_zefix_firm_search and co_rues — '_'(0x5F)<'i';
    # city faces take the host stem: data.cityofchicago.org → chi_bacp, tx_/wa_ state-axis ruling extended) ——
    f_chi = v.add_parser("chi_bacp_licenses", parents=[g()],
                         help="Chicago BACP business licenses full history (data.cityofchicago.org Socrata r5kz-chrr; keyless)",
                         description="1,210,956-row corpus, 1997→ full history — TWO-LEVEL "
                                     "business key account_number (enterprise across addresses) "
                                     "x site_number (address) + license_id per issuance + id = "
                                     "license_number-expiration compact; legal_name x DBA; "
                                     "license_code/description x business_activity taxonomy; "
                                     "six-date lifecycle; license_status codes verbatim "
                                     "(AAI/AA/AIN/CAN — no guessed variants); Chicago geo "
                                     "stack; payment_date refreshes DAILY. SoQL verbatim "
                                     "channel — no total echo, none faked; :@computed_region_* "
                                     "system columns pass through.")
    f_chi.add_argument("--where", default=None,
                       help="Raw SoQL filter (upstream param: $where; e.g. \"license_description='Consumption on Premises - Incidental Activity' and license_status='AAI'\")")
    f_chi.add_argument("--limit", type=int, default=20,
                       help="Rows to return (upstream param: $limit; 1-500 politeness cap, default 20)")
    f_chi.add_argument("--offset", type=int, default=0,
                       help="Row offset (upstream param: $offset; >=0 — Socrata deep-offset friendly)")
    f_chi.add_argument("--order", default=None,
                       help="Sort column [ASC|DESC] (upstream param: $order; rejects NULLS — e.g. date_issued DESC)")
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
    # —— 0.3.41 DE federal insolvency announcements (dictionary slot: de_inso between cz_ares and fdic) ——
    f_inso_reg = v.add_parser("de_inso_register_lookup", parents=[g()],
                              help="German federal insolvency announcements by register entry (HRB/HRA point lookup)",
                              description="neu.insolvenzbekanntmachungen.de: the register entry "
                                          "lookup — the hard join key against the commercial "
                                          "registers. The upstream demands the entry "
                                          "unambiguously: court + type + number all three (a "
                                          "half-filled entry is rejected: 'Der Registereintrag "
                                          "muss eindeutig belegt sein'). The court is given as "
                                          "the upstream code (R1101) or as the court name "
                                          "('Düsseldorf'; the 149 register courts are embedded). "
                                          "The row grain is the announcement, so one register "
                                          "entry returns several rows (openings, the discharge "
                                          "decision, the distribution list)")
    f_inso_reg.add_argument("--register-court", dest="register_court", required=True,
                            help="Registergericht — the upstream code (e.g. R1101) or the court name (e.g. Düsseldorf)")
    f_inso_reg.add_argument("--register-type", dest="register_type", required=True,
                            choices=["HRA", "HRB", "VR", "PR", "GNR", "GSR"],
                            help="Registerart (HRA/HRB/VR/PR/GNR/GSR)")
    f_inso_reg.add_argument("--register-number", dest="register_number", required=True,
                            help="Register number (the register's own number, e.g. 101036)")
    f_inso_reg.add_argument("--date-from", dest="date_from", default=None,
                            help="Window start YYYY-MM-DD (upstream param: ldi_datumVon; default today — widen it to cover the entity's lifetime)")
    f_inso_reg.add_argument("--date-to", dest="date_to", default=None,
                            help="Window end YYYY-MM-DD (upstream param: ldi_datumBis; default today; the portal published since 2022-01-03)")
    f_inso_reg.add_argument("--limit", type=int, default=20,
                            help="Rows to return (local payload wall 1-2000, default 20; total_matched echoes the full count)")
    f_inso_s = v.add_parser("de_inso_search", parents=[g()],
                            help="German federal insolvency announcements (search face — state/subject/window/name/case number)",
                            description="neu.insolvenzbekanntmachungen.de: a Jakarta Faces "
                                        "postback portal (one GET for the ViewState + the form "
                                        "action that carries the session, one form POST). The "
                                        "name field matches the surname / company designation "
                                        "EXACTLY, case-insensitively ('af-media gmbh' hits, "
                                        "'AF-Media' does not); the row grain is the "
                                        "announcement, not the case (one case carries several "
                                        "announcements on one day). The upstream refuses a "
                                        "window above its own cap ('maximale Trefferzahl "
                                        "beträgt 1000') — that answer comes back as a "
                                        "structured state, and the working grain is ONE STATE x "
                                        "ONE DAY (a state-day renders ~1,050-1,080 rows, a "
                                        "two-day state window is refused). The announcement "
                                        "full text needs a real browser click and is not in "
                                        "this face")
    f_inso_s.add_argument("--state", default=None,
                          choices=["BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW",
                                   "RP", "SL", "SN", "ST", "SH", "TH"],
                          help="Bundesland (upstream param: scl_bundesland; the working grain is one state x one day)")
    f_inso_s.add_argument("--subject", default=None,
                          choices=["EROEFF", "ABWMASS", "SICHMASS", "ENT_VERF", "ENT_RSB",
                                   "ENT_AUF_VERF", "INSO_PLAN", "VERTVERZ", "SONST"],
                          help="Gegenstand (upstream param: scl_gegenstand; EROEFF = openings, ENT_RSB = discharge decisions)")
    f_inso_s.add_argument("--date-from", dest="date_from", default=None,
                          help="Window start YYYY-MM-DD (upstream param: ldi_datumVon; default today)")
    f_inso_s.add_argument("--date-to", dest="date_to", default=None,
                          help="Window end YYYY-MM-DD (upstream param: ldi_datumBis; default today)")
    f_inso_s.add_argument("--name", default=None,
                          help="Surname / company designation — matched EXACTLY, case-insensitively (upstream param: litx_firmaNachName)")
    f_inso_s.add_argument("--first-name", dest="first_name", default=None,
                          help="First name (upstream param: litx_vorname; the debtor cell reads 'Nachname, Vorname')")
    f_inso_s.add_argument("--seat", default=None,
                          help="Seat / residence (upstream param: litx_sitzWohnsitz)")
    f_inso_s.add_argument("--az", default=None,
                          help="Case number '<Abteilung> <SIGN> <lfd>/<Jahr>' (upstream param: iaz_aktenzeichen; SIGN in AR/IE/IK/IN; the Abteilung may be absent, e.g. 'IN 261/24')")
    f_inso_s.add_argument("--limit", type=int, default=20,
                          help="Rows to return (local payload wall 1-2000, default 20; total_matched echoes the full count)")
    # —— 0.3.45 ES BORME daily gazette 正册双面（lexicographic slot: es_borme between edgar_fts and es_cnmv）——
    f_borme_day = v.add_parser("es_borme_day", parents=[g()],
                               help="BORME daily gazette inventory (one publication day's notices; no-publication day = published:false)",
                               description="www.boe.es/borme/dias/{y}/{m}/{d}/: the day's <li class=dispo> rows — "
                                           "each carries its BORME-A-*/BORME-B-*/BORME-C-* id (the key; the prefix is "
                                           "the subsection: A = SECCIÓN PRIMERA Empresarios actos inscritos — ids carry "
                                           "the boletin segment, BORME-A-2026-212-03; B = SECCIÓN PRIMERA otros actos "
                                           "publicados; C = SECCIÓN SEGUNDA anuncios — ids without it, BORME-C-2026-5782) "
                                           "and its signed-PDF path. Weekends / gazette holidays answer 404 upstream — "
                                           "structured as published:false, never an error; a future date is refused "
                                           "locally. ids chain into es_borme_notice (the day page carries no xml.php links).")
    f_borme_day.add_argument("--date", required=True,
                             help="Publication day YYYY-MM-DD (REQUIRED, zero-padded; corpus reaches back to 2005 day by day)")
    f_borme_day.add_argument("--kind", default=None, choices=["A", "B", "C"],
                             help="Subsection filter: A (SECCIÓN PRIMERA actos inscritos), B (SECCIÓN PRIMERA otros actos publicados), C (SECCIÓN SEGUNDA anuncios); omit for the whole day")
    f_borme_day.add_argument("--limit", type=int, default=20,
                             help="Rows to return (local slice wall 1-100, default 20; total_matched echoes the day's count; the census always reports the WHOLE day)")
    f_borme_no = v.add_parser("es_borme_notice", parents=[g()],
                              help="one BORME notice, machine-readable XML (A/B: companies+event paragraphs; C: announcement text verbatim)",
                              description="www.boe.es/diario_borme/xml.php?id=…: A/B notices (SECCIÓN PRIMERA Empresarios) parse as "
                                          "companies[] (<p class=articulo>ORDER - NAME.</p> opens; <p class=parrafo> appends events — "
                                          "Constitución/Nombramientos/Reelecciones/…, the trailing «Datos registrales» sheet string; 1:1 "
                                          "measured MADRID 756/756); C notices (SECCIÓN SEGUNDA) are parrafo-only announcement text "
                                          "with a <departamento> heading. NO NIF/registration number in the body — joins ride name + "
                                          "Datos registrales. BORME-S-* summary ids are refused (upstream 400s); unknown ids answer "
                                          "upstream_not_found.")
    f_borme_no.add_argument("--id", required=True,
                            help="Notice id BORME-A-YYYY-N / BORME-C-YYYY-N (REQUIRED; take ids from the es_borme_day face)")
    f_borme_no.add_argument("--name", default=None,
                            help="Company-name substring (local contains, NFKC+casefold, A notices only — the upstream has no query surface)")
    f_borme_no.add_argument("--order", type=int, default=None,
                            help="Articulo ORDER number, exact (e.g. 756 = the 756th company in the notice)")
    f_borme_no.add_argument("--limit", type=int, default=20,
                            help="Companies to return (local slice wall 1-100, default 20; total_matched echoes the notice's company count)")
    # —— 0.3.44 ES CNMV entidades 正册单面（lexicographic slot: es_cnmv between de_inso and fdic）——
    f_cnmv = v.add_parser("es_cnmv_entities", parents=[g()],
                          help="CNMV supervised-entity register (one category per call, keyless full-list local scan)",
                          description="www.cnmv.es/portal/consultas/listadoentidad.aspx?id=1&tipoent=0..13: "
                                      "FOURTEEN categories, one shot each (no key, no pagination, no POST — "
                                      "te=10's __VIEWSTATE shell is inert under GET). 1,760 entities live "
                                      "2026-11-04; te=4 (EEA investment firms passported, 812) and te=10 (EU "
                                      "credit entities passported, 469) are Spain's view of the European "
                                      "financial passport. The row is <li class=blocks-single> with the "
                                      "entity's own detail href as its key (TEN endpoint×tipo kinds); NIFs "
                                      "come dashed AND bare — normalised for joins; portfolio_managers and "
                                      "eu_credit_subsidiaries_passport are EMPTY categories (the register "
                                      "returns a normal titled page with zero rows). The cookie banner "
                                      "occupies <h1> on the big pages — the title is read from <title>.")
    f_cnmv.add_argument("--category", required=True, choices=list(es_cnmv.CATEGORIES),
                        help="Register category (14-slug closed set, REQUIRED — one GET per category; "
                             "securities_firms 113 / financial_advisers 92 / eea_investment_firms_passport 812 / "
                             "spanish_credit_entities 102 / eu_credit_passport 469 / national_financial_advisers 60 / …)")
    f_cnmv.add_argument("--name", default=None,
                        help="Entity-name substring (local contains, NFKC+casefold — the upstream has no query surface)")
    f_cnmv.add_argument("--nif", default=None,
                        help="Spanish NIF, exact (national entities only; dashed A-83217281 and bare B22526768 forms both accepted, normalised for the match)")
    f_cnmv.add_argument("--numero", default=None,
                        help="Official register number, exact (the passport/branch families key on numero, not NIF)")
    f_cnmv.add_argument("--limit", type=int, default=20,
                        help="Rows to return (local slice wall 1-100, default 20; total_matched echoes the full category count)")
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
    # —— 0.3.53 FR Regafi ACPR pair (dictionary slot: fr_recherche_search < fr_regafi_authorisations < fr_regafi_entities < gb_*; registration order == FLAT order) ——
    f5a = v.add_parser("fr_regafi_authorisations", parents=[g()],
                       help="French ACPR per-authorisation timeline (regafi.fr ODS v2.1 prd-banque-autorisations; keyless)",
                       description="One row per authorisation the ACPR granted — 31,107 rows live "
                                   "2026-11-10. id_referentiel joins fr_regafi_entities; date_debut "
                                   "runs 1946→today; the *_json columns carry the per-service blocks "
                                   "with their own effective dates (services de paiement, cryptos, "
                                   "cautions réglementées…), parsed in place. nature = the register's "
                                   "own seven-word vocabulary (exact); situation = closed ACTIF/MANDAT "
                                   "pair; categorie passes verbatim.")
    f5a.add_argument("--id-referentiel", dest="id_referentiel", default=None,
                     help="Entity join key (upstream where: id_referentiel=<int> — the register's own key, from fr_regafi_entities rows)")
    f5a.add_argument("--categorie", default=None,
                     help="Authorisation family (upstream where: categorie=…; e.g. Établissement de Crédit; pass verbatim)")
    f5a.add_argument("--nature", default=None,
                     help="Authorisation nature (upstream where: nature_autorisation=…; Agrément/Autorisation/Habilitation/Enregistrement/Approbation/Inscription liste/Exemption d'agrément — exact match)")
    f5a.add_argument("--situation", default=None,
                     help="Lifecycle (upstream where: situation=…; closed pair ACTIF | MANDAT)")
    f5a.add_argument("--limit", type=int, default=20,
                     help="Rows to return (upstream param: limit; 1-100 the ODS v2.1 ceiling, default 20)")
    f5a.add_argument("--offset", type=int, default=0,
                     help="Row offset (upstream param: offset; >=0; total_count is echoed for arithmetic)")
    f5b = v.add_parser("fr_regafi_entities", parents=[g()],
                       help="French ACPR supervised-entity register (regafi.fr ODS v2.1 prd-banque-entites; keyless)",
                       description="The supervised financial-entity roster — 25,890 rows live "
                                   "2026-11-10. id_referentiel is the official key; siren + lei are "
                                   "the dual hard keys (SIREN joins the FR company master, LEI joins "
                                   "GLEIF); id_entite_parente carries the parent edge; nom_commerciaux "
                                   "rides parsed (renaming history); categorie is multi-valued "
                                   "(Agent PSP 22,485 / Entreprise d'Investissement 1,009 / "
                                   "Établissement de Crédit 941 / Etablissement de paiement 584 / "
                                   "Établissement de Monnaie Électronique 320 …).")
    f5b.add_argument("--siren", default=None,
                     help="SIREN exact lookup (upstream where: siren=… — the FR company-master hard key)")
    f5b.add_argument("--lei", default=None,
                     help="LEI exact lookup (upstream where: lei=… — the GLEIF hard key)")
    f5b.add_argument("--categorie", default=None,
                     help="Category filter (upstream where: categorie=…; multi-valued upstream — an OR membership; 24-value vocabulary, pass verbatim)")
    f5b.add_argument("--pays", default=None,
                     help="Country filter (upstream where: pays=…; e.g. FRANCE)")
    f5b.add_argument("--q", default=None,
                     help="Name full-text (upstream where: search(denomination, …) — assembled locally; quotes refused)")
    f5b.add_argument("--limit", type=int, default=20,
                     help="Rows to return (upstream param: limit; 1-100 the ODS v2.1 ceiling, default 20)")
    f5b.add_argument("--offset", type=int, default=0,
                     help="Row offset (upstream param: offset; >=0; total_count is echoed for arithmetic)")
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
    # —— 0.3.42 JP FSA licensed/registered institution farm (dictionary slot: jp_fsa between je_jfsc and kz_gbd) ——
    f_jpfsa = v.add_parser("jp_fsa_licensed", parents=[g()],
                           help="FSA licensed/registered institution registers — 31 XLSX, ~4,082 entities (banks/insurers/securities/crypto/trust/FMIs/audit)",
                           description="www.fsa.go.jp/en/regulated/licensed/: thirty-one keyless "
                                       "XLSX registers behind one hub, each with its own as-of "
                                       "stamp and sheet shape — the JCN / Corporate Number / 法人番号 "
                                       "columns are ONE join key under three spellings; the 'Total N "
                                       "banks' subtotal cells ride ON data rows (row stays, class "
                                       "does not change); several registers are FROZEN years back "
                                       "(securities-finance/designated-parent as of Oct 2017, "
                                       "clearing Aug 2016) and each file's own as-of rides the "
                                       "census; the two Japanese sintaku files carry the furigana "
                                       "reading concatenated onto every value (stripped "
                                       "positionally, only there); fafia folds 545 sheet rows into "
                                       "104 audit firms with their '○'-marked foreign-issuer lists; "
                                       "the insurance lists and the FMI four carry NO corporate "
                                       "number. Files fetched once per 24h window, scanned locally "
                                       "— the upstream has NO query surface")
    f_jpfsa.add_argument("--category", required=True, choices=sorted(jp_fsa_categories),
                         help="Which register (the hub's own families as slugs: city_banks 36 / regional_banks 97 / financial_instruments_operators 1,957 / crypto_exchanges 27 / trust_agents 349 / foreign_audit_firms 104 / … — live counts 2026-11-05)")
    f_jpfsa.add_argument("--name", default=None,
                         help="Entity-name contains-match (local scan; NFKC+casefold — full-width alphanumerics unify)")
    f_jpfsa.add_argument("--jcn", default=None,
                         help="13-digit JCN / Corporate Number / 法人番号 (exact, local scan)")
    f_jpfsa.add_argument("--limit", type=int, default=20,
                         help="Rows back (local payload wall 1-100, default 20; total_matched echoes the full count)")
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
    # —— 0.3.49 US city-license trio (dictionary slot: lacity between kz_gbd_ul and no_brreg — 'k'<'l'<'n';
    # provider stem 'lacity' NOT 'la_' — 'LA' is ISO alpha-2 Laos and SDK prefixes are country codes) ——
    f_la = v.add_parser("lacity_registrations", parents=[g()],
                        help="LA Office of Finance active-business tax registrations (data.lacity.org Socrata 6rrh-rzua; keyless)",
                        description="632,799-row register — location_account compact key "
                                    "(account-location-segment '0000000108-0001-3', the only "
                                    "join key), naics + primary_naics_description (the "
                                    "three-city batch's only industry-code face), mailing_* "
                                    "family present-only per row, council_district, "
                                    "location_start_date (future dates = advance "
                                    "registrations); NOT a license book — business-tax "
                                    "register. SoQL verbatim channel — no total echo, none "
                                    "faked; :@computed_region_* system columns pass through "
                                    "with per-row count drift (probed 5↔6).")
    f_la.add_argument("--where", default=None,
                      help="Raw SoQL filter (upstream param: $where; e.g. \"naics like '7213%%' and council_district='10'\")")  # %% — argparse printf-expands help strings
    f_la.add_argument("--limit", type=int, default=20,
                      help="Rows to return (upstream param: $limit; 1-500 politeness cap, default 20)")
    f_la.add_argument("--offset", type=int, default=0,
                      help="Row offset (upstream param: $offset; >=0 — Socrata deep-offset friendly)")
    f_la.add_argument("--order", default=None,
                      help="Sort column [ASC|DESC] (upstream param: $order; rejects NULLS — e.g. location_start_date DESC)")
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
    # —— 0.3.49 US city-license trio (dictionary slot: nyc_dcwp between no_brreg_roller and nzco — 'o'<'y'<'z') ——
    f_nyc = v.add_parser("nyc_dcwp_licenses", parents=[g()],
                         help="NYC DCWP license register (data.cityofnewyork.us Socrata w7w3-xahh; keyless)",
                         description="72,452-row corpus — applications+licenses book, NOT "
                                     "the padlocked licensed-locations table; license_nbr = "
                                     "number+agency suffix ('0016371-DCA') over "
                                     "business_unique_id ('BA-1322274-2022' enterprise "
                                     "anchor), business_category x license_type "
                                     "(Premises/Individual), Surrendered rows stay (history "
                                     "not just actives), split address family with borough "
                                     "column, NYC planning geo stack (community_board / "
                                     "council_district / bin / bbl / nta / census); "
                                     "~2.5-month refresh lag. SoQL verbatim channel — no "
                                     "total echo, none faked.")
    f_nyc.add_argument("--where", default=None,
                       help="Raw SoQL filter (upstream param: $where; e.g. \"business_category='Secondhand Dealer - General' and license_status='Active'\")")
    f_nyc.add_argument("--limit", type=int, default=20,
                       help="Rows to return (upstream param: $limit; 1-500 politeness cap, default 20)")
    f_nyc.add_argument("--offset", type=int, default=0,
                       help="Row offset (upstream param: $offset; >=0 — Socrata deep-offset friendly)")
    f_nyc.add_argument("--order", default=None,
                       help="Sort column [ASC|DESC] (upstream param: $order; rejects NULLS — e.g. lic_expir_dd DESC)")
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

    # —— 0.3.37 RU CBR credit-organisations face (dictionary slot: ru_cbr between ror and sec; registration order == FLAT order) ——
    f_ruc = v.add_parser("ru_cbr_credit_orgs", parents=[g()],
                         help="Bank of Russia credit-organisations register (FullCoList)",
                         description="cbr.ru FullCoList: the WHOLE register ships in ONE keyless "
                                     "HTML page (~790KB, 1,897 rows × 9 columns, nightly rebuild "
                                     "— the as-of stamp rides the census), cached 24h and scanned "
                                     "locally. Rows are the 9 upstream columns verbatim; "
                                     "license_status keeps the register's four-status vocabulary "
                                     "(Действующая 358 / Отозванная 282 / Аннулированная 2 / "
                                     "Ликвидация 1,255 — the liquidation wall is the register's "
                                     "largest segment; --status translates the English closed "
                                     "set); kind is null on the 1,746 universal banks (the "
                                     "register's own empty-cell convention); the name cell's "
                                     "/finorg/foinfo/?ogrn= anchor is kept as foinfo_path (the "
                                     "register's own per-entity edge). ОГРН = the ЕГРЮЛ join key "
                                     "(empty on 188 legacy/liquidated rows)")
    f_ruc.add_argument("--name", default=None,
                       help="Org name — substring, case-insensitive (over Наименование)")
    f_ruc.add_argument("--status", default=None,
                       choices=["active", "revoked", "annulled", "liquidation"],
                       help="License status (Статус лицензии: active | revoked | annulled | liquidation — translated from the verbatim Russian)")
    f_ruc.add_argument("--ogrn", default=None,
                       help="ОГРН digit key, exact match (13 digits; the ЕГРЮЛ join key)")
    f_ruc.add_argument("--limit", type=int, default=20,
                       help="Rows to return (local payload wall 1-100, default 20; total_matched echoes the full count)")

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
    # —— 0.3.46 SG data.gov.sg open-data platform (dictionary slot: sg_datagovsg between sec_* and
    # ted_*; _download sorts before _datasets — '_' < 's'; the ACRA register of record rides the
    # national platform as bulk CSV) ——
    f_sgdl = v.add_parser("sg_datagovsg_dataset_download", parents=[g()],
                          help="Minted download coordinates for one dataset (1-hour S3 signed URL; file body rides the batch line)",
                          description="api-open.data.gov.sg /v1/public/api/datasets/<id>/initiate-download → "
                                      "201 with the S3 signed URL immediately (both probe sizes did); a short "
                                      "no-cache poll walk is the fallback when initiate mints nothing. The URL "
                                      "is a 1-hour signature on s3.ap-southeast-1.amazonaws.com — the face "
                                      "parses mint time, the expiry window and the true file title "
                                      "(response-content-disposition filename) out of the signature itself. "
                                      "The file BODY rides the batch line (the ACRA master alone is 234 MB); "
                                      "S3 hop guidance: HEAD 403, GET/Range GET 200/206 with Content-Range "
                                      "total. Unknown id answers upstream_not_found (cz_ares posture).")
    f_sgdl.add_argument("--id", required=True,
                        help="Dataset id d_ + 32 hex (REQUIRED, e.g. d_3f960c10fed6145404ca7b821f263b87 — the ACRA master file; take ids from the sg_datagovsg_datasets face)")
    f_sgds = v.add_parser("sg_datagovsg_datasets", parents=[g()],
                          help="data.gov.sg catalog page (10 rows, local filters; the ACRA corpus's host platform)",
                          description="api-open.data.gov.sg /v2/public/api/datasets?page=N: the national "
                                      "open-data catalog, 4,665 datasets across 467 pages (2026-11-05 probe), "
                                      "datasetId ascending, 10 rows per page. The upstream has NO query "
                                      "surface: only ?page= is honoured — q/pageSize/agency are ALL silently "
                                      "ignored (probed), there is no search route and no single-dataset "
                                      "route. --q/--agency/--format are LOCAL over the fetched page's rows; "
                                      "whole-catalog discovery is an explicit page walk at the polite tier. "
                                      "Beyond the last page the upstream answers 200 with empty rows and "
                                      "zeroed totals — reported honestly. Page < 1 is refused locally (the "
                                      "upstream silently clamps page 0 to page 1). The ACRA register of "
                                      "record (~2.13M entities, UEN keys) rides this platform as bulk CSV.")
    f_sgds.add_argument("--page", type=int, default=1,
                        help="Catalog page (REQUIRED upstream param, default 1; the only honoured query param — 10 rows per page)")
    f_sgds.add_argument("--q", default=None,
                        help="Name/description substring (LOCAL contains over this page's rows — the upstream ignores its own q)")
    f_sgds.add_argument("--agency", default=None,
                        help="Managing-agency substring (LOCAL contains, e.g. 'ACRA' does not exist — ACRA rows say Accounting and Corporate Regulatory Authority)")
    f_sgds.add_argument("--format", dest="fmt", default=None,
                        help="Format exact, case-folded (e.g. CSV; LOCAL over the page)")
    f_sgds.add_argument("--limit", type=int, default=20,
                        help="Rows to return (local slice wall 1-100, default 20; the page is fixed at 10 rows upstream)")
    f17 = v.add_parser("ted_notices_search", parents=[g()],
                      help="EU procurement notices (TED v3 expert search; --query expert syntax)",
                      description="Tenders Electronic Daily: expert-syntax query via --query (e.g. 'organisation-name-buyer=Siemens* AND organisation-country-buyer=DEU' / classification-cpv=33100000); limit 1-250 is an upstream hard wall")
    f17.add_argument("--query", required=True, help="Expert syntax (upstream param: query; trailing wildcard = prefix match; buyer facets organisation-name-buyer / organisation-country-buyer, CPV via classification-cpv)")
    f17.add_argument("--fields", default=None, help="Comma list of eForms fields (upstream param: fields; wrong names 400 with the full 1,833-field dump)")
    f17.add_argument("--limit", type=int, default=10, help="Notices per page (upstream param: limit; 1-250 hard wall, default 10)")
    f17.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    # —— 0.3.40 TR BDDK authorised-institution card register (dictionary slot: tr_bddk between ted and tr_spk) ——
    f_bddk = v.add_parser("tr_bddk_institutions", parents=[g()],
                          help="BDDK authorised-institution cards (12 category pages, 640 cards live — banks/leasing/factoring/audit/valuation …)",
                          description="www.bddk.org.tr Kurulus/Liste/{id}: twelve server-rendered "
                                      "category pages, each holding its whole category (640 cards live, "
                                      "no paging, no query surface), cached 24h and scanned locally. The "
                                      "cards live in the detayliGor popup button's data-* attributes, not "
                                      "in the table: ad (name), aciklama (event history, sometimes the "
                                      "board decision in prose), isFaaliyette (1 = in operation, 0 = "
                                      "exited), eftKodu (the EFT routing code — the payments join key), "
                                      "isDijital ('(Dijital Banka)' on the six digital banks), telefon, "
                                      "faks, adres, webadresi, sektordenCikisTarihi (exit date; '-' is the "
                                      "placeholder, not a value), kurulKarari (the board decision). The "
                                      "register is a LIFETIME book — the 222 exited cards are the "
                                      "screening surface. Same-name cards are NOT collapsed (640 cards = "
                                      "631 distinct category+name pairs); no registration number, MERSIS "
                                      "key or tax id on the cards")
    f_bddk.add_argument("--name", default=None,
                        help="Institution name — substring, case-insensitive and Turkish-insensitive (over data-ad; no upstream query surface)")
    f_bddk.add_argument("--category", default="all",
                        choices=["all", "bankalar", "finansal_kiralama", "faktoring", "finansman",
                                 "finansal_holding", "varlik_yonetim", "yabanci_temsilcilik",
                                 "bagimsiz_denetim", "degerleme", "derecelendirme", "meslek_birligi",
                                 "tasarruf_finansman"],
                        help="Category page (all = the twelve pages, 640 cards, default; one slug = that page only)")
    f_bddk.add_argument("--eft", default=None,
                        help="EFT routing code, digits (data-eftKodu; the payments join key)")
    f_bddk.add_argument("--status", default="all", choices=["all", "active", "exited"],
                        help="Lifecycle filter (all = both, default; active = isFaaliyette 1; exited = the screening surface)")
    f_bddk.add_argument("--limit", type=int, default=20,
                        help="Rows to return (local payload wall 1-100, default 20; total_matched echoes the full count)")
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
    # —— 0.3.48 US state-license Socrata twin batch (dictionary slot: tx_tdlr between tr_spk_listed and usaspending) ——
    f_tx = v.add_parser("tx_tdlr_licenses", parents=[g()],
                        help="Texas TDLR All Licenses register (data.texas.gov Socrata 7358-krk7; keyless)",
                        description="966,778-row corpus, ~40 license types (top: Apprentice "
                                    "Electrician 283,425 / Cosmetology Operator 198,702). "
                                    "license_type x license_number registry key + "
                                    "business_name/owner_name duality + county + subtype family "
                                    "(AE/REG/CER/OP) + MM/DD/YYYY expiration column verbatim + "
                                    "CE flag; TDLR batch-refreshes (~monthly rowsUpdatedAt), not "
                                    "daily. SoQL verbatim channel — no total echo, none faked.")
    f_tx.add_argument("--where", default=None,
                      help="Raw SoQL filter (upstream param: $where; e.g. \"license_type='Cosmetology Operator' and business_county='TRAVIS'\")")
    f_tx.add_argument("--limit", type=int, default=20,
                      help="Rows to return (upstream param: $limit; 1-500 politeness cap, default 20)")
    f_tx.add_argument("--offset", type=int, default=0,
                      help="Row offset (upstream param: $offset; >=0 — Socrata deep-offset friendly)")
    f_tx.add_argument("--order", default=None,
                      help="Sort column [ASC|DESC] (upstream param: $order; rejects NULLS — e.g. license_number DESC)")
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
    # 0.3.48 second half (dictionary slot: wa_doh after vies_vat — the company tail; 'vi' < 'wa') ——
    f_wa = v.add_parser("wa_doh_credentials", parents=[g()],
                        help="Washington DoH health-care provider credentials (data.wa.gov Socrata qxh8-f4bd; keyless)",
                        description="2,468,860-row corpus, daily refresh — credentialnumber hard "
                                    "key (registrar grammar 'RN.RN.61687583.MSL'), practitioner "
                                    "names, credentialtype (Registered Nurse License 377,103 / …) "
                                    "x status (Active 564,934 / Expired 1,518,554 / …), "
                                    "firstissuedate/lastissuedate/expirationdate three-axis date "
                                    "family. **birthyear column stripped from every row — PII "
                                    "red line (birth year + full name stays out of the face; "
                                    "names in a public register are collectable, no_brreg roller "
                                    "precedent)**. SoQL verbatim channel — no total echo, none faked.")
    f_wa.add_argument("--where", default=None,
                      help="Raw SoQL filter (upstream param: $where; e.g. \"credentialtype='Physician And Surgeon License' and status='Active'\")")
    f_wa.add_argument("--limit", type=int, default=20,
                      help="Rows to return (upstream param: $limit; 1-500 politeness cap, default 20)")
    f_wa.add_argument("--offset", type=int, default=0,
                      help="Row offset (upstream param: $offset; >=0)")
    f_wa.add_argument("--order", default=None,
                      help="Sort column [ASC|DESC] (upstream param: $order; rejects NULLS — e.g. expirationdate ASC)")
    # —— 0.3.3 European country registry realtime faces (CH Zefix / NO Brreg / FI YTJ) ——

FLAT = {
    # company 0.2.0 flat panel (upstream params under original names + our defaults; the lambda only ferries names across namespaces)
    # 0.3.38 BR BACEN Olinda registers batch (dictionary slot: br_bacen at the FLAT head, before ch)
    "br_bacen_branches": lambda a: {"if_name": a.if_name, "agency": a.agency, "compe": a.compe,
                                    "uf": a.uf, "cnpj_root": a.cnpj_root, "limit": a.limit},
    "br_bacen_dasfn": lambda a: {"cnpj": a.cnpj, "name": a.name, "api": a.api,
                                 "recurso": a.recurso, "limit": a.limit},
    "br_bacen_domains": lambda a: {"domain": a.dominio, "name": a.name, "tipo": a.tipo,
                                   "conglomerado": a.conglomerado, "limit": a.limit},
    "br_bacen_institutions": lambda a: {"name": a.name, "family": a.family, "segmento": a.segmento,
                                        "uf": a.uf, "cnpj_root": a.cnpj_root, "limit": a.limit},
    # 0.3.43 CA OSB CCAA restructuring roster (dictionary slot: ca_osb between br_bacen and ch_zefix)
    "ca_ccaa_records": lambda a: {"name": a.name, "province": a.province, "monitor": a.monitor,
                                  "osb": a.osb, "limit": a.limit},
    "ch_zefix_firm": lambda a: {"ehraid": a.ehraid},
    # 0.3.3 European country registry realtime faces (five)
    "ch_zefix_firm_search": lambda a: {"name": a.name, "max_entries": a.max_entries, "offset": a.offset},
    # 0.3.49 US city-license Socrata trio (dictionary slot: chi_bacp between ch_zefix_firm_search and co_rues)
    "chi_bacp_licenses": lambda a: {"where": a.where, "limit": a.limit, "offset": a.offset,
                                    "order": a.order},
    # 0.3.11 CO RUES + KR hometax dual-country batch
    "co_rues_companies": lambda a: {"where": a.where, "limit": a.limit, "offset": a.offset,
                          "order": a.order},
    # 0.3.32 CZ ARES economic-entities register batch
    "cz_ares_ekonomicke_subjekty": lambda a: {"ico": a.ico},
    "cz_ares_ekonomicke_subjekty_vyhledat": lambda a: {"obchodni_jmeno": a.obchodni_jmeno,
                                          "pocet": a.pocet, "start": a.start},
    # 0.3.41 DE federal insolvency announcements (dictionary slot: de_inso between cz_ares and fdic)
    "de_inso_register_lookup": lambda a: {"register_court": a.register_court,
                                          "register_type": a.register_type,
                                          "register_number": a.register_number,
                                          "date_from": a.date_from, "date_to": a.date_to,
                                          "limit": a.limit},
    "de_inso_search": lambda a: {"state": a.state, "subject": a.subject,
                                 "date_from": a.date_from, "date_to": a.date_to,
                                 "name": a.name, "first_name": a.first_name,
                                 "seat": a.seat, "az": a.az, "limit": a.limit},
    "es_borme_day": lambda a: {"date": a.date, "kind": a.kind, "limit": a.limit},
    "es_borme_notice": lambda a: {"notice_id": a.id, "name": a.name, "order": a.order,
                                  "limit": a.limit},
    "es_cnmv_entities": lambda a: {"category": a.category, "name": a.name, "nif": a.nif,
                                   "numero": a.numero, "limit": a.limit},
    "fdic_institutions": lambda a: {"search": a.search, "filters": a.filters,
                            "limit": a.limit},
    "fi_ytj_companies": lambda a: {"name": a.name, "business_id": a.business_id},
    "fr_recherche_search": lambda a: {"q": a.q, "page": a.page, "per_page": a.per_page,
                            "etat_administratif": a.etat_administratif},
    # 0.3.53 FR Regafi ACPR pair (slot: fr_recherche_search < fr_regafi_authorisations < fr_regafi_entities < gb_*)
    "fr_regafi_authorisations": lambda a: {"id_referentiel": a.id_referentiel,
                                           "categorie": a.categorie, "nature": a.nature,
                                           "situation": a.situation, "limit": a.limit,
                                           "offset": a.offset},
    "fr_regafi_entities": lambda a: {"siren": a.siren, "lei": a.lei, "categorie": a.categorie,
                                     "pays": a.pays, "q": a.q, "limit": a.limit,
                                     "offset": a.offset},
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
    # 0.3.42 JP FSA licensed/registered institution farm (dictionary slot: jp_fsa between je_jfsc and kz_gbd)
    "jp_fsa_licensed": lambda a: {"category": a.category, "name": a.name, "jcn": a.jcn,
                                  "limit": a.limit},
    "kr_hometax_biz_status": lambda a: {"biz_no": a.biz_no},
    # 0.3.34 KZ GBD_UL master register batch
    "kz_gbd_ul_companies": lambda a: {"text": a.text, "page": a.page, "count": a.count},
    # 0.3.49 US city-license trio (dictionary slot: lacity between kz_gbd_ul and no_brreg — 'k'<'l'<'n')
    "lacity_registrations": lambda a: {"where": a.where, "limit": a.limit, "offset": a.offset,
                                       "order": a.order},
    "no_brreg_enheter": lambda a: {"navn": a.navn, "organisasjonsnummer": a.organisasjonsnummer,
                          "page": a.page, "size": a.size},
    "no_brreg_roller": lambda a: {"organisasjonsnummer": a.organisasjonsnummer},
    # 0.3.49 US city-license trio (dictionary slot: nyc_dcwp between no_brreg_roller and nzco — 'o'<'y'<'z')
    "nyc_dcwp_licenses": lambda a: {"where": a.where, "limit": a.limit, "offset": a.offset,
                                    "order": a.order},
    "nzco_companies": lambda a: {"q": a.q, "entity_types": a.entity_types,
                                 "start": a.start, "limit": a.limit},
    "nzco_directors": lambda a: {"company_number": a.company_number},
    "ror_organizations": lambda a: {"query": a.query, "ror_id": a.ror_id, "page": a.page,
                                    "all_status": a.all_status},
    # 0.3.37 RU CBR credit-organisations face (dictionary slot: ru_cbr between ror and sec)
    "ru_cbr_credit_orgs": lambda a: {"name": a.name, "status": a.status, "ogrn": a.ogrn,
                                     "limit": a.limit},
    "sec_fulltext_search": lambda a: {"q": a.q, "forms": a.forms, "startdt": a.startdt,
                          "enddt": a.enddt, "limit": a.limit},
    "sec_submissions": lambda a: {"cik": a.cik},
    # 0.3.46 SG data.gov.sg open-data platform (dictionary slot: sg_datagovsg between sec_* and ted_*; _download sorts before _datasets — '_' < 's')
    "sg_datagovsg_dataset_download": lambda a: {"dataset_id": a.id},
    "sg_datagovsg_datasets": lambda a: {"page": a.page, "q": a.q, "agency": a.agency,
                                        "fmt": a.fmt, "limit": a.limit},
    "ted_notices_search": lambda a: {"query": a.query,
                              "fields": a.fields, "limit": a.limit, "page": a.page},
    # 0.3.40 TR BDDK authorised-institution card register (dictionary slot: tr_bddk between ted and tr_spk)
    "tr_bddk_institutions": lambda a: {"name": a.name, "category": a.category,
                                       "eft": a.eft, "status": a.status, "limit": a.limit},
    # 0.3.36 TR SPK listed-companies directory (dictionary slot: tr_spk_listed between ted and usaspending)
    "tr_spk_listed": lambda a: {"name": a.name, "segment": a.segment,
                                "mersis": a.mersis, "limit": a.limit},
    # 0.3.48 US state-license Socrata twin batch (dictionary slot: tx_tdlr between tr_spk_listed and usaspending;
    # wa_doh between usaspending and vies_vat — US sub-national faces take the state code prefix, ny_open_data precedent)
    "tx_tdlr_licenses": lambda a: {"where": a.where, "limit": a.limit, "offset": a.offset,
                                   "order": a.order},
    "usaspending_spending_by_award": lambda a: {"recipient_search_text": a.recipient_search_text,
                                     "award_type_codes": a.award_type_codes,
                                     "start_date": a.start_date, "end_date": a.end_date,
                                     "fields": a.fields, "limit": a.limit, "page": a.page,
                                     "subawards": a.subawards},
    "vies_vat": lambda a: {"vat": a.vat},
    "wa_doh_credentials": lambda a: {"where": a.where, "limit": a.limit, "offset": a.offset,
                                     "order": a.order},
}


# 0.3.10 jurisdiction chapter: face → jurisdiction (default = the issuing authority's jurisdiction; bodies
# covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2 + EU + GLOBAL) — merged into _JURISDICTION by the root cli.py; success envelopes carry the jurisdiction chapter
COUNTRY = {
    "br_bacen_branches": "BR",
    "br_bacen_dasfn": "BR",
    "br_bacen_domains": "BR",
    "br_bacen_institutions": "BR",
    "ca_ccaa_records": "CA",
    "ch_zefix_firm": "CH",
    "ch_zefix_firm_search": "CH",
    # 0.3.49 US city-license trio (US city sources keep the US jurisdiction stamp — tx_tdlr/wa_doh 0.3.48 ruling;
    # chi_bacp between CH and CO, lacity between KZ and NO, nyc_dcwp between NO and NZ)
    "chi_bacp_licenses": "US",
    "co_rues_companies": "CO",
    "cz_ares_ekonomicke_subjekty": "CZ",
    "cz_ares_ekonomicke_subjekty_vyhledat": "CZ",
    "de_inso_register_lookup": "DE",
    "de_inso_search": "DE",
    "es_borme_day": "ES",
    "es_borme_notice": "ES",
    "es_cnmv_entities": "ES",
    "fdic_institutions": "US",
    "fi_ytj_companies": "FI",
    "fr_recherche_search": "FR",
    # 0.3.53 FR Regafi ACPR pair (slot: fr_recherche_search < fr_regafi_* < gb_*)
    "fr_regafi_authorisations": "FR",
    "fr_regafi_entities": "FR",
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
    "jp_fsa_licensed": "JP",
    "kr_hometax_biz_status": "KR",
    "kz_gbd_ul_companies": "KZ",
    "lacity_registrations": "US",
    "no_brreg_enheter": "NO",
    "no_brreg_roller": "NO",
    "nyc_dcwp_licenses": "US",
    "nzco_companies": "NZ",
    "nzco_directors": "NZ",
    "ror_organizations": "GLOBAL",
    "ru_cbr_credit_orgs": "RU",
    "sec_fulltext_search": "US",
    "sec_submissions": "US",
    "sg_datagovsg_dataset_download": "SG",
    "sg_datagovsg_datasets": "SG",
    "ted_notices_search": "EU",
    "tr_bddk_institutions": "TR",
    "tr_spk_listed": "TR",
    # 0.3.48 US state-license Socrata twin batch (US sub-national sources keep the US jurisdiction stamp;
    # tx_tdlr slots before usaspending ('tr'<'tx'<'us'), wa_doh is the company tail ('vi'<'wa'))
    "tx_tdlr_licenses": "US",
    "usaspending_spending_by_award": "US",
    "vies_vat": "EU",
    "wa_doh_credentials": "US",
}
