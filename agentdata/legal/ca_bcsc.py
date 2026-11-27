"""ca_bcsc — BC Securities Commission Disciplined Parties list (gateway.bcsc.bc.ca
Sitecore SearchTable, keyless).

CA legal face (0.3.58; admitted from research booklet ca-csa-disciplined booklet 136, probed live
2026-11-13, tmp/probe-sdk-0358/p3_bcsc.py — the working body replays the site's own
Disciplined List DataTable exactly). The BCSC keeps the sanctioned/disciplined roster of the
British Columbia Securities Commission — parties sanctioned under the Securities Act (BC);
1,834 rows live. The face searches the party name channel (title + item name + other names
upstream — the three SearchFields) with a party-type facet on the same dimension the site
facets on (computeddisciplinedpartytypefield_s; 'Company' → 532 rows measured).

CONTRACT (form-POST, urlencoded — a JSON body answers 500, form is the only channel):
POST /api/SearchTable with the browser's exact body — draw/start/length (Datatables paging),
order[0][column]=1&order[0][dir]=desc (date desc), search[value] (the term carrier; EMPTY
STRING = the full library — omitting the key entirely is silently answered with an EMPTY
page), IndexName=sitecore_pub_index_MainAlias, the FilterTags[]/TemplateIds[] GUID pair that
pins the Disciplined List template, SearchFields[] three times (computedsearchtitlefield_t /
computeditemnamefield_t / other_names_t — repeated keys, the transport urlencoded channel's
doseq shape), and the Facets[0][*] block (FieldName=computeddisciplinedpartytypefield_s,
SelectedValues empty = all party types). The response echoes only data/draw/recordsFiltered/
recordsTotal — NO facets block, so the party-type vocabulary is not enumerable from this
endpoint (the site's own facet values are the vocabulary; 'Company' and the individual forms
measured).

Row shape: title = the disciplined party's name, date 'Nov 2, 2026' (en-US) + dateLabel
'Order Date', itemType 'Disciplined Party', url = the detail-page path on www.bcsc.bc.ca,
directLinkUrl1-3 = PDF/document links (nullable), newsReleaseNumber, orderEffectiveDate,
reportingIssuer* trio. The module normalizes date→ISO (hand-rolled month map — strptime %b is
locale-sensitive) and absolutizes url/pdf links against www.bcsc.bc.ca. 0.25/2 polite, TTL 24h.
"""
from ..errors import SdkError

provider = {
    "id": "ca_bcsc",
    "baseUrl": "https://gateway.bcsc.bc.ca",
    "rate": {"rps": 0.25, "burst": 2},
    "concurrency": 1,
    "ops": {
        # form-urlencoded POST; the JSON/multipart channels answer 500 — urlencoded is measured
        "search": {"path": "/api/SearchTable", "method": "POST", "urlencoded": True,
                   "idempotent": True, "timeout": 30.0},
    },
    "ttl": {"search": 24 * 3600},
}

_SITE = "https://www.bcsc.bc.ca"
_MON = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _us_date_to_iso(v):
    """'Nov 2, 2026' → '2026-11-02' (hand-rolled month map — datetime.strptime %b is
    locale-sensitive and this face must not depend on the embedding process's locale)."""
    if not isinstance(v, str):
        return None
    parts = v.strip().split()
    if len(parts) == 3 and parts[0] in _MON:
        try:
            day, year = int(parts[1].rstrip(",")), int(parts[2])
            return f"{year:04d}-{_MON[parts[0]]:02d}-{day:02d}"
        except ValueError:
            return None
    return None


