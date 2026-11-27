"""company domain package — provider adapters flat layout (one source per file) + faces/cli (0.2.6 per-domain reorg)."""
from . import (at_wiener, au_asx, br_bacen, br_bndes, ca_cse, ca_osb, ca_tmx, cf, ch_six_fqs, ch_six_onot,  # noqa: F401
               ch_zefix, chi_bacp,
               co_rues, cz_ares, de_inso, de_register, de_xetra, edgar_arch, edgar_cik, edgar_fts, edgar_ownership,
               edgar_xbrl,
               es_borme, es_cnmv, es_oepm, eu_eiopa, eu_esef, eu_euronext, fdic_bankfind, fi_ytj,
               fr_inpi,
               fr_recherche, fr_regafi, fts, gb_fca, gb_lse, gg_gfsc, gleif, hk_hkex, hk_hkexdi, in_sebi_intm, it_borsa,
               je_jfsc, jp_fsa, jp_jplatpat, jp_jpx, kr_hometax, kr_kipris, kr_krx, kz_gbd_ul, lacity,
               nasdaq_nordic,
               no_brreg, nyc_dcwp, nz_nzx, nzco, ror, ru_cbr_credit, se_mfn, sg_datagovsg, ted, tr_bddk,
               tr_kap, tr_spk_borsa, tx_tdlr, usaspending, vies, wa_doh)
