"""cisa_kev — CISA Known Exploited Vulnerabilities (KEV) Catalog provider (catalog of vulnerabilities
exploited in the wild; keyless).

Keyless static feed (~1.8MB single shot, probed 2026-10-26, count=1756). Upstream takes no query params —
all cve/ransomware filtering is a **local post-filter** (echoed in input; upstream stays pure with empty params).
The catalog updates at weekly cadence (the catalogVersion date stamp goes into reason).
"""
provider = {
    "id": "cisa-kev",
    "baseUrl": "https://www.cisa.gov",
    "rate": {"rps": 0.25, "burst": 2},
    "ops": {
        "catalog": {"path": "/sites/default/files/feeds/known_exploited_vulnerabilities.json",
                    "method": "GET", "idempotent": True},
    },
    "ttl": {"catalog": 24 * 3600},
}


def _row(v):
    return {
        "cve_id": v.get("cveID"), "vendor_project": v.get("vendorProject"),
        "product": v.get("product"), "vulnerability_name": v.get("vulnerabilityName"),
        "date_added": v.get("dateAdded"), "due_date": v.get("dueDate"),
        "known_ransomware_campaign_use": v.get("knownRansomwareCampaignUse"),
        "short_description": v.get("shortDescription"),
        "required_action": v.get("requiredAction"), "notes": v.get("notes"),
        "cwes": v.get("cwes") or [],
    }


def catalog_raw(*, cache=None, no_cache=False):
    """→ {catalog_version, date_released, count_total, vulnerabilities, _meta}; the feed reshaped as-is.
    No upstream params (static feed); the local post-filter happens at the face layer (the provider keeps the
    zero-hidden-params discipline)."""
    from ..transport import call_provider

    r = call_provider(provider, "catalog", {}, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    vulns = [_row(v) for v in d.get("vulnerabilities") or []]
    return {"catalog_version": d.get("catalogVersion"), "date_released": d.get("dateReleased"),
            "count_total": d.get("count"), "vulnerabilities": vulns, "_meta": r}
