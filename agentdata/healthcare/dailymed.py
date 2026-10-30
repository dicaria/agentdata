"""dailymed — NLM DailyMed v2 (SPL labeling metadata layer; keyless; NLM family 20/s — 0.2.8 sped up to 10 rps into the nlm group bucket).

TTL: the spls list 7 days (setid is immutable, the list changes slowly with each release). First-version scope: setid + title + labeling URL as the verbatim-text entry point;
the SPL XML full text is not parsed (let the agent fetch it along the URL).
Probed and confirmed (2026-10-22): metadata.total_elements = the full count (atorvastatin 406) — the old face lost it entirely;
the real pagesize limit is 100; published_date 'MMM dd, yyyy' is not ISO → normalized; empty pagination values in metadata are the string 'null', not JSON null.
"""

import re

provider = {
    "id": "dailymed",
    "baseUrl": "https://dailymed.nlm.nih.gov/dailymed/services/v2",
    # NLM family 20/s (tier B, DailyMed is not listed separately so it follows NLM policy); 0.2.8 sped up to 10/4 into the nlm group bucket (same note as rxnav)
    "rate": {"rps": 10, "burst": 4, "group": "nlm"},
    "ops": {
        "spls": {"path": "/spls.json", "ttl": 7 * 86400},
    },
}

_MONTHS = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
           "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
_US_DATE = re.compile(r"^([A-Z][a-z]{2}) (\d{1,2}), (\d{4})$")


def us_date_to_iso(v):
    """'Oct 19, 2026' → '2026-10-19' (the same MDY-normalization family as the FDIC batch). Values in any other shape are returned unchanged."""
    if not isinstance(v, str):
        return None if v is None else v
    m = _US_DATE.match(v.strip())
    if m and m.group(1) in _MONTHS:
        return f"{m.group(3)}-{_MONTHS[m.group(1)]}-{int(m.group(2)):02d}"
    return v


def row_from_upstream(x: dict) -> dict:
    return {
        "setid": x.get("setid"),
        "title": x.get("title"),  # the title carries its own [labeler] bracket section — that is the upstream shape, passed through verbatim
        "spl_version": x.get("spl_version"),
        "published_date": us_date_to_iso(x.get("published_date")),
        "url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={x['setid']}" if x.get("setid") else None,
    }


def search_label(drug: str, limit: int = 5, cache=None, no_cache: bool = False) -> dict:
    from ..transport import call_provider

    r = call_provider(provider, "spls",
                      {"drug_name": drug, "pagesize": min(50, max(1, int(limit)))},
                      cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    rows = data.get("data") or []
    total = ((data.get("metadata") or {}).get("total_elements")) or len(rows)
    return {
        "total": total,
        "rows": [row_from_upstream(x) for x in rows],
        "_meta": r,
    }


def spls_raw(*, drug_name=None, manufacturer=None, setid=None, page=None, pagesize=None,
             sort=None, cache=None, no_cache: bool = False) -> dict:
    """0.2.0 mirror face: all six spls.json params passed through under their upstream names (all verified by probing on 2026-10-23: manufacturer=Pfizer → Hospira rows,
    setid filters exactly, page/pagesize/sort paginate and sort).

    No hard cap: upstream silently clamps pagesize to 100 (101 → elements_per_page=100, no error) — the default None = omit (the upstream default is 100),
    and the clamp is visible through the elements_per_page echo; a bare call is legal (full SPL enumeration, which upstream can express).
    → {total, rows[], page, elements_per_page, params, _meta}; empty pagination values in metadata are the string 'null' and are normalized.
    """
    from ..transport import call_provider
    from ..errors import SdkError

    params = {}
    if drug_name:
        params["drug_name"] = str(drug_name)
    if manufacturer:
        params["manufacturer"] = str(manufacturer)
    if setid:
        params["setid"] = str(setid)
    if page is not None:
        params["page"] = int(page)
    if pagesize is not None:
        ps = int(pagesize)
        if ps < 1:
            raise SdkError("usage_error", provider="dailymed", detail=f"pagesize must be >= 1, got {ps}")
        params["pagesize"] = ps
    if sort:
        params["sort"] = str(sort)
    r = call_provider(provider, "spls", params, cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    meta = data.get("metadata") or {}
    rows = data.get("data") or []
    total = meta.get("total_elements") or len(rows)
    return {
        "total": total,
        "rows": [row_from_upstream(x) for x in rows],
        "page": meta.get("current_page"),
        "elements_per_page": meta.get("elements_per_page"),
        "params": params,
        "_meta": r,
    }
