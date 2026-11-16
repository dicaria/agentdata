"""mx_cnv — CNBV financial-sanctions register (apim-servicios.cnbv.gob.mx Azure APIM, keyless-by-
publication).

legal enforcement face (0.3.55; register 414, probed tmp/probe-audit + re-verified live
2026-11-12, tmp/probe-sdk-0355/). Shape measured 2026-11-12:
GET /sanciones/v1/api/sanctions answers a BARE JSON ROW LIST in the body — the pagination lives in
the response HEADERS (x-total-items / x-total-pages echo the filter set; 11,593 rows live
2026-11-12, drift from 11,597 measured 2026-11-10), which is why this op declares resp_headers
(extension 11). Request headers: Ocp-Apim-Subscription-Key = the key hardcoded in the public
React bundle (anonymous-by-publication — the AU ACMA family; NOT a credential, and the same bundle
also leaks an OpenAI key that is someone else's credential and is deliberately NOT carried here),
X-Page-Number (0-BASED) + X-Page-Size (10-1000; the bundle's own pageSizeOptions are
10/20/50/100/500/1000), and optional X-Order-Field + X-Order-Type (ASC|DESC; imposedOn verified
both ways — DESC head 2026-09-30, ASC head 2017-05-09). Row keys (11, verbatim): id /
obligatedSubject (the regulated-entity full name — the company join key) / sector / subSector /
type (sanction type) / amount (NUMERIC fine, MXN) / conduct (the violation text) / imposedOn +
publishedOn (YYYY-MM-DD, the two date axes) / pagado (paid flag) / officeNumber (the CNBV document
number). Coverage: everything since the 2014-01-10 Lineamientos — including the NON-regulated AML
faces (Centros Cambiarios / Transmisores de Dinero / SOFOMES E.N.R.), which is the face's
differentiator: the unregulated money-sector roster no other MX register carries.
Fallback host (bundle isUsingFallback): publicacion-sanciones-service.cnbv.gob.mx/api — not wired;
sectores enums at apim …/pes/v1 — not wired (no verified need). Detail /sanctions/{id}/detail
exists (casfimKey + personType Moral/Física + yearOfOccurrence) — future face.
No TTL (the op is uncached by design); polite tier 0.5 rps (APIM, no published quota).
"""
from ..errors import SdkError

provider = {
    "id": "mx_cnv",
    "baseUrl": "https://apim-servicios.cnbv.gob.mx",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "sanctions": {"path": "/sanciones/v1/api/sanctions", "timeoutMs": 30000,
                      "resp_headers": True},  # ext 11: totals ride the response headers
    },
    # no ttl: the sanctions op is never cached (header-only paging state cannot key a cache entry)
}

# Published in the sanctions.cnbv.gob.mx frontend bundle (main.70a7baf4.js env object) — a public
# APIM subscription key hardcoded in the anonymous SPA, the AU ACMA family of "keyless by
# publication". NOT a secret: rotating it breaks the CNBV's own website.
_PUBLIC_APIM_KEY = "1f7c355272df48c6ab638ce14fe8487a"

_ORDER_TYPES = ("ASC", "DESC")


def rows_from_upstream(data):
    """bare row list → sanction rows (pure function; the 11 upstream keys verbatim)."""
    return list(data or [])


def totals_from_headers(headers):
    """x-total-items/x-total-pages → ints (None when absent — a cache replay carries no headers)."""
    if not headers:
        return None, None
    h = {str(k).lower(): v for k, v in headers.items()}

    def _int(name):
        try:
            return int(h[name])
        except (KeyError, TypeError, ValueError):
            return None

    return _int("x-total-items"), _int("x-total-pages")


def sanctions_raw(*, page_number=0, page_size=1000, order_field=None, order_type=None,
                  cache=None, no_cache=False):
    """→ {rows, total_items, total_pages, page_number, page_size_applied, headers_sent, _meta}
    (header-paginated walk: page through 0..total_pages-1 at page_size 1000 = 12 calls for the
    whole register).

    page_number is 0-BASED (the upstream's own X-Page-Number semantics, kept verbatim); page_size
    1-1000 (the bundle's pageSizeOptions ceiling); order_field is passed through verbatim
    (imposedOn verified both directions; amount expected but not pinned); order_type ASC|DESC.
    Totals come from x-total-items/x-total-pages on every call (the op is never cached — the
    header-only paging state cannot key a cache entry, see the provider notes)."""
    # cache/no_cache accepted for signature symmetry; the op bypasses the cache by design.
    from ..transport import call_provider

    try:
        pn = int(page_number) if page_number is not None else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="mx_cnv",
                       detail=f"page_number must be an integer (0-BASED), got {page_number!r}")
    if pn < 0:
        raise SdkError("usage_error", provider="mx_cnv",
                       detail=f"page_number is 0-BASED and must be ≥0, got '{page_number}'")
    try:
        ps = int(page_size) if page_size is not None else 1000
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="mx_cnv",
                       detail=f"page_size must be an integer 1-1000, got {page_size!r}")
    if not 1 <= ps <= 1000:
        raise SdkError("usage_error", provider="mx_cnv",
                       detail=f"page_size must be 1-1000 (the upstream pageSizeOptions ceiling), got '{page_size}'")
    ot = str(order_type).upper() if order_type else None
    if ot is not None and ot not in _ORDER_TYPES:
        raise SdkError("usage_error", provider="mx_cnv",
                       detail=f"order_type must be ASC|DESC, got '{order_type}'")
    if ot and not order_field:
        raise SdkError("usage_error", provider="mx_cnv",
                       detail="order_type requires order_field (X-Order-Field rides the request too)")
    headers = {"Ocp-Apim-Subscription-Key": _PUBLIC_APIM_KEY,
               "X-Page-Number": str(pn), "X-Page-Size": str(ps)}
    if order_field:
        headers["X-Order-Field"] = str(order_field)
        if ot:
            headers["X-Order-Type"] = ot
    # The ENTIRE paging state rides headers — the URL is identical for every page, so a cache keyed
    # on (op, params) would hand page 5 page 0's body. The op is therefore NEVER cached (cache=None
    # through call_provider), which also keeps x-total-items/x-total-pages present on every call
    # (ext 11 surfaces response headers on the miss path only). The ungm precedent keys pages via
    # query params; this upstream offers no such surface, and inventing query echoes is unverified
    # wire noise. Rate tier 0.5 rps keeps the uncached walk polite.
    r = call_provider(provider, "sanctions", {}, cache=None, extra_headers=headers)
    rows = rows_from_upstream(r["data"])
    total_items, total_pages = totals_from_headers(r.get("resp_headers"))
    return {"rows": rows, "total_items": total_items, "total_pages": total_pages,
            "page_number": pn, "page_size_applied": ps,
            "headers_sent": {k: v for k, v in headers.items() if k != "Ocp-Apim-Subscription-Key"},
            "_meta": r}
