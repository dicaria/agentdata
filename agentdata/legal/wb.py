"""wb — World Bank debarred-firms roster provider (apigwext SAP gateway; keyless via the page-embedded public apikey).

legal debarment-roster face (0.3.21; admitted 2026-11-02, probed tmp/probe-debar-0321). Shape measured 2026-11-02:
GET /dvsvc/v1.0/json/APPLICATION/ADOBE_EXPRNCE_MGR/FIRM/SANCTIONED_FIRM + header apikey
  → {"response": {"ZPROCSUPP": [1,546 rows × 45 SAP fields]}} — a single-shot full dump, no paging, 1.77MB
  (the page self-reports a 3-hour refresh; the row count drifts as the live register is regenerated).
Golden fields: SUPP_ID (the WB supplier key) × SUPP_NAME × SUPP_TYPE_CODE (F firm 1,268 / I individual 269 /
U 8 / C 1) × LAND1+COUNTRY_NAME × address quartet × SUPP_ELIG_STAT (DEBARRED 890 / X-DEBARRED 656) ×
DEBAR_FROM_DATE~DEBAR_TO_DATE (**2999-12-31 = indefinite**, measured) × DEBAR_REASON (procurement-guidelines
clause citation, "Procurement Guidelines, 1.14(a)(ii)") × INELIGIBLY_STATUS ("Ongoing"). China leads the
roster at 392 firms (LAND1=CN, measured 2026-11-02); DNB/REGISTER identifier fields exist in the schema but
measure empty — name walk is the join channel (name × country narrows well).
The gateway apikey is a **browser-public constant embedded in the debarred-firms page inline script** (every
browser visitor sends the same key; not a registration credential — the same class as dgcomp's CS_PROD_ODSE_PROD
public config key); pinned live 2026-11-02: plain agentdata UA + this key = 200, no UA override needed.
Screening = **local full-register scan** (upstream has no query surface) — pull the whole dump once, cache 24h,
then contains-match scans run with zero network (same contract as csl_screening_list).
TTL: 24h (upstream refreshes every 3h; a day-old screening register is fine); polite tier 0.2 rps
(single-endpoint face, one pull per day suffices).
"""
from ..errors import SdkError

provider = {
    "id": "wb",
    "baseUrl": "https://apigwext.worldbank.org",
    "rate": {"rps": 0.2, "burst": 1},
    "ops": {
        "sanctioned_firms": {  # single-shot full dump (no paging, no query surface)
            "path": "/dvsvc/v1.0/json/APPLICATION/ADOBE_EXPRNCE_MGR/FIRM/SANCTIONED_FIRM",
            "timeoutMs": 120000,  # 1.77MB JSON
        },
    },
    "ttl": {"sanctioned_firms": 24 * 3600},
}

# browser-public apikey embedded in the debarred-firms page inline script (pinned 2026-11-02;
# the same constant every browser visitor sends — not a .env credential, see module docstring)
_PUBLIC_APIKEY = {"apikey": "z9duUaFUiEUYSHs97CU38fcZO7ipOPvm"}

# row narrowing: of the 45 SAP fields, the twelve golden ones (identity × jurisdiction × window × reason)
_FIELDS = ("SUPP_ID", "SUPP_NAME", "SUPP_TYPE_CODE", "LAND1", "COUNTRY_NAME", "SUPP_CITY", "SUPP_ADDR",
           "SUPP_ELIG_STAT", "DEBAR_FROM_DATE", "DEBAR_TO_DATE", "DEBAR_REASON", "INELIGIBLY_STATUS")


def rows_from_upstream(data):
    """Upstream ZPROCSUPP array → debarred-firm rows (pure function, offline-testable; SAP field names verbatim,
    narrowed to the golden twelve — the DNB/REGISTER identifier fields measure empty and are dropped)."""
    payload = (data or {}).get("response") or {}
    rows = [{k: r.get(k) for k in _FIELDS} for r in (payload.get("ZPROCSUPP") or [])]
    return rows


def filter_rows(rows, name=None, country=None, type=None):
    """Local register scan (pure function for offline regression). name: contains-match (case-insensitive)
    over SUPP_NAME; country: contains over COUNTRY_NAME **or** the LAND1 code ("China" and "CN" both hit);
    type: exact over SUPP_TYPE_CODE (F/I/U/C, case-insensitive)."""
    needle = str(name or "").strip().lower() or None
    cn_needle = str(country or "").strip().lower() or None
    ty_needle = str(type or "").strip().upper() or None
    hits = []
    for r in rows:
        if cn_needle and cn_needle not in str(r.get("COUNTRY_NAME") or "").lower() \
                and cn_needle != str(r.get("LAND1") or "").lower():
            continue
        if ty_needle and str(r.get("SUPP_TYPE_CODE") or "").strip().upper() != ty_needle:
            continue
        if needle and needle not in str(r.get("SUPP_NAME") or "").lower():
            continue
        hits.append(r)
    return hits


def debarred_firms_raw(name=None, *, country=None, type=None, limit=20, cache=None, no_cache=False):
    """Full-register scan (pulls the whole dump, caches 24h, then scans locally)
    → {rows, total_matched, scanned_rows, limit_applied, params, _meta}.

    name = contains-match over SUPP_NAME; country = contains over country name or the LAND1 code;
    type = F/I/U/C exact. No filter → enumerate from the register head (the local payload wall keeps
    truncation visible: total_matched echoes the exact hit count)."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20  # explicit None check — an `or default` swallows 0, the 0.2.10 trap
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="wb",
                       detail=f"limit must be 1-100 (local payload wall), got '{limit}'")
    r = call_provider(provider, "sanctioned_firms", {}, cache=cache, no_cache=no_cache,
                      extra_headers=_PUBLIC_APIKEY)
    rows = rows_from_upstream(r["data"])
    hits = filter_rows(rows, name=name, country=country, type=type)
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "limit_applied": size,
            "params": {"name": name, "country": country, "type": type}, "_meta": r}
