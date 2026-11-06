"""jp_fsa — FSA (Financial Services Agency of Japan) licensed / registered institution
XLSX farm, www.fsa.go.jp/en/regulated/licensed/{stem}.xlsx (research volume
jp-fsa-licensed-xlsx-farm, 册 241; face admitted in 0.3.42, probed first-hand
2026-11-04/05 tmp/probe-jp-fsa-0342/ — the hub plus all 31 files 200 + PK magic +
sharedStrings with zero parse failures, honest agentdata UA, 4.5s pacing).

The hub (…/licensed/index.html) links THIRTY-ONE keyless XLSX workbooks — separate
registers, each with its own as-of stamp and its own sheet shape. The face is ONE
local-scan family face over the farm: --category picks the register (31 slugs, one
or two files each), the file(s) are fetched once per TTL window and scanned locally
(--name contains, --jcn exact — the upstream has NO query surface at all).

Postures this face keeps:
  * every register keeps the FILE'S OWN wording verbatim — names, addresses and
    registration numbers are never re-typed; the only derivations are the JCN
    normalisation (NFKC; '―'/'－'/'－' full-width dashes are the register's
    "not applicable", never a value), the date decodes (Excel serial → ISO,
    d/m/yyyy strings, 平成/令和 era dates → ISO) and the shared-string
    furigana strip on the two Japanese-language files;
  * several registers are FROZEN years back (dpc/sfc as of Oct 2017, fico Aug
    2016, fco Feb 2021) — the census carries each file's own as-of so a stale
    register never masquerades as a live one;
  * the 'Total N banks' cells ride ON DATA ROWS (e.g. bank_holding's
    'Total 31 companies' sits on the Hokuhoku Financial Group row) — the row
    stays, the category does NOT change (the marker is a subtotal, not a class);
  * the JCN / Corporate Number / 法人番号 columns are ONE key under three
    spellings (fibo says 'JCN', the crypto registers say 'Corporate Number',
    sintaku says 法人番号) — mapped to one field; the two insurance lists and
    the FMI four carry NO corporate number at all (honest nulls, never guessed);
  * fafia (Foreign Audit Firms) is an ACCUMULATING register: one firm's row is
    followed by continuation rows carrying address fragments and '○'-prefixed
    foreign-issuer lines — the walkers fold continuations into the firm row
    (545 sheet rows → the firms themselves);
  * the two Japanese-language sintaku files concatenate the furigana reading
    onto every value ('北海道財務局長/（代信）第1号ホッカイドウ…' — kanji, '/',
    reading) — the strip is positional (trailing katakana runs), applied ONLY
    on those two files, never on the romanised ones.

Channel: honest agentdata UA, direct, zero extra headers → 200 on the hub and all
31 files (t1, 2026-11-04/05). Rate: polite 0.5 rps / burst 2 (its own host
www.fsa.go.jp — not shared with any other provider). TTL: 24h per file (register
posture; the freshest file turned over same-day, the stalest is nine years old —
each file's own as-of rides the census). Transport: accept='bytes' (extension 9 —
the xlsx body ships as a lossless latin-1 string, re-encoded and unzipped with
stdlib zipfile; sharedStrings AND inline strings both resolved, the ru_cbr sheets
were inline-only, these are shared-string).
"""
import datetime as _dt
import io
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET

from ..errors import SdkError

