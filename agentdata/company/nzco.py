"""nzco — New Zealand Companies Office register (app.companiesoffice.govt.nz; keyless HTML).

Two faces (0.3.30; probed 2026-11-03, tmp/probe-company-0330/; research volume
nz-companies-register, P1 7/7 — the company master register, 15th country):

  * companies — the register search. GET /companies/app/ui/pages/companies/search with the
    canonical parameter set mode=standard&type=entities&q=<term>&advancedPanel=true&entityTypes=ALL
    (a bare ?q= returns the empty-match page — the full set is REQUIRED, pinned in the research
    probe tmp/probe-nzco/). Paging is the pager's own vocabulary: start=<offset> + limit=<rows>
    (both observed live: 5 and 15 rows per page; other limits are unpinned and not shipped).
    Rows are server-rendered blocks: a javascript:viewCompanyDetails('<number>') anchor (the
    official company number), <span class="entityName">, an entityInfo span carrying
    "(<number>) (NZBN: <16 digits>) <status>" plus a nested entityType span, and an optional
    address <div>. Status words are the register's own ("Registered", "Removed" — NOT
    "Active"; captured verbatim). The NZBN is the second official key (cross-government join
    key). has_next comes from the pager's own start= offsets (max offset > current offset).
  * directors — the directors tab. GET /companies/app/ui/pages/companies/<number>/directors;
    the page H1 carries "<name> (<number>) <status>" and each current director sits in one
    <td class="director"> block: Full legal name (multi-line, whitespace-collapsed),
    Residential Address (statutorily public in NZ; partially masked since the privacy-law
    change — captured verbatim whatever the register shows) and Appointment Date (verbatim
    register wording, e.g. "01 May 2025"). Former/ceased directors render in a DIFFERENT
    section after the current blocks (the ceasedDate rows) and are not td.director blocks —
    this face returns current appointments only.

Channel: plain GET, no CAPTCHA, no key; the register is a UI surface (no published API rate)
-> polite 0.5 rps / burst 2, honest agentdata UA (occ.gov precedent; if the site ever
UA-gates, extension (8) extra_headers is the documented remedy).
TTL: search 12h (new incorporations land in the index); directors 24h (appointments change
less often than the index).
"""
import html as _html
import re

from ..errors import SdkError

provider = {
    "id": "nzco",
    "baseUrl": "https://app.companiesoffice.govt.nz",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/companies/app/ui/pages/companies/search", "accept": "text",
                   "timeoutMs": 60000},
        "directors": {"path": "/companies/app/ui/pages/companies/{company_number}/directors",
                      "accept": "text", "notFound": [404], "timeoutMs": 60000},
    },
    "ttl": {"search": 12 * 3600, "directors": 24 * 3600},
}

# entityTypes checkbox values excavated from the live filter form (probe search-airnz.html)
ENTITY_TYPES = ("ALL", "LTD", "UNLTD", "COOP", "ASIC", "NON_ASIC")
_LIMITS = (5, 15)  # both observed live in the pager (5 rows on the legacy shell, 15 canonical)

_ENTITY_NAME_RE = re.compile(r'<span class="entityName">([^<]*)</span>')
_ENTITY_INFO_RE = re.compile(
    r'<span class="entityInfo">\s*\((\d+)\)\s*\(NZBN:\s*(\d+)\)\s*([^<]*?)\s*'
    r'<span class="entityType">([^<]*)</span>', re.S)
_ENTITY_TYPE_RE = re.compile(r'<span class="entityType">([^<]*)</span>')
_ADDR_RE = re.compile(r'<br>\s*<div[^>]*>\s*([^<]+?)\s*</div>', re.S)
_START_RE = re.compile(r'[?&]start=(\d+)')
_H1_RE = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)

_LABEL_RE = {
    "name": re.compile(r'for="fullName">[^<]*</label>\s*(.*?)\s*</div>', re.S),
    "address": re.compile(r'for="residentialAddress">[^<]*</label>\s*(.*?)\s*</div>', re.S),
    "appointment": re.compile(r'for="appointmentDate">[^<]*</label>\s*([^<]+?)\s*</div>', re.S),
}


def _clean(s):
    """collapse the register's heavy multi-line whitespace and unescape entities."""
    return _html.unescape(re.sub(r"\s+", " ", s or "").strip()).replace(" ,", ",")


def _norm_q(q):
    if q is None or not str(q).strip():
        raise SdkError("usage_error", provider="nzco",
                       detail="nzco_companies requires --q (a name substring, e.g. "
                              "'air new zealand'; the register also matches by company "
                              "number inside the name index)")
    return str(q).strip()


def _to_int(v, name):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="nzco",
                       detail=f"{name} must be an integer, got {v!r}")


def _norm_paging(start, limit):
    start_i = _to_int(start, "start") if start not in (None, "") else 0
    if start_i < 0:
        raise SdkError("usage_error", provider="nzco",
                       detail=f"start must be a non-negative row offset, got {start!r}")
    limit_i = _to_int(limit, "limit") if limit not in (None, "") else 15
    if limit_i not in _LIMITS:
        raise SdkError("usage_error", provider="nzco",
                       detail=f"limit must be one of {list(_LIMITS)} (both observed in the "
                              f"live pager; other page sizes are unpinned and not shipped), "
                              f"got {limit!r}")
    return start_i, limit_i


