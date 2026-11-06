"""ru_cbr_warning — Bank of Russia warning list of entities with signs of illegal financial
activity (www.cbr.ru UniDbQuery DownloadExcel export 123126; the legal domain's first RU face;
research volume ru-cbr-registers-recipe, 册 235; face admitted in 0.3.37, probed first-hand
2026-11-04 tmp/probe-ru-cbr-0337/ with the SDK's own polite UA, direct).

One face — warning_list. The register ships as ONE xlsx (~3.1MB) through the UniDbQuery export
endpoint: GET /Queries/UniDbQuery/DownloadExcel/123126?FromDate=MM/DD/YYYY&ToDate=MM/DD/YYYY
&posted=False (AMERICAN date order, pinned at research time; FromDate=01/01/2014 is a harmless
overshoot — the register's own history starts 2021-02-01; ToDate = today UTC, so the cache key
rolls daily with the register's nightly rebuild). Parsed with the transport's accept='bytes'
channel (extension 9 — the body arrives as a lossless latin-1 string; this module re-encodes
.encode('latin-1') and unzips with stdlib zipfile; the sheet uses INLINE strings, no
sharedStrings.xml) — 27,635 rows × 12 columns (2026-11-04 pin).

Columns (the register's own Russian headers → snake keys): Дата → date (Excel serial → ISO
date); Название → name; ИНН → inn (present on only 3,094 of 27,635 rows — internet projects
ship none → null); Адрес → address (for internet-project rows this column carries the URL
list: t.me/… bots, *.workers.dev fronts); Сайт → site; Признаки, установленные Банком России →
violations (verbatim Russian, comma/newline-joined when multiple); Регионы → regions ("0" on
internet-project rows, kept verbatim); Согласно ЕГРЮЛ/ЕГРИП, деятельность прекращена →
egrul_terminated ("0"/"1" verbatim); Дополнительно → additional (upstream numeric, semantics
unpublished — kept verbatim, NOT interpreted); Внутренний идентификатор записи → record_id
(empty on sampled rows → null); Дата последнего обновления данных → updated (Excel serial
float → ISO datetime); Тип записи → record_type (six verbatim kinds: Интернет-проект 22,798 /
Юридическое лицо 3,030 / Точка присутствия 924 / Компания 818 / Индивидуальный
предприниматель 64 / Прочее 1).

The violations column carries SIX canonical kinds (verbatim Russian, pinned 2026-11-04):
финансовой пирамиды 14,054 · нелегального профессионального участника рынка ценных бумаг 7,356
· нелегального кредитора 2,567 · незаконного привлечения инвестиций 116 · нелегального
оператора инвестиционной платформы 16 · нелегальной деятельности на страховом рынке 57 (rows
can carry several — two rows even embed a raw \r\n inside the cell, kept verbatim; the
violation filter splits on commas/newlines and matches whitespace-collapsed).

**PII stance (the co_sic_sanctions / ie_revenue precedent)**: the register is published BY
STATUTE — the Bank of Russia's consumer-protection warning list (FZ 115 framework); names,
addresses and sites are republished verbatim from a public regulator register, not leaked
personal data.

Channel: honest agentdata UA, direct, zero extra headers → 200 with a clean PK\x03\x04 ZIP
magic (t2, 2026-11-04; the %2F-encoded query the transport emits passes untouched). Rate:
polite 0.2 rps / burst 1 (heavy single-file host; the host-layer bucket is shared with company
ru_cbr_credit on www.cbr.ru). TTL: 24h (register posture).
"""
import datetime
import html
import io
import re
import zipfile

from ..errors import SdkError

provider = {
    "id": "ru_cbr_warning",
    "baseUrl": "https://www.cbr.ru",
    "rate": {"rps": 0.2, "burst": 1},
    "ops": {
        "list": {"path": "/Queries/UniDbQuery/DownloadExcel/123126", "accept": "bytes",
                 "timeout": 120.0},
    },
    "ttl": {"list": 24 * 3600},
}

# the register's canonical violation kinds -> the face's English closed set (rows keep the
# verbatim Russian cell; the filter splits the cell on commas/newlines and matches
# whitespace-collapsed against these)
_VIOLATION_MAP = {
    "pyramid": 'Признаки "финансовой пирамиды"',
    "illegal_securities_professional": "Признаки нелегального профессионального участника рынка ценных бумаг",
    "illegal_lender": "Признаки нелегального кредитора",
    "illegal_investment_solicitation": "Признаки незаконного привлечения инвестиций",
    "illegal_platform_operator": "Признаки нелегального оператора инвестиционной платформы",
    "illegal_insurance_activity": "Признаки нелегальной деятельности на страховом рынке",
}

# the register's record-type vocabulary -> the face's English closed set (rows keep verbatim)
_RECORD_TYPE_MAP = {
    "internet_project": "Интернет-проект",
    "legal_entity": "Юридическое лицо",
    "individual_entrepreneur": "Индивидуальный предприниматель",
    "presence_point": "Точка присутствия",
    "company": "Компания",
    "other": "Прочее",
}

_EPOCH = datetime.datetime(1899, 12, 30)   # Excel serial epoch (the 1900 leap-year bug included)