provider = {
    "id": "jp_fsa",
    "baseUrl": "https://www.fsa.go.jp",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "file": {"path": "/en/regulated/licensed/{stem}", "accept": "bytes", "timeout": 120.0},
    },
    "ttl": {"file": 24 * 3600},
}

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# ---------------------------------------------------------------- the farm map
# slug -> spec. files: workbooks fetched for the category (one or two); label: the
# hub's own wording; shape: the walker; sheets: which sheets of the workbook feed
# the category (True = the only sheet). Live grain 2026-11-05 in the census.
FAMILIES = {
    "city_banks": {"files": ["city.xlsx"],
                   "sheets": {"City Banks and Trust Banks": True},
                   "label": "City Banks and Trust Banks", "shape": "bank5"},
    "foreign_banks": {"files": ["city.xlsx"],
                      "sheets": {"Foreign Banks": True},
                      "label": "Foreign Banks (licensed in Japan)", "shape": "bank5"},
    "regional_banks": {"files": ["reg.xlsx"],
                       "sheets": {"Regional Banks": True, "Regional Banks Ⅱ": True, "Others": True},
                       "label": "Regional Banks (incl. Ⅱ and others)", "shape": "regional"},
    "bank_holding_companies": {"files": ["bank_holding.xlsx"],
                               "sheets": {"Bank Holding company": True},
                               "label": "Bank Holding Companies", "shape": "bank5"},
    "credit_associations": {"files": ["s_banks.xlsx"],
                            "sheets": {"Credit Associations": True},
                            "label": "Credit Associations (Shinkin banks)", "shape": "plain4_headless"},
    "shinkumi_banks": {"files": ["e_shinkumi.xlsx"],
                       "sheets": {"Shinkumi Banks": True},
                       "label": "Credit Cooperative (Shinkumi Banks)", "shape": "plain4_headless"},
    "keito_institutions": {"files": ["keito.xlsx"],
                           "sheets": {"Keito Financial Institutions": True},
                           "label": "Keito Financial Institutions (system institutions)",
                           "shape": "keito"},
    "trust_business_institutions": {"files": ["fietb.xlsx"],
                                    "sheets": {"FIeTB": True},
                                    "label": "Financial Institutions which engage in trust business",
                                    "shape": "bank5"},
    "trust_companies": {"files": ["trustcompanies.xlsx"],
                        "sheets": {"Trust Companies": True},
                        "label": "Trust Companies", "shape": "bank5"},
    "self_trust_companies": {"files": ["sintaku02.xlsx"],
                             "sheets": {"自己信託会社": True},
                             "label": "Self-Trust Companies (自己信託会社)", "shape": "sintaku"},
    "trust_agents": {"files": ["sintaku_a.xlsx"],
                     "sheets": {"信託契約代理店": True},
                     "label": "Trust Contract Agents (信託契約代理店)", "shape": "sintaku"},
    "foreign_bank_agents": {"files": ["foreign.xlsx"],
                            "sheets": {"Foreign Bank's Agent Banks": True},
                            "label": "Foreign Banks' Agent Banks in Japan", "shape": "agents"},
    "financial_instruments_operators": {"files": ["fibo.xlsx"],
                                        "sheets": {"English": True},
                                        "label": "Financial Instruments Business Operators",
                                        "shape": "fibo"},
    "financial_intermediaries": {"files": ["fiisp.xlsx"],
                                 "sheets": {"English": True},
                                 "label": "Financial Instruments Intermediary Service Providers",
                                 "shape": "fiisp"},
    "high_speed_traders": {"files": ["hst.xlsx"],
                           "sheets": {"High Speed Traders": True},
                           "label": "High Speed Traders", "shape": "hst"},
    "crypto_exchanges": {"files": ["en_kasoutuka.xlsx"],
                         "sheets": {"list": True},
                         "label": "Registered Crypto-asset Exchange Service Providers",
                         "shape": "registered8"},
    "electronic_payment_issuers": {"files": ["denshikessaisyudan.xlsx"],
                                   "sheets": {"list": True},
                                   "label": "Registered Electronic Payment Instruments Exchange Service Providers",
                                   "shape": "registered8"},
    "fx_analysis_providers": {"files": ["kawasebunseki.xlsx"],
                              "sheets": {"為替取引分析業者": True},
                              "label": "FX Transaction Analysis Providers (為替取引分析業者)",
                              "shape": "fx8"},
    "clearing_organizations": {"files": ["fico.xlsx", "foreign_fico.xlsx"],
                               "sheets": {"CCPs": True},
                               "label": "Financial Instruments Clearing Organizations (domestic + foreign)",
                               "shape": "fm4"},
    "fund_clearing_organizations": {"files": ["fco.xlsx"],
                                    "sheets": {"Fund Clearing Organization": True},
                                    "label": "Fund Clearing Organization", "shape": "fm4"},
    "book_entry_transfer_institutions": {"files": ["beti.xlsx"],
                                         "sheets": {"Book-Entry Transfer Institution": True},
                                         "label": "Book-Entry Transfer Institution", "shape": "fm4"},
    "trade_repositories": {"files": ["tr.xlsx"],
                           "sheets": {"Trade Repository": True},
                           "label": "Trade Repository", "shape": "fm4"},
    "credit_rating_agencies": {"files": ["cra.xlsx"],
                               "sheets": {"信用格付業者登録一覧": True},
                               "label": "Credit Rating Agencies", "shape": "simple4"},
    "benchmark_administrators": {"files": ["Specified_Financial_Benchmark_Administrators.xlsx"],
                                 "sheets": {"SFBA": True},
                                 "label": "Specified Financial Benchmark Administrators",
                                 "shape": "simple4"},
    "securities_finance_companies": {"files": ["sfc.xlsx"],
                                     "sheets": {"securities finance companies": True},
                                     "label": "Securities Finance Companies", "shape": "plain4_headless"},
    "designated_parent_companies": {"files": ["dpc.xlsx"],
                                    "sheets": {"Designated Parent Company": True},
                                    "label": "Designated Parent Company", "shape": "simple4"},
    "exchange_operators": {"files": ["authorized_ope.xlsx"],
                           "sheets": {"authorized_ope": True},
                           "label": "Authorized Transaction-at-Exchange Operators",
                           "shape": "simple2"},
    "life_insurers": {"files": ["ins_life.xlsx"],
                      "sheets": {"List": True},
                      "label": "Life Insurance Companies", "shape": "ins_list"},
    "nonlife_insurers": {"files": ["ins_nonlife.xlsx"],
                         "sheets": {"domestic companies": "domestic", "Branch Offices": "branch"},
                         "label": "Non-life Insurance Companies (domestic + branch offices)",
                         "shape": "ins_nonlife"},
    "insurance_holdings": {"files": ["ins_holding.xlsx"],
                           "sheets": {"Insurance holding companies": True},
                           "label": "Insurance Holding Companies", "shape": "ins_list"},
    "foreign_audit_firms": {"files": ["fafia.xlsx"],
                            "sheets": {"Foreign Audit Firms": True},
                            "label": "Foreign Audit Firms and Individual Accountants",
                            "shape": "fafia"},
}

# ------------------------------------------------------------ xlsx (stdlib-only)
def _col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def xlsx_sheets(payload):
    """accept='bytes' payload (lossless latin-1 string) -> {sheet_name: rows} with
    shared AND inline strings resolved (pure function; stdlib zipfile + ElementTree)."""
    z = zipfile.ZipFile(io.BytesIO(payload.encode("latin-1")))
    names = z.namelist()
    shared = []
    if "xl/sharedStrings.xml" in names:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rel_map = {r.get("Id"): r.get("Target") for r in rels}
    out = {}
    for sh in wb.find(f"{NS}sheets"):
        rid = sh.get(f"{RNS}id")
        tgt = rel_map.get(rid, "")
        path = tgt.lstrip("/") if tgt.startswith("/") else (tgt if tgt.startswith("xl/") else "xl/" + tgt)
        try:
            xmlb = z.read(path)
        except KeyError:
            out[sh.get("name")] = []
            continue
        root = ET.fromstring(xmlb)
        rows = []
        for row in root.iter(f"{NS}row"):
            cells = []
            for c in row.findall(f"{NS}c"):
                idx = _col_index(re.match(r"([A-Z]+)", c.get("r", "A1")).group(1))
                while len(cells) < idx:
                    cells.append(None)
                t = c.get("t")
                if t == "s":
                    v = c.find(f"{NS}v")
                    cells.append(shared[int(v.text)] if v is not None else None)
                elif t == "inlineStr":
                    is_ = c.find(f"{NS}is")
                    cells.append("".join(x.text or "" for x in is_.iter(f"{NS}t")) if is_ is not None else None)
                else:
                    v = c.find(f"{NS}v")
                    cells.append(v.text if v is not None else None)
            rows.append(cells)
        out[sh.get("name")] = rows
    return out


