"""agentdata.cli — the dual command-line entry (console_scripts `agentdata` + `python -m agentdata`).

Exit-code contract: 0 success / 1 upstream-availability family / 2 usage family (api.md section 9.4).
enrichment works with zero config; the corpus family needs --base-url/--api-key (or env
AGENTDATA_BASE_URL / AGENTDATA_API_KEY).
"""
import argparse
import json
import sys
import uuid

from . import __version__
from . import capabilities as capabilities_mod
from .client import Client
from .company import cli as company_cli
from .economy import cli as economy_cli
from .esg import cli as esg_cli
from .healthcare import cli as healthcare_cli
from .legal import cli as legal_cli
from .procurement import cli as procurement_cli
from .research import cli as research_cli
from .security import cli as security_cli

# 0.2.6 per-domain split: the domain command registrars (register(v, g)) live in each domain's cli.py;
# the root keeps only the shared parts plus the search/read dispatch
# 0.3.10 domain order = lexicographic (DOMAIN_ORDER is the source of truth — the build_parser loop, per-domain face order, and site navigation all follow it; the sort key is the English identifier)
DOMAIN_ORDER = ("company", "economy", "esg", "healthcare", "legal", "procurement", "research", "security")
_CLI = {"company": company_cli, "economy": economy_cli, "esg": esg_cli,
        "healthcare": healthcare_cli, "legal": legal_cli, "procurement": procurement_cli,
        "research": research_cli, "security": security_cli}
from .errors import SdkError


def _filter_arg(pairs):
    """--filter 'k=v' / 'k=v1|v2' / 'k>=v' / 'k>v' / 'k<=v' / 'k<v' -> a DSL node."""
    filters = {}
    for raw in pairs or []:
        for op_key, op in ((">=", "gte"), ("<=", "lte"), (">", "gt"), ("<", "lt")):
            if op_key in raw:
                k, _, v = raw.partition(op_key)
                filters.setdefault(k, {"range": {}})["range"][op] = _cast(v)
                break
        else:
            k, _, v = raw.partition("=")
            if "|" in v:
                filters[k] = {"any": v.split("|")}
            else:
                filters[k] = {"eq": _cast(v)}
    return filters


def _cast(v):
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        return v


def _leaf_globals():
    """Global flags placed after a subcommand (the README example shape `agentdata company search … --api-key x`).
    The dest gets a sub_ prefix + default=argparse.SUPPRESS: when argparse enters a subparser it opens
    a separate namespace, parses there and writes the whole thing back into the parent namespace, so a
    dest that carries a default overwrites the value the parent just parsed —
    a global flag between the domain and the verb (`agentdata healthcare --no-cache epmc_search …`)
    is therefore swallowed silently (reproduced by measurement on 2026-10-20). Under SUPPRESS a dest
    that never appeared does not land in the namespace, so the parent's value survives; every read
    uses getattr(…, default)."""
    g = argparse.ArgumentParser(add_help=False)
    g.add_argument("--base-url", dest="sub_base_url", default=argparse.SUPPRESS, metavar="URL", help="Hosted API base URL (env AGENTDATA_BASE_URL)")
    g.add_argument("--api-key", dest="sub_api_key", default=argparse.SUPPRESS, metavar="PAT", help="Bearer PAT (env AGENTDATA_API_KEY)")
    g.add_argument("--cache-dir", dest="sub_cache_dir", default=argparse.SUPPRESS, metavar="DIR", help="Cache directory (env AGENTDATA_CACHE_DIR)")
    g.add_argument("--no-cache", dest="sub_no_cache", action="store_true", default=argparse.SUPPRESS, help="Bypass the cache for this call")
    g.add_argument("--execution", dest="sub_execution", default=argparse.SUPPRESS, choices=["local", "hosted", "auto"], help="Realtime execution location (default auto -> local; realtime faces support local execution only — the hosted corpus uses --base-url/--api-key)")
    return g


