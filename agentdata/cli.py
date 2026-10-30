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
from .client import Client
from .company import cli as company_cli
from .esg import cli as esg_cli
from .healthcare import cli as healthcare_cli
from .legal import cli as legal_cli
from .procurement import cli as procurement_cli
from .research import cli as research_cli
from .security import cli as security_cli

# 0.2.6 per-domain split: the domain command registrars (register(v, g)) live in each domain's cli.py;
# the root keeps only the shared parts plus the search/read dispatch
# 0.3.10 domain order = lexicographic (DOMAIN_ORDER is the source of truth — the build_parser loop, per-domain face order, and site navigation all follow it; the sort key is the English identifier)
DOMAIN_ORDER = ("company", "esg", "healthcare", "legal", "procurement", "research", "security")
_CLI = {"company": company_cli, "esg": esg_cli, "healthcare": healthcare_cli,
        "legal": legal_cli, "procurement": procurement_cli,
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
    g.add_argument("--base-url", dest="sub_base_url", default=argparse.SUPPRESS, help="Hosted API base URL (env AGENTDATA_BASE_URL)")
    g.add_argument("--api-key", dest="sub_api_key", default=argparse.SUPPRESS, help="Bearer PAT (env AGENTDATA_API_KEY)")
    g.add_argument("--cache-dir", dest="sub_cache_dir", default=argparse.SUPPRESS, help="Cache directory (env AGENTDATA_CACHE_DIR)")
    g.add_argument("--no-cache", dest="sub_no_cache", action="store_true", default=argparse.SUPPRESS, help="Bypass the cache for this call")
    g.add_argument("--execution", dest="sub_execution", default=argparse.SUPPRESS, choices=["local", "hosted", "auto"], help="Execution location (default auto: realtime queries run locally)")
    return g


def build_parser():
    p = argparse.ArgumentParser(prog="agentdata", description="AgentData SDK CLI (corpus queries via the hosted API + realtime queries executed locally)")
    p.add_argument("--version", action="version", version=f"agentdata {__version__}")
    p.add_argument("--base-url", default=None, help="Hosted API base URL (env AGENTDATA_BASE_URL)")
    p.add_argument("--api-key", default=None, help="Bearer PAT (env AGENTDATA_API_KEY)")
    p.add_argument("--cache-dir", default=None, help="Cache directory (env AGENTDATA_CACHE_DIR)")
    p.add_argument("--no-cache", action="store_true", help="Bypass the cache for this call")
    p.add_argument("--execution", default="auto", choices=["local", "hosted", "auto"])
    sub = p.add_subparsers(dest="domain", required=True)
    for domain in DOMAIN_ORDER:
        d = sub.add_parser(domain, parents=[_leaf_globals()])
        v = d.add_subparsers(dest="verb", required=True)
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
    return p


# 0.2.6 per-domain split: the source of truth for the flat dispatch table is each domain's cli.FLAT,
# merged here (the search/read dispatch stays in this module's main)
_FLAT_DISPATCH = {}
for _m in _CLI.values():
    _FLAT_DISPATCH.update(_m.FLAT)
assert len(_FLAT_DISPATCH) == 83, f"flat dispatch {len(_FLAT_DISPATCH)} != 83 (83 faces; 0.3.2 esg +2 + 0.3.3 European registries +5 + 0.3.4 FR recherche +1 + 0.3.5 esg port-state +5 + 0.3.6 World Bank/NY +3 + 0.3.12 UNGM/NY OGS collection +2; the csl_screening alias was removed in 0.3.0)"
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




def main(argv=None) -> int:
    # Force UTF-8 for piped/redirected output: on Chinese Windows the pipe defaults to CP936 and agents
    # or redirected consumers would receive bad bytes; the interactive console is already UTF-8 under
    # PEP 528, so reconfigure is imperceptible there.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    a = _merge_globals(build_parser().parse_args(argv))
    try:
        c = Client(a.base_url, a.api_key, cache_dir=a.cache_dir, no_cache=a.no_cache,
                   execution=a.execution)
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
