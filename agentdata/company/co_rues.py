"""co_rues — Colombia RUES commercial-registry master provider (datos.gov.co Socrata; keyless).

company roster (admitted in 0.3.11, probe tmp/probe-co-kr/; harvest-side recipe in the co-rues-socrata volume).
Shape verified 2026-10-30: GET /resource/c82u-588k.json?$limit= → array straight out (9,436,330-row corpus,
36 columns — Socrata omits null fields per row: natural-person rows carry no NIT/RL columns, legal-entity
rows surface the three-column RL family).
Company-row key and profile: matricula (camara x matricula registry key) + numero_identificacion
(rows with clase_identificacion='NIT' = corporate tax id NIT) + digito_verificacion check digit +
razon_social + CIIU primary/secondary industries (cod_ciiu_act_econ_pri/sec) + tipo_sociedad/
organizacion_juridica two-level legal form + estado_matricula/fecha_cancelacion status family +
representante_legal (officer-name edge — names in a public registry are collectable, no_brreg roller precedent).

**PII double gate (red line, pinned by the 2026-10-30 probe)**: (1) default base filter
clase_identificacion='NIT' — on persona natural rows numero_identificacion equals the nit column
= cedula personal id (observed 7174354); the company-domain face admits tax-entity rows only
(the user where is AND-merged with the base filter, parentheses preserve the user expression);
(2) row shaping strips num_identificacion_representante_legal (the RL's cedula number) —
the name is kept, the number is not collected. Sole-proprietor bulk needs go through the harvest
bulk line (api/views rows.csv has no Range), not this face.
Licence CC-BY-SA (contagious — site redistribution on its own rail; the SDK query face is not restricted).

Socrata $-param verbatim channel (same contract as ny_open_data/secop): $where raw SoQL passthrough /
$limit 1-500 / $offset>=0 / $order rejects NULLS; no total echo, none faked (corpus count probed
separately via $select=count).
TTL: registry master changes slowly — 7 days; politeness 1 rps (conservative tier for anonymous Socrata).
"""
from ..errors import SdkError

provider = {
    "id": "co_rues",
    "baseUrl": "https://www.datos.gov.co",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "companies": {"path": "/resource/c82u-588k.json"},  # Socrata $limit/$offset/$where/$order
    },
    "ttl": {"companies": 7 * 86400},
}

# PII red-line columns: RL (legal representative) cedula number — name columns kept, number columns always stripped
_RL_ID_COLUMNS = ("num_identificacion_representante_legal",)

# Default base filter: tax-entity rows only (clase_identificacion='NIT') — on persona natural rows
# numero_identificacion/nit = cedula personal id; the company-domain face does not admit them (PII gate one of two)
_BASE_FILTER = "clase_identificacion='NIT'"


def _strip_pii(row):
    for col in _RL_ID_COLUMNS:
        row.pop(col, None)
    return row


def companies_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, params, _meta} (Socrata echoes no total; RL number column stripped from rows)."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20  # explicit None check — 0 swallowed by or is the 0.2.10-style pit
    if not 1 <= size <= 500:
        raise SdkError("usage_error", provider="co_rues",
                       detail=f"limit must be 1-500 (politeness cap), got {limit!r}")
    off = int(offset) if offset is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="co_rues", detail=f"offset must be >=0, got {offset!r}")
    w = str(where or "").strip() or None
    merged = f"({w}) and {_BASE_FILTER}" if w else _BASE_FILTER  # base filter AND-merged (parentheses preserve the user expression)
    params = {"$limit": size, "$offset": off, "$where": merged}
    o = str(order or "").strip() or None
    if o:
        params["$order"] = o
    r = call_provider(provider, "companies", params, cache=cache, no_cache=no_cache)
    data = [_strip_pii(x) for x in (r["data"] or [])]
    return {"rows": data, "count": len(data), "limit_applied": size, "params": params, "_meta": r}
