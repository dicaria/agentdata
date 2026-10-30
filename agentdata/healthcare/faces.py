"""healthcare faces — flat face methods mixed in (moved out of client.py's _Domain in the 0.2.6 domain split).

Mixin root _Domain (MRO assembly, see client.py); discipline: no __init__, it may only depend on root internals
(_flat_env/_c/_request…), method names are globally unique across domains (a collision would shadow another domain's face).
"""
from ..errors import SdkError
from ..transport import _tty_tag
import urllib.error
import urllib.parse
import urllib.request


from .. import healthcare  # the domain module is called by path (the historical shape, kept for the least-perturbation C2)

class HealthcareFaces:
    def _hc_only(self, tool: str):
        if self.name != "healthcare":
            raise SdkError("usage_error", detail=f"{tool} is a healthcare domain capability (not available in the {self.name} domain)")
    def rxnav_rxcui_by_name(self, *, name, execution=None, no_cache=None):
        """healthcare rxnav_rxcui_by_name: drug/brand name → an RxCUI normalization card (the upstream rxcuiByName single-record face, no paging)."""
        self._hc_only("rxnav_rxcui_by_name")
        v = str(name or "").strip()
        if not v:
            raise SdkError("usage_error", provider="rxnav", detail="rxnav_rxcui_by_name needs name (a drug or brand name)")
        r = healthcare.rxnav.resolve_drug_name(v, cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        metas = [m for m in (r["_meta"].get("lookup"), r["_meta"].get("props")) if m]
        return self._flat_env(
            tool="rxnav_rxcui_by_name", input={"name": v},
            reason=f"RxNav normalization: drug name '{v}' → RxCUI {r['rxcui']}{_tty_tag(r.get('tty'))}",
            result=result,
            evidence=[{"quote": f"RxCUI {r['rxcui']} = {result.get('normalized_name') or v}",
                       "url": f"https://rxnav.nlm.nih.gov/REST/rxcui/{r['rxcui']}/properties.json"}],
            provider_id="rxnav", metas=metas,
            query={"source": "raw", "upstream": {"name": v}},
        )

    def rxnav_rxcui_atc(self, *, rxcui, execution=None, no_cache=None):
        """healthcare rxnav_rxcui_atc: RxCUI → ATC code (the upstream property.json?propName=ATC; run rxnav_rxcui_by_name first for drug names)."""
        self._hc_only("rxnav_rxcui_atc")
        v = str(rxcui or "").strip()
        if not v.isdigit():
            raise SdkError("usage_error", provider="rxnav",
                           detail="rxnav_rxcui_atc needs rxcui (a numeric string; normalize drug names first with rxnav_rxcui_by_name)")
        at = healthcare.rxnav.get_atc(v, cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        codes = at["atc"]
        return self._flat_env(
            tool="rxnav_rxcui_atc", input={"rxcui": v},
            reason=(f"RxNav ATC: RxCUI {v} → {'/'.join(codes) if codes else 'no ATC (this concept carries no ATC level — ATC attaches to the ingredient level, and brand-name concepts are usually empty)'}"),
            result={"rxcui": v, "atc": codes},
            evidence=[{"quote": f"RxCUI {v} ATC = {', '.join(codes) or '(empty)'}",
                       "url": f"https://rxnav.nlm.nih.gov/REST/rxcui/{v}/property.json?propName=ATC"}],
            provider_id="rxnav", metas=[at["_meta"]],
            query={"source": "raw", "upstream": {"rxcui": v, "propName": "ATC"}},
        )

    def mesh_descriptor(self, *, label, match="contains", limit=10, execution=None, no_cache=None):
        """healthcare mesh_descriptor: drug/disease term → MeSH descriptor candidates + the preferred record's synonym pool (the upstream names label/match/limit;
        the name mirrors the /mesh/lookup/descriptor path segment — the verb face resolve kind=mesh_term stays frozen)."""
        self._hc_only("mesh_descriptor")
        v = str(label or "").strip()
        if not v:
            raise SdkError("usage_error", provider="mesh", detail="mesh_descriptor needs label (a drug/disease name, etc.)")
        m = str(match or "contains").strip()
        if m not in ("contains", "exact", "startswith"):
            raise SdkError("usage_error", provider="mesh",
                           detail=f"the match closed set is contains|exact|startswith (the real upstream limit), got '{m}'")
        size = min(50, max(1, int(limit)))
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        r = healthcare.mesh.search_descriptors(v, match=m, limit=size, cache=cache, no_cache=nc)
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["candidates"] or [None])[0]
        top_descriptor, dmeta = None, None
        if top:  # details of the preferred record: synonym pool + qualifier anchors (a fixed two-hop cost, the vocabulary is released yearly)
            d = healthcare.mesh.descriptor_details(top["mesh_ui"], cache=cache, no_cache=nc)
            top_descriptor = {"mesh_ui": d["descriptor"], "label": top["label"],
                              "preferred_term": d["preferred_term"], "synonyms": d["synonyms"],
                              "qualifiers": d["qualifiers"], "seealso": d["seealso"]}
            dmeta = d["_meta"]
        return self._flat_env(
            tool="mesh_descriptor", input={"label": v, "match": m, "limit": size},
            reason=(f"MeSH normalization: '{v}' → {top_descriptor['mesh_ui']} {top_descriptor['label']}"
                    f" ({len(top_descriptor['synonyms'])} synonyms, authoritative name {top_descriptor['preferred_term'] or '—'})"
                    if top_descriptor else
                    f"MeSH zero hits: '{v}' is not in the controlled vocabulary (an empty result is a legal answer; for a brand name try the ingredient name)"),
            result={**result, "top_descriptor": top_descriptor},
            evidence=[{"quote": f"{c['mesh_ui'] or '—'} = {c['label'] or '—'}",
                       "url": c["descriptor_uri"] or "https://id.nlm.nih.gov/mesh/lookup/descriptor"}
                      for c in result["candidates"][:5]],
            provider_id="mesh", metas=[r["_meta"], dmeta],
            query={"source": "raw", "upstream": {"label": v, "match": m, "limit": size}},
        )

    def gudid_devices(self, *, di=None, udi=None, record_key=None, execution=None, no_cache=None):
        """healthcare gudid_devices: the US device master record (AccessGUDID v3, a single endpoint with exactly one of di/udi/record_key)."""
        self._hc_only("gudid_devices")
        r = healthcare.gudid.lookup_device(di=di, udi=udi, record_key=record_key,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        key = r["by"]
        return self._flat_env(
            tool="gudid_devices", input={k: v for k, v in (("di", di), ("udi", udi), ("record_key", record_key)) if v},
            reason=(f"AccessGUDID v3 master record: {key}={r[key]} → {r.get('brand_name') or '(no brand name)'}"
                    f" / {r.get('company_name') or '(no manufacturer name)'}"),
            result=result,
            evidence=[{"quote": (r.get("device_description") or f"{key}={r[key]}")[:200],
                       "url": f"https://accessgudid.nlm.nih.gov/api/v3/devices/lookup.json?{key}={r[key]}"}],
            provider_id="gudid", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {key: r[key]}},
        )

    def eudamed_devices_udi_di_data(self, *, primary_di, page=0, page_size=5, iso2_code="en",
                       execution=None, no_cache=None):
        """healthcare eudamed_devices_udi_di_data: the EU device master record (an EUDAMED primaryDi exact lookup + paging under the upstream names page/pageSize/iso2Code)."""
        self._hc_only("eudamed_devices_udi_di_data")
        r = healthcare.eudamed.query_udi_di(primary_di, page=page, page_size=page_size, iso2_code=iso2_code,
                                           cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        mfr = result.get("manufacturer") or {}
        ar = result.get("authorised_representative")
        return self._flat_env(
            tool="eudamed_devices_udi_di_data",
            input={"primary_di": str(primary_di).strip(), "page": int(page),
                   "page_size": int(page_size), "iso2_code": str(iso2_code)},
            reason=(f"EUDAMED master record: DI {result.get('primary_di')} → {result.get('trade_name') or '(no brand name)'}"
                    f" ({mfr.get('name') or '—'}, SRN {mfr.get('srn') or '—'}"
                    + (f"; authorised rep {ar['srn']}" if ar and ar.get("srn") else "")
                    + f", {result.get('risk_class') or '—'}) — total_elements={result.get('total_elements')}"
                    f" (page={result.get('page')}, page_size={result.get('page_size')})"),
            result=result,
            evidence=[{"quote": (f"{result.get('primary_di')} = {result.get('trade_name') or '—'} / "
                                 f"{mfr.get('name') or '—'} (SRN {mfr.get('srn') or '—'})"),
                       "url": (f"https://ec.europa.eu/tools/eudamed/api/devices/udiDiData"
                               f"?primaryDi={result.get('primary_di')}&page={int(page)}&pageSize={int(page_size)}")}],
            provider_id="eudamed", metas=[r["_meta"]],
            query={"source": "raw",
                   "upstream": {"primaryDi": str(primary_di).strip(), "page": int(page),
                                "pageSize": int(page_size), "size": int(page_size),
                                "iso2Code": str(iso2_code)}},
        )

    def epmc_search(self, *, search=None,
                      result_type="lite", page_size=25, cursor_mark="*", sort=None,
                      execution=None, no_cache=None):
        """healthcare epmc_search: literature evidence search (Europe PMC; search=query is the verbatim param channel, AFF: for affiliation search)."""
        self._hc_only("epmc_search")
        q = str(search or "").strip() or None
        if not q:
            raise SdkError("usage_error", provider="epmc",
                           detail="epmc_search needs search (the expression uses the upstream name, e.g. AFF:\"Novartis\")")
        r = healthcare.epmc.search_raw(q, result_type=result_type, page_size=page_size,
                                      cursor_mark=cursor_mark, sort=sort,
                                      cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        quartet = {"source": "raw", "search": q,
                   "upstream": {"query": q, "format": "json", "resultType": str(result_type),
                                "pageSize": r["page_size"], "cursorMark": str(cursor_mark or "*"),
                                **({"sort": str(sort)} if sort else {})}}
        return self._flat_env(
            tool="epmc_search",
            input={"search": q,
                   "result_type": result_type, "page_size": r["page_size"],
                   "cursor_mark": str(cursor_mark or "*"), "sort": sort},
            reason=(f"Europe PMC: {r['hitCount']} hits, {len(rows)} returned"
                    + f" (expression {q})"
                    + (f", next page cursorMark={r['next_cursor_mark']}" if r.get("next_cursor_mark") else "")),
            result={"hitCount": r["hitCount"], "count": len(rows), "rows": rows,
                    "next_cursor_mark": r.get("next_cursor_mark"), "page_size": r["page_size"]},
            evidence=[{"quote": x["title"], **({"url": x["url"]} if x["url"] else {}),  # PAT rows have no EPMC page — omit the key rather than emitting null (0.2.8)
                       "pmid": x["pmid"], "journal": x["journal"], "pub_year": x["pub_year"],
                       "cited_by": x["cited_by"]}
                      for x in rows[:5]],
            provider_id="epmc", metas=[r["_meta"]],
            query=quartet,
        )

    def ctgov_studies(self, *, query_term=None, query_titles=None, query_intr=None,
                     query_cond=None, filter_advanced=None, agg_filters=None, fields=None,
                     page_size=20, page_token=None, sort=None,
                     count_total=True, execution=None, no_cache=None):
        """healthcare ctgov_studies: clinical-trial search (CT.gov v2; query_term is the query.term verbatim channel,
        query_titles/query_intr/agg_filters/fields are independent upstream params that combine with any of them (opened by probing on 2026-10-28),
        query_cond/filter_advanced likewise; a bare call = the first page of the whole database, which is legal)."""
        self._hc_only("ctgov_studies")
        qt = str(query_term or "").strip() or None
        r = healthcare.ctgov.search_raw(query_term=qt, query_titles=query_titles, query_intr=query_intr,
                                       query_cond=query_cond, filter_advanced=filter_advanced,
                                       agg_filters=agg_filters, fields=fields,
                                       page_size=page_size, page_token=page_token, sort=sort,
                                       count_total=count_total, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        total = r["total"] if r["total"] is not None else len(rows)
        reason = f"CT.gov: {total} hits, {len(rows)} returned"
        if r.get("next_page_token"):
            reason += f" (next page page_token={r['next_page_token']})"
        quartet = {"source": "raw", "upstream": r["params"]}
        if qt:
            quartet["search"] = qt
        return self._flat_env(
            tool="ctgov_studies",
            input={"query_term": qt, "query_titles": query_titles, "query_intr": query_intr,
                   "query_cond": query_cond, "filter_advanced": filter_advanced,
                   "agg_filters": agg_filters, "fields": fields,
                   "page_size": r["page_size"], "page_token": page_token, "sort": sort,
                   "count_total": bool(count_total)},
            reason=reason,
            result={"total": r["total"], "count": len(rows), "rows": rows,
                    "next_page_token": r.get("next_page_token"), "page_size": r["page_size"]},
            evidence=[{"quote": f"{x['nct_id']} {x['title']}", "url": x["url"],
                       "status": x["status"], "phase": x["phase"], "sponsor": x["sponsor"]}
                      for x in rows[:5]],
            provider_id="ctgov", metas=[r["_meta"]],
            query=quartet,
        )

    def dailymed_spls(self, *, search=None, manufacturer=None, setid=None,
                       page=None, pagesize=None, sort=None, execution=None, no_cache=None):
        """healthcare dailymed_spls: SPL labeling metadata (the six DailyMed spls.json params under their upstream names;
        search→drug_name; manufacturer/setid/page/pagesize/sort combine freely)."""
        self._hc_only("dailymed_spls")
        drug_name = str(search or "").strip() or None
        r = healthcare.dailymed.spls_raw(drug_name=drug_name, manufacturer=manufacturer, setid=setid,
                                        page=page, pagesize=pagesize, sort=sort,
                                        cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        # Silent-clamp visibility: empty pagination values in metadata are the string 'null' — compare only when both ends parse as integers
        clamp_note = ""
        if pagesize is not None:
            try:
                epp = int(str(r["elements_per_page"]))
                clamp_note = f", upstream actually sent elements_per_page={epp}" + (" (silently clamped to 100 — a larger value has no effect)" if epp < int(pagesize) else "")
            except (TypeError, ValueError):
                clamp_note = f", elements_per_page={r['elements_per_page']}"
        quartet = {"source": "raw", "upstream": r["params"]}
        if drug_name:
            quartet["search"] = drug_name
        return self._flat_env(
            tool="dailymed_spls",
            input={"search": drug_name, "manufacturer": manufacturer, "setid": setid,
                   "page": page, "pagesize": pagesize, "sort": sort},
            reason=f"DailyMed SPL: {r['total']} labels hit, {len(rows)} returned{clamp_note}",
            result={"total": r["total"], "count": len(rows), "rows": rows,
                    "page": r["page"], "elements_per_page": r["elements_per_page"]},
            evidence=[{"quote": x["title"], "url": x["url"], "setid": x["setid"],
                       "published_date": x["published_date"]} for x in rows[:5]],
            provider_id="dailymed", metas=[r["_meta"]],
            query=quartet,
        )

    def fda_drug_shortages(self, *, search=None,
                           limit=20, skip=0, sort="update_date:desc", execution=None, no_cache=None):
        """healthcare fda_drug_shortages: a single lookup of FDA drug shortages (openFDA;
        the search channel uses the upstream name (e.g. openfda.manufacturer_name.exact:"…" / generic_name:"…" / status:Current);
        limit 1-1000 is the upstream hard limit)."""
        self._hc_only("fda_drug_shortages")
        q = str(search or "").strip() or None
        if not q:
            raise SdkError("usage_error", provider="shortages",
                           detail="fda_drug_shortages needs search (the expression uses the upstream name, e.g. generic_name:\"bupivacaine\")")
        r = healthcare.shortages.search_raw(q, limit=limit, skip=skip, sort=sort,
                                           cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        quartet = {"source": "raw", "search": q, "upstream": {"search": q, "limit": result["limit_applied"],
                                                               **({"skip": result["skip"]} if result["skip"] else {}),
                                                               **({"sort": r["sort"]} if r.get("sort") else {})}}
        return self._flat_env(
            tool="fda_drug_shortages",
            input={"search": q,
                   "limit": result["limit_applied"], "skip": result["skip"], "sort": r.get("sort")},
            reason=(f"openFDA drug shortages: {result['total']} hits (update_date descending), {result['count']} returned"
                    + (f", next page skip={result['skip'] + result['count']}" if result.get("has_more") else "")
                    + " — manufacturer names match the openFDA normalization layer (exact phrase); parent and subsidiary groups are not merged, so narrow by NDC/application_number before storing"
                    if result["total"] else
                    f"openFDA drug shortages: zero hits (zero hits is a legal answer — this manufacturer/drug name has no shortage registration)"),
            result=result,
            evidence=[{"quote": (f"{row['generic_name'] or '—'} = "
                                 f"{row['company_name'] or (row['manufacturers'] or ['—'])[0]}"
                                 f" ({row['availability'] or '—'} / {row['status'] or '—'}, updated {row['update_date'] or '—'})"),
                       "url": f"https://api.fda.gov/drug/shortages.json?search={urllib.parse.quote(q, safe='')}",
                       "package_ndc": row["package_ndc"]}
                      for row in result["rows"][:5]],
            provider_id="shortages", metas=[r["_meta"]],
            query=quartet,
        )

    def _fda_recall_face(self, tool, face, *, search, limit, skip, sort, evidence_fmt, lead, no_cache=None):
        """The envelope shared by the three Wave 10 recall faces (born flat: the upstream param names search/limit/skip/sort, zero sugar, zero deprecations)."""
        raw = str(search or "").strip() or None
        r = healthcare.fda_recalls.search(face, raw, limit=limit, skip=skip, sort=sort,
                                      cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        quartet = {"source": "raw", "search": result["search"],
                   "upstream": {"search": result["search"], "limit": result["limit_applied"],
                                **({"skip": result["skip"]} if result["skip"] else {}),
                                **({"sort": r["sort"]} if r.get("sort") else {})}}
        return self._flat_env(
            tool=tool,
            input={"search": raw, "limit": result["limit_applied"], "skip": result["skip"], "sort": r.get("sort")},
            reason=(f"{lead}: {result['total']} hits ({r.get('sort') or 'default order'}), {result['count']} returned"
                    + (f", next page skip={result['skip'] + result['count']}" if result.get("has_more") else "")
                    + " — firm names follow the registration convention (each subsidiary is recorded separately), so group due diligence must aggregate before searching"
                    if result["total"] else
                    f"{lead}: zero hits (an openFDA 404=NOT_FOUND is a legal answer — this expression has no recall registration)"),
            result=result,
            evidence=[{"quote": evidence_fmt(row),
                       "url": f"https://api.fda.gov{healthcare.fda_recalls.provider['ops'][face]['path']}"
                              f"?search={urllib.parse.quote(result['search'], safe='')}"}
                      for row in result["rows"][:5]],
            provider_id=healthcare.fda_recalls.provider["id"], metas=[r["_meta"]],
            query=quartet,
        )

    def fda_drug_recalls(self, *, search=None, limit=20, skip=0, sort=None, execution=None, no_cache=None):
        """healthcare fda_drug_recalls: FDA drug recalls (openFDA drug/enforcement;
        search passes through under the upstream name, e.g. recalling_firm.exact:"Firm Name"; limit 1-1000 is a hard limit; the default is report_date descending)."""
        self._hc_only("fda_drug_recalls")
        return self._fda_recall_face(
            "fda_drug_recalls", "drug", search=search, limit=limit, skip=skip, sort=sort,
            evidence_fmt=lambda row: (f"{row['recall_number'] or '—'} · {row['recalling_firm'] or '—'}"
                                      f" ({row['classification'] or '—'} / {row['status'] or '—'}, "
                                      f"recall initiated {row['recalled_on'] or '—'})"),
            lead="openFDA drug recalls (the drug/enforcement press-release face, 2012+)", no_cache=no_cache)

    def fda_device_recalls(self, *, search=None, limit=20, skip=0, sort=None, execution=None, no_cache=None):
        """healthcare fda_device_recalls: FDA device recalls (openFDA device/recall = the RES system;
        firm search uses the phrase form recalling_firm:"Firm Name" (.exact is unverified); it is a different system from the bulk device/enforcement face)."""
        self._hc_only("fda_device_recalls")
        return self._fda_recall_face(
            "fda_device_recalls", "device", search=search, limit=limit, skip=skip, sort=sort,
            evidence_fmt=lambda row: (f"{row['res_event_number'] or '—'} · {row['recalling_firm'] or '—'}"
                                      f" ({row['recall_status'] or '—'}, initiated {row['initiated_on'] or '—'})"),
            lead="openFDA device recalls (the device/recall RES face, including the full Ongoing lifecycle)", no_cache=no_cache)

    def fda_food_recalls(self, *, search=None, limit=20, skip=0, sort=None, execution=None, no_cache=None):
        """healthcare fda_food_recalls: FDA food recalls (openFDA food/enforcement;
        search passes through under the upstream name, e.g. recalling_firm.exact:"Firm Name"; the default is report_date descending)."""
        self._hc_only("fda_food_recalls")
        return self._fda_recall_face(
            "fda_food_recalls", "food", search=search, limit=limit, skip=skip, sort=sort,
            evidence_fmt=lambda row: (f"{row['recall_number'] or '—'} · {row['recalling_firm'] or '—'}"
                                      f" ({row['classification'] or '—'} / {row['status'] or '—'}, "
                                      f"recall initiated {row['recalled_on'] or '—'})"),
            lead="openFDA food recalls (the food/enforcement face, 2012+)", no_cache=no_cache)

    def fda_crl_letters(self, *, search=None, limit=20, skip=0, sort="letter_date:desc",
                        execution=None, no_cache=None):
        """healthcare fda_crl_letters: FDA Complete Response Letters (openFDA transparency/crl;
        company_name:"Firm Name" finds the company's negative-approval events; company_rep/approver_name (person names, PII) and text (OCR noise) are not returned)."""
        self._hc_only("fda_crl_letters")
        raw = str(search or "").strip() or None
        r = healthcare.fda_crl.search(raw, limit=limit, skip=skip, sort=sort,
                                  cache=self._c._cache,
                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        quartet = {"source": "raw", "search": result["search"],
                   "upstream": {"search": result["search"], "limit": result["limit_applied"],
                                **({"skip": result["skip"]} if result["skip"] else {}),
                                **({"sort": r["sort"]} if r.get("sort") else {})}}
        return self._flat_env(
            tool="fda_crl_letters",
            input={"search": raw, "limit": result["limit_applied"], "skip": result["skip"], "sort": r.get("sort")},
            reason=(f"openFDA CRLs: {result['total']} letters hit (letter_date descending), {result['count']} returned"
                    + (f", next page skip={result['skip'] + result['count']}" if result.get("has_more") else "")
                    + " — the negative-approval event stream (approval_status = the application outcome after the letter)"
                    if result["total"] else
                    "openFDA CRLs: zero hits (an openFDA 404=NOT_FOUND is a legal answer — this company has no CRL registration or is not covered)"),
            result=result,
            evidence=[{"quote": f"{row['company_name'] or '—'} ({row['letter_date'] or '—'}, "
                                f"outcome {row['approval_status'] or '—'})",
                       "url": f"https://api.fda.gov/transparency/crl.json"
                              f"?search={urllib.parse.quote(result['search'], safe='')}"}
                      for row in result["rows"][:5]],
            provider_id=healthcare.fda_crl.provider["id"], metas=[r["_meta"]],
            query=quartet,
        )

    def _fda_wave10b_face(self, tool, mod, face, *, search, limit, skip, sort, evidence_fmt, lead, no_cache=None):
        """The envelope shared by the seven Wave 10b faces (born flat: the upstream param names search/limit/skip/sort, zero sugar, zero deprecations;
        mod = the fda_drugs|fda_devices provider module; the same shape as _fda_recall_face but parameterised by module)."""
        raw = str(search or "").strip() or None
        r = mod.search(face, raw, limit=limit, skip=skip, sort=sort,
                       cache=self._c._cache,
                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        quartet = {"source": "raw", "search": result["search"],
                   "upstream": {"search": result["search"], "limit": result["limit_applied"],
                                **({"skip": result["skip"]} if result["skip"] else {}),
                                **({"sort": r["sort"]} if r.get("sort") else {})}}
        return self._flat_env(
            tool=tool,
            input={"search": raw, "limit": result["limit_applied"], "skip": result["skip"], "sort": r.get("sort")},
            reason=(f"{lead}: {result['total']} hits ({r.get('sort') or 'default order'}), {result['count']} returned"
                    + (f", next page skip={result['skip'] + result['count']}" if result.get("has_more") else "")
                    + " — company names follow the registration convention (each subsidiary is recorded separately), so group due diligence must aggregate before searching"
                    if result["total"] else
                    f"{lead}: zero hits (an openFDA 404=NOT_FOUND is a legal answer — this expression has no registration record)"),
            result=result,
            evidence=[{"quote": evidence_fmt(row),
                       "url": f"https://api.fda.gov{mod.provider['ops'][face]['path']}"
                              f"?search={urllib.parse.quote(result['search'], safe='')}"}
                      for row in result["rows"][:5]],
            provider_id=mod.provider["id"], metas=[r["_meta"]],
            query=quartet,
        )

    def fda_drug_approvals(self, *, search=None, limit=20, skip=0, sort=None, execution=None, no_cache=None):
        """healthcare fda_drug_approvals: FDA drug application/approval dossiers (openFDA drug/drugsfda;
        sponsor_name:\"TEVA\" finds the company (applicant_name is a documentation illusion, measured with _exists_ on 2026-10-29; the keyword field is case-sensitive — only all-caps matches); the default is the latest submission date descending)."""
        self._hc_only("fda_drug_approvals")
        return self._fda_wave10b_face(
            "fda_drug_approvals", healthcare.fda_drugs, "approvals", search=search, limit=limit, skip=skip, sort=sort,
            evidence_fmt=lambda row: (f"{row['application_number'] or '—'} · {row['sponsor_name'] or '—'}"
                                      f" ({(row['submissions'] or [{}])[0].get('submission_status') or '—'}, "
                                      f"{(row['submissions'] or [{}])[0].get('submission_status_date') or '—'})"),
            lead="openFDA drug application dossiers (drug/drugsfda, 29,420 applications)", no_cache=no_cache)

    def fda_drug_catalog(self, *, search=None, limit=20, skip=0, sort=None, execution=None, no_cache=None):
        """healthcare fda_drug_catalog: the NDC catalogue (openFDA drug/ndc; labeler_name finds the labeler;
        it includes the marketing_start/end_date + marketing_category merged in from NSDE — the standalone NSDE endpoint died, measured 2026-10-29)."""
        self._hc_only("fda_drug_catalog")
        return self._fda_wave10b_face(
            "fda_drug_catalog", healthcare.fda_drugs, "catalog", search=search, limit=limit, skip=skip, sort=sort,
            evidence_fmt=lambda row: (f"{row['product_ndc'] or '—'} · {row['labeler_name'] or '—'}"
                                      f" ({row['brand_name'] or '—'} / {row['marketing_category'] or '—'}, "
                                      f"marketed {row['marketing_start_date'] or '—'})"),
            lead="openFDA NDC drug catalogue (drug/ndc, daily refresh)", no_cache=no_cache)

    def fda_orangebook(self, *, search=None, limit=20, skip=0, sort=None, execution=None, no_cache=None):
        """healthcare fda_orangebook: Orange Book approved drugs (the openFDA drug/orangebook API face;
        the company key is products[].application_name/_full_name (the top-level applicant fields do not exist, measured); the default is approval date descending)."""
        self._hc_only("fda_orangebook")
        return self._fda_wave10b_face(
            "fda_orangebook", healthcare.fda_drugs, "orange_book", search=search, limit=limit, skip=skip, sort=sort,
            evidence_fmt=lambda row: (f"{(row['products'] or [{}])[0].get('application_number') or '—'} · "
                                      f"{(row['products'] or [{}])[0].get('application_full_name') or '—'}"
                                      f" ({(row['products'] or [{}])[0].get('application_type') or '—'}, "
                                      f"approved {row['approval_date'] or '—'})"),
            lead="openFDA Orange Book (drug/orangebook, 48,865 rows, the therapeutic-equivalence reference face)", no_cache=no_cache)

    def fda_device_510k(self, *, search=None, limit=20, skip=0, sort=None, execution=None, no_cache=None):
        """healthcare fda_device_510k: device premarket notification 510(k) (openFDA device/510k; applicant finds the company
        (the same name as pma; applicant_name is a documentation illusion); contact (person names, PII) is not returned; the default is decision_date descending)."""
        self._hc_only("fda_device_510k")
        return self._fda_wave10b_face(
            "fda_device_510k", healthcare.fda_devices, "clearance_510k", search=search, limit=limit, skip=skip, sort=sort,
            evidence_fmt=lambda row: (f"{row['k_number'] or '—'} · {row['applicant'] or '—'}"
                                      f" ({row['decision_code'] or '—'}, {row['decision_date'] or '—'})"),
            lead="openFDA device 510(k) clearances (device/510k, 176,466 rows)", no_cache=no_cache)

    def fda_device_pma(self, *, search=None, limit=20, skip=0, sort=None, execution=None, no_cache=None):
        """healthcare fda_device_pma: device premarket approval PMA (openFDA device/pma; applicant finds the company;
        the ao_statement long text and street addresses are not returned; the default is decision_date descending)."""
        self._hc_only("fda_device_pma")
        return self._fda_wave10b_face(
            "fda_device_pma", healthcare.fda_devices, "pma", search=search, limit=limit, skip=skip, sort=sort,
            evidence_fmt=lambda row: (f"{row['pma_number'] or '—'}{row['supplement_number'] or ''} · "
                                      f"{row['applicant'] or '—'} ({row['decision_code'] or '—'}, "
                                      f"{row['decision_date'] or '—'})"),
            lead="openFDA device PMA approvals (device/pma, 12,896 rows)", no_cache=no_cache)

    def fda_device_registrations(self, *, search=None, limit=20, skip=0, sort=None, execution=None, no_cache=None):
        """healthcare fda_device_registrations: the device establishment register (openFDA device/registrationlisting;
        company search is registration.name:\"Firm Name\" (every field lives in the registration.* namespace; the top-level fields all 404, measured);
        us_agent/official_correspondent (person names, PII) are not returned; the default is the registration expiry year descending)."""
        self._hc_only("fda_device_registrations")
        return self._fda_wave10b_face(
            "fda_device_registrations", healthcare.fda_devices, "registrations", search=search, limit=limit, skip=skip, sort=sort,
            evidence_fmt=lambda row: (f"{row['registration_number'] or '—'} · {row['firm_name'] or '—'}"
                                      f" ({row['iso_country_code'] or '—'}, expires {row['reg_expiry_date_year'] or '—'})"),
            lead="openFDA device establishment register (device/registrationlisting, 336,946 rows, quarterly)", no_cache=no_cache)

    def fda_device_classification(self, *, search=None, limit=20, skip=0, sort=None, execution=None, no_cache=None):
        """healthcare fda_device_classification: the device product-code taxonomy face (openFDA device/classification;
        device_name:\"syringe\" finds the category; no date field means no default sort; product_code links to the 510k/pma/recall faces)."""
        self._hc_only("fda_device_classification")
        return self._fda_wave10b_face(
            "fda_device_classification", healthcare.fda_devices, "classification", search=search, limit=limit, skip=skip, sort=sort,
            evidence_fmt=lambda row: (f"{row['product_code'] or '—'} · {row['device_name'] or '—'}"
                                      f" (Class {row['device_class'] or '—'} / "
                                      f"{row['medical_specialty_description'] or '—'}, 21 CFR {row['regulation_number'] or '—'})"),
            lead="openFDA device product-code classification (device/classification)", no_cache=no_cache)


    def tga_artg(self, *, query=None, limit=20, skip=0,
                          execution=None, no_cache=None):
        """healthcare tga_artg: search of the AU ARTG register (the TGA eBS Domino face;
        query=Query is a verbatim all-fields AND channel (a quoted phrase also matches the Sponsor column exactly))."""
        self._hc_only("tga_artg")
        raw = str(query or "").strip() or None
        size = min(max(1, int(limit or 20)), 100)  # SearchView Count measured 100/page (the real upstream limit)
        r = healthcare.tga.search_art_register(None, raw, limit=size, skip=skip,
                                              cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        who = f"search '{raw}'" if raw else "the whole database"
        if result["count"] == 0:
            reason = f"TGA ARTG register: {who} zero hits (zero hits is a legal answer — a quoted phrase matches exactly; if the full name does not match, try all-field words)"
        else:
            more = " — full page, there may be more (continue with --skip)" if result.get("has_more") else ""
            reason = f"TGA ARTG register: {who} {result['count']} hits (this page, self-evident from the Sponsor column){more}"
        quartet = {"source": "raw",
                   "search": result["query"],
                   "upstream": {"SearchView": "", "Query": result["query"], "Count": result["limit_applied"],
                                "charset": "utf-8", **({"Start": result["skip"]} if result["skip"] else {})}}
        return self._flat_env(
            tool="tga_artg",
            input={"query": raw, "limit": result["limit_applied"], "skip": result["skip"]},
            reason=reason, result=result,
            evidence=[{"quote": (f"{row['artg_id'] or '—'} {row['product_name'] or '—'} = "
                                 f"{row['sponsor'] or '—'} ({row['product_type'] or '—'})"),
                       "url": row["doc_url"]}
                      for row in result["rows"][:5]],
            provider_id="tga", metas=[r["_meta"]],
            query=quartet,
        )

    def tga_manufacturers(self, *, state=None, limit=100, execution=None, no_cache=None):
        """healthcare tga_manufacturers: the AU manufacturer licence register (MIS: 444 licences in one full shot + a state filter; limit ≤500 is the upstream single-page hard limit)."""
        self._hc_only("tga_manufacturers")
        size = min(max(1, int(limit or 100)), 500)
        r = healthcare.tga.list_manufacturers(state, limit=size, cache=self._c._cache,
                                             no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        by_state = {}
        for row in result["rows"]:
            by_state[row.get("state") or "—"] = by_state.get(row.get("state") or "—", 0) + 1
        state_note = " / ".join(f"{k} {v}" for k, v in by_state.items())
        return self._flat_env(
            tool="tga_manufacturers",
            input={"state": state, "limit": result["limit_applied"]},
            reason=(f"TGA MIS licence register: {result['total']} licences in the register, {result['count']} returned"
                    + (f" (state filter {state})" if state else "")
                    + (f" — {state_note}" if state_note else "")),
            result=result,
            evidence=[{"quote": f"{row['licence_number'] or '—'} = {row['manufacturer'] or '—'} ({row['state'] or '—'})",
                       "url": "https://www.ebs.tga.gov.au/ebs/ANZTPAR/PublicWeb.nsf/luPortalManufacturers"
                              "?ReadViewEntries&outputformat=json&count=500"}
                      for row in result["rows"][:5]],
            provider_id="tga", metas=[r["_meta"]],
            query={"source": "raw",
                   # state is a local post-filter (not an upstream param): it is echoed in input.state while upstream stays purely what was sent
                   "upstream": {"ReadViewEntries": "", "outputformat": "json", "count": 500, "charset": "utf-8"}},
        )

    # ---------- 0.2.0 flat panel commands (the company main face: source-qualified name + upstream param names + our defaults) ----------