# ---------------------------------------------------------------- value helpers
_PLACEHOLDERS = {"", "-", "―", "－", "—", "－", "N/A", "n/a", "－"}


def _text(v):
    """cell -> verbatim text or None (the register's dash placeholders are empties)."""
    if v is None:
        return None
    s = unicodedata.normalize("NFKC", str(v)).strip()
    return None if s in _PLACEHOLDERS or s == "　" * len(s) else s


def _fold(s):
    """search fold: NFKC + casefold (full-width alphanumerics unify)."""
    return unicodedata.normalize("NFKC", str(s or "")).casefold()


def _jcn(v):
    """JCN / Corporate Number / 法人番号 cell -> the 13-digit string or None."""
    s = _text(v)
    if s is None:
        return None
    s2 = s.replace(" ", "").replace("　", "")
    return s2 if s2.isdigit() else s


def _serial_date(v):
    """Excel serial (epoch 1899-12-30) -> ISO date or None."""
    s = _text(v)
    if s is None:
        return None
    try:
        n = int(float(s))
    except ValueError:
        return None
    if not 30000 <= n <= 60000:  # 1982..2064 — a serial outside the register era is not a date
        return None
    return (_dt.date(1899, 12, 30) + _dt.timedelta(days=n)).isoformat()


_MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}
for _m, _i in list(_MONTHS.items()):          # the registers abbreviate ('Oct 30, 2026')
    _MONTHS[_m[:3]] = _i


def _text_date(v):
    """'Aug 7, 2008' / 'September 24, 2026' / '30th September, 2026' -> ISO or None."""
    s = _text(v)
    if s is None:
        return None
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s).replace(",", " ")
    parts = s.split()
    for i, p in enumerate(parts):
        if p.isdigit() and len(p) == 4:
            for q in parts:
                mq = _MONTHS.get(q)
                if mq:
                    days = [int(x) for x in parts if x.isdigit() and len(x) <= 2]
                    if days:
                        try:
                            return _dt.date(int(p), mq, days[0]).isoformat()
                        except ValueError:
                            return None
    return None


def _dmy_date(v):
    """'21/6/2018' (d/m/yyyy — 21 proves the day leads) -> ISO or None."""
    s = _text(v)
    if not s:
        return None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return _dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


_ERAS = {"明治": (1868, "meiji"), "大正": (1912, "taisho"), "昭和": (1926, "showa"),
         "平成": (1989, "heisei"), "令和": (2019, "reiwa")}


def _era_date(v):
    """'平成16年12月30日' / '令和8年9月30日現在' -> ISO or None (the era starts Jan 1 of its year-1)."""
    s = _text(v)
    if not s:
        return None
    m = re.search(r"(明治|大正|昭和|平成|令和)\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", s)
    if not m:
        return None
    base, _ = _ERAS[m.group(1)]
    y = base + int(m.group(2)) - 1
    try:
        return _dt.date(y, int(m.group(3)), int(m.group(4))).isoformat()
    except ValueError:
        return None


def _any_date(v):
    """era > text > d/m/y > serial, in that order (an era string never parses as serial)."""
    return _era_date(v) or _text_date(v) or _dmy_date(v) or _serial_date(v)


_KATAKANA_RUN = re.compile(r"[゠-ヿーｰ]+$")


def _defurigana(s):
    """sintaku files only: strip the appended/interleaved furigana reading. The cells
    carry kanji + reading as 'kanji/reading' or 'kanjireading'; a '/'-part whose
    trailing katakana run strips away is a reading continuation (joins the previous
    part), a '/'-part left unchanged is a separate list item (the affiliated
    companies cell). Returns the list of defuriganed parts."""
    s = unicodedata.normalize("NFKC", str(s or "")).strip()
    if not s:
        return []
    out = []
    for part in s.split("/"):
        if not part:
            continue
        stripped = _KATAKANA_RUN.sub("", part)
        if stripped and stripped != part and out:
            out[-1] += stripped          # reading fragment — joins the current value
        elif stripped:
            out.append(stripped if stripped != part else part)
        # a pure-katakana part with nothing left strips to '' — a reading, dropped
    return [p for p in out if p]


def _split_list(v, sep):
    """'BTC、ETH、XRP' or 'A / B / C' -> list (verbatim items)."""
    s = _text(v)
    if not s:
        return None
    items = [x.strip() for x in s.split(sep) if x.strip()]
    return items or None


_MARKER_CNT = re.compile(r"【[^：]*?[：:]\s*([0-9０-９]+)\s*[^0-9]*】")
_TOTAL_EN = re.compile(r"Total\s+([0-9]+)\s*(banks|companies|firms)", re.I)
_COMPANIES_N = re.compile(r"^([0-9]+)\s+companies$", re.I)
_DOMESTIC_N = re.compile(r"Domestic companies:\s*([0-9]+)", re.I)
_NUMBER_N = re.compile(r"【Number[：:]\s*([0-9０-９]+)\s*】")   # NFKC turns the full-width colon ASCII
_GROUP_N = re.compile(r"([A-Za-z ]+?):\s*\(([0-9]+)\)")


def _countof(raw):
    """full-width-safe integer out of a marker/claim regex group."""
    return int(unicodedata.normalize("NFKC", str(raw)))


