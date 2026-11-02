"""rasff — EU RASFF Window food-safety alert search face provider
(webgate.ec.europa.eu/rasff-window/; keyless).

healthcare domain (0.3.19; admitted 2026-11-02, probed). Shapes verified by first-hand live probing
2026-11-02 (the probe corpus lives in tmp/probe-ca-eu-faces/):
GET /rasff-window/screen/search
  → the SPA shell — its GET mints the JSESSIONID session cookie (the two-step handshake).
POST /rasff-window/backend/public/notification/search/consolidated/en/
  → body {"parameters": {...}}; the response envelope is {notifications[], totalPages, totalElements}.
  **Pit nailed: the path must end with the language segment AND a trailing slash — dropping either
  one returns 404 (not an empty set).**
  **Pit nailed (Origin/Referer are mandatory): the POST carries Origin + Referer to the window
  screen plus the session cookie — the probe's requests without them do not return the search
  envelope.**
  Verified filter shapes (all three confirmed by the totalElements oracle, 2026-11-02):
    subject               → free text on the alert subject (aflatoxin → 2,919 hits)
    notificationReference → the reference number, exact (2026.9701 → 1 hit)
    ecValidDateFrom/To    → the window dates, format "dd-MM-yyyy 00:00:00" (01-09-2026 → 70 hits).
      The format is the upstream's own (the SPA's formatDate helper: en-GB dd/MM/yyyy → dd-MM-yyyy
      + " 00:00:00"); ISO input is rejected with 400.
    pageNumber (1-based) + itemsPerPage (the browser default 25).
  **Known limitation (documented, not guessed around): the enum-shaped filters — notifyingCountry /
  originCountry / productCategory / notificationClassification / riskDecision / notificationType /
  notificationStatus / notificationBasis / actionTaken / analyticalFinding — are NOT exposed here.
  Their parameter names come from the SPA's search component, but every object shape probed
  ({id,description} / {id} / plain string / full object) was rejected with the same generic
  [ERR-1003] body, so the shapes stay unproven and guessing them would burn requests for a silent
  near-miss. This face therefore ships the three proven filters + paging only.**
  Row shape: notif_id, ecValidationDate ("30-10-2026 18:59:15"), reference ("2026.9701"),
  notifyingCountry{organizationName, isoCode}, subject, productCategory{id,description},
  productType{id,description}, notificationClassification{id,description}, riskDecision{id,description},
  published (bool), originCountries[{organizationName, isoCode}].
  Corpus: 33,256 notifications across 11,086 pages (measured 2026-11-02).
TTL 24h (the window is refreshed on the EU's own cadence); polite rate 1 rps (the portal publishes
no quota for this backend — conservative).
"""
import re

from ..errors import SdkError

provider = {
    "id": "rasff",
    "baseUrl": "https://webgate.ec.europa.eu",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "screen": {"path": "/rasff-window/screen/search", "accept": "text"},  # the session bootstrap
        "search": {"path": "/rasff-window/backend/public/notification/search/consolidated/en/",
                   "method": "POST", "idempotent": True},  # params: parameters{...}
    },
    "ttl": {"search": 24 * 3600},
}

_SESSION_TTL = 15 * 60  # the JSESSIONID pairing is reused inside its session window

_ORIGIN = "https://webgate.ec.europa.eu"
_REFERER = "https://webgate.ec.europa.eu/rasff-window/screen/search"
_DATE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})(?:\s+00:00:00)?$")


def _fmt_date(v, field):
    """'01-09-2026' (or the full 'dd-MM-yyyy 00:00:00' form) → the upstream date string.

    The upstream format is fixed by the SPA's own formatDate helper (en-GB dd/MM/yyyy →
    'dd-MM-yyyy 00:00:00'); ISO input is rejected upstream with 400, so it is converted here
    rather than passed through."""
    s = str(v or "").strip()
    if not s:
        return None
    m = _DATE.match(s)
    if not m:
        raise SdkError("usage_error", provider="rasff",
                       detail=f"{field} must be dd-MM-yyyy (the upstream date format, e.g. 01-09-2026 — ISO input is rejected upstream with 400), got \"{v}\"")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)} 00:00:00"


