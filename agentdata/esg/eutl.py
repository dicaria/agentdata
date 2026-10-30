"""eutl — EU Emissions Trading System registry (Union Registry) official bulk-download catalog provider (keyless).

Sibling face of the esg batch pipeline: EUTL's 15 bulk files (the carbon-emissions surface) previously had
download coordinates but no API face; 2026-10-29 overturned that: the portal ships its own catalog API
`GET /api/data-download` that returns a keyless JSON array of 15 files
`{name, pane_index, group_index, sort_index, url, action}` — this face adopts it as the **download-catalog
query face** (the file bodies still go through the batch pipeline; this SDK does not proxy large-file downloads).
Measured shape (2026-10-29):
- Host **union-registry-data.ec.europa.eu** (the old euetsdata.europa.eu is ENOTFOUND — do not probe it again).
- The 15 files fall into three tiers (measured 4+10+1): 4 Azure daily extracts
  (dlsclimabi.blob.core.windows.net…csv.gz: Accounts/Operators/Operators Yearly Activity/Registry Holdings Daily)
  + 1 Transactions file + 10 climate.ec.europa.eu yearly files (Compliance 2021-2025 x5 + Verified Emissions 2021-2025).
- Yearly file URLs are direct document/download/<uuid> links (no suffix); daily file URLs carry the cadence in the path.
- The action field is a portal frontend hook name (d_accounts_daily etc.), not a stable contract — pass through, do not interpret.
TTL 1 day (the catalog file set rolls slowly); politeness tier 0.5 rps.
"""
from ..errors import SdkError

provider = {
    "id": "eutl",
    "baseUrl": "https://union-registry-data.ec.europa.eu",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "datasets": {"path": "/api/data-download"},  # no params: one request returns the whole 15-file catalog
    },
    "ttl": {"datasets": 86400},
}


def _cadence(name, url):
    """Derive the cadence tier from the file name/URL: daily = Azure daily extract / yearly = portal yearly file /
    static = the Transactions file (it hangs on the same climate.ec.europa.eu domain but is not a rolling yearly
    file — split by name; measured 15 files = 4+10+1)."""
    n, u = name or "", url or ""
    if "blob.core.windows.net" in u:
        return "daily"
    if "transaction" in n.lower():
        return "static"
    if "climate.ec.europa.eu" in u:
        return "yearly"
    return "other"


def datasets_from_upstream(data):
    """Upstream response -> datasets face result (pure function, offline-testable)."""
    rows = [{
        "name": d.get("name"),
        "url": d.get("url"),                       # direct download link (daily = .csv.gz on Azure; yearly = document uuid)
        "cadence": _cadence(d.get("name"), d.get("url")),  # daily/yearly/other
        "group_index": d.get("group_index"),
        "pane_index": d.get("pane_index"),
        "sort_index": d.get("sort_index"),
        "action": d.get("action"),                 # portal frontend hook name, not a stable contract
    } for d in (data or []) if isinstance(d, dict)]
    return {"rows": rows, "count": len(rows)}


def datasets_raw(*, cache=None, no_cache=False):
    """0.3.2 flat face internals: the whole catalog in one request (upstream has no filter params — the client filters rows locally).

    -> {rows[], count, params, _meta} — params={} (zero upstream params, replayability proven by the empty param set)."""
    from ..transport import call_provider

    params = {}
    r = call_provider(provider, "datasets", params, cache=cache, no_cache=no_cache)
    return {**datasets_from_upstream(r["data"]), "params": params, "_meta": r}
