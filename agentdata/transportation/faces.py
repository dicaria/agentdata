"""transportation faces — flat face-method mixin (0.3.54 founding: seven faces consolidated from
esg/company + the CA TC CCAR pair).

Mixed into the root _Domain (MRO assembly, see client.py); discipline: no __init__, depends only on root
internals (_flat_env/_c/_request…), method names globally unique across domains (a collision
would shadow another domain's face).
"""
from ..errors import SdkError


from .. import transportation  # call via the domain-module path (historical shape, kept to minimize churn)

class TransportationFaces:
    def _transportation_only(self, tool: str):
        if self.name != "transportation":
            raise SdkError("usage_error", detail=f"{tool} is a transportation-domain capability (unavailable on the {self.name} domain)")

    # ---------- 0.3.54 CA TC CCAR live search + per-aircraft record (册 292; the aviation axis opens) ----------

    def ca_ccar_aircraft(self, adet_id, *, execution=None, no_cache=None):
        """transportation ca_ccar_aircraft: CCAR per-aircraft record by ADet id — the four blocks
        (aircraft/manufacturer/registration/registered owner) in one flat dict; a not-found id is a
        legal empty (the ~500k id space has holes)."""
        self._transportation_only("ca_ccar_aircraft")
        r = transportation.ca_ccar.aircraft_raw(adet_id=adet_id,
                                                cache=self._c._cache,
                                                no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        a = result.get("aircraft")
        return self._flat_env(
            tool="ca_ccar_aircraft", input={"adet_id": str(adet_id)},
            reason=(f"CCAR aircraft record: {a['mark']} {a.get('common_name') or '—'} {a.get('model_name') or '—'} "
                    f"(s/n {a.get('serial_number') or '—'}), {a.get('category') or '—'}; manufacturer "
                    f"{a.get('manufacturer') or '—'} ({a.get('country_of_manufacture') or '—'}, "
                    f"{a.get('year_of_manufacture') or '—'}); registration {a.get('type_of_registration') or '—'}, "
                    f"owner since {a.get('owner_registered_since') or '—'}, certificate "
                    f"{a.get('latest_certificate_issued') or '—'}; owner {a.get('owner_name') or '—'}, "
                    f"{a.get('owner_city') or '—'} {a.get('owner_postal_code') or ''}"
                    if a else
                    f"CCAR aircraft record id={adet_id}: not on the register (a legal empty — the ADet id "
                    f"space has holes; take ids from ca_ccar_search rows, never guess)"),
            result=result,
            evidence=[({"quote": f"{a['mark']} — owner {a.get('owner_name') or '—'}, "
                                f"{a.get('owner_address') or '—'}, {a.get('owner_city') or '—'} "
                                f"{a.get('owner_postal_code') or ''}; base {a.get('base_of_operations') or '—'}",
                        "url": f"https://wwwapps.tc.gc.ca/Saf-Sec-Sur/2/CCARCS-RIACC/ADet.aspx?id={adet_id}"}
                      if a else
                      {"quote": f"ADet id {adet_id} renders no record blocks",
                       "url": f"https://wwwapps.tc.gc.ca/Saf-Sec-Sur/2/CCARCS-RIACC/ADet.aspx?id={adet_id}"})],
            provider_id="ca_ccar", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def ca_ccar_search(self, owner=None, mark=None, common_name=None, model_name=None,
                       serial_number=None, *, limit=200, execution=None, no_cache=None):
        """transportation ca_ccar_search: Canadian Civil Aircraft Register contains-search (stateless
        pipe-wrapped GET on the print rendition — no ViewState, no pager; the whole result set ships in
        one page, at least one criterion required)."""
        self._transportation_only("ca_ccar_search")
        r = transportation.ca_ccar.search_raw(owner=owner, mark=mark, common_name=common_name,
                                              model_name=model_name, serial_number=serial_number,
                                              limit=limit,
                                              cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        crit = " + ".join(f"{k}={v}" for k, v in result["params"].items())
        capped = result["total_matched"] > result["limit_applied"]
        return self._flat_env(
            tool="ca_ccar_search", input={"criteria": result["params"], "limit": limit},
            reason=(f"CCAR search {crit}: {result['total_matched']} aircraft on the register"
                    + (" (contains-match; the print rendition carries the whole set)"
                       if not capped else
                       f" — rows capped at {result['limit_applied']} (total_matched carries the true count)")
                    + (f"; e.g. {top['mark']} {top['common_name'] or '—'} {top['model_name'] or '—'} "
                       f"(s/n {top['serial_number'] or '—'}), owner {top['owner'] or '—'} "
                       f"since {top['owner_registered_since'] or '—'}"
                       if top else " — zero hits (a legal empty: no register row contains every criterion)")),
            result=result,
            evidence=[{"quote": f"{x['mark']} — {x['common_name'] or '—'} {x['model_name'] or '—'} "
                                f"(s/n {x['serial_number'] or '—'}): {x['owner'] or '—'} "
                                f"(ADet id {x['adet_id']})",
                       "url": "https://wwwapps.tc.gc.ca/Saf-Sec-Sur/2/CCARCS-RIACC/RchSimp.aspx?lang=eng"}
                      for x in result["rows"][:5]],
            provider_id="ca_ccar", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["upstream_params"]},  # the pipe-wrapped wire truth (r["params"] = the criteria echo)
        )

    # ---------- 0.3.5 port-state emissions/supervision axis (thetis_mrv catalog face + paris_mou four
    # snapshot/search faces; 0.3.54 migrated esg -> transportation with the domain founding) ----------

    def thetis_mrv_datasets(self, *, execution=None, no_cache=None):
        """transportation thetis_mrv_datasets: EU MRV ship emissions-reporting versioned bulk-file catalog (THETIS-MRV
        reporting-periods x downloadable-files combined — the reporting-period x version ledger; XLSX bodies go through the batch pipeline)."""
        self._transportation_only("thetis_mrv_datasets")
        r = transportation.thetis_mrv.datasets_raw(cache=self._c._cache,
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
        """transportation paris_mou_detentions: Paris MoU currently-detained ships snapshot (THETIS getCurrentDetentions;
        a daily-rolling live state — ship IMO / detention port / reporting authority; historical detentions go through the inspections window search)."""
        self._transportation_only("paris_mou_detentions")
        r = transportation.paris_mou.detentions_raw(cache=self._c._cache,
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
        """transportation paris_mou_bans: Paris MoU banned ships register (THETIS getBanShips; the embedded ismCompany is
        flattened into the official ship x ISM management-company edge — the company IMO number is a zero-padded 7-digit string)."""
        self._transportation_only("paris_mou_bans")
        r = transportation.paris_mou.bans_raw(cache=self._c._cache,
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
        """transportation paris_mou_low_performance_companies: Paris MoU low-performance ISM company list
        (THETIS getLowPerformance6MonthsISMCompanies, rolling 6-month window — 100% carry an IMO company number)."""
        self._transportation_only("paris_mou_low_performance_companies")
        r = transportation.paris_mou.low_performance_raw(cache=self._c._cache,
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
        """transportation paris_mou_inspections: Paris MoU historical PSC inspection stream window search (THETIS getPublicInspections
        form-encoded POST; period_min/period_max dd/mm/yyyy window <= 3 years + psc_inspection_regime (1 = the only live
        value, 0.3.20 audit: 0 -> poisoned empty, 2 -> HTTP 500, walled with evidence) + page/start/limit paging +
        ism_company_name/ism_company_imo_number direct company query (IMO padded/unpadded both accepted) — the resume
        window stats ride along)."""
        self._transportation_only("paris_mou_inspections")
        r = transportation.paris_mou.inspections_raw(period_min=period_min, period_max=period_max,
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

    # ---------- 0.3.22 transport-compliance axis (EU air safety list catalog face; the founding-era
    # naming said 'transport compliance' — 0.3.54 made the domain literal) ----------

    def euasl_datasets(self, *, execution=None, no_cache=None):
        """transportation euasl_datasets: EU Air Safety List download catalog (banned/restricted third-country air
        carriers — one XLSX machine-readable master + 24 official-language PDF renditions; the document UUIDs
        rotate on every republication, reconcile against this listing and never guess file names; the binary
        bodies go through the batch pipeline — same posture as eutl/thetis_mrv)."""
        self._transportation_only("euasl_datasets")
        r = transportation.euasl.datasets_raw(cache=self._c._cache,
                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        master = result.get("master")
        langs = len({x["language"] for x in result["rows"] if x.get("language")})
        return self._flat_env(
            tool="euasl_datasets", input={},
            reason=(f"EU Air Safety List download catalog: {result['count']} files across {langs} languages — the machine-readable "
                    f"XLSX master ({master['file_name']}) sorts first, the rest are official-language PDF renditions; "
                    f"Annex A = carriers under an operating ban, Annex B = restrictions/conditions; "
                    f"the document UUIDs rotate on every republication — reconcile against this listing, the binary bodies go through the batch pipeline"
                    if top and master else
                    "EU Air Safety List page rendered without download links (an abnormal state — the Commission reorganization moved the page, not a legal empty"),
            result=result,
            evidence=[{"quote": f"{x['file_name']} ({x['format']}, {x['language']}): {x['download_path']}",
                       "url": "https://transport.ec.europa.eu/transport-themes/eu-air-safety-list_en"}
                      for x in result["rows"][:5]],
            provider_id="euasl", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )


    def us_fmcsa_carriers(self, where=None, *, limit=20, offset=0, order=None,
                          execution=None, no_cache=None):
        """transportation us_fmcsa_carriers: FMCSA Motor Carrier Management Information Company
        Census (data.transportation.gov Socrata az4n-8mr2; where → $where raw SoQL verbatim
        channel; limit/offset/order mirrored by name). The full-history US carrier universe —
        active AND out-of-service, 4,528,322 rows live 2026-11-09 (the ~400k audit figure was
        the active face). dot_number hard key (US transport-compliance universe join key),
        status_code lifecycle, dun_bradstreet_no = the rare official DUNS cross-key (mind its
        "0" sentinels), phy_*/carrier_mailing_* dual address blocks, company_officer_1/2
        verbatim, fleet trio + mcs150 mileage + hm_ind + crgo_* cargo flags. Catalog advertises
        ~58 columns but Socrata omits null fields per row — a populated row ships 53 keys;
        unrated carriers simply lack safety_rating (rides in the view, appears only when set)."""
        self._transportation_only("us_fmcsa_carriers")
        r = transportation.us_fmcsa.carriers_raw(where, limit=limit, offset=offset, order=order,
                                          cache=self._c._cache,
                                          no_cache=no_cache if no_cache is not None else self._c.no_cache)
        res = {k: v for k, v in r.items() if k != "_meta"}
        rows = res["rows"]
        if rows:
            x0 = rows[0]
            reason = (f"FMCSA carrier census: {len(rows)} rows returned (from offset={offset}; Socrata echoes no total)"
                      f" — dot_number key (sample #{x0.get('dot_number') or '—'},"
                      f" {x0.get('legal_name') or '—'}"
                      f" [{x0.get('status_code') or '—'}],"
                      f" {x0.get('phy_city') or '—'}, {x0.get('phy_state') or '—'},"
                      f" officers {x0.get('company_officer_1') or '—'}"
                      + (f" / {x0.get('company_officer_2')}" if x0.get("company_officer_2") else "")
                      + f"; {len(x0)} keys on this row — Socrata omits null fields per row)"
                      f"; corpus 4,528,322 active+historical (live count 2026-11-09);"
                      " dun_bradstreet_no = the rare official DUNS cross-key")
        else:
            reason = ("FMCSA carrier census: 0 rows — the where filter matched nothing or offset is past the end; both are "
                      "legal answers (not errors); deterministic forms: dot_number='963305' exact, "
                      "upper(legal_name) like '%SCHNEIDER%'")
        ev = [{"quote": f"DOT {x.get('dot_number') or '—'} — {x.get('legal_name') or '—'}"
                        f" ({x.get('phy_city') or '—'}, {x.get('phy_state') or '—'};"
                        f" status {x.get('status_code') or '—'},"
                        f" carrier_operation {x.get('carrier_operation') or '—'},"
                        f" {x.get('truck_units') or '—'} trucks/{x.get('power_units') or '—'} power/{x.get('bus_units') or '—'} bus"
                        + (f", DUNS {x.get('dun_bradstreet_no')}" if x.get("dun_bradstreet_no") not in (None, "0") else "") + ")",
               "url": "https://data.transportation.gov/resource/az4n-8mr2.json"}
              for x in rows[:3] if x.get("dot_number")]
        return self._flat_env(tool="us_fmcsa_carriers",
                              input={"where": where, "limit": limit, "offset": offset, "order": order},
                              reason=reason, result=res, evidence=ev, provider_id="us_fmcsa",
                              metas=[r["_meta"]],
                              query={"source": "raw", "upstream": r["params"]})
