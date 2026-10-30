"""dgcomp — EU DG COMP competition case register provider (company name → EU competition cases; keyless).

The endpoint is the search backend webgate ES API of the competition-cases.ec.europa.eu portal.
Shape verified 2026-10-20: POST /es/search-api/rest/search/grouped, body = multipart FormData with an
embedded query field = bare ES bool DSL (same as the SPA; first user of the transport form channel, extension 4);
apiKey=CS_PROD_ODSE_PROD is a database label exposed in the public SPA configuration plaintext (not a credential).
Python urllib direct connection verified (webgate is not gated per client stack; Node undici also works — no curl needed).
pageSize hard cap 100: verified 2026-10-26, pageSize=200 → silently returns only 100 rows (verified on the instrument=SA 62k face).
TTL: search 7 days (case cards change slowly); polite rate 0.5 rps (webgate publishes no quota).
"""
from ..errors import SdkError

provider = {
    "id": "dgcomp",
    "baseUrl": "https://webgate.ec.europa.eu/es/search-api/rest",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/search/grouped", "method": "POST", "idempotent": True, "form": "query"},
    },
    "ttl": {"search": 7 * 86400},
}

API_KEY = "CS_PROD_ODSE_PROD"  # static config exposed by the public SPA (not a secret; see module docstring)
# caseInstrument closed set — distinct probe against upstream (webgate ES) 2026-10-21:
#   {AT: 8, M: 6, SA: 2, InstrumentDMA: 4}; term caseInstrument=InstrumentDMA → 55 cases (the DMA.100018 case family).
# The raw DMA value carries the Instrument prefix — guessing "DMA" and firing a term misses (silent 0 rows).
# The closed set comes from upstream probing; do not generalize from first-seen samples
# (lesson: an earlier closed set missed DMA and with it an entire act family).
INSTRUMENTS = {"AT", "M", "SA", "InstrumentDMA"}  # antitrust / merger / state aid / Digital Markets Act (upstream literals)
INSTRUMENT_ALIASES = {"DMA": "InstrumentDMA"}  # human alias → upstream literal (normalized via .upper())
INSTRUMENT_KIND = {"AT": "AT", "M": "M", "SA": "SA", "InstrumentDMA": "DMA"}  # upstream literal → stable short code


def build_query(name=None, instrument=None) -> dict:
    """→ bare ES bool DSL (SPA-identical construction; pure function so the body is offline-testable).
    Company-name search = text query with fields=[caseTitle,caseCompanies,caseOriginalTitle] (copied from the SPA main.js).
    instrument takes the upstream literal (AT/M/SA/InstrumentDMA) or an alias (DMA, case-insensitive), normalized
    to the literal before entering the term."""
    must = []
    q = str(name or "").strip()
    if q:
        must.append({"text": {"fields": ["caseTitle", "caseCompanies", "caseOriginalTitle"],
                              "query": q, "defaultOperator": "AND"}})
    if instrument:
        ins = str(instrument).strip()
        canon = ins if ins in INSTRUMENTS else INSTRUMENT_ALIASES.get(ins.upper())
        if canon not in INSTRUMENTS:
            raise SdkError("usage_error", provider="dgcomp",
                           detail=f"instrument must be AT|M|SA|DMA, got \"{instrument}\"")
        must.append({"term": {"caseInstrument": canon}})
    if not must:
        raise SdkError("usage_error", provider="dgcomp", detail="search_cases requires name / instrument — at least one of the two")
    return {"bool": {"must": must}}


def _first(a):
    return a[0] if isinstance(a, list) and a else None


