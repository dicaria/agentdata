"""gg_gfsc — Guernsey GFSC regulated & registered-business registers (www.gfsc.gg; keyless JSON feeds).

Two faces (0.3.33; probed 2026-11-04, tmp/probe-company-0333/; research volumes gg-gfsc-registry +
je-jfsc-registry, offshore Channel-Islands regulated-registers batch):

  * regulated_entities — the full regulated-entities feed. GET /gfsc-company/feed/regulated →
    {"companies": […]} 3,795 rows / 2.4MB. **The display fields are HTML-embedded**: name,
    GFSC_x0020_Ref, Licences and View each arrive as `<a href="…">text</a>` (name even carries a
    leading "\t" on some rows) — the face strips the tags and keeps the register's own detail path
    (the href, /commission/regulated-entities/<ref>). The plain-text twin of Licences is Filters —
    the licence-group label **verbatim, commas included**: "Secondary Licensee, Pension Provider"
    is ONE combined group label (43 rows), not two licences.
  * registered_businesses — GET /gfsc-company/feed/registeredbusiness → 133 rows, the same shape
    minus status/surrendered/GreenFund; Filters = the prescribed-business category (Accountant 74 /
    Estate Agent 22 / Money Service Providers 20 / Legal Professional 17). 23 refs also appear on
    the regulated feed (dual-listed entities).

Row granularity is the feed's own trap, pinned live: **one entity = one row per licence group** —
26 refs sit on 2+ rows (e.g. ref 2293247 "1818 Venture Capital Limited": an Investment Licensee
row surrendered=0 + a revoked Primary Licensee row surrendered=1). The envelope therefore counts
total_matched (rows) and entities_matched (distinct refs) side by side. surrendered is a "0"/"1"
**string** on the wire → bool here. Status is null (1,571 rows) more often than Active (1,579) or
Inactive (645) — null is the register stating nothing, not missing data. **GFSC refs are not
uniformly 7-digit**: legacy 5-6-digit refs exist (16020, 80277, 134767) — the ref filter matches
the digit string exactly, with no length assumption. The feed-internal `id` is unique per row
(1..5177) and distinct from the public ref.
Licence (gate 6): the GFSC /copyright page sets no reuse restriction on the register data.

Channel: plain GET JSON, no key, no CAPTCHA, no published rate window → polite 0.5 rps / burst 2
(registry-search family posture). TTL 24h both feeds (the register dumps move slowly; the feed is
the site search's own backing store).
"""
import html
import re

from ..errors import SdkError

provider = {
    "id": "gg_gfsc",
    "baseUrl": "https://www.gfsc.gg",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "regulated": {"path": "/gfsc-company/feed/regulated", "timeoutMs": 90000},
        "registered_businesses": {"path": "/gfsc-company/feed/registeredbusiness", "timeoutMs": 90000},
    },
    "ttl": {"regulated": 24 * 3600, "registered_businesses": 24 * 3600},
}

_TAG_RE = re.compile(r"<[^>]+>")
_HREF_RE = re.compile(r'href="([^"]+)"')


def _text(field):
    """HTML-embedded display field → (text, href): the feed ships name/ref/licences/View as
    <a href="…">text</a>; the text may carry stray tabs (name row0 does)."""
    raw = str(field or "")
    m = _HREF_RE.search(raw)
    href = m.group(1) if m else None
    txt = " ".join(html.unescape(_TAG_RE.sub("", raw)).split())
    return (txt or None), href


def _flag(v):
    """surrendered is a "0"/"1" string on the wire → bool (no third value measured)."""
    s = str(v or "").strip()
    return True if s == "1" else False if s == "0" else None


def _yes(v):
    """GreenFund / Natural_Capital_Fund: "Yes" / null → bool / None."""
    return v == "Yes" if isinstance(v, str) else None


def _detail_path(row, fallback):
    """The register's own detail page: the href out of View (all display-field hrefs agree per
    row; View is the dedicated link field, the rest are fallbacks)."""
    m = _HREF_RE.search(str(row.get("View") or ""))
    return m.group(1) if m else fallback


def _map_regulated(raw):
    name, name_href = _text(raw.get("name"))
    ref, _ = _text(raw.get("GFSC_x0020_Ref"))
    return {
        "id": str(raw.get("id") or "") or None,          # feed-internal row id, unique per row
        "ref": ref,                                       # GFSC ref, digits (legacy 5-6-digit exist)
        "name": name,
        "licence": str(raw.get("Filters") or "").strip() or None,   # group label verbatim, commas included
        "status": raw.get("Status") or None,              # None/Active/Inactive — null = register states nothing
        "surrendered": _flag(raw.get("surrendered")),
        "green_fund": _yes(raw.get("GreenFund")),
        "natural_capital_fund": _yes(raw.get("Natural_Capital_Fund")),
        "detail_path": _detail_path(raw, name_href),
    }


def _map_registered(raw):
    name, name_href = _text(raw.get("name"))
    ref, _ = _text(raw.get("GFSC_x0020_Ref"))
    return {
        "id": str(raw.get("id") or "") or None,
        "ref": ref,
        "name": name,
        "category": str(raw.get("Filters") or "").strip() or None,
        "detail_path": _detail_path(raw, name_href),
    }


def rows_from_upstream(data, feed):
    """Upstream {"companies": […]} → flat rows (pure function; the HTML strip + the href rescue
    happen here so the face rows are plain JSON)."""
    mapper = _map_regulated if feed == "regulated" else _map_registered
    return [mapper(x) for x in ((data or {}).get("companies") or []) if isinstance(x, dict)]


def filter_rows(rows, name=None, licence=None, status=None, surrendered=None, ref=None,
                category=None):
    """Local register scan (pure function). name: contains (case-insensitive); licence/category:
    contains over the group/category label (labels embed commas — filter on the token, e.g.
    'Insurer' or 'Pension Provider'); status: exact ACTIVE/INACTIVE (null-status rows match
    neither); surrendered: True/False over the flag; ref: exact digit-string match (no length
    assumption — legacy refs are 5-6 digits)."""
    nm = str(name or "").strip().lower() or None
    lc = str(licence or category or "").strip().lower() or None
    st = str(status or "").strip().upper() or None
    rf = str(ref or "").strip() or None
    hits = []
    for r in rows:
        if st and str(r.get("status") or "").strip().upper() != st:
            continue
        if surrendered is not None and r.get("surrendered") != bool(surrendered):
            continue
        if rf and r.get("ref") != rf:
            continue
        if lc and lc not in str(r.get("licence") or r.get("category") or "").lower():
            continue
        if nm and nm not in str(r.get("name") or "").lower():
            continue
        hits.append(r)
    return hits


def _norm_limit(limit):
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="gg_gfsc",
                       detail=f"limit must be 1-100 (local payload wall after the full-feed scan), got '{limit}'")
    return size


def _scan(op, feed, *, name=None, licence=None, status=None, surrendered=None, ref=None,
          category=None, limit=20, cache=None, no_cache=False):
    """Shared full-feed scan → {rows, total_matched, entities_matched, scanned_rows, limit_applied,
    params, _meta}. One entity = one row per licence group, so rows and distinct refs are counted
    side by side."""
    from ..transport import call_provider

    size = _norm_limit(limit)
    r = call_provider(provider, op, {}, cache=cache, no_cache=no_cache)
    rows = rows_from_upstream(r["data"], feed)
    hits = filter_rows(rows, name=name, licence=licence, status=status,
                       surrendered=surrendered, ref=ref, category=category)
    return {"rows": hits[:size], "total_matched": len(hits),
            "entities_matched": len({h["ref"] for h in hits if h["ref"]}),
            "scanned_rows": len(rows), "limit_applied": size,
            "params": {"name": name, "licence": licence, "status": status,
                       "surrendered": surrendered, "ref": ref, "category": category},
            "_meta": r}


def regulated_entities_raw(name=None, *, licence=None, status=None, surrendered=None, ref=None,
                           limit=20, cache=None, no_cache=False):
    """Regulated-entities register scan → the envelope (see _scan). status: ACTIVE/INACTIVE exact
    (null rows — 41% of the feed — match neither, honestly)."""
    return _scan("regulated", "regulated", name=name, licence=licence, status=status,
                 surrendered=surrendered, ref=ref, limit=limit, cache=cache, no_cache=no_cache)


def registered_businesses_raw(name=None, *, category=None, ref=None, limit=20,
                              cache=None, no_cache=False):
    """Registered (prescribed) businesses scan → the envelope (see _scan). category: contains over
    the category label (Accountant / Estate Agent / Money Service Providers / Legal Professional)."""
    return _scan("registered_businesses", "registered", name=name, category=category, ref=ref,
                 limit=limit, cache=cache, no_cache=no_cache)
