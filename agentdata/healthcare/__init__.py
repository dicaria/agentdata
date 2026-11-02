"""healthcare domain package — flat provider adapters (one file per source) + faces/cli (domain reorg in 0.2.6).

One domain per package: provider adapters laid flat (one source per file) + faces/cli.
"""
from . import (ctgov, dailymed, epmc, eudamed, gudid, mesh,  # noqa: F401
               fda_crl, fda_devices, fda_drugs, fda_recalls, rxnav, shortages, au_tga, gb_mhra)
