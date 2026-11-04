"""euvd — ENISA EU Vulnerability Database services API (euvdservices.enisa.europa.eu; keyless).

Research chapter 91 (2026-11-02, probe corpus tmp/probe-round3/): the SPA shell host
euvd.enisa.europa.eu answers /api/v1/* with the shell HTML (dead paths) — the real API base
https://euvdservices.enisa.europa.eu/api hides in the main.61fcf30f.js bundle. Two ops stand up
as faces: the point lookup /api/enisaid?id= (CVE or EUVD code; unknown id = HTTP 404 with
{"error":"EUVD not found"} — probed 2026-11-03 tmp/probe-euvd-0325/, a clean carried not-found)
and the EU KEV rolling window /api/exploitedvulnerabilities (a rolling window, NOT the full
history — the 399,311-row euvd_id<->cve_id mapping travels the raw side as the 12MB
/api/dump/cve-euvd-mapping CSV and is not a face). /api/criticalvulnerabilities and
/api/advisory stayed uncovered this round (recorded, not adopted — the two faces cover the
screening use cases).

Two shape walls (everything else passes through under its row key):
  * Java date format — every date field arrives as "Apr 12, 2024, 7:20:00 AM" (MMM d, yyyy,
    h:mm:ss AM); normalized locally with a fixed month table (datetime.strptime %b is
    locale-bound and would break on a non-English host); unparsable values pass through
    verbatim rather than crash.
  * references / aliases arrive as newline-joined STRINGS — split into lists.

Rate: no published limit -> polite 0.5 rps / burst 2. TTL: 24h (records mutate as member-state
CSAF advisories attach; the rolling window refreshes continuously).
"""
from ..errors import SdkError

provider = {
    "id": "euvd",
    "baseUrl": "https://euvdservices.enisa.europa.eu",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "vulnerability": {"path": "/api/enisaid", "notFound": [404]},
        "exploited": {"path": "/api/exploitedvulnerabilities"},
    },
    "ttl": {"vulnerability": 24 * 3600, "exploited": 24 * 3600},
}

import re

_ID_RE = re.compile(r"^(?:CVE|EUVD)-\d{4}-\d{4,}$")

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def _iso(s):
    """Java "MMM d, yyyy, h:mm:ss AM" -> ISO "yyyy-MM-ddTHH:MM:SS" (fixed month table —
    strptime %b is locale-dependent; unparsable values pass through verbatim, never crash)."""
    if not isinstance(s, str) or not s:
        return s
    try:
        head, year, clock = s.split(",")
        mon, day = head.strip().split(" ")
        hhmmss, ampm = clock.strip().split(" ")
        h, m, sec = (int(x) for x in hhmmss.split(":"))
        if ampm.upper() == "PM" and h != 12:
            h += 12
        elif ampm.upper() == "AM" and h == 12:
            h = 0
        return f"{int(year):04d}-{_MONTHS[mon.lower()]:02d}-{int(day):02d}T{h:02d}:{m:02d}:{sec:02d}"
    except (ValueError, KeyError, IndexError, AttributeError, TypeError):
        return s


def _lines(s):
    """newline-joined upstream strings -> list (references / aliases arrive as one string)."""
    if not isinstance(s, str) or not s:
        return []
    return [ln for ln in (x.strip() for x in s.splitlines()) if ln]


def _norm_id(vuln_id):
    t = str(vuln_id or "").strip().upper()
    if not _ID_RE.match(t):
        raise SdkError("usage_error", provider="euvd",
                       detail=f"id \"{vuln_id}\" is not a CVE or EUVD code "
                              "(forms: CVE-2024-3400 / EUVD-2024-31989; the point lookup takes either)")
    return t


def _product_row(p):
    prod = p.get("product") or {}
    return {"vendor": ((prod.get("vendor") or {}).get("name")),
            "product": prod.get("name"),
            "version": p.get("product_version")}


def _advisory_row(x):
    a = x.get("advisory") or {}
    return {"id": a.get("id"),
            "source": (a.get("source") or {}).get("name"),
            "summary": a.get("summary"),
            "date_published": _iso(a.get("datePublished"))}


def _row(d):
    """One EUVD record — the point-lookup dict and the exploited-list rows share the shape
    (list rows may simply lack enisaIdProduct/enisaIdAdvisory/enisaIdVulnerability)."""
    return {"euvd_id": d.get("id"),
            "aliases": _lines(d.get("aliases")),
            "description": d.get("description"),
            "base_score": d.get("baseScore"),
            "base_score_version": d.get("baseScoreVersion"),
            "base_score_vector": d.get("baseScoreVector"),
            "epss": d.get("epss"),
            "exploited_since": _iso(d.get("exploitedSince")),
            "date_published": _iso(d.get("datePublished")),
            "date_updated": _iso(d.get("dateUpdated")),
            "assigner": d.get("assigner"),
            "references": _lines(d.get("references")),
            "products": [_product_row(p) for p in d.get("enisaIdProduct") or []],
            "vendors": [(v.get("vendor") or {}).get("name")
                        for v in d.get("enisaIdVendor") or []],
            "advisories": [_advisory_row(x) for x in d.get("enisaIdAdvisory") or []]}


def vulnerability_raw(vuln_id, *, cache=None, no_cache=False):
    """-> {row, params, _meta}; /api/enisaid?id= — one full record, keyed by CVE or EUVD code.
    Unknown id: upstream 404 {"error":"EUVD not found"} -> upstream_not_found (carried clean)."""
    from ..transport import call_provider

    code = _norm_id(vuln_id)
    r = call_provider(provider, "vulnerability", {"id": code}, cache=cache, no_cache=no_cache)
    data = r["data"]
    if not isinstance(data, dict) or not data.get("id"):
        raise SdkError("upstream_unavailable", provider="euvd",
                       detail="The EUVD enisaid answer is not a vulnerability record")
    return {"row": _row(data), "params": {"id": code}, "_meta": r}


def exploited_raw(*, limit=50, cache=None, no_cache=False):
    """-> {count, rows, params, _meta}; /api/exploitedvulnerabilities — the EU KEV rolling
    window (probed 2026-11-02: 4 rows; the window grows as ENISA tracks new in-the-wild
    exploitation). No upstream params; limit is a LOCAL slice (envelope-blast guard, the cisa
    kev posture — the full-history leg is the raw-side mapping dump, not this face)."""
    from ..transport import call_provider

    r = call_provider(provider, "exploited", {}, cache=cache, no_cache=no_cache)
    data = r["data"]
    if not isinstance(data, list):
        raise SdkError("upstream_unavailable", provider="euvd",
                       detail="The EUVD exploitedvulnerabilities answer is not the rolling list")
    rows = [_row(x) for x in data]
    n = max(1, int(limit))
    return {"count": min(len(rows), n), "total": len(rows), "rows": rows[:n],
            "params": {"limit": n}, "_meta": r}