def _no_abbrev(v):
    """Turn off argument abbreviation for every subparser registered on this verb parser.

    argparse does NOT inherit allow_abbrev into a subparser: the root's setting would leave every
    face parser at the default True, where `--api-k` silently becomes `--api-key` and a mistyped
    flag is accepted as a prefix of a real one. Wrapping the registrar once per domain is far
    cheaper than touching 172 call sites."""
    orig = v.add_parser

    def add_parser(name, **kw):
        kw.setdefault("allow_abbrev", False)
        return orig(name, **kw)

    v.add_parser = add_parser


def build_parser():
    p = argparse.ArgumentParser(prog="agentdata", allow_abbrev=False,
                                description="AgentData SDK CLI (corpus queries via the hosted API + realtime queries executed locally)")
    p.add_argument("--version", action="version", version=f"agentdata {__version__}")
    p.add_argument("--base-url", default=None, metavar="URL", help="Hosted API base URL (env AGENTDATA_BASE_URL)")
    p.add_argument("--api-key", default=None, metavar="PAT", help="Bearer PAT (env AGENTDATA_API_KEY)")
    p.add_argument("--cache-dir", default=None, metavar="DIR", help="Cache directory (env AGENTDATA_CACHE_DIR)")
    p.add_argument("--no-cache", action="store_true", help="Bypass the cache for this call")
    p.add_argument("--execution", default="auto", choices=["local", "hosted", "auto"],
                   help="Realtime execution location (default auto -> local; realtime faces support local execution only — the hosted corpus uses --base-url/--api-key)")
    sub = p.add_subparsers(dest="domain", required=True)
    for domain in DOMAIN_ORDER:
        d = sub.add_parser(domain, parents=[_leaf_globals()], allow_abbrev=False)
        # metavar="FACE": the usage line stops listing every face name (the legal domain alone
        # spelled 38 of them across three lines) while the per-face catalog below stays intact —
        # argparse lists a subcommand individually as long as it was registered with a help= line.
        v = d.add_subparsers(dest="verb", required=True, metavar="FACE")
        _no_abbrev(v)
        _CLI[domain].register(v, _leaf_globals)

        s = v.add_parser("search", parents=[_leaf_globals()], help="Corpus search (hosted)",
                         description="Corpus search (hosted, PAT required): filters/record_kind/level/pagination")
        s.add_argument("--filter", action="append", default=[], metavar="K=V", help="Filter K=V (repeatable)")
        s.add_argument("--record-kind", default=None, help="Record kind (closed set from the domain spec)")
        s.add_argument("--facets", default=None, help="Comma-separated fields (facet counts)")
        s.add_argument("--level", default="tier1", choices=["tier1", "tier2", "tier3"], help="T-layer depth (default tier1)")
        s.add_argument("--limit", type=int, default=50, help="Page size (default 50, ≤1000)")
        s.add_argument("--cursor", default=None, help="Pagination cursor (feed next_cursor from the response)")
        s.add_argument("--mode", default=None, choices=["screen"], help="Special mode (screen: batch screening; requires --input)")
        s.add_argument("--input", default=None, help="Input JSONL file for batch-screening mode (--mode screen)")

        rd = v.add_parser("read", parents=[_leaf_globals()], help="Corpus record (hosted)",
                          description="Corpus single-record read (hosted): id + T-layer depth")
        rd.add_argument("--id", required=True, help="Subject id")
        rd.add_argument("--level", default="tier1", choices=["tier1", "tier2", "tier3"], help="T-layer depth (default tier1)")

    # hub family (RFC-002 §3.4/3.5): PAT -> short-lived subject JWT -> allowlisted GET; a command
    # group of its own so the eight domain dispatch tables above stay untouched
    h = sub.add_parser("hub", parents=[_leaf_globals()], help="Hub family (PAT to short-lived JWT to allowlisted GET)",
                       description="Hub family (RFC-002): exchange the PAT for a short-lived subject JWT, then GET allowlisted OmniHub paths. The PAT is never printed.")
    hv = h.add_subparsers(dest="hub_verb", required=True)
    ht = hv.add_parser("token", parents=[_leaf_globals()],
                       help="Exchange the PAT for a short-lived Hub subject JWT (prints the access_token envelope, never the PAT)")
    ht.add_argument("--token-url", default=None, help="Downstream-token endpoint (env AGENTDATA_TOKEN_URL)")
    hg = hv.add_parser("get", parents=[_leaf_globals()],
                       help="Allowlisted GET against the Hub (query built only from --param)")
    hg.add_argument("--path", required=True, help="Allowlisted path (RFC-002 §3.5, e.g. /v1/company/companies:search)")
    hg.add_argument("--param", action="append", default=[], metavar="K=V", help="Query parameter K=V (repeatable; strings verbatim)")
    hg.add_argument("--token-url", default=None, help="Downstream-token endpoint (env AGENTDATA_TOKEN_URL)")
    hg.add_argument("--hub-base-url", default=None, help="Hub base URL (env AGENTDATA_HUB_BASE_URL)")

    # The discovery surface (0.3.52): the face table rendered from the command tree. It needs no
    # base URL and no PAT — it describes what this installed package can run.
    cap = sub.add_parser("capabilities", allow_abbrev=False,
                          help="Face table (discovery: every face, its summary and its parameters)",
                          description="The face table rendered from the command tree: every realtime face with "
                                      "its one-line summary, its parameters (closed sets, required flags) and its "
                                      "jurisdiction, plus the hosted corpus family. Generated, not maintained by "
                                      "hand — it cannot drift from the commands it describes.")
    cap.add_argument("--format", choices=["json", "md"], default="json", help="Output format (default json)")
    cap.add_argument("--domain-filter", dest="domain_filter", default=None, choices=list(DOMAIN_ORDER),
                     help="Limit the listing to one domain")
    cap.add_argument("--face", dest="face_filter", default=None, help="Limit the listing to one face (exact name)")
    return p


