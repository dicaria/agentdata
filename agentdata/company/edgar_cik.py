"""edgar_cik — SEC EDGAR submissions (CIK → registrant identity card; keyless).

data.sec.gov/submissions/CIK##########.json — same source as edgar_fts, different face: FTS handles search,
this file handles normalization (fulltext hits resolve via ciks[0] here; ticker/LEI→CIK closes at the same door).
Official fair-access policy caps at 10 req/s and requires a UA — we set 5 rps/burst 5 (0.2.7 realignment: the old
5/10 worst case was 15>10 in a 1s window, an lda-type violation; quota semantics 5+5=10≤10 stay inside; as with
edgar_fts, the UA is attached uniformly by the transport layer).
Field-value findings confirmed by probing (2026-10-22): business state key = stateOrCountry, not state (the old
read of state made the US state permanently null — Apple=CA was the confirmed live failure); foreign-address state
semantics lives in foreignStateTerritory (Shell plc=DC); ein '000000000' = foreign issuer without EIN sentinel;
person-face empty-string values (sic/category/stateOfIncorporation '') normalize to null; entityType has only the
two values {operating, other} — natural persons (Musk) are also other, not a distinct value.
P1-1 port (2026-10-22): full business key table (three live entities) = street1/street2/city/stateOrCountry/zipCode/
stateOrCountryDescription/isForeignLocation/foreignStateTerritory/country/countryCode — state code and readable name
are two parallel slots (ASML P7→Netherlands; Apple CA→CA; foreign rows fall back to the readable country name
country=United Kingdom; the country key is kept, not always null); filings_total = recent + files[].filingCount
(recent is always truncated at the top).
CIK input tolerance: bare digits / leading zeros / the "CIK0000320193" prefix are all accepted (non-digits stripped,
then padded to 10).
"""
import re

provider = {
    "id": "edgar-cik",
    "baseUrl": "https://data.sec.gov",
    "rate": {"rps": 5, "burst": 5},  # quota semantics at the line: 5+5×1s=10≤SEC 10/s (0.2.7 realignment)
    "ops": {
        "submissions": {"path": "/submissions/CIK{cik10}.json", "notFound": [404]},
    },
    "ttl": {"submissions": 7 * 86400},
}


def normalize_cik(value) -> str:
    """→ 10-digit zero-padded CIK (parity with Node normalizeCik; non 1-10 digit number → usage_error)."""
    from ..errors import SdkError

    digits = re.sub(r"\D+", "", str(value if value is not None else ""))
    if not digits or len(digits) > 10:
        raise SdkError("usage_error", provider="edgar-cik",
                       detail=f"CIK must be 1-10 digits (got \"{value}\")")
    return digits.zfill(10)


def card_from_upstream(d, cik10):
    """Identity card pure mapping (split out for offline testing; key-name fixes and sentinel normalization live in this layer)."""
    recent = (d.get("filings") or {}).get("recent") or {}
    biz = (d.get("addresses") or {}).get("business")
    return {
        "cik": d.get("cik") or cik10,
        "name": d.get("name"),
        "entity_type": d.get("entityType"),
        "tickers": d.get("tickers") or [],
        "exchanges": d.get("exchanges") or [],
        "ein": d.get("ein") if d.get("ein") and d.get("ein") != "000000000" else None,  # foreign sentinel→null
        "sic": ({"code": d["sic"], "description": d.get("sicDescription") or None}
                if d.get("sic") else None),  # person face sic='' is falsy → None
        "filer_category": d.get("category") or None,
        "state_of_incorporation": d.get("stateOfIncorporation") or None,  # empty string → None
        "fiscal_year_end": d.get("fiscalYearEnd"),  # MMDD format (Apple '0926') kept upstream-verbatim
        "former_names": [{"name": f.get("name"),
                          "from": (f.get("from") or "")[:10], "to": (f.get("to") or "")[:10]}
                         for f in (d.get("formerNames") or [])],
        "business_address": ({"city": biz.get("city"),
                              "state_or_country": biz.get("stateOrCountry") or biz.get("foreignStateTerritory"),  # code slot: CA/P7; foreign state semantics = foreignStateTerritory (Shell=DC)
                              "state_or_country_name": biz.get("stateOrCountryDescription") or biz.get("country"),  # readable-name slot: CA/Netherlands; foreign rows fall back to the country name (United Kingdom)
                              "country": biz.get("country")} if biz else None),  # only present for foreign addresses (2026-10-22 live check: Shell carries a real value, do not remove)
        "recent_filings_count": len(recent.get("form") or []),
        "filings_total": (len(recent.get("form") or [])
                          + sum(int(f.get("filingCount") or 0)
                                for f in ((d.get("filings") or {}).get("files") or []))),  # recent is always truncated at ~1000, history pagination lives in files[].filingCount — the two numbers must not be mixed
        "last_filing_date": (recent.get("filingDate") or [None])[0],  # recent arrays are newest-first
    }


def lookup_cik(value, *, cache=None, no_cache=False):
    """→ registrant identity card (legal/former names, tickers·exchanges, EIN, SIC industry, filer category, address)."""
    from ..transport import call_provider

    cik10 = normalize_cik(value)
    r = call_provider(provider, "submissions", {"cik10": cik10}, cache=cache, no_cache=no_cache)
    out = card_from_upstream(r["data"] or {}, cik10)
    out["_meta"] = r
    return out
