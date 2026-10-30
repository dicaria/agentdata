"""edgar_fts — SEC EDGAR Full-Text Search (2001+ full-text filing search; keyless).

Official fair-access policy caps at 10 req/s and requires a UA — we set 5 rps/burst 5 (0.2.7 realignment: the old
5/10 worst case was 15>10 in a 1s window, an lda-type violation; quota semantics 5+5=10≤10; the UA is attached
uniformly by the transport layer).
First case of the "full-text search exception": we do not build a local terabyte-scale inverted index and instead
lean on the official compute as an external read-only FTS face.
Live-shape check:
hits.hits[]{_id="adsh:file", _source{adsh,ciks[],display_names[],root_forms[],file_date,form}}.
Date-range pitfall (probed live 2026-10-20): upstream applies dateRange=custom only when startdt AND enddt are
both given — a single end is silently ignored (tell-tale signs: total pinned at 10000 + relation:"gte" + out-of-range
file_date with ok:true) — so if either end is given the other is filled in (missing startdt → corpus start 2001-01-01,
missing enddt → today); date_range echoes the window actually in effect.
"""
import re

provider = {
    "id": "edgar-fts",
    "baseUrl": "https://efts.sec.gov",
    "rate": {"rps": 5, "burst": 5},  # quota semantics at the line: 5+5×1s=10≤SEC 10/s (0.2.7 realignment)
    "ops": {
        "search": {"path": "/LATEST/search-index"},  # params: q, forms, startdt, enddt, dateRange (assembled query)
    },
    "ttl": {"search": 24 * 3600},  # new filings keep landing, a search page stays valid for a day
}

_TAIL_PARENS = re.compile(r"(\s*\([^()]*\))+\s*$")


def clean_display_name(v):
    """Strip the parenthesized tail noise from upstream display_names[0] ('NAME  (TICKER)  (CIK ##########)' → 'NAME').

    Double spaces + a CIK tail that duplicates the cik field already in the card; mid-string parentheses such as
    'X (formerly Y) Inc.' are left untouched."""

    if not isinstance(v, str):
        return v if v is not None else None
    cleaned = _TAIL_PARENS.sub("", v).strip()
    return cleaned or v


def search_fulltext(q, *, forms=None, startdt=None, enddt=None, limit=10, cache=None, no_cache=False):
    """→ {total, total_relation, hits[], date_range, _meta}; hit.adsh directly composes the accession key shared with the SEC corpus line, doc_url points at the human-readable original.
    total_relation:"gte" = upstream truncation (≥ ten thousand, not an exact value), "eq" = exact; date_range=None means no date window was enabled."""
    from ..transport import call_provider
    from ..errors import SdkError

    query = str(q or "").strip()
    if not query:
        raise SdkError("usage_error", provider="edgar-fts", detail="fulltext requires --q")
    params = {"q": query}
    if forms:
        params["forms"] = str(forms)  # form-type filter is decoupled from the date window (forms no longer triggers dateRange)
    date_range = None
    if startdt or enddt:  # fill the missing end: a single end is silently ignored upstream, both ends are required
        from ..daterange import resolve as _range
        _start, _end, date_range = _range(startdt, enddt, default_start="2001-01-01",
                                          provider=provider["id"])
        params["startdt"], params["enddt"] = _start, _end
        params["dateRange"] = "custom"
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    hits = ((r["data"] or {}).get("hits") or {}).get("hits") or []
    cap = min(max(1, int(limit) or 10), 100)
    rows = []
    for h in hits[:cap]:
        s = h.get("_source") or {}
        cik = (s.get("ciks") or [None])[0]
        _id = h.get("_id") or ""
        file = _id.split(":")[1] if ":" in _id else None
        adsh = s.get("adsh") or (_id.split(":")[0] if _id else None)
        rows.append({
            "adsh": adsh,  # accession number — same key as the SEC corpus line
            "cik": cik,
            "company": clean_display_name((s.get("display_names") or [None])[0]),  # strip the (TICKER)(CIK) parenthesized tail
            "form_type": s.get("form") or (s.get("root_forms") or [None])[0],
            "file_date": s.get("file_date"),
            "period_ending": s.get("period_ending"),
            "doc_url": (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/{file}"
                        if cik and adsh and file else None),
        })
    total_obj = (((r["data"] or {}).get("hits") or {}).get("total") or {})
    total = total_obj.get("value")
    return {"total": total if total is not None else len(rows),
            "total_relation": total_obj.get("relation"),  # gte=truncated (≥ ten thousand), not an exact value
            "hits": rows, "limit_applied": cap, "date_range": date_range, "_meta": r}  # cap = client-side slice size, truncation must stay visible


def search_raw(q, *, forms=None, startdt=None, enddt=None, limit=10, cache=None, no_cache=False):
    """→ {total, total_relation, hits[], limit_applied, date_range, params, _meta}; the four params pass through verbatim.
    params = the actually sent query-string keys (q/forms/startdt/enddt[/dateRange=custom]) — after end completion both ends are always present (a single end is
    silently ignored upstream, measured 2026-10-20), date_range echoes the window actually in effect; the echo is replayable."""
    r = search_fulltext(q, forms=forms, startdt=startdt, enddt=enddt,
                        limit=limit, cache=cache, no_cache=no_cache)
    params = {"q": str(q).strip()}
    if forms:
        params["forms"] = str(forms)
    if r["date_range"]:
        params["startdt"] = r["date_range"]["startdt"]
        params["enddt"] = r["date_range"]["enddt"]
        params["dateRange"] = "custom"
    return {**r, "params": params}
