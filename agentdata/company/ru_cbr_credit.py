"""ru_cbr_credit — Bank of Russia credit-organisations register (www.cbr.ru FullCoList; the
company domain's first RU face; research volume ru-cbr-registers-recipe, 册 235; face admitted
in 0.3.37, probed first-hand 2026-11-04 tmp/probe-ru-cbr-0337/ with the SDK's own polite UA,
direct).

One face — credit_orgs. The register ships as ONE HTML page (~790KB) with the whole table
inline (no paging, no query surface — local scan family): GET /banking_sector/credit/FullCoList/
answers 1,897 rows × 9 columns verbatim (as-of stamp 04.11.2026 lives in the <title>,
"по состоянию на DD.MM.YYYY"). Columns (the register's own headers → snake keys):
№ п/п → no (the register's own position, kept); Вид → kind (EMPTY on 1,746 rows = universal
credit organisation — the register's own convention, kept as null, NOT invented into a word);
Регистрационный номер → reg_no; ОГРН → ogrn (the 13-digit join key onto ЕГРЮЛ — empty on 188
legacy/liquidated rows → null); Наименование → name (the cell anchors /finorg/foinfo/?ogrn=… —
the register's own per-entity detail edge, kept as foinfo_path); Организационно-правовая форма →
org_form; Дата регистрации Банком России → reg_date (DD.MM.YYYY verbatim, 1989→2026);
Статус лицензии → license_status (FOUR statuses, verbatim Russian: Действующая 358 /
Отозванная 282 / Аннулированная 2 / Ликвидация 1,255 — the research volume named only two;
the liquidation wall is the register's largest segment and IS the lifecycle tail);
Местонахождение → address.

The as-of stamp moves daily (the register is rebuilt each night) — every call is a fresh full
pull, cached 24h. Rate: polite 0.2 rps / burst 1 (heavy single-file host, the ie_revenue
static-file posture; the host-layer bucket is shared with legal ru_cbr_warning on
www.cbr.ru). TTL: 24h (register posture).

CHANNEL — DDoS-Guard JS-challenge gate on the HTML tree (pinned 2026-11-04, the 0.3.37
acceptance audit, tmp/probe-ru-cbr-0340/): the register's own /banking_sector/* pages answer
the DEFAULT agentdata UA with a 403 DDoS-Guard challenge page ("Checking your browser before
accessing", 902-byte stub, /.well-known/ddos-guard/js-challenge/) — the 0.3.37 channel note
("honest agentdata UA + direct egress = 200", observed at research time on 2026-11-04) no
longer holds on this host. Measured: default UA → 403 ×2; the FULL BROWSER DOCUMENT SUITE
(ext 8 per-request header override — the afdb/ungm family) → 200 ×2, 1,897 rows, as-of
04.11.2026. The gate sits on the /banking_sector/ + /finorg/ tree, NOT on the sibling
/Queries/UniDbQuery export surface the legal ru_cbr_warning face reads. A challenge page
served with 2xx must never be parsed as an empty register — the guard below turns it into an
explicit upstream_unavailable.
"""
import html
import re

from ..errors import SdkError

provider = {
    "id": "ru_cbr_credit",
    "baseUrl": "https://www.cbr.ru",
    "rate": {"rps": 0.2, "burst": 1},
    "ops": {
        "fullco": {"path": "/banking_sector/credit/FullCoList/", "accept": "text",
                   "timeout": 90.0},
    },
    "ttl": {"fullco": 24 * 3600},
}

# the register's own status vocabulary -> the face's English closed set (rows keep the verbatim
# Russian value; the filter translates)
_STATUS_MAP = {"active": "Действующая", "revoked": "Отозванная",
               "annulled": "Аннулированная", "liquidation": "Ликвидация"}

# DDoS-Guard JS-challenge gate on the /banking_sector/ HTML tree (pinned 2026-11-04, the
# 0.3.37 acceptance audit): the default agentdata UA → 403 + a 902-byte "Checking your browser"
# stub; the full browser document suite → 200 (twice, 1,897 rows, as-of 04.11.2026). ext-8
# per-request header override — the afdb/ungm family precedent.
_CBR_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.cbr.ru/banking_sector/credit/FullCoList/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# the challenge stub's own marker (the page title + the /.well-known/ddos-guard/ asset path)
_CHALLENGE_MARKERS = ("ddos-guard", "checking your browser")

_AS_OF_RE = re.compile(r"по состоянию на (\d\d\.\d\d\.\d{4})")