def _prelude(rows, limit=6):
    """rows before the header -> (as_of, as_of_raw, claims, notes_n). The as-of line
    rides anywhere in the first cells ('As of September 24, 2026', '(as of October 1,
    2026)', 'As at October 1, 2017', '令和８年９月30日現在'); the claims are the title's
    own totals ('Total 36 banks', '【The total number of …：31】', '【Number：27】')."""
    as_of = as_of_raw = None
    claims = []
    for r in rows[:limit]:
        for cell in (r or []):
            s = _text(cell)
            if not s:
                continue
            if as_of_raw is None:
                m = re.search(r"(?:as\s+of|as\s+at)[,:\s]+(.+?)(?:\)|$)", s, re.I | re.S)
                if m:
                    as_of_raw = m.group(1).strip(" .()")
                    as_of = _text_date(as_of_raw)
                elif "現在" in s:
                    as_of_raw = s
                    as_of = _era_date(s)
                elif s.replace(".", "").isdigit() and _serial_date(s) is not None:
                    as_of_raw = s          # a lone decodable number in the prelude is the serial as-of (fibo 46295)
                    as_of = _serial_date(s)
            for rx in (_TOTAL_EN,):
                m = rx.search(s)
                if m:
                    claims.append({"claim": s, "count": _countof(m.group(1))})
            for rx in (_MARKER_CNT, _NUMBER_N):
                m = rx.search(s)
                if m:
                    claims.append({"claim": s, "count": _countof(m.group(1))})
            m = _COMPANIES_N.match(s)
            if m:
                claims.append({"claim": s, "count": _countof(m.group(1))})
            m = _DOMESTIC_N.search(s)
            if m:
                claims.append({"claim": s, "count": _countof(m.group(1))})
    return as_of, as_of_raw, claims


