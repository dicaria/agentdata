"""lv_knab — KNAB (Latvia, Corruption Prevention and Combating Bureau) political party
finance public database (info.knab.gov.lv/api, keyless).

LV legal faces (0.3.59; admitted from research booklet lv-knab-party-finance booklet — the party-
finance family's 18th pillar, rated 9/10 P0 — re-probed live 2026-11-13,
tmp/probe-sdk-0359/r2_knab_*.json). Two faces over the Vite-bundle-reverse-engineered API:
/api/parties — the party register (112 parties live; registrationNumber is the LV company
registry code, the hard join key), and /api/payments — the transaction-level named-donation
ledger (78,081 rows live, daily-updated down to yesterday; firstName/lastName/person are the
published donor names — statutory disclosure, by law — while personCode is the state-masked
PII form '211186*****', passed through verbatim and never de-masked).

CONTRACT (GET, query params; both endpoints echo {…, pagination: {page, limit, total,
totalPages}}):
- /api/parties?limit=&page= — rows {public_id, name, registrationNumber, foundedAt
  (DD.MM.YYYY), liquidated (0/1)}. No server-side term filter (the SPA searches client-side;
  a ?search= param is silently ignored — measured). page is 1-based (page=2 verified).
- /api/payments?limit=&page=&party_public_id= — rows {public_id, party_public_id, party,
  typeId, type ('Nauda' = money), amountDisplay ('75.00' — negative = expenditure
  direction), currency (EUR; the totals block also carries LVL for pre-2014 legacy),
  firstName, lastName, person, personCode (masked), date (DD.MM.YYYY, rolls to yesterday)}.
  party_public_id filters server-side (measured: one party → 121 rows).
- limit is echoed verbatim (no upstream clamp — limit=500 returned all 112 parties); totals
  on payments: {page: {EUR, LVL}, total: {EUR, LVL}} rides along.
The module normalizes dates DD.MM.YYYY → ISO, passes the masked personCode untouched, and
keeps amounts as strings (amountDisplay verbatim) + a numeric parse. 0.5/2 polite, TTL 24h.
"""
import re

from ..errors import SdkError

provider = {
    "id": "lv_knab",
    "baseUrl": "https://info.knab.gov.lv",
    "rate": {"rps": 0.5, "burst": 2},
    "concurrency": 2,
    "ops": {
        "parties": {"path": "/api/parties", "method": "GET", "idempotent": True, "timeout": 30.0},
        "payments": {"path": "/api/payments", "method": "GET", "idempotent": True, "timeout": 30.0},
    },
    "ttl": {"parties": 24 * 3600, "payments": 24 * 3600},
}

_DDMMYYYY = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")


def _lv_date_to_iso(v):
    """'16.06.2026' → '2026-06-16' (raw string rides along — upstream format is a contract)."""
    if not isinstance(v, str):
        return None
    m = _DDMMYYYY.match(v.strip())
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def party_from_upstream(d):
    """Party card (pure function — split out for offline testing)."""
    return {
        "public_id": d.get("public_id"),
        "name": d.get("name"),
        "registration_number": d.get("registrationNumber"),   # LV registry code — hard join key
        "founded": _lv_date_to_iso(d.get("foundedAt")),
        "founded_raw": d.get("foundedAt"),
        "liquidated": bool(d.get("liquidated")) if d.get("liquidated") is not None else None,
    }


def payment_from_upstream(d):
    """Payment card (pure function — split out for offline testing). personCode is the
    state-published MASKED form — passed through verbatim, never de-masked."""
    return {
        "public_id": d.get("public_id"),
        "party_public_id": d.get("party_public_id"),
        "party": d.get("party"),
        "type_id": d.get("typeId"),
        "type": d.get("type"),
        "amount_display": d.get("amountDisplay"),             # negative = expenditure direction
        "amount": _num(d.get("amountDisplay")),
        "currency": d.get("currency"),
        "donor_first_name": d.get("firstName"),
        "donor_last_name": d.get("lastName"),
        "donor": d.get("person"),
        "donor_code_masked": d.get("personCode"),
        "date": _lv_date_to_iso(d.get("date")),
        "date_raw": d.get("date"),
    }


def parties_raw(limit=100, page=1, *, cache=None, no_cache=False):
    """→ {total, rows[], params, pagination, _meta}. limit/page verbatim upstream (no clamp;
    the register is small — 112 parties live, one page can hold it all). No term filter
    upstream (measured silent-ignore) — filter client-side on the returned rows."""
    from ..transport import call_provider
    n, pg = _page_args(limit, page)
    r = call_provider(provider, "parties", {"limit": n, "page": pg},
                      cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    if not isinstance(doc, dict) or "parties" not in doc:
        raise SdkError("upstream_unavailable", provider="lv_knab",
                       detail="/api/parties answered an unexpected shape (no parties key)")
    return {"total": (doc.get("pagination") or {}).get("total"),
            "rows": [party_from_upstream(x) for x in doc.get("parties") or []],
            "pagination": doc.get("pagination"),
            "params": {"limit": n, "page": pg}, "_meta": r}


def payments_raw(limit=100, page=1, *, party_public_id=None, cache=None, no_cache=False):
    """→ {total, rows[], totals, params, pagination, _meta}. party_public_id = the server-side
    party filter (from parties_raw rows). 78,081 rows live — page through; the daily roll
    means a cached window is at most 24h stale."""
    from ..transport import call_provider
    n, pg = _page_args(limit, page)
    r = call_provider(provider, "payments", {"limit": n, "page": pg,
                                             "party_public_id": party_public_id},
                      cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    if not isinstance(doc, dict) or "payments" not in doc:
        raise SdkError("upstream_unavailable", provider="lv_knab",
                       detail="/api/payments answered an unexpected shape (no payments key)")
    return {"total": (doc.get("pagination") or {}).get("total"),
            "rows": [payment_from_upstream(x) for x in doc.get("payments") or []],
            "totals": doc.get("totals"),
            "pagination": doc.get("pagination"),
            "params": {"limit": n, "page": pg, "party_public_id": party_public_id},
            "_meta": r}


def _page_args(limit, page):
    """Shared wall: limit 1-500, page 1-based >=1."""
    try:
        n = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="lv_knab",
                       detail=f"limit must be an integer 1-500, got {limit!r}")
    if not 1 <= n <= 500:
        raise SdkError("usage_error", provider="lv_knab",
                       detail=f"limit must be 1-500 (echoed verbatim upstream, no clamp), got {limit!r}")
    try:
        pg = int(page) if page is not None else 1
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="lv_knab",
                       detail=f"page must be an integer >=1, got {page!r}")
    if pg < 1:
        raise SdkError("usage_error", provider="lv_knab",
                       detail=f"page is 1-based, got {pg}")
    return n, pg
