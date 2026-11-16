"""ca_asc — Alberta Securities Commission notices / decisions / orders enforcement library
(www.asc.ca Coveo headless chain, keyless).

CA legal face (0.3.58; admitted from research booklet ca-provinces-round2 册 139, probed live
2026-11-13, tmp/probe-sdk-0358/p4_asc.py). The ASC enforcement library (7,304 documents live —
notices, decisions, orders, rulings 2001→today) rides a THREE-STEP KEYLESS chain, all plain
urllib (the de_register token-chain pattern):

  1. GET www.asc.ca/coveo/rest/token → {"token": "<JWT>"} (fresh, no auth; the Referer header
     is part of the measured contract). The JWT's claims carry organization=albertasecurities
     commissionprod2a34tiy7 and a 24h exp — the face caches it 12h, safely inside the window.
  2. decode the JWT payload locally (base64url middle segment) → the org id for step 3.
  3. POST https://platform.cloud.coveo.com/rest/search/v2?organizationId=<org> with Bearer +
     JSON body {q, numberOfResults, pipeline:'noticesdecisionsordersenforcement',
     searchHub:'asc'} — the CLOUD endpoint directly (the on-site /coveo/rest/v2/query proxy is
     404; the site's own JS queries platform.cloud.coveo.com and so does the face). The op path
     is the absolute cloud URL with the org baked into its query segment (the ukec law), so the
     provider baseUrl stays www.asc.ca and only the token op shares its host bucket.

MEASURED QUIRKS:
- 3× DUPLICATES: the index answers every document three times per page (three result objects,
  same clickUri, e.g. 10 results = 3 documents + 1 pair). The face dedups by clickUri (first
  occurrence wins) and reports both the raw and deduped counts — totalCount upstream counts the
  duplicated index (7,304 / 3 ≈ 2,435 unique documents).
- LEGACY JUNK TITLES: pre-web rows carry raw file paths as titles ('Q:\\SCC_ADM\\AAWebsite\\
  Enforcement Orders Database 2001\\#826514 v1 - …'). Kept verbatim (title IS the historical
  record), counted per page as junk_titles; z95xfileref / z95xfullpath carry the cleaner path.
- BOUNDARY (metadata-only): clickUri targets cm.asc.ca PDFs, which answer 403 to non-browser
  clients from this egress — the face serves the document metadata + link, never the PDF
  binary (the harvest layer owns binary retrieval).

Row payload: title / url (clickUri) / issuer (z95xefissuer) / category (z95xdecisionsorders-
category) / content_type (z95xcontenttype — 'PDO Order' family) / date (z95xcreateddate epoch
ms → ISO; the z95xpdoproceedingdate -17955907200000 sentinel is year-1400 noise, not mapped) /
date_type ('Issued'/'Effective') / year / is_archived / investor_alert / file_ref / full_path.
0.25/2 polite, concurrency 1, search TTL 24h.
"""
import base64
import json
import time

from ..errors import SdkError

provider = {
    "id": "ca_asc",
    "baseUrl": "https://www.asc.ca",
    "rate": {"rps": 0.25, "burst": 2},
    "concurrency": 1,
    "ops": {
        # {"token": "<JWT>"} — cached 12h (upstream exp = 24h from iat, measured)
        "token": {"path": "/coveo/rest/token", "timeout": 30.0},
        # absolute-URL op: the cloud endpoint with the org in the query segment (the token op's
        # host bucket does not apply here — Coveo's own platform quota is far above our tier)
        "search": {"path": "https://platform.cloud.coveo.com/rest/search/v2?organizationId={org}",
                   "method": "POST", "idempotent": True, "timeout": 30.0},
    },
    "ttl": {"token": 12 * 3600, "search": 24 * 3600},
}

_PIPELINE = "noticesdecisionsordersenforcement"
_SEARCH_HUB = "asc"


def _first(v):
    """Coveo multi-value fields arrive as lists — the card keeps the first value."""
    if isinstance(v, (list, tuple)):
        return v[0] if v else None
    return v


def _epoch_ms_to_date(v):
    """z95xcreateddate epoch ms → 'YYYY-MM-DD' (None on anything else — the year-1400 sentinel
    stays unmapped)."""
    if isinstance(v, (int, float)) and v > 0:
        return time.strftime("%Y-%m-%d", time.gmtime(v / 1000.0))
    return None


