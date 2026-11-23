"""ch_six_onot — SIX Swiss Exchange official notices v2 (six-group.com
/sheldon/official_notices, keyless; 0.3.72 batch E14).

Same host as ch_six_fqs but a different service family (the sheldon notice
pipeline vs the FQS reference query) — its own provider identity and
politeness (the edgar-family precedent: providers per service, host shared).

2026-11-19 probed laws (tmp/probe-e14/):
  - TWO ENDPOINTS: GET /sheldon/official_notices/v2/find.json?firstDate=…
    &lastDate=…&pageNumber=…&pageSize=…&sortAttribute=date&sortDirection=desc
    → {status,totalCount,itemList[{noticeId,date(int yyyymmdd),publishTime,
    noticeType,contact,title,isin}]} and GET …/details/{noticeId}.json → the
    SAME envelope with itemList[0] = 11 keys (number/isin/text(full body)/
    contact/contactPerson/contactPhone/valorNumber/noticeId/noticeType/date/
    title — person/phone/valor are null on many rows, verbatim).
  - THE show* TYPE SWITCHES ARE DEAD: an 8-combination matrix (bare,
    showFL=true, showA=false, FL-true+rest-false, case variant…) all answered
    the IDENTICAL bare-window response — server-side type filtering is gone.
    The face filters noticeType LOCALLY (A automatic / M manual / EX
    ex-dividend / PZ provisional / FL first-listing / DE delisting). Historic
    recipes claiming show* semantics are stale — do not send them.
  - issuerWords IS ALIVE (server-side issuer filter): issuerWords=Vontobel
    over a 6-day window answered totalCount 142 with every contact a Vontobel
    entity — passed through verbatim, never second-guessed client-side. BUT
    THE ISSUER VIEW IS A PAGE-1 SNAPSHOT: page 1 answers a PARTIAL page (43
    rows against totalCount 143 — an upstream internal cap), and deeper
    issuer pages garble PERSISTENTLY (4 retries, all non-JSON — the garble
    storm does not clear on backoff). p9 2026-11-19.
  - PAGE-SIZE LAW: pageSize=100 pages soundly (100/100/100/100/15 then a clean
    empty page). pageSize=200 answers page 1 with 200 rows but page 3 EMPTY;
    pageSize=1000 answers an EMPTY itemList while totalCount still echoes —
    the silent-over-cap shape. The engine pins pageSize=100.
  - REACHABLE CEILING: a 6-day all-types window answers totalCount 515 while
    only 415 rows are reachable (5 pages × 100, then empty) — keep windows
    ~1 week for full coverage; the boundary is documented, not worked around.
  - THE STREAM: ~515 notices/week all-types; A dominates (377/415 reachable
    rows — structured-product barrier events; Bank Vontobel is the top
    contact), M 22 / EX 6 / PZ 5 / FL 5. FL (first-listing) titles are BARE
    DATE STRINGS ("Part I", "17.11.2026") — the semantics live in the details
    text; isin is null on most list rows and fills on details (or inside the
    text body). noticeId is the sequential anchor (max 371130 probe day).
  - TRANSIENT GARBLED 200s happen (two JSONDecodeErrors inside one probe run)
    — the module parses manually and retries once through no_cache before
    giving up (never caches a garbled body as good).

Politeness 1 rps, burst 1. TTLs: find 1h (the stream grows intraday), detail
24h (a published notice freezes — the DI-forms law).
"""
import json
import time
from datetime import date, timedelta

from ..errors import SdkError

provider = {
    "id": "ch_six_onot",
    "baseUrl": "https://www.six-group.com",
    "rate": {"rps": 1.0, "burst": 1},
    "ops": {
        "find": {"path": "/sheldon/official_notices/v2/find.json",
                 "idempotent": True, "accept": "text", "timeout": 90.0},
        "detail": {"path": "/sheldon/official_notices/v2/details/{notice_id}.json",
                   "idempotent": True, "accept": "text", "timeout": 90.0,
                   "notFound": [404]},
    },
    "ttl": {"find": 3600, "detail": 86400},
}

NOTICE_TYPES = ("A", "M", "EX", "PZ", "FL", "DE")
_PAGESIZE = 100  # the measured sound page size (200 breaks paging, 1000 answers empty)


def _parse(text):
    if not text or not text.strip():
        return None
    return json.loads(text)


def _norm_date(v, *, default=None):
    """accept YYYYMMDD or ISO yyyy-mm-dd → yyyymmdd string (a 19-11-2026 shape is
    REFUSED — dash-stripping it would silently pass as a legal-looking 8-digit string
    with the day/year fields swapped)."""
    if v is None or v == "":
        if default is None:
            return None
        v = default
    raw = str(v).strip()
    if "-" in raw:
        parts = raw.split("-")
        if len(parts) != 3 or len(parts[0]) != 4:
            raise SdkError("usage_error", provider="ch_six_onot",
                           detail=f"date must be YYYYMMDD or ISO yyyy-mm-dd, got \"{v}\"")
        s = "".join(parts)
    else:
        s = raw
    if len(s) != 8 or not s.isdigit():
        raise SdkError("usage_error", provider="ch_six_onot",
                       detail=f"date must be YYYYMMDD or ISO yyyy-mm-dd, got \"{v}\"")
    return s


