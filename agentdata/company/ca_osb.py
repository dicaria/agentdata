"""ca_osb — Office of the Superintendent of Bankruptcy (Canada) CCAA records,
open.canada.ca CKAN package 92697343-d36d-4427-a1a8-ebac6b2725cc (research volume
ca-osb-insolvency, 册 227; face admitted in 0.3.43, probed first-hand 2026-11-05
tmp/probe-ca-osb-0343/ — the catalog GET and the 285KB XLSX both 200 + PK magic,
honest agentdata UA, keyless, direct).

The CCAA Records List (Companies' Creditors Arrangement Act — the federal
large-company restructuring proceeding) ships as ELEVEN keyless year-named XLSX
resources behind one CKAN package. Each year's file is a CUMULATIVE snapshot (the
2026 Q2 file = 730 proceedings spanning 2009→2026), so the face resolves the
LATEST resource at call time (the URL rolls quarterly — never hard-coded) and
scans it locally. The upstream has NO query surface: --name / --monitor /
--province / --osb are local filters over the fetched workbook.

Postures this face keeps:
  * the Federal Insolvency Records Search (ised-isde.canada.ca/cc/sra) is a paid
    wall (account + ~$8/query, 1978→today estate library) — NOT here, per the
    keyless-only ruling; this face is the free roster only;
  * column mapping is by HEADER NAME anchors, never positions — the 2016-era
    files carry 17 columns ('Monitor's Representation', no employees/powers/
    amounts) while the current files carry 21: both parse, and a drifted header
    is upstream_unavailable, never a guessed column;
  * dates ride THREE forms inside one file (Excel serial / ISO strings /
    dd/mm/yyyy in the oldest files) — all decoded to ISO; a 5-digit-year typo
    ('20250-05-28') or any unverifiable form → null, never a guess;
  * the province rides the OSB File Number suffix ('0000875-2026-AB') — the
    authoritative subnational code, not a court-string guess; two source rows
    carry typo'd year segments ('-2201-', '-7201-') and stay VERBATIM (the
    suffix still resolves, the census counts the dirty rows);
  * amounts are strings with thousands separators and occasional Excel float
    tails ('116386808.81999999') — parsed as float verbatim, never re-rounded;
  * the employees column doubles as a sealing-order marker ('*Sealing Order',
    '*requested sealing order…' = court-sealed cases): non-numeric values are
    null employees and the row carries sealed_order=true (publicly listed as
    sealed — the census counts them);
  * legacy rows (2009-2013 era) were appended from an older layout: their
    'Monitor Additional Powers' cell holds a bare date — kept VERBATIM in that
    column, never reattributed, the census counts the rows;
  * 'Company Name' embeds a '/'-joined alias string on a handful of rows — kept
    verbatim (a slash INSIDE a legal name is real: 'Sunrise/Saskatoon…'), the
    dedicated other-names column is the alias field, the census counts the rides;
  * monitor representatives / emails / phones are practicing-professional public
    register information — recorded exactly as published.

Channel: honest agentdata UA, direct, zero extra headers → 200 on the catalog and
the file (t1, 2026-11-05). Rate: polite 0.5 rps / burst 2 — one provider bucket
over TWO hosts (the catalog on open.canada.ca, the file on ised-isde.canada.ca —
the absolute resource URL rides transport extension 10; the ic.gc.ca URLs in the
package are the 2016-2021 archives this face never fetches). TTL: 24h on the
catalog and on the file (quarterly rollover = a new cache key, the resource URL
is the key).
"""
import datetime as _dt
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET

from ..errors import SdkError

provider = {
    "id": "ca_osb",
    "baseUrl": "https://open.canada.ca",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "catalog": {"path": "/data/api/action/package_show"},  # params: id (the fixed package uuid)
        # transport extension 10 carries the absolute resource URL raw (no quoting, no base
        # prefix) — the catalog hands back full URLs on a different host that roll quarterly
        "file": {"path": "{file_url}", "accept": "bytes", "timeout": 120.0},
    },
    "ttl": {"catalog": 24 * 3600, "file": 24 * 3600},
}

PACKAGE_ID = "92697343-d36d-4427-a1a8-ebac6b2725cc"

# CA subnational codes the OSB File Number suffix can carry (the territories ride the same field)
PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

_PLACEHOLDERS = {"", "n/a", "na", "n.a.", "-", "–", "—", "none"}

