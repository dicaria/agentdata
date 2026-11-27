"""company faces — flat face-method mixin (0.2.6 per-domain split, migrated from client.py _Domain).

Mixed into the root _Domain (assembled via MRO, see client.py); discipline: no __init__, depends only on root
internals (_flat_env/_c/_request…), method names globally unique across domains (a collision would shadow another domain's face).
"""
from ..errors import SdkError

import json  # XBRL fact rows re-serialized verbatim into evidence quotes (E8)
import warnings  # deprecated sec_* alias shims (us_ prefix rename, pre-release 2026-11-17)

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

    # —— 0.3.58 FDIC BankFind siblings (dictionary order: fdic_failures < fdic_financials <
    # fdic_history < fdic_institutions < fdic_locations; the four share the institutions
    # contract — filters required locally, limit ≤10000 upstream, row offset) ——

    def fdic_failures(self, *, filters=None, fields=None, limit=20, offset=0,
                      sort_by=None, sort_order=None, execution=None, no_cache=None):
        """company fdic_failures: US bank failure history 1934→today (api.fdic.gov /banks/failures;
        4,117 rows; filters like 'CERT:3510' or 'PSTALP:TX' — the state field on THIS index is
        PSTALP (STALP/CITY/NAME text filters answer a silent zero); FAILDATE normalized
        M/D/YYYY→ISO; early rows carry CERT null — FUND is the then-key)."""
        self._co_only("fdic_failures")
        raw_filters = str(filters or "").strip() or None
        r = company.fdic_bankfind.failures_raw(filters=raw_filters, fields=fields, limit=limit,
                                               offset=offset, sort_by=sort_by, sort_order=sort_order,
                                               cache=self._c._cache,
                                               no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="fdic_failures",
            input={"filters": raw_filters, "limit": r["params"]["limit"], "offset": r["params"]["offset"]},
            reason=(f"FDIC failure history: {result['total']} rows matched"
                    + (f", top {top['NAME'] or '—'} ({top['CITY'] or '—'}) failed {top['FAILDATE'] or '—'}" if top
                       else ", zero hits (an empty result is a legal answer — the CERT never failed or the filter is too narrow)")),
            result=result,
            evidence=[{"quote": f"{x['NAME'] or '—'} failed {x['FAILDATE'] or '—'} ({x['CITY'] or '—'}"
                                + (f", CERT {x['CERT']}" if x.get("CERT") else ", CERT null (pre-cert-numbering era — FUND is the then-key)"),
                       "url": (f"https://banks.data.fdic.gov/bankfind-suite/detail/institution/{x['CERT']}"
                               if x.get("CERT") else "https://banks.data.fdic.gov/bankfind-suite/")}
                      for x in result["rows"][:5]],
            provider_id="fdic-bankfind", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def fdic_financials(self, *, filters=None, fields=None, limit=20, offset=0,
                        sort_by=None, sort_order=None, execution=None, no_cache=None):
        """company fdic_financials: US bank quarterly statements of financial health
        (api.fdic.gov /banks/financials; CERT:628 = 170 quarters back to 1984; REPDTE
        'YYYYMMDD'→ISO; ASSET/DEP/EQ/NETINC are $ THOUSANDS — the suite's own convention,
        never rescaled)."""
        self._co_only("fdic_financials")
        raw_filters = str(filters or "").strip() or None
        r = company.fdic_bankfind.financials_raw(filters=raw_filters, fields=fields, limit=limit,
                                                 offset=offset, sort_by=sort_by, sort_order=sort_order,
                                                 cache=self._c._cache,
                                                 no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="fdic_financials",
            input={"filters": raw_filters, "limit": r["params"]["limit"], "offset": r["params"]["offset"]},
            reason=(f"FDIC quarterly financials: {result['total']} quarters matched"
                    + (f", top row {top['REPDTE']} — ASSET ${top['ASSET']:,}k / DEP ${top['DEP']:,}k / NETINC ${top['NETINC']:,}k ($ thousands)" if top
                       else ", zero hits (an empty result is a legal answer — check the CERT spelling)")),
            result=result,
            evidence=[{"quote": f"{x['REPDTE']} · ASSET ${x['ASSET']:,}k · DEP ${x['DEP']:,}k · EQ ${x['EQ']:,}k · NETINC ${x['NETINC']:,}k",
                       "url": f"https://banks.data.fdic.gov/bankfind-suite/detail/institution/{x['CERT']}"}
                      for x in result["rows"][:5]],
            provider_id="fdic-bankfind", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def fdic_history(self, *, filters=None, fields=None, limit=20, offset=0,
                     sort_by=None, sort_order=None, execution=None, no_cache=None):
        """company fdic_history: US bank structural-change log (api.fdic.gov /banks/history;
        585,634 rows, CERT:628 alone = 13,418; CHANGECODE_DESC the human sentence; ENDDATE
        '9999-12-31' sentinel → null = still-open change)."""
        self._co_only("fdic_history")
        raw_filters = str(filters or "").strip() or None
        r = company.fdic_bankfind.history_raw(filters=raw_filters, fields=fields, limit=limit,
                                              offset=offset, sort_by=sort_by, sort_order=sort_order,
                                              cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="fdic_history",
            input={"filters": raw_filters, "limit": r["params"]["limit"], "offset": r["params"]["offset"]},
            reason=(f"FDIC change log: {result['total']} events matched"
                    + (f", top {top['CHANGECODE_DESC'] or '—'} on {top['EFFDATE'] or '—'}" if top
                       else ", zero hits (an empty result is a legal answer — check the CERT spelling)")),
            result=result,
            evidence=[{"quote": f"{x['CHANGECODE_DESC'] or '—'} · {x['EFFDATE'] or '?'}→{x['ENDDATE'] or 'open'}"
                                + (f" · {x['INSTNAME'] or '—'}" if x.get("INSTNAME") else ""),
                       "url": f"https://banks.data.fdic.gov/bankfind-suite/detail/institution/{x['CERT']}"}
                      for x in result["rows"][:5]],
            provider_id="fdic-bankfind", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

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

    def fdic_locations(self, *, filters=None, fields=None, limit=20, offset=0,
                       sort_by=None, sort_order=None, execution=None, no_cache=None):
        """company fdic_locations: US bank branch/office roster (api.fdic.gov /banks/locations;
        CERT:628 = 5,414 offices; MAINOFF=1 marks the head office, SERVTYPE_DESC the service
        type; rows verbatim)."""
        self._co_only("fdic_locations")
        raw_filters = str(filters or "").strip() or None
        r = company.fdic_bankfind.locations_raw(filters=raw_filters, fields=fields, limit=limit,
                                                offset=offset, sort_by=sort_by, sort_order=sort_order,
                                                cache=self._c._cache,
                                                no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="fdic_locations",
            input={"filters": raw_filters, "limit": r["params"]["limit"], "offset": r["params"]["offset"]},
            reason=(f"FDIC office roster: {result['total']} offices matched"
                    + (f", top {top['OFFNAME'] or '—'} ({'HEAD OFFICE' if str(top.get('MAINOFF')) == '1' else 'branch'}, {top['SERVTYPE_DESC'] or '—'}, {top['CITY'] or '—'} {top['STALP'] or '—'})" if top
                       else ", zero hits (an empty result is a legal answer — check the CERT spelling)")),
            result=result,
            evidence=[{"quote": f"{x['OFFNAME'] or '—'} · office #{x['OFFNUM']} · {x['SERVTYPE_DESC'] or '—'}"
                                + (" · HEAD OFFICE" if str(x.get("MAINOFF")) == "1" else "")
                                + f" · {x['CITY'] or '—'} {x['STALP'] or '—'}",
                       "url": f"https://banks.data.fdic.gov/bankfind-suite/detail/institution/{x['CERT']}"}
                      for x in result["rows"][:5]],
            provider_id="fdic-bankfind", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def us_sec_submissions(self, *, cik, execution=None, no_cache=None):
        """company us_sec_submissions: SEC CIK → registrant identity card (data.sec.gov submissions single record;
        bare digits / leading zeros / the CIK prefix — all three spellings accepted — non-digits stripped, padded to 10)."""
        self._co_only("us_sec_submissions")
        v = str(cik or "").strip()
        if not v:
            raise SdkError("usage_error", provider="edgar-cik", detail="us_sec_submissions requires cik (1-10 digits, CIK prefix allowed)")
        r = company.edgar_cik.lookup_cik(v, cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        tk = (f" ({'/'.join(result['tickers'])}·{'/'.join(result['exchanges']) or '?'})"
              if result.get("tickers") else " (no ticker — unlisted or no trading venue registered)")
        return self._flat_env(
            tool="us_sec_submissions", input={"cik": v},
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

    def sec_submissions(self, *, cik, execution=None, no_cache=None):
        """company sec_submissions: DEPRECATED alias of us_sec_submissions (renamed 2026-11-17
        pre-release so the SEC cluster carries the us_ jurisdiction prefix like every other face;
        kept working with a DeprecationWarning, removal slated 0.4.x)."""
        warnings.warn("sec_submissions is deprecated — use us_sec_submissions (removal slated 0.4.x)",
                      DeprecationWarning, stacklevel=2)
        return self.us_sec_submissions(cik=cik, execution=execution, no_cache=no_cache)

    # —— 0.3.66 SEC ticker directory (dictionary order: us_sec_tickers sorts after
    # us_sec_submissions — the reverse-lookup face the submissions card lacks: it only takes CIK
    # input, ticker→CIK had no face before this) ——

    def us_sec_tickers(self, *, ticker=None, name=None, cik=None,
                       execution=None, no_cache=None):
        """company us_sec_tickers: SEC ticker↔CIK directory (10,404 rows) — exactly one selector:
        --ticker exact (case-insensitive) / --name title substring / --cik reverse (all tickers
        of one registrant — share classes share a CIK: 10,404 rows resolve to 7,997 CIKs)."""
        self._co_only("us_sec_tickers")
        given = [x for x in (ticker, name, cik) if x is not None and str(x).strip()]
        if len(given) != 1:
            raise SdkError("usage_error", provider="edgar_xbrl",
                           detail="us_sec_tickers requires exactly one of --ticker / --name / --cik "
                                  "(bare enumeration of all 10,404 rows is not a face — use the "
                                  "corpus line for bulk; got "
                                  + str(len(given)) + " selectors)")
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        r = company.edgar_xbrl.tickers_raw(cache=cache, no_cache=nc)
        rows_raw = list((r["data"] or {}).values())
        sel = ticker if ticker is not None else (name if name is not None else cik)
        sel_name = "ticker" if ticker is not None else ("name" if name is not None else "cik")
        rows = company.edgar_xbrl.tickers_lookup(rows_raw, ticker=ticker, name=name, cik=cik)
        if sel_name == "ticker":
            sel_disp = str(sel).strip().upper()
        else:
            sel_disp = str(sel).strip()
        head = (f"{rows[0]['ticker']} → CIK {rows[0]['cik']} {rows[0]['title']}" if rows else None)
        return self._flat_env(
            tool="us_sec_tickers",
            input={sel_name: sel_disp},
            reason=(f"SEC ticker directory: {sel_name} \"{sel_disp}\" — {len(rows)} of {len(rows_raw)} rows matched"
                    + (f", top {head}" if head else " (zero hits are a legal answer — check the spelling; "
                       "OTC-only issuers may be absent from the directory)")),
            result={"total": len(rows), "rows": rows, "selector": {sel_name: sel_disp}},
            evidence=[{"quote": f"{x['ticker']} → CIK {x['cik']} = {x['title']}",
                       "url": "https://www.sec.gov/files/company_tickers.json"} for x in rows[:5]],
            provider_id="edgar_xbrl", metas=[r],
            query={"source": "raw", "upstream": {"directory": "company_tickers.json"}},
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

    # —— 0.3.74 E16 FCA data-API family (dictionary slot: gb_contracts_finder_* < gb_fca_* <
    # gb_fts_*; ONE keyless endpoint, api.data.fca.org.uk/search?index=…, FOUR indexes — the
    # regulator's own portal data, not an exchange feed) ——

    def gb_fca_firds_search(self, *, fininstrmgnlattrbts_id=None, tradgvnrltdattrbts_id=None,
                            isin_sngl_noindx=None, isin_bskt=None, issr=None,
                            fininstrmgnlattrbts_clssfctntp=None, keyword=None, active_only=True,
                            date_field="publication", from_date=None, to_date=None,
                            sort="fininstrmgnlattrbts_id", order="asc", offset=0, limit=20,
                            execution=None, no_cache=None):
        """company gb_fca_firds_search: FCA FIRDS instrument register — 169.6M published+active
        UK-reportable instrument lines (own ISIN, MIC, issuer LEI, CFI, life-cycle dates); criteria
        are plain strings AND'ed together, keyword is free text and mutually exclusive; dates bound
        the --date-field (publication | first_trade | termination) and a bare from-date is legal
        (the engine fills the far-future to-bound the index demands)."""
        self._co_only("gb_fca_firds_search")
        r = company.gb_fca.firds_search(
            fininstrmgnlattrbts_id=fininstrmgnlattrbts_id,
            tradgvnrltdattrbts_id=tradgvnrltdattrbts_id,
            isin_sngl_noindx=isin_sngl_noindx, isin_bskt=isin_bskt, issr=issr,
            fininstrmgnlattrbts_clssfctntp=fininstrmgnlattrbts_clssfctntp, keyword=keyword,
            active_only=active_only, date_field=date_field, from_date=from_date, to_date=to_date,
            sort=sort, order=order, offset=offset, limit=limit,
            cache=self._c._cache,
            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="gb_fca_firds_search",
            input={k: v for k, v in result["params"].items()},
            reason=(f"FCA FIRDS: {result['total']:,} instrument lines"
                    + (" published+active" if active_only else " incl. inactive")
                    + f" — {len(rows)} rows from offset {result['offset']}"
                    + (f", top {top.get('fininstrmgnlattrbts_fullnm') or top.get('fininstrmgnlattrbts_shrtnm') or '—'}"
                       f" ({top.get('fininstrmgnlattrbts_id')})" if top else "")
                    + " — never-published internal records are excluded upstream; field sets vary by instrument type"),
            result=result,
            evidence=[{"quote": f"{x.get('fininstrmgnlattrbts_fullnm') or x.get('fininstrmgnlattrbts_shrtnm') or '—'}"
                                f" · ISIN {x.get('fininstrmgnlattrbts_id') or '—'}"
                                f" · issuer {x.get('issr') or '—'}"
                                + (f" · CFI {x['fininstrmgnlattrbts_clssfctntp']}" if x.get("fininstrmgnlattrbts_clssfctntp") else ""),
                       "url": "https://data.fca.org.uk/"} for x in rows[:5]],
            provider_id="gb_fca", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def gb_fca_nsm_search(self, *, lei=None, company=None, text=None, text_mode="match_all_words",
                          types=None, sources=None, formats=None, tag_esef=False,
                          date_field="publication_date", from_date=None, to_date=None,
                          sort="publication_date", order="desc", offset=0, limit=20,
                          execution=None, no_cache=None):
        """company gb_fca_nsm_search: UK National Storage Mechanism — 5.57M regulatory
        disclosures 2010→today (RNS/EQS/PRN announcements, annual reports, final terms,
        shareholdings, PDMR dealings…); filters AND together, --text adds the full-text path
        (document content OR headline, latest versions only, ANDs with the LEI/facet filters);
        rows carry only populated fields upstream and the absolute artefact URLs."""
        self._co_only("gb_fca_nsm_search")
        from . import gb_fca as _eng  # local alias — the `company` FILTER param shadows the package
        r = _eng.nsm_search(
            lei=lei, company=company, text=text, text_mode=text_mode, types=types,
            sources=sources, formats=formats, tag_esef=tag_esef, date_field=date_field,
            from_date=from_date, to_date=to_date, sort=sort, order=order, offset=offset,
            limit=limit, cache=self._c._cache,
            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        facets = result.get("facets") or {}
        return self._flat_env(
            tool="gb_fca_nsm_search",
            input={k: v for k, v in result["params"].items()},
            reason=(f"FCA NSM: {result['total']:,} disclosures"
                    + (" (full-text path — latest versions only)" if text else "")
                    + f" — {len(rows)} rows from offset {result['offset']}"
                    + (f", top {top.get('company') or '—'} · {top.get('type') or '—'}"
                       f" ({(top.get('publication_date') or '')[:10]})" if top else "")
                    + (f" · facet vocabularies: {', '.join(sorted(facets))}" if facets else "")
                    + " — the whole NSM is keyless here; the portal UI needs no login for the same data"),
            result=result,
            evidence=[{"quote": f"{x.get('company') or '—'} · {x.get('type') or '—'} · {(x.get('publication_date') or '—')[:10]}"
                                + (f" · {x.get('headline') or '—'}" if x.get("headline") else ""),
                       "url": x.get("document_url") or "https://data.fca.org.uk/"} for x in rows[:5]],
            provider_id="gb_fca", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def gb_fca_official_list(self, *, listing_category=None, lei=None, security_isin=None, text=None,
                             from_date=None, to_date=None, sort="security_isin", order="asc",
                             offset=0, limit=20, execution=None, no_cache=None):
        """company gb_fca_official_list: the FCA Official List — 15,160 live securities admitted
        to official UK listing across 11 categories (ISIN, security name, category, status, issuer
        LEI + name, initial admission date); rows carry only populated fields upstream (placeholder
        records omit LEI/name; a null admission date is genuine data); --text matches ISIN, LEI or
        issuer name, NOT the security name."""
        self._co_only("gb_fca_official_list")
        r = company.gb_fca.official_list(
            listing_category=listing_category, lei=lei, security_isin=security_isin, text=text,
            from_date=from_date, to_date=to_date, sort=sort, order=order, offset=offset,
            limit=limit, cache=self._c._cache,
            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="gb_fca_official_list",
            input={k: v for k, v in result["params"].items()},
            reason=(f"FCA Official List: {result['total']:,} live securities"
                    + (f" ({listing_category[0]}…)" if listing_category else "")
                    + f" — {len(rows)} rows from offset {result['offset']}"
                    + (f", top {top.get('security_name') or top.get('issuer_name') or '—'}"
                       f" ({top.get('security_isin') or '—'}, {top.get('listing_category') or '—'})" if top else "")
                    + " — the regulator's Official List, not an exchange feed; join onto LEI/ISIN"),
            result=result,
            evidence=[{"quote": f"{x.get('security_name') or x.get('issuer_name') or '—'} · ISIN {x.get('security_isin') or '—'}"
                                f" · {x.get('listing_category') or '—'} · {x.get('security_status') or '—'}"
                                + (f" · admitted {(x.get('security_initial_admission_date') or '')[:10]}" if x.get("security_initial_admission_date") else ""),
                       "url": "https://data.fca.org.uk/"} for x in rows[:5]],
            provider_id="gb_fca", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def gb_fca_official_list_activity(self, *, security_activity, from_date=None, to_date=None,
                                      sort="security_effective_datetime", order="desc", offset=0,
                                      limit=20, execution=None, no_cache=None):
        """company gb_fca_official_list_activity: the Official List daily event log — admissions
        (102,667 all-time), cancellations (16,204), suspensions (733), restorations (206) with
        effective datetime, ISIN, issuer LEI, category; the four kinds are separate queries
        (security_activity REQUIRED and validated here — an unknown value would silently answer
        the whole log upstream)."""
        self._co_only("gb_fca_official_list_activity")
        r = company.gb_fca.official_list_activity(
            security_activity=security_activity, from_date=from_date, to_date=to_date, sort=sort,
            order=order, offset=offset, limit=limit, cache=self._c._cache,
            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="gb_fca_official_list_activity",
            input={k: v for k, v in result["params"].items()},
            reason=(f"Official List {security_activity}: {result['total']:,} events all-time"
                    + f" — {len(rows)} rows from offset {result['offset']}"
                    + (f", top effective {(top.get('security_effective_datetime') or '—')[:19].replace('T', ' ')}"
                       f" · ISIN {top.get('security_isin') or '—'}" if top else "")
                    + " — the listing-life-cycle audit trail behind the Official List snapshot"),
            result=result,
            evidence=[{"quote": f"{(x.get('security_effective_datetime') or '—')[:19].replace('T', ' ')} · ISIN {x.get('security_isin') or '—'}"
                                f" · {x.get('security_name') or x.get('issuer_name') or '—'} · {x.get('listing_category') or '—'}",
                       "url": "https://data.fca.org.uk/"} for x in rows[:5]],
            provider_id="gb_fca", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def gb_lse_bond_details(self, *, tidm, execution=None, no_cache=None):
        """company gb_lse_bond_details: the LSE security-details card (GB — isin/sedol/
        listingDate/fullName/currencyCode/mifirIdentifierCode/maturityDate; LIVE REVERSAL
        2026-11-24: the face answers EQUITY tidms too — BARC returns a full card with
        maturityDate null (the research doc's "equities answer 404" was wrong); an unknown
        tidm answers the honest 404 → found=false)."""
        self._co_only("gb_lse_bond_details")
        r = company.gb_lse.bond_details(tidm=tidm, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        card = result.get("card") or {}
        if r["found"]:
            reason = (f"LSE security card {r['tidm']}: {card.get('fullName') or '—'}"
                      f" · ISIN {card.get('isin') or '—'} · {card.get('currencyCode') or '—'}"
                      f" · listed {card.get('listingDate') or '—'}"
                      f" · maturity {card.get('maturityDate') or '—'}"
                      f" · mifir {card.get('mifirIdentifierCode') or '—'}")
        else:
            reason = (f"LSE security card {r['tidm']}: not found (honest 404 — no such "
                      f"instrument upstream; check the tidm on gb_lse_universe)")
        return self._flat_env(
            tool="gb_lse_bond_details",
            input={"tidm": r["tidm"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{card.get('fullName') or r['tidm']} · ISIN {card.get('isin') or '—'}"
                                f" · {card.get('currencyCode') or '—'} · listed {card.get('listingDate') or '—'}"
                                f" · maturity {card.get('maturityDate') or '—'}",
                       "url": f"https://www.londonstockexchange.com/en/quote/bonds/{r['tidm']}"}]
                      if r["found"] else [],
            provider_id="gb-lse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://apidata.londonstockexchange.com/cmdf/v1/securitybonddetails?tidm={r['tidm']}",
                                "note": "generic security-details card — equities answer with maturityDate null"}},
        )

    def gb_lse_fundamentals(self, *, ric, execution=None, no_cache=None):
        """company gb_lse_fundamentals: the LSE fundamentals card keyed by RIC (GB — PE/EPS/
        free-float/outstanding/market-cap verbatim; UK cards m GBP, international-book cards m EUR —
        the upstream's own figures, never re-unit-ed)."""
        self._co_only("gb_lse_fundamentals")
        r = company.gb_lse.fundamentals(ric=ric, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        row = result.get("row") or {}
        if r["found"]:
            reason = (f"LSE fundamentals {r['ric']}: PE {row.get('pe_ratio') or '—'} · EPS "
                      f"{row.get('earnings_per_share') or '—'} · free float "
                      f"{row.get('free_float_shares') or '—'} · outstanding "
                      f"{row.get('outstanding_shares') or '—'} · mcap "
                      f"{row.get('company_market_cap') or '—'} (m)")
        else:
            reason = (f"LSE fundamentals {r['ric']}: not found (check the RIC on "
                      f"gb_lse_ric_lookup — the face keys on the LSE RIC, BARC.L form)")
        return self._flat_env(
            tool="gb_lse_fundamentals",
            input={"ric": r["ric"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{r['ric']} · PE {row.get('pe_ratio') or '—'} · EPS "
                                f"{row.get('earnings_per_share') or '—'} · free float "
                                f"{row.get('free_float_shares') or '—'} · mcap "
                                f"{row.get('company_market_cap') or '—'} (m)",
                       "url": "https://www.londonstockexchange.com/"}] if r["found"] else [],
            provider_id="gb-lse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://apidata.londonstockexchange.com/fundamentals/v1/lookup?ric={r['ric']}"}},
        )

    def gb_lse_index_membership(self, *, tidm, execution=None, no_cache=None):
        """company gb_lse_index_membership: the instrument's FTSE index memberships with weights
        (GB — indexCode/indexName/indexWeight are PARALLEL comma lists, an empty slot = not a member;
        strict zip alignment, rows only for actual memberships; the full card rides result.card)."""
        self._co_only("gb_lse_index_membership")
        r = company.gb_lse.index_membership(tidm=tidm, cache=self._c._cache,
                                            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        card = result.get("card") or {}
        if r["found"]:
            wset = ", ".join(f"{x['index_code']} {x['index_weight']}%" for x in rows[:4])
            reason = (f"LSE FTSE memberships {r['tidm']}: {result['total']} of 11 index slots"
                      f" ({wset}{' …' if result['total'] > 4 else ''})"
                      f" — primary {card.get('primaryIndexName') or '—'}, constituent {card.get('constituentCode') or '—'}")
        else:
            reason = (f"LSE FTSE memberships {r['tidm']}: not found (check the tidm on gb_lse_universe)")
        return self._flat_env(
            tool="gb_lse_index_membership",
            input={"tidm": r["tidm"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{x['index_code']} · {x['index_name']} · weight {x['index_weight']}%",
                       "url": f"https://www.londonstockexchange.com/en/quote/equity/{r['tidm']}"} for x in rows[:5]],
            provider_id="gb-lse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://apidata.londonstockexchange.com/cmdf/v1/ftseindexconstituents?tidm={r['tidm']}"}},
        )

    def gb_lse_issuer_address(self, *, issuer_code, execution=None, no_cache=None):
        """company gb_lse_issuer_address: the issuer's registered address and website (GB —
        issuerCode from the gb_lse_security_master card)."""
        self._co_only("gb_lse_issuer_address")
        r = company.gb_lse.issuer_address(issuer_code=issuer_code, cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        row = result.get("row") or {}
        if r["found"]:
            addr = " ".join(str(row.get("fullAddress") or "").split())
            reason = (f"LSE issuer {r['issuer_code']}: {addr[:80]}"
                      f" · website {row.get('websiteLink') or row.get('website') or '—'}")
        else:
            reason = (f"LSE issuer {r['issuer_code']}: not found (the issuerCode comes off the "
                      f"gb_lse_security_master card)")
        return self._flat_env(
            tool="gb_lse_issuer_address",
            input={"issuer_code": r["issuer_code"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{r['issuer_code']} · {' '.join(str(row.get('fullAddress') or '').split())[:80]}"
                                f" · {row.get('websiteLink') or row.get('website') or '—'}",
                       "url": "https://www.londonstockexchange.com/"}] if r["found"] else [],
            provider_id="gb-lse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://apidata.londonstockexchange.com/issuer-address-website/v1?issuerCode={r['issuer_code']}"}},
        )

    def gb_lse_issuer_profile(self, *, code, execution=None, no_cache=None):
        """company gb_lse_issuer_profile: the issuer's own IR card on the LSEG issuer-services cache
        (GB — instruments[] family with tidm+ISIN+type, admissiondate, sector/indices, contacts,
        reports/events; coverage is ISSUER-OPTED — VOVOD answers a 33-instrument card, BASDE an
        honest 404 → found=false, never fabricated; the profile code is the nrdp displayissuercode,
        NOT the ticker — Vodafone's ticker is VOD, its issuer code VOVOD)."""
        self._co_only("gb_lse_issuer_profile")
        r = company.gb_lse.issuer_profile(code=code, cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        prof = result.get("profile") or {}
        inst = result.get("instruments") or []
        mi = prof.get("marketinformation") or {}
        if r["found"]:
            reason = (f"LSE issuer profile {r['code']}: {prof.get('name') or '—'}"
                      f" · {len(inst)} instruments (primary {prof.get('primaryInstrument') or '—'})"
                      f" · admitted {mi.get('admissiondate') or '—'}"
                      f" · sector {(prof.get('tradinginformation') or {}).get('sector') or '—'}")
        else:
            reason = (f"LSE issuer profile {r['code']}: not found (coverage is issuer-opted — "
                      f"uncarded issuers answer an honest 404; iterate nrdp displayissuercode to find carded ones)")
        return self._flat_env(
            tool="gb_lse_issuer_profile",
            input={"code": r["code"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{prof.get('name') or r['code']} · {len(inst)} instruments · admitted "
                                f"{mi.get('admissiondate') or '—'} · "
                                f"{(prof.get('tradinginformation') or {}).get('sector') or '—'}",
                       "url": f"https://cache-api.lsegissuerservices.com/profile/{r['code']}"}]
                      if r["found"] else [],
            provider_id="gb-lse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://cache-api.lsegissuerservices.com/profile/{r['code']}"}},
        )

    def gb_lse_ric_lookup(self, *, tidm, execution=None, no_cache=None):
        """company gb_lse_ric_lookup: the tidm→RIC bridge (GB — BARC→BARC.L; the RIC keys
        gb_lse_fundamentals)."""
        self._co_only("gb_lse_ric_lookup")
        r = company.gb_lse.ric_lookup(tidm=tidm, cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        if r["found"]:
            reason = f"LSE RIC bridge {r['tidm']} → {r['ric']}"
        else:
            reason = f"LSE RIC bridge {r['tidm']}: not resolved (check the tidm on gb_lse_universe)"
        return self._flat_env(
            tool="gb_lse_ric_lookup",
            input={"tidm": r["tidm"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{r['tidm']} → {r['ric']}",
                       "url": "https://www.londonstockexchange.com/"}] if r["found"] else [],
            provider_id="gb-lse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://apidata.londonstockexchange.com/rdp/v1/ric?tidm={r['tidm']}"}},
        )

    def gb_lse_rns_archive(self, *, month, category=None, limit=None, execution=None, no_cache=None):
        """company gb_lse_rns_archive: one month's RNS article index (GB — rows {url, category,
        hash}; the slug is the RNS category (form-8-3 Takeover Code 1%+ disclosures ≈ 2,938/month,
        form-8-5 EPT ≈ 1,870/month) but it is a category-company MELT — never read it as a company
        name. Archive floor 2024-11 (older months answer S3 AccessDenied — refused locally); the
        rolling ~25-month window is the depth ceiling)."""
        self._co_only("gb_lse_rns_archive")
        r = company.gb_lse.rns_archive(month=month, category=category, limit=limit,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        reason = (f"LSE RNS archive {r['month']}: {result['total']:,} articles"
                  + (f" ({result['total']:,} filtered to category~\"{category}\" → {len(rows)} rows)"
                     if category else "")
                  + (f" — top {top['category']}" if top else ""))
        return self._flat_env(
            tool="gb_lse_rns_archive",
            input={"month": r["month"], "category": category, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x['category']} · {x['hash']}", "url": x["url"]} for x in rows[:5]],
            provider_id="gb-lse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://www.londonstockexchange.com/en/sitemap-news-{r['month']}.xml",
                                "window": "2024-11 floor (older months answer S3 AccessDenied)"}},
        )

    def gb_lse_rns_article(self, *, url, execution=None, no_cache=None):
        """company gb_lse_rns_article: the RNS article's server-embedded full disclosure body (GB —
        the JS-string articleBody decoded (\\x22/\\uXXXX/\\/ escapes), the RichTextGrid metadata
        (Company information / Released On / Source / RNS Number) parsed, ISINs extracted from the
        body (UK/IE issuers and NAV notes carry them; US-target form-8-3 bodies legitimately carry
        none — the upstream's own absence)."""
        self._co_only("gb_lse_rns_article")
        r = company.gb_lse.rns_article(url=url, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        md = result.get("metadata") or {}
        if r["found"]:
            reason = (f"LSE RNS article: {result.get('title') or '—'}"
                      f" · disclosed by {md.get('Company information') or '—'}"
                      f" · RNS {md.get('RNS Number') or '—'}"
                      f" · released {md.get('Released On') or '—'}"
                      f" · body {result['body_chars']:,} chars"
                      + (f" · ISINs {', '.join(result['isins'][:4])}{'…' if len(result['isins']) > 4 else ''}"
                         if result.get("isins") else " · no ISIN in body"))
        else:
            reason = ("LSE RNS article: the page carries no articleBody (a removed article answers an "
                      "honest miss — check the url on gb_lse_rns_archive)")
        return self._flat_env(
            tool="gb_lse_rns_article",
            input={"url": r["url"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{md.get('Company information') or '—'} · RNS "
                                f"{md.get('RNS Number') or '—'} · {result['body_chars']:,} chars"
                                + (f" · ISIN {result['isins'][0]}" if result.get("isins") else ""),
                       "url": r["url"]}] if r["found"] else [],
            provider_id="gb-lse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": r["url"], "panel": "articleBody (server-embedded)"}},
        )

    def gb_lse_security_master(self, *, tidm, execution=None, no_cache=None):
        """company gb_lse_security_master: the nrdp join-key card (GB — instrumentId/isinCode/sedol/
        mic XLON|XLOM/issuerCode/firstTradingDate/typology; the issuerCode feeds gb_lse_issuer_address,
        the displayissuercode feeds gb_lse_issuer_profile, the tidm feeds the ric bridge)."""
        self._co_only("gb_lse_security_master")
        r = company.gb_lse.security_master(tidm=tidm, cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        card = result.get("card") or {}
        if r["found"]:
            reason = (f"LSE master {r['tidm']}: {card.get('instrumentName') or '—'}"
                      f" · ISIN {card.get('isinCode') or '—'} · SEDOL {card.get('sedol') or '—'}"
                      f" · MIC {card.get('mic') or '—'} · issuer {card.get('issuerCode') or '—'}"
                      f" · first trade {card.get('firstTradingDate') or '—'}"
                      f" · {card.get('typology') or '—'}")
        else:
            reason = (f"LSE master {r['tidm']}: not found (check the tidm on gb_lse_universe — "
                      f"UK ticker BARC form or international SEDOL 0A00 form)")
        return self._flat_env(
            tool="gb_lse_security_master",
            input={"tidm": r["tidm"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{r['tidm']} · {card.get('instrumentName') or '—'} · ISIN "
                                f"{card.get('isinCode') or '—'} · MIC {card.get('mic') or '—'} · issuer "
                                f"{card.get('issuerCode') or '—'}",
                       "url": f"https://www.londonstockexchange.com/en/quote/equity/{r['tidm']}"}]
                      if r["found"] else [],
            provider_id="gb-lse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://apidata.londonstockexchange.com/nrdp/v1?tidm={r['tidm']}"}},
        )

    def gb_lse_universe(self, *, book="equity", limit=None, execution=None, no_cache=None):
        """company gb_lse_universe: the LSE quote-page sitemap enumeration (GB — the TIDM
        enumeration source: rows {book, tidm, slug, url}; five books totalling 62,713 pages,
        equity 5,761 probe day; UK tickers BARC form plus international SEDOL 0A00 form — the
        LSE international order book)."""
        self._co_only("gb_lse_universe")
        r = company.gb_lse.universe(book=book, limit=limit, cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        reason = (f"LSE universe {r['book']}: {result['total']:,} quote pages"
                  + (f" — sample {top['tidm']} ({top['slug']})" if top else ""))
        return self._flat_env(
            tool="gb_lse_universe",
            input={"book": r["book"], "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x['book']}/{x['tidm']} · {x['slug']}", "url": x["url"]} for x in rows[:5]],
            provider_id="gb-lse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://www.londonstockexchange.com/en/sitemap-security-{r['book']}.xml"}},
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

    # —— 0.3.75 E17 EDGAR holdings-disclosure family (dictionary slots: us_sec_13dg_stakes < us_sec_13f_holdings <
    # us_sec_companyconcept ('1'<'c'), us_sec_form4 between filing_document and frames ('fi'<'fo'<'fr')):
    # the holdings-disclosure layer under the filings line — submissions=index, fts=hits, xbrl=facts,
    # filing_document=bytes,
    # THIS adds the three structured ownership schemas parsed live: 13F institutional holdings, Form 4/5
    # insider transactions, Schedule 13D/G activist stakes (probe-e17 2026-11-23; zero new provider
    # buckets — edgar_cik submissions + edgar_arch index/doc ride again; the XSL-shell law: 13F/13DG
    # primaryDocument points at the human rendering, the raw XML sits at the accession root).
    def us_sec_13dg_stakes(self, *, cik, limit=5, execution=None, no_cache=None):
        """company us_sec_13dg_stakes: Schedule 13D/G activist stakes on one CIK (issuer OR filer
        side — jointly filed) — submissions enumeration over the EIGHT form strings (structured era
        "SCHEDULE 13D/G(/A)" AND legacy HTML era "SC 13D/G(/A)"), 2022+ edgarSubmission XML parsed
        to filer cards (name/type/citizenship/shares/class percent/four powers); legacy HTML rides
        parsed=False with doc_url — never a fabricated stake."""
        self._co_only("us_sec_13dg_stakes")
        cik10 = company.edgar_cik.normalize_cik(cik)
        n = min(max(1, int(limit or 5)), 50)
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        r = company.edgar_ownership.fetch_13dg_filings(cik10, limit=n, cache=cache, no_cache=nc)
        result = {k: x for k, x in r.items() if k != "_meta"}
        first = next((f for f in result["filings"] if f.get("parsed")), None)
        stake = ""
        if first:
            fl = first.get("filers") or [{}]
            stake = (f", e.g. {fl[0].get('name') or '?'} on {first.get('issuer_name') or '?'}"
                     f" ({fl[0].get('class_percent') or 'pct n/a'} of class)" if first else "")
        return self._flat_env(
            tool="us_sec_13dg_stakes",
            input={"cik": cik10, "limit": result["filings_scanned"]},
            reason=(f"SEC Schedule 13D/G: {result['filings_scanned']} newest filings under CIK "
                    f"{int(cik10)} — {result['structured_total']} structured (2022+ edgarSubmission "
                    f"XML parsed to filer cards){stake}; the rest are legacy HTML era (SC 13D/G form "
                    "strings) riding parsed=False with doc_url — eight form strings because "
                    "submissions carries both families"),
            result=result,
            evidence=[{"quote": f"{f['form']} filed {f['filing_date']} — "
                                + (f"{len(f.get('filers') or [])} filer(s), issuer "
                                   f"{f.get('issuer_name') or '?'}" if f.get("parsed")
                                   else "legacy HTML (metadata only)"),
                       "url": f["doc_url"]}
                      for f in result["filings"][:5]],
            provider_id="edgar_ownership", metas=[r["_meta"]],
            query={"source": "live", "upstream": {"submissions": f"CIK{cik10}",
                                                  "forms": "SCHEDULE|SC 13D/G 8-string union"}},
        )

    def us_sec_13f_holdings(self, *, cik, limit=1, execution=None, no_cache=None):
        """company us_sec_13f_holdings: 13F-HR institutional holdings of one filer CIK — the
        information table parsed to position rows (issuer/class/cusip/value/shares/discretion/
        voting powers). value_units rides the card (2023-Q1+ whole USD, earlier thousands — never
        unit-ambiguous sums)."""
        self._co_only("us_sec_13f_holdings")
        cik10 = company.edgar_cik.normalize_cik(cik)
        n = min(max(1, int(limit or 1)), 50)
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        r = company.edgar_ownership.fetch_13f_filings(cik10, limit=n, cache=cache, no_cache=nc)
        result = {k: x for k, x in r.items() if k != "_meta"}
        first = result["filings"][0]
        units = first["value_units"]
        vsum = first.get("value_total")
        return self._flat_env(
            tool="us_sec_13f_holdings",
            input={"cik": cik10, "limit": result["filings_scanned"]},
            reason=(f"SEC 13F: {first['form']} filed {first['filing_date']} (report "
                    f"{first['report_date'] or 'n/a'}) — {first['holdings_total']} positions, "
                    f"value sum {vsum if vsum is not None else 'n/a'} ({units}; 2023-Q1+ whole "
                    "USD, earlier thousands of USD — the units switch is period-based, the card "
                    "always carries it)"),
            result=result,
            evidence=[{"quote": json.dumps(first["rows"][0], default=str)},
                      {"quote": f"{first['accession']} information table {first['information_table']} "
                                f"({first['holdings_total']} rows)",
                       "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/"
                              f"{first['accession'].replace('-', '')}/{first['information_table']}"}]
                      if first["rows"] else [],
            provider_id="edgar_ownership", metas=[r["_meta"]],
            query={"source": "live", "upstream": {"submissions": f"CIK{cik10}",
                                                  "forms": "13F-HR, 13F-HR/A"}},
        )

    def us_sec_form4_transactions(self, *, cik, form="4", limit=5, execution=None, no_cache=None):
        """company us_sec_form4_transactions: Form 4/5 insider transactions under one CIK (issuer
        or insider — jointly filed) — the ownershipDocument XML parsed to flattened transaction
        lines (date/code/shares/price/A-D/post-shares/direct-indirect; derivative lines carry
        exercise/expiration/underlying)."""
        self._co_only("us_sec_form4_transactions")
        cik10 = company.edgar_cik.normalize_cik(cik)
        raw_form = str(form or "4").strip()
        if raw_form not in company.edgar_ownership._FORM4_FORMS:
            raise SdkError("usage_error", provider="edgar_ownership",
                           detail=f"form must be one of {', '.join(company.edgar_ownership._FORM4_FORMS)} "
                                  f"(got \"{form}\")")
        n = min(max(1, int(limit or 5)), 100)
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        r = company.edgar_ownership.fetch_form4_filings(cik10, form=raw_form, limit=n,
                                                        cache=cache, no_cache=nc)
        result = {k: x for k, x in r.items() if k != "_meta"}
        tx_total = sum(len(f.get("rows") or []) for f in result["filings"])
        issuer = next((f.get("issuer") or {} for f in result["filings"] if f.get("issuer")), {})
        return self._flat_env(
            tool="us_sec_form4_transactions",
            input={"cik": cik10, "form": raw_form, "limit": result["filings_scanned"]},
            reason=(f"SEC Form {raw_form}: {result['filings_scanned']} newest filings under CIK "
                    f"{int(cik10)} (issuer side {issuer.get('name') or '?'}, jointly filed under "
                    f"insider CIKs too) — {tx_total} transaction lines parsed from the "
                    "ownershipDocument XML"),
            result=result,
            evidence=[{"quote": json.dumps((result["filings"][0].get("rows") or [{}])[0], default=str)},
                      {"quote": f"{result['filings'][0]['accession']} ({result['filings'][0]['filing_date']})",
                       "url": result["filings"][0]["doc_url"]}],
            provider_id="edgar_ownership", metas=[r["_meta"]],
            query={"source": "live", "upstream": {"submissions": f"CIK{cik10}",
                                                  "forms": raw_form}},
        )

    # —— 0.3.66 SEC XBRL structured-facts family (dictionary order: us_sec_companyconcept <
    # us_sec_companyfacts < us_sec_frames < us_sec_fulltext_search — 'c'<'f'; the quantitative layer under the
    # edgar_cik registry layer — the 2026-10-19 deferral reopened 2026-11-17: the local XBRL
    # bulk it leaned on was lost with the E: drive and the MCP/OmniHub surface carries no
    # financial-data paths. Names carry the us_ jurisdiction prefix from birth — the whole
    # cluster was renamed pre-release 2026-11-17 (user ruling: one pass, docs included); the
    # two faces that had shipped (submissions/fulltext_search) keep deprecated sec_* aliases) ——

    def us_sec_companyconcept(self, *, cik, concept, taxonomy="us-gaap", form=None,
                              execution=None, no_cache=None):
        """company us_sec_companyconcept: single-concept server-side time series (the cheap point
        query — 18KB vs companyfacts' 4MB; 404 = the issuer never filed this concept)."""
        self._co_only("us_sec_companyconcept")
        cik10 = company.edgar_cik.normalize_cik(cik)
        raw_tx = company.edgar_xbrl._clean_tag(taxonomy, "taxonomy", company.edgar_xbrl._TAX_RE)
        tag = company.edgar_xbrl._clean_tag(concept, "concept")
        raw_form = str(form or "").strip() or None
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        r = company.edgar_xbrl.concept_raw(cik10, raw_tx, tag, cache=cache, no_cache=nc)
        card = company.edgar_xbrl.concept_from_upstream(r["data"] or {}, raw_form)
        latest = card.get("latest_fact") or {}
        return self._flat_env(
            tool="us_sec_companyconcept",
            input={"cik": cik10, "taxonomy": raw_tx, "concept": tag, "form": raw_form},
            reason=(f"SEC XBRL concept: {card['entity_name']} {raw_tx}/{tag} — {card['facts_total']} facts"
                    + (f" (form filter {raw_form}: {card['facts_before_form_filter']} before)" if raw_form else "")
                    + (f", latest {latest.get('val'):,} ({latest.get('form')} filed {latest.get('filed')})"
                       if latest else ", no facts survive the filter")),
            result=card,
            evidence=[{"quote": json.dumps(latest, default=str)},
                      {"quote": f"{card['entity_name']} — {tag}: {card.get('label') or '—'}",
                       "url": f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik10}/{raw_tx}/{tag}.json"}],
            provider_id="edgar_xbrl", metas=[r],
            query={"source": "raw", "upstream": {"cik10": cik10, "taxonomy": raw_tx, "tag": tag}},
        )

    def us_sec_companyfacts(self, *, cik, taxonomy=None, concept=None, form=None,
                            execution=None, no_cache=None):
        """company us_sec_companyfacts: issuer-level XBRL dump — inventory mode (no concept:
        taxonomy → concept-name list, the drift-discovery face) XOR concept mode (the tag's
        full series across taxonomies). Concept names pass through VERBATIM — they drift
        (Revenues → RevenueFromContractWithCustomerExcludingAssessedTax after 2018) and
        issuers simply lack some (Apple has no EarningsPerShareDiluted)."""
        self._co_only("us_sec_companyfacts")
        cik10 = company.edgar_cik.normalize_cik(cik)
        raw_tx = str(taxonomy or "").strip() or None
        if raw_tx is not None:
            company.edgar_xbrl._clean_tag(raw_tx, "taxonomy", company.edgar_xbrl._TAX_RE)
        raw_form = str(form or "").strip() or None
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        r = company.edgar_xbrl.facts_raw(cik10, cache=cache, no_cache=nc)
        d = r["data"] or {}
        name = d.get("entityName") or "(no name)"
        if not concept:
            if raw_tx and raw_tx not in (d.get("facts") or {}):
                raise SdkError("usage_error", provider="edgar_xbrl",
                               detail=f"taxonomy {raw_tx} not present for CIK {int(cik10)} "
                                      f"(present: {', '.join(sorted((d.get('facts') or {}).keys())) or 'none'})")
            inv = company.edgar_xbrl.inventory_from_upstream(d)
            if raw_tx:
                inv["taxonomies"] = {raw_tx: inv["taxonomies"][raw_tx]}
                inv["concepts"] = {raw_tx: inv["concepts"][raw_tx]}
            total = sum(inv["taxonomies"].values())
            return self._flat_env(
                tool="us_sec_companyfacts",
                input={"cik": cik10, "taxonomy": raw_tx, "concept": None, "form": None},
                reason=(f"SEC XBRL inventory: CIK {int(cik10)} {name} — "
                        + " / ".join(f"{tx} {n}" for tx, n in inv["taxonomies"].items())
                        + f" = {total} concepts (names verbatim — they drift across taxonomies; "
                        + "point-queries ride --concept)"),
                result=inv,
                evidence=[{"quote": f"{tx}: {', '.join(inv['concepts'][tx][:4])}"
                                    + (f", … ({n} concepts)" if n > 4 else "")}
                          for tx, n in inv["taxonomies"].items()],
                provider_id="edgar_xbrl", metas=[r],
                query={"source": "raw", "upstream": {"cik10": cik10}},
            )
        tag = company.edgar_xbrl._clean_tag(concept, "concept")
        card = company.edgar_xbrl.concept_from_dump(d, tag, raw_form)
        if card is None:
            raise SdkError("usage_error", provider="edgar_xbrl",
                           detail=f"concept {tag} not in CIK {int(cik10)}'s facts (an absent concept is a "
                                  f"legal answer — issuers lack concepts; call without --concept for the "
                                  f"inventory of what this issuer DOES file; names drift: Revenues → "
                                  f"RevenueFromContractWithCustomerExcludingAssessedTax)")
        latest = card.get("latest_fact") or {}
        return self._flat_env(
            tool="us_sec_companyfacts",
            input={"cik": cik10, "taxonomy": raw_tx, "concept": tag, "form": raw_form},
            reason=(f"SEC XBRL facts: {name} {card['taxonomy']}/{tag} — {card['facts_total']} facts"
                    + (f" (form filter {raw_form}: {card['facts_before_form_filter']} before)" if raw_form else "")
                    + (f", latest {latest.get('val'):,} ({latest.get('form')} filed {latest.get('filed')})"
                       if latest else ", no facts survive the filter")),
            result=card,
            evidence=[{"quote": json.dumps(company.edgar_xbrl._latest_fact(card["units"]), default=str)},
                      {"quote": f"{card['taxonomy']}/{tag} — {card['facts_total']} facts verbatim",
                       "url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"}],
            provider_id="edgar_xbrl", metas=[r],
            query={"source": "raw", "upstream": {"cik10": cik10}},
        )

    # —— 0.3.69 E11 filing-document body fetch (dictionary order: us_sec_filing_document sorts
    # between us_sec_companyfacts and us_sec_frames — 'fi' between 'co' and 'fr'): the body-fetch
    # face the filings line lacked; every prior us_sec face is index/structured (submissions =
    # filing index, fts = full-text hit metadata, xbrl = facts), doc_url links were the only door
    # to the bytes themselves.
    def us_sec_filing_document(self, *, cik=None, accession=None, filename=None, url=None,
                               text=None, list_mode=None, execution=None, no_cache=None):
        """company us_sec_filing_document: fetch a filed document's bytes from EDGAR Archives
        (verbatim; --text strips HTML) — 8-K bodies, EX-99 exhibits, 10-K iXBRL, whatever the
        accession directory carries. Forms: --url (the doc_url us_sec_fulltext_search returns)
        XOR --cik + --accession (filename optional: submissions primaryDocument > single index
        candidate > usage_error naming candidates). --list: the accession directory table."""
        self._co_only("us_sec_filing_document")
        want_text = bool(text)
        want_list = bool(list_mode)
        if want_list and want_text:
            raise SdkError("usage_error", provider="edgar_arch",
                           detail="--list and --text are two different modes of one face — call twice")
        has_url = bool(str(url or "").strip())
        has_pair = bool(str(cik or "").strip()) and bool(str(accession or "").strip())
        if not has_url and not has_pair:
            raise SdkError("usage_error", provider="edgar_arch",
                           detail="us_sec_filing_document needs --url (a www.sec.gov/Archives/... "
                                  "document URL, the doc_url us_sec_fulltext_search returns) or "
                                  "--cik + --accession")
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        if want_list:
            out = company.edgar_arch.fetch_index(cik=cik, accession=accession, url=url,
                                                 cache=cache, no_cache=nc)
            docs = [r for r in out["rows"] if r["is_document"]]
            return self._flat_env(
                tool="us_sec_filing_document",
                input={"cik": out["cik"], "accession": out["accession"], "list": True},
                reason=(f"SEC Archives directory {out['accession']}: {out['total']} rows, "
                        f"{out['documents']} filed documents (scaffold rows — the auto-generated "
                        "index/headers/.txt entries — are flagged, never counted as documents; "
                        "a scaffold-only dir is upstream_not_found: the bogus-accession shape, "
                        "the upstream answers 200 with a ghost listing)"),
                result={**{k: out[k] for k in ("cik", "accession", "total", "documents", "rows",
                                               "dir_url")}},
                evidence=[{"quote": f"{r['name']} — {r['size']} bytes" + (" (scaffold)" if r["scaffold"] else ""),
                           "url": out["dir_url"]} for r in out["rows"][:5]],
                provider_id="edgar_arch", metas=[out["_meta"]],
                query={"source": "live", "upstream": {"archive_dir": out["dir_url"]}},
            )
        out = company.edgar_arch.fetch_document(cik=cik, accession=accession, filename=filename,
                                                url=url, want_text=want_text, cache=cache, no_cache=nc)
        env = out.get("envelope")
        metas = [out["_meta"]]
        for extra in (out.get("_index_meta"), out.get("_submissions_meta")):
            if extra:
                metas.append(extra)
        quote = (out["text"] if want_text else out["content"]) or ""
        head = " ".join(quote[:220].split())
        via_note = {"given": "explicit --filename",
                    "submissions_primary": "primaryDocument from the submissions recent window",
                    "index_single": "the accession directory carries exactly one document"}.get(
                        out.get("filename_via"), out.get("filename_via"))
        return self._flat_env(
            tool="us_sec_filing_document",
            input=out["params"],
            reason=(f"SEC Archives {out['accession']} / {out['filename']} — {out['size_bytes']:,}B "
                    f"sha256 {out['sha256'][:12]}… ({via_note}; "
                    + (f"SGML envelope split: TYPE={env.get('type')}, SEQ={env.get('sequence')}"
                       f", DESC={env.get('description')}" if env else
                       "no SGML envelope — modern filings serve bare iXBRL/HTML")
                    + ("; --text stripped the HTML" if want_text else "") + ")"),
            result={k: out[k] for k in ("cik", "accession", "filename", "url", "envelope",
                                        "envelope_split", "size_bytes", "sha256", "encoding_used",
                                        "content", "text", "filename_via")},
            evidence=[{"quote": head + ("…" if len(quote) > 220 else ""), "url": out["url"]}],
            provider_id="edgar_arch", metas=metas,
            query={"source": "live", "upstream": {"archive_doc": out["url"]}},
        )

    def us_sec_frames(self, *, concept, frame, taxonomy="us-gaap", unit="USD",
                      execution=None, no_cache=None):
        """company us_sec_frames: one concept × unit × period cross-section — every filer that
        reported the concept in the frame, one shot (NetIncomeLoss CY2024 = 6,084 entities).
        Frames: CY<year> / CY<year>Q<n> / CY<year>Q<n>I (instant)."""
        self._co_only("us_sec_frames")
        raw_tx = company.edgar_xbrl._clean_tag(taxonomy, "taxonomy", company.edgar_xbrl._TAX_RE)
        tag = company.edgar_xbrl._clean_tag(concept, "concept")
        raw_unit = company.edgar_xbrl._clean_tag(unit, "unit", company.edgar_xbrl._TAX_RE)
        raw_frame = str(frame or "").strip()
        if not company.edgar_xbrl._FRAME_RE.match(raw_frame):
            raise SdkError("usage_error", provider="edgar_xbrl",
                           detail=f"frame must be CY<year> / CY<year>Q<n> / CY<year>Q<n>I (got \"{frame}\")")
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        r = company.edgar_xbrl.frames_raw(raw_tx, tag, raw_unit, raw_frame, cache=cache, no_cache=nc)
        result = company.edgar_xbrl.frames_from_upstream(r["data"] or {})
        rows = result["rows"]
        vals = [x.get("val") for x in rows if isinstance(x.get("val"), (int, float))]
        rng = (f", range {min(vals):,}..{max(vals):,}" if vals else "")
        return self._flat_env(
            tool="us_sec_frames",
            input={"taxonomy": raw_tx, "concept": tag, "unit": raw_unit, "frame": raw_frame},
            reason=(f"SEC XBRL frames {raw_tx}/{tag} {raw_unit} {raw_frame}: {result['total']} entities{rng}"
                    + (" (a 404 here usually means NO issuer reported the concept in this frame — "
                       "check the frame spelling before blaming the concept)" if not rows else "")),
            result=result,
            evidence=[{"quote": json.dumps(rows[0], default=str),
                       "url": f"https://data.sec.gov/api/xbrl/frames/{raw_tx}/{tag}/{raw_unit}/{raw_frame}.json"}]
                      if rows else [],
            provider_id="edgar_xbrl", metas=[r],
            query={"source": "raw", "upstream": {"taxonomy": raw_tx, "tag": tag, "unit": raw_unit, "frame": raw_frame}},
        )

    def us_sec_fulltext_search(self, *, q, forms=None, startdt=None, enddt=None, limit=10,
                               census=None, census_entity=None, census_max_requests=400,
                               execution=None, no_cache=None):
        """company us_sec_fulltext_search: SEC filing full-text search 2001+ (EDGAR FTS four params verbatim;
        either startdt/enddt given → the other is auto-filled — a single end is silently ignored upstream
        (measured 2026-10-20); after filling, both ends are always present).
        census=True → the full-window sweep (0.3.67 §9.6 fix ticket): adaptive date bisection until every
        leaf window is exact, all pages harvested, rows deduped by _id/adsh — filings_total is the number the
        plain mode's 100-hit page systematically undercounts. census_entity applies the entity predicate
        LOCALLY (the upstream does not parse company:"..." as a field filter — probed 2026-11-17)."""
        self._co_only("us_sec_fulltext_search")
        v = str(q or "").strip()
        if not v:
            raise SdkError("usage_error", provider="edgar-fts", detail="us_sec_fulltext_search requires q (EDGAR FTS syntax)")
        if census_entity is not None and not census:
            raise SdkError("usage_error", provider="edgar-fts",
                           detail="--census-entity rides only with --census (the entity predicate is the census "
                                  "mode's local post-filter; plain mode returns one 100-hit page and must not "
                                  "pretend to filter it)")
        if census:
            r = company.edgar_fts.census(v, forms=forms, startdt=startdt, enddt=enddt,
                                         entity=census_entity, max_requests=census_max_requests,
                                         limit=limit, cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
            result = {k: x for k, x in r.items() if k != "_meta"}
            ovf = "" if result["complete"] else f", {len(result['overflow_windows'])} single-day windows still ≥10k (excluded, see overflow_windows)"
            ent = f" entity-filtered on '{result['entity']}'" if result["entity"] else ""
            return self._flat_env(
                tool="us_sec_fulltext_search", input={"q": v, "forms": forms, "startdt": startdt, "enddt": enddt,
                                       "limit": result["limit_applied"], "census": True,
                                       "census_entity": result["entity"], "census_max_requests": census_max_requests},
                reason=(f"EDGAR FTS census: {result['filings_total']} filings / {result['docs_total']} documents "
                        f"({result['requests']} requests over {len(result['windows'])} windows{ent}{ovf}), "
                        f"returning {len(result['rows'])} sample rows — adsh shares its key with the SEC corpus line"),
                result=result,
                evidence=[{"quote": f"{h['form_type'] or '—'} {h['adsh'] or '—'} = "
                                    f"{h['company'] or '—'} ({h['file_date'] or '—'})",
                           "url": h["doc_url"] or "https://efts.sec.gov/LATEST/search-index"}
                          for h in result["rows"][:5]],
                provider_id="edgar-fts", metas=[r["_meta"]],
                query={"source": "raw", "search": v,
                       "upstream": {"q": v, **({"forms": forms} if forms else {}),
                                    "window": result["window"], "pagination": "from-offset/100-page"}},
            )
        r = company.edgar_fts.search_raw(v, forms=forms, startdt=startdt, enddt=enddt,
                                           limit=limit, cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        dr = result.get("date_range")
        span = f", window {dr['startdt']}~{dr['enddt']}" if dr else ""
        cap = ", capped at ≥ this count" if result.get("total_relation") == "gte" else ""
        return self._flat_env(
            tool="us_sec_fulltext_search", input={"q": v, "forms": forms, "startdt": startdt, "enddt": enddt,
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

    def sec_fulltext_search(self, *, q, forms=None, startdt=None, enddt=None, limit=10,
                            census=None, census_entity=None, census_max_requests=400,
                            execution=None, no_cache=None):
        """company sec_fulltext_search: DEPRECATED alias of us_sec_fulltext_search (renamed
        2026-11-17 pre-release so the SEC cluster carries the us_ jurisdiction prefix like every
        other face; kept working with a DeprecationWarning, removal slated 0.4.x)."""
        warnings.warn("sec_fulltext_search is deprecated — use us_sec_fulltext_search (removal slated 0.4.x)",
                      DeprecationWarning, stacklevel=2)
        return self.us_sec_fulltext_search(q=q, forms=forms, startdt=startdt, enddt=enddt,
                                           limit=limit, census=census, census_entity=census_entity,
                                           census_max_requests=census_max_requests,
                                           execution=execution, no_cache=no_cache)

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

    # ---------- 0.3.68 E10 developed-economy exchange faces (five: SIX FQS / Euronext / Borsa /
    # JPX x2 — ca_tmx deferred: tsx.com AWS WAF JS challenge flipped on 2026-11-18 pm, p2c-p2e) ----------

    def ch_six_fqs_search(self, *, segment="EQ", columns=None, order_by="ISIN", page=1, pagesize=100,
                          execution=None, no_cache=None):
        """company ch_six_fqs_search: SIX Swiss Exchange reference query (fqs/ref.json command API,
        15-min delayed; price columns opt-in — SIX closing prices carry a commercial-use caveat)."""
        self._co_only("ch_six_fqs_search")
        r = company.ch_six_fqs.search_universe(segment, columns=columns, order_by=order_by,
                                               page=page, pagesize=pagesize,
                                               cache=self._c._cache,
                                               no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        ins = result["instruments"]
        price_cols = [c for c in result["col_names"] if c in ("ClosingPriceCHF", "NumberInIssue")]
        top = (ins or [None])[0]
        head = (f"SIX FQS segment {r['params']['where']}: {len(ins)} rows of {result['total_rows']}"
                f" (page {result['page']}/{max(1, -(-int(result['total_rows'] or 0) // result['pagesize']))}), "
                + ("price columns ON (opt-in — SIX commercial-use caveat), " if price_cols else "reference preset, ")
                + (f"top {top.get('IssuerNameFull') or '—'} ({top.get('ISIN') or '—'}, {top.get('SecTypeDesc') or '—'})"
                   if top else "empty page"))
        url = ("https://www.six-group.com/fqs/ref.json?select=%s&where=%s&orderby=%s&page=%s&pagesize=%s"
               % (r["params"]["select"], r["params"]["where"], r["params"]["orderby"],
                  result["page"], result["pagesize"]))
        return self._flat_env(
            tool="ch_six_fqs_search",
            input={"segment": str(segment).upper(), "columns": r["params"]["select"],
                   "order_by": r["params"]["orderby"], "page": result["page"],
                   "pagesize": result["pagesize"]},
            reason=head,
            result=result,
            evidence=[{"quote": f"{x.get('IssuerNameFull') or '—'} (ISIN {x.get('ISIN') or '—'}, "
                                f"{x.get('SecTypeDesc') or '—'}, sector {x.get('SBISectorDesc') or '—'})",
                       "url": url}
                      for x in ins[:5]],
            provider_id="ch_six_fqs", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.72 CH SIX official notices v2 (E14; ch_six_onot = its own provider on the
    # six-group.com host — the sheldon notice pipeline vs ch_six_fqs's reference query,
    # the edgar per-service precedent) ——

    def ch_six_official_notices(self, *, from_date=None, to_date=None, notice_type=None,
                                issuer=None, page=1, limit=None, execution=None, no_cache=None):
        """company ch_six_official_notices: SIX Swiss Exchange official notices window
        (CH — sheldon v2 find.json; ~515/week all-types, A dominates: structured-product
        barrier events; M manual / EX ex-dividend / PZ provisional / FL first-listing /
        DE delisting). The upstream show* type switches are DEAD — --notice-type filters
        the FETCHED PAGE locally (walk --page for the window's older pages); --issuer
        rides issuerWords (server-side, alive — but a PAGE-1 SNAPSHOT: partial page +
        deeper issuer pages garble persistently). pageSize pinned 100 (200 breaks paging,
        1000 answers empty — the silent-over-cap shape). Reachable ceiling ~5
        pages/window: keep windows ~1 week; totalCount can exceed the reachable rows
        (515 vs 415 on the probe window) — documented boundary, not worked around."""
        self._co_only("ch_six_official_notices")
        r = company.ch_six_onot.find(from_date=from_date, to_date=to_date,
                                     notice_type=notice_type, issuer=issuer, page=page,
                                     limit=limit, cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        result = {k: x for k, x in r.items() if k != "_meta"}
        p = r["params"]
        base = (f"SIX official notices {p['firstDate']}–{p['lastDate']}"
                + (f", issuer \"{p['issuerWords']}\"" if p.get("issuerWords") else "")
                + (f", local noticeType={str(notice_type).upper()} filter" if notice_type else ""))
        if rows:
            top = rows[0]
            reason = (base + f", page {r['page']}: {len(rows)} rows (stream totalCount "
                      f"{r['total_count']}) — newest {top.get('noticeId')} · "
                      f"{top.get('noticeType')} · {top.get('date')} · "
                      f"{str(top.get('title') or '—')[:60]} · {top.get('contact') or '—'}")
        else:
            reason = (base + f", page {r['page']}: zero rows — "
                      + ("the type filter applies to the fetched page only; walk --page for "
                         "the window's older pages" if notice_type else
                         "an empty window/page is a legitimate answer"))
        return self._flat_env(
            tool="ch_six_official_notices",
            input={"from_date": p["firstDate"], "to_date": p["lastDate"],
                   "notice_type": str(notice_type).upper() if notice_type else None,
                   "issuer": p.get("issuerWords"), "page": r["page"], "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('noticeId')} · {x.get('noticeType')} · {x.get('date')} · "
                                f"{str(x.get('title') or '—')[:70]} · {x.get('contact') or '—'}",
                       "url": ("https://www.six-group.com/sheldon/official_notices/v2/find.json?"
                               f"firstDate={p['firstDate']}&lastDate={p['lastDate']}"
                               f"&pageNumber={r['page']}&pageSize={r['pagesize']}"
                               "&sortAttribute=date&sortDirection=desc"
                               + (f"&issuerWords={p['issuerWords']}" if p.get("issuerWords") else ""))}
                      for x in rows[:5]],
            provider_id="ch_six_onot", metas=[r["_meta"]],
            query={"source": "raw", "upstream": dict(p)},
        )

    def ch_six_notice_detail(self, *, notice_id, execution=None, no_cache=None):
        """company ch_six_notice_detail: one SIX official notice in full (CH — sheldon
        v2 details/{noticeId}.json; 11 keys: number/isin/text full body/contact/
        contactPerson/contactPhone/valorNumber + the list-row echoes — person/phone/
        valor are null on many rows, verbatim). FL first-listing titles are BARE DATE
        STRINGS — the semantics live in `text`. Published notices freeze (TTL 24h).
        Unknown id = empty itemList → found=false, never fabricated."""
        self._co_only("ch_six_notice_detail")
        r = company.ch_six_onot.detail(notice_id=notice_id, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        n = r.get("notice") or {}
        if r["found"]:
            reason = (f"SIX notice {r['notice_id']}: {n.get('noticeType')} · {n.get('date')} · "
                      f"{str(n.get('title') or '—')[:60]} · contact {n.get('contact') or '—'}"
                      + (f" · ISIN {n['isin']}" if n.get("isin") else "")
                      + f" · body {len(str(n.get('text') or ''))} chars")
        else:
            reason = (f"SIX notice {r['notice_id']}: not found (empty itemList — pick ids "
                      "from ch_six_official_notices rows)")
        return self._flat_env(
            tool="ch_six_notice_detail",
            input={"notice_id": r["notice_id"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{n.get('noticeId')} · {n.get('noticeType')} · "
                                f"{str(n.get('title') or '—')[:70]} · "
                                f"body {len(str(n.get('text') or ''))} chars",
                       "url": ("https://www.six-group.com/sheldon/official_notices/v2/details/"
                               f"{r['notice_id']}.json")}]
                      if r["found"] else [],
            provider_id="ch_six_onot", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"notice_id": r["notice_id"]}},
        )

    def eu_euronext_instrument_search(self, *, q, execution=None, no_cache=None):
        """company eu_euronext_instrument_search: Euronext instrument resolver across all seven
        markets ({isin,mic,name,symbol,link}; join on ISIN+MIC — one ISIN lists on many venues)."""
        self._co_only("eu_euronext_instrument_search")
        v = str(q or "").strip()
        if not v:
            raise SdkError("usage_error", provider="eu_euronext",
                           detail="eu_euronext_instrument_search requires q (ISIN, name or mnemonic)")
        r = company.eu_euronext.search_instruments(v, cache=self._c._cache,
                                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        ins = result["instruments"]
        by_isin = {}
        for x in ins:
            if x.get("isin"):
                by_isin.setdefault(x["isin"], []).append(x.get("mic"))
        top = (ins or [None])[0]
        head = (f"Euronext resolver \"{v}\": {len(ins)} venue rows across {len(by_isin)} ISIN"
                + ("s" if len(by_isin) != 1 else "")
                + (f" — {top.get('isin')} on {'+'.join(sorted(m for m in by_isin.get(top['isin'], []) if m))}"
                   f" ({top.get('name') or '—'})" if top else "")
                + " — join on ISIN+MIC, the bare ISIN is ambiguous across venues")
        return self._flat_env(
            tool="eu_euronext_instrument_search", input={"q": v},
            reason=head,
            result=result,
            evidence=[{"quote": f"{x.get('name') or '—'} ({x.get('symbol') or '—'} @ {x.get('mic') or '—'}, "
                                f"ISIN {x.get('isin') or '—'})",
                       "url": "https://live.euronext.com" + (x.get("link") or "/en/instrumentSearch/searchJSON")}
                      for x in ins[:5]],
            provider_id="eu_euronext", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def it_borsa_quote(self, *, isin, mic=None, execution=None, no_cache=None):
        """company it_borsa_quote: Borsa Italiana dati-completi card by ISIN (market cap parsed from
        IT number format; unknown ISIN = silent generic page, reported found=false — never fabricated)."""
        self._co_only("it_borsa_quote")
        r = company.it_borsa.get_quote(isin, mic=mic, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        card = result["card"]
        if not result["found"]:
            head = (f"Borsa dati-completi: no instrument metadata for {result['isin']}"
                    + (f" @ {mic}" if mic else "")
                    + " — the upstream serves a generic page silently for an unknown ISIN/mismatched mic (probed), not a 404")
        else:
            cap = card.get("market_cap_eur")
            head = (f"Borsa card {card.get('ticker') or '—'} ({card.get('name') or card.get('isin')}): "
                    f"{card.get('segment') or '—'}, super sector {card.get('super_sector') or '—'}"
                    + ((f", market cap €{cap:,.0f}") if cap is not None else "")
                    + (f", last {card.get('last_price')}" if card.get("last_price") is not None else "")
                    + f" — {len(card.get('meta') or {})} label/value pairs verbatim in meta")
        q = r["params"]
        evidence = ([{"quote": f"{card.get('ticker')} — {card.get('segment')}: cap {card.get('market_cap_raw') or '—'}",
                      "url": ("https://www.borsaitaliana.it/borsa/azioni/euronext-growth-milan/dati-completi.html"
                              f"?isin={q.get('isin')}" + (f"&mic={q.get('mic')}" if q.get("mic") else "") + "&lang=it")}]
                    if result["found"] else
                    [{"quote": "no Codice Isin pair in the served page (generic-page silent shape)",
                      "url": "https://www.borsaitaliana.it/borsa/azioni/euronext-growth-milan/dati-completi.html"
                             f"?isin={q.get('isin')}&lang=it"}])
        return self._flat_env(
            tool="it_borsa_quote", input={"isin": q.get("isin"), "mic": q.get("mic")},
            reason=head,
            result=result,
            evidence=evidence,
            provider_id="it_borsa", metas=[r["_meta"]],
            query={"source": "raw", "upstream": q},
        )

    def jp_jpx_stock_list(self, *, section="1", page=1, maxdisp=100,
                          execution=None, no_cache=None):
        """company jp_jpx_stock_list: one page of the JPX listed universe (qjsonp gateway;
        hitcount/pagecount echo; rows self-describe board + 33-sector industry)."""
        self._co_only("jp_jpx_stock_list")
        r = company.jp_jpx.list_stocks(section=section, page=page, maxdisp=maxdisp,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        stocks = result["stocks"]
        top = (stocks or [None])[0]
        head = (f"JPX stock_list key2={result['section']} page {result['page']}/{result['pagecount'] or '—'}: "
                f"{len(stocks)} rows of hitcount {result['hitcount']}"
                + (f", top {top.get('name_en') or top.get('name_ja') or '—'} ({top.get('code')}, "
                   f"{top.get('board') or '—'}, {top.get('industry_en') or '—'})" if top else "")
                + " — rows carry board (LISSE) + 33-sector industry verbatim")
        url = ("https://quote.jpx.co.jp/jpxhp/jcgi/wrap/qjsonp.aspx?F=ctl/stock_list&key2=%s"
               "&refindex=01&maxdisp=%s&page=%s" % (result["section"], result["params"]["maxdisp"], result["page"]))
        return self._flat_env(
            tool="jp_jpx_stock_list",
            input={"section": result["section"], "page": result["page"],
                   "maxdisp": result["params"]["maxdisp"]},
            reason=head,
            result=result,
            evidence=[{"quote": f"{x.get('name_en') or x.get('name_ja') or '—'} ({x.get('code')}, "
                                f"{x.get('board') or '—'}, {x.get('industry_en') or '—'}, last {x.get('last_price') or '—'})",
                       "url": url}
                      for x in stocks[:5]],
            provider_id="jp_jpx", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def jp_jpx_stock_detail(self, *, qcode, execution=None, no_cache=None):
        """company jp_jpx_stock_detail: the 57-field JPX issue card (ISIN/MKCP market cap JPY/SHRK
        shares/A_HISTDAYL daily OHLCV/EPS history — passed through verbatim)."""
        self._co_only("jp_jpx_stock_detail")
        r = company.jp_jpx.stock_detail(qcode, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        d = result["detail"]
        if d is None:
            head = (f"JPX stock_detail {qcode}: empty data dict — unknown code (honest zero, "
                    "the gateway answers 200 with no card rather than an error)")
        else:
            head = (f"JPX card {d.get('TTCODE2') or qcode} {d.get('FLLNE') or d.get('FLLN') or '—'}: "
                    f"ISIN {d.get('ISIN') or '—'}"
                    + (f", market cap ¥{d.get('MKCP')} JPY" if d.get("MKCP") not in (None, "-", "") else "")
                    + (f", shares {d.get('SHRK')}" if d.get("SHRK") not in (None, "-", "") else "")
                    + f", {len(d)} fields verbatim (incl. A_HISTDAYL daily OHLCV + EPS history)")
        url = f"https://quote.jpx.co.jp/jpxhp/jcgi/wrap/qjsonp.aspx?F=ctl/stock_detail&qcode={qcode}"
        return self._flat_env(
            tool="jp_jpx_stock_detail", input={"qcode": str(qcode).strip()},
            reason=head,
            result=result,
            evidence=[{"quote": (f"{d.get('FLLNE') or d.get('FLLN') or '—'} — ISIN {d.get('ISIN')}, "
                                 f"MKCP {d.get('MKCP')}, SHRK {d.get('SHRK')}" if d
                                else "section1.data empty — no card for this code"),
                       "url": url}],
            provider_id="jp_jpx", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
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

    # —— 0.3.59 EU EIOPA IORP register (dictionary slot: es_oepm_bopi < eu_eiopa_iorps <
    # fdic_failures; method kept adjacent to the European registry cluster it joins — the
    # live query channel over the register already harvested raw as eu-eiopa-iorps-pensions,
    # 6,099 schemes live) ——

    def eu_eiopa_iorps(self, limit=100, page=1, execution=None, no_cache=None):
        """company eu_eiopa_iorps: EIOPA register of occupational pension schemes
        (registers.eiopa.europa.eu public data exchange POST API; 6,099 IORPs live; per scheme
        the official name, home/operating country, NCA, address, managing entity, registration
        window, cross-border status, LEI, id code). Enumeration face — page is 1-BASED
        (page 0 answers upstream 400, measured); sortField is hardcoded 'id' (an invalid one
        silently clamps the register to totalItems 0)."""
        self._co_only("eu_eiopa_iorps")
        r = company.eu_eiopa.iorps_raw(limit, page, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="eu_eiopa_iorps",
            input={"limit": result["params"]["limit"], "page": result["params"]["page"]},
            reason=(f"EIOPA IORP register: {result['total']} schemes"
                    + f" — page {result['params']['page']} × {result['params']['limit']}"
                    + (f" ({len(rows)} rows)" if rows else " — page past the end of 6,099")
                    + (f", top {top['official_name'] or '—'} ({top.get('type') or '—'}, {top.get('home_country') or '—'},"
                       f" LEI {top.get('lei') or '—'})" if top else "")
                    + " — managing_entity is the legal name of the managing entity (the join key onto insurers);"
                      " no term filter upstream (the data-table filter vocabulary is unmeasured) — enumerate and filter locally"),
            result=result,
            evidence=[{"quote": f"{x.get('official_name') or '—'} · {x.get('type') or '—'}"
                                + f" · {x.get('home_country') or '—'} → operates {x.get('operating_country') or '—'}"
                                + (f" · LEI {x['lei']}" if x.get("lei") else "")
                                + (f" · reg {x['registration_start']}" if x.get("registration_start") else ""),
                       "url": "https://registers.eiopa.europa.eu/PublicDataExchange/"} for x in rows[:5]],
            provider_id="eu_eiopa", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    # —— 0.3.74 E16 ESEF register (dictionary slot: eu_eiopa_iorps < eu_esef_facts <
    # eu_esef_filings < eu_euronext_instrument_search; filings.xbrl.org — the EU Transparency
    # Directive annual-report pillar, keyless JSON:API) ——

    def eu_esef_facts(self, *, filing_id=None, lei=None, period_end=None, concept=None,
                      all_periods=False, annual_only=True, include_dimensions=False,
                      include_text=False, limit=None, execution=None, no_cache=None):
        """company eu_esef_facts: the structured IFRS facts of one ESEF annual report
        (XBRL-JSON → compact rows: concept, value, decimals, unit, period, entity, dimensions);
        select by --filing-id or issuer --lei (latest period_end wins, --period-end picks
        another); concept filter is case-insensitive with a trailing * wildcard — 'Revenue*'
        catches both ifrs-full:Revenue and RevenueFromContractsWithCustomers."""
        self._co_only("eu_esef_facts")
        r = company.eu_esef.facts(
            filing_id=filing_id, lei=lei, period_end=period_end, concept=concept,
            all_periods=all_periods, annual_only=annual_only,
            include_dimensions=include_dimensions, include_text=include_text, limit=limit,
            cache=self._c._cache,
            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        f = result["filing"] or {}
        top = (rows or [None])[0]
        return self._flat_env(
            tool="eu_esef_facts",
            input=result["params"],
            reason=(f"ESEF facts filing {f.get('filing_id')} — {f.get('entity_name') or '—'}"
                    f" ({f.get('lei') or '—'}, period end {f.get('period_end') or '—'}):"
                    f" {result['matched_count']} of {result['fact_count']} facts match"
                    + (f", top {top.get('concept')} = {top.get('value')}" if top else "")
                    + " — one XBRL-JSON artefact read end-to-end; durations are end-exclusive upstream"
                      " (period_end is the raw instant minus one day, the inclusive end)"),
            result=result,
            evidence=[{"quote": f"{x.get('concept')} = {x.get('value')}"
                                + f" ({x.get('period_start') or x.get('period_end')} → {x.get('period_end')}"
                                + f" {x.get('unit') or ''})",
                       "url": f.get("json_url") or "https://filings.xbrl.org/"} for x in rows[:5]],
            provider_id="eu_esef", metas=r.get("_metas") or [r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def eu_esef_filings(self, *, lei=None, name=None, country=None, period_end=None,
                        period_from=None, period_to=None, added_from=None, added_to=None,
                        fxo_id=None, sort="processed", order="desc", page=1, limit=30,
                        execution=None, no_cache=None):
        """company eu_esef_filings: the ESEF filings register — 27,817 inline-XBRL annual
        reports from 7,505 EEA issuers (GB 2,982 filings / 806 issuers, DK 2,247, SE 1,841, NO
        1,199, FR 1,188…; DE and IE absent); one row per filing with period_end, country, fxo_id
        (-0 original, -1… amended) and the absolute viewer/zip/report/XBRL-JSON URLs; page is
        1-BASED, limit caps at 1,000."""
        self._co_only("eu_esef_filings")
        r = company.eu_esef.filings(
            lei=lei, name=name, country=country, period_end=period_end, period_from=period_from,
            period_to=period_to, added_from=added_from, added_to=added_to, fxo_id=fxo_id,
            sort=sort, order=order, page=page, limit=limit, cache=self._c._cache,
            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = (rows or [None])[0]
        return self._flat_env(
            tool="eu_esef_filings",
            input=result["params"],
            reason=(f"ESEF register: {result['total']:,} filings"
                    + (f" from {name!r}" if name else (f" for {lei}" if lei else ""))
                    + f" — page {result['page']} of {result['pages']}, {len(rows)} rows"
                    + (f", top {top.get('entity_name') or '—'} · {top.get('period_end')} · {top.get('country')}" if top else "")
                    + " — join onto eu_esef_facts by filing_id for the structured IFRS numbers"),
            result=result,
            evidence=[{"quote": f"{x.get('entity_name') or '—'} · {x.get('period_end')} · {x.get('country')}"
                                f" · {x.get('fxo_id') or '—'}"
                                + (f" · amended" if x.get("amendment") else ""),
                       "url": x.get("viewer_url") or "https://filings.xbrl.org/"} for x in rows[:5]],
            provider_id="eu_esef", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    # ---------- 0.3.4 FR annuaire live search face (recherche-entreprises) ----------

    # —— 0.3.58 FR INPI accounting ratios pair (dictionary slot: fi_ytj_companies <
    # fr_inpi_ratios < fr_inpi_ratios_sectors < fr_recherche_search; ODS v2.1, the fr_regafi
    # stack on the Ministry's mirror — the only keyless surface over RNE accounts) ——

    def fr_inpi_ratios(self, siren=None, *, type_bilan=None, confidentiality=None,
                       date_cloture=None, limit=20, offset=0, execution=None, no_cache=None):
        """company fr_inpi_ratios: FR company accounting ratios per fiscal year (INPI open data
        via data.economie.gouv.fr ratios_inpi_bce, ~6.8M rows; siren 9-digit exact — quoted by
        the module; confidentiality walled to the register's own four-value disclosure tier;
        values are € thousands, passed through verbatim)."""
        self._co_only("fr_inpi_ratios")
        if siren is None and not (type_bilan or confidentiality or date_cloture):
            raise SdkError("usage_error", provider="fr_inpi",
                           detail="fr_inpi_ratios requires siren (the 9-digit FR company key) or at least "
                                  "one filter (type_bilan / confidentiality / date_cloture) — the whole-register "
                                  "enumeration belongs to the corpus line, not the lookup face")
        raw_siren = str(siren or "").strip() or None
        r = company.fr_inpi.ratios_raw(raw_siren, type_bilan=type_bilan, confidentiality=confidentiality,
                                       date_cloture=date_cloture, limit=limit, offset=offset,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="fr_inpi_ratios",
            input={"siren": raw_siren, "type_bilan": type_bilan, "confidentiality": confidentiality,
                   "date_cloture": date_cloture, "limit": result["params"]["limit"],
                   "offset": result["params"]["offset"]},
            reason=(f"INPI accounting ratios: {result['total_count']} fiscal-year rows matched"
                    + (f", top row FY closed {top['date_cloture_exercice'] or '—'} — CA €{top['chiffre_d_affaires']:,}k / résultat net €{top['resultat_net']:,}k / taux d'endettement {top['taux_d_endettement']}" if top
                       else ", zero hits (the SIREN filed no disclosable accounts — check against fr_recherche_search that the company exists and files)")),
            result=result,
            evidence=[{"quote": f"SIREN {x['siren']} · FY {x['date_cloture_exercice']} · type_bilan {x['type_bilan']} · {x['confidentiality']}",
                       "url": "https://data.economie.gouv.fr/explore/dataset/ratios_inpi_bce/"} for x in result["rows"][:5]],
            provider_id="fr_inpi", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    def fr_inpi_ratios_sectors(self, classe_naf=None, *, classe_ca=None, exercice=None,
                               limit=20, offset=0, execution=None, no_cache=None):
        """company fr_inpi_ratios_sectors: FR sector ratio benchmarks at q10-q90 quantiles
        (ratios_inpi_bce_sectors, 22,159 rows; classe_naf = NAF rev.2 class e.g. 1102 ×
        classe_ca turnover band '<2M' × exercice — the benchmark an individual company's
        fr_inpi_ratios row compares against)."""
        self._co_only("fr_inpi_ratios_sectors")
        if classe_naf is None and not (classe_ca or exercice):
            raise SdkError("usage_error", provider="fr_inpi",
                           detail="fr_inpi_ratios_sectors requires classe_naf (NAF rev.2 class code) or at "
                                  "least one filter (classe_ca / exercice) — 22k rows over 94 columns is the "
                                  "whole panel, serve it filtered")
        raw_naf = str(classe_naf or "").strip() or None
        r = company.fr_inpi.sectors_raw(raw_naf, classe_ca=classe_ca, exercice=exercice,
                                        limit=limit, offset=offset, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="fr_inpi_ratios_sectors",
            input={"classe_naf": raw_naf, "classe_ca": classe_ca, "exercice": exercice,
                   "limit": result["params"]["limit"], "offset": result["params"]["offset"]},
            reason=(f"INPI sector benchmarks: {result['total_count']} panel rows matched"
                    + (f", top {top['classe_naf']} / CA {top['classe_ca'] or '—'} / FY {top['exercice'] or '—'} — marge brute q50 {top.get('part_ca_marge_brute_q50')}" if top
                       else ", zero hits (the NAF class code is wrong or the band×year cell is empty — NAF classes are 4-digit, e.g. 1102)")),
            result=result,
            evidence=[{"quote": f"{x['classe_naf']} · CA {x['classe_ca']} · FY {x['exercice']}"
                                + (f" · marge brute q10/q50/q90 {x.get('part_ca_marge_brute_q10')}/{x.get('part_ca_marge_brute_q50')}/{x.get('part_ca_marge_brute_q90')}" if x.get("part_ca_marge_brute_q50") is not None else ""),
                       "url": "https://data.economie.gouv.fr/explore/dataset/ratios_inpi_bce_sectors/"} for x in result["rows"][:5]],
            provider_id="fr_inpi", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

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

    # —— 0.3.53 FR Regafi ACPR financial-register pair (the qualification axis joins fr_recherche's roster axis) ——

    def fr_regafi_authorisations(self, id_referentiel=None, categorie=None, nature=None,
                                 situation=None, *, limit=20, offset=0,
                                 execution=None, no_cache=None):
        """company fr_regafi_authorisations: French ACPR per-authorisation timeline (regafi.fr
        ODS Explore v2.1 prd-banque-autorisations, keyless; 31,107 rows live 2026-11-10).
        One row per granted authorisation — id_referentiel joins the entities face, date_debut
        runs 1946→today, and the *_json columns carry the per-service blocks with their own
        effective dates (services de paiement, cryptos, cautions réglementées…), parsed in
        place. nature is the register's own seven-word vocabulary (exact match), situation the
        closed ACTIF/MANDAT pair; categorie passes verbatim (the multi-regime space evolves)."""
        self._co_only("fr_regafi_authorisations")
        r = company.fr_regafi.authorisations_raw(id_referentiel, categorie, nature, situation,
                                                 limit=limit, offset=offset,
                                                 cache=self._c._cache,
                                                 no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        flt = ", ".join(f"{k}={v}" for k, v in
                        (("id_referentiel", id_referentiel), ("categorie", categorie),
                         ("nature", nature), ("situation", situation)) if v)
        if result["rows"]:
            first = result["rows"][0]
            reason = (f"ACPR authorisation timeline: {result['total_count']:,} rows match"
                      + (f" ({flt})" if flt else " (unfiltered — the whole register)")
                      + f" — showing {result['count']} (offset {result['params']['offset']}); "
                        f"id_referentiel joins fr_regafi_entities, the *_json blocks carry the "
                        f"per-service dates (sample: {first.get('categorie') or '—'} / "
                        f"{first.get('nature_autorisation') or '—'} since {first.get('date_debut') or '—'})")
        else:
            reason = (f"ACPR authorisation timeline: zero rows"
                      + (f" for {flt}" if flt else "")
                      + " — a legitimate empty filter, or an offset past the end "
                        f"(the register carries {result['total_count']:,} rows)")
        return self._flat_env(
            tool="fr_regafi_authorisations",
            input={"id_referentiel": id_referentiel, "categorie": categorie,
                   "nature": nature, "situation": situation,
                   "limit": result["params"]["limit"], "offset": result["params"]["offset"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"[id_autorisation {x.get('id_autorisation')}] réf {x.get('id_referentiel')}"
                                + f" — {x.get('categorie') or '—'} / {x.get('sous_categorie') or '—'}:"
                                  f" {x.get('nature_autorisation') or '—'} since {x.get('date_debut') or '—'}"
                                  f" ({x.get('situation') or '—'}, {x.get('pays_exercice') or '—'})",
                       "url": "https://regafi.fr/api/explore/v2.1/catalog/datasets/prd-banque-autorisations/records"}
                      for x in result["rows"][:5]],
            provider_id="fr_regafi", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def fr_regafi_entities(self, siren=None, lei=None, categorie=None, pays=None, q=None,
                           *, limit=20, offset=0, execution=None, no_cache=None):
        """company fr_regafi_entities: French ACPR supervised-entity register (regafi.fr ODS
        Explore v2.1 prd-banque-entites, keyless; 25,890 rows live 2026-11-10). id_referentiel
        is the official key; lei + siren are the dual hard keys (SIREN joins the FR company
        master, LEI joins GLEIF); id_entite_parente/denomination_entite_parente carry the
        parent edge; nom_commerciaux rides parsed (renaming history); categorie is the
        multi-valued 24-value vocabulary (Agent PSP 22,485 / Entreprise d'Investissement
        1,009 / Établissement de Crédit 941 …). q is full-text over denomination."""
        self._co_only("fr_regafi_entities")
        r = company.fr_regafi.entities_raw(siren, lei, categorie, pays, q,
                                           limit=limit, offset=offset,
                                           cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        flt = ", ".join(f"{k}={v}" for k, v in
                        (("siren", siren), ("lei", lei), ("categorie", categorie),
                         ("pays", pays), ("q", q)) if v)
        if result["rows"]:
            top = result["rows"][0]
            reason = (f"ACPR supervised entities: {result['total_count']:,} rows match"
                      + (f" ({flt})" if flt else " (unfiltered — the whole register)")
                      + f" — showing {result['count']} (offset {result['params']['offset']}); "
                        f"dual hard keys ride every row (SIREN {top.get('siren') or '—'} / LEI "
                        f"{str(top.get('lei') or '—')[:20]}), the parent edge when grouped "
                        f"(id_entite_parente {top.get('id_entite_parente') or '—'})")
        else:
            reason = (f"ACPR supervised entities: zero rows"
                      + (f" for {flt}" if flt else "")
                      + " — a legitimate empty filter (siren/lei are exact; try q for the name channel), "
                        f"or an offset past the end (the register carries {result['total_count']:,} rows)")
        def _cat(x):
            # categorie is multi-valued upstream (Agent PSP + Établissement de Crédit …) — render as a joined line, never a list repr
            c = x.get("categorie")
            return " + ".join(c) if isinstance(c, list) and c else (c or "—")

        return self._flat_env(
            tool="fr_regafi_entities",
            input={"siren": siren, "lei": lei, "categorie": categorie, "pays": pays,
                   "q": q, "limit": result["params"]["limit"], "offset": result["params"]["offset"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"réf {x.get('id_referentiel')} — {x.get('denomination') or '—'}"
                                + (f" ({x.get('sigle')})" if x.get("sigle") else "")
                                + f" · SIREN {x.get('siren') or '—'} · {_cat(x)}"
                                  f" · {x.get('ville') or '—'} {x.get('pays') or ''}",
                       "url": "https://regafi.fr/api/explore/v2.1/catalog/datasets/prd-banque-entites/records"}
                      for x in result["rows"][:5]],
            provider_id="fr_regafi", metas=[r["_meta"]],
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

    # —— 0.3.72 NZ NZX SSR dehydrated state (E14; robots allows the SSR pages only —
    # /api/ and /search are never touched; every page carries its data in the
    # __NEXT_DATA__ TanStack dehydrated state) ——

    def nz_nzx_listed(self, *, board="NZSX", code=None, name=None, security_class=None,
                      category=None, quotes=False, limit=None, execution=None, no_cache=None):
        """company nz_nzx_listed: the NZX whole-exchange master (NZ — activeInstruments
        in the SSR dehydrated state; 427 rows probe day × 16 keys incl.
        isin/sharesIssued/firstListedDate; the ACTIVE set — delisted instruments drop
        out, lastListedDate 3000-01-01 is the listed sentinel). NZSX and NZDX pages
        carry the SAME master; the board picks the live quote panel (NZSX 178 equities
        / NZDX 135 bonds — type F securityClass W). --quotes merges the panel quote
        onto matching rows. --code exact, --name substring, --security-class exact
        (E/F), --category exact (SHRS/…), --limit slices."""
        self._co_only("nz_nzx_listed")
        r = company.nz_nzx.listed(board=board, code=code, name=name,
                                  security_class=security_class, category=category,
                                  quotes=quotes, limit=limit, cache=self._c._cache,
                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        result = {k: x for k, x in r.items() if k != "_meta"}
        if rows:
            top = rows[0]
            reason = (f"NZX {r['board']} master: {r['total']} rows match"
                      f" (board quote panel {r['quote_rows']}) — sample {top.get('code')} "
                      f"{str(top.get('name') or '—')[:40]} · {top.get('securityClass') or '—'} · "
                      f"{top.get('category') or '—'} · listed {str(top.get('firstListedDate') or '—')[:10]}"
                      + (" · quote merged (--quotes)" if quotes else ""))
        else:
            reason = (f"NZX {r['board']} master: zero rows match (code={code or '—'}, "
                      f"name={name or '—'}, security_class={security_class or '—'}, "
                      f"category={category or '—'} — an empty answer is a legitimate miss)")
        return self._flat_env(
            tool="nz_nzx_listed",
            input={"board": r["board"], "code": code, "name": name,
                   "security_class": security_class, "category": category,
                   "quotes": bool(quotes), "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('code')} {str(x.get('name') or '—')[:40]} · "
                                f"{x.get('isin') or '—'} · {x.get('securityClass') or '—'}/"
                                f"{x.get('category') or '—'} · shares "
                                f"{x.get('sharesIssued') if x.get('sharesIssued') is not None else '—'}",
                       "url": f"https://www.nzx.com/markets/{r['board']}"}
                      for x in rows[:5]],
            provider_id="nz_nzx", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://www.nzx.com/markets/{r['board']}",
                                "panel": "activeInstruments"}},
        )

    def nz_nzx_company(self, *, code, execution=None, no_cache=None):
        """company nz_nzx_company: the NZX issuer governance card (NZ — summary carries
        financialYearEnd{month,day} + auditor + solicitor + primaryRegistry +
        primaryListingVenue; contact the address/website/secretary; directors the
        official register verbatim — role/type I|N/isCurrent/start/end; instruments
        the issuer's live quote rows). Bad code = an honest 404 whose dehydrated
        queries list is EMPTY → found=false, never fabricated (unlike the CSE
        zero-byte silent-empty shape, NZX answers a real 404)."""
        self._co_only("nz_nzx_company")
        r = company.nz_nzx.company(code=code, cache=self._c._cache,
                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        card = r.get("card") or {}
        s = card.get("summary") or {}
        fye = s.get("financialYearEnd") or {}
        dirs = card.get("directors") or []
        current = [d for d in dirs if d.get("isCurrent")]
        if r["found"]:
            reason = (f"NZX issuer card {r['code']}: FYE {fye.get('month')}/{fye.get('day')}"
                      f" · auditor {s.get('auditor') or '—'} · solicitor {s.get('solicitor') or '—'}"
                      f" · registry {s.get('primaryRegistry') or '—'}"
                      f" · directors {len(current)} current of {len(dirs)}"
                      f" · instruments {len(card.get('instruments') or [])}")
        else:
            reason = (f"NZX issuer card {r['code']}: not found (honest 404, empty dehydrated "
                      "queries — check the code on nz_nzx_listed)")
        return self._flat_env(
            tool="nz_nzx_company",
            input={"code": r["code"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{r['code']} · FYE {fye.get('month')}/{fye.get('day')} · "
                                f"auditor {s.get('auditor') or '—'} · "
                                f"{len(current)} current of {len(dirs)} directors · "
                                f"venue {s.get('primaryListingVenue') or '—'}",
                       "url": f"https://www.nzx.com/companies/{r['code']}"}]
                      if r["found"] else [],
            provider_id="nz_nzx", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://www.nzx.com/companies/{r['code']}",
                                "panels": ["contact", "summary", "directors", "instruments"]}},
        )

    def nz_nzx_announcements(self, *, board="NZSX", code=None, type=None,
                             price_sensitive=None, limit=None, execution=None, no_cache=None):
        """company nz_nzx_announcements: the NZX board announcements snapshot (NZ —
        newest 200, id-desc; the id is the sequential anchor for incremental pulls,
        max 484034 probe day; rows carry summary/details/attachments verbatim — SHINTR
        substantial-holder family, price-sensitive flags). THE ?page PARAM IS IGNORED
        UPSTREAM (page 2 dehydrates page 1) — 200 rows is the whole SSR surface, the
        deeper API is robots-blocked; documented boundary, final. --code exact on
        companyCode, --type exact, --price-sensitive bool, --limit slices."""
        self._co_only("nz_nzx_announcements")
        r = company.nz_nzx.announcements(board=board, code=code, type=type,
                                         price_sensitive=price_sensitive, limit=limit,
                                         cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        result = {k: x for k, x in r.items() if k != "_meta"}
        base = (f"NZX {r['board']} announcements: {r['total']} of 200 rows"
                + (f" (local code={code} filter)" if code else "")
                + (f" (local type={type} filter)" if type else "")
                + (f" (price_sensitive={price_sensitive})" if price_sensitive is not None else ""))
        if rows:
            top = rows[0]
            s = top.get("summary") or {}
            d = top.get("details") or {}
            reason = (base + f" — newest id {top.get('id')} · {s.get('publicationDate')} · "
                      f"{str(s.get('title') or '—')[:60]}"
                      + (" · PRICE SENSITIVE" if d.get("isPriceSensitive") else ""))
        else:
            reason = base + " — zero rows: an empty filter is a legitimate miss"
        return self._flat_env(
            tool="nz_nzx_announcements",
            input={"board": r["board"], "code": code, "type": type,
                   "price_sensitive": price_sensitive, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{(x.get('summary') or {}).get('companyCode')} · id {x.get('id')} · "
                                f"{(x.get('summary') or {}).get('type')} · "
                                f"{str((x.get('summary') or {}).get('title') or '—')[:60]}"
                                + (" · PS" if (x.get("details") or {}).get("isPriceSensitive") else ""),
                       "url": f"https://www.nzx.com/markets/{r['board']}/announcements"}
                      for x in rows[:5]],
            provider_id="nz_nzx", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": f"https://www.nzx.com/markets/{r['board']}/announcements",
                                "panel": "announcements/recent", "boundary": "newest-200 (page param ignored upstream)"}},
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

    # —— 0.3.37 RU CBR credit-organisations face (dictionary slot: ru_cbr between ror and sec) ——

    def ru_cbr_credit_orgs(self, name=None, *, status=None, ogrn=None, limit=20,
                           execution=None, no_cache=None):
        """company ru_cbr_credit_orgs: the Bank of Russia credit-organisations register
        (www.cbr.ru FullCoList; the company domain's first RU face). The WHOLE register ships in
        ONE keyless HTML page (~790KB, 1,897 rows × 9 columns, nightly rebuild — the as-of stamp
        lives in the census), cached 24h and scanned locally. Rows are the 9 upstream columns
        verbatim; license_status keeps the register's four-status vocabulary (status= translates
        the English closed set active|revoked|annulled|liquidation → Действующая|Отозванная|
        Аннулированная|Ликвидация); kind is null on the 1,746 universal banks (the register's
        own empty-cell convention, kept); the name cell's /finorg/foinfo/?ogrn= anchor is kept
        as foinfo_path (the register's own per-entity edge). ogrn = the exact 13-digit ОГРН key
        (empty on 188 legacy/liquidated rows)."""
        self._co_only("ru_cbr_credit_orgs")
        nm = str(name or "").strip() or None
        r = company.ru_cbr_credit.credit_orgs_raw(nm, status=status, ogrn=ogrn, limit=limit,
                                                  cache=self._c._cache,
                                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        cen = result["census"]
        st = cen["by_status"]
        recap = (f" (name contains \"{nm}\")" if nm else "") \
            + (f", status={status}" if status else "") \
            + (f", ОГРН {ogrn}" if ogrn else "")
        if result["rows"]:
            reason = (f"Bank of Russia credit-organisations register: {result['total_matched']} of {result['scanned_rows']:,} rows matched"
                      + recap
                      + f" — as of {cen['as_of']}: Действующая {st.get('Действующая', 0):,} / Отозванная {st.get('Отозванная', 0):,}"
                      + f" / Аннулированная {st.get('Аннулированная', 0):,} / Ликвидация {st.get('Ликвидация', 0):,}"
                      + f" (the liquidation wall is the register's largest segment), registrations {cen['reg_year_min']}→{cen['reg_year_max']};"
                      + " ОГРН is the ЕГРЮЛ join key (empty on legacy rows); foinfo_path = the register's own per-entity edge")
        else:
            reason = (f"Bank of Russia credit-organisations register: zero hits on the {result['scanned_rows']:,}-row register"
                      + recap
                      + " — a legitimate answer = clean screening (drop filters to enumerate from the head)")
        return self._flat_env(
            tool="ru_cbr_credit_orgs",
            input={"name": nm, "status": status, "ogrn": result["params"]["ogrn"],
                   "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['name'] or '—')[:60]} · reg {x['reg_no'] or '—'}"
                                + f" · {x['license_status']} · reg. {x['reg_date'] or '—'}",
                       "url": ("https://www.cbr.ru" + x["foinfo_path"] if x["foinfo_path"]
                               else "https://www.cbr.ru/banking_sector/credit/FullCoList/")}
                      for x in result["rows"][:5]],
            provider_id="ru_cbr_credit", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.38 BR BACEN Olinda faces (dictionary slot: br_bacen at the FLAT head, before ch) ——

    def br_bacen_institutions(self, name=None, *, family=None, segmento=None, uf=None,
                              cnpj_root=None, limit=20, execution=None, no_cache=None):
        """company br_bacen_institutions: the BACEN authorised-institutions register
        (olinda.bcb.gov.br Instituicoes_em_funcionamento; the company domain's first BR face).
        FOUR resources merged — SedesBancoComMultCE 154 / SedesCooperativas 752 /
        SedesSociedades 704 / SedesConsorcios 130 = 1,740 rows — each shipped whole in one
        keyless GET, cached 24h, scanned locally. family=banco|cooperativa|sociedade|consorcio
        is the resource boundary; the key variants are the register's own (banco carries
        SEGMENTO+CARTEIRA_COMERCIAL, cooperativa swaps in CLASSE/CATEGCOOPSING/FILIACAO/
        ASSOCIACAO with no SEGMENTO, sociedade carries a 15-value SEGMENTO, consorcio is a
        bare address block). CNPJ arrives as the 8-digit ROOT — the 14-digit whole key lives
        on branches/dasfn rows."""
        self._co_only("br_bacen_institutions")
        nm = str(name or "").strip() or None
        r = company.br_bacen.institutions_raw(nm, family=family, segmento=segmento, uf=uf,
                                              cnpj_root=cnpj_root, limit=limit,
                                              cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        cen = result["census"]
        fam = cen["by_family"]
        recap = (f" (name contains \"{nm}\")" if nm else "") \
            + (f", family={family}" if family else "") \
            + (f", segmento contains \"{segmento}\"" if segmento else "") \
            + (f", UF {result['params']['uf']}" if result["params"]["uf"] else "") \
            + (f", CNPJ root {result['params']['cnpj_root']}" if result["params"]["cnpj_root"] else "")
        if result["rows"]:
            reason = (f"BACEN authorised-institutions register: {result['total_matched']} of {result['scanned_rows']:,} rows matched"
                      + recap
                      + f" — four resources merged: banco {fam.get('banco', 0)} / cooperativa {fam.get('cooperativa', 0):,}"
                      + f" / sociedade {fam.get('sociedade', 0)} / consorcio {fam.get('consorcio', 0)};"
                      + f" {cen['with_email']} of {result['scanned_rows']:,} rows carry E_MAIL;"
                      + " CNPJ is the 8-digit root (join the 14-digit whole key via br_bacen_branches/dasfn)")
        else:
            reason = (f"BACEN authorised-institutions register: zero hits on the {result['scanned_rows']:,}-row register"
                      + recap
                      + " — a legitimate answer = not a BACEN-authorised institution (drop filters to enumerate from the head)")
        base = "https://olinda.bcb.gov.br/olinda/servico/Instituicoes_em_funcionamento/versao/v1/odata"
        res = {"banco": "SedesBancoComMultCE", "cooperativa": "SedesCooperativas",
               "sociedade": "SedesSociedades", "consorcio": "SedesConsorcios"}
        return self._flat_env(
            tool="br_bacen_institutions",
            input={"name": nm, "family": family, "segmento": segmento,
                   "uf": result["params"]["uf"], "cnpj_root": result["params"]["cnpj_root"],
                   "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['name'] or '—')[:60]} · {x.get('segmento') or x['family']} · CNPJ root {x['cnpj_root'] or '—'}"
                                + f" · {x.get('municipio') or '—'}/{x.get('uf') or '—'}",
                       "url": f"{base}/{res[x['family']]}"}
                      for x in result["rows"][:5]],
            provider_id="br_bacen", metas=metas,
            query={"source": "raw", "upstream": r["params"]},
        )

    def br_bacen_branches(self, if_name=None, *, agency=None, compe=None, uf=None,
                          cnpj_root=None, limit=20, execution=None, no_cache=None):
        """company br_bacen_branches: the BACEN branch register (olinda.bcb.gov.br
        Informes_Agencias Agencias; 13,590 rows × 639 IFs × 20 Segmento). The register ships
        whole in TWO keyless pages ($top=10000 + $skip=10000 — Olinda's $inlinecount is a 400
        on this service, so the total is what you pull), cached 24h, scanned locally. CNPJ
        arrives three-part (CnpjBase 8 / CnpjSequencial 4 / CnpjDv 2) and rows also emit the
        joined 14-digit cnpj_full — the RFB whole-library join key. compe is the 5-digit
        COMPE settlement code (empty on 731 rows → null). posicao is the panel as-of date;
        data_inicio is the branch's own start date (dd/mm/yyyy, 1949→)."""
        self._co_only("br_bacen_branches")
        nm = str(if_name or "").strip() or None
        r = company.br_bacen.branches_raw(nm, agency=agency, compe=compe, uf=uf,
                                          cnpj_root=cnpj_root, limit=limit,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        cen = result["census"]
        recap = (f" (IF contains \"{nm}\")" if nm else "") \
            + (f", agency contains \"{agency}\"" if agency else "") \
            + (f", COMPE {result['params']['compe']}" if result["params"]["compe"] else "") \
            + (f", UF {result['params']['uf']}" if result["params"]["uf"] else "") \
            + (f", CNPJ root {result['params']['cnpj_root']}" if result["params"]["cnpj_root"] else "")
        if result["rows"]:
            reason = (f"BACEN branch register: {result['total_matched']} of {result['scanned_rows']:,} rows matched"
                      + recap
                      + f" — {cen['ifs']:,} IFs × {cen['segmento_n']} segmentos, panel as of {cen['as_of']},"
                      + f" branch start dates {cen['start_year_min']}→{cen['start_year_max']};"
                      + f" COMPE (the PIX/TED settlement key) is missing on {cen['compe_missing']:,} rows;"
                      + " cnpj_full is the joined 14-digit RFB whole-library join key")
        else:
            reason = (f"BACEN branch register: zero hits on the {result['scanned_rows']:,}-row register"
                      + recap
                      + " — a legitimate answer = no branch on record for that IF/key (drop filters to enumerate from the head)")
        return self._flat_env(
            tool="br_bacen_branches",
            input={"if_name": nm, "agency": agency, "compe": result["params"]["compe"],
                   "uf": result["params"]["uf"], "cnpj_root": result["params"]["cnpj_root"],
                   "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['if_name'] or '—')[:50]} · ag. {(x['agency_name'] or '—')[:40]}"
                                + f" · CNPJ {x['cnpj_full'] or '—'} · COMPE {x['compe'] or '—'}"
                                + f" · {x.get('municipio') or '—'}/{x.get('uf') or '—'}",
                       "url": "https://olinda.bcb.gov.br/olinda/servico/Informes_Agencias/versao/v1/odata/Agencias"}
                      for x in result["rows"][:5]],
            provider_id="br_bacen", metas=metas,
            query={"source": "raw", "upstream": r["params"]},
        )

    def br_bacen_domains(self, domain=None, *, name=None, tipo=None, conglomerado=None,
                         limit=20, execution=None, no_cache=None):
        """company br_bacen_domains: the BACEN verified-domains register (olinda.bcb.gov.br
        DominiosVerificados; 1,892 rows = 1,740 institutions × verified-domain status). Shipped
        whole in one keyless GET, cached 24h, scanned locally — the anti-phishing edge: match a
        domain against it before trusting a 'bank' URL. tipo=own|member|none translates the
        register's three-value vocabulary (534 Dominio próprio / 279 Domínio de intregrante do
        conglomerado — the upstream typo is kept verbatim on rows — / 1,079 Sem domínio
        verificado, and the 1,079 honest negatives STAY in the scan). conglomerado is the
        635-code conglomerate lineage key; CNPJ keeps the register's own 00000000 placeholder
        on 2 BB rows."""
        self._co_only("br_bacen_domains")
        dom = str(domain or "").strip() or None
        r = company.br_bacen.domains_raw(dom, name=name, tipo=tipo, conglomerado=conglomerado,
                                         limit=limit, cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        cen = result["census"]
        tp = cen["by_tipo"]
        recap = (f" (domain contains \"{dom}\")" if dom else "") \
            + (f", name contains \"{name}\"" if name else "") \
            + (f", tipo={tipo}" if tipo else "") \
            + (f", conglomerado {result['params']['conglomerado']}" if result["params"]["conglomerado"] else "")
        if result["rows"]:
            reason = (f"BACEN verified-domains register: {result['total_matched']} of {result['scanned_rows']:,} rows matched"
                      + recap
                      + f" — own {tp.get('Dominio próprio', 0)} / conglomerate-member {tp.get('Domínio de intregrante do conglomerado', 0)}"
                      + f" / no-verified-domain {tp.get('Sem domínio verificado', 0):,} across {cen['inst_n']:,} institutions"
                      + f" ({cen['conglomerado_n']} conglomerate codes);"
                      + " the tipo value 'Domínio de intregrante do conglomerado' is the upstream typo, kept verbatim")
        else:
            reason = (f"BACEN verified-domains register: zero hits on the {result['scanned_rows']:,}-row register"
                      + recap
                      + " — a legitimate answer = no BACEN-verified domain on record (anti-phishing negative;"
                      + " drop filters to enumerate from the head)")
        return self._flat_env(
            tool="br_bacen_domains",
            input={"domain": dom, "name": name, "tipo": tipo,
                   "conglomerado": result["params"]["conglomerado"],
                   "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['inst'] or '—')[:55]} · {(x['domain'] or '—')[:50]} · {x['tipo']}"
                                + (f" · cong. {x['conglomerado_code']}" if x.get("conglomerado_code") else ""),
                       "url": "https://olinda.bcb.gov.br/olinda/servico/Instituicoes_em_funcionamento/versao/v1/odata/DominiosVerificados"}
                      for x in result["rows"][:5]],
            provider_id="br_bacen", metas=metas,
            query={"source": "raw", "upstream": r["params"]},
        )

    def br_bacen_dasfn(self, cnpj=None, *, name=None, api=None, recurso=None,
                       limit=20, execution=None, no_cache=None):
        """company br_bacen_dasfn: the BACEN open-data/open-finance API participation directory
        (olinda.bcb.gov.br DASFN Recursos; 10,419 rows × 513 institutions × 4 API kinds). The
        register ships whole in TWO keyless pages, cached 24h, scanned locally — each row is
        ONE API endpoint an institution actually serves in Produção: api=pilar3 (open-banking
        Pillar 3, 9,885 rows) | canais_atendimento | taxas_cartoes | pix_saque, versao the
        register's own five, url_dados/url_consulta the live endpoint + human page. The
        upstream serialises null Argumento as the literal string 'None' — normalised to null.
        cnpj is the exact 14-digit whole key (this register carries CnpjInstituicao full,
        unlike the Sedes roots). Path trap: the service lives at /DASFN/versao/v1/ — the
        /DASFN/v1 form answers 403."""
        self._co_only("br_bacen_dasfn")
        c = str(cnpj or "").strip() or None
        r = company.br_bacen.dasfn_raw(c, name=name, api=api, recurso=recurso, limit=limit,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        cen = result["census"]
        ap = cen["by_api"]
        recap = (f" (CNPJ {c})" if c else "") \
            + (f", name contains \"{name}\"" if name else "") \
            + (f", api={api}" if api else "") \
            + (f", recurso contains \"{recurso}\"" if recurso else "")
        if result["rows"]:
            reason = (f"BACEN DASFN API-participation directory: {result['total_matched']} of {result['scanned_rows']:,} rows matched"
                      + recap
                      + f" — pilar3 {ap.get('pilar3', 0):,} / canais_atendimento {ap.get('canais_atendimento', 0)}"
                      + f" / taxas_cartoes {ap.get('taxas_cartoes', 0)} / pix_saque {ap.get('pix_saque', 0)}"
                      + f" across {cen['cnpj_n']} institution CNPJs, all Situacao=Produção;"
                      + " rows are per-endpoint — one CNPJ yields many recursos")
        else:
            reason = (f"BACEN DASFN API-participation directory: zero hits on the {result['scanned_rows']:,}-row directory"
                      + recap
                      + " — a legitimate answer = that institution serves no registered open-data endpoints"
                      + " (drop filters to enumerate from the head)")
        return self._flat_env(
            tool="br_bacen_dasfn",
            input={"cnpj": c, "name": name, "api": api, "recurso": recurso,
                   "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['name'] or '—')[:55]} · {x['api']} v{x['versao']} · {(x['recurso'] or '—')[:40]}"
                                + f" · {x['situacao']}",
                       "url": "https://olinda.bcb.gov.br/olinda/servico/DASFN/versao/v1/odata/Recursos"}
                      for x in result["rows"][:5]],
            provider_id="br_bacen", metas=metas,
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.40 TR BDDK authorised-institution card register (dictionary slot: tr_bddk between ted and tr_spk) ——

    def tr_bddk_institutions(self, name=None, *, category="all", eft=None, status="all",
                             limit=20, execution=None, no_cache=None):
        """company tr_bddk_institutions: the BDDK authorised-institution card register
        (www.bddk.org.tr/Kurulus/Liste/{id}; the company domain's second TR face). TWELVE
        category pages — banks 67 / financial-leasing 86 / factoring 118 / financing 31 /
        financial-holding 3 / asset-management 44 / foreign-bank representatives 36 /
        independent audit 73 / valuation 169 / credit-rating 1 / professional associations 3 /
        savings-financing 9 = 640 cards live (2026-11-04) — each page server-rendered whole
        (no paging, no query surface), cached 24h and scanned locally. The cards are NOT in
        the table: they live in the detayliGor popup button's data-* attributes (ad, aciklama,
        isFaaliyette, eftKodu, isDijital, telefon, faks, adres, webadresi,
        sektordenCikisTarihi, kurulKarari) — the register's own wording is kept verbatim and
        the only derivations are the booleans and the decision number. The register is a
        LIFETIME book: the 222 exited cards are the screening surface (8 of them carry no
        exit date, 79 no decision number — honest gaps stay null). Same-name cards are NOT
        collapsed (640 cards = 631 distinct category+name pairs; e.g. ZİRAAT FİNANSAL
        KİRALAMA appears twice, once active and once exited) — the census reports the
        duplicate structure. No registration number, MERSIS key or tax id on the cards —
        the join to the SPK register is by name + domain."""
        self._co_only("tr_bddk_institutions")
        nm = str(name or "").strip() or None
        r = company.tr_bddk.institutions_raw(nm, category=category, eft=eft, status=status,
                                             limit=limit, cache=self._c._cache,
                                             no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        cen = result["census"]
        cats = " / ".join(f"{k} {v}" for k, v in sorted(cen["by_category"].items()))
        recap = (f" (name contains \"{nm}\")" if nm else "") \
            + (f", category {category}" if category and category != "all" else "") \
            + (f", EFT {eft}" if eft else "") \
            + (f", status {status}" if status and status != "all" else "")
        if result["rows"]:
            reason = (f"BDDK authorised-institution cards: {result['total_matched']} of {result['scanned_rows']:,} cards matched"
                      + recap
                      + f" — {len(cen['categories_scanned'])} of 12 category pages scanned ({cats});"
                      + f" {cen['active']} in operation / {cen['exited']} exited (a lifetime register — the exited cards are the screening surface;"
                      + f" {cen['with_exit_date']} carry an exit date, {cen['with_decision']} a board decision);"
                      + f" {cen['with_eft']} carry an EFT routing code (the payments join key), {cen['digital_banks']} are digital banks;"
                      + f" {cen['duplicate_name_groups']} same-name card groups are kept as published;"
                      + " no registration number or MERSIS key on the cards — join to the SPK register by name + domain")
        else:
            reason = (f"BDDK authorised-institution cards: zero hits on the {result['scanned_rows']:,}-card register"
                      + recap
                      + " — a legitimate answer = no card under that filter (drop the filters to enumerate from the head; the exited cards are the screening surface)")
        return self._flat_env(
            tool="tr_bddk_institutions",
            input={"name": nm, "category": result["params"]["category"], "eft": result["params"]["eft"],
                   "status": result["params"]["status"], "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['name'] or '—')[:55]} · {x['category_label']}"
                                + f" · {'in operation' if x.get('active') else 'EXITED'}"
                                + (f" {x['exit_date']}" if x.get("exit_date") else "")
                                + (f" · EFT {x['eft_code']}" if x.get("eft_code") else "")
                                + (f" · decision {x['decision_no']}" if x.get("decision_no") else ""),
                       "url": ("https://www.bddk.org.tr/Kurulus/Liste/%d"
                               % company.tr_bddk.CATEGORIES[x["category"]][0])}
                      for x in result["rows"][:5]],
            provider_id="tr_bddk", metas=metas,
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.57 TR KAP company-disclosure platform registers (dictionary slot: tr_kap_disclosures <
    # tr_kap_members, both between tr_bddk_institutions and tr_spk_listed; the company domain's TR
    # depth No. 2 — the disclosed-issuer register + the disclosure stream) ——

    def tr_kap_disclosures(self, from_date, *, to_date=None, limit=20,
                           execution=None, no_cache=None):
        """company tr_kap_disclosures: the KAP disclosure stream for a date window
        (www.kap.org.tr POST /tr/api/disclosure/members/byCriteria, JSON body
        {fromDate, toDate}; keyless — the research-era three-piece key was measured OPEN
        all four ways 2026-11-12, so the bare client ships). Rows are disclosures
        verbatim — publishDate in the upstream's own TR format ("12.11.2026 12:41:43"),
        kapTitle, disclosureClass/Type/Category, subject, summary, relatedStocks,
        attachmentCount; corpus reaches 2009-06.

        THE 2,000-ROW RESPONSE CAP: a 10-day window answers EXACTLY 2,000 rows
        newest-first (measured 2026-11-12); no total echo upstream — none fabricated,
        likely_truncated flags the cap and the caller narrows the window (the face caps
        the window at 31 days locally). Egress note: some corporate proxies' exits are
        TLS-reset for this host (this dev machine's is) — direct connect works."""
        self._co_only("tr_kap_disclosures")
        r = company.tr_kap.disclosures_raw(from_date, to_date=to_date, limit=limit,
                                           cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: v for k, v in r.items() if k != "_meta"}
        rows = r["rows"]
        if r["likely_truncated"]:
            head = (f"KAP disclosures {r['from']}..{r['to']}: {r['total_matched']} rows — EXACTLY "
                    f"the {r['census']['response_cap']}-row response cap, the window is wider than "
                    "one response; likely_truncated=true, narrow the window for full coverage "
                    "(no total echo upstream, none fabricated)")
        elif rows:
            head = (f"KAP disclosures {r['from']}..{r['to']}: {r['total_matched']} rows newest-first "
                    f"— e.g. {rows[0].get('publishDate')} {rows[0].get('kapTitle')}")
        else:
            head = (f"KAP disclosures {r['from']}..{r['to']}: zero rows — a window with no "
                    "disclosures (a legitimate answer; KAP publishes trading-day intraday)")
        reason = head + "; rows verbatim (publishDate is the upstream's own TR date format); chain: kapTitle/taxNo joins onto tr_kap_members, stockCodes onto BIST tickers"
        return self._flat_env(
            tool="tr_kap_disclosures",
            input={"from": r["from"], "to": r["to"], "limit": r["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x.get('publishDate')} · {x.get('kapTitle')} · "
                                + str(x.get("disclosureClass")) + "/"
                                + str(x.get('disclosureType')) + " · "
                                + str(x.get("subject") or "")[:90],
                       "url": "https://www.kap.org.tr/tr/bildirim-sorgu"}
                      for x in rows[:5]],
            provider_id="tr_kap", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def tr_kap_members(self, type="IGS", *, state="A", limit=20,
                       execution=None, no_cache=None):
        """company tr_kap_members: the KAP-member issuer register, one segment per call
        (www.kap.org.tr GET /tr/api/company/items/{type}/{state}; keyless bare client —
        the gate was measured open all four ways 2026-11-12). type is the register's own
        segment code (IGS/YK/PYS/BBDK/IGMS — semantics undocumented upstream; IGS/A
        measured 756 rows × 27 keys), state A = the live register. Rows carry the issuer
        join keys verbatim: taxNo + tradeRegNo + tradeRegOffice (the TR company triple),
        mkkMemberOid (the MKK depository id), stockCode (BIST ticker when listed),
        kapMemberTitle, paidCapital/kayitliSermayeTavani, faaliyetDurumu, cityName.

        The W-state placeholder is a FILTER LAW: state=W answers ONE fake row (taxNo
        111111111111, tradeRegNo 'A', no title — the register's placeholder, measured)
        — dropped from rows[], counted in census.placeholder_rows, never shipped as an
        issuer. sgbfOrtaklikYapisi is a STRUCTURE flag kept verbatim; no SGBF
        member-entity face exists by ruling (fund-manager PII red line)."""
        self._co_only("tr_kap_members")
        r = company.tr_kap.members_raw(type=type, state=state, limit=limit,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: v for k, v in r.items() if k != "_meta"}
        rows = r["rows"]
        cen = r["census"]
        top = (rows or [None])[0]
        reason = (f"KAP member register, type {r['type']} / state {r['state']}: "
                  f"{r['total_matched']} issuers"
                  + (f" — top hit {top.get('kapMemberTitle')} (taxNo {top.get('taxNo')}"
                     + (f", BIST {top.get('stockCode')}" if top.get("stockCode") else "") + ")"
                     if top else "")
                  + (f"; {cen['placeholder_rows']} placeholder row(s) dropped (the W-state fake "
                     "record — taxNo 111111111111, tradeRegNo 'A', no title)" if cen["placeholder_rows"] else "")
                  + "; the TR company triple taxNo+tradeRegNo+tradeRegOffice and mkkMemberOid are "
                    "the join keys; sgbfOrtaklikYapisi is a structure flag verbatim (no SGBF "
                    "member-entity face exists by ruling — fund-manager PII red line)")
        return self._flat_env(
            tool="tr_kap_members",
            input={"type": r["type"], "state": r["state"], "limit": r["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{x.get('kapMemberTitle')} · taxNo {x.get('taxNo')}"
                                + (f" · tradeRegNo {x.get('tradeRegNo')} ({x.get('tradeRegOffice')})"
                                   if x.get("tradeRegNo") else "")
                                + (f" · BIST {x.get('stockCode')}" if x.get("stockCode") else ""),
                       "url": "https://www.kap.org.tr/tr/bildirim-sorgu"}
                      for x in rows[:5]],
            provider_id="tr_kap", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )


    # —— 0.3.41 DE federal insolvency announcements (dictionary slot: de_inso between cz_ares and edgar/fdic) ——

    def de_inso_search(self, state=None, *, subject=None, date_from=None, date_to=None,
                       name=None, first_name=None, seat=None, az=None, limit=20,
                       execution=None, no_cache=None):
        """company de_inso_search: the German federal insolvency announcements
        (neu.insolvenzbekanntmachungen.de/ap/suche.jsf; the company domain's first DE face).
        A Jakarta Faces postback portal, not a query API: one GET (ViewState + the form action
        that carries the session) + one form-urlencoded POST. Every filter is the portal's own
        — --state (the sixteen Länder codes), --subject (the nine Gegenstand codes: EROEFF =
        openings, ENT_RSB = the discharge decisions, …), --date-from/--date-to (the portal's
        window), --name (the surname / company designation — the upstream matches it EXACTLY,
        case-insensitively: "af-media gmbh" hits, "AF-Media" does not), --first-name, --seat,
        --az (the case number "504 IN 277/26" — the Abteilung may be absent, "IN 261/24").

        The row grain is the ANNOUNCEMENT, not the case (one case carries several announcements
        on one day — the rows are never deduped). Each row carries six cells: date, case
        number, court, debtor, seat and the REGISTER cell ("Düsseldorf, HRB 101036") — the hard
        join key, present on ~9% of the rows. The upstream refuses a window above its own cap
        ("maximale Trefferzahl beträgt 1000"); that answer comes back as a structured state
        with the upstream's verbatim sentence, not as an error — the working grain is ONE STATE
        x ONE DAY (a single state-day renders ~1,050-1,080 rows; a two-day state window is
        refused). The announcement full text (the row's zoom popup) needs a real browser click
        and is NOT part of this face."""
        self._co_only("de_inso_search")
        r = company.de_inso.search_raw(state=state, subject=subject, date_from=date_from,
                                       date_to=date_to, name=name, first_name=first_name,
                                       seat=seat, az=az, limit=limit,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        p = result["params"]
        cen = result["census"]
        recap = (f" (name \"{p['name']}\")" if p["name"] else "") \
            + (f", first name \"{p['first_name']}\"" if p["first_name"] else "") \
            + (f", seat \"{p['seat']}\"" if p["seat"] else "") \
            + (f", case number {p['az']}" if p["az"] else "") \
            + (f", state {p['state']}" if p["state"] else "") \
            + (f", subject {p['subject']}" if p["subject"] else "") \
            + f", window {p['date_from']}..{p['date_to']}"
        if result["state"] == "too_many_hits":
            reason = ("German federal insolvency announcements: the upstream refused the window "
                      + recap
                      + f' — "{result["message"]}"'
                      + " (its cap counts above ~1,000 announcements; the working grain is ONE "
                        "STATE x ONE DAY — narrow with --state and a one-day window, or add a "
                        "name / register / case-number filter)")
        elif result["rows"]:
            reason = (f"German federal insolvency announcements: {result['total_matched']} announcement rows"
                      + recap
                      + f" — {cen['distinct_cases']} distinct cases over {cen['distinct_debtors']} debtors"
                      + f" ({cen['duplicate_case_rows']} duplicate case rows kept — the grain is the announcement, not the case);"
                      + f" {cen['with_register']} of {result['total_matched']} rows carry the Register cell (the join key);"
                      + f" the portal applied {cen['state_applied']} / {cen['window_applied']}"
                      + " (the announcement full text needs a real browser click — not in this face)")
        else:
            reason = ("German federal insolvency announcements: zero hits"
                      + recap
                      + " — a legitimate answer = no announcement under that filter (the name "
                        "field matches the surname / company designation EXACTLY, case-insensitively)")
        return self._flat_env(
            tool="de_inso_search",
            input={"state": p["state"], "subject": p["subject"], "date_from": p["date_from"],
                   "date_to": p["date_to"], "name": p["name"], "first_name": p["first_name"],
                   "seat": p["seat"], "az": p["az"], "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['date_iso'] or x['date'] or '—')} · {x['case_number'] or '—'}"
                                f" · {x['debtor'] or '—'}"
                                + (f" · {x['register']}" if x.get("register") else ""),
                       "url": "https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf"}
                      for x in result["rows"][:5]],
            provider_id="de_inso", metas=metas,
            query={"source": "raw", "upstream": p},
        )

    def de_inso_register_lookup(self, register_court=None, *, register_type=None,
                                register_number=None, date_from=None, date_to=None, limit=20,
                                execution=None, no_cache=None):
        """company de_inso_register_lookup: the German federal insolvency announcements by
        REGISTER ENTRY — the HRB/HRA point lookup, the hard join key against the commercial
        registers. The upstream demands the entry unambiguously: court + type + number all
        three (a half-filled entry is rejected: "Der Registereintrag muss eindeutig belegt
        sein"). --register-court takes the upstream code (R1101) or the court name
        ("Düsseldorf" — the 149 register courts are embedded); --register-type is one of
        HRA/HRB/VR/PR/GNR/GSR; --register-number is the register's own number.

        The window defaults to today; widen it to cover the entity's lifetime (the portal has
        published since 2022-01-03). The row grain is the announcement — one register entry
        carries several announcements (openings, the discharge decision, the distribution
        list) and they are kept apart."""
        self._co_only("de_inso_register_lookup")
        r = company.de_inso.register_lookup_raw(register_court=register_court,
                                                register_type=register_type,
                                                register_number=register_number,
                                                date_from=date_from, date_to=date_to, limit=limit,
                                                cache=self._c._cache,
                                                no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        p = result["params"]
        cen = result["census"]
        court_name = company.de_inso.REGISTER_COURTS.get(p["register_court"], p["register_court"])
        recap = (f" (register {court_name} {p['register_type']} {p['register_number']})"
                 + f", window {p['date_from']}..{p['date_to']}")
        if result["state"] == "too_many_hits":
            reason = ("German federal insolvency announcements (register entry): the upstream refused the window"
                      + recap
                      + f' — "{result["message"]}" (narrow the window)')
        elif result["rows"]:
            reason = (f"German federal insolvency announcements (register entry): {result['total_matched']} announcement rows"
                      + recap
                      + f" — {cen['distinct_cases']} distinct cases over {cen['distinct_debtors']} debtors"
                      + " (the grain is the announcement — one register entry carries several: openings, "
                        "the discharge decision, the distribution list)"
                      + " (the announcement full text needs a real browser click — not in this face)")
        else:
            reason = ("German federal insolvency announcements (register entry): zero hits"
                      + recap
                      + " — a legitimate answer = no announcement for that register entry in the window")
        return self._flat_env(
            tool="de_inso_register_lookup",
            input={"register_court": p["register_court"], "register_type": p["register_type"],
                   "register_number": p["register_number"], "date_from": p["date_from"],
                   "date_to": p["date_to"], "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['date_iso'] or x['date'] or '—')} · {x['case_number'] or '—'}"
                                f" · {x['debtor'] or '—'}"
                                + (f" · {x['register']}" if x.get("register") else ""),
                       "url": "https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf"}
                      for x in result["rows"][:5]],
            provider_id="de_inso", metas=metas,
            query={"source": "raw", "upstream": p},
        )

    # —— 0.3.45 ES BORME daily gazette (dictionary slot: es_borme between edgar_fts and es_cnmv) ——

    def es_borme_day(self, date, *, kind=None, limit=20, execution=None, no_cache=None):
        """company es_borme_day: one publication day's BORME notice inventory (www.boe.es;
        the company domain's second/third ES faces with es_borme_notice). GET
        /borme/dias/{y}/{m}/{d}/ — one keyless shot per day, scanned locally (the upstream
        has no query surface). Each row is <li class="dispo"> whose id IS the key and whose
        PREFIX carries the subsection — THREE measured: BORME-A-* = SECCIÓN PRIMERA
        Empresarios actos inscritos (the company-life-event register; ids carry the
        boletin segment, BORME-A-2026-212-03), BORME-B-* = SECCIÓN PRIMERA «Otros actos
        publicados en el Registro Mercantil» (ids like BORME-B-2026-212-08), BORME-C-* =
        SECCIÓN SEGUNDA anuncios y avisos legales (ids WITHOUT the boletin segment,
        BORME-C-2026-5782). The row title cannot be kind-guessed (A/B rows are provinces —
        BARCELONA appears in BOTH primera subsections on the same day — and C rows are
        usually company names but CAN be provinces) — the id prefix is the only authority;
        the census counts the day's dispo li's separately from parsed rows so a drifted
        row shows as a gap instead of vanishing.

        No-publication days (weekends, gazette holidays — measured 2026-11-01) answer HTTP
        404 upstream and surface here as a structured published=false answer, never an
        error; a future date is refused locally (the gazette publishes early morning CET).
        Chain: take ids from this face into es_borme_notice — the day page carries NO
        xml.php links."""
        self._co_only("es_borme_day")
        r = company.es_borme.day_raw(date, kind=kind, limit=limit, cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        cen = r["census"]
        p = r["params"]
        if not r["published"]:
            reason = (f"BORME day inventory, {r['date']}: no issue published — the upstream day page "
                      "answers 404 (weekend / gazette holiday, or the day's issue is not out yet — "
                      "BORME publishes early morning CET). A legitimate no-publication day, "
                      "structured as such, never an error")
        else:
            head = (f"BORME day inventory, {r['date']} (boletin Núm. {r['boletin_number']}, "
                    f"\"{r['title']}\"): scanned {r['scanned_rows']} rows, {r['total_matched']} matched"
                    + (f" with --kind {p['kind']}" if p["kind"] else "")
                    + f" — A {cen['a_count']} (SECCIÓN PRIMERA Empresarios: actos inscritos)"
                    + (f" + B {cen['b_count']} (SECCIÓN PRIMERA: otros actos publicados)"
                       if cen["b_count"] else "")
                    + f" + C {cen['c_count']} (SECCIÓN SEGUNDA, anuncios y avisos legales)")
            drift = ("; ROW SHAPE DRIFT: dispo li count != parsed rows — a row's link block "
                     "drifted upstream, inspect before trusting the inventory"
                     if cen["dispo_rows"] != cen["parsed_rows"] else "")
            reason = (head + drift
                      + "; the id prefix carries the section — the row title cannot be "
                        "kind-guessed (C rows can be provinces too); ids chain into es_borme_notice")
        return self._flat_env(
            tool="es_borme_day",
            input={"date": r["date"], "kind": p["kind"], "limit": r["limit_applied"]},
            reason=reason,
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": f"{x['id']} · {x['kind']} · {x['title']}",
                       "url": "https://www.boe.es" + x["pdf_path"]}
                      for x in r["rows"][:5]],
            provider_id="es_borme", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"path": "/borme/dias/{y}/{m}/{d}/", "date": r["date"],
                                "local_scan": {"kind": p["kind"]}}},
        )

    def es_borme_notice(self, notice_id, *, name=None, order=None, limit=20,
                        execution=None, no_cache=None):
        """company es_borme_notice: one BORME notice from its machine-readable XML twin
        (www.boe.es/diario_borme/xml.php?id=…; ids come from es_borme_day — the day page
        carries no xml.php links). A/B notices (SECCIÓN PRIMERA Empresarios — actos
        inscritos / otros actos publicados) parse as companies[]:
        <p class=articulo>ORDER - NAME.</p> opens a company, every following
        <p class=parrafo> appends an event paragraph (Constitución / objeto social /
        domicilio / Capital / Socio único, Nombramientos / Adm. Unico, Reelecciones /
        Auditor, …, the trailing «Datos registrales» sheet string); 1:1 articulo↔parrafo
        measured on MADRID 756/756, the state machine covers multi-paragraph companies.
        C notices (SECCIÓN SEGUNDA) are parrafo-only announcement text with a
        <departamento> heading — kept verbatim.

        Postures: NO NIF / registration number exists in the body — joins ride the name
        plus the Datos registrales sheet string, both verbatim; fecha_actualizacion rides
        the result so a corrected republication is visible (TTL 7d — a published notice is
        frozen); a well-formed but unknown id answers upstream_not_found (the cz_ares
        posture); BORME-S-* summary ids are refused locally (upstream 400s them)."""
        self._co_only("es_borme_notice")
        r = company.es_borme.notice_raw(notice_id, name=name, order=order, limit=limit,
                                        cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        cen = r["census"]
        sec = r["seccion"] or {}
        p = r["params"]
        kind = cen.get("kind")
        id_kind = cen.get("id_kind")
        if kind in ("A", "B"):
            body = (f"{kind} notice (SECCIÓN PRIMERA Empresarios) — scanned {r['scanned_companies']} "
                    f"companies, {cen['events']} event paragraphs (articulo opens, parrafo appends); "
                    "NO NIF/registration number in the body — joins ride the name plus the "
                    "«Datos registrales» sheet string, both verbatim")
        else:
            body = (f"C announcement ({r['departamento'] or 'no departamento heading'}) — "
                    f"{cen['paragraphs']} paragraphs verbatim")
        mism = ""
        if id_kind and kind and id_kind != kind:
            mism = (f"; ID/SECTION MISMATCH: the id prefix says {id_kind} while the XML section "
                    f"says {kind} — upstream shape drifted")
        frag = ""
        if kind in ("A", "B") and (cen.get("unparsed_articulo") or cen.get("orphan_parrafo")):
            frag = ("; UNPARSED fragments present (articulo without the ORDER - NAME shape / "
                    "parrafo before the first articulo) — counted in the census, kept, never dropped")
        filtered = p["name"] or p["order"] is not None
        if kind in ("A", "B") and not r["companies"] and filtered:
            filt_tail = " — zero hits is a legitimate answer (no company under that filter)"
        elif filtered:
            filt_tail = f"; --name/--order matched {r['total_matched']} of {r['scanned_companies']}"
        else:
            filt_tail = ""
        reason = (f"BORME notice {r['identificador']} (\"{r['titulo']}\", {sec.get('titulo')}, "
                  f"diario Núm. {r['diario_numero']}, published {r['fecha_publicacion']}, "
                  f"pages {r['pagina_inicial']}–{r['pagina_final']}): {body}"
                  + (f"; as-of {r['fecha_actualizacion']}" if r["fecha_actualizacion"] else "")
                  + mism + frag + filt_tail)

        def _ev(c):
            first = (c["events"][0][:110] + "…") if c["events"] else "(no event paragraphs)"
            return f"{c['order']} · {c['name']} · {len(c['events'])} event(s) · {first}"
        evidence = [{"quote": _ev(x), "url": r["url_pdf"]} for x in r["companies"][:5]]
        if not r["companies"] and r["paragraphs"]:
            evidence = [{"quote": r["paragraphs"][0][:160], "url": r["url_pdf"]}]
        return self._flat_env(
            tool="es_borme_notice",
            input={"id": r["identificador"], "name": p["name"], "order": p["order"],
                   "limit": r["limit_applied"]},
            reason=reason,
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=evidence,
            provider_id="es_borme", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"path": "/diario_borme/xml.php", "id": r["identificador"],
                                "local_scan": {"name": p["name"], "order": p["order"]}}},
        )

    # —— 0.3.44 ES CNMV entidades register (dictionary slot: es_cnmv between de_inso and fdic) ——

    def es_cnmv_entities(self, category, *, name=None, nif=None, numero=None, limit=20,
                         execution=None, no_cache=None):
        """company es_cnmv_entities: the CNMV supervised-entity register (www.cnmv.es; the
        company domain's first ES face) — FOURTEEN categories behind one endpoint
        (listadoentidad.aspx?id=1&tipoent=0..13), one keyless shot per category, scanned
        locally because the upstream has no query surface. 1,760 entities live 2026-11-04;
        eea_investment_firms_passport (812) + eu_credit_passport (469) are Spain's view of
        the European financial passport.

        The row is <li class="blocks-single"> with the entity's own detail href as its key —
        TEN (endpoint, tipo) kinds measured (esis?nif= national / esisextranjeraslp?CLP|XLP /
        esisextranjerassuc?CSU|XSU / esisentcredito?ECN|SECC|SECE|ECCLP|ECELP / eafi?EAF /
        afn?AFN); the numero values are official register numbers, never synthesized into a
        walk. NIFs come dashed AND bare (A-83217281 / B22526768) — normalised for joins, both
        forms accepted by --nif. The cookie banner occupies <h1> on the big pages while the
        data is fine — the title is read from <title>. portfolio_managers and
        eu_credit_subsidiaries_passport are EMPTY categories (a titled page with zero rows —
        the SGC list moved to its own ListadoGestorasFTA page): reported as category
        emptiness, never retried as an error. The NIF keyspace is shared with the CNMV
        sanctions register (datosentidad.aspx) — roster↔sanctions is the licence-lifecycle
        join."""
        self._co_only("es_cnmv_entities")
        r = company.es_cnmv.entities_raw(category=category, name=name, nif=nif, numero=numero,
                                         limit=limit, cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        cen = r["census"]
        top = (rows or [None])[0]
        p = r["params"]
        filtered = p["name"] or p["nif"] or p["numero"]
        if cen["empty_category"]:
            tail = (" — this CATEGORY is empty on the register (a titled page with zero rows; "
                    "the SGC list moved to its own ListadoGestorasFTA page), not a filter miss")
        elif rows:
            tail = (f" — top hit {top['name']}"
                    + (f" (NIF {top['nif']})" if top["nif"] else
                       f" (numero {top['numero']}, {top['key_kind']})"))
        elif filtered:
            tail = " — zero hits is a legitimate answer (no entity under that filter)"
        else:
            tail = ""
        reason = (f"CNMV entidades register, category {cen['category']} "
                  f"(tipoent {cen['tipoent']}, \"{cen['page_title']}\"): scanned "
                  f"{r['scanned_rows']} rows, {r['total_matched']} matched{tail}; key kinds "
                  f"{cen['key_kinds']}"
                  + (f"; NIFs dashed {cen['nif_dashed']} / bare {cen['nif_bare']} — normalised for joins"
                     if cen["nif_dashed"] or cen["nif_bare"] else "")
                  + ("; UNMAPPED key kinds present — the href space drifted" if cen["unmapped_key_kinds"] else "")
                  + "; the NIF keyspace is shared with the CNMV sanctions register (datosentidad.aspx)")
        return self._flat_env(
            tool="es_cnmv_entities",
            input={"category": p["category"], "name": p["name"], "nif": p["nif"],
                   "numero": p["numero"], "limit": r["limit_applied"]},
            reason=reason,
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": (f"{x['name']} · "
                                 + (f"NIF {x['nif']} ({x['nif_form']})" if x["nif"]
                                    else f"numero {x['numero']} · {x['key_kind']}")
                                 + " · detail " + x["detail_path"]),
                       "url": x["detail_url"]}
                      for x in rows[:5]],
            provider_id="es_cnmv", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"path": "/portal/consultas/listadoentidad.aspx",
                                "id": 1, "tipoent": cen["tipoent"], "local_scan":
                                    {"name": p["name"], "nif": p["nif"], "numero": p["numero"]}}},
        )

    # —— 0.3.57 ES OEPM industrial-property gazette index (dictionary slot: es_oepm between
    # es_cnmv_entities and fdic_institutions; the company domain's IP face No. 2 after the
    # jp_jplatpat trio — trademarks/patents are company-hard-keyed surfaces) ——

    def es_oepm_bopi(self, tomo, date, *, execution=None, no_cache=None):
        """company es_oepm_bopi: one BOPI issue's publication metadata + the tomo's
        chapter/modality reference lists (sede.oepm.gob.es/apibopiweb; keyless plain SDK
        UA). The issue payload is small and half-empty BY DESIGN: id and
        fechaPublicacion arrive null on every measured issue — idPdfUcm / idXmlUcm /
        idHtmlUcm are the real keys (the whole issue's PDF/XML/HTML documents, a second
        surface out of this face's scope — the kr_law ruling). Tomo 1 = marcas
        (trademarks), tomo 2 = patents / utility models / designs.

        The non-publication negative is a CHANNEL WALL: a weekend AND a pre-digital date
        (1995) both answer HTTP 200 with a ZERO-BYTE body — the op declares accept:'text'
        so the empty body passes as "" (the JSON channel would blame a WAF) and the face
        surfaces published=false, never an error. The chapter list ([{"13": "1.
        MARCAS"}, …], single-key dicts) and the modality code map ({"1": "M - Marca", …}
        — incl. F transfer / K rename / L license) ride along as the tomo's decoding
        dictionaries (cached 7d — structural)."""
        self._co_only("es_oepm_bopi")
        r = company.es_oepm.bopi_raw(tomo, date, cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: v for k, v in r.items() if k != "_meta"}
        ref = r["reference"]
        if not r["published"]:
            reason = (f"OEPM BOPI tomo {r['tomo']}, {r['date']}: no issue — the upstream answers "
                      "200 with a zero-byte body (weekend / gazette holiday / pre-digital date; "
                      "measured on a Saturday and on 1995-01-04), the register's own no-issue "
                      "signal, structured as such, never an error")
        else:
            iss = r["issue"] or {}
            reason = (f"OEPM BOPI tomo {r['tomo']}, {r['date']}: issue published — UCM artifact "
                      f"keys idPdfUcm {iss.get('idPdfUcm')} / idXmlUcm {iss.get('idXmlUcm')} / "
                      f"idHtmlUcm {iss.get('idHtmlUcm')} (the whole issue's documents — a second "
                      "surface out of scope); id/fechaPublicacion arrive null upstream, kept "
                      "verbatim; reference: "
                      + str(len(ref["capitulos"])) + " chapters, "
                      + str(len(ref["modalidades"])) + " modality codes")
        return self._flat_env(
            tool="es_oepm_bopi",
            input={"tomo": r["tomo"], "date": r["date"]},
            reason=reason,
            result=result,
            evidence=([{"quote": f"tomo {r['tomo']} · {r['date']} · idPdfUcm "
                                + str((r["issue"] or {}).get("idPdfUcm"))
                                + " · idXmlUcm " + str((r["issue"] or {}).get("idXmlUcm")),
                       "url": (f"https://sede.oepm.gob.es/apibopiweb/publicacionesBopiTomoYFecha/"
                               f"{r['tomo']}/{r['date'][8:10]}-{r['date'][5:7]}-{r['date'][:4]}")}]
                      if r["published"] else
                      [{"quote": "200 OK, zero-byte body — the register's own no-issue signal",
                        "url": "https://sede.oepm.gob.es/apibopiweb/publicacionesBopiTomoYFecha/"
                               + f"{r['tomo']}/{r['date'][8:10]}-{r['date'][5:7]}-{r['date'][:4]}"}]),
            provider_id="es_oepm", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"path": "/apibopiweb/publicacionesBopiTomoYFecha/{tomo}/{ddmmyyyy}",
                                "tomo": r["tomo"], "ddmmyyyy":
                                    f"{r['date'][8:10]}-{r['date'][5:7]}-{r['date'][:4]}"}},
        )

    # —— 0.3.42 JP FSA licensed/registered institution farm (dictionary slot: jp_fsa between je_jfsc and kz_gbd) ——

    def jp_fsa_licensed(self, category, *, name=None, jcn=None, limit=20,
                        execution=None, no_cache=None):
        """company jp_fsa_licensed: the FSA licensed / registered institution farm
        (www.fsa.go.jp/en/regulated/licensed/*.xlsx; the company domain's first JP
        face). THIRTY-ONE keyless XLSX registers behind one hub, each with its own
        as-of stamp and its own sheet shape — --category picks the register
        (city_banks 36 / foreign_banks 57 / regional_banks 97 / bank_holding 31 /
        credit_associations 255 / shinkumi_banks 144 / keito 1 / trust_business 61 /
        trust_companies 37 / self_trust 3 / trust_agents 349 / foreign_bank_agents 46
        / financial_instruments_operators 1,957 / financial_intermediaries 678 /
        high_speed_traders 54 / crypto_exchanges 27 / electronic_payment_issuers 2 /
        fx_analysis 3 / clearing_organizations 7 / fund_clearing 1 / book_entry 2 /
        trade_repositories 1 / credit_rating_agencies 8 / benchmark_administrators 2
        / securities_finance 1 / designated_parent 2 / exchange_operators 2 /
        life_insurers 41 / nonlife_insurers 59 / insurance_holdings 14 /
        foreign_audit_firms 104 — live 2026-11-05; ~4,082 entities over the farm).
        The files are fetched once per 24h window and scanned locally — the upstream
        has NO query surface (--name contains, --jcn exact 13 digits are local).

        Postures kept: the JCN / Corporate Number / 法人番号 columns are ONE key under
        three spellings; the 'Total N banks' subtotal cells ride ON data rows (the row
        stays, the class does not change); several registers are FROZEN years back
        (securities_finance/designated_parent as of Oct 2017, clearing Aug 2016) and
        each file's own as-of rides the census so a stale register never masquerades
        as live; the two Japanese-language sintaku files carry the furigana reading
        concatenated onto every value (stripped positionally, only on those files);
        fafia is an ACCUMULATING register (545 sheet rows fold into 104 firms with
        their '○'-marked foreign-issuer lists); the insurance lists and the FMI four
        carry NO corporate number (honest nulls)."""
        self._co_only("jp_fsa_licensed")
        r = company.jp_fsa.licensed_raw(category, name=name, jcn=jcn, limit=limit,
                                        cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        p = result["params"]
        cen = result["census"]
        label = company.jp_fsa.FAMILIES[p["category"]]["label"]
        recap = (f" (name contains \"{p['name']}\")" if p["name"] else "") \
            + (f", JCN {p['jcn']}" if p["jcn"] else "")
        asofs = " / ".join(f"{stem.split('.')[0]} {f['as_of']}" if f.get("as_of") else f"{stem.split('.')[0]} (no stamp)"
                           for stem, f in cen["files"].items())
        frozen = [stem for stem, f in cen["files"].items()
                  if f.get("as_of") and str(f["as_of"]) < "2024-01-01"]
        if result["rows"]:
            reason = (f"FSA {label}: {result['total_matched']} of {result['scanned_rows']:,} register rows matched"
                      + recap
                      + f" — register(s) {asofs};"
                      + f" {cen['with_jcn']} rows carry the JCN / Corporate Number (the join key),"
                      + f" {cen['with_registration_number']} a registration number, {cen['registered']} a decoded registration date"
                      + ("; the register(s) are FROZEN years back — a stale snapshot, not a live list"
                         if frozen else "")
                      + ("; the register carries NO corporate number — join by name" if cen["with_jcn"] == 0 else ""))
        else:
            reason = (f"FSA {label}: zero hits on the {result['scanned_rows']:,}-row register"
                      + recap
                      + " — a legitimate answer = no licensed entity under that filter (drop the filters to enumerate from the head)")
        return self._flat_env(
            tool="jp_fsa_licensed",
            input={"category": p["category"], "name": p["name"], "jcn": p["jcn"],
                   "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x.get('name') or '—')[:55]}"
                                + (f" · JCN {x['jcn']}" if x.get("jcn") else "")
                                + (f" · {x['registration_number']}" if x.get("registration_number") else "")
                                + (f" · {x['business_category']}" if x.get("business_category") else "")
                                + (f" · registered {x['registered_at']}" if x.get("registered_at") else "")
                                + (f" · {len(x['issuers_audited'])} issuers" if x.get("issuers_audited") else "")
                                + (f" · {len(x['instruments'])} crypto-assets" if x.get("instruments") else ""),
                       "url": "https://www.fsa.go.jp/en/regulated/licensed/" + x["file"]}
                      for x in result["rows"][:5]],
            provider_id="jp_fsa", metas=metas,
            query={"source": "raw", "upstream": p},
        )

    # —— 0.3.43 CA OSB CCAA restructuring roster (dictionary slot: ca_osb between br_bacen and ch_zefix) ——

    def ca_ccaa_records(self, name=None, *, province=None, monitor=None, osb=None,
                        limit=20, execution=None, no_cache=None):
        """company ca_ccaa_records: the Office of the Superintendent of Bankruptcy CCAA
        roster (open.canada.ca CKAN package 92697343-…; the free Companies' Creditors
        Arrangement Act list — federal large-company restructuring). ELEVEN keyless
        year-named XLSX resources behind one CKAN package, each a CUMULATIVE snapshot:
        the face resolves the LATEST at call time (URL rolls quarterly, never
        hard-coded) and scans it locally — 730 proceedings spanning 2009→2026, live
        2026-11-05 (resource 'CCAA Records List - 2026', Q2 file). ~50-80 filings a
        year, each row carrying the court, the OSB File Number (estate key, province
        in its suffix), the initial order date, head office, and the full
        court-appointed-monitor block (KPMG/FTI/PwC/EY/Deloitte… with representative,
        email, employees) plus filing amounts where disclosed. The upstream has NO
        query surface (--name / --monitor / --province / --osb are local filters).

        Postures kept: the Federal Insolvency Records Search (the 1978→today estate
        library) is a PAID wall — account + ~$8/query — and is NOT this face
        (keyless-only ruling); columns map by HEADER NAME anchors (the 2016-era
        files carry 17 columns, the current 21 — both parse, drift fails loudly);
        dates ride THREE forms in one file (Excel serial / ISO strings / dd/mm/yyyy
        in the oldest files) — all decoded; the province rides the OSB File Number
        suffix, not a court-string guess; the employees column doubles as a
        sealing-order marker (court-sealed cases — sealed_order=true, null
        employees); amounts keep their float tails verbatim; monitor contact
        details are practicing-professional public register information."""
        self._co_only("ca_ccaa_records")
        r = company.ca_osb.ccaa_records_raw(name=name, province=province, monitor=monitor,
                                            osb=osb, limit=limit,
                                            cache=self._c._cache,
                                            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_metas")}
        metas = r.get("_metas") or [r["_meta"]]
        p = result["params"]
        cen = result["census"]
        span = cen.get("initial_order_year_span") or {}
        recap = (f" (name contains \"{p['name']}\")" if p["name"] else "") \
            + (f", province {p['province']}" if p["province"] else "") \
            + (f", monitor contains \"{p['monitor']}\"" if p["monitor"] else "") \
            + (f", OSB {p['osb']}" if p["osb"] else "")
        provs = cen["provinces"]
        if result["rows"]:
            reason = (f"OSB CCAA cumulative roster: {result['total_matched']} of {result['scanned_rows']:,} proceedings matched"
                      + recap
                      + f" — resource \"{cen['resource']['name']}\" spans {span.get('min')}→{span.get('max')}"
                      + f" (ON {provs.get('ON', 0)} / QC {provs.get('QC', 0)} / AB {provs.get('AB', 0)} / BC {provs.get('BC', 0)});"
                      + f" {cen['with_amounts']} rows carry filing amounts, {cen['sealed_orders']} are court-sealed,"
                      + f" {cen['discharged']} carry a discharge order — NO corporate-number column: join by company name + province"
                      + " (the 1978→today full estate library is a paid wall, NOT this face)")
        else:
            reason = (f"OSB CCAA cumulative roster: zero hits on the {result['scanned_rows']:,}-proceeding snapshot"
                      + recap
                      + " — a legitimate answer = no CCAA proceeding under that filter (drop the filters to enumerate from the head)")
        return self._flat_env(
            tool="ca_ccaa_records",
            input={"name": p["name"], "province": p["province"], "monitor": p["monitor"],
                   "osb": p["osb"], "limit": result["limit_applied"]},
            reason=reason,
            result=result,
            evidence=[{"quote": f"{(x['company_name'] or '—')[:55]}"
                                + f" · OSB {x['osb_file_number']}"
                                + (f" · {x['province']}" if x["province"] else "")
                                + (f" · initial {x['initial_order_date']}" if x["initial_order_date"] else "")
                                + (f" · {x['monitor'][:40]}" if x["monitor"] else "")
                                + (" · SEALED" if x["sealed_order"] else ""),
                       "url": x["proceedings_web_page"] or cen["resource"]["url"]}
                      for x in result["rows"][:5]],
            provider_id="ca_osb", metas=metas,
            query={"source": "raw", "upstream": p},
        )
    # —— 0.3.71 E13 CSE universe + issuer card (dictionary slot: ca_ccaa_records <
    # ca_cse_company < ca_cse_listed < ch_six_fqs_search; thecse.com Next.js head's own
    # /api/webapi/* JSON — no screen-scraping) ——

    def ca_cse_listed(self, *, symbol=None, name=None, sector=None, status=None,
                      security_type=None, tier=None, limit=None, execution=None, no_cache=None):
        """company ca_cse_listed: the Canadian Securities Exchange listed universe
        (CA — thecse.com's own /api/webapi/listed-companies/ JSON: 739 rows probe day,
        fields verbatim snake_case). Status is the negative-list material: Active 628 /
        Suspended 85 / Halted Pending Fundamental Change 23 / Delisted 3 — --status
        filters them. --symbol exact, --name substring, --sector/--security-type exact
        case-insensitive, --tier int, --limit slices. trading_date is PER-ROW (last
        trade date, not an as-at anchor)."""
        self._co_only("ca_cse_listed")
        r = company.ca_cse.listed(symbol=symbol, name=name, sector=sector, status=status,
                                  security_type=security_type, tier=tier, limit=limit,
                                  cache=self._c._cache,
                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        result = {k: x for k, x in r.items() if k != "_meta"}
        if rows:
            top = rows[0]
            reason = (f"CSE listed universe: {r['total']} rows match"
                      f" — sample {top.get('symbol') or '—'} {top.get('security_name') or '—'} · "
                      f"{top.get('status') or '—'} · {top.get('sector') or '—'}"
                      + (f" · traded {top.get('trading_date')}" if top.get("trading_date") else "")
                      + " — rows carry live quote fields (trading_date is per-row last trade, "
                        "not an as-at anchor)")
        else:
            reason = (f"CSE listed universe: zero rows match (symbol={symbol or '—'}, "
                      f"name={name or '—'}, sector={sector or '—'}, status={status or '—'}, "
                      f"security_type={security_type or '—'}, tier={tier if tier is not None else '—'} "
                      "— an empty answer is a legitimate miss; --status suspended/halted "
                      "negative lists are legal queries)")
        return self._flat_env(
            tool="ca_cse_listed",
            input={"symbol": symbol, "name": name, "sector": sector, "status": status,
                   "security_type": security_type, "tier": tier, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('symbol') or '—'} {x.get('security_name') or '—'} · "
                                f"{x.get('status') or '—'} · tier {x.get('tier') if x.get('tier') is not None else '—'} · "
                                f"{x.get('security_type') or '—'} · {x.get('currency') or '—'}",
                       "url": "https://thecse.com/en/api/webapi/listed-companies/"}
                      for x in rows[:5]],
            provider_id="ca_cse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": "https://thecse.com/en/api/webapi/listed-companies/"}},
        )

    def ca_cse_company(self, *, symbol, execution=None, no_cache=None):
        """company ca_cse_company: the CSE issuer market card for one symbol —
        metadata + quote (bid/ask) + ticker (OHLC) + trades with market-maker dealer
        names + depth by order and by price + the CSE2 twin + consolidated. Bad symbol
        = 200 with a ZERO-BYTE body upstream → found=false (the silent-empty law;
        never fabricated). The deprecated `metatdata` key (upstream removal_date
        2022-07-01) is dropped — `metadata` is the live one."""
        self._co_only("ca_cse_company")
        r = company.ca_cse.company(symbol=symbol, cache=self._c._cache,
                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        md = (r.get("card") or {}).get("metadata") or {}
        if r["found"]:
            reason = (f"CSE issuer card {r['symbol']}: {md.get('security_name') or '—'}"
                      f" · {md.get('status') or '—'} · {md.get('sector') or '—'} · {md.get('currency') or '—'}"
                      + (f" · listed {md.get('listing_date')}" if md.get("listing_date") else "")
                      + " — card carries quote/ticker/trades (dealer names)/depth/CSE2 twin/"
                        "consolidated and the `legal` disclaimer text")
        else:
            reason = (f"CSE issuer card {r['symbol']}: not found (upstream answered 200 with "
                      "an empty body — the silent-empty law; check the ticker on ca_cse_listed)")
        return self._flat_env(
            tool="ca_cse_company",
            input={"symbol": r["symbol"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{md.get('symbol') or r['symbol']} {md.get('security_name') or '—'} · "
                                f"{md.get('status') or '—'} · {md.get('sector') or '—'} · "
                                f"{md.get('currency') or '—'} · tier {md.get('tier') if md.get('tier') is not None else '—'}",
                       "url": "https://thecse.com/en/api/webapi/company/?symbol="
                              + r["symbol"] + "&type=listed"}
                      ] if r["found"] else [],
            provider_id="ca_cse", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"endpoint": "https://thecse.com/en/api/webapi/company/",
                                "symbol": r["symbol"]}},
        )
    # —— 0.3.46 SG data.gov.sg open-data platform (dictionary slot: sg_datagovsg after ru_cbr;
    # the ACRA register of record rides the national platform as bulk CSV — no per-company
    # query surface exists, BizFile is a paid wall) ——

    def sg_datagovsg_datasets(self, page=1, *, q=None, agency=None, fmt=None, limit=20,
                              execution=None, no_cache=None):
        """One data.gov.sg catalog page (10 rows), locally filtered. The upstream has
        NO query surface: only ?page= is honoured, everything else is silently
        ignored — --q/--agency/--format are LOCAL over the fetched page's rows, and
        whole-catalog discovery (4,665 datasets across 467 pages) is an explicit page
        walk. Beyond the last page the upstream answers 200 with empty rows and
        zeroed totals — reported honestly, never an error."""
        self._co_only("sg_datagovsg_datasets")
        r = company.sg_datagovsg.catalog_raw(page=page, q=q, agency=agency, fmt=fmt,
                                             limit=limit, cache=self._c._cache,
                                             no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        cen = r["census"]
        if r["beyond_range"]:
            reason = (
                f"page {r['page']} lies beyond the catalog's last page — the "
                "upstream answers 200 with EMPTY rows and ZEROED totals (pages=0, "
                "totalRowCount=0) rather than a 404; walk pages 1..N where N is the "
                "pages value carried on any in-range call (467 at the 2026-11-05 probe)")
        else:
            filters = []
            if q:
                filters.append(f"--q {q!r} (LOCAL contains over name+description)")
            if agency:
                filters.append(f"--agency {agency!r} (LOCAL contains)")
            if fmt:
                filters.append(f"--format {fmt!r} (LOCAL exact, case-folded)")
            fl = ("; " + "; ".join(filters)) if filters else \
                " (no filters — the page as issued, datasetId ascending)"
            reason = (
                f"catalog page {r['page']}: {r['total_matched']} of "
                f"{r['scanned_rows']} rows match{fl}. The upstream exposes NO "
                "query surface — only ?page= is honoured (q/pageSize/agency are "
                "silently ignored, no search route, no single-dataset route), so the "
                "filters above ran locally over this page's rows; the census carries "
                f"the whole-catalog frame ({cen['catalog_total']} datasets across "
                f"{cen['catalog_pages']} pages at the 2026-11-05 probe). Whole-catalog "
                "discovery is an explicit page walk at the polite tier.")
        return self._flat_env(
            tool="sg_datagovsg_datasets",
            input={"page": r["page"], "q": q, "agency": agency, "fmt": fmt,
                   "limit": r["limit_applied"]},
            reason=reason,
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": f"{x['datasetId']} · {str(x.get('name') or '—')[:70]}"
                               + f" · {x.get('managedByAgencyName') or '—'}"
                               + f" · {x.get('format') or '—'}",
                       "url": "https://data.gov.sg/datasets/" + x["datasetId"] + "/view"}
                      for x in r["rows"][:5]],
            provider_id="sg_datagovsg", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"route": "/v2/public/api/datasets",
                                                 "page": r["page"],
                                                 "local_scan": {"q": q, "agency": agency,
                                                                "fmt": fmt}}},
        )

    def sg_datagovsg_dataset_download(self, dataset_id, *, execution=None, no_cache=None):
        """Minted download coordinates for one dataset: initiate → (fallback) a short
        poll walk → the 1-hour S3 signed URL with mint time, expiry and true file
        title parsed out of the signature. The file BODY rides the batch line — the
        SDK stays coordinates-only (the ACRA master alone is 234 MB)."""
        self._co_only("sg_datagovsg_dataset_download")
        r = company.sg_datagovsg.download_raw(dataset_id, cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        via = r["minted_via"]
        if via == "poll":
            reason = (
                f"download coordinates for {r['dataset_id']} — the initiate call "
                "came back without a URL, so the face walked "
                f"{r['census']['poll_rounds']} no-cache poll rounds until the "
                "platform reported DOWNLOAD_SUCCESS; coordinates carry the mint time, "
                "the 1-hour signature window and the true file title parsed from the "
                "minted S3 URL itself")
        else:
            reason = (
                f"download coordinates for {r['dataset_id']} — the platform minted "
                "the S3 signed URL immediately at initiate (both probe sizes did: the "
                "3.2 MB others-UEN file AND the 234 MB ACRA master); the poll channel "
                "exists as fallback only. The signature lives 1 hour "
                f"(minted {r['minted_at']}, dies {r['expires_at']}); the file "
                "title (response-content-disposition filename) rides the URL verbatim. "
                "The file BODY rides the batch line — the SDK is coordinates-only "
                "(the ACRA master file alone is 234 MB); caller guidance for the S3 "
                "hop: HEAD answers 403, plain GET and Range GET answer 200/206 with "
                "Content-Range total. The ACRA register of record (~2.13M entities, "
                "UEN keys) rides this platform as bulk CSV only — master file "
                "d_3f960c10fed6145404ca7b821f263b87, 27 letter volumes, monthly "
                "formation/cessation panels; discover ids via sg_datagovsg_datasets.")
        return self._flat_env(
            tool="sg_datagovsg_dataset_download",
            input={"dataset_id": r["dataset_id"]},
            reason=reason,
            result={k: v for k, v in r.items() if k != "_meta"},
            evidence=[{"quote": f"{r['dataset_id']} · {r['filename'] or '—'}"
                                + f" · expires {r['expires_at']}"
                                + f" · {r['host']}",
                       "url": r["download_url"]}],
            provider_id="sg_datagovsg", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {"route": "/v1/public/api/datasets/"
                                                         f"{r['dataset_id']}/initiate-download",
                                                 "minted_via": via,
                                                 "poll_rounds": r["census"]["poll_rounds"]}},
        )

    # —— 0.3.48 US state-license Socrata twin batch (dictionary slot: tx_tdlr between tr_spk_listed and usaspending,
    # wa_doh between usaspending and vies_vat — US sub-national faces take the state code prefix, ny_open_data precedent) ——
    def tx_tdlr_licenses(self, where=None, *, limit=20, offset=0, order=None,
                         execution=None, no_cache=None):
        """company tx_tdlr_licenses: Texas TDLR All Licenses register (data.texas.gov Socrata
        7358-krk7; where → $where raw SoQL verbatim channel; limit/offset/order mirrored by
        name). 966,778-row corpus, ~40 license types — license_type x license_number registry
        key, business_name/owner_name duality, county, subtype family (AE/REG/CER/OP),
        MM/DD/YYYY expiration column verbatim; TDLR batch-refreshes (~monthly), not daily."""
        self._co_only("tx_tdlr_licenses")
        r = company.tx_tdlr.licenses_raw(where, limit=limit, offset=offset, order=order,
                                         cache=self._c._cache,
                                         no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        if rows:
            reason = (f"TX TDLR license register: {len(rows)} rows returned (from offset={offset}; Socrata echoes no total)"
                      f" — license_type x license_number key (sample {rows[0].get('license_type') or '—'}"
                      f" #{rows[0].get('license_number') or '—'}, {rows[0].get('business_name') or rows[0].get('owner_name') or '—'},"
                      f" subtype {rows[0].get('license_subtype') or '—'}, expires {rows[0].get('license_expiration_date_mmddccyy') or '—'})"
                      f"; corpus 966,778, ~40 types (top: Apprentice Electrician 283,425 / Cosmetology Operator 198,702)"
                      " — TDLR batch-refreshes (~monthly), not daily")
        else:
            reason = ("TX TDLR: 0 rows — the where filter matched nothing or offset is past the end; both are legal "
                      "answers (not errors)")
        ev = [{"quote": f"{x.get('license_type') or '—'} #{x.get('license_number') or '—'} — "
                        f"{x.get('business_name') or x.get('owner_name') or '—'}"
                        f" ({x.get('business_county') or '—'} County, subtype {x.get('license_subtype') or '—'},"
                        f" expires {x.get('license_expiration_date_mmddccyy') or '—'}, CE {x.get('continuing_education_flag') or '—'})",
               "url": "https://data.texas.gov/resource/7358-krk7.json"}
              for x in rows[:3] if (x.get("business_name") or x.get("owner_name"))]
        return self._flat_env(tool="tx_tdlr_licenses",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="tx_tdlr",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    def wa_doh_credentials(self, where=None, *, limit=20, offset=0, order=None,
                           execution=None, no_cache=None):
        """company wa_doh_credentials: Washington DoH Health Care Provider Credential Data
        (data.wa.gov Socrata qxh8-f4bd; where → $where raw SoQL verbatim channel;
        limit/offset/order mirrored by name). 2,468,860-row corpus — credentialnumber hard key
        (registrar grammar 'RN.RN.61687583.MSL'), practitioner names, credentialtype x status,
        three-axis date family; **birthyear column stripped from every row (PII red line —
        birth year + full name stays out of the face; names in a public register are
        collectable, no_brreg roller precedent)**; daily refresh."""
        self._co_only("wa_doh_credentials")
        r = company.wa_doh.credentials_raw(where, limit=limit, offset=offset, order=order,
                                           cache=self._c._cache,
                                           no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        if rows:
            reason = (f"WA DoH credential register: {len(rows)} rows returned (from offset={offset}; Socrata echoes no total)"
                      f" — credentialnumber key (sample {rows[0].get('credentialnumber') or '—'},"
                      f" {rows[0].get('lastname') or '—'}, {rows[0].get('firstname') or '—'};"
                      f" {rows[0].get('credentialtype') or '—'} / {rows[0].get('status') or '—'},"
                      f" expires {rows[0].get('expirationdate') or '—'})"
                      f"; corpus 2,468,860 (top: Registered Nurse License 377,103 / Nursing Assistant "
                      "Registration 296,694 — daily refresh, the count moved +1 past the research probe the same day);"
                      " birthyear stripped from every row (PII red line)")
        else:
            reason = ("WA DoH: 0 rows — the where filter matched nothing or offset is past the end; both are legal "
                      "answers (not errors)")
        ev = [{"quote": f"{x.get('credentialnumber') or '—'} — {x.get('lastname') or '—'}, "
                        f"{x.get('firstname') or '—'} ({x.get('credentialtype') or '—'}, "
                        f"{x.get('status') or '—'}, first issued {x.get('firstissuedate') or '—'})",
               "url": "https://data.wa.gov/resource/qxh8-f4bd.json"}
              for x in rows[:3] if x.get("credentialnumber")]
        return self._flat_env(tool="wa_doh_credentials",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="wa_doh",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    # —— 0.3.49 US city-license Socrata trio (dictionary slots: chi_bacp between ch_zefix_firm_search and
    # co_rues ('_'(0x5F)<'i'), lacity between kz_gbd_ul and no_brreg, nyc_dcwp between no_brreg_roller and
    # nzco ('o'<'y'<'z'); provider stems avoid ISO collisions — 'lacity' not 'la_' (Laos), city faces take
    # the host stem, tx_/wa_ state-axis ruling extended to the city axis) ——
    def chi_bacp_licenses(self, where=None, *, limit=20, offset=0, order=None,
                          execution=None, no_cache=None):
        """company chi_bacp_licenses: Chicago BACP business licenses full history
        (data.cityofchicago.org Socrata r5kz-chrr; where → $where raw SoQL verbatim channel;
        limit/offset/order mirrored by name). 1,210,956-row corpus, 1997→ full history — the
        TWO-LEVEL business key account_number (enterprise across addresses) x site_number
        (address) with license_id per issuance and id = license_number-expiration compact;
        legal_name x DBA duality, license_code/description x business_activity taxonomy,
        six-date lifecycle, license_status lifecycle codes verbatim (AAI/AA/AIN/CAN — no
        guessed variants), Chicago geo stack; payment_date refreshes DAILY."""
        self._co_only("chi_bacp_licenses")
        r = company.chi_bacp.licenses_raw(where, limit=limit, offset=offset, order=order,
                                          cache=self._c._cache,
                                          no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        if rows:
            reason = (f"Chicago BACP license register: {len(rows)} rows returned (from offset={offset}; Socrata echoes no total)"
                      f" — account x site two-level key (sample acct {rows[0].get('account_number') or '—'}"
                      f" / site {rows[0].get('site_number') or '—'}, license_id {rows[0].get('license_id') or '—'},"
                      f" {rows[0].get('license_description') or '—'}, {rows[0].get('application_type') or '—'}"
                      f" / {rows[0].get('license_status') or '—'})"
                      f"; corpus 1,210,956 full history 1997→, payment_date refreshes daily"
                      " (probe rows carry 2026-11-03 payments)")
        else:
            reason = ("Chicago BACP: 0 rows — the where filter matched nothing or offset is past the end; both are legal "
                      "answers (not errors)")
        ev = [{"quote": f"{x.get('license_description') or '—'} — {x.get('legal_name') or '—'}"
                        f" (DBA {x.get('doing_business_as_name') or '—'}, acct {x.get('account_number') or '—'}"
                        f"/site {x.get('site_number') or '—'}, {x.get('application_type') or '—'},"
                        f" {x.get('license_status') or '—'}, expires {(x.get('expiration_date') or '—')[:10]})",
               "url": "https://data.cityofchicago.org/resource/r5kz-chrr.json"}
              for x in rows[:3] if (x.get("legal_name") or x.get("doing_business_as_name"))]
        return self._flat_env(tool="chi_bacp_licenses",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="chi_bacp",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    def lacity_registrations(self, where=None, *, limit=20, offset=0, order=None,
                             execution=None, no_cache=None):
        """company lacity_registrations: LA Office of Finance active-business tax registrations
        (data.lacity.org Socrata 6rrh-rzua; where → $where raw SoQL verbatim channel;
        limit/offset/order mirrored by name). 632,799-row register — location_account compact
        key (account-location-segment '0000000108-0001-3', the only join key), naics +
        primary_naics_description (the batch's only industry-code face), mailing_* family
        present-only per row, council_district, location_start_date (future dates = advance
        registrations); NOT a license book — business-tax register; provider stem 'lacity'
        not 'la_' (ISO Laos)."""
        self._co_only("lacity_registrations")
        r = company.lacity.registrations_raw(where, limit=limit, offset=offset, order=order,
                                             cache=self._c._cache,
                                             no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        if rows:
            reason = (f"LA active-business tax register: {len(rows)} rows returned (from offset={offset}; Socrata echoes no total)"
                      f" — location_account key (sample {rows[0].get('location_account') or '—'},"
                      f" {rows[0].get('business_name') or '—'}, NAICS {rows[0].get('naics') or '—'}"
                      f" {rows[0].get('primary_naics_description') or '—'}, at location since"
                      f" {(rows[0].get('location_start_date') or '—')[:10]})"
                      f"; corpus 632,799 — the only NAICS face of the three-city batch"
                      " (Chicago/NYC carry license taxonomies)")
        else:
            reason = ("LA Office of Finance: 0 rows — the where filter matched nothing or offset is past the end; both "
                      "are legal answers (not errors)")
        ev = [{"quote": f"{x.get('location_account') or '—'} — {x.get('business_name') or '—'}"
                        f" (NAICS {x.get('naics') or '—'} {x.get('primary_naics_description') or '—'},"
                        f" council district {x.get('council_district') or '—'},"
                        f" since {(x.get('location_start_date') or '—')[:10]})",
               "url": "https://data.lacity.org/resource/6rrh-rzua.json"}
              for x in rows[:3] if x.get("location_account")]
        return self._flat_env(tool="lacity_registrations",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="lacity",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    def nyc_dcwp_licenses(self, where=None, *, limit=20, offset=0, order=None,
                          execution=None, no_cache=None):
        """company nyc_dcwp_licenses: NYC DCWP license register (data.cityofnewyork.us Socrata
        w7w3-xahh; where → $where raw SoQL verbatim channel; limit/offset/order mirrored by
        name). 72,452-row corpus — applications+licenses book, NOT the padlocked
        licensed-locations table; license_nbr = number+agency suffix ('0016371-DCA') over
        business_unique_id ('BA-1322274-2022' enterprise anchor), business_category x
        license_type (Premises/Individual), Surrendered rows stay (history not just actives),
        split address family with borough column, NYC planning geo stack (community_board /
        council_district / bin / bbl / nta / census); ~2.5-month refresh lag."""
        self._co_only("nyc_dcwp_licenses")
        r = company.nyc_dcwp.licenses_raw(where, limit=limit, offset=offset, order=order,
                                          cache=self._c._cache,
                                          no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        if rows:
            reason = (f"NYC DCWP license register: {len(rows)} rows returned (from offset={offset}; Socrata echoes no total)"
                      f" — license_nbr key (sample {rows[0].get('license_nbr') or '—'},"
                      f" {rows[0].get('business_name') or '—'} [{rows[0].get('business_unique_id') or '—'}],"
                      f" {rows[0].get('business_category') or '—'} / {rows[0].get('license_type') or '—'},"
                      f" {rows[0].get('license_status') or '—'},"
                      f" expires {(rows[0].get('lic_expir_dd') or '—')[:10]})"
                      f"; corpus 72,452 — Surrendered rows stay (history not just actives);"
                      " ~2.5-month refresh lag")
        else:
            reason = ("NYC DCWP: 0 rows — the where filter matched nothing or offset is past the end; both are legal "
                      "answers (not errors)")
        ev = [{"quote": f"{x.get('license_nbr') or '—'} — {x.get('business_name') or '—'}"
                        f" [{x.get('business_unique_id') or '—'}] ({x.get('business_category') or '—'},"
                        f" {x.get('license_status') or '—'}, expires {(x.get('lic_expir_dd') or '—')[:10]},"
                        f" {x.get('address_borough') or '—'})",
               "url": "https://data.cityofnewyork.us/resource/w7w3-xahh.json"}
              for x in rows[:3] if x.get("license_nbr")]
        return self._flat_env(tool="nyc_dcwp_licenses",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="nyc_dcwp",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})

    # —— 0.3.56 Batch B major-economy axis I (DE/JP/KR existing-jurisdiction deepening — de_register live-search face + jplatpat hash-gate three-face +
    # kr_kipris patent flagship face; dictionary slot alphabetical: de_inso < de_register < edgar_*; jp_fsa < jp_jplatpat < kr_*;
    # kr_hometax < kr_kipris) ——

    def de_register_search(self, name=None, *, exact=True, q=None, offset=0,
                           execution=None, no_cache=None):
        """company de_register_search: German Unternehmensregister live register search
        (unternehmensregister.de three-hop keyless: /api/search-token → RSC /de/suche →
        embedded JSON). ~ DE the live company register (the offeneregister mirror is frozen
        at 2018); name = the exact channel (companyName + ExactMatch=true — best-effort:
        the same query returned Siemens AG HRB 6684 on 11-02 and Siemens Energy AG
        HRB 252581 on 11-12), q = the fuzzy companySearchTerm channel. Rows are the
        companyDto register entries (euid "DED2601V.HRB6684" = THE EU interconnection key;
        register_court_code+register_number is the compound join key — an HRB number is
        only unique per court); the company's publication event stream (announcements with
        free-PDF encrypted_payload) rides alongside in result.publications. 60 rows/page,
        from=<offset> paging, 1,000-hit query cap; deletedFlag is the struck-off flag,
        lastUpdate ticks weekly. The search hop is never cached (the token rides the URL —
        the mx_cnv ruling); the token itself is cached 45min (upstream validity 1h)."""
        self._co_only("de_register_search")
        r = company.de_register.search_raw(name, exact=exact, q=q, offset=offset,
                                           cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            top = rows[0]
            reason = (f"Unternehmensregister: {len(rows)} register entries from row {result['current_page']}"
                      f" (page {result['current_page']} of {result['total_pages']})"
                      + (" — 1,000-hit cap reached" if result.get("has_reached_results_limit") else "")
                      + f" — sample {top.get('name') or '—'} · {top.get('euid') or '—'}"
                      f" ({top.get('register_court_code') or '—'} {top.get('register_type') or '—'}"
                      f" {top.get('registerNumber') or '—'}, {top.get('state_name') or '—'})"
                      + (" · struck-off (deletedFlag)" if top.get("deletedFlag") else "")
                      + f" · lastUpdate {top.get('lastUpdate') or '—'}"
                      + (f" · {len(result['publications'])} publication events ride alongside"
                         if result["publications"] else "")
                      + " — euid is the strong join key; HRB number needs its court code")
        else:
            reason = ("Unternehmensregister: zero register entries — a legitimate narrow query "
                      "(exact matching is best-effort: try the fuzzy q channel), or an offset past the end")
        return self._flat_env(
            tool="de_register_search",
            input={"name": name, "exact": exact, "q": q, "offset": offset},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('name') or '—'} · {x.get('euid') or '—'} ·"
                                f" {(x.get('register_court_code') or '—')} {(x.get('registerNumber') or '—')}"
                                f" · {'struck-off' if x.get('deletedFlag') else (x.get('lastUpdate') or '—')}",
                       "url": "https://www.unternehmensregister.de/"}
                      for x in rows[:5]],
            provider_id="de_register", metas=[r["_meta"]],
            query={"source": "raw", "upstream": result["params"]},
        )

    # —— 0.3.73 DE Deutsche Börse Xetra/Frankfurt (E15; de_xetra — the T7
    # tradable-instruments universe + the Newsboard event stream on
    # cashmarket.deutsche-boerse.com, the former xetra.com host) ——

    def de_xetra_instruments(self, *, venue="xetra", instrument_type=None, pag=None,
                             isin=None, limit=None, execution=None, no_cache=None):
        """company de_xetra_instruments: Deutsche Börse T7 tradable-instruments
        master (DE — 153 columns verbatim, ISIN+WKN on every row). venue=xetra ≈5.5k
        rows (ETF/CS/ETN/ETC…); venue=frankfurt = the bond-heavy ~56k variant
        (the CSV hangs under the Xetra section at boersefrankfurt — the
        /Tradable-Instruments-Frankfurt/Downloads URL is a 404 decoy). The CSV
        link re-resolves from the landing page every fetch (blob hashes
        version on upload); Date Last Update rides every response. Row counts
        drift daily — snapshot counts, never pinned."""
        self._co_only("de_xetra_instruments")
        r = company.de_xetra.instruments(venue=venue, instrument_type=instrument_type,
                                         pag=pag, isin=isin, limit=limit,
                                         cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        base = (f"Deutsche Börse T7 {result['venue']} master"
                + (f", Date Last Update {result['date_last_update']}" if result.get("date_last_update") else "")
                + (f", local Instrument Type={str(instrument_type).upper()} filter" if instrument_type else "")
                + (f", PAG {pag}" if pag else ""))
        if rows:
            top = rows[0]
            reason = (base + f": {result['row_count']:,} rows — {top.get('Instrument')} · "
                      f"{top.get('ISIN')} · WKN {top.get('WKN')} · {top.get('Instrument Type')}")
        else:
            reason = base + ": zero rows — a filter with no matches is a legitimate answer (types: ETF/CS/ETN/ETC…; PAG codes are AST0-style)"
        landing = ("https://www.cashmarket.deutsche-boerse.com/cash-en/trading/Tradable-Instruments-Xetra/Downloads"
                   if result["venue"] == "xetra" else
                   "https://www.cashmarket.deutsche-boerse.com/cash-en/trading/Tradable-Instruments-Xetra/boersefrankfurt")
        return self._flat_env(
            tool="de_xetra_instruments",
            input={"venue": result["venue"], "instrument_type": instrument_type,
                   "pag": pag, "isin": isin, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('Instrument')} · {x.get('ISIN')} · WKN {x.get('WKN')} · "
                                f"{x.get('Instrument Type')} · Mnemonic {x.get('Mnemonic')}",
                       "url": landing}
                      for x in rows[:5]],
            provider_id="de_xetra", metas=[r["_meta"]],
            query={"source": "raw", "upstream": dict(r["params"])},
        )

    def de_xetra_newsboard(self, *, venue=None, event_type=None, isin=None,
                           limit=None, execution=None, no_cache=None):
        """company de_xetra_newsboard: Xetra/Frankfurt Newsboard event stream
        (DE — RSS rolling window of the latest 100 notices, ~15h; suspension/
        resumption (Aussetzung/Wiederaufnahme), dividend/interest, delisting).
        Titles carry the venue prefix (XETR:/XFRA:), the event class and the
        ISIN or mnemonic; venue/event-type/isin filter locally. Hourly polling
        is the no-loss cadence — full history via de_xetra_newsboard_search."""
        self._co_only("de_xetra_newsboard")
        r = company.de_xetra.newsboard(venue=venue, event_type=event_type, isin=isin,
                                       limit=limit, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        base = ("Xetra/Frankfurt Newsboard rolling window (latest 100 notices)"
                + (f", local venue={str(venue).upper()} filter" if venue else "")
                + (f", local event~{str(event_type).upper()} filter" if event_type else "")
                + (f", ISIN {isin}" if isin else ""))
        if rows:
            reason = base + f": {result['item_count']} matching rows — newest {rows[0]['pub_date']} · {rows[0]['event'][:70]}"
        else:
            reason = base + ": zero matching rows — the 100-item window ages out in ~15h (suspension bursts age out fastest); query de_xetra_newsboard_search for history"
        return self._flat_env(
            tool="de_xetra_newsboard",
            input={"venue": str(venue).upper() if venue else None,
                   "event_type": str(event_type).upper() if event_type else None,
                   "isin": isin, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('pub_date')} · {x.get('venue')}: {x.get('event', '')[:80]}",
                       "url": "https://www.cashmarket.deutsche-boerse.com/cash-en/Stay-Informed/newsroom/Xetra-Frankfurt-Newsboard/4091644!rss"}
                      for x in rows[:5]],
            provider_id="de_xetra", metas=[r["_meta"]],
            query={"source": "raw", "upstream": dict(r["params"])},
        )

    def de_xetra_newsboard_search(self, *, query, page=1, limit=None,
                                  execution=None, no_cache=None):
        """company de_xetra_newsboard_search: Newsboard full-history search
        (DE — every notice ever posted; delisting notices back to the 2020
        number block ride ISINs in the path). Query by ISIN, mnemonic, or an
        event word (Aussetzung/Suspension, Wiederaufnahme/Resumption,
        delisting, DIVIDEND…); 100 hits/page, pageNum rides statelessly."""
        self._co_only("de_xetra_newsboard_search")
        r = company.de_xetra.newsboard_search(query=query, page=page, limit=limit,
                                              cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            reason = (f"Newsboard history \"{result['query']}\" page {result['page']}: "
                      f"{result['row_count']} rows — newest {rows[0]['date']} · {(rows[0]['text'] or '')[:70]}")
        else:
            reason = (f"Newsboard history \"{result['query']}\" page {result['page']}: zero rows — "
                      "try the German event word (Aussetzung) or a bare ISIN")
        return self._flat_env(
            tool="de_xetra_newsboard_search",
            input={"query": result["query"], "page": result["page"], "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('date')} · {(x.get('text') or '')[:90]}",
                       "url": ("https://www.cashmarket.deutsche-boerse.com/cash-en/Stay-Informed/"
                               f"newsroom/Xetra-Frankfurt-Newsboard/4091644!search?query={result['query']}"
                               f"&pageNum={result['page']}&hitsPerPage=100")}
                      for x in rows[:5]],
            provider_id="de_xetra", metas=[r["_meta"]],
            query={"source": "raw", "upstream": dict(r["params"])},
        )

    def _jp_jplatpat_face(self, tool, face, q, year, year_sign, no_cache=None):
        r = getattr(company.jp_jplatpat, face + "_search_raw")(
            q, year=year, year_sign=year_sign,
            cache=self._c._cache,
            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        holder_key = "APPN_RIGHT_HOLDER_HOLDER" if face == "trademark" else "APPN_RIGHT_HOLDER"
        if rows:
            top = rows[0]
            holders = top.get(holder_key) or []
            an = top.get("APP_NUM_DISP") or top.get("APP_NUM") or top.get("DOCU_NUM") or "—"
            reason = (f"J-PlatPat {face}: {result['total']:,} hits for \"{result['params']['q']}\""
                      + (f" ({result['params']['year_sign']}{result['params']['year']} slice)"
                         if result["params"]["year"] else "")
                      + f", {len(rows)} rows returned"
                      + (f" — auto-narrowed from {result['auto_narrow']['prev_count']:,}"
                         " (the 3,000 per-call cap; slice by year/facet to walk deeper)"
                         if result.get("auto_narrow") else "")
                      + f" — sample {an} · {(holders[0] if holders else '—')}"
                      + " — holder names are NAME-level joins (no 法人番号; align NTA bulk for a hard key)")
        else:
            reason = (f"J-PlatPat {face}: zero rows for \"{result['params']['q']}\" — a legitimate narrow "
                      "query (katakana must ride full-width), or the C90003-E 3,000-cap wall without "
                      "auto-narrow (slice by year)")
        return self._flat_env(
            tool=tool,
            input={"q": result["params"]["q"], "year": result["params"]["year"],
                   "year_sign": result["params"]["year_sign"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('APP_NUM_DISP') or x.get('APP_NUM') or x.get('DOCU_NUM') or '—'} ·"
                                f" {'; '.join(x.get(holder_key) or []) or '—'} ·"
                                f" {(x.get('APP_DATE_INTL_REG_DATE_AFT_SPC_DATE') or x.get('APP_DATE') or '—')}",
                       "url": "https://www.j-platpat.inpit.go.jp/"}
                      for x in rows[:5]],
            provider_id="jp_jplatpat", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def jp_trademark_search(self, q=None, *, year=None, year_sign=None,
                            execution=None, no_cache=None):
        """company jp_trademark_search: J-PlatPat trademark search (JPO official portal,
        wst0303 JSON face — the client-computed hash cookie gate broken zero-credential:
        Z=sha256(U+L+ECKY) for ECRL=105). 41-key rows with the holder array
        APPN_RIGHT_HOLDER_HOLDER (name-level join), Nice PER_DIVISION facets, status, dates,
        app/reg numbers; the register reaches 1953 (full history, live). q = keyword —
        holder names ride the same simple-keyword face (no dedicated applicant endpoint);
        katakana must be FULL-WIDTH, latin self-normalizes. year + year_sign ('='|'>='|'<='|'>')
        slice PER_APP_Y_BY — the SIGN is mandatory (a bare year is silently ignored);
        single-call cap 3,000 with auto-narrow reporting the pre-narrow total; 4s/request
        politeness (RSLT_CD=8 is the captcha — the face raises rather than retries)."""
        self._co_only("jp_trademark_search")
        return self._jp_jplatpat_face("jp_trademark_search", "trademark", q, year, year_sign,
                                      no_cache=no_cache)

    def jp_patent_search(self, q=None, *, year=None, year_sign=None,
                         execution=None, no_cache=None):
        """company jp_patent_search: J-PlatPat patent·utility-model search (wsp0103; 37-key
        rows, holder APPN_RIGHT_HOLDER, FI facets, STAGE/DETAILED_EVENT status fields, app/
        publication/grant numbers — 特願2025-161044 display forms verbatim). year slices
        KNOWN_Y_BY (公知年). Same hash-gate/key/cap laws as jp_trademark_search."""
        self._co_only("jp_patent_search")
        return self._jp_jplatpat_face("jp_patent_search", "patent", q, year, year_sign,
                                      no_cache=no_cache)

    def jp_design_search(self, q=None, *, year=None, year_sign=None,
                         execution=None, no_cache=None):
        """company jp_design_search: J-PlatPat design (意匠) search (wsd0203; 27-key rows,
        holder APPN_RIGHT_HOLDER, DESIGN_GOODS, JPN design classifications, international
        registration numbers DM/232315-002 verbatim). year slices PER_APP_Y_BY. Same
        hash-gate/key/cap laws as jp_trademark_search."""
        self._co_only("jp_design_search")
        return self._jp_jplatpat_face("jp_design_search", "design", q, year, year_sign,
                                      no_cache=no_cache)

    def kr_kipris_patents(self, q=None, *, page=1, page_size=20,
                          execution=None, no_cache=None):
        """company kr_kipris_patents: KIPRIS domestic patent·utility-model search (KIPO portal
        kpat/resulta.do, keyless form-POST — a JSON body answers the empty "98" code, so the
        face rides the verified form channel; queryText=expression=historyQuery all carry the
        query). THE KR IP pillar: 84-key rows at up to 2,000/page — and the row field APC is
        the 사업자등록번호 (business registration number), the IP family's second hard
        corporate key after AU's ABN (pipe-separated when multiple). q = keyword or the
        upstream date DSL verbatim (OPD=[YYYYMMDD~YYYYMMDD] publication / PD application /
        RPD registration). resultCode "98" = ZERO-HIT query mapped to rows=[] + zero_hit=True —
        weekend/holiday dates and unindexed date axes answer 98, NOT an error (a batch walker
        must not treat 98 as a failure); "99" = the 255-page wall. Empty cells arrive as the
        literal "&nbsp;" — verbatim. True pagination (page1∩page2 = 0 measured)."""
        self._co_only("kr_kipris_patents")
        r = company.kr_kipris.search_raw(q, page=page, page_size=page_size,
                                         cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            top = rows[0]
            reason = (f"KIPRIS: {result['total']:,} domestic patents·utility models hit"
                      f" \"{result['params']['q']}\", {len(rows)} rows from page {result['params']['page']}"
                      f" — sample {top.get('AN') or '—'} · {(top.get('AP') or '—')} [APC"
                      f" {top.get('APC') or '—'}]"
                      f" · {(top.get('TL') or '—')[:60]}"
                      + (" — APC (사업자등록번호) is the hard join key (pipe-separated when multiple)"
                         if top.get("APC") else " — this row carries no APC (name-level only)"))
        elif result.get("zero_hit"):
            reason = (f"KIPRIS: zero hits for \"{result['params']['q']}\" (resultCode 98 = the upstream's "
                      "zero-hit answer — weekend/holiday publication dates and lagging date axes are "
                      "legitimate empties, not errors)")
        else:
            reason = (f"KIPRIS: zero rows for \"{result['params']['q']}\"")
        return self._flat_env(
            tool="kr_kipris_patents",
            input={"q": result["params"]["q"], "page": result["params"]["page"],
                   "page_size": result["params"]["page_size"]},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('AN') or '—'} · {(x.get('AP') or '—')} [APC {x.get('APC') or '—'}]"
                                f" · {(x.get('TL') or '—')[:60]} · {(x.get('IPC') or '—')}",
                       "url": "https://www.kipris.or.kr/khome/search/searchResult.do?tab=patent"}
                      for x in rows[:5]],
            provider_id="kr_kipris", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # —— 0.3.73 KR KRX Global (E15; kr_krx — the OPEN portal of the
    # three-sister gate family: data.krx=member wall, kind.krx=WAF,
    # global.krx=robots Allow:/) ——

    def kr_krx_listed(self, *, board="all", industry=None, limit=None,
                      execution=None, no_cache=None):
        """company kr_krx_listed: KRX Global listed-company universe (KR — the
        OTP double-step grid, one-shot ~2,769 rows × 10 cols: isu_cd /
        eng_cor_nm / std_ind_cd + ind_nm industry / lst_stk_vl listed shares /
        cpt capital / par_pr par value). board picks market_gubun
        (all/kospi/kosdaq/konex — All reconciles with the board splits);
        industry filters std_ind_cd by PREFIX (the 2+2+2 six-digit hierarchy:
        '07' wholesale / '0746' / '074604' all legal). Numbers keep verbatim
        comma strings + *_num int companions."""
        self._co_only("kr_krx_listed")
        r = company.kr_krx.listed(board=board, industry=industry, limit=limit,
                                  cache=self._c._cache,
                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        base = (f"KRX Global listed universe, board={result['board']}"
                + (f", local std_ind_cd~{industry} prefix filter" if industry else ""))
        if rows:
            top = rows[0]
            reason = (base + f": {result['total_count']:,} total · {result['row_count']:,} rows — "
                      f"{top.get('isu_cd')} {top.get('eng_cor_nm')} · {top.get('ind_nm')} · "
                      f"capital {top.get('cpt_num'):,} {top.get('iso_cd')}")
        else:
            reason = base + ": zero rows — the board/industry combination has no listings (std_ind_cd prefixes: 2/4/6 digits)"
        return self._flat_env(
            tool="kr_krx_listed",
            input={"board": result["board"], "industry": industry, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('isu_cd')} {x.get('eng_cor_nm')} · {x.get('ind_nm')} · "
                                f"std_ind_cd {x.get('std_ind_cd')} · capital {x.get('cpt')} {x.get('iso_cd')}",
                       "url": "https://global.krx.co.kr/contents/GLB/03/0308/0308010000/GLB0308010000.jsp"}
                      for x in rows[:5]],
            provider_id="kr_krx", metas=[r["_meta"]],
            query={"source": "raw", "upstream": dict(r["params"])},
        )

    def kr_krx_indices(self, *, execution=None, no_cache=None):
        """company kr_krx_indices: KRX main-index snapshot (KR — the free-OTP
        family: GET main.jspx?bld=index_list, no OTP dance; KOSPI / KOSDAQ /
        KOSPI 200 / KRX 300 / Korea Value-up — the set drifts). clsprc_idx
        close / cmpr_idx change / cmpr_rt rate keeps upstream's raw
        scientific-notation string verbatim; updown carries the direction."""
        self._co_only("kr_krx_indices")
        r = company.kr_krx.indices(cache=self._c._cache,
                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        if rows:
            names = " / ".join(str(x.get("idx_nm")) for x in rows[:4])
            top = rows[0]
            reason = (f"KRX main indices: {result['row_count']} indices — {names}"
                      + (f" — {top.get('idx_nm')} {top.get('clsprc_idx')} ({top.get('updown')})" if top else ""))
        else:
            reason = "KRX main indices: zero rows — the free-OTP family may have moved; re-probe"
        return self._flat_env(
            tool="kr_krx_indices",
            input={},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('idx_nm')} · close {x.get('clsprc_idx')} · change {x.get('cmpr_idx')} · {x.get('updown')}",
                       "url": "https://global.krx.co.kr/main/main.jsp"}
                      for x in rows[:5]],
            provider_id="kr_krx", metas=[r["_meta"]],
            query={"source": "raw", "upstream": dict(r["params"])},
        )

    # ===================== 0.3.60 batch E2 — BNDES financing operations (BR) =====================

    def br_bndes_financiamento(self, name=None, *, uf=None, natureza=None, ano=None,
                               municipio=None, rows=20, start=0, facet=False,
                               execution=None, no_cache=None):
        """company br_bndes_financiamento: BNDES financing operations (the "Operações" gateway,
        gateway.apis.bndes.gov.br — the keyless Solr gateway over the CNPJ-contracted
        operations). name = the CLIENT NAME (the query runs over the client-name index; the
        wildcard enumeration is refused upstream with 403); uf / natureza / ano / municipio are
        the upstream fq filters (server-side); facet = the classic facet form (facet=true&
        facet.field=…).
        LIVE LAWS (measured 2026-11-13): the gateway's Tomcat REJECTS the characters that are
        invalid in an RFC 3986 request target (a raw json.facet body answers 400 "Invalid
        character found in the request target", and so does an fq with raw parentheses/quotes —
        the transport percent-encodes the values and the upstream decodes them correctly); the
        CLIENT's CNPJ is MASKED in the index (documentoCliente = "XXXXXXXXX00146", only the last
        five digits), so the join key onto a company register is the client NAME plus the
        uf/municipio pair — while the financing agent's CNPJ (cnpjAgenteFinanceiro) is NOT
        masked; the wildcard / *:* enumeration is refused, so a named term is always required.
        Rows: the beneficiary (cliente), the masked CNPJ, the financing agent + its CNPJ, the
        client nature (PRIVADA / PÚBLICA DIRETA / PÚBLICA INDIRETA), the state and municipality,
        the contract/disbursed values, the interest rate, the instrument and product, the
        supported sector and the CNAE."""
        self._co_only("br_bndes_financiamento")
        r = company.br_bndes.operations_raw(name, uf=uf, natureza=natureza, ano=ano,
                                             municipio=municipio, rows=rows, start=start,
                                             facet=facet, cache=self._c._cache,
                                             no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows_out = result["rows"]
        p = result["params"]
        if rows_out:
            top = rows_out[0]
            reason = (f"BNDES financing operations: {result['total']} operations for "
                      f"\"{p.get('q')}\", {len(rows_out)} rows returned"
                      + (f" (uf {p.get('uf')})" if p.get("uf") else "")
                      + (f" (year {p.get('ano')})" if p.get("ano") else "")
                      + f" — sample {top.get('client') or '—'}"
                      + f" · {top.get('client_nature') or '—'}"
                      + f" · {top.get('uf') or '—'}/{top.get('municipality') or '—'}"
                      + f" · contracted {top.get('contract_value') or '—'}"
                      + f" · disbursed {top.get('disbursed_value') or '—'}"
                      + " — the client's CNPJ is masked upstream; the name + uf/municipio pair is "
                        "the join key (the financing agent's CNPJ is not masked)")
        else:
            reason = (f"BNDES financing operations: zero operations for \"{p.get('q')}\""
                      + (f" under uf={p.get('uf')}" if p.get("uf") else "")
                      + " (an empty result is a legitimate answer — the client has no BNDES "
                        "contracted operation)")
        return self._flat_env(
            tool="br_bndes_financiamento",
            input={"name": p.get("q"), "uf": p.get("uf"), "natureza": p.get("natureza"),
                   "ano": p.get("ano"), "municipio": p.get("municipio"),
                   "rows": p.get("rows"), "start": p.get("start")},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('client') or '—'} · {x.get('uf') or '—'}/"
                                f"{x.get('municipality') or '—'} · {x.get('year') or '—'}"
                                + f" · contracted {x.get('contract_value') or '—'}"
                                + f" · disbursed {x.get('disbursed_value') or '—'}"
                                + (f" · {x.get('sector') or '—'}" if x.get("sector") else ""),
                       "url": "https://gateway.apis.bndes.gov.br/operacoes/web/select?q="
                              + str(p.get("q") or "")}
                      for x in rows_out[:5]],
            provider_id="br_bndes", metas=[r["_meta"]],
            query={"source": "raw", "upstream": p},
        )

    # ===================== 0.3.70 batch E12 — listed universes AT/AU + HKEX deep (5 faces) =====================

    def at_wiener_borse_listed(self, *, segment="all", code=None, isin=None, name=None,
                               execution=None, no_cache=None):
        """company at_wiener_borse_listed: the Wiener Börse listed-equity universe (AT — prime
        47 / standard ~26 issuers probe day, the server-rendered wienerborse.at segment tables).
        segment all|prime|standard; --isin exact (the company-page slug carries the only
        per-row structured id), --name substring, --code a courtesy alias (ISIN tail or name
        head — the table quotes carry no ticker column). SPAN-STACK LAW: stacked cells (diff
        %+abs, date+time, bid/ask price+volume) split on element boundaries; GERMAN NUMBER LAW:
        verbatim strings ride every row, parsed floats ride *_num (Mio.×1e6 / Mrd.×1e9)."""
        self._co_only("at_wiener_borse_listed")
        r = company.at_wiener.listed(segment=segment, code=code, isin=isin, name=name,
                                     cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        m = r["_meta"]
        metas = m if isinstance(m, list) else [m]
        rows = r["rows"]
        result = {k: x for k, x in r.items() if k != "_meta"}
        if rows:
            top = rows[0]
            reason = (f"Wiener Börse {'+'.join(r['segments'])} segments: {r['total']} issuers — "
                      f"sample {top['name']} ({top['isin']}) · {top['price'] or '—'} EUR"
                      + (f" · mkt cap {top['market_cap']}" if top.get("market_cap") else "")
                      + " — German number shapes verbatim, *_num the parsed companions")
        else:
            reason = (f"Wiener Börse {'+'.join(r['segments'])} segments: zero issuers match "
                      f"(isin={isin or '—'}, name={name or '—'}, code={code or '—'} — an empty "
                      "answer is a legitimate miss, not an error)")
        return self._flat_env(
            tool="at_wiener_borse_listed",
            input={"segment": segment, "code": code, "isin": isin, "name": name},
            reason=reason, result=result,
            evidence=[{"quote": f"{x['name']} ({x['isin']}) · {x['price'] or '—'}"
                                + (f" · {x['diff_pct'] or '—'}" if x.get("diff_pct") else "")
                                + (f" · mkt cap {x['market_cap']}" if x.get("market_cap") else ""),
                       "url": f"https://www.wienerborse.at/aktien-{x['segment']}-market/"}
                      for x in rows[:5]],
            provider_id="at_wiener", metas=metas,
            query={"source": "raw",
                   "upstream": {"segments": r["segments"],
                                "pages": [mm.get("url") for mm in metas if mm.get("url")]}},
        )

    def au_asx_listed(self, *, code=None, name=None, gics=None, limit=None,
                      execution=None, no_cache=None):
        """company au_asx_listed: the ASX listed-companies directory (AU — 2,060 rows probe day,
        the exchange's own ASXListedCompanies.csv). THREE-PART shape: banner as-at anchor / blank
        / header row. GICS rides the 27-group closed set ("Not Applic" and "Class Pend" are legal
        values, not dirty data). --code exact (BHP), --name substring, --gics substring
        ("Materials"); --limit slices the display."""
        self._co_only("au_asx_listed")
        r = company.au_asx.listed(code=code, name=name, gics=gics, limit=limit,
                                  cache=self._c._cache,
                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        result = {k: x for k, x in r.items() if k != "_meta"}
        if rows:
            top = rows[0]
            reason = (f"ASX listed companies as at {r['as_at'] or '—'}: {r['total']} rows match — "
                      f"sample {top['company_name']} [{top['asx_code']}] · "
                      f"{top['gics_industry_group'] or '—'} (GICS industry-group level)")
        else:
            reason = (f"ASX listed companies as at {r['as_at'] or '—'}: zero rows match "
                      f"(code={code or '—'}, name={name or '—'}, gics={gics or '—'} — an empty "
                      "answer is a legitimate miss, not an error)")
        return self._flat_env(
            tool="au_asx_listed",
            input={"code": code, "name": name, "gics": gics, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x['company_name']} [{x['asx_code']}] · "
                                f"{x['gics_industry_group'] or '—'}",
                       "url": "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"}
                      for x in rows[:5]],
            provider_id="au_asx", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"file": "https://www.asx.com.au/asx/research/ASXListedCompanies.csv",
                                "as_at": r["as_at"]}},
        )

    def hk_hkex_securities(self, *, code=None, name=None, category=None, sub_category=None,
                           limit=None, execution=None, no_cache=None):
        """company hk_hkex_securities: the HKEX listed-securities universe (HK — the
        ListOfSecurities.xlsx: 17,336 rows probe day — 2,812 equities but ALSO 6,908 derivative
        warrants and 5,830 CBBC, so --category Equity is the working shape). 18 columns verbatim
        (column P is the multiline Spread Table legend, rows carry part codes 1/3/5/4/6; column R
        carries the paired RMB counter). --code exact (leading zeros optional both ways),
        --name substring, --category/--sub-category exact, --limit slices the display."""
        self._co_only("hk_hkex_securities")
        r = company.hk_hkex.securities(code=code, name=name, category=category,
                                       sub_category=sub_category, limit=limit,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        result = {k: x for k, x in r.items() if k != "_meta"}
        if rows:
            top = rows[0]
            reason = (f"HKEX List of Securities as at {r['as_at'] or '—'}: {r['total']} rows match "
                      f"— sample {top['stock_code']} {top['name'] or '—'} · "
                      f"{top['category'] or '—'}/{top['sub_category'] or '—'}"
                      + (f" · ISIN {top['isin']}" if top.get("isin") else "")
                      + (" — the universe dwarfs the equities; --category Equity is the working "
                         "shape" if not category else ""))
        else:
            reason = (f"HKEX List of Securities as at {r['as_at'] or '—'}: zero rows match "
                      f"(code={code or '—'}, name={name or '—'}, category={category or '—'}, "
                      f"sub_category={sub_category or '—'} — an empty answer is a legitimate miss)")
        return self._flat_env(
            tool="hk_hkex_securities",
            input={"code": code, "name": name, "category": category,
                   "sub_category": sub_category, "limit": limit},
            reason=reason, result=result,
            evidence=[{"quote": f"{x['stock_code'] or '—'} {x['name'] or '—'} · "
                                f"{x['category'] or '—'}/{x['sub_category'] or '—'}"
                                + (f" · ISIN {x['isin']}" if x.get("isin") else "")
                                + (f" · RMB counter {x['rmb_counter']}" if x.get("rmb_counter") else ""),
                       "url": "https://www.hkex.com.hk/eng/services/trading/securities/"
                              "securitieslists/ListOfSecurities.xlsx"}
                      for x in rows[:5]],
            provider_id="hk_hkex", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"file": "https://www.hkex.com.hk/eng/services/trading/securities/"
                                        "securitieslists/ListOfSecurities.xlsx",
                                "as_at": r["as_at"]}},
        )
    # —— 0.3.71 E13 HKEX DI disclosure-of-interests (dictionary slot: hk_hkex_securities <
    # hk_hkexdi_{corp_list,form,ir_summaries} < hk_hkexnews_document — '_'(0x5F)<'d'<'n';
    # di.hkex.com.hk, the SFO Part XV register — second host under the hkex deep-dive ruling) ——

    def hk_hkexdi_corp_list(self, *, stock_code, list_code="ns", from_date=None,
                            to_date=None, pg=1, execution=None, no_cache=None):
        """company hk_hkexdi_corp_list: one HK listed corporation's DI notices (SFO
        Part XV — the substantial-shareholder/director register). ASP.NET flow: the
        face bootstraps the search form session (VIEWSTATE quartet + cookie cached
        together 30min), POSTs once, parses the seven list links off the resolution
        page (sid/cid/sd/ed verbatim — never invented), then GETs the chosen list
        with the session. --list codes: ns notices · as complete SS · cs consolidated
        SS · ad complete director · nd director notices · an all notices (default ns).
        Dates ISO accepted, default window 90d→today; from_date < 2017-07-03 refused
        (the DION floor — upstream silently clamps earlier asks). A dead session
        re-bootstraps once. Row's form_fn feeds hk_hkexdi_form."""
        self._co_only("hk_hkexdi_corp_list")
        r = company.hk_hkexdi.corp_list(stock_code=stock_code, list_code=list_code,
                                        from_date=from_date, to_date=to_date, pg=pg,
                                        cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        result = {k: x for k, x in r.items() if k != "_meta"}
        if rows:
            top = rows[0]
            first = next(iter(top.values()), None)
            reason = (f"HKEX DI {r['list_code']}/{r['list_label'] or '—'} for {r['stock_code']} "
                      f"{r['corp_name'] or '—'}: {r['total'] if r['total'] is not None else len(rows)} records "
                      f"— sample {top.get('Date of notice') or top.get('Date of change') or first or '—'}"
                      + (" — session re-bootstrapped once (stale cached quartet)"
                         if r.get("_session_refreshed") else ""))
        else:
            reason = (f"HKEX DI {r['list_code']}/{r['list_label'] or '—'} for {r['stock_code']} "
                      f"{r['corp_name'] or '—'}: zero rows in {result['params']['from_date']}→"
                      f"{result['params']['to_date']} (a legitimate miss — widen --from-date, "
                      "note the 2017-07-03 DION floor, or try --list as)")
        return self._flat_env(
            tool="hk_hkexdi_corp_list",
            input={"stock_code": result["params"]["stock_code"], "list": list_code,
                   "from_date": from_date, "to_date": to_date, "pg": pg},
            reason=reason, result=result,
            evidence=[{"quote": " · ".join(str(v) for v in list(x.values())[:4] if v is not None)
                                + (f" · fn {x['form_fn']}" if x.get("form_fn") else ""),
                       "url": x.get("form_url")
                              or "https://di.hkex.com.hk/di/NSSrchCorp.aspx?src=MAIN&lang=EN"}
                      for x in rows[:5]],
            provider_id="hk_hkexdi", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"host": "di.hkex.com.hk", "list": list_code,
                                "stock_code": result["params"]["stock_code"]}},
        )

    def hk_hkexdi_form(self, *, fn, execution=None, no_cache=None):
        """company hk_hkexdi_form: one DI notice's full detail (fn= hard key —
        {CS|DA|IR}{yyyymmdd}E{seq}; IR serials ride NSForm4, CS/DA ride NSForm2, pure
        GET no session). tables carries EVERY table verbatim (header split when the
        first row reads as one); positions picks the Long/Short/LendingPool three-state
        block; controlled_corporations picks the controlled-company chain (the official
        equity-penetration graph: name/%control/direct Y/N/shares). Capacity/derivative
        code legends (2201/16021…) ride the tables verbatim."""
        self._co_only("hk_hkexdi_form")
        r = company.hk_hkexdi.form(fn=fn, cache=self._c._cache,
                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        n_tab = len(r["tables"])
        pos_bits = []
        for k in ("Long position", "Short position", "Lending Pool"):
            v = (r.get("positions") or {}).get(k)
            if v and v.get("total_number_of_shares"):
                pos_bits.append(f"{k} {v['total_number_of_shares']}")
        reason = (f"DI form {r['fn']} ({r['form_kind']} — {r['form_title'] or 'form'}): "
                  f"{n_tab} tables verbatim"
                  + (f"; positions " + ", ".join(pos_bits) if pos_bits else "")
                  + (f"; {len(r['controlled_corporations'])} controlled-corporation rows"
                     if r["controlled_corporations"] else "")
                  + " — capacity/derivative code legends ride the tables verbatim")
        return self._flat_env(
            tool="hk_hkexdi_form",
            input={"fn": r["fn"]},
            reason=reason, result=result,
            evidence=[{"quote": (f"table {t['index']}"
                                 + (f" [{t['header'][0][:40]}…]" if t.get("header") else "")
                                 + f" {len(t['rows'])} rows — "
                                 + " | ".join(c for c in (t["rows"][0] or [])[:4] if c))[:180],
                       "url": ("https://di.hkex.com.hk/di/NSForm4.aspx?fn=" if r["form_kind"] == "IR"
                               else "https://di.hkex.com.hk/di/NSForm2.aspx?fn=") + r["fn"]
                              + "&src=MAIN&lang=EN&g_lang=en"}
                      for t in r["tables"][:5] if t.get("rows")],
            provider_id="hk_hkexdi", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"host": "di.hkex.com.hk", "fn": r["fn"], "op": r["params"]["op"]}},
        )

    def hk_hkexdi_ir_summaries(self, *, pg=1, stock_code=None, execution=None, no_cache=None):
        """company hk_hkexdi_ir_summaries: the C5 market-wide "Results of
        investigations" daily release stream (NSC5Sum.aspx — pure GET, no session;
        53 rows/page probe day, Total records 281). Each row's serial is a hard
        NSForm4 fn= key feeding hk_hkexdi_form. --pg pages (1-based); --stock-code
        filters client-side (digits-normalized)."""
        self._co_only("hk_hkexdi_ir_summaries")
        r = company.hk_hkexdi.ir_summaries(pg=pg, stock_code=stock_code,
                                           cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        result = {k: x for k, x in r.items() if k != "_meta"}
        if rows:
            top = rows[0]
            reason = (f"DI C5 investigation results page {r['page']}: {len(rows)} rows"
                      + (f" of {r['total']} total" if r["total"] is not None else "")
                      + f" — sample {top.get('serial') or '—'} {top.get('stock_code') or '—'} "
                      f"{(top.get('report_name') or '—')[:60]}"
                      + (" (client-side stock filter)" if stock_code else ""))
        else:
            reason = (f"DI C5 investigation results page {r['page']}: zero rows"
                      + (f" on stock {stock_code}" if stock_code else "")
                      + (f" (page beyond the {r['total']}-record stream)" if r["total"] else ""))
        return self._flat_env(
            tool="hk_hkexdi_ir_summaries",
            input={"pg": pg, "stock_code": stock_code},
            reason=reason, result=result,
            evidence=[{"quote": f"{x.get('serial') or '—'} · {x.get('release_date') or '—'} · "
                                f"{x.get('stock_code') or '—'} · {(x.get('report_name') or '—')[:60]}",
                       "url": x.get("form_url")
                              or "https://di.hkex.com.hk/di/NSC5Sum.aspx?pg=" + str(r["page"])}
                      for x in rows[:5]],
            provider_id="hk_hkexdi", metas=[r["_meta"]],
            query={"source": "live",
                   "upstream": {"host": "di.hkex.com.hk", "op": "c5", "pg": r["page"]}},
        )

    def hk_hkexnews_search(self, *, stock=None, title=None, market="SEHK", from_date=None,
                           to_date=None, t1=None, t2=None, t2g=None, document_type=None,
                           row_range=100, first=0, codebook=None, execution=None, no_cache=None):
        """company hk_hkexnews_search: HKEXnews announcements (HK — the disclosure-of-interests
        grade filings corpus: 11,189 items on probe day alone, searchable back to 1999-04-01).
        THREE mutually-exclusive modes: --stock (code or name — resolved to stockId via the
        prefix.do JSONP, searchType=1) XOR --title (keyword, searchType=0) XOR --codebook (one of
        the six eds codebooks verbatim). market SEHK|GEM. t1/t2/t2g post-2007-06-25 headline
        codes; document_type the pre-2007 era (doc_e). DATE_TIME keeps the HK DD/MM/YYYY HH:MM
        shape verbatim; each row's full_url feeds hk_hkexnews_document."""
        self._co_only("hk_hkexnews_search")
        r = company.hk_hkex.search(stock=stock, title=title, market=market, from_date=from_date,
                                   to_date=to_date, t1=t1, t2=t2, t2g=t2g,
                                   document_type=document_type, row_range=row_range, first=first,
                                   codebook=codebook, cache=self._c._cache,
                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        metas = [r["_meta"]]
        if r.get("_resolve_meta"):
            metas.append(r["_resolve_meta"])
        result = {k: x for k, x in r.items() if k not in ("_meta", "_resolve_meta")}
        if r["mode"] == "codebook":
            reason = (f"HKEXnews codebook {r['codebook']}: "
                      f"{r['total'] if r['total'] is not None else len(r['rows'])} entries verbatim "
                      "(one of the six eds dictionaries — t1/t2/t2G categories, doc-era types, "
                      "active/inactive stock resolve maps)")
        elif r["mode"] == "stock":
            s = r["stock"] or {}
            reason = (f"HKEXnews {r['market']} announcements for {s.get('code') or '—'} "
                      f"{s.get('name') or ''} (stockId {s.get('stock_id') or '—'} via prefix.do): "
                      f"{r['total']:,} items, {len(r['rows'])} rows returned"
                      + (f" from {from_date}" if from_date else "")
                      + (f" to {to_date}" if to_date else "")
                      + " — DATE_TIME is HK-shaped DD/MM/YYYY HH:MM verbatim")
        else:
            reason = (f"HKEXnews {r['market']} title search \"{title}\": {r['total']:,} items, "
                      f"{len(r['rows'])} rows returned"
                      + (f" from {from_date}" if from_date else "")
                      + (f" to {to_date}" if to_date else ""))
        rows = r["rows"] if isinstance(r.get("rows"), list) else []
        return self._flat_env(
            tool="hk_hkexnews_search",
            input=({"codebook": r["codebook"]} if r["mode"] == "codebook" else
                   {"stock": stock, "title": title, "market": r["market"],
                    "from_date": from_date, "to_date": to_date, "t1": t1, "t2": t2, "t2g": t2g,
                    "document_type": document_type, "row_range": row_range, "first": first}),
            reason=reason, result=result,
            evidence=[{"quote": (f"{x.get('DATE_TIME') or '—'} · {x.get('STOCK_CODE') or '—'} · "
                                 f"{(x.get('TITLE') or '—')[:90]}"
                                 + (f" · {x.get('DOCUMENT_TYPE') or ''}"
                                    if r["mode"] != "codebook" and x.get("DOCUMENT_TYPE") else "")),
                       "url": x.get("full_url") or "https://www1.hkexnews.hk/search/titlesearch.xhtml"}
                      for x in rows[:5]],
            provider_id="hk_hkex", metas=metas,
            query={"source": "raw", "upstream": r.get("params") or {"codebook": r["codebook"]}},
        )

    def hk_hkexnews_document(self, *, url=None, link=None, execution=None, no_cache=None):
        """company hk_hkexnews_document: fetch an HKEXnews announcement's PDF bytes verbatim (the
        E11 body-fetch pattern — hk_hkexnews_search's full_url / FILE_LINK in, sha256 +
        content_latin1 out; no --text, PDF is not HTML and text extraction stays on the harvest
        line). Wall: www1.hkexnews.hk/listedco/… only — anything else never leaves the process."""
        self._co_only("hk_hkexnews_document")
        out = company.hk_hkex.document(url=url, link=link, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        head = out["content_latin1"][:60].replace("\r", " ").replace("\n", " ")
        return self._flat_env(
            tool="hk_hkexnews_document",
            input=out["params"],
            reason=(f"HKEXnews document {out['file_name']} — {out['size_bytes']:,}B "
                    f"sha256 {out['sha256'][:12]}… ({out['file_type']} — frozen once published, "
                    "TTL 7d; content_latin1 round-trips: .encode('latin-1') == the original bytes)"),
            result={k: out[k] for k in ("file_name", "url", "size_bytes", "sha256",
                                        "file_type", "content_latin1")},
            evidence=[{"quote": head + ("…" if len(out["content_latin1"]) > 60 else ""),
                       "url": out["url"]}],
            provider_id="hk_hkex", metas=[out["_meta"]],
            query={"source": "live", "upstream": {"document": out["url"]}},
        )
