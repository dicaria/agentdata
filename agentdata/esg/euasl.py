"""euasl — EU Air Safety List (third-country carriers banned or restricted, European Commission) file-catalog provider (keyless).

esg transport-compliance axis (2026-11-02, 0.3.22 batch): the list lives on a Liferay page
(transport.ec.europa.eu/transport-themes/eu-air-safety-list_en — the pre-migration /aviation-policy path is
dead 404) whose only machine-readable form is a single XLSX (~28KB: Annex A = carriers subject to an
operating ban, 188 rows measured 2026-10-20; Annex B = carriers operating under restrictions and conditions,
2 rows — AIR KORYO / IRAN AIR) plus 24 official-language PDF renditions off the same page. The SDK does not
proxy binary bodies (the JSON-only transport would corrupt a zip — same posture as eutl/thetis_mrv): this
face returns the live download catalog. Measured shape (2026-11-02, fresh page 200/127KB):
- 25 download links, href="/document/download/<uuid>_<lang>?filename=air-safety-list[_<lang>][.ext]" —
  **the document UUIDs rotate on every republication** (they are publish-time content ids, not stable keys),
  so reconcile harvests against this listing and never guess file names. One XLSX master (uuid 67b75752-…,
  lang en) + 24 language PDFs (uuid 3195fabb-…; the hr rendition carries an _2 suffix on the filename only —
  the language token is still the path segment).
- Update cadence: "whenever the Commission considers it necessary" (historically several revisions a year).
- The XLSX parses offline but not naively: ~71 self-closing <c/> cells in the sheet mean position-guessing
  fails — cell references (r="A<n>") are the parse key, sharedStrings holds the strings (batch-pipeline
  concern; the catalog face is what keeps the link honest).
TTL 1 day (the page re-renders on each republication; links are stable between them). Politeness tier 0.5 rps.
"""
import re

_DOWNLOAD_RE = re.compile(r'href="(/document/download/([^"]+?))"')
_FILENAME_RE = re.compile(r'filename=([^&"]+)')

provider = {
    "id": "euasl",
    "baseUrl": "https://transport.ec.europa.eu",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "page": {"path": "/transport-themes/eu-air-safety-list_en", "accept": "text"},  # Liferay HTML — links parsed at this layer
    },
    "ttl": {"page": 86400},
}


def datasets_from_upstream(html):
    """Page HTML -> download-catalog rows (pure function, offline-testable).

    rows are sorted xlsx-master first then by language code (deterministic); download_path is a site path
    (prefix the baseUrl — the batch pipeline assembles the URL from it); `master` carries the machine-readable
    XLSX row (or None — the page without the xlsx link is an abnormal state the caller surfaces)."""
    rows, seen = [], set()
    for full, tail in _DOWNLOAD_RE.findall(html or ""):
        if full in seen:
            continue
        seen.add(full)
        path_part, _, query = tail.partition("?")  # the query (?filename=…) rides the href too — split it off before the language split
        uuid, _, lang = path_part.rpartition("_")  # uuid carries hyphens only, the language token is the last path segment
        fm = _FILENAME_RE.search(query)
        file_name = fm.group(1) if fm else None
        fmt = ("xlsx" if (file_name or "").lower().endswith(".xlsx")
               else "pdf" if (file_name or "").lower().endswith(".pdf") else None)
        rows.append({
            "document_id": uuid or None,
            "language": lang or None,
            "file_name": file_name,
            "format": fmt,
            "download_path": full,
        })
    rows.sort(key=lambda r: (0 if r["format"] == "xlsx" else 1, r["language"] or "", r["file_name"] or ""))
    master = next(({"file_name": r["file_name"], "download_path": r["download_path"]}
                   for r in rows if r["format"] == "xlsx"), None)
    return {"rows": rows, "count": len(rows), "master": master}


def datasets_raw(*, cache=None, no_cache=False):
    """0.3.22 flat face internals: the live EU Air Safety List download catalog in one request (upstream has no filter params).

    -> {rows[], count, master, params, _meta} — params={} (zero upstream params)."""
    from ..transport import call_provider

    params = {}
    r = call_provider(provider, "page", params, cache=cache, no_cache=no_cache)
    return {**datasets_from_upstream(r["data"]), "params": params, "_meta": r}
