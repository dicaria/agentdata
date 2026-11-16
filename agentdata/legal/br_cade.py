"""br_cade — CADE (Brazil's competition authority, conselho admin strSEI "pesquisa avançada"
proxy) case register — keyless form POST.

BR legal face (0.3.60; admitted from the research booklet br-cade-pesquisaavancada, re-probed
live 2026-11-13):

CONTRACT (one form POST per module):
  POST https://pesquisaavancada.cade.gov.br/sei/modulos/pesquisaavancada{module}/servicos.php
       ?servico=pesquisaSimples
  Content-Type: application/x-www-form-urlencoded, X-Requested-With: XMLHttpRequest,
  Referer: https://pesquisaavancada.cade.gov.br/consulta
  body: txtProtocoloPesquisa=&txtPesquisaLivre=&txtInteressado=<name>&txtDataDecisaoDe=
        &txtDataDecisaoAte=&hdnCaptcha=N&g-recaptcha-response=&avancado=[]&limit=limit 0,500
  answer: {error, message, result[], tamanho, datas, sql}
  Modules: apac (Ato de Concentração, 90 rows), tcc (Requerimento de TCC, 476),
           consulta (general consultation, 74) — the sizes measured live 2026-11-13.

LIVE LAWS (measured 2026-11-13 — the booklet did not carry the encoding law):
  - the upstream signals "no match" with error=true + the (base64) message "Sua pesquisa não
    encontrou nenhum protocolo correspondente!" and an empty `result` — that is an EMPTY ANSWER,
    not a failure ("PETROBRAS" → 0 rows; "JBS" → 2 rows; no filter → the whole 90-row module).
    Only an error=true answer that does NOT carry that message is a real failure.
  - EVERY scalar string in the answer is BASE64, and the decoded bytes are NOT uniform UTF-8:
    the upstream encodes some columns as UTF-8 ("Certidão" → C3 A2) and some as cp1252
    ("Finalístico" → single 0xED). Decoding with UTF-8 alone leaves the cp1252 columns
    mojibake; decoding with latin-1 alone mangles the UTF-8 ones. The decoder therefore tries
    UTF-8 strict first and falls back to cp1252, and only accepts a result whose characters are
    all printable — the tokens (link / linkProcessual, which are opaque encrypted blobs) are
    therefore left untouched.
  - the date fields (txtDataDecisaoDe / txtDataDecisaoAte) are DECORATIVE: the upstream echoes
    a fixed window (datas.decisao = 01/12/2014 → 01/01/2030) whatever is sent, so the face
    does not send them as filters and does not claim date filtering.
  - txtInteressado is the party filter and it works server-side ("JBS" → 2 rows); the answer
    carries the total in `tamanho` and the SQL echo in `sql` (the base64 SQL names the exact
    view/table behind the module).

Rows: {id_procedimento, protocolo_formatado, tipo_processo, decisao1, decisao2,
       documentos[{id_documento, protocolo_formatado, numero, nome_tipo, data_documento, link}],
       linkProcessual}.

Politeness: 0.2/2, concurrency 1, TTL 12h.
"""
import base64
import binascii
import re

from ..errors import SdkError

provider = {
    "id": "br_cade",
    "baseUrl": "https://pesquisaavancada.cade.gov.br",
    "rate": {"rps": 0.2, "burst": 2},
    "concurrency": 1,
    "ops": {
        "search": {"path": "/sei/modulos/pesquisaavancada{module}/servicos.php?servico=pesquisaSimples",
                   "method": "POST", "urlencoded": True, "idempotent": True, "timeout": 60.0},
    },
    "ttl": {"search": 12 * 3600},
}

MODULES = {
    "apac": "Ato de Concentração (merger control)",
    "tcc": "Requerimento de TCC (trade-practice clearance)",
    "consulta": "Consulta (general consultation surface)",
}

# the fields whose scalar values the upstream base64-encodes
_ENCODED = {"protocolo_formatado", "tipo_processo", "decisao1", "decisao2",
            "nome_tipo", "data_documento", "numero"}

_B64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
# the upstream signals "no match" with error=true + this message (base64-encoded) — an EMPTY
# answer, not a failure ("Sua pesquisa não encontrou nenhum protocolo correspondente!")
_EMPTY_RE = re.compile(r"n[aã]o encontrou nenhum protocolo|nenhum protocolo correspondente", re.I)