def _norm_header(h):
    """header text -> comparable form: NFKC (full-width unifies), whitespace runs
    collapse (the headers break lines mid-word), 'Securities- Related' reunites."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(h or ""))).strip().replace("- ", "-").casefold()


def _find_header(rows, anchors, limit=12):
    """first row whose normalised cells contain ALL anchor substrings -> its index
    (None = the shape drifted — the caller raises upstream_unavailable, never guesses)."""
    want = [_norm_header(a) for a in anchors]
    for i, r in enumerate(rows[:limit]):
        cells = [_norm_header(x) for x in (r or [])]
        if all(any(a in c for c in cells if c) for a in want):
            return i
    return None


def _map_columns(header_row, spec):
    """header cells -> {col_index: field} per the family's (field, substrings[, "optional"])
    spec. Each field claims the FIRST unclaimed cell whose text contains its keys — a
    field never takes two columns (the kawase trap: 'Permission' alone would swallow the
    'Date of Permission' column and starve the date field). An entry marked "optional"
    may be absent altogether (the alternative-label registers — city's two sheets lead
    with EITHER 'Business category' OR 'Country/Area'; sintaku02 has no
    affiliated-companies column; SFBA carries no JCN); a required field that misses =
    shape drift = None."""
    cells = [_norm_header(x) for x in (header_row or [])]
    mapping = {}
    for entry in spec:
        field, keys = entry[0], [_norm_header(k) for k in entry[1]]
        optional = len(entry) > 2 and entry[2] == "optional"
        hit = False
        for idx, cell in enumerate(cells):
            if not cell or idx in mapping:
                continue
            if all(k in cell for k in keys):
                mapping[idx] = field
                hit = True
                break
        if not hit and not optional:
            return None
    return mapping


# ------------------------------------------------------------------- walkers
def _walk_bank5(rows, sheet):
    """Business-category (or Country/Area) forward-fill + name + JCN + address +
    telephone. The 'Total N banks/companies' subtotal cells ride ON DATA ROWS — the
    row stays, the category does not change."""
    hi = _find_header(rows, ["JCN"])
    if hi is None:
        return None
    mapping = _map_columns(rows[hi], [
        ("business_category", ["business category"], "optional"),
        ("country", ["country"], "optional"),
        ("name", ["name"]),
        ("jcn", ["jcn"]),
        ("address", ["address"]),
        ("telephone", ["telephon"]),
    ])
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    ffill_field = "business_category" if "business_category" in inv else ("country" if "country" in inv else None)
    out, ffill = [], None
    for r in rows[hi + 1:]:
        get = lambda f: (r or [])[inv[f]] if f in inv and inv[f] < len(r or []) else None
        name = _text(get("name"))
        cell = _text(get(ffill_field)) if ffill_field else None
        if cell is not None and not _TOTAL_EN.fullmatch(cell):
            ffill = cell
        if name is None:
            continue
        row = {"name": name}
        if ffill_field:
            row[ffill_field] = ffill
        if "jcn" in inv:
            row["jcn"] = _jcn(get("jcn"))
        row["address"] = _text(get("address"))
        row["telephone"] = _text(get("telephone"))
        out.append(row)
    return out, {"header_row": hi}


def _walk_regional(rows, sheet):
    """name(Japanese) + name(English) + JCN + phone; spacer rows carry no name."""
    hi = _find_header(rows, ["name(english)", "jcn"])
    if hi is None:
        return None
    mapping = _map_columns(rows[hi], [
        ("name_ja", ["name(japanese)"]), ("name", ["name(english)"]),
        ("jcn", ["jcn"]), ("telephone", ["phone"]),
    ])
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    out = []
    for r in rows[hi + 1:]:
        get = lambda f: (r or [])[inv[f]] if inv[f] < len(r or []) else None
        if _text(get("name")) is None and _jcn(get("jcn")) is None:
            continue
        out.append({"name_ja": _text(get("name_ja")), "name": _text(get("name")),
                    "jcn": _jcn(get("jcn")), "telephone": _text(get("telephone"))})
    return out, {"header_row": hi}


def _walk_plain4_headless(rows, sheet):
    """NO header row at all (s_banks / e_shinkumi) or a None-padded one (sfc):
    columns positional — col0 filler, name, JCN, phone-or-address. The entity marker
    is a DIGIT JCN: the sheets open with label rows that carry a name but no number
    ('The list of…', 'Federation of Shinkumi Banks') — sfc's whole register is ONE
    company under its title, and the title itself parses as a name without this rule."""
    out = []
    for r in rows:
        cells = r or []
        name = _text(cells[1]) if len(cells) > 1 else None
        jcn = _jcn(cells[2]) if len(cells) > 2 else None
        if name is None or jcn is None or not str(jcn).isdigit():
            continue
        row = {"name": name, "jcn": jcn}
        tail = [_text(x) for x in cells[3:6]]
        tail = [x for x in tail if x]
        if tail:
            row["telephone"] = tail[0] if re.match(r"^[0-9()\-+. ー]+$", tail[0]) else None
            rest = [x for x in tail if x is not row.get("telephone")]
            if rest and row.get("telephone") is None:
                row["address"] = rest[0]
        out.append(row)
    return out, {}


def _walk_keito(rows, sheet):
    """Supervisory + Prefecture + name + Postal + Address + Telephone. ONE institution
    (the Norinchukin Bank) plus a footnote row — the footnote has no name cell and drops."""
    hi = _find_header(rows, ["prefecture", "telephone"])
    if hi is None:
        return None
    mapping = _map_columns(rows[hi], [
        ("authority", ["supervisory"]), ("prefecture", ["prefecture"]), ("name", ["name"]),
        ("postal_code", ["postal"]), ("address", ["address"]), ("telephone", ["telephon"]),
    ])
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    out = []
    for r in rows[hi + 1:]:
        get = lambda f: (r or [])[inv[f]] if inv[f] < len(r or []) else None
        if _text(get("name")) is None:
            continue
        out.append({"authority": _text(get("authority")), "prefecture": _text(get("prefecture")),
                    "name": _text(get("name")), "postal_code": _text(get("postal_code")),
                    "address": _text(get("address")), "telephone": _text(get("telephone"))})
    return out, {"header_row": hi}


def _walk_agents(rows, sheet):
    """Foreign banks' agent banks: Supervisory + Licence No. ('－' = none) + permission
    date (serial) + name + JCN + post + address + tel + principal bank + home country."""
    hi = _find_header(rows, ["licence", "jcn"])
    if hi is None:
        return None
    mapping = _map_columns(rows[hi], [
        ("authority", ["supervisory"]), ("licence_no", ["licence"]),
        ("registered_at", ["permission"]), ("name", ["name"]),
        ("jcn", ["jcn"]), ("postal_code", ["post"]), ("address", ["address"]),
        ("telephone", ["telephon"]), ("principal_bank", ["principal"]),
        ("country", ["home country"]),
    ])
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    out, ffill, history = [], {}, 0
    for r in rows[hi + 1:]:
        get = lambda f: (r or [])[inv[f]] if f in inv and inv[f] < len(r or []) else None
        if _text(get("name")) is None:
            if _text(get("registered_at")) is not None or _text(get("licence_no")) is not None:
                history += 1    # the nameless rows are the register's own permission history
            continue
        for f in ("authority", "country", "principal_bank"):
            v = _text(get(f))
            if v is not None:
                ffill[f] = v
        out.append({"authority": ffill.get("authority"),
                    "licence_no": _text(get("licence_no")),
                    "registered_at": _serial_date(get("registered_at")),
                    "name": _text(get("name")), "jcn": _jcn(get("jcn")),
                    "postal_code": _text(get("postal_code")), "address": _text(get("address")),
                    "telephone": _text(get("telephone")),
                    "principal_bank": ffill.get("principal_bank"),
                    "country": ffill.get("country")})
    return out, {"header_row": hi, "permission_history_rows": history}


def _walk_flags_tail(rows, sheet, tail_fields, extras=None):
    """shared walker for fibo / fiisp: Jurisdiction ffill + registration numbers +
    name + JCN + address + telephone, then the register's own tail columns —
    ○-marked business types (fibo) or the '/'-separated affiliated-company list
    (fiisp). Values are '○' or blank; the column's own header is the type's name."""
    hi = _find_header(rows, ["registration numbers", "jcn"])
    if hi is None:
        return None
    head = [
        ("authority", ["jurisdiction"]), ("registration_number", ["registration numbers"]),
        ("name", ["name"]), ("jcn", ["jcn"]), ("address", ["address"]),
        ("telephone", ["telephon"]),
    ]
    mapping = _map_columns(rows[hi], head + extras)
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    tail_cols = {idx: field for field, keys in tail_fields for idx, f2 in mapping.items() if f2 == field}
    out, ffill = [], None
    for r in rows[hi + 1:]:
        get = lambda f: (r or [])[inv[f]] if f in inv and inv[f] < len(r or []) else None
        if _text(get("name")) is None:
            continue
        a = _text(get("authority"))
        if a is not None:
            ffill = a
        row = {"authority": ffill, "registration_number": _text(get("registration_number")),
               "name": _text(get("name")), "jcn": _jcn(get("jcn")),
               "address": _text(get("address")), "telephone": _text(get("telephone"))}
        flags = []
        for idx, field in sorted(tail_cols.items()):
            v = (r or [])[idx] if idx < len(r or []) else None
            if v is not None and str(v).strip() and "○" in str(v):
                label = tail_fields_lookup(tail_fields, field)
                flags.append(label)
        if flags:
            row["business_types"] = flags
        for field, conv in (("affiliated", lambda x: _split_list(x, "/")),):
            if field in inv and get(field) is not None:
                # the affiliated list rides one cell, '/'- or newline-separated (both in the wild)
                v = [p for x in conv(get(field)) or [] for p in str(x).split("\n") if p.strip()] or None
                if v:
                    row[field] = v
        out.append(row)
    return out, {"header_row": hi}


def tail_fields_lookup(tail_fields, field):
    """the ○ column's own header text, verbatim (the type's name of record)."""
    for f, keys in tail_fields:
        if f == field:
            return " ".join(keys)
    return field


def _walk_hst(rows, sheet):
    """High Speed Traders: registration date is a d/m/yyyy STRING (21/6/2018 — the 21
    proves the day leads) and the JCN column is mostly '―' — the foreign entities have
    no Japanese corporate number (honest null)."""
    hi = _find_header(rows, ["registration numbers", "jcn"])
    if hi is None:
        return None
    mapping = _map_columns(rows[hi], [
        ("authority", ["jurisdiction"]), ("registration_number", ["registration numbers"]),
        ("registered_at", ["registration date"]), ("name", ["name"]),
        ("jcn", ["jcn"]), ("address", ["address"]),
    ])
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    out, ffill = [], None
    for r in rows[hi + 1:]:
        get = lambda f: (r or [])[inv[f]] if inv[f] < len(r or []) else None
        if _text(get("name")) is None:
            continue
        a = _text(get("authority"))
        if a is not None:
            ffill = a
        out.append({"authority": ffill, "registration_number": _text(get("registration_number")),
                    "registered_at": _dmy_date(get("registered_at")) or _text(get("registered_at")),
                    "name": _text(get("name")), "jcn": _jcn(get("jcn")),
                    "address": _text(get("address"))})
    return out, {"header_row": hi}


def _walk_registered8(rows, sheet):
    """the crypto / electronic-payment registers: the registering bureau rides col0 with
    its own 【Number：N】 per-bureau count ('The Kanto Financial Bureau【Number：25】' —
    NFKC turns the full-width ： into ':'), dates are serials, the JCN column is named
    'Corporate Number', and the handled-instruments column is a '、'-joined list."""
    hi = _find_header(rows, ["registration number", "corporate number"])
    if hi is None:
        return None
    mapping = _map_columns(rows[hi], [
        ("authority", ["bureau"], "optional"),   # the bureau column carries NO header — the
        # 【Number：N】 cells ride it positionally, injected below
        ("registration_number", ["registration number"]),
        ("registered_at", ["date of registration"]), ("name", ["name"]),
        ("jcn", ["corporate number"]), ("postal_code", ["postal"]),
        ("address", ["location"]), ("telephone", ["phone"]),
        ("instruments", ["handled"]),
    ])
    mapping.setdefault(0, "authority")
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    out, ffill, sections = [], None, {}
    for r in rows[hi + 1:]:
        get = lambda f: (r or [])[inv[f]] if inv[f] < len(r or []) else None
        raw_auth = _text(get("authority"))
        if raw_auth is not None:
            m = _NUMBER_N.search(raw_auth)
            if m:
                label = _NUMBER_N.sub("", raw_auth).strip()
                sections[label] = _countof(m.group(1))
                ffill = label
        if _text(get("name")) is None:
            continue
        out.append({"authority": ffill, "registration_number": _text(get("registration_number")),
                    "registered_at": _serial_date(get("registered_at")),
                    "name": _text(get("name")), "jcn": _jcn(get("jcn")),
                    "postal_code": _text(get("postal_code")), "address": _text(get("address")),
                    "telephone": _text(get("telephone")),
                    "instruments": _split_list(get("instruments"), "、")})
    return out, {"header_row": hi, "sections": sections}


def _walk_fx8(rows, sheet):
    """為替取引分析業者: Supervisory + Permission No. + serial date + name +
    Corporate Number + post + address + telephone."""
    hi = _find_header(rows, ["permission", "corporate number"])
    if hi is None:
        return None
    mapping = _map_columns(rows[hi], [
        ("authority", ["supervisory"]), ("registration_number", ["permission"]),
        ("registered_at", ["date of permission"]), ("name", ["name"]),
        ("jcn", ["corporate number"]), ("postal_code", ["postal"]),
        ("address", ["address"]), ("telephone", ["telephon"]),
    ])
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    out = []
    for r in rows[hi + 1:]:
        get = lambda f: (r or [])[inv[f]] if inv[f] < len(r or []) else None
        if _text(get("name")) is None:
            continue
        out.append({"authority": _text(get("authority")),
                    "registration_number": _text(get("registration_number")),
                    "registered_at": _serial_date(get("registered_at")),
                    "name": _text(get("name")), "jcn": _jcn(get("jcn")),
                    "postal_code": _text(get("postal_code")), "address": _text(get("address")),
                    "telephone": _text(get("telephone"))})
    return out, {"header_row": hi}


def _walk_fm4(rows, sheet):
    """the FMI four (+CCPs): Business-category forward-fill + name + address +
    telephone; NO corporate number on these registers."""
    hi = _find_header(rows, ["name of company", "address"])
    if hi is None:
        return None
    mapping = _map_columns(rows[hi], [
        ("business_category", ["business category", "category"]),
        ("name", ["name"]), ("address", ["address"]), ("telephone", ["telephon"]),
    ])
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    out, ffill = [], None
    for r in rows[hi + 1:]:
        get = lambda f: (r or [])[inv[f]] if inv[f] < len(r or []) else None
        cell = _text(get("business_category")) if "business_category" in inv else None
        if cell is not None:
            ffill = cell
        if _text(get("name")) is None:
            continue
        row = {"name": _text(get("name")), "address": _text(get("address")),
               "telephone": _text(get("telephone"))}
        if "business_category" in inv:
            row["business_category"] = ffill
        out.append(row)
    return out, {"header_row": hi}


def _walk_simple(rows, sheet, fields):
    """Name(+JCN)+Address(+Telephone) registers (cra / dpc / SFBA / authorized_ope) —
    the hub's smallest lists, some frozen years back (dpc 2017). The anchors are the
    REQUIRED fields' keys (SFBA carries no JCN; cra/dpc carry no Jurisdiction column)."""
    anchors = [ks[0] for entry in fields for ks in [entry[1]] if not (len(entry) > 2 and entry[2] == "optional")]
    hi = _find_header(rows, anchors)
    if hi is None:
        return None
    mapping = _map_columns(rows[hi], fields)
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    out = []
    for r in rows[hi + 1:]:
        get = lambda f: (r or [])[inv[f]] if f in inv and inv[f] < len(r or []) else None
        if _text(get("name")) is None:
            continue
        row = {"name": _text(get("name"))}
        if "jcn" in inv:
            row["jcn"] = _jcn(get("jcn"))
        if "address" in inv:
            row["address"] = _text(get("address"))
        if "telephone" in inv:
            row["telephone"] = _text(get("telephone"))
        out.append(row)
    return out, {"header_row": hi}


