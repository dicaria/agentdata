"""legal domain package — provider adapters laid flat (one source per file) + faces/cli (0.2.6 per-domain split).
"""
from . import (afdb, at_ris, au_accc, au_frl, br_bacen_complaints, br_bacen_regimes, br_cade,  # noqa: F401
               ca_asc, ca_bcsc, ca_cbsa, ca_sema,
               cfpb, ch_efk, ch_finma, csl,
               courtlistener, co_sic, de_lobbyregister, dgcomp, dk_ft, ecfr, ee_erjk, es_boe,
               es_cnmv_sanctions, eu_cijeu, federalregister, fr_adlc,
               fr_amf, fr_court, gazette, gb_nmw,
               idb, ie_revenue, ie_sipo, in_cci, in_indiacode, in_sebi, it_agcm, it_arera, jp_jftc, kr_fss, kr_law, lda,
               lv_knab, mx_cnv,
               mx_sabg, nl_acm, nl_rechtspraak, occ, pl_uokik,
               ru_cbr_warning, sipri, tr_spk, ua_nazk, us_cbp, us_cftc, us_ferc, us_occ, gb_tna_caselaw, ukec,
               gb_cma, wb)
# 0.3.55: mx_cnv/mx_sabg/nl_rechtspraak added in alphabetical slots (lda < mx_* < nl_* < occ).
# 0.3.56: kr_law added in alphabetical slot (it_arera < kr_law < lda — 'i'<'k'<'l').
# 0.3.57: es_boe added in alphabetical slot (ee_erjk < es_boe < federalregister).
# 0.3.58: ca_asc/ca_bcsc added in alphabetical slots (br_bacen_regimes < ca_asc < ca_bcsc < ca_sema).
# 0.3.59: ch_efk/ch_finma/eu_cijeu/fr_amf/in_indiacode/lv_knab added in alphabetical slots
# (cfpb < ch_efk < ch_finma < csl; es_boe < eu_cijeu < federalregister; fr_adlc < fr_amf < gazette;
# ie_sipo < in_indiacode < in_sebi — 'd'<'s'; lda < lv_knab < mx_cnv).
# 0.3.60: au_frl/br_cade/ca_cbsa/de_lobbyregister/dk_ft/it_agcm/pl_uokik/us_cbp added in alphabetical
# slots (at_ris < au_frl < br_bacen_*; br_bacen_regimes < br_cade < ca_asc; ca_bcsc < ca_cbsa < ca_sema;
# co_sic < de_lobbyregister < dgcomp < dk_ft < ecfr; in_sebi < it_agcm < it_arera;
# nl_rechtspraak < occ < pl_uokik < ru_cbr_warning; ua_nazk < us_cbp < us_cftc).
# 0.3.61: fr_court/us_occ added in alphabetical slots (fr_amf < fr_court < gazette;
# us_ferc < us_occ — the 0.3.28 module 'occ' (news releases) keeps its id; 'us_occ' = the EASearch DB).
# 0.3.62: es_cnmv_sanctions/kr_fss/nl_acm added in alphabetical slots (es_boe < es_cnmv_sanctions <
# eu_cijeu; it_arera < kr_fss < kr_law; nl_acm < nl_rechtspraak — batch E4; the SECOND cnmv provider id
# beside the 0.3.44 company-domain es_cnmv entidades register, the wb/wb_proc precedent).
# 0.3.63: au_accc/in_cci/jp_jftc added in alphabetical slots (at_ris < au_accc < au_frl;
# ie_sipo < in_cci < in_indiacode; it_arera < jp_jftc < kr_fss — batch E5; JP's first legal faces).
# 0.3.64: gb_nmw added in alphabetical slot (gazette < gb_nmw < idb — batch E6, the negative-list
# batch; us_cftc gains redlist+dispositions ops in place, no new module).
