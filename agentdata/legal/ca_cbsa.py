"""ca_cbsa — CBSA national rulings (Canada Border Services Agency, the tariff classification
advance rulings, ccp-pcc.cbsa-asfc.cloud-nuage.canada.ca, keyless).

CA legal face (0.3.60; admitted from the research booklet customs-rulings, re-probed live
2026-11-13):

CONTRACT (two keyless REST calls):
  1. list — GET /carmwebservices/v2/carm/publicrulings/list?lang=en
     → {type: "publicRulingsListWsDTO", rulings: [{classificationNumber, date, product,
       rulingsId, type}, …]} — 1,234 rulings (measured 2026-11-13).
  2. detail — GET /carmwebservices/v2/carm/publicrulings/rulingsdetails/{rulingsId}?lang=en
     → {type, analysis, applicant, cbsaContact, classificationNumber, consent, date, decision,
       externalReference, introduction, product, productDescription, reference, rulingsId,
       trsNumber}
     The applicant block names the importer (the company): "Furukh Khan / Bed Bath & Beyond
     Inc. / 700 Liberty Avenue Union / NJ 07083 US" — the first line is the contact person,
     the second the company.

LIVE LAWS (measured 2026-11-13):
  - the `lang` query parameter is MANDATORY: without it the service answers 400. It is baked
    into both op paths (en).
  - the text fields carry "&&" as the line separator (and HTML entities such as &nbsp; and
    &amp;) — the parser turns "&&" into newlines and unescapes the entities.
  - the rulingsId is a string (e.g. "8000001670"), not a number.

Politeness: 0.5/4, concurrency 2, TTL 24h.
"""
import html
import re

from ..errors import SdkError

provider = {
    "id": "ca_cbsa",
    "baseUrl": "https://ccp-pcc.cbsa-asfc.cloud-nuage.canada.ca",
    "rate": {"rps": 0.5, "burst": 4},
    "concurrency": 2,
    "ops": {
        # lang=en is mandatory upstream (400 without it)
        "list": {"path": "/carmwebservices/v2/carm/publicrulings/list?lang=en", "timeout": 60.0},
        "detail": {"path": "/carmwebservices/v2/carm/publicrulings/rulingsdetails/{rulings_id}"
                         "?lang=en",
                   "timeout": 60.0},
    },
    "ttl": {"list": 24 * 3600, "detail": 24 * 3600},
}


def _clean(s):
    """The service's text fields: "&&" is the line separator, the entities are HTML."""
    t = html.unescape(str(s or ""))
    t = t.replace("&&", "\n")
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in t.split("\n")]
    return "\n".join([x for x in lines if x])


def _lines(s):
    return [x for x in _clean(s).split("\n") if x]


def flat_ruling(row):
    """One list row → the flat row."""
    return {
        "rulings_id": row.get("rulingsId"),
        "classification_number": row.get("classificationNumber"),
        "date": row.get("date"),
        "product": row.get("product"),
        "type": row.get("type"),
    }


def parse_detail(doc):
    """The detail document → the flat detail (the applicant block is split into its lines)."""
    if not isinstance(doc, dict) or not doc.get("rulingsId"):
        raise SdkError("upstream_unavailable", provider="ca_cbsa",
                       detail="the ruling detail answered an unexpected shape (no rulingsId)")
    applicant_lines = _lines(doc.get("applicant"))
    contact_lines = _lines(doc.get("cbsaContact"))
    return {
        "rulings_id": doc.get("rulingsId"),
        "classification_number": doc.get("classificationNumber"),
        "date": doc.get("date"),
        "type": doc.get("type"),
        "product": doc.get("product"),
        "product_description": _clean(doc.get("productDescription")),
        "applicant": "\n".join(applicant_lines),
        "applicant_lines": applicant_lines,
        # the importer is the line after the contact person (upstream order)
        "applicant_company": applicant_lines[1] if len(applicant_lines) > 1 else
                             (applicant_lines[0] if applicant_lines else None),
        "cbsa_contact": contact_lines[0] if contact_lines else None,
        "introduction": _clean(doc.get("introduction")),
        "analysis": _clean(doc.get("analysis")),
        "decision": _clean(doc.get("decision")),
        "reference": _clean(doc.get("reference")),
        "consent": _clean(doc.get("consent")),
        "external_reference": doc.get("externalReference"),
        "trs_number": doc.get("trsNumber"),
    }


def rulings_raw(*, limit=50, offset=0, cache=None, no_cache=False):
    """→ {total, rows[], params, _meta}. The list is the whole ruling set (1,234 live);
    the face pages it locally."""
    from ..transport import call_provider

    try:
        lim = int(limit)
        off = int(offset)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="ca_cbsa",
                       detail=f"limit/offset must be integers, got limit={limit!r} offset={offset!r}")
    if lim < 1:
        raise SdkError("usage_error", provider="ca_cbsa", detail=f"limit must be >= 1, got {lim}")
    if off < 0:
        raise SdkError("usage_error", provider="ca_cbsa", detail=f"offset must be >= 0, got {off}")

    r = call_provider(provider, "list", {}, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    raw = doc.get("rulings")
    if raw is None and isinstance(doc, list):
        raw = doc
    if not isinstance(raw, list):
        raise SdkError("upstream_unavailable", provider="ca_cbsa",
                       detail="the ruling list answered an unexpected shape (no rulings array)")
    rows = [flat_ruling(x) for x in raw]
    return {
        "total": len(rows),
        "rows": rows[off:off + lim],
        "params": {"limit": lim, "offset": off},
        "_meta": r,
    }


def ruling_raw(rulings_id, *, cache=None, no_cache=False):
    """→ {row…, params, _meta}. One ruling (the rulingsId from the list)."""
    from ..transport import call_provider

    rid = str(rulings_id or "").strip()
    if not rid:
        raise SdkError("usage_error", provider="ca_cbsa", detail="rulings_id is required")
    r = call_provider(provider, "detail", {"rulings_id": rid}, cache=cache, no_cache=no_cache)
    row = parse_detail(r["data"] or {})
    row["params"] = {"rulings_id": rid}
    row["_meta"] = r
    return row