# 0.2.6 per-domain split: the source of truth for the flat dispatch table is each domain's cli.FLAT,
# merged here (the search/read dispatch stays in this module's main)
_FLAT_DISPATCH = {}
for _m in _CLI.values():
    _FLAT_DISPATCH.update(_m.FLAT)
assert len(_FLAT_DISPATCH) == 180, f"flat dispatch {len(_FLAT_DISPATCH)} != 161 (161 faces; 0.3.2 esg +2 + 0.3.3 European registries +5 + 0.3.4 FR recherche +1 + 0.3.5 esg port-state +5 + 0.3.6 World Bank/NY +3 + 0.3.8 legal TNA caselaw +2 + 0.3.12 UNGM/NY OGS collection +2 + 0.3.14 CO RUES/KR hometax +2 + 0.3.16 legal co_sic +1 + healthcare gb_mhra +2 + 0.3.19 healthcare CA DPD/MDALL +4 + rasff/safety_gate +3 + 0.3.21 legal debarment rosters afdb/ca_sema/idb/wb +4 + 0.3.22 transport compliance euasl_datasets +1 + 0.3.23 economy domain (wb/eurostat/ecb/fred/who_xmart/un_comtrade/ilo_stat) +10 + 0.3.24 economy expansion (imf_sdmx/bis/unsd_sdg/wb_ids) +5 + 0.3.25 security EUVD (euvd) +2 + 0.3.26 economy expansion (comext/oecd_sdmx) +2 + 0.3.27 legal gazette/ie_revenue +2 + 0.3.28 legal us_occ +1 + 0.3.29 economy bls_series +1 + 0.3.30 company NZ Companies Office nzco_companies/nzco_directors +2 + 0.3.31 legal CFPB cfpb_complaints/cfpb_suggest_company +2 + 0.3.32 company CZ ARES cz_ares_ekonomicke_subjekty/cz_ares_ekonomicke_subjekty_vyhledat +2 + 0.3.33 company offshore Channel Islands gg_gfsc_regulated_entities/gg_gfsc_registered_businesses/je_jfsc_regulated_entities +3 + 0.3.34 company KZ GBD_UL kz_gbd_ul_companies +1 + 0.3.35 IN SEBI legal in_sebi_orders/company in_sebi_intermediaries+in_sebi_default_brokers +3 + 0.3.36 TR SPK legal tr_spk_fines+tr_spk_bans/company tr_spk_listed +3 + 0.3.37 RU CBR legal ru_cbr_warning_list/company ru_cbr_credit_orgs +2 (first RU jurisdiction) + 0.3.38 BR BACEN legal br_bacen_regimes/company br_bacen_institutions+br_bacen_branches+br_bacen_domains+br_bacen_dasfn +5 (first BR jurisdiction) + 0.3.39 legal br_bacen_complaints rdrweb +1 + 0.3.40 company tr_bddk_institutions BDDK cards +1 + 0.3.41 company DE federal insolvency announcements de_inso_search/de_inso_register_lookup +2 (first DE jurisdiction) + 0.3.42 company JP FSA licensed farm jp_fsa_licensed +1 (first JP jurisdiction) + 0.3.43 company CA OSB CCAA roster ca_ccaa_records +1 + 0.3.44 company ES CNMV entidades register es_cnmv_entities +1 (first ES jurisdiction) + 0.3.45 company ES BORME daily gazette es_borme_day+es_borme_notice +2 (ES jurisdiction #2) + 0.3.46 company SG data.gov.sg open-data platform sg_datagovsg_datasets+sg_datagovsg_dataset_download +2 (first SG jurisdiction — the ACRA register of record rides the national platform) + 0.3.47 legal AT RIS OGD at_ris_judgments+at_ris_statutes +2 (first AT jurisdiction) + 0.3.48 company US state licenses tx_tdlr_licenses+wa_doh_credentials +2 (Socrata twin) + 0.3.49 company US city licenses chi_bacp_licenses+lacity_registrations+nyc_dcwp_licenses +3 (Socrata city trio) + 0.3.50 legal enforcement/party-finance tier us_ferc_elibrary+ie_sipo_lobbying+ee_erjk_quarterly_reports+ee_erjk_election_reports+ua_nazk_parties+ua_nazk_party_reports +6 (first EE and UA jurisdictions) + 0.3.51 legal enforcement tier-two fr_adlc_sanctions+it_arera_decisions+us_cftc_enforcement + company us_fmcsa_carriers +4 (first FR and IT legal jurisdictions) + 0.3.53 company fr_regafi_authorisations+fr_regafi_entities + esg uk_fhrs_establishments + healthcare us_npi_organizations +4; the csl_screening alias was removed in 0.3.0)"
# 0.3.10 jurisdiction chapter: face -> jurisdiction (default = the issuing authority's jurisdiction; institutions covering global phenomena = GLOBAL; vocabulary = ISO-3166 alpha-2 + EU + GLOBAL).
# The per-domain source of truth is each domain cli.py's COUNTRY (same face set as FLAT); the root only merges them; the success envelope carries a jurisdiction chapter (search/read are hosted mixed-jurisdiction corpus services — unstamped)
_JURISDICTION = {f: cc for _m in _CLI.values() for f, cc in _m.COUNTRY.items()}
assert set(_JURISDICTION) == set(_FLAT_DISPATCH), f"jurisdiction coverage {len(_JURISDICTION)} != dispatch faces {len(_FLAT_DISPATCH)}"
def _merge_globals(a):
    """Merge global flags: the ones placed after the subcommand (sub_*) win, the top level is the
    fallback — both placements work (the README example shape). sub_* are all SUPPRESS: if one never
    appeared the attribute does not exist, so every read falls back via getattr."""
    a.base_url = getattr(a, "sub_base_url", None) or a.base_url
    a.api_key = getattr(a, "sub_api_key", None) or a.api_key
    a.cache_dir = getattr(a, "sub_cache_dir", None) or a.cache_dir
    a.no_cache = a.no_cache or getattr(a, "sub_no_cache", False)
    a.execution = getattr(a, "sub_execution", None) or a.execution
    for k in ("sub_base_url", "sub_api_key", "sub_cache_dir", "sub_no_cache", "sub_execution"):
        if hasattr(a, k):
            delattr(a, k)
    return a


