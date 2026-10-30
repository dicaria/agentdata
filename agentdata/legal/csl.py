"""csl — US Consolidated Screening List provider (12 list families, 26k rows in one CSV).

Sanctions-screening negative-signal face. data.trade.gov/downloadable_consolidated_screening_list/v1/consolidated.csv:
SDN 19,471 + Entity List 3,419 + DPL 1,596 + ITAR Debarred (DTC) 801 + SSI 286 + MEU 70 etc. — 12 list families
merged into 26,173 rows × 29 columns (full-sweep value domain probed 2026-10-28; the row count drifts as the official
file is regenerated). The official page lists 13 families — FSE (Foreign Sanctions Evaders) is registered but currently
has zero rows in the CSV.
Name screening = **local full-register scan** (upstream search.trade.gov requires a key, not on the roadmap) — pull the
whole 16.8MB CSV once, cache 24h, then any number of screenings run with zero network (the keyless equivalent of
quota-free batch screening).
Multi-value columns are semicolon-delimited (programs/alt_names/addresses/ids/citizenships/places_of_birth);
the type column can be empty on EL/ACN etc. rows; the source filter is a substring match — "ITAR Debarred (DTC)"
contains the "ITAR" substring, so --source ITAR matches (value domain verified 2026-10-28).
Screening semantics: name contains-match (case-insensitive) against both name + alt_names; matched_on echoes the hit face.
0.2.9 audit (2026-10-28): row mapping extended from 15 to 28 columns — remarks (SDN passport/DOB/relationship details
often live only here), places_of_birth×citizenships (identity-disambiguation pair), federal_register_notice (joins the FR
face), license_policy (the upstream spec keeps both columns — mapped through), standard_order, the six vessel fields
(call_sign = alternative vessel identifier key), source_list_url, title — all incorporated.
TTL: screening 24h (official rolling regeneration); polite rate 0.2 rps (single-file face, one pull per day suffices).
"""
import csv
import io

from ..errors import SdkError

provider = {
    "id": "csl",
    "baseUrl": "https://data.trade.gov",
    "rate": {"rps": 0.2, "burst": 1},
    "ops": {
        "screening": {"path": "/downloadable_consolidated_screening_list/v1/consolidated.csv",
                      "accept": "text", "timeoutMs": 180000},
    },
    "ttl": {"screening": 24 * 3600},
}


def _split_semi(v):
    return [x.strip() for x in str(v or "").split(";") if x.strip()]


def rows_from_csv(text):
    """CSV raw text → object rows (header-driven). Returns [] when there is no data row."""
    if not text:
        return []
    reader = csv.reader(io.StringIO(text))
    try:
        head = next(reader)
    except StopIteration:
        return []
    head = [h.strip() for h in head]
    out = []
    for rec in reader:
        if len(rec) != len(head):  # ragged rows with a mismatched column count are dropped
            continue
        out.append(dict(zip(head, rec)))
    return out


def _row_to_screening(o, matched_on, matched_value):
    return {
        "name": o.get("name") or None,
        "alt_names": _split_semi(o.get("alt_names")),
        "matched_on": matched_on,                    # name | alt_names (hit face echo)
        "matched_value": matched_value,              # matched text verbatim (≠ name on the alt_names face)
        "type": o.get("type") or None,               # Entity/Individual/Vessel/Aircraft; empty on EL/ACN etc. rows
        "source_list": o.get("source") or None,      # list family ("Entity List (EL) - Bureau of Industry and Security")
        "programs": _split_semi(o.get("programs")),
        "entity_number": o.get("entity_number") or None,
        "ids": _split_semi(o.get("ids")),            # passport/registration-number identifiers ("Passport X" form)
        "addresses": _split_semi(o.get("addresses")),
        "nationalities": _split_semi(o.get("nationalities")),
        "dates_of_birth": _split_semi(o.get("dates_of_birth")),
        "vessel_owner": o.get("vessel_owner") or None,
        "license_requirement": o.get("license_requirement") or None,
        "license_policy": o.get("license_policy") or None,          # 0.2.9 audit add (upstream spec keeps both columns — mapped through)
        "title": o.get("title") or None,               # person title ("Minister of Defense" form; empty on entity rows)
        "federal_register_notice": o.get("federal_register_notice") or None,  # FR citation (joins the FR face)
        "standard_order": o.get("standard_order") or None,
        "citizenships": _split_semi(o.get("citizenships")),          # 0.2.9 audit add: identity-disambiguation pair
        "places_of_birth": _split_semi(o.get("places_of_birth")),    # 0.2.9 audit add (paired with citizenships)
        "remarks": o.get("remarks") or None,           # 0.2.9 audit add: SDN passport/DOB/relationship details often live only here
        "call_sign": o.get("call_sign") or None,       # 0.2.9 audit add: vessel six-pack (call_sign = alternative identifier key)
        "vessel_type": o.get("vessel_type") or None,
        "gross_tonnage": o.get("gross_tonnage") or None,
        "gross_registered_tonnage": o.get("gross_registered_tonnage") or None,
        "vessel_flag": o.get("vessel_flag") or None,
        "source_list_url": o.get("source_list_url") or None,
        "start_date": o.get("start_date") or None,
        "end_date": o.get("end_date") or None,
        "source_information_url": o.get("source_information_url") or None,
    }


def filter_rows(rows, name=None, source=None, type=None):
    """Screening hit rows (pure function for offline regression). name: contains-match (case-insensitive)
    against name + alt_names; source: list-family substring; type: exact (case-insensitive)."""
    needle = str(name or "").strip().lower()
    if not needle:
        raise SdkError("usage_error", provider="csl",
                       detail="screening requires name (subject name, contains-matches name+alt_names)")
    src_needle = str(source).lower() if source else None
    type_needle = str(type).strip().lower() if type else None
    hits = []
    for o in rows:
        if src_needle and src_needle not in str(o.get("source") or "").lower():
            continue
        if type_needle and str(o.get("type") or "").strip().lower() != type_needle:
            continue
        nm = str(o.get("name") or "")
        if needle in nm.lower():
            hits.append(_row_to_screening(o, "name", nm))
            continue
        alt = next((a for a in _split_semi(o.get("alt_names")) if needle in a.lower()), None)
        if alt:
            hits.append(_row_to_screening(o, "alt_names", alt))
    return hits


def screen_list(name=None, source=None, type=None, limit=20, cache=None, no_cache=False):
    """Full-register screening (pulls the whole CSV, caches 24h, then scans locally)
    → {total_matched, scanned_rows, limit_applied, rows}.

    The upstream search.trade.gov search face requires a key (not on the roadmap) — the local filter is the
    keyless equivalent of quota-free batch screening.
    """
    from ..transport import call_provider

    r = call_provider(provider, "screening", {}, cache=cache, no_cache=no_cache)
    rows = rows_from_csv(r["data"])
    size = min(max(1, int(limit or 20)), 100)  # local payload wall (envelope row cap): truncation stays visible
    hits = filter_rows(rows, name=name, source=source, type=type)
    return {
        "total_matched": len(hits),              # local full scan: hit count is exact (not upstream-clamped)
        "scanned_rows": len(rows),               # rows scanned (audit echo: the full register really was scanned)
        "limit_applied": size,
        "rows": hits[:size],
        "_meta": r,
    }
