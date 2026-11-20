"""au_asx — ASX listed-companies directory (www.asx.com.au CSV, keyless; 0.3.69 batch E12).

2026-11-18 probed shape (tmp/probe-e12/asx-listed.csv):
  GET /asx/research/ASXListedCompanies.csv → 200, Content-Disposition attachment — a THREE-PART
  CSV: line 0 is a banner "ASX listed companies as at Wed Nov 18 20:23:29 AEDT 2026" (the AS-AT
  anchor — parsed, also returned verbatim), line 1 BLANK, line 2 the header
  (Company name,ASX code,GICS industry group), lines 3+ the quoted data rows — 2,060 rows on
  probe day. GICS rides the INDUSTRY GROUP level (27-group closed set measured: Materials 776 /
  Not Applic 303 / Class Pend 19 — "Not Applic" and "Class Pend" are LEGAL closed-set values,
  not dirty data — / Energy 123 / Software & Services 104 / Financial Services 93 / …).
  AU's first company-domain face: the listed universe as the exchange itself publishes it,
  refreshed daily (banner timestamp moves with the file).
TTL 1 day; politeness 1 rps (no published limit; probed 200s, no wall).
"""
import csv
import io
import re

from ..errors import SdkError

provider = {
    "id": "au_asx",
    "baseUrl": "https://www.asx.com.au",
    "rate": {"rps": 1.0, "burst": 2},
    "ops": {
        "listed": {"path": "/asx/research/ASXListedCompanies.csv", "idempotent": True,
                   "accept": "text", "timeout": 30.0},
    },
    "ttl": {"listed": 86400},
}

_BANNER_RE = re.compile(r"^ASX listed companies as at (.+)$")


def _parse_csv(text):
    """→ (as_at, header, rows[(name, code, gics)]) — the three-part shape, lenient on quoting."""
    lines = text.splitlines()
    as_at = None
    if lines and _BANNER_RE.match(lines[0].strip()):
        as_at = _BANNER_RE.match(lines[0].strip()).group(1).strip()
    rows = []
    header = None
    for rec in csv.reader(io.StringIO("\n".join(lines))):
        if not rec or not any(c.strip() for c in rec):
            continue
        if header is None and rec and rec[0].strip() == "Company name":
            header = [c.strip() for c in rec]
            continue
        if header is None:
            continue  # banner/blank lines before the header
        if len(rec) >= 3:
            rows.append((rec[0].strip(), rec[1].strip(), rec[2].strip()))
    return as_at, header, rows


def listed(*, code=None, name=None, gics=None, limit=None, cache=None, no_cache=False):
    """→ {as_at, total, rows[], params, _meta}; the ASX listed universe (2,060 rows probe day).
    Client-side selectors: --code exact ASX code (case-insensitive, e.g. BHP), --name substring
    (case-insensitive), --gics substring on the industry group ("Materials", "Not Applic"…);
    --limit slices the display, the full filtered set is what's returned otherwise."""
    from ..transport import call_provider

    r = call_provider(provider, "listed", {}, cache=cache, no_cache=no_cache)
    text = r["data"]
    if not isinstance(text, str) or "Company name" not in text:
        raise SdkError("upstream_changed", provider="au_asx",
                       detail="the CSV no longer carries the 'Company name,ASX code,GICS industry group' header — "
                              "shape drifted from the 2026-11-18 probe (tmp/probe-e12/)")
    as_at, header, parsed = _parse_csv(text)
    q_code = str(code).strip().upper() if code else None
    q_name = str(name).strip().lower() if name else None
    q_gics = str(gics).strip().lower() if gics else None
    rows = []
    for nm, cd, gc in parsed:
        if q_code and cd.upper() != q_code:
            continue
        if q_name and q_name not in nm.lower():
            continue
        if q_gics and q_gics not in gc.lower():
            continue
        rows.append({"company_name": nm, "asx_code": cd, "gics_industry_group": gc})
    total = len(rows)
    if limit is not None:
        lim = int(limit)
        if lim >= 0:
            rows = rows[:lim]
    return {"as_at": as_at, "header": header, "total": total, "rows": rows,
            "params": {"code": q_code, "name": q_name, "gics": q_gics, "limit": limit},
            "_meta": r}
