"""economy cli — domain command-face registration (the eighth domain, 0.3.23; 0.3.24 expansion).

register(v, g): registers the flat commands onto the domain subparser (g = root _leaf_globals
factory, passed in as a parameter to avoid a cli <-> domain-cli cycle); FLAT = flat dispatch table,
merged by the root cli for main to use.

Face order = lexicographic over the English identifiers (the 0.3.12 contract guard): within the
domain the faces group by source automatically (bis / ecb / eurostat / fred / ilo_stat /
imf_sdmx / un_comtrade / unsd_sdg / wb / who_xmart).
"""


def register(v, g):
    f1 = v.add_parser("bis_sdmx_series", parents=[g()],
                      description="BIS SDMX series (realtime, local execution; /api/v1/data/{flow}/{key}/all, the SDMX 2.1 generic-CSV channel; key = the raw dot-separated series key with AT LEAST two segments — the segment order is flow-specific: WS_CBPOL FREQ.REF_AREA (M.US), WS_DSR FREQ.BORROWERS_CTY.DSR_BORROWERS (Q.US.N), WS_XRU FREQ.REF_AREA.CURRENCY.COLLECTION (M.CN.CNY.E); a one-segment key is every area at once — a multi-megabyte answer; a wrong key answers 404 with an SDMX error, which is not a block; --start / --end are the upstream startPeriod / endPeriod bounds)")
    f1.add_argument("--flow", required=True, help="BIS dataflow id (e.g. WS_CBPOL, WS_DSR, WS_XRU)")
    f1.add_argument("--key", required=True, help="SDMX series key, >= 2 dot-separated segments (e.g. M.US, Q.US.N, M.CN.CNY.E)")
    f1.add_argument("--start", default=None, help="Period window start (upstream param: startPeriod)")
    f1.add_argument("--end", default=None, help="Period window end (upstream param: endPeriod)")

    f2 = v.add_parser("ecb_fx_rates", parents=[g()],
                      description="ECB euro reference rate for one currency (realtime, local execution; /EXR/D.{CCY}.EUR.SP00.A?format=csvdata; the value is units of {currency} per 1 EUR and the date travels with every row; --start / --end are the upstream startPeriod / endPeriod bounds and one of them is required; the historical eurofxref CSV is a stale 2010 snapshot and is not used)")
    f2.add_argument("--currency", required=True, help="ISO 4217 currency code (e.g. USD, JPY, GBP)")
    f2.add_argument("--start", default=None, help="Window start date (upstream param: startPeriod)")
    f2.add_argument("--end", default=None, help="Window end date (upstream param: endPeriod)")

    f3 = v.add_parser("eurostat_table", parents=[g()],
                      description="Eurostat table query (realtime, local execution; /data/{table}; geo / time / --dim k=v are the upstream dimension filters — SEVERAL values are REPEATED parameters (the '+' form is a 400 and the comma form silently yields zero cells); --since / --until are the upstream sinceTimePeriod / untilTimePeriod bounds; the JSON-stat grid is decoded into flat rows; a geo outside the table yields zero cells and no upstream error)")
    f3.add_argument("--table", required=True, help="Eurostat table code (e.g. tec00001, demo_pjan, nama_10_a64)")
    f3.add_argument("--geo", action="append", default=None, metavar="CODE",
                    help="Geopolitical entity filter (repeatable, e.g. DE; several codes become repeated upstream parameters)")
    f3.add_argument("--time", action="append", default=None, metavar="PERIOD",
                    help="Time filter (repeatable, e.g. 2023)")
    f3.add_argument("--dim", action="append", default=None, metavar="K=V",
                    help="Any other dimension filter as k=v (repeatable, e.g. age=TOTAL, sex=T, unit=NR)")
    f3.add_argument("--since", default=None, help="Time window start (upstream param: sinceTimePeriod)")
    f3.add_argument("--until", default=None, help="Time window end (upstream param: untilTimePeriod)")
    f3.add_argument("--lang", default="EN", help="Upstream language (default EN)")

    f4 = v.add_parser("fred_series", parents=[g()],
                      description="FRED series observations (realtime, local execution; /fredgraph.csv?id=; ONE series id per call — several ids answer a ZIP archive the JSON transport cannot carry; an unknown series id answers an HTML error page and is reported as not-found; a missing observation is null; --start / --end are the upstream cosd / coed bounds)")
    f4.add_argument("--series", required=True, help="FRED series id (e.g. GDP, CPIAUCSL, DGS10)")
    f4.add_argument("--start", default=None, help="Observation window start (upstream param: cosd)")
    f4.add_argument("--end", default=None, help="Observation window end (upstream param: coed)")

    f5 = v.add_parser("ilo_stat_indicator", parents=[g()],
                      description="ILOSTAT indicator for one country (realtime, local execution; /data/indicator/; the format flag is the query parameter format=json — a path suffix is a 400/404; --ref-area (ISO-3) is required — the world-wide answer is orders of magnitude bigger; --time-from / --time-until are the upstream timefrom / timeto bounds — the upstream spells the upper bound 'timeto' and silently ignores 'timeuntil'; the urllib channel is the working one on this host — the curl stack answers an empty 200)")
    f5.add_argument("--indicator", required=True, help="ILOSTAT indicator code (e.g. EMP_TEMP_SEX_ECO_NB_A)")
    f5.add_argument("--ref-area", dest="ref_area", required=True, help="Country ISO-3 code (e.g. USA)")
    f5.add_argument("--time-from", dest="time_from", default=None, help="Year window start (upstream param: timefrom)")
    f5.add_argument("--time-until", dest="time_until", default=None, help="Year window end (upstream param: timeto)")
    f5.add_argument("--sex", default=None, help="Sex dimension filter (upstream param: sex)")
    f5.add_argument("--classif", default=None, help="Classification dimension filter (upstream param: classif1)")
    f5.add_argument("--source", default=None, help="Source filter (upstream param: source)")

    f6 = v.add_parser("imf_sdmx_series", parents=[g()],
                      description="IMF SDMX series (realtime, local execution; /external/sdmx/2.1/data/{flow}/{COUNTRY.INDICATOR[.FREQUENCY]}, the SDMX 2.1 generic-CSV channel; --country AND --indicator are both required — the country-only key is the multi-megabyte wall; the key shape fits the WEO/GDD/CPI family, NOT UNFCCC whose dimensions insert INDUSTRY/GAS_TYPE before the indicator; --start / --end are the upstream startPeriod / endPeriod bounds; OBS_VALUE carries the true value — SCALE is only a display hint)")
    f6.add_argument("--flow", required=True, help="IMF dataflow id (e.g. WEO, GDD, CPI)")
    f6.add_argument("--country", required=True, help="Country code as the dataflow spells it (ISO-3 in WEO/GDD, e.g. USA)")
    f6.add_argument("--indicator", required=True, help="Indicator code (e.g. NGDP_RPCH = real GDP growth)")
    f6.add_argument("--frequency", default=None, help="Optional trailing key dimension (e.g. A)")
    f6.add_argument("--start", default=None, help="Period window start (upstream param: startPeriod)")
    f6.add_argument("--end", default=None, help="Period window end (upstream param: endPeriod)")

    f7 = v.add_parser("un_comtrade_trade", parents=[g()],
                      description="UN Comtrade trade mirror, public preview (realtime, local execution; /public/v1/preview/{type}/{freq}/{cl}; --reporter / --partner take an ISO-3 code or the numeric area code — the ISO3 is translated through the area reference, whose historical and duplicate rows make a naive map wrong (USA = 842, not 840 or 841); --period 2023 / 202301; --cmd is the commodity code (comma list, TOTAL = all goods); --flow X / M / 'X,M'; the preview answers at most 500 records)")
    f7.add_argument("--reporter", required=True, help="Reporting country: ISO-3 (e.g. USA) or the numeric area code")
    f7.add_argument("--period", required=True, help="Period (e.g. 2023 or 202301)")
    f7.add_argument("--partner", default=None, help="Partner area: ISO-3 or numeric code (0 / W00 = the World aggregate)")
    f7.add_argument("--cmd", default=None, help="Commodity code, comma list allowed (default TOTAL = all goods)")
    f7.add_argument("--flow", default=None, help="Trade flow: X (export), M (import), 'X,M'")
    f7.add_argument("--type-code", dest="type_code", default="C", help="Path segment: commodity type (C)")
    f7.add_argument("--freq-code", dest="freq_code", default="A", help="Path segment: frequency (A = annual)")
    f7.add_argument("--cl-code", dest="cl_code", default="HS", help="Path segment: classification (HS)")
    f7.add_argument("--max-records", dest="max_records", type=int, default=500,
                    help="Records per call (upstream param: maxRecords; 1-500)")
    f7.add_argument("--partner2", default=None, help="Second partner area (upstream param: partner2Code)")
    f7.add_argument("--customs", default=None, help="Customs regime (upstream param: customsCode)")
    f7.add_argument("--mot", default=None, help="Mode of transport (upstream param: motCode)")

    f8 = v.add_parser("unsd_sdg_indicators", parents=[g()],
                      description="UNSD SDG indicator catalog (realtime, local execution; /Indicator/List — 251 indicators over the 17 goals, each row carrying its series codes (713 in total) nested inside; the upstream answers the whole catalog in one payload — --page / --per-page slice it locally and --search is a LOCAL keyword scan over the whole catalog, never an upstream filter)")
    f8.add_argument("--page", type=int, default=1, help="Local page slice (the upstream payload is whole)")
    f8.add_argument("--per-page", dest="per_page", type=int, default=50, help="Local page size (1-500)")
    f8.add_argument("--search", default=None, help="Local keyword scan (code / description / series codes)")

    f9 = v.add_parser("unsd_sdg_series", parents=[g()],
                      description="UNSD SDG series observations (realtime, local execution; /Series/Data?seriesCode= — series granularity only: the whole-indicator endpoint is a 3.2M-row wall that is never formed; --geo is a LOCAL filter over the fetched page matching the geoAreaCode or geoAreaName — the upstream 'area' parameter is DECORATIVE, byte-identical with and without it; --time is the upstream timePeriod filter, the one upstream filter that works on this endpoint)")
    f9.add_argument("--series", required=True, help="SDG series code (e.g. SI_POV_DAY1, DC_ODA_POVLG — list them with unsd_sdg_indicators)")
    f9.add_argument("--geo", default=None, help="Local geo filter: geoAreaCode or geoAreaName, case-insensitive (e.g. 842, China)")
    f9.add_argument("--time", default=None, help="Period filter (upstream param: timePeriod, e.g. 2020)")
    f9.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    f9.add_argument("--page-size", dest="page_size", type=int, default=100,
                    help="Rows per page (upstream param: pageSize; 1-1000)")

    f10 = v.add_parser("wb_countries", parents=[g()],
                       description="World Bank country reference (realtime, local execution; /v2/country; ISO3 / ISO2 / region / income level / lending type / coordinates — the income band is the buyer-screen dimension; the 296 entries include the aggregate regions)")
    f10.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    f10.add_argument("--per-page", dest="per_page", type=int, default=100,
                     help="Rows per page (upstream param: per_page; 1-1000)")

    f11 = v.add_parser("wb_ids_indicators", parents=[g()],
                       description="World Bank International Debt Statistics catalog (realtime, local execution; /v2/indicator with source pinned to 6 = IDS — 577 indicators in seven debt families: DOD stocks / INT interest / AMT disbursements / DIS / NFL net flows / NTR / TDS service plus the balance-of-payments mirrors; the per-page default 600 holds the whole catalog in one page; the VALUES of the DT.* codes are served by wb_wdi_values WITHOUT a source parameter — the value endpoint breaks with source=6 and the API silently falls back to sourceid 2)")
    f11.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    f11.add_argument("--per-page", dest="per_page", type=int, default=600,
                     help="Rows per page (upstream param: per_page; 1-1000; 600 = the whole catalog)")
    f11.add_argument("--search", default=None, help="Local keyword scan over the page (code / name / organization)")

    f12 = v.add_parser("wb_wdi_indicators", parents=[g()],
                       description="World Bank indicator catalog (realtime, local execution; /v2/indicator?source=; source 2 = WDI — without it the catalog is every World Bank source at once (29,544 rows); --search is a LOCAL keyword scan over the returned page, not an upstream filter)")
    f12.add_argument("--source", default=2, help="World Bank source id (2 = WDI, the default)")
    f12.add_argument("--page", type=int, default=1, help="Page number (upstream param: page)")
    f12.add_argument("--per-page", dest="per_page", type=int, default=500,
                     help="Rows per page (upstream param: per_page; 1-1000)")
    f12.add_argument("--search", default=None, help="Local keyword scan over the page (code / name / organization)")

    f13 = v.add_parser("wb_wdi_values", parents=[g()],
                       description="World Bank WDI indicator values (realtime, local execution; /v2/country/{country}/indicator/{indicator}; country = ISO3, several codes joined by ';'; ONE indicator code per call — the upstream rejects several codes in one call (\"120 Invalid value\"); date = YYYY or YYYY:YYYY; a missing observation is null, never fabricated)")
    f13.add_argument("--country", required=True, help="ISO3 country code (e.g. CHN; several codes may be joined by ';')")
    f13.add_argument("--indicator", required=True, help="WDI indicator code (e.g. NY.GDP.MKTP.CD, or a DT.* IDS code — WITHOUT --source)")
    f13.add_argument("--date", default=None, help="Year or year window (upstream param: date; 'YYYY' or 'YYYY:YYYY')")
    f13.add_argument("--per-page", dest="per_page", type=int, default=100,
                     help="Rows per page (upstream param: per_page; 1-1000)")

    f14 = v.add_parser("who_xmart_indicators", parents=[g()],
                       description="WHO xMart indicator directory (realtime, local execution; IND_DIRECTORY_WIDE — 1,561 indicators, each row carrying IND_URI_API (the per-indicator API diameter) and IND_URI_WEB; --filter is the raw upstream OData $filter; --search is a LOCAL keyword scan over the returned page)")
    f14.add_argument("--filter", default=None, help="Raw upstream OData $filter (e.g. \"IND_NAME eq 'TB_ppm_enrol_tx_prct'\")")
    f14.add_argument("--top", type=int, default=500, help="Page size (upstream param: $top; 1-5000)")
    f14.add_argument("--skip", type=int, default=0, help="Offset (upstream param: $skip)")
    f14.add_argument("--search", default=None, help="Local keyword scan over the page (name / unit / web URI)")

    f15 = v.add_parser("who_xmart_values", parents=[g()],
                       description="WHO xMart indicator observations (realtime, local execution; DATA_/{entity set}; the entity set is resolved from the directory row's IND_URI_API — when several entity sets carry the same indicator name the candidate list is NOT auto-picked, pass --entity-set; --geo takes an ISO-3 country (translated through REF_GEO_WIDE into the M49 code) or a raw M49 code; --year is the DIM_TIME string value)")
    f15.add_argument("--indicator", required=True, help="Indicator code (e.g. TB_ppm_enrol_tx_prct)")
    f15.add_argument("--geo", default=None, help="Country: ISO-3 (e.g. PAK) or the raw M49 code")
    f15.add_argument("--year", default=None, help="Observation year (DIM_TIME, a string value)")
    f15.add_argument("--entity-set", dest="entity_set", default=None,
                     help="WHO entity set (e.g. RELAY_TBPPM) — resolved from the directory when omitted")
    f15.add_argument("--top", type=int, default=500, help="Page size (upstream param: $top; 1-5000)")
    f15.add_argument("--skip", type=int, default=0, help="Offset (upstream param: $skip)")


FLAT = {
    # economy (0.3.23 + 0.3.24): the country-level denominator layer — macro indicators,
    # reference rates, official statistics and the trade mirror (upstream param names verbatim
    # + our defaults; lambdas only shuttle names across namespaces)
    "bis_sdmx_series": lambda a: {"flow": a.flow, "key": a.key, "start": a.start, "end": a.end},
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
    "ecb_fx_rates": "EU",
    "eurostat_table": "EU",
    "fred_series": "US",
    "ilo_stat_indicator": "GLOBAL",
    "imf_sdmx_series": "GLOBAL",
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
