"""gb_fca — FCA market-data search API (api.data.fca.org.uk, keyless; 0.3.74 batch E16).

The FCA data portal (data.fca.org.uk — the National Storage Mechanism, the Official List and
the Financial Instrument Data Search) is a single-page app over ONE endpoint: POST
/search?index=<index> with an Elastic-style JSON query body. No key, no cookie (the NSM web
UI's click-through disclaimer is UI-only; the API answers without it).

2026-11-23 probed laws (tmp/probe-e16/ — ol-shape*.py, probe3-5.py, smoke-e16.py):
  - ONE ENDPOINT, FOUR INDEXES: nsm-search (5,570,535 regulatory disclosures), official-list-main
    (15,160 live securities), official-list-daily-activity (119,810 events), firds-view (169.6M
    published active instruments). GET /details/{id} adds nothing beyond the hit's _source —
    no details op.
  - ERROR-SHAPE LAW: a malformed query answers 404 + plain text "Unable to search the data"
    (wrong date format, unsupported sort field, over-window paging, a list where an object is
    expected, a missing required bound); a wrong facet VALUE usually answers 200 + total 0 (the
    silent-zero trap — vocabularies are normalised locally below). A 404 is self-inflicted until
    diffed against a known-good body: the SDK re-raises it with that hint.
  - ROWS ARE THE POPULATED FIELDS of the upstream record: a null field is simply absent (a
    placeholder Official List record carries 5 keys, a settled one 8; NSM rows differ by source
    — Direct Upload rows carry html / json / csv links, RNS rows classifications).
  - DATE-FORMAT-PER-INDEX LAW: nsm-search and official-list-daily-activity take full ISO
    "YYYY-MM-DDTHH:mm:ssZ"; official-list-main and firds-view take "dd/MM/yyyy". NSM, activity
    and the Official List accept one-sided bounds; FIRDS REQUIRES the upper bound (a from-only
    window answers 404 — the SDK fills 31/12/2099).
  - 10,000 WINDOW LAW: from + size must stay within the FIRST 10,000 hits of the sort order
    whatever the total — measured on all four indexes (from 9,990 + size 11 answers 404).
    Flipping sortorder reaches the tail; the middle only through a narrower query. No upstream
    page-size wall measured up to 10,000 — the SDK caps a page at 5,000.
  - NSM, TWO PATHS: criteriaObj.criteria are AND'ed facets with array values (type / source /
    document_format / tag_esef — type and format match case-insensitively, tag_esef and source
    only in their stored casing) plus single-string terms (lei — exact and case-sensitive;
    company — a case-insensitive partial name match); dateCriteria bound publication_date |
    submitted_date. Full text is the OTHER path: primarySearch document_content / headline
    entries carrying [mode, text] pairs (match_all_words = AND of the words, exact_match = the
    phrase; case-insensitive; entries OR'ed) — it answers 404 unless the body also carries
    latestFlag "Y" and a criteriaObj whose dateCriteria is a LIST (empty allowed). latestFlag
    is a no-op on the criteria path. disclosure_id + sort hist_seq desc = the version history
    of one announcement.
  - OFFICIAL LIST: 11 listing categories (380 commercial equity lines … 11,061 debt lines);
    lei and security_isin criteria are exact and case-sensitive; text searches ISIN, LEI or
    issuer name (partial, case-insensitive — NOT the security name). Sortable: security_isin,
    security_initial_admission_date, lei, last_updated_date and the pair
    "security_initial_admission_date,security_isin"; issuer_name / security_name /
    listing_category answers 404; a top-level securityStatus is ignored.
  - ACTIVITY: security_activity is REQUIRED and one of Admission | Suspension | Restoration |
    Cancellation — an unknown value is ignored upstream (all 119,810 rows answer) and a
    lowercase one answers 0, so it is validated locally. securityActivityDateCriteria is an
    OBJECT {name, value{from,to}} (a list answers 404); the four kinds cannot be combined.
  - FIRDS: criteria are single strings (an array answers a silent 0) — fininstrmgnlattrbts_id =
    the instrument's own ISIN, tradgvnrltdattrbts_id = MIC (UPPERCASE: 'xlon' + ESVUFR matches
    36,671 rows where 'XLON' matches 1,577), isin_sngl_noindx = the UNDERLYING ISIN of a
    derivative, isin_bskt = basket ISIN, issr = issuer LEI, fininstrmgnlattrbts_clssfctntp =
    an exact 6-char CFI (no wildcard). dateCriteria honours techattrbts_pblctnprd_frdt (first
    publication date), tradgvnrltdattrbts_frsttraddt (first trade date) and
    tradgvnrltdattrbts_termntndt (termination date). A body carrying BOTH keyword and
    criteriaObj ignores the keyword — the SDK refuses the mix. The SPA always adds
    techattrbts_nvrpblshd=false + active_flag=Y (never-published instruments are internal
    records) — the SDK follows both.
  - ARTEFACTS: the *_link fields are site-relative under https://data.fca.org.uk/artefacts/
    (the same path under the host root answers 403) and a plain GET answers 200 (RNS HTML,
    Tagged html_link XHTML, json_link = XBRL-JSON). NEVER send a Range header to that host —
    it resets the connection (10054, measured).
  - data.fca.org.uk/robots.txt: Allow: / with Content-Signal search=yes, ai-train=no,
    use=reference. The SPA's analytics / honeypot endpoints are never called by this engine.

Politeness 0.5 rps, burst 2 (no published limit). TTLs: NSM 15min (≈2,230 disclosures per
trading day), official list 6h (nightly rebuild), activity 1h, FIRDS 6h.
"""
import datetime
import re