def _walk_ins_list(rows, sheet):
    """ins_life / ins_holding: the group cell rides col1 ('Mutual companies: (5)'),
    name col2, phone col3; NO corporate number on the insurance lists."""
    hi = _find_header(rows, ["name of company"])
    if hi is None:
        return None
    out, group, groups = [], None, {}
    for r in rows[hi + 1:]:
        cells = r or []
        name = _text(cells[2]) if len(cells) > 2 else None
        gcell = _text(cells[1]) if len(cells) > 1 else None
        if gcell is not None:
            m = _GROUP_N.search(gcell)
            if m:
                groups[re.sub(r"\s*:\s*\(\d+\)\s*$", "", gcell).strip()] = _countof(m.group(2))
            group = re.sub(r"\s*:\s*\(\d+\)\s*$", "", gcell).strip()
        if name is None:
            continue
        out.append({"business_category": group, "name": name,
                    "telephone": _text(cells[3]) if len(cells) > 3 else None})
    return out, {"header_row": hi, "groups": groups}


def _walk_ins_nonlife(rows, sheet):
    """ins_nonlife: two sheets — domestic ([?, name, phone]) and Branch Offices
    ([nationality ffill, name, phone]); NO corporate number."""
    out, nat, nats = [], None, {}
    for r in rows:
        cells = r or []
        name = _text(cells[1]) if len(cells) > 1 else None
        ncell = _text(cells[0]) if cells else None
        if ncell is not None and not name:
            nat = ncell
        if name is None:
            continue
        if ncell is not None and name:
            nat = ncell
        out.append({"business_category": nat, "name": name,
                    "telephone": _text(cells[2]) if len(cells) > 2 else None})
    for x in out:
        nats[x["business_category"]] = nats.get(x["business_category"], 0) + 1
    return out, {"groups": nats}