def _norm_entity_types(entity_types):
    et = (entity_types or "ALL").strip()
    if et.upper() not in ENTITY_TYPES:
        raise SdkError("usage_error", provider="nzco",
                       detail=f"entity_types must be one of {list(ENTITY_TYPES)} (the filter "
                              f"form's own checkbox codes: LTD/UNLTD/COOP = NZ companies, "
                              f"ASIC/NON_ASIC = overseas), got {entity_types!r}")
    return et.upper()


def _norm_company_number(company_number):
    n = str(company_number or "").strip()
    if not n.isdigit():
        raise SdkError("usage_error", provider="nzco",
                       detail="nzco_directors requires --company-number (the NZ company "
                              "number, digits only — find it with nzco_companies; e.g. "
                              "104799 = Air New Zealand Limited)")
    return n


def _parse_search(text, start, limit):
    """blocks split on the viewCompanyDetails anchors; the first chunk is the page header."""
    rows = []
    for chunk in text.split("javascript:viewCompanyDetails('")[1:]:
        num = re.match(r"(\d+)", chunk)
        if not num:
            continue
        number = num.group(1)
        nm = _ENTITY_NAME_RE.search(chunk)
        info = _ENTITY_INFO_RE.search(chunk)
        et = _ENTITY_TYPE_RE.search(chunk)
        addr = _ADDR_RE.search(chunk)
        if info and info.group(1) == number:
            nzbn, status = info.group(2), _clean(info.group(3))
        else:
            # an entityInfo shape we have not met (e.g. no NZBN on a pre-2007 relic) — keep the
            # official number, never fabricate the rest
            nzbn, status = None, None
        rows.append({
            "name": _clean(nm.group(1)) if nm else None,
            "company_number": number,
            "nzbn": nzbn,
            "status": status,
            "entity_type": _clean(et.group(1)) if et else None,
            "address": _clean(addr.group(1)) if addr else None,
        })
    offsets = [int(x) for x in _START_RE.findall(text)]
    has_next = bool(offsets) and max(offsets) > start
    return rows, has_next


def companies_raw(q, *, entity_types=None, start=None, limit=None, cache=None, no_cache=False):
    """-> {count, rows, start, limit, entity_types, has_next, params, _meta};
    rows are {name, company_number, nzbn, status, entity_type, address}."""
    from ..transport import call_provider

    term = _norm_q(q)
    et = _norm_entity_types(entity_types)
    start_i, limit_i = _norm_paging(start, limit)
    params = {"mode": "standard", "type": "entities", "q": term,
              "advancedPanel": "true", "entityTypes": et}
    if start_i:
        params["start"] = start_i
    if limit_i != 15:
        params["limit"] = limit_i
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    rows, has_next = _parse_search(r["data"] or "", start_i, limit_i)
    return {"total": len(rows), "count": len(rows), "rows": rows,
            "start": start_i, "limit": limit_i, "entity_types": et, "has_next": has_next,
            "params": params, "_meta": r}


def _parse_directors(text):
    """current directors = the td.director blocks (the ceased section renders elsewhere)."""
    company_number, status = None, None
    company_name = None
    h1 = _H1_RE.search(text)
    if h1:
        flat = _html.unescape(re.sub(r"<[^>]+>", " ", h1.group(1)))
        company_name = _clean(flat.split("(")[0])
        ident = re.search(r"\((\d+)\)\s*([A-Za-z ]+)", flat)
        if ident:
            company_number, status = ident.group(1), ident.group(2).strip()
    rows = []
    for chunk in text.split('<td class="director">')[1:]:
        nm = _LABEL_RE["name"].search(chunk)
        addr = _LABEL_RE["address"].search(chunk)
        appt = _LABEL_RE["appointment"].search(chunk)
        rows.append({
            "name": _clean(nm.group(1)) if nm else None,
            "address": _clean(addr.group(1)) if addr else None,
            "appointment_date": _clean(appt.group(1)) if appt else None,
        })
    return company_name, company_number, status, rows


def directors_raw(company_number, *, cache=None, no_cache=False):
    """-> {company_name, company_number, status, count, rows, params, _meta};
    rows are {name, address, appointment_date} (current appointments)."""
    from ..transport import call_provider

    n = _norm_company_number(company_number)
    r = call_provider(provider, "directors", {"company_number": n},
                      cache=cache, no_cache=no_cache)
    company_name, number, status, rows = _parse_directors(r["data"] or "")
    if number and number != n:
        raise SdkError("upstream_error", provider="nzco",
                       detail=f"directors page answered for company {number} but {n} was "
                              f"requested — refusing to attribute rows across companies")
    return {"company_name": company_name, "company_number": n, "status": status,
            "total": len(rows), "count": len(rows), "rows": rows,
            "params": {"company_number": n}, "_meta": r}
