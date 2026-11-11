"""esg domain package — flat provider adapters (one file per source) + faces/cli (0.2.6 domain reorg).

One domain per package: provider adapters laid flat (one source per file) + faces/cli.
"""
from . import climatetrace, eiti, epa_frs, eutl, uk_fhrs  # noqa: F401
# 0.3.53: uk_fhrs added in alphabetical slot (thetis_mrv < uk_fhrs — tail).
# 0.3.54: euasl/paris_mou/thetis_mrv migrated to the transportation domain package (domain founding).