def _answer_message(doc):
    """The answer's message → text (the upstream base64-encodes it like every other scalar)."""
    m = doc.get("message")
    if not isinstance(m, str) or not m:
        return ""
    try:
        raw = base64.b64decode(m + "=" * (-len(m) % 4))
        s = raw.decode("utf-8", "replace")
        if s.strip():
            return s
    except (binascii.Error, ValueError):
        pass
    return m


def _decode_scalar(v):
    """One base64 scalar → text (UTF-8 strict first, cp1252 fallback, printable check)."""
    if not isinstance(v, str) or len(v) < 4 or not _B64.match(v):
        return v
    try:
        raw = base64.b64decode(v + "=" * (-len(v) % 4))
    except (binascii.Error, ValueError):
        return v
    if not raw:
        return v
    for enc in ("utf-8", "cp1252"):
        try:
            s = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if s and all(ch.isprintable() or ch in "\r\n\t" for ch in s):
            return s
    return v


def _decode_row(row):
    """One row → the decoded row (the opaque link tokens stay as they are)."""
    out = {}
    for k, v in (row or {}).items():
        if k in ("documentos", "linkProcessual", "link") or not isinstance(v, str):
            if k == "documentos" and isinstance(v, list):
                out[k] = [_decode_row(x) for x in v]
            else:
                out[k] = v
            continue
        out[k] = _decode_scalar(v) if k in _ENCODED else v
    return out


def parse_answer(doc):
    """The answer JSON → {total, rows[], datas, sql} (pure function — offline testable)."""
    if not isinstance(doc, dict):
        raise SdkError("upstream_unavailable", provider="br_cade",
                       detail="the CADE proxy answered an unexpected shape (not a JSON object)")
    rows = [_decode_row(r) for r in (doc.get("result") or [])]
    total = doc.get("tamanho")
    try:
        total = int(total)
    except (TypeError, ValueError):
        total = len(rows)
    return {
        "total": total,
        "rows": rows,
        "datas": doc.get("datas"),
        "sql": _decode_scalar(doc.get("sql")) if isinstance(doc.get("sql"), str) else doc.get("sql"),
        "message": doc.get("message"),
    }


def cases_raw(*, module="apac", name=None, protocol=None, limit=50, cache=None, no_cache=False):
    """→ {total, rows[], datas, sql, params, _meta}. name = the party filter
    (upstream field txtInteressado — server-side, "JBS" → 2 rows); protocol = the process
    protocol number (txtProtocoloPesquisa). The upstream's date fields are decorative and
    are therefore not sent."""
    from ..transport import call_provider

    m = str(module or "apac").strip().lower()
    if m not in MODULES:
        raise SdkError("usage_error", provider="br_cade",
                       detail=f"unknown module {module!r} — known modules: {sorted(MODULES)}")
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="br_cade", detail=f"limit must be an integer, got {limit!r}")
    if lim < 1:
        raise SdkError("usage_error", provider="br_cade", detail=f"limit must be >= 1, got {lim}")

    body = {
        "txtProtocoloPesquisa": str(protocol or ""),
        "txtPesquisaLivre": "",
        "txtInteressado": str(name or ""),
        "txtDataDecisaoDe": "",
        "txtDataDecisaoAte": "",
        "hdnCaptcha": "N",
        "g-recaptcha-response": "",
        "avancado": "[]",
        "limit": "limit 0,500",
    }
    r = call_provider(provider, "search", dict(body, module=m), cache=cache, no_cache=no_cache,
                      extra_headers={"Referer": "https://pesquisaavancada.cade.gov.br/consulta",
                                     "X-Requested-With": "XMLHttpRequest",
                                     "Accept-Language": "pt-BR,pt;q=0.9"})
    doc = r["data"] or {}
    if doc.get("error"):
        # error=true + "no matching protocol" is the upstream's EMPTY answer (a party with no
        # cases), not a failure — everything else under error=true is a real failure.
        msg = _answer_message(doc)
        if not ((not (doc.get("result") or [])) and _EMPTY_RE.search(msg)):
            raise SdkError("upstream_unavailable", provider="br_cade",
                           detail=f"the CADE proxy answered error=true: {msg!r}")
    parsed = parse_answer(doc)
    parsed["rows"] = parsed["rows"][:lim]
    parsed["params"] = {"module": m, "name": name, "protocol": protocol, "limit": lim}
    parsed["_meta"] = r
    return parsed
