"""agentdata.capabilities — the reflection-based discovery surface.

Every face parser in the argparse tree already carries the two things a caller needs in order to
use it without reading the manual: a one-line summary (`help=`) and a long form (`description=`
— upstream endpoint, the traps that face carries, the walls), plus, per parameter, the help text,
the closed set where one exists, whether it is required and its type.

So the face table is RENDERED from that tree instead of being maintained as a second hand-written
list. A hand-written list would have to be re-typed for every new face and would drift from the
command surface the first time it was not — the same failure the 172-face assertion in cli.py
exists to catch. Here nothing is authored per face: `agentdata capabilities` therefore ships with
every release without asking for a release of its own.

The surface is local-only by construction: it describes what THIS INSTALLED PACKAGE can run. The
hosted service keeps its own, server-rendered list (a deployment-bound surface that also carries
the per-face minimum client version — the two are reconciled by that field, never by hand).
"""
from __future__ import annotations

import argparse
import json

from . import __version__

# The global flags ride on every leaf parser through the parents=[_leaf_globals()] mechanism; they
# are not face parameters and must not show up in the capability view.
_GLOBAL_OPTION_STRINGS = {"--base-url", "--api-key", "--cache-dir", "--no-cache", "--execution"}
_GLOBAL_DESTS = {"sub_base_url", "sub_api_key", "sub_cache_dir", "sub_no_cache", "sub_execution"}

# The two corpus verbs are registered on every domain parser by the root CLI. They belong to the
# hosted corpus family (a PAT is required), not to the realtime face family.
_CORPUS_VERBS = ("search", "read")


def _subparsers_action(parser):
    """The _SubParsersAction of a parser (argparse keeps it in a private slot)."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _choice_help(action):
    """{name: help text} for the subcommands that were registered WITH a help= line.

    argparse only lists a subcommand individually when it was given a help= string; a face
    registered with description= alone stays invisible in the parent's help listing (that is why
    the economy domain used to have no catalog at all)."""
    out = {}
    for pseudo in getattr(action, "_choices_actions", []):
        out[pseudo.dest] = pseudo.help
    return out


def _is_global(action):
    return bool(set(action.option_strings) & _GLOBAL_OPTION_STRINGS) or action.dest in _GLOBAL_DESTS


def _param(action):
    default = action.default
    if default is argparse.SUPPRESS:
        default = None
    elif isinstance(default, tuple):
        default = list(default)
    # argparse carries the action kind in the class name (_AppendAction, _StoreTrueAction, …);
    # there is no `.action` attribute on the instance.
    kind = type(action).__name__
    return {
        "flag": action.option_strings[0] if action.option_strings else None,
        "dest": action.dest,
        "required": bool(action.required),
        "type": getattr(action.type, "__name__", None) or "str",
        "choices": list(action.choices) if action.choices else None,
        "default": default,
        "repeatable": kind in ("_AppendAction", "_AppendConstAction", "_ExtendAction"),
        "boolean": action.nargs == 0,
        "help": action.help,
    }


def _params(parser):
    """The face's own parameters (the inherited globals and the help action are not parameters)."""
    out = []
    for action in parser._actions:
        if not action.option_strings:
            continue
        if action.dest == "help" or _is_global(action):
            continue
        out.append(_param(action))
    return out


def _summary(help_text, description):
    """The one-line summary and where it came from.

    `help=` is the authored one-liner; when a face was registered without one the long
    description is the only text there is, and the source is recorded so a reader knows the
    summary is a prefix of the detail rather than a separate claim."""
    if help_text:
        return help_text, "help"
    if description:
        return description, "description"
    return "", "none"


def _face(domain, name, parser, help_text, jurisdiction):
    summary, source = _summary(help_text, parser.description)
    return {
        "face": name,
        "command": f"agentdata {domain} {name}",
        "jurisdiction": jurisdiction,
        "execution": "local",
        "key_required": False,
        "summary": summary,
        "summary_source": source,
        "description": parser.description or "",
        "params": _params(parser),
    }


def collect(parser, flat_faces, jurisdiction=None):
    """Render the capability surface.

    flat_faces: the set of realtime face names (the flat dispatch table is the source of truth for
    "is a realtime face"); jurisdiction: {face: country code} (optional, per face)."""
    jurisdiction = jurisdiction or {}
    root_action = _subparsers_action(parser)
    domains = []
    corpus = []
    for domain, domain_parser in sorted((root_action.choices if root_action else {}).items()):
        verb_action = _subparsers_action(domain_parser)
        if verb_action is None:
            continue
        helps = _choice_help(verb_action)
        faces = []
        corpus_verbs = {}
        for name, face_parser in sorted(verb_action.choices.items()):
            if name in _CORPUS_VERBS:
                corpus_verbs[name] = (face_parser, helps.get(name))
                continue
            if name not in flat_faces:
                continue
            faces.append(_face(domain, name, face_parser, helps.get(name), jurisdiction.get(name)))
        if faces:
            domains.append({"domain": domain, "faces": faces})
        if corpus_verbs:
            corpus.append(_corpus_face(domain, corpus_verbs))
    return {
        "sdk_version": __version__,
        "generated_by": "agentdata capabilities (reflection over the argparse tree)",
        "counts": {
            "realtime_faces": sum(len(d["faces"]) for d in domains),
            "domains": len(domains),
            "corpus_domains": len(corpus),
        },
        "realtime": domains,
        "corpus": corpus,
    }


