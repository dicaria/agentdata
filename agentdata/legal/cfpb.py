"""cfpb — US CFPB Consumer Complaint Database provider (consumerfinance.gov; keyless, CC0).

legal consumer-complaint face (0.3.31; admitted 2026-11-03, probed tmp/probe-0331). Two upstream
surfaces, both keyless, both covered by the official OpenAPI spec (cfpb/ccdb5-api, the spec file
swagger-config.yaml pulled from the /documentation/ initializer):

- `GET .../data-research/consumer-complaints/search/api/v1/` — the complaint search. The envelope is
  an OpenSearch shape, NOT a plain list:
  `{took, timed_out, _shards, hits{total{value,relation}, max_score, hits[{_index,_id,_score,_source}]},
  aggregations?, _meta{license,last_updated,last_indexed,total_record_count,is_data_stale,
  has_data_issue,break_points}}`; `_source` carries the 15 official fields (complaint_id / company /
  product / sub_product / issue / sub_issue / date_received / date_sent_to_company / state / zip_code /
  submitted_via / timely / company_response / company_public_response / tags).
- `GET .../api/v1/_suggest_company/` — the company typeahead: a **bare JSON array of strings**
  (the spec models a SuggestResult object; the live wire is the array — both shapes are parsed).

**Four upstream traps (pinned 2026-11-03, probe files in tmp/probe-0331/):**

1. `company=` is EXACT and case-sensitive: `company=TRANSUNION` → 0 hits, while the corpus's own
   spelling `company=TRANSUNION INTERMEDIATE HOLDINGS, INC.` → 2,591,659 hits. The typeahead
   (cfpb_suggest_company) is the resolution channel — a brand name is NOT the corpus key.
2. `term=` is a DEAD parameter — accepted and silently ignored: `field=company&term=Discover`
   returns the whole corpus (18,879,284 hits, every score 1.0). The live name is `search_term`.
3. `no_aggs=false` (the upstream default) returns the aggregation block — ~380KB and ~20s per call
   (probed: 400,573 bytes). The face takes the lean path (`no_aggs=true`) unless asked otherwise.
4. The aggregation block's per-field `doc_count` is NOT reliably filter-scoped: probed with a
   0-hit filter the product/state aggregations collapsed to 0 while the company aggregation still
   reported the whole corpus (18,879,284); with a 2,591,659-hit filter the state aggregation still
   reported 18,879,284. So the block is a value-domain census, not a facet count of the filter —
   the face says so in its reason and keeps it opt-in.

Closed sets measured corpus-wide from the aggregation census of 2026-11-03 (the bucket doc_counts
sum to the full corpus, so the value domain is complete): timely = {Yes, No}; submitted_via = {Web,
Referral, Phone, Postal mail, Fax, Email}; company_response = 8 values (+21 rows with none);
product = 21 plain values (the upstream also accepts the combined form `Product•SubProduct` per the
spec); state = 63 codes (50 states + DC + territories + the armed-forces codes AE/AP/AA + the
free-associated states FM/PW/MH).

TTL: complaints 6h (the corpus is re-indexed daily — `_meta.last_updated` 2026-11-03T12:00:00-05:00);
suggest 24h. Polite 0.5 rps (the upstream publishes no window number).
"""
import re

from ..errors import SdkError

provider = {
    "id": "cfpb",
    "baseUrl": "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # the trailing slash is part of the route (the spec's server url ends in /api/v1/)
        "complaints": {"path": "/", "timeout": 60.0},
        # the typeahead route needs its trailing slash too, and its wire param is `text`
        # (the spec names the parameter `suggest_text`, but `suggest_text=` gets a 400
        #  {"text": ["This field is required."]})
        "suggest_company": {"path": "/_suggest_company/", "timeout": 60.0},
    },
    "ttl": {"complaints": 6 * 3600, "suggest_company": 24 * 3600},
}

# The row whitelist — the 15 official complaint fields plus the date_indexed stamp some rows carry.
_ROW_COLS = ("complaint_id", "company", "product", "sub_product", "issue", "sub_issue",
             "date_received", "date_sent_to_company", "state", "zip_code", "submitted_via",
             "timely", "company_response", "company_public_response", "tags", "date_indexed")

# The upstream `field` enum (OpenAPI) and the `sort` enum (OpenAPI).
_FIELDS = ("company", "all")
_SORTS = ("relevance_desc", "relevance_asc", "created_date_desc", "created_date_asc")

# Closed sets measured corpus-wide (aggregation census 2026-11-03; see the module docstring).
_TIMELY = ("Yes", "No")
_SUBMITTED_VIA = ("Web", "Referral", "Phone", "Postal mail", "Fax", "Email")
_COMPANY_RESPONSE = ("Closed with explanation", "Closed with non-monetary relief", "In progress",
                     "Closed with monetary relief", "Untimely response", "Closed without relief",
                     "Closed", "Closed with relief")
_STATES = ("TX", "FL", "CA", "GA", "NY", "IL", "PA", "NC", "NJ", "AL", "MD", "SC", "LA", "MI", "OH",
           "VA", "MS", "AZ", "TN", "NV", "MA", "IN", "MO", "WA", "WI", "CT", "CO", "AR", "MN", "OK",
           "DE", "KY", "PR", "DC", "OR", "UT", "KS", "RI", "IA", "NM", "HI", "NE", "WV", "NH", "ID",
           "ME", "ND", "AK", "MT", "SD", "WY", "VT", "VI", "AE",
           "UNITED STATES MINOR OUTLYING ISLANDS", "AP", "GU", "AS", "AA", "MP", "FM", "PW", "MH")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The array-shaped filters — upstream `explode: true` → repeated keys on the wire
# (company / product / issue / state / zip_code / submitted_via / timely / company_response /
#  company_public_response / tags).
_LIST_FILTERS = ("company", "product", "issue", "state", "zip_code", "submitted_via", "timely",
                 "company_response", "company_public_response", "tags")

# The aggregation digest cap — the upstream's company aggregation alone carries 6,500 buckets
# (probe 2026-11-03); the envelope keeps a bounded prefix of each field's bucket list.
_AGG_BUCKET_CAP = 50


def _as_list(value):
    """A filter value → the list to explode on the wire. A string is ONE value (never split on
    commas — the corpus' company names carry commas: "TRANSUNION INTERMEDIATE HOLDINGS, INC.");
    a list/tuple passes through."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value]
    else:
        items = [str(value).strip()]
    items = [v for v in items if v]
    return items or None


def _enum_wall(provider_id, name, value, allowed, note):
    """A closed-set check with the upstream evidence in the message (the house rule: a wall
    carries its evidence, it is never an unexplained refusal)."""
    if value not in allowed:
        raise SdkError("usage_error", provider=provider_id,
                       detail=f"{name} must be one of {' / '.join(allowed)} ({note}), got '{value}'")


def _date_wall(provider_id, name, value):
    if not _DATE_RE.match(str(value or "")):
        raise SdkError("usage_error", provider=provider_id,
                       detail=f"{name} must be YYYY-MM-DD (the upstream schema: format=date, "
                              f"e.g. 2017-03-04), got '{value}'")


def _rows_from_hits(hits):
    """The upstream hits[] → the row whitelist (pure function)."""
    rows = []
    for h in hits or []:
        src = h.get("_source") or {}
        rows.append({k: src.get(k) for k in _ROW_COLS if k in src})
    return rows


def _agg_digest(aggs):
    """The upstream aggregation block → a bounded digest (pure function).

    Per field: the upstream doc_count, how many buckets the field has, and the first
    `_AGG_BUCKET_CAP` buckets (upstream order = doc_count desc). The doc_count is NOT reliably
    filter-scoped upstream (see the module docstring) — the digest repeats it verbatim."""
    out = {}
    for field, block in (aggs or {}).items():
        inner = (block or {}).get(field) or {}
        buckets = inner.get("buckets") or []
        out[field] = {
            "doc_count": (block or {}).get("doc_count"),
            "buckets_total": len(buckets),
            "buckets": [{"key": b.get("key"), "doc_count": b.get("doc_count")}
                        for b in buckets[:_AGG_BUCKET_CAP]],
            "truncated": len(buckets) > _AGG_BUCKET_CAP,
        }
    return out


def search_after_from(break_points, page):
    """The upstream pagination token: `_meta.break_points["<page>"]` = [score, id] → the
    `search_after` value "<score>_<id>" (the OpenAPI description: 'use the value page=n&frm=25&
    search_after=k_id', where k_id is the two break-point values joined by an underscore)."""
    bp = (break_points or {}).get(str(page))
    if not bp or len(bp) < 2:
        return None
    return f"{bp[0]}_{bp[1]}"


def complaints_raw(search_term=None, *, field=None, company=None, product=None, issue=None,
                   state=None, zip_code=None, submitted_via=None, timely=None,
                   company_response=None, company_public_response=None, tags=None,
                   date_received_min=None, date_received_max=None,
                   company_received_min=None, company_received_max=None,
                   frm=None, size=10, sort=None, search_after=None, aggregations=False,
                   cache=None, no_cache=False):
    """Search the complaint database → {total, relation, count, rows, meta…, params, _meta}.

    search_term = the full-text term (fuzzy; `field=company` narrows it to the company field);
    company = the corpus' exact, case-sensitive company string (use cfpb_suggest_company to get
    it); the array filters explode into repeated keys; date_received_* / company_received_* are
    YYYY-MM-DD windows; frm = the offset, size = the page size (1-100), search_after = the
    upstream pagination token; aggregations = ask for the aggregation block (a corpus-wide value
    census, ~380KB / ~20s upstream — off by default)."""
    from ..transport import call_provider

    term = str(search_term).strip() if search_term is not None else ""
    qs = {}
    if term:
        qs["search_term"] = term
    if field is not None:
        _enum_wall("cfpb", "field", field, _FIELDS, "the upstream enum (OpenAPI)")
        if not term:
            raise SdkError("usage_error", provider="cfpb",
                           detail="field only takes effect together with search_term (the upstream "
                                  "description: 'If the parameter search_term has a value, use field "
                                  "to specify which field is searched') — passing it alone is a "
                                  "silent no-op that returns the whole corpus")
        qs["field"] = field
    for name, value in (("company", company), ("product", product), ("issue", issue),
                        ("state", state), ("zip_code", zip_code), ("submitted_via", submitted_via),
                        ("timely", timely), ("company_response", company_response),
                        ("company_public_response", company_public_response), ("tags", tags)):
        items = _as_list(value)
        if items:
            qs[name] = items
    if timely:
        for t in qs.get("timely") or []:
            _enum_wall("cfpb", "timely", t, _TIMELY,
                       "the corpus-wide census of 2026-11-03 — the bucket counts sum to the whole "
                       "corpus, so this is the complete value domain")
    if submitted_via:
        for s in qs.get("submitted_via") or []:
            _enum_wall("cfpb", "submitted_via", s, _SUBMITTED_VIA,
                       "the corpus-wide census of 2026-11-03 (bucket counts sum to the whole corpus)")
    if company_response:
        for c in qs.get("company_response") or []:
            _enum_wall("cfpb", "company_response", c, _COMPANY_RESPONSE,
                       "the corpus-wide census of 2026-11-03 (8 values; 21 complaints carry none)")
    if state:
        states = [str(x).upper() for x in (qs.get("state") or [])]
        for st in states:
            _enum_wall("cfpb", "state", st, _STATES,
                       "the corpus-wide census of 2026-11-03 (63 codes: the states + DC + the "
                       "territories + the armed-forces codes; the upstream wants the abbreviation)")
        qs["state"] = states
    for name, value in (("date_received_min", date_received_min),
                        ("date_received_max", date_received_max),
                        ("company_received_min", company_received_min),
                        ("company_received_max", company_received_max)):
        if value:
            _date_wall("cfpb", name, value)
            qs[name] = value
    sz = int(size if size is not None else 10)
    if not 1 <= sz <= 100:
        raise SdkError("usage_error", provider="cfpb",
                       detail=f"size must be 1-100 (the upstream hard max — OpenAPI size: minimum 1, "
                              f"maximum 100), got '{size}'")
    qs["size"] = sz
    fr = int(frm or 0)
    if not 0 <= fr <= 100000:
        raise SdkError("usage_error", provider="cfpb",
                       detail=f"frm must be 0-100000 (the upstream offset window — OpenAPI frm: "
                              f"maximum 100000; the schema's minimum 1 is the first-page convention, "
                              f"the default offset is 0), got '{frm}'")
    if fr:
        qs["frm"] = fr
    if sort is not None:
        _enum_wall("cfpb", "sort", sort, _SORTS, "the upstream enum (OpenAPI)")
        qs["sort"] = sort
    if search_after:
        qs["search_after"] = str(search_after)
    # the upstream default is no_aggs=false (the ~380KB aggregation block); the lean path is ours
    qs["no_aggs"] = "false" if aggregations else "true"

    r = call_provider(provider, "complaints", qs, cache=cache, no_cache=no_cache)
    data = r["data"] or {}
    hits = data.get("hits") or {}
    total_obj = hits.get("total") or {}
    try:
        total = int(total_obj.get("value") or 0)
    except (TypeError, ValueError):
        total = 0
    meta = data.get("_meta") or {}
    rows = _rows_from_hits(hits.get("hits"))
    return {
        "total": total,
        "relation": total_obj.get("relation"),
        "count": len(rows),
        "rows": rows,
        "size": sz,
        "frm": fr,
        "sort": sort,
        "aggregations": _agg_digest(data.get("aggregations")) if data.get("aggregations") else None,
        "last_updated": meta.get("last_updated"),
        "last_indexed": meta.get("last_indexed"),
        "total_record_count": meta.get("total_record_count"),
        "is_data_stale": meta.get("is_data_stale"),
        "has_data_issue": meta.get("has_data_issue"),
        "break_points": meta.get("break_points") or {},
        "license": meta.get("license"),
        "params": qs,
        "_meta": r,
    }


def suggest_company_raw(text=None, *, size=10, cache=None, no_cache=False):
    """The company typeahead → {text, count, suggestions, params, _meta}.

    `text` is required (the upstream's required parameter; an empty text gets a 400
    {"text": ["This field is required."]}). The live wire is a bare JSON array of company
    strings — the corpus' own spellings, which are what the complaints face's `company=`
    filter (exact, case-sensitive) needs."""
    from ..transport import call_provider

    t = str(text or "").strip()
    if not t:
        raise SdkError("usage_error", provider="cfpb",
                       detail="text is required (the upstream typeahead's required parameter — an "
                              "empty text gets a 400 {\"text\": [\"This field is required.\"]})")
    sz = int(size if size is not None else 10)
    if not 1 <= sz <= 100:
        raise SdkError("usage_error", provider="cfpb",
                       detail=f"size must be 1-100 (the upstream hard max — OpenAPI size: minimum 1, "
                              f"maximum 100), got '{size}'")
    qs = {"text": t, "size": sz}
    r = call_provider(provider, "suggest_company", qs, cache=cache, no_cache=no_cache)
    data = r["data"]
    if isinstance(data, dict):        # the spec's SuggestResult object shape — the live wire is an array
        items = data.get("suggestions") or data.get("results") or []
    else:
        items = data or []
    return {"text": t, "count": len(items),
            "suggestions": [str(x) for x in items],
            "params": qs, "_meta": r}