def row_from_upstream(res):
    """Coveo result object → curated card (pure function — split out for offline testing)."""
    raw = res.get("raw") or {}
    title = res.get("title")
    return {
        "title": title,
        "is_legacy_path_title": isinstance(title, str) and "\\" in title,
        "url": res.get("clickUri") or res.get("uri"),
        "issuer": raw.get("z95xefissuer"),
        "category": _first(raw.get("z95xdecisionsorderscategory")),
        "content_type": _first(raw.get("z95xcontenttype")),
        "information_type": _first(raw.get("z95xinformationtype")),
        "date": _epoch_ms_to_date(raw.get("z95xcreateddate")),
        "date_type": _first(raw.get("z95xdatetype")),
        "year": raw.get("z95xcreateddateyear"),
        "is_archived": raw.get("z95xisarchived"),
        "investor_alert": raw.get("z95xinvestoralert"),
        "file_ref": raw.get("z95xfileref"),
        "full_path": raw.get("z95xfullpath"),
    }


def _token_and_org(cache, no_cache):
    """→ (token, org) — the cached 12h JWT plus its organization claim (decoded locally)."""
    from ..transport import call_provider
    r = call_provider(provider, "token", {}, cache=cache, no_cache=no_cache)
    d = r["data"]
    tk = (d or {}).get("token") if isinstance(d, dict) else None
    if not tk:
        raise SdkError("upstream_unavailable", provider="ca_asc",
                       detail="the Coveo token endpoint returned no token (the site's headless chain may have changed)")
    try:
        payload = tk.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        raise SdkError("upstream_unavailable", provider="ca_asc",
                       detail="the token is not a decodable JWT — the headless chain contract may have changed")
    org = claims.get("organization")
    if not org:
        raise SdkError("upstream_unavailable", provider="ca_asc",
                       detail="the token carries no organization claim (the cloud query needs it in the URL)")
    return tk, org


def search_raw(q=None, *, limit=20, cache=None, no_cache=False):
    """→ {total, count, duplicates_dropped, junk_titles, rows[], params, _meta}. q = full-text
    term (empty/None = browse the whole enforcement library, newest first); limit 1-100 local
    (Coveo would serve 1000 — the politeness tier caps at 100). Rows are DEDUPED by clickUri
    (the index answers every document 3×; duplicates_dropped counts the dropped copies)."""
    from ..transport import call_provider

    term = str(q or "").strip()
    try:
        size = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ca_asc", detail=f"limit must be an integer 1-100, got {limit!r}")
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="ca_asc", detail=f"limit must be 1-100 (local politeness tier; Coveo's own wall is 1000), got {limit!r}")
    tk, org = _token_and_org(cache, no_cache)
    body = {"q": term, "numberOfResults": size, "pipeline": _PIPELINE, "searchHub": _SEARCH_HUB}
    # cacheable, unlike the de_register shape: the token rides the HEADER (not the cache key)
    # and the org in the key is a stable constant, so keys do not fork across token refreshes
    r = call_provider(provider, "search", dict(body, org=org), cache=cache, no_cache=no_cache,
                      extra_headers={"Authorization": f"Bearer {tk}",
                                     "Origin": "https://www.asc.ca",
                                     "Referer": "https://www.asc.ca/en/enforcement/notices-decisions-and-orders"})
    doc = r["data"] or {}
    if not isinstance(doc, dict) or "results" not in doc:
        raise SdkError("upstream_unavailable", provider="ca_asc",
                       detail="the Coveo search endpoint answered an unexpected shape (no results key — token expired mid-flight or the pipeline moved)")
    rows, seen = [], {}
    for res in doc.get("results") or []:
        uri = res.get("clickUri") or res.get("uri")
        if uri in seen:
            seen[uri] += 1
            continue
        seen[uri] = 1
        rows.append(row_from_upstream(res))
    dropped = sum(n - 1 for n in seen.values())
    junk = sum(1 for x in rows if x["is_legacy_path_title"])
    return {"total": doc.get("totalCount"), "count": len(rows),
            "duplicates_dropped": dropped, "junk_titles": junk,
            "rows": rows, "params": {"q": term or None, "limit": size},
            "_meta": r}
