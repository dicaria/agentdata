"""agentdata.entries — 0.2.0 per-domain executable entry points (console_scripts healthcare/company/esg/legal;
research/security were born domains but missed registration in 0.2.2, fixed in 0.2.4).

Naming ruling (2026-10-23): the agentdata prefix on the call face is redundant — each domain gets its own
executable name (`healthcare fda_drug_shortages …`); the pip package name stays agentdata (the
`agentdata <domain> …` compatibility alias remains). argv is spliced straight into cli.main, so parsing,
exit codes and global flags are identical to the agentdata main entry.
"""
import sys

from .cli import main


def _domain_entry(domain: str):
    def run() -> int:
        return main([domain, *sys.argv[1:]])
    run.__name__ = domain
    run.__doc__ = f"agentdata {domain} — per-domain executable (args identical to `agentdata {domain} …`)"
    return run


healthcare = _domain_entry("healthcare")
company = _domain_entry("company")
esg = _domain_entry("esg")
legal = _domain_entry("legal")
procurement = _domain_entry("procurement")  # 0.3.0: the seventh domain
research = _domain_entry("research")   # added in 0.2.4 (formerly named grants — the alias was removed in 0.3.0; research is the only entry)
security = _domain_entry("security")   # added in 0.2.4 (born domain missed registration in 0.2.2)