# field -> (header spellings across file eras, required). The 2016-era files say
# "Monitor's Representation", the current files "Monitor's Representative" — one field.
_COLUMNS = [
    ("court_file_number", ("Court File Number",), True),
    ("court", ("Court & Judicial District",), True),
    ("osb_file_number", ("OSB File Number",), True),
    ("initial_order_raw", ("Date of Initial Order",), True),
    ("proceedings_web_page", ("Monitor's Web Page for the Proceedings",), False),
    ("company_name", ("Company Name",), True),
    ("other_names", ("Other names under which the company carries on business",), False),
    ("head_office", ("Head Office",), False),
    ("telephone", ("Telephone",), False),
    ("website", ("Website",), False),
    ("monitor", ("Court-Appointed Monitor",), False),
    ("monitor_website", ("Monitor's Website",), False),
    ("monitor_representative", ("Monitor's Representative", "Monitor's Representation"), False),
    ("monitor_address", ("Address",), False),
    ("monitor_telephone", ("Monitor's Telephone",), False),
    ("monitor_email", ("Email",), False),
    ("employees_raw", ("No of Canadian Employees",), False),
    ("discharge_raw", ("Date of Discharge Order",), False),
    ("monitor_additional_powers", ("Monitor Additional Powers",), False),
    ("assets_raw", ("Amount of Assets at Initial Filing",), False),
    ("liabilities_raw", ("Amount of Liabilities at Initial Filing",), False),
]

_EPOCH = _dt.date(1899, 12, 30)


def _text(v):
    """NFKC + trim; the register's own placeholder spellings -> None."""
    if v is None:
        return None
    s = unicodedata.normalize("NFKC", str(v)).strip()
    return None if s.lower() in _PLACEHOLDERS else s


def _fold(v):
    return unicodedata.normalize("NFKC", str(v or "")).casefold()


def _date_any(v):
    """serial (2007-2036 window) / ISO string / dd/mm/yyyy -> ISO; unverifiable -> None."""
    if v is None:
        return None
    s = unicodedata.normalize("NFKC", str(v)).strip()
    if not s:
        return None
    if s.isdigit():
        n = int(s)
        if 39000 <= n <= 50000:  # 2006-11 .. 2036-11 — outside = not a plausible serial
            return (_EPOCH + _dt.timedelta(days=n)).isoformat()
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):  # the '20250-05-28' 5-digit-year typo fails here
        y, m, d = int(s[:4]), int(s[5:7]), int(s[8:10])
        try:
            return _dt.date(y, m, d).isoformat()
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)  # the 2016-era files are d/m/yyyy strings
    if m:
        try:
            return _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def _amount(v):
    """'35,183,216.00' / '116386808.81999999' -> float verbatim; anything else -> None."""
    if v is None:
        return None
    s = unicodedata.normalize("NFKC", str(v)).strip().replace(",", "").replace("$", "").replace(" ", "")
    if not s or not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    return float(s)


def _employees(v):
    """digits -> int; the '*Sealing Order…' markers -> (None, sealed); else (None, False)."""
    s = unicodedata.normalize("NFKC", str(v or "")).strip()
    if not s:
        return None, False
    if re.fullmatch(r"\d{1,7}(,\d{3})*", s):
        return int(s.replace(",", "")), False
    if "ealing" in s.lower():  # '*Sealing Order' / '*requested sealing order…' — court-sealed cases
        return None, True
    return None, False


def _col_index(ref):
    """'C3' -> 2 (0-based column position from the spreadsheet cell reference)."""
    letters = re.match(r"([A-Z]+)", ref or "").group(1)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def xlsx_first_sheet(payload):
    """bytes payload (latin-1 lossless string from the transport) -> first sheet as row lists.
    sharedStrings AND inline strings both resolve; cells land at their column position."""
    if isinstance(payload, str):
        payload = payload.encode("latin-1", "replace")
    import io as _io
    try:
        z = zipfile.ZipFile(_io.BytesIO(payload))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheet = wb.find(NS + "sheets")[0]  # single-sheet workbooks — take the first, names drift
        rid = sheet.get(RNS + "id")
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = [r.get("Target") for r in rels if r.get("Id") == rid][0]
        sst = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ["".join(t.text or "" for t in si.iter(NS + "t"))
                   for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        ws = ET.fromstring(z.read("xl/" + target.replace("xl/", "")))
        rows = []
        for row in ws.iter(NS + "row"):
            cells = []
            for c in row.iter(NS + "c"):
                v = c.find(NS + "v")
                if v is None:
                    t = c.find(NS + "is")
                    val = "".join(x.text or "" for x in t.iter(NS + "t")) if t is not None else ""
                else:
                    val = sst[int(v.text)] if c.get("t") == "s" else (v.text or "")
                ci = _col_index(c.get("r"))
                while len(cells) <= ci:
                    cells.append("")
                cells[ci] = val
            rows.append(cells)
        return rows
    except SdkError:
        raise
    except Exception as e:  # a corrupt/non-zip body (an HTML error page decoded as latin-1)
        raise SdkError("upstream_unavailable", provider="ca_osb",
                       detail=f"the XLSX body did not parse ({e.__class__.__name__}) — not a zip/PK payload")


def _norm_header(v):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(v or ""))).strip().casefold()


