"""security cli — domain command registration (split per domain in 0.2.6, moved in from the root cli.py).

register(v, g): registers the flat commands on the domain subparser (g = the root _leaf_globals factory,
passed in to avoid a cli↔domain-cli cycle); FLAT = the flat dispatch table, merged by the root cli for main.
"""
import argparse

def register(v, g):
    f1 = v.add_parser("cisa_kev_catalog", parents=[g()],
                      help="CISA Known Exploited Vulnerabilities catalog — static feed ~1.8MB",
                      description="CISA Known Exploited Vulnerabilities catalog (realtime, local execution; static feed ~1.8MB; --cve and --ransomware are local post-filters, upstream stays empty-param pure; catalog updates weekly, catalogVersion echoed in reason)")
    f1.add_argument("--cve", default=None, help="CVE id exact lookup (local filter, e.g. CVE-2021-44228)")
    f1.add_argument("--ransomware", action="store_true",
                    help="Only entries with known ransomware campaign use (local filter)")
    f1.add_argument("--limit", type=int, default=50, help="Rows to return (default 50; full catalog ~1,756 rows — page instead of dumping)")

    f2 = v.add_parser("euvd_exploited", parents=[g()],
                      help="ENISA EU KEV rolling window — exploited in the wild per EU tracking",
                      description="ENISA EU KEV rolling window — vulnerabilities currently exploited in the wild per EU tracking (realtime, local execution; the window refreshes continuously; the 399,311-row full EUVD↔CVE mapping is a raw-side 12MB dump, not this face; --limit is a local slice)")
    f2.add_argument("--limit", type=int, default=50, help="Rows to return (default 50; the rolling window is small but grows)")

    f3 = v.add_parser("euvd_vulnerability", parents=[g()],
                      help="ENISA EUVD single-vulnerability full record by CVE or EUVD code",
                      description="ENISA EUVD single-vulnerability full record by CVE or EUVD code (realtime, local execution; richer than the NVD public face — CVSS vector+version, EPSS inline, exploitedSince, CVE+GHSA aliases, vendor×product×version ranges, EU member-state CSAF advisories; dates are Java-format upstream and ISO-normalized locally; unknown id = 404 carried as not-found)")
    f3.add_argument("--id", required=True,
                    help="CVE or EUVD code (e.g. CVE-2024-3400 or EUVD-2024-31989)")

    f4 = v.add_parser("osv_vulns", parents=[g()],
                      help="Open-source package vulnerability query",
                      description="Open-source package vulnerability query (realtime, local execution; OSV /v1/query POST; ecosystem is a closed set validated locally because upstream silently returns empty for unknown values; version omitted = all known vulns for the package)")
    f4.add_argument("--package", required=True, help="Package name (e.g. lodash)")
    f4.add_argument("--ecosystem", required=True,
                    help="OSV ecosystem (npm/PyPI/Go/Maven/crates.io/RubyGems/NuGet/Packagist/Debian/Alpine/Linux/OSS-Fuzz/Hex/Pub/Conda/Android/GitHub Actions)")
    f4.add_argument("--version", default=None, help="Package version (omit = all known vulns)")
    f4.add_argument("--page-token", dest="page_token", default=None,
                    help="Continuation token from a prior response's result.next_page_token (upstream paginates at >1000 vulns or >20s)")

FLAT = {
    "cisa_kev_catalog": lambda a: {"cve": a.cve, "ransomware": a.ransomware, "limit": a.limit},
    "euvd_exploited": lambda a: {"limit": a.limit},
    "euvd_vulnerability": lambda a: {"id": a.id},
    "osv_vulns": lambda a: {"package": a.package, "ecosystem": a.ecosystem,
                            "version": a.version, "page_token": a.page_token},
}


# 0.3.10 jurisdiction chapter: face -> jurisdiction (default = the issuing authority's jurisdiction;
# institutions covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2 + EU + GLOBAL) — the root cli.py merges this into _JURISDICTION; the success envelope carries a jurisdiction chapter
COUNTRY = {
    "cisa_kev_catalog": "US",
    "euvd_exploited": "EU",
    "euvd_vulnerability": "EU",
    "osv_vulns": "GLOBAL",
}
