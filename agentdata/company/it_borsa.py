"""it_borsa — Borsa Italiana per-ISIN quote card (borsaitaliana.it dati-completi, keyless GET).

2026-11-18 probed shape (tmp/probe-e10/p6*): GET /borsa/azioni/{market}/dati-completi.html
?isin={ISIN}&mic={MIC}&lang=it → server-rendered HTML, zero cookie. Laws:

  SLUG-DECORATIVE: the {market} path segment is IGNORED upstream — ENI answered 200 with
  identical content under both its true segment (miv) and a wrong one (euronext-growth-milan,
  probed p6h); only isin/mic are authoritative. The engine therefore pins one fixed segment.
  LANG PIN: lang=it serves the card; lang=en serves a DIFFERENT generic page (54,285B, no
  metadata table, probed p6m) — the engine pins lang=it.
  MIC-OPTIONAL (with lang=it): dati-completi without mic returns the full card (p6i/p6m).
  SILENT-ERROR SHAPE: an unknown isin (or mismatched mic, e.g. ENI+MTAH) does NOT 404 — the
  upstream serves a generic ~118KB landing page with NO metadata table (p6i/p6m: bad isin /
  wrong mic both 118,371B). The engine detects "no Codice Isin pair" and reports not-found
  honestly, never a fake card.
  HEADERS: bare transport headers suffice — the 2026-11-18 header matrix (p6l/p6o, single and
  suite, through call_provider) got the 57,252B card on every variant; an earlier generic-page
  theory was falsified (the card always arrived; a regex bridge bug ate the extraction, p6p).
  NUMBERS are Italian-format (dots group thousands, comma decimals): Capitalizzazione di Mercato
  "77.546.623.783" → 77,546,623,783; prices "25,61" → 25.61. Raw strings ride alongside parsed
  numbers. Metadata markup: <td><span class="t-text"><strong>LABEL</strong></span></td>
  <td><span class="t-text -right">VALUE</span></td> — 28 pairs for ENI (ISIN/ID Strumento/
  Codice Alfanumerico/Super Sector/Mercato-Segmento/market cap/lot/quote stack/52-week/performances).
  The label pattern is a single text node — see the _PAIR_RE comment for the bridge bug.

Adjacent per-ISIN faces on the same contract (E11 candidates, not this engine): dividends
(elenco-completo-dividendi, market-free /borsa/quotazioni/azioni/ tree), company documents,
shareholders' meeting list. PDFs and *page= pagination are robots-barred — out of policy.
TTL 6h (15-min delayed quotes); politeness 0.5 rps.
"""
import html as _html
import re as _re

from ..errors import SdkError

provider = {
    "id": "it_borsa",
    "baseUrl": "https://www.borsaitaliana.it",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # accept text: server-rendered HTML parsed here; the {market} segment is decorative (p6h)
        "quote": {"path": "/borsa/azioni/euronext-growth-milan/dati-completi.html",
                  "accept": "text", "timeout": 45.0, "idempotent": True},
    },
    "ttl": {"quote": 6 * 3600},
}

# LABEL LAW: the label must be a single text node ([^<]*). A lazy .*? label BRIDGES — the page's
# first <strong> is the breadcrumb "Sei in: …" hundreds of bytes before the table, and .*? crosses
# tags until the first real pair, fusing breadcrumb+first label into one mega-pair that the ≤40
# cap then drops (smoke defect 2026-11-18: found=False while the 57KB card was in hand, p6p).
_PAIR_RE = _re.compile(
    r"<strong>([^<]*)</strong>\s*</span>\s*</td>\s*<td>\s*<span[^>]*>([^<]*)</span>")
_NAME_RE = _re.compile(r'<h1[^>]*>\s*<a[^>]+href="/borsa/azioni/scheda/[^"]+"[^>]*>(.*?)</a>', _re.S)


def _clean(s):
    return _re.sub(r"\s+", " ", _html.unescape(s or "")).replace("\xa0", " ").strip()


def _num(s):
    """Italian-format number → float (dots=thousands, comma=decimal); None when unparseable."""
    t = (s or "").strip()
    if not t or not _re.search(r"\d", t):
        return None
    t = t.split(" ")[0].split("-")[0].strip()
    try:
        return float(t.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def get_quote(isin, *, mic=None, cache=None, no_cache=False):
    """→ {found, isin, card, params, _meta}; the dati-completi card by ISIN.
    found=False means the upstream served its generic page (unknown ISIN / mismatched mic —
    probed silent shape), not an error. Card: meta{} = all label/value pairs verbatim +
    canonical parsed keys (ticker/super_sector/segment/market_cap_eur/last_price/id_strumento)."""
    from ..transport import call_provider

    v = str(isin or "").strip().upper()
    if not _re.match(r"^[A-Z]{2}[A-Z0-9]{9}\d$", v):
        raise SdkError("usage_error", provider="it_borsa",
                       detail=f"isin must be a 12-char ISO 6166 ISIN, got \"{isin}\"")
    m = str(mic or "").strip().upper() or None
    params = {"isin": v, "lang": "it"}
    if m:
        params["mic"] = m
    r = call_provider(provider, "quote", params, cache=cache, no_cache=no_cache)
    body = r["data"] or ""
    meta = {}
    for label, value in _PAIR_RE.findall(body):
        lab = _clean(label)
        if 0 < len(lab) <= 40:                       # drops the breadcrumb false-pair (probed 329-char label)
            meta[lab] = _clean(value)
    isin_row = meta.get("Codice Isin") or meta.get("Codice Isin'")
    if not isin_row:
        return {"found": False, "isin": v, "card": None, "params": params, "_meta": r}
    nm = _NAME_RE.search(body)
    card = {
        "isin": isin_row,
        "name": _clean(nm.group(1)) if nm else None,   # h1 → the instrument's scheda link anchor text

        "id_strumento": meta.get("ID Strumento"),
        "ticker": meta.get("Codice Alfanumerico"),
        "super_sector": meta.get("Super Sector"),
        "segment": meta.get("Mercato/Segmento"),
        "market_cap_eur": _num(meta.get("Capitalizzazione di Mercato", "")),
        "market_cap_raw": meta.get("Capitalizzazione di Mercato"),
        "last_price": _num(meta.get("Prezzo Ultimo Contratto", "")),
        "lot_minimo": meta.get("Lotto Minimo"),
        "meta": meta,
    }
    return {"found": True, "isin": isin_row, "card": card, "params": params, "_meta": r}