def _find_header(rows):
    """the REAL header = the row whose cells carry every required anchor (the group-title row
    above it says only File Information / Debtor Company Information / Monitor Information)."""
    for i, row in enumerate(rows[:6]):
        cells = {_norm_header(x) for x in (row or [])}
        if all(any(_norm_header(a) in cells for a in spellings)
               for _f, spellings, req in _COLUMNS if req):
            return i
    return None


def _map_columns(header_row):
    cols = {}
    for ci, cell in enumerate(header_row or []):
        h = _norm_header(cell)
        for field, spellings, _req in _COLUMNS:
            if field not in cols and any(_norm_header(a) == h for a in spellings):
                cols[field] = ci
                break
    return cols


def _province(osb):
    m = re.search(r"-([A-Z]{2})$", str(osb or ""))
    return m.group(1) if m and m.group(1) in PROVINCES else None


def _latest_resource(catalog):
    """the max-year XLS(X) resource (tie -> latest created) — the cumulative snapshot."""
    res = ((catalog or {}).get("result") or {}).get("resources") or []

    def year_of(r):
        m = re.search(r"(19|20)\d{2}", r.get("name") or "")
        return int(m.group(0)) if m else -1

    cands = [r for r in res
             if (r.get("format") or "").upper() in ("XLS", "XLSX") and year_of(r) > 0]
    if not cands:
        raise SdkError("upstream_unavailable", provider="ca_osb",
                       detail="no year-named XLSX resource in the CKAN package — the catalog shape drifted")
    return max(cands, key=lambda r: (year_of(r), str(r.get("created") or ""))), len(res)


def _top_monitors(monitors):
    """case-folded ranking, most frequent original spelling shown, total proceedings per firm."""
    folded = {}
    for name, n in monitors.items():
        key = _fold(name)
        f = folded.setdefault(key, {"spelling": {}, "total": 0})
        f["spelling"][name] = f["spelling"].get(name, 0) + n
        f["total"] += n
    top = sorted(folded.values(), key=lambda f: -f["total"])[:5]
    return [{"monitor": max(f["spelling"], key=f["spelling"].get), "proceedings": f["total"]}
            for f in top]


