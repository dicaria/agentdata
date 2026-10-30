"""research cli — domain command-face registration (split per domain in 0.2.6, migrated from the root cli.py).

register(v, g): registers verb-compat faces + flat commands onto the domain subparser (g = root _leaf_globals
factory, passed in as a parameter to avoid a cli <-> domain-cli cycle); FLAT = flat dispatch table, merged by
the root cli for main to use.
"""
import argparse

def register(v, g):
    f1 = v.add_parser("biorxiv_details", parents=[g()],
                      description="bioRxiv preprint metadata window stream (realtime, local execution; /details/biorxiv/{from}/{to}/{cursor}; authors arrive as a semicolon-joined string and jatsxml is a full-text XML URL, not inline — full-text bulk belongs to the jatsxml_url links; message counts are strings upstream, normalized here)")
    f1.add_argument("--from-date", dest="from_date", required=True, help="Window start YYYY-MM-DD")
    f1.add_argument("--to-date", dest="to_date", required=True, help="Window end YYYY-MM-DD")
    f1.add_argument("--cursor", type=int, default=0, help="Page index (0-based)")

    f2 = v.add_parser("crossref_works", parents=[g()],
                      description="Crossref works search with funder bridge (realtime, local execution; query full-text × funder DOI (filter=funder:) × award_number (filter=award.number:, requires --funder) × from/to publication window combine AND; award numbers live only inside rows' funders[].award — select cannot fetch them (probe: select-not-available); offset+rows ≤ 10,000 documented upstream wall — deep paging switches to --cursor, the official deep-pager channel (0.2.9 audit)")
    f2.add_argument("--query", default=None, help="Full-text query")
    f2.add_argument("--funder", default=None, help="Funder DOI (e.g. 10.13039/100000001 = NSF)")
    f2.add_argument("--award-number", dest="award_number", default=None,
                    help="Award/grant number (requires --funder)")
    f2.add_argument("--from-pub-date", dest="from_pub_date", default=None,
                    help="Publication window start YYYY-MM-DD (upstream filter: from-pub-date; 0.2.9 audit)")
    f2.add_argument("--to-pub-date", dest="to_pub_date", default=None,
                    help="Publication window end YYYY-MM-DD (upstream filter: until-pub-date; 0.2.9 audit)")
    f2.add_argument("--rows", type=int, default=25, help="Rows (upstream param: rows; 1-100 politeness, upstream doc cap 1000)")
    f2.add_argument("--offset", type=int, default=0, help="Result offset (offset+rows ≤ 10,000; mutually exclusive with --cursor)")
    f2.add_argument("--cursor", default=None,
                    help="Deep-pager cursor ('*' for first page, then feed next_cursor; bypasses the 10,000 offset wall; 0.2.9 audit)")

    f3 = v.add_parser("gtr_projects", parents=[g()],
                      description="UK UKRI Gateway to Research projects (realtime, local execution; /projects?q=&s=&p=; s ≥ 10 is an upstream 400 wall; upstream sends no total — full page signals more via has_more; organisation edges live one hop deeper in detail links.link[] rel=LEAD_ORG, this face is the list only)")
    f3.add_argument("--q", required=True, help="Search term")
    f3.add_argument("--s", type=int, default=20, help="Page size (upstream param: s; ≥10)")
    f3.add_argument("--p", type=int, default=1, help="Page number (upstream param: p)")

    f4 = v.add_parser("icite_pubs", parents=[g()],
                      description="NIH iCite citation-impact card for a PubMed paper (realtime, local execution; /api/pubs?pmids= single record; RCR/FCR/citation counts — the impact hop after nih_reporter_publications hands you a pmid)")
    f4.add_argument("--pmid", required=True, help="PubMed id (digits only, e.g. 26017442)")

    f5 = v.add_parser("nih_reporter_projects", parents=[g()],
                      description="NIH RePORTER project search (realtime, local execution; POST /v2/projects/search; criteria=snake_case and include_fields=camelCase are separately hard-bound upstream — wrong shapes are silently ignored, so bare passthrough is not exposed; org match is exact, not fuzzy; offset+limit cap 15,000)")
    f5.add_argument("--org-name", dest="org_name", default=None,
                    help="Receiving organization name (exact match upstream; scalar auto-wrapped into org_names array)")
    f5.add_argument("--fiscal-year", dest="fiscal_year", type=int, default=None,
                    help="Fiscal year (goes into fiscal_years array)")
    f5.add_argument("--include-fields", dest="include_fields", default=None,
                    help="Comma list of camelCase fields (upstream include_fields; wrong names are silently ignored upstream)")
    f5.add_argument("--limit", type=int, default=25, help="Page size (upstream param: limit; 1-500)")
    f5.add_argument("--offset", type=int, default=0, help="Result offset (offset+limit ≤ 15,000)")

    f6 = v.add_parser("nih_reporter_publications", parents=[g()],
                      description="NIH funding↔publication bridge (realtime, local execution; POST /v2/publications/search; criteria recognizes ONLY pmids/appl_ids — every other key is silently ignored upstream and dumps the whole 8.3M table, so the local gate requires one of the two and no other criteria is passed through; rows are a 3-key bridge {coreproject, pmid, applid}; zero rows = no linkage on record, sparseness is a real answer)")
    f6.add_argument("--pmids", dest="pmids", default=None,
                    help="Comma list of PubMed ids (criteria.pmids)")
    f6.add_argument("--appl-ids", dest="appl_ids", default=None,
                    help="Comma list of NIH application ids from nih_reporter_projects (criteria.appl_ids)")
    f6.add_argument("--limit", type=int, default=25, help="Page size (upstream param: limit; 1-500)")
    f6.add_argument("--offset", type=int, default=0, help="Result offset")

    f7 = v.add_parser("nsf_awards", parents=[g()],
                      description="US NSF awards search (realtime, local execution; keyword full-text XOR id point lookup; rpp 1-200 per upstream doc; upstream sends no total — full page signals more via has_more)")
    f7.add_argument("--keyword", default=None, help="Full-text search keyword (XOR --id)")
    f7.add_argument("--id", default=None, help="NSF award id, point lookup (XOR --keyword)")
    f7.add_argument("--rpp", type=int, default=25, help="Results per page (upstream param: rpp; 1-200)")
    f7.add_argument("--offset", type=int, default=0, help="Result offset for pagination")

    f8 = v.add_parser("openalex_institutions", parents=[g()],
                      description="Research-institution candidate search (realtime, local execution; /institutions?search=; same-name multi-country clones coexist — the candidate list is NOT auto-picked: choose the ROR explicitly, then query output via openalex_works --ror)")
    f8.add_argument("--search", required=True, help="Institution name (e.g. pfizer)")
    f8.add_argument("--per-page", dest="per_page", type=int, default=25,
                    help="Results per page (upstream param: per-page; 1-200)")

    f9 = v.add_parser("openalex_works", parents=[g()],
                      description="Global scholarly works search (realtime, local execution; api.openalex.org/works; search full-text × ror institution edge × doi × title_search combine AND into filter=; per_page 1-200 (explicit upstream 400 wall); cursor pagination via meta.next_cursor — the cursor encodes paging only, so re-send the same constraints when continuing; select is force-merged with core fields so slimming cannot strip id/doi/display_name/authorships/open_access)")
    f9.add_argument("--search", default=None, help="Full-text search term")
    f9.add_argument("--ror", default=None, help="ROR id (bare 01xdqrp08 or full https://ror.org/… → filter=institutions.ror:)")
    f9.add_argument("--doi", default=None, help="DOI exact match (filter=doi:)")
    f9.add_argument("--title-search", dest="title_search", default=None,
                    help="Title substring match (filter=title.search:)")
    f9.add_argument("--per-page", dest="per_page", type=int, default=25,
                    help="Results per page (upstream param: per-page; 1-200)")
    f9.add_argument("--cursor", default=None, help="Pagination cursor from next_cursor (constraints must be re-sent)")
    f9.add_argument("--select", default=None,
                    help="Comma list of extra fields (core fields are force-merged, never stripped)")

    f10 = v.add_parser("opencitations_citations", parents=[g()],
                      description="OpenCitations COCI citing-DOI list (realtime, local execution; /index/v1/citations/{doi}; doi: prefix and doi.org URLs are normalized away — upstream 400s otherwise; upstream limit param is silently ignored (probe: ?limit=3 still returns all 217) so no fake pagination, the full list comes back with a count)")
    f10.add_argument("--doi", required=True, help="Cited DOI (doi: prefix auto-stripped)")

