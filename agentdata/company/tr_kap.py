"""tr_kap — KAP company-disclosure platform registers (www.kap.org.tr; keyless; the
company domain's TR depth face No. 2 after tr_spk_listed — the disclosed-issuer register
and the disclosure stream behind it).

Two faces (0.3.57; probed 2026-11-12, tmp/probe-sdk-0357/ — kap-igs-a.json (756 rows ×
27 keys) + kap-igs-w.json (the W placeholder) + kap-byCriteria.json (2,000-row cap window)
+ the four-way gate measurement; research volume booklet 121):

  * members — the KAP-member register: GET /tr/api/company/items/{type}/{state}. type is
    the register's own segment code (IGS / YK / PYS / BBDK / IGMS — passed verbatim, the
    semantics are not documented upstream; IGS/A measured 756 rows × 27 keys), state is
    A / P / W (A = the live register). Rows carry the issuer's join keys verbatim:
    taxNo + tradeRegNo + tradeRegOffice (the TR company triple), mkkMemberOid (the MKK
    central depository id), stockCode (the BIST ticker when listed), kapMemberTitle,
    kayitliSermayeTavani / paidCapital, faaliyetDurumu, cityName, and
    sgbfOrtaklikYapisi — a STRUCTURE flag (whether the member is an SGBF fund-manager
    group), kept verbatim. **No SGBF member-entity face exists by ruling** — the SGBF
    (fund managers) directory is a natural-person-adjacent PII surface, deliberately out.
  * **the W placeholder is a filter law**: state=W answers ONE fake row (taxNo
    111111111111, tradeRegNo 'A', kapMemberTitle null — measured 2026-11-12). The row is
    dropped from rows[] and counted in census.placeholder_rows — never shipped as an
    issuer.
  * disclosures — the disclosure stream: POST /tr/api/disclosure/members/byCriteria with
    a JSON body {fromDate, toDate} (ISO dates). Rows are disclosures verbatim (publishDate
    "12.11.2026 12:41:43" — the upstream's own TR format, kept), kapTitle, disclosureClass/
    Type/Category, subject, summary, relatedStocks, year, period, disclosureIndex, isLate,
    attachmentCount, modifyStatus. Corpus reaches 2009-06.
  * **the 2,000-row response cap**: a 10-day window (11-01..11-10) answers EXACTLY 2,000
    rows newest-first (measured 2026-11-12); a 2-day window answers 823. There is no
    total echo upstream — none is fabricated; len(rows) == 2000 flags likely_truncated
    and the caller narrows the window (the face caps the window at 31 days locally).
  * **the gate is measured OPEN (all four ways)**: the research-era three-piece key
    (warmup cookie + Referer + research UA, pinned 2026-11-02) is NO LONGER enforced —
    cookie+referer+UA / cookie only / referer only / NEITHER all answer 200 (measured
    2026-11-12, the kr_law gate-drift precedent: measure all ways, ship the simple bare
    client, document the drift). Egress note: from THIS development machine the env
    proxy's exit is TLS-reset for www.kap.org.tr (WinError 10054 — urllib honors env
    proxies); direct connect works. Callers behind such a proxy unset it for this host.

Channel: bare GET/POST, SDK UA, no key, no CAPTCHA, no published rate window → polite
0.5 rps / burst 2. TTL: members 24h (register posture), disclosures 1h (the stream
updates intraday).
"""
from datetime import date as _date

from ..errors import SdkError
from ..transport import call_provider

provider = {
    "id": "tr_kap",
    "baseUrl": "https://www.kap.org.tr",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # params: type/state ride the path (the register's own segment codes, validated
        # locally). Bare list JSON payload.
        "items": {"path": "/tr/api/company/items/{type}/{state}", "timeout": 60.0},
        # POST read semantics: the non-path params {fromDate, toDate} become the JSON
        # body (idempotent — a pure read). Bare list JSON payload, newest-first.
        "disclosures": {"path": "/tr/api/disclosure/members/byCriteria", "method": "POST",
                        "idempotent": True, "timeout": 60.0},
    },
    "ttl": {"items": 24 * 3600, "disclosures": 3600},
}

_TYPES = ("IGS", "YK", "PYS", "BBDK", "IGMS")
_STATES = ("A", "P", "W")
_DATE_RE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$")
_CAP = 2000  # the measured response cap (a 10-day window answers exactly this)
_MAX_WINDOW = 31  # local politeness wall on the from..to span


