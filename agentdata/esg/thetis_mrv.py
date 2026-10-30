"""thetis_mrv — EU MRV ship emissions reporting (THETIS-MRV, EMSA) versioned bulk-file catalog provider (keyless).

esg port-state emissions axis (2026-10-29, 0.3.5 batch): mrv.emsa.europa.eu is an ExtJS shell (app.json ->
a 9.5MB app.js was reverse-engineered) that yielded the `/api/public-emission-report/` family of 19 endpoints;
this face adopts the **reporting-period x versioned-publication listing** query (the XLSX bodies, ~9.5MB per
file, still go through the batch pipeline; this SDK does not proxy large-file downloads — same posture as eutl).
Measured shape (2026-10-29):
- `reporting-periods` -> `[{value: 2018..2025}]`, eight years (2018 is the first reporting year).
- `downloadable-files` -> `{results: [{reportingPeriod, version, generationDate "DD-MM-YYYY HH:MM:SS",
  fileName}], total}` — **versioned rolling regeneration** (the 2025 file was v76 at the 10-20 probe and had
  already jumped to v76/v254 by 10-29; the 2024 file is v254) — reconcile against the listing, never guess
  file names; generationDate is mostly an early-morning batch (05:2x).
- The download path is the template `reporting-period-document/binary/{year}/{version}` (an XLSX attachment;
  Range is ignored and the full 200 body comes back — mind this in the batch pipeline). The file schema gains
  columns year by year (no CH₄/N₂O columns before 2024).
TTL 1 day (the version ledger rolls with the daily batch); politeness tier 0.5 rps.
"""

provider = {
    "id": "thetis_mrv",
    "baseUrl": "https://mrv.emsa.europa.eu",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "periods": {"path": "/api/public-emission-report/reporting-periods"},  # [{value: year}] in one response
        "files": {"path": "/api/public-emission-report/downloadable-files"},   # {results, total} version ledger
    },
    "ttl": {"periods": 86400, "files": 86400},
}

_BINARY_PATH = "/api/public-emission-report/reporting-period-document/binary/{period}/{version}"


def datasets_from_upstream(periods_data, files_data):
    """Two op responses -> datasets face result (pure function, offline-testable).

    rows are sorted by reportingPeriod descending (newest reporting period first); download_path is a template
    path (the batch pipeline assembles the download URL from it)."""
    periods = [p.get("value") for p in (periods_data or []) if isinstance(p, dict) and p.get("value") is not None]
    rows = []
    for f in ((files_data or {}).get("results") or []):
        if not isinstance(f, dict):
            continue
        period, version = f.get("reportingPeriod"), f.get("version")
        rows.append({
            "reporting_period": period,
            "version": version,
            "generation_date": f.get("generationDate"),   # "DD-MM-YYYY HH:MM:SS" (early-morning batch timestamp)
            "file_name": f.get("fileName"),               # "2025-v76-29102026-EU MRV Publication of information"
            "download_path": _BINARY_PATH.format(period=period, version=version) if period is not None and version is not None else None,
        })
    rows.sort(key=lambda r: (r["reporting_period"] or 0, r["version"] or 0), reverse=True)
    return {"rows": rows, "count": len(rows), "reporting_periods": periods}


def datasets_raw(*, cache=None, no_cache=False):
    """0.3.5 flat face internals: two requests merged into the reporting-period + version ledger (upstream has no filter params — the client filters rows locally).

    -> {rows[], count, reporting_periods[], params, _meta} — params={} (zero upstream params);
    _meta is the round trip of the files op (the main ledger surface); a failing periods op is a hard
    usage-level error (the whole result is untrustworthy)."""
    from ..transport import call_provider

    params = {}
    periods = call_provider(provider, "periods", params, cache=cache, no_cache=no_cache)
    files = call_provider(provider, "files", params, cache=cache, no_cache=no_cache)
    out = datasets_from_upstream(periods["data"], files["data"])
    return {**out, "params": params, "_meta": files}