from ..errors import SdkError

ID = "gb_fca"
ARTEFACT = "https://data.fca.org.uk/artefacts/"
MAX_WINDOW = 10000  # upstream index_max_result_window (all four indexes)

provider = {
    "id": ID,
    "baseUrl": "https://api.data.fca.org.uk",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # notFound: a 404 here is "Unable to search the data" — a clean upstream round trip
        # on a rejected query (counted as such by the breaker); _search() re-raises with a hint
        "nsm": {"path": "/search?index=nsm-search", "method": "POST", "idempotent": True,
                "timeout": 60.0, "notFound": [404]},
        "official_list": {"path": "/search?index=official-list-main", "method": "POST",
                          "idempotent": True, "timeout": 60.0, "notFound": [404]},
        "official_list_activity": {"path": "/search?index=official-list-daily-activity",
                                   "method": "POST", "idempotent": True, "timeout": 60.0,
                                   "notFound": [404]},
        "firds": {"path": "/search?index=firds-view", "method": "POST", "idempotent": True,
                  "timeout": 60.0, "notFound": [404]},
    },
    "ttl": {"nsm": 900, "official_list": 21600, "official_list_activity": 3600, "firds": 21600},
}

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,9})?)?(Z|[+-]\d{2}:\d{2})?$")
_LEI = re.compile(r"^[A-Z0-9]{20}$")
_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


# —— shared validation shapers (pure — split out for offline testing) ——

def _int(value, name, lo, hi=None, default=None):
    if value is None:
        return default
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider=ID, detail=f"{name} must be an integer, got {value!r}")
    if n < lo or (hi is not None and n > hi):
        rng = f">={lo}" if hi is None else f"{lo}-{hi}"
        raise SdkError("usage_error", provider=ID, detail=f"{name} must be {rng}, got {value!r}")
    return n


def _choice(value, name, allowed, default=None):
    if value is None or value == "":
        return default
    v = str(value).strip()
    if v not in allowed:
        raise SdkError("usage_error", provider=ID,
                       detail=f"{name} must be one of {' | '.join(allowed)}, got \"{value}\"")
    return v


def _iso_bound(value, name, end):
    """YYYY-MM-DD -> the day's first / last second in the full ISO form the NSM and activity
    indexes demand; a fuller stamp (with time) passes verbatim."""
    s = str(value).strip()
    if _DATE.match(s):
        try:
            datetime.date.fromisoformat(s)
        except ValueError:
            raise SdkError("usage_error", provider=ID, detail=f"{name} is not a real date: {value!r}")
        return s + ("T23:59:59Z" if end else "T00:00:00Z")
    if _STAMP.match(s):
        return s
    raise SdkError("usage_error", provider=ID,
                   detail=f"{name} must be YYYY-MM-DD (or a full ISO timestamp), got {value!r}")


def _dmy(value, name):
    """YYYY-MM-DD -> dd/MM/yyyy (the Official List and FIRDS date form)."""
    s = str(value).strip()
    try:
        return datetime.date.fromisoformat(s).strftime("%d/%m/%Y")
    except ValueError:
        raise SdkError("usage_error", provider=ID, detail=f"{name} must be YYYY-MM-DD, got {value!r}")


def _upper(value, name, pattern=None, what="a 20-character LEI"):
    s = str(value).strip().upper().replace(" ", "")
    if pattern is not None and not pattern.match(s):
        raise SdkError("usage_error", provider=ID, detail=f"{name} must be {what}, got {value!r}")
    return s


def _window(offset, limit):
    """the 10,000 window law — checked BEFORE the request (the upstream answer is a bare 404)."""
    if offset + limit > MAX_WINDOW:
        raise SdkError(
            "usage_error", provider=ID,
            detail=f"offset + limit = {offset + limit} crosses the upstream result window: only the first "
                   f"{MAX_WINDOW:,} hits of the sort order are reachable (index_max_result_window; over the "
                   "line the upstream answers 404 'Unable to search the data'). Narrow the query "
                   "(--lei / --type / --from-date…), or flip --order to walk the tail from the other end")


