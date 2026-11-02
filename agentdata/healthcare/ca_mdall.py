"""ca_mdall — Health Canada Medical Devices Active Licence Listing (MDALL) face provider
(health-products.canada.ca; keyless — the same host as ca_dpd).

healthcare domain (0.3.19; admitted 2026-11-02, probed). Shapes verified by first-hand live probing
2026-11-02 (the probe corpus lives in tmp/probe-ca-eu-faces/):
GET /api/medical-devices/company/?lang=en&type=json
  → the MDALL company register in ONE shot (no pagination surface — 7,682 rows measured 2026-11-02;
    rows carry company_id (the MDALL join key) + company_name + company_status A/I + postal address
    + country_cd/region_cd — a rare two-country register: US manufacturers dominate the volume).
GET /mdall-limh/information?licenceId=111577&type=active&lang=eng
  → the single-licence dossier as a server-rendered HTML page (the LIMH = Licence Listing search
    application the site itself uses). **Pit nailed: the search POST (prepareSearch → option=4) is a
    PRG dance needing a CSRF pairing, but the information GET it redirects to works stateless and
    session-free — the point-lookup face skips the dance entirely.** A browser-looking referer/cookie
    is NOT required (a bare GET returns 200). The page shape:
    h2 Manufacturer → name span + em/span address lines + "Company ID:" span;
    "Licence No.:" h3 → licence span; Type / Device class / Device first issue date / Licence name
    label→span pairs; a "Device details" table whose td[headers*=idname] cells are the device
    identifiers (one row per identifier, grouped under th[namedev*] device names).
    A 200 page WITHOUT the "Licence No.:" block = no such licence at that type (active vs archived
    are separate indexes — an archived licence under type=active returns the empty page, not the record).
Param-minimalism pitfall (same host family as ca_dpd): unprobed params are silently ignored or dump
full registers — **the /api/medical-devices/device/ endpoint has NO working server-side filter (a
licence_no filter is ignored → the full 22.8MB device register), which is why the device face here
is the limh point lookup, not a device listing** — do not widen.
Local row slicing (limit/skip) is a post-slice over the single cached full shot.
TTL: companies 7 days (a slowly-changing register) / licence 7 days (issued licences change slowly);
polite rate 1 rps (the host publishes no quota; shared host with ca_dpd — the host bucket coordinates).
"""
import re

from ..errors import SdkError

provider = {
    "id": "ca_mdall",
    "baseUrl": "https://health-products.canada.ca",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "companies": {"path": "/api/medical-devices/company/"},  # params: lang/type fixed for this face
        "licence": {"path": "/mdall-limh/information", "accept": "text"},  # params: licenceId/type/lang (HTML dossier)
    },
    "ttl": {"companies": 7 * 86400, "licence": 7 * 86400},
}

# —— HTML dossier anchors (server-rendered WET page; regex parse — the same style as the ungm row family) ——
_TAGWS = re.compile(r"<[^>]+>|\s+")
_MFG = re.compile(r"<h2>Manufacturer</h2>\s*<span\s*>(.*?)</span>", re.S)
_EM_ADDR = re.compile(r"<em>\s*<span[^>]*>(.*?)</span>\s*</em>", re.S)
_COMPANY_ID = re.compile(r'Company ID:</span></strong>\s*<span\s*>(.*?)</span>', re.S)
_LABELLED = re.compile(r'<span\s*>(Licence No\.:|Type:|Device class:|Device first issue date:|Licence name:)</span>\s*(?:</strong>)?\s*<span\s*>(.*?)</span>', re.S)
# the Licence No. pair sits in its own h3 (no </strong> after it) — a second pattern for that shape:
_LICNO_H3 = re.compile(r'<h3><span\s*>Licence No\.:</span>\s*<span\s*>(.*?)</span>\s*</h3>', re.S)
_DEVICE_NAME = re.compile(r'<th id="namedev(\d+)"[^>]*>(.*?)</th>', re.S)
_DEVICE_ID = re.compile(r'<td headers="datedev(\d+) namedev\d+ idname">(.*?)</td>', re.S)
_NO_RESULT = re.compile(r'Licence No\.:')  # absence of this marker = the empty page


def _txt(x):
    from html import unescape
    return _TAGWS.sub(" ", unescape(x or "")).strip() or None


