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


# ---------- census mode (0.3.67, premium §9.6 fix ticket: completeness over the 100-hit page) ----------
#
# PAGINATION LAW (probed live 2026-11-17): the upstream ES answers `from` as a true offset (first_id shifts),
# ignores page/offset/start entirely, and hard-caps the page at 100 rows (size=200/500 answered the same 100).
# The result window is 10,000: from=9900 still answers 100 rows, from=9999 answers 200 + hits.hits=[] + NO
# hits.total — the SILENT over-window shape a naive reader would score as a legal empty page. Census therefore
# never sends from beyond 9900 and treats a missing total as "window too deep", never as zero.
# QUOTED-PREDICATE LAW (premium §9.1 ⚠️#2, confirmed): q='company:"IREN Ltd"' is NOT a field filter — the
# prefix rides as a plain full-text term (3923 vs bare 10000-gte, first hit an NPORT primary_doc): entity
# scoping is a LOCAL post-filter (--census-entity), never a server-side promise.
# BISECTION LAW: a window with total_relation="gte" (the 10k floor) or total>10000 is split at its date
# midpoint until every leaf window is exact (≤10000, relation eq) — then all pages are harvested and the
# rows deduped by _id (docs) and adsh (filings). A single-day leaf still at the floor is honestly reported
# in overflow_windows (counted as ≥10k, excluded from the totals), never silently dropped.

_PAGE = 100          # upstream page size (size param ignored, probed 2026-11-17)
_FROM_CEILING = 9900  # from+100<=10000 (ES max_result_window); beyond it the silent no-total shape


def _census_page(q, forms, startdt, enddt, from_, *, cache=None, no_cache=False):
    """One page of one window → (total_value|None, relation|None, hits[] verbatim)."""
    from ..transport import call_provider

    params = {"q": q, "from": from_, "startdt": startdt, "enddt": enddt, "dateRange": "custom"}
    if forms:
        params["forms"] = str(forms)
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    h = (r["data"] or {}).get("hits") or {}
    total_obj = h.get("total") or {}
    return total_obj.get("value"), total_obj.get("relation"), list(h.get("hits") or []), r


def _bisect(startdt, enddt):
    """Midpoint split of [startdt, enddt] → (left, right); None, None when the window is a single day."""
    from datetime import date, timedelta

    s = date.fromisoformat(startdt)
    e = date.fromisoformat(enddt)
    if e <= s:
        return None, None
    mid = s + (e - s) // 2
    return (startdt, mid.isoformat()), ((mid + timedelta(days=1)).isoformat(), enddt)


