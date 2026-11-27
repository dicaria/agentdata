"""legal faces — flat face-method mixin (split per domain in 0.2.6, moved in from client.py _Domain).

Mixed into the root _Domain (assembled via MRO, see client.py); discipline: no __init__, depends only on the
root internals (_flat_env/_c/_request…), method names globally unique across domains (a collision
would shadow another domain's face).
"""
from ..errors import SdkError
from ..transport import resolve_execution
from ..transport import enrich_source
import re
import urllib.parse


from .. import legal  # domain-module path call (historical shape, kept for minimal disturbance)


def _flag(value):
    """Coerce a CLI boolean-string ("true"/"false") into a real bool (None stays None).

    The argparse faces declare the flag choices as the strings "true"/"false" (so the
    surface stays textual and upstream-echoed), but the provider modules compare real
    booleans — a bare bool("false") would be True and silently invert the filter.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "y"):
        return True
    if text in ("false", "0", "no", "n"):
        return False
    return value


class LegalFaces:
    def _lg_only(self, tool: str):
        if self.name != "legal":
            raise SdkError("usage_error", detail=f"{tool} is a legal-domain capability (not available on the {self.name} domain)")

    def dgcomp_cases_search(self, query=None, *, name=None, instrument=None, text="",
                     limit=20, page=1, execution=None, no_cache=None):
        """legal dgcomp_cases_search: EU competition cases (DG COMP webgate ES; query = the bare DSL
        verbatim-name channel × name/instrument sugar assembling the DSL; pageSize wall 1-100 —
        verified 2026-10-26, 200 → silently 100)."""
        self._lg_only("dgcomp_cases_search")
        deps, assembled_from = [], None
        q = str(name or "").strip() or None
        if isinstance(query, str):  # the CLI face hands us JSON text — normalize to a bare DSL dict
            import json as _json
            try:
                query = _json.loads(query)
            except ValueError:
                raise SdkError("usage_error", provider="dgcomp",
                               detail="query must be a bare ES bool DSL dict in valid JSON (the CLI face passes JSON text)")
        if query is not None and not isinstance(query, dict):
            raise SdkError("usage_error", provider="dgcomp",
                           detail="query must be a dict-shaped bare ES bool DSL (e.g. {\"bool\": {\"must\": […]}})")
        if query is not None and (q or instrument):
            raise SdkError("usage_error", provider="dgcomp",
                           detail="query (verbatim-name channel: bare ES bool DSL) and name/instrument (sugar assembles the DSL) are mutually exclusive — give only one")
        if query is None and not q and not instrument:
            raise SdkError("usage_error", provider="dgcomp",
                           detail="dgcomp_cases_search requires query (bare ES DSL) or name/instrument — at least one of them")
        if query is None and (q or instrument):
            assembled_from = {k: v for k, v in (("name", q), ("instrument", instrument)) if v}
            deps.append("name/instrument sugar assembles the ES bool DSL (text three-field / term caseInstrument) — "
                        "the sugar stays (not deprecated); use query (bare DSL dict) for the verbatim-name channel")
        r = legal.dgcomp.search_raw(query, name=q, instrument=instrument, text=text,
                                        limit=limit, page=page, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        quartet = {"source": "assembled" if assembled_from else "raw",
                   "upstream": r["params"]}
        if assembled_from:
            quartet["assembled_from"] = assembled_from
        return self._flat_env(
            tool="dgcomp_cases_search",
            input={"query": query, "name": q, "instrument": instrument, "text": text,
                   "limit": result["limit_applied"], "page": page},
            reason=(f"DG COMP: {result['total'] or len(result['rows'])} cases hit"
                    + (f" (party/case name contains \"{q or instrument}\")" if q or instrument else " (bare DSL query)")
                    + f", returning {len(result['rows'])} rows — on SA cases title = the beneficiary company name (the subsidy event stream)"
                    if result["rows"] else f"DG COMP zero hits (an empty result is a legitimate answer — the query was too narrow or the party is not in the case register)"),
            result=result,
            evidence=[{"quote": f"{c['case_number'] or '—'} {c['title'] or '—'}"
                                f" ({c['instrument'] or '—'}, {'; '.join(c['companies']) if c['companies'] else '—'})",
                       "url": c["url"] or "https://competition-cases.ec.europa.eu/search"}
                      for c in result["rows"][:5]],
            provider_id="dgcomp", metas=[r["_meta"]],
            query=quartet, deprecations=deps or None,
        )

    def lda_filings(self, client_name=None, registrant_name=None, filing_year=None, *,
                    limit=20, page=None, ordering="-dt_posted", execution=None, no_cache=None):
        """legal lda_filings: US lobbying filings (LDA DRF; client_name/registrant_name/filing_year/
        page/ordering go through with verbatim names, limit→page_size with a 1-25 wall — verified
        2026-10-26, 26/50/100/500 silently return only 25)."""
        self._lg_only("lda_filings")
        cn = str(client_name or "").strip() or None
        rn = str(registrant_name or "").strip() or None
        if not cn and not rn and filing_year is None:
            raise SdkError("usage_error", provider="lda",
                           detail="lda_filings requires client_name / registrant_name / filing_year — at least one of the three"
                                  " (local safety wall: enumerating the full 70,545+ row corpus belongs to the batch line)")
        r = legal.lda.search_raw(client_name=cn, registrant_name=rn, filing_year=filing_year,
                                     limit=limit, page=page, ordering=ordering,
                                     cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="lda_filings",
            input={"client_name": cn, "registrant_name": rn, "filing_year": filing_year,
                   "limit": result["limit_applied"], "page": page, "ordering": ordering},
            reason=(f"LDA lobbying face: {result['total'] or len(result['rows'])} filings hit, returning {len(result['rows'])} rows"
                    + (f" (lobbied company \"{cn}\")" if cn else "")
                    + (f" (lobbying firm \"{rn}\")" if rn else "")
                    + " — income/expenses appear only on quarterly reports (always null on RR/RA registration filings); page through page (25-row per-page cap, upstream hard clamp)"
                    if result["rows"] else "LDA zero hits (an empty result is a legitimate answer; names match by contains — try swapping short/full name forms)"),
            result=result,
            evidence=[{"quote": f"{f['period'] or f['filing_type'] or '—'} {f['client']['name'] if f['client'] else '—'}"
                                f" ← {f['registrant']['name'] if f['registrant'] else '—'}"
                                + (f" income=${f['income']}" if f["income"] else ""),
                       "url": f["document_url"] or "https://lda.gov/api/v1/filings/"}
                      for f in result["rows"][:5]],
            provider_id="lda", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def gb_ec_donations(self, query, *, from_=None, to=None, limit=20, start=None,
                        execution=None, no_cache=None):
        """legal gb_ec_donations: UK political donations (the UK EC /donations single-endpoint face; query goes
        through verbatim, from_/to→from/to — we complete a missing window because a missing window → upstream
        Total=-1 fake success; rows wall 1-50, verified 2026-10-26)."""
        self._lg_only("gb_ec_donations")
        q = str(query or "").strip()
        if not q:
            raise SdkError("usage_error", provider="ukec",
                           detail="gb_ec_donations requires query (donor / regulated-entity name, upstream verbatim name)")
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        d = legal.ukec.donations_raw(q, _from=from_, to=to, limit=limit,
                                         start=start or 0, cache=cache, no_cache=nc)
        rows = d["rows"]
        dr = d.get("date_range") or {}
        return self._flat_env(
            tool="gb_ec_donations",
            input={"query": q, "from_": from_, "to": to,
                   "limit": d["limit_applied"], "start": start or 0},
            reason=(f"UK EC political donations: {d['total'] or len(rows)} records (\"{q}\", window {dr.get('from')}~{dr.get('to')}; "
                    f"50-row cap — upstream rows hard clamp, verified 2026-10-26)"
                    if rows else f"UK EC zero hits: no political donation records for \"{q}\" (an empty result is a legitimate answer)"),
            result={"total": d["total"], "rows": rows, "date_range": dr},
            evidence=[{"quote": f"donation {x['donor_or_lender'] or '—'} → {x['recipient'] or '—'} "
                                f"£{x['value_gbp'] or '—'} ({x['date'] or '—'})",
                       "url": "https://search.electoralcommission.org.uk/"}
                      for x in rows[:5]],
            provider_id="ukec", metas=[d["_meta"]],
            query={"source": "raw", "query": q, "upstream": d["params"]},
        )

    def gb_ec_loans(self, query, *, limit=20, start=None, execution=None, no_cache=None):
        """legal gb_ec_loans: UK political loans (the UK EC /loans single-endpoint face; the upstream loans
        endpoint takes no date-window params)."""
        self._lg_only("gb_ec_loans")
        q = str(query or "").strip()
        if not q:
            raise SdkError("usage_error", provider="ukec",
                           detail="gb_ec_loans requires query (lender / borrower name, upstream verbatim name)")
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        l = legal.ukec.loans_raw(q, limit=limit, start=start or 0, cache=cache, no_cache=nc)
        rows = l["rows"]
        return self._flat_env(
            tool="gb_ec_loans",
            input={"query": q, "limit": l["limit_applied"], "start": start or 0},
            reason=(f"UK EC political loans: {l['total'] or len(rows)} records (\"{q}\"; 50-row cap — upstream rows hard clamp, verified 2026-10-26)"
                    if rows else f"UK EC zero hits: no political loan records for \"{q}\" (an empty result is a legitimate answer)"),
            result={"total": l["total"], "rows": rows},
            evidence=[{"quote": f"loan {x['donor_or_lender'] or '—'} → {x['recipient'] or '—'} "
                                f"£{x['value_gbp'] or '—'} ({x['date'] or '—'})",
                       "url": "https://search.electoralcommission.org.uk/"}
                      for x in rows[:5]],
            provider_id="ukec", metas=[l["_meta"]],
            query={"source": "raw", "query": q, "upstream": l["params"]},
        )

    def sipri_trades_search(self, filters=None, *, supplier=None, recipient=None, type="delivered",
                         page=1, limit=20, execution=None, no_cache=None):
        """legal sipri_trades_search: country-level arms-transfer face (SIPRI atbackend; filters = the raw POST
        body verbatim-name channel (numeric EntityId in listData) × supplier/recipient country-name sugar
        (resolved against the 30-day cached EntityId table first); pageSize wall 1-100, upstream cap)."""
        self._lg_only("sipri_trades_search")
        deps, assembled_from = [], None
        sp = str(supplier or "").strip() or None
        rc = str(recipient or "").strip() or None
        if isinstance(filters, str):  # the CLI face hands us JSON text — normalize to a bare filter list
            import json as _json
            try:
                filters = _json.loads(filters)
            except ValueError:
                raise SdkError("usage_error", provider="sipri",
                               detail="filters must be a valid-JSON filter list (the CLI face passes JSON text)")
        if filters is not None and (sp or rc):
            raise SdkError("usage_error", provider="sipri",
                           detail="filters (verbatim-name channel: numeric EntityId in listData) and supplier/recipient (sugar: country names resolved first) are mutually exclusive — give only one")
        if filters is None and not sp and not rc:
            raise SdkError("usage_error", provider="sipri",
                           detail="sipri_trades_search requires supplier / recipient (country names) or filters (the raw EntityId table) — at least one of them")
        if filters is None:
            assembled_from = {k: v for k, v in (("supplier", sp), ("recipient", rc)) if v}
            deps.append("supplier/recipient country-name sugar resolves EntityIds first (30-day cached table; a country name in value1 causes a 500) — "
                        "the sugar stays (not deprecated); use filters (numeric EntityId in listData) for the verbatim-name channel")
        r = legal.sipri.search_raw(filters, supplier=sp, recipient=rc, type=type,
                                       page=page, limit=limit, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        resolved = result.get("resolved_countries") or {}
        quartet = {"source": "assembled" if assembled_from else "raw",
                   "upstream": r["params"]}
        if assembled_from:  # resolution results live in result.resolved_countries — assembled_from only records the sugar inputs verbatim
            quartet["assembled_from"] = assembled_from
        return self._flat_env(
            tool="sipri_trades_search",
            input={"filters": filters, "supplier": sp, "recipient": rc, "type": type,
                   "limit": result["limit_applied"], "page": page},
            reason=(f"SIPRI arms transfers ({type}): {f'supplier {sp}' if sp else ''}"
                    f"{' × ' if sp and rc else ''}{f'recipient {rc}' if rc else ''}"
                    + ("" if sp or rc else " (bare filters query)")
                    + f" returning {len(result['rows'])} rows (model-level, the Est flag = estimated value; trades is a country-level face, not company-level — "
                      f"the company-level universe lives in the Top-100 XLSX batch file)"
                    if result["rows"] else "SIPRI zero hits (an empty result is a legitimate answer; use full English country names, e.g. United States / Angola)"),
            result=result,
            evidence=[{"quote": f"{t['delivery_year'] or t['order_year'] or '—'} {t['supplier'] or '—'}"
                                f" → {t['recipient'] or '—'}: {t['designation'] or t['description'] or '—'}"
                                f" ×{t['units'] or '?'}{'(est)' if t['units_est'] else ''}",
                       "url": "https://www.sipri.org/databases/armstransfers"}
                      for t in result["rows"][:5]],
            provider_id="sipri", metas=metas,
            query=quartet, deprecations=deps or None,
        )

    def federalregister_documents(self, q, *, startdt=None, enddt=None, order="relevance",
                             page=1, limit=20, doc_type=None, agencies=None,
                             cfr_title=None, cfr_part=None, execution=None, no_cache=None):
        """legal federalregister_documents: search over the federal regulation/notice daily release stream
        (conditions[term]/[publication_date]/[type][]/[agencies][]/[cfr][title|part] go through with verbatim
        names; a missing end is auto-completed so both ends are always sent — a single end is silently ignored
        upstream, verified 2026-10-23; per_page politeness cap 50, upstream ceiling 1000.
        0.2.9 audit param additions (live-probed 2026-10-28): doc_type closed set of four values validated
        locally (an invalid value silently returns 0 rows upstream = a false negative), agencies agency slug,
        cfr code anchoring (part must accompany title); order gains the fourth official value executive_order_number."""
        self._lg_only("federalregister_documents")
        v = str(q or "").strip()
        if not v:
            raise SdkError("usage_error", provider="federalregister",
                           detail="federalregister_documents requires q (quote phrases for exact-phrase matching)")
        r = legal.federalregister.search_raw(v, startdt=startdt, enddt=enddt,
                                                 order=order, page=page, limit=limit,
                                                 doc_type=doc_type, agencies=agencies,
                                                 cfr_title=cfr_title, cfr_part=cfr_part,
                                                 cache=self._c._cache,
                                                 no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        dr = result.get("date_range")
        span = f", window {dr['startdt']}~{dr['enddt']}" if dr else ""
        return self._flat_env(
            tool="federalregister_documents",
            input={"q": v, "startdt": startdt, "enddt": enddt, "order": order,
                   "page": page, "limit": result["limit_applied"],
                   "doc_type": doc_type, "agencies": agencies,
                   "cfr_title": cfr_title, "cfr_part": cfr_part},
            reason=(f"Federal Register: {result.get('total', len(result['rows']))} hits"
                    f" (1994+ full-text level{span}), returning {len(result['rows'])} rows"
                    " — document_number is the stable key; a single record's raw_text_url feeds the corpus batch line for full text"),
            result=result,
            evidence=[{"quote": f"{d['type'] or '—'} {d['document_number'] or '—'} {d['title'] or '—'}"
                                f" ({d['publication_date'] or '—'}, {d['agencies'][0] if d['agencies'] else '—'})",
                       "url": d["url"] or "https://www.federalregister.gov/api/v1/documents.json"}
                      for d in result["rows"][:5]],
            provider_id="federalregister", metas=[r["_meta"]],
            query={"source": "raw", "search": v, "upstream": r["params"]},
        )

    def courtlistener_opinions_search(self, *, q=None, case_name=None, court=None,
                                      judge=None, docket_number=None, filed_after=None,
                                      filed_before=None, order_by=None, cursor=None,
                                      execution=None, no_cache=None):
        """legal courtlistener_opinions_search: US federal + state case-law search (Search API v4, anonymous and
        keyless; covers federal + state courts — the first probe hit California Court of Appeal; CAP
        (api.case.law) is retired and this source carries it; type is always "o"; at least one filter param
        (local safety wall); page_size is silently ignored upstream, always 20/page — page through cursor
        (next_cursor is recovered from the response).
        **0.2.9 audit snapshot (2026-10-28)**: the search endpoint returns 401 "Authentication credentials were
        not provided" for the anonymous tier — anonymous access still worked on 2026-10-26 (type=o count 8.3M);
        upstream added an auth gate within two days; the other v4 endpoints remain anonymously 200 (courts/
        verified as a control). Under the keyless-only ruling this face is on watch: restoring anonymous access
        or requiring a token is an upstream decision, not a param gap. The rate-limit wording was rewritten in
        step: upstream publishes only the authenticated tiers 5/min·50/hr·125/day; the anonymous numbers are not
        published upstream (api-usage page wording); 30/day was our own conservative tier; 429+Retry-After is the
        only signal verified live."""
        self._lg_only("courtlistener_opinions_search")
        r = legal.courtlistener.opinions_search_raw(
            q=q, case_name=case_name, court=court, judge=judge,
            docket_number=docket_number, filed_after=filed_after,
            filed_before=filed_before, order_by=order_by, cursor=cursor,
            cache=self._c._cache,
            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        filt = {k: v for k, v in r["params"].items() if k != "type"}
        who = ", ".join(f"{k}={v}" for k, v in filt.items()) or "whole corpus"
        reason = (f"CourtListener: {result['total']:,} opinions for {who}, {result['count']} on this page"
                  + (f", top hit {top['case_name'] or '—'}"
                     f" ({top['court'] or '—'}, {top['date_filed'] or '—'})" if top else "")
                  + (" — continue with next_cursor" if result.get("next_cursor") else ""))
        return self._flat_env(
            tool="courtlistener_opinions_search",
            input={**filt, "order_by": order_by, "cursor": cursor},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{o['case_name'] or '—'}"
                                f" ({o['court'] or '—'}, {o['date_filed'] or '—'}, "
                                f"{'/'.join(o['citations'][:1]) or 'no citation'})",
                       "url": ("https://www.courtlistener.com" + o["absolute_url"])
                              if o["absolute_url"] and o["absolute_url"].startswith("/")
                              else (o["absolute_url"] or "https://www.courtlistener.com/?q=o&type=o")}
                      for o in result["rows"][:5]],
            provider_id="courtlistener", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- enrichment (local) ----------
    def csl_screening_list(self, name=None, *, value=None, source=None, type=None, limit=20,
                      execution=None, no_cache=None):
        """US Consolidated Screening List name screening (realtime, local execution): 12 list families
        (SDN / Entity List / DPL / ITAR / SSI …) 26k rows in one CSV, local full-register scan —
        empty result = clean screening (a legitimate answer). source = list-family substring
        (e.g. "Entity List"), type = Entity|Individual|Vessel|Aircraft."""
        if self.name != "legal":
            raise SdkError("usage_error", detail=f"csl_screening_list is a legal-domain command (got \"{self.name}\")")
        ex = resolve_execution(execution or self._c.default_execution)
        nc = self._c.no_cache if no_cache is None else bool(no_cache)
        q = name if name is not None else value
        if not q:
            raise SdkError("usage_error", detail="csl_screening_list requires name (screening subject, contains-matches name+alt_names)")
        r = legal.csl.screen_list(q, source=source, type=type, limit=limit or 20,
                                      cache=self._c._cache, no_cache=nc)
        result = {k: v for k, v in r.items() if k != "_meta"}
        return {
            "ok": True, "domain": "legal", "tool": "csl_screening_list",
            "input": {"name": q, "source": source, "type": type, "limit": int(limit or 20)},
            "from_cache": bool(r["_meta"].get("from_cache")),
            "reason": (f"CSL consolidated screening positive: {result['total_matched']} of {result['scanned_rows']} full-register rows "
                       f"(12 list families) matched \"{q}\", returning {len(result['rows'])} rows — matched_on=name|alt_names is the hit face; zero hits = clean screening"
                       if result["rows"] else
                       f"CSL screening negative: \"{q}\" is not in the {result['scanned_rows']} consolidated-screening rows (SDN/EL/DPL/ITAR/SSI etc., 12 families)"
                       " — an empty result is a legitimate answer = clean screening"),
            "result": result,
            "evidence": [{"quote": f"{row['source_list'] or '—'} | {row['type'] or '—'} | {row['name'] or '—'}"
                                   + (f" (alt: {'; '.join(row['alt_names'][:3])}…)" if row["alt_names"] else "")
                                   + (f" | {';'.join(row['programs'][:3])}" if row["programs"] else ""),
                          "url": row["source_information_url"] or "https://www.trade.gov/consolidated-screening-list"}
                         for row in result["rows"][:5]],
            "source": enrich_source("csl", ex, r["_meta"]),
            "request_id": self._c._request_id(),
        }
    def ecfr_search(self, q=None, *, query=None, value=None, page=1, limit=20,
                    date=None, execution=None, no_cache=None):
        """eCFR current-code section search (keyless): where a topic lives in the codified
        US Code of Federal Regulations today — counterpart of legal fulltext (FR daily flow).
        coords = seven-level citation; starts_on~ends_on = that version's effective window
        (section-level change semantics, not plain full-text)."""
        if self.name != "legal":
            raise SdkError("usage_error", detail=f"ecfr_search is a legal-domain command (got \"{self.name}\")")
        ex = resolve_execution(execution or self._c.default_execution)
        nc = self._c.no_cache if no_cache is None else bool(no_cache)
        term = q if q is not None else (query if query is not None else value)
        if not term:
            raise SdkError("usage_error", detail="ecfr_search requires q (topic term; returns section-level current-state hits, not the FR daily feed)")
        r = legal.ecfr.search_results(term, page=page, limit=limit or 20, date=date,
                                          cache=self._c._cache, no_cache=nc)
        result = {k: v for k, v in r.items() if k != "_meta"}
        return {
            "ok": True, "domain": "legal", "tool": "ecfr_search",
            "input": {"q": str(term), "page": int(page or 1), "limit": int(limit or 20), "date": date or None},
            "from_cache": bool(r["_meta"].get("from_cache")),
            "reason": (f"eCFR {'point-in-time ' + str(date) + ' ' if date else 'current state'}: {result['total']} sections hit library-wide (page {result['current_page']}/{result['total_pages']}), "
                       f"returning {len(result['rows'])} rows — coords = the seven-level code citation; starts_on~ends_on = that version's effective window"
                       " (section-level change semantics, not full-text search); for the current full-text stream use legal fulltext (FR daily)"
                       if result["rows"] else
                       f"eCFR zero hits: \"{term}\" is not in the current code's section-level index (an empty result is a legitimate answer; try a synonym or check the spelling)"),
            "result": result,
            "evidence": [{"quote": f"{row['coords'] or '—'} | {row['type'] or '—'} | "
                                   + (re.sub(r"<[^>]+>", "", (row['headings'] or {}).get('part')
                                             or (row['headings'] or {}).get('chapter') or "") or '—')
                                   + (f" | effective {row['starts_on']}" + (f"~{row['ends_on']}" if row['ends_on'] else "→")
                                      if row["starts_on"] else ""),
                          "url": (f"https://www.ecfr.gov/current/title-{(row['hierarchy'] or {}).get('title')}"
                                  if (row["hierarchy"] or {}).get("title") else "https://www.ecfr.gov/")}
                         for row in result["rows"][:5]],
            "source": enrich_source("ecfr", ex, r["_meta"]),
            "request_id": self._c._request_id(),
        }

    def ecfr_titles(self, *, execution=None, no_cache=None):
        """eCFR title catalog (keyless): the 50 CFR titles with latest_amended_on /
        latest_issue_date and the library-wide currency watermark (as_of — eCFR integrates
        daily; observed T-2)."""
        if self.name != "legal":
            raise SdkError("usage_error", detail=f"ecfr_titles is a legal-domain command (got \"{self.name}\")")
        ex = resolve_execution(execution or self._c.default_execution)
        nc = self._c.no_cache if no_cache is None else bool(no_cache)
        r = legal.ecfr.titles_catalog(cache=self._c._cache, no_cache=nc)
        result = {k: v for k, v in r.items() if k != "_meta"}
        return {
            "ok": True, "domain": "legal", "tool": "ecfr_titles",
            "input": {},
            "from_cache": bool(r["_meta"].get("from_cache")),
            "reason": f"eCFR catalog: {result['count']} titles ({result['active']} active), daily-update watermark as_of={result['as_of']}"
                      " — title number + name + latest amendment/issue dates; for section-level current-state search use ecfr_search",
            "result": result,
            "evidence": [{"quote": f"Title {t['number']} {t['name']} (amended {t['latest_amended_on'] or '—'}, "
                                   f"integrated through {t['up_to_date_as_of'] or '—'}" + (", reserved" if t["reserved"] else "") + ")",
                          "url": f"https://www.ecfr.gov/current/title-{t['number']}"}
                         for t in result["titles"][:5]],
            "source": enrich_source("ecfr", ex, r["_meta"]),
            "request_id": self._c._request_id(),
        }

    def gb_cma_cases(self, q=None, *, count=20, start=0, execution=None, no_cache=None):
        """legal gb_cma_cases: UK CMA case search (gov.uk search API, filter_format=cma_case fixed;
        q/count/start go through with verbatim names — count politeness wall 1-100 (upstream has no wall,
        count=1000 delivers in full, verified 2026-10-29), start = offset paging; case name = the party-pair
        "A / B" form, title is the party search face)."""
        self._lg_only("gb_cma_cases")
        term = str(q or "").strip() or None
        r = legal.gb_cma.search_raw(q=term, count=count, start=start,
                                    cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        return self._flat_env(
            tool="gb_cma_cases",
            input={"q": term, "count": result["limit_applied"], "start": start},
            reason=(f"UK CMA case register: {result['total']} cases hit, returning {len(result['rows'])} rows"
                    + (f" (query \"{term}\")" if term else " (full-register enumeration)")
                    + " — case name = the party pair (merger/inquiry cases); for single-case detail use gb_cma_case (slug from the row)"
                    if result["rows"] else
                    f"UK CMA zero hits (an empty result is a legitimate answer — query too narrow or no registered cases; enumerate the full register of {result['total']} cases by omitting q)"),
            result=result,
            evidence=[{"quote": f"{c['title'] or '—'} (updated {c['public_timestamp'] or '—'}, "
                               f"{'; '.join(c['organisations']) if c['organisations'] else '—'})",
                       "url": c["url"] or "https://www.gov.uk/search/all?keywords=&level_one_taxon=&"
                                          "manual_close_coronavirus=none&order=updated-newest"}
                      for c in result["rows"][:5]],
            provider_id="gb_cma", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def gb_cma_case(self, slug, *, execution=None, no_cache=None):
        """legal gb_cma_case: the full UK CMA single-case dossier (gov.uk content API; content_id = the UUID
        stable key; change_history = the evolution stream newest→oldest (last = First published),
        attachments = the decision/notice PDF family — the company × case negative-signal detail face)."""
        self._lg_only("gb_cma_case")
        if not str(slug or "").strip():
            raise SdkError("usage_error", provider="gb_cma",
                           detail="gb_cma_case requires slug (the case-page tail segment, echoed verbatim from "
                                  "gb_cma_cases rows; a pasted full base_path also gets its prefix stripped)")
        r = legal.gb_cma.case_raw(slug, cache=self._c._cache,
                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        latest = (result["change_history"] or [{}])[0]  # upstream order = newest→oldest ([0] = latest, last = First published)
        return self._flat_env(
            tool="gb_cma_case",
            input={"slug": result["slug"]},
            reason=(f"UK CMA single case: {result['title'] or result['slug']}"
                    + (" (withdrawn)" if result["withdrawn"] else "")
                    + f" — {len(result['change_history'])} change-history entries (latest: {latest.get('note') or '—'})"
                    + f", {len(result['attachments'])} decision/notice PDFs; first published {result['first_published_at'] or '—'}")
                    if result["content_id"] else "gov.uk content API returned empty (slug not in the register — go back to the search face and check the spelling)",
            result=result,
            evidence=[{"quote": f"{a['title'] or '—'} ({a['content_type'] or '—'})",
                       "url": a["url"] or result["url"]}
                      for a in result["attachments"][:5]]
                    or [{"quote": latest.get("note") or result["title"] or result["slug"], "url": result["url"]}],
            provider_id="gb_cma", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"path": f"/api/content/cma-cases/{result['slug']}"}},
        )

    # ---------- 0.3.16 legal CO SIC sanctions face (datos.gov.co Socrata 73dx-n59j; same $-param contract as co_secop_contracts) ----------

    def co_sic_sanctions(self, where=None, *, limit=20, offset=0, order=None, execution=None, no_cache=None):
        """legal co_sic_sanctions: Colombia SIC firm-sanctions register (datos.gov.co Socrata 73dx-n59j, keyless):
        multado (the sanctioned party) × valor (fine, COP) × conducta (the violation) × sector — 3,938 firm
        sanctions 2013→. $where raw SoQL / $limit 1-500 / $offset / $order column[ ASC|DESC] verbatim (same
        contract as co_secop_contracts); Socrata sends no total echo — paging goes through offset. Name-only
        key (no NIT column): a name join onto co_rues_companies is the corpus line's job."""
        self._lg_only("co_sic_sanctions")
        w = str(where or "").strip() or None
        r = legal.co_sic.sanctions_raw(w, limit=limit, offset=offset, order=order,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        return self._flat_env(
            tool="co_sic_sanctions",
            input={"where": w, "limit": result["limit_applied"], "offset": offset, "order": order},
            reason=(f"Colombia SIC sanctions register: {len(result['rows'])} rows returned"
                    + (f" (SoQL filter \"{w}\")" if w else " (enumerate from the head of the register; the corpus holds 3,938 firm sanctions 2013→, counted at admission)")
                    + " — row = multado (sanctioned party) × valor (COP) × conducta × sector; name-only key, join onto NIT via co_rues_companies on the corpus line"
                    if result["rows"] else
                    "Colombia SIC zero hits (an empty result is a legitimate answer — SoQL too narrow or no firm sanction on record; drop --where to enumerate from the register head)"),
            result=result,
            evidence=[{"quote": f"{c['multado'] or '—'} — {c['conducta'] or '—'} ({c['sector'] or '—'}), "
                               f"COP {c['valor'] or '—'}, res. {c['res_sancion'] or '—'} of {(c['fecha_emitida'] or '')[:10]}",
                       "url": "https://www.datos.gov.co/Comercio-Industria-y-Turismo/Sanciones-impuestas-en-firme-por-la-SIC/73dx-n59j"}
                      for c in result["rows"][:5]],
            provider_id="co_sic", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- legal caselaw line (TNA Find Case Law: search + Akoma Ntoso single record; born 0.3.8, ISO-prefixed 0.3.13, Englished in the 0.3.14 collection round) ----------

    def gb_tna_caselaw_search(self, query=None, *, court=None, tribunal=None, party=None, judge=None,
                           order=None, page=1, per_page=50, minimum_availability=None,
                           execution=None, no_cache=None):
        """legal gb_tna_caselaw_search: UK judgment search (TNA Find Case Law /atom.xml; party/judge = whole-word
        party/judge-name matching, query = full text, court/tribunal = court codes, repeatable (explode),
        order = ±date/±updated/±transformation — eight upstream-named params passed straight through;
        per_page polite tier 1-50 (the upstream default is 50). Rows carry the neutral_citation (the
        human-readable official key, [2026] EWHC 2298 (Admin)) + uri (the machine-stable key, fed straight
        into the judgment face) + contenthash.
        **The Open Justice Licence forbids bulk computational analysis (free-application regime) — this
        face is directed search / rolling monitoring; do not enumerate the corpus**."""
        self._lg_only("gb_tna_caselaw_search")
        r = legal.gb_tna_caselaw.search_raw(query=query, court=court, tribunal=tribunal,
                                         party=party, judge=judge, order=order, page=page,
                                         per_page=per_page, minimum_availability=minimum_availability,
                                         cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        return self._flat_env(
            tool="gb_tna_caselaw_search",
            input={"query": query, "court": court, "tribunal": tribunal, "party": party,
                   "judge": judge, "order": order, "page": result["page"],
                   "per_page": result["per_page"], "minimum_availability": minimum_availability},
            reason=(f"UK caselaw library (TNA Find Case Law): page {result['page']}/{result['total_pages'] or '?'}, "
                    f"{result['count']} rows — row = case name (party string)/court/judgment date/neutral citation; "
                    "the full judgment text goes through gb_tna_caselaw_judgment (uri = the row's uri)"
                    if result["rows"] else
                    "TNA zero hits (an empty result is a valid answer — party/judge are whole-word matches; "
                    "try a single word of the name or switch to a full-text query)"),
            result=result,
            evidence=[{"quote": f"{c['neutral_citation'] or c['uri'] or '—'} {c['title'] or ''}"
                               f" ({c['court'] or '—'}, {(c['published'] or '')[:10]})",
                       "url": c["html_url"] or c["data_url"] or "https://caselaw.nationalarchives.gov.uk/atom.xml"}
                      for c in result["rows"][:5]],
            provider_id="gb_tna_caselaw", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def gb_tna_caselaw_judgment(self, document_uri, *, execution=None, no_cache=None):
        """legal gb_tna_caselaw_judgment: the full UK single-judgment dossier (Akoma Ntoso data.xml;
        neutral_citation = the neutral-citation official key, parties=[{name, role}] the party→role official
        edge (claimant/defendant, company and personal names), judges, text = the plain-text extraction of
        the judgment body). document_uri takes all three forms: legacy ewhc/admin/2026/2298, new-style
        d-<uuid>, tna.<fclid> — fed straight from the search row's uri; a pasted full URL is unwrapped
        automatically."""
        self._lg_only("gb_tna_caselaw_judgment")
        if not str(document_uri or "").strip():
            raise SdkError("usage_error", provider="gb_tna_caselaw",
                           detail="gb_tna_caselaw_judgment requires document_uri (fed straight from the "
                                  "gb_tna_caselaw_search row's uri; three forms accepted: legacy "
                                  "ewhc/admin/2026/2298, new-style d-<uuid>, tna.<fclid>)")
        r = legal.gb_tna_caselaw.judgment_raw(document_uri, cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        n_cl = sum(1 for p in result["parties"] or [] if p.get("role") == "claimant")
        n_df = sum(1 for p in result["parties"] or [] if p.get("role") == "defendant")
        return self._flat_env(
            tool="gb_tna_caselaw_judgment",
            input={"document_uri": result["uri"]},
            reason=(f"UK judgment dossier: {result['neutral_citation'] or result['uri']} ({result['court_code'] or '—'}, "
                    f"judged {result['date'] or '—'}) — {len(result['parties'] or [])} parties"
                    f" (claimant {n_cl}/defendant {n_df}) · {len(result['judges'] or [])} judges · "
                    f"body {result['text_length']} chars; licence = Open Justice (reuse compliant, bulk analysis requires an application)"
                    if result["neutral_citation"] else
                    "data.xml came back empty or is not a judgment structure (the uri is not in the register — "
                    "go back to gb_tna_caselaw_search and check)"),
            result=result,
            evidence=[{"quote": f"{p['role'] or 'party'}: {p['name'] or '—'}", "url": result["url"]}
                      for p in (result["parties"] or [])[:5]]
                      or [{"quote": result["title"] or result["uri"], "url": result["url"]}],
            provider_id="gb_tna_caselaw", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"path": f"/{result['uri']}/data.xml"}},
        )

    # ---------- 0.3.21 legal debarment-roster line (WB + AfDB + IDB MDB debarment + CA SEMA sanctions; born flat; local-scan trio carries no quartet — there are no upstream params to replay, the csl_screening_list precedent) ----------

    def afdb_debarred_entities(self, name=None, *, type=None, basis=None, limit=20,
                               execution=None, no_cache=None):
        """legal afdb_debarred_entities: African Development Bank debarment register (afdb.org json-feed,
        keyless; full 1,440-row dump cached 24h and scanned locally). Basis = the cross-debarment edge
        self-evidenced (CROSS DEBARMENT : WBG/ADB/IDB/EBRD vs DEBARMENT:AFDB) — contains-match because
        upstream punctuation is inconsistent; To empty = ongoing."""
        self._lg_only("afdb_debarred_entities")
        nm = str(name or "").strip() or None
        r = legal.afdb.debarred_entities_raw(nm, type=type, basis=basis, limit=limit,
                                             cache=self._c._cache,
                                             no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        return self._flat_env(
            tool="afdb_debarred_entities",
            input={"name": nm, "type": type, "basis": basis, "limit": result["limit_applied"]},
            reason=(f"AfDB debarment register: {result['total_matched']} of {result['scanned_rows']} rows matched"
                    + (f" (name contains \"{nm}\")" if nm else "")
                    + (f", type {type}" if type else "") + (f", basis contains \"{basis}\"" if basis else "")
                    + ", returning top rows — Basis carries the cross-debarment edge (WBG/ADB/IDB/EBRD tokens; To empty = ongoing); zero hits = not on the AfDB register"
                    if result["rows"] else
                    f"AfDB zero hits (an empty result is a legitimate answer = clean screening on the {result['scanned_rows']}-row register; drop filters to enumerate from the head)"),
            result=result,
            evidence=[{"quote": f"{x['Name'] or '—'} ({x['Type'] or '—'}, {x['Nationality'] or '—'}) "
                               f"{x['From'] or '?'}→{x['To'] or 'ongoing'} · {x['Basis'] or '—'}",
                       "url": "https://www.afdb.org/en/projects-operations/debarment-and-sanctions-procedures"}
                      for x in result["rows"][:5]],
            provider_id="afdb", metas=[r["_meta"]],
        )

    # —— 0.3.58 CA provincial securities commission pair (dictionary slot: ca_asc_enforcement <
    # ca_bcsc_disciplined < ca_sema_sanctions; the AMF (Québec) sibling is DEFERRED — lautorite.qc.ca
    # answers CF 403 to non-browser clients from this egress, the tr_ekap precedent) ——

    def ca_asc_enforcement(self, q=None, *, limit=20, execution=None, no_cache=None):
        """legal ca_asc_enforcement: Alberta Securities Commission notices/decisions/orders
        (www.asc.ca Coveo headless chain — token → cloud query; 7,304 documents 2001→today
        answered 3× per document, DEDUPED by clickUri; cm.asc.ca PDFs are 403 to non-browser
        clients — a metadata-only face)."""
        self._lg_only("ca_asc_enforcement")
        qq = str(q or "").strip() or None
        r = legal.ca_asc.search_raw(qq, limit=limit, cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="ca_asc_enforcement",
            input={"q": qq, "limit": result["params"]["limit"]},
            reason=(f"ASC enforcement library: {result['total']} documents upstream"
                    + f", {result['count']} returned after dedup ({result['duplicates_dropped']} duplicated copies dropped — the index answers every document 3×)"
                    + (f", top {top['issuer'] or top['title'] or '—'} ({top['date'] or '—'}, {top['category'] or '—'})" if top
                       else " — zero hits (an empty result is a legal answer)")),
            result=result,
            evidence=[{"quote": f"{x['issuer'] or '—'} · {x['category'] or '—'} · {x['date'] or '—'}"
                                + (" · [legacy path title]" if x["is_legacy_path_title"] else ""),
                       "url": x["url"]} for x in rows[:5]],
            provider_id="ca_asc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def ca_bcsc_disciplined(self, q=None, *, party_type=None, limit=20, offset=0,
                            execution=None, no_cache=None):
        """legal ca_bcsc_disciplined: BC Securities Commission Disciplined Parties
        (gateway.bcsc.bc.ca Sitecore SearchTable form-POST; 1,834 rows live; party-name search
        over title/item-name/other-names with a party-type facet 'Company'→532)."""
        self._lg_only("ca_bcsc_disciplined")
        qq = str(q or "").strip() or None
        r = legal.ca_bcsc.search_raw(qq, party_type=party_type, limit=limit, offset=offset,
                                     cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="ca_bcsc_disciplined",
            input={"q": qq, "party_type": party_type, "limit": result["params"]["limit"],
                   "offset": result["params"]["offset"]},
            reason=(f"BCSC Disciplined List: {result['total_matched']} of {result['total']} rows matched"
                    + (f" (party \"{qq}\")" if qq else "")
                    + (f" ({party_type})" if party_type else "")
                    + (f", top {top['title'] or '—'} ordered {top['date'] or '—'}" if top
                       else " — zero hits (an empty result is a legal answer = clean screening on the BC register)")),
            result=result,
            evidence=[{"quote": f"{x['title'] or '—'} · {x['item_type'] or '—'} · ordered {x['date'] or '—'}"
                                + (f" · RI default: {x['reporting_issuer_default_flag']}" if x.get("reporting_issuer_default_flag") else ""),
                       "url": x["url"]} for x in rows[:5]],
            provider_id="ca_bcsc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def ca_sema_sanctions(self, name=None, *, country=None, limit=20,
                          execution=None, no_cache=None):
        """legal ca_sema_sanctions: Canada SEMA sanctions listings (Global Affairs Canada sema-lmes.xml,
        keyless; the Consolidated Canadian Autonomous Sanctions List — 5,708 live records: persons, entities
        and ships; bilingual cells verbatim; 731 ships carry an IMO number = the join key onto shipping
        rosters). Name screening contains-matches name + aliases (matched_on echoes the hit face)."""
        self._lg_only("ca_sema_sanctions")
        nm = str(name or "").strip() or None
        r = legal.ca_sema.sanctions_raw(nm, country=country, limit=limit,
                                        cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        return self._flat_env(
            tool="ca_sema_sanctions",
            input={"name": nm, "country": country, "limit": result["limit_applied"]},
            reason=(f"Canada SEMA sanctions list: {result['total_matched']} of {result['scanned_rows']} listings matched"
                    + (f" (name/alias contains \"{nm}\")" if nm else "")
                    + (f", country contains \"{country}\"" if country else "")
                    + " — bilingual cells verbatim (Syria / Syrie), schedule = the SEMA schedule reference; zero hits = not designated under SEMA"
                    if result["rows"] else
                    f"Canada SEMA zero hits (an empty result is a legitimate answer = clean screening on the {result['scanned_rows']}-listing register; the bilingual country cell matches either language)"),
            result=result,
            evidence=[{"quote": f"{x['name'] or '—'} ({x['kind'] or '—'}, {x['country'] or '—'})"
                               + (f" IMO {x['ship_imo']}" if x["ship_imo"] else "")
                               + f" · listed {x['date_of_listing'] or '—'}",
                       "url": "https://www.international.gc.ca/world-monde/international_relations-relations_internationales/sanctions/consolidated-consolide.aspx?lang=eng"}
                      for x in result["rows"][:5]],
            provider_id="ca_sema", metas=[r["_meta"]],
        )

    # —— 0.3.59 enforcement/party-finance cluster first slice: ch_finma_enforcement_news (dictionary slot:
    # ca_sema < ch_finma < idb — FINMA's whole news surface: press releases + enforcement
    # news; the query term is mandatory live law, the page window is upstream-fixed at 20) ——
    def ch_finma_enforcement_news(self, q, *, lang="en", limit=20, offset=0,
                                  execution=None, no_cache=None):
        """legal ch_finma_enforcement_news: FINMA news & enforcement search (www.finma.ch Sitecore
        CMS form-POST; 'enforcement' → 125 hits live; spans press releases, enforcement news,
        publications — count is the term's total, MaxResultCount 1000 upstream)."""
        self._lg_only("ch_finma_enforcement_news")
        r = legal.ch_finma.search_raw(q, lang=lang, limit=limit, offset=offset,
                                      cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="ch_finma_enforcement_news",
            input={"q": result["params"]["q"], "lang": result["params"]["lang"],
                   "limit": result["params"]["limit"], "offset": result["params"]["offset"]},
            reason=(f"FINMA news search: {result['count']} hits for \"{result['params']['q']}\""
                    + f" ({lang}, page window at offset {offset} — 20 rows upstream-fixed)"
                    + (f", top {top['title'] or '—'} ({top['date'] or '—'})" if top
                       else " — zero hits (an empty result is a legal answer; also check the German tree, lang='de')")
                    + " — rows are the published news cards; enforcement proceedings surface as press releases"),
            result=result,
            evidence=[{"quote": f"{x['date'] or '—'} · {x['title'] or '—'}"
                                + (f" · {x['category']}" if x.get("category") else ""),
                       "url": x["url"] or f"https://www.finma.ch/{lang}/news/"}
                      for x in rows[:5]],
            provider_id="ch_finma", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def idb_debarred_entities(self, q=None, *, filters=None, limit=20, offset=0, sort=None,
                              execution=None, no_cache=None):
        """legal idb_debarred_entities: Inter-American Development Bank sanctioned-firms register
        (data.iadb.org CKAN DataStore, keyless, server-side search: q full-text verbatim, filters =
        JSON field→value exact matches verbatim, offset paging, include_total always; live register
        1,343 rows; Source carries the cross-debarment markers ADB/WBG cross debarment)."""
        self._lg_only("idb_debarred_entities")
        qq = str(q or "").strip() or None
        r = legal.idb.debarred_entities_raw(qq, filters=filters, limit=limit, offset=offset, sort=sort,
                                            cache=self._c._cache,
                                            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        return self._flat_env(
            tool="idb_debarred_entities",
            input={"q": qq, "filters": filters, "limit": result["limit_applied"], "offset": offset, "sort": sort},
            reason=(f"IDB sanctioned-firms register: {result['total']} rows total, {len(result['rows'])} returned"
                    + (f" (q \"{qq}\")" if qq else "")
                    + (f" (filters {filters})" if filters else "")
                    + " — Entity=Firm rows are the company roster; Source carries cross-debarment markers (ADB/WBG cross debarment); page through offset"
                    if result["rows"] else
                    "IDB zero hits (an empty result is a legitimate answer; q is a full-text match and filters are exact-match — drop them to enumerate from the register head)"),
            result=result,
            evidence=[{"quote": f"{x.get('Title') or '—'} ({x.get('Entity') or '—'}, {x.get('Nationality') or '—'}) "
                               f"{(x.get('From') or '?')[:10]}→{x.get('To') or '?'} · {(x.get('Prohibited Practice') or '—').strip()}"
                               + (f" · {x.get('Source')}" if x.get("Source") and str(x.get("Source")) != "IDB" else ""),
                       "url": "https://www.iadb.org/en/transparency/sanctioned-firms-and-individuals"}
                      for x in result["rows"][:5]],
            provider_id="idb", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def wb_debarred_firms(self, name=None, *, country=None, type=None, limit=20,
                          execution=None, no_cache=None):
        """legal wb_debarred_firms: World Bank debarred-firms register (apigwext SAP gateway via the
        page-embedded public apikey; full 1,546-row dump cached 24h and scanned locally). SUPP_ID = the WB
        supplier key; DEBAR_TO_DATE 2999-12-31 = indefinite; eligibility DEBARRED/X-DEBARRED; China leads
        the roster (392 firms); the DNB/REGISTER identifier fields ship empty — name × country is the
        join channel."""
        self._lg_only("wb_debarred_firms")
        nm = str(name or "").strip() or None
        r = legal.wb.debarred_firms_raw(nm, country=country, type=type, limit=limit,
                                        cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        return self._flat_env(
            tool="wb_debarred_firms",
            input={"name": nm, "country": country, "type": type, "limit": result["limit_applied"]},
            reason=(f"World Bank debarred-firms register: {result['total_matched']} of {result['scanned_rows']} rows matched"
                    + (f" (name contains \"{nm}\")" if nm else "")
                    + (f", country contains \"{country}\"" if country else "")
                    + (f", type {type}" if type else "")
                    + " — DEBAR_REASON cites the procurement-guidelines clause; DEBAR_TO_DATE 2999-12-31 = indefinite; zero hits = not on the WB register"
                    if result["rows"] else
                    f"World Bank zero hits (an empty result is a legitimate answer = clean screening on the {result['scanned_rows']}-row register; country matches the name or the LAND1 code, e.g. China/CN)"),
            result=result,
            evidence=[{"quote": f"{x['SUPP_NAME'] or '—'} ({x['COUNTRY_NAME'] or '—'}) "
                               f"{x['DEBAR_FROM_DATE'] or '?'}→{x['DEBAR_TO_DATE'] or '?'} · {x['DEBAR_REASON'] or '—'}",
                       "url": "https://www.worldbank.org/en/projects-operations/procurement/debarred-firms"}
                      for x in result["rows"][:5]],
            provider_id="wb", metas=[r["_meta"]],
        )

    # ---------- 0.3.27 gazette + IE defaulters line (UK official-record search + IE statutory tax-defaulters register; born flat) ----------

    def gb_gazette_notices(self, text=None, *, noticetypes=None, insolvency=None,
                           start_date=None, end_date=None, page=1, page_size=20, sort=None,
                           execution=None, no_cache=None):
        """legal gb_gazette_notices: The Gazette notice search (thegazette.co.uk data.json, keyless,
        OGL; 3.58M notices digitised from 1992, three editions). Event filtering is by notice code —
        noticetypes +-joined (the noticecode= param is silently ignored) or the insolvency chapter
        preset; title = the company name on corporate insolvency codes; geo:Point = the registered
        office; at least one filter is required (the 4.89M-notice bulk wall)."""
        self._lg_only("gb_gazette_notices")
        txt = str(text or "").strip() or None
        r = legal.gazette.notices_raw(txt, noticetypes=noticetypes, insolvency=insolvency,
                                      start_date=start_date, end_date=end_date,
                                      page=page, page_size=page_size, sort=sort,
                                      cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        codes = r["params"].get("noticetypes")
        return self._flat_env(
            tool="gb_gazette_notices",
            input={"text": txt, "noticetypes": noticetypes, "insolvency": bool(insolvency),
                   "start_date": start_date, "end_date": end_date,
                   "page": result["page"], "page_size": result["page_size"], "sort": sort},
            reason=(f"The Gazette: {result['total']:,} notices match, {result['count']} rows on page {result['page']}"
                    + (f", text \"{txt}\"" if txt else "")
                    + (f", codes {codes}" if codes else "")
                    + (f", published {start_date or '…'}→{end_date or '…'}" if start_date or end_date else "")
                    + " — title = the company name on corporate insolvency codes (2432 liquidator, 2410 administrator, 2431 cessation); placed_by = liquidator/administrator or the edition; geo = the registered office"
                    if result["rows"] else
                    f"The Gazette zero rows on page {result['page']} of {result['total']:,} matches (past the last page?) "
                    "or nothing matches the filters — an empty result is a legitimate answer; drop filters or go back to page 1"),
            result=result,
            evidence=[{"quote": f"{x['title'] or '—'} ({x['category'] or x['notice_code'] or '—'}) "
                               f"· {x['published'] or '—'} · placed by {x['placed_by'] or '—'}",
                       "url": x["url"] or "https://www.thegazette.co.uk/notice/" + str(x["notice_id"] or "")}
                      for x in result["rows"][:5]],
            provider_id="gazette", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- 0.3.64 batch E6 — UK NMW naming-scheme pair (dictionary slot: gb_gazette_notices < gb_nmw_round < gb_nmw_rounds < gb_tna_caselaw_judgment) ----------

    def gb_nmw_rounds(self, *, count=20, start=0, execution=None, no_cache=None):
        """legal gb_nmw_rounds: the UK National Minimum Wage naming-scheme rounds index
        (gov.uk search API, keyless, OGL; the register's own discovery query pinned:
        "named and shamed" "minimum wage" + press_release, newest first). 41 results live
        (Round 22 2026-01-19 at top — 492 employers, £6M repaid); the full history walks
        back through start= offsets. Not every hit is a numbered round (rate-reminder and
        statistics releases ride the same query — titles tell them apart, kept verbatim).
        The named-employers xlsx rides each round's detail face as a coordinate, never
        bytes (the EUASL precedent)."""
        self._lg_only("gb_nmw_rounds")
        r = legal.gb_nmw.rounds_raw(count=count, start=start,
                                    cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["rows"]:
            reason = (f"NMW naming-scheme rounds ({result['limit_applied']}/page, offset {start}): "
                      f"{result['count']} rows of {result['total']} — newest first; the numbered "
                      f"rounds carry the named-employers list as an xlsx attachment (Round 22 = "
                      f"492 employers × 15 columns with three-tier ONS SIC codes)")
        else:
            reason = (f"NMW naming-scheme rounds (offset {start}): zero rows — the offset is past "
                      f"the {result['total']}-result register")
        return self._flat_env(
            tool="gb_nmw_rounds",
            input={"count": result["limit_applied"], "start": start},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x['public_timestamp'][:10] if x['public_timestamp'] else '—'} — "
                               f"{(x['title'] or '')[:110]}",
                       "url": x["url"]}
                      for x in result["rows"][:5]],
            provider_id="gb_nmw", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def gb_nmw_round(self, slug, *, execution=None, no_cache=None):
        """legal gb_nmw_round: one naming-scheme round's dossier (gov.uk press-release
        page, keyless, OGL): title/description/published/updated + xlsx_urls — the
        coordinate(s) of the official named-employers list on
        assets.publishing.service.gov.uk (Round_22_NMW_Naming_Scheme__List_of_employers_
        as_of_16_October.xlsx; attachment names carry NO year suffix — hand-assembling
        them 404s). The content API body is empty for these pages (the attachment exists
        only in the HTML); a release with no list (rate reminders) answers xlsx_urls=[]
        honestly."""
        self._lg_only("gb_nmw_round")
        r = legal.gb_nmw.round_raw(slug, cache=self._c._cache,
                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["xlsx_urls"]:
            reason = (f"NMW round {result['slug']}: {len(result['xlsx_urls'])} named-employers "
                      f"list(s) on the assets host — the official list is the xlsx body "
                      f"(batch line); published {result['published'] or '—'}")
        else:
            reason = (f"NMW round {result['slug']}: no xlsx attachment — not a numbered round "
                      f"(a rate-reminder or statistics release riding the same query)")
        return self._flat_env(
            tool="gb_nmw_round",
            input={"slug": result["slug"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(result['title'] or '')[:110]} · "
                               f"{len(result['xlsx_urls'])} xlsx · {result['published'] or '—'}",
                       "url": result["xlsx_urls"][0] if result["xlsx_urls"] else result["url"]}],
            provider_id="gb_nmw", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"slug": result["slug"]}},
        )

    def ie_revenue_defaulters(self, part=None, *, year=None, month=None,
                              execution=None, no_cache=None):
        """legal ie_revenue_defaulters: Irish Revenue List of Defaulters (revenue.ie, keyless; the
        statutory quarterly publication, current year on the index). One part per call — part 1 =
        penalties determined by a court (issue type / fine / sentence / charges), part 2 = Revenue
        settlements (tax / interest / penalties / total / unpaid): TWO row schemas under one
        publication, `kind` says which; individuals + companies in one register; money as ints
        (comma-thousands stripped, decimals/annotations dropped); names/addresses are published by
        statute — the co_sic precedent."""
        self._lg_only("ie_revenue_defaulters")
        r = legal.ie_revenue.defaulters_raw(part, year=year, month=month,
                                            cache=self._c._cache,
                                            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["rows"]:
            tail = (f"statutory quarterly publication, part {result['part']} = "
                    + ("court-determined penalties (fine + sentence + charges)"
                       if result["kind"] == "court_penalties" else
                       "Revenue settlements (Total = the settlement, Unpaid = still outstanding)"))
            reason = (f"Irish Revenue defaulters {result['quarter']} part {result['part']}: "
                      f"{result['count']} rows — {tail}; "
                      f"quarters on the index: {', '.join(result['available_quarters'])}")
        else:
            reason = (f"Irish Revenue defaulters {result['quarter']} part {result['part']} is empty "
                      "(a quarter with no entries above the disclosure threshold — a legitimate answer)")
        if result["kind"] == "court_penalties":
            evidence = [{"quote": f"{x['name'] or '—'} ({x['occupation'] or '—'}) "
                                  + (f"· fine €{x['fine_amount']:,}" if x["fine_amount"] is not None else "· fine —")
                                  + (f", {x['sentence_imposed']}" if x["sentence_imposed"] else ""),
                         "url": "https://www.revenue.ie/en/corporate/press-office/list-of-defaulters/index.aspx"}
                        for x in result["rows"][:5]]
        else:
            evidence = [{"quote": f"{x['name'] or '—'} ({x['occupation'] or '—'}, {x['county'] or '—'}) "
                                 + (f"· Total €{x['total']:,}" if x["total"] is not None else "· Total —")
                                 + (f", unpaid €{x['unpaid']:,}" if x["unpaid"] else ""),
                         "url": "https://www.revenue.ie/en/corporate/press-office/list-of-defaulters/index.aspx"}
                        for x in result["rows"][:5]]
        return self._flat_env(
            tool="ie_revenue_defaulters",
            input={"part": result["part"], "year": year, "month": month,
                   "quarter": result["quarter"]},
            reason=reason,
            result=result,
            evidence=evidence,
            provider_id="ie_revenue", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def in_sebi_orders(self, category="member_orders", *, search=None, from_date=None,
                       to_date=None, page=1, execution=None, no_cache=None):
        """legal in_sebi_orders: SEBI enforcement orders (sebi.gov.in/sebiweb AJAX fragment;
        the legal domain's first IN face). 11 order categories verbatim (--category; default
        = Chairperson/Members, 6,433 orders; AO holds 12,020). search is the site's own entity
        filter ("Adani" → 17); fromDate/toDate are DD-MM-YYYY (the upstream form's own
        format). One stateless POST per page (next=n + zero-based doDirect — the channel the
        site's own pager uses); a page past the last answers the CLEAN empty page
        ("No record(s) available.", nextDel=0) — no snap-back. Rows: date verbatim
        ("Nov 03, 2026") + title + the order PDF url."""
        self._lg_only("in_sebi_orders")
        r = legal.in_sebi.orders_raw(category, search=search, from_date=from_date,
                                     to_date=to_date, page=page,
                                     cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        top = (rows or [None])[0]
        total_s = f"{r['total']:,}" if isinstance(r["total"], int) else "—"
        if rows:
            reason = (f"SEBI orders ({r['category_name']}): {total_s} orders"
                      + (f" matching \"{r['params']['search']}\"" if r["params"]["search"] else "")
                      + (f", {r['params']['fromDate']}..{r['params']['toDate']}"
                         if r["params"]["fromDate"] or r["params"]["toDate"] else "")
                      + f", page {r['page']}/{r['pages'] or '—'}"
                      + (", more pages" if r["has_more"] else "")
                      + f", top {top['date']} — {top['title'][:70]}")
        elif r["pages"] is not None and r["page"] > r["pages"]:
            reason = (f"SEBI orders ({r['category_name']}): the clean empty page — page {r['page']} "
                      f"is past the last ({r['pages']}); the fragment answers "
                      "\"No record(s) available.\" (nextDel=0), no snap-back")
        else:
            reason = (f"SEBI orders ({r['category_name']}): zero hits"
                      + (f" for \"{r['params']['search']}\"" if r["params"]["search"] else "")
                      + " — a legitimate answer (the filter is the site's own)")
        return self._flat_env(
            tool="in_sebi_orders",
            input={"category": r["category"], "search": search, "from_date": from_date,
                   "to_date": to_date, "page": r["page"]},
            reason=reason,
            result={k: x for k, x in r.items() if k != "_meta"},
            evidence=[{"quote": f"{x['date']} · {x['title']}", "url": x["url"]}
                      for x in rows[:5]],
            provider_id="in_sebi", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def us_occ_enforcements(self, year=None, *, month=None, all_year=False,
                            execution=None, no_cache=None):
        """legal us_occ_enforcements: US OCC monthly bank-enforcement releases (occ.gov, keyless;
        the by-year news-release listing → the "Enforcement Actions" releases → the body). TWO
        body schemas under one face, `form` says which — sentences (2024+): one row per bank
        action (cmp_amount scaled from the "$750 million" wording; docket No. AA-ENF-YYYY-NN is
        the EASearch join key) plus IAP = institution-affiliated-party prohibition rows (names
        are statutory public disclosures — the co_sic precedent); tables (≤2020): per-section
        order rows (No./Name-Bank-City/State/Date). Default = the latest release of the year;
        --month picks by month name (2026-era titles carry it, earlier listings' dates do)."""
        self._lg_only("us_occ_enforcements")
        r = legal.occ.enforcements_raw(year, month=month, all_year=all_year,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        sel = [s["nr"] for s in result["selected"]]
        rel_url = {s["nr"]: "https://www.occ.gov" + s["path"] for s in result["selected"]}
        if result["rows"]:
            reason = (f"OCC {result['year']} enforcement actions: {result['count']} rows from "
                      f"{len(sel)} release(s) ({', '.join(sel)}), form={result['form']} — docket "
                      f"No. AA-ENF-* is the official key (joins the EASearch database, 1989+, out "
                      f"of SDK scope); cmp_amount is scaled from the \"$750 million\" wording; "
                      f"IAP = institution-affiliated party (individual prohibition orders — names "
                      f"published by statute, the co_sic precedent)")
        else:
            reason = (f"OCC {result['year']} enforcement actions: {len(sel)} release(s) "
                      f"({', '.join(sel)}) parsed to the {result['form']} shape but carried zero "
                      "action rows — a legitimate answer only if the release genuinely holds none; "
                      "check upstream before trusting it")
        return self._flat_env(
            tool="us_occ_enforcements",
            input={"year": result["year"], "month": month, "all_year": bool(all_year),
                   "releases": sel, "form": result["form"]},
            reason=reason,
            result=result,
            evidence=[{"quote": ((x.get("name") or x.get("who") or "—")
                                 + (f" ({x['city']}, {x['state']})"
                                    if x.get("city") or x.get("state") else "")
                                 + (f" · CMP ${x['cmp_amount']:,}" if x.get("cmp_amount") else "")
                                 + (f" · {x['role']}" if x.get("role") else "")
                                 + (f" · dockets {'/'.join(x['dockets'])}" if x.get("dockets") else "")
                                 + (f" · {x['order_type']} {x['date']}" if x.get("order_type") else "")
                                 + f" · {x['release_nr']}"),
                       "url": rel_url.get(x.get("release_nr"),
                                          "https://www.occ.gov/news-events/newsroom/news-issuances-by-year/news-releases.html")}
                      for x in result["rows"][:5]],
            provider_id="occ", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.31 CFPB consumer-complaint faces (dictionary slot: cfpb between ca_sema and co_sic) ——
    def cfpb_complaints(self, search_term=None, *, field=None, company=None, product=None,
                        issue=None, state=None, zip_code=None, submitted_via=None, timely=None,
                        company_response=None, company_public_response=None, tags=None,
                        date_received_min=None, date_received_max=None,
                        company_received_min=None, company_received_max=None,
                        frm=None, size=10, sort=None, search_after=None, aggregations=False,
                        execution=None, no_cache=None):
        """legal cfpb_complaints: US CFPB consumer complaints (consumerfinance.gov; keyless, CC0).

        The complaint search (the corpus: ~18.9M complaints, re-indexed daily). Two company channels
        with different semantics: `search_term` is the FUZZY one (with field=company it matches
        company names loosely), while the `company` filter is EXACT and case-sensitive — the
        corpus' own spelling ("TRANSUNION INTERMEDIATE HOLDINGS, INC."), not the brand; resolve a
        brand with cfpb_suggest_company first. The row is the 15 official complaint fields."""
        self._lg_only("cfpb_complaints")
        r = legal.cfpb.complaints_raw(search_term, field=field, company=company, product=product,
                                       issue=issue, state=state, zip_code=zip_code,
                                       submitted_via=submitted_via, timely=timely,
                                       company_response=company_response,
                                       company_public_response=company_public_response, tags=tags,
                                       date_received_min=date_received_min,
                                       date_received_max=date_received_max,
                                       company_received_min=company_received_min,
                                       company_received_max=company_received_max,
                                       frm=frm, size=size, sort=sort, search_after=search_after,
                                       aggregations=aggregations,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        url = ("https://www.consumerfinance.gov/data-research/consumer-complaints/"
               "search/api/v1/?" + urllib.parse.urlencode(result["params"], doseq=True))
        corpus = result["total_record_count"]
        corpus_s = f"{corpus:,}" if isinstance(corpus, int) else "?"
        if result["rows"]:
            reason = (f"CFPB consumer complaint database: {result['total']:,} complaints match, "
                      f"{result['count']} rows returned (corpus {corpus_s}, "
                      f"last updated {result['last_updated']}"
                      + (f", relation={result['relation']}" if result["relation"] else "") + ") — "
                      "the company filter is exact and case-sensitive (the corpus' own spelling, "
                      "not the brand: resolve one with cfpb_suggest_company); search_term is the "
                      "fuzzy channel, field=company narrows it to the company field")
        else:
            reason = (f"CFPB consumer complaint database: {result['total']:,} complaints match, zero "
                      "rows returned — if you filtered by company, remember the filter is EXACT "
                      "and case-sensitive (a brand name is not the corpus key: resolve one with "
                      "cfpb_suggest_company)")
        return self._flat_env(
            tool="cfpb_complaints",
            input={"search_term": search_term, "field": field, "company": company,
                   "product": product, "issue": issue, "state": state, "zip_code": zip_code,
                   "submitted_via": submitted_via, "timely": timely,
                   "company_response": company_response,
                   "company_public_response": company_public_response, "tags": tags,
                   "date_received_min": date_received_min, "date_received_max": date_received_max,
                   "company_received_min": company_received_min,
                   "company_received_max": company_received_max,
                   "frm": result["frm"], "size": result["size"], "sort": sort,
                   "search_after": search_after, "aggregations": bool(aggregations)},
            reason=reason,
            result=result,
            evidence=[{"quote": (f"{x.get('company') or '—'} · {x.get('product') or '—'}"
                                 + (f" / {x.get('sub_product')}" if x.get("sub_product") else "")
                                 + f" · {x.get('issue') or '—'} · received {x.get('date_received') or '—'}"
                                 + (f" · {x.get('state')}" if x.get("state") else "")
                                 + (f" · {x.get('company_response')}" if x.get("company_response") else "")),
                       "url": url}
                      for x in result["rows"][:5]],
            provider_id="cfpb", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def cfpb_suggest_company(self, text=None, *, size=10, execution=None, no_cache=None):
        """legal cfpb_suggest_company: the CFPB company typeahead (consumerfinance.gov; keyless).

        Resolves a company name to the corpus' own spelling — the key the complaints face's
        `company=` filter (exact, case-sensitive) needs. The upstream returns a bare array of
        company strings."""
        self._lg_only("cfpb_suggest_company")
        r = legal.cfpb.suggest_company_raw(text, size=size, cache=self._c._cache,
                                            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        url = ("https://www.consumerfinance.gov/data-research/consumer-complaints/"
               "search/api/v1/_suggest_company/?" + urllib.parse.urlencode(result["params"]))
        if result["suggestions"]:
            reason = (f"CFPB company typeahead: {result['count']} company strings match "
                      f"'{result['text']}' — these are the corpus' own spellings; pass one to "
                      "cfpb_complaints --company (that filter is exact and case-sensitive, so the "
                      "brand name itself will not match)")
        else:
            reason = (f"CFPB company typeahead: no company string matches '{result['text']}' — "
                      "the typeahead only knows companies that appear in the complaint corpus")
        return self._flat_env(
            tool="cfpb_suggest_company",
            input={"text": result["text"], "size": result["params"].get("size")},
            reason=reason,
            result=result,
            evidence=[{"quote": s, "url": url} for s in result["suggestions"][:5]],
            provider_id="cfpb", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.36 TR SPK enforcement faces (dictionary slot: tr_spk between sipri and us_occ) ——

    def tr_spk_fines(self, name=None, *, year=None, limit=20, execution=None, no_cache=None):
        """legal tr_spk_fines: SPK administrative fines (ws.spk.gov.tr; the legal domain's first
        TR face). The WHOLE register ships in ONE keyless GET — 2,281 rows 2016→, cached 24h
        and scanned locally (upstream publishes no query surface; the POST filter body is
        silently ignored). Rows are the 14 upstream columns verbatim; 1,281 of 2,281 subjects
        are INDIVIDUALS (mkkSicilNo masked); davaBilgisi Var = a lawsuit stage rides
        yargilamaAsamasi; tutar = the fine in TL. name = contains over unvan; year = the
        Board-decision year."""
        self._lg_only("tr_spk_fines")
        nm = str(name or "").strip() or None
        r = legal.tr_spk.fines_raw(nm, year=year, limit=limit,
                                   cache=self._c._cache,
                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        cen = result["census"]
        if result["rows"]:
            reason = (f"SPK administrative fines: {result['total_matched']} of {result['scanned_rows']:,} rows matched"
                      + (f" (name contains \"{nm}\")" if nm else "")
                      + (f", karar year {year}" if year else "")
                      + f" — {cen['persons']:,} of {result['scanned_rows']:,} subjects are individuals (mkkSicilNo arrives masked),"
                      + f" karar years {cen['year_min']}→{cen['year_max']}, dava Var {cen['dava_var']:,};"
                      + " tutar is the fine in TL; teblig cites the communiqué clause (yasa/madde are near-always null);"
                      + " zero hits = no SPK fine on record")
        else:
            reason = (f"SPK administrative fines: zero hits on the {result['scanned_rows']:,}-row register"
                      + (f" (name contains \"{nm}\")" if nm else "")
                      + (f", karar year {year}" if year else "")
                      + " — a legitimate answer = clean screening (drop filters to enumerate from the head)")
        return self._flat_env(
            tool="tr_spk_fines",
            input={"name": nm, "year": year, "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x['unvan'] or '—'} · karar {x['kurulKararNo']} "
                               f"{(x['kurulKararTarihi'] or '')[:10]} · ₺{x['tutar']:,.2f}"
                               + (f" · {str(x['teblig'] or '')[:60]}" if x["teblig"] else ""),
                       "url": "https://idariyaptirimlar.spk.gov.tr/idariparacezalari"}
                      for x in result["rows"][:5]],
            provider_id="tr_spk", metas=[r["_meta"]],
        )

    def tr_spk_bans(self, name=None, *, type=None, limit=20, execution=None, no_cache=None):
        """legal tr_spk_bans: SPK capital-market trading bans (ws.spk.gov.tr IslemYasaklari).
        Both walls in one call — persons (295, mkkSicilNo masked) + companies (3, mersisNo the
        16-digit MERSIS key), each company auto-enriched with its ban edges (pay = the banned
        equity's issuer, payKodu = the BIST ticker, karar no/date — the substance of the ban).
        name = contains over person name / company name / the banned issuer (screening the
        issuer hits the banned party); type = person|company. The person-detail endpoint's key
        is the UNMASKED MKK number, which the public list masks — not shippable, so person rows
        stay two-column."""
        self._lg_only("tr_spk_bans")
        nm = str(name or "").strip() or None
        r = legal.tr_spk.bans_raw(nm, type=type, limit=limit,
                                  cache=self._c._cache,
                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        sc = result["scanned"]
        if result["rows"]:
            reason = (f"SPK trading bans: {result['total_matched']} of {sc['persons'] + sc['companies']} rows matched"
                      + f" ({sc['persons']} persons + {sc['companies']} companies on the walls"
                      + (f", type {type}" if type else "") + ")"
                      + (f", name contains \"{nm}\"" if nm else "")
                      + " — company rows carry bans = one edge per banned equity (pay the issuer, payKodu the BIST"
                        " ticker); person rows stay two-column (the unmasked MKK key the detail endpoint needs is"
                        " not public); zero hits = no SPK ban on record")
        else:
            reason = (f"SPK trading bans: zero hits on the {sc['persons']}-person + {sc['companies']}-company walls"
                      + (f" (name contains \"{nm}\"" if nm else "")
                      + (f"{', ' if nm else '('}type {type}" if type else "")
                      + ") — a legitimate answer = clean screening (drop filters to enumerate both walls)")
        ev = []
        for x in result["rows"][:5]:
            if x["kind"] == "person":
                ev.append({"quote": f"{x['isimSoyisim'] or '—'} · mkk {x['mkkSicilNo'] or '—'} (masked)",
                           "url": "https://idariyaptirimlar.spk.gov.tr/islemyasaklari"})
            else:
                edges = "; ".join(f"{b.get('payKodu') or '?'} ({(b.get('pay') or '')[:40]}) karar "
                                  f"{b.get('kurulKararNo')} {(b.get('kurulKararTarihi') or '')[:10]}"
                                  for b in (x.get("bans") or []))
                ev.append({"quote": f"{x['unvani'] or '—'} · MERSIS {x['mersisNo']}"
                                   + (f" · banned: {edges}" if edges else " · no ban edges resolved"),
                           "url": "https://idariyaptirimlar.spk.gov.tr/islemyasaklari"})
        return self._flat_env(
            tool="tr_spk_bans",
            input={"name": nm, "type": type, "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=ev,
            provider_id="tr_spk", metas=metas,
        )

    # —— 0.3.55 API-faces batch A (dictionary slots: mx_cnv < mx_sabg < nl_rechtspraak, between lda and ru_cbr) ——

    def mx_cnv_sanctions(self, *, page_number=0, page_size=1000, order_field=None,
                         order_type=None, execution=None, no_cache=None):
        """legal mx_cnv_sanctions: CNBV financial-sanctions register (apim-servicios.cnbv.gob.mx,
        keyless by publication — the APIM subscription key is hardcoded in the public frontend).
        Header-paginated bare row list: totals ride x-total-items/x-total-pages (11,593 rows live
        2026-11-12; everything since the 2014-01-10 Lineamientos INCLUDING the non-regulated AML
        faces — Centros Cambiarios / Transmisores de Dinero / SOFOMES E.N.R.). obligatedSubject is
        the company join key; amount is numeric MXN; pagado is the paid flag. page_number is
        0-based (the upstream's own semantics); the op is uncached (header-only paging state)."""
        self._lg_only("mx_cnv_sanctions")
        r = legal.mx_cnv.sanctions_raw(page_number=page_number, page_size=page_size,
                                       order_field=order_field, order_type=order_type)
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["rows"]:
            top = result["rows"][0]
            amt = f"MXN {top['amount']:,}" if isinstance(top.get("amount"), (int, float)) else "amount —"
            reason = (f"CNBV sanctions: {result['total_items']:,} rows on the register"
                      + (f", page {result['page_number']} of {result['total_pages']:,}" if result["total_pages"] else "")
                      + f", {len(result['rows'])} returned — {top.get('type') or '—'} on "
                        f"{top.get('obligatedSubject') or '—'} ({amt})"
                      + (f" imposed {top.get('imposedOn')}" if top.get("imposedOn") else "")
                      + (" · PAID" if top.get("pagado") else " · unpaid")
                      + " — obligatedSubject is the company join key; walk page_number 0..total_pages-1 at page_size 1000 for the whole ledger")
        else:
            reason = (f"CNBV sanctions: zero rows on page {result['page_number']}"
                      + (f" (the register carries {result['total_items']:,} rows)" if result["total_items"] else "")
                      + " — a page past x-total-pages or an empty filter; page_number is 0-BASED")
        return self._flat_env(
            tool="mx_cnv_sanctions",
            input={"page_number": result["page_number"], "page_size": result["page_size_applied"],
                   "order_field": order_field, "order_type": order_type},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x.get('id')} · {x.get('obligatedSubject') or '—'} — {x.get('type') or '—'} "
                                + (f"MXN {x['amount']:,}" if isinstance(x.get("amount"), (int, float)) else "amount —")
                                + f" · {x.get('imposedOn') or '?'}"
                                + (" · paid" if x.get("pagado") else ""),
                       "url": "https://sanciones.cnbv.gob.mx/"}
                      for x in result["rows"][:5]],
            provider_id="mx_cnv", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"headers": result["headers_sent"]}},
        )

    def mx_sabg_sanctioned_servants(self, q=None, *, filters=None, limit=100, offset=0,
                                    sort=None, execution=None, no_cache=None):
        """legal mx_sabg_sanctioned_servants: Mexican sanctioned public servants, in-force
        register (datos.gob.mx CKAN datastore bypass — the direct CSV sits behind an Akamai gate,
        the datastore inlines the whole register as JSON; keyless, 435 rows live 2026-11-12,
        monthly snapshot). Rows are the 13 statutory columns verbatim: expediente / the person's
        three name parts / autoridad / dependencia / sancion_impuesta (Inhabilitación) / causa
        (Abuso de autoridad…) / inicio→fin THE BARRING WINDOW / ley (LFRASP). The historical
        archive (already-unbarred) is behind the PDN S3 challenge gate — not this face."""
        self._lg_only("mx_sabg_sanctioned_servants")
        qq = str(q or "").strip() or None
        r = legal.mx_sabg.sanctioned_servants_raw(qq, filters=filters, limit=limit,
                                                  offset=offset, sort=sort,
                                                  cache=self._c._cache,
                                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["rows"]:
            top = result["rows"][0]
            name = " ".join(str(top.get(k) or "") for k in ("nombre", "apellido_paterno", "apellido_materno")).strip()
            reason = (f"SABG sanctioned servants (in-force): {result['total']} rows on the register, "
                      f"{len(result['rows'])} returned"
                      + (f" (q \"{qq}\")" if qq else "")
                      + (f" (filters {filters})" if filters else "")
                      + f" — sample {name or '—'} · {top.get('causa') or '—'} · barred {top.get('inicio') or '?'}→{top.get('fin') or '?'}"
                        f" · the inicio→fin window is the live judgement (fin in the past = the row leaves this register)")
        else:
            reason = ("SABG zero hits (an empty result is a legitimate answer; q is a full-text match and "
                      "filters are exact-match — drop them to enumerate the register head)")
        return self._flat_env(
            tool="mx_sabg_sanctioned_servants",
            input={"q": qq, "filters": filters, "limit": result["limit_applied"],
                   "offset": offset, "sort": sort},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x.get('expediente') or '—'} · "
                                f"{' '.join(str(x.get(k) or '') for k in ('nombre', 'apellido_paterno', 'apellido_materno')).strip() or '—'}"
                                f" · {x.get('dependencia') or '—'} · {x.get('causa') or '—'} · barred "
                                f"{x.get('inicio') or '?'}→{x.get('fin') or '?'} ({x.get('ley') or '—'})",
                       "url": "https://www.datos.gob.mx/"}
                      for x in result["rows"][:5]],
            provider_id="mx_sabg", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def nl_rechtspraak_search(self, q=None, *, sort_order="Relevance", start_row=0,
                              page_size=20, facets=False, execution=None, no_cache=None):
        """legal nl_rechtspraak_search: Netherlands judiciary published-case search
        (uitspraken.rechtspraak.nl/api/zoek, keyless POST with a strict PascalCase body — the one
        verified shape; malformed variants are answered by the mededeling SPA error page). ~479k
        published cases live 2026-11-12; TitelEmphasis IS the ECLI, GerechtelijkProductType splits
        uitspraak vs conclusie (the advocate-general stream), dates are DD-MM-YYYY text, and the
        register reaches 1847 (UitspraakDatumAsc head). pdf_url is derived per row (the verified
        full-text channel, colons→underscores) without fetching; facets=True rides the six-axis
        FacetCounts on the same call."""
        self._lg_only("nl_rechtspraak_search")
        qq = str(q or "").strip() or None
        r = legal.nl_rechtspraak.zoek_raw(qq, sort_order=sort_order, start_row=start_row,
                                          page_size=page_size, facets=facets,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["rows"]:
            top = result["rows"][0]
            reason = (f"Rechtspraak: {result['total']:,} published cases hit \"{result['q']}\", "
                      f"{len(result['rows'])} returned from row {result['start_row']}"
                      + (f" ({result['sort_order']})" if result["sort_order"] != "Relevance" else "")
                      + f" — sample {top.get('ecli') or '—'} · {(top.get('Uitspraakdatum') or '—')} · "
                        f"{(top.get('Titel') or '—')[:60]}"
                      + (f" · {top.get('GerechtelijkProductType')}" if top.get("GerechtelijkProductType") == "conclusie" else "")
                      + " — ECLI (TitelEmphasis) is the join key; pdf_url is the full-text channel")
        else:
            reason = (f"Rechtspraak: zero rows for \"{result['q']}\" at start_row {result['start_row']} — "
                      "a legitimate narrow query, or a start_row past the result set")
        return self._flat_env(
            tool="nl_rechtspraak_search",
            input={"q": result["q"], "sort_order": result["sort_order"],
                   "start_row": result["start_row"], "page_size": result["page_size_applied"],
                   "facets": facets},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x.get('ecli') or '—'} · {x.get('Uitspraakdatum') or '—'} · "
                                f"{(x.get('Titel') or '—')[:70]}"
                                + (f" · {(x.get('Tekstfragment') or '')[:60]}…" if x.get("Tekstfragment") else ""),
                       "url": x.get("DeeplinkUrl") or "https://uitspraken.rechtspraak.nl/"}
                      for x in result["rows"][:5]],
            provider_id="nl_rechtspraak", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"method": "POST", "path": "/api/zoek", "body": result["body"]}},
        )

    # —— 0.3.59 enforcement/party-finance cluster: eu_cijeu_search (joins the case-law searchers — nl_rechtspraak's
    # cluster; the letters run eu < nl, cluster adjacency wins; the CJEU affair index is
    # metadata-only — full text rides the CELEX → EUR-Lex Cellar bridge) ——
    def eu_cijeu_search(self, q=None, *, lang="EN", limit=20, page=0,
                        execution=None, no_cache=None):
        """legal eu_cijeu_search: CJEU jurisprudence search (infocuriaws elastic connector, the
        SPA's own XHR DSL; 'insurance' → 5,049 hits, bare browse → 7,630; exact-mode, tab
        jurisprudence, metadata rows — logicDocId/idPublished/celex/ecli/docDate carry the
        identity, full text via CELEX on EUR-Lex)."""
        self._lg_only("eu_cijeu_search")
        qq = str(q or "").strip() or None
        r = legal.eu_cijeu.search_raw(qq, lang=lang, limit=limit, page=page,
                                      cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="eu_cijeu_search",
            input={"q": result["params"]["q"], "lang": result["params"]["lang"],
                   "limit": result["params"]["limit"], "page": result["params"]["page"]},
            reason=(f"CJEU jurisprudence: {result['total']} hits"
                    + (f" for \"{qq}\"" if qq else " (bare tab browse)")
                    + f", returning {len(rows)} rows at page {page}"
                    + (f", top {top.get('id_published') or '—'} ({top.get('doc_date') or '—'}, CELEX {top.get('celex') or '—'})" if top
                       else " — zero hits (an empty result is a legal answer; exact-mode matching — try the party's own spelling)")
                    + " — the affair index carries metadata only; key the full text by celex on EUR-Lex"),
            result=result,
            evidence=[{"quote": f"{x.get('id_published') or '—'} · {x.get('doc_type') or '—'} · {x.get('doc_date') or '—'}"
                                + (f" · CELEX {x['celex']}" if x.get("celex") else ""),
                       "url": ("https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:" + x["celex"])
                       if x.get("celex") else "https://curia.europa.eu/juris/recherche.jsf"}
                      for x in rows[:5]],
            provider_id="eu_cijeu", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    # —— 0.3.37 RU CBR warning-list face (dictionary slot: ru_cbr between lda and sipri) ——

    def ru_cbr_warning_list(self, name=None, *, inn=None, site=None, violation=None, type=None,
                            limit=20, execution=None, no_cache=None):
        """legal ru_cbr_warning_list: the Bank of Russia warning list of entities with signs of
        illegal financial activity (www.cbr.ru UniDbQuery DownloadExcel export; the legal
        domain's first RU face). The WHOLE register ships in ONE keyless xlsx GET (~3.1MB,
        27,635 rows, span 2021-02→, nightly rebuild), cached 24h and scanned locally (upstream
        publishes no query surface on the export). Rows are the 12 upstream columns verbatim
        (Excel serials → ISO); the violations column carries SIX canonical kinds — rows keep the
        verbatim Russian wording, the filter splits the cell on commas/newlines; record_type
        keeps the register's own six-kind vocabulary. inn = the exact ИНН digit key (present on
        only ~3,100 rows — internet projects ship none); site = contains over site AND address
        (internet-project rows carry their t.me/*/workers.dev fronts in the address column)."""
        self._lg_only("ru_cbr_warning_list")
        nm = str(name or "").strip() or None
        r = legal.ru_cbr_warning.warning_list_raw(nm, inn=inn, site=site, violation=violation,
                                                  type=type, limit=limit,
                                                  cache=self._c._cache,
                                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        cen = result["census"]
        recap = (f" (name contains \"{nm}\")" if nm else "") \
            + (f", ИНН {inn}" if inn else "") \
            + (f", site contains \"{site}\"" if site else "") \
            + (f", violation={violation}" if violation else "") \
            + (f", type={type}" if type else "")
        if result["rows"]:
            reason = (f"Bank of Russia warning list: {result['total_matched']} of {result['scanned_rows']:,} rows matched"
                      + recap
                      + f" — register span {cen['date_min']}→{cen['date_max']}, ИНН present on only {cen['with_inn']:,} rows;"
                      + " rows keep the verbatim Russian violation wording;"
                      + " internet-project rows carry their t.me/*/workers.dev fronts in the address column")
        else:
            reason = (f"Bank of Russia warning list: zero hits on the {result['scanned_rows']:,}-row register"
                      + recap
                      + " — a legitimate answer = no warning on record (drop filters to enumerate from the head)")
        return self._flat_env(
            tool="ru_cbr_warning_list",
            input={"name": nm, "inn": result["params"]["inn"], "site": site,
                   "violation": violation, "type": type, "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['name'] or '—')[:60]} · {x['date'] or '—'} · {x['record_type'] or '—'}"
                                + (f" · {str(x['violations'])[:60]}" if x["violations"] else ""),
                       "url": "https://www.cbr.ru/Queries/UniDbQuery/DownloadExcel/123126"}
                      for x in result["rows"][:5]],
            provider_id="ru_cbr_warning", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.38 BR BACEN special-regimes face (dictionary slot: br_bacen between afdb and ca_sema) ——

    def br_bacen_regimes(self, name=None, *, cnpj=None, uf=None, limit=20,
                         execution=None, no_cache=None):
        """legal br_bacen_regimes: the BACEN special-regimes register — financial institutions
        under state administration (olinda.bcb.gov.br regimes_especiais; the legal domain's
        first BR face). Today one Tipo, LIQUIDAÇÃO EXTRAJUDICIAL (all 25 rows), Inicio
        02/08/2013→30/04/2026; the register ships whole in one keyless GET, cached 24h, scanned
        locally. A screening face: match an entity's CNPJ and you know it is being wound down,
        with the liquidation's own contact block (responsavel/emails/telefones) for
        verification. cnpj accepts the 8-digit root or the 14-digit whole key — both sit on
        every row; dates are the register's own dd/mm/yyyy, verbatim."""
        self._lg_only("br_bacen_regimes")
        nm = str(name or "").strip() or None
        r = legal.br_bacen_regimes.regimes_raw(nm, cnpj=cnpj, uf=uf, limit=limit,
                                               cache=self._c._cache,
                                               no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        cen = result["census"]
        recap = (f" (name contains \"{nm}\")" if nm else "") \
            + (f", CNPJ {result['params']['cnpj']}" if result["params"]["cnpj"] else "") \
            + (f", UF {result['params']['uf']}" if result["params"]["uf"] else "")
        if result["rows"]:
            reason = (f"BACEN special-regimes register: {result['total_matched']} of {result['scanned_rows']} rows matched"
                      + recap
                      + f" — {cen['by_tipo'].get('LIQUIDAÇÃO EXTRAJUDICIAL', 0)} of {result['scanned_rows']} rows are"
                      + " LIQUIDAÇÃO EXTRAJUDICIAL (extrajudicial liquidation, the register's only regime today),"
                      + f" Inicio span {cen['start_date_min']}→{cen['start_date_max']};"
                      + " responsavel/emails/telefones are the liquidation's own contact block")
        else:
            reason = (f"BACEN special-regimes register: zero hits on the {result['scanned_rows']}-row register"
                      + recap
                      + " — a legitimate answer = no special regime on record (drop filters to enumerate from the head)")
        return self._flat_env(
            tool="br_bacen_regimes",
            input={"name": nm, "cnpj": result["params"]["cnpj"],
                   "uf": result["params"]["uf"], "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['name'] or '—')[:60]} · {x['tipo']} · from {x['inicio'] or '—'}"
                                + f" · CNPJ {x['cnpj'] or '—'}",
                       "url": "https://olinda.bcb.gov.br/olinda/servico/regimes_especiais/versao/v1/odata/Regimes"}
                      for x in result["rows"][:5]],
            provider_id="br_bacen_regimes", metas=metas,
            query={"source": "raw", "upstream": r["params"]},
        )

    def br_bacen_complaints(self, name=None, *, ano=None, periodicidade=None, periodo=None,
                            tipo="banks", cnpj=None, limit=20, execution=None, no_cache=None):
        """legal br_bacen_complaints: the BACEN rdrweb complaint-index ranking (www3.bcb.gov.br
        /rdrweb/rest/ext/ranking + /arquivo CSV) — consumer complaints against financial
        institutions that BACEN received, analysed and closed per reference period, 2014→. The
        period catalog is the axis: (ano, periodicidade, periodo, tipo) is validated against it
        (a ghost combination answers usage_error with the available combos — upstream would
        answer HTTP 204 with a 0-byte body); defaults ride the catalog's latest slot for the
        tipo. tipo=banks (Bancos e financeiras, quarterly) or consortiums (Consorcios,
        semi-annual — CNPJ on every row). Schema drifts by era; rows keep the columns the file
        carries; Índice is computed only for ranked institutions (honest blanks → null)."""
        self._lg_only("br_bacen_complaints")
        nm = str(name or "").strip() or None
        r = legal.br_bacen_complaints.complaints_raw(
            nm, ano=ano, periodicidade=periodicidade, periodo=periodo, tipo=tipo, cnpj=cnpj,
            limit=limit, cache=self._c._cache,
            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        p = result["params"]
        cen = result["census"]
        recap = (f" (name contains \"{nm}\")" if nm else "") \
            + (f", CNPJ {p['cnpj']}" if p["cnpj"] else "")
        label = {"banks": "Bancos e financeiras", "consortiums": "Consorcios"}[p["tipo"]]
        period_note = (f"period {p['ano']} {p['periodicidade']} p{p['periodo']} ({label})"
                       f", catalog 2014→ latest slot")
        if result["rows"]:
            top = result["rows"][0]
            head = f" · top row: {(top['name'] or '—')[:40]}"
            head += f" Índice {top['indice'] if top['indice'] is not None else '—'}" \
                if isinstance(top.get("indice"), (int, float)) else ""
            reason = (f"BACEN rdrweb complaint-index ranking: {result['total_matched']} of "
                      f"{result['scanned_rows']} rows matched{recap} — {period_note}"
                      f"; {cen['with_indice']} of {cen['total']} rows carry an Índice"
                      f" (max {cen['indice_max']}); {cen['with_cnpj_root']} rows carry a CNPJ root"
                      + head)
        else:
            reason = (f"BACEN rdrweb complaint-index ranking: zero hits on the "
                      f"{result['scanned_rows']}-row {period_note} panel{recap}"
                      " — a legitimate answer = no complaint row for that filter (the register"
                      " lists institutions WITH analysed complaints; drop filters to enumerate)")
        return self._flat_env(
            tool="br_bacen_complaints",
            input={"name": nm, "ano": p["ano"], "periodicidade": p["periodicidade"],
                   "periodo": p["periodo"], "tipo": p["tipo"], "cnpj": p["cnpj"],
                   "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['name'] or '—')[:60]}"
                                + (f" · CNPJ {x['cnpj_root']}" if x.get("cnpj_root") else "")
                                + (f" · Índice {x['indice']}" if x.get("indice") is not None else "")
                                + (f" · {x['categoria']}" if x.get("categoria") else ""),
                       "url": f"https://www3.bcb.gov.br/rdrweb/rest/ext/ranking/arquivo"
                              f"?ano={p['ano']}&periodicidade={p['periodicidade']}"
                              f"&periodo={p['periodo']}&tipo={label.replace(' ', '%20')}"}
                      for x in result["rows"][:5]],
            provider_id="br_bacen_complaints", metas=metas,
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.47 AT RIS OGD faces (dictionary slot: at_ris between afdb and br_bacen; legal's first AT face) ——

    def at_ris_judgments(self, court="Justiz", *, q=None, case_number=None, norm=None,
                         date_from=None, date_to=None, page=1, limit=20, execution=None,
                         no_cache=None):
        """legal at_ris_judgments: Austrian case law over the RIS OGD API v2.6 (data.bka.gv.at,
        keyless, CC BY 4.0; the legal domain's first AT face). Judikatur = ~1.01M documents in 16
        exact-case court shards — Justiz (OGH/OLG/LG/BG merged, the default) 138,516 / Vwgh 357,753
        / Bvwg 292,078 / Lvwg 78,286 / AsylGH 53,113 / Uvs 25,939 / Vfgh 24,177 / Normenliste
        14,676 / Verg 8,143 / Dok 4,873 / Ubas 4,052 / Pvak 2,550 / Dsk 1,891 / Gbk 1,067 / Bks 745
        / Umse 742 (census 2026-11-03, daily drift). q = Suchworte full text; case_number =
        Geschaeftszahl in the case's own spacing ("2 Ob 52/16k" → the Rechtssatz family, 27 rows);
        norm = the norm citation axis; date_from/date_to = the Entscheidungsdatum window
        (YYYY-MM-DD). Rows are the Metadaten projection with ECLI verbatim; Entscheidungstexte
        keep coordinates only (Geschaeftszahl/DokumentUrl) — the long Beisatz annotations ride the
        ogd.ris.bka.gv.at document URL, not this face. Page size is pinned at 20 upstream
        (--limit is a local slice); beyond the last page (ceil(total/20)) the upstream answers
        HTTP 500 "Die Seitennummer ist höher als die Anzahl der verfügbaren Seiten" — read total
        from any response and page inside the window."""
        self._lg_only("at_ris_judgments")
        r = legal.at_ris.judgments_raw(court, q=q, case_number=case_number, norm=norm,
                                       date_from=date_from, date_to=date_to, page=page,
                                       limit=limit,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        cen = result["census"]
        shard = cen["shard_census_2026_11_03"].get(result["court"])
        recap = (f" (Suchworte contains \"{q}\")" if q else "") \
            + (f", Geschaeftszahl {case_number}" if case_number else "") \
            + (f", Norm {norm}" if norm else "") \
            + (f", {date_from}→{date_to}" if date_from or date_to else "")
        if result["rows"]:
            reason = (f"RIS Judikatur shard {result['court']}: page {result['page']} of "
                      f"{(result['total'] + 19) // 20 if result['total'] else '?'} "
                      f"({result['total']:,} documents; census 2026-11-03 {shard:,}, live drift is the "
                      f"daily refresh){recap} — page size pinned at 20 upstream; rows carry ECLI "
                      f"verbatim and document coordinates (full texts ride the ogd.ris.bka.gv.at URLs)")
        else:
            reason = (f"RIS Judikatur shard {result['court']}: zero rows on page {result['page']}"
                      f"{recap} — a legitimate answer = no judgment matches on this page; read total "
                      f"(the shard census is {shard:,}) and page inside ceil(total/20), or drop "
                      f"filters — beyond the last page the upstream answers HTTP 500, not an empty page")
        return self._flat_env(
            tool="at_ris_judgments",
            input={"court": result["court"], "q": q, "case_number": case_number,
                   "norm": norm, "date_from": date_from, "date_to": date_to,
                   "page": result["page"], "limit": limit},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['ecli'] or x['ris_id'] or '—')}"
                                + (f" · {x['geschaeftszahlen'][0]}" if x["geschaeftszahlen"] else "")
                                + (f" · {x['dokumenttyp']}" if x["dokumenttyp"] else "")
                                + (f" · {x['entscheidungsdatum']}" if x["entscheidungsdatum"] else ""),
                       "url": x["dokument_url"] or "https://data.bka.gv.at/ris/api/v2.6/Judikatur"}
                      for x in result["rows"][:5]],
            provider_id="at_ris", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def at_ris_statutes(self, *, q=None, page=1, limit=20, execution=None, no_cache=None):
        """legal at_ris_statutes: consolidated Austrian federal law over the RIS OGD API v2.6
        (Bundesrecht?Applikation=BrKons, 442,058 documents, census 2026-11-03). q = Suchworte full
        text (GmbH → 6,908 documents). Rows are the BrKons projection: NOR id, Kurztitel/Titel, ELI
        canonical link, Kundmachungsorgan + BGBl citation axes (Stammnorm/Novellen), Typ,
        Art/Paragraph, and the validity window — Ausserkrafttretensdatum is present-only (in-force
        norms carry none). Page size pinned at 20 upstream; the beyond-last-page HTTP-500 wall and
        the daily drift posture are the same as Judikatur."""
        self._lg_only("at_ris_statutes")
        r = legal.at_ris.statutes_raw(q=q, page=page, limit=limit,
                                      cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        recap = (f" (Suchworte contains \"{q}\")" if q else "")
        if result["rows"]:
            reason = (f"RIS Bundesrecht/BrKons: page {result['page']} of "
                      f"{(result['total'] + 19) // 20 if result['total'] else '?'} "
                      f"({result['total']:,} documents; census 2026-11-03 "
                      f"{result['census']['corpus_documents_2026_11_03']:,}){recap} — consolidated "
                      f"federal law: Stammnorm/Novellen BGBl axes + in-force window; rows whose "
                      f"ausserkrafttretensdatum is absent are in force")
        else:
            reason = (f"RIS Bundesrecht/BrKons: zero rows on page {result['page']}{recap} — a "
                      f"legitimate answer = no consolidated norm matches on this page; read total and "
                      f"page inside ceil(total/20) — beyond the last page the upstream answers HTTP 500")
        return self._flat_env(
            tool="at_ris_statutes",
            input={"q": q, "page": result["page"], "limit": limit},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x['nor_id'] or '—'} · {str(x['kurztitel'] or x['titel'] or '—')[:60]}"
                                + (f" · {x['typ']}" if x["typ"] else "")
                                + (f" · {x['kundmachungsorgan']}" if x["kundmachungsorgan"] else ""),
                       "url": x["dokument_url"] or "https://data.bka.gv.at/ris/api/v2.6/Bundesrecht"}
                      for x in result["rows"][:5]],
            provider_id="at_ris", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.50 enforcement/party-finance tier (us_ferc / ie_sipo / ee_erjk ×2 / ua_nazk ×2; the legal domain's first EE and UA jurisdictions) ——

    def us_ferc_elibrary(self, text=None, docket=None, *, date_type=None, date_from=None,
                         date_to=None, page=1, limit=20, execution=None, no_cache=None):
        """legal us_ferc_elibrary: FERC eLibrary document search (elibrary.ferc.gov, keyless;
        the 4.7M-document 1980→ corpus — dockets, orders, comments, transmittals over the whole
        FERC-regulated energy lifecycle). All filters combinable (docket + text + one date
        facet); no filter = the upstream's own "*" wildcard, newest first. Cloudflare
        UA-fingerprint gate = the full browser header suite (the afdb ext-8 family). Rows pass
        through verbatim minus the internal reference pair-key — acesssionNumber keeps the
        upstream's own triple-s and is the official key (the PDF rides the download endpoint)."""
        self._lg_only("us_ferc_elibrary")
        r = legal.us_ferc.elibrary_raw(text, docket, date_type=date_type, date_from=date_from,
                                       date_to=date_to, page=page, limit=limit,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        flt = (f" (docket {result['params']['docketSearches'][0]['docketNumber']})"
               if result["params"]["docketSearches"] else "") + \
              (f" · date facet {result['params']['dateSearches'][0]['dateType']}"
               f" {result['params']['dateSearches'][0]['startDate']}→{result['params']['dateSearches'][0]['endDate']}"
               if result["params"]["dateSearches"] else "")
        if result["rows"]:
            reason = (f"FERC eLibrary: {result['total']:,} documents match{flt} — page "
                      f"{result['page']} × {result['page_size']} ({result['count']} rows); the corpus "
                      f"spans 1980→today over pipeline certificates, hydro licenses, tariffs and "
                      f"rate cases; docketNumbers list + the three date faces ride every row")
        else:
            reason = (f"FERC eLibrary: zero documents on page {result['page']}{flt} (total "
                      f"{result['total']:,}) — a legitimate empty page; iterate inside "
                      f"ceil(total/{result['page_size']})")
        return self._flat_env(
            tool="us_ferc_elibrary",
            input={"text": text, "docket": docket, "date_type": date_type,
                   "date_from": date_from, "date_to": date_to,
                   "page": result["page"], "limit": result["page_size"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"[{x.get('acesssionNumber')}] {str(x.get('description') or x.get('category'))[:110]}"
                                + (f" · filed {x['filedDate']}" if x.get("filedDate") else ""),
                       "url": "https://elibrary.ferc.gov/eLibraryWebAPI/"}
                      for x in result["rows"][:5]],
            provider_id="us_ferc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.59 enforcement/party-finance cluster: ch_efk_party_financings (dictionary slot: ca-cluster letters put
    # ch < ie — slotted ahead of ie_sipo to keep the party-money cluster contiguous:
    # SIPO lobbying → EFK party financing → EE ERJK quarterly reports) ——
    def ch_efk_party_financings(self, lang="de", *, year=None, actor=None,
                                execution=None, no_cache=None):
        """legal ch_efk_party_financings: Swiss EFK political party financing disclosure tree
        (politikfinanzierung.efk.admin.ch frontend API; 3 year-roots × 10 parties × disclosure
        forms live; rows are flattened form cards with the campaign download URL)."""
        self._lg_only("ch_efk_party_financings")
        r = legal.ch_efk.tree_raw(lang, year=year, actor=actor,
                                  cache=self._c._cache,
                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="ch_efk_party_financings",
            input={"lang": result["params"]["lang"], "year": result["params"]["year"],
                   "actor": result["params"]["actor"]},
            reason=(f"EFK party financing ({result['params']['lang']}): {len(rows)} disclosure form cards"
                    + (f", year {year}" if year else ", all years on the tree")
                    + (f", actor contains \"{actor}\"" if actor else "")
                    + (f", top {top['actor'] or '—'} · {top['form'] or '—'} ({top['year']})" if top
                       else " — zero rows (the year filter is the label, e.g. '2025'; the actor filter is a substring)")
                    + " — download_url keys the campaign PDF (annual income disclosure / grants over CHF 15,000)"),
            result=result,
            evidence=[{"quote": f"{x['year']} · {x['actor']} · {x['form']}",
                       "url": x["download_url"] or "https://politikfinanzierung.efk.admin.ch/"}
                      for x in rows[:5]],
            provider_id="ch_efk", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def ie_sipo_lobbying(self, query_text=None, client=None, dpo=None, public_bodys=None,
                         period=None, return_date_from=None, return_date_to=None, page=1,
                         limit=20, execution=None, no_cache=None):
        """legal ie_sipo_lobbying: Irish SIPO Regulation of Lobbying register search
        (api.lobbying.ie, keyless; 123,591 returns live 2026-11-09). Each row is one lobbying
        return embedding the three parties verbatim — Lobbyist (carrying CompanyRegistrationNumber,
        the CRO key, on 43.6% of registrants) × Clients (carrying Cro) × Dpos. The 13-param wall:
        every parameter rides every call with explicit empties (a missing one is answered 404 —
        the face assembles the full set). Dates are DD-MM-YYYY, the register form's own shape
        (ISO is answered HTTP 500; the wall is local)."""
        self._lg_only("ie_sipo_lobbying")
        r = legal.ie_sipo.lobbying_raw(query_text, client=client, dpo=dpo, public_bodys=public_bodys,
                                       period=period, return_date_from=return_date_from,
                                       return_date_to=return_date_to, page=page, limit=limit,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        active = [k for k, v in result["params"].items() if v]
        if result["rows"]:
            reason = (f"SIPO lobbying register: {result['total']:,} returns"
                      + (f" — filtered: {', '.join(active)}" if active else "")
                      + f" — page {result['page']} × {result['page_size']} ({result['count']} rows); each "
                        f"row carries the three-party shape (Lobbyist CRN × Clients Cro × Dpos) — the "
                        f"register's own join keys, verbatim")
        else:
            reason = (f"SIPO lobbying register: zero returns on page {result['page']}"
                      + (f" — filtered: {', '.join(active)}" if active else "")
                      + " — either a legitimate empty filter or a page past the end; iterate inside "
                        f"ceil(total/{result['page_size']})")
        return self._flat_env(
            tool="ie_sipo_lobbying",
            input={"query_text": query_text, "client": client, "dpo": dpo,
                   "public_bodys": public_bodys, "period": period,
                   "return_date_from": return_date_from, "return_date_to": return_date_to,
                   "page": result["page"], "limit": result["page_size"]},
            reason=reason,
            result=result,
            evidence=[{"quote": (f"{(x.get('Lobbyist') or {}).get('Name') or '—'}"
                                 + (f" [CRN {(x.get('Lobbyist') or {}).get('CompanyRegistrationNumber')}]"
                                    if (x.get("Lobbyist") or {}).get("CompanyRegistrationNumber") else "")
                                 + f" · {x.get('PeriodName') or x.get('Period') or '—'}"
                                 + f" · {str(x.get('SubjectMatterText') or x.get('SubjectMatterName'))[:80]}"
                                 + (" · nil return" if x.get("NilReturn") else "")),
                       "url": x.get("FormattedUrl") or "https://www.lobbying.ie/"}
                      for x in result["rows"][:5]],
            provider_id="ie_sipo", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def ee_erjk_quarterly_reports(self, party_id=None, period=None, limit=100,
                                  execution=None, no_cache=None):
        """legal ee_erjk_quarterly_reports: Estonian party-finance receipts matrix
        (erjk.ee/avaandmet, keyless; the SDK's first EE jurisdiction). One shot = the whole
        party × period × donation-category aggregate matrix (455 rows 2013→2026 live
        2026-11-09); party_id narrows to one party (163 Keskerakond / 158 Reformierakond),
        period to one year. Party donations are natural-persons-only by Estonian law — the
        corporate edge lives in the election face (ee_erjk_election_reports)."""
        self._lg_only("ee_erjk_quarterly_reports")
        r = legal.ee_erjk.quarterly_reports_raw(party_id, period=period, limit=limit,
                                                cache=self._c._cache,
                                                no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        scope = (f"party {result['party_id']}" if str(result["party_id"]) != "all" else "all parties") + \
                (f", period {result['period']}" if str(result["period"]) != "show_all" else ", full history")
        if result["rows"]:
            tail = ", ".join(f"{x['party_name']} {x['period']} {x['category_name']} "
                             + (f"€{x['amount']:,.0f}" if x["amount"] is not None else "€—")
                             for x in result["rows"][:3])
            reason = (f"ERJK party-finance matrix: {result['total']} aggregate rows for {scope} — "
                      f"e.g. {tail}; each row is the upstream's own party × period × category "
                      f"aggregate (Rahaline annetus = cash donation, membership fees, events…)")
        else:
            reason = (f"ERJK party-finance matrix: zero rows for {scope} — either a party/year with "
                      f"no filed receipts or a filter combination outside the register's history")
        return self._flat_env(
            tool="ee_erjk_quarterly_reports",
            input={"party_id": party_id, "period": period, "limit": limit},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x['party_name']} · {x['period']} · {x['category_name']} · "
                                + (f"€{x['amount']:,.2f}" if x["amount"] is not None else "€—"),
                       "url": "https://erjk.ee/et/avaandmetest"}
                      for x in result["rows"][:5]],
            provider_id="ee_erjk", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def ee_erjk_election_reports(self, event_id=None, organisation_id=None, report_id=None,
                                 limit=500, execution=None, no_cache=None):
        """legal ee_erjk_election_reports: Estonian election/candidate receipts report — the
        register's company-hard-key layer (erjk.ee, keyless). Two entry forms: report_id
        directly, or event_id + organisation_id (resolves the organisation's report slots and
        takes the main report Põhiaruanne; every slot rides available_reports). Rows flatten
        {person: [entries]}: person + birthdate (the register's own key form, verbatim) +
        payer + **reg_code — a direct RIK äriregister registry code when the payer is a legal
        person** (the corporate-money edge; party donations are natural-persons-only by law,
        so this is where company money enters Estonian politics)."""
        self._lg_only("ee_erjk_election_reports")
        r = legal.ee_erjk.election_reports_raw(event_id, organisation_id, report_id=report_id,
                                               limit=limit, cache=self._c._cache,
                                               no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        with_reg = sum(1 for x in result["rows"] if x.get("reg_code"))
        if result["rows"]:
            reason = (f"ERJK election report {result['report_id']}"
                      + (f" ({result['report_title']})" if result.get("report_title") else "")
                      + f": {result['total']} receipt entries, {with_reg} carrying a payer reg_code "
                        f"(the RIK company edge)"
                      + (f"; slots available: "
                         + ", ".join(f"{s['report_id']}={s['report_title']}"
                                     for s in result["available_reports"])
                         if result.get("available_reports") else ""))
        else:
            reason = (f"ERJK election report {result['report_id']}: zero receipt entries — a filed "
                      f"report with nothing above the disclosure threshold (a legitimate answer)")
        return self._flat_env(
            tool="ee_erjk_election_reports",
            input={"event_id": event_id, "organisation_id": organisation_id,
                   "report_id": result["report_id"], "limit": limit},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x['person'] or '—'} · {x['payer'] or x['receipt_group'] or '—'}"
                                + (f" [reg {x['reg_code']}]" if x["reg_code"] else "")
                                + (f" · €{x['amount']}" if x["amount"] is not None else ""),
                       "url": "https://erjk.ee/et/avaandmetest"}
                      for x in result["rows"][:5]],
            provider_id="ee_erjk", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.57 ES BOE daily gazette table of contents (dictionary slot: es_boe_sumario between
    # ee_erjk_election_reports and federalregister_documents; legal's first BOE face — the company
    # domain's es_borme rides the same host for the mercantile gazette) ——

    def es_boe_sumario(self, date, *, section=None, limit=20, execution=None, no_cache=None):
        """legal es_boe_sumario: one publication day's full BOE table of contents
        (www.boe.es/datosabiertos/api/boe/sumario/{YYYYMMDD}; keyless — the JSON channel
        rides content negotiation, Accept: application/json, which the SDK sends by
        default; a bare no-Accept request answers 400 XML). Every container level
        (seccion → departamento → item) arrives dict-OR-list upstream — the
        singleton-collapse family — and items nest in FOUR measured shapes
        (departamento.item, epigrafe[].item, texto.item, texto.epigrafe[].item — the
        Constitutional-Court T section nests deepest), all collected with a
        seccion/departamento/epigrafe breadcrumb; a depth-blind recursive census rides
        alongside so a drifted shape shows as a gap instead of vanishing rows.

        The row keeps the BOE's own keys verbatim: identificador (BOE-A-…, THE key),
        control (the ministry docket), titulo, url_xml/url_html (item full text is a
        SECOND surface — the item-level xml.php serves XML whatever the Accept header,
        out of scope by the kr_law ruling), url_pdf{bytes, paginas}. No-publication days
        (Saturday measured) answer 404 and surface as published=false, never an error; a
        future date is refused locally; the archive reaches back to the 1960s (1965-01-05
        answers a full day)."""
        self._lg_only("es_boe_sumario")
        r = legal.es_boe.sumario_raw(date, section=section, limit=limit,
                                     cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: v for k, v in r.items() if k != "_meta"}
        p = r["params"]
        cen = r["census"]
        if not r["published"]:
            reason = (f"BOE sumario {r['date']}: no issue published — the upstream answers 404 "
                      "(weekend / gazette holiday, or the day's issue is not out yet; BOE "
                      "publishes early morning CET). A legitimate no-publication day, "
                      "structured as such, never an error")
        else:
            drift = ("; ROW SHAPE DRIFT: breadcrumb-parsed items != depth-blind walked items — "
                     "a nesting shape drifted upstream, inspect before trusting the day"
                     if cen["items"] != cen["walked_items"] else "")
            sec_tail = (f", filtered to section {p['section']} ({r['total_matched']} of "
                        f"{r['scanned_rows']} items)" if p["section"] else "")
            # 3.10 floor: an f-string inside an f-string replacement field cannot reuse
            # either quote (outer `"` is the delimiter, the join arg already spends `'`),
            # so the pairs join is hoisted out instead of nested (PEP 701 is 3.12+ only)
            sec_pairs = ", ".join(f"{s['codigo']}={s['items']}" for s in r["sections"])
            reason = (f"BOE sumario {r['date']} ({r['identificador']}, boletín Núm. "
                      f"{r['boletin_number']}): {cen['items']} items across {cen['sections']} "
                      f"sections ({sec_pairs})"
                      + sec_tail + drift
                      + "; identificador is THE key (BOE-A-YYYY-NNNNN chains into the item's "
                        "url_xml/url_html twins — item full text is XML-only upstream, out of "
                        "this face's scope)")
        return self._flat_env(
            tool="es_boe_sumario",
            input={"date": r["date"], "section": p["section"], "limit": r["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x['id']} · sec {x['seccion']} · {x['departamento']}"
                                + (f" · {x['epigrafe']}" if x["epigrafe"] else "")
                                + f" · {x['titulo'][:110]}",
                       "url": x["url_html"] or x["url_xml"]}
                      for x in r["rows"][:5]],
            provider_id="es_boe", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"path": "/datosabiertos/api/boe/sumario/{ymd}",
                                "ymd": r["date"].replace("-", ""),
                                "local_scan": {"section": p["section"]}}},
        )

    # —— 0.3.59 enforcement/party-finance cluster: lv_knab parties/payments pair (dictionary slot: es_boe < lv_knab
    # < ua_nazk — the party-finance family's 18th pillar: LV party register + the
    # transaction-level named-donation ledger, daily-rolled, personCode state-masked) ——
    def lv_knab_parties(self, limit=100, page=1, execution=None, no_cache=None):
        """legal lv_knab_parties: Latvia KNAB political-party register (info.knab.gov.lv /api/parties,
        keyless; 112 parties live; registrationNumber = the LV registry code, the hard join key
        onto company registers). No server-side term filter (the SPA searches client-side) —
        enumerate and filter locally; limit echoed verbatim upstream (no clamp)."""
        self._lg_only("lv_knab_parties")
        r = legal.lv_knab.parties_raw(limit, page, cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        return self._flat_env(
            tool="lv_knab_parties",
            input={"limit": result["params"]["limit"], "page": result["params"]["page"]},
            reason=(f"KNAB party register: {result['total']} parties live"
                    + f" — page {result['params']['page']} × {result['params']['limit']}"
                    + (f" ({len(rows)} rows)" if rows else " — page past the end of 112")
                    + " — registration_number is the LV company-registry code; founded_raw keeps the DD.MM.YYYY upstream contract"),
            result=result,
            evidence=[{"quote": f"{x['name']} · reg {x['registration_number'] or '—'}"
                                + f" · founded {x['founded'] or x['founded_raw'] or '—'}"
                                + (" · LIQUIDATED" if x.get("liquidated") else ""),
                       "url": "https://info.knab.gov.lv/"} for x in rows[:5]],
            provider_id="lv_knab", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def lv_knab_payments(self, limit=100, page=1, *, party_public_id=None,
                         execution=None, no_cache=None):
        """legal lv_knab_payments: Latvia KNAB donation ledger, transaction level
        (info.knab.gov.lv /api/payments, keyless; 78,081 rows live, rolled daily to yesterday;
        named donors by law — firstName/lastName/person are published, personCode is the
        state-masked form passed through verbatim; negative amountDisplay = expenditure
        direction). party_public_id (from lv_knab_parties rows) filters server-side."""
        self._lg_only("lv_knab_payments")
        r = legal.lv_knab.payments_raw(limit, page, party_public_id=party_public_id,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        tot = result.get("totals") or {}
        return self._flat_env(
            tool="lv_knab_payments",
            input={"limit": result["params"]["limit"], "page": result["params"]["page"],
                   "party_public_id": result["params"]["party_public_id"]},
            reason=(f"KNAB donation ledger: {result['total']} payments"
                    + (" (server-side party filter)" if party_public_id else "")
                    + f" — page {result['params']['page']} × {result['params']['limit']}"
                    + (f", top {top.get('donor') or '—'} → {top.get('party') or '—'}"
                       f" {top.get('amount_display') or '—'} {top.get('currency') or ''} on {top.get('date') or '—'}" if top
                       else " — zero rows (a page past the end, or a party with no recorded transactions)")
                    + (f" — corpus totals: EUR {tot.get('total', {}).get('EUR', '—')}"
                       if isinstance(tot.get("total"), dict) else "")
                    + " — donors are named by statute; personCode arrives state-masked and stays masked"),
            result=result,
            evidence=[{"quote": f"{x['date'] or x['date_raw'] or '—'} · {x['donor'] or '—'}"
                                + (f" ({x['donor_code_masked']})" if x.get("donor_code_masked") else "")
                                + f" → {x['party'] or '—'} · {x['amount_display'] or '—'} {x['currency'] or ''}"
                                + f" · {x['type'] or '—'}",
                       "url": "https://info.knab.gov.lv/"} for x in rows[:5]],
            provider_id="lv_knab", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def ua_nazk_parties(self, page=1, limit=20, execution=None, no_cache=None):
        """legal ua_nazk_parties: Ukrainian political-party register (politdata.nazk.gov.ua
        /api/v2, keyless all-POST; the SDK's first UA jurisdiction). 321 registered parties
        (count echo, live 2026-11-09) with the register's own keys: code (registration
        number), head_info (named leadership), register_address, contacts; id = the party uuid
        that keys the reports face. pageSize is server-clamped (send 10, 20 return) — the face
        asks verbatim and reports the clamped reality via count."""
        self._lg_only("ua_nazk_parties")
        r = legal.ua_nazk.parties_raw(page=page, limit=limit, cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["rows"]:
            reason = (f"NAZK party register: {result['total']} parties — page {result['page']} "
                      f"(asked {result['page_size']}, got {result['count']} — the upstream clamps "
                      f"pageSize to its own preference); rows carry code (registration number), "
                      f"head_info and the party uuid that keys ua_nazk_party_reports")
        else:
            reason = (f"NAZK party register: zero parties on page {result['page']} — past the end; "
                      f"iterate inside ceil({result['total']}/{result['count'] or result['page_size']})")
        return self._flat_env(
            tool="ua_nazk_parties",
            input={"page": result["page"], "limit": result["page_size"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x.get('code') or '—'} · {str(x.get('name'))[:70]}"
                                + (f" · head {x['head_info'].get('head_last_name')} "
                                   f"{x['head_info'].get('head_first_name')}" if x.get("head_info") else "")
                                + ("" if x.get("is_active") else " · INACTIVE"),
                       "url": "https://politdata.nazk.gov.ua/"}
                      for x in result["rows"][:5]],
            provider_id="ua_nazk", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def ua_nazk_party_reports(self, party_id, page=1, limit=20, execution=None, no_cache=None):
        """legal ua_nazk_party_reports: one Ukrainian party's report inventory
        (politdata.nazk.gov.ua, keyless all-POST; 2021→2026Q3). Rows verbatim with the embedded
        public_summary — the aggregated receipts/expenses per category (sums + row_counts) the
        upstream computed, zero extra calls; id = the report uuid that keys the follow-up
        payment faces (monetary_contributions carries payer_name/payer_type; payer_code is
        masked upstream). Regional-office reports sit in the same inventory
        (is_party_office=true)."""
        self._lg_only("ua_nazk_party_reports")
        r = legal.ua_nazk.party_reports_raw(party_id, page=page, limit=limit,
                                            cache=self._c._cache,
                                            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["rows"]:
            reason = (f"NAZK party reports for {result['party_id'][:8]}…: {result['total']} reports — "
                      f"page {result['page']} (asked {result['page_size']}, got {result['count']}); each "
                      f"row embeds public_summary (aggregated receipts/expenses — the zero-call money "
                      f"view) and the report uuid for the payment-detail faces")
        else:
            reason = (f"NAZK party reports for {result['party_id'][:8]}…: zero reports on page "
                      f"{result['page']} — a wrong party uuid (take id from ua_nazk_parties) or a page "
                      f"past the end")
        return self._flat_env(
            tool="ua_nazk_party_reports",
            input={"party_id": result["party_id"], "page": result["page"],
                   "limit": result["page_size"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x.get('report_type') or '—'} {x.get('year')} Q{x.get('quarter')}"
                                + (" · party office" if x.get("is_party_office") else "")
                                + f" · {str(x.get('id'))[:8]}…",
                       "url": "https://politdata.nazk.gov.ua/"}
                      for x in result["rows"][:5]],
            provider_id="ua_nazk", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.51 enforcement tier-two (fr_adlc / it_arera / us_cftc — one face per source) ——

    def fr_adlc_sanctions(self, entreprise=None, id_decision=None, year=None, *,
                          limit=20, execution=None, no_cache=None):
        """legal fr_adlc_sanctions: French Autorité de la concurrence company-level fine
        register (data.gouv.fr official mirror, keyless; the authority's own domain
        egress-blocks this exit — the mirror is the same publication). The whole 2009→
        ledger rides one GET (1,208-row 2026-11-08 build live): id_decision (the case key —
        a case's per-company Montant individuel rows sum into its repeated Montant total),
        entreprise, amounts (decimal strings cast to float), year. Filters are local and
        combinable; the stamped CSV resource URL rolls on every monthly build, so the face
        resolves the latest resource through the datasets API at call time (dataset op TTL
        1h, CSV TTL 24h) and never hardcodes the path."""
        self._lg_only("fr_adlc_sanctions")
        r = legal.fr_adlc.sanctions_raw(entreprise, id_decision, year, limit=limit,
                                        cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        flt = ", ".join(f"{k}={v}" for k, v in
                        (("entreprise", result["params"]["entreprise"]),
                         ("id_decision", result["params"]["id_decision"]),
                         ("year", result["params"]["year"])) if v)
        ds = result["dataset"]
        if result["rows"]:
            reason = (f"ADLC sanctions ledger: {result['total']:,} company-level fine rows match"
                      + (f" ({flt})" if flt else " (unfiltered — the whole build)")
                      + f" — showing {result['count']} (limit {result['limit_applied']}); build "
                        f"{ds['rows_in_build']:,} rows, dataset updated {str(ds['last_update'])[:10]}; "
                        f"montant_total repeats a case-level figure that does NOT always equal the "
                        f"row sum (26-D-05: 12.67M published vs 15.26M row sum) — both are official "
                        f"figures, ship verbatim, never recompute one from the other")
        else:
            reason = (f"ADLC sanctions ledger: zero rows"
                      + (f" for {flt}" if flt else "")
                      + f" — a legitimate empty filter (the build carries {ds['rows_in_build']:,} rows "
                        f"2009→; company names are the register's own spellings, try a shorter stem)")
        return self._flat_env(
            tool="fr_adlc_sanctions",
            input={"entreprise": entreprise, "id_decision": id_decision, "year": year,
                   "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"[{x['id_decision']}] {x['entreprise']}"
                                + (f" — €{x['montant_individuel']:,.0f}" if x["montant_individuel"] is not None else "")
                                + (f" (case total €{x['montant_total']:,.0f})" if x["montant_total"] is not None else "")
                                + (f", {int(x['annee'])}" if x["annee"] is not None else ""),
                       "url": f"https://www.data.gouv.fr/datasets/{legal.fr_adlc.DATASET_SLUG}"}
                      for x in result["rows"][:5]],
            provider_id="fr_adlc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.59 enforcement/party-finance cluster: fr_amf sanction/transaction pair + in_indiacode_search
    # (dictionary slots: fr_adlc < fr_amf < in_indiacode < it_arera — the AMF REST double
    # face is single-shot full-JSON, no pagination upstream; India Code is the DSpace 7
    # discovery API over the Central+State act repository) ——
    def fr_amf_sanction(self, theme=None, *, date_from=None, date_to=None,
                        execution=None, no_cache=None):
        """legal fr_amf_sanction: AMF (FR markets authority) disciplinary sanctions
        (www.amf-france.org/fr/rest/listing_sanction, keyless single-shot; 454 rows live;
        per decision the parties (text_egard split), the amount/penalty text, the appeal flag
        (recours oui/non) and the decision-PDF direct link — amount/party/PDF coverage
        454/454). theme = taxonomy tid or the exact French theme name (the 12-value measured
        map resolves locally); date window = ISO YYYY-MM-DD pair (unix upstream)."""
        self._lg_only("fr_amf_sanction")
        r = legal.fr_amf.sanctions_raw(theme, date_from=date_from, date_to=date_to,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="fr_amf_sanction",
            input={"theme": result["theme"], "date_from": date_from, "date_to": date_to},
            reason=(f"AMF sanctions: {result['total']} decisions"
                    + (f" (theme tid {result['theme']})" if result["theme"] else "")
                    + ((f", {date_from} → {date_to}" if date_from or date_to else ""))
                    + (f", top {top['id'] or '—'} decided {top['decision_date'] or '—'}"
                       f" — {len(top.get('parties') or [])} parties, appealed: {top.get('appealed')}" if top
                       else " — zero rows (an empty window is a legal answer; the full stream is 454)")
                    + " — upstream returns the whole matching set in one shot (no pagination)"),
            result=result,
            evidence=[{"quote": f"{x['id']} · {x['decision_date']} · {x['theme'] or '—'}"
                                + (f" · {x['amount_text']}" if x.get("amount_text") else "")
                                + (" · appealed" if x.get("appealed") else ""),
                       "url": x["source_url"] or "https://www.amf-france.org/fr/sanctions-transactions"}
                      for x in rows[:5]],
            provider_id="fr_amf", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def fr_amf_transaction(self, theme=None, *, date_from=None, date_to=None,
                           execution=None, no_cache=None):
        """legal fr_amf_transaction: AMF homologated settlement transactions
        (…/fr/rest/listing_transaction, keyless single-shot; 138 rows live — richer than the
        sitemap's 121; per transaction the actor, the amount text and total (numeric),
        the decision-PDF link). Same theme/date contract as fr_amf_sanction."""
        self._lg_only("fr_amf_transaction")
        r = legal.fr_amf.transactions_raw(theme, date_from=date_from, date_to=date_to,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="fr_amf_transaction",
            input={"theme": result["theme"], "date_from": date_from, "date_to": date_to},
            reason=(f"AMF transactions: {result['total']} homologated settlements"
                    + (f" (theme tid {result['theme']})" if result["theme"] else "")
                    + ((f", {date_from} → {date_to}" if date_from or date_to else ""))
                    + (f", top {top['id'] or '—'} decided {top['decision_date'] or '—'}"
                       f" — {top.get('actor') or '—'}"
                       + (f", €{top['amount_numeric']:,.0f}" if top.get("amount_numeric") else "") if top
                       else " — zero rows (an empty window is a legal answer; the full stream is 138)")
                    + " — total is the upstream numeric amount (134/137 cards carry it)"),
            result=result,
            evidence=[{"quote": f"{x['id']} · {x['decision_date']} · {x['actor'] or '—'}"
                                + (f" · {x['amount_text']}" if x.get("amount_text") else ""),
                       "url": x["source_url"] or "https://www.amf-france.org/fr/sanctions-transactions"}
                      for x in rows[:5]],
            provider_id="fr_amf", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def in_indiacode_search(self, q, *, limit=20, page=0, execution=None, no_cache=None):
        """legal in_indiacode_search: India Code act repository search (indiacode.gov.in DSpace 7
        REST discovery, keyless; 'companies act' → 13,530 items live; per act the catalogue
        metadata — act_id/act_number/act_year/enact_date/state/chapters/sections/repealed —
        verbatim from the dc.* keys, hitHighlights carry the match snippets). page 0-based,
        limit = size (upstream honors 100); full document keys via uuid + bundles_url."""
        self._lg_only("in_indiacode_search")
        r = legal.in_indiacode.search_raw(q, limit=limit, page=page,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="in_indiacode_search",
            input={"q": result["params"]["q"], "limit": result["params"]["limit"],
                   "page": result["params"]["page"]},
            reason=(f"India Code: {result['total']} items across {result['total_pages']} pages"
                    + f" for \"{result['params']['q']}\""
                    + f" — returning {len(rows)} rows at page {page}"
                    + (f", top {top.get('title') or top.get('name') or '—'}"
                       + (f" (act no. {top['act_number']}, {top.get('act_year') or '—'}"
                          + (f", {top['state']}" if top.get("state") else "") + ")" if top.get("act_number") else "") if top
                       else " — zero hits (an empty result is a legal answer; the repository matches by contains)")
                    + " — repealed/repealed-year and chapter/section counts ride the metadata"),
            result=result,
            evidence=[{"quote": f"{x.get('title') or x.get('name') or '—'}"
                                + (f" · no. {x['act_number']}" if x.get("act_number") else "")
                                + (f" · {x.get('act_year') or x.get('enact_date') or '—'}" if x.get("act_year") or x.get("enact_date") else "")
                                + (" · REPEALED" if str(x.get("repealed") or "").lower() in ("yes", "true", "1") else ""),
                       "url": x.get("uri") or x.get("self_url") or "https://indiacode.gov.in/"}
                      for x in rows[:5]],
            provider_id="in_indiacode", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def it_arera_decisions(self, anno=None, numero=None, tipologia=None, settore=None,
                           *, page=1, execution=None, no_cache=None):
        """legal it_arera_decisions: Italian ARERA regulated-sector decision register
        (www.arera.it atti e provvedimenti, keyless; the energy/gas/water/waste/district-
        heating regulator's TYPO3 library, 1,560 pages × 15,599 documents live 2026-11-09).
        All filters optional and combinable (anno + numero + tipologia + settore); the
        single-document form is deterministic (anno=2022 & numero=312 & tipologia=Delibera
        answers exactly one card). tipologia is the register's own nine-word vocabulary
        (exact match, walled), anno spans 1996→current (the dropdown's own floor). Rows are
        the list cards: sigla (the register's hard key "NNN/YYYY/SETTORE"), detail anchor
        (the PDF paths live on the detail page — fileadmin naming drifts by era and is never
        assembled from the sigla), date DD/MM/YYYY verbatim, oggetto (entity-unescaped)."""
        self._lg_only("it_arera_decisions")
        r = legal.it_arera.list_raw(anno, numero, tipologia, settore, page=page,
                                    cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        flt = ", ".join(f"{k}={v}" for k, v in
                        (("anno", result["params"].get("anno")),
                         ("numero", result["params"].get("numero")),
                         ("tipologia", result["params"].get("tipologia")),
                         ("settore", result["params"].get("settore"))) if v)
        if result["rows"]:
            reason = (f"ARERA decision register: {result['total_results']:,} documents match"
                      + (f" ({flt})" if flt else " (unfiltered — the register's own newest-first listing)")
                      + f" — page {result['page']} of {result['total_pages']:,} ({result['count']} rows); "
                        f"sigla is the hard key, the detail anchor carries the real PDF paths")
        else:
            reason = (f"ARERA decision register: zero documents on page {result['page']}"
                      + (f" for {flt}" if flt else "")
                      + " — either a legitimate empty filter (numero alone is ambiguous across years — "
                        "pair it with anno) or a page past the end")
        return self._flat_env(
            tool="it_arera_decisions",
            input={"anno": anno, "numero": numero, "tipologia": tipologia,
                   "settore": settore, "page": result["page"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x['sigla'] or '—'} · {x['tipologia'] or '—'}"
                                + (f" · {x['date']}" if x["date"] else "")
                                + f" — {str(x['oggetto'] or '—')[:100]}",
                       "url": "https://www.arera.it" + str(x["detail"] or "")}
                      for x in result["rows"][:5]],
            provider_id="it_arera", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.56 KR 국가법령정보센터 dual-pillar list search (law.go.kr form-POST; the booklet's
    # "session trio" disproven as requirement — a plain urlencoded POST answers the same
    # fragment, measured all three ways 2026-11-12) ——

    def kr_law_statutes(self, q="*", *, page=1, page_size=20, execution=None, no_cache=None):
        """legal kr_law_statutes: Korean statute list search (www.law.go.kr lsScListR, keyless;
        the KR statutes gap closed in one source with kr_law_precedents). q = 법령 name keyword,
        or "*" for full enumeration under the verified current-statutes filter combo
        (section=lawNm + p9='2,4' + p18='0' + p19='1,3'; ≈6-7k 現行 법령 — the full corpus incl.
        자치법규 is ~24k and rides its own filter set, not shipped). Rows carry the DOUBLE key
        (lsi_seq, effective_date) — the statute-version serial × effective date, both needed to
        address one version (the lsViewWideAll anchor's own two args); law_number (법률 제<N>호)
        parses from the title. efYd='99990101' is the 시행미정 (not-yet-in-force) sentinel —
        mapped to effective_date=None + pending=True, never a date. page_size 1-100 (outmax);
        the deep-page ceiling sits at pg≈300-350 × 20 under this filter."""
        self._lg_only("kr_law_statutes")
        r = legal.kr_law.statutes_raw(q, page=page, page_size=page_size,
                                      cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            top = rows[0]
            pend = sum(1 for x in rows if x["pending"])
            num = f"법률 제{top['law_number']}호" if top["law_number"] else "법률 호 미상"
            tot = ("total not echoed by the fragment" if result["total"] is None
                   else f"{result['total']:,} total under the current-statutes filter")
            reason = (f"law.go.kr statutes: {tot}, {len(rows)} rows from page "
                      f"{result['params']['page']}"
                      f" — sample [{top['lsi_seq']}] {(top['title'] or '—')[:60]}"
                      f" · effective {top['effective_date'] or '— (시행미정 pending)'}"
                      f" · {num}"
                      + (f" — {pend} pending rows on this page (the 99990101 sentinel)"
                         if pend else "")
                      + " — (lsi_seq, effective_date) is the compound key; the full text is a second surface")
        else:
            reason = ("law.go.kr statutes: zero rows — a page past the deep-page ceiling "
                      "(pg≈300-350 × 20 under this filter) or a keyword with no match")
        return self._flat_env(
            tool="kr_law_statutes",
            input={"q": result["params"]["q"], "page": result["params"]["page"],
                   "page_size": result["params"]["page_size"]},
            reason=reason, result=result,
            evidence=[{"quote": f"[{x['lsi_seq']}] {(x['title'] or '—')[:80]}"
                                + (f" · 시행 {x['effective_date']}" if x["effective_date"] else " · 시행미정")
                                + (f" · 법률 제{x['law_number']}호" if x["law_number"] else ""),
                       "url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=" + x["lsi_seq"]}
                      for x in rows[:5]],
            provider_id="kr_law", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def kr_law_precedents(self, q="*", *, page=1, page_size=20, execution=None, no_cache=None):
        """legal kr_law_precedents: Korean Supreme Court precedent list search (www.law.go.kr
        precScListR, keyless; q="*" ≈119,970 판례, bisected to certainty 2026-11-04 — the KR
        case-law gap closed in one source with kr_law_statutes). q = case-name keyword, or "*"
        for the full walk. Rows: prec_seq (the precView() numeric key into the full-text detail
        page — a second surface out of this face's scope), case_name, and the decision struct
        parsed from the title attr: court × decided ('2023. 7. 20.' verbatim) × case_number ×
        kind (판결|결정). page_size 1-100 (outmax), true pagination."""
        self._lg_only("kr_law_precedents")
        r = legal.kr_law.precedents_raw(q, page=page, page_size=page_size,
                                        cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            top = rows[0]
            dec = top.get("decision") or {}
            tot = ("total not echoed by the fragment" if result["total"] is None
                   else f"{result['total']:,} total")
            reason = (f"law.go.kr precedents: {tot}, {len(rows)} rows from page "
                      f"{result['params']['page']} — sample [{top['prec_seq']}] "
                      f"{(top['case_name'] or '—')[:60]}"
                      + (f" · {dec.get('court') or '—'} {dec.get('decided') or '—'} 선고 "
                         f"{dec.get('case_number') or '—'}" if dec else " · (title carries no 선고 meta)")
                      + " — prec_seq keys the full-text detail page (a second surface)")
        else:
            reason = ("law.go.kr precedents: zero rows — a page past the end "
                      "(≈119,970 precedents; at page_size 100 that is ~1,200 pages) or a "
                      "keyword with no match")
        return self._flat_env(
            tool="kr_law_precedents",
            input={"q": result["params"]["q"], "page": result["params"]["page"],
                   "page_size": result["params"]["page_size"]},
            reason=reason, result=result,
            evidence=[{"quote": f"[{x['prec_seq']}] {(x['case_name'] or '—')[:70]}"
                                + (f" · {x['decision']['court']} {x['decision']['decided']} 선고 "
                                   f"{x['decision']['case_number']} {x['decision']['kind']}"
                                   if x.get("decision") else ""),
                       "url": "https://www.law.go.kr/LSW/precInfoP.do?precSeq=" + x["prec_seq"]}
                      for x in rows[:5]],
            provider_id="kr_law", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- 0.3.64 batch E6 — CFTC register pair (dictionary slot: us_cftc_dispositions < us_cftc_enforcement < us_cftc_redlist) ----------

    def us_cftc_dispositions(self, *, page=0, execution=None, no_cache=None):
        """legal us_cftc_dispositions: the CFTC reparations-decisions register
        (www.cftc.gov Drupal views, keyless; complainant v. registrant captions —
        "David Kaminski v. TradeStation Securities, Inc."). 46 pages × 10 ≈456 rows,
        newest-first (2026-10-26 live top); each row's anchor IS the decision PDF
        (/sites/default/files/YYYY/MM/) and the docket number rides the blurb cell
        (CFTC Docket No. 25-R016). page is 0-based upstream verbatim."""
        self._lg_only("us_cftc_dispositions")
        r = legal.us_cftc.dispositions_raw(page=page, cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["rows"]:
            reason = (f"CFTC reparation decisions (page {result['page']}): {result['count']} rows — "
                      f"the register runs ~456 decisions over 46 pages (0..45), newest first; each "
                      f"row anchors its decision PDF and the docket number (e.g. 25-R016)")
        else:
            reason = (f"CFTC reparation decisions (page {result['page']}): zero rows — a page past "
                      f"the live end (0..45)")
        return self._flat_env(
            tool="us_cftc_dispositions",
            input={"page": result["page"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"[{x['docket_no'] or '—'}] {x['date']} — {x['title'][:100]}",
                       "url": "https://www.cftc.gov" + str(x["pdf_path"] or "")}
                      for x in result["rows"][:5]],
            provider_id="us_cftc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def us_cftc_enforcement(self, year=None, *, page=0, execution=None, no_cache=None):
        """legal us_cftc_enforcement: CFTC enforcement-actions index (www.cftc.gov Drupal
        views, keyless; the commission's full history 1995→2026, ≈2,610 actions over ~261
        pages of 10). Optional ?year= filter (the register's own dropdown 1995→current —
        1998 is absent from it, a historical broken year, walled as such); page is 0-based
        upstream verbatim, page 260 ends at the 1995 floor. Rows carry the press-release
        anchor (release_number is the anchor tail, e.g. 9320-26), the title (entity-
        unescaped, whitespace-normalized) and related_docs — the judgment/consent-order
        attachments under /media/ with their labels. Bare UA 403'd live 2026-11-09; the
        face ships the full browser header suite (the ferc/afdb ext-8 family)."""
        self._lg_only("us_cftc_enforcement")
        r = legal.us_cftc.actions_raw(year, page=page, cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        scope = (f"year {result['year']}" if result["year"] else "all years (newest first)") + \
                f", page {result['page']}"
        if result["rows"]:
            docs = sum(len(x["related_docs"]) for x in result["rows"])
            reason = (f"CFTC enforcement actions ({scope}): {result['count']} rows, {docs} attached "
                      f"judgment/order documents — the register runs 1995→today (~2,610 actions, "
                      f"~10/page, 0..260); release_number is the anchor tail and the press-release "
                      f"path keys the story behind each action")
        else:
            reason = (f"CFTC enforcement actions ({scope}): zero rows — either a page past the end "
                      f"(live range 0..260) or a year with no indexed actions; 1998 is a historical "
                      f"broken year the register's own filter never offered")
        return self._flat_env(
            tool="us_cftc_enforcement",
            input={"year": year, "page": result["page"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"[{x['release_number']}] {x['date']} — {x['title'][:110]}"
                                + (f" · {len(x['related_docs'])} docs" if x["related_docs"] else ""),
                       "url": "https://www.cftc.gov" + str(x["release_path"] or "")}
                      for x in result["rows"][:5]],
            provider_id="us_cftc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def us_cftc_opinions(self, *, page=0, execution=None, no_cache=None):
        """legal us_cftc_opinions: the CFTC OGC Opinions & Adjudicatory Orders register
        (www.cftc.gov Drupal views, keyless; reparations appeals and initial decisions,
        parties-first captions — "Eric Thompson, Jonathan Morse, … v. …"). ≈87 rows over
        9 pages (0..8) of 10, date-descending 2012→2025. DUAL-ERA PDF paths verbatim:
        recent rows /sites/default/files/YYYY/MM/, older rows the legacy /idc/groups/
        public/%40lropinionsandadjudicaryorders/ path (%40=@; "adjudicary" is the
        upstream's own misspelling). The docket number rides inline in the blurb
        ("CFTC Docket No. 23-R001"); rows without one report None. page is 0-based
        upstream verbatim."""
        self._lg_only("us_cftc_opinions")
        r = legal.us_cftc.opinions_raw(page=page, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["rows"]:
            reason = (f"CFTC opinions & adjudicatory orders (page {result['page']}): "
                      f"{result['count']} rows — ≈87 decisions over 9 pages (0..8), newest "
                      f"first (2012→2025); anchors are dual-era decision PDFs and the docket "
                      f"number rides inline in the caption")
        else:
            reason = (f"CFTC opinions & adjudicatory orders (page {result['page']}): zero rows "
                      f"— a page past the live end (0..8)")
        return self._flat_env(
            tool="us_cftc_opinions",
            input={"page": result["page"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"[{x['docket_no'] or '—'}] {x['date']} — {x['title'][:100]}",
                       "url": "https://www.cftc.gov" + str(x["pdf_path"] or "")}
                      for x in result["rows"][:5]],
            provider_id="us_cftc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def us_cftc_redlist(self, *, page=0, execution=None, no_cache=None):
        """legal us_cftc_redlist: the CFTC RED List — registration-deficiency register
        (www.cftc.gov Drupal views, keyless): unregistered FOREIGN entities the commission
        has charged or settled with (forex/derivatives solicitations). Complementary to
        OFAC CSL — a non-sanctions, unregistered-entity negative register. 29 pages × 10,
        last page 4 rows → 284 entities live; the register's own order is ALPHABETICAL by
        company (Date Entered scatters 2015→2023 within a page); each row anchors a Drupal
        node detail page (/REDlist/node/<id>, titled "RED List: <name>"). ?items_per_page
        is decorative (a widened ask answers zero rows — page size stays 10)."""
        self._lg_only("us_cftc_redlist")
        r = legal.us_cftc.redlist_raw(page=page, cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if result["rows"]:
            reason = (f"CFTC RED List (page {result['page']}): {result['count']} rows — 284 "
                      f"unregistered entities over 29 alphabetical pages (0..28); names anchor "
                      f"their /REDlist/node detail pages; dates are entry dates, scattered by "
                      f"name order (2015→2023)")
        else:
            reason = (f"CFTC RED List (page {result['page']}): zero rows — a page past the "
                      f"alphabetical end (0..28)")
        return self._flat_env(
            tool="us_cftc_redlist",
            input={"page": result["page"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x['name']} — entered {x['date']}",
                       "url": "https://www.cftc.gov" + str(x["node_path"] or "")}
                      for x in result["rows"][:5]],
            provider_id="us_cftc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ===================== 0.3.60 batch E2 — API-faces depth wave (AU/BR/CA/DE/DK/IT/PL/US) =====================
    # Naming per docs/domains/command-naming.md §1/§2/§4/§6/§7: every token points at an upstream path
    # resource segment, an upstream document/product name, or an upstream public object name; long
    # names are not truncated (§7).

    def au_frl_titles(self, collection=None, term=None, *, top=20, execution=None, no_cache=None):
        """legal au_frl_titles: Australian Federal Register of Legislation titles (the Office of
        Parliamentary Counsel's OData v1 service api.prod.legislation.gov.au/v1, keyless) — the
        Commonwealth Acts register (13,754 titles live, measured 2026-11-13) plus Notifiable
        Legislation and Compilations. term = the OData $search full-text query (a quoted phrase
        is honoured upstream); collection = the register's own collection (Act / Notifiable
        Legislation / Compilation); top = $top (1-1000).
        LIVE LAWS: the $-prefixed OData option names must NOT be percent-encoded (the gateway
        answers 400 on %24top) — they are baked into the op path; the bare host
        api.legislation.gov.au resets TLS, so the prod host is pinned.
        Rows: id (the canonical FRL title id, the join key), name, makingDate, collection,
        isInForce, status, year/number, nameHistory[] and statusHistory[] (with the amending or
        repealing titles named)."""
        self._lg_only("au_frl_titles")
        if term:
            r = legal.au_frl.search_raw(term, top=top, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        else:
            r = legal.au_frl.titles_raw(collection=collection, top=top, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        p = result["params"]
        if rows:
            top_row = rows[0]
            reason = (f"AU Federal Register of Legislation: {result['total'] or len(rows)} titles, "
                      f"{len(rows)} rows returned"
                      + (f" (collection {p.get('collection')})" if p.get("collection") else "")
                      + (f" (search \"{p.get('q')}\")" if p.get("q") else "")
                      + f" — sample [{top_row.get('id')}] {(top_row.get('name') or '—')[:70]}"
                      + f" · {top_row.get('status') or '—'}"
                      + (" · in force" if top_row.get("isInForce") else " · not in force")
                      + " — the title id is the canonical FRL key (legislation.gov.au/<id>)")
        else:
            # 3.10 floor: a backslash inside an f-string expression part is 3.12+ only —
            # hoisted, and quotes picked so no escape is needed anywhere
            q_disp = f'the search "{p.get("q")}"' if p.get("q") else "the requested collection"
            reason = ("AU Federal Register of Legislation: zero titles for "
                      f"{q_disp}"
                      " (an empty result is a legitimate answer)")
        return self._flat_env(
            tool="au_frl_titles",
            input={"collection": p.get("collection"), "term": p.get("q"), "top": p.get("top")},
            reason=reason, result=result,
            evidence=[{"quote": f"[{x.get('id')}] {(x.get('name') or '—')[:90]}"
                                + f" · {x.get('status') or '—'} · made {x.get('makingDate') or '—'}",
                       "url": f"https://www.legislation.gov.au/{x.get('id')}"}
                      for x in rows[:5]],
            provider_id="au_frl", metas=[r["_meta"]],
            query={"source": "raw", "upstream": p},
        )

    def br_cade_pesquisa_avancada(self, name=None, *, module="apac", protocol=None, limit=50,
                                   execution=None, no_cache=None):
        """legal br_cade_pesquisa_avancada: CADE case register — the council's own "Pesquisa
        Avançada" proxy (pesquisaavancada.cade.gov.br, keyless form POST; one POST per module:
        apac = Ato de Concentração, tcc = Requerimento de TCC, consulta = the general
        consultation surface). name = the party filter (upstream field txtInteressado, server-side
        — "JBS" → 2 rows); protocol = the process protocol number (txtProtocoloPesquisa).
        LIVE LAWS: every scalar in the answer is BASE64 and the decoded bytes are MIXED UTF-8 /
        cp1252 (the upstream encodes some columns as UTF-8, some as cp1252) — the decoder tries
        UTF-8 strict first and falls back to cp1252, keeping only printable results; the date
        fields (txtDataDecisaoDe / txtDataDecisaoAte) are DECORATIVE upstream (a fixed window is
        echoed back whatever is sent) so they are NOT sent as filters and no date filtering is
        claimed. Rows: id_procedimento, protocolo_formatado, tipo_processo, decisao1/decisao2,
        documentos[] and the linkProcessual token."""
        self._lg_only("br_cade_pesquisa_avancada")
        r = legal.br_cade.cases_raw(module=module, name=name, protocol=protocol, limit=limit,
                                    cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        p = result["params"]
        if rows:
            top_row = rows[0]
            reason = (f"CADE pesquisa avançada ({p.get('module')}): {result['total']} proceedings, "
                      f"{len(rows)} rows returned"
                      + (f" (party \"{name}\")" if name else "")
                      + (f" (protocol {protocol})" if protocol else "")
                      + f" — sample {top_row.get('protocolo_formatado') or '—'}"
                      + f" · {top_row.get('tipo_processo') or '—'}"
                      + (f" · {len(top_row.get('documentos') or [])} documents" if top_row.get("documentos") else "")
                      + " — the upstream's date fields are decorative, so no date filter is applied")
        else:
            reason = (f"CADE pesquisa avançada ({p.get('module')}): zero proceedings"
                      + (f" for party \"{name}\"" if name else "")
                      + " (an empty result is a legitimate answer — the party is not in this module)")
        return self._flat_env(
            tool="br_cade_pesquisa_avancada",
            input={"name": name, "module": p.get("module"), "protocol": protocol, "limit": p.get("limit")},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('protocolo_formatado') or '—'} · {x.get('tipo_processo') or '—'}"
                                + (f" · {x.get('decisao1')}" if x.get("decisao1") else ""),
                       "url": "https://pesquisaavancada.cade.gov.br/consulta"}
                      for x in rows[:5]],
            provider_id="br_cade", metas=[r["_meta"]],
            query={"source": "raw", "upstream": p},
        )

    def ca_cbsa_rulings(self, *, limit=50, offset=0, execution=None, no_cache=None):
        """legal ca_cbsa_rulings: CBSA national tariff-classification advance rulings (the CARM
        public-rulings list, ccp-pcc.cbsa-asfc.cloud-nuage.canada.ca, keyless) — 1,234 rulings
        live (measured 2026-11-13). LIVE LAW: the lang query parameter is MANDATORY (the service
        answers 400 without it) — it is baked into the op path (en). The list is the whole
        register; the face pages it locally.
        Rows: rulingsId (the join key into the detail face), classificationNumber, date, product
        and the ruling type."""
        self._lg_only("ca_cbsa_rulings")
        r = legal.ca_cbsa.rulings_raw(limit=limit, offset=offset, cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        p = result["params"]
        if rows:
            top_row = rows[0]
            reason = (f"CBSA national advance rulings: {result['total']} rulings in the register, "
                      f"{len(rows)} rows returned from offset {p.get('offset')} — sample "
                      f"[{top_row.get('rulings_id')}] HS {top_row.get('classification_number') or '—'}"
                      f" · {top_row.get('date') or '—'}"
                      + f" · {(top_row.get('product') or '—')[:60]}"
                      + " — the rulingsId is the key into the detail face")
        else:
            reason = (f"CBSA national advance rulings: zero rows from offset {p.get('offset')} "
                      "(an offset past the end of the 1,234-ruling register)")
        return self._flat_env(
            tool="ca_cbsa_rulings",
            input={"limit": p.get("limit"), "offset": p.get("offset")},
            reason=reason, result=result,
            evidence=[{"quote": f"[{x.get('rulings_id')}] HS {x.get('classification_number') or '—'}"
                                f" · {x.get('date') or '—'} · {(x.get('product') or '—')[:80]}",
                       "url": "https://ccp-pcc.cbsa-asfc.cloud-nuage.canada.ca/carmwebservices/v2/carm/publicrulings/list?lang=en"}
                      for x in rows[:5]],
            provider_id="ca_cbsa", metas=[r["_meta"]],
            query={"source": "raw", "upstream": p},
        )

    def ca_cbsa_ruling(self, rulings_id=None, *, execution=None, no_cache=None):
        """legal ca_cbsa_ruling: one CBSA national advance ruling (the CARM ruling-detail
        endpoint, keyless). rulings_id = the rulingsId from the list face (e.g. "8000001670").
        LIVE LAWS: lang=en is mandatory; the text fields carry "&&" as the line separator and
        HTML entities — the parser turns "&&" into newlines and unescapes them. The applicant
        block names the importer: the first line is the contact person, the second the company
        (the company join surface)."""
        self._lg_only("ca_cbsa_ruling")
        r = legal.ca_cbsa.ruling_raw(rulings_id, cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        reason = (f"CBSA advance ruling {result.get('rulings_id')}: HS "
                  f"{result.get('classification_number') or '—'} · {result.get('date') or '—'} — "
                  f"importer {result.get('applicant_company') or '—'}"
                  + (f" · {result.get('product') or ''}" if result.get("product") else "")
                  + " (the decision text and the CBSA analysis ride the detail fields)")
        return self._flat_env(
            tool="ca_cbsa_ruling",
            input={"rulings_id": result.get("params", {}).get("rulings_id")},
            reason=reason, result=result,
            evidence=[{"quote": (result.get("applicant") or "—").replace("\n", " / ")[:160],
                       "url": "https://ccp-pcc.cbsa-asfc.cloud-nuage.canada.ca/carmwebservices/v2/carm/publicrulings/rulingsdetails/"
                              + str(result.get("rulings_id") or "") + "?lang=en"}],
            provider_id="ca_cbsa", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def de_lobbyregister_entries(self, name=None, *, active=None, identity=None,
                                 codex_violations=None, legislation=None, limit=50, offset=0,
                                 execution=None, no_cache=None):
        """legal de_lobbyregister_entries: German Bundestag lobby register (Lobbyregister des
        Deutschen Bundestages, www.lobbyregister.bundestag.de — the keyless JSON export
        /sucheJson). 7,044 entries live (measured 2026-11-13); the official REST API (v1/v2) is
        ApiKey-gated, so it is NOT on the route (keyless-only ruling).
        LIVE LAW: the export carries NO server-side filter — the whole 18 MB register is read
        once (cached 24 h) and filtered locally.
        Rows: registerNumber, the identity (ORGANIZATION | PERSON), the active flag, the codex
        violations flag, the employee FTE and — the compliance-grade part — the money columns
        (financialExpensesEuro, totalDonationsEuro, totalMembershipFees) and the
        project/statement/contract counts."""
        self._lg_only("de_lobbyregister_entries")
        r = legal.de_lobbyregister.entries_raw(name=name, active=_flag(active), identity=identity,
                                               codex_violations=_flag(codex_violations),
                                               legislation=legislation, limit=limit, offset=offset,
                                               cache=self._c._cache,
                                               no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        p = result["params"]
        if rows:
            top_row = rows[0]
            reason = (f"Bundestag lobby register: {result['total']} entries match, {len(rows)} rows "
                      f"returned (the register itself holds {result.get('register_total')} entries) — "
                      f"sample {top_row.get('name') or '—'}"
                      + f" · {top_row.get('identity') or '—'}"
                      + (" · active" if top_row.get("active") else " · inactive")
                      + (f" · codex violations" if top_row.get("codex_violations") else "")
                      + f" · expenses €{top_row.get('financial_expenses_eur') or '—'}"
                      + " — the money columns and the project/statement/contract counts are the "
                        "lobbying-law disclosure")
        else:
            reason = ("Bundestag lobby register: zero entries match the filter "
                      "(an empty result is a legitimate answer)")
        return self._flat_env(
            tool="de_lobbyregister_entries",
            input={"name": name, "active": p.get("active"), "identity": p.get("identity"),
                   "codex_violations": p.get("codex_violations"), "legislation": p.get("legislation"),
                   "limit": p.get("limit"), "offset": p.get("offset")},
            reason=reason, result=result,
            evidence=[{"quote": f"[{x.get('register_number') or '—'}] {x.get('name') or '—'}"
                                + f" · {x.get('identity') or '—'}"
                                + (f" · expenses €{x.get('financial_expenses_eur')}" if x.get("financial_expenses_eur") else "")
                                + (f" · donations €{x.get('total_donations_eur')}" if x.get("total_donations_eur") else "")
                                + (f" · {x.get('regulatory_projects')} projects" if x.get("regulatory_projects") else ""),
                       "url": x.get("details_page_url") or "https://www.lobbyregister.bundestag.de"}
                      for x in rows[:5]],
            provider_id="de_lobbyregister", metas=[r["_meta"]],
            query={"source": "raw", "upstream": p},
        )

    def dk_ft_inspektionsredegoerelser_og_afgoerelser(self, q=None, *, year=None, page=1,
                                                       exact_match=None, execution=None,
                                                       no_cache=None):
        """legal dk_ft_inspektionsredegoerelser_og_afgoerelser: Danish Finanstilsynet supervision
        archive — inspection reports and supervisory decisions (www.finanstilsynet.dk, the gbapi
        search service, keyless). 4,038 items live (measured 2026-11-13: "Danske Bank" → 1,651,
        year 2025 → 214). q = the free-text query (server-side); year = the server-side year
        window; page = 1-based (10 items per page upstream); exact_match = the upstream's
        exactMatch flag.
        LIVE LAWS (measured 2026-11-13): the POST REQUIRES a Referer header (without it the API
        answers 400 "Incorrect request referer header") and the body is a NESTED object —
        userInput is an OBJECT {query, months, categorizations, additionalFilters, template}, not
        a plain string (a string userInput answers 400); the archive page's data-config attribute
        (HTML-escaped JSON) is the config the body must echo back verbatim.
        Rows: type (Redegørelse / Påbud / Påtale), title, url, date and the teaser."""
        self._lg_only("dk_ft_inspektionsredegoerelser_og_afgoerelser")
        r = legal.dk_ft.decisions_raw(q or "", year=year, page=page, exact_match=_flag(exact_match),
                                      cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        p = result["params"]
        if rows:
            top_row = rows[0]
            reason = (f"Finanstilsynet supervision archive: {result['total']} items"
                      + (f" for \"{p.get('q')}\"" if p.get("q") else "")
                      + (f" (year {p.get('year')})" if p.get("year") else "")
                      + f", {len(rows)} rows from page {p.get('page')} — sample "
                      f"{(top_row.get('type') or '—')} · {(top_row.get('title') or '—')[:70]}"
                      + f" · {top_row.get('date_display') or top_row.get('date') or '—'}"
                      + " — the archive mixes inspection reports (Redegørelse), injunctions (Påbud) "
                        "and reprimands (Påtale)")
        else:
            reason = (f"Finanstilsynet supervision archive: zero items"
                      + (f" for \"{p.get('q')}\"" if p.get("q") else "")
                      + (f" in {p.get('year')}" if p.get("year") else "")
                      + f" (page {p.get('page')} is past the end)")
        return self._flat_env(
            tool="dk_ft_inspektionsredegoerelser_og_afgoerelser",
            input={"q": p.get("q"), "year": p.get("year"), "page": p.get("page"),
                   "exact_match": p.get("exact_match")},
            reason=reason, result=result,
            evidence=[{"quote": f"{(x.get('type') or '—')} · {(x.get('title') or '—')[:90]}"
                                + f" · {x.get('date_display') or x.get('date') or '—'}",
                       "url": x.get("url") or "https://www.finanstilsynet.dk"}
                      for x in rows[:5]],
            provider_id="dk_ft", metas=[r["_meta"]],
            query={"source": "raw", "upstream": p},
        )

    def it_agcm_ricerca_provvedimenti(self, words=None, *, replica="dbconc", view="vw0401",
                                      start=0, maxresults=10, execution=None, no_cache=None):
        """legal it_agcm_ricerca_provvedimenti: AGCM case register — the authority's own decision
        search (www.agcm.it, the Domino custom endpoint /dotcmsCustom/getDomino, keyless).
        replica = dbconc (concentrations / abuse of dominance / unfair terms) or dbcons (consumer
        protection); view = the register's own view (dbconc: vw0401 concentrations, vw0301 abuse
        of dominance, vw0201 unfair terms; dbcons: vw0301); words = the upstream's name filter.
        LIVE LAWS (measured 2026-11-13): the Cloudflare gate is IP-BOUND, not fingerprint-bound —
        on direct egress every path answers 403 with "Cf-Mitigated: challenge" whatever the UA
        is; through this machine's proxy egress the same URLs answer 200. The words filter is a
        SINGLE TOKEN (a multi-word name answers HTTP 5000 upstream) — the face refuses it up
        front. Counts: dbconc vw0401 12,878 · vw0301 944 · vw0201 1,132 · dbcons vw0301 8,508."""
        self._lg_only("it_agcm_ricerca_provvedimenti")
        r = legal.it_agcm.cases_raw(replica=replica, view=view, words=words or "", start=start,
                                    maxresults=maxresults, cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        p = result["params"]
        if rows:
            top_row = rows[0]
            reason = (f"AGCM decision register ({p.get('replica')}/{p.get('view')}): {len(rows)} rows "
                      f"from offset {p.get('start')}"
                      + (f" (name filter \"{p.get('words')}\")" if p.get("words") else "")
                      + " — the case cell carries the /dettaglio link, the key into the detail face")
        else:
            reason = (f"AGCM decision register ({p.get('replica')}/{p.get('view')}): zero rows at "
                      f"offset {p.get('start')}"
                      + (f" for \"{p.get('words')}\"" if p.get("words") else "")
                      + " (an empty result is a legitimate answer)")
        return self._flat_env(
            tool="it_agcm_ricerca_provvedimenti",
            input={"words": p.get("words"), "replica": p.get("replica"), "view": p.get("view"),
                   "start": p.get("start"), "maxresults": p.get("maxresults")},
            reason=reason, result=result,
            evidence=[{"quote": " · ".join(f"{k}={v.get('value')}" for k, v in list(x.items())[:4]
                                           if isinstance(v, dict))[:180],
                       "url": "https://www.agcm.it/competenze/tutella-della-concorrenza"}
                      for x in rows[:5]],
            provider_id="it_agcm", metas=[r["_meta"]],
            query={"source": "raw", "upstream": p},
        )

    def it_agcm_rating(self, words=None, *, start=0, maxresults=10, execution=None,
                       no_cache=None):
        """legal it_agcm_rating: AGCM credit-rating register (the "Rating: elenco imprese" view
        of the dbrating replica, www.agcm.it — the same Domino custom endpoint as the decision
        search, keyless). 17,669 rows live (measured 2026-11-13).
        LIVE LAW: the words filter is a SINGLE TOKEN (a multi-word name answers HTTP 5000
        upstream). The rating value is an icon file name (/images/icons/2S0P.gif) — the parser
        lifts the code out of the file name.
        Rows: the company's name, its codice fiscale, the legal seat, the decision date, the
        outcome and the rating — the company-name → Italian tax-code join surface."""
        self._lg_only("it_agcm_rating")
        r = legal.it_agcm.cases_raw(replica="dbrating", view="vInternetWebdot", words=words or "",
                                    start=start, maxresults=maxresults, cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        p = result["params"]
        if rows:
            top_row = rows[0]
            reason = (f"AGCM credit-rating register: {len(rows)} rows from offset {p.get('start')}"
                      + (f" (name filter \"{p.get('words')}\")" if p.get("words") else "")
                      + " — each row carries the company's tax code and legal seat (the Italian "
                        "company join surface)")
        else:
            reason = (f"AGCM credit-rating register: zero rows at offset {p.get('start')}"
                      + (f" for \"{p.get('words')}\"" if p.get("words") else "")
                      + " (an empty result is a legitimate answer)")
        return self._flat_env(
            tool="it_agcm_rating",
            input={"words": p.get("words"), "replica": "dbrating", "view": "vInternetWebdot",
                   "start": p.get("start"), "maxresults": p.get("maxresults")},
            reason=reason, result=result,
            evidence=[{"quote": " · ".join(f"{k}={v.get('value')}" for k, v in list(x.items())[:5]
                                           if isinstance(v, dict))[:180],
                       "url": "https://www.agcm.it/competenze/tutella-della-concorrenza/"}
                      for x in rows[:5]],
            provider_id="it_agcm", metas=[r["_meta"]],
            query={"source": "raw", "upstream": p},
        )

    def it_agcm_dettaglio(self, uid=None, *, replica="dbconc", execution=None, no_cache=None):
        """legal it_agcm_dettaglio: one AGCM case card (the /dettaglio detail surface, served by
        /dotcmsCustom/getDominoDetail, keyless). uid = the 32-hex unid carried by the case link
        in the list rows; replica = the replica the uid belongs to (dbconc / dbcons / dbrating).
        LIVE LAW: the Cloudflare gate is IP-bound (403 "Cf-Mitigated: challenge" on direct
        egress; 200 through this machine's proxy egress).
        The card's field skeleton is a bold label div + a value div, grouped under the band
        headers DATI GENERALI / ISTRUTTORIA / DECISIONE / PROVVEDIMENTI COLLEGATI; the linked
        provvedimenti (the measures) come as the card's list items."""
        self._lg_only("it_agcm_dettaglio")
        r = legal.it_agcm.detail_raw(replica=replica, uid=uid, cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        fields = result.get("fields") or {}
        provvedimenti = result.get("provvedimenti") or []
        reason = (f"AGCM case card ({result.get('params', {}).get('replica')}): "
                  f"{len(fields)} fields, {len(provvedimenti)} linked measures — "
                  f"{(fields.get('Ragione') or fields.get('Oggetto') or fields.get('Tipo') or '—')}"
                  + (f" · {(provvedimenti[0].get('text') or '')[:70]}" if provvedimenti else ""))
        return self._flat_env(
            tool="it_agcm_dettaglio",
            input={"uid": result.get("params", {}).get("uid"), "replica": result.get("params", {}).get("replica")},
            reason=reason, result=result,
            evidence=[{"quote": f"{k}: {v}"} for k, v in list(fields.items())[:5]],
            provider_id="it_agcm", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def pl_uokik_decisions(self, *, year=None, practice=None, party=None, limit=50, offset=0,
                           execution=None, no_cache=None):
        """legal pl_uokik_decisions: UOKiK decisions of the President (decyzje.uokik.gov.pl, the
        Domino "dec_prez" view enumeration, keyless) — 22,344 decisions under 12 practices and
        216 years (measured 2026-11-13).
        LIVE LAWS: the host RESETS the TLS connection on roughly half the requests from this
        machine (the transport's retry absorbs it) and the index is a 15.1 MB payload — it is
        cached whole (TTL 12 h) and NEVER re-fetched per row. The surface has NO server-side
        filter (it is a view enumeration, not a search), so year / practice / party filter
        LOCALLY — exactly like the LV KNAB party register.
        Rows: the practice (Rodzaj praktyki), the year, the decision number ("Numer decyzji:
        DIH-II-39/2026"), the decision date, the parties (Uczestnicy postępowania) and the
        32-hex unid that keys the detail face."""
        self._lg_only("pl_uokik_decisions")
        r = legal.pl_uokik.decisions_raw(year=year, practice=practice, party=party, limit=limit,
                                         offset=offset, cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        p = result["params"]
        if rows:
            top_row = rows[0]
            reason = (f"UOKiK President decisions: {result['total']} decisions match, {len(rows)} rows "
                      f"returned"
                      + (f" (year {p.get('year')})" if p.get("year") else "")
                      + (f" (practice \"{p.get('practice')}\")" if p.get("practice") else "")
                      + (f" (party \"{p.get('party')}\")" if p.get("party") else "")
                      + f" — sample {top_row.get('decision_number') or '—'}"
                      + f" · {top_row.get('decision_date') or '—'}"
                      + f" · {top_row.get('category') or '—'}"
                      + (f" · {', '.join((top_row.get('parties') or [])[:2])}"
                         if top_row.get("parties") else "")
                      + " — the register is enumerated whole and filtered locally")
        else:
            reason = ("UOKiK President decisions: zero decisions match the filter "
                      "(an empty result is a legitimate answer)")
        return self._flat_env(
            tool="pl_uokik_decisions",
            input={"year": p.get("year"), "practice": p.get("practice"), "party": p.get("party"),
                   "limit": p.get("limit"), "offset": p.get("offset")},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('decision_number') or '—'} · {x.get('decision_date') or '—'}"
                                + (f" · {', '.join((x.get('parties') or [])[:2])}" if x.get("parties") else "")
                                + f" · {x.get('category') or '—'}",
                       "url": x.get("url") or "https://decyzje.uokik.gov.pl"}
                      for x in rows[:5]],
            provider_id="pl_uokik", metas=[r["_meta"]],
            query={"source": "raw", "upstream": p},
        )

    def pl_uokik_decision(self, unid=None, *, execution=None, no_cache=None):
        """legal pl_uokik_decision: one UOKiK decision card (decyzje.uokik.gov.pl, the
        ?act=Decyzja detail surface, keyless). unid = the 32-hex id the index rows carry.
        LIVE LAWS: the host resets TLS on roughly half the requests from this machine (the
        transport's retry absorbs it).
        The card is a two-column table whose rows are <td><b>LABEL:</b></td><td>VALUE</td> —
        Numer decyzji / Data wydania decyzji / Sygnatura akt / Uczestnicy postępowania /
        Rodzaj praktyki / Kara (the penalty) / Branża / Region / Odwołanie do sądu, plus the
        decision PDF link."""
        self._lg_only("pl_uokik_decision")
        r = legal.pl_uokik.decision_raw(unid, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        fields = result.get("fields") or {}
        parties = result.get("parties") or []
        reason = (f"UOKiK decision {fields.get('Numer decyzji') or '—'}"
                  + (f" · {fields.get('Data wydania decyzji')}" if fields.get("Data wydania decyzji") else "")
                  + (f" · penalty: {fields.get('Kara')}" if fields.get("Kara") else "")
                  + (f" · parties: {', '.join(parties[:3])}" if parties else "")
                  + f" · practice {fields.get('Rodzaj praktyki') or '—'}")
        return self._flat_env(
            tool="pl_uokik_decision",
            input={"unid": result.get("params", {}).get("unid")},
            reason=reason, result=result,
            evidence=[{"quote": f"{k}: {v}"} for k, v in list(fields.items())[:6]],
            provider_id="pl_uokik", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def us_cbp_ruling(self, ruling_number=None, *, execution=None, no_cache=None):
        """legal us_cbp_ruling: US Customs and Border Protection CROSS ruling (rulings.cbp.gov,
        keyless) — the tariff-classification ruling, fetched by its ruling number.
        LIVE LAW (measured 2026-11-13): the SEARCH endpoint (/api/search) is behind a reCAPTCHA
        Enterprise gate and answers 403 — only the detail-by-number surface is on the route, so
        the face takes a ruling number (the register's size comes from the census face).
        The body is CRLF-padded plain text with a header block; the importer name is the line
        after the contact line (the company join surface). The `url` field is a pre-signed S3
        link to the original .doc/.pdf — it expires (X-Amz-Expires=900)."""
        self._lg_only("us_cbp_ruling")
        r = legal.us_cbp.ruling_raw(ruling_number, cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        reason = (f"CBP CROSS ruling {result.get('ruling_number')}: {result.get('ruling_date') or '—'}"
                  + f" · importer {result.get('importer') or '—'}"
                  + (f" · {result.get('subject') or '—'}"[:120] if result.get("subject") else "")
                  + (" · operationally revoked" if result.get("operationally_revoked") else ""))
        return self._flat_env(
            tool="us_cbp_ruling",
            input={"ruling_number": result.get("params", {}).get("ruling_number")},
            reason=reason, result=result,
            evidence=[{"quote": (result.get("text") or "")[:200].replace("\n", " / "),
                       "url": "https://rulings.cbp.gov/api/ruling/" + str(result.get("ruling_number") or "")}],
            provider_id="us_cbp", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def us_cbp_stat(self, *, execution=None, no_cache=None):
        """legal us_cbp_stat: the CBP CROSS register census (rulings.cbp.gov — the
        /api/stat/lastupdate endpoint, keyless): the number of searchable rulings (222,344
        live, measured 2026-11-13) and the register's last-update stamp.
        This is the register-level surface: the upstream's SEARCH endpoint is behind a
        reCAPTCHA Enterprise gate (403), so the census is the only way to size the corpus from
        the machine."""
        self._lg_only("us_cbp_stat")
        r = legal.us_cbp.stat_raw(cache=self._c._cache,
                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        stat = result.get("stat") or {}
        reason = (f"CBP CROSS register census: {result.get('total') or '—'} searchable rulings"
                  + (f" · last update {stat.get('lastUpdate') or stat.get('lastupdate') or '—'}"
                     if (stat.get("lastUpdate") or stat.get("lastupdate")) else "")
                  + " — the upstream's search endpoint is reCAPTCHA-gated, so the register is "
                    "reachable by ruling number only")
        return self._flat_env(
            tool="us_cbp_stat",
            input={},
            reason=reason, result=result,
            evidence=[{"quote": f"{k}={v}"} for k, v in list(stat.items())[:6]
                       if isinstance(v, (int, str, float))],
            provider_id="us_cbp", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {}},
        )

    # ===================== 0.3.61 batch E3 — API-faces depth wave (FR/US) =====================

    def fr_court_judgments(self, year=None, month=None, court="ce", *, execution=None, no_cache=None):
        """legal fr_court_judgments: French administrative courts monthly judgment archive
        (opendata.justice-administrative.fr, keyless) — one court-month zip → the metadata
        rows of EVERY judgment in it: Conseil d'État (--court ce, /DCE/…/CE_{ym}.zip — 791
        judgments in 2026-10, 2.7MB) or the cours administratives d'appel (--court caa,
        /DCA/…/CAA_{ym}.zip — 2,340 judgments in 2026-10, 11.3MB); history 2021-06→.
        Rows carry ecli (CE only — the CAA archives carry NO Numero_ECLI element, measured
        0/24), dossier_number, jurisdiction code+name, lecture_date, decision/appeal type,
        publication_code, solution (the outcome verbatim — Rejet / Annulation …), audience
        date/role/formation. doc_id (DCE_503183_20261001 / DCA_20BX01837_20261007) keys the
        full-text face. The zip rides the bytes channel (jp_fsa/ca_osb ext-9 family)."""
        self._lg_only("fr_court_judgments")
        r = legal.fr_court.judgments_raw(year=year, month=month, court=court,
                                         cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        court_label = "Conseil d'État" if result["court"] == "ce" else "cours administratives d'appel"
        if rows:
            with_ecli = sum(1 for x in rows if x.get("ecli"))
            sample = rows[0]
            reason = (f"{court_label} archive {result['archive']}: {result['total']} judgments — "
                      f"{with_ecli} carry ECLI (CE zips only; CAA zips have no Numero_ECLI "
                      f"element — doc_id keys the full text) — sample {sample.get('doc_id')} "
                      f"{sample.get('solution') or '—'} · {sample.get('jurisdiction_name') or '—'}")
        else:
            reason = (f"{court_label} archive {result['archive']}: zero judgments — a month "
                      f"before 2021-06 (the archive's floor) or a not-yet-published month")
        return self._flat_env(
            tool="fr_court_judgments",
            input={"year": result["year"], "month": result["month"], "court": result["court"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('doc_id')} · {x.get('solution') or '—'}"
                                + (f" · {x.get('ecli')}" if x.get("ecli") else "")
                                + f" · {x.get('jurisdiction_name') or '—'}",
                       "url": f"https://opendata.justice-administrative.fr/"
                              f"{'DCE' if result['court'] == 'ce' else 'DCA'}/{result['year']}/"
                              f"{result['month']:02d}/{result['archive']}"}
                      for x in rows[:5]],
            provider_id="fr_court", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def fr_court_judgment(self, doc_id=None, *, execution=None, no_cache=None):
        """legal fr_court_judgment: ONE French administrative judgment with its full text
        (opendata.justice-administrative.fr, keyless). doc_id takes the archive stem the
        rows carry (DCE_503183_20261001 / DCA_20BX01837_20261007) or a CE ECLI
        (ECLI:FR:CECHR:2026:503183.20261001 — the dossier+date tail maps onto the same
        stem); the year+month route to the one monthly zip that holds it. Returns the
        metadata row plus texte_integral — the judgment body, upstream HTML verbatim."""
        self._lg_only("fr_court_judgment")
        r = legal.fr_court.judgment_raw(doc_id, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        body = result.get("texte_integral") or ""
        reason = (f"judgment {result.get('doc_id')}: {result.get('solution') or '—'}"
                  + (f" · {result.get('ecli')}" if result.get("ecli") else "")
                  + f" · read {result.get('lecture_date') or '—'}"
                  + f" · {result.get('jurisdiction_name') or '—'}"
                  + f" · full text {len(body):,} chars")
        return self._flat_env(
            tool="fr_court_judgment",
            input={"doc_id": result.get("params", {}).get("doc_id")},
            reason=reason, result=result,
            evidence=[{"quote": f"{result.get('doc_id')} · {result.get('solution') or '—'} · "
                                f"dossier {result.get('dossier_number') or '—'}",
                       "url": "https://opendata.justice-administrative.fr/"},
                      {"quote": body[:200].replace("\n", " / ") if body else "—",
                       "url": "https://opendata.justice-administrative.fr/"}],
            provider_id="fr_court", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def us_occ_ea_search(self, q=None, *, start_dte_min=None, start_dte_max=None,
                         active_only=None, terminated_only=None, ind_only=None, inst_only=None,
                         limit=None, execution=None, no_cache=None):
        """legal us_occ_ea_search: the OCC enforcement-actions DATABASE (apps.occ.gov
        /EASearch/Search/ExportToJson, keyless) — the structured twin of the 0.3.28
        news-release face: the FULL HISTORY 1989→2026 in one endpoint (~6,072 actions),
        14 fields per row — Institution / CharterNumber (the hard join key into the US
        bank registers) / Company / Individual (the sanctioned person) / TypeCode+
        TypeDescription (C&D, CMP, Prohibition …) / Amount (numeric) / StartDate /
        StartDocuments (the AA-ENF-YYYY-NN docket ids — the ea{docket}.pdf download key)
        / Termination pair / DocketNumber / SubjectMatters (violation codes, list).
        At least one filter is required (q / start-date window / one flag) — the
        unfiltered call is the whole 6,000-row history and stays on the bulk path."""
        self._lg_only("us_occ_ea_search")
        r = legal.us_occ.enforcements_raw(q, start_dte_min=start_dte_min,
                                          start_dte_max=start_dte_max,
                                          active_only=active_only,
                                          terminated_only=terminated_only,
                                          ind_only=ind_only, inst_only=inst_only,
                                          limit=limit, cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            fined = sum(1 for x in rows if x.get("amount_usd"))
            sample = rows[0]
            reason = (f"OCC enforcement actions: {result['total']} rows"
                      + (" (truncated)" if result.get("truncated") else "")
                      + f", {fined} with a CMP amount — the register runs the full history "
                      f"1989→today — sample {sample.get('type_description') or '—'} against "
                      f"{sample.get('institution') or sample.get('individual') or '—'}"
                      + (f" (${sample['amount_usd']:,.0f})" if sample.get("amount_usd") else ""))
        else:
            reason = ("OCC enforcement actions: zero rows — a name substring with no match "
                      "or a start-date window outside 1989→today")
        return self._flat_env(
            tool="us_occ_ea_search",
            input={"q": q, "start_dte_min": start_dte_min, "start_dte_max": start_dte_max,
                   "active_only": bool(active_only), "terminated_only": bool(terminated_only),
                   "ind_only": bool(ind_only), "inst_only": bool(inst_only), "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('type_description') or '—'} · "
                                f"{x.get('institution') or x.get('company') or x.get('individual') or '—'}"
                                + (f" · ${x['amount_usd']:,.0f}" if x.get("amount_usd") else "")
                                + f" · {x.get('start_date') or '—'}"
                                + (f" · docket {x['start_documents'][0]}" if x.get("start_documents") else ""),
                       "url": (x.get("pdf_urls") or ["https://apps.occ.gov/EASearch"])[0]}
                      for x in rows[:5]],
            provider_id="us_occ", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ===================== 0.3.62 batch E4 — API-faces depth wave (NL/ES/KR) =====================

    def nl_acm_publications(self, category=None, q=None, *, limit=20, execution=None, no_cache=None):
        """legal nl_acm_publications: Netherlands ACM publication register BY SITEMAP
        (www.acm.nl, keyless) — the /nl/publicaties/ corpus (13,368 URLs,
        2003→2026): the list page's JS window does not widen, so /sitemap.xml
        (a 9-page index of itself, ?page=1..9, per-URL lastmod) IS the channel.
        Rows carry doc_id (the /publicatie/{id}/ numeric — the detail face's
        key), slug, url, lastmod. --category is a slug-token heuristic
        (concentratie 2,263 / boete 457 / onderzoek 457 / kartel 175 / cbb
        ~159 / rechtbank ~118 — research-counted), not an upstream field.
        A list call sweeps index + 9 submaps, all cached 12h."""
        self._lg_only("nl_acm_publications")
        r = legal.nl_acm.publications_raw(category, q, limit=limit,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            reason = (f"ACM publications: {result['total_matched']:,} of {result['total_corpus']:,} "
                      f"URLs match ({result['submaps']} sitemap pages, lastmod "
                      f"{str(result['lastmod_min'])[:10]}→{str(result['lastmod_max'])[:10]}) — "
                      f"sample {rows[0].get('slug', '')[:60]}")
        else:
            reason = ("ACM publications: zero rows — a slug substring or category token with "
                      "no match in the 13k-URL corpus")
        return self._flat_env(
            tool="nl_acm_publications",
            input={"category": category, "q": q, "limit": result.get("limit_applied") or limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{(x.get('lastmod') or '—')[:10]} · {(x.get('doc_id') or 'no-id')}"
                                f" · {x.get('slug', '')[:70]}",
                       "url": x.get("url")} for x in rows[:5]],
            provider_id="nl_acm", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def nl_acm_publication(self, doc_id=None, url=None, *, execution=None, no_cache=None):
        """legal nl_acm_publication: ONE Netherlands ACM publication
        (www.acm.nl, keyless) — the content-block field family with the Dutch
        labels verbatim (Publicatiedatum / Publicatietype / Beslisdatum / Zaak
        = Zaaknummer + the /nl/zaak/{id} case link / Partijen — a NESTED second
        h3 inside the Zaak block / Trefwoorden / Onderwerpen) plus pdf_urls.
        doc_id = the numeric id from nl_acm_publications rows (resolved
        through the cached sitemap set); a full URL is also accepted."""
        self._lg_only("nl_acm_publication")
        r = legal.nl_acm.publication_raw(doc_id, url, cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        f = result.get("fields") or {}
        zaak = f.get("Zaak") or "—"
        reason = (f"ACM publication {result.get('doc_id') or ''}: {result.get('title') or '—'}"
                  + (f" · Partijen {f.get('Partijen')}" if f.get("Partijen") else "")
                  + (f" · zaak_id {result.get('zaak_id')}" if result.get("zaak_id") else "")
                  + f" · {len(f)} fields · {len(result.get('pdf_urls') or [])} PDFs")
        return self._flat_env(
            tool="nl_acm_publication",
            input={"doc_id": result.get("params", {}).get("doc_id"), "url": url},
            reason=reason, result=result,
            evidence=[{"quote": f"{k}: {v[:90]}", "url": result.get("url")}
                      for k, v in list(f.items())[:5]],
            provider_id="nl_acm", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def es_cnmv_sanctions(self, page=None, *, all_pages=False, party=None, severity=None,
                          lang="es", limit=20, execution=None, no_cache=None):
        """legal es_cnmv_sanctions: the Spanish CNMV securities sanction register
        (www.cnmv.es RegistroSanciones, keyless ASP.NET) — the statutory
        publicity register (LMV art. 32.3): a rolling FIVE-YEAR window, five-row
        pages, the tail page discovered from the page links (18 pages on
        2026-11-16 — the window slides). Rows carry the resolution prose
        verbatim with severity tokens (muy graves / graves), the parties
        (company-suffix forms vs don/doña persons, parsed heuristically beside
        the prose), the '(BOE de …)' gazette ref and the per-row PDF
        (verdocumento?e={opaque token}). Default = page 0; --page fetches one
        page; --party/--severity/--all sweep every page (each cached 24h)."""
        self._lg_only("es_cnmv_sanctions")
        r = legal.es_cnmv_sanctions.sanctions_raw(page, all_pages=all_pages, party=party,
                                                  severity=severity, lang=lang, limit=limit,
                                                  cache=self._c._cache,
                                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            s = rows[0]
            reason = (f"CNMV sanctions: {result['total_matched']} of {result['scanned_rows']} entries "
                      f"(pages {result['pages']}, the rolling five-year window) — sample "
                      f"{s.get('date_iso')} {s.get('severity') or '—'} "
                      f"{(s.get('parties_companies') or s.get('parties_persons') or ['—'])[0]}")
        else:
            reason = ("CNMV sanctions: zero rows — a party substring/severity token with no match "
                      "in the window (the register carries ~90 entries at any time)")
        return self._flat_env(
            tool="es_cnmv_sanctions",
            input={"page": page, "all_pages": bool(all_pages), "party": party,
                   "severity": severity, "lang": lang, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('date_iso')} · {x.get('severity') or '—'} · "
                                f"{x.get('resolution_text', '')[:110]}",
                       "url": x.get("pdf_url") or "https://www.cnmv.es/Portal/Consultas/RegistroSanciones/verRegSanciones.aspx"}
                      for x in rows[:5]],
            provider_id="es_cnmv_sanctions", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def kr_fss_sanctions(self, org=None, *, date_from=None, date_to=None, layer=None,
                         limit=20, execution=None, no_cache=None):
        """legal kr_fss_sanctions: the Korean FSS 제재 정보 register as ONE xlsx
        (www.fss.or.kr excelDown.uxls, keyless) — the register's one-shot
        channel: 5,804 rows 2008-10-02→today in one ~270KB POST answer (the
        list page's default window shows only 303). MEASURED column shape (the
        header row misaligns): A the sanctioned/inspected entity, B the date,
        C/D/E the sanction content split institution/executive/employee, F the
        FSS department. 1,245 rows carry no inline content — recent rows'
        content is a PDF attachment on the view.do detail (keyless direct
        download) — kept null and counted; the PDF walk is a batch concern.
        The transport's first POST × bytes combination (ext 7 × ext 9)."""
        self._lg_only("kr_fss_sanctions")
        r = legal.kr_fss.sanctions_raw(org, date_from=date_from, date_to=date_to,
                                       layer=layer, limit=limit, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        cen = result.get("census") or {}
        if rows:
            s = rows[0]
            content = (s.get("institution_sanction") or s.get("executive_sanction")
                       or s.get("employee_sanction") or "no inline content (PDF-attachment row)")
            reason = (f"FSS sanctions: {result['total_matched']:,} of {result['scanned_rows']:,} rows "
                      f"({cen.get('date_min')}→{cen.get('date_max')}; "
                      f"{cen.get('rows_without_inline_content', 0):,} PDF-attachment rows) — "
                      f"sample {s.get('org')} {s.get('date')}")
        else:
            reason = ("FSS sanctions: zero rows — an org substring/date window/layer with no match "
                      "in the 5.8k-row register")
        return self._flat_env(
            tool="kr_fss_sanctions",
            input={"org": org, "date_from": date_from, "date_to": date_to,
                   "layer": layer, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('org') or '—'} · {x.get('date') or '—'} · "
                                + ((x.get("institution_sanction") or x.get("executive_sanction")
                                    or x.get("employee_sanction") or "PDF-attachment row")[:70])
                                + f" · {x.get('department') or '—'}",
                       "url": "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476"}
                      for x in rows[:5]],
            provider_id="kr_fss", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def jp_jftc_decisions(self, subject=None, branch=None, year=None, number=None,
                          era="R", page=1, *, limit=20, execution=None, no_cache=None):
        """legal jp_jftc_decisions: the Japan FTC 審決・判決 database search
        (snk.jftc.go.jp DC004, keyless but UA-fingerprinted + Laravel CSRF):
        the JFTC's own case search over 6,220 rows (2026-11-16). Rows carry
        rank, the DC005 case_id, title, the type span (決定/審決/判決/排除命令/
        課徴金納付命令), court, 事件番号, the era 処分年月日 normalized to ISO
        (令和08年02月20日 → 2026-02-20; R=2018+n / H=1988+n / S=1925+n), 適用法条,
        the pdf_url + KB and the two inline 概要 blocks. subject = 被審人 slots
        (1-5, upstream dsubject[0-4] — ソニー → 14 rows); branch = the
        case-class token (J01 判 / J03 納 / J05 訟…); year/number = the event
        no. --page is 1-BASED, 10 rows/page (maxOnePageItem is NOT honoured
        upstream — measured). The session bootstrap caches {token, cookie}
        together; a stale pair 419s and the face re-bootstraps once."""
        self._lg_only("jp_jftc_decisions")
        r = legal.jp_jftc.decisions_raw(subject, branch, year, number, era, page,
                                        limit=limit, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            s = rows[0]
            reason = (f"JFTC decisions: {result['total_matched']:,} rows upstream, page "
                      f"{result['page']}/{result['pages'] or '?'} (10/page, 1-based) — sample "
                      f"{(s.get('disposal_date_iso') or '—')} {s.get('type') or '—'} "
                      f"{(s.get('title') or '')[:60]}")
        else:
            reason = (f"JFTC decisions: zero rows on page {result.get('page')} — a subject "
                      f"slot/branch/event-no with no match (ソニー → 14; bare sweep → 6,220)")
        return self._flat_env(
            tool="jp_jftc_decisions",
            input={"subject": subject, "branch": branch, "year": year, "number": number,
                   "era": era, "page": page, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('rank')} · {x.get('event_no') or '—'} · "
                                f"{x.get('disposal_date_iso') or '—'} · {(x.get('title') or '')[:60]}",
                       "url": x.get("url")} for x in rows[:5]],
            provider_id="jp_jftc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def jp_jftc_decision(self, case_id, *, execution=None, no_cache=None):
        """legal jp_jftc_decision: ONE JFTC case full text (snk.jftc.go.jp DC005,
        keyless + fingerprint suite): the h_cont structured header (title, 適用法条
        + court, 事件番号 — full-width digits upstream, verbatim kept — the h3
        section 決定/審決/判決 + its era date as ISO, the parties block verbatim
        INCLUDING the 《氏名》 official anonymization, the judge panel) plus the
        full 主文+事実及び理由 text. case_id = the DC005 path token from
        jp_jftc_decisions rows (e.g. R080220R07G05000194K). PDFs live on the
        list row (a.pdf_dl), not the detail page."""
        self._lg_only("jp_jftc_decision")
        r = legal.jp_jftc.decision_raw(case_id, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        reason = (f"JFTC decision {result.get('case_id')}: {result.get('title') or '—'}"
                  + (f" · {result.get('section')} {result.get('section_date_iso') or ''}" if result.get("section") else "")
                  + (f" · {result.get('law')}" if result.get("law") else "")
                  + f" · text {len(result.get('text') or '')} chars")
        return self._flat_env(
            tool="jp_jftc_decision",
            input={"case_id": result.get("params", {}).get("case_id")},
            reason=reason, result=result,
            evidence=[{"quote": f"{k}: {str(v)[:90]}", "url": result.get("url")}
                      for k, v in (("title", result.get("title")),
                                   ("event_no", result.get("event_no")),
                                   ("law", result.get("law")),
                                   ("section", result.get("section")),
                                   ("judges", result.get("judges"))) if v],
            provider_id="jp_jftc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def in_cci_antitrust_orders(self, q=None, case_no=None, order_type=None, page=1, *,
                                limit=20, execution=None, no_cache=None):
        """legal in_cci_antitrust_orders: the Competition Commission of India
        antitrust order register (www.cci.gov.in /antitrust/orders/list, keyless
        but Laravel CSRF'd — the DataTables POST replayed byte-equal with
        tab_type=antitrust and the 5 measured columns; 1,246 rows on
        2026-11-16). Rows carry case_no, the Act section, the order type
        ('Anti-trust Section 19 (1)'), the description VERBATIM — recent rows
        read 'XYZ' because the parties live in the order PDF, never guessed —
        the dd/mm/yyyy dates and the attachment JSON (title/file/KB) plus the
        /orders/details direct links. q rides search[value] (upstream-global);
        case_no/order_type are page-local substrings."""
        self._lg_only("in_cci_antitrust_orders")
        r = legal.in_cci.antitrust_orders_raw(q, case_no, order_type, page, limit=limit,
                                              cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            s = rows[0]
            reason = (f"CCI antitrust orders: {result['total_records']:,} rows upstream, page "
                      f"{result['page']}/{result['pages'] or '?'} — sample "
                      f"{s.get('case_no')} {s.get('section') or '—'} "
                      f"{(s.get('description') or '')[:60]}")
        else:
            reason = ("CCI antitrust orders: zero rows on this page for the filters — "
                      "q is upstream-global, case_no/order_type page-local")
        return self._flat_env(
            tool="in_cci_antitrust_orders",
            input={"q": q, "case_no": case_no, "order_type": order_type,
                   "page": page, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('case_no')} · {x.get('section') or '—'} · "
                                f"{x.get('order_date')} · {(x.get('description') or '')[:70]}",
                       "url": (x.get("detail_urls") or [None])[0]} for x in rows[:5]],
            provider_id="in_cci", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def in_cci_combinations(self, party=None, status=None, form_type=None, q=None,
                            page=1, *, limit=20, execution=None, no_cache=None):
        """legal in_cci_combinations: the CCI combination-order register
        (www.cci.gov.in /combination/orders-section31, keyless + CSRF — the
        DataTables GET replayed byte-equal with the 9 measured columns; the
        POST answers 405; 1,491 rows on 2026-11-16). Rows carry combination_no
        ('C-2026/10/1485'), party_name (real parties here, not XYZ), the form
        (I/II/III), order_type (Green Channel Notices…), notification/
        decision dates and the summary/order attachments. party rides the
        upstream searchString; status/form_type pass through verbatim."""
        self._lg_only("in_cci_combinations")
        r = legal.in_cci.combinations_raw(party, status, form_type, q, page, limit=limit,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            s = rows[0]
            reason = (f"CCI combinations: {result['total_records']:,} rows upstream, page "
                      f"{result['page']}/{result['pages'] or '?'} — sample "
                      f"{s.get('combination_no')} {s.get('form_type') or '—'} "
                      f"{(s.get('party_name') or '')[:60]}")
        else:
            reason = ("CCI combinations: zero rows on this page for the filters — "
                      "party/searchString upstream, status/form_type verbatim")
        return self._flat_env(
            tool="in_cci_combinations",
            input={"party": party, "status": status, "form_type": form_type,
                   "q": q, "page": page, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('combination_no')} · {x.get('order_type') or '—'} · "
                                f"{(x.get('party_name') or '')[:70]}",
                       "url": (x.get("detail_urls") or [None])[0]} for x in rows[:5]],
            provider_id="in_cci", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )

    def au_accc_actions(self, topic=None, q=None, page=0, action_type=None, *,
                        limit=20, execution=None, no_cache=None):
        """legal au_accc_actions: the ACCC enforcement-actions stream
        (www.accc.gov.au news-centre, keyless but UA-fingerprinted + Drupal
        lazy views — the listing renders form + filtered pager but an EMPTY
        view-content; the rows exist only through GET /views/ajax, the
        viewsAjaxHistory module's own hop with the full exposed-input shape).
        Topic 12039 = Compliance and enforcement (~3,106 items /
        125 pages, 25 cards/page on 2026-11-16): media releases, speeches and
        updates with the accc-date-card shape — data_url path (the item key),
        ribbon type (Media release / Speech / Update), publish day-month-year
        as ISO, the h2 title (entities unescaped), the acccgov-summary and
        the topic badges. --page is 0-BASED; --type news|update selects the
        content-type tab; q is a page-local substring."""
        self._lg_only("au_accc_actions")
        r = legal.au_accc.actions_raw(topic, q, page, action_type, limit=limit,
                                      cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            s = rows[0]
            reason = (f"ACCC actions: page {result['page']} of {result['pages'] or '?'} "
                      f"({result['page_size']} cards/page, topic "
                      f"{result['params'].get('topic')}) — sample "
                      f"{s.get('date_iso') or '—'} {s.get('item_type') or '—'} "
                      f"{(s.get('title') or '')[:55]}")
        else:
            reason = ("ACCC actions: zero rows on this page — the upstream lazy views "
                      "sometimes gates the /views/ajax rows window (form+pager still "
                      "render); walk pages, drop q, or retry later — the search box is "
                      "page-local either way")
        return self._flat_env(
            tool="au_accc_actions",
            input={"topic": topic, "q": q, "page": page,
                   "action_type": action_type, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('date_iso') or '—'} · {x.get('item_type') or '—'} · "
                                f"{(x.get('title') or '')[:80]}",
                       "url": x.get("url")} for x in rows[:5]],
            provider_id="au_accc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result.get("params", {})},
        )
