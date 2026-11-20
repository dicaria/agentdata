"""at_wiener — Wiener Börse listed equities (wienerborse.at segment tables; 0.3.69 batch E12).

2026-11-18 probed laws (tmp/probe-e12/):
TLS REVERSAL: the E10 deferral (2026-11-18 am) was the host serving a *.factsetdigitalsolutions.com
  certificate from www.wienerborse.at — same-day re-probe gets a clean DigiCert chain with
  CN=www.wienerborse.at and 200s. The reversal-window law: a same-day reversal is re-probed
  before any verdict, and a deferred face revives on its evidence.
UNIVERSE: the two Austrian equity segments are SERVER-RENDERED tables — /aktien-prime-market/
  (47 issuers probe day) and /aktien-standard-market/ (~26). The ISIN rides the company-page
  slug (.../agrana-beteiligungs-ag-AT000AGRANA3/), the only per-row structured id. Server-side
  sort knob ?c2974-sort=name_logo|price|diff|ask|bid|datetime|marketCapitalization exists but
  the engine always walks the default order.
SPAN-STACK LAW: one <td> can stack several values in nested spans/divs/<br> — Diff.% and
  Diff. abs. share a cell (two divs), date and time share a cell (<br>), bid/ask price+volume
  share a cell (two divs) — the parser splits on element boundaries (span/a/b/small/div/p/br),
  and the naive strip-all-tags view glues them ("18.11.202612:03:29" = 18.11.2026 | 12:03:29).
GERMAN NUMBER LAW: decimal comma ("11,7500"), thousands dot ("3.265"), unit suffixes
  "Mio." (×1e6) / "Mrd." (×1e9) on Marktkapitalisierung ("734,2 Mio.") — parsed values ride
  *_num keys, the verbatim strings always ride alongside.
TTL 1 hour (an intraday quote table); politeness 1 rps (no published limit; probes 200, no wall).
"""
import re
from html.parser import HTMLParser

from ..errors import SdkError

provider = {
    "id": "at_wiener",
    "baseUrl": "https://www.wienerborse.at",
    "rate": {"rps": 1.0, "burst": 2},
    "ops": {
        "prime": {"path": "/aktien-prime-market/", "idempotent": True, "accept": "text",
                  "timeout": 30.0},
        "standard": {"path": "/aktien-standard-market/", "idempotent": True, "accept": "text",
                     "timeout": 30.0},
    },
    "ttl": {"prime": 3600, "standard": 3600},
}

_SEGMENTS = {"prime": "prime", "standard": "standard"}
_ISIN_RE = re.compile(r"(AT[A-Z0-9]{10})/?$")  # the slug carries a trailing slash