def filter_caps(caps, domain=None, face=None):
    """Narrow the listing. The counts are recomputed — a filtered view that kept the global
    counts would be a small lie."""
    realtime, corpus = caps["realtime"], caps["corpus"]
    if domain:
        realtime = [d for d in realtime if d["domain"] == domain]
        corpus = [c for c in corpus if c["domain"] == domain]
    if face:
        realtime = [{"domain": d["domain"], "faces": [f for f in d["faces"] if f["face"] == face]}
                    for d in realtime]
        realtime = [d for d in realtime if d["faces"]]
    out = dict(caps)
    out["realtime"] = realtime
    out["corpus"] = corpus
    out["counts"] = {
        "realtime_faces": sum(len(d["faces"]) for d in realtime),
        "domains": len(realtime),
        "corpus_domains": len(corpus),
    }
    return out


def _corpus_face(domain, corpus_verbs):
    """The hosted corpus family of one domain (search + read) as a single entry.

    The corpus lives on the server, so this entry is the one place where the local surface
    describes something this package does NOT execute: it is a hosted service and needs a PAT."""
    verbs = {}
    for verb, (parser, help_text) in corpus_verbs.items():
        summary, _ = _summary(help_text, parser.description)
        verbs[verb] = {"summary": summary, "description": parser.description or "", "params": _params(parser)}
    union = []
    seen = set()
    for verb in sorted(verbs):
        for p in verbs[verb]["params"]:
            if p["flag"] not in seen:
                seen.add(p["flag"])
                union.append(p)
    return {
        "domain": domain,
        "commands": [f"agentdata {domain} {v}" for v in sorted(verbs)],
        "execution": "hosted",
        "key_required": True,
        "summary": " + ".join(f"{v}: {verbs[v]['summary']}" for v in sorted(verbs)),
        "verbs": verbs,
        "params": union,
    }


def _md_param_rows(params):
    rows = ["| flag | req | type | default | closed set | meaning |",
            "|---|---|---|---|---|---|"]
    for p in params:
        default = "–" if p["default"] in (None, [], "") else str(p["default"])
        choices = "–" if not p["choices"] else ", ".join(str(c) for c in p["choices"])
        flag = p["flag"] or p["dest"]
        if p["repeatable"]:
            flag += " (repeatable)"
        meaning = (p["help"] or "").replace("|", "\\|").replace("\n", " ")
        rows.append(f"| `{flag}` | {'yes' if p['required'] else 'no'} | {p['type']} | {default} | {choices} | {meaning} |")
    return rows


def _md(caps):
    out = []
    out.append(f"# AgentData SDK capabilities (v{caps['sdk_version']})")
    out.append("")
    out.append(f"{caps['counts']['realtime_faces']} realtime faces across {caps['counts']['domains']} "
               f"domains — local execution, keyless — plus {caps['counts']['corpus_domains']} hosted "
               f"corpus domains (a PAT is required).")
    out.append("")
    out.append("Generated from the command tree: nothing on this page is maintained by hand, so it "
               "cannot drift from the commands it describes.")
    out.append("")
    for domain in caps["realtime"]:
        out.append(f"## {domain['domain']}")
        out.append("")
        for face in domain["faces"]:
            out.append(f"### `{face['command']}`")
            meta = [face["jurisdiction"] or "–", face["execution"]]
            out.append("· " + " · ".join(meta))
            out.append("")
            out.append(face["summary"])
            if face["summary_source"] == "description" and face["description"] != face["summary"]:
                detail = face["description"]
                out.append("")
                out.append(detail[:220] + ("…" if len(detail) > 220 else ""))
            if face["params"]:
                out.append("")
                out.extend(_md_param_rows(face["params"]))
            out.append("")
    if caps["corpus"]:
        out.append("## corpus (hosted)")
        out.append("")
        first = caps["corpus"][0]
        out.append(f"`agentdata <domain> search` / `agentdata <domain> read` — hosted, PAT required. "
                   f"{len(caps['corpus'])} domains: "
                   + ", ".join(c["domain"] for c in caps["corpus"]) + ".")
        out.append("")
        out.extend(_md_param_rows(first["params"]))
        out.append("")
    return "\n".join(out)


def render(caps, fmt="json"):
    """The capability surface as text. `json` is the machine contract; `md` is the human page."""
    if fmt == "md":
        return _md(caps)
    return json.dumps(caps, ensure_ascii=False, indent=2)
