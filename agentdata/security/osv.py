"""osv — OSV.dev API provider (open-source package vulnerability queries; keyless).

Keyless (the api.osv.dev public query face, polite rate 1 rps). POST /v1/query:
package{name,ecosystem}+version (version may be omitted = all known vulns for the package — upstream semantics);
upstream returns an empty vulns[] for an unknown ecosystem (**a silent false negative**) — this face blocks that
with a closed-set check locally (the OSV docs enumeration).
The single-vuln detail face is GET /v1/vulns/{id} (keyless); no face stood up for it this round
(the screening face already covers the use cases).
"""
provider = {
    "id": "osv",
    "baseUrl": "https://api.osv.dev",
    "rate": {"rps": 1, "burst": 5},
    "ops": {
        "query": {"path": "/v1/query", "method": "POST", "idempotent": True},
    },
    "ttl": {"query": 24 * 3600},
}

# OSV docs ecosystem enumeration (normalized case-insensitively to the canonical form); upstream silently
# returns empty for unknown values — the false-negative guard lives here
ECOSYSTEMS = {
    "npm": "npm", "pypi": "PyPI", "go": "Go", "maven": "Maven", "crates.io": "crates.io",
    "rubygems": "RubyGems", "nuget": "NuGet", "packagist": "Packagist", "debian": "Debian",
    "alpine": "Alpine", "linux": "Linux", "oss-fuzz": "OSS-Fuzz", "hex": "Hex",
    "pub": "Pub", "conda": "Conda", "android": "Android", "github actions": "GitHub Actions",
}


def query_raw(package, ecosystem, *, version=None, page_token=None,
              cache=None, no_cache=False):
    """→ {count, vulns, next_page_token, params, _meta}; /v1/query POST with verbatim names.
    ecosystem closed-set check (case-insensitive → canonical form); version may be omitted = all known vulns
    (upstream semantics).
    Paging: upstream paginates past >1000 vulns or >20s (official docs), the response carries next_page_token —
    surfaced as-is + pass it back as page_token to continue until it goes absent; an occasional
    "token-only, no rows" page must still be continued (per the docs).
    Probed 2026-10-28: Linux/Kernel 2719 rows on the first page + a token present.
    Recorded, not adopted (2026-10-28 audit): purl (an alternative to package{name,ecosystem}, the toolchain
    form) and commit (another key for version lookups) — the screening name+ecosystem form already covers the
    use cases, so no params were added."""
    from ..transport import call_provider
    from ..errors import SdkError

    name = str(package or "").strip()
    if not name:
        raise SdkError("usage_error", provider="osv", detail="osv_vulns requires package (the package name)")
    eco_canon = ECOSYSTEMS.get(str(ecosystem or "").strip().lower())
    if not eco_canon:
        raise SdkError("usage_error", provider="osv",
                       detail=f"ecosystem \"{ecosystem}\" is not in the OSV enumeration ("
                              + ", ".join(sorted(set(ECOSYSTEMS.values()))) +
                              "; upstream silently returns empty for unknown values — the false-negative guard lives here; treat the OSV docs as authoritative for new values")
    body = {"package": {"name": name, "ecosystem": eco_canon}}
    if version not in (None, ""):
        body["version"] = str(version).strip()
    if page_token not in (None, ""):
        body["page_token"] = str(page_token).strip()
    r = call_provider(provider, "query", body, cache=cache, no_cache=no_cache)
    vulns = (r["data"] or {}).get("vulns") or []
    rows = [{
        "id": v.get("id"),
        "aliases": v.get("aliases") or [],
        "summary": v.get("summary"),
        "published": v.get("published"), "modified": v.get("modified"),
        "severity": v.get("severity") or [],
        "advisory_url": (f"https://github.com/advisories/{v['id']}"
                         if str(v.get("id") or "").startswith("GHSA-") else None),
    } for v in vulns]
    return {"count": len(rows), "vulns": rows,
            "next_page_token": (r["data"] or {}).get("next_page_token"),
            "params": body, "_meta": r}
