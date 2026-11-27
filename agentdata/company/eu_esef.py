"""eu_esef — ESEF filings register + XBRL-JSON financial facts (filings.xbrl.org, keyless; 0.3.74 batch E16).

filings.xbrl.org is the public registry of European Single Electronic Format annual reports
(EU Transparency Directive — every EEA-listed issuer files an inline-XBRL annual financial
report since FY2021). A JSON:API (content-type application/vnd.api+json) serves the register;
the processed reports are downloadable as XBRL-JSON — structured IFRS facts per issuer.

2026-11-23 probed laws (tmp/probe-e16/):
  - RESOURCES: filing /api/filings, entity /api/entities/{LEI}; page[size] default 30, max
    1000 (1001 -> 400 "Page size must be between 1 and 1000. For bulk downloads of filings,
    use the index files"); page[number] from 1 (0 = first page; -1 -> 400); beyond the last
    page -> 200 with an empty data[] and the unchanged meta.count.
  - FILTER GRAMMAR: filter=<urlencoded JSON list> of {"name","op","val"} (all must match):
    entity.identifier eq <LEI> (THE per-issuer query — `lei` and `entity_id` are refused
    "filing has no attribute"), entity.name ilike %text%, country in [..], period_end ge/le/eq,
    processed ge, date_added ge/le, fxo_id eq, sha256 eq. URL-building order matters:
    a filter needs sorting (sort=-processed measured).
  - PUBLISHED IS SPARSE: `published` is null on 23,630 of 27,815 filings — on EVERY GB row
    (2,982) — and nulls sort first under sort=-published. date_added (date-only) is the
    practical filing date; the SDK exposes no published filter or sort.
  - RATE CLAMP (undocumented): HTTP 429 "Too Many Requests" (Apache HTML, no Retry-After)
    above ~10 requests per rolling 60 s, 4xx included — 7.5 s spacing answers zero 429s.
    The upstream asks routine API users for a contact-bearing User-Agent (the SDK's default
    UA stays generic; an end user may set AGENTDATA_CONTACT).
  - CORPUS: 27,817 filings / 7,505 entities / 28 countries. UA 9,908 (EDRPOU-coded rows,
    fxo_id "EDRPOU-…", mostly no package), GB 2,982 (806 issuers), DK 2,247, SE 1,841, NO
    1,199, FR 1,188, FI 1,169…; DE and IE file nothing here. fxo_id suffix -0 = original,
    -1/-2… = amended filings (2,633 entity-periods carry more than one, max 8).
  - ARTEFACTS: viewer_url / package_url / report_url / json_url are site-relative
    (prefix https://filings.xbrl.org); json_url is null on 289 rows (processing failed);
    package_url is a .zip (GB 2,930) or .xbri (GB 52). Plain GET, no Accept-Encoding
    (identity forces a slow path on the index files), Range is not honoured.
  - XBRL-JSON FACT SHAPE: facts{<id>: {value: "<string>", decimals: <int>?, dimensions:
    {concept: "ifrs-full:Revenue", entity: "scheme:<LEI>", period, unit: "iso4217:GBP"
    | "iso4217:X/xbrli:shares", language: "en" (text facts), <axis>: <member>…}}}.
    PERIOD LAW: durations are END-EXCLUSIVE ("2025-01-01T00:00:00/2026-01-01T00:00:00" =
    FY2025) and instants are the midnight AFTER the balance-sheet date ("2026-01-01T00:00:00"
    = as at 2025-12-31) — both normalise to the inclusive calendar end (minus one day).
    Numeric facts carry `unit`; text facts carry `language` and no unit.

Politeness 0.1 rps (6/min, under the observed 10/min clamp), burst 2. TTLs: filings list 6h,
filing record 1h (json_url fills in when processing completes), facts 7d (immutable per id).
"""
import datetime
import json
import re

from ..errors import SdkError

