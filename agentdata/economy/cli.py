"""economy cli — domain command-face registration (the eighth domain, 0.3.23; 0.3.24 + 0.3.26 expansions).

register(v, g): registers the flat commands onto the domain subparser (g = root _leaf_globals
factory, passed in as a parameter to avoid a cli <-> domain-cli cycle); FLAT = flat dispatch table,
merged by the root cli for main to use.

Face order = lexicographic over the English identifiers (the 0.3.12 contract guard): within the
domain the faces group by source automatically (bis / bls / comext / ecb / eurostat / fred /
ilo_stat / imf_sdmx / oecd_sdmx / un_comtrade / unsd_sdg / wb / who_xmart).
"""


def register(v, g):
    f1 = v.add_parser("bis_sdmx_series", parents=[g()],
                      help="BIS SDMX series — SDMX 2.1 generic-CSV channel",
                      description="BIS SDMX series (realtime, local execution; /api/v1/data/{flow}/{key}/all, the SDMX 2.1 generic-CSV channel; key = the raw dot-separated series key with AT LEAST two segments — the segment order is flow-specific: WS_CBPOL FREQ.REF_AREA (M.US), WS_DSR FREQ.BORROWERS_CTY.DSR_BORROWERS (Q.US.N), WS_XRU FREQ.REF_AREA.CURRENCY.COLLECTION (M.CN.CNY.E); a one-segment key is every area at once — a multi-megabyte answer; a wrong key answers 404 with an SDMX error, which is not a block; --start / --end are the upstream startPeriod / endPeriod bounds)")
    f1.add_argument("--flow", required=True, help="BIS dataflow id (e.g. WS_CBPOL, WS_DSR, WS_XRU)")
    f1.add_argument("--key", required=True, help="SDMX series key, >= 2 dot-separated segments (e.g. M.US, Q.US.N, M.CN.CNY.E)")
    f1.add_argument("--start", default=None, help="Period window start (upstream param: startPeriod)")
    f1.add_argument("--end", default=None, help="Period window end (upstream param: endPeriod)")

    f18 = v.add_parser("bls_series", parents=[g()],
                       help="BLS v2 series observations — up to 25 series x 10 years",
                       description="BLS v2 series observations (realtime, local execution; POST /publicAPI/v2/timeseries/data/ with a JSON body; --series takes up to 25 comma-separated ids — the documented keyless caps are 25 series x 10 years x 500 queries/day; a window wider than 10 years is refused locally because the upstream clamp keeps the EARLIEST ten years (startyear-anchored: a 2010..2026 ask answered 2010..2019); a bogus id answers 200 and the id is listed under series_without_data; omitting both years answers the latest ~3 calendar years; catalog/calculations/annualaverage/aspects are key-gated options and are never sent)")
    f18.add_argument("--series", required=True,
                     help="BLS series id(s), comma-separated, <= 25 (e.g. CUUR0000SA0 = CPI-U, LNS14000000 = unemployment rate, CES0000000001 = nonfarm payrolls)")
    f18.add_argument("--start-year", dest="start_year", default=None, help="Window start year (upstream param: startyear; travels with --end-year)")
    f18.add_argument("--end-year", dest="end_year", default=None, help="Window end year (upstream param: endyear; travels with --start-year)")


    f2 = v.add_parser("comext_flows", parents=[g()],
                      help="Eurostat Comext annual HS2-4-6 trade mirror since 2002",
                      description="Eurostat Comext annual HS2-4-6 trade mirror since 2002 (realtime, local execution; the DEDICATED comext dissemination root /api/comext/dissemination/.../data/ds-059341 — the plain Eurostat root 404s the ds- datasets; at least one filter is required — the filterless mirror is a 413 \"Full extraction forbidden\" (31.3 billion cells, one query caps at 5 million); --flow 1 imports / 2 exports; --indicators defaults to VALUE_EUR; the reporter aggregates EU / EU27_2020 / EA / EA21 live alongside the country codes; the JSON-stat grid is decoded into flat rows; the monthly CN8 detail (DS-045409) travels the raw side, not this face)")
    f2.add_argument("--reporter", action="append", default=None, metavar="CODE",
                    help="Reporting economy filter (repeatable, e.g. DE, EU27_2020)")
    f2.add_argument("--partner", action="append", default=None, metavar="CODE",
                    help="Partner economy filter (repeatable, e.g. CN, WLD)")
    f2.add_argument("--product", action="append", default=None, metavar="HS",
                    help="HS 2/4/6 product code filter (repeatable, e.g. 85 = electrical machinery)")
    f2.add_argument("--flow", action="append", default=None, metavar="1|2",
                    help="Trade flow (repeatable: 1 = imports, 2 = exports)")
    f2.add_argument("--indicators", default=None, metavar="CODE",
                    help="Value measure (upstream param: indicators; default VALUE_EUR, also QUANTITY_IN_100KG)")
    f2.add_argument("--time", action="append", default=None, metavar="YEAR",
                    help="Year filter (repeatable, e.g. 2024)")
    f2.add_argument("--since", default=None, help="Time window start (upstream param: sinceTimePeriod)")
    f2.add_argument("--until", default=None, help="Time window end (upstream param: untilTimePeriod)")

    f3 = v.add_parser("ecb_fx_rates", parents=[g()],
                      help="ECB euro reference rate for one currency",
                      description="ECB euro reference rate for one currency (realtime, local execution; /EXR/D.{CCY}.EUR.SP00.A?format=csvdata; the value is units of {currency} per 1 EUR and the date travels with every row; --start / --end are the upstream startPeriod / endPeriod bounds and one of them is required; the historical eurofxref CSV is a stale 2010 snapshot and is not used)")
    f3.add_argument("--currency", required=True, help="ISO 4217 currency code (e.g. USD, JPY, GBP)")
    f3.add_argument("--start", default=None, help="Window start date (upstream param: startPeriod)")
    f3.add_argument("--end", default=None, help="Window end date (upstream param: endPeriod)")

    f4 = v.add_parser("eurostat_table", parents=[g()],
                      help="Eurostat table query — JSON-stat grid decoded to flat rows",
                      description="Eurostat table query (realtime, local execution; /data/{table}; geo / time / --dim k=v are the upstream dimension filters — SEVERAL values are REPEATED parameters (the '+' form is a 400 and the comma form silently yields zero cells); --since / --until are the upstream sinceTimePeriod / untilTimePeriod bounds; the JSON-stat grid is decoded into flat rows; a geo outside the table yields zero cells and no upstream error)")
    f4.add_argument("--table", required=True, help="Eurostat table code (e.g. tec00001, demo_pjan, nama_10_a64)")
    f4.add_argument("--geo", action="append", default=None, metavar="CODE",
                    help="Geopolitical entity filter (repeatable, e.g. DE; several codes become repeated upstream parameters)")
    f4.add_argument("--time", action="append", default=None, metavar="PERIOD",
                    help="Time filter (repeatable, e.g. 2023)")
    f4.add_argument("--dim", action="append", default=None, metavar="K=V",
                    help="Any other dimension filter as k=v (repeatable, e.g. age=TOTAL, sex=T, unit=NR)")
    f4.add_argument("--since", default=None, help="Time window start (upstream param: sinceTimePeriod)")
    f4.add_argument("--until", default=None, help="Time window end (upstream param: untilTimePeriod)")
    f4.add_argument("--lang", default="EN", help="Upstream language (default EN)")

    f5 = v.add_parser("fred_series", parents=[g()],
                      help="FRED series observations — one series per call",
                      description="FRED series observations (realtime, local execution; /fredgraph.csv?id=; ONE series id per call — several ids answer a ZIP archive the JSON transport cannot carry; an unknown series id answers an HTML error page and is reported as not-found; a missing observation is null; --start / --end are the upstream cosd / coed bounds)")
    f5.add_argument("--series", required=True, help="FRED series id (e.g. GDP, CPIAUCSL, DGS10)")
    f5.add_argument("--start", default=None, help="Observation window start (upstream param: cosd)")
    f5.add_argument("--end", default=None, help="Observation window end (upstream param: coed)")

    f6 = v.add_parser("ilo_stat_indicator", parents=[g()],
                      help="ILOSTAT indicator for one country",
                      description="ILOSTAT indicator for one country (realtime, local execution; /data/indicator/; the format flag is the query parameter format=json — a path suffix is a 400/404; --ref-area (ISO-3) is required — the world-wide answer is orders of magnitude bigger; --time-from / --time-until are the upstream timefrom / timeto bounds — the upstream spells the upper bound 'timeto' and silently ignores 'timeuntil'; the urllib channel is the working one on this host — the curl stack answers an empty 200)")
    f6.add_argument("--indicator", required=True, help="ILOSTAT indicator code (e.g. EMP_TEMP_SEX_ECO_NB_A)")
    f6.add_argument("--ref-area", dest="ref_area", required=True, help="Country ISO-3 code (e.g. USA)")
    f6.add_argument("--time-from", dest="time_from", default=None, help="Year window start (upstream param: timefrom)")
    f6.add_argument("--time-until", dest="time_until", default=None, help="Year window end (upstream param: timeto)")
    f6.add_argument("--sex", default=None, help="Sex dimension filter (upstream param: sex)")
    f6.add_argument("--classif", default=None, help="Classification dimension filter (upstream param: classif1)")
    f6.add_argument("--source", default=None, help="Source filter (upstream param: source)")

    f7 = v.add_parser("imf_sdmx_series", parents=[g()],
                      help="IMF SDMX series — SDMX 2.1 generic-CSV channel",
                      description="IMF SDMX series (realtime, local execution; /external/sdmx/2.1/data/{flow}/{COUNTRY.INDICATOR[.FREQUENCY]}, the SDMX 2.1 generic-CSV channel; --country AND --indicator are both required — the country-only key is the multi-megabyte wall; the key shape fits the WEO/GDD/CPI family, NOT UNFCCC whose dimensions insert INDUSTRY/GAS_TYPE before the indicator; --start / --end are the upstream startPeriod / endPeriod bounds; OBS_VALUE carries the true value — SCALE is only a display hint)")
    f7.add_argument("--flow", required=True, help="IMF dataflow id (e.g. WEO, GDD, CPI)")
    f7.add_argument("--country", required=True, help="Country code as the dataflow spells it (ISO-3 in WEO/GDD, e.g. USA)")
    f7.add_argument("--indicator", required=True, help="Indicator code (e.g. NGDP_RPCH = real GDP growth)")
    f7.add_argument("--frequency", default=None, help="Optional trailing key dimension (e.g. A)")
    f7.add_argument("--start", default=None, help="Period window start (upstream param: startPeriod)")
    f7.add_argument("--end", default=None, help="Period window end (upstream param: endPeriod)")

    f8 = v.add_parser("oecd_sdmx_series", parents=[g()],
                      help="OECD SDMX series — SDMX generic-CSV channel",
                      description="OECD SDMX series (realtime, local execution; /public/rest/data/{flow}/{key}/all, the SDMX generic-CSV channel; --flow takes the CATALOG form agency,DSD@DF[,version] — the bare DF spelling answers 404 \"Could not find Dataflow and/or DSD\"; --key is dot-separated with EXACTLY one segment per DSD dimension and an EMPTY segment as the wildcard — the segment count is validated against the DSD structure before the data call, so the short-key 403 (\"expecting 12 got 6\") never forms; --start / --end are the upstream startPeriod / endPeriod bounds; the whole service is keyless — the 2026-11-02 'needs a key' ruling was a request-form misdiagnosis)")
    f8.add_argument("--flow", required=True, help="OECD dataflow in catalog form (e.g. OECD.ECO.MAD,DSD_EO@DF_EO,1.5 = Economic Outlook 119; OECD.SDD.NAD,DSD_NAAG@DF_NAAG_I,1.0 = national accounts GDP chapter)")
    f8.add_argument("--key", required=True, help="Dot-separated series key, one segment per DSD dimension, empty = wildcard (e.g. DEU.. for DSD_EO = Germany, all measures, all frequencies)")
    f8.add_argument("--start", default=None, help="Period window start (upstream param: startPeriod)")
    f8.add_argument("--end", default=None, help="Period window end (upstream param: endPeriod)")

    f9 = v.add_parser("un_comtrade_trade", parents=[g()],
                      help="UN Comtrade trade mirror, public preview",
                      description="UN Comtrade trade mirror, public preview (realtime, local execution; /public/v1/preview/{type}/{freq}/{cl}; --reporter / --partner take an ISO-3 code or the numeric area code — the ISO3 is translated through the area reference, whose historical and duplicate rows make a naive map wrong (USA = 842, not 840 or 841); --period 2023 / 202301; --cmd is the commodity code (comma list, TOTAL = all goods); --flow X / M / 'X,M'; the preview answers at most 500 records)")
    f9.add_argument("--reporter", required=True, help="Reporting country: ISO-3 (e.g. USA) or the numeric area code")
    f9.add_argument("--period", required=True, help="Period (e.g. 2023 or 202301)")
    f9.add_argument("--partner", default=None, help="Partner area: ISO-3 or numeric code (0 / W00 = the World aggregate)")
    f9.add_argument("--cmd", default=None, help="Commodity code, comma list allowed (default TOTAL = all goods)")
    f9.add_argument("--flow", default=None, help="Trade flow: X (export), M (import), 'X,M'")
    f9.add_argument("--type-code", dest="type_code", default="C", help="Path segment: commodity type (C)")
    f9.add_argument("--freq-code", dest="freq_code", default="A", help="Path segment: frequency (A = annual)")
    f9.add_argument("--cl-code", dest="cl_code", default="HS", help="Path segment: classification (HS)")
    f9.add_argument("--max-records", dest="max_records", type=int, default=500,
                    help="Records per call (upstream param: maxRecords; 1-500)")
    f9.add_argument("--partner2", default=None, help="Second partner area (upstream param: partner2Code)")
    f9.add_argument("--customs", default=None, help="Customs regime (upstream param: customsCode)")
    f9.add_argument("--mot", default=None, help="Mode of transport (upstream param: motCode)")

    f10 = v.add_parser("unsd_sdg_indicators", parents=[g()],
                       help="UNSD SDG indicator catalog — 251 indicators over the 17 goals",
                       description="UNSD SDG indicator catalog (realtime, local execution; /Indicator/List — 251 indicators over the 17 goals, each row carrying its series codes (713 in total) nested inside; the upstream answers the whole catalog in one payload — --page / --per-page slice it locally and --search is a LOCAL keyword scan over the whole catalog, never an upstream filter)")
    f10.add_argument("--page", type=int, default=1, help="Local page slice (the upstream payload is whole)")
    f10.add_argument("--per-page", dest="per_page", type=int, default=50, help="Local page size (1-500)")
    f10.add_argument("--search", default=None, help="Local keyword scan (code / description / series codes)")

    f11 = v.add_parser("unsd_sdg_series", parents=[g()],
                       help="UNSD SDG series observations — series granularity only",
                       description="UNSD SDG series observations (realtime, local execution; /Series/Data?seriesCode= — series granularity only: the whole-indicator endpoint is a 3.2M-row wall that is never formed; --geo is a LOCAL filter over the fetched page matching the geoAreaCode or geoAreaName — the upstream 'area' parameter is DECORATIVE, byte-identical with and without it; --time is the upstream timePeriod filter, the one upstream filter that works on this endpoint)")
    f11.add_argument("--series", required=True, help="SDG series code (e.g. SI_POV_DAY1, DC_ODA_POVLG — list them with unsd_sdg_indicators)")
    f11.add_argument("--geo", default=None, help="Local geo filter: geoAreaCode or geoAreaName, case-insensitive (e.g. 842, China)")
    f11.add_argument("--time", default=None, help="Period filter (upstream param: timePeriod, e.g. 2020)")
    f11.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    f11.add_argument("--page-size", dest="page_size", type=int, default=100,
                     help="Rows per page (upstream param: pageSize; 1-1000)")


    f12 = v.add_parser("wb_countries", parents=[g()],
                       help="World Bank country reference — ISO3/ISO2/region/income level",
                       description="World Bank country reference (realtime, local execution; /v2/country; ISO3 / ISO2 / region / income level / lending type / coordinates — the income band is the buyer-screen dimension; the 296 entries include the aggregate regions)")
    f12.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    f12.add_argument("--per-page", dest="per_page", type=int, default=100,
                     help="Rows per page (upstream param: per_page; 1-1000)")

    f13 = v.add_parser("wb_ids_indicators", parents=[g()],
                       help="World Bank International Debt Statistics catalog — 577 indicators",
                       description="World Bank International Debt Statistics catalog (realtime, local execution; /v2/indicator with source pinned to 6 = IDS — 577 indicators in seven debt families: DOD stocks / INT interest / AMT disbursements / DIS / NFL net flows / NTR / TDS service plus the balance-of-payments mirrors; the per-page default 600 holds the whole catalog in one page; the VALUES of the DT.* codes are served by wb_wdi_values WITHOUT a source parameter — the value endpoint breaks with source=6 and the API silently falls back to sourceid 2)")
    f13.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    f13.add_argument("--per-page", dest="per_page", type=int, default=600,
                     help="Rows per page (upstream param: per_page; 1-1000; 600 = the whole catalog)")
    f13.add_argument("--search", default=None, help="Local keyword scan over the page (code / name / organization)")

    f14 = v.add_parser("wb_wdi_indicators", parents=[g()],
                       help="World Bank indicator catalog — source 2 = WDI",
                       description="World Bank indicator catalog (realtime, local execution; /v2/indicator?source=; source 2 = WDI — without it the catalog is every World Bank source at once (29,544 rows); --search is a LOCAL keyword scan over the returned page, not an upstream filter)")
    f14.add_argument("--source", default=2, help="World Bank source id (2 = WDI, the default)")
    f14.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    f14.add_argument("--per-page", dest="per_page", type=int, default=500,
                     help="Rows per page (upstream param: per_page; 1-1000)")
    f14.add_argument("--search", default=None, help="Local keyword scan over the page (code / name / organization)")

    f15 = v.add_parser("wb_wdi_values", parents=[g()],
                       help="World Bank WDI indicator values",
                       description="World Bank WDI indicator values (realtime, local execution; /v2/country/{country}/indicator/{indicator}; country = ISO3, several codes joined by ';'; ONE indicator code per call — the upstream rejects several codes in one call (\"120 Invalid value\"); date = YYYY or YYYY:YYYY; a missing observation is null, never fabricated)")
    f15.add_argument("--country", required=True, help="ISO3 country code (e.g. CHN; several codes may be joined by ';')")
    f15.add_argument("--indicator", required=True, help="WDI indicator code (e.g. NY.GDP.MKTP.CD, or a DT.* IDS code — WITHOUT --source)")
    f15.add_argument("--date", default=None, help="Year or year window (upstream param: date; 'YYYY' or 'YYYY:YYYY')")
    f15.add_argument("--per-page", dest="per_page", type=int, default=100,
                     help="Rows per page (upstream param: per_page; 1-1000)")

    f16 = v.add_parser("who_xmart_indicators", parents=[g()],
                       help="WHO xMart indicator directory — 1,561 indicators",
                       description="WHO xMart indicator directory (realtime, local execution; IND_DIRECTORY_WIDE — 1,561 indicators, each row carrying IND_URI_API (the per-indicator API diameter) and IND_URI_WEB; --filter is the raw upstream OData $filter; --search is a LOCAL keyword scan over the returned page)")
    f16.add_argument("--filter", default=None, help="Raw upstream OData $filter (e.g. \"IND_NAME eq 'TB_ppm_enrol_tx_prct'\")")
    f16.add_argument("--top", type=int, default=500, help="Page size (upstream param: $top; 1-5000)")
    f16.add_argument("--skip", type=int, default=0, help="Offset (upstream param: $skip)")
    f16.add_argument("--search", default=None, help="Local keyword scan over the page (name / unit / web URI)")

    f17 = v.add_parser("who_xmart_values", parents=[g()],
                       help="WHO xMart indicator observations",
                       description="WHO xMart indicator observations (realtime, local execution; DATA_/{entity set}; the entity set is resolved from the directory row's IND_URI_API — when several entity sets carry the same indicator name the candidate list is NOT auto-picked, pass --entity-set; --geo takes an ISO-3 country (translated through REF_GEO_WIDE into the M49 code) or a raw M49 code; --year is the DIM_TIME string value)")
    f17.add_argument("--indicator", required=True, help="Indicator code (e.g. TB_ppm_enrol_tx_prct)")
    f17.add_argument("--geo", default=None, help="Country: ISO-3 (e.g. PAK) or the raw M49 code")
    f17.add_argument("--year", default=None, help="Observation year (DIM_TIME, a string value)")
    f17.add_argument("--entity-set", dest="entity_set", default=None,
                     help="WHO entity set (e.g. RELAY_TBPPM) — resolved from the directory when omitted")
    f17.add_argument("--top", type=int, default=500, help="Page size (upstream param: $top; 1-5000)")
    f17.add_argument("--skip", type=int, default=0, help="Offset (upstream param: $skip)")