def _walk_sintaku(rows, sheet, with_affiliated):
    """the two Japanese-language registers: furigana is concatenated onto every value
    ('北海道財務局長/（代信）第1号ホッカイドウ…'), dates are 平成/令和 era strings (trust_agents)
    or serials (self_trust), the JCN column is 法人番号, and the bureau col0 carries its
    own 【計N社】/【計N店】 count. Every value passes _defurigana."""
    hi = _find_header(rows, ["法人番号"])
    if hi is None:
        return None
    mapping = _map_columns(rows[hi], [
        ("authority", ["所管"]), ("registration_number", ["登録番号"]),
        ("registered_at", ["登録年月日"]), ("name", ["名"]),
        ("jcn", ["法人番号"]), ("postal_code", ["郵便番号"]),
        ("address", ["所在地"]), ("telephone", ["電話番号"]),
        ("affiliated", ["所属"], "optional"),   # sintaku02 (self-trust) has no affiliated column
    ])
    if mapping is None:
        return None
    inv = {v: k for k, v in mapping.items()}
    out, ffill, sections = [], None, {}
    for r in rows[hi + 1:]:
        cells = r or []
        get = lambda f: cells[inv[f]] if f in inv and inv[f] < len(cells) else None
        raw_auth = _text(get("authority"))
        if raw_auth is not None:
            parts = _defurigana(raw_auth)
            if parts:
                m = re.search(r"【計([0-9０-９]+)[社店]】", parts[-1] if "/" in raw_auth else raw_auth)
                label = re.sub(r"【[^】]*】", "", parts[0]).strip()
                if m:
                    sections[label] = _countof(m.group(1))
                ffill = label
        name = _text(get("name"))
        if name is None:
            continue
        name = _defurigana(name)
        if not name:
            continue
        aff = None
        if with_affiliated and "affiliated" in inv:
            # the affiliated trust companies ride one cell, newline-separated (the '/'
            # belongs to the furigana convention, not to the company list)
            aff = [p.strip() for part in _defurigana(_text(get("affiliated")) or "")
                   for p in part.split("\n") if p.strip()] or None
        out.append({"authority": ffill,
                    "registration_number": (_defurigana(_text(get("registration_number")) or "") or [None])[0],
                    "registered_at": _any_date(get("registered_at")),
                    "name": name[0], "jcn": _jcn(get("jcn")),
                    "postal_code": (_defurigana(_text(get("postal_code")) or "") or [None])[0],
                    "address": (_defurigana(_text(get("address")) or "") or [None])[0],
                    "telephone": _text(get("telephone")),
                    **({"affiliated_trust_companies": aff} if aff else {})})
    return out, {"header_row": hi, "sections": sections}


def _walk_fafia(rows, sheet):
    """Foreign Audit Firms: a FIRM row (No. + dates + name) is followed by continuation
    rows carrying address fragments and '○'-prefixed foreign-issuer lines — the walk
    folds them into the firm (545 sheet rows -> the firms). 'Aug 7, 2008（Dec 6, 2024）'
    carries the original notification and the updating date."""
    hi = _find_header(rows, ["original notification"])
    if hi is None:
        return None
    out = []
    cur = None
    for r in rows[hi + 1:]:
        cells = r or []
        no = _text(cells[0]) if cells else None
        dates_raw = _text(cells[1]) if len(cells) > 1 else None
        name = _text(cells[2]) if len(cells) > 2 else None
        addr = _text(cells[3]) if len(cells) > 3 else None
        issuer = _text(cells[4]) if len(cells) > 4 else None
        if no is not None or (name is not None and (cur is None or cur.get("name") != name)):
            notified = updated = None
            if dates_raw:
                both = re.findall(r"[A-Z][a-z]{2}\s+\d{1,2},\s*\d{4}", unicodedata.normalize("NFKC", dates_raw))
                notified = _text_date(both[0]) if both else None
                updated = _text_date(both[1]) if len(both) > 1 else None
            if cur is not None:
                out.append(cur)
            cur = {"serial": no, "name": name,
                   "notified_at": notified, "updated_at": updated,
                   "updated_raw": dates_raw, "address": None, "issuers_audited": []}
        if cur is None:
            continue
        if name is not None and cur.get("name") is None:
            cur["name"] = name
        if addr is not None and cur.get("address") is None:
            cur["address"] = addr
        elif addr is not None:
            cur["address"] = (cur["address"] or "") + " " + addr
        if issuer is not None:
            for line in str(issuer).splitlines():
                line = unicodedata.normalize("NFKC", line).strip()
                if line.startswith("○"):
                    who = line.lstrip("○").strip()
                    if who:
                        cur["issuers_audited"].append(who)
    if cur is not None:
        out.append(cur)
    return out, {"header_row": hi}


# fibo's ○ tail columns (the register's own header wording is the type's name)
_FIBO_TAIL = [
    ("type_i", ["Type I Financial Instruments Business"]),
    ("type_ii", ["Type II"]),
    ("advisory_agency", ["Investment Advisory and Agency"]),
    ("investment_management", ["Investment Management"]),
    ("securities_related", ["Securities-Related"]),
]