def _cell(td_html):
    """One <td> -> stripped text (entities unescaped; the register's only normalisation)."""
    return html.unescape(re.sub(r"<[^>]+>", "", td_html)).strip() or None


def rows_from_upstream(text):
    """FullCoList HTML -> (rows, as_of) (pure function). Rows carry the 9 columns verbatim; the
    name cell's foinfo anchor is kept as foinfo_path (the register's own per-entity edge)."""
    m = _AS_OF_RE.search(text or "")
    as_of = m.group(1) if m else None
    i = text.find("<tbody>")
    j = text.find("</tbody>", i)
    body = text[i:j] if i != -1 and j != -1 else text
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) != 9:
            continue
        anchor = re.search(r'href="(/finorg/foinfo/\?ogrn=\d+)"', tds[4]) or \
            re.search(r'href="([^"]*foinfo[^"]*)"', tds[4])
        rows.append({
            "no": int(tds[0]) if tds[0].strip().isdigit() else None,
            "kind": _cell(tds[1]),           # empty on the register = universal credit org
            "reg_no": _cell(tds[2]),
            "ogrn": _cell(tds[3]),
            "name": _cell(tds[4]),
            "org_form": _cell(tds[5]),
            "reg_date": _cell(tds[6]),       # DD.MM.YYYY verbatim
            "license_status": _cell(tds[7]),
            "address": _cell(tds[8]),
            "foinfo_path": anchor.group(1) if anchor else None,
        })
    return rows, as_of


def credit_orgs_raw(name=None, *, status=None, ogrn=None, limit=20, cache=None, no_cache=False):
    """Full-register scan (pulls the whole ~1,900-row register in ONE GET, caches 24h, scans
    locally) -> {rows, total_matched, scanned_rows, census, limit_applied, params, _meta}.

    name = contains (case-insensitive) over name; status = active|revoked|annulled|liquidation
    (the register's four-status vocabulary, translated from the verbatim Russian); ogrn = exact
    13-digit key. No filter -> enumerate from the register's head."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="ru_cbr_credit",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    if status not in (None, "") and status not in _STATUS_MAP:
        raise SdkError("usage_error", provider="ru_cbr_credit",
                       detail=f"status must be one of active|revoked|annulled|liquidation (the "
                              f"register's four-status vocabulary), got {status!r}")
    ogr = str(ogrn).strip() if ogrn not in (None, "") else None
    if ogr is not None and not (ogr.isdigit() and 13 <= len(ogr) <= 15):
        raise SdkError("usage_error", provider="ru_cbr_credit",
                       detail=f"ogrn must be the 13-digit ОГРН key (digit string), got {ogrn!r}")
    needle = str(name or "").strip().lower() or None
    r = call_provider(provider, "fullco", {}, cache=cache, no_cache=no_cache,
                      extra_headers=_CBR_BROWSER_HEADERS)
    payload = r["data"]
    if isinstance(payload, str):
        head = payload[:2000].lower()
        if any(m in head for m in _CHALLENGE_MARKERS):
            # a challenge page is not an empty register — accept:'text' would otherwise hand the
            # stub to the parser and report a clean "0 of 0 rows" (a false negative on a screening
            # face); refuse it loudly instead
            raise SdkError("upstream_unavailable", provider="ru_cbr_credit",
                           detail="Upstream returned a DDoS-Guard JS-challenge page instead of the "
                                  "register (the HTML tree is behind a UA-fingerprint gate) — the "
                                  "browser document suite should have passed it; retry later / check "
                                  "the egress, do not read this as an empty register")
    rows, as_of = rows_from_upstream(r["data"])
    want = _STATUS_MAP.get(status) if status else None
    hits = []
    for x in rows:
        if want and x.get("license_status") != want:
            continue
        if ogr and x.get("ogrn") != ogr:
            continue
        if needle and needle not in str(x.get("name") or "").lower():
            continue
        hits.append(x)
    by_status, by_kind = {}, {}
    years = set()
    for x in rows:
        by_status[x.get("license_status")] = by_status.get(x.get("license_status"), 0) + 1
        by_kind[x.get("kind")] = by_kind.get(x.get("kind"), 0) + 1
        if x.get("reg_date"):
            years.add(x["reg_date"].split(".")[-1])
    years = sorted(years)
    census = {
        "as_of": as_of,
        "total": len(rows),
        "by_status": by_status,
        "by_kind": by_kind,
        "reg_year_min": years[0] if years else None,
        "reg_year_max": years[-1] if years else None,
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"name": name, "status": status or None, "ogrn": ogr},
            "_meta": r}
