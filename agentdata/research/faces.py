"""research faces — flat face-method mixin (0.2.6 domain split, migrated from client.py _Domain).

Mixes into the root _Domain (assembled via MRO, see client.py); discipline: no __init__,
depend only on root internals (_flat_env/_c/_request…), method names globally unique across
domains (a collision would shadow another domain's face).
"""
from ..errors import SdkError


from .. import research  # call through the domain module (historical shape, kept for minimal churn)

class ResearchFaces:
    def _research_only(self, tool: str):
        if self.name != "research":
            raise SdkError("usage_error", detail=f"{tool} is a research-domain capability (not available on the {self.name} domain)")

    def nsf_awards(self, *, keyword=None, id=None, rpp=25, offset=0,
                    execution=None, no_cache=None):
        """research nsf_awards: NSF funding search (awards.json verbatim four params; keyword
        full-text × id point lookup, XOR enforced locally; rpp 1-200 upstream doc wall; upstream
        sends no total — a full page signals more via has_more)."""
        self._research_only("nsf_awards")
        r = research.nsf.awards_raw(keyword, id=id, rpp=rpp, offset=offset,
                                     cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        q = keyword or id
        return self._flat_env(
            tool="nsf_awards", input={"keyword": keyword, "id": id,
                                      "rpp": r["params"]["rpp"], "offset": r["params"]["offset"]},
            reason=(f"NSF: '{q}' — {result['count']} rows this page"
                    + (" (full page, likely more — continue with --offset)" if result.get("has_more") else "")
                    + (f", top hit {top['id']} {top['title'] or '—'}"
                       f" ({top['institution'] or '—'}, ${top['amount'] or '—'})" if top else ", zero hits")),
            result=result,
            evidence=[{"quote": f"{a['id'] or '—'} = {a['title'] or '—'}"
                                f" ({a['institution'] or '—'}, PI {a['principal_investigator'] or '—'})",
                       "url": a["award_notice_url"] or "https://www.nsf.gov/awardsearch/"}
                      for a in result["rows"][:5]],
            provider_id="nsf", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def nih_reporter_projects(self, *, org_name=None, fiscal_year=None, include_fields=None,
                              limit=25, offset=0, execution=None, no_cache=None):
        """research nih_reporter_projects: NIH funded-project search (/v2/projects/search POST;
        at least one of org_name/fiscal_year (local safety wall); criteria=snake_case and
        include_fields=camelCase are the two axes each hard-bound upstream (a wrong shape is
        silently ignored — bare params are not passed through); offset+limit ≤15,000 upstream
        deep-paging wall)."""
        self._research_only("nih_reporter_projects")
        r = research.nih_reporter.projects_raw(org_name, fiscal_year=fiscal_year,
                                                include_fields=include_fields, limit=limit, offset=offset,
                                                cache=self._c._cache,
                                                no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        crit = r["params"]["criteria"]
        who = ""
        if crit.get("org_names"):
            who += f"org '{crit['org_names'][0]}' "
        if crit.get("fiscal_years"):
            who += f"FY{crit['fiscal_years'][0]} "
        if result["total"] is None:
            reason = f"NIH RePORTER: {result['count']} items returned"
        else:
            reason = (f"NIH RePORTER: {who}— {result['total']} items in total, {result['count']} on this page"
                      + (f", top hit {top['appl_id']} {top['project_title'] or '—'}"
                         f" ({top['org_name'] or '—'})" if top else "")
                      + (f" — human-readable search page {result['search_url']}" if result.get("search_url") else ""))
        return self._flat_env(
            tool="nih_reporter_projects",
            input={"org_name": org_name, "fiscal_year": fiscal_year,
                   "include_fields": include_fields, "limit": r["params"]["limit"],
                   "offset": r["params"]["offset"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{p['appl_id'] or '—'} = {p['project_title'] or '—'}"
                                f" ({p['org_name'] or '—'}, "
                                f"{'/'.join(x['full_name'] or '—' for x in p['pis'][:2]) or '—'})",
                       "url": f"https://reporter.nih.gov/project-details/{p['appl_id']}"}
                      for p in result["rows"][:5]],
            provider_id="nih-reporter", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.2.4 research new faces (OpenAlex/Crossref/GtR/NIH bridge/iCite/bioRxiv/OpenCitations) ——

    def openalex_works(self, *, search=None, ror=None, doi=None, title_search=None,
                       per_page=25, cursor=None, select=None, execution=None, no_cache=None):
        """research openalex_works: global scholarly output search (/works verbatim name;
        search full-text × ror institution edge × doi × title_search — four constraints combined
        with AND; per_page 1-200 explicit upstream 400 wall; the cursor encodes paging only —
        when continuing, the constraint parameters must be re-sent unchanged; select is
        force-merged with the core fields (adversarial-review constraints 2/3))."""
        self._research_only("openalex_works")
        r = research.openalex.works_raw(search, ror=ror, doi=doi, title_search=title_search,
                                         per_page=per_page, cursor=cursor, select=select,
                                         cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        cons = []
        if search:
            cons.append(f"full-text '{search}'")
        if r["params"].get("filter"):
            cons.append("filter " + r["params"]["filter"])
        return self._flat_env(
            tool="openalex_works",
            input={"search": search, "ror": ror, "doi": doi, "title_search": title_search,
                   "per_page": r["params"]["per-page"], "cursor": cursor, "select": select},
            reason=(f"OpenAlex: {' × '.join(cons)} — {result['total']:,} works hit, {result['count']} rows this page"
                    + (f", top hit {top['display_name'] or '—'}"
                       f" ({top['publication_year']}, cited {top['cited_by_count']})" if top else "")
                    + (" — continue with next_cursor (re-send the constraint parameters unchanged)" if result.get("next_cursor") else "")),
            result=result,
            evidence=[{"quote": f"{w['display_name'] or '—'} ({w['publication_year']}, "
                                + "; ".join((a["institutions"] or [{}])[0].get("display_name")
                                            or (a["raw_author_name"] or a["author"] or "—")
                                            for a in w["authorships"][:2])
                                + f", cited {w['cited_by_count']})",
                       "url": w["doi"] or w["id"]}
                      for w in result["rows"][:5]],
            provider_id="openalex", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def openalex_institutions(self, *, search=None, per_page=25, execution=None, no_cache=None):
        """research openalex_institutions: institution candidate search (/institutions?search=
        verbatim name; same-name clones in different countries coexist (a pfizer probe returned
        24 candidates incl. US/UK/FR) — **the candidate list is never auto-picked**: choose the
        ROR explicitly, then query output via openalex_works (adversarial-review constraint 1))."""
        self._research_only("openalex_institutions")
        r = research.openalex.institutions_raw(search, per_page=per_page,
                                                cache=self._c._cache,
                                                no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="openalex_institutions",
            input={"search": search, "per_page": r["params"]["per-page"]},
            reason=(f"OpenAlex institution candidates: '{search}' hit {result['total']}, {result['count']} rows this page"
                    + (f", top relevance {top['display_name']} ({top['ror']}, {top['type']}, "
                       f"{top['works_count']:,} works) — same-name clones in different countries: "
                       "pick the ROR manually, then query output via openalex_works --ror" if top else ", zero hits")),
            result=result,
            evidence=[{"quote": f"{i['display_name']} ({i['ror']}, {i['country_code']} {i['type']}, "
                                f"{i['works_count']:,} works, cited {i['cited_by_count']:,})",
                       "url": i["id"]}
                      for i in result["rows"][:5]],
            provider_id="openalex", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def crossref_works(self, *, query=None, funder=None, award_number=None, rows=25,
                       offset=0, cursor=None, from_pub_date=None, to_pub_date=None,
                       execution=None, no_cache=None):
        """research crossref_works: DOI registry paper search (/works verbatim name; query
        full-text × funder (funder DOI→filter=funder:, the funder-output bridge) × award_number
        (filter=award.number: combined with funder narrows exactly to the award number) ×
        from/to_pub_date (publication window adopted in 0.2.9) combine with AND;
        cursor=deep-pager is the proper deep-paging channel (adopted 0.2.9, "*" for the first
        page/next_cursor to continue, mutually exclusive with offset — the offset channel is
        the way around the 10,000 wall); awards live only inside rows and cannot be selected —
        probe-confirmed)."""
        self._research_only("crossref_works")
        r = research.crossref.works_raw(query, funder=funder, award_number=award_number,
                                         rows=rows, offset=offset, cursor=cursor,
                                         from_pub_date=from_pub_date, to_pub_date=to_pub_date,
                                         cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        cons = []
        if query:
            cons.append(f"full-text '{query}'")
        if funder:
            cons.append(f"funder {funder}")
            if award_number:
                cons.append(f"award {award_number}")
        if from_pub_date or to_pub_date:
            cons.append(f"pub window {from_pub_date or '…'}~{to_pub_date or '…'}")
        return self._flat_env(
            tool="crossref_works",
            input={"query": query, "funder": funder, "award_number": award_number,
                   "rows": r["params"]["rows"],
                   "offset": r["params"].get("offset"), "cursor": cursor,
                   "from_pub_date": from_pub_date, "to_pub_date": to_pub_date},
            reason=(f"Crossref: {' × '.join(cons) or 'hits'} — {result['total']:,} works in total, {result['count']} rows this page"
                    + (f", top hit {top['title'] or '—'} ({top['container_title'] or top['type']}, {top['year']})"
                       if top else ", zero hits")
                    + (", cursor continuation available" if result.get("next_cursor") else
                       (" (cursor last page)" if cursor else ""))),
            result=result,
            evidence=[{"quote": f"{w['title'] or '—'} ({w['container_title'] or w['type'] or '—'}, {w['year']}, "
                                + ("; ".join(f"{f['name']} award {'/'.join(f['award'][:2])}" for f in w["funders"])
                                   if w["funders"] else "no funder block in row") + ")",
                       "url": w["url"] or f"https://doi.org/{w['doi']}"}
                      for w in result["rows"][:5]],
            provider_id="crossref", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def gtr_projects(self, *, q=None, s=20, p=1, execution=None, no_cache=None):
        """research gtr_projects: UK UKRI funded-project search (/projects?q= verbatim three
        params; s≥10 upstream 400 wall (probe showed a friendly error); upstream sends no
        total — a full page signals more via has_more; the organisation edge is a second hop
        in detail (links.link[] rel=LEAD_ORG), this face is the list only)."""
        self._research_only("gtr_projects")
        r = research.gtr.projects_raw(q, s=s, p=p,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="gtr_projects",
            input={"q": q, "s": r["params"]["s"], "p": r["params"]["p"]},
            reason=(f"UKRI GtR: '{q}' — {result['count']} rows this page"
                    + (" (full page, likely more — continue with --p)" if result.get("has_more") else "")
                    + (f", top hit {top['title'] or '—'} ({top['status'] or '—'}, "
                       f"{top['start'] or '?'}→{top['end'] or '?'}, {top['lead_funder'] or '—'})"
                       if top else ", zero hits")),
            result=result,
            evidence=[{"quote": f"{x['title'] or '—'} ({x['status'] or '—'}, "
                                f"{x['start'] or '?'}→{x['end'] or '?'})",
                       "url": x["href"]}
                      for x in result["rows"][:5]],
            provider_id="gtr", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def nih_reporter_publications(self, *, pmids=None, appl_ids=None, limit=25, offset=0,
                                  execution=None, no_cache=None):
        """research nih_reporter_publications: NIH funding↔paper bridge table
        (/v2/publications/search POST; criteria accepts exactly two keys, pmids/appl_ids —
        every other key is **silently ignored** upstream and the whole 8.3M table gets dumped
        (probe-confirmed), hence the local wall = at least one of the two, and no other
        criteria is passed through; rows = the 3-key bridge {coreproject,pmid,applid};
        0 rows = no linkage on record for that project (sparseness is a real answer; Yale
        FY2018 probed with zero linked papers))."""
        self._research_only("nih_reporter_publications")
        r = research.nih_reporter.publications_raw(pmids, appl_ids=appl_ids,
                                                    limit=limit, offset=offset,
                                                    cache=self._c._cache,
                                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        crit = r["params"]["criteria"]
        who = f"pmid {'/'.join(str(x) for x in crit['pmids'])}" if "pmids" in crit \
            else f"appl {crit['appl_ids'][0]}" + (f" and {len(crit['appl_ids'])} items" if len(crit["appl_ids"]) > 1 else "")
        return self._flat_env(
            tool="nih_reporter_publications",
            input={"pmids": r["params"]["criteria"].get("pmids"),
                   "appl_ids": r["params"]["criteria"].get("appl_ids"),
                   "limit": r["params"]["limit"], "offset": r["params"]["offset"]},
            reason=(f"NIH RePORTER bridge: {who} — {result['total']} linked records in total, {result['count']} rows this page"
                    + (f", top hit applid {top['applid']} → pmid {top['pmid']} ({top['coreproject']})"
                       if top else " — 0 rows = no linkage on record for that project (sparse linkage is a real answer, not a failed query)")),
            result=result,
            evidence=[{"quote": f"applid {x['applid']} ↔ pmid {x['pmid']} ({x['coreproject']})",
                       "url": f"https://reporter.nih.gov/project-details/{x['applid']}"}
                      for x in result["rows"][:5]],
            provider_id="nih-reporter", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def icite_pubs(self, *, pmid=None, execution=None, no_cache=None):
        """research icite_pubs: PubMed paper citation-impact card (/pubs?pmids= query-parameter
        single record; RCR/FCR/clinical citations (is_clinical/cited_by_clin_count; the upstream
        cited_by is a pmid array already reduced to a count) — the final impact hop after
        nih_reporter_publications yields a pmid)."""
        self._research_only("icite_pubs")
        r = research.icite.pub_raw(pmid, cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        cb = result["cited_by_count"]
        cb_txt = f"{cb:,}" if isinstance(cb, int) else "—"   # empty card (pmid not in iCite): None must not crash
        rcr = result["relative_citation_ratio"]
        return self._flat_env(
            tool="icite_pubs",
            input={"pmid": result["pmid"]},
            reason=(f"iCite: pmid {result['pmid']} ({result['journal'] or '—'} {result['year'] or '—'}) "
                    f"cited {cb_txt}, RCR {rcr if rcr is not None else '—'}"
                    + (" (incl. clinical citations — cited_by_clin on record)" if result.get("cited_by_clin_count") else "")),
            result=result,
            evidence=[{"quote": f"{(result['title'] or '—')[:80]} (cited {cb_txt}, "
                                f"RCR {rcr if rcr is not None else '—'})",
                       "url": f"https://pubmed.ncbi.nlm.nih.gov/{result['pmid']}/"}],
            provider_id="icite", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def biorxiv_details(self, *, from_date=None, to_date=None, cursor=0, execution=None, no_cache=None):
        """research biorxiv_details: bioRxiv preprint interval metadata stream
        (/details/biorxiv/{from}/{to}/{cursor} verbatim name; authors is a semicolon-joined
        string, jatsxml = a full-text XML link, not inline — the full-text bulk path goes
        through jatsxml_url, this face is metadata only; the messages count strings are already
        normalized)."""
        self._research_only("biorxiv_details")
        r = research.biorxiv.details_raw(from_date, to_date, cursor=cursor,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="biorxiv_details",
            input={"from_date": from_date, "to_date": to_date, "cursor": r["params"]["cursor"]},
            reason=(f"bioRxiv: {from_date}→{to_date} interval holds {result['total']:,} papers, "
                    f"cursor {r['params']['cursor']} page has {result['count']} rows"
                    + (" (a non-empty page may not be the end — continue with --cursor)" if result.get("has_more") else " (empty page = interval exhausted)")
                    + (f", top hit {top['title'] or '—'} ({top['category'] or '—'}, "
                       f"{top['author_corresponding_institution'] or '—'})" if top else ", zero hits")),
            result=result,
            evidence=[{"quote": f"{x['title'] or '—'} ({x['category'] or '—'}, {x['date']}, "
                                f"{x['author_corresponding_institution'] or '—'})",
                       "url": f"https://doi.org/{x['doi']}"}
                      for x in result["rows"][:5]],
            provider_id="biorxiv", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"from_date": from_date, "to_date": to_date,
                                                 "cursor": r["params"]["cursor"]}},
        )

    def opencitations_citations(self, *, doi=None, execution=None, no_cache=None):
        """research opencitations_citations: open citation index COCI (/index/v1/citations/{doi}
        — the full list for one DOI, verbatim name; the doi: prefix is auto-stripped (the
        upstream 400 wall reports the format itself); the upstream limit parameter is silently
        ignored (probe: ?limit=3 still returned all 217 rows) — no fake pagination, the full
        list comes back)."""
        self._research_only("opencitations_citations")
        r = research.opencitations.citations_raw(doi, cache=self._c._cache,
                                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="opencitations_citations",
            input={"doi": result["doi"]},
            reason=(f"OpenCitations COCI: {result['doi']} cited {result['count']} times (full list; "
                    "the upstream limit is silently ignored, no fake pagination)"
                    + (f", latest {top['citing']} ({top['creation']})" if top else " — zero citations is a legitimate answer")),
            result=result,
            evidence=[{"quote": f"{x['citing']} → {x['cited']} ({x['creation']}, OCI {x['oci']})",
                       "url": f"https://doi.org/{x['citing']}"}
                      for x in result["rows"][:5]],
            provider_id="opencitations", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- 0.2.2 flat panel commands (security: OSV / CISA KEV) ----------