# 0.3.43 rider: jp_fsa was missing from this eager-import list (0.3.42) — the attribute only
# resolved in processes where a test had imported the submodule directly; a fresh interpreter
# hit AttributeError on company.jp_fsa. Fix-forward, disclosed in the 0.3.43 changelog entry.
# 0.3.44: es_cnmv added in alphabetical slot (de_inso < edgar_* < es_cnmv < fdic_bankfind).
# 0.3.45: es_borme added in alphabetical slot (edgar_* < es_borme < es_cnmv).
# 0.3.46: sg_datagovsg added in alphabetical slot (ru_cbr_credit < sg_datagovsg < ted).
# 0.3.48: tx_tdlr/wa_doh added in alphabetical slots (tr_spk_borsa < tx_tdlr < usaspending;
# usaspending < vies < wa_doh — tail; US sub-national providers take the state code prefix, ny_open_data precedent).
# 0.3.49: chi_bacp/lacity/nyc_dcwp added in alphabetical slots (ch_zefix < chi_bacp < co_rues — '_'<'i';
# kz_gbd_ul < lacity < no_brreg; no_brreg < nyc_dcwp < nzco — 'o'<'y'<'z'). City faces take the host stem
# (data.cityofchicago.org/data.cityofnewyork.us/data.lacity.org); 'lacity' NOT 'la_' — 'LA' is ISO alpha-2 Laos.
# 0.3.51: us_fmcsa added in alphabetical slot (tx_tdlr < us_fmcsa < usaspending — '_'<'a');
# 0.3.54: us_fmcsa migrated to the transportation domain package (domain founding).
# 0.3.56: de_register/jp_jplatpat/kr_kipris added in alphabetical slots (de_inso < de_register < edgar_*;
# jp_fsa < jp_jplatpat < kr_hometax; kr_hometax < kr_kipris < kz_gbd_ul).
# 0.3.53: fr_regafi added in alphabetical slot (fr_recherche < fr_regafi < fts — 'rec'<'reg'<'t').
# 0.3.57: es_oepm/tr_kap added in alphabetical slots (es_cnmv < es_oepm < fdic_bankfind;
# tr_bddk < tr_kap < tr_spk_borsa).
# 0.3.58: fr_inpi added in alphabetical slot (fi_ytj < fr_inpi < fr_recherche — 'i'<'r').
# The four FDIC sibling faces live on the existing fdic_bankfind provider (no new module).
# 0.3.59: eu_eiopa added in alphabetical slot (fdic_bankfind < eu_eiopa < fi_ytj — 'd'<'u').
# 0.3.60: br_bndes added in alphabetical slot (br_bacen < br_bndes < ca_osb).
# 0.3.68: ch_six_fqs/eu_euronext/it_borsa/jp_jpx added in alphabetical slots (ch_six_fqs <
# ch_zefix — 's'<'z'; eu_eiopa < eu_euronext; in_sebi_intm < it_borsa < je_jfsc;
# jp_jplatpat < jp_jpx < kr_hometax) — the E10 developed-economy exchange faces. ca_tmx was
# written then DEFERRED unreleased: tsx.com flipped to an AWS WAF JS challenge 2026-11-18 pm
# (probe-e10 p2c-p2e — all-UA matrix challenged incl. the morning's working one; urllib cannot
# execute the challenge JS; re-probe when upstream relents).
# 0.3.69: edgar_arch added in alphabetical slot (de_register < edgar_arch < edgar_cik — 'a'<'c')
# — the E11 filing-document body fetch (www.sec.gov/Archives): the body layer under the filings
# line (submissions = index, fts = hit metadata, xbrl = facts). Shares the declared-UA fair-access
# family and the www.sec.gov host bucket with edgar_xbrl's tickers op.
# 0.3.70: at_wiener/au_asx/hk_hkex added in alphabetical slots (at_wiener < au_asx < br_bacen;
# gleif < hk_hkex < in_sebi_intm) — the E12 developed-economy exchange faces. at_wiener is the
# E10 TLS-reversal revival (the factsetdigital cert misconfig was upstream's, fixed same-day);
# hk_hkex rides ONE provider id over TWO hosts (www.hkex.com.hk universe + www1.hkexnews.hk
# announcements/documents — absolute-path ops, each host keeps its own polite bucket).
# 0.3.71: ca_cse/hk_hkexdi added in alphabetical slots (br_bndes < ca_cse < ca_osb;
# hk_hkex < hk_hkexdi < in_sebi_intm) — the E13 faces: CSE universe/issuer card (thecse.com
# /api/webapi/* JSON — /en prefix + trailing slash pinned) + HKEX DI disclosure-of-interests
# (di.hkex.com.hk — ASP.NET VIEWSTATE quartet + session cookie cached TOGETHER, the jp_jftc
# law; DION floor 2017-07-03 refused, not clamped; the date-axis captcha wall stays closed;
# SDW/CCASS out of scope by upstream terms §2.3). ca_tmx re-probed 2026-11-19 — still the
# AWS WAF challenge, stays deferred.
# 0.3.72: ch_six_onot/nz_nzx added in alphabetical slots (ch_six_fqs < ch_six_onot < ch_zefix
# — 'f'<'o'<'z'; nyc_dcwp < nz_nzx < nzco — 'y'<'z', '_'<'c') — the E14 faces: SIX official
# notices v2 (www.six-group.com/sheldon — the SAME host as ch_six_fqs but a different service
# family, its own provider id per the edgar precedent; the show* type switches are DEAD server-
# side, noticeType filters locally; issuerWords alive; pageSize pinned 100) + NZX SSR dehydrated
# state (www.nzx.com __NEXT_DATA__ — robots allows the SSR pages only, /api/ and /search never
# touched; the announcements ?page param is ignored upstream = newest-200 boundary, final).
# Rider: the no_* segment's physical order had drifted (nzco before nyc_dcwp, contradicting the
# 0.3.49 comment's own stated order) — restored to the stated order while inserting nz_nzx.
# 0.3.66: edgar_xbrl added in alphabetical slot (edgar_fts < edgar_xbrl < es_borme) — the SEC XBRL
# structured-facts family (companyfacts/companyconcept/frames/tickers), one provider id whose
# tickers op rides an ABSOLUTE path to www.sec.gov (build_url passes it through; each host keeps
# its own polite bucket). E8 batch: the 2026-10-19 deferral reopened — the local XBRL bulk lost
# with the E: drive, the MCP/OmniHub surface carries no financial-data paths.