def licence_from_upstream(html, licence_id):
    """LIMH information page HTML → the licence dossier (pure function, offline-testable).

    The labelled pairs come in two shapes (Licence No. lives in an h3; the rest after a </strong>) —
    both shapes are collected; device identifiers are flattened with their group device name."""
    if not _NO_RESULT.search(html or ""):
        return None  # the 200 empty page = no such licence at this type
    fields = dict(_LABELLED.findall(html))
    lic = _LICNO_H3.search(html)
    if lic:
        fields["Licence No.:"] = lic.group(1)
    names = {int(i): _txt(x) for i, x in _DEVICE_NAME.findall(html)}
    # each identifier row names its device group via the headers attribute (datedevN namedevN idname) — the group index is the join
    identifiers = [{"device_name": names.get(int(g)), "device_identifier": _txt(x)}
                   for g, x in _DEVICE_ID.findall(html)]
    return {
        "licence_id": str(licence_id),
        "licence_no": _txt(fields.get("Licence No.:")),
        "licence_name": _txt(fields.get("Licence name:")),
        "licence_type": _txt(fields.get("Type:")),               # e.g. Device Family
        "device_class": _txt(fields.get("Device class:")),
        "first_issue_date": _txt(fields.get("Device first issue date:")),
        "manufacturer": None if not _MFG.search(html) else {
            "name": _txt(_MFG.search(html).group(1)),
            "address": [_txt(x) for x in _EM_ADDR.findall(html) if _txt(x)],
            "company_id": _txt(_COMPANY_ID.search(html).group(1)) if _COMPANY_ID.search(html) else None,
        },
        "device_identifiers": identifiers,
        "device_names": [n for n in names.values() if n],
    }


def companies_from_upstream(data):
    """Upstream company array → company rows (pure function, offline-testable)."""
    rows = [{
        "company_id": r.get("company_id"),              # the MDALL join key
        "company_name": r.get("company_name"),
        "company_status": r.get("company_status"),      # A = active / I = inactive
        "address": {k: r.get(k) for k in ("addr_line_1", "addr_line_2", "addr_line_3",
                                          "city", "region_cd", "postal_code", "country_cd")},
    } for r in (data or []) if isinstance(r, dict)]
    return {"rows": rows, "count": len(rows)}


def companies_raw(*, limit=200, skip=0, cache=None, no_cache=False):
    """Flat-panel low-level face: the MDALL company register, one full shot (7,682 rows measured
    2026-11-02) cached whole; limit/skip is a local post-slice.

    → {rows[], count, total, params, _meta} — total = the whole register size (not the page)."""
    from ..transport import call_provider

    off = int(skip) if skip is not None else 0
    if off < 0:
        raise SdkError("usage_error", provider="ca_mdall", detail=f"skip must be >=0, got \"{skip}\"")
    size = int(limit) if limit is not None else 200
    if size < 1:
        raise SdkError("usage_error", provider="ca_mdall", detail=f"limit must be >=1 (local post-slice, no upstream cap), got \"{limit}\"")
    params = {"lang": "en", "type": "json"}
    r = call_provider(provider, "companies", params, cache=cache, no_cache=no_cache)
    out = companies_from_upstream(r["data"])
    return {"rows": out["rows"][off:off + size], "count": min(size, max(0, out["count"] - off)),
            "total": out["count"], "params": params, "_meta": r}


def licence_raw(licence_id, *, licence_type="active", lang="eng", cache=None, no_cache=False):
    """Flat-panel low-level face: the MDALL single-licence dossier (LIMH information page, stateless GET).

    licence_id = the numeric MDALL licence number (e.g. 111577); licence_type = active|archived
    (separate upstream indexes — an archived licence must be asked for with type=archived);
    lang = eng|fra. A 200 page without the licence block = not_found (no such licence at that type).
    → {licence dossier…, params, _meta}."""
    from ..transport import call_provider

    v = str(licence_id or "").strip()
    if not v.isdigit():
        raise SdkError("usage_error", provider="ca_mdall",
                       detail=f"licence_id must be the numeric MDALL licence number (e.g. 111577, echoed from the LIMH listing), got \"{licence_id}\"")
    t = str(licence_type or "active").strip()
    if t not in ("active", "archived"):
        raise SdkError("usage_error", provider="ca_mdall",
                       detail=f"licence_type must be active|archived (two separate upstream indexes — an inactive licence lives under archived), got \"{licence_type}\"")
    lg = str(lang or "eng").strip()
    if lg not in ("eng", "fra"):
        raise SdkError("usage_error", provider="ca_mdall", detail=f"lang must be eng|fra, got \"{lang}\"")
    params = {"licenceId": v, "type": t, "lang": lg}
    r = call_provider(provider, "licence", params, cache=cache, no_cache=no_cache)
    dossier = licence_from_upstream(r["data"] or "", v)
    if dossier is None:
        raise SdkError("upstream_not_found", provider="ca_mdall",
                       detail=f"no MDALL licence {v} under type={t} (the page returns 200 empty — try licence_type=archived)")
    # the index param echoes under its upstream name "type"; the dossier's own licence_type is the
    # page's "Type:" field (Device Family …) — the two live side by side, no clobbering
    return {**dossier, "type": t, "params": params, "_meta": r}