def _serial_to_date(v):
    try:
        return (_EPOCH + datetime.timedelta(days=float(v))).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _serial_to_datetime(v):
    try:
        d = _EPOCH + datetime.timedelta(days=float(v))
        return d.strftime("%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return None


def _cells(row_xml):
    """One <x:row> -> {col letter: value} (inline strings unescaped; numeric cells verbatim)."""
    out = {}
    for cm in re.finditer(r'<x:c r="([A-Z]+)\d+"[^>]*>(.*?)</x:c>', row_xml, re.S):
        col, inner = cm.group(1), cm.group(2)
        tm = re.search(r"<x:t[^>]*>(.*?)</x:t>", inner, re.S)
        vm = re.search(r"<x:v>(.*?)</x:v>", inner, re.S)
        raw = tm.group(1) if tm else (vm.group(1) if vm else None)
        out[col] = html.unescape(raw).strip() if raw is not None else None
    return out


def rows_from_upstream(text):
    """accept='bytes' payload (latin-1 string) -> warning rows (pure function; re-encodes to the
    original bytes, unzips sheet1, maps the 12 columns)."""
    z = zipfile.ZipFile(io.BytesIO(text.encode("latin-1")))
    sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")
    xrows = re.findall(r"<x:row .*?</x:row>", sheet, re.S)
    rows = []
    for xr in xrows[1:]:   # row 1 = the Russian header row itself
        c = _cells(xr)
        if not c:
            continue
        rows.append({
            "date": _serial_to_date(c.get("A")),
            "name": c.get("B") or None,
            "inn": c.get("C") or None,
            "address": c.get("D") or None,
            "site": c.get("E") or None,
            "violations": c.get("F") or None,
            "regions": c.get("G") or None,
            "egrul_terminated": c.get("H") or None,
            "additional": c.get("I") or None,
            "record_id": c.get("J") or None,
            "updated": _serial_to_datetime(c.get("K")),
            "record_type": c.get("L") or None,
        })
    return rows


def _violation_parts(cell):
    """The violations cell -> whitespace-collapsed canonical parts (commas/newlines split)."""
    if not cell:
        return []
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"[,\r\n]+", cell) if p.strip()]


def warning_list_raw(name=None, *, inn=None, site=None, violation=None, type=None,
                     limit=20, cache=None, no_cache=False):
    """Full-register scan (pulls the whole ~27,600-row xlsx in ONE GET, caches 24h, scans
    locally) -> {rows, total_matched, scanned_rows, census, limit_applied, params, _meta}.

    name = contains (case-insensitive) over name; inn = exact ИНН key; site = contains over
    site AND address (internet-project rows carry their t.me/*/workers.dev fronts in the
    address column); violation = pyramid|illegal_securities_professional|illegal_lender|
    illegal_investment_solicitation|illegal_platform_operator|illegal_insurance_activity
    (matched per part); type = internet_project|legal_entity|individual_entrepreneur|
    presence_point|company|other. No filter -> enumerate from the register's head."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="ru_cbr_warning",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    if violation not in (None, "") and violation not in _VIOLATION_MAP:
        raise SdkError("usage_error", provider="ru_cbr_warning",
                       detail=f"violation must be one of {'|'.join(_VIOLATION_MAP)}, got {violation!r}")
    if type not in (None, "") and type not in _RECORD_TYPE_MAP:
        raise SdkError("usage_error", provider="ru_cbr_warning",
                       detail=f"type must be one of {'|'.join(_RECORD_TYPE_MAP)}, got {type!r}")
    inneedle = str(inn).strip() if inn not in (None, "") else None
    if inneedle is not None and not inneedle.isdigit():
        raise SdkError("usage_error", provider="ru_cbr_warning",
                       detail=f"inn must be the digit-string ИНН key, got {inn!r}")
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%m/%d/%Y")
    r = call_provider(provider, "list", {"FromDate": "01/01/2014", "ToDate": today,
                                         "posted": "False"}, cache=cache, no_cache=no_cache)
    rows = rows_from_upstream(r["data"])
    needle = str(name or "").strip().lower() or None
    site_needle = str(site or "").strip().lower() or None
    want_v = _VIOLATION_MAP.get(violation) if violation else None
    want_t = _RECORD_TYPE_MAP.get(type) if type else None
    hits = []
    for x in rows:
        if inneedle and x.get("inn") != inneedle:
            continue
        if want_t and x.get("record_type") != want_t:
            continue
        if want_v and want_v not in _violation_parts(x.get("violations")):
            continue
        if needle and needle not in str(x.get("name") or "").lower():
            continue
        if site_needle and site_needle not in (str(x.get("site") or "") + " " +
                                               str(x.get("address") or "")).lower():
            continue
        hits.append(x)
    by_v, by_t = {}, {}
    dates = set()
    with_inn = 0
    for x in rows:
        for p in _violation_parts(x.get("violations")):
            by_v[p] = by_v.get(p, 0) + 1
        by_t[x.get("record_type")] = by_t.get(x.get("record_type"), 0) + 1
        if x.get("date"):
            dates.add(x["date"])
        if x.get("inn"):
            with_inn += 1
    dates = sorted(dates)
    census = {
        "total": len(rows),
        "by_violation": by_v,
        "by_record_type": by_t,
        "date_min": dates[0] if dates else None,
        "date_max": dates[-1] if dates else None,
        "with_inn": with_inn,
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"name": name, "inn": inneedle, "site": site,
                       "violation": violation or None, "type": type or None},
            "_meta": r}
