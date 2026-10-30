"""security cli — domain command registration (split per domain in 0.2.6, moved in from the root cli.py).

register(v, g): registers the flat commands on the domain subparser (g = the root _leaf_globals factory,
passed in to avoid a cli↔domain-cli cycle); FLAT = the flat dispatch table, merged by the root cli for main.
"""
import argparse

def register(v, g):
    f1 = v.add_parser("cisa_kev_catalog", parents=[g()],
                      description="CISA Known Exploited Vulnerabilities catalog (realtime, local execution; static feed ~1.8MB; --cve and --ransomware are local post-filters, upstream stays empty-param pure; catalog updates weekly, catalogVersion echoed in reason)")
    f1.add_argument("--cve", default=None, help="CVE id exact lookup (local filter, e.g. CVE-2021-44228)")
    f1.add_argument("--ransomware", action="store_true",
                    help="Only entries with known ransomware campaign use (local filter)")
    f1.add_argument("--limit", type=int, default=50, help="Rows to return (default 50; full catalog ~1,756 rows — page instead of dumping)")

    f2 = v.add_parser("osv_vulns", parents=[g()],
                      description="Open-source package vulnerability query (realtime, local execution; OSV /v1/query POST; ecosystem is a closed set validated locally because upstream silently returns empty for unknown values; version omitted = all known vulns for the package)")
    f2.add_argument("--package", required=True, help="Package name (e.g. lodash)")
    f2.add_argument("--ecosystem", required=True,
                    help="OSV ecosystem (npm/PyPI/Go/Maven/crates.io/RubyGems/NuGet/Packagist/Debian/Alpine/Linux/OSS-Fuzz/Hex/Pub/Conda/Android/GitHub Actions)")
    f2.add_argument("--version", default=None, help="Package version (omit = all known vulns)")
    f2.add_argument("--page-token", dest="page_token", default=None,
                    help="Continuation token from a prior response's result.next_page_token (upstream paginates at >1000 vulns or >20s)")

FLAT = {
    "cisa_kev_catalog": lambda a: {"cve": a.cve, "ransomware": a.ransomware, "limit": a.limit},
    "osv_vulns": lambda a: {"package": a.package, "ecosystem": a.ecosystem,
                            "version": a.version, "page_token": a.page_token},
}


# 0.3.10 jurisdiction chapter: face -> jurisdiction (default = the issuing authority's jurisdiction;
# institutions covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2 + EU + GLOBAL) — the root cli.py merges this into _JURISDICTION; the success envelope carries a jurisdiction chapter
COUNTRY = {
    "cisa_kev_catalog": "US",
    "osv_vulns": "GLOBAL",
}
