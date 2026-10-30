"""gudid — AccessGUDID v3 (device DI → master record; keyless; TTL 7 days).

Migrated v2→v3 (2026-10-22): v2 carries an upstream 2021-07 deprecation notice (claiming removal after 2022-12-31, never executed and still 200);
v3 has the same shape and was probed — a field-by-field diff on the same DI only adds keys (gmdnTerms.gmdn gains gmdnCode/implantable/gmdnCodeStatus),
the 404 shape is the same, the WAF behaviour is the same; v3 also accepts the udi=/record_key= params (recorded, unused).

Channel note: upstream has an AWS WAF human gate, and on 2026-10-16 it was measured to hold **by client stack and by egress IP** — the local Node undici
always got 202 with an empty HTML body (the system curl always passed locally); after switching the egress proxy, curl/urllib also all got 202 + the x-amzn-waf-action challenge page.
The Python default is transport='urllib'; whether it is blocked must be verified on a real machine (live-transport verification, off by default); if blocked, check the egress IP / change network first
(the transport already raises an actionable error for a 2xx non-JSON response), and only pin 'curl' once the local egress confirms urllib is blocked. Data fallback: openFDA UDI, the same origin.
Note: the v1 endpoint is deprecated and 404s — do not step on it.
"""

provider = {
    "id": "gudid",
    "baseUrl": "https://accessgudid.nlm.nih.gov",
    "rate": {"rps": 2, "burst": 4},
    "ops": {
        "lookup": {"path": "/api/v3/devices/lookup.json", "notFound": [404], "ttl": 7 * 86400,
                   "transport": "urllib"},
    },
}


def _pick(o, *keys):
    for k in keys:
        if o and o.get(k) is not None:
            return o[k]
    return None


def card_from_upstream(data):
    """Pure mapper (testable offline) — v2/v3 have the same shape; only the top-level productCodes bare array is the strong shape (five fields),
    gudid.device.productCodes.fdaProductCode is the weak shape (code+name only) — do not read them mixed.
    The v2 response was verified field by field against a real 200 response for the DI
    10198459305313 (2026-10-20), and v3 was verified on 2026-10-22 to use the same names; the old names are kept as a fallback."""
    dev = ((data or {}).get("gudid") or {}).get("device") or {}
    pcs = (data or {}).get("productCodes") or []
    return {
        "brand_name": _pick(dev, "brandName", "brand_name"),
        "company_name": _pick(dev, "companyName", "company_name"),
        "device_description": _pick(dev, "deviceDescription", "device_description"),
        "model": _pick(dev, "versionModelNumber", "version_or_model_number"),
        "mr_safety": _pick(dev, "MRISafetyStatus", "mriSafetyInformation", "mri_safety"),
        "record_status": _pick(dev, "deviceRecordStatus", "recordStatus", "record_status"),
        "public_version": _pick(dev, "publicVersionNumber", "public_version_number"),
        "product_codes": [
            {
                "code": c.get("productCode"),
                "name": c.get("deviceName"),
                "device_class": c.get("deviceClass"),
                "regulation_number": c.get("regulationNumber"),
                "medical_specialty": c.get("medicalSpecialty"),
            }
            for c in pcs
        ],
    }


def lookup_di(di: str, cache=None, no_cache: bool = False) -> dict:
    from ..transport import call_provider

    r = call_provider(provider, "lookup", {"di": str(di).strip()}, cache=cache, no_cache=no_cache)
    return {"di": str(di).strip(), **card_from_upstream(r["data"]), "_meta": r}


def lookup_device(di=None, udi=None, record_key=None, *, cache=None, no_cache: bool = False) -> dict:
    """0.2.0 mirror face: one v3 endpoint with three input params (di/udi/record_key — exactly one of the three required) — the udi=/record_key=
    two-param shapes recorded by the audit are unlocked this way (on 2026-10-23 the missing-param 400 was judged by probing: this is the only positive v3 endpoint)."""
    from ..errors import SdkError
    from ..transport import call_provider

    given = {k: str(v).strip() for k, v in (("di", di), ("udi", udi), ("record_key", record_key)) if v}
    if len(given) != 1:
        raise SdkError("usage_error", provider="gudid",
                       detail=f"exactly one of di/udi/record_key is required (the single-record lookup endpoint; got {sorted(given) or 'none'})")
    k, v = next(iter(given.items()))
    try:
        r = call_provider(provider, "lookup", {k: v}, cache=cache, no_cache=no_cache)
    except SdkError as e:
        if e.code == "upstream_unavailable":  # WAF/TLS fingerprint gate or gateway timeout — add the same-origin fallback pointer into the envelope (0.2.8)
            e.detail = (f"{e.detail}; same-origin fallback: openFDA /device/udi.json (another public face of the DI master record, not covered by this SDK, callable directly)")
        raise
    return {"by": k, k: v, **card_from_upstream(r["data"]), "_meta": r}
