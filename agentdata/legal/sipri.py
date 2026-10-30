"""sipri — SIPRI arms-transfer database provider (country-level arms-trade face; keyless anonymous /api/p).

Shape verified 2026-10-20: POST JSON body {filters:[…], logic:"AND", type:"delivered"|"orders", status:"0",
pageNo, pageSize, sorts:{}}; **country filters need a numeric EntityId in listData** (putting a country name in
value1 → 500 NumberFormatException); the EntityId table = GET /countries/getAllCountriesTrimmed (385 countries,
quasi-static); the response is a **bare array** (no wrapper key); sorts must be a map ({}), not an array; pageSize is
capped at 100; a wrong prefix /api/v1 = 401.
Note: trades is a country-level face (buyer/seller = country names), not a company-level one — the company-level
universe lives in the Top-100 XLSX (batch line).
TTL: trades 30 days (the historical database changes slowly) / countries 30 days (quasi-static table); polite rate 0.5 rps.
"""
from ..errors import SdkError

provider = {
    "id": "sipri",
    "baseUrl": "https://atbackend.sipri.org/api/p",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "trades": {"path": "/trades/search", "method": "POST", "idempotent": True},  # params: the whole body (filters/logic/type/status/pageNo/pageSize/sorts)
        "countries": {"path": "/countries/getAllCountriesTrimmed"},                  # params: none (the full 385-country EntityId table)
    },
    "ttl": {"trades": 30 * 86400, "countries": 30 * 86400},
}


def _mk_filter(field, entity_id):
    return {"field": field, "oldField": "", "condition": "contains", "value1": "", "value2": "",
            "logic": "AND", "listData": [entity_id]}


def trades_body(supplier_id=None, recipient_id=None, *, type="delivered", page=1, limit=20):
    """→ the POST body (pure function so the body is offline-testable); a country name in value1 → upstream 500,
    it needs a numeric EntityId in listData."""
    if type not in ("delivered", "orders"):
        raise SdkError("usage_error", provider="sipri", detail=f"type must be delivered|orders, got \"{type}\"")
    filters = []
    if supplier_id:
        filters.append(_mk_filter("Supplier", supplier_id))
    if recipient_id:
        filters.append(_mk_filter("Recipient", recipient_id))
    if not filters:
        raise SdkError("usage_error", provider="sipri",
                       detail="search_trades requires supplier / recipient — at least one of the two")
    return {
        "filters": filters, "logic": "AND", "type": type, "status": "0",
        "pageNo": max(1, int(page or 1)), "pageSize": min(max(1, int(limit or 20)), 100), "sorts": {},
    }


def _resolve_country(name, cache=None, no_cache=False):
    """Country name → EntityId (exact match, case-insensitive; the table is cached for 30 days).
    On a miss it offers near matches."""
    from ..transport import call_provider

    r = call_provider(provider, "countries", {}, cache=cache, no_cache=no_cache)
    lst = r["data"] if isinstance(r["data"], list) else []
    low = str(name).lower()
    hit = next((c for c in lst if str(c.get("Name") or "").lower() == low), None)
    if not hit:
        near = [c.get("Name") for c in lst if low in str(c.get("Name") or "").lower()][:5]
        hint = f" (near: {' / '.join(near)})" if near else " (use the full English name, e.g. United States / Angola)"
        raise SdkError("usage_error", provider="sipri", detail=f"country name is not in the SIPRI table: \"{name}\"{hint}")
    return {"entity_id": hit["EntityId"], "name": hit["Name"], "code": hit.get("CountryCode"), "_meta": r}


def search_trades(supplier=None, recipient=None, *, type=None, page=1, limit=20,
                  cache=None, no_cache=False):
    """→ {rows[], _meta, _metas}; arms-transfer rows (country × model × quantity).
    Each country-name → EntityId resolution costs one cached call (30-day table); the trades call passes through,
    and metas keeps the from_cache flags accurate for the whole chain."""
    from ..transport import call_provider

    if not supplier and not recipient:
        raise SdkError("usage_error", provider="sipri",
                       detail="search_trades requires supplier / recipient — at least one of the two")
    size = min(max(1, int(limit or 20)), 100)  # upstream pageSize caps at 100; truncation must stay visible (limit_applied)
    metas = []
    supplier_id = recipient_id = None
    if supplier:
        s = _resolve_country(supplier, cache, no_cache)
        supplier_id, _ = s["entity_id"], metas.append(s["_meta"])
    if recipient:
        s = _resolve_country(recipient, cache, no_cache)
        recipient_id, _ = s["entity_id"], metas.append(s["_meta"])
    r = call_provider(provider, "trades",
                      trades_body(supplier_id, recipient_id, type=type or "delivered",
                                  page=page, limit=limit),
                      cache=cache, no_cache=no_cache)
    data = r["data"]
    trades = data if isinstance(data, list) else (data or {}).get("trades") or []
    rows = [{
        "trade_id": t.get("tradeId") or t.get("id"),
        "supplier": t.get("seller"),               # exporting country (country name)
        "recipient": t.get("buyer"),               # importing country (country name)
        "order_year": t.get("orderYr"),
        "order_year_est": t.get("orderYrEst"),     # estimated flag (data-quality flag)
        "delivery_year": t.get("deliveryYr"),
        "units": t.get("units"),
        "units_est": t.get("unitsEst"),
        "designation": t.get("desg"),              # model (An-26 etc.)
        "description": t.get("desc"),              # equipment description (transport aircraft)
        "category": t.get("category"),             # major category (Aircraft etc.)
        "sub_category": t.get("subCategory"),
    } for t in trades]
    return {"rows": rows, "limit_applied": size, "_meta": r, "_metas": metas + [r]}