_SHAPE_WALKERS = {
    "bank5": lambda rows, sheet: _walk_bank5(rows, sheet),
    "regional": _walk_regional,
    "plain4_headless": _walk_plain4_headless,
    "keito": _walk_keito,
    "agents": _walk_agents,
    "fibo": lambda rows, sheet: _walk_flags_tail(
        rows, sheet, _FIBO_TAIL,
        extras=[(f, [k]) for f, keys in _FIBO_TAIL for k in keys]),
    "fiisp": lambda rows, sheet: _walk_flags_tail(
        rows, sheet, [], extras=[("affiliated", ["Affiliation"])]),
    "hst": _walk_hst,
    "registered8": _walk_registered8,
    "fx8": _walk_fx8,
    "fm4": _walk_fm4,
    "simple4": lambda rows, sheet: _walk_simple(rows, sheet, [
        ("authority", ["Jurisdiction"], "optional"), ("name", ["Name"]),
        ("jcn", ["JCN"], "optional"), ("address", ["Address"]),
        ("telephone", ["Telephone"])]),
    "simple2": lambda rows, sheet: _walk_simple(rows, sheet, [
        ("name", ["Name"]), ("address", ["Address"])]),
    "ins_list": _walk_ins_list,
    "ins_nonlife": _walk_ins_nonlife,
    "sintaku": lambda rows, sheet: _walk_sintaku(rows, sheet, with_affiliated=True),
    "fafia": _walk_fafia,
}

_SHEET_TAG = {"domestic": "domestic companies", "branch": "branch offices"}


def _parse_file(slug, stem, sheets_data):
    """one workbook -> (rows, per-file census). A missing sheet or a drifted header is
    upstream_unavailable — never a guessed parse."""
    spec = FAMILIES[slug]
    shape = spec["shape"]
    walk = _SHAPE_WALKERS[shape]
    all_rows, sheets_meta, sections, groups, claims = [], {}, {}, {}, []
    as_of = as_of_raw = None
    for sheet_name, mode in spec["sheets"].items():
        rows = sheets_data.get(sheet_name)
        if rows is None:
            raise SdkError("upstream_unavailable", provider="jp_fsa",
                           detail=f"{stem}: sheet {sheet_name!r} not found — the workbook shape drifted")
        got = walk(rows, sheet_name)
        if got is None:
            raise SdkError("upstream_unavailable", provider="jp_fsa",
                           detail=f"{stem}/{sheet_name}: header anchors not found — the register shape drifted")
        srows, meta = got
        tag = _SHEET_TAG.get(mode, sheet_name) if isinstance(mode, str) else sheet_name
        sheets_meta[tag] = {"rows_in_sheet": len(rows), "entities": len(srows),
                            **({"header_row": meta["header_row"]} if "header_row" in meta else {}),
                            **({"permission_history_rows": meta["permission_history_rows"]}
                               if "permission_history_rows" in meta else {})}
        sections.update(meta.get("sections") or {})
        groups.update(meta.get("groups") or {})
        # the prelude STOPS AT THE HEADER (or the first 3 rows on the headerless sheets):
        # a wider window swallows data rows and a JCN would pose as a serial as-of
        a, ar, cl = _prelude(rows[:meta["header_row"]] if "header_row" in meta else rows[:3])
        if a and not as_of:
            as_of, as_of_raw = a, ar
        claims.extend(cl)
        for x in srows:
            x["file"] = stem
            x["sheet"] = tag
        all_rows.extend(srows)
    fcensus = {"sheets": sheets_meta, "as_of": as_of, "as_of_raw": as_of_raw,
               "claims": claims, "entities": len(all_rows)}
    if sections:
        fcensus["sections"] = sections
    if groups:
        fcensus["groups"] = groups
    return all_rows, fcensus


def licensed_raw(category, *, name=None, jcn=None, limit=20, cache=None, no_cache=False):
    """one FSA register -> {rows, total_matched, scanned_rows, census, limit_applied,
    params, _meta, _metas}. The upstream has NO query surface — --name / --jcn are
    local filters over the fetched workbook(s)."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="jp_fsa",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    cat = str(category or "").strip() or None
    if cat not in FAMILIES:
        raise SdkError("usage_error", provider="jp_fsa",
                       detail=f"category must be one of {sorted(FAMILIES)}, got {category!r}")
    jc = str(jcn).strip() if jcn not in (None, "") else None
    if jc is not None and not (jc.isdigit() and len(jc) == 13):
        raise SdkError("usage_error", provider="jp_fsa",
                       detail=f"jcn must be the 13-digit JCN / Corporate Number, got {jcn!r}")
    needle = _fold(name) or None

    spec = FAMILIES[cat]
    scanned, metas, files_census = [], [], {}
    for stem in spec["files"]:
        r = call_provider(provider, "file", {"stem": stem}, cache=cache, no_cache=no_cache)
        rows, fcensus = _parse_file(cat, stem, xlsx_sheets(r["data"]))
        files_census[stem] = fcensus
        for x in rows:
            x["category"] = cat
            x["category_label"] = spec["label"]
        scanned.extend(rows)
        metas.append(r)

    hits = []
    for x in scanned:
        if jc is not None and str(x.get("jcn") or "") != jc:
            continue
        if needle and needle not in _fold(x.get("name")):
            continue
        hits.append(x)

    census = {
        "entities": len(scanned),
        "files": files_census,
        "with_jcn": sum(1 for x in scanned if x.get("jcn")),
        "with_registration_number": sum(1 for x in scanned if x.get("registration_number")),
        "registered": sum(1 for x in scanned if x.get("registered_at") or x.get("notified_at")),
        "with_address": sum(1 for x in scanned if x.get("address")),
        "files_fetched": len(spec["files"]),
    }
    if cat == "foreign_audit_firms":
        census["issuers_listed"] = sum(len(x.get("issuers_audited") or []) for x in scanned)
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(scanned),
            "census": census, "limit_applied": size,
            "params": {"category": cat, "name": name or None, "jcn": jc},
            "_meta": metas[0], "_metas": metas}
