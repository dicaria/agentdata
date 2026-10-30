"""fdic_bankfind — FDIC BankFind Suite (US insured-bank institution master lookup; keyless).

Keyless at roughly ~1,000 req/hr/IP — we set 0.25 rps/burst 5, same tier as usaspending.
Live-shape check: **the host has moved to api.fdic.gov** (banks.data.fdic.gov 301) — new home /banks/institutions;
response data[].data.{NAME,CERT,CITY,STALP,ACTIVE,ID} (double-layered data).
Field-value findings confirmed by probing (2026-10-21): null fields are omitted upstream (absence = null, not
distinguishable); operating rows carry the ENDEFYMD='12/31/9999' sentinel (a flat export stamps every live row with a
9999 end date) → null; the end-date sense covers closure/de-insurance/M&A exits (SVB 24735=03/10/2023).
Financials are not here (the fdic-edos corpus line already covers them); this face only answers "which bank is this,
is it still alive" against the master current values.
"""
import re

provider = {
    "id": "fdic-bankfind",
    "baseUrl": "https://api.fdic.gov",
    "rate": {"rps": 0.25, "burst": 5},
    "ops": {
        "institutions": {"path": "/banks/institutions"},  # params: search / filters / fields / limit (assembled query)
    },
    "ttl": {"institutions": 30 * 86400},  # registry master changes slowly
}

FIELDS = "NAME,CERT,CITY,STALP,ACTIVE,REPDTE,ESTYMD,ENDEFYMD"

MDY_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
# active sentinel: a flat export stamps every live row with a 9999 end date
ACTIVE_SENTINEL = "12/31/9999"


def mdy_to_iso(v):
    """'MM/DD/YYYY'→'YYYY-MM-DD' (MDY strings are easy to misread across regions; other shapes are returned unchanged)."""
    if isinstance(v, str):
        s = v.strip()
        if MDY_RE.match(s):
            return f"{s[6:10]}-{s[0:2]}-{s[3:5]}"
    return v if v is not None else None


def institution_from_upstream(d):
    """Institution card pure mapping (split out for offline testing; upstream omits null fields — absence = null, not
    distinguishable; the ENDEFYMD sentinel '12/31/9999' = operating → null, only a real end date lands a value)."""
    end = d.get("ENDEFYMD") if d.get("ENDEFYMD") and d.get("ENDEFYMD") != ACTIVE_SENTINEL else None
    active = d.get("ACTIVE")
    return {
        "cert": d.get("CERT"),
        "name": d.get("NAME"),
        "city": d.get("CITY"),
        "state": d.get("STALP"),
        "active": True if active == 1 else False if active == 0 else None,
        "established_date": mdy_to_iso(d.get("ESTYMD")),   # opening date
        "end_date": mdy_to_iso(end),                       # end of the insurance relationship (null while operating)
        "report_date": mdy_to_iso(d.get("REPDTE")),        # master current-value reporting period
    }


def find_bank(*, name=None, cert=None, limit=5, cache=None, no_cache=False):
    """→ {total, institutions[{cert,name,city,state,active,established_date,end_date,report_date}], _meta}.
    Name fuzzy (ES phrase form) or CERT exact — exactly one of the two; active semantics 1=operating, 0=closed."""
    from ..transport import call_provider
    from ..errors import SdkError

    params = {"fields": FIELDS, "limit": min(max(1, int(limit) or 5), 50)}
    if cert is not None and str(cert).strip() != "":
        try:
            params["filters"] = f"CERT:{int(str(cert).strip())}"  # CERT exact
        except ValueError:
            raise SdkError("usage_error", provider="fdic-bankfind",
                           detail=f"CERT must be numeric: {cert}")
    elif name:
        q = str(name).strip()
        if not q:
            raise SdkError("usage_error", provider="fdic-bankfind", detail="findBank requires either --name or --cert")
        params["search"] = f'NAME:"{q}"'  # ES phrase-form name match
    else:
        raise SdkError("usage_error", provider="fdic-bankfind", detail="findBank requires either --name or --cert")
    r = call_provider(provider, "institutions", params, cache=cache, no_cache=no_cache)
    rows = [institution_from_upstream(e.get("data") or {})
            for e in (r["data"] or {}).get("data") or []]
    total = (r["data"] or {}).get("meta", {}).get("total")
    return {"total": total if total is not None else len(rows), "institutions": rows, "_meta": r}


def institutions_raw(*, search=None, filters=None, fields=None, limit=5,
                     cache=None, no_cache=False):
    """→ {total, institutions[], params, _meta}; search/filters pass through with upstream names (combinable — ES full text × structured filter).
    limit has no upstream wall: measured 2026-10-23, 1001 really returns 1001 rows and 10000 really returns 10000 rows
    (whole database 27,835); the old find_bank 50 cap is this repo's politeness tier, not an upstream limit. fields defaults to
    the eight FIELDS columns and can be overridden with a comma-separated string.
    Zero hits is a legal empty set (no raise — the find_bank CERT face carries its own semantics at the client layer)."""
    from ..transport import call_provider
    from ..errors import SdkError

    lim = int(limit)
    if lim < 1:
        raise SdkError("usage_error", provider="fdic-bankfind", detail="limit must be ≥1")
    params = {"fields": str(fields).strip() if fields else FIELDS, "limit": lim}
    if search:
        params["search"] = str(search)
    if filters:
        params["filters"] = str(filters)
    r = call_provider(provider, "institutions", params, cache=cache, no_cache=no_cache)
    rows = [institution_from_upstream(e.get("data") or {})
            for e in (r["data"] or {}).get("data") or []]
    total = (r["data"] or {}).get("meta", {}).get("total")
    return {"total": total if total is not None else len(rows), "institutions": rows,
            "params": params, "_meta": r}