def search_raw(filters=None, *, supplier=None, recipient=None, type="delivered",
               page=1, limit=20, cache=None, no_cache=False):
    """Flat-panel low-level face: filters (the raw POST body, verbatim-name channel: [{field, listData:[EntityId], …}])
    XOR supplier/recipient (sugar: country name → EntityId resolved against the 30-day cached table first).

    → {rows[], limit_applied, resolved_countries, params, _meta, _metas} — params is the exact POST body sent.
    A country name in value1 → upstream 500 NumberFormatException (verified 2026-10-20): the sugar channel
    guarantees that what lands in listData is a numeric EntityId; pageSize wall 1-100 (upstream cap,
    verified 2026-10-20)."""
    from ..transport import call_provider

    if filters is not None and (str(supplier or "").strip() or str(recipient or "").strip()):
        raise SdkError("usage_error", provider="sipri",
                       detail="filters (verbatim-name channel: numeric EntityId in listData) and supplier/recipient "
                              "(sugar: country names resolved to EntityId first) are mutually exclusive — give only one")
    lim = int(limit or 20)
    if not 1 <= lim <= 100:
        raise SdkError("usage_error", provider="sipri",
                       detail=f"limit must be 1-100 (upstream pageSize caps at 100, verified 2026-10-20), got \"{limit}\"")
    if type not in ("delivered", "orders"):
        raise SdkError("usage_error", provider="sipri", detail=f"type must be delivered|orders, got \"{type}\"")
    metas, resolved = [], {}
    if filters is not None:
        if not isinstance(filters, list) or not filters:
            raise SdkError("usage_error", provider="sipri",
                           detail="filters must be a non-empty list ([{field:'Supplier'|'Recipient', listData:[EntityId], …}])")
        for f in filters:
            if not isinstance(f, dict) or f.get("field") not in ("Supplier", "Recipient") \
                    or not (isinstance(f.get("listData"), list) and f["listData"]):
                raise SdkError("usage_error", provider="sipri",
                               detail="filters elements look like {\"field\": \"Supplier\", \"listData\": [<numeric EntityId>]} — "
                                      "a country name in value1 causes a 500 (verified 2026-10-20)")
            for eid in f["listData"]:
                if not str(eid).isdigit():
                    raise SdkError("usage_error", provider="sipri",
                                   detail=f"listData must hold numeric EntityIds (resolve country names first via the supplier/recipient sugar), got \"{eid}\"")
        body = {"filters": filters, "logic": "AND", "type": type, "status": "0",
                "pageNo": max(1, int(page or 1)), "pageSize": lim, "sorts": {}}
    else:
        if not supplier and not recipient:
            raise SdkError("usage_error", provider="sipri",
                           detail="search_raw requires supplier / recipient (country names) or filters (the raw EntityId table) — at least one of the two")
        sid = rid = None
        if supplier:
            s = _resolve_country(supplier, cache, no_cache)
            sid, resolved["supplier"] = s["entity_id"], {"entity_id": s["entity_id"], "name": s["name"]}
            metas.append(s["_meta"])
        if recipient:
            s = _resolve_country(recipient, cache, no_cache)
            rid, resolved["recipient"] = s["entity_id"], {"entity_id": s["entity_id"], "name": s["name"]}
            metas.append(s["_meta"])
        body = trades_body(sid, rid, type=type, page=page, limit=lim)
    r = call_provider(provider, "trades", body, cache=cache, no_cache=no_cache)
    data = r["data"]
    trades = data if isinstance(data, list) else (data or {}).get("trades") or []
    rows = [{
        "trade_id": t.get("tradeId") or t.get("id"),
        "supplier": t.get("seller"),               # exporting country (country name)
        "recipient": t.get("buyer"),               # importing country (country name)
        "order_year": t.get("orderYr"),
        "order_year_est": t.get("orderYrEst"),     # estimated flag (data-quality flag)
        "delivery_year": t.get("deliveryYr"),
        "units": t.get("units"),
        "units_est": t.get("unitsEst"),
        "designation": t.get("desg"),              # model (An-26 etc.)
        "description": t.get("desc"),              # equipment description (transport aircraft)
        "category": t.get("category"),             # major category (Aircraft etc.)
        "sub_category": t.get("subCategory"),
    } for t in trades]
    return {"rows": rows, "limit_applied": lim, "resolved_countries": resolved or None,
            "params": body, "_meta": r, "_metas": metas + [r]}
