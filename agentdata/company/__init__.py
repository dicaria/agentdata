"""company domain package — provider adapters flat layout (one source per file) + faces/cli (0.2.6 per-domain reorg)."""
from . import (br_bacen, br_bndes, ca_osb, cf, ch_zefix, chi_bacp, co_rues, cz_ares, de_inso,  # noqa: F401
               de_register, edgar_cik, edgar_fts, es_borme, es_cnmv, es_oepm, fdic_bankfind, eu_eiopa,
               fi_ytj, fr_inpi, fr_recherche, fr_regafi, fts, gg_gfsc, gleif, in_sebi_intm, je_jfsc,
               jp_fsa, jp_jplatpat, kr_hometax, kr_kipris, kz_gbd_ul, lacity, no_brreg, nzco, nyc_dcwp,
               ror, ru_cbr_credit, sg_datagovsg, ted, tr_bddk, tr_kap, tr_spk_borsa, tx_tdlr,
               usaspending, vies, wa_doh)
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