def search_cases(name=None, *, instrument=None, limit=20, page=1, cache=None, no_cache=False):
    """→ {total, rows[], _meta}; case rows (case_number official key / parties array / decision dates).
    /search/grouped still returns per-document rows (groupById=case number) — deduped client-side by groupById
    into one row per case; the grouped face's totalResults = deduped case count (on the non-grouped face it is the
    document row count, which over-counts) — verified 2026-10-20."""
    from ..transport import call_provider

    size = min(max(1, int(limit or 20)), 100)  # upstream pageSize hard cap 100 (verified 2026-10-26: 200 → silent 100 rows)
    r = call_provider(provider, "search", {
        "query": build_query(name, instrument),
        "apiKey": API_KEY,
        "text": "",  # required query param (the SPA always sends it; empty string = no extra text condition; omitting → 400 businessError, verified 2026-10-20)
        "pageNumber": max(1, int(page or 1)),
        "pageSize": size,
    }, cache=cache, no_cache=no_cache)
    return {**_rows_from(r["data"], size), "_meta": r}


def _rows_from(data, size):
    """Upstream response → deduped case rows (deduped client-side by groupById into one row per case; pure function, offline-testable)."""
    seen, rows = set(), []
    for e in (data or {}).get("results") or []:
        m = e.get("metadata") or {}
        num = _first(m.get("caseNumber")) or e.get("groupById") or e.get("reference")
        if not num or num in seen:
            continue
        seen.add(num)
        ins_raw = _first(m.get("caseInstrument"))
        rows.append({
            "case_number": num,
            "title": _first(m.get("caseOriginalTitle")) or _first(m.get("caseTitle")),  # caseTitle carries <b> highlights — prefer originalTitle
            "instrument": ins_raw,  # upstream literal passed through (AT/M/SA/InstrumentDMA), not rewritten
            "instrument_kind": INSTRUMENT_KIND.get(ins_raw),  # stable short code (AT/M/SA/DMA)
            "member_state": (_first(m.get("caseMemberState")) or "").replace("Country", "") or None,
            "companies": m.get("caseCompanies") or [],  # structured parties (named per AT case; often empty on SA cases — the beneficiary name is in title)
            "sectors_nace": m.get("caseSectors") or [],
            "decision_date": (_first(m.get("caseLastDecisionDate")) or "")[:10] or None,
            "initiation_date": (_first(m.get("caseInitiationDate")) or "")[:10] or None,
            "dg": (_first(m.get("caseDg")) or "").replace("DG_", "", 1).replace("DG", "", 1) or None,
            "url": f"https://competition-cases.ec.europa.eu/search?caseNumber={num}",
        })
    return {"total": (data or {}).get("totalResults"), "rows": rows, "limit_applied": size}


def search_raw(query=None, *, name=None, instrument=None, text="", limit=20, page=1,
               cache=None, no_cache=False):
    """Flat-panel low-level face: query (bare ES bool DSL dict, verbatim-name channel) XOR name/instrument (sugar assembles the DSL).

    → {total, rows[], limit_applied, params, _meta} — params is the exact form body sent (query/apiKey/text/
    pageNumber/pageSize; apiKey = public SPA static label, not a credential). pageSize wall 1-100:
    verified 2026-10-26, pageSize=200 → silently returns only 100 rows (upstream hard cap — walls must fail
    clearly, not clamp silently)."""
    from ..transport import call_provider

    if query is not None and (str(name or "").strip() or instrument):
        raise SdkError("usage_error", provider="dgcomp",
                       detail="query (verbatim-name channel: bare ES bool DSL) and name/instrument (sugar assembles the DSL) are mutually exclusive — give only one")
    dsl = query if query is not None else build_query(name, instrument)  # all empty → at-least-one usage_error
    lim = int(limit or 20)
    if not 1 <= lim <= 100:
        raise SdkError("usage_error", provider="dgcomp",
                       detail=f"limit must be 1-100 (upstream pageSize hard cap: verified 2026-10-26, 200 → silently returns 100 rows), got \"{limit}\"")
    params = {"query": dsl, "apiKey": API_KEY, "text": str(text or ""),
              "pageNumber": max(1, int(page or 1)), "pageSize": lim}
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    return {**_rows_from(r["data"], lim), "params": params, "_meta": r}
