"""edgar_xbrl — SEC XBRL structured facts family (companyfacts/companyconcept/frames/tickers; keyless).

data.sec.gov/api/xbrl/* + www.sec.gov/files/company_tickers.json — the quantitative layer under
edgar_cik's registry layer and edgar_fts's document layer: audited values per concept x period,
each fact stamped accn (the filing it was reported in — joins us_sec_submissions/us_sec_fulltext_search
on the accn/CIK keys). Batch E8 (0.3.66) — the 2026-11-17 reopening of the 2026-10-19 deferral:
the local XBRL bulk that ruling leaned on was lost with the E: drive, and the MCP/OmniHub
PATH_ALLOWLIST surface carries no financial-data paths (hub.py §3.5 checked 2026-11-17), so the
structured point-query rides the live API again (user ruling 2026-11-17).
CONCEPT-DRIFT LAW (the family's central law): us-gaap concept names drift across taxonomy
versions — Revenues is dead after 2018 (replaced by
RevenueFromContractWithCustomerExcludingAssessedTax) and issuers simply LACK concepts (Apple has
no EarningsPerShareDiluted) — concept/tag names pass through VERBATIM, never guessed, never
case-normalized; a missing concept answers upstream_not_found (companyconcept 404) or the local
inventory hint (companyfacts), never a fuzzy match.
FY/FP LAW: the fy/fp fields on a fact are the FILING's fiscal year, not the fact period's — a
FY2025 10-K carries FY2024 comparison-period facts stamped fy=2025 (staging-v21-review-sec.md
rule 3); period membership is read off start/end, never off fy/fp.
FRAME LAW: frames periods are CY<year> (duration) / CY<year>Q<n> (quarter duration) /
CY<year>Q<n>I (instant) — nothing else is accepted; the frame answers one concept x unit x
period cross-section in one shot (6,084 entities for NetIncomeLoss CY2024, 2026-11-17 probed).
Fair access: 10 req/s per IP with a declared UA — same 5/5 quota semantics as edgar_cik
(5+5=10<=10, the 0.2.7 realignment); data.sec.gov traffic additionally rides the shared host
bucket (submissions+XBRL combined stay under one polite cap), and tickers rides an ABSOLUTE path
to www.sec.gov (build_url passes absolute op paths through unprefixed — one provider id, two
hosts, each with its own host bucket).
"""
import re

provider = {
    "id": "edgar_xbrl",
    "baseUrl": "https://data.sec.gov",
    "rate": {"rps": 5, "burst": 5},  # same quota semantics as edgar_cik: 5+5x1s=10<=SEC 10 req/s
    "ops": {
        "companyfacts": {"path": "/api/xbrl/companyfacts/CIK{cik10}.json", "notFound": [404]},
        "companyconcept": {"path": "/api/xbrl/companyconcept/CIK{cik10}/{taxonomy}/{tag}.json", "notFound": [404]},
        "frames": {"path": "/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{frame}.json", "notFound": [404]},
        # absolute path — build_url passes it through unprefixed; www.sec.gov gets its own host bucket
        "tickers": {"path": "https://www.sec.gov/files/company_tickers.json", "notFound": [404]},
    },
    "ttl": {"companyfacts": 7 * 86400, "companyconcept": 7 * 86400,
            "frames": 7 * 86400, "tickers": 86400},  # closed-period frames are frozen; the directory churns with registrations
}

_TAG_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")  # us-gaap tags: CamelCase, may carry _ . -
_TAX_RE = re.compile(r"^[A-Za-z][A-Za-z0-9\-_.]*$")  # us-gaap / dei / ffd / srt ...
_FRAME_RE = re.compile(r"^CY\d{4}(?:Q[1-4]I?)?$")  # CY2024 / CY2024Q4 / CY2024Q4I


def _clean_tag(value, what, pattern=_TAG_RE):
    """Verbatim pass-through behind a char-class wall (concept names are never normalized)."""
    from ..errors import SdkError

    v = str(value if value is not None else "").strip()
    if not v or not pattern.match(v):
        raise SdkError("usage_error", provider="edgar_xbrl",
                       detail=f"{what} must match {pattern.pattern} and pass through verbatim "
                              f"(concept names drift across taxonomies — never guess or rewrite them; got \"{value}\")")
    return v


def _cik10(value):
    from .edgar_cik import normalize_cik  # one CIK normalizer for the whole SEC family

    return normalize_cik(value)


def facts_raw(cik10, *, cache=None, no_cache=False):
    """Issuer-level full dump (3-4MB for a large filer — the ttl does the heavy lifting)."""
    from ..transport import call_provider

    return call_provider(provider, "companyfacts", {"cik10": cik10}, cache=cache, no_cache=no_cache)


