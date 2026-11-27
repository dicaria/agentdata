"""fr_amf — AMF (Autorité des marchés financiers) sanctions & settlements, REST listing
double face (www.amf-france.org/fr/rest, keyless).

FR legal faces (0.3.59; admitted from research booklet fr-amf-sanctions booklet 125, re-probed
live 2026-11-13, tmp/probe-sdk-0359/r1_amf_*.json — the REST family was broken through on
2026-11-03 and re-verified today). The AMF publishes its two decision streams as single-shot
full-JSON REST endpoints: listing_sanction (454 rows live — disciplinary sanctions by the
Commission des sanctions) and listing_transaction (138 rows — homologated settlement
transactions). NO pagination: the theme/date path segments filter, the body returns the whole
matching set in one shot.

CONTRACT (GET, path-filtered):
/fr/rest/listing_sanction/{theme}/{date_from}/{date_to} and the listing_transaction twin.
- theme position takes a Drupal taxonomy tid ('all' = every theme; tids are stable — the
  measured map is embedded below and the live taxonomy endpoint /fr/rest/taxonomy/{kind}/all
  returns the same 12 pairs, verified 2026-11-13; tid 90 → 37 rows, all 'Manipulation de
  marché').
- the date pair takes unix seconds ('all' ≡ 0/9999999999 — verified equivalent). The module
  accepts ISO YYYY-MM-DD and converts (UTC midnight), or passes unix ints through.
- response {"data": [cards]} — every card {date: unix-string, theme, infos{...}}.

Row schema (the infos block, uniform 454/454 sanction · 138/138 transaction):
- sanction infos: title (SAN-2026-07 primary key), text_egard (the parties, '<br/>'-separated
  — persons and companies mixed, split here), text (the amount/penalty, small HTML), legend,
  link.url (decision page on amf-france.org), recours ('oui'/'non' appeal flag — sanction
  only), download.sanction.links.url (the decision PDF, relative path under
  /sites/institutionnel/files/private/YYYY-MM/).
- transaction infos adds text_acteur (the actor) and total (numeric string amount, e.g.
  '15000'); text carries the amount with HTML entities ('15 000 &euro;').
Amount/party/PDF coverage is 454/454 full on the live sanction body. The module strips the
light HTML (tags + entities + whitespace collapse), converts unix→ISO dates, and absolutizes
PDF/page URLs against https://www.amf-france.org. The OS-label mirror of the booklet is NOT
wired (separate static table — enrichment layer, not part of the live face). 0.5/2 polite,
TTL 24h.
"""
import html
import re
import time

from ..errors import SdkError

provider = {
    "id": "fr_amf",
    "baseUrl": "https://www.amf-france.org",
    "rate": {"rps": 0.5, "burst": 2},
    "concurrency": 2,
    "ops": {
        "sanctions": {"path": "/fr/rest/listing_sanction/{theme}/{date_from}/{date_to}",
                      "method": "GET", "idempotent": True, "timeout": 60.0},
        "transactions": {"path": "/fr/rest/listing_transaction/{theme}/{date_from}/{date_to}",
                         "method": "GET", "idempotent": True, "timeout": 60.0},
        # the live tid map (12 pairs; embedded one is a fallback — the module consults it
        # locally so theme-name sugar never costs an extra upstream call)
        "taxonomy": {"path": "/fr/rest/taxonomy/{kind}/all", "method": "GET",
                     "idempotent": True, "timeout": 30.0},
    },
    "ttl": {"sanctions": 24 * 3600, "transactions": 24 * 3600, "taxonomy": 7 * 24 * 3600},
}

# measured 2026-11-13 via /fr/rest/taxonomy/sanction/all (name → tid; 'all' excluded —
# the module passes 'all' itself when theme is None)
THEMES = {
    "Procédure": "86",
    "Obligation d'information": "89",
    "Manipulation de marché": "90",
    "CIF, CIP ou autres prestataires": "91",
    "PSI": "181",
    "Infrastructure de marché": "183",
    "Imputabilité": "184",
    "Obligations professionnelles": "242",
    "Instrument financier": "325",
    "Manquement d'initié": "461",
    "Produit d'épargne collective": "462",
}

_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<br\s*/?\s*>", re.IGNORECASE)
_WS = re.compile(r"\s+")


def _strip_html(v):
    """Light HTML → plain text (tags dropped, entities unescaped, whitespace collapsed)."""
    if not isinstance(v, str):
        return None
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", _BR.sub("\n", v)))).strip()


def _parse_date(v):
    """'2026-05-14' → unix seconds (UTC midnight); unix int/str passes through."""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s == "all":
        return None
    if s.isdigit():
        n = int(s)
        if n <= 0 or n >= 9999999999:
            raise SdkError("usage_error", provider="fr_amf",
                           detail=f"date bound {s} out of range — pass unix seconds or ISO YYYY-MM-DD")
        return n
    try:
        t = time.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise SdkError("usage_error", provider="fr_amf",
                       detail=f"date {v!r} must be ISO YYYY-MM-DD or unix seconds")
    return int(time.mktime(t))  # local-midnight unix is fine for a day-precision filter


def _iso_from_unix(v):
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(int(v)))
    except (TypeError, ValueError):
        return None


