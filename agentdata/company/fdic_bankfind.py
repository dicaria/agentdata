"""fdic_bankfind — FDIC BankFind Suite (US insured-bank data: institutions master + failure /
change-log / locations / financials siblings; keyless).

Keyless at roughly ~1,000 req/hr/IP — we set 0.25 rps/burst 5, same tier as usaspending.
Live-shape check: **the host has moved to api.fdic.gov** (banks.data.fdic.gov 301) — new home /banks/institutions;
response data[].data.{NAME,CERT,CITY,STALP,ACTIVE,ID} (double-layered data).
Field-value findings confirmed by probing (2026-10-21): null fields are omitted upstream (absence = null, not
distinguishable); operating rows carry the ENDEFYMD='12/31/9999' sentinel (a flat export stamps every live row with a
9999 end date) → null; the end-date sense covers closure/de-insurance/M&A exits (SVB 24735=03/10/2023).

0.3.58 siblings (probed live 2026-11-13, tmp/probe-sdk-0358/p1_fdic.py + p7_refine.py — every
endpoint verified on api.fdic.gov itself, no redirect hop):
- failures /banks/failures: 4,117 rows, 1934→today. FAILDATE is M/D/YYYY (single-digit months
  legal, '5/28/1934'); pre-1960 rows can carry CERT null (the cert numbering post-dates them) —
  FUND is the then-key. mdy_to_iso normalizes FAILDATE in place.
- history /banks/history: the per-CERT structural-change log, 585,634 rows total (CERT:628 alone
  = 13,418). Real column names are CHANGECODE_DESC (the human sentence, 'Branch Acquired in
  Merger/Consolidation/Failure'), EFFDATE (ISO datetime), ENDDATE (ISO datetime with the
  '9999-12-31T00:00:00' still-open sentinel → null), INSTNAME / FRM_OFF_NAME (the rename pair).
  ~140 columns by default — the curated whitelist keeps eight.
- locations /banks/locations: the branch/office roster (CERT:628 = 5,414 offices; 37 cols by
  default — OFFNAME/OFFNUM/MAINOFF/SERVTYPE_DESC are the load-bearing ones).
- financials /banks/financials: quarterly statements of financial health (CERT:628 = 170
  quarters back to 1984). REPDTE is the 'YYYYMMDD' string; ID = 'CERT_REPDTE' composite; ASSET /
  DEP / EQ / NETINC are $ THOUSANDS (the suite's own convention — pass through, never rescale).
All four share the institutions contract: filters= / fields= / sort_by= / sort_order= / limit /
offset (row-based; limit wall 10,000 upstream — above it the suite answers a structured
400 validate:too_big), totals.count carries the matched count, and INVALID field names are
SILENTLY DROPPED (a typo costs a column without an error signal — the whitelists are the guard).
"""
import re

provider = {
    "id": "fdic-bankfind",
    "baseUrl": "https://api.fdic.gov",
    "rate": {"rps": 0.25, "burst": 5},
    "ops": {
        "institutions": {"path": "/banks/institutions"},  # params: search / filters / fields / limit (assembled query)
        # 0.3.58 sibling endpoints (probed live 2026-11-13, tmp/probe-sdk-0358/p1+p7): the same
        # BankFind Suite host serves the failure history, the per-CERT change log, the branch
        # location roster and the quarterly financial statements as /banks/* siblings
        "failures": {"path": "/banks/failures"},
        "history": {"path": "/banks/history"},
        "locations": {"path": "/banks/locations"},
        "financials": {"path": "/banks/financials"},
    },
    "ttl": {"institutions": 30 * 86400,   # registry master changes slowly
            "failures": 7 * 86400,        # 1934→today memorial (4,117 rows) — moves rarely
            "history": 7 * 86400,         # per-CERT change log — structural events, slow
            "locations": 7 * 86400,       # branch roster — M&A cadence
            "financials": 24 * 3600},     # quarterly statements — new quarter lands quarterly
}

FIELDS = "NAME,CERT,CITY,STALP,ACTIVE,REPDTE,ESTYMD,ENDEFYMD"

# 0.3.58 curated default column sets (measured field names — invalid names are SILENTLY DROPPED
# from the response upstream, so a typo costs a column without any error signal)
FAILURES_FIELDS = "NAME,CERT,CITY,PSTALP,FAILDATE,FUND"
HISTORY_FIELDS = "CERT,CHANGECODE,CHANGECODE_DESC,EFFDATE,ENDDATE,INSTNAME,FRM_OFF_NAME"
LOCATIONS_FIELDS = "CERT,OFFNAME,OFFNUM,MAINOFF,SERVTYPE_DESC,CITY,STALP"
FINANCIALS_FIELDS = "CERT,REPDTE,ASSET,DEP,EQ,NETINC,ID"

MDY_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
# active sentinel: a flat export stamps every live row with a 9999 end date
ACTIVE_SENTINEL = "12/31/9999"
# history ENDDATE sentinel: still-open change records carry '9999-12-31T00:00:00' — same 9999
# family as the institutions ENDEFYMD law, datetime flavour
HISTORY_END_SENTINEL = "9999-12-31"


def mdy_to_iso(v):
    """'M/D/YYYY'→'YYYY-MM-DD' (single- OR double-digit month/day — the failures FAILDATE spells
    '5/28/1934'; MDY strings are easy to misread across regions; other shapes are returned unchanged)."""
    if isinstance(v, str):
        s = v.strip()
        if MDY_RE.match(s):
            m, d, y = s.split("/")
            return f"{y}-{int(m):02d}-{int(d):02d}"
    return v if v is not None else None