def row_from_upstream(d):
    """Disciplined-party card mapping (pure function — split out for offline testing)."""
    pdf_links = []
    for k in ("directLinkUrl1", "directLinkUrl2", "directLinkUrl3"):
        u = d.get(k)
        if u:
            pdf_links.append(u if u.startswith("http") else _SITE + u)
    url = d.get("url")
    return {
        "title": d.get("title"),                                  # the disciplined party's name
        "item_type": d.get("itemType"),                           # 'Disciplined Party'
        "document_type": d.get("documentType"),
        "date": _us_date_to_iso(d.get("date")),                   # Order Date, ISO
        "date_raw": d.get("date"),                                # 'Nov 2, 2026' verbatim
        "date_label": d.get("dateLabel"),
        "url": url if url and url.startswith("http") else (_SITE + url if url else None),
        "pdf_links": pdf_links,
        "news_release_number": d.get("newsReleaseNumber"),
        "order_effective_date": d.get("orderEffectiveDate") or None,
        "reporting_issuer_default_flag": d.get("reportingIssuerDefaultFlag"),
        "reporting_issuer_principal": d.get("reportingIssuerPrincipal"),
        "reporting_issuer_other_names": d.get("reportingIssuerOtherNames") or None,
        "abstract": d.get("abstract"),
    }


def search_raw(q=None, *, party_type=None, limit=20, offset=0, cache=None, no_cache=False):
    """→ {total, total_matched, rows[], params, _meta}. q = party-name term (substring over title
    + item name + other names; empty/None = the full library — 1,834 rows live). party_type = the
    facet value on computeddisciplinedpartytypefield_s ('Company' measured → 532; the vocabulary
    is the site's own facet, not enumerable from this endpoint). limit = Datatables length
    (local wall 1-100), offset = Datatables start (row-based)."""
    from ..transport import call_provider

    term = str(q or "").strip()
    party = str(party_type or "").strip()
    try:
        size = int(limit)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ca_bcsc", detail=f"limit must be an integer 1-100, got {limit!r}")
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="ca_bcsc", detail=f"limit must be 1-100 (Datatables length), got {limit!r}")
    try:
        off = int(offset) if offset else 0
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ca_bcsc", detail=f"offset must be an integer >=0, got {offset!r}")
    if off < 0:
        raise SdkError("usage_error", provider="ca_bcsc", detail=f"offset must be >=0, got {off}")
    # the browser's exact measured body (SearchFields[] ×3 = the doseq repeated-key shape)
    params = {
        "draw": 1, "start": off, "length": size,
        "order[0][column]": 1, "order[0][dir]": "desc",
        "search[value]": term,
        "IndexName": "sitecore_pub_index_MainAlias",
        "FilterTags[]": "{885DDE4B-F673-4492-A1E0-3AF27BBDCCC6}",
        "TemplateIds[]": "{7641EEC8-DF76-45F5-8AD8-ECDD807F4076}",
        "SearchFields[]": ["computedsearchtitlefield_t", "computeditemnamefield_t", "other_names_t"],
        "Facets[0][FieldName]": "computeddisciplinedpartytypefield_s",
        "Facets[0][SortOrder]": "desc",
        "Facets[0][DisplayCount]": 100,
        "Facets[0][SelectedValues]": party,
        "Facets[0][FieldType]": "String",
        "Facets[0][UsesAndOperator]": "false",
    }
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache,
                      extra_headers={"Origin": "https://www.bcsc.bc.ca",
                                     "Referer": "https://www.bcsc.bc.ca/enforcement/administrative-enforcement/"
                                                "administrative-sanctions/disciplined-list"})
    doc = r["data"] or {}
    if not isinstance(doc, dict) or "data" not in doc:
        raise SdkError("upstream_unavailable", provider="ca_bcsc",
                       detail="SearchTable answered an unexpected shape (no data key — a silently-empty "
                              "replay usually means the body contract drifted; a 500 means the form channel was bypassed)")
    return {"total": doc.get("recordsTotal"), "total_matched": doc.get("recordsFiltered"),
            "rows": [row_from_upstream(x) for x in doc.get("data") or []],
            "params": {"q": term or None, "party_type": party or None, "limit": size, "offset": off},
            "_meta": r}
