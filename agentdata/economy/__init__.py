"""economy domain package — flat provider adapters (one file per source) + faces/cli.

The eighth domain (0.3.23): the country-level denominator layer — macro indicators, reference
rates, official statistics and the trade mirror. The subject is the country (ISO code), never the
company: these faces emit no company fact and occupy no rec_type; they exist so the other five
domains can normalise against real numbers (TAM denominators, amount conversion, income-band
buyer screens).
"""
from . import (bis, ecb, eurostat, fred, ilo_stat, imf_sdmx,  # noqa: F401
               un_comtrade, unsd_sdg, wb, who_xmart)