FLAT = {
    # research (grants axis stood up in 0.2.2, renamed research with 8 more faces in 0.2.4) / security 0.2.2 flat panel
    # (upstream param names verbatim + our defaults; lambdas only shuttle names across namespaces)
    "biorxiv_details": lambda a: {"from_date": a.from_date, "to_date": a.to_date, "cursor": a.cursor},
    "crossref_works": lambda a: {"query": a.query, "funder": a.funder, "award_number": a.award_number,
                                 "rows": a.rows, "offset": a.offset, "cursor": a.cursor,
                                 "from_pub_date": a.from_pub_date, "to_pub_date": a.to_pub_date},
    "gtr_projects": lambda a: {"q": a.q, "s": a.s, "p": a.p},
    "icite_pubs": lambda a: {"pmid": a.pmid},
    "nih_reporter_projects": lambda a: {"org_name": a.org_name, "fiscal_year": a.fiscal_year,
                                        "include_fields": [x for x in (a.include_fields or "").split(",") if x.strip()] or None,
                                        "limit": a.limit, "offset": a.offset},
    "nih_reporter_publications": lambda a: {"pmids": [int(x) for x in (a.pmids or "").split(",") if x.strip()] or None,
                                            "appl_ids": [int(x) for x in (a.appl_ids or "").split(",") if x.strip()] or None,
                                            "limit": a.limit, "offset": a.offset},
    "nsf_awards": lambda a: {"keyword": a.keyword, "id": a.id, "rpp": a.rpp, "offset": a.offset},
    "openalex_institutions": lambda a: {"search": a.search, "per_page": a.per_page},
    "openalex_works": lambda a: {"search": a.search, "ror": a.ror, "doi": a.doi,
                                 "title_search": a.title_search, "per_page": a.per_page,
                                 "cursor": a.cursor, "select": a.select},
    "opencitations_citations": lambda a: {"doi": a.doi},
}


# 0.3.10 jurisdiction chapter: face → jurisdiction (default = issuing authority's jurisdiction; institutions
# covering global phenomena = GLOBAL; vocabulary ISO-3166 alpha-2 + EU + GLOBAL) —— merged by the root cli.py
# into _JURISDICTION, the success envelope carries a jurisdiction chapter
COUNTRY = {
    "biorxiv_details": "GLOBAL",
    "crossref_works": "GLOBAL",
    "gtr_projects": "GB",
    "icite_pubs": "US",
    "nih_reporter_projects": "US",
    "nih_reporter_publications": "US",
    "nsf_awards": "US",
    "openalex_institutions": "GLOBAL",
    "openalex_works": "GLOBAL",
    "opencitations_citations": "GLOBAL",
}
