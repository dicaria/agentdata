"""vies — EU VIES provider (EU VAT number online validation; keyless).

GET /ms/{cc}/vat/{number} → {isValid, userError, name, address, requestDate, requestIdentifier,
vatNumber, originalVatNumber, viesApproximate{matchName, matchStreet…}}.
Three-way semantics: isValid=true → valid (name/address may be masked as '---' by a member state — DE does,
record null honestly); isValid=false + userError=INVALID → the legal answer "number invalid" (ok=True, not an
error); userError=anything else (MS_UNAVAILABLE/TIME_OUT/*MAX_CONCURRENT_REQ…) → upstream_unavailable (the
member-state system is offline/rate-limited).
Input accepts the whole VAT string ('DE811907980', first two chars = member-state code, Greece is EL not GR —
passed through as-is, not normalized).
TTL: 7 days (the validation verdict; requestIdentifier is the official audit-trace key).
"""
import re

from ..errors import SdkError

provider = {
    "id": "vies",
    "baseUrl": "https://ec.europa.eu/taxation_customs/vies/rest-api",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "check": {"path": "/ms/{cc}/vat/{number}", "ttl": 7 * 86400, "timeoutMs": 30000},
    },
    "ttl": {"check": 7 * 86400},
}

_VAT = re.compile(r"^([A-Z]{2})([A-Z0-9+*]{2,13})$")


def _soft(v):
    return None if v == "---" else v


def parse_vat(value):
    """'DE811907980' → ('DE','811907980'); no country prefix → usage_error (VIES routes by member state)."""
    s = re.sub(r"[\s.]", "", str(value or "")).upper()
    m = _VAT.match(s)
    if not m:
        raise SdkError("usage_error", provider="vies",
                       detail="VAT number must carry a member-state prefix (e.g. DE811907980 / EL040127129); add the country code to a bare number first")
    return m.group(1), m.group(2)


def check_vat(value, *, cache=None, no_cache=False):
    """→ {valid, user_error, vat_number, name, address, request_identifier, approximate, _meta}."""
    from ..transport import call_provider

    cc, number = parse_vat(value)
    r = call_provider(provider, "check", {"cc": cc, "number": number}, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    ue = d.get("userError")
    if ue and ue not in ("VALID", "INVALID"):
        raise SdkError("upstream_unavailable", provider="vies",
                       detail=f"VIES member-state system returned no verdict (userError={ue}) — retry later, not a validation failure")
    return {
        "valid": d.get("isValid") is True,
        "user_error": ue,
        "country_code": cc,
        "vat_number": f"{cc}{d.get('originalVatNumber') or d.get('vatNumber') or number}",  # display sense, prefix restored
        "name": _soft(d.get("name")),
        "address": _soft(d.get("address")),
        "request_date": d.get("requestDate"),
        "request_identifier": d.get("requestIdentifier"),   # official audit-trace key (for audit backtracking)
        "approximate": d.get("viesApproximate"),            # approximate match scores (corroborating evidence for member-state data confidence)
        "_meta": r,
    }
