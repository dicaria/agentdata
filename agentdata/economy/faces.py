"""economy faces — flat face-method mixin (the eighth domain, stood up in 0.3.23).

Mixed into the root _Domain (MRO assembly, see client.py); discipline: no __init__, depends only
on root internals (_flat_env/_c/_request…), method names globally unique across domains (a
collision would shadow another domain's face).

The economy domain is the country-level denominator layer: macro indicators, reference rates,
official statistics and the trade mirror — the numbers the other five domains normalise against
(TAM denominators, amount conversion, income-band buyer screens). The subject is the country
(ISO code), never the company: these faces emit no company fact and occupy no rec_type.
"""
from ..errors import SdkError


from .. import economy  # call via the domain-module path (historical shape, kept to minimize churn)

class EconomyFaces:
    def _economy_only(self, tool: str):
        if self.name != "economy":
            raise SdkError("usage_error", detail=f"{tool} is an economy-domain capability (unavailable on the {self.name} domain)")

    # ---------- World Bank WDI (global, keyless) ----------

    def wb_wdi_values(self, *, country=None, indicator=None, date=None, per_page=100,
                      execution=None, no_cache=None):
        """economy wb_wdi_values: World Bank WDI indicator values for one or more countries
        (/v2/country/{country}/indicator/{indicator}; country = ISO3, several codes joined by
        ';'; indicator = ONE WDI code — the upstream rejects several codes in one call
        ("120 Invalid value"); date = "YYYY" or "YYYY:YYYY"; a missing observation is null)."""
        self._economy_only("wb_wdi_values")
        r = economy.wb.wdi_values_raw(country, indicator, date=date, per_page=per_page,
                                       cache=self._c._cache,
                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="wb_wdi_values",
            input={"country": country, "indicator": indicator, "date": date,
                   "per_page": r["params"]["per_page"]},
            reason=(f"World Bank WDI: {r['params']['country']} × {r['params']['indicator']} — "
                    f"{result['count']} rows"
                    + (f" (total {result['total']})" if result.get("total") is not None else "")
                    + (f", last updated {result['last_updated']}" if result.get("last_updated") else "")
                    + (f", top {top['country_iso3']} {top['year']} = {top['value']}" if top else ", zero rows")),
            result=result,
            evidence=[{"quote": f"{x['country_iso3']} {x['year']} = {x['value']} ({x['indicator_name'] or x['indicator_code']})",
                       "url": f"https://data.worldbank.org/indicator/{x['indicator_code']}?locations={x['country_iso3']}"}
                      for x in result["rows"][:5]],
            provider_id="wb", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def wb_wdi_indicators(self, *, source=2, page=1, per_page=500, search=None,
                          execution=None, no_cache=None):
        """economy wb_wdi_indicators: the World Bank indicator catalog (/v2/indicator;
        source = the World Bank source id, 2 = WDI — without it the catalog is every source at
        once (29,544 rows); search = a LOCAL keyword scan over the returned page, not an
        upstream filter)."""
        self._economy_only("wb_wdi_indicators")
        r = economy.wb.wdi_indicators_raw(source=source, page=page, per_page=per_page,
                                           search=search, cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="wb_wdi_indicators",
            input={"source": r["params"]["source"], "page": r["params"]["page"],
                   "per_page": r["params"]["per_page"], "search": search},
            reason=(f"World Bank indicator catalog (source {r['params']['source']}) — "
                    f"{result['total']:,} indicators in total, {result['count']} on this page"
                    + (f", top {top['indicator_code']} = {top['name']}" if top else "")
                    + (" — the keyword filter is a local scan over this page" if search else "")),
            result=result,
            evidence=[{"quote": f"{x['indicator_code']} = {x['name']} ({x['source_name']})",
                       "url": f"https://data.worldbank.org/indicator/{x['indicator_code']}"}
                      for x in result["rows"][:5]],
            provider_id="wb", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def wb_countries(self, *, page=1, per_page=100, execution=None, no_cache=None):
        """economy wb_countries: the World Bank country reference (/v2/country — ISO3 / ISO2 /
        region / income level / lending type; the income band is the buyer-screen dimension
        and the 296 entries include the aggregate regions)."""
        self._economy_only("wb_countries")
        r = economy.wb.countries_raw(page=page, per_page=per_page, cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="wb_countries",
            input={"page": r["params"]["page"], "per_page": r["params"]["per_page"]},
            reason=(f"World Bank country reference — {result['total']} entries in total, "
                    f"{result['count']} on this page"
                    + (f", top {top['iso3']} {top['name']} ({top['income_level']})" if top else "")),
            result=result,
            evidence=[{"quote": f"{x['iso3']} {x['name']} ({x['income_level']}, {x['region_name']})",
                       "url": f"https://data.worldbank.org/country/{x['iso3']}"}
                      for x in result["rows"][:5]],
            provider_id="wb", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def wb_ids_indicators(self, *, page=1, per_page=600, search=None,
                          execution=None, no_cache=None):
        """economy wb_ids_indicators: the World Bank International Debt Statistics catalog
        (/v2/indicator with source pinned to 6 = IDS — 577 indicators in seven debt families:
        DOD stocks / INT interest / AMT disbursements / DIS / NFL net flows / NTR / TDS service
        plus the balance-of-payments mirrors; the per-page default 600 holds the whole catalog
        in one page). The VALUES of the DT.* codes are served by wb_wdi_values WITHOUT a source
        parameter — the value endpoint breaks with source=6 ("175 indicator was not found";
        the API silently falls back to sourceid 2)."""
        self._economy_only("wb_ids_indicators")
        r = economy.wb.wdi_indicators_raw(source=6, page=page, per_page=per_page,
                                          search=search, cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="wb_ids_indicators",
            input={"page": r["params"]["page"], "per_page": r["params"]["per_page"],
                   "search": search},
            reason=(f"World Bank International Debt Statistics catalog (source 6) — "
                    f"{result['total']} indicators in total, {result['count']} on this page"
                    + (f", top {top['indicator_code']} = {top['name']}" if top else "")
                    + (" — the keyword filter is a local scan over this page" if search else "")
                    + " — the DT.* values are served by wb_wdi_values WITHOUT --source"),
            result=result,
            evidence=[{"quote": f"{x['indicator_code']} = {x['name']}",
                       "url": f"https://data.worldbank.org/indicator/{x['indicator_code']}"}
                      for x in result["rows"][:5]],
            provider_id="wb", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- Eurostat (EU) ----------

    def eurostat_table(self, *, table=None, geo=None, time=None, dims=None, since=None,
                       until=None, lang="EN", execution=None, no_cache=None):
        """economy eurostat_table: one Eurostat table through the filters you give
        (/data/{table}; geo / time / dims = the upstream dimension filters — several values
        are REPEATED parameters; dims = the table-specific dimension ids as k=v pairs;
        since / until = the upstream sinceTimePeriod / untilTimePeriod window; the JSON-stat
        grid is decoded row-major into flat rows)."""
        self._economy_only("eurostat_table")
        r = economy.eurostat.table_raw(table, geo=geo, time=time, dims=dims, since=since,
                                        until=until, lang=lang, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        # The dimension dictionary carries every code -> label pair (tens of KB for a wide
        # table), so the reason line names the dimension ids and their code counts, and the
        # top cell spells out the dimension codes it sits at.
        dims_shown = ", ".join(
            f"{k} ({len(d.get('codes') or [])} code{'s' if len(d.get('codes') or []) != 1 else ''})"
            for k, d in (result.get("dimensions") or {}).items() if k not in ("geo", "time"))
        top_dims = ""
        if top:
            extra = " ".join(f"{k}={v}" for k, v in top.items()
                             if k not in ("geo", "time", "value", "status"))
            top_dims = f" {extra}" if extra else ""
        return self._flat_env(
            tool="eurostat_table",
            input={"table": table, "geo": geo, "time": time, "dims": dims,
                   "since": since, "until": until, "lang": lang},
            reason=(f"Eurostat {result.get('label') or table} — {result['count']} cells"
                    + (f" (table holds {result['total']:,})" if result.get("total") else "")
                    + (f", updated {result['updated']}" if result.get("updated") else "")
                    + (f", dims {dims_shown}" if dims_shown else "")
                    + (f", top {top.get('geo', '—')} {top.get('time', '—')}{top_dims} = {top.get('value')}"
                       if top else ", zero cells")
                    + (" — a geo outside the table yields zero cells and NO upstream error" if not result["count"] else "")),
            result=result,
            evidence=[{"quote": " ".join(f"{k}={v}" for k, v in x.items() if k != "value") + f" = {x.get('value')}",
                       "url": f"https://ec.europa.eu/eurostat/databrowser/view/{table}/default/table?lang=en"}
                      for x in result["rows"][:5]],
            provider_id="eurostat", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- Comext trade mirror (EU) ----------

    def comext_flows(self, *, reporter=None, partner=None, product=None, flow=None,
                     indicators=None, time=None, since=None, until=None,
                     execution=None, no_cache=None):
        """economy comext_flows: Eurostat Comext annual HS2-4-6 trade mirror since 2002 (the
        DEDICATED comext dissemination root — the plain Eurostat root 404s the ds- datasets;
        at least one filter is required — the filterless mirror is a 413 "Full extraction
        forbidden" with a 5-million-cell single-query cap; flow = 1 imports / 2 exports;
        indicators defaults to VALUE_EUR; the reporter aggregates EU / EU27_2020 / EA / EA21
        live alongside the country codes; the monthly CN8 detail travels the raw side)."""
        self._economy_only("comext_flows")
        r = economy.comext.flows_raw(reporter=reporter, partner=partner, product=product,
                                     flow=flow, indicators=indicators, time=time,
                                     since=since, until=until, cache=self._c._cache,
                                     no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]

        def _dims(x):
            return ", ".join(f"{k}={v}" for k, v in x.items()
                             if k not in ("value", "status", "labels"))

        return self._flat_env(
            tool="comext_flows",
            input={"reporter": reporter, "partner": partner, "product": product,
                   "flow": flow, "indicators": r["params"].get("indicators"),
                   "time": time, "since": since, "until": until},
            reason=(f"Comext annual HS mirror — {result['count']} cells"
                    + (f" of {result['total']:,} in the grid" if result.get("total") else "")
                    + (f", top {_dims(top)} = {top['value']}" if top else ", zero cells")
                    + (f" (updated {result['updated']})" if result.get("updated") else "")),
            result=result,
            evidence=[{"quote": f"{_dims(x)} = {x['value']}"
                             + (f" [{x['status']}]" if x.get("status") else ""),
                       "url": "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/ds-059341"}
                      for x in result["rows"][:5]],
            provider_id="comext", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- ECB reference rates (EU) ----------

    def ecb_fx_rates(self, *, currency=None, start=None, end=None, execution=None, no_cache=None):
        """economy ecb_fx_rates: the ECB euro reference rate for one currency
        (/EXR/D.{CCY}.EUR.SP00.A, csvdata; the value is units of {currency} per 1 EUR; start /
        end = the upstream startPeriod / endPeriod window; the historical eurofxref CSV is a
        stale 2010 snapshot and is NOT used — this live SDMX endpoint is)."""
        self._economy_only("ecb_fx_rates")
        r = economy.ecb.fx_rates_raw(currency, start=start, end=end, cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        # the ECB rows are sorted ASCENDING by date — the latest observation is the LAST row
        top = (result["rows"] or [None])[-1]
        return self._flat_env(
            tool="ecb_fx_rates",
            input={"currency": r["params"]["currency"], "start": start, "end": end},
            reason=(f"ECB reference rate {r['params']['currency']}/EUR — {result['count']} daily observations"
                    + (f" {r['params']['start']}→{r['params']['end']}" if r["params"].get("start") or r["params"].get("end") else "")
                    + (f", latest {top['date']} = {top['rate']}" if top else ", zero observations")),
            result=result,
            evidence=[{"quote": f"{x['date']}: 1 EUR = {x['rate']} {x['currency']}",
                       "url": "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"}
                      for x in result["rows"][:5]],
            provider_id="ecb", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- FRED (US) ----------

    def fred_series(self, *, series=None, start=None, end=None, execution=None, no_cache=None):
        """economy fred_series: one FRED series over a date window (/fredgraph.csv?id=;
        ONE series id per call — several ids answer a ZIP archive, which the JSON transport
        cannot carry; start / end = the upstream cosd / coed window; an unknown series id
        answers an HTML error page and is reported as not-found)."""
        self._economy_only("fred_series")
        r = economy.fred.series_raw(series, start=start, end=end, cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        # the FRED rows are sorted ASCENDING by date — the latest observation is the LAST row
        top = (result["rows"] or [None])[-1]
        return self._flat_env(
            tool="fred_series",
            input={"series": r["params"]["series"], "start": start, "end": end},
            reason=(f"FRED {r['params']['series']} — {result['count']} observations"
                    + (f", first {result['rows'][0]['date']}, latest {top['date']} = {top['value']}"
                       if top else ", zero observations")),
            result=result,
            evidence=[{"quote": f"{x['date']}: {x['value']} ({x['series']})",
                       "url": f"https://fred.stlouisfed.org/series/{x['series']}"}
                      for x in result["rows"][:5]],
            provider_id="fred", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- WHO xMart (global) ----------

    def who_xmart_indicators(self, *, filter=None, top=500, skip=0, search=None,
                              execution=None, no_cache=None):
        """economy who_xmart_indicators: the WHO xMart indicator directory
        (IND_DIRECTORY_WIDE — 1,561 indicators, each row carrying IND_URI_API, the per-indicator
        API diameter, and IND_URI_WEB; filter = the raw upstream OData $filter; search = a LOCAL
        keyword scan over the returned page)."""
        self._economy_only("who_xmart_indicators")
        r = economy.who_xmart.indicator_directory_raw(filter=filter, top=top, skip=skip,
                                                       search=search, cache=self._c._cache,
                                                       no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        filtered = bool(r["params"].get("filter"))
        head = (f"WHO xMart indicator directory — {result['total']} indicators "
                + ("match the upstream $filter" if filtered else "in the catalog"))
        return self._flat_env(
            tool="who_xmart_indicators",
            input={"filter": r["params"]["filter"], "top": r["params"]["top"],
                   "skip": r["params"]["skip"], "search": search},
            reason=(f"{head}, {result['count']} on this page"
                    + (f", top {top['IND_NAME']} — {top.get('IND_NAME_FULL') or top.get('IND_UNIT')}" if top else "")
                    + (" — the keyword filter is a local scan over this page" if search else "")),
            result=result,
            evidence=[{"quote": f"{x['IND_NAME']} — {x.get('IND_NAME_FULL') or x.get('IND_UNIT') or ''}".strip(),
                       "url": x.get("IND_URI_WEB") or f"https://xmart-api-public.who.int/DATA_/IND_DIRECTORY_WIDE"}
                      for x in result["rows"][:5]],
            provider_id="who_xmart", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def who_xmart_values(self, *, indicator=None, geo=None, year=None, entity_set=None,
                         top=500, skip=0, execution=None, no_cache=None):
        """economy who_xmart_values: the observations of one WHO indicator
        (DATA_/{entity set}; the entity set comes from the directory row's IND_URI_API — when
        several entity sets carry the same indicator name the candidate list is NOT auto-picked;
        geo = an ISO-3 country (translated through REF_GEO_WIDE into the M49 code the value
        tables use) or a raw M49 code; year = the DIM_TIME value (a string, so it is quoted)."""
        self._economy_only("who_xmart_values")
        code = str(indicator or "").strip()
        if not code:
            raise SdkError("usage_error", provider="who_xmart",
                           detail="who_xmart_values requires --indicator (the indicator code, "
                                  "e.g. TB_ppm_enrol_tx_prct — list them with who_xmart_indicators)")
        metas = []
        es = str(entity_set or "").strip().strip("/")
        if not es:
            rows, dir_meta = economy.who_xmart.entity_sets_for_indicator(
                code, cache=self._c._cache,
                no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
            metas.append(dir_meta)
            if not rows:
                raise SdkError("upstream_not_found", provider="who_xmart",
                               detail=f"No WHO xMart indicator named '{code}' — list the catalog "
                                      "with who_xmart_indicators")
            sets = []
            for row in rows:
                uri = row.get("IND_URI_API") or ""
                name = uri.rstrip("/").split("/")[-1]
                if name and name not in sets:
                    sets.append(name)
            if len(sets) > 1:
                raise SdkError("usage_error", provider="who_xmart",
                               detail=f"The indicator '{code}' is published in {len(sets)} entity "
                                      f"sets ({', '.join(sets)}) — pick one explicitly with "
                                      "--entity-set (the candidate list is never auto-picked)")
            es = sets[0]
        geo_value = None
        geo_meta = None
        if geo:
            g = str(geo).strip()
            if g.isdigit():
                geo_value = g
            else:
                m49, geo_rows, geo_meta = economy.who_xmart.m49_for_iso3(
                    g, cache=self._c._cache,
                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
                if not m49:
                    raise SdkError("upstream_not_found", provider="who_xmart",
                                   detail=f"No WHO geography row for '{g}' (REF_GEO_WIDE has no "
                                          "such ISO-3 code)")
                geo_value = m49
        odata = [f"IND_CODE eq '{code}'"]
        if year:
            odata.append(f"DIM_TIME eq '{str(year).strip()}'")
        if geo_value:
            odata.append(f"DIM_GEO_CODE_M49 eq '{geo_value}'")
        r = economy.who_xmart.indicator_values_raw(es, filter=" and ".join(odata), top=top,
                                                    skip=skip, cache=self._c._cache,
                                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        metas.append(r["_meta"])
        if geo_meta:
            metas.append(geo_meta)
        result = {k: x for k, x in r.items() if k != "_meta"}
        top_row = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="who_xmart_values",
            input={"indicator": code, "geo": geo, "year": year, "entity_set": es,
                   "top": r["params"]["top"], "skip": r["params"]["skip"]},
            reason=(f"WHO xMart {code} (entity set {es}) — {result['count']} observations"
                    + (f", geo {geo_value}" if geo_value else "")
                    + (f", {year}" if year else "")
                    + (f", top {top_row['DIM_TIME']} {top_row['DIM_GEO_CODE_M49']} = {top_row['VALUE_NUMERIC']}"
                       if top_row else ", zero observations")),
            result=result,
            evidence=[{"quote": f"{x.get('DIM_TIME')} {x.get('DIM_GEO_CODE_M49')} {x.get('DIM_MEMBER_1_CODE') or ''} = {x.get('VALUE_NUMERIC')}".strip(),
                       "url": f"https://xmart-api-public.who.int/DATA_/{es}"}
                      for x in result["rows"][:5]],
            provider_id="who_xmart", metas=metas,
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- UN Comtrade (global) ----------

    def un_comtrade_trade(self, *, reporter=None, period=None, partner=None, cmd=None,
                          flow=None, type_code="C", freq_code="A", cl_code="HS",
                          max_records=500, partner2=None, customs=None, mot=None,
                          execution=None, no_cache=None):
        """economy un_comtrade_trade: the UN Comtrade trade mirror (public preview API;
        reporter / partner = an ISO-3 code or the numeric area code — the ISO3 is translated
        through the area reference, whose historical rows and duplicate ISO3 entries make a
        naive map wrong (USA is 842, not 840 or 841); period = 2023 / 202301; cmd = the
        commodity code (a comma list, TOTAL = all goods); flow = X / M / "X,M")."""
        self._economy_only("un_comtrade_trade")
        r = economy.un_comtrade.trade_raw(reporter, period=period, partner=partner, cmd=cmd,
                                          flow=flow, type_code=type_code, freq_code=freq_code,
                                          cl_code=cl_code, max_records=max_records,
                                          partner2=partner2, customs=customs, mot=mot,
                                          cache=self._c._cache,
                                          no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="un_comtrade_trade",
            input={"reporter": reporter, "period": period, "partner": partner, "cmd": cmd,
                   "flow": flow, "type_code": type_code, "freq_code": freq_code,
                   "cl_code": cl_code, "max_records": max_records},
            reason=(f"UN Comtrade {reporter} × {partner or 'World'} — {period}, "
                    f"cmd {cmd or 'TOTAL'}, flow {flow or 'all'}: {result['count']} rows"
                    + (f", top {top['flow_name']} {top['cmd_code']} = {top['primary_value']} USD"
                       if top else ", zero rows")),
            result=result,
            evidence=[{"quote": f"{x['period']} {x['reporter_iso3']} → {x['partner_iso3']} "
                                f"{x['flow_name']} {x['cmd_code']} = {x['primary_value']} USD",
                       "url": "https://comtradeplus.un.org/"}
                      for x in result["rows"][:5]],
            provider_id="un_comtrade", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- ILOSTAT (global) ----------

    def ilo_stat_indicator(self, *, indicator=None, ref_area=None, time_from=None,
                           time_until=None, sex=None, classif=None, source=None,
                           execution=None, no_cache=None):
        """economy ilo_stat_indicator: one ILOSTAT indicator for one country
        (/data/indicator/; indicator = the ILOSTAT code; ref_area = the ISO-3 country — the
        world-wide answer is orders of magnitude bigger, so the country is required;
        time_from / time_until = the year bounds; sex / classif / source = the upstream
        dimension filters)."""
        self._economy_only("ilo_stat_indicator")
        r = economy.ilo_stat.indicator_raw(indicator, ref_area=ref_area, time_from=time_from,
                                           time_until=time_until, sex=sex, classif=classif,
                                           source=source, cache=self._c._cache,
                                           no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]     # the rows are sorted newest year first
        top_dims = ""
        if top:
            bits = [str(top.get("sex") or ""), str(top.get("classif1") or "")]
            top_dims = " " + " ".join(b for b in bits if b)
        win = ""
        if r["params"].get("time_from") and r["params"].get("time_until"):
            win = f" {r['params']['time_from']}→{r['params']['time_until']}"
        elif r["params"].get("time_from"):
            win = f" from {r['params']['time_from']}"
        elif r["params"].get("time_until"):
            win = f" until {r['params']['time_until']}"
        return self._flat_env(
            tool="ilo_stat_indicator",
            input={"indicator": r["params"]["indicator"], "ref_area": r["params"]["ref_area"],
                   "time_from": time_from, "time_until": time_until, "sex": sex,
                   "classif": classif, "source": source},
            reason=(f"ILOSTAT {r['params']['indicator']} × {r['params']['ref_area']} — "
                    f"{result['count']} observations{win}"
                    + (f", latest {top['time']}{top_dims} = {top['obs_value']}" if top else ", zero observations")),
            result=result,
            evidence=[{"quote": f"{x['time']} {x.get('sex') or ''} {x.get('classif1') or ''} = {x['obs_value']}".strip(),
                       "url": f"https://rshiny.ilo.org/dataexplorer50/?lang=en&id={r['params']['indicator']}"}
                      for x in result["rows"][:5]],
            provider_id="ilo_stat", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- IMF SDMX 2.1 (global) ----------

    def imf_sdmx_series(self, *, flow=None, country=None, indicator=None, frequency=None,
                        start=None, end=None, execution=None, no_cache=None):
        """economy imf_sdmx_series: one IMF dataflow series (/external/sdmx/2.1/data/{flow}/
        {COUNTRY.INDICATOR[.FREQUENCY]}, the SDMX 2.1 generic-CSV channel; flow = WEO / GDD /
        CPI …; country AND indicator are both required — the country-only key is the
        multi-megabyte wall; the key shape fits the WEO/GDD/CPI family, NOT UNFCCC whose
        dimensions insert INDUSTRY/GAS_TYPE before the indicator; start / end = the upstream
        startPeriod / endPeriod bounds; OBS_VALUE carries the true value — SCALE is only a
        display hint)."""
        self._economy_only("imf_sdmx_series")
        r = economy.imf_sdmx.sdmx_series_raw(flow, country, indicator, frequency=frequency,
                                             start=start, end=end, cache=self._c._cache,
                                             no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        # the rows are sorted ascending by period — the latest observation is the LAST row
        top = (result["rows"] or [None])[-1]
        win = (f" {r['params']['start']}→{r['params']['end']}"
               if r["params"].get("start") and r["params"].get("end")
               else (f" from {r['params']['start']}" if r["params"].get("start")
                     else (f" until {r['params']['end']}" if r["params"].get("end") else "")))
        return self._flat_env(
            tool="imf_sdmx_series",
            input={"flow": r["params"]["flow"], "country": r["params"]["country"],
                   "indicator": r["params"]["indicator"], "frequency": r["params"]["frequency"],
                   "start": start, "end": end},
            reason=(f"IMF SDMX {r['params']['flow']} {result['key']} — {result['count']} observations{win}"
                    + (f", first {result['rows'][0]['period']}, latest {top['period']} = {top['value']}"
                       if top else ", zero observations")
                    + (f" ({top['series_name']})" if top and top.get("series_name") else "")),
            result=result,
            evidence=[{"quote": f"{x['period']} {x['value']}"
                             + (f" ({', '.join(f'{k}={v}' for k, v in x['dims'].items())})" if x["dims"] else ""),
                       "url": f"https://api.imf.org/external/sdmx/2.1/data/{r['params']['flow']}/{result['key']}"}
                      for x in result["rows"][:5]],
            provider_id="imf_sdmx", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- BIS SDMX (global) ----------

    def bis_sdmx_series(self, *, flow=None, key=None, start=None, end=None,
                        execution=None, no_cache=None):
        """economy bis_sdmx_series: one BIS dataflow series (/api/v1/data/{flow}/{key}/all, the
        SDMX 2.1 generic-CSV channel; key = the raw dot-separated series key with at least two
        segments — the segment order is flow-specific: WS_CBPOL FREQ.REF_AREA (M.US), WS_DSR
        FREQ.BORROWERS_CTY.DSR_BORROWERS (Q.US.N), WS_XRU FREQ.REF_AREA.CURRENCY.COLLECTION
        (M.CN.CNY.E); a one-segment key is every area at once — the multi-megabyte wall; a
        wrong key answers 404 with an SDMX error, it is not a block; start / end = the
        upstream startPeriod / endPeriod bounds)."""
        self._economy_only("bis_sdmx_series")
        r = economy.bis.sdmx_series_raw(flow, key, start=start, end=end, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        # the rows are sorted ascending by period — the latest observation is the LAST row
        top = (result["rows"] or [None])[-1]
        win = (f" {r['params']['start']}→{r['params']['end']}"
               if r["params"].get("start") and r["params"].get("end")
               else (f" from {r['params']['start']}" if r["params"].get("start")
                     else (f" until {r['params']['end']}" if r["params"].get("end") else "")))
        return self._flat_env(
            tool="bis_sdmx_series",
            input={"flow": r["params"]["flow"], "key": r["params"]["key"],
                   "start": start, "end": end},
            reason=(f"BIS {r['params']['flow']} {result['key']} — {result['count']} observations{win}"
                    + (f", first {result['rows'][0]['period']}, latest {top['period']} = {top['value']}"
                       if top else ", zero observations")
                    + (f" ({top['title']})" if top and top.get("title") else "")),
            result=result,
            evidence=[{"quote": f"{x['period']} {x['value']}"
                             + (f" ({', '.join(f'{k}={v}' for k, v in x['dims'].items())})" if x["dims"] else ""),
                       "url": f"https://stats.bis.org/api/v1/data/{r['params']['flow']}/{result['key']}/all"}
                      for x in result["rows"][:5]],
            provider_id="bis", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- OECD SDMX (global) ----------

    def oecd_sdmx_series(self, *, flow=None, key=None, start=None, end=None,
                         execution=None, no_cache=None):
        """economy oecd_sdmx_series: one OECD dataflow series (/public/rest/data/{flow}/{key}/all,
        the SDMX generic-CSV channel; flow = the CATALOG form agency,DSD@DF[,version] — the
        bare DF spelling answers 404; key = dot-separated with EXACTLY one segment per DSD
        dimension, an empty segment is the wildcard — the segment count is validated against
        the DSD structure before the data call, so the short-key 403 never forms; start / end
        = the upstream startPeriod / endPeriod bounds)."""
        self._economy_only("oecd_sdmx_series")
        r = economy.oecd_sdmx.sdmx_series_raw(flow, key, start=start, end=end,
                                              cache=self._c._cache,
                                              no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        # the rows are sorted ascending by period — the latest observation is the LAST row
        top = (result["rows"] or [None])[-1]
        win = (f" {r['params']['start']}→{r['params']['end']}"
               if r["params"].get("start") and r["params"].get("end")
               else (f" from {r['params']['start']}" if r["params"].get("start")
                     else (f" until {r['params']['end']}" if r["params"].get("end") else "")))
        return self._flat_env(
            tool="oecd_sdmx_series",
            input={"flow": r["params"]["flow"], "key": r["params"]["key"],
                   "start": start, "end": end},
            reason=(f"OECD SDMX {r['params']['flow']} {r['params']['key']} — "
                    f"{result['count']} observations{win}"
                    + (f", first {result['rows'][0]['period']}, latest {top['period']} = {top['value']}"
                       if top else ", zero observations")
                    + (f" ({top['unit_measure']})" if top and top.get("unit_measure") else "")),
            result=result,
            evidence=[{"quote": f"{x['period']} {x['value']}"
                             + (f" ({', '.join(f'{k}={v}' for k, v in x['dims'].items())})" if x["dims"] else "")
                             + (f" [{x['unit_measure']}]" if x.get("unit_measure") else ""),
                       "url": f"https://sdmx.oecd.org/public/rest/data/{r['params']['flow']}/{r['params']['key']}/all"}
                      for x in result["rows"][:5]],
            provider_id="oecd_sdmx", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    # ---------- UNSD SDG (global) ----------

    def unsd_sdg_indicators(self, *, page=1, per_page=50, search=None,
                            execution=None, no_cache=None):
        """economy unsd_sdg_indicators: the UN SDG indicator catalog (/Indicator/List — 251
        indicators over the 17 goals, each row carrying its series codes (713 in total) nested
        inside; the upstream answers the whole catalog in one payload — page / per_page slice
        it locally and search is a LOCAL keyword scan over the whole catalog, never an
        upstream filter)."""
        self._economy_only("unsd_sdg_indicators")
        r = economy.unsd_sdg.indicators_raw(page=page, per_page=per_page, search=search,
                                            cache=self._c._cache,
                                            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        return self._flat_env(
            tool="unsd_sdg_indicators",
            input={"page": r["params"]["page"], "per_page": r["params"]["per_page"],
                   "search": search},
            reason=(f"UNSD SDG indicator catalog — {result['total']} indicators "
                    + ("match the keyword" if search else "over the 17 goals")
                    + f", {result['count']} on this page"
                    + (f", top {top['code']} (goal {top['goal']}, {top['series_count']} series) = "
                       f"{(top['description'] or '')[:80]}" if top else "")),
            result=result,
            evidence=[{"quote": f"{x['code']} (goal {x['goal']}) — {(x['description'] or '')[:80]}"
                              + f" [{', '.join(x['series_codes'][:3])}{'…' if len(x['series_codes']) > 3 else ''}]",
                       "url": f"https://unstats.un.org/SDGAPI{x['uri']}" if x.get("uri")
                       else "https://unstats.un.org/SDGAPI/v1/sdg/Indicator/List"}
                      for x in result["rows"][:5]],
            provider_id="unsd_sdg", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def unsd_sdg_series(self, *, series=None, geo=None, time=None, page=1, page_size=100,
                        execution=None, no_cache=None):
        """economy unsd_sdg_series: the observations of ONE SDG series (/Series/Data?
        seriesCode=… — series granularity only: the whole-indicator endpoint is a 3.2M-row
        wall that is never formed; geo = a LOCAL filter over the fetched page matching the
        geoAreaCode or geoAreaName — the upstream `area` parameter is DECORATIVE,
        byte-identical with and without it; time = the upstream timePeriod filter, the one
        upstream filter that works on this endpoint)."""
        self._economy_only("unsd_sdg_series")
        r = economy.unsd_sdg.series_raw(series, geo=geo, time=time, page=page,
                                        page_size=page_size, cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        top = (result["rows"] or [None])[0]
        total_bits = (f" of {result['total']:,} total" if result.get("total") is not None else "")
        return self._flat_env(
            tool="unsd_sdg_series",
            input={"series": r["params"]["series"], "geo": geo, "time": r["params"]["time"],
                   "page": r["params"]["page"], "page_size": r["params"]["page_size"]},
            reason=(f"UNSD SDG series {r['params']['series']} — {result['count']} rows on this "
                    f"page{total_bits}"
                    + (f", geo {r['params']['geo']} (local filter)" if r["params"].get("geo") else "")
                    + (f", period {r['params']['time']}" if r["params"].get("time") else "")
                    + (f", top {top['geo_area_name']} {top['period']} = {top['value']}" if top
                       else ", zero rows on this page")),
            result=result,
            evidence=[{"quote": f"{x['geo_area_name']} ({x['geo_area_code']}) {x['period']} = {x['value']}",
                       "url": f"https://unstats.un.org/SDGAPI/v1/sdg/Series/Data?seriesCode={r['params']['series']}"}
                      for x in result["rows"][:5]],
            provider_id="unsd_sdg", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def bls_series(self, *, series=None, start_year=None, end_year=None,
                   execution=None, no_cache=None):
        """economy bls_series: BLS v2 series observations (POST /publicAPI/v2/timeseries/data/
        — up to 25 series ids over one <= 10-year window on the keyless tier; catalog/
        calculations/annualaverage/aspects are key-gated options and are never sent; a window
        wider than 10 years is refused locally because the upstream clamp keeps the EARLIEST
        ten years (startyear-anchored, pinned 2026-11-03); a bogus id answers 200 and surfaces
        as series_without_data; omitting both years answers the latest ~3 calendar years)."""
        self._economy_only("bls_series")
        r = economy.bls.series_raw(series, start_year=start_year, end_year=end_year,
                                   cache=self._c._cache,
                                   no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        rows = result["rows"]
        top = rows[0] if rows else None
        dead = (f"; {len(result['series_without_data'])} of {len(result['series'])} series "
                f"returned no data ({'; '.join(result['series_without_data'])})"
                if result["series_without_data"] else "")
        return self._flat_env(
            tool="bls_series",
            input={"series": result["series"], "start_year": start_year, "end_year": end_year},
            reason=(f"BLS series {', '.join(result['series'])} — {result['count']} observations"
                    + (f", window {r['params']['startyear']}..{r['params']['endyear']}"
                       if r["params"]["startyear"] else ", latest ~3 years (default window)")
                    + dead
                    + (f"; first {top['series']} {top['year']}-{top['period']} = {top['value']}"
                       if top else ", zero observations")),
            result=result,
            evidence=[{"quote": f"{x['series']} {x['year']}-{x['period']} ({x['period_name']}) = {x['value']}",
                       "url": "https://api.bls.gov/publicAPI/v2/timeseries/data/"}
                      for x in rows[:5]],
            provider_id="bls", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )
