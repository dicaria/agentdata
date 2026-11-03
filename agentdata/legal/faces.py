"""legal faces — flat face-method mixin (split per domain in 0.2.6, moved in from client.py _Domain).

Mixed into the root _Domain (assembled via MRO, see client.py); discipline: no __init__, depends only on the
root internals (_flat_env/_c/_request…), method names globally unique across domains (a collision
would shadow another domain's face).
"""
from ..errors import SdkError
from ..transport import resolve_execution
from ..transport import enrich_source
import re


from .. import legal  # domain-module path call (historical shape, kept for minimal disturbance)

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

    # ---------- 0.3.16 legal CO SIC 制裁面（datos.gov.co Socrata 73dx-n59j；与 co_secop_contracts 同 $-参数契约） ----------

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

    # ---------- 0.2.4 flat-panel commands (research: grants × papers × institutions × impact — upstream verbatim params) ----------
    # The grants axis was established in 0.2.2 and renamed research in 0.2.4 (the grants alias was removed in 0.3.0).
