"""ch_efk — EFK (Eidgenössische Finanzkontrolle, Swiss Federal Finance Administration)
political party financing disclosure, frontend API
(politikfinanzierung.efk.admin.ch/api/frontend/v1, keyless).

CH legal face (0.3.59; admitted from research booklet ch-party-financing, probed live
2026-11-13, tmp/probe-sdk-0359/r2_efk_party.json — 12.5KB body, 3 year-roots × 10 parties ×
disclosure forms). The Swiss transparency register for federal political party financing:
per year, per party, the disclosure forms (annual income disclosure; individual grants above
CHF 15,000) with their campaign download paths.

CONTRACT (GET, path-segment language — mandatory):
/api/frontend/v1/{lang}/party_financings with lang ∈ {de, fr, it} (no language segment = 404;
'de' measured). Response {data: {tree_roots: [...]}, meta: {powered_by 'Sitrox',
data_checksum_sha256}} — a three-level tree: root {id, label '2025', type 'party_financing'}
→ children actors {id, label 'Die Mitte, Bern', type 'actor'} → children forms {id, label
'Offenlegung der jährlichen Einnahmen', type 'form', campaign_id, download_path
'/api/frontend/latest/{lang}/downloads/campaigns/{cid}/forms/{fid}'}.
The face flattens the tree into form rows (year × party × form × download URL absolutized
against the API host) and offers client-side year / actor-substring filters (the tree is
small — tens of rows; no server-side filter exists). 0.25/2 polite, TTL 7d (annual
cadence).
"""
from ..errors import SdkError

provider = {
    "id": "ch_efk",
    "baseUrl": "https://politikfinanzierung.efk.admin.ch",
    "rate": {"rps": 0.25, "burst": 2},
    "concurrency": 1,
    "ops": {
        "tree": {"path": "/api/frontend/v1/{lang}/party_financings", "method": "GET",
                 "idempotent": True, "timeout": 30.0},
    },
    "ttl": {"tree": 7 * 24 * 3600},
}

_LANGS = ("de", "fr", "it")


def form_from_upstream(year_root, actor, form):
    """Flatten one tree leaf (pure function — split out for offline testing)."""
    dp = form.get("download_path")
    return {
        "year": year_root.get("label"),
        "year_id": year_root.get("id"),
        "actor_id": actor.get("id"),
        "actor": actor.get("label"),
        "form_id": form.get("id"),
        "form": form.get("label"),
        "campaign_id": form.get("campaign_id"),
        "download_path": dp,
        "download_url": provider["baseUrl"] + dp if dp else None,
    }


def tree_raw(lang="de", *, year=None, actor=None, cache=None, no_cache=False):
    """→ {total, rows[], params, meta, _meta}. lang ∈ {de, fr, it} (walled — the API 404s
    without a language segment). year = label filter ('2025'), exact match client-side;
    actor = substring filter on the party label, client-side. rows are flattened form cards
    (one per disclosure form per party per year); the raw tree is NOT echoed (small,
    reconstructible from the rows)."""
    language = str(lang or "de").strip().lower() or "de"
    if language not in _LANGS:
        raise SdkError("usage_error", provider="ch_efk",
                       detail=f"lang must be one of {', '.join(_LANGS)} (no segment = upstream 404), got {lang!r}")
    yr = str(year).strip() if year is not None else None
    ac = str(actor or "").strip() or None
    from ..transport import call_provider
    r = call_provider(provider, "tree", {"lang": language}, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    roots = ((doc.get("data") or {}).get("tree_roots")) if isinstance(doc, dict) else None
    if not isinstance(roots, list):
        raise SdkError("upstream_unavailable", provider="ch_efk",
                       detail="party_financings answered an unexpected shape (no data.tree_roots)")
    rows = []
    for root in roots:
        for a in root.get("children") or []:
            for f in a.get("children") or []:
                rows.append(form_from_upstream(root, a, f))
    if yr:
        rows = [x for x in rows if x["year"] == yr]
    if ac:
        needle = ac.casefold()
        rows = [x for x in rows if needle in (x["actor"] or "").casefold()]
    return {"total": len(rows),
            "rows": rows,
            "params": {"lang": language, "year": yr, "actor": ac},
            "meta": doc.get("meta") if isinstance(doc, dict) else None,
            "_meta": r}
