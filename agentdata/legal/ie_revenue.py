"""ie_revenue — Irish Revenue Commissioners List of Defaulters provider (revenue.ie; keyless).

legal tax-defaulters face (0.3.27; admitted 2026-11-03, probed tmp/probe-legal-0327). Two-step resolution:
the index page (/en/corporate/press-office/list-of-defaulters/index.aspx, ~72KB HTML) links ONLY the current
year's quarterly files — 12 links = 2 quarters × 2 parts × 3 formats for 2026-11 (pdf / xlsx / csv; March
part 1 ships .xls, a one-off anomaly); older years live under their own year folders but are NOT linked from
the index. The CSV arrives as application/octet-stream with a UTF-8 BOM; the header row carries TRAILING
SPACES ("County ", "Total ") — normalised before mapping; amounts are quoted comma-thousands ("549,292"),
occasionally annotated ("114,659 (including surcharge of 10,423)") — the leading number is the amount.

10 columns: Name, Address, County, Occupation, Tax, Interest, Penalties, Total, Additional particulars,
Unpaid (Unpaid empty = nothing further outstanding). Individuals and companies sit in one list
("COATES, NIAMH" PAYE EMPLOYEE next to LIMITED companies) — the register's own ordering.

**PII stance (the co_sic_sanctions precedent)**: names + addresses are published BY STATUTE (Revenue's
quarterly defaulters publication, court-confirmed settlements above the disclosure threshold) — a public
register, republished verbatim; not leaked personal data.

**Accept content-negotiation gate (pinned live 2026-11-03)**: the transport's default Accept
(application/json) → HTTP 406 on BOTH endpoints — ext-8 override "text/html, */*" passes (the ca_sema
family's fourth pinned member; the */* arm carries the octet-stream csv).

TTL: index 24h (quarterly cadence), csv 7d; polite tier 0.2 rps (static-file host).
"""
import csv
import io
import re

from ..errors import SdkError

provider = {
    "id": "ie_revenue",
    "baseUrl": "https://www.revenue.ie",
    "rate": {"rps": 0.2, "burst": 1},
    "ops": {
        "index": {"path": "/en/corporate/press-office/list-of-defaulters/index.aspx",
                  "accept": "text", "timeoutMs": 60000},
        "defaulters": {"path": "{csv_path}", "accept": "text", "notFound": [404],
                       "path_safe": "/", "timeoutMs": 90000},
    },
    "ttl": {"index": 24 * 3600, "defaulters": 7 * 86400},
}

# Accept gate override (both endpoints): application/json → 406; text/html (index) and */* (csv) pass
_HTML_ACCEPT = {"Accept": "text/html, */*"}

# quarterly publication: march/june/september/december; two parts per quarter — AND THE TWO PARTS ARE
# TWO DIFFERENT TABLES (pinned live 2026-11-03): part 1 = penalties determined by a court
# (Issue Type / Name / Address / Occupation / Fine Amount € / Sentence Imposed / No. of Charges — the
# header embeds padding + a € sign), part 2 = Revenue settlements (Name / Address / County / Occupation
# / Tax / Interest / Penalties / Total / Additional particulars / Unpaid).
_MONTH_RANK = {"march": 1, "june": 2, "september": 3, "december": 4}

_SETTLEMENT_COLS = {"name": "name", "address": "address", "county": "county", "occupation": "occupation",
                    "particulars": "additional particulars"}
_SETTLEMENT_MONEY = ("tax", "interest", "penalties", "total", "unpaid")
_COURT_COLS = {"issue_type": "issue type", "name": "name", "address": "address",
               "occupation": "occupation", "sentence_imposed": "sentence imposed"}


def _norm_header(h):
    """Header cell → match key: strip, lower, collapse whitespace/€/U+FFFD runs to single spaces
    ("County " → "county"; "Fine Amount     €" → "fine amount" — the part-1 header's € byte arrives
    as the U+FFFD replacement char (the file's own mojibake), collapsed the same way)."""
    return re.sub(r"[\s€�]+", " ", str(h or "").strip().lower()).strip()


def _amount(cell):
    """"549,292" → 549292; "24,172.00" → 24172 (the court fines carry trailing .00);
    "114,659 (including surcharge of 10,423)" → 114659 (annotation dropped); "0" → 0; ""/None → None."""
    m = re.search(r"\d[\d,]*(?=[\s(]|\.0|$)", str(cell or "").strip())
    return int(m.group(0).replace(",", "")) if m else None


def _text(cell):
    """A text column's cell: verbatim when non-blank (upstream trailing spaces are the data),
    None when empty/blank (the same empty-is-missing contract as the money columns)."""
    s = str(cell) if cell is not None else ""
    return s if s.strip() else None