def census(q, *, forms=None, startdt=None, enddt=None, entity=None,
           max_requests=400, limit=10, cache=None, no_cache=False):
    """→ {mode:"census", docs_total, filings_total, windows[], overflow_windows[], requests, pages, rows[], ...}.

    The full-window sweep behind the premium §9.6 fix ticket: adaptive date bisection until every leaf window
    is exact, then every page harvested, then dedup by _id/adsh — the number workbuddy had to hand-roll in
    1h5m (and still got wrong) falls out as `filings_total`. `entity` (case-insensitive substring over the
    row's display name) applies the QUOTED-PREDICATE LAW locally — server-side q stays verbatim."""
    from ..errors import SdkError

    query = str(q or "").strip()
    if not query:
        raise SdkError("usage_error", provider="edgar-fts", detail="census requires --q")
    from ..daterange import resolve as _range
    w_start, w_end, _ = _range(startdt, enddt, default_start="2001-01-01",
                               provider=provider["id"])

    requests = 0
    pages = 0
    hits = []          # verbatim _source-bearing hits, deduped by _id at the end
    seen_ids = set()
    windows = []       # harvested leaves: {startdt, enddt, total, relation, pages}
    overflow = []      # single-day leaves still at the 10k floor (≥10k, excluded from totals)
    stack = [(w_start, w_end)]
    first_meta = None
    while stack:
        ws, we = stack.pop(0)
        total, relation, page_hits, meta = _census_page(query, forms, ws, we, 0, cache=cache, no_cache=no_cache)
        requests += 1
        if first_meta is None:
            first_meta = meta
        if requests > max_requests:
            raise SdkError("usage_error", provider="edgar-fts",
                           detail=f"census budget exhausted at {requests} requests (windows done: {len(windows)}, "
                                  f"docs so far: {len(seen_ids)}) — raise --census-max-requests or narrow "
                                  f"--startdt/--enddt (the 5 rps politeness cap makes large budgets slow)")
        if total is None:  # silent over-window shape (no hits.total) — bisect, never score as zero
            left, right = _bisect(ws, we)
            if left is None:
                overflow.append({"startdt": ws, "enddt": we, "at_least": _PAGE})
                continue
            stack[0:0] = [left, right]
            continue
        if relation == "gte" or total > 10000:  # the 10k floor → split at the date midpoint
            left, right = _bisect(ws, we)
            if left is None:
                overflow.append({"startdt": ws, "enddt": we, "at_least": total})
                continue
            stack[0:0] = [left, right]
            continue
        # exact leaf: harvest every page (page 0 already in hand)
        n_pages = 1
        for h in page_hits:
            if h.get("_id") not in seen_ids:
                seen_ids.add(h.get("_id"))
                hits.append(h)
        for from_ in range(_PAGE, total, _PAGE):
            if from_ > _FROM_CEILING:  # cannot happen on an exact leaf (total<=10000); belt and suspenders
                break
            if requests >= max_requests:  # the harvest loop burns budget too (a 10k leaf = 100 pages)
                raise SdkError("usage_error", provider="edgar-fts",
                               detail=f"census budget exhausted at {requests} requests (windows done: {len(windows)}, "
                                      f"docs so far: {len(seen_ids)}) — raise --census-max-requests or narrow "
                                      f"--startdt/--enddt (the 5 rps politeness cap makes large budgets slow)")
            _, _, more, _ = _census_page(query, forms, ws, we, from_, cache=cache, no_cache=no_cache)
            requests += 1
            n_pages += 1
            pages += 1
            for h in more:
                if h.get("_id") not in seen_ids:
                    seen_ids.add(h.get("_id"))
                    hits.append(h)
        windows.append({"startdt": ws, "enddt": we, "total": total, "relation": relation, "pages": n_pages})

    rows = [_hit_row(h) for h in hits]
    if entity:
        # WORD-BOUNDARY LAW (anchor-calibrated 2026-11-17): a raw substring "IREN" also matches
        # "Siren ETF Trust" — 26 fund filings (NPORT-P/13F-HR/N-PX/N-CSR) whose holdings mention
        # Nvidia; \b-anchored matching drops exactly those and lands IREN×Nvidia on the workbuddy
        # reference 47 (73 − 26). The entity filter is word(s), never infix.
        needle = re.escape(str(entity).strip())
        rx = re.compile(rf"(?<![A-Za-z0-9]){needle}(?![A-Za-z0-9])", re.IGNORECASE)
        rows = [r for r, h in zip(rows, hits)
                if rx.search(str(r.get("company") or ""))
                or any(rx.search(str(d or "")) for d in _display_names(h))]
    docs_total = len(hits)
    filings = {r["adsh"] for r in rows if r.get("adsh")}
    cap = min(max(1, int(limit) or 10), 100)
    return {
        "mode": "census", "q": query, "forms": forms or None,
        "window": {"startdt": w_start, "enddt": w_end},
        "docs_total": docs_total,
        "filings_total": len(filings),
        "entity": str(entity).strip() if entity else None,
        "windows": windows, "overflow_windows": overflow,
        "requests": requests, "pages": pages + len(windows),
        "complete": not overflow,
        "rows": rows[:cap], "limit_applied": cap,
        "_meta": first_meta,
    }


def _display_names(hit):
    return (hit.get("_source") or {}).get("display_names") or []


def _hit_row(h):
    """Census row = the same shape the plain face returns (doc-level, verbatim keys)."""
    s = h.get("_source") or {}
    cik = (s.get("ciks") or [None])[0]
    _id = h.get("_id") or ""
    file = _id.split(":")[1] if ":" in _id else None
    adsh = s.get("adsh") or (_id.split(":")[0] if _id else None)
    return {
        "adsh": adsh, "cik": cik,
        "company": clean_display_name((s.get("display_names") or [None])[0]),
        "form_type": s.get("form") or (s.get("root_forms") or [None])[0],
        "file_date": s.get("file_date"),
        "period_ending": s.get("period_ending"),
        "doc_url": (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/{file}"
                    if cik and adsh and file else None),
    }