def _parse_sheet(rows):
    """sheet rows -> (entity rows, census fragments). A drifted header is never guessed."""
    hi = _find_header(rows)
    if hi is None:
        raise SdkError("upstream_unavailable", provider="ca_osb",
                       detail="header anchors (Court File Number / OSB File Number / Company Name) "
                              "not found — the workbook shape drifted")
    cols = _map_columns(rows[hi])
    missing = [f for f, _s, req in _COLUMNS if req and f not in cols]
    if missing:
        raise SdkError("upstream_unavailable", provider="ca_osb",
                       detail=f"required columns unmapped after header find ({missing}) — shape drifted")

    def cell(row, field):
        ci = cols.get(field)
        return row[ci] if ci is not None and ci < len(row or []) else None

    out, provinces, monitors = [], {}, {}
    legacy_powers = alias_ride = dirty_year = with_amounts = 0
    years = []
    for row in rows[hi + 1:]:
        osb = _text(cell(row, "osb_file_number"))
        name = _text(cell(row, "company_name"))
        if not osb or not name:
            continue  # blank / spacer rows — an entity row needs BOTH keys
        ym = re.search(r"-(\d{4})-", osb)
        if ym and not re.fullmatch(r"(19|20)\d{2}", ym.group(1)):
            dirty_year += 1
        prov = _province(osb)
        if prov:
            provinces[prov] = provinces.get(prov, 0) + 1
        mon = _text(cell(row, "monitor"))
        if mon:
            monitors[mon] = monitors.get(mon, 0) + 1
        emp, is_sealed = _employees(cell(row, "employees_raw"))
        powers = _text(cell(row, "monitor_additional_powers"))
        if powers and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(powers)):
            legacy_powers += 1
        onm = _text(cell(row, "other_names"))
        if not onm and " / " in str(name):
            alias_ride += 1
        assets = _amount(cell(row, "assets_raw"))
        liabs = _amount(cell(row, "liabilities_raw"))
        if assets is not None or liabs is not None:
            with_amounts += 1
        d_init = _date_any(cell(row, "initial_order_raw"))
        if d_init:
            years.append(int(d_init[:4]))
        out.append({
            "court_file_number": _text(cell(row, "court_file_number")),
            "court": _text(cell(row, "court")),
            "osb_file_number": osb,
            "province": prov,
            "initial_order_date": d_init,
            "proceedings_web_page": _text(cell(row, "proceedings_web_page")),
            "company_name": name,
            "other_names": onm,
            "head_office": _text(cell(row, "head_office")),
            "telephone": _text(cell(row, "telephone")),
            "website": _text(cell(row, "website")),
            "monitor": mon,
            "monitor_website": _text(cell(row, "monitor_website")),
            "monitor_representative": _text(cell(row, "monitor_representative")),
            "monitor_address": _text(cell(row, "monitor_address")),
            "monitor_telephone": _text(cell(row, "monitor_telephone")),
            "monitor_email": _text(cell(row, "monitor_email")),
            "canadian_employees": emp,
            "sealed_order": is_sealed,
            "discharge_order_date": _date_any(cell(row, "discharge_raw")),
            "monitor_additional_powers": powers,
            "assets_at_filing": assets,
            "liabilities_at_filing": liabs,
        })
    frag = {
        "header_row": hi,
        "provinces": dict(sorted(provinces.items(), key=lambda kv: -kv[1])),
        # the register spells one firm several ways ('Ernst & Young Inc.' / 'ERNST & YOUNG INC.')
        # — the census folds case for the ranking, showing the register's most frequent spelling
        "monitors_top": _top_monitors(monitors),
        "with_amounts": with_amounts,
        "sealed_orders": sum(1 for x in out if x["sealed_order"]),
        "legacy_powers_date_only_rows": legacy_powers,
        "name_alias_ride_rows": alias_ride,
        "dirty_osb_year_rows": dirty_year,
    }
    if years:
        frag["initial_order_year_span"] = {"min": min(years), "max": max(years)}
    return out, frag


def ccaa_records_raw(*, name=None, province=None, monitor=None, osb=None,
                     limit=20, cache=None, no_cache=False):
    """the CCAA cumulative roster -> {rows, total_matched, scanned_rows, census, limit_applied,
    params, _meta, _metas}. The upstream has NO query surface — every filter is local over the
    latest cumulative workbook."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="ca_osb",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    prov_q = str(province or "").strip().upper() or None
    if prov_q is not None and prov_q not in PROVINCES:
        raise SdkError("usage_error", provider="ca_osb",
                       detail=f"province must be one of {sorted(PROVINCES)}, got {province!r}")
    osb_q = str(osb).strip() if osb not in (None, "") else None
    needle = _fold(name) or None
    mon_needle = _fold(monitor) or None

    cat = call_provider(provider, "catalog", {"id": PACKAGE_ID}, cache=cache, no_cache=no_cache)
    body = cat["data"]
    if not isinstance(body, dict) or not body.get("success", True):
        raise SdkError("upstream_unavailable", provider="ca_osb",
                       detail=f"the CKAN package_show call did not return a result envelope — {str(body)[:120]}")
    res, n_res = _latest_resource(body)

    fr = call_provider(provider, "file", {"file_url": res["url"]}, cache=cache, no_cache=no_cache)
    rows, frag = _parse_sheet(xlsx_first_sheet(fr["data"]))
    res_year = re.search(r"(19|20)\d{2}", res.get("name") or "")

    hits = []
    for x in rows:
        if prov_q is not None and x["province"] != prov_q:
            continue
        if osb_q is not None and x["osb_file_number"] != osb_q:
            continue
        if needle and needle not in _fold(x["company_name"]) and needle not in _fold(x["other_names"]):
            continue
        if mon_needle and mon_needle not in _fold(x["monitor"]):
            continue
        hits.append(x)

    census = {
        "proceedings": len(rows),
        "resources_in_package": n_res,
        "resource": {"name": res.get("name"), "format": res.get("format"),
                     "created": res.get("created"), "url": res.get("url")},
        "discharged": sum(1 for x in rows if x["discharge_order_date"]),
        "with_employees": sum(1 for x in rows if x["canadian_employees"] is not None),
        "with_monitor_web_page": sum(1 for x in rows if x["proceedings_web_page"]),
        **frag,
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"name": name or None, "province": prov_q, "monitor": monitor or None,
                       "osb": osb_q},
            "_meta": cat, "_metas": [cat, fr]}
