"""fda_recalls — FDA recall provider, three faces (openFDA drug/enforcement · device/recall · food/enforcement; keyless).

Wave 10 of the healthcare domain (2026-10-28 decision to fill out the query faces with the openFDA family; third of the four opening faces).
The family contract is shared with shortages: GET /<ep>.json?search=&limit=&skip=&sort=, zero hits = HTTP 404
{"error":{"code":"NOT_FOUND"}} is a legal answer (notFound:[404] → an empty envelope that is not cached).
Row shapes measured 2026-10-28:
  drug/enforcement (18,010 rows, weekly): recalling_firm.exact:"SV Labs Toronto Corporation" → 2 hits;
    status was seen as Ongoing; **the drug line has no separate recall endpoint — enforcement is the recall face** (a press-release source).
  device/recall (59,618 rows, the RES recall system): recalling_firm:"Sedecal" as a phrase → 62 hits; recall_status
    was seen as Terminated/Ongoing; rows carry firm_fei_number + k_numbers — **this is a different system from device/enforcement (the
    press-release face already bulk-loaded)**: RES is the newer authority (and carries the full Ongoing lifecycle). .exact is unverified, so the wrapped form is always a phrase.
  food/enforcement (29,485 rows): recalling_firm.exact:"TODD'S SEEDS LLC" → 6 hits; status was seen as Ongoing.
Rate limit: a keyless quota shared with shortages on the same host (polite 2 rps per face, the family total must stay under ~4 rps).
TTL 24h (all three faces are on a weekly cadence).
"""
from datetime import datetime, timezone

from ..errors import SdkError

provider = {
    "id": "fda_recalls",
    "baseUrl": "https://api.fda.gov",
    "rate": {"rps": 2, "burst": 5},
    "ops": {
        "drug": {"path": "/drug/enforcement.json", "notFound": [404]},
        "device": {"path": "/device/recall.json", "notFound": [404]},
        "food": {"path": "/food/enforcement.json", "notFound": [404]},
    },
    "ttl": {"drug": 24 * 3600, "device": 24 * 3600, "food": 24 * 3600},
}

# Default sort per face (our default, not the upstream one; both enforcement faces use the same key report_date, the RES face uses the posted date)
_DEFAULT_SORT = {"drug": "report_date:desc", "food": "report_date:desc",
                 "device": "event_date_posted:desc"}


def _enf_rows(results):
    """drug/food enforcement rows → recall record rows (pure function, testable offline). Key order verified against the 2026-10-28 probe."""
    out = []
    for r in results if isinstance(results, list) else []:
        of = r.get("openfda") or {}
        out.append({
            "recall_number": r.get("recall_number"),
            "event_id": r.get("event_id"),                      # stable key (links to the bulk events corpus line)
            "recalling_firm": r.get("recalling_firm"),          # company edge, primary column
            "classification": r.get("classification"),          # Class I/II/III
            "status": r.get("status"),                          # Ongoing/Terminated/Completed
            "product_type": r.get("product_type"),
            "product_description": r.get("product_description"),
            "product_quantity": r.get("product_quantity"),
            "reason_for_recall": r.get("reason_for_recall"),
            "code_info": r.get("code_info"),
            "more_code_info": r.get("more_code_info"),
            "distribution_pattern": r.get("distribution_pattern"),
            "voluntary_mandated": r.get("voluntary_mandated"),
            "initial_firm_notification": r.get("initial_firm_notification"),
            "recalled_on": r.get("recall_initiation_date"),     # YYYYMMDD
            "reported_on": r.get("report_date"),
            "city": r.get("city"), "state": r.get("state"), "country": r.get("country"),
            "address": r.get("address_1"),
            "applications": of.get("application_number"),       # links to the drugsfda product line
            "product_ndcs": of.get("product_ndc"),
        })
    return out


def _device_rows(results):
    """device/recall (RES system) rows → recall record rows (pure function; FEI is the company-facility-product hub key).

    additional_info_contact (the recalling firm's contact, often a person name) is not returned — the same PII red line as the PhilGEPS Contact Person.
    """
    out = []
    for r in results if isinstance(results, list) else []:
        out.append({
            "res_event_number": r.get("res_event_number"),
            "product_res_number": r.get("product_res_number"),
            "cfres_id": r.get("cfres_id"),
            "recalling_firm": r.get("recalling_firm"),          # company edge, primary column
            "firm_fei_number": r.get("firm_fei_number"),        # FEI hub key (links to registrationlisting)
            "k_numbers": r.get("k_numbers"),                    # links to the 510(k) device line
            "product_code": r.get("product_code"),
            "recall_status": r.get("recall_status"),            # Ongoing/Terminated/…
            "action": r.get("action"),
            "product_description": r.get("product_description"),
            "reason_for_recall": r.get("reason_for_recall"),
            "root_cause_description": r.get("root_cause_description"),
            "code_info": r.get("code_info"),
            "product_quantity": r.get("product_quantity"),
            "distribution_pattern": r.get("distribution_pattern"),
            "initiated_on": r.get("event_date_initiated"),      # ISO date
            "posted_on": r.get("event_date_posted"),
            "terminated_on": r.get("event_date_terminated"),
            "address": r.get("address_1"),
            "city": r.get("city"), "state": r.get("state"),
        })
    return out


def search(face, search, *, limit=20, skip=0, sort=None, cache=None, no_cache=False):
    """Born flat: the search expression is passed through verbatim (upstream param names search/limit/skip/sort, zero sugar).
    face ∈ drug|device|food. limit 1-1000 (the openFDA search hard limit, same as shortages measured 1001→400).
    search is required (local safety gate: under a keyless quota a bare full-table query is served by the bulk harvest line).
    → {rows[], total, count, skip, limit_applied, has_more, search, sort, _meta}; zero hits = an empty set that is not cached.
    """
    from ..transport import call_provider

    if face not in provider["ops"]:
        raise SdkError("usage_error", provider=provider["id"], detail=f"face must be drug|device|food, got '{face}'")
    q = str(search or "").strip()
    if not q:
        raise SdkError("usage_error", provider=provider["id"],
                       detail="search requires an expression (e.g. recalling_firm.exact:\"Firm Name\"; a bare full-table query is served by the bulk line)")
    size = int(limit) if limit is not None else 20  # 0 is an explicitly bad value (do not let `or` swallow it into the default); the gate below rejects it
    if not 1 <= size <= 1000:
        raise SdkError("usage_error", provider=provider["id"],
                       detail=f"limit must be 1-1000 (the openFDA search hard limit, same as shortages measured on 2026-10-23), got {size}")
    sk = max(0, int(skip or 0))
    so = str(sort).strip() if sort is not None else _DEFAULT_SORT[face]
    params = {"search": q, "limit": size}
    if sk:
        params["skip"] = sk
    if so:
        params["sort"] = so
    try:
        r = call_provider(provider, face, params, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_not_found":
            return {"rows": [], "total": 0, "count": 0, "skip": sk, "limit_applied": size,
                    "has_more": False, "search": q, "sort": so or None,
                    "_meta": {"from_cache": False,
                              "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}}
        raise
    data = r.get("data") or {}
    rows = (_device_rows if face == "device" else _enf_rows)(data.get("results"))
    total = (data.get("meta") or {}).get("results", {}).get("total", len(rows))
    return {"rows": rows, "total": total, "count": len(rows), "skip": sk, "limit_applied": size,
            "has_more": total > sk + len(rows), "search": q, "sort": so or None, "_meta": r}