def concept_raw(cik10, taxonomy, tag, *, cache=None, no_cache=False):
    """Single-concept server-side time series (18KB for Apple revenue — the point query)."""
    from ..transport import call_provider

    return call_provider(provider, "companyconcept", {"cik10": cik10, "taxonomy": taxonomy, "tag": tag},
                         cache=cache, no_cache=no_cache)


def frames_raw(taxonomy, tag, unit, frame, *, cache=None, no_cache=False):
    """One concept x unit x period cross-section (all filers, one shot)."""
    from ..transport import call_provider

    return call_provider(provider, "frames", {"taxonomy": taxonomy, "tag": tag, "unit": unit, "frame": frame},
                         cache=cache, no_cache=no_cache)


def tickers_raw(*, cache=None, no_cache=False):
    """Ticker<->CIK directory (one JSON, ~10.4k rows)."""
    from ..transport import call_provider

    return call_provider(provider, "tickers", {}, cache=cache, no_cache=no_cache)


# ---------- pure shapers (split out for offline testing, card_from_upstream style) ----------

def inventory_from_upstream(d):
    """companyfacts inventory mode: taxonomy -> concept-name list (the drift-discovery face)."""
    facts = d.get("facts") or {}
    taxonomies = {}
    concepts = {}
    for tx in facts:  # dict order = upstream order (dei, us-gaap, ffd for Apple)
        names = list((facts[tx] or {}).keys())
        taxonomies[tx] = len(names)
        concepts[tx] = names
    return {"cik": d.get("cik"), "entity_name": d.get("entityName"), "taxonomies": taxonomies, "concepts": concepts}


def _filter_form(units, form):
    """form filter over every unit list; returns (filtered_units, before, after)."""
    if not form:
        return units, sum(len(v) for v in units.values()), sum(len(v) for v in units.values())
    out = {}
    before = after = 0
    for unit, facts in units.items():
        before += len(facts)
        keep = [f for f in facts if f.get("form") == form]
        after += len(keep)
        if keep:
            out[unit] = keep
    return out, before, after


def _latest_fact(units):
    """Newest filed fact across units (filed-date max; the arrays are filing-order, not period-order)."""
    best = None
    for facts in units.values():
        for f in facts:
            if best is None or str(f.get("filed") or "") > str(best.get("filed") or ""):
                best = f
    return best


def concept_card(entity_name, taxonomy, tag, label, description, units, form):
    """Shared card for companyfacts-concept / companyconcept modes (verbatim units; form filter honest)."""
    units2, before, after = _filter_form(units or {}, form)
    card = {"entity_name": entity_name, "taxonomy": taxonomy, "concept": tag,
            "label": label, "description": description,
            "facts_total": after, "units": units2}
    if form:
        card["facts_before_form_filter"] = before
        card["form_filter"] = form
    latest = _latest_fact(units2)
    if latest:
        card["latest_fact"] = latest
    return card


def concept_from_dump(d, tag, form=None):
    """companyfacts concept mode: find the tag across ALL taxonomies (None when absent — the caller
    raises the inventory hint; taxonomy assignment rides the find, not a guess)."""
    facts = d.get("facts") or {}
    for tx in facts:
        entry = (facts[tx] or {}).get(tag)
        if entry is not None:
            return concept_card(d.get("entityName"), tx, tag, entry.get("label"),
                                entry.get("description"), entry.get("units"), form)
    return None


def concept_from_upstream(d, form=None):
    """companyconcept card (the endpoint answers exactly one taxonomy/tag)."""
    return concept_card(d.get("entityName"), d.get("taxonomy"), d.get("tag"), d.get("label"),
                        d.get("description"), d.get("units"), form)


def frames_from_upstream(d):
    """frames card: meta verbatim + rows verbatim (the cross-section IS the product)."""
    return {"taxonomy": d.get("taxonomy"), "concept": d.get("tag"), "frame": d.get("ccp"),
            "unit": d.get("uom"), "label": d.get("label"), "description": d.get("description"),
            "total": len(d.get("data") or []), "rows": list(d.get("data") or [])}


def tickers_lookup(rows, *, ticker=None, name=None, cik=None):
    """Directory selectors: ticker exact / title substring (case-insensitive) / CIK reverse.
    Row keys renamed cik_str->cik (documented; the rest verbatim)."""
    out = []
    if ticker is not None:
        t = str(ticker).strip().upper()
        out = [r for r in rows if str(r.get("ticker") or "").upper() == t]
    elif name is not None:
        n = str(name).strip().lower()
        out = [r for r in rows if n in str(r.get("title") or "").lower()]
    elif cik is not None:
        want = int(re.sub(r"\D+", "", str(cik)) or 0)
        out = [r for r in rows if int(r.get("cik_str") or 0) == want]
    return [{"cik": r.get("cik_str"), "ticker": r.get("ticker"), "title": r.get("title")} for r in out]