def _abs(url):
    if not url:
        return None
    return url if url.startswith("http") else provider["baseUrl"] + url


def resolve_theme(theme=None):
    """theme → the path segment: None/'all' → 'all'; a tid string/number passes through;
    an exact theme name resolves against the measured map (accent/case-tolerant)."""
    if theme is None or str(theme).strip() in ("", "all"):
        return "all"
    s = str(theme).strip()
    if s.isdigit():
        return s
    folded = {k.casefold(): v for k, v in THEMES.items()}
    tid = folded.get(s.casefold())
    if tid is None:
        raise SdkError("usage_error", provider="fr_amf",
                       detail=f"unknown theme {theme!r} — pass one of the measured names "
                              f"({', '.join(sorted(THEMES))}) or a taxonomy tid")
    return tid


def row_from_upstream(d, kind):
    """Card mapping (pure function — split out for offline testing). kind 'sanction'|'transaction'."""
    infos = d.get("infos") or {}
    dl = ((infos.get("download") or {}).get("sanction") or {}).get("links") or {}
    row = {
        "id": infos.get("title"),
        "decision_date": _iso_from_unix(d.get("date")),
        "decision_ts": int(d.get("date")) if str(d.get("date") or "").isdigit() else None,
        "theme": _strip_html(d.get("theme")),
        "source_url": _abs((infos.get("link") or {}).get("url")),
        "pdf_url": _abs(dl.get("url")),
        "pdf_label": dl.get("text"),
        "legend": _strip_html(infos.get("legend")) or None,
    }
    if kind == "sanction":
        row["parties"] = [p for p in (_strip_html(x) for x in _BR.split(infos.get("text_egard") or "")) if p]
        row["amount_text"] = _strip_html(infos.get("text"))
        rec = str(infos.get("recours") or "").strip().lower()
        row["appealed"] = {"oui": True, "non": False}.get(rec)
    else:
        row["actor"] = _strip_html(infos.get("text_acteur"))
        row["amount_text"] = _strip_html(infos.get("text"))
        total = str(infos.get("total") or "").strip()
        row["amount_numeric"] = float(total) if re.fullmatch(r"-?\d+(\.\d+)?", total) else None
    return row


def _listing_raw(op, kind, theme, date_from, date_to, cache=None, no_cache=False):
    tid = resolve_theme(theme)
    lo = _parse_date(date_from) or 0
    hi = _parse_date(date_to) or 9999999999
    if lo > hi:
        raise SdkError("usage_error", provider="fr_amf",
                       detail=f"date_from {date_from!r} is after date_to {date_to!r}")
    from ..transport import call_provider
    r = call_provider(provider, op, {"theme": tid, "date_from": lo, "date_to": hi},
                      cache=cache, no_cache=no_cache)
    doc = r["data"]
    if isinstance(doc, dict):
        doc = doc.get("data")
    if not isinstance(doc, list):
        raise SdkError("upstream_unavailable", provider="fr_amf",
                       detail=f"listing_{kind} answered an unexpected shape (no data list — "
                              f"the REST family may have moved; re-probe /fr/rest/listing_{kind}/all/all/all)")
    return {"kind": kind, "theme": None if tid == "all" else tid,
            "date_from": date_from, "date_to": date_to,
            "total": len(doc),
            "rows": [row_from_upstream(x, kind) for x in doc],
            "params": {"theme": tid, "date_from": lo, "date_to": hi},
            "_meta": r}


def sanctions_raw(theme=None, *, date_from=None, date_to=None, cache=None, no_cache=False):
    """→ {kind, theme, date_from, date_to, total, rows[], params, _meta}. Full stream = 454 rows
    in one shot (no pagination upstream — narrow with theme tid and/or the ISO date window)."""
    return _listing_raw("sanctions", "sanction", theme, date_from, date_to,
                        cache=cache, no_cache=no_cache)


def transactions_raw(theme=None, *, date_from=None, date_to=None, cache=None, no_cache=False):
    """→ same envelope, kind 'transaction' (138 rows live — the REST body runs richer than the
    sitemap's 121). total is absent ('' ) on transaction cards — amount_numeric is the number."""
    return _listing_raw("transactions", "transaction", theme, date_from, date_to,
                        cache=cache, no_cache=no_cache)


def taxonomy_raw(kind="sanction", *, cache=None, no_cache=False):
    """→ the live tid map: [{name, tid}...] (kind 'sanction' measured; the embedded THEMES map
    mirrors it for the theme-name sugar)."""
    k = str(kind or "sanction").strip() or "sanction"
    if k not in ("sanction", "transaction"):
        raise SdkError("usage_error", provider="fr_amf",
                       detail=f"kind must be 'sanction' or 'transaction', got {kind!r}")
    from ..transport import call_provider
    r = call_provider(provider, "taxonomy", {"kind": k}, cache=cache, no_cache=no_cache)
    doc = r["data"]
    if not isinstance(doc, list):
        raise SdkError("upstream_unavailable", provider="fr_amf",
                       detail="taxonomy answered an unexpected shape (no list)")
    return {"kind": k, "themes": [{"name": e.get("name"), "tid": e.get("tid")}
                                  for e in doc if isinstance(e, dict)],
            "params": {"kind": k}, "_meta": r}
