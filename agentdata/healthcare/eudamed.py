"""eudamed — EUDAMED public device catalogue (EU UDI-DI → master record; keyless).

Endpoint = the SPA's same-origin REST (the api:{…} map is plaintext in the main bundle, not an officially documented face): GET /api/devices/udiDiData.
Rows carry manufacturerSrn (XX-MF-…) + authorisedRepresentativeSrn (XX-AR-…) — the EU counterpart of GUDID;
the AccessGUDID egress is intermittently gated by a TLS fingerprint gate (2026-10-16 case), so the EU face became its own edge.
Acceptance gate observations: probed 2026-10-17 and re-checked 2026-10-20 — the endpoint / param semantics / row shape are stable.
Channel note (measured 2026-10-20): the upstream exact DI query (primaryDi=) is unindexed — cold 50.8s / warm 11.2s,
so the op gets a 90s timeout and 0 retries (the slow path must not burn retries); tradeName= is the fast face but it is a search, not a normalization, so it does not enter this kind.
Pagination (all three params are sent together): page&pageSize&size + iso2Code=en; totalElements===0 = a structured not_found —
but an empty set is never authoritative for the cache: the unindexed face occasionally returns a wholly empty page (hit here on 2026-10-20: a 0-hit page poisoned the 7-day TTL), so an empty verdict discards the cached entry and refetches once.
"""


def _tail(code):
    """refdata.risk-class.class-iia → class-iia (non-string → None).

    P1-2 (folded in 2026-10-22): the same batch of upstream fields comes in two shapes — riskClass/deviceStatusType/manufacturerStatus
    are {code} objects (the real-machine shape), while issuingAgency on list pages can be an object or a bare string. Both shapes are collected here,
    so call sites can pass the value straight through; the old implementation only accepted strings, so manufacturerStatus was always None.
    """
    if isinstance(code, dict):
        code = code.get("code")
    return code.split(".").pop() if isinstance(code, str) else None


def _params(v):
    return {"primaryDi": v, "page": 0, "pageSize": 5, "size": 5, "iso2Code": "en"}


def _empty(d):
    return not (d or {}).get("totalElements") or not (d or {}).get("content")


provider = {
    "id": "eudamed",
    "baseUrl": "https://ec.europa.eu/tools/eudamed",
    "rate": {"rps": 1, "burst": 2},
    "concurrency": 1,  # ⑤ host concurrency pinned to 1: primaryDi is unindexed and cold ~50s, so more concurrency would only drag down the EU face
    "ops": {
        "lookup": {"path": "/api/devices/udiDiData", "timeout": 90.0, "retries": 0},
    },
    "ttl": {"lookup": 7 * 86400},
}


def _query(params, cache, no_cache):
    """A single udiDiData query + the empty-page poison guard (an empty verdict discards the cached entry and refetches once; only a still-empty result counts as not_found)."""
    from ..errors import SdkError
    from ..transport import call_provider, cache_key_for

    r = call_provider(provider, "lookup", params, cache=cache, no_cache=no_cache)
    if _empty(r["data"]):
        # An empty set is untrustworthy: discard the cached entry (including a stale empty one) and refetch once; only a still-empty result counts as not_found. The refetch goes through the normal read path
        # (the entry was deleted, so it must miss) and a good result is written back — the same effect as "noCache only skips reads, not writes" on the Node side (both stacks align).
        key = cache_key_for("lookup", params)
        if cache is not None:
            cache.delete("eudamed", key)
        fresh = call_provider(provider, "lookup", params, cache=cache, no_cache=False)
        if _empty(fresh["data"]):
            if cache is not None:
                cache.delete("eudamed", key)
            raise SdkError("upstream_not_found", provider="eudamed",
                           detail=f"no such EUDAMED record (0 hits is a structured empty set): {params.get('primaryDi') or params}")
        r = fresh
    return r


def _card_from_row(row):
    ia = row.get("issuingAgency")  # on list pages it can be an object or a string (the detail face is richer) — both shapes are accepted
    ia_code = ia.get("code") if isinstance(ia, dict) else ia
    return {
        "primary_di": row.get("primaryDi"),
        "basic_udi": row.get("basicUdi"),
        "trade_name": row.get("tradeName"),
        "device_name": row.get("deviceName"),
        "device_model": row.get("deviceModel"),
        "risk_class": _tail((row.get("riskClass") or {}).get("code")),
        "device_status": _tail((row.get("deviceStatusType") or {}).get("code")),
        "version_number": row.get("versionNumber"),
        "issuing_agency": _tail(ia_code),
        "sterile": row.get("sterile"),
        # manufacturerStatus is a {code} object (same shape as riskClass) — _tail accepts both shapes, so passing it straight yields active (P1-2)
        "manufacturer": {"name": row.get("manufacturerName"), "srn": row.get("manufacturerSrn"),
                         "status": _tail(row.get("manufacturerStatus"))},
        "authorised_representative": (
            {"name": row.get("authorisedRepresentativeName"), "srn": row.get("authorisedRepresentativeSrn")}
            if (row.get("authorisedRepresentativeSrn") or row.get("authorisedRepresentativeName")) else None),
        "last_update_date": row.get("lastUpdateDate"),
        "uuid": row.get("uuid"),
    }


def lookup_di_eu(di, *, cache=None, no_cache=False):
    """→ EU device identity card (manufacturer SRN + authorised-rep SRN edge + risk class/status/version) — the old verb face (resolve kind=device_eu)."""
    from ..errors import SdkError

    v = str(di or "").strip()
    if not v:
        raise SdkError("usage_error", provider="eudamed", detail="resolve kind=device_eu needs a DI code")
    r = _query(_params(v), cache, no_cache)
    row = (r["data"].get("content") or [None])[0]
    return {**_card_from_row(row), "_meta": r}


def query_udi_di(primary_di=None, *, page=0, page_size=5, iso2_code="en", cache=None, no_cache=False):
    """0.2.0 mirror face: the primaryDi exact lookup + the upstream param names page/pageSize/iso2Code (paging is unlocked this way).

    size is sent together with pageSize (all three params go out together); a larger pageSize widens the rows (the unindexed face is cold ~50s, so widen with care).
    → identity card (the first-page row) + pagination echo total_elements/page/page_size; paging past the end = an empty page → not_found (the single-record face is the detail lookup).
    """
    from ..errors import SdkError

    v = str(primary_di or "").strip()
    if not v:
        raise SdkError("usage_error", provider="eudamed", detail="eudamed_device needs primary_di (the EU UDI-DI)")
    if int(page_size) < 1:
        raise SdkError("usage_error", provider="eudamed", detail="page_size must be >= 1")
    params = {"primaryDi": v, "page": int(page), "pageSize": int(page_size),
              "size": int(page_size), "iso2Code": str(iso2_code or "en")}
    r = _query(params, cache, no_cache)
    row = (r["data"].get("content") or [None])[0]
    return {**_card_from_row(row),
            "total_elements": (r["data"] or {}).get("totalElements"),
            "page": int(page), "page_size": int(page_size), "_meta": r}
