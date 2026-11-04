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
        """company gleif_lei_records: LEI → entity identity card (GLEIF /lei-records/{lei} single-record face; ISO 17442 20-char
        shape gate). 2026-10-30 param-fidelity round: the card additionally surfaces bic/mic, legal_form{elf id, other},
        expiration{date, reason} and successor_entities (successor LEI list — the M&A successor edge, resolve each via
        this same face)."""
        self._co_only("gleif_lei_records")
        v = str(lei or "").strip().upper()
        if not v:
            raise SdkError("usage_error", provider="gleif", detail="gleif_lei_records requires lei (ISO 17442: 20 alphanumeric chars)")
        r = company.gleif.lookup_lei(v, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        succ = result.get("successor_entities") or []
        return self._flat_env(
            tool="gleif_lei_records", input={"lei": v},
            reason=(f"GLEIF normalization: LEI {r['lei']} → {r.get('legal_name') or '(no legal name)'}"
                    f" ({r.get('entity_status') or 'unknown status'})"
                    + (f"; {len(succ)} successor entity LEI(s) on record (M&A successor edge): {', '.join(succ[:3])}"
                       if succ else "")),
            result=result,
            evidence=[{"quote": (f"LEI {r['lei']} = {r.get('legal_name') or '—'}"
                                 f" ({r.get('entity_status') or '—'}, {r.get('jurisdiction') or '—'})"),
                       "url": f"https://api.gleif.org/api/v1/lei-records/{r['lei']}"}],
            provider_id="gleif", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"lei": r["lei"]}},
        )

    def gleif_lei_records_search(self, *, filter_entity_legal_name, page_size=10, filter_entity_jurisdiction=None,
                                 filter_entity_status=None, page_number=None, execution=None, no_cache=None):
        """company gleif_lei_records_search: company name → LEI candidates (GLEIF filter[entity.legalName] contains match;
        page[size] 1-200 upstream hard wall — probed 201→400, 200 served in full). Candidates are not an authoritative normalization.
        The parameter names are bracket transcriptions of upstream filter[entity.legalName]/filter[entity.jurisdiction]/
        filter[entity.status] (naming convention §5). 2026-10-30 param-fidelity round: jurisdiction (ISO country or
        region code, CH/US-MO — probed US-MO→Nestlé Purina registeredAs=00007498), status (ACTIVE/INACTIVE/NULL entity
        lifecycle — LAPSED is registration.status, a different field), page_number (walk while page <= page.lastPage)."""
        self._co_only("gleif_lei_records_search")
        v = str(filter_entity_legal_name or "").strip()
        if not v:
            raise SdkError("usage_error", provider="gleif",
                           detail="gleif_lei_records_search requires filter_entity_legal_name (company name)")
        size = int(page_size)
        if not 1 <= size <= 200:
            raise SdkError("usage_error", provider="gleif",
                           detail="page_size must be 1-200 (probed: page[size] 201→400, 200 served in full)")
        j = str(filter_entity_jurisdiction or "").strip().upper() or None   # normalize before the call so the
        s = str(filter_entity_status or "").strip().upper() or None         # upstream echo equals what was sent
        extra = {}
        if j:
            extra["jurisdiction"] = j
        if s:
            extra["status"] = s
        if page_number is not None:
            if int(page_number) < 1:
                raise SdkError("usage_error", provider="gleif",
                               detail="page_number is 1-based (upstream param: page[number])")
            extra["page_number"] = int(page_number)
        r = company.gleif.search_lei_by_name(v, limit=size, cache=self._c._cache,
                                               no_cache=self._c.no_cache if no_cache is None else bool(no_cache), **extra)
        result = {k: x for k, x in r.items() if k != "_meta"}
        result["limit_applied"] = size
        top = (result["candidates"] or [None])[0]
        scope = (f", filtered to jurisdiction {j}" if j else "") + (f", entity status {s}" if s else "")
        up_query = {"filter[entity.legalName]": v, "page[size]": size}
        if j:
            up_query["filter[entity.jurisdiction]"] = j
        if s:
            up_query["filter[entity.status]"] = s
        if "page_number" in extra:
            up_query["page[number]"] = extra["page_number"]
        inp = {"filter_entity_legal_name": v, "page_size": size,
               **({"filter_entity_jurisdiction": j} if j else {}),
               **({"filter_entity_status": s} if s else {}),
               **({"page_number": extra["page_number"]} if "page_number" in extra else {})}
        return self._flat_env(
            tool="gleif_lei_records_search", input=inp,
            reason=(f"GLEIF reverse name search: {result['total']} candidates{scope}, top hit {top['legal_name'] or '—'}"
                    f" (LEI {top['lei']}, {top['entity_status'] or '—'})"
                    + (f", registered as {top['registered_as']}" if top.get("registered_as") else "")
                    + " — legal-name contains match, not fuzzy tolerance, "
                    f"candidates are not an authoritative normalization; re-verify with gleif_lei_records before persisting"
                    if top else f"GLEIF reverse name search zero hits: {v}{scope} (an empty result is a legal answer)"),
            result=result,
            evidence=[{"quote": f"LEI {c['lei']} = {c['legal_name'] or '—'} ({c['entity_status'] or '—'}"
                               + (f", registered as {c['registered_as']}" if c.get("registered_as") else "") + ")",
                       "url": f"https://api.gleif.org/api/v1/lei-records/{c['lei']}"}
                      for c in result["candidates"][:5]],
            provider_id="gleif", metas=[r["_meta"]],
            query={"source": "raw", "upstream": up_query},
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
        subject = "ROR id " + rid if rid else f'"{q}"'
        return self._flat_env(
            tool="ror_organizations", input={"query": q, "ror_id": rid, "page": page, "all_status": all_status},
            reason=(f"ROR {mode}: {subject} → {top['name'] or '—'}"
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

    # ---------- 0.3.11 CO RUES + KR hometax dual-country batch (LatAm/Korea company master & status faces) ----------

    def co_rues_companies(self, where=None, *, limit=20, offset=0, order=None,
                          execution=None, no_cache=None):
        """company co_rues_companies: Colombia RUES commercial-registry master (datos.gov.co Socrata c82u-588k;
        where â $where raw SoQL verbatim channel; limit/offset/order mirrored by name). 9.44M-row corpus â
        matricula registry key x numero_identificacion (NIT tax id) x CIIU industry x legal form x RL officer-name edge;
        **default base filter admits tax-entity rows only + RL cedula-number column stripped (PII double gate)**."""
        self._co_only("co_rues_companies")
        r = company.co_rues.companies_raw(where, limit=limit, offset=offset, order=order,
                                          cache=self._c._cache,
                                          no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        if rows:
            reason = (f"CO RUES registry master: {len(rows)} rows returned (from offset={offset}; Socrata echoes no total)"
                      f" â matricula x NIT x CIIU (sample {rows[0].get('razon_social') or 'â'}, "
                      f"NIT {rows[0].get('numero_identificacion') or 'â'}, "
                      f"{rows[0].get('organizacion_juridica') or 'â'})"
                      f"; base filter clase_identificacion='NIT' (sole-proprietor personal-id rows stay out of the face), RL number column stripped")
        else:
            reason = ("CO RUES: 0 rows â the where filter matched nothing or offset is past the end; both are legal answers (not errors); "
                      "base filter clase_identificacion='NIT' always on (sole proprietors go through the bulk line, not this face)")
        ev = [{"quote": f"{x.get('matricula') or 'â'} {x.get('razon_social') or 'â'} â "
                        f"NIT {x.get('numero_identificacion') or 'â'}-{x.get('digito_verificacion') or 'â'}"
                        f" ({x.get('estado_matricula') or 'â'}, CIIU {x.get('cod_ciiu_act_econ_pri') or 'â'})",
               "url": "https://www.datos.gov.co/resource/c82u-588k.json"}
              for x in rows[:3] if x.get("razon_social")]
        return self._flat_env(tool="co_rues_companies",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="co_rues",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    def kr_hometax_biz_status(self, *, biz_no, execution=None, no_cache=None):
        """company kr_hometax_biz_status: Korea NTA business-registration-status single-shot (í´í¬ì/tax type;
        biz_no 10 digits (3-2-5 hyphens optional); all four states are legal answers â operating / closed (ISO í­ìì¼ì) /
        unregistered (result=S) / error; txprNm stays null when anonymous â no owner-name leak)."""
        self._co_only("kr_hometax_biz_status")
        r = company.kr_hometax.biz_status_raw(biz_no, cache=self._c._cache,
                                              no_cache=no_cache if no_cache is not None else self._c.no_cache)
        s = r["status"]
        state_label = {"active": "operating", "closed": "closed", "unregistered": "unregistered",
                       "error": "malformed shape"}[s["state"]]
        tail = f", í­ìì¼ì {s['closed_date']}" if s["closed_date"] else ""
        reason = (f"KR hometax: {s['biz_no']} â {state_label}"
                  + (f" ({s['tax_type'] or s['simple_status'] or 'â'})" if s["state"] != "error" else " (verbatim passthrough)")
                  + tail
                  + " â unregistered is also a legal result=S answer (same family as VIES INVALID); txprNm stays null when anonymous")
        return self._flat_env(
            tool="kr_hometax_biz_status", input={"biz_no": s["biz_no"]},
            reason=reason, result={"status": s},
            evidence=[{"quote": (f"{s['biz_no']}: {s['tax_type'] or 'â'}"
                                 + (f" | EN: {s['english_status']}" if s["english_status"] else "")),
                       "url": "https://hometax.go.kr/wqAction.do?actionId=ATTABZAA001R08"}],
            provider_id="kr_hometax", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"actionId": "ATTABZAA001R08", "txprDscmNo": s["biz_no"],
                                                 "dongCode": s["biz_no"][3:5]}},
        )

    def nzco_companies(self, *, q, entity_types=None, start=None, limit=None,
                       execution=None, no_cache=None):
        """company nzco_companies: NZ Companies Register search (name substring over the whole
        register index; the canonical parameter set is required — a bare ?q= answers an empty
        match). Rows carry the dual official keys (company number + 16-digit NZBN), the register's
        own status word (Registered / Removed — not "Active"), the entity type and the registered
        address. Paging uses the pager's own vocabulary: start=<row offset> + limit 5|15 (both
        observed live; other page sizes unpinned and not shipped); has_next reads the pager
        offsets. entity_types narrows via the filter form's own checkbox codes (LTD/UNLTD/COOP =
        NZ companies, ASIC/NON_ASIC = overseas)."""
        self._co_only("nzco_companies")
        r = company.nzco.companies_raw(q, entity_types=entity_types, start=start, limit=limit,
                                       cache=self._c._cache,
                                       no_cache=no_cache if no_cache is not None else self._c.no_cache)
        rows = r["rows"]
        reason = (f"NZ Companies Office: '{r['params']['q']}' → {r['count']} companies"
                  + (f" (rows {r['start'] + 1}..{r['start'] + r['count']}, {r['limit']}/page,"
                     + (" more pages)" if r["has_next"] else " last page)") if rows else ")")
                  + (f", entityTypes={r['entity_types']}" if r["entity_types"] != "ALL" else ""))
        return self._flat_env(
            tool="nzco_companies",
            input={"q": r["params"]["q"], "entity_types": r["entity_types"],
                   "start": r["start"], "limit": r["limit"]},
            reason=reason,
            result={"count": r["count"], "rows": rows, "start": r["start"], "limit": r["limit"],
                    "entity_types": r["entity_types"], "has_next": r["has_next"]},
            evidence=[{"quote": f"{x['company_number']} {x['name']} — NZBN {x['nzbn']} ({x['status']})",
                       "url": "https://app.companiesoffice.govt.nz/companies/app/ui/pages/companies/search"}
                      for x in rows[:5]],
            provider_id="nzco", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def nzco_directors(self, *, company_number, execution=None, no_cache=None):
        """company nzco_directors: NZ company current directors by company number — the page H1
        confirms the company (name + number + status; a mismatch would refuse to attribute rows)
        and each director row carries the full legal name, the residential address (statutorily
        public in NZ, partially masked since the privacy-law change — captured verbatim) and the
        appointment date in the register's own wording. Ceased/former appointments render in a
        different section (ceasedDate rows) and stay out of this face."""
        self._co_only("nzco_directors")
        r = company.nzco.directors_raw(company_number, cache=self._c._cache,
                                       no_cache=no_cache if no_cache is not None else self._c.no_cache)
        rows = r["rows"]
        reason = (f"NZ Companies Office: {r['company_name'] or '(page H1 unreadable)'} "
                  f"({r['company_number']}{', ' + r['status'] if r['status'] else ''}) → "
                  f"{r['count']} current directors — names and residential addresses are the "
                  f"register's statutory public record")
        return self._flat_env(
            tool="nzco_directors", input={"company_number": r["company_number"]},
            reason=reason,
            result={"company_name": r["company_name"], "company_number": r["company_number"],
                    "status": r["status"], "count": r["count"], "rows": rows},
            evidence=[{"quote": (f"{x['name']} — appointed {x['appointment_date']}"
                                + (f", {x['address']}" if x["address"] else "")),
                       "url": ("https://app.companiesoffice.govt.nz/companies/app/ui/pages/"
                               f"companies/{r['company_number']}/directors")}
                      for x in rows[:5]],
            provider_id="nzco", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- 0.3.32 CZ ARES economic-entities register batch (CZ master + name search) ----------

    def cz_ares_ekonomicke_subjekty(self, *, ico, execution=None, no_cache=None):
        """company cz_ares_ekonomicke_subjekty: Czech ARES economic-entities register, single record by
        IČO (GET /ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}). The IČO is validated against
        the upstream's own regex [0-9]{8} and a malformed one is refused locally (upstream would answer
        400 VSTUP_NEVALIDNI_FORMAT_ICO); an unknown but well-formed IČO answers 404 NENALEZENO and is
        carried as upstream_not_found — a clean round trip, not an error. The record carries the
        structured address with the full administrative code ladder (kodAdresnihoMista = the RUIÁN
        address-point code, the address-graph join key), the legal-form code, the VAT key (dic =
        CZ<ico>), the founding and last-update dates, the CZ-NACE 2008 code list and the 16-register
        status matrix (seznamRegistraci — every register's own state)."""
        self._co_only("cz_ares_ekonomicke_subjekty")
        r = company.cz_ares.detail_raw(ico, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        reg = r["register_status"]
        active = sum(1 for v in reg.values() if v == "AKTIVNI")
        addr = r["address"] or {}
        reason = (f"CZ ARES: IČO {r['ico']} → {r['name'] or '(no name)'}"
                  f" (legal form {r['legal_form'] or '—'}, VAT {r['vat'] or '—'}, "
                  f"primary source {r['primary_source'] or '—'}, founded {r['founded_at'] or '—'}, "
                  f"updated {r['updated_at'] or '—'})"
                  f" — {active}/{len(reg)} registers active"
                  + (f", address point code {addr.get('kodAdresnihoMista')}" if addr.get("kodAdresnihoMista") else "")
                  + (f", {len(r['nace_2008'])} NACE-2008 codes" if r["nace_2008"] else "")
                  + "; the 16-register matrix is per-register state, not one company status")
        return self._flat_env(
            tool="cz_ares_ekonomicke_subjekty", input={"ico": r["params"]["ico"]},
            reason=reason,
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": (f"{r['ico']} {r['name'] or '—'} — {r['address_text'] or '—'}"
                                 f" (form {r['legal_form'] or '—'}, VAT {r['vat'] or '—'})"),
                       "url": f"https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{r['ico']}"}],
            provider_id="cz_ares", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def cz_ares_ekonomicke_subjekty_vyhledat(self, *, obchodni_jmeno, pocet=10, start=0,
                                             execution=None, no_cache=None):
        """company cz_ares_ekonomicke_subjekty_vyhledat: Czech ARES name search (POST
        /ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/vyhledat — the search endpoint is POST-only).
        The envelope carries pocetCelkem = the real total. **The upstream folds the record names to ASCII
        but not the query**: a diacritic in the query is dropped and the match set shifts, so the face
        folds the query itself and echoes both forms. **The rows do not share one join key**: `ico` is
        present only for the rows whose primary source carries the trade-register identifier, and an
        RZP-primary row carries only the ARES surrogate icoId ("ARES_00358750") — which the
        single-record face's [0-9]{8} validator refuses, so those rows are not joinable from here."""
        self._co_only("cz_ares_ekonomicke_subjekty_vyhledat")
        r = company.cz_ares.vyhledat_raw(obchodni_jmeno, pocet=pocet, start=start,
                                         cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        joined = sum(1 for x in rows if x.get("ico"))
        reason = (f"CZ ARES name search: {r['query_name_original']!r} → {r['total'] if r['total'] is not None else '—'} "
                  f"matches (this page {r['count']}, start={r['start']}, pocet={r['pocet']})"
                  + (f"; query folded to {r['params']['obchodniJmeno']!r} for the upstream's ASCII index" if r["params"]["obchodniJmeno"] != r["query_name_original"] else "")
                  + (f"; {joined}/{len(rows)} rows carry a joinable ico (the rest are RZP-primary surrogate rows)"
                     if rows and joined < len(rows) else "")
                  + " — a 404 by ico is a legal answer, not an error")
        return self._flat_env(
            tool="cz_ares_ekonomicke_subjekty_vyhledat",
            input={"obchodni_jmeno": r["query_name_original"], "pocet": r["pocet"], "start": r["start"]},
            reason=reason,
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": (f"{x.get('ico') or x.get('ico_id') or '—'} {x.get('name') or '—'} — "
                                 f"{x.get('address_text') or '—'} (source {x.get('primary_source') or '—'})"),
                       "url": "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/vyhledat"}
                      for x in rows[:5]],
            provider_id="cz_ares", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- 0.3.33 offshore Channel-Islands registers batch (GG GFSC feeds + JE JFSC search) ----------

    def gg_gfsc_regulated_entities(self, name=None, *, licence=None, status=None, surrendered=None,
                                   ref=None, limit=20, execution=None, no_cache=None):
        """company gg_gfsc_regulated_entities: Guernsey GFSC regulated-entities register (full-feed
        local scan). The feed ships its display fields as HTML <a> links — stripped here to
        ref/name/licence plus the register's own detail path. **One row per licence group**: the
        same entity appears on 2+ rows when its groups sit in different states (26 such refs;
        1818 Venture Capital = an Investment Licensee row surrendered=False + a revoked Primary
        Licensee row surrendered=True) — read entities_matched for the entity count.
        surrendered is a "0"/"1" string on the wire → bool. Status null (41% of rows) = the
        register states nothing, not missing data. Refs are not uniformly 7-digit — legacy 5-6-digit
        refs exist; --ref matches the digit string exactly with no length assumption."""
        self._co_only("gg_gfsc_regulated_entities")
        st = str(status).strip().upper() or None if status is not None else None
        r = company.gg_gfsc.regulated_entities_raw(name, licence=licence, status=st,
                                                   surrendered=surrendered, ref=ref, limit=limit,
                                                   cache=self._c._cache,
                                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        top = (rows or [None])[0]
        dup_note = (f", {r['total_matched']} rows = {r['entities_matched']} distinct entities"
                    f" (one row per licence group)" if r["total_matched"] != r["entities_matched"] else "")
        return self._flat_env(
            tool="gg_gfsc_regulated_entities",
            input={"name": name, "licence": licence, "status": st, "surrendered": surrendered,
                   "ref": ref, "limit": r["limit_applied"]},
            reason=(f"GG GFSC regulated register: scanned {r['scanned_rows']} feed rows, "
                    f"{r['total_matched']} matched{dup_note}"
                    + (f", top hit {top['ref']} {top['name']} ({top['licence'] or '—'})" if top
                       else " (zero hits is a legal answer)")
                    + (f", surrendered={'yes' if surrendered else 'no'}" if surrendered is not None else "")),
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": f"{x['ref'] or '—'} {x['name'] or '—'} — {x['licence'] or '—'}"
                                + (" [surrendered]" if x["surrendered"] else ""),
                       "url": f"https://www.gfsc.gg{x['detail_path']}" if x["detail_path"]
                              else "https://www.gfsc.gg/commission/regulated-entities"}
                      for x in rows[:5]],
            provider_id="gg_gfsc", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"feed": "/gfsc-company/feed/regulated", "local_scan": r["params"]}},
        )

    def gg_gfsc_registered_businesses(self, name=None, *, category=None, ref=None, limit=20,
                                      execution=None, no_cache=None):
        """company gg_gfsc_registered_businesses: Guernsey GFSC registered (prescribed) businesses
        (full-feed local scan, 133 rows): Accountant 74 / Estate Agent 22 / Money Service Providers
        20 / Legal Professional 17 — the Registration of Prescribed Businesses face. 23 refs also
        appear on the regulated feed (dual-listed entities); same HTML-strip + detail-path rescue
        as the regulated face."""
        self._co_only("gg_gfsc_registered_businesses")
        r = company.gg_gfsc.registered_businesses_raw(name, category=category, ref=ref, limit=limit,
                                                      cache=self._c._cache,
                                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="gg_gfsc_registered_businesses",
            input={"name": name, "category": category, "ref": ref, "limit": r["limit_applied"]},
            reason=(f"GG GFSC prescribed-business register: scanned {r['scanned_rows']} feed rows, "
                    f"{r['total_matched']} matched"
                    + (f", top hit {top['ref']} {top['name']} ({top['category'] or '—'})" if top
                       else " (zero hits is a legal answer)")),
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": f"{x['ref'] or '—'} {x['name'] or '—'} — {x['category'] or '—'}",
                       "url": f"https://www.gfsc.gg{x['detail_path']}" if x["detail_path"]
                              else "https://www.gfsc.gg/commission/registered-entities"}
                      for x in rows[:5]],
            provider_id="gg_gfsc", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"feed": "/gfsc-company/feed/registeredbusiness", "local_scan": r["params"]}},
        )

    def in_sebi_default_brokers(self, execution=None, no_cache=None):
        """company in_sebi_default_brokers: SEBI defaulters & expelled stock brokers
        (sebi.gov.in/sebiweb BrokerAction; the negative register, ONE 1.2MB page — no paging,
        no search). Cards: Name / Trade Name / Registration No. (INB…) / Exchange Name / Status
        (Defaulter | Expelled | "Defaulter and expelled" — 80/215/150 of 445 pinned
        2026-11-04). One entity may span multiple cards (one per exchange)."""
        self._co_only("in_sebi_default_brokers")
        r = company.in_sebi_intm.default_brokers_raw(
            cache=self._c._cache,
            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        top = (rows or [None])[0]
        statuses = {}
        for x in rows:
            if x.get("status"):
                statuses[x["status"]] = statuses.get(x["status"], 0) + 1
        stat_s = ", ".join(f"{k} {v}" for k, v in sorted(statuses.items())) or "—"
        return self._flat_env(
            tool="in_sebi_default_brokers",
            input={},
            reason=(f"SEBI defaulters & expelled brokers register: {r['count']} cards in one page "
                    f"({stat_s})"
                    + (f", top {top['name'] or '—'} ({top.get('registration_no') or '—'}, "
                       f"{top.get('exchange') or '—'})" if top else "")),
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": f"{x['name'] or '—'} ({x.get('registration_no') or '—'}, "
                                f"{x.get('exchange') or '—'}) — {x.get('status') or '—'}",
                       "url": "https://www.sebi.gov.in/sebiweb/broker/BrokerAction.do?doBroker=yes"}
                      for x in rows[:5]],
            provider_id="in_sebi_intm", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def in_sebi_intermediaries(self, category="sb_equity", *, search=None, regno=None,
                               execution=None, no_cache=None):
        """company in_sebi_intermediaries: SEBI registered intermediaries by category
        (sebi.gov.in/sebiweb; 37 categories verbatim, default = equity-segment stock brokers).
        **Exactly one of search (substring over names — MOTILAL → 7 cards) or regno (the exact
        registration-number lookup, INB030484617)** — an empty search over a full category
        times out server-side (5,011 equity brokers), the wall carries that evidence. Cards
        are title/value pairs whose FIELD SET VARIES BY CATEGORY (CRA cards carry Contact
        Person/Correspondence Address and no Exchange; regno formats differ per class —
        INB…/INZ…/IN/CRA/…); every pair rides, unknown labels verbatim. One entity spans
        multiple cards (one per exchange — the register's own multi-row shape)."""
        self._co_only("in_sebi_intermediaries")
        r = company.in_sebi_intm.intermediaries_raw(category, search=search, regno=regno,
                                                    cache=self._c._cache,
                                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        top = (rows or [None])[0]
        via = (f"name search \"{r['query']}\"" if r["mode"] == "search"
               else f"regNo exact lookup {r['query']}")
        if rows:
            keys = [k for k in (top.get("registration_no"), top.get("exchange")) if k]
            reason = (f"SEBI intermediaries — {r['category_name']}: {r['count']} cards via {via}, "
                      f"top {top.get('name') or '—'}"
                      + (f" ({', '.join(keys)})" if keys else ""))
        else:
            reason = (f"SEBI intermediaries — {r['category_name']}: zero cards via {via} "
                      "— a legitimate answer (the filter is the site's own)")
        return self._flat_env(
            tool="in_sebi_intermediaries",
            input={"category": r["category"], "search": search, "regno": regno},
            reason=reason,
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": f"{x.get('name') or '—'} ({x.get('registration_no') or '—'}, "
                                f"{x.get('exchange') or x.get('type') or '—'})",
                       "url": "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognised=yes"}
                      for x in rows[:5]],
            provider_id="in_sebi_intm", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def je_jfsc_regulated_entities(self, *, keyword, page_size=20, page=1,
                                   execution=None, no_cache=None):
        """company je_jfsc_regulated_entities: Jersey JFSC regulated-entities register (Umbraco
        site-search POST). **NoResults is a result count, not a zero flag** — Keyword "Barclays"
        answers NoResults=1 with one row (Barclays Bank plc, Jersey Branch, five law sections).
        Rows are site-search rows (Title/Url/Rank); the official licence text rides in
        Properties[0].LawSection verbatim and is parsed into law/code/ref triplets (the raw text is
        kept alongside). Refiners are not exposed — the upstream facet values are space-joined
        lowercase keys, a lossy spelling that would break on any reword (rasff precedent).
        keyword is required; the empty-keyword POST is the full-register enumeration, unpinned
        here (harvest-side)."""
        self._co_only("je_jfsc_regulated_entities")
        r = company.je_jfsc.regulated_entities_raw(keyword, page_size=page_size, page=page,
                                                   cache=self._c._cache,
                                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="je_jfsc_regulated_entities",
            input={"keyword": r["params"]["Keyword"], "page_size": r["params"]["PageSize"],
                   "page": r["params"]["PageNumber"]},
            reason=(f"JE JFSC register: \"{r['params']['Keyword']}\" → {r['total'] if r['total'] is not None else '—'} "
                    f"hits (page {r['page']}/{r['pages'] or '—'}"
                    + (", more pages" if r["has_more"] else "") + ")"
                    + (f", top hit {top['name'] or '—'} (entity {top['entity_id'] or '—'}, "
                       f"{len(top['law_sections'])} law sections)" if top
                       else " (zero hits is a legal answer — the total is NoResults=0)")
                    + " — the row's LawSection carries the official licence refs verbatim"),
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": (f"{x['name'] or '—'} — {x['law_section_text'] or '—'}"),
                       "url": x["url"] or "https://www.jerseyfsc.org/industry/regulated-entities/"}
                      for x in rows[:5]],
            provider_id="je_jfsc", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def kz_gbd_ul_companies(self, *, text=None, page=1, count=20, execution=None, no_cache=None):
        """company kz_gbd_ul_companies: Kazakhstan GBD_UL legal-entities master register
        (data.egov.kz getdata; the company master register's 19th jurisdiction, first Central-Asian).
        Bilingual column pairs verbatim (nameru/namekz, okedru/okedkz, statusru/statuskz,
        addressru/addresskz); bin is the 12-digit hard key but the pre-BIN-era rows (page 1's
        1995-1999 registrants) carry bin=null — the register's own statement. datereg is
        tri-modal (bare date / +06:00 pre-2024 / +05:00 unified KZ) and travels verbatim.
        getdata sits behind a portal-session cookie gate (bootstrap = the dataset page itself);
        count is hard-clamped to 20 upstream; column/order sorts are silently ignored (not
        shipped); a page past the last snaps to the last page — has_more reads the echoed page."""
        self._co_only("kz_gbd_ul_companies")
        r = company.kz_gbd_ul.companies_raw(text, page=page, count=count,
                                            cache=self._c._cache,
                                            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        top = (rows or [None])[0]
        total_s = f"{r['total']:,}" if isinstance(r["total"], int) else "—"
        return self._flat_env(
            tool="kz_gbd_ul_companies",
            input={"text": r["text"], "page": r["params"]["page"], "count": r["params"]["count"]},
            reason=(f"KZ GBD_UL register: {total_s} entities"
                    + (f" matching \"{r['text']}\"" if r["text"] else "")
                    + f", page {r['page'] or '—'}/{r['pages'] or '—'}"
                    + (", more pages" if r["has_more"] else "")
                    + (f", top hit bin {top['bin'] or '— (pre-BIN era)'} {top['nameru'] or '—'}" if top
                       else " (zero hits is a legal answer)")),
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": f"{x['bin'] or '—'} {x['nameru'] or '—'} — {x['statusru'] or '—'}"
                                + (f" ({x['datereg']})" if x["datereg"] else ""),
                       "url": "https://data.egov.kz/datasets/view?index=gbd_ul"}
                      for x in rows[:5]],
            provider_id="kz_gbd_ul", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- 0.2.0 flat panel commands (esg: source-qualified names + upstream param names + our defaults) ----------

    # —— 0.3.36 TR SPK listed-companies directory (dictionary slot: tr_spk_listed between ted and usaspending) ——

    def tr_spk_listed(self, name=None, *, segment="all", mersis=None, limit=20,
                      execution=None, no_cache=None):
        """company tr_spk_listed: SPK publicly-listed companies directory (ws.spk.gov.tr
        HalkaAcikSirket; the company domain's first TR face). Two one-shot walls — Borsa 628
        exchange-traded + BorsaDisi 121 non-exchange, cached 24h and scanned locally. mersisNo
        = the 16-digit MERSIS key (8 rows ship it empty -> null); mkkSicilNo arrives as "" or
        null inconsistently (both -> null); the lifecycle status rides INLINE in unvani
        ("(İFLAS NEDENİYLE) TASFİYE HALİNDE …" — 1 Borsa / 15 BorsaDisi rows; no separate
        status column). --mersis (the single-record channel) adds tur/faaliyetDurumu/street
        adres the lists lack — and sirketVarmi LIES (a MERSIS outside the register also answers
        true, with an all-null shell; found mirrors unvani instead)."""
        self._co_only("tr_spk_listed")
        nm = str(name or "").strip() or None
        r = company.tr_spk_borsa.listed_raw(nm, segment=segment, mersis=mersis, limit=limit,
                                            cache=self._c._cache,
                                            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        if mersis not in (None, ""):   # the single-record channel
            result = {k: x for k, x in r.items() if k != "_meta"}
            sirket = result["sirket"]
            if result["found"]:
                reason = (f"SPK listed-company record for MERSIS {result['mersis']}: {sirket['unvani']}"
                          + (f" — {sirket['faaliyetDurumu']}" if sirket["faaliyetDurumu"] else "")
                          + (f", {sirket['tur']}" if sirket["tur"] else "")
                          + " — tur/faaliyetDurumu/adres exist only on this channel, not on the lists;"
                            " sirketVarmi is NOT an existence signal (it answers true outside the register too)")
            else:
                reason = (f"MERSIS {result['mersis']} is NOT on the SPK listed-companies register: the channel "
                          f"answered sirketVarmi={result['sirketVarmi']} with an ALL-NULL sirket shell — the flag "
                          "lies (pinned 2026-11-04); the null shell is the honest negative signal (the entity may "
                          "still exist in the TR trade registry, just not as a listed company)")
            return self._flat_env(
                tool="tr_spk_listed",
                input={"mersis": result["mersis"], "segment": None, "name": None},
                reason=reason,
                result=result,
                evidence=[{"quote": (f"{sirket['unvani'] or '—'} · MERSIS {sirket['mersisNo'] or result['mersis']}"
                                     + (f" · {sirket['faaliyetDurumu']}" if sirket["faaliyetDurumu"] else "")
                                     + (f" · {sirket['adres'] or ''}" if sirket["adres"] else "")),
                           "url": f"https://ws.spk.gov.tr/HalkaAcikSirket/api/Sirket/{result['mersis']}"}],
                provider_id="tr_spk_borsa", metas=[r["_meta"]],
                query={"source": "raw", "upstream": r["params"]},
            )
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        sc = result["scanned"]
        seg_s = " + ".join(f"{k} {v}" for k, v in sc.items())
        if result["rows"]:
            reason = (f"SPK listed companies: {result['total_matched']} of {sum(sc.values())} rows matched"
                      + f" ({seg_s})"
                      + (f", segment {segment}" if segment != "all" else "")
                      + (f", name contains \"{nm}\"" if nm else "")
                      + " — mersisNo is the 16-digit MERSIS join key (a few rows ship it null); the lifecycle"
                        " status rides INLINE in unvani ((İFLAS NEDENİYLE) TASFİYE HALİNDE … on 16 rows);"
                        " mkkSicilNo joins the MKK register")
        else:
            reason = (f"SPK listed companies: zero hits on the {sum(sc.values())}-row directory ({seg_s})"
                      + (f", name contains \"{nm}\"" if nm else "")
                      + " — a legitimate answer (drop filters to enumerate the directory)")
        return self._flat_env(
            tool="tr_spk_listed",
            input={"name": nm, "segment": segment, "mersis": None,
                   "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x['unvani'] or '—'} · MERSIS {x['mersisNo'] or '—'}"
                                + (f" · {x['adresIl']}" if x["adresIl"] else ""),
                       "url": (f"https://ws.spk.gov.tr/HalkaAcikSirket/api/Sirket/{x['mersisNo']}"
                               if x["mersisNo"] else
                               "https://ws.spk.gov.tr/HalkaAcikSirket/api/Sirketler/Borsa")}
                      for x in result["rows"][:5]],
            provider_id="tr_spk_borsa", metas=metas,
        )
