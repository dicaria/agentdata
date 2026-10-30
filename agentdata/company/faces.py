"""company faces — flat face-method mixin (0.2.6 per-domain split, migrated from client.py _Domain).

Mixed into the root _Domain (assembled via MRO, see client.py); discipline: no __init__, depends only on root
internals (_flat_env/_c/_request…), method names globally unique across domains (a collision would shadow another domain's face).
"""
from ..errors import SdkError

from .. import company  # domain-module path invocation (historical shape, kept for minimal churn in C2)

class CompanyFaces:
    def _co_only(self, tool: str):
        if self.name != "company":
            raise SdkError("usage_error", detail=f"{tool} is a company-domain capability (not available on the {self.name} domain)")

    def gleif_lei_records(self, *, lei, execution=None, no_cache=None):
        """company gleif_lei_records: LEI → entity identity card (GLEIF /lei-records/{lei} single-record face; ISO 17442 20-char shape gate)."""
        self._co_only("gleif_lei_records")
        v = str(lei or "").strip().upper()
        if not v:
            raise SdkError("usage_error", provider="gleif", detail="gleif_lei_records requires lei (ISO 17442: 20 alphanumeric chars)")
        r = company.gleif.lookup_lei(v, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        return self._flat_env(
            tool="gleif_lei_records", input={"lei": v},
            reason=(f"GLEIF normalization: LEI {r['lei']} → {r.get('legal_name') or '(no legal name)'}"
                    f" ({r.get('entity_status') or 'unknown status'})"),
            result=result,
            evidence=[{"quote": (f"LEI {r['lei']} = {r.get('legal_name') or '—'}"
                                 f" ({r.get('entity_status') or '—'}, {r.get('jurisdiction') or '—'})"),
                       "url": f"https://api.gleif.org/api/v1/lei-records/{r['lei']}"}],
            provider_id="gleif", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"lei": r["lei"]}},
        )

    def gleif_lei_records_search(self, *, filter_entity_legal_name, page_size=10, execution=None, no_cache=None):
        """company gleif_lei_records_search: company name → LEI candidates (GLEIF filter[entity.legalName] contains match;
        page[size] 1-200 upstream hard wall — probed 201→400, 200 served in full). Candidates are not an authoritative normalization.
        The parameter name is the bracket transcription of upstream filter[entity.legalName] (naming convention §5)."""
        self._co_only("gleif_lei_records_search")
        v = str(filter_entity_legal_name or "").strip()
        if not v:
            raise SdkError("usage_error", provider="gleif",
                           detail="gleif_lei_records_search requires filter_entity_legal_name (company name)")
        size = int(page_size)
        if not 1 <= size <= 200:
            raise SdkError("usage_error", provider="gleif",
                           detail="page_size must be 1-200 (probed: page[size] 201→400, 200 served in full)")
        r = company.gleif.search_lei_by_name(v, limit=size, cache=self._c._cache,
                                               no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        result["limit_applied"] = size
        top = (result["candidates"] or [None])[0]
        return self._flat_env(
            tool="gleif_lei_records_search", input={"filter_entity_legal_name": v, "page_size": size},
            reason=(f"GLEIF reverse name search: {result['total']} candidates, top hit {top['legal_name'] or '—'}"
                    f" (LEI {top['lei']}, {top['entity_status'] or '—'}) — legal-name contains match, not fuzzy tolerance, "
                    f"candidates are not an authoritative normalization; re-verify with gleif_lei_records before persisting"
                    if top else f"GLEIF reverse name search zero hits: {v} (an empty result is a legal answer)"),
            result=result,
            evidence=[{"quote": f"LEI {c['lei']} = {c['legal_name'] or '—'} ({c['entity_status'] or '—'})",
                       "url": f"https://api.gleif.org/api/v1/lei-records/{c['lei']}"}
                      for c in result["candidates"][:5]],
            provider_id="gleif", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"filter[entity.legalName]": v, "page[size]": size}},
        )

    def _gleif_parent_face(self, tool, which, *, lei, no_cache):
        """Shared envelope for gleif_direct_parent / gleif_ultimate_parent (naming convention §4: one command one endpoint, each endpoint gets its own face)."""
        self._co_only(tool)
        v = str(lei or "").strip().upper()
        if not v:
            raise SdkError("usage_error", provider="gleif",
                           detail=f"{tool} requires lei (ISO 17442: 20 alphanumeric chars)")
        fn = (company.gleif.get_direct_parent if which == "direct_parent"
              else company.gleif.get_ultimate_parent)
        r = fn(v, cache=self._c._cache,
               no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        p = r["parent"]
        label = "direct parent" if which == "direct_parent" else "ultimate parent"
        return self._flat_env(
            tool=tool, input={"lei": r["lei"]},
            reason=(f"GLEIF {label}: {r['lei']} → {p['legal_name'] or p['lei']}"
                    if p else f"GLEIF {label}: {r['lei']} none reported (independent entity or simply unreported — an honest 404 null, not an error)"),
            result={"lei": r["lei"], which: p},
            evidence=([{"quote": f"{p['legal_name'] or p['lei']} (LEI {p['lei']}, {p['entity_status'] or '—'})",
                        "url": f"https://api.gleif.org/api/v1/lei-records/{p['lei']}"}] if p else []),
            provider_id="gleif", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"lei": r["lei"],
                                "path": f"/lei-records/{r['lei']}/{which.replace('_', '-')}"}},
        )

    def gleif_direct_parent(self, *, lei, execution=None, no_cache=None):
        """company gleif_direct_parent: LEI → direct parent (GLEIF /lei-records/{lei}/direct-parent dedicated endpoint)."""
        return self._gleif_parent_face("gleif_direct_parent", "direct_parent", lei=lei, no_cache=no_cache)

    def gleif_ultimate_parent(self, *, lei, execution=None, no_cache=None):
        """company gleif_ultimate_parent: LEI → ultimate parent (GLEIF /lei-records/{lei}/ultimate-parent dedicated endpoint)."""
        return self._gleif_parent_face("gleif_ultimate_parent", "ultimate_parent", lei=lei, no_cache=no_cache)

    def fdic_institutions(self, *, search=None, filters=None, limit=5,
                  execution=None, no_cache=None):
        """company fdic_institutions: US insured-bank master lookup (api.fdic.gov /banks/institutions;
        search/filters upstream names (combinable — phrase search 'NAME:\"…\"' / exact-key filters 'CERT:n');
        limit has no upstream wall — 10000 measured, served in full)."""
        self._co_only("fdic_institutions")
        raw_search = str(search or "").strip() or None
        raw_filters = str(filters or "").strip() or None
        if not (raw_search or raw_filters):
            raise SdkError("usage_error", provider="fdic-bankfind",
                           detail="fdic_institutions requires at least one of search / filters "
                                  "(local safety wall: enumerating the whole 27,835-row keyless database is served by the corpus line; the lookup face does not allow bare scans)")
        r = company.fdic_bankfind.institutions_raw(search=raw_search, filters=raw_filters,
                                                     limit=limit, cache=self._c._cache,
                                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["institutions"] or [None])[0]
        quartet = {"source": "raw", "upstream": r["params"]}
        active = "active" if top and top["active"] is True else "closed" if top and top["active"] is False else None
        return self._flat_env(
            tool="fdic_institutions",
            input={"search": raw_search, "filters": raw_filters,
                   "limit": r["params"]["limit"]},
            reason=(f"FDIC BankFind: {result['total']} rows matched"
                    + (f", top hit {top['cert']} {top['name'] or '—'} ({active}"
                       + f"{', ' + top['end_date'] if top['active'] is False and top.get('end_date') else ''}"
                       + f", {top['city'] or '—'} {top['state'] or '—'})" if top else ", zero hits (an empty result is a legal answer)")),
            result=result,
            evidence=[{"quote": f"CERT {b['cert']} = {b['name'] or '—'} ({b['state'] or '—'}, "
                                f"{'active' if b['active'] else 'closed' if b['active'] is False else 'status unknown'})",
                       "url": f"https://banks.data.fdic.gov/bankfind-suite/detail/institution/{b['cert']}"}
                      for b in result["institutions"][:5]],
            provider_id="fdic-bankfind", metas=[r["_meta"]],
            query=quartet,
        )

    def sec_submissions(self, *, cik, execution=None, no_cache=None):
        """company sec_submissions: SEC CIK → registrant identity card (data.sec.gov submissions single record;
        bare digits / leading zeros / the CIK prefix — all three spellings accepted — non-digits stripped, padded to 10)."""
        self._co_only("sec_submissions")
        v = str(cik or "").strip()
        if not v:
            raise SdkError("usage_error", provider="edgar-cik", detail="sec_submissions requires cik (1-10 digits, CIK prefix allowed)")
        r = company.edgar_cik.lookup_cik(v, cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        tk = (f" ({'/'.join(result['tickers'])}·{'/'.join(result['exchanges']) or '?'})"
              if result.get("tickers") else " (no ticker — unlisted or no trading venue registered)")
        return self._flat_env(
            tool="sec_submissions", input={"cik": v},
            reason=(f"SEC normalization: CIK {int(result['cik'])} → {result.get('name') or '(no legal name)'}{tk}"
                    + (f", {result['filer_category']}" if result.get("filer_category") else "")),
            result=result,
            evidence=[{"quote": (f"CIK {result['cik']} = {result.get('name') or '—'} (EIN {result.get('ein') or '—'}"
                                 + (f", SIC {result['sic']['code']} {result['sic'].get('description') or ''}"
                                    if result.get("sic") else "")
                                 + f"; filings total {result['filings_total']})"),
                       "url": f"https://data.sec.gov/submissions/CIK{result['cik']}.json"}],
            provider_id="edgar-cik", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"cik10": result["cik"]}},
        )

    def ror_organizations(self, *, query=None, ror_id=None, page=None, all_status=None,
                          execution=None, no_cache=None):
        """company ror_organizations: research-org master record (ROR v2; query search face XOR ror_id single-record face —
        two separate upstream endpoints; all_status added in the 0.2.9 audit — upstream default returns only active,
        inactive/withdrawn are hidden wholesale by default)."""
        self._co_only("ror_organizations")
        q = str(query or "").strip() or None
        rid = str(ror_id or "").strip() or None
        if q and rid:
            raise SdkError("usage_error", provider="ror",
                           detail="query (search face) and ror_id (single-record face) are mutually exclusive — upstream is two endpoints, give exactly one of the two required")
        if not q and not rid:
            raise SdkError("usage_error", provider="ror", detail="ror_organizations requires query (org name) or ror_id (0+8 chars)")
        if rid and all_status is not None:
            raise SdkError("usage_error", provider="ror",
                           detail="all_status belongs to the search face (query) only — the single-record face (ror_id) has no such upstream param")
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        if rid:
            r = company.ror.lookup_ror(rid, cache=cache, no_cache=nc)
            upstream = {"id": f"https://ror.org/{(r['candidates'] or [{}])[0].get('ror_id') or rid.lower()}"}
        else:
            r = company.ror.search_orgs(q, page=page, all_status=all_status, cache=cache, no_cache=nc)
            upstream = {"query": q, **({"page": int(page)} if page is not None else {}),
                        **({"all_status": "true" if all_status else "false"} if all_status is not None else {})}
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["candidates"] or [None])[0]
        mode = "id normalization" if rid else "name search"
        return self._flat_env(
            tool="ror_organizations", input={"query": q, "ror_id": rid, "page": page, "all_status": all_status},
            reason=(f"ROR {mode}: {'ROR id ' + rid if rid else f'\"{q}\"'} → {top['name'] or '—'}"
                    f" ({top['country'] or '—'}, {top['type'] or '—'}"
                    + (f"; parent org {top['parent']['name'] or '—'}" if top.get("parent") else "")
                    + f") — {'authoritative single record' if rid else 'candidates, not an authoritative normalization (fixed 20 rows/page)'}"
                    if top else (f"ROR zero hits: no such ROR id ({rid})" if rid
                                 else f"ROR zero hits: \"{q}\" is not in the research-org master record (an empty result is a legal answer; for purely commercial entities use gleif_lei_records_search)")),
            result=result,
            evidence=[{"quote": (f"{c['ror_id'] or '—'} = {c['name'] or '—'} ({c['country'] or '—'}, {c['type'] or '—'})"),
                       "url": f"https://ror.org/{c['ror_id'] or ''}"}
                      for c in result["candidates"][:5]],
            provider_id="ror", metas=[r["_meta"]],
            query={"source": "raw", "upstream": upstream},
        )

    def vies_vat(self, *, vat, execution=None, no_cache=None):
        """company vies_vat: EU VAT number online validation (official VIES face; INVALID is a legal answer, not an error;
        member-state masked name/address '---' → null, not missing data)."""
        self._co_only("vies_vat")
        v = str(vat or "").strip()
        if not v:
            raise SdkError("usage_error", provider="vies", detail="vies_vat requires vat (with member-state prefix, e.g. DE811907980)")
        r = company.vies.check_vat(v, cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        cc, number = company.vies.parse_vat(v)
        masked = ", member-state masked name/address (--- → null, not missing data)" if result["valid"] and not result["name"] else ""
        addr = str(result["address"] or "").split(chr(10))[0][:80]
        return self._flat_env(
            tool="vies_vat", input={"vat": v.upper()},
            reason=(f"VIES check: {result['vat_number']} valid ({result['country_code']}"
                    + (f" → {result['name']}" if result["name"] else masked) + ")"
                    if result["valid"] else
                    f"VIES check: {result['vat_number']} invalid/unregistered (userError={result['user_error'] or '—'} — this is a legal answer, not an error)"),
            result=result,
            evidence=[{"quote": f"{result['vat_number']} = {'valid' if result['valid'] else 'invalid'}"
                                + (f": {result['name']}" if result["name"] else "")
                                + (f", {addr}" if result["address"] else "")
                                + (f" (audit trace {result['request_identifier']})" if result.get("request_identifier") else ""),
                       "url": f"https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{cc}/vat/{number}"}],
            provider_id="vies", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"cc": cc, "number": number}},
        )

    def usaspending_spending_by_award(self, *, recipient_search_text, award_type_codes=None, start_date=None,
                           end_date=None, fields=None, limit=10, page=1, subawards=False,
                           execution=None, no_cache=None):
        """company usaspending_spending_by_award: federal contracts/grants by recipient (spending_by_award POST params
        verbatim; recipient_search_text has upstream array semantics — a scalar is auto-wrapped; time_period auto-fills
        a single end)."""
        self._co_only("usaspending_spending_by_award")
        q = str(recipient_search_text or "").strip()
        if not q:
            raise SdkError("usage_error", provider="usaspending",
                           detail="usaspending_spending_by_award requires recipient_search_text (recipient name)")
        r = company.usaspending.awards_raw(q, award_type_codes=award_type_codes,
                                             start_date=start_date, end_date=end_date,
                                             fields=fields, limit=limit, page=page,
                                             subawards=subawards, cache=self._c._cache,
                                             no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        dr = result.get("date_range")
        span = f", recipient period {dr['startdt']}~{dr['enddt']}" if dr else ""
        types_note = ",".join(r["params"]["filters"]["award_type_codes"])
        return self._flat_env(
            tool="usaspending_spending_by_award",
            input={"recipient_search_text": q, "award_type_codes": types_note,
                   "start_date": start_date, "end_date": end_date,
                   "limit": r["params"]["limit"], "page": r["params"]["page"],
                   "subawards": r["params"]["subawards"]},
            reason=(f"USAspending: \"{q}\" type {types_note}, {len(result['awards'])} rows{span}"
                    f"{' (page_metadata.hasNext=more available, continue with --page)' if result.get('has_more') else ''}"
                    f" — name-matched recipients, parent/subsidiary groups not merged; narrow by CIK/UEI before persisting"),
            result=result,
            evidence=[{"quote": f"{w['award_id'] or '—'} = {w['recipient_name'] or '—'}"
                                f" (${w['award_amount'] or '—'}, {w['awarding_agency'] or '—'})",
                       "url": "https://www.usaspending.gov/"}
                      for w in result["awards"][:5]],
            provider_id="usaspending", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def ted_notices_search(self, *, query=None, fields=None,
                    limit=10, page=1, execution=None, no_cache=None):
        """company ted_notices_search: EU procurement notices (TED v3 expert search POST;
        query = expert-syntax verbatim channel (buyer face organisation-name-buyer=*/organisation-country-buyer=,
        classification-cpv=); limit 1-250 upstream hard wall, measured 2026-10-23)."""
        self._co_only("ted_notices_search")
        q = str(query or "").strip() or None
        if not q:
            raise SdkError("usage_error", provider="ted",
                           detail="ted_notices_search requires query (expert syntax, e.g. organisation-name-buyer=Siemens*)")
        r = company.ted.search_raw(q, fields=fields, limit=limit, page=page,
                                     cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        quartet = {"source": "raw", "search": q, "upstream": r["params"]}
        return self._flat_env(
            tool="ted_notices_search",
            input={"query": q,
                   "limit": r["params"]["limit"], "page": r["params"]["page"]},
            reason=(f"TED v3: \"{q}\" {len(result['notices'])} rows"
                    f"{' (full page, more may exist — limit cap 250)' if result.get('has_more') else ''}"
                    f" — name-prefix match on the buyer face (trailing wildcard), parent/subsidiary groups not merged; narrow by VAT/LEI before persisting"),
            result=result,
            evidence=[{"quote": f"{n['publication_number'] or '—'} = {n['buyer'] or '—'}"
                                f" ({n['buyer_country'] or '—'}, {n['notice_type'] or '—'}, {n['publication_date'] or '—'})",
                       "url": f"https://ted.europa.eu/udl?srcid={n['publication_number'] or ''}"}
                      for n in result["notices"][:5]],
            provider_id="ted", metas=[r["_meta"]],
            query=quartet,
        )

    def gb_fts_release_packages(self, *, name=None, stages="award", limit=10, cursor=None,
                       updated_from=None, updated_to=None, execution=None, no_cache=None):
        """company gb_fts_release_packages: UK WTO-line procurement (FTS OCDS five params verbatim;
        upstream has no name-search param — name is a client-side contains filter (convenience: always fetch the full
        100-row page then filter, matching either the buyer or supplier side)."""
        self._co_only("gb_fts_release_packages")
        nm = str(name or "").strip() or None
        fetch_limit = 100 if nm else limit  # name-filter line "always fetch the full 100 then filter" (fetching the original page at limit then filtering is almost guaranteed empty)
        r = company.fts.releases_raw(stages=stages, limit=fetch_limit, cursor=cursor,
                                       updated_from=updated_from, updated_to=updated_to,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows, matched_on = r["rows"], None
        if nm:
            q = nm.lower()
            rows = [x for x in r["rows"]
                    if q in str(x.get("buyer") or "").lower()
                    or any(q in str(s or "").lower() for s in (x.get("suppliers") or []))][:int(limit)]
            matched_on = "buyer|suppliers contains"
        result = {"rows": rows, "next_cursor": r["next_cursor"], "has_more": r["has_more"],
                  "total_in_page": len(r["rows"])}
        if matched_on:
            result["matched_on"] = matched_on
        quartet = {"source": "assembled" if nm else "raw", "upstream": r["params"]}
        if nm:
            quartet["assembled_from"] = {"name": nm, "fetch_limit_forced": 100,
                                         "filter": "client-side contains"}
        return self._flat_env(
            tool="gb_fts_release_packages",
            input={"name": nm, "stages": r["params"]["stages"], "limit": int(limit),
                   "cursor": cursor, "updated_from": updated_from, "updated_to": updated_to},
            reason=(f"UK FTS: \"{nm}\" matched {len(rows)} rows / original page {len(r['rows'])} rows ({matched_on}"
                    + (", next page available to walk" if r.get("next_cursor") else ", last page")
                    + ") — the OCDS face has no name-search param; contains-matching is the agreed sense, not a defect"
                    if nm else
                    f"UK FTS: {len(rows)} rows (stages={r['params']['stages']}"
                    + (", next page available to walk" if r.get("next_cursor") else ", last page") + ")"),
            result=result,
            evidence=[{"quote": f"{n['ocid'] or '—'} = {n['buyer'] or '—'} × "
                                f"{' / '.join(n['suppliers']) or '(not awarded)'} ({n['date'] or '—'})",
                       "url": f"https://www.find-tender.service.gov.uk/Search/Results?stages={r['params']['stages']}"}
                      for n in rows[:5]],
            provider_id="fts", metas=[r["_meta"]],
            query=quartet,
        )

    def gb_contracts_finder_published_notices(self, *, name=None, published_from=None, published_to=None,
                            stages=None, limit=10, cursor=None, execution=None, no_cache=None):
        """company gb_contracts_finder_published_notices: UK below-threshold small contracts (CF OCDS params verbatim;
        publishedFrom/To bare dates are legal — the opposite of FTS's full-timestamp requirement; both-default = rolling
        7-day window (our default; upstream is always empty without a window);
        stages=tender|award added in the 0.2.9 audit (upstream 400 self-validates, default = mixed feed);
        name = client-side contains filter (convenience: always fetch the full 100-row page then filter)."""
        self._co_only("gb_contracts_finder_published_notices")
        nm = str(name or "").strip() or None
        fetch_limit = 100 if nm else limit
        r = company.cf.search_raw(published_from=published_from, published_to=published_to,
                                    limit=fetch_limit, cursor=cursor, stages=stages,
                                    cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows, matched_on = r["rows"], None
        if nm:
            q = nm.lower()
            rows = [x for x in r["rows"]
                    if q in str(x.get("buyer") or "").lower()
                    or any(q in str(s or "").lower() for s in (x.get("suppliers") or []))][:int(limit)]
            matched_on = "buyer|suppliers contains"
        win = r["window"]
        result = {"rows": rows, "next_cursor": r["next_cursor"], "has_more": r["has_more"],
                  "total_in_page": len(r["rows"]), "window": win}
        if matched_on:
            result["matched_on"] = matched_on
        quartet = {"source": "assembled" if nm else "raw", "upstream": r["params"]}
        if nm:
            quartet["assembled_from"] = {"name": nm, "fetch_limit_forced": 100,
                                         "filter": "client-side contains"}
        window_note = (f" (window {win['published_from']}~{win['published_to']}"
                       + ("=our default rolling 7 days" if not (published_from or published_to) else "") + ")")
        return self._flat_env(
            tool="gb_contracts_finder_published_notices",
            input={"name": nm, "published_from": published_from, "published_to": published_to,
                   "stages": stages, "limit": int(limit), "cursor": cursor},
            reason=(f"UK CF: \"{nm}\" matched {len(rows)} rows / original page {len(r['rows'])} rows ({matched_on}"
                    + (", next page available to walk" if r.get("next_cursor") else ", last page")
                    + f"; window {win['published_from']}~{win['published_to']})"
                    + " — the below-threshold face complements FTS; supplier id is the GB-COH/GB-CFS registry key"
                    if nm else
                    f"UK CF: {len(rows)} rows{window_note}"
                    + (", next page available to walk (carry the same window when walking)" if r.get("next_cursor") else ", last page")),
            result=result,
            evidence=[{"quote": f"{n['ocid'] or '—'} = {n['buyer'] or '—'} × "
                                f"{' / '.join(n['suppliers']) or '(not awarded)'} ({n['date'] or '—'})",
                       "url": "https://www.contractsfinder.service.gov.uk/"}
                      for n in rows[:5]],
            provider_id="cf", metas=[r["_meta"]],
            query=quartet,
        )

    def sec_fulltext_search(self, *, q, forms=None, startdt=None, enddt=None, limit=10,
                execution=None, no_cache=None):
        """company sec_fulltext_search: SEC filing full-text search 2001+ (EDGAR FTS four params verbatim;
        either startdt/enddt given → the other is auto-filled — a single end is silently ignored upstream
        (measured 2026-10-20); after filling, both ends are always present)."""
        self._co_only("sec_fulltext_search")
        v = str(q or "").strip()
        if not v:
            raise SdkError("usage_error", provider="edgar-fts", detail="sec_fulltext_search requires q (EDGAR FTS syntax)")
        r = company.edgar_fts.search_raw(v, forms=forms, startdt=startdt, enddt=enddt,
                                           limit=limit, cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        dr = result.get("date_range")
        span = f", window {dr['startdt']}~{dr['enddt']}" if dr else ""
        cap = ", capped at ≥ this count" if result.get("total_relation") == "gte" else ""
        return self._flat_env(
            tool="sec_fulltext_search", input={"q": v, "forms": forms, "startdt": startdt, "enddt": enddt,
                                   "limit": result["limit_applied"]},
            reason=(f"EDGAR FTS: {result['total']} hits (2001+ full-text{cap}{span}), "
                    f"returning {len(result['hits'])} rows — adsh shares its key with the SEC corpus line"),
            result=result,
            evidence=[{"quote": f"{h['form_type'] or '—'} {h['adsh'] or '—'} = "
                                f"{h['company'] or '—'} ({h['file_date'] or '—'})",
                       "url": h["doc_url"] or "https://efts.sec.gov/LATEST/search-index"}
                      for h in result["hits"][:5]],
            provider_id="edgar-fts", metas=[r["_meta"]],
            query={"source": "raw", "search": v, "upstream": r["params"]},
        )

    # ---------- 0.3.3 European national registry live faces (CH Zefix / NO Brreg / FI YTJ) ----------

    def ch_zefix_firm_search(self, *, name, max_entries=100, offset=0,
                     execution=None, no_cache=None):
        """company ch_zefix_firm_search: Swiss commercial register name search (Zefix POST search.json three params
        verbatim; name is a contains-match that also hits historical names — candidates are not an authoritative
        normalization)."""
        self._co_only("ch_zefix_firm_search")
        v = str(name or "").strip()
        if not v:
            raise SdkError("usage_error", provider="ch_zefix", detail="ch_zefix_firm_search requires name (company name)")
        n = min(max(1, int(max_entries or 100)), 100)
        off = max(0, int(offset or 0))
        r = company.ch_zefix.search_firms(v, max_entries=n, offset=off,
                                             cache=self._c._cache,
                                             no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["firms"] or [None])[0]
        return self._flat_env(
            tool="ch_zefix_firm_search", input={"name": v, "max_entries": n, "offset": off},
            reason=(f"Zefix search: {len(result['firms'])} candidates"
                    + (f", top hit {top['name']} (uid {top['uid'] or '—'}, {top['status'] or '—'}, {top['legal_seat'] or '—'})"
                       if top else "") + " — contains-match, not an authoritative normalization; the three keys (ehraid/uid/chid) are surfaced directly"
                    if top else f"Zefix search zero hits: \"{v}\" (an empty result is a legal answer)"),
            result=result,
            evidence=[{"quote": (f"{f['name']} (ehraid {f['ehraid']}, uid {f['uid'] or '—'}, "
                                 f"{f['status'] or '—'}, {f['legal_seat'] or '—'})"),
                       "url": f"https://www.zefix.ch/ZefixREST/api/v1/firm/{f['ehraid']}.json"}
                      for f in result["firms"][:5]],
            provider_id="ch_zefix", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def ch_zefix_firm(self, *, ehraid, execution=None, no_cache=None):
        """company ch_zefix_firm: full record card by ehraid (Zefix /firm/{ehraid}.json; oldNames + M&A edges)."""
        self._co_only("ch_zefix_firm")
        v = str(ehraid or "").strip()
        if not v.isdigit():
            raise SdkError("usage_error", provider="ch_zefix",
                           detail=f"ch_zefix_firm requires ehraid (numeric master id, surfaced by search rows), got \"{ehraid}\"")
        r = company.ch_zefix.get_firm(v, cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        f = r["firm"]
        edges = (f"; predecessors {len(f['has_taken_over'])} / successors {len(f['taken_over_by'])} M&A edges"
                 if (f["has_taken_over"] or f["taken_over_by"]) else "")
        evidence = [{"quote": f"{f['name'] or '—'} ({f['status'] or '—'}, {f['legal_seat'] or '—'})",
                     "url": f"https://www.zefix.ch/ZefixREST/api/v1/firm/{f['ehraid'] or v}.json"}]
        if f["taken_over_by"]:
            e = f["taken_over_by"][0]
            evidence.append({"quote": f"successor edge: taken over by {e.get('name') or '—'} (ehraid {e.get('ehraid')})",
                             "url": f"https://www.zefix.ch/ZefixREST/api/v1/firm/{e.get('ehraid')}.json"})
        elif f["has_taken_over"]:
            e = f["has_taken_over"][0]
            evidence.append({"quote": f"predecessor edge: has taken over {e.get('name') or '—'} (ehraid {e.get('ehraid')})",
                             "url": f"https://www.zefix.ch/ZefixREST/api/v1/firm/{e.get('ehraid')}.json"})
        return self._flat_env(
            tool="ch_zefix_firm", input={"ehraid": v},
            reason=(f"Zefix single record: {f['name'] or '(no name)'} (uid {f['uid'] or '—'}, {f['status'] or '—'}, "
                    f"{f['legal_seat'] or '—'}){edges} — purpose/oldNames full text included"),
            result=f,
            evidence=evidence,
            provider_id="ch_zefix", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"ehraid": f["ehraid"]}},
        )

    def no_brreg_enheter(self, *, navn=None, organisasjonsnummer=None, page=0, size=20,
                     execution=None, no_cache=None):
        """company no_brreg_enheter: Norwegian registry master record (Enhetsregisteret; navn search face XOR org-number
        single-record face — two separate upstream endpoints; page/size 0-based HAL pagination belongs to the search face)."""
        self._co_only("no_brreg_enheter")
        q = str(navn or "").strip() or None
        org = str(organisasjonsnummer or "").replace(" ", "").strip() or None
        if q and org:
            raise SdkError("usage_error", provider="no_brreg",
                           detail="navn (search face) and organisasjonsnummer (single-record face) are mutually exclusive — upstream is two endpoints, give exactly one of the two required")
        if not q and not org:
            raise SdkError("usage_error", provider="no_brreg",
                           detail="no_brreg_enheter requires navn (name search) or organisasjonsnummer (9-digit org number)")
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        if org:
            if not org.isdigit() or len(org) != 9:
                raise SdkError("usage_error", provider="no_brreg",
                               detail=f"organisasjonsnummer must be 9 digits (Norwegian org number), got \"{organisasjonsnummer}\"")
            r = company.no_brreg.get_enhet(org, cache=cache, no_cache=nc)
            result = {"enhet": r["enhet"]}
            upstream = {"organisasjonsnummer": org}
            top = r["enhet"]
            head = (f"single record {top['organisasjonsnummer']} = {top['navn'] or '—'}"
                    f" ({top['organisasjonsform']['beskrivelse'] or '—'}, {top['naeringskode1']['kode'] or '—'}"
                    + (f", {top['antall_ansatte']} employees" if top.get("antall_ansatte") is not None else "") + ")")
        else:
            p, s = max(0, int(page or 0)), min(max(1, int(size or 20)), 100)
            r = company.no_brreg.search_enheter(q, page=p, size=s, cache=cache, no_cache=nc)
            result = {"enheter": r["enheter"], "page": r["page"]}
            upstream = r["params"]
            top = (r["enheter"] or [None])[0]
            head = (f"{result['page']['total_elements'] if result['page']['total_elements'] is not None else len(r['enheter'])} companies matched"
                    + (f", top hit {top['navn'] or '—'} ({top['organisasjonsnummer']})" if top else " (zero hits is a legal answer)"))
        mode = "id normalization" if org else "name search"
        return self._flat_env(
            tool="no_brreg_enheter", input={"navn": q, "organisasjonsnummer": org,
                                   "page": page if not org else None, "size": size if not org else None},
            reason=(f"Brreg {mode}: {head} — navn is the verbatim Norwegian param (?name= 400s)"),
            result=result,
            evidence=[{"quote": (f"{(top or {}).get('organisasjonsnummer') or '—'} = "
                                 f"{(top or {}).get('navn') or '—'}"
                                 f" ({(top.get('organisasjonsform') or {}).get('beskrivelse') or '—'}, "
                                 f"{(top.get('naeringskode1') or {}).get('kode') or '—'})"),
                       "url": f"https://data.brreg.no/enhetsregisteret/api/enheter/"
                              f"{(top or {}).get('organisasjonsnummer') or ''}"}
                      for top in (result.get("enheter") or ([result.get("enhet")] if result.get("enhet") else []))[:5]
                      if top],
            provider_id="no_brreg", metas=[r["_meta"]],
            query={"source": "raw", "upstream": upstream},
        )

    def no_brreg_roller(self, *, organisasjonsnummer, execution=None, no_cache=None):
        """company no_brreg_roller: org number → roles face (Enhetsregisteret /roller; DAGL CEO / STYR board /
        REVI auditor groups; person rows = name + birth date (no national id number on the public face), corporate
        rows = org number; avregistrert = retired)."""
        self._co_only("no_brreg_roller")
        v = str(organisasjonsnummer or "").replace(" ", "").strip()
        if not v.isdigit() or len(v) != 9:
            raise SdkError("usage_error", provider="no_brreg",
                           detail=f"no_brreg_roller requires organisasjonsnummer (9-digit Norwegian org number), got \"{organisasjonsnummer}\"")
        r = company.no_brreg.get_roller(v, cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        groups = r["rollegrupper"]
        roles_n = sum(len(g["roller"]) for g in groups)
        persons = [m["person"]["navn"] for g in groups for m in g["roller"] if m.get("person")]
        return self._flat_env(
            tool="no_brreg_roller", input={"organisasjonsnummer": v},
            reason=(f"Brreg roles face: {v} → {len(groups)} groups, {roles_n} seats"
                    + (f" ({'; '.join(persons[:3])}{'…' if len(persons) > 3 else ''})" if persons else "")
                    + " — name + birth date are collectible (no national id number on the public face); avregistrert=true = retired"),
            result={"organisasjonsnummer": v, "rollegrupper": groups},
            evidence=[{"quote": (f"{g['type_beskrivelse'] or g['type_kode']}: "
                                 + "; ".join((m.get("person") or {}).get("navn")
                                             or f"enhet {m.get('enhet_organisasjonsnummer')}"
                                             or m.get("kode") or "—" for m in g["roller"][:3])),
                       "url": f"https://data.brreg.no/enhetsregisteret/api/enheter/{v}/roller"}
                      for g in groups[:5]],
            provider_id="no_brreg", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"organisasjonsnummer": v}},
        )

    def fi_ytj_companies(self, *, name=None, business_id=None,
                     execution=None, no_cache=None):
        """company fi_ytj_companies: Finnish YTJ business master (PRH v3 one endpoint, two lookups; name search face
        XOR businessId direct face; names[] = versioned name history; **pagination params are silently ignored
        upstream — page size is always ~63 rows, total_results is the real total**)."""
        self._co_only("fi_ytj_companies")
        nm = str(name or "").strip() or None
        bid = str(business_id or "").replace(" ", "").strip() or None
        if bool(nm) == bool(bid):
            raise SdkError("usage_error", provider="fi_ytj",
                           detail="name (search face) and business_id (direct face) — provide exactly one of the two required")
        r = company.fi_ytj.search_companies(nm, bid, cache=self._c._cache,
                                               no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["companies"] or [None])[0]
        mode = "id normalization" if bid else "name search"
        return self._flat_env(
            tool="fi_ytj_companies", input={"name": nm, "business_id": bid},
            reason=(f"YTJ {mode}: \"{nm or bid}\" → {result['total_results'] if result['total_results'] is not None else len(result['companies'])} companies"
                    + (f" (returning {len(result['companies'])} rows — pagination params ignored upstream, page size always ~63)"
                       if result["total_results"] is not None and result["total_results"] > len(result["companies"]) else "")
                    + (f", top hit {top['latest_name'] or '—'} ({top['business_id']}, status {top['status'] or '—'})"
                       if top else " (zero hits is a legal answer)")
                    + " — name matches historical/branch names by contains"),
            result=result,
            evidence=[{"quote": (f"{c.get('business_id')} = {c.get('latest_name') or '—'}"
                                 f" ({(c.get('main_business_line') or {}).get('code') or '—'}, "
                                 f"{(c.get('main_business_line') or {}).get('description') or '—'})"),
                       "url": f"https://avoindata.prh.fi/opendata-ytj-api/v3/companies?businessId={c.get('business_id')}"}
                      for c in result["companies"][:5]],
            provider_id="fi_ytj", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- 0.3.4 FR annuaire live search face (recherche-entreprises) ----------

    def fr_recherche_search(self, *, q, page=None, per_page=10, etat_administratif=None,
                            execution=None, no_cache=None):
        """company fr_recherche_search: French annuaire-entreprises official aggregate search (q takes name/officer
        name/SIREN alike; per_page hard wall 1-25; etat_administratif A active / C ceased is a true filter)."""
        self._co_only("fr_recherche_search")
        v = str(q or "").strip()
        pp = int(per_page if per_page is not None else 10)
        ea = str(etat_administratif).strip().upper() if etat_administratif is not None else None
        r = company.fr_recherche.search(v, page=page, per_page=pp, etat_administratif=ea,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["results"] or [None])[0]
        nd = len(top.get("dirigeants") or []) if top else 0
        return self._flat_env(
            tool="fr_recherche_search",
            input={"q": v, "page": page, "per_page": pp, "etat_administratif": ea},
            reason=(f"FR recherche: \"{v}\" → {result['total_results'] if result['total_results'] is not None else len(result['results'])} companies"
                    + (f" (page {result['page']}/{result['total_pages']})" if result.get("total_pages") else "")
                    + (f", top hit {top['nom_complet'] or '—'} (SIREN {top['siren']}, {top['etat_administratif'] or '—'}"
                       f"{', dirigeants ' + str(nd) + ' rows' if nd else ''})" if top else " (zero hits is a legal answer)")
                    + (", ceased rows only" if ea == "C" else ", active rows only" if ea == "A" else "")
                    + " — q takes name/officer name/SIREN alike"),
            result=result,
            evidence=[{"quote": (f"{c['siren']} = {c['nom_complet'] or '—'}"
                                 f" ({c['categorie_entreprise'] or '—'}, {c['nature_juridique'] or '—'}"
                                 f"{(', dirigeants ' + str(len(c.get('dirigeants') or [])) + ' rows') if c.get('dirigeants') else ''})"),
                       "url": f"https://recherche-entreprises.api.gouv.fr/search?q={c['siren']}"}
                      for c in result["results"][:5]],
            provider_id="fr_recherche", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- 0.2.0 flat panel commands (esg: source-qualified names + upstream param names + our defaults) ----------