def ymd_to_iso(v):
    """'YYYYMMDD' string→'YYYY-MM-DD' (the financials REPDTE spelling, e.g. '20260630')."""
    if isinstance(v, str) and len(v) == 8 and v.isdigit():
        return f"{v[0:4]}-{v[4:6]}-{v[6:8]}"
    return v


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


# —— 0.3.58 sibling faces (shared request/response plumbing; one _raw per endpoint) ——

def _sibling_raw(op, default_fields, *, filters=None, fields=None, limit=20, offset=0,
                 sort_by=None, sort_order=None, cache=None, no_cache=False):
    """Shared plumbing: filters required (the local whole-database safety wall — fdic_institutions
    law), limit 1-10000 (upstream 400 validate:too_big above), row-based offset, optional sort.
    Rows come back verbatim under upstream column names with in-place date normalization."""
    from ..transport import call_provider
    from ..errors import SdkError

    flt = str(filters or "").strip()
    if not flt:
        raise SdkError("usage_error", provider="fdic-bankfind",
                       detail=f"{op} requires filters (e.g. 'CERT:628' or a state sweep 'STALP:MI' — "
                              "the failures index spells its state field PSTALP; "
                              "the whole-register enumeration belongs to the corpus line, not the lookup face)")
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="fdic-bankfind", detail=f"limit must be an integer, got {limit!r}")
    if not 1 <= lim <= 10000:
        raise SdkError("usage_error", provider="fdic-bankfind",
                       detail=f"limit must be 1-10000 (the suite's own validate:too_big wall answers 400 above it), got {limit!r}")
    try:
        off = int(offset) if offset else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="fdic-bankfind", detail=f"offset must be an integer >=0, got {offset!r}")
    if off < 0:
        raise SdkError("usage_error", provider="fdic-bankfind", detail=f"offset must be >=0, got {off}")
    params = {"filters": flt, "fields": str(fields).strip() if fields else default_fields,
              "limit": lim, "offset": off}
    if sort_by:
        params["sort_by"] = str(sort_by).strip()
        params["sort_order"] = "desc" if str(sort_order or "").strip().lower() == "desc" else "asc"
    r = call_provider(provider, op, params, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    rows = [dict(e.get("data") or {}) for e in doc.get("data") or []]
    total = (doc.get("totals") or {}).get("count", (doc.get("meta") or {}).get("total"))
    return {"total": total if total is not None else len(rows), "rows": rows,
            "params": params, "_meta": r}


def failures_raw(*, filters=None, fields=None, limit=20, offset=0,
                 sort_by=None, sort_order=None, cache=None, no_cache=False):
    """→ {total, rows[], params, _meta}. Failure history 1934→today (4,117 rows); filters like
    'CERT:3510' (First Republic) or 'PSTALP:TX' (911 TX failures — this index spells the state
    field PSTALP; STALP/CITY/NAME text filters answer a SILENT zero here). FAILDATE normalized
    M/D/YYYY→ISO in place; early rows carry CERT null (FUND is the then-key) — kept verbatim."""
    out = _sibling_raw("failures", FAILURES_FIELDS, filters=filters, fields=fields,
                       limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order,
                       cache=cache, no_cache=no_cache)
    for row in out["rows"]:
        if "FAILDATE" in row:
            row["FAILDATE"] = mdy_to_iso(row["FAILDATE"])
    return out


def history_raw(*, filters=None, fields=None, limit=20, offset=0,
                sort_by=None, sort_order=None, cache=None, no_cache=False):
    """→ {total, rows[], params, _meta}. Per-CERT structural-change log (585,634 rows; CERT:628 =
    13,418). ENDDATE '9999-12-31T00:00:00' sentinel → null (still-open change) in place; EFFDATE
    kept ISO verbatim; CHANGECODE_DESC is the human sentence."""
    out = _sibling_raw("history", HISTORY_FIELDS, filters=filters, fields=fields,
                       limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order,
                       cache=cache, no_cache=no_cache)
    for row in out["rows"]:
        end = row.get("ENDDATE")
        if isinstance(end, str) and end.startswith(HISTORY_END_SENTINEL):
            row["ENDDATE"] = None
    return out


def locations_raw(*, filters=None, fields=None, limit=20, offset=0,
                  sort_by=None, sort_order=None, cache=None, no_cache=False):
    """→ {total, rows[], params, _meta}. Branch/office roster (CERT:628 = 5,414 offices); MAINOFF
    =1 marks the head office, SERVTYPE_DESC the service type. Rows verbatim (no date columns)."""
    return _sibling_raw("locations", LOCATIONS_FIELDS, filters=filters, fields=fields,
                        limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order,
                        cache=cache, no_cache=no_cache)


def financials_raw(*, filters=None, fields=None, limit=20, offset=0,
                   sort_by=None, sort_order=None, cache=None, no_cache=False):
    """→ {total, rows[], params, _meta}. Quarterly statements of financial health (CERT:628 = 170
    quarters; default sort REPDTE desc). REPDTE 'YYYYMMDD'→ISO in place; ASSET/DEP/EQ/NETINC are
    $ THOUSANDS — the suite's own convention, passed through verbatim, never rescaled."""
    out = _sibling_raw("financials", FINANCIALS_FIELDS, filters=filters, fields=fields,
                       limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order,
                       cache=cache, no_cache=no_cache)
    for row in out["rows"]:
        if "REPDTE" in row:
            row["REPDTE"] = ymd_to_iso(row["REPDTE"])
    return out
