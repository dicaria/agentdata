"""esg faces — flat face-method mixin (0.2.6 per-domain split, moved out of client.py _Domain).

Mixed into the root _Domain (MRO assembly, see client.py); discipline: no __init__, depends only on root
internals (_flat_env/_c/_request…), method names globally unique across domains (a collision
would shadow another domain's face).
"""
from ..errors import SdkError


from .. import esg  # call via the domain-module path (historical shape, kept to minimize churn)

class EsgFaces:
    def _esg_only(self, tool: str):
        if self.name != "esg":
            raise SdkError("usage_error", detail=f"{tool} is an esg-domain capability (unavailable on the {self.name} domain)")

    def eiti_companies(self, *, company_name__like=None, name=None, size=10,
                       execution=None, no_cache=None):
        """esg eiti_companies: extractives filer company candidates (EITI Datasette view_companies;
        company_name__like verbatim (%/_ yours to manage) XOR name sugar (%contains%) — same slot)."""
        self._esg_only("eiti_companies")
        deps, assembled_from = [], None
        raw_like = str(company_name__like or "").strip() or None
        nm = str(name or "").strip() or None
        if raw_like and nm:
            raise SdkError("usage_error", provider="eiti",
                           detail="company_name__like (raw channel: %/_ yours to manage) and name (sugar: %contains%) share one slot and are mutually exclusive — give only one")
        if not raw_like and not nm:
            raise SdkError("usage_error", provider="eiti",
                           detail="eiti_companies requires at least one of company_name__like or name")
        if nm:
            assembled_from = {"name": nm}
            deps.append("name sugar assembles company_name__like=%…% (contains) — retained sugar (not deprecated); "
                        "the raw channel is company_name__like (%/_ metacharacters yours to manage)")
            raw_like = f"%{nm}%"
        r = esg.eiti.companies_raw(raw_like, size=size, cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["candidates"] or [None])[0]
        matched = esg.eiti.total_display(result.get("total_matches"), result.get("total_matches_capped"))
        quartet = {"source": "assembled" if assembled_from else "raw", "upstream": r["params"]}
        if assembled_from:
            quartet["assembled_from"] = assembled_from
        return self._flat_env(
            tool="eiti_companies",
            input={"company_name__like": company_name__like, "name": nm,
                   "size": result["limit_applied"]},
            reason=(f"EITI name search: {len(result['candidates'])} candidates on this page / {matched} total upstream matches, "
                    f"top {top['company_name'] or '—'}"
                    f" ({top['hq_country'] or '—'}, reported {top['first_year_reported'] or '?'}–{top['last_year_reported'] or '?'}) — candidates are not authoritative normalization"
                    if top else f"EITI name search zero hits: not in the extractives filer universe (EITI has 10,200 companies; an empty result is a legal answer)"),
            result=result,
            evidence=[{"quote": f"{c['company_name'] or '—'} ({c['hq_country'] or '—'}, {c['sectors'] or '—'})",
                       "url": "https://eiti-database.eiti.org/eiti_database/view_companies.json"}
                      for c in result["candidates"][:5]],
            provider_id="eiti", metas=[r["_meta"]],
            query=quartet, deprecations=deps or None,
        )

    def eiti_payments(self, *, eiti_id_company__exact=None, eiti_id=None,
                      company_name__like=None, name=None, size=50,
                      execution=None, no_cache=None):
        """esg eiti_payments: company->government payment rows (EITI view_payments_detailed;
        id channel eiti_id_company__exact verbatim XOR eiti_id sugar (adds the eiti_id_company: prefix),
        name channel company_name__like verbatim XOR name sugar (%contains%) — the two channels may combine, XOR within each slot)."""
        self._esg_only("eiti_payments")
        deps, assembled_from = [], {}
        raw_eid = str(eiti_id_company__exact or "").strip() or None
        raw_like = str(company_name__like or "").strip() or None
        eid = str(eiti_id or "").strip() or None
        nm = str(name or "").strip() or None
        if raw_eid and eid:
            raise SdkError("usage_error", provider="eiti",
                           detail="eiti_id_company__exact (raw channel) and eiti_id (sugar: auto-adds the eiti_id_company: prefix) share one slot and are mutually exclusive — give only one")
        if raw_like and nm:
            raise SdkError("usage_error", provider="eiti",
                           detail="company_name__like (raw channel) and name (sugar: %contains%) share one slot and are mutually exclusive — give only one")
        if not (raw_eid or raw_like or eid or nm):
            raise SdkError("usage_error", provider="eiti",
                           detail="eiti_payments requires at least one of the id channel (eiti_id_company__exact / eiti_id) "
                                  "or the name channel (company_name__like / name)"
                                  "(local safety wall: a bare scan of all 104,484 rows is served by the batch pipeline)")
        if eid:
            assembled_from["eiti_id"] = eid
            deps.append("eiti_id sugar assembles eiti_id_company__exact=eiti_id_company:<UUID> (official values carry the prefix) — "
                        "retained sugar (not deprecated); the raw channel is eiti_id_company__exact")
            raw_eid = esg.eiti._norm_id(eid)
        if nm:
            assembled_from["name"] = nm
            deps.append("name sugar assembles company_name__like=%…% (contains) — retained sugar (not deprecated); "
                        "the raw channel is company_name__like")
            raw_like = f"%{nm}%"
        r = esg.eiti.payments_raw(eiti_id_company__exact=raw_eid, company_name__like=raw_like,
                                        size=size, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        countries = sorted({p["country_iso3"] for p in result["rows"] if p["country_iso3"]})
        usd = sum(p["payment_value_usd"] for p in result["rows"]
                  if isinstance(p["payment_value_usd"], (int, float)))
        total = esg.eiti.total_display(result.get("total_rows"), result.get("total_rows_capped"))
        quartet = {"source": "assembled" if assembled_from else "raw", "upstream": r["params"]}
        if assembled_from:
            quartet["assembled_from"] = assembled_from
        return self._flat_env(
            tool="eiti_payments",
            input={"eiti_id_company__exact": eiti_id_company__exact, "eiti_id": eid,
                   "company_name__like": company_name__like, "name": nm,
                   "size": result["limit_applied"]},
            reason=(f"EITI payments face: {len(result['rows'])} rows on this page / {total} total upstream rows"
                    f" ({'/'.join(countries) or '—'}; USD ~${round(usd):,} is this page's subtotal, not the full total; GFS-classified figures are comparable across batches)"
                    if result["rows"] else "EITI payments face zero hits (an empty result is a legal answer — not a filer, or the name did not match)"),
            result=result,
            evidence=[{"quote": f"{p['company_name'] or '—'} {p['year'] or '—'} -> {p['gov_entity'] or '—'}: "
                                f"{p['revenue_stream'] or '—'}" + (f" (${p['payment_value_usd']})" if p["payment_value_usd"] else ""),
                       "url": "https://eiti-database.eiti.org/eiti_database/view_payments_detailed"}
                      for p in result["rows"][:5]],
            provider_id="eiti", metas=[r["_meta"]],
            query=quartet, deprecations=deps or None,
        )

    def climatetrace_owners(self, *, name, limit=10, offset=None, execution=None, no_cache=None):
        """esg climatetrace_owners: emissions-owner candidates (Climate TRACE v7 owners;
        name/limit/offset straight through under upstream names — zero hits = empty candidates, the upstream 404 JSON is already mapped to a legal empty)."""
        self._esg_only("climatetrace_owners")
        v = str(name or "").strip()
        if not v:
            raise SdkError("usage_error", provider="climatetrace",
                           detail="climatetrace_owners requires name (company name, upstream param name)")
        r = esg.climatetrace.owners_raw(v, limit=limit, offset=offset,
                                              cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["candidates"] or [None])[0]
        return self._flat_env(
            tool="climatetrace_owners", input={"name": v, "limit": result["limit_applied"],
                                               "offset": offset},
            reason=(f"Climate TRACE owner search: {len(result['candidates'])} candidates, top {top['owner_name'] or '—'}"
                    f" ({top['trace_owner_id'] or '—'}) — candidates are not authoritative normalization, the rows face trusts owner_ids; "
                    f"ordering is unstable across limits (measured 2026-10-23), fetch enough in one go"
                    if top else f"Climate TRACE zero hits: '{v}' is not in the emissions-owner universe"
                                f" (point-source sectors such as oil & gas, mining, heavy industry, power; an empty result is a legal answer)"),
            result=result,
            evidence=[{"quote": f"{c['trace_owner_id'] or '—'} = {c['owner_name'] or '—'}",
                       "url": f"https://api.climatetrace.org/v7/owners?name={v}"}
                      for c in result["candidates"][:5]],
            provider_id="climatetrace", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def climatetrace_sources(self, *, owner_ids=None, owner_name=None, year=None, gas=None,
                             limit=50, offset=None, sectors=None, subsectors=None,
                             gadm_id=None, city_id=None, country_group=None, continent=None,
                             execution=None, no_cache=None):
        """esg climatetrace_sources: emissions-owner -> facility/aggregate emission rows (Climate TRACE v7 sources;
        owner_ids -> ownerIds verbatim (comma-joined = union with dedup) XOR owner_name sugar (resolves the first
        candidate) — two channels, one of the two required; year has no local wall for out-of-window values (upstream
        returns null, not an error); gas straight through under its own name — a non-co2e basis switches the row key
        to emissions_quantity.
        0.2.9 audit parameter expansion (2026-10-28 openapi + live probing): offset paging, sectors closed set
        validated locally (invalid values make the upstream silently return the whole corpus = a false negative),
        subsectors pass-through (upstream 400 self-validates), four location params gadm_id/city_id/
        country_group/continent pass-through (mutual exclusion upstream-proven by a 400); at least one of
        owner_ids / a filter param (soft wall against bare corpus scans)."""
        self._esg_only("climatetrace_sources")
        deps, assembled_from = [], None
        oids = str(owner_ids or "").strip() or None
        nm = str(owner_name or "").strip() or None
        if oids and nm:
            raise SdkError("usage_error", provider="climatetrace",
                           detail="owner_ids (raw channel: ownerIds comma union) and owner_name (sugar: resolves the first candidate) are mutually exclusive — give only one")
        has_filter = any(x not in (None, "") for x in
                         (sectors, subsectors, gadm_id, city_id, country_group, continent))
        if not oids and not nm and not has_filter:
            raise SdkError("usage_error", provider="climatetrace",
                           detail="climatetrace_sources requires at least one of owner_ids (E key), owner_name (company name), "
                                  "or a filter param (sectors/subsectors/gadm_id/city_id/country_group/continent)"
                                  " — a bare whole-corpus scan goes through the batch pipeline service "
                                  "(upstream allows it, but this face's politeness tier intercepts bulk corpus scans)")
        cache, nc = self._c._cache, self._c.no_cache if no_cache is None else bool(no_cache)
        metas = []
        if nm and not oids:
            s = esg.climatetrace.owners_raw(nm, limit=5, cache=cache, no_cache=nc)
            metas.append(s["_meta"])
            if not s["candidates"]:
                return self._flat_env(
                    tool="climatetrace_sources", input={"owner_ids": oids, "owner_name": nm,
                                                        "year": year, "gas": gas, "limit": limit,
                                                        "offset": offset, "sectors": sectors,
                                                        "subsectors": subsectors, "gadm_id": gadm_id,
                                                        "city_id": city_id, "country_group": country_group,
                                                        "continent": continent},
                    reason=(f"Climate TRACE emissions face zero hits: owner name '{nm}' has no candidates"
                            f" (an empty result is a legal answer — not a point-source-sector owner; use the owner_ids raw channel on the rows face)"),
                    result={"rows": [], "count": 0, "resolved_owner": None,
                            "year": year, "gas": gas or "co2e_100yr", "matched_on": None},
                    evidence=[], provider_id="climatetrace", metas=metas,
                    query={"source": "assembled", "assembled_from": {"owner_name": nm},
                           "upstream": s["params"]},
                    deprecations=["owner_name sugar resolves the first owners candidate (not authoritative normalization)",
                                  "— the raw channel is owner_ids"],
                )
            oids = s["candidates"][0]["trace_owner_id"]
            assembled_from = {"owner_name": nm, "resolved_first_candidate": oids}
            deps.append("owner_name sugar resolves the first owners candidate (not authoritative normalization) — the raw channel is owner_ids")
        r = esg.climatetrace.sources_raw(oids, year=year, gas=gas, limit=limit, offset=offset,
                                         sectors=sectors, subsectors=subsectors,
                                         gadm_id=gadm_id, city_id=city_id,
                                         country_group=country_group, continent=continent,
                                         cache=cache, no_cache=nc)
        metas.append(r["_meta"])
        result = {k: x for k, x in r.items() if k != "_meta"}
        countries = sorted({x["country"] for x in result["rows"] if x["country"]})
        is_tco2e = result.get("gas") == "co2e_100yr"
        rkey = "emissions_tco2e" if is_tco2e else "emissions_quantity"
        skey = f"{rkey}_sum"
        unit = "tCO2e (co2e_100yr basis)" if is_tco2e \
            else f"{result.get('gas')} native unit (not tCO2e — row key emissions_quantity)"
        yr_note = "" if (result["year"] or 0) >= 2021 else \
            f"; year={result['year']} is outside the data window (2021 onward) — upstream returns empty, not an error (measured 2026-10-23)"
        quartet = {"source": "assembled" if assembled_from else "raw", "upstream": r["params"]}
        if assembled_from:
            quartet["assembled_from"] = assembled_from
        return self._flat_env(
            tool="climatetrace_sources",
            input={"owner_ids": owner_ids, "owner_name": owner_name,
                   "year": result["year"], "gas": result.get("gas"), "limit": r["params"]["limit"],
                   "offset": offset, "sectors": sectors, "subsectors": subsectors,
                   "gadm_id": gadm_id, "city_id": city_id,
                   "country_group": country_group, "continent": continent},
            reason=(f"Climate TRACE emissions face: {len(result['rows'])} sources for {result['year']}"
                    f" totalling {result[skey]:,.2f} {unit}"
                    f" ({'/'.join(countries[:3]) or '—'}{'…' if len(countries) > 3 else ''}){yr_note}"
                    if result["rows"] else
                    f"Climate TRACE emissions face zero hits (an empty result is a legal answer — not a point-source-sector "
                    f"owner, or no data for that year; aggregate surfaces have source_type != point-source){yr_note}"),
            result=result,
            evidence=[{"quote": f"{x['name'] or '—'} ({x['country'] or '—'}, {x['sector'] or '—'}): "
                                + (f"{round(x[rkey]):,}" if x.get(rkey) is not None else "—")
                                + f" ({x['gas'] or ''}) {x['year'] or ''}",
                       "url": "https://api.climatetrace.org/v7/sources"}
                      for x in result["rows"][:5]],
            provider_id="climatetrace", metas=metas,
            query=quartet, deprecations=deps or None,
        )

    def eutl_datasets(self, *, execution=None, no_cache=None):
        """esg eutl_datasets: EU carbon registry official bulk-download catalog (EUTL data-download;
        zero upstream params, the whole catalog in one response — two families: Azure daily extracts x climate.ec.europa.eu yearly files; the file bodies go through the batch pipeline)."""
        self._esg_only("eutl_datasets")
        r = esg.eutl.datasets_raw(cache=self._c._cache,
                                  no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        azure = [x for x in result["rows"] if x["cadence"] == "daily"]
        yearly = [x for x in result["rows"] if x["cadence"] == "yearly"]
        static = [x for x in result["rows"] if x["cadence"] == "static"]
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="eutl_datasets", input={},
            reason=(f"EUTL official bulk-download catalog: {result['count']} files — {len(azure)} Azure daily extracts"
                    f" (accounts/operators/holdings csv.gz) + {len(yearly)} European Commission yearly files"
                    f" (compliance/verified emissions 2021-2025) + {len(static)} transactions file — a coordinates face, the file bodies go through the batch pipeline"
                    if result["rows"] else "EUTL catalog empty (the portal has no files — an abnormal state, not the legal-empty semantics)"),
            result=result,
            evidence=[{"quote": f"{x['name'] or '—'} ({x['cadence']}): {x['url'] or '—'}",
                       "url": "https://union-registry-data.ec.europa.eu/api/data-download"}
                      for x in result["rows"][:5]],
            provider_id="eutl", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def epa_frs_facilities(self, *, registry_id=None, primary_name=None, state_code=None,
                           city_name=None, start=0, size=50, execution=None, no_cache=None):
        """esg epa_frs_facilities: FRS facility master point query (Envirofacts efservice frs_facility_site;
        four filter columns under upstream names (all `=` exact, combinable AND) + start/size closed-interval paging — born flat, zero sugar)."""
        self._esg_only("epa_frs_facilities")
        r = esg.epa_frs.facilities_raw(registry_id=registry_id, primary_name=primary_name,
                                       state_code=state_code, city_name=city_name,
                                       start=start, size=size, cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k not in ("_meta", "_count_meta")}
        top = (result["rows"] or [None])[0]
        total = result.get("total_matches")
        total_s = f"{total:,}" if isinstance(total, int) else "?"
        exact_note = ("; primary_name is an exact match (the upstream contains/~ operators silently return 0 — fuzzy facility names go through the ECHO face)"
                      if primary_name else "")
        return self._flat_env(
            tool="epa_frs_facilities",
            input={"registry_id": registry_id, "primary_name": primary_name,
                   "state_code": (state_code or "").strip().upper() if state_code else None,
                   "city_name": city_name, "start": result["offset"],
                   "size": result["limit_applied"]},
            reason=(f"FRS facility master registry: {result['count']} rows on this page / {total_s} total matches"
                    f", top {top['primary_name'] or '—'} ({top['registry_id'] or '—'}, "
                    f"{top['std_full_address'] or top['location_address'] or '—'}) — "
                    f"registry_id is the authoritative ECHO/TRI/GHGRP convergence key{exact_note}"
                    if top else f"FRS facility master registry zero hits: 0 rows on this page / {total_s} total matches"
                                f" (an empty result is a legal answer — the name did not match, or the state has no facilities){exact_note}"),
            result=result,
            evidence=[{"quote": f"{x['registry_id'] or '—'} = {x['primary_name'] or '—'}"
                                f" ({x['std_full_address'] or x['location_address'] or '—'})",
                       "url": "https://data.epa.gov/efservice/frs_facility_site"}
                      for x in result["rows"][:5]],
            provider_id="epa_frs", metas=[r["_meta"], r["_count_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- 0.3.5 port-state emissions/supervision axis (thetis_mrv catalog face + paris_mou four snapshot/search faces) ----------

    def thetis_mrv_datasets(self, *, execution=None, no_cache=None):
        """esg thetis_mrv_datasets: EU MRV ship emissions-reporting versioned bulk-file catalog (THETIS-MRV
        reporting-periods x downloadable-files combined — the reporting-period x version ledger; XLSX bodies go through the batch pipeline)."""
        self._esg_only("thetis_mrv_datasets")
        r = esg.thetis_mrv.datasets_raw(cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        periods = result.get("reporting_periods") or []
        return self._flat_env(
            tool="thetis_mrv_datasets", input={},
            reason=(f"THETIS-MRV emissions-reporting file catalog: {len(periods)} reporting periods ({periods[-1] if periods else '—'}-"
                    f"{periods[0] if periods else '—'}) x {result['count']} versioned publication files — newest "
                    f"{top['reporting_period']} v{top['version']} (regenerated {top['generation_date']}); "
                    f"the version ledger rolls in jumps, reconcile harvests against the listing and never guess file names; XLSX bodies go through the batch pipeline"
                    if top else "THETIS-MRV version ledger empty (the portal has no files — an abnormal state, not the legal-empty semantics)"),
            result=result,
            evidence=[{"quote": f"{x['reporting_period']} v{x['version']} ({x['generation_date']}): {x['file_name']}",
                       "url": "https://mrv.emsa.europa.eu/api/public-emission-report/downloadable-files"}
                      for x in result["rows"][:5]],
            provider_id="thetis_mrv", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def paris_mou_detentions(self, *, execution=None, no_cache=None):
        """esg paris_mou_detentions: Paris MoU currently-detained ships snapshot (THETIS getCurrentDetentions;
        a daily-rolling live state — ship IMO / detention port / reporting authority; historical detentions go through the inspections window search)."""
        self._esg_only("paris_mou_detentions")
        r = esg.paris_mou.detentions_raw(cache=self._c._cache,
                                         no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="paris_mou_detentions", input={},
            reason=(f"Paris MoU current detentions: {result['count']} ships detained (e.g. {top['ship_name']} / IMO "
                    f"{top['imo_number']}, detained {top['detention_date']} at {top['detention_country_code']} "
                    f"{top['detention_port']}) — a live-state snapshot rolling daily; the ship IMO number is the asset key"
                    if top else "Paris MoU currently zero detentions (a legal empty for the live state — a clean-list day)"),
            result=result,
            evidence=[{"quote": f"{x['ship_name']} (IMO {x['imo_number']}, {x['flag_code']}, "
                                f"{x['ship_type'] or '—'}): detained {x['detention_date']} at "
                                f"{x['detention_country_code'] or '—'} {x['detention_port'] or '—'}",
                       "url": "https://portal.emsa.europa.eu/o/portlet-public/rest/detention/getCurrentDetentions.json"}
                      for x in result["rows"][:5]],
            provider_id="paris_mou", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def paris_mou_bans(self, *, execution=None, no_cache=None):
        """esg paris_mou_bans: Paris MoU banned ships register (THETIS getBanShips; the embedded ismCompany is
        flattened into the official ship x ISM management-company edge — the company IMO number is a zero-padded 7-digit string)."""
        self._esg_only("paris_mou_bans")
        r = esg.paris_mou.bans_raw(cache=self._c._cache,
                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        with_co = [x for x in result["rows"] if x.get("company_imo_number")]
        return self._flat_env(
            tool="paris_mou_bans", input={},
            reason=(f"Paris MoU bans register: {result['count']} rows, {len(with_co)} of which carry an ISM management-company "
                    f"IMO number (e.g. {top['ship_name']} / IMO {top['imo_number']} -> {top['company_name']} / "
                    f"company IMO {top['company_imo_number']}, banned {top['ban_date']}) — "
                    f"the official ship x management-company edge emitted directly; the company key can be matched against shipping-company records"
                    if top else "Paris MoU bans register empty (a legal empty for the live state)"),
            result=result,
            evidence=[{"quote": f"{x['ship_name']} (IMO {x['imo_number']}, {x['flag_code']}): "
                                f"{x['ban_date']} {x['ban_occurrence'] or ''} ban"
                                f" ({x['banning_authority'] or '—'}) -> {x['company_name'] or '—'}"
                                f" (company IMO {x['company_imo_number'] or 'none'})",
                       "url": "https://portal.emsa.europa.eu/o/portlet-public/rest/ban/getBanShips.json"}
                      for x in result["rows"][:5]],
            provider_id="paris_mou", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def paris_mou_low_performance_companies(self, *, execution=None, no_cache=None):
        """esg paris_mou_low_performance_companies: Paris MoU low-performance ISM company list
        (THETIS getLowPerformance6MonthsISMCompanies, rolling 6-month window — 100% carry an IMO company number)."""
        self._esg_only("paris_mou_low_performance_companies")
        r = esg.paris_mou.low_performance_raw(cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        countries = len({x["country_code"] for x in result["rows"] if x.get("country_code")})
        return self._flat_env(
            tool="paris_mou_low_performance_companies", input={},
            reason=(f"Paris MoU low-performance ISM companies: {result['count']} companies across {countries} countries/regions, 100% carrying an IMO "
                    f"company number (e.g. {top['name']} / IMO {top['imo_number']}, {top['country_name']}, "
                    f"{top['performance']}, listed {top['effect_date']}) — a rolling 6-month-window company-risk attribute list"
                    if top else "Paris MoU low-performance list empty (a legal empty for the rolling window)"),
            result=result,
            evidence=[{"quote": f"{x['name']} (IMO {x['imo_number']}, {x['country_name']}, "
                                f"{x['performance']}, listed {x['effect_date']})",
                       "url": "https://portal.emsa.europa.eu/o/portlet-public/rest/companyperformance/getLowPerformance6MonthsISMCompanies.json"}
                      for x in result["rows"][:5]],
            provider_id="paris_mou", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def paris_mou_inspections(self, *, period_min, period_max, psc_inspection_regime=1,
                              page=1, start=0, limit=50,
                              ism_company_name=None, ism_company_imo_number=None,
                              execution=None, no_cache=None):
        """esg paris_mou_inspections: Paris MoU historical PSC inspection stream window search (THETIS getPublicInspections
        form-encoded POST; period_min/period_max dd/mm/yyyy window <= 3 years + page/start/limit paging +
        ism_company_name/ism_company_imo_number direct company query — the resume window stats ride along)."""
        self._esg_only("paris_mou_inspections")
        r = esg.paris_mou.inspections_raw(period_min=period_min, period_max=period_max,
                                          psc_inspection_regime=psc_inspection_regime,
                                          page=page, start=start, limit=limit,
                                          ism_company_name=ism_company_name,
                                          ism_company_imo_number=ism_company_imo_number,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        total = result.get("total")
        total_s = f"{total:,}" if isinstance(total, int) else "?"
        resume = result.get("resume") or {}
        resume_s = (f"window stats: {resume.get('inspections')} inspections/{resume.get('ships')} ships/"
                    f"{resume.get('detentions')} detentions/{resume.get('ism_deficiencies')} ISM deficiencies"
                    if resume else "no window stats")
        co_filter = (f"; company filter {ism_company_imo_number or ism_company_name}"
                     if (ism_company_imo_number or ism_company_name) else "")
        return self._flat_env(
            tool="paris_mou_inspections",
            input={"period_min": period_min, "period_max": period_max,
                   "psc_inspection_regime": r["params"]["pscInspectionRegime"],
                   "page": result["paging"]["page"], "start": result["paging"]["start"],
                   "limit": result["paging"]["limit"],
                   "ism_company_name": ism_company_name,
                   "ism_company_imo_number": ism_company_imo_number},
            reason=(f"Paris MoU historical inspection stream: window {period_min}–{period_max}, {result['count']} rows on this page / whole window "
                    f"{total_s}{co_filter} — {resume_s}; first row {top['ship_name']} (IMO {top['imo_number']}) "
                    f"{top['inspection_date']} @{top['member_state']} {top['port_name']} "
                    f"{top['ndeficiencies']} deficiencies — the id key allows a per-inspection deep dive (getInspectionDetail)"
                    if top else f"Paris MoU historical inspection stream zero hits: window {period_min}–{period_max}, whole window "
                                f"{total_s} rows{co_filter} (an empty window or a too-narrow filter = a legal empty) — {resume_s}"),
            result=result,
            evidence=[{"quote": f"{x['ship_name']} (IMO {x['imo_number']}, {x['flag_code']}): "
                                f"{x['inspection_date']} @{x['member_state']} {x['port_name']} — "
                                f"{x['ndeficiencies']} deficiencies ({x['inspection_type'] or '—'})",
                       "url": "https://portal.emsa.europa.eu/o/portlet-public/rest/inspection/getPublicInspections.json"}
                      for x in result["rows"][:5]],
            provider_id="paris_mou", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- 0.2.0 flat face commands (legal: source-qualified names + upstream param names verbatim + our defaults) ----------