def notifications_from_upstream(data):
    """Upstream envelope → notification rows (pure function, offline-testable)."""
    rows = []
    for n in ((data or {}).get("notifications") or []):
        rows.append({
            "notif_id": n.get("notifId"),
            "reference": n.get("reference"),
            "ec_validation_date": n.get("ecValidationDate"),
            "subject": n.get("subject"),
            "notifying_country": (n.get("notifyingCountry") or {}).get("organizationName"),
            "notifying_country_iso": (n.get("notifyingCountry") or {}).get("isoCode"),
            "origin_countries": [{"name": (c or {}).get("organizationName"), "iso": (c or {}).get("isoCode")}
                                 for c in (n.get("originCountries") or [])],
            "product_category": (n.get("productCategory") or {}).get("description"),
            "product_type": (n.get("productType") or {}).get("description"),
            "classification": (n.get("notificationClassification") or {}).get("description"),
            "risk_decision": (n.get("riskDecision") or {}).get("description"),
            "published": n.get("published"),
        })
    return {"rows": rows, "count": len(rows),
            "total_elements": (data or {}).get("totalElements"),
            "total_pages": (data or {}).get("totalPages")}


def _session(cache, no_cache=False):
    """-> the session cookie header (the JSESSIONID minted by the window shell GET); cached 15 minutes."""
    if not no_cache and cache is not None:
        hit = cache.get("rasff", "window_session", _SESSION_TTL)
        if hit:
            return hit["payload"]["cookie"]
    from ..transport import call_provider
    r = call_provider(provider, "screen", {}, cache=cache, no_cache=True)
    cookies = r.get("set_cookie") or []
    if not cookies:
        raise SdkError("upstream_unavailable", provider="rasff",
                       detail="the window shell did not mint a session cookie (the handshake shape may have changed)")
    cookie = "; ".join(c.split(";", 1)[0].strip() for c in cookies)
    if cache is not None:
        cache.set("rasff", "window_session", {"cookie": cookie}, _SESSION_TTL)
    return cookie


def search_raw(subject=None, *, notification_reference=None, ec_valid_date_from=None,
               ec_valid_date_to=None, page_number=1, items_per_page=25, cache=None, no_cache=False):
    """Flat-panel low-level face: the RASFF notification search (the consolidated English window).

    The three filters are the proven ones (subject / notificationReference / ecValidDateFrom-To);
    paging is pageNumber (1-based) + itemsPerPage (the browser default 25, politeness cap 200).
    → {rows[], count, total_elements, total_pages, params, _meta} — params = the upstream body
    actually sent (the "parameters" object), replayable."""
    from ..transport import call_provider

    idx = int(page_number) if page_number is not None else 1
    if idx < 1:
        raise SdkError("usage_error", provider="rasff", detail=f"page_number must be >=1 (1-based, as the SPA sends it), got \"{page_number}\"")
    size = int(items_per_page) if items_per_page is not None else 25
    if not 1 <= size <= 200:
        raise SdkError("usage_error", provider="rasff",
                       detail=f"items_per_page must be 1-200 (the browser default is 25; politeness cap — the portal publishes no quota), got \"{items_per_page}\"")
    params = {"pageNumber": idx, "itemsPerPage": size}
    subj = str(subject or "").strip()
    if subj:
        params["subject"] = subj
    ref = str(notification_reference or "").strip()
    if ref:
        params["notificationReference"] = ref
    dfrom = _fmt_date(ec_valid_date_from, "ec_valid_date_from")
    if dfrom:
        params["ecValidDateFrom"] = dfrom
    dto = _fmt_date(ec_valid_date_to, "ec_valid_date_to")
    if dto:
        params["ecValidDateTo"] = dto

    cookie = _session(cache, no_cache)
    hdrs = {"Origin": _ORIGIN, "Referer": _REFERER, "Cookie": cookie,
            "Accept": "application/json, text/plain, */*"}
    try:
        r = call_provider(provider, "search", {"parameters": params}, cache=cache, no_cache=no_cache,
                          extra_headers=hdrs)
    except SdkError as e:
        # a dead session cookie (the window re-mints it) → re-collect a FRESH pairing once and resend
        # (the re-collection is itself uncached, so it runs under no_cache too)
        if e.status not in (400, 403):
            raise
        cookie = _session(None)
        r = call_provider(provider, "search", {"parameters": params}, cache=cache, no_cache=no_cache,
                          extra_headers={"Origin": _ORIGIN, "Referer": _REFERER, "Cookie": cookie,
                                         "Accept": "application/json, text/plain, */*"})
    return {**notifications_from_upstream(r["data"]), "params": params, "_meta": r}