FLAT = {
    # economy (0.3.23 + 0.3.24 + 0.3.26): the country-level denominator layer — macro indicators,
    # reference rates, official statistics and the trade mirror (upstream param names verbatim
    # + our defaults; lambdas only shuttle names across namespaces)
    "bis_sdmx_series": lambda a: {"flow": a.flow, "key": a.key, "start": a.start, "end": a.end},
    "bls_series": lambda a: {"series": a.series, "start_year": a.start_year, "end_year": a.end_year},
    "comext_flows": lambda a: {"reporter": a.reporter, "partner": a.partner, "product": a.product,
                               "flow": a.flow, "indicators": a.indicators, "time": a.time,
                               "since": a.since, "until": a.until},
    "ecb_fx_rates": lambda a: {"currency": a.currency, "start": a.start, "end": a.end},
    "eurostat_table": lambda a: {"table": a.table, "geo": a.geo, "time": a.time,
                                 "dims": a.dim, "since": a.since, "until": a.until,
                                 "lang": a.lang},
    "fred_series": lambda a: {"series": a.series, "start": a.start, "end": a.end},
    "ilo_stat_indicator": lambda a: {"indicator": a.indicator, "ref_area": a.ref_area,
                                     "time_from": a.time_from, "time_until": a.time_until,
                                     "sex": a.sex, "classif": a.classif, "source": a.source},
    "imf_sdmx_series": lambda a: {"flow": a.flow, "country": a.country,
                                  "indicator": a.indicator, "frequency": a.frequency,
                                  "start": a.start, "end": a.end},
    "oecd_sdmx_series": lambda a: {"flow": a.flow, "key": a.key, "start": a.start, "end": a.end},
    "un_comtrade_trade": lambda a: {"reporter": a.reporter, "period": a.period,
                                    "partner": a.partner, "cmd": a.cmd, "flow": a.flow,
                                    "type_code": a.type_code, "freq_code": a.freq_code,
                                    "cl_code": a.cl_code, "max_records": a.max_records,
                                    "partner2": a.partner2, "customs": a.customs, "mot": a.mot},
    "unsd_sdg_indicators": lambda a: {"page": a.page, "per_page": a.per_page, "search": a.search},
    "unsd_sdg_series": lambda a: {"series": a.series, "geo": a.geo, "time": a.time,
                                  "page": a.page, "page_size": a.page_size},
    "wb_countries": lambda a: {"page": a.page, "per_page": a.per_page},
    "wb_ids_indicators": lambda a: {"page": a.page, "per_page": a.per_page, "search": a.search},
    "wb_wdi_indicators": lambda a: {"source": a.source, "page": a.page,
                                    "per_page": a.per_page, "search": a.search},
    "wb_wdi_values": lambda a: {"country": a.country, "indicator": a.indicator,
                                "date": a.date, "per_page": a.per_page},
    "who_xmart_indicators": lambda a: {"filter": a.filter, "top": a.top, "skip": a.skip,
                                       "search": a.search},
    "who_xmart_values": lambda a: {"indicator": a.indicator, "geo": a.geo, "year": a.year,
                                   "entity_set": a.entity_set, "top": a.top, "skip": a.skip},
}


# 0.3.10 jurisdiction chapter: face -> jurisdiction (default = the issuing authority's
# jurisdiction; institutions covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2
# + EU + GLOBAL) —— merged by the root cli.py into _JURISDICTION
COUNTRY = {
    "bis_sdmx_series": "GLOBAL",
    "bls_series": "US",
    "comext_flows": "EU",
    "ecb_fx_rates": "EU",
    "eurostat_table": "EU",
    "fred_series": "US",
    "ilo_stat_indicator": "GLOBAL",
    "imf_sdmx_series": "GLOBAL",
    "oecd_sdmx_series": "GLOBAL",
    "un_comtrade_trade": "GLOBAL",
    "unsd_sdg_indicators": "GLOBAL",
    "unsd_sdg_series": "GLOBAL",
    "wb_countries": "GLOBAL",
    "wb_ids_indicators": "GLOBAL",
    "wb_wdi_indicators": "GLOBAL",
    "wb_wdi_values": "GLOBAL",
    "who_xmart_indicators": "GLOBAL",
    "who_xmart_values": "GLOBAL",
}