ID = "eu_esef"
BASE = "https://filings.xbrl.org"

provider = {
    "id": ID,
    "baseUrl": BASE,
    "rate": {"rps": 0.1, "burst": 2},
    "ops": {
        "filings": {"path": "/api/filings", "timeout": 60.0},
        "filing": {"path": "/api/filings/{filing_id}", "timeout": 60.0, "notFound": [404]},
        # {url} substitutes a FULL https://filings.xbrl.org/… URL (extension 10): the
        # XBRL-JSON path carries the filing's own file name and is known only from the
        # filing record (json_url) — never built here. Largest measured: 18.9 MB
        "facts": {"path": "{url}", "timeout": 180.0},
    },
    "ttl": {"filings": 21600, "filing": 3600, "facts": 7 * 86400},
}

_LEI = re.compile(r"^[A-Z0-9]{20}$")
_CC = re.compile(r"^[A-Z]{2}$")
_NUM = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")
_INT = re.compile(r"^-?\d+$")
_FXO = re.compile(r"-ESEF-[A-Z]{2}-(\d+)$")

SORTS = ("processed", "period_end", "date_added", "country", "fxo_id", "warning_count")


def _list(value):
    if value is None:
        return []
    return [v for v in (value if isinstance(value, (list, tuple)) else [value])
            if v is not None and str(v).strip() != ""]


def _date(value, name):
    s = str(value).strip()
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        raise SdkError("usage_error", provider=ID, detail=f"{name} must be YYYY-MM-DD, got {value!r}")
    return s


def _int(value, name, lo, hi=None, default=None):
    if value is None or str(value).strip() == "":
        return default
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider=ID, detail=f"{name} must be an integer, got {value!r}")
    if n < lo or (hi is not None and n > hi):
        rng = f">={lo}" if hi is None else f"{lo}-{hi}"
        raise SdkError("usage_error", provider=ID, detail=f"{name} must be {rng}, got {value!r}")
    return n


def _lei(value):
    """20-char LEI (accepted in any case; entity.identifier is stored uppercase)."""
    s = str(value).strip().upper().replace(" ", "")
    if not _LEI.match(s):
        raise SdkError("usage_error", provider=ID, detail=f"lei must be a 20-character LEI, got {value!r}")
    return s


# —— filings list ——

def filing_filters(*, lei=None, name=None, country=None, period_end=None, period_from=None,
                   period_to=None, added_from=None, added_to=None, fxo_id=None):
    """the JSON-list filter (pure): every entry must match."""
    fl = []
    if lei:
        fl.append({"name": "entity.identifier", "op": "eq", "val": _lei(lei)})
    if name:
        fl.append({"name": "entity.name", "op": "ilike", "val": "%" + " ".join(str(name).split()) + "%"})
    cs = [str(c).strip().upper() for c in _list(country)]
    for c in cs:
        if not _CC.match(c):
            raise SdkError("usage_error", provider=ID,
                           detail=f"country must be an ISO 3166-1 alpha-2 code (GB, DE, SE…), got {c!r}")
    if cs:
        fl.append({"name": "country", "op": "in", "val": cs})
    if period_end:
        fl.append({"name": "period_end", "op": "eq", "val": _date(period_end, "period_end")})
    if period_from:
        fl.append({"name": "period_end", "op": "ge", "val": _date(period_from, "period_from")})
    if period_to:
        fl.append({"name": "period_end", "op": "le", "val": _date(period_to, "period_to")})
    if added_from:
        fl.append({"name": "date_added", "op": "ge", "val": _date(added_from, "added_from")})
    if added_to:
        fl.append({"name": "date_added", "op": "le", "val": _date(added_to, "added_to")})
    if fxo_id:
        fl.append({"name": "fxo_id", "op": "eq", "val": str(fxo_id).strip()})
    return fl


