"""fi_ytj — Finnish PRH YTJ business information system v3 (avoindata open API front door; keyless).

2026-10-29 probed shape: GET /companies?name=|businessId= (one endpoint, two lookup shapes);
name is a contains-match that also hits historical names and secondary names (nokia hits the branch name Fysios Nokia);
**pagination params are ignored upstream — resultsFrom/maxResults silently have no effect (p63/p200 measured
byte-identical), page size is always ~63 rows, and totalResults is the real total** — so large name families cannot be
fetched in full; narrow with a more precise name or a businessId direct lookup.
Row shape: businessId is a nested object {value, registrationDate, source}; names[] = versioned name history
(type 1 main name / 3 branch name); mainBusinessLine/companyForms/companySituations carry fi/sv/en
descriptions (languageCode 1=fi 2=sv 3=en).
TTL: 7 days (registry current values); politeness tier 0.5 rps (no published quota).
"""
from ..errors import SdkError

provider = {
    "id": "fi_ytj",
    "baseUrl": "https://avoindata.prh.fi/opendata-ytj-api/v3",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "companies": {"path": "/companies"},   # params: name | businessId (query; pagination params are not upstream, not exposed)
    },
    "ttl": {"companies": 7 * 86400},
}


def _desc(trilingual):
    """[{languageCode, description}] → joined en/fi string (languageCode 3=en 1=fi; sv dropped — projection to reduce noise)."""
    by = {d.get("languageCode"): d.get("description") for d in trilingual or []}
    parts = [by.get(c) for c in ("3", "1")]
    return " / ".join(x for x in parts if x) or None


def search_companies(name=None, business_id=None, *, cache=None, no_cache=False):
    """→ {total_results, companies[], params, _meta}; name search XOR businessId direct lookup (one endpoint, two lookup shapes).
    name also matches historical/branch names by contains; **page size is always ~63 rows (pagination params are silently
    ignored upstream, pinned by measurement), total_results is the real total — large families must be narrowed with a more
    precise name or a businessId**."""
    from ..transport import call_provider

    nm = str(name or "").strip() or None
    bid = str(business_id or "").replace(" ", "").strip() or None
    if bool(nm) == bool(bid):
        raise SdkError("usage_error", provider="fi_ytj",
                       detail="name (search face) and business_id (direct lookup face) are mutually exclusive — provide exactly one of the two required")
    params = {"name": nm, "businessId": bid}
    r = call_provider(provider, "companies", params, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    return {"total_results": d.get("totalResults"),
            "companies": [_norm(c) for c in d.get("companies") or []],
            "params": {k: v for k, v in params.items() if v}, "_meta": r}


def _norm(c):
    """Row projection: businessId split out of its nested object; full name history kept; trilingual fields joined en/fi; address takes the first row."""
    bid = c.get("businessId") or {}
    addr0 = (c.get("addresses") or [{}])[0] or {}
    city = None
    for po in addr0.get("postOffices") or []:
        if po.get("languageCode") in ("1", "3"):  # fi or en city name
            city = po.get("city")
            if po.get("languageCode") == "3":
                break
    return {
        "business_id": bid.get("value"),                # 0194099-3 shape (value split from the nested object)
        "business_id_registration_date": bid.get("registrationDate"),
        "latest_name": ((c.get("names") or [{}])[0]).get("name"),   # names[0] = most recent row (upstream order)
        "names": [{"name": n.get("name"), "type": n.get("type"),          # full history (1 main name / 3 branch name)
                   "registration_date": n.get("registrationDate"), "end_date": n.get("endDate"),
                   "version": n.get("version")} for n in c.get("names") or []],
        "main_business_line": {"code": (c.get("mainBusinessLine") or {}).get("type"),
                               "description": _desc((c.get("mainBusinessLine") or {}).get("descriptions")),
                               "codeset": (c.get("mainBusinessLine") or {}).get("typeCodeSet")},  # TOIMI4
        "company_forms": [{"type": f.get("type"), "description": _desc(f.get("descriptions")),
                           "start_date": f.get("startDate"), "end_date": f.get("endDate")}
                          for f in c.get("companyForms") or []],
        "company_situations": [{"description": _desc(s.get("descriptions")),
                                "start_date": s.get("startDate"), "end_date": s.get("endDate")}
                               for s in c.get("companySituations") or []],
        "status": c.get("status"),                       # upstream numeric code (2 = registered/live is the common value)
        "trade_register_status": c.get("tradeRegisterStatus"),
        "registration_date": c.get("registrationDate"),
        "end_date": c.get("endDate"),
        "last_modified": c.get("lastModified"),
        "address": {"street": addr0.get("street"), "building_number": addr0.get("buildingNumber"),
                    "post_code": addr0.get("postCode"), "city": city},
        "registered_entries": [{"type": e.get("type"), "description": _desc(e.get("descriptions")),
                                "registration_date": e.get("registrationDate"), "end_date": e.get("endDate")}
                               for e in c.get("registeredEntries") or []],   # commercial register entry history
    }
