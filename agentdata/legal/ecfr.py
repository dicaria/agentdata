"""ecfr — eCFR provider (the codified current state of US federal regulations: 50 titles, updated daily).

The counterpart face of the FR daily feed (the federalregister provider): eCFR = "where the current clause lives",
FR = "what changed today". www.ecfr.gov has two keyless faces (shape verified 2026-10-26):
GET /api/search/v1/results?query=<term>&per_page=N&page=P
  → {meta:{current_page,total_pages,total_count,max_score,description},results:[{starts_on,ends_on,type,
     hierarchy{title,subtitle,chapter,subchapter,part,subpart,subject_group,section,appendix}, headings{proper-noun form},
     hierarchy_headings{label form}, full_text_excerpt(HTML highlights), structure_index(int), change_types[], removed,
     reserved(bool), score}]}
GET /api/versioner/v1/titles.json → {titles:[{number,name,latest_amended_on,latest_issue_date,
  up_to_date_as_of,reserved}]} (reserved titles have up_to_date_as_of=null — treat as empty and skip, do not compare).
Param pitfalls (verified): paging only honors per_page/page — limit/max_results both 400 with
"Found unpermitted parameter" (the error body is the documentation); page=3 re-verified with meta.current_page=3 echoed
back and total_pages self-consistent = really bound.
TTL: both faces 24h (the code updates daily); polite rate 0.5 rps (no 429 seen during same-day probing — conservative start).
0.2.9 audit (2026-10-28): search gained a date param (point-in-time retrieval — the clause versions in force on that
date; probed asbestos: no date = 1,436 vs date=2024-01-01 = 339, rows carry starts_on/ends_on validity windows).
"""

import re as _re

_DATE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _coords_of(hierarchy):
    """Seven-level code coordinates → readable string (e.g. "40 CFR Part 763 Subpart E App. D")."""
    h = hierarchy or {}
    parts = []
    if h.get("title"):
        parts.append(f"{h['title']} CFR")
    if h.get("part"):
        parts.append(f"Part {h['part']}")
    if h.get("subpart"):
        parts.append(f"Subpart {h['subpart']}")
    if h.get("section"):
        parts.append(f"§ {h['section']}")
    if h.get("appendix"):
        parts.append(h["appendix"])
    return " ".join(parts)


def rows_from_upstream(data, size):
    """Upstream response → hit rows (pure function, offline-testable)."""

    rows = [{
        "coords": _coords_of(r.get("hierarchy")),   # readable coordinates (for citation / re-joining the enforcement face)
        "hierarchy": r.get("hierarchy") or {},      # seven-level code form, verbatim
        "headings": r.get("headings") or {},        # proper-noun form (EPA/Toxic Substances…)
        "type": r.get("type"),                      # Section|Appendix|Part…
        "starts_on": r.get("starts_on"),            # that version's effective window (change-stream semantics)
        "ends_on": r.get("ends_on"),
        "change_types": r.get("change_types") or [],  # effective/initial…
        "removed": r.get("removed") is True,
        "reserved": r.get("reserved") is True,
        "structure_index": r.get("structure_index"),  # structure index (anchor for versioner lookups)
        "score": r.get("score") if isinstance(r.get("score"), (int, float)) else None,
        "excerpt": r.get("full_text_excerpt") or None,  # HTML-highlighted excerpt (hit terms wrapped in <strong>)
    } for r in ((data or {}).get("results") or [])]
    meta = (data or {}).get("meta") or {}
    return {
        "rows": rows, "count": len(rows),
        "limit_applied": size,
        "total": meta.get("total_count") if isinstance(meta.get("total_count"), int) else None,
        "total_pages": meta.get("total_pages") if isinstance(meta.get("total_pages"), int) else None,
        "current_page": meta.get("current_page") if isinstance(meta.get("current_page"), int) else None,
        "description": meta.get("description"),     # upstream self-description ("Changes to sections matching …")
    }


def search_results(q=None, *, page=1, limit=20, date=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, total, total_pages, current_page, description, _meta}.

    Section-level current-state search (q required; params mirror the upstream names query/per_page/page/date —
    all four verified bound). date (adopted in the 0.2.9 audit, YYYY-MM-DD): point-in-time retrieval — returns the
    clause versions in force on that date (rows carry starts_on/ends_on validity windows); probed query=asbestos:
    no date = 1,436 hits vs date=2024-01-01 = 339 (a subset inside the point-in-time window, probed 2026-10-28)."""
    from ..transport import call_provider
    from ..errors import SdkError

    term = str(q or "").strip()
    if not term:
        raise SdkError("usage_error", provider="ecfr",
                       detail="ecfr_search requires q (topic term; returns section-level current-state hits)")
    d = str(date or "").strip() or None
    if d is not None and not _DATE_RE.fullmatch(d):
        raise SdkError("usage_error", provider="ecfr", detail=f"date must be YYYY-MM-DD (point-in-time retrieval): {date}")
    size = min(max(1, int(limit or 20)), 100)  # local payload wall; no documented upstream per_page ceiling — polite cap 100
    params = {"query": term, "per_page": size, "page": max(1, int(page or 1))}
    if d:
        params["date"] = d
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    out = rows_from_upstream(r.get("data"), size)
    out["_meta"] = r
    return out


def titles_catalog(cache=None, no_cache=False):
    """→ {count, active, as_of, titles[], _meta} — the 50-title catalog (as_of = library-wide currency watermark)."""
    from ..transport import call_provider

    r = call_provider(provider, "titles", {}, cache=cache, no_cache=no_cache)
    titles = [{
        "number": t.get("number"),
        "name": t.get("name"),
        "latest_amended_on": t.get("latest_amended_on"),
        "latest_issue_date": t.get("latest_issue_date"),
        "up_to_date_as_of": t.get("up_to_date_as_of"),  # None on reserved titles
        "reserved": t.get("reserved") is True,
    } for t in (((r.get("data") or {}).get("titles")) or [])]
    dated = sorted(t["up_to_date_as_of"] for t in titles if t["up_to_date_as_of"])
    return {
        "count": len(titles),
        "active": sum(1 for t in titles if not t["reserved"]),
        "as_of": dated[-1] if dated else None,     # library-wide daily-update watermark (observed at T-2 level)
        "titles": titles,
        "_meta": r,
    }


provider = {
    "id": "ecfr",
    "baseUrl": "https://www.ecfr.gov",
    "rate": {"rps": 0.5, "burst": 1},
    "ops": {
        "search": {"path": "/api/search/v1/results"},      # params: query, per_page, page, date (all four verified bound)
        "titles": {"path": "/api/versioner/v1/titles.json"},
    },
    "ttl": {"search": 24 * 3600, "titles": 24 * 3600},
}