def _dumps(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def filing_row(item, included=None):
    """one JSON:API filing resource -> row (pure): attributes verbatim with the four artefact
    URLs made absolute, + filing_id / lei / entity_name / api_url / amendment /
    identifier_type (UA rows are EDRPOU-coded, not LEIs)."""
    a = dict(item.get("attributes") or {})
    rel = item.get("relationships") or {}
    ent = rel.get("entity") or {}
    lei = str((ent.get("links") or {}).get("related") or "").rstrip("/").rsplit("/", 1)[-1] or None
    inc = (included or {}).get(((ent.get("data") or {}).get("id")))
    for k in ("viewer_url", "package_url", "report_url", "json_url"):
        if a.get(k):
            a[k] = str(a[k]) if str(a[k]).startswith("http") else BASE + str(a[k])
    fid = item.get("id")
    try:
        fid = int(fid)
    except (TypeError, ValueError):
        pass
    m = _FXO.search(str(a.get("fxo_id") or ""))
    vm = str(((rel.get("validation_messages") or {}).get("links") or {}).get("related") or "")
    row = {"filing_id": fid}
    row.update(a)
    row.update({
        "lei": lei,
        "entity_name": ((inc or {}).get("attributes") or {}).get("name") if inc else None,
        "api_url": f"{BASE}/api/filings/{fid}",
        "validation_messages_url": (BASE + vm) if vm else None,
        # -0 = the original filing, -1/-2… = amendments of the same entity period
        "amendment": int(m.group(1)) if m else None,
        "identifier_type": "EDRPOU" if (lei or "").startswith("EDRPOU-") else ("LEI" if lei else None),
    })
    return row


def filing_page(doc, params, page, size):
    """one JSON:API page of filings -> the result envelope (pure). Beyond the last page the
    upstream answers an empty data[] with the unchanged meta.count."""
    if not isinstance(doc, dict) or not isinstance(doc.get("data"), list):
        raise SdkError("upstream_unavailable", provider=ID,
                       detail="filings.xbrl.org answered an unexpected shape (no JSON:API data[]) — "
                              "the API layout may have moved; re-probe")
    included = {e.get("id"): e for e in (doc.get("included") or []) if isinstance(e, dict)}
    rows = [filing_row(x, included) for x in doc["data"] if isinstance(x, dict) and x.get("type") == "filing"]
    total = (doc.get("meta") or {}).get("count")
    total = total if isinstance(total, int) else None
    out = {"total": total, "page": page, "limit": size, "row_count": len(rows), "rows": rows,
           "params": params}
    if total is not None:
        out["pages"] = (total + size - 1) // size
        out["next_page"] = page + 1 if page * size < total else None
    return out


def filings(*, lei=None, name=None, country=None, period_end=None, period_from=None, period_to=None,
            added_from=None, added_to=None, fxo_id=None, sort="processed", order="desc", page=1,
            limit=30, cache=None, no_cache=False):
    """→ {total, page, limit, pages, row_count, rows[], next_page, params, _meta}; the ESEF
    filings register — 27,817 annual reports from 7,505 EEA issuers (GB 2,982 filings / 806
    issuers, DK 2,247, SE 1,841, NO 1,199, FR 1,188…; DE and IE absent). One row per filing:
    period_end, country, fxo_id (suffix -0 original, -1… amended), date_added, processed,
    error/warning/inconsistency counts and the absolute viewer / package (zip) / report
    (inline XHTML) / json (XBRL-JSON) URLs. lei is exact (entity.identifier), name a
    case-insensitive substring of the issuer name, country a repeatable ISO alpha-2,
    period_end exact or period_from…period_to (inclusive), added_from / added_to the filing
    date range, fxo_id exact. sort processed (default, desc = the latest processed first) |
    period_end | date_added | country | fxo_id | warning_count; page 1-based, limit <= 1000
    (the upstream's documented max — for bulk, the upstream points to its index files)."""
    from ..transport import call_provider

    fl = filing_filters(lei=lei, name=name, country=country, period_end=period_end,
                        period_from=period_from, period_to=period_to, added_from=added_from,
                        added_to=added_to, fxo_id=fxo_id)
    if sort not in SORTS:
        raise SdkError("usage_error", provider=ID,
                       detail=f"sort must be one of {' | '.join(SORTS)}, got {sort!r}")
    if order not in ("asc", "desc"):
        raise SdkError("usage_error", provider=ID, detail=f"order must be asc or desc, got {order!r}")
    size = _int(limit, "limit", 1, 1000, 30)
    pg = _int(page, "page", 1, default=1)
    params = {"page[size]": size, "page[number]": pg, "include": "entity",
              "sort": ("-" if order == "desc" else "") + sort}
    if fl:
        params["filter"] = _dumps(fl)
    r = call_provider(provider, "filings", params, cache=cache, no_cache=no_cache)
    out = filing_page(r["data"], params, pg, size)
    out["_meta"] = r
    return out


# —— XBRL-JSON facts ——

_CORE = ("concept", "entity", "period", "unit")


def fact_period(raw):
    """the period law: a duration 'A/B' is end-exclusive, an instant 'B' is the midnight after
    the balance-sheet date -> (period_type, period_start, inclusive period_end, days)."""
    p = str(raw or "")
    try:
        if "/" in p:
            a, _, b = p.partition("/")
            start = datetime.date.fromisoformat(a[:10])
            end = datetime.date.fromisoformat(b[:10])
            return "duration", start.isoformat(), (end - datetime.timedelta(days=1)).isoformat(), (end - start).days
        end = datetime.date.fromisoformat(p[:10])
        # only a midnight instant is the ESEF end-of-day form; a timed instant keeps its date
        time = p[11:]
        if time.startswith("00:00:00"):
            end -= datetime.timedelta(days=1)
        return "instant", None, end.isoformat(), None
    except ValueError:
        return "unknown", None, None, None


def _number(value):
    s = str(value)
    if _INT.match(s):
        return int(s)
    if _NUM.match(s):
        return float(s)
    return None


def fact_row(fact_id, fact):
    """one XBRL-JSON fact -> row (pure). value stays the upstream string (no precision loss);
    value_num is the numeric companion; dimensions holds the extra axes only (the entity-level
    fact of a consolidated statement has none)."""
    d = fact.get("dimensions") or {}
    concept = str(d.get("concept") or "")
    ptype, pstart, pend, days = fact_period(d.get("period"))
    value = fact.get("value")
    row = {"fact_id": fact_id, "concept": concept, "value": value,
           "value_num": _number(value) if not isinstance(value, (dict, list)) else None,
           "decimals": fact.get("decimals"), "unit": d.get("unit"),
           "period_type": ptype, "period_start": pstart, "period_end": pend, "days": days,
           "entity": str(d.get("entity") or "").replace("scheme:", "", 1) or None}
    extra = {k: v for k, v in d.items() if k not in _CORE}
    if extra:
        row["dimensions"] = extra
    if "format" in fact:
        row["format"] = fact["format"]
    return row


def _concept_match(concept, concepts):
    if not concepts:
        return True
    c = concept.lower()
    local = c.rsplit(":", 1)[-1]
    for want in concepts:
        w = str(want).strip().lower()
        if w.endswith("*"):
            pre = w[:-1]
            if pre and (c.startswith(pre) or local.startswith(pre)):  # 'Revenue*' catches the
                return True  # prefixed local name too, whatever the taxonomy prefix is
            continue
        if w and (c == w or local == w):
            return True
    return False


def fact_rows(doc, *, period_end=None, all_periods=False, annual_only=True, include_dimensions=False,
              include_text=False, concepts=None):
    """the XBRL-JSON document -> fact rows (pure), sorted by concept then period. Default view
    = the filing's own reporting period: numeric facts, entity-level (no dimensional
    qualifiers), instants + ~annual durations (348-380 days)."""
    if not isinstance(doc, dict) or not isinstance(doc.get("facts"), dict):
        raise SdkError("upstream_unavailable", provider=ID,
                       detail="the XBRL-JSON artefact answered an unexpected shape (no facts{}) — "
                              "re-probe the json_url payload")
    wants = [c for c in _list(concepts)]
    rows = []
    for fid, f in doc["facts"].items():
        if not isinstance(f, dict) or not isinstance(f.get("dimensions"), dict):
            continue
        d = f["dimensions"]
        value = f.get("value")
        numeric = ("unit" in d) or (isinstance(value, str) and bool(_NUM.match(value)))
        if not numeric and not include_text:
            continue
        if not include_dimensions and any(k not in _CORE for k in d):
            continue
        if not _concept_match(str(d.get("concept") or ""), wants):
            continue
        row = fact_row(fid, f)
        if row["period_end"] is None:
            continue
        if not all_periods and row["period_end"] != period_end:
            continue
        if annual_only and row["period_type"] == "duration" and not (348 <= (row["days"] or 0) <= 380):
            continue
        rows.append(row)
    rows.sort(key=lambda x: (x["concept"], x["period_end"], x["fact_id"]))
    return rows


def _json_url(card):
    """the filing's XBRL-JSON artefact as a FULL URL (extension 10) — null json_url means the
    upstream processing failed; the artefact must stay on the filings.xbrl.org host."""
    url = card.get("json_url")
    if not url:
        n = card.get("_same_period_count") or 1
        raise SdkError("upstream_not_found", provider=ID,
                       detail=f"{card.get('entity_name') or card.get('lei')} period {card.get('period_end')}: "
                              f"{'none of the ' + str(n) + ' filings' if n > 1 else 'the filing'} "
                              f"{card.get('fxo_id')} has no XBRL-JSON artefact (json_url is null — the "
                              "upstream processing failed; the package / report links are on the "
                              "eu_esef_filings row)")
    if not str(url).startswith(BASE + "/"):
        raise SdkError("upstream_unavailable", provider=ID,
                       detail=f"json_url left the filings.xbrl.org host ({str(url)[:120]!r}) — not fetched; re-probe")
    return str(url)


def facts(*, filing_id=None, lei=None, period_end=None, concept=None, all_periods=False,
          annual_only=True, include_dimensions=False, include_text=False, limit=None,
          cache=None, no_cache=False):
    """→ {filing, fact_count, matched_count, row_count, rows[], params, _meta, _metas};
    the structured IFRS facts of one ESEF annual report as compact rows (concept, value,
    value_num, decimals, unit, period, entity, dimensions). Select the report by filing_id
    (the numeric ESEF filing id) OR by issuer lei (the latest period_end filed, or the given
    period_end; where a period has amendments the latest processed filing with a JSON
    artefact wins). Default view = the report's own period, numeric entity-level facts,
    instants + annual durations; concept filters (repeatable: "ifrs-full:Revenue", a bare
    local name, or a "Revenue*" prefix — issuers tag either ifrs-full:Revenue or
    ifrs-full:RevenueFromContractsWithCustomers, so the wildcard is the issuer-agnostic form),
    all_periods adds the comparative periods,
    include_dimensions keeps segment / axis breakdowns, include_text adds text blocks.
    Rows are sorted by concept then period; limit slices locally."""
    from ..transport import call_provider

    has_id = filing_id is not None and str(filing_id).strip() != ""
    has_lei = lei is not None and str(lei).strip() != ""
    if has_id == has_lei:
        raise SdkError("usage_error", provider=ID,
                       detail="pass exactly one of filing_id (a numeric ESEF filing id from eu_esef_filings) "
                              "or lei (a 20-character issuer LEI)")
    metas = []
    if has_id:
        fid = _int(filing_id, "filing_id", 1)
        try:
            r1 = call_provider(provider, "filing", {"filing_id": fid, "include": "entity"},
                               cache=cache, no_cache=no_cache)
        except SdkError as e:
            if e.code == "upstream_not_found":
                raise SdkError("upstream_not_found", provider=ID,
                               detail=f"no ESEF filing with id {fid} — filing ids are the numeric ids on "
                                      "eu_esef_filings rows") from None
            raise
        metas.append(r1)
        doc = r1["data"]
        res = doc.get("data") if isinstance(doc, dict) else None
        if not isinstance(res, dict) or res.get("type") != "filing":
            raise SdkError("upstream_unavailable", provider=ID,
                           detail="filings.xbrl.org answered an unexpected shape on /api/filings/{id} — re-probe")
        inc = {e.get("id"): e for e in (doc.get("included") or []) if isinstance(e, dict)}
        card = filing_row(res, inc)
    else:
        L = _lei(lei)
        wanted = _date(period_end, "period_end") if period_end else None
        found, pg = [], 1
        while True:  # the most filings measured per issuer is 34 — one page of 100
            params = {"page[size]": 100, "page[number]": pg, "include": "entity", "sort": "-period_end",
                      "filter": _dumps([{"name": "entity.identifier", "op": "eq", "val": L}])}
            r = call_provider(provider, "filings", params, cache=cache, no_cache=no_cache)
            metas.append(r)
            env = filing_page(r["data"], params, pg, 100)
            found.extend(env["rows"])
            if not env["rows"] or (env["total"] is not None and len(found) >= env["total"]) or pg >= 5:
                break
            pg += 1
        if not found:
            raise SdkError("upstream_not_found", provider=ID,
                           detail=f"no ESEF filing for LEI {L} — the ESEF register holds EEA issuers' annual "
                                  "reports (DE and IE file none; UA rows are EDRPOU-coded); the LEI may belong "
                                  "to an issuer outside the regime")
        wanted = wanted or found[0].get("period_end")
        same = [c for c in found if c.get("period_end") == wanted]
        if not same:
            ends = sorted({str(c.get("period_end")) for c in found if c.get("period_end")}, reverse=True)
            raise SdkError("usage_error", provider=ID,
                           detail=f"no ESEF filing with period_end {wanted} for {found[0].get('entity_name') or L}; "
                                  f"filed period ends: {', '.join(ends[:12])}")
        with_json = [c for c in same if c.get("json_url")]
        card = max(with_json or same, key=lambda c: (str(c.get("processed") or ""), c.get("filing_id") or 0))
        card = dict(card)
        card["_same_period_count"] = len(same)
    url = _json_url(card)
    card = {k: v for k, v in card.items() if not k.startswith("_")}
    r = call_provider(provider, "facts", {"url": url}, cache=cache, no_cache=no_cache)
    doc = r["data"]
    rows = fact_rows(doc, period_end=card.get("period_end"), all_periods=all_periods,
                     annual_only=annual_only, include_dimensions=include_dimensions,
                     include_text=include_text, concepts=concept)
    matched = len(rows)
    if limit is not None and int(limit) >= 0:
        rows = rows[: int(limit)]
    return {"filing": card, "fact_count": len(doc["facts"]) if isinstance(doc, dict) and isinstance(doc.get("facts"), dict) else None,
            "matched_count": matched, "row_count": len(rows), "rows": rows,
            "params": {"filing_id": card.get("filing_id"), "lei": card.get("lei"), "fxo_id": card.get("fxo_id"),
                       "period_end": card.get("period_end"), "fact_period_end": None if all_periods else card.get("period_end"),
                       "concept": _list(concept) or None, "all_periods": bool(all_periods),
                       "annual_only": bool(annual_only), "include_dimensions": bool(include_dimensions),
                       "include_text": bool(include_text), "limit": limit},
            "_meta": r, "_metas": metas + [r]}
