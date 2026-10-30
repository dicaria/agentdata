"""ch_zefix — Swiss Zefix commercial register (Zentraler Firmenindex) provider (same-origin REST front door; keyless).

2026-10-29 probed shape: POST /firm/search.json with JSON body
{languageKey, maxEntries, offset, name} → {list[], hasMoreResults, offset, maxEntries, maxOffset};
name is a contains-match (nestle hits Nestler), pagination = offset+hasMoreResults (maxOffset ~540k = upstream offset wall);
single record GET /firm/{ehraid}.json returns the full record: oldNames[] name history + hasTakenOver/wasTakenOverBy M&A edges
(rows carry ehraid/uid/chid cross-references — closed-loop linking inside the Swiss registry system) + purpose full text.
Three keys surfaced directly: ehraid (master id) / uid (CHE business id) / chid (register id). Officers/directors are not in the public face.
TTL: search 7 days (current-value query) / firm 30 days (records change slowly); politeness tier 0.5 rps (no published quota).
"""
from ..errors import SdkError

provider = {
    "id": "ch_zefix",
    "baseUrl": "https://www.zefix.ch/ZefixREST/api/v1",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/firm/search.json", "method": "POST", "idempotent": True},  # params: name/maxEntries/offset (all in the JSON body)
        "firm": {"path": "/firm/{ehraid}.json", "notFound": [404]},                     # params: ehraid (path template)
    },
    "ttl": {"search": 7 * 86400, "firm": 30 * 86400},
}


def search_firms(name, *, max_entries=100, offset=0, cache=None, no_cache=False):
    """→ {firms[], has_more, max_offset, params, _meta}; name → registry candidates (contains-match, not authoritative normalization).
    maxEntries/offset are honored and echoed upstream (probed: maxEntries=3 returned 3 rows); 1-100 is our politeness cap, not an upstream wall."""
    from ..transport import call_provider

    q = str(name or "").strip()
    if not q:
        raise SdkError("usage_error", provider="ch_zefix", detail="search requires name (company name, contains-match)")
    n = min(max(1, int(max_entries or 100)), 100)
    off = max(0, int(offset or 0))
    r = call_provider(provider, "search",
                      {"name": q, "maxEntries": n, "offset": off, "languageKey": "en"},
                      cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    rows = [{
        "ehraid": f.get("ehraid"),
        "uid": f.get("uid"),
        "uid_formatted": f.get("uidFormatted"),
        "chid": f.get("chid"),
        "chid_formatted": f.get("chidFormatted"),
        "name": f.get("name"),
        "status": f.get("status"),                      # EXISTIEREND / GELOESCHT…
        "legal_seat": f.get("legalSeat"),
        "legal_form_id": f.get("legalFormId"),
        "register_office_id": f.get("registerOfficeId"),
        "shab_date": f.get("shabDate"),                 # latest gazette date
        "delete_date": f.get("deleteDate"),             # non-null on GELOESCHT rows
        "cantonal_excerpt_web": f.get("cantonalExcerptWeb"),  # cantonal register excerpt page (human-readable)
    } for f in d.get("list") or []]
    return {"firms": rows, "has_more": bool(d.get("hasMoreResults")),
            "max_offset": d.get("maxOffset"),
            "params": {"name": q, "maxEntries": n, "offset": off, "languageKey": "en"},
            "_meta": r}


def get_firm(ehraid, *, cache=None, no_cache=False):
    """→ {firm, _meta}; full record card by ehraid (purpose/oldNames/M&A edges).
    hasTakenOver = predecessors this firm absorbed / wasTakenOverBy = the successor that absorbed this firm —
    rows carry ehraid/uid/chid so ch_zefix_firm/ch_zefix_firm_search can be called next for a closed loop."""
    from ..transport import call_provider

    v = str(ehraid or "").strip()
    if not v.isdigit():
        raise SdkError("usage_error", provider="ch_zefix",
                       detail=f"ehraid must be numeric (master id, surfaced by search rows), got \"{ehraid}\"")
    r = call_provider(provider, "firm", {"ehraid": v}, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    firm = {
        "ehraid": d.get("ehraid"),
        "uid": d.get("uid"),
        "uid_formatted": d.get("uidFormatted"),
        "chid": d.get("chid"),
        "chid_formatted": d.get("chidFormatted"),
        "name": d.get("name"),
        "translation": d.get("translation"),
        "status": d.get("status"),
        "legal_seat": d.get("legalSeat"),
        "legal_form_id": d.get("legalFormId"),
        "register_office_id": d.get("registerOfficeId"),
        "shab_date": d.get("shabDate"),
        "delete_date": d.get("deleteDate"),
        "cantonal_excerpt_web": d.get("cantonalExcerptWeb"),
        "purpose": d.get("purpose"),                    # full statement of purpose
        "address": d.get("address"),                    # registered address (upstream shape passed through)
        "old_names": [{"name": o.get("name"), "sequence_nr": o.get("sequenceNr"),
                       "translation": o.get("translation")} for o in d.get("oldNames") or []],
        "has_taken_over": _edge(d.get("hasTakenOver")),      # predecessors: merged into this firm
        "taken_over_by": _edge(d.get("wasTakenOverBy")),     # successors: absorbed this firm
    }
    return {"firm": firm, "_meta": r}


def _edge(rows):
    """M&A edge row projection: name + three keys (ehraid/uid/chid) — keys feed the next hop, the rest is dropped."""
    return [{"name": e.get("name"), "ehraid": e.get("ehraid"),
             "uid": e.get("uid"), "chid": e.get("chid")} for e in rows or []]