def _search(op, body, cache, no_cache):
    from ..transport import call_provider

    try:
        return call_provider(provider, op, body, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.status == 404:
            raise SdkError(
                "upstream_unavailable", provider=ID, status=404,
                detail="Upstream 404 'Unable to search the data' — the FCA search endpoint rejects a "
                       "malformed query with a bare 404 (date format, sort field, value type or a "
                       "criterion the index does not honour); the request shape may have drifted from "
                       "the 2026-11-23 probe — re-probe against a known-good body") from None
        raise


def _hits(doc, op):
    if not isinstance(doc, dict) or not isinstance(doc.get("hits"), dict) \
            or not isinstance(doc["hits"].get("hits"), list):
        raise SdkError("upstream_unavailable", provider=ID,
                       detail=f"the FCA search index answered an unexpected shape (no hits[] on op {op}) — "
                              "the endpoint layout may have moved; re-probe")
    total = (doc["hits"].get("total") or {}).get("value")
    return (total if isinstance(total, int) else 0), doc["hits"]["hits"]


def _facets(doc):
    """the sterms#*_options aggregations -> {field: [{value, count}]} (bucket keys are the
    lowercased terms — the discovery vocabulary of the silent-zero facets)."""
    out = {}
    for name, agg in (doc.get("aggregations") or {}).items():
        if not isinstance(agg, dict):
            continue
        key = str(name).split("#", 1)[-1].replace("_options", "")
        buckets = [{"value": b.get("key"), "count": b.get("doc_count")}
                   for b in (agg.get("buckets") or []) if isinstance(b, dict) and "key" in b]
        if buckets:
            out[key] = buckets
    return out or None


def _artefact(link):
    s = str(link or "")
    return s if s.startswith(("https://", "http://")) else (ARTEFACT + s.lstrip("/") if s else None)


def _envelope(op, body, doc, rows, offset, size, r, cache_hit_url=None):
    total, _ = _hits(doc, op)
    out = {"total": total, "offset": offset, "limit": size, "row_count": len(rows), "rows": rows,
           "next_offset": (offset + size) if offset + size < total else None,
           "params": body, "_meta": r}
    facets = _facets(doc)
    if facets:
        out["facets"] = facets
    if total > MAX_WINDOW:
        out["window_note"] = (f"{total:,} hits — the upstream serves only the first {MAX_WINDOW:,} of the sort "
                              "order (offset + limit <= 10000); flip --order to reach the tail, narrow the "
                              "filters to reach the middle")
    return out


def _canon(values, name, vocabulary, strict=False):
    """facet values are matched verbatim upstream and a miss is a silent 0 — map a known
    vocabulary case-insensitively to its stored casing. strict: an unknown value is refused
    (a fixed legal taxonomy); otherwise it passes through verbatim (a live vocabulary — the
    upstream may have added a value since the 2026-11-23 snapshot)."""
    out = []
    for v in (values if isinstance(values, (list, tuple)) else [values]):
        if v is None or str(v).strip() == "":
            continue
        s = str(v).strip()
        hit = vocabulary.get(s.lower())
        if hit is None and strict:
            raise SdkError("usage_error", provider=ID,
                           detail=f"unknown {name} value \"{s}\" — pick one of: "
                                  + " | ".join(vocabulary.values()))
        out.append(hit or s)
    return out


# —— National Storage Mechanism (index nsm-search) ——

# stored casing as of 2026-11-23 (the bucket keys of sterms#type_options are lowercased; a few
# stored values are irregular — "Directorate change", "Block listing Interim Review", and
# "Supplementary Registration Document " carries a trailing space)
NSM_TYPES = (
    "1st Quarter Results", "3rd Quarter Results", "Acquisition", "Additional Listing",
    "Admission to Trading", "AGM Statement", "Agreement", "AIM Admission - Update", "AIM Notice",
    "AIM Prospective Admission", "Alliance", "Announcement re: Rights Issue", "Annual Financial Report",
    "Annual Information Update", "Annual report - Guarantor", "Aquis Exchange", "Base Prospectus",
    "Base Rate Change", "Block listing Interim Review", "Capital Reorganisation", "Cboe Markets",
    "Change of Adviser", "Change of Name", "Change of Nomad", "Change of Registered Office",
    "Circ re.", "Company Secretary Change", "Compliance with Model Code", "Compulsory Acquisition of Shares",
    "Contract", "Conversion of Securities", "Director Declaration", "Director/PDMR Shareholding",
    "Directorate change", "Disclosure Table (Takeover Panel use only)", "Disposal",
    "Dividend Declaration", "Doc re.", "Drilling/Production Report", "Euronext Dublin",
    "Exchange Suspension/Restoration", "Final Announcement Released", "Final Results", "Final Terms",
    "Form 8 (DD)", "Form 8 (Opening Position Disclosure)", "Form 8.3", "Form 8.5 (EPT/NON-RI)",
    "Form 8.5 (EPT/RI)", "Formal notice", "FRN Variable Rate Fix", "FTSE", "Further re",
    "Geographical Distribution", "GM Statement", "Half-year Financial Report", "Holding(s) in Company",
    "Industry Regulator Statement", "Initial admission to the Official List", "Intention to Float",
    "Intention to Float - AIM", "Interim Management Statement", "IPX", "Irish Takeover Panel",
    "Issue of Debt", "Issue of Equity", "Joint Venture", "JP Jenkins", "Letter of Intent Signed",
    "Listing Particulars", "Listing Supplement", "London Stock Exchange Notice", "Merger Update",
    "Merger Update(CMA use only)", "Miscellaneous", "Net Asset Value(s)", "New Accounting Ref Date",
    "Nomad Register (LSE USE ONLY)", "Non Regulatory Announcement", "Notice of AGM", "Notice of GM",
    "Notice of Results", "Offer by", "Offer Document Posted", "Offer for", "Offer Lapsed",
    "Offer Rejection", "Offer Talks Terminated", "Offer Update", "Official List Notice",
    "Official List Notice (FCA use only)", "Other non-regulated information", "Portfolio Update",
    "Preliminary Results", "Price Monitoring Extension", "Pricing Supplement",
    "Prior Notice of Merger (CMA use only)", "Product Launch", "Prospectus Summary", "Proxy Form",
    "Publication of a Prospectus", "Publication of a Supplementary Prospectus", "Registration Document",
    "Regulatory Application", "Regulatory Approval", "Report on Payments to Governments",
    "Research Update", "Response to", "Restoration of Listing", "Restructure Proposals", "Result of AGM",
    "Result of Equity Issue", "Result of Meeting", "Result of Tender Offer", "Rule 2.9 Announcement",
    "Scheme of Arrangement", "Second price Monitoring Extension", "Securities Note",
    "Stabilisation Notice", "Statement re", "Statement re (CMA use only)", "Statement re Possible Offer",
    "Statement re Press Comment", "Statement re Share Price Movement", "Statement re Takeover Panel",
    "Statement re. Suspension", "Strategy/Company/ Operations Update", "Supplementary Registration Document",
    "Supplementary Registration Document ", "Syndicate Results", "Temporary Suspension", "Tender Offer",
    "Test Message", "Total Assets Value", "Total Voting Rights", "Trading Statement",
    "Transaction in Own Shares", "Treasury Stock",
)
NSM_SOURCES = ("RNS", "EQS", "PRN", "BWI", "Portal (pre-Sept 2017)", "FCA", "Direct Upload", "GNW",
               "NASDAQNEWS", "TEN")
NSM_FORMATS = ("Plain text", "PDF", "Tagged", "Untagged", "Other")
_TYPE_VOCAB = {t.lower(): t for t in NSM_TYPES}
_SOURCE_VOCAB = {s.lower(): s for s in NSM_SOURCES}
_FORMAT_VOCAB = {f.lower(): f for f in NSM_FORMATS}
NSM_DATE_FIELDS = ("publication_date", "submitted_date")
NSM_SORTS = ("publication_date", "submitted_date", "company", "headline", "type", "lei",
             "disclosure_id", "seq_id", "hist_seq", "ContentVersionId", "latest_flag")
TEXT_MODES = ("match_all_words", "exact_match")

# the three mixed-case upstream keys are snake_cased in rows; every other _source key is
# already snake_case and passes verbatim (no pruning)
_NSM_RENAME = {"ContentVersionId": "content_version_id", "ProcessType": "process_type",
               "IsTestSubmission": "is_test_submission", "RegionOfIncorporation": "region_of_incorporation"}


def nsm_body(*, lei=None, company=None, text=None, text_mode="match_all_words", types=None,
             sources=None, formats=None, tag_esef=False, date_field="publication_date",
             from_date=None, to_date=None, sort="publication_date", order="desc", offset=0, limit=20):
    """the NSM query body (pure). Two upstream paths, AND'ed together: criteriaObj.criteria
    (LEI, company, facets) + dateCriteria; and — when text is given — primarySearch
    (document_content OR headline), which also needs latestFlag "Y" and list-typed
    criteriaObj members (the text-path 404 law)."""
    criteria = []
    if lei:
        criteria.append({"name": "lei", "value": _upper(lei, "lei", _LEI)})
    if types:
        criteria.append({"name": "type", "value": _canon(types, "type", _TYPE_VOCAB)})
    if sources:
        criteria.append({"name": "source", "value": _canon(sources, "source", _SOURCE_VOCAB)})
    if formats:
        criteria.append({"name": "document_format", "value": _canon(formats, "document_format", _FORMAT_VOCAB)})
    if tag_esef:
        criteria.append({"name": "tag_esef", "value": ["Tagged"]})
    dates = None
    if from_date or to_date:
        field = _choice(date_field, "date_field", NSM_DATE_FIELDS, "publication_date")
        dates = [{"name": field,
                  "value": {"from": _iso_bound(from_date, "from_date", False) if from_date else None,
                            "to": _iso_bound(to_date, "to_date", True) if to_date else None}}]
    company = " ".join(str(company).split()) if company else ""
    if company:
        criteria.append({"name": "company", "value": company})
    body = {"from": _int(offset, "offset", 0, default=0), "size": _int(limit, "limit", 1, 5000, 20),
            "sort": _choice(sort, "sort", NSM_SORTS, "publication_date"),
            "sortorder": _choice(order, "order", ("asc", "desc"), "desc")}
    phrase = " ".join(str(text).split()) if text else ""
    if phrase:
        mode = _choice(text_mode, "text_mode", TEXT_MODES, "match_all_words")
        pair = [mode, phrase]
        body["latestFlag"] = "Y"
        body["primarySearch"] = [{"name": "document_content", "value": [pair]},
                                 {"name": "headline", "value": [pair]}]
        body["criteriaObj"] = {"criteria": criteria, "dateCriteria": dates or []}
    elif criteria or dates:
        body["criteriaObj"] = {"criteria": criteria, "dateCriteria": dates}
    _window(body["from"], body["size"])
    return body


def nsm_row(hit):
    """one NSM hit -> row (pure): _source verbatim (three keys snake_cased) + the absolute
    artefact URLs (document_url from download_link; html_url / json_url / csv_url on Tagged rows)."""
    s = dict(hit.get("_source") or {})
    for k, v in _NSM_RENAME.items():
        if k in s:
            s[v] = s.pop(k)
    row = {"disclosure_id": s.get("disclosure_id") or hit.get("_id")}
    row.update(s)
    for link, key in (("download_link", "document_url"), ("html_link", "html_url"),
                      ("json_link", "json_url"), ("csv_link", "csv_url")):
        if s.get(link):
            row[key] = _artefact(s[link])
    return row


def nsm_search(*, lei=None, company=None, text=None, text_mode="match_all_words", types=None,
               sources=None, formats=None, tag_esef=False, date_field="publication_date",
               from_date=None, to_date=None, sort="publication_date", order="desc", offset=0,
               limit=20, cache=None, no_cache=False):
    """→ {total, offset, limit, row_count, rows[], next_offset, facets?, window_note?, params, _meta};
    the National Storage Mechanism — 5.57M regulatory disclosures (RNS 4.03M, EQS 441k, PRN
    344k…; NAV notices 3.26M, Form 8.3 328k, final terms 197k, holdings 136k, PDMR 119k, annual
    financial reports 39k, half-year 34k). No filter = the latest disclosures first.
    lei is an exact case-sensitive LEI criterion; company a case-insensitive partial name
    match; text a match_all_words | exact_match search over document content OR headline
    (the upstream serves this path for the latest version of each disclosure only); types /
    sources / formats / tag_esef are AND'ed facets (stored vocabulary, case-insensitive here);
    from_date / to_date bound publication_date | submitted_date (YYYY-MM-DD, inclusive).
    Tagged rows (ESEF annual reports, 3,063) carry html_url (XHTML), json_url (XBRL-JSON) and
    csv_url — all keyless plain GETs. offset + limit must stay within the first 10,000 hits."""
    body = nsm_body(lei=lei, company=company, text=text, text_mode=text_mode, types=types,
                    sources=sources, formats=formats, tag_esef=tag_esef, date_field=date_field,
                    from_date=from_date, to_date=to_date, sort=sort, order=order, offset=offset,
                    limit=limit)
    r = _search("nsm", body, cache, no_cache)
    rows = [nsm_row(h) for h in _hits(r["data"], "nsm")[1]]
    return _envelope("nsm", body, r["data"], rows, body["from"], body["size"], r)


# —— Official List (index official-list-main) ——

LISTING_CATEGORIES = (
    "Equity shares (commercial companies)",
    "Equity shares (shell companies)",
    "Equity shares (international commercial companies secondary listing)",
    "Equity shares (transition)",
    "Closed-ended investment funds",
    "Open-ended investment companies",
    "Non-equity shares and non-voting equity shares",
    "Certificates representing certain securities (depository receipts)",
    "Debt and debt-like securities",
    "Securitised derivatives",
    "Warrants, options and other miscellaneous securities",
)
_CATEGORY_VOCAB = {c.lower(): c for c in LISTING_CATEGORIES}
OL_SORTS = ("security_isin", "security_initial_admission_date", "security_initial_admission_date,security_isin",
            "lei", "last_updated_date")


def official_list_body(*, listing_category=None, lei=None, security_isin=None, text=None,
                       from_date=None, to_date=None, sort="security_isin", order="asc",
                       offset=0, limit=20):
    """the Official List query body (pure). criteriaObj is sent only when something narrows
    the list — an unfiltered body is the whole Official List, a category the FCA adds later
    included."""
    criteria = []
    cats = _canon(listing_category, "listing_category", _CATEGORY_VOCAB, strict=True)
    if cats:
        criteria.append({"name": "listing_category", "value": cats})
    if lei:
        criteria.append({"name": "lei", "value": _upper(lei, "lei", _LEI)})
    if security_isin:
        criteria.append({"name": "security_isin", "value": _upper(security_isin, "security_isin", _ISIN,
                                                                    "a 12-character ISIN")})
    dates = None
    if from_date or to_date:
        dates = [{"name": "security_initial_admission_date",
                  "value": {"from": _dmy(from_date, "from_date") if from_date else None,
                            "to": _dmy(to_date, "to_date") if to_date else None}}]
    body = {"from": _int(offset, "offset", 0, default=0), "size": _int(limit, "limit", 1, 5000, 20),
            "sort": _choice(sort, "sort", OL_SORTS, "security_isin"),
            "sortorder": _choice(order, "order", ("asc", "desc"), "asc")}
    t = " ".join(str(text).split()) if text else ""
    if t:
        body["primarySearch"] = [{"name": "security_isin", "value": t}, {"name": "lei", "value": t},
                                 {"name": "issuer_name", "value": t}]
    if criteria or dates:
        body["criteriaObj"] = {"criteria": criteria, "dateCriteria": dates}
    _window(body["from"], body["size"])
    return body


def official_list_row(hit):
    """one Official List hit -> row (pure): _source verbatim + api_id (the _id)."""
    row = {"api_id": hit.get("_id")}
    row.update(hit.get("_source") or {})
    return row


def official_list(*, listing_category=None, lei=None, security_isin=None, text=None, from_date=None,
                  to_date=None, sort="security_isin", order="asc", offset=0, limit=20,
                  cache=None, no_cache=False):
    """→ {total, offset, limit, row_count, rows[], next_offset, window_note?, params, _meta};
    the FCA Official List — the securities admitted to official trading under UK law
    (15,160 live: ISIN, name, listing category, status, issuer LEI + name, initial admission
    date). listing_category (repeatable) narrows to one of the 11 categories — equity shares
    (commercial companies) 380, closed-ended investment funds, debt and debt-like securities…;
    lei / security_isin are exact (case-sensitive upstream — uppercased here); text is a
    3-way OR search (ISIN, LEI, issuer name — partial, not the security name);
    from_date / to_date bound security_initial_admission_date (YYYY-MM-DD, inclusive). A row
    carries the fields the upstream record holds — a placeholder record (temporary ISIN)
    has no LEI, name or admission date yet. offset + limit must stay within 10,000."""
    body = official_list_body(listing_category=listing_category, lei=lei, security_isin=security_isin,
                              text=text, from_date=from_date, to_date=to_date, sort=sort, order=order,
                              offset=offset, limit=limit)
    r = _search("official_list", body, cache, no_cache)
    rows = [official_list_row(h) for h in _hits(r["data"], "official_list")[1]]
    return _envelope("official_list", body, r["data"], rows, body["from"], body["size"], r)


# —— Official List daily activity (index official-list-daily-activity) ——

ACTIVITIES = ("Admission", "Suspension", "Restoration", "Cancellation")
ACTIVITY_SORTS = ("security_effective_datetime", "security_isin")


def activity_body(*, security_activity, from_date=None, to_date=None, sort="security_effective_datetime",
                  order="desc", offset=0, limit=20):
    """the daily-activity query body (pure). security_activity is REQUIRED and validated here
    (an unknown value is ignored upstream — all 119,810 rows answer); the four kinds cannot be
    combined. securityActivityDateCriteria is an OBJECT (a list answers 404)."""
    if security_activity is None or str(security_activity).strip() == "":
        raise SdkError("usage_error", provider=ID,
                       detail="security_activity is required (Admission | Suspension | Restoration | "
                              "Cancellation) — without it the upstream index answers every kind")
    body = {"from": _int(offset, "offset", 0, default=0), "size": _int(limit, "limit", 1, 5000, 20),
            "security_activity": _choice(security_activity, "security_activity", ACTIVITIES),
            "sort": _choice(sort, "sort", ACTIVITY_SORTS, "security_effective_datetime"),
            "sortorder": _choice(order, "order", ("asc", "desc"), "desc")}
    if from_date or to_date:
        body["securityActivityDateCriteria"] = {
            "name": "security_effective_datetime",
            "value": {"from": _iso_bound(from_date, "from_date", False) if from_date else None,
                      "to": _iso_bound(to_date, "to_date", True) if to_date else None}}
    _window(body["from"], body["size"])
    return body


def official_list_activity(*, security_activity, from_date=None, to_date=None,
                           sort="security_effective_datetime", order="desc", offset=0, limit=20,
                           cache=None, no_cache=False):
    """→ {total, offset, limit, row_count, rows[], next_offset, window_note?, params, _meta};
    the Official List daily activity log — admissions (102,667), cancellations (16,204),
    suspensions (733) and restorations (206) of officially listed securities, with the
    effective datetime, ISIN, issuer + LEI and listing category (suspension / cancellation
    rows also the security name). security_activity is one of Admission | Suspension |
    Restoration | Cancellation; from_date / to_date bound security_effective_datetime
    (YYYY-MM-DD, inclusive; one-sided allowed). Admissions exceed the 10,000 window — walk
    them by date window."""
    body = activity_body(security_activity=security_activity, from_date=from_date, to_date=to_date,
                         sort=sort, order=order, offset=offset, limit=limit)
    r = _search("official_list_activity", body, cache, no_cache)
    rows = [dict(h.get("_source") or {}) for h in _hits(r["data"], "official_list_activity")[1]]
    return _envelope("official_list_activity", body, r["data"], rows, body["from"], body["size"], r)


# —— Financial Instrument Data Search (index firds-view) ——

FIRDS_CRITERIA = ("fininstrmgnlattrbts_id", "tradgvnrltdattrbts_id", "isin_sngl_noindx", "isin_bskt",
                  "issr", "fininstrmgnlattrbts_clssfctntp")
FIRDS_SORTS = ("fininstrmgnlattrbts_id", "isin_sngl_noindx", "fininstrmgnlattrbts_fullnm", "issr",
               "tradgvnrltdattrbts_frsttraddt", "tradgvnrltdattrbts_termntndt", "mtrtydt",
               "techattrbts_pblctnprd_frdt", "fininstrmgnlattrbts_clssfctntp")
FIRDS_DATE_FIELDS = {"publication": "techattrbts_pblctnprd_frdt", "first_trade": "tradgvnrltdattrbts_frsttraddt",
                     "termination": "tradgvnrltdattrbts_termntndt"}
FAR_FUTURE = "31/12/2099"  # FIRDS requires BOTH date bounds (from-only answers 404)
_CFI = re.compile(r"^[A-Z0-9]{6}$")


def firds_body(*, fininstrmgnlattrbts_id=None, tradgvnrltdattrbts_id=None, isin_sngl_noindx=None,
               isin_bskt=None, issr=None, fininstrmgnlattrbts_clssfctntp=None, keyword=None,
               active_only=True, date_field="publication", from_date=None, to_date=None,
               sort="fininstrmgnlattrbts_id", order="asc", offset=0, limit=20):
    """the FIRDS query body (pure). Criteria are strings (an array value answers a silent 0);
    keyword (free text) and criteria are mutually exclusive upstream — enforced here."""
    crit = {"fininstrmgnlattrbts_id": fininstrmgnlattrbts_id,
            "tradgvnrltdattrbts_id": tradgvnrltdattrbts_id,
            "isin_sngl_noindx": isin_sngl_noindx, "isin_bskt": isin_bskt, "issr": issr,
            "fininstrmgnlattrbts_clssfctntp": fininstrmgnlattrbts_clssfctntp}
    given = {k: v for k, v in crit.items() if v is not None and str(v).strip() != ""}
    has_dates = bool(from_date or to_date)
    if keyword is not None and str(keyword).strip():
        if given or has_dates:
            raise SdkError("usage_error", provider=ID,
                           detail="keyword cannot be combined with criteria or date bounds (the upstream "
                                  "reads either the keyword or the criteria object)")
        body = {"from": _int(offset, "offset", 0, default=0), "size": _int(limit, "limit", 1, 5000, 20),
                "keyword": " ".join(str(keyword).split())}
        _window(body["from"], body["size"])
        return body
    # each criterion carries its own validator (ISIN / MIC / LEI / CFI shape)
    criteria = []
    if "fininstrmgnlattrbts_id" in given:
        criteria.append({"name": "fininstrmgnlattrbts_id",
                         "value": _upper(given["fininstrmgnlattrbts_id"], "fininstrmgnlattrbts_id",
                                         _ISIN, "a 12-character ISIN")})
    if "tradgvnrltdattrbts_id" in given:
        criteria.append({"name": "tradgvnrltdattrbts_id",
                         "value": _upper(given["tradgvnrltdattrbts_id"], "tradgvnrltdattrbts_id",
                                         re.compile(r"^[A-Z0-9]{4}$"), "a 4-character MIC (e.g. XLON)")})
    if "isin_sngl_noindx" in given:
        criteria.append({"name": "isin_sngl_noindx",
                         "value": _upper(given["isin_sngl_noindx"], "isin_sngl_noindx", _ISIN,
                                         "a 12-character ISIN")})
    if "isin_bskt" in given:
        criteria.append({"name": "isin_bskt",
                         "value": _upper(given["isin_bskt"], "isin_bskt", _ISIN, "a 12-character ISIN")})
    if "issr" in given:
        criteria.append({"name": "issr", "value": _upper(given["issr"], "issr", _LEI)})
    if "fininstrmgnlattrbts_clssfctntp" in given:
        criteria.append({"name": "fininstrmgnlattrbts_clssfctntp",
                         "value": _upper(given["fininstrmgnlattrbts_clssfctntp"],
                                         "fininstrmgnlattrbts_clssfctntp", _CFI,
                                         "a 6-character CFI code (e.g. ESVUFR)")})
    criteria.append({"name": "techattrbts_nvrpblshd", "value": "false"})
    if active_only:
        criteria.append({"name": "active_flag", "value": "Y"})
    dates = None
    if has_dates:
        dates = [{"name": FIRDS_DATE_FIELDS[_choice(date_field, "date_field", tuple(FIRDS_DATE_FIELDS),
                                                          "publication")],
                  "value": {"from": _dmy(from_date, "from_date") if from_date else None,
                            "to": _dmy(to_date, "to_date") if to_date else FAR_FUTURE}}]
    body = {"from": _int(offset, "offset", 0, default=0), "size": _int(limit, "limit", 1, 5000, 20),
            "sort": _choice(sort, "sort", FIRDS_SORTS, "fininstrmgnlattrbts_id"),
            "sortorder": _choice(order, "order", ("asc", "desc"), "asc"),
            "criteriaObj": {"criteria": criteria, "dateCriteria": dates}}
    _window(body["from"], body["size"])
    return body


def firds_row(hit):
    """one FIRDS hit -> row (pure): _source verbatim (the field set varies by instrument
    type — 26 keys on an equity line) + api_id (the _id)."""
    row = {"api_id": hit.get("_id")}
    row.update(hit.get("_source") or {})
    return row


def firds_search(*, fininstrmgnlattrbts_id=None, tradgvnrltdattrbts_id=None, isin_sngl_noindx=None,
                 isin_bskt=None, issr=None, fininstrmgnlattrbts_clssfctntp=None, keyword=None,
                 active_only=True, date_field="publication", from_date=None, to_date=None,
                 sort="fininstrmgnlattrbts_id", order="asc", offset=0, limit=20,
                 cache=None, no_cache=False):
    """→ {total, offset, limit, row_count, rows[], next_offset, window_note?, params, _meta};
    the FCA Financial Instrument Data Search — 169.6M published, active instruments
    (ISIN-level reference data: full/short name, CFI classification, currency, issuer LEI,
    trading venue + first/last trade dates, publication period, maturity…). Criteria AND:
    fininstrmgnlattrbts_id = the instrument's own ISIN; tradgvnrltdattrbts_id = MIC
    (UPPERCASE — XLON 28,856 active lines); issr = issuer LEI (Barclays PLC 3,488 active);
    fininstrmgnlattrbts_clssfctntp = CFI (XLON + ESVUFR = 1,429 LSE voting unrestricted fully
    paid registered share lines); isin_sngl_noindx = the UNDERLYING ISIN of a derivative;
    isin_bskt = basket ISIN. date_field + from_date / to_date bound the first publication
    date (default) | first trade date | termination date — the upstream needs both bounds, so
    a missing to_date is filled with 31/12/2099. active_only keeps active_flag=Y (set False
    to include terminated instruments); never-published records are always excluded. keyword
    = the upstream free-text search (its own result set, terminated lines included; cannot be
    combined with criteria or dates)."""
    body = firds_body(fininstrmgnlattrbts_id=fininstrmgnlattrbts_id,
                      tradgvnrltdattrbts_id=tradgvnrltdattrbts_id, isin_sngl_noindx=isin_sngl_noindx,
                      isin_bskt=isin_bskt, issr=issr,
                      fininstrmgnlattrbts_clssfctntp=fininstrmgnlattrbts_clssfctntp, keyword=keyword,
                      active_only=active_only, date_field=date_field, from_date=from_date,
                      to_date=to_date, sort=sort, order=order, offset=offset, limit=limit)
    r = _search("firds", body, cache, no_cache)
    rows = [firds_row(h) for h in _hits(r["data"], "firds")[1]]
    return _envelope("firds", body, r["data"], rows, body["from"], body["size"], r)
