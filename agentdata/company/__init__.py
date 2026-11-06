"""company domain package — provider adapters flat layout (one source per file) + faces/cli (0.2.6 per-domain reorg)."""
from . import (br_bacen, ca_osb, cf, ch_zefix, chi_bacp, co_rues, cz_ares, de_inso,  # noqa: F401
               edgar_cik, edgar_fts, es_borme, es_cnmv, fdic_bankfind, fi_ytj,
               fr_recherche, fts, gg_gfsc, gleif, in_sebi_intm, je_jfsc, jp_fsa,
               kr_hometax, kz_gbd_ul, lacity, no_brreg, nzco, nyc_dcwp, ror,
               ru_cbr_credit, sg_datagovsg, ted, tr_bddk, tr_spk_borsa, tx_tdlr,
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
