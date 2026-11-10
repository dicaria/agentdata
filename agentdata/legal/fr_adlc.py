"""fr_adlc — French Autorité de la concurrence company-level fine register (data.gouv.fr official mirror; keyless).

legal antitrust-enforcement face (0.3.51; admitted from research 册 164 fr-adlc-datagouv-bulk,
probed live 2026-11-09, tmp/probe-sdk0350/l5/ p01+p02). The authority's own domain
(autoritedelaconcurrence.fr — NOT autorite-concurrence.fr, the look-alike decoy that dies on
every stack) egress-blocks this exit, but the authority publishes everything through its
official data.gouv.fr organization — DS2 "Entreprises sanctionnées financièrement depuis 2009"
is the company-level sanctions ledger (1,208 rows × 5 columns, the 2026-11-08 build, verified
live: id_decision / Entreprise / Montant individuel / Montant total / Annee).

Two-op chain mirrors ca_ccaa_records: the resource URL carries a build timestamp
(…/20261108-110109/sanctions-depuis-2009.csv) so it ROLLS on every update — the face resolves
the LATEST csv resource through the datasets API at call time and never hardcodes the stamped
path (dataset op TTL 1h; the CSV itself TTL 24h — a monthly build is frozen between updates).
Amounts arrive as decimal strings ("10000000.0" individuel, "12670000" total — mixed shapes)
and cast to float locally (the ee_erjk precedent); empty cells → None. Montant individuel is
the per-company share while Montant total repeats a case-level figure on every row of that
case — and the two DO NOT reconcile (26-D-05 live: individuel rows sum to 15,260,000 while
the register's own total says 12,670,000; 15-D-19 ships €672,332,000 case-level). Both figures
are upstream-published: ship verbatim, never recompute one from the other. Politeness 0.5/2
(no published quota).
"""
import csv
import io

provider = {
    "id": "fr_adlc",
    "baseUrl": "https://www.data.gouv.fr",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "dataset": {"path": "/api/1/datasets/{dataset_slug}"},
        # transport extension 10 carries the absolute resource URL raw (no quoting, no base
        # prefix) — the datasets API hands back full static.data.gouv.fr URLs that roll per build
        "csv": {"path": "{resource_url}", "accept": "text", "timeout": 120.0},
    },
    "ttl": {"dataset": 3600, "csv": 24 * 3600},
}

DATASET_SLUG = ("entreprises-sanctionnees-financierement-par-l"
                "autorite-de-la-concurrence-depuis-2009")


def _num(val):
    s = str(val or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def sanctions_raw(entreprise=None, id_decision=None, year=None, *, limit=20,
                  cache=None, no_cache=False):
    """→ {total, count, limit_applied, rows[], params, dataset, _meta}.

    Filters are local (the whole 1,208-row ledger rides one GET) and combinable: entreprise =
    case-insensitive substring against the Entreprise column; id_decision = exact case-insensitive
    ("26-D-05"); year = the Annee column (int). No filter = the whole ledger, newest case year
    last in file order (the register's own order — 2009→2026 by build, not sorted by us).
    """
    from ..errors import SdkError
    from ..transport import call_provider

    n = None
    if limit is not None:
        try:
            n = int(limit)
        except (TypeError, ValueError):
            raise SdkError("usage_error", provider="fr_adlc",
                           detail=f"limit must be an integer 1-200, got {limit!r}")
    n = 20 if n is None else n  # explicit None check — 0 swallowed by or is the 0.2.10-style pit
    if not 1 <= n <= 200:
        raise SdkError("usage_error", provider="fr_adlc",
                       detail=f"limit must be 1-200 (the whole ledger is 1,208 rows — take it home "
                              f"via repeated pages instead of a giant page), got {limit!r}")
    ent = str(entreprise).strip() if entreprise else None
    dec = str(id_decision).strip() if id_decision else None
    yr = None
    if year is not None and str(year).strip():
        try:
            yr = int(str(year).strip())
        except ValueError:
            raise SdkError("usage_error", provider="fr_adlc",
                           detail=f"year must be an integer (the Annee column), got {year!r}")
        if yr < 2009:
            raise SdkError("usage_error", provider="fr_adlc",
                           detail=f"the register covers 2009→ (its own title 'depuis 2009'), got {yr}")

    ds = call_provider(provider, "dataset", {"dataset_slug": DATASET_SLUG},
                       cache=cache, no_cache=no_cache)
    d = ds["data"] or {}
    resources = d.get("resources") or []
    csvs = [r for r in resources if (r.get("format") or "").lower() == "csv"]
    if not csvs:
        raise SdkError("upstream_unavailable", provider="fr_adlc",
                       detail="the datasets API lists no csv resource for the sanctions dataset "
                              f"(resources seen: {[r.get('format') for r in resources]})")
    res = csvs[0]
    resource_url = res.get("url")
    if not resource_url:
        raise SdkError("upstream_unavailable", provider="fr_adlc",
                       detail="the csv resource carries no url (datasets API shape drift)")

    r = call_provider(provider, "csv", {"resource_url": resource_url},
                      cache=cache, no_cache=no_cache)
    body = r["data"] or ""
    if not isinstance(body, str) or not body.strip():
        raise SdkError("upstream_unavailable", provider="fr_adlc",
                       detail="the sanctions csv answered empty (monthly build in flight?)")

    rows_all = []
    for row in csv.DictReader(io.StringIO(body.lstrip("﻿"))):  # lstrip the U+FEFF BOM the export carries
        rows_all.append({
            "id_decision": (row.get("id_decision") or "").strip() or None,
            "entreprise": (row.get("Entreprise") or "").strip() or None,
            "montant_individuel": _num(row.get("Montant individuel")),
            "montant_total": _num(row.get("Montant total")),
            "annee": _num(row.get("Annee")),
        })
    selected = rows_all
    if ent:
        needle = ent.casefold()
        selected = [x for x in selected if needle in str(x["entreprise"] or "").casefold()]
    if dec:
        needle = dec.casefold()
        selected = [x for x in selected if str(x["id_decision"] or "").casefold() == needle]
    if yr is not None:
        selected = [x for x in selected if x["annee"] == float(yr)]

    return {"total": len(selected), "count": min(len(selected), n),
            "limit_applied": n, "rows": selected[:n],
            "params": {"entreprise": ent, "id_decision": dec, "year": yr, "limit": n},
            "dataset": {"title": d.get("title"), "slug": d.get("slug"),
                        "last_update": d.get("last_update"),
                        "resource_url": resource_url,
                        "resource_updated": res.get("last_modified"),
                        "rows_in_build": len(rows_all)},
            "_meta": r}
