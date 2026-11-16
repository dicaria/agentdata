"""kr_kipris — KIPRIS domestic patent·utility-model search (KIPO portal www.kipris.or.kr,
/kpat/resulta.do, keyless). Register 2026-11-04, re-verified live 2026-11-12 with the SDK's
own polite UA (probes tmp/probe-sdk-0356/p3*, total ≈30 requests). The company-domain KR
pillar of the IP axis — the flag bearer: 84-key rows at up to 2,000 rows/page, and the row
field APC is the 사업자등록번호 (Korean business registration number) — the IP family's second
hard corporate key after AU's ABN.

WIRE CONTRACT (form-urlencoded POST — a JSON body is answered resultCode "98" empty; measured
both ways 2026-11-12): queryText = expression = historyQuery = the query — all three fields
carry the SAME value (an empty expression/historyQuery is answered "98" even when queryText
would hit 394,837 rows; measured). Plus numPerPage / currentPage / sortField=RANK /
sortState=Desc. The upstream's own SPA cadence headers (X-Requested-With, Referer, Origin) are
sent along — cheap insurance, none of them gated (measured). The polite `agentdata/*` UA
passes clean (no UA fingerprint gate — measured with and without).

QUERY DSL: q takes a bare keyword (삼성전자 → 394,837) or the upstream date-window DSL
verbatim: OPD=[YYYYMMDD~YYYYMMDD] (공개일/publication date), PD (출원일/application),
RPD (등록일/registration), OD (design-class single-day) — windows compound across the DSL with
spaces. Result-count semantics live-verified: OPD 2026-11-03 (Tue) = 786, 11-11 = 205,
2025-10 whole month = 13,116; whole-history keyword search reaches the full corpus.

RESPONSE CODE LAW (the trap): resultCode "00" = rows follow; **"98" = ZERO-HIT query, not an
error** — a zero-publication day (Sundays: 11-01, 11-07 measured; holidays: 2026-01-01), a
date axis still empty (AD=[20261111~20261111] — application dates lag in the index), or a
keyword with no match all answer {"countInfo":{...0},"resultCode":"98"}. The face maps 98 →
rows=[], total=0 (zero_hit=True) — a batch walker must treat 98 as the empty answer, NOT a
failure. "99" = page beyond the 255 wall (raise).

ROWS: 84 keys verbatim — AP (출원인 한글, pipe-separated multi-value) / APE (English) /
**APC (사업자등록번호 — THE hard join key; pipe-separated when multiple)** / APBRN (KIPO
customer number, often "&nbsp;" placeholder) / AN (application) / OPN (publication) / GN
(grant) / AD-PD-OD-GD dates / TL·TL2 titles (TL carries <!HS>…<!HE> highlight tokens, TLE/TLV
carry <span class='red'> wraps — strip or keep, both verbatim upstream) / IPC·CPC·FI·FT
classifications / LST·SST legal-status fields. Empty cells arrive as the literal string
"&nbsp;" — kept verbatim (the honest-gap convention). True pagination (page1∩page2 = 0
measured on AN keys). TTL 24h.
"""
from ..errors import SdkError

provider = {
    "id": "kr_kipris",
    "baseUrl": "https://www.kipris.or.kr",
    "rate": {"rps": 0.25, "burst": 2},
    "concurrency": 1,
    "ops": {
        "search": {"path": "/kpat/resulta.do", "method": "POST", "urlencoded": True,
                   "idempotent": True, "timeout": 120.0},
    },
    "ttl": {"search": 24 * 3600},
}

_PAGE_CAP = 2000     # numPerPage hard ceiling (booklet-measured)
_PAGE_WALL = 255     # currentPage beyond this answers resultCode "99"


def rows_from_upstream(data):
    """resulta.do response → {rows, total, count, result_code, zero_hit} (pure function).
    resultCode "98" is the upstream's ZERO-HIT answer (empty corpus day / unmatched keyword /
    unindexed date axis) — mapped to rows=[], zero_hit=True, NOT an error."""
    code = data.get("resultCode")
    ci = data.get("countInfo") or {}
    if code == "98":
        return {"rows": [], "total": 0, "count": 0, "result_code": "98", "zero_hit": True}
    return {"rows": list(data.get("resultList") or []),
            "total": ci.get("totalcount"), "count": ci.get("count"),
            "result_code": code, "zero_hit": False}


def search_raw(q, *, page=1, page_size=20, cache=None, no_cache=False):
    """→ rows_from_upstream(...) + params + _meta. q = bare keyword or the upstream date DSL
    verbatim (OPD=[YYYYMMDD~YYYYMMDD] publication / PD application / RPD registration);
    page 1-based; page_size 1-2000 (the family's highest throughput; the SPA itself walks
    10/page)."""
    from ..transport import call_provider

    qq = str(q or "").strip()
    if not qq:
        raise SdkError("usage_error", provider="kr_kipris",
                       detail="search requires q (keyword or the date DSL verbatim, e.g. "
                              'OPD=[20261103~20261103] — a zero-publication day (weekend/holiday) '
                              'answers the "98" zero-hit code, which this face maps to an empty result)')
    try:
        pg = int(page) if page is not None else 1
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="kr_kipris",
                       detail=f"page must be an integer >=1, got {page!r}")
    if pg < 1:
        raise SdkError("usage_error", provider="kr_kipris",
                       detail=f"page is 1-based (got {pg}; upstream answers resultCode 99 beyond page {_PAGE_WALL})")
    if pg > _PAGE_WALL:
        raise SdkError("usage_error", provider="kr_kipris",
                       detail=f"page beyond the upstream 255 wall (got {pg}) — slice by date window instead")
    try:
        size = int(page_size) if page_size is not None else 20
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="kr_kipris",
                       detail=f"page_size must be an integer 1-{_PAGE_CAP}, got {page_size!r}")
    if not 1 <= size <= _PAGE_CAP:
        raise SdkError("usage_error", provider="kr_kipris",
                       detail=f"page_size must be 1-{_PAGE_CAP} (upstream hard ceiling), got '{page_size}'")
    params = {"queryText": qq, "expression": qq, "historyQuery": qq,   # all three MUST carry the query
              "numPerPage": str(size), "currentPage": str(pg),
              "sortField": "RANK", "sortState": "Desc"}
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache,
                      extra_headers={"X-Requested-With": "XMLHttpRequest",
                                     "Referer": provider["baseUrl"] + "/khome/search/searchResult.do?tab=patent",
                                     "Origin": provider["baseUrl"]})
    d = r["data"] or {}
    out = rows_from_upstream(d)
    if out["result_code"] == "99":
        raise SdkError("upstream_unavailable", provider="kr_kipris",
                       detail=f'resultCode 99 — page {pg} rejected as out-of-range (wall {_PAGE_WALL})')
    if out["result_code"] not in ("00", "98"):
        raise SdkError("upstream_unavailable", provider="kr_kipris",
                       detail=f'unknown resultCode {out["result_code"]!r} — the upstream contract may have changed')
    out["params"] = {"q": qq, "page": pg, "page_size": size}
    out["_meta"] = r
    return out
