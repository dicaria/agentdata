"""nsf — NSF Awards API (US NSF funding search; keyless).

No key needed (upstream states no keyless quota — self-imposed polite tier of 1 rps/burst 5).
Double response shell: the payload sits inside {"response": {"award": [...]}} (probed
2026-10-26); keyword full-text search × id award-number point lookup — upstream actually
combines them with AND (measured 0.2.9), the local XOR is a sugar-split wall;
rpp 1-200 (upstream API doc wall, row-count re-verified 2026-10-28);
upstream sends no total — a full page signals more via has_more (len(rows)==rpp).
"""
provider = {
    "id": "nsf",
    "baseUrl": "https://api.nsf.gov",
    "rate": {"rps": 1, "burst": 5},
    "ops": {
        "awards": {"path": "/services/v1/awards.json", "method": "GET", "idempotent": True},
    },
    "ttl": {"awards": 24 * 3600},
}


def _award_row(a):
    return {
        "id": a.get("id"), "title": a.get("title"), "agency": a.get("agency"),
        "date": a.get("date"), "start_date": a.get("startDate"), "exp_date": a.get("expDate"),
        "amount": a.get("amount"), "principal_investigator": a.get("pi"),
        "institution": a.get("institution"), "organization": a.get("organization"),
        "fund_program": a.get("fundProgramName"), "cfda": a.get("cfda"),
        "abstract_text": a.get("abstractText"), "award_notice_url": a.get("awardNoticeUrl"),
    }


def awards_raw(keyword=None, *, id=None, rpp=25, offset=0, cache=None, no_cache=False):
    """→ {total(=None, upstream sends no count), count, rows, has_more, params, _meta}; awards.json direct, verbatim name.
    keyword XOR id (**a local wall, not upstream** — measured 2026-10-28 upstream combines with
    AND: keyword=lithium&id=2624369→1 row, the intersection hit; sending both neither 400s nor
    first-wins; the local XOR is a deliberate split between the full-text and point-lookup
    channels); rpp 1-200 (upstream API doc; row-count re-verified 2026-10-28, rpp=200 truly
    sends 200 rows); offset ≥0; an empty keyword semantically means browse-the-corpus (legal
    upstream), no local wall here."""
    from ..transport import call_provider
    from ..errors import SdkError

    kw = str(keyword or "").strip() or None
    aid = str(id or "").strip() or None
    if kw and aid:
        raise SdkError("usage_error", provider="nsf",
                       detail="pass only one of keyword (full-text search) or id (award-number "
                              "point lookup) (local sugar-split wall — upstream actually combines "
                              "them with AND into the intersection, probed 2026-10-28)")
    if not kw and not aid:
        raise SdkError("usage_error", provider="nsf",
                       detail="nsf_awards requires at least one of keyword or id")
    size = int(rpp)
    if not 1 <= size <= 200:
        raise SdkError("usage_error", provider="nsf",
                       detail="rpp must be 1-200 (upstream API doc page-size cap)")
    off = int(offset)
    if off < 0:
        raise SdkError("usage_error", provider="nsf", detail="offset must be ≥0")
    params = {"rpp": size, "offset": off}
    if kw:
        params["keyword"] = kw
    else:
        params["id"] = aid
    r = call_provider(provider, "awards", params, cache=cache, no_cache=no_cache)
    rows = [_award_row(a) for a in ((r["data"] or {}).get("response") or {}).get("award") or []]
    return {"total": None, "count": len(rows), "rows": rows,
            "has_more": len(rows) == size, "params": params, "_meta": r}