# 0.3.73: de_xetra/kr_krx added in alphabetical slots (de_register < de_xetra < edgar_arch;
# kr_kipris < kr_krx < kz_gbd_ul — 'i'<'r', 'krx'<'kz') — E15: the Deutsche Börse T7 universe
# (Xetra/Frankfurt CSV master + Newsboard event stream; cashmarket.deutsche-boerse.com, the
# former xetra.com host) and the KRX Global listed universe + main-index snapshot (the OPEN
# portal of the three-sister gate family; the OTP grid's code never enters the cache key).
# 0.3.74: eu_esef/gb_fca added in alphabetical slots (eu_eiopa < eu_esef < eu_euronext;
# fts < gb_fca < gg_gfsc) — E16: the UK FCA data-portal family (api.data.fca.org.uk — ONE
# search endpoint, FOUR indexes: NSM disclosures / Official List / daily activity / FIRDS)
# and the ESEF filings register + XBRL-JSON facts (filings.xbrl.org — the EU Transparency
# Directive annual-report pillar; the facts op rides an ABSOLUTE json_url per filing, the
# edgar_arch/www.sec.gov absolute-path precedent).
# 0.3.75: edgar_ownership added in alphabetical slot (edgar_fts < edgar_ownership < edgar_xbrl)
# — E17: the EDGAR holdings-disclosure family (13F/Form 4/Schedule 13D-G structured ownership
# XML parsed). No new provider bucket: the module reuses edgar_cik submissions + edgar_arch
# Archives index/doc ops and adds the enumeration filters, document-pick laws (the XSL-shell
# primaryDocument trap) and the three parsers.
# 0.3.76: gb_lse added in alphabetical slot (gb_fca < gb_lse < gg_gfsc) — E18: the LSE
# exchange-universe family (apidata.londonstockexchange.com keyless REST + www sitemap/RNS
# pages + cache-api.lsegissuerservices.com issuer profiles — ONE provider id over THREE hosts,
# the hk_hkex/edgar_xbrl absolute-path precedent). The quote surfaces (pricing/instrument-
# summaries/trade-summaries/tmv/tns ticks/OHLCV bars) are MARKET-DATA — licensed goods,
# deliberately out (the red line); everything in the module is company-axis identity/index/
# issuer/disclosure data.
# 0.3.77: nasdaq_nordic added in alphabetical slot (lacity < nasdaq_nordic < no_brreg — 'a'<'o')
# and se_mfn (ru_cbr_credit < se_mfn < sg_datagovsg — r < s, 'se' < 'sg') — E20: the Nasdaq
# Nordic four-venue screener family
# (api.nasdaq.com/api/nordic — ALL ops transport='curl', the first load-bearing curl-channel
# batch: the JA3 gate blocks python TLS, curl UA-only passes, probe-e20 ctrl.sh dual-stack proof)
# + the MFN.se disclosure wire (se_mfn — server-rendered HTML only, machine feeds robots-banned;
# SE joins the jurisdiction set 36→37). Quote columns strip at the face layer (red line); the
# NewsWeb API stays egress-blocked (ECONNRESET re-certified 2026-11-24) — out, do not force.
# 0.3.78: ca_tmx added in alphabetical slot (ca_osb < ca_tmx < cf) — E21: the TMX Canada directory
# + GraphQL gateway family, ONE provider id over TWO hosts (www.tsx.com /json/company-directory/*
# keyless JSON + app-money.tmx.com Apollo GraphQL POST — absolute-path ops, the hk_hkex/
# edgar_xbrl/gb_lse precedent). The E10 deferral is CLOSED: the 2026-11-18 AWS WAF JS challenge
# keyed on EXIT-IP REPUTATION WINDOWS, not headers or stacks (2026-11-23 and 2026-11-27 egress
# both answered clean 14/14; dual-stack urllib passes bare-UA — NO curl pin, the nasdaq-nordic
# contrast). Red line: the gateway's quote block is stripped at the QUERY level (the 41-field
# profile selection never asks prices/volumes/ranges) and the filings face is metadata-only
# (urlToPdf lands on app.quotemedia.com, robots bans /data/ — pointer kept, never fetched).
