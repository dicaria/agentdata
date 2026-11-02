"""co_sic — Colombia SIC firm sanctions face provider (datos.gov.co Socrata dataset
73dx-n59j "Sanciones impuestas en firme por la SIC"; keyless).

legal domain (0.3.16; admitted 2026-10-30, probed). Shape measured 2026-10-30:
GET /resource/73dx-n59j.json?$limit=2&$order=fecha_emitida DESC
  → [rows…7 columns…] radicado (case number) / res_sancion (resolution number) /
    fecha_emitida / multado (the sanctioned party, company or individual name) /
    valor (fine amount, COP) / conducta (the violation) / sector — the register holds
    **3,938 firm sanctions 2013→** ($select=count measured 2026-10-30). Socrata sends
    the row array directly with no total echo — paging goes through $offset (same
    contract as co_secop_contracts on the same platform).
Row-level golden fields: multado × valor × conducta × sector = the company × fine ×
violation × industry quartet for negative-signal screening. No document-number column
exists in this register (name-only key) — sanctioned names are the SIC's own public
record and are returned as-is; a name-based join onto co_rues_companies / co_secop
NITs is the corpus line's job, not this face's.
Socrata $-parameter channel, verbatim names (same shape as co_secop): $where raw SoQL
(passed through, no local wall) / $limit/$offset / $order = column[ ASC|DESC]
(no NULLS syntax — SoQL 400s, measured on the sibling dataset).
TTL: sanctions in firme change slowly (append-mostly register) — 24h; polite tier
1 rps (anonymous Socrata throttling, same as the sibling co_secop face).
"""
from ..errors import SdkError

provider = {
    "id": "co_sic",
    "baseUrl": "https://datos.gov.co",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "sanctions": {"path": "/resource/73dx-n59j.json"},  # Socrata $limit/$offset/$where/$order
    },
    "ttl": {"sanctions": 24 * 3600},
}

# row narrowing: the register has exactly seven columns — all seven are golden, kept verbatim
_FIELDS = ("radicado", "res_sancion", "fecha_emitida", "multado", "valor", "conducta", "sector")


def sanctions_from_upstream(data):
    """Upstream SODA row array → sanction rows (pure function, offline-testable;
    column names verbatim, no transformation — the register is already narrow)."""
    rows = [{k: r.get(k) for k in _FIELDS} for r in data or []]
    return {"rows": rows, "count": len(rows)}


def sanctions_raw(where=None, *, limit=20, offset=0, order=None, cache=None, no_cache=False):
    """→ {rows[], count, limit_applied, params, _meta} (Socrata sends no total echo — paging
    goes through offset; the corpus-wide count 3,938 was measured at admission).

    where = $where raw SoQL (e.g. "upper(multado) like '%AVIANCA%'"); limit/$limit
    politeness cap 1-500; offset/$offset ≥0; order/$order = column[ ASC|DESC]
    (e.g. "fecha_emitida DESC")."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20  # explicit None check — an `or default` swallows 0, the same trap as 0.2.10
    if not 1 <= size <= 500:
        raise SdkError("usage_error", provider="co_sic",
                       detail=f"limit must be 1-500 (politeness cap), got '{limit}'")
    off = int(offset) if offset is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="co_sic", detail=f"offset must be ≥0, got '{offset}'")
    params = {"$limit": size, "$offset": off}
    w = str(where or "").strip() or None
    if w:
        params["$where"] = w
    o = str(order or "").strip() or None
    if o:
        params["$order"] = o
    r = call_provider(provider, "sanctions", params, cache=cache, no_cache=no_cache)
    return {**sanctions_from_upstream(r["data"]), "limit_applied": size, "params": params, "_meta": r}