def _call_with_parse_retry(op, params, cache, no_cache):
    """the flaky-gateway law (live 2026-11-19): sheldon answers BOTH transient
    502s (issuerWords queries hit the gateway hard — transport's own ~6s
    retry loop is too impatient, an 8s patient retry recovers) AND occasional
    garbled 200s. One no-cache retry each; a garbled body never stands (and
    never caches as the good copy)."""
    from ..transport import call_provider

    try:
        r = call_provider(provider, op, params, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code != "upstream_unavailable":
            raise
        time.sleep(8)
        r = call_provider(provider, op, params, cache=None, no_cache=True)
    try:
        return _parse(r["data"]), r
    except ValueError:
        time.sleep(4)
        r2 = call_provider(provider, op, params, cache=None, no_cache=True)
        try:
            return _parse(r2["data"]), r2
        except ValueError:
            raise SdkError("upstream_unavailable", provider="ch_six_onot",
                           detail=f"{op} answered 200 with a non-JSON body twice (transient garble observed live) — retry shortly")


def find(*, from_date=None, to_date=None, notice_type=None, issuer=None,
         page=1, limit=None, cache=None, no_cache=False):
    """→ {total_count, page, pagesize, rows[], params, _meta}; the official
    notices window query (~515/week all-types; A dominates). noticeType
    filters LOCALLY (the upstream show* switches are dead — verified
    2026-11-19, do not send them); issuer rides issuerWords (server-side,
    alive — but a PAGE-1 SNAPSHOT: partial page + deeper issuer pages garble
    persistently). pageSize pinned at 100 (200 breaks paging, 1000 answers empty —
    the silent-over-cap shape). Reachable ceiling ~5 pages/window: keep
    windows ~1 week for full coverage (totalCount can exceed the reachable
    rows — 515 vs 415 on the probe window)."""
    today = date.today()
    f = _norm_date(from_date, default=(today - timedelta(days=7)).strftime("%Y%m%d"))
    t = _norm_date(to_date, default=today.strftime("%Y%m%d"))
    if f > t:
        raise SdkError("usage_error", provider="ch_six_onot",
                       detail=f"from-date {f} is after to-date {t}")
    nt = str(notice_type).strip().upper() if notice_type else None
    if nt is not None and nt not in NOTICE_TYPES:
        raise SdkError("usage_error", provider="ch_six_onot",
                       detail=f"notice-type must be one of {'/'.join(NOTICE_TYPES)} (A/M/EX/PZ/FL/DE), got \"{notice_type}\"")
    pg = max(1, int(page or 1))
    params = {"firstDate": f, "lastDate": t, "pageNumber": pg,
              "pageSize": _PAGESIZE, "sortAttribute": "date",
              "sortDirection": "desc"}
    if issuer:
        params["issuerWords"] = str(issuer).strip()
    d, r = _call_with_parse_retry("find", params, cache, no_cache)
    if not isinstance(d, dict) or "itemList" not in d:
        raise SdkError("upstream_unavailable", provider="ch_six_onot",
                       detail="find.json did not answer the {status,totalCount,itemList} envelope — the sheldon API may have moved; re-probe")
    items = d.get("itemList") or []
    rows = [x for x in items if nt is None or str(x.get("noticeType") or "").upper() == nt]
    total_stream = d.get("totalCount")
    if limit is not None and int(limit) >= 0:
        rows = rows[: int(limit)]
    return {"total_count": total_stream, "page": pg, "pagesize": _PAGESIZE,
            "rows": rows,
            "params": params, "_meta": r}


def detail(*, notice_id, cache=None, no_cache=False):
    """→ {found, notice_id, notice|None, params, _meta}; one notice's full body
    (11 keys — number/isin/text/contact/contactPerson/contactPhone/
    valorNumber + the list-row echoes). FL titles are bare date strings; the
    semantics live in `text`. Published notices freeze → TTL 24h."""
    try:
        nid = int(str(notice_id).strip())
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ch_six_onot",
                       detail=f"--notice-id must be an integer noticeId (e.g. 371130), got \"{notice_id}\"")
    if nid <= 0:
        raise SdkError("usage_error", provider="ch_six_onot",
                       detail=f"--notice-id must be positive, got {nid}")
    d, r = _call_with_parse_retry("detail", {"notice_id": nid}, cache, no_cache)
    items = (d or {}).get("itemList") or [] if isinstance(d, dict) else []
    if not items:
        return {"found": False, "notice_id": nid, "notice": None,
                "params": {"notice_id": nid}, "_meta": r}
    return {"found": True, "notice_id": nid, "notice": items[0],
            "params": {"notice_id": nid}, "_meta": r}
