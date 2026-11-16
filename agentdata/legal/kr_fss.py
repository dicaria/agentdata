"""kr_fss — Korea Financial Supervisory Service 제재 정보 (sanctions disclosure,
www.fss.or.kr /fss/job/openInfo/list.do?menuNo=200476, keyless SSR).

KR legal face (0.3.62; admitted from the research booklet 册 133, 7.5 P0 after
the 2026-11-03 翻案; re-probed live 2026-11-16 tmp/probe-e4/ with the SDK's own
polite UA — the excelDown endpoint answers the urlencoded POST with a clean
PK zip through the transport's bytes channel; first POST × bytes combination
in the tree).

The register's ONE-SHOT channel (the default list window shows only 303 rows —
the wide window is 5,785+; the excel export IS the corpus): POST
/fss/job/openInfo/excelDown.uxls with menuNo=200476&sdate=2000-01-01&edate=
{today}&viewType=EXCEL → one ~270KB xlsx, ALL rows 2008-10-02→today
(5,804 data rows on 2026-11-16; 5,786 on the 2026-11-03 pin — the register
grows at the head). The sheet uses INLINE strings, no sharedStrings refs.

LIVE LAWS (measured 2026-11-16, tmp/probe-e4/):
  - HEADER MISALIGNMENT: the header row reads 제재조치일 | 제재조치요구일 |
    제재조치내용_제재대상_기관/임원/직원 | 관련부서 but the DATA rows carry
    A = the sanctioned/inspected entity name, B = the date (yyyymmdd),
    C/D/E = the sanction content split institution/executive/employee,
    F = the FSS department. The face maps by the MEASURED data shape (columns
    letter-keyed, never order-keyed — empty cells drop out of the XML).
  - 1,245 of 5,804 rows carry NO inline C/D/E content: recent rows' content
    is a PDF ATTACHMENT on the view.do detail page
    (/fss.hpdownload?path=/dtm/opn/&file={encoded-name}, keyless, measured
    146,771B %PDF — the 2026-11-03 翻案; pdfViewr returns a 477B Docuzen
    shell, that is not a failure). The face keeps these rows with null
    content columns and counts them in the census — the PDF walk is a batch
    concern, not a query-face round trip.
  - the composite detail key is examMgmtNo+emOpenSeq (the view.do params);
    the xlsx does NOT carry them — the excel rows are keyed (name, date).

Politeness: 0.2/1, concurrency 1 (a heavy single-file host), TTL 24h
(register posture; the cache key rolls daily with edate=today, the ru_cbr
warning-list precedent).
"""
import datetime
import html as _html
import io
import re
import zipfile

from ..errors import SdkError

provider = {
    "id": "kr_fss",
    "baseUrl": "https://www.fss.or.kr",
    "rate": {"rps": 0.2, "burst": 1},
    "concurrency": 1,
    "ops": {
        "excel": {"path": "/fss/job/openInfo/excelDown.uxls", "method": "POST",
                  "urlencoded": True, "idempotent": True, "accept": "bytes",
                  "timeout": 120.0},
    },
    "ttl": {"excel": 24 * 3600},
}

_HEADERS = {"Accept": "*/*",
            "Referer": "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476"}

_LAYERS = {"institution": "C", "executive": "D", "employee": "E"}


def _cells(row_xml):
    """One <row> → {col letter: value} (inline strings unescaped, letter-keyed —
    the empty cells drop out of the XML, order-keyed parsing misaligns)."""
    out = {}
    for m in re.finditer(r'<c r="([A-Z]+)\d+"[^>]*>(.*?)</c>', row_xml, re.S):
        tm = re.search(r"<t[^>]*>(.*?)</t>", m.group(2), re.S)
        vm = re.search(r"<v>(.*?)</v>", m.group(2), re.S)
        raw = tm.group(1) if tm else (vm.group(1) if vm else None)
        out[m.group(1)] = _html.unescape(raw).strip() if raw is not None else ""
    return out


def rows_from_upstream(text):
    """accept='bytes' payload (latin-1 string) → sanction rows (pure function;
    re-encodes to the original bytes, unzips sheet1, maps the six columns by
    the MEASURED data shape A/B/C/D/E/F)."""
    z = zipfile.ZipFile(io.BytesIO(text.encode("latin-1")))
    sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")
    rows = []
    for xr in re.findall(r"<row[^>]*>.*?</row>", sheet, re.S)[1:]:
        c = _cells(xr)
        if not c:
            continue
        d = c.get("B") or ""
        rows.append({
            "org": c.get("A") or None,
            "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if re.fullmatch(r"\d{8}", d) else (d or None),
            "institution_sanction": c.get("C") or None,
            "executive_sanction": c.get("D") or None,
            "employee_sanction": c.get("E") or None,
            "department": c.get("F") or None,
        })
    return rows


def sanctions_raw(org=None, *, date_from=None, date_to=None, layer=None,
                  limit=20, cache=None, no_cache=False):
    """→ {rows[], total_matched, scanned_rows, census, limit_applied, params, _meta}.

    org = contains (case-insensitive) over the entity name; date_from/date_to =
    ISO yyyy-mm-dd bounds over the sanction date; layer = institution|
    executive|employee (rows whose sanction-content column for that layer is
    non-empty). No filter → enumerate from the register's head (newest first —
    the sheet runs newest-first)."""
    from ..transport import call_provider

    if layer not in (None, "") and layer not in _LAYERS:
        raise SdkError("usage_error", provider="kr_fss",
                       detail=f"layer must be one of {sorted(_LAYERS)}, got {layer!r}")
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="kr_fss",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    for label, v in (("date_from", date_from), ("date_to", date_to)):
        if v not in (None, "") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)):
            raise SdkError("usage_error", provider="kr_fss",
                           detail=f"{label} must be ISO yyyy-mm-dd, got {v!r}")
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    r = call_provider(provider, "excel",
                      {"menuNo": "200476", "sdate": "2000-01-01", "edate": today,
                       "viewType": "EXCEL"},
                      cache=cache, no_cache=no_cache, extra_headers=_HEADERS)
    rows = rows_from_upstream(r["data"])
    needle = str(org or "").strip().lower() or None
    want_layer = _LAYERS.get(layer) if layer else None
    hits = []
    for x in rows:
        if needle and needle not in str(x.get("org") or "").lower():
            continue
        if date_from and (x.get("date") or "") < date_from:
            continue
        if date_to and (x.get("date") or "") > date_to:
            continue
        if want_layer and not x.get(f"{layer}_sanction"):
            continue
        hits.append(x)
    by_layer = {"institution": 0, "executive": 0, "employee": 0}
    by_dept = {}
    no_content = 0
    dates = []
    for x in rows:
        for lay in by_layer:
            if x.get(f"{lay}_sanction"):
                by_layer[lay] += 1
        if x.get("department"):
            by_dept[x["department"]] = by_dept.get(x["department"], 0) + 1
        if not (x.get("institution_sanction") or x.get("executive_sanction")
                or x.get("employee_sanction")):
            no_content += 1
        if x.get("date"):
            dates.append(x["date"])
    dates.sort()
    census = {
        "total": len(rows),
        "by_layer": by_layer,
        "rows_without_inline_content": no_content,
        "top_departments": sorted(by_dept.items(), key=lambda kv: -kv[1])[:5],
        "date_min": dates[0] if dates else None,
        "date_max": dates[-1] if dates else None,
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"org": needle, "date_from": date_from or None,
                       "date_to": date_to or None, "layer": layer or None},
            "_meta": r}
