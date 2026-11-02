"""co_secop — Colombia SECOP II electronic contract face provider (datos.gov.co Socrata dataset
jbjy-vk9h; keyless).

procurement domain (0.3.0 founding; admitted 2026-10-29, probed). Shape measured 2026-10-29:
GET /resource/jbjy-vk9h.json?$limit=2&$order=ultima_actualizacion DESC
  → [rows…88 columns…] (Socrata returns an array directly, no total echo — paging goes through
  $offset; the corpus-wide count is probed separately via $select=count)
  — the Colombian procurement corpus holds **5,665,176 electronic contracts** (count measured
  2026-10-29).
Row-level golden fields: nit_entidad (buyer NIT) × documento_proveedor+proveedor_adjudicado
(supplier NIT/CC) × the amount family valor_del_contrato/facturado/pagado/pendiente_de_pago
× departamento/ciudad/sector × id_contrato as the stable key × the date family
fecha_de_firma/inicio/fin × es_pyme — joins straight onto the RUES register by NIT.
PII red line (precedent: fda_crl): on rows whose tipodocproveedor is a personal-document type
(Cédula de Ciudadanía/Extranjería, Pasaporte, NUIP, Tarjeta de Identidad) the
documento_proveedor and the supplier's personal name are not returned — set to None +
proveedorMascarado:true stated explicitly; NIT (company tax id) rows are returned as-is.
Socrata $-parameter channel, verbatim names: $where raw SoQL (same shape as dgcomp's raw DSL
precedent — passed through, no local wall) / $limit/$offset/$order; the $order value domain is
column[ ASC|DESC] (measured 2026-10-29: the "… DESC NULL LAST" form 400s — SoQL does not
accept the NULLS syntax).
TTL: contract rows change slowly with ultima_actualizacion — 24h; polite tier 1 rps (anonymous
Socrata throttling, take the conservative value).
"""
from ..errors import SdkError

provider = {
    "id": "co_secop",
    "baseUrl": "https://datos.gov.co",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "contracts": {"path": "/resource/jbjy-vk9h.json"},  # Socrata $limit/$offset/$where/$order
    },
    "ttl": {"contracts": 24 * 3600},
}

# personal-document types (masked); NIT = company tax id, returned as-is
_PERSONAL_DOC = {"cédula de ciudadanía", "cédula de extranjería", "pasaporte",
                 "nuip", "tarjeta de identidad", "cedula de ciudadania", "cedula de extranjeria"}

# row narrowing (88 columns → bilateral + amount + status skeleton; upstream column names verbatim)
_FIELDS = ("nombre_entidad", "nit_entidad", "departamento", "ciudad", "orden", "sector", "rama",
           "proceso_de_compra", "id_contrato", "estado_contrato", "tipo_de_contrato",
           "modalidad_de_contratacion", "fecha_de_firma", "fecha_de_inicio_del_contrato",
           "fecha_de_fin_del_contrato", "tipodocproveedor", "documento_proveedor",
           "proveedor_adjudicado", "es_pyme", "valor_del_contrato", "valor_facturado",
           "valor_pagado", "valor_pendiente_de_pago")


def contracts_from_upstream(data):
    """Upstream SODA row array → contract rows (pure function, offline-testable; PII masking
    happens at this layer)."""
    rows = []
    for r in data or []:
        row = {k: r.get(k) for k in _FIELDS}
        masked = str(r.get("tipodocproveedor") or "").strip().lower() in _PERSONAL_DOC
        if masked:
            row["documento_proveedor"] = None
            row["proveedor_adjudicado"] = None
        row["proveedorMascarado"] = masked
        rows.append(row)
    return {"rows": rows, "count": len(rows)}


def contracts_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, params, _meta} (Socrata sends no total echo — paging
    goes through offset).

    where = $where raw SoQL (e.g. "upper(proveedor_adjudicado) like '%ECOPETROL%'"); limit/$limit
    politeness cap 1-500; offset/$offset ≥0; order/$order = column[ ASC|DESC]."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20  # explicit None check — an `or default` swallows 0, the same trap as 0.2.10
    if not 1 <= size <= 500:
        raise SdkError("usage_error", provider="co_secop",
                       detail=f"limit must be 1-500 (politeness cap), got '{limit}'")
    off = int(offset) if offset is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="co_secop", detail=f"offset must be ≥0, got '{offset}'")
    params = {"$limit": size, "$offset": off}
    w = str(where or "").strip() or None
    if w:
        params["$where"] = w
    o = str(order or "").strip() or None
    if o:
        params["$order"] = o
    r = call_provider(provider, "contracts", params, cache=cache, no_cache=no_cache)
    return {**contracts_from_upstream(r["data"]), "limit_applied": size, "params": params, "_meta": r}