def _quarter_links(html):
    """Index HTML → {csv_path: (year, month, part)} — the .csv hrefs only (pdf/xlsx siblings skipped)."""
    out = {}
    for href in re.findall(r'href="([^"]*defaulters-list-part-[^"]*\.csv)"', html or ""):
        m = re.search(r"defaulters-list-part-(\d)-([a-z]+)-(\d{4})\.csv", href)
        if m and m.group(2) in _MONTH_RANK:
            out[href] = (int(m.group(3)), m.group(2), int(m.group(1)))
    return out


def rows_from_upstream(text):
    """CSV text → {"kind": "court_penalties"|"revenue_settlements", "rows": [...]} (pure function).
    BOM stripped; headers normalised (trailing spaces, the part-1 padding + €); money to int
    (comma-thousands stripped, decimals/annotations dropped)."""
    if not text:
        return {"kind": "unknown", "rows": []}
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = [_norm_header(h) for h in next(reader)]
    except StopIteration:
        return {"kind": "unknown", "rows": []}
    kind = ("court_penalties" if "issue type" in header
            else "revenue_settlements" if "total" in header else "unknown")
    cols = _COURT_COLS if kind == "court_penalties" else _SETTLEMENT_COLS
    rows = []
    for rec in reader:
        if not rec or not any(str(x or "").strip() for x in rec):
            continue                                    # trailing blank lines
        cell = {header[i]: (rec[i] if i < len(rec) else None) for i in range(len(header))}
        row = {k: (_text(cell.get(v))) for k, v in cols.items()}
        if kind == "court_penalties":
            row["fine_amount"] = _amount(cell.get("fine amount"))
            n = str(cell.get("no. of charges") or "").strip()
            row["charges"] = int(n) if n.isdigit() else None
        else:
            for m in _SETTLEMENT_MONEY:
                row[m] = _amount(cell.get(m))
        rows.append(row)
    return {"kind": kind, "rows": rows}


def defaulters_raw(part=None, *, year=None, month=None, cache=None, no_cache=False):
    """Resolve + fetch one quarterly part → {quarter, part, kind, count, rows, available_quarters,
    params, _meta}.

    part 1|2 (default 1): part 1 = court-determined penalties, part 2 = Revenue settlements — two
    different row schemas under one publication (kind says which). year + month select the quarter
    (month = quarter name, march/june/september/december) — both or neither; the default is the LATEST
    quarter on the index. The index is fetched first (cached 24h), the chosen CSV cached 7d."""
    from ..transport import call_provider

    p = int(part or 1)
    if p not in (1, 2):
        raise SdkError("usage_error", provider="ie_revenue",
                       detail=f"part must be 1 or 2 (1 = court penalties, 2 = Revenue settlements), got '{part}'")
    m = str(month).strip().lower() if month else None
    if m is not None and m not in _MONTH_RANK:
        raise SdkError("usage_error", provider="ie_revenue",
                       detail=f"month must be one of {', '.join(_MONTH_RANK)} (quarterly publication), "
                              f"got '{month}'")
    y = int(year) if year else None
    if (y is None) != (m is None):
        raise SdkError("usage_error", provider="ie_revenue",
                       detail="year and month come together (a quarterly list) — give both or neither")

    idx = call_provider(provider, "index", {}, cache=cache, no_cache=no_cache,
                        extra_headers=_HTML_ACCEPT)
    links = _quarter_links(idx["data"])
    if not links:
        raise SdkError("upstream_unavailable", provider="ie_revenue",
                       detail="the defaulters index parsed to zero csv links (page shape changed?)")
    available = sorted({(yy, mm) for (yy, mm, _) in links.values()},
                       key=lambda t: (t[0], _MONTH_RANK[t[1]]))
    if y is None:
        y, m = available[-1]                            # the latest quarter on the index
    hit = [path for path, (yy, mm, pp) in links.items() if yy == y and mm == m and pp == p]
    if not hit:
        have = ", ".join(f"{mm} {yy}" for yy, mm in available)
        raise SdkError("upstream_not_found", provider="ie_revenue",
                       detail=f"no defaulters list for {m} {y} part {p} on the index (the index links "
                              f"the current year only); available quarters: {have}")
    r = call_provider(provider, "defaulters", {"csv_path": hit[0]}, cache=cache, no_cache=no_cache,
                      extra_headers=_HTML_ACCEPT)
    parsed = rows_from_upstream(r["data"])
    if parsed["kind"] == "unknown":
        raise SdkError("upstream_unavailable", provider="ie_revenue",
                       detail="the defaulters CSV header matches neither the court-penalties nor the "
                              "settlements shape (upstream format change?)")
    return {"quarter": f"{m} {y}", "part": p, "kind": parsed["kind"], "count": len(parsed["rows"]),
            "rows": parsed["rows"],
            "available_quarters": [f"{mm} {yy}" for yy, mm in available],
            "params": {"csv_path": hit[0]}, "_meta": r}
