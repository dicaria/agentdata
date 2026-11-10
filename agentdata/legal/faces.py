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