class _TableParser(HTMLParser):
    """Collects tbody rows: per <td> a LIST of span-split text parts + the first <a href>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._in_cell = False
        self._buf = None
        self._parts = None
        self._href = None
        self._row = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._in_cell = True
            self._buf = ""
            self._parts = []
            self._href = None
        elif self._in_cell and tag in ("span", "a", "b", "small", "div", "p", "br"):
            if tag == "a" and self._href is None:
                for k, v in attrs:
                    if k == "href":
                        self._href = v
            self._flush()

    def handle_endtag(self, tag):
        if tag == "td" and self._in_cell:
            self._flush()
            self._row.append({"parts": self._parts, "href": self._href})
            self._in_cell = False
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
        elif self._in_cell and tag in ("span", "a", "b", "small", "div", "p", "br"):
            self._flush()

    def handle_data(self, data):
        if self._in_cell and data:
            self._buf += data

    def _flush(self):
        if self._buf.strip():
            self._parts.append(self._buf.strip())
        self._buf = ""


def _de_num(raw):
    """German-format → float ('11,7500'→11.75, '734,2 Mio.'→734200000.0, '-0,42 %'→-0.42); None on junk."""
    if raw is None:
        return None
    s = str(raw).strip().replace("\xa0", " ").replace("%", "").strip()
    mult = 1.0
    for suf, m in (("Mrd.", 1e9), ("Mio.", 1e6)):
        if s.endswith(suf):
            mult, s = m, s[: -len(suf)].strip()
            break
    s = s.replace(".", "").replace(",", ".")
    try:
        return round(float(s) * mult, 6)
    except ValueError:
        return None


def _part(cell, i=0):
    return cell["parts"][i].strip() if len(cell["parts"]) > i else None


def _parse_segment(html, segment):
    """→ rows of the quote table; raises upstream_changed when the 10-column shape drifts."""
    p = _TableParser()
    p.feed(html)
    out = []
    for cells in p.rows:
        if len(cells) < 10:  # sort-link rows / foreign tables never carry the 10 columns
            continue
        name_cell = cells[0]
        name = " ".join(name_cell["parts"])
        href = name_cell.get("href") or ""
        mis = _ISIN_RE.search(href)
        if not name or not mis:
            continue
        def two(c):  # span-stacked cell → (first, second)
            return _part(c, 0), (_part(c, 1) if len(c["parts"]) > 1 else None)
        diff_pct, diff_abs = two(cells[2])
        date, time_s = two(cells[3])
        bid, bid_vol = two(cells[5])
        ask, ask_vol = two(cells[6])
        row = {
            "name": name, "isin": mis.group(1), "company_url": href or None,
            "segment": segment,
            "price": _part(cells[1]), "price_num": _de_num(_part(cells[1])),
            "diff_pct": diff_pct, "diff_pct_num": _de_num(diff_pct),
            "diff_abs": diff_abs, "diff_abs_num": _de_num(diff_abs),
            "date": date, "time": time_s,
            "market_cap": _part(cells[4]), "market_cap_num": _de_num(_part(cells[4])),
            "bid": bid, "bid_volume": bid_vol, "bid_num": _de_num(bid),
            "ask": ask, "ask_volume": ask_vol, "ask_num": _de_num(ask),
            "turnover_shares": _part(cells[7]), "turnover_value": _part(cells[8]),
            "status": _part(cells[9]),
        }
        out.append(row)
    return out


def listed(*, segment="all", code=None, isin=None, name=None, cache=None, no_cache=False):
    """→ {segments[], total, rows[], params, _meta[]}; the Austrian listed-equity universe.
    segment all|prime|standard (prime 47 / standard ~26 issuers probe day). Selectors: --isin
    exact (the slug-carried id), --name substring, --code — Wiener Börse quotes carry no ticker
    column, so --code matches the ISIN's tail or name head as a courtesy alias. Verbatim German
    strings ride every row; parsed floats ride *_num."""
    from ..transport import call_provider

    seg = str(segment or "all").strip().lower()
    if seg not in ("all", "prime", "standard"):
        raise SdkError("usage_error", provider="at_wiener",
                       detail=f"segment must be all|prime|standard (got \"{segment}\")")
    segs = ["prime", "standard"] if seg == "all" else [seg]
    metas = []
    rows = []
    for s in segs:
        r = call_provider(provider, s, {}, cache=cache, no_cache=no_cache)
        metas.append(r)
        rows.extend(_parse_segment(r["data"], s))
    if not rows:
        raise SdkError("upstream_changed", provider="at_wiener",
                       detail="no segment table rows parsed — the wienerborse.at table shape "
                              "drifted from the 2026-11-18 probe (tmp/probe-e12/)")
    q_isin = str(isin).strip().upper() if isin else None
    q_name = str(name).strip().lower() if name else None
    q_code = str(code).strip().upper() if code else None
    out = []
    for row in rows:
        if q_isin and row["isin"] != q_isin:
            continue
        if q_name and q_name not in row["name"].lower():
            continue
        if q_code and not (row["isin"].endswith(q_code) or row["name"].upper().startswith(q_code)):
            continue
        out.append(row)
    return {"segments": segs, "total": len(out), "rows": out,
            "params": {"segment": seg, "code": code, "isin": isin, "name": name},
            "_meta": metas[0] if len(metas) == 1 else metas}