def _hub_params(pairs):
    """--param 'k=v' (repeatable) -> query dict; values stay verbatim strings."""
    params = {}
    for raw in pairs or []:
        k, _, v = raw.partition("=")
        if not k:
            raise SdkError("usage_error", detail=f"--param expects K=V, got {raw!r}")
        params[k] = v
    return params




def main(argv=None) -> int:
    # Force UTF-8 for piped/redirected output: on Chinese Windows the pipe defaults to CP936 and agents
    # or redirected consumers would receive bad bytes; the interactive console is already UTF-8 under
    # PEP 528, so reconfigure is imperceptible there. Guarded: replaced/captured stdout (tests) may
    # not be a TextIOWrapper.
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    parser = build_parser()
    a = _merge_globals(parser.parse_args(argv))
    if a.domain == "capabilities":
        # The discovery surface needs no credentials and no network: it is the command tree itself.
        caps = capabilities_mod.collect(parser, flat_faces=set(_FLAT_DISPATCH),
                                         jurisdiction=_JURISDICTION)
        caps = capabilities_mod.filter_caps(caps, domain=a.domain_filter, face=a.face_filter)
        print(capabilities_mod.render(caps, a.format))
        return 0
    try:
        c = Client(a.base_url, a.api_key, cache_dir=a.cache_dir, no_cache=a.no_cache,
                   execution=a.execution,
                   token_url=getattr(a, "token_url", None),
                   hub_base_url=getattr(a, "hub_base_url", None))
        if a.domain == "hub":
            if a.hub_verb == "token":
                out = c.hub.token_payload()
            else:  # argparse required=True leaves only "get"
                out = c.hub_get(a.path, _hub_params(a.param))
        else:
            d = getattr(c, a.domain)
            flat = _FLAT_DISPATCH.get(a.verb)
            if flat is not None:
                out = getattr(d, a.verb)(**flat(a))
                out["jurisdiction"] = _JURISDICTION[a.verb]  # 0.3.10 jurisdiction chapter: downstream can route by country without digging through docs
            elif a.verb == "search":
                screen_inputs = None
                if a.mode == "screen":
                    if not a.input:
                        raise SdkError("usage_error", detail="--mode screen requires --input x.jsonl")
                    with open(a.input, encoding="utf-8") as f:
                        screen_inputs = [json.loads(line) for line in f if line.strip()]
                out = d.search(filters=_filter_arg(a.filter), record_kind=a.record_kind,
                               facets=a.facets.split(",") if a.facets else None, level=a.level,
                               limit=a.limit, cursor=a.cursor, mode=a.mode, screen_inputs=screen_inputs)
            else:
                out = d.read(a.id, level=a.level)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except SdkError as e:
        # api.md section 9.5: request_id runs through both the success and error states (mirroring the
        # Node cli.mjs randomUUID emitted in both states)
        print(json.dumps({"request_id": str(uuid.uuid4()), **e.to_dict()}, ensure_ascii=False, indent=2), file=sys.stderr)
        return e.exit_code
    except RuntimeError as e:  # actionable config errors such as an unwritable cache directory
        print(f"Config error: {e}", file=sys.stderr)
        return 2
