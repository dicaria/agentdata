"""gb_mhra — UK MHRA medicines & medical-device safety-alert face provider
(www.gov.uk search/content API; keyless — the same host and contract family as the
gb_cma case chain).

healthcare domain (0.3.16; admitted 2026-10-30, probed). Shape verified 2026-10-30:
GET /api/search.json?filter_format=medical_safety_alert&q=&count=&start=
  → {results:[{title,link:'/drug-device-alerts/<slug>',_id≡base_path,public_timestamp,
     organisations:[…],document_type:'medical_safety_alert',…}], total, start, aggregates}
  — filter_format=medical_safety_alert is this face's semantics (a fixed param, not a
    user param); q/count/start go through with upstream verbatim names. q= is a company-
    name penetration channel into the alert corpus (measured: Abbott → 160 alerts across
    2019-2026). **Pit nailed: rows returned under a q= query drop the link field — the
    base_path then lives only in _id (link and _id are both the base_path on this API);
    the row mapper reads link first, falling back to _id.** total=1,462 measured
    2026-10-30.
GET /api/content/drug-device-alerts/{slug}
  → {content_id(UUID stable key), title, description, first_published_at, public_updated_at,
     updated_at, withdrawn_notice, details:{body(HTML), change_history:[{note,public_timestamp}],
     attachments:[…], metadata:{alert_type, issued_date, medical_specialism:[…]}},
     links:{organisations(MHRA),…}}
  — **Pit nailed: the content API has no .json variant — /api/content<base_path>.json
    returns the gov.uk 404 HTML page (a silent near-miss, not an error body); the op path
    carries no suffix and a pasted slug with a trailing .json is stripped.**
  — alert_type (e.g. medicines-recall-notification / device-field-safety-notice) and
    issued_date from details.metadata are the MHRA-golden fields.
Param-minimalism pitfall (same host as gb_cma): unprobed param combinations → 422 — this
face accepts only q/count/start, do not widen it.
TTL: search 24h (the alert stream lands at daily-to-weekly cadence) / alert 7 days
(alert pages change slowly; change_history records the evolution); polite rate 1 rps
(gov.uk publishes no search-API quota — conservative, same as gb_cma).
"""
from ..errors import SdkError

provider = {
    "id": "gb_mhra",
    "baseUrl": "https://www.gov.uk",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "alerts": {"path": "/api/search.json"},               # params: q, count, start (filter_format is fixed for this face)
        "alert": {"path": "/api/content/drug-device-alerts/{slug}"},  # slug = the tail of the alert-page base_path (link or _id of the search row)
    },
    "ttl": {"alerts": 24 * 3600, "alert": 7 * 86400},
}


def alerts_from_upstream(data, size):
    """Upstream search response → alert rows (pure function, offline-testable)."""
    rows = [{
        "slug": ((r.get("link") or r.get("_id") or "").removeprefix("/drug-device-alerts/") or None),
        # ^ join key into the detail face; under q= the rows drop link — the base_path then
        #   lives only in _id (both ≡ base_path on this API; do not pass _id off as content_id)
        "title": r.get("title"),                      # alert name = "Class 2 Medicines Recall: <firm>, <product>" / "MDA/2020/019 …" forms
        "public_timestamp": r.get("public_timestamp"),
        "organisations": [o.get("title") for o in (r.get("organisations") or []) if o.get("title")],
        "url": ("https://www.gov.uk" + p) if (p := (r.get("link") or r.get("_id"))) else None,
    } for r in ((data or {}).get("results") or [])]
    return {
        "rows": rows, "count": len(rows), "limit_applied": size,
        "total": data.get("total") if isinstance(data, dict) and isinstance(data.get("total"), int) else None,
    }


def alerts_raw(q=None, *, count=20, start=0, cache=None, no_cache=False):
    """Flat-panel low-level face: q/count/start go through with verbatim names
    (filter_format=medical_safety_alert fixed).

    → {rows[], count, limit_applied, total, params, _meta}. A missing q = full-register
    enumeration (1,462 live alerts counted 2026-10-30); count politeness wall 1-100
    (same host contract as gb_cma — upstream walls unprobed, keep the family cap);
    start = offset paging."""
    from ..transport import call_provider

    term = str(q or "").strip() or None
    size = int(count) if count is not None else 20  # explicit None check — 0 being swallowed by `or` was a same-type bug caught by a test
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="gb_mhra",
                       detail=f"count must be 1-100 (politeness cap; the gov.uk search API publishes no quota — same family cap as gb_cma), got \"{count}\"")
    off = int(start) if start is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="gb_mhra", detail=f"start must be an offset ≥0, got \"{start}\"")
    params = {"filter_format": "medical_safety_alert", "count": size, "start": off}
    if term:
        params["q"] = term
    r = call_provider(provider, "alerts", params, cache=cache, no_cache=no_cache)
    return {**alerts_from_upstream(r["data"], size), "params": params, "_meta": r}


def _clean_slug(slug):
    s = str(slug or "").strip()
    # Tolerance: a pasted full base_path (/drug-device-alerts/<slug> or https://www.gov.uk/drug-device-alerts/<slug>)
    # gets its prefix stripped; a trailing .json (the 404 trap shape) is stripped too
    for pre in ("https://www.gov.uk/drug-device-alerts/", "http://www.gov.uk/drug-device-alerts/", "/drug-device-alerts/"):
        if s.startswith(pre):
            s = s[len(pre):]
    s = s.strip("/")
    if s.endswith(".json"):
        s = s[: -len(".json")]
    if not s or "/" in s:
        raise SdkError("usage_error", provider="gb_mhra",
                       detail=f"slug must be the alert-page tail segment (e.g. class-2-medicines-recall-xeal-pharma-clopidogrel-oral-liquids-all-strengths-el-26-a-slash-43, "
                              f"echoed verbatim from the search row's slug field): {slug}")
    return s


def alert_raw(slug, *, cache=None, no_cache=False):
    """→ the full single-alert dossier (content API, no .json suffix — with it gov.uk
    serves the 404 HTML page; content_id = the UUID stable key).
    alert_type/issued_date = the MHRA metadata fields; attachments = the notice PDF family."""
    from ..transport import call_provider

    s = _clean_slug(slug)
    r = call_provider(provider, "alert", {"slug": s}, cache=cache, no_cache=no_cache)
    x = r["data"] or {}
    det = x.get("details") or {}
    md = det.get("metadata") or {}
    return {
        "slug": s,
        "content_id": x.get("content_id"),
        "title": x.get("title"),
        "description": x.get("description") or None,
        "document_type": x.get("document_type"),
        "alert_type": md.get("alert_type"),           # e.g. medicines-recall-notification / device-field-safety-notice (MHRA metadata)
        "issued_date": md.get("issued_date"),         # e.g. 2026-10-26 (MHRA metadata)
        "first_published_at": x.get("first_published_at"),
        "public_updated_at": x.get("public_updated_at"),
        "updated_at": x.get("updated_at"),
        "withdrawn": bool(x.get("withdrawn_notice")),
        "change_history": det.get("change_history") or [],      # [{note, public_timestamp}] newest→oldest (last = First published)
        "attachments": [{"title": a.get("title"), "url": a.get("url"),
                         "content_type": a.get("content_type"), "content_id": a.get("content_id")}
                        for a in (det.get("attachments") or [])],
        "body_html": det.get("body") or "",                     # the alert-page body HTML (recall/action instructions)
        "organisations": [o.get("title") for o in ((x.get("links") or {}).get("organisations") or [])
                          if o.get("title")],
        "url": f"https://www.gov.uk/drug-device-alerts/{s}",
        "_meta": r,
    }
