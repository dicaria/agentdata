"""healthcare domain package — flat provider adapters (one file per source) + faces/cli (domain reorg in 0.2.6).

One domain per package: provider adapters laid flat (one source per file) + faces/cli.
"""
from . import (br_cnes, ctgov, dailymed, epmc, eudamed, gudid, jp_navii, mesh,  # noqa: F401
               fda_crl, fda_devices, fda_drugs, fda_recalls, rxnav, shortages, au_tga, gb_mhra,
               ca_dpd, ca_mdall, rasff, safety_gate, us_npi)
# 0.3.53: us_npi added at the tail (safety_gate < us_npi).
# 0.3.56: jp_navii added in alphabetical slot (gudid < jp_navii < mesh — 'g'<'j'<'m').
# 0.3.58: br_cnes added at the head (br_cnes < ctgov — the domain's first BR face).