def _is_placeholder(row):
    """the W-state fake record: taxNo 111111111111 + tradeRegNo 'A' + no title (measured
    2026-11-12) — the register's own placeholder shape, never an issuer."""
    return (row.get("kapMemberTitle") is None
            and str(row.get("taxNo")) == "111111111111"
            and str(row.get("tradeRegNo")) == "A")


def rows_from_items(data):
    """the bare list → member rows + placeholder census — pure (dict rows pass verbatim;
    the placeholder is separated, never dropped silently)."""
    rows, placeholders = [], 0
    for r in data if isinstance(data, list) else []:
        if not isinstance(r, dict):
            continue
        if _is_placeholder(r):
            placeholders += 1
            continue
        rows.append(r)
    return rows, placeholders


def members_raw(type="IGS", state="A", limit=20, cache=None, no_cache=False):
    """one register segment's member list (a local scan family face — the upstream has no
    query surface, the whole segment answers in one shot)."""
    t = str(type or "").strip().upper()
    if t not in _TYPES:
        raise SdkError("usage_error", provider="tr_kap",
                       detail=("--type is the register's own segment code: " + ", ".join(_TYPES) +
                               " (semantics undocumented upstream; IGS/A measured 756 rows)"))
    s = str(state or "").strip().upper()
    if s not in _STATES:
        raise SdkError("usage_error", provider="tr_kap",
                       detail="--state is A (the live register), P or W (W answers the register's placeholder row — dropped, counted in census)")
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    if not 1 <= limit <= 100:
        raise SdkError("usage_error", provider="tr_kap",
                       detail="limit must be 1-100 (local slice wall)")
    wall = limit
    res = call_provider(provider, "items", {"type": t, "state": s},
                        cache=cache, no_cache=no_cache)
    rows, placeholders = rows_from_items(res["data"])
    total_matched = len(rows)
    return {
        "type": t, "state": s,
        "rows": rows[:wall], "total_matched": total_matched,
        "census": {"upstream_rows": total_matched + placeholders,
                   "placeholder_rows": placeholders},
        "limit_applied": min(wall, total_matched),
        "params": {"type": t, "state": s}, "_meta": res,
    }


def disclosures_raw(from_date, to_date=None, limit=20, cache=None, no_cache=False):
    """the disclosure stream for a date window (newest-first verbatim). --to defaults to
    --from (a single day). The response caps at 2,000 rows upstream — likely_truncated
    flags it; narrow the window, the upstream echoes no total (none is fabricated)."""
    today = _date.today().isoformat()
    if to_date is None:
        to_date = from_date
    for name, v in (("--from", from_date), ("--to", to_date)):
        if not _DATE_RE.match(str(v or "")):
            raise SdkError("usage_error", provider="tr_kap",
                           detail=f"{name} must be YYYY-MM-DD (zero-padded), e.g. 2026-11-10")
    try:
        span = (_date.fromisoformat(str(to_date)) - _date.fromisoformat(str(from_date))).days
    except ValueError:
        raise SdkError("usage_error", provider="tr_kap",
                       detail="--from/--to must be real calendar dates")
    if span < 0:
        raise SdkError("usage_error", provider="tr_kap",
                       detail="--from must be on or before --to")
    if str(to_date) > today:
        raise SdkError("usage_error", provider="tr_kap",
                       detail=f"--to {to_date} is in the future — the stream has not reached that day")
    if span + 1 > _MAX_WINDOW:
        raise SdkError("usage_error", provider="tr_kap",
                       detail=(f"the window {from_date}..{to_date} is {span + 1} days — cap it at "
                               f"{_MAX_WINDOW} days (the response caps at {_CAP} rows upstream; "
                               "narrow the window for full coverage)"))
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    if not 1 <= limit <= 100:
        raise SdkError("usage_error", provider="tr_kap",
                       detail="limit must be 1-100 (local slice wall)")
    wall = limit
    res = call_provider(provider, "disclosures",
                        {"fromDate": str(from_date), "toDate": str(to_date)},
                        cache=cache, no_cache=no_cache)
    rows = [r for r in res["data"] if isinstance(r, dict)] if isinstance(res["data"], list) else []
    total = len(rows)
    return {
        "from": str(from_date), "to": str(to_date),
        "rows": rows[:wall], "total_matched": total,
        "likely_truncated": total >= _CAP,
        "census": {"upstream_rows": total, "response_cap": _CAP,
                   "truncated_flag_rule": f"rows == {total} >= {_CAP} — narrow the window"},
        "limit_applied": min(wall, total),
        "params": {"fromDate": str(from_date), "toDate": str(to_date)}, "_meta": res,
    }
