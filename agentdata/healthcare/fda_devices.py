"""fda_devices — FDA device provider, four faces (openFDA device/510k · pma · registrationlisting · classification; keyless).

Wave 10b of the healthcare domain (second batch; row shapes measured 2026-10-29).
The family contract is shared with fda_recalls/shortages/fda_drugs: GET /<ep>.json?search=&limit=&skip=&sort=,
zero hits = HTTP 404 {"error":{"code":"NOT_FOUND"}} is a legal answer (notFound:[404] → an empty envelope that is not cached).
Probing anchors on 2026-10-29 (field names verified by _exists_, not inferred from the docs):
  device/510k (176,466 clearances): company field = **applicant** (the same name as pma; the docs once said applicant_name — overturned);
    **contact (a person-name slot, e.g. Marybeth Gamber) is not returned — the same PII red line as additional_info_contact on Wave 10 device recalls**;
    openfda.registration_number can carry 100+ entries on one row (row inflation), so the whole slot is not returned.
  device/pma (12,896 approvals): company field = applicant; ao_statement (long approval text) is not returned (row slimming, same precedent as CRL text);
    street_1/2+zip are not returned (street-level address; city/state are kept).
  device/registrationlisting (336,946 registration rows, quarterly): company fields = **registration.name + registration.owner_operator.firm_name**
    (three keys: registration_number/fei_number/owner_operator_number; the top-level firm_name/fei_number etc. all 404 under _exists_ —
    everything lives in the registration.* namespace; the default sort on the nested key registration.reg_expiry_date_year:desc was measured to work).
    **registration.us_agent (US agent name+phone+email+address) and owner_operator.official_correspondent (personal contact) are not returned — PII red line**.
  device/classification (the product-code taxonomy face): no date field → no default sort; the openfda sub-object is small (k_number/registration_number
    /fei_number cross keys), so it is kept whole.
Rate limit: the openFDA family shares a keyless quota (polite 2 rps per face, the family total must stay under ~4 rps).
TTL: 510k/pma 24h, registrations 7d (quarterly), classification 30d (the taxonomy is near-static).
"""
from datetime import datetime, timezone

from ..errors import SdkError

provider = {
    "id": "fda_devices",
    "baseUrl": "https://api.fda.gov",
    "rate": {"rps": 2, "burst": 5},
    "ops": {
        "clearance_510k": {"path": "/device/510k.json", "notFound": [404]},
        "pma": {"path": "/device/pma.json", "notFound": [404]},
        "registrations": {"path": "/device/registrationlisting.json", "notFound": [404]},
        "classification": {"path": "/device/classification.json", "notFound": [404]},
    },
    "ttl": {"clearance_510k": 24 * 3600, "pma": 24 * 3600,
            "registrations": 7 * 24 * 3600, "classification": 30 * 24 * 3600},
}

# Default sort per face (our default, not the upstream one; classification has no date field → None)
_DEFAULT_SORT = {"clearance_510k": "decision_date:desc",
                 "pma": "decision_date:desc",
                 "registrations": "registration.reg_expiry_date_year:desc"}


def _k510_rows(results):
    """device/510k rows → premarket notification clearance rows (pure function, testable offline). Key order verified against the 2026-10-29 probe of k510.ex2.json.

    contact (the applicant's contact, often a person name) and openfda (a registration_number list with 100+ entries per row) are not returned.
    """
    out = []
    for r in results if isinstance(results, list) else []:
        out.append({
            "k_number": r.get("k_number"),                            # hub key (links to the recall k_numbers)
            "applicant": r.get("applicant"),                          # company edge, primary column (the applicant)
            "device_name": r.get("device_name"),
            "clearance_type": r.get("clearance_type"),
            "decision_code": r.get("decision_code"),                  # SESE/SE/…
            "decision_description": r.get("decision_description"),
            "decision_date": r.get("decision_date"),                  # ISO date
            "date_received": r.get("date_received"),
            "expedited_review_flag": r.get("expedited_review_flag"),
            "third_party_flag": r.get("third_party_flag"),
            "advisory_committee": r.get("advisory_committee"),
            "advisory_committee_description": r.get("advisory_committee_description"),
            "product_code": r.get("product_code"),                    # links to the classification face
            "statement_or_summary": r.get("statement_or_summary"),
            "city": r.get("city"), "state": r.get("state"), "country_code": r.get("country_code"),
        })
    return out


def _pma_rows(results):
    """device/pma rows → premarket approval rows (pure function). The ao_statement long text and street/zip are not returned (row slimming + street-level address)."""
    out = []
    for r in results if isinstance(results, list) else []:
        out.append({
            "pma_number": r.get("pma_number"),                        # hub key
            "supplement_number": r.get("supplement_number"),
            "supplement_type": r.get("supplement_type"),
            "supplement_reason": r.get("supplement_reason"),
            "applicant": r.get("applicant"),                          # company edge, primary column
            "trade_name": r.get("trade_name"),
            "generic_name": r.get("generic_name"),
            "decision_code": r.get("decision_code"),                  # APPR/…
            "decision_date": r.get("decision_date"),                  # ISO date
            "date_received": r.get("date_received"),
            "expedited_review_flag": r.get("expedited_review_flag"),
            "advisory_committee": r.get("advisory_committee"),
            "advisory_committee_description": r.get("advisory_committee_description"),
            "product_code": r.get("product_code"),
            "docket_number": r.get("docket_number"),
            "city": r.get("city"), "state": r.get("state"),
        })
    return out


def _reg_rows(results):
    """device/registrationlisting rows → facility registration rows (pure function). Key order verified against the 2026-10-29 probe of reg.f2-registration.name.json.

    registration.us_agent (US agent name/phone/email/address) and owner_operator.official_correspondent (personal contact)
    are not returned — PII red line; address_line_1/2 (street-level) are not returned, city/iso_country_code/postal_code are kept.
    registration.* is flattened to the top level (the namespace survives only inside the search expression).
    """
    out = []
    for r in results if isinstance(results, list) else []:
        reg = r.get("registration") or {}
        own = reg.get("owner_operator") or {}
        out.append({
            "registration_number": reg.get("registration_number"),    # hub key (links to 510k openfda / recalls)
            "fei_number": reg.get("fei_number"),                      # FEI facility key (links to the recall firm_fei_number)
            "firm_name": reg.get("name"),                             # company edge, primary column (the registered facility name)
            "owner_operator_number": own.get("owner_operator_number"),
            "owner_operator_name": own.get("firm_name"),              # parent / responsible-operator name
            "status_code": reg.get("status_code"),
            "initial_importer_flag": reg.get("initial_importer_flag"),
            "reg_expiry_date_year": reg.get("reg_expiry_date_year"),
            "city": reg.get("city"), "state_code": reg.get("state_code"),
            "iso_country_code": reg.get("iso_country_code"), "postal_code": reg.get("postal_code"),
            "establishment_types": r.get("establishment_type"),
            "proprietary_names": r.get("proprietary_name"),
            "k_number": r.get("k_number"), "pma_number": r.get("pma_number"),
            "products": [{"product_code": p.get("product_code"),
                          "created_date": p.get("created_date"),
                          "openfda": p.get("openfda")}                 # device_name/regulation_number/device_class
                         for p in (r.get("products") or []) if isinstance(p, dict)],
        })
    return out


def _cls_rows(results):
    """device/classification rows → product-code taxonomy rows (pure function). The openfda cross keys are small, so they are kept whole."""
    out = []
    for r in results if isinstance(results, list) else []:
        out.append({
            "product_code": r.get("product_code"),                    # hub key (links to 510k/pma/recalls)
            "device_name": r.get("device_name"),
            "device_class": r.get("device_class"),                    # 1/2/3
            "definition": r.get("definition"),
            "regulation_number": r.get("regulation_number"),
            "medical_specialty": r.get("medical_specialty"),
            "medical_specialty_description": r.get("medical_specialty_description"),
            "review_panel": r.get("review_panel"),
            "review_code": r.get("review_code"),
            "submission_type_id": r.get("submission_type_id"),
            "implant_flag": r.get("implant_flag"),
            "gmp_exempt_flag": r.get("gmp_exempt_flag"),
            "third_party_flag": r.get("third_party_flag"),
            "life_sustain_support_flag": r.get("life_sustain_support_flag"),
            "summary_malfunction_reporting": r.get("summary_malfunction_reporting"),
            "unclassified_reason": r.get("unclassified_reason"),
            "openfda": r.get("openfda"),                              # k_number/registration_number/fei_number
        })
    return out


_ROWS = {"clearance_510k": _k510_rows, "pma": _pma_rows,
         "registrations": _reg_rows, "classification": _cls_rows}


def search(face, search, *, limit=20, skip=0, sort=None, cache=None, no_cache=False):
    """Born flat: the search expression is passed through verbatim (upstream param names search/limit/skip/sort, zero sugar).
    face ∈ clearance_510k|pma|registrations|classification. limit 1-1000 (the openFDA search hard limit).
    search is required (local safety gate: under a keyless quota a bare full-table query is served by the bulk harvest line).
    → {rows[], total, count, skip, limit_applied, has_more, search, sort, _meta}; zero hits = an empty set that is not cached.
    """
    from ..transport import call_provider

    if face not in provider["ops"]:
        raise SdkError("usage_error", provider=provider["id"],
                       detail=f"face must be clearance_510k|pma|registrations|classification, got '{face}'")
    q = str(search or "").strip()
    if not q:
        raise SdkError("usage_error", provider=provider["id"],
                       detail="search requires an expression (e.g. registration.name:\"Firm Name\" or applicant:\"Medtronic\"; a bare full-table query is served by the bulk line)")
    size = int(limit) if limit is not None else 20  # 0 is an explicitly bad value (do not let `or` swallow it into the default); the gate below rejects it
    if not 1 <= size <= 1000:
        raise SdkError("usage_error", provider=provider["id"],
                       detail=f"limit must be 1-1000 (the openFDA search hard limit, same as shortages measured on 2026-10-23), got {size}")
    sk = max(0, int(skip or 0))
    so = str(sort).strip() if sort is not None else _DEFAULT_SORT.get(face)
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
    rows = _ROWS[face](data.get("results"))
    total = (data.get("meta") or {}).get("results", {}).get("total", len(rows))
    return {"rows": rows, "total": total, "count": len(rows), "skip": sk, "limit_applied": size,
            "has_more": total > sk + len(rows), "search": q, "sort": so or None, "_meta": r}
