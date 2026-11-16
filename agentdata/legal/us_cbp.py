"""us_cbp — US Customs and Border Protection CROSS rulings (rulings.cbp.gov, keyless).

US legal face (0.3.60; admitted from the research booklet customs-rulings, re-probed live
2026-11-13):

CONTRACT:
  1. detail — GET /api/ruling/{ruling_number} → the full ruling (200, JSON):
     {text, url, id, rulingNumber, subject, categories, rulingDate, isUsmca, isNafta,
      collection, relatedRulings, modifiedBy, modifies, revokedBy, revokes, tariffs,
      operationallyRevoked, commodityGrouping}
     `text` is the ruling's plain-text body; its header block names the importer and the
     importer's address (the company join surface). `url` is a pre-signed S3 link to the
     original .doc/.pdf (it expires — X-Amz-Expires=900).
  2. stat — GET /api/stat/lastupdate → {…} the register's last-update stamp and the ruling
     count (222,344 rulings live, measured 2026-11-13).

LIVE LAWS (measured 2026-11-13):
  - the SEARCH endpoint (/api/search) is behind a reCAPTCHA Enterprise gate and answers 403 —
    only the detail-by-number surface is on the route (the face therefore takes a ruling
    number, and the register's size comes from the stat endpoint).
  - the ruling body is CRLF-padded plain text with a header block; the importer name is the
    line after the contact line.

Politeness: 0.5/4, concurrency 2, TTL 24h (the register is republished daily).
"""
import re

from ..errors import SdkError

provider = {
    "id": "us_cbp",
    "baseUrl": "https://rulings.cbp.gov",
    "rate": {"rps": 0.5, "burst": 4},
    "concurrency": 2,
    "ops": {
        "detail": {"path": "/api/ruling/{ruling_number}", "timeout": 40.0},
        "stat": {"path": "/api/stat/lastupdate", "timeout": 40.0},
    },
    "ttl": {"detail": 24 * 3600, "stat": 12 * 3600},
}

_NUMBER = re.compile(r"^\s*\d{4,8}\s*$")


def _clean_lines(text):
    """The ruling body → its non-empty lines (the upstream pads with CRs)."""
    out = []
    for raw in re.split(r"[\r\n]+", str(text or "")):
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if line:
            out.append(line)
    return out


def parse_detail(doc):
    """The ruling JSON → the flat row (the header block names the importer)."""
    if not isinstance(doc, dict) or not doc.get("rulingNumber"):
        raise SdkError("upstream_unavailable", provider="us_cbp",
                       detail="the ruling detail answered an unexpected shape (no rulingNumber)")
    lines = _clean_lines(doc.get("text"))
    # the header block: the ruling number/date, the classification line, then the CONTACT
    # line (Mr./Ms. …) and the IMPORTER company's name + address. The company is the line
    # AFTER the contact person (ruling 954699: "Mr. Y. Yoneyama" then "Sumitomo Corporation
    # of America"); a ruling addressed straight at a company (Corporation/Inc./Ltd/LLC line)
    # names the company itself.
    importer = None
    for i, line in enumerate(lines[:12]):
        if line.startswith(("Mr.", "Ms.", "Mrs.", "Dr.")):
            importer = lines[i + 1] if i + 1 < len(lines) else line
            break
        if line.startswith(("Corporation", "Inc.", "Ltd", "LLC")):
            importer = line
            break
    header = lines[:10]
    return {
        "ruling_number": doc.get("rulingNumber"),
        "id": doc.get("id"),
        "subject": doc.get("subject"),
        "ruling_date": doc.get("rulingDate"),
        "tariffs": doc.get("tariffs"),
        "collection": doc.get("collection"),
        "categories": doc.get("categories"),
        "is_usmca": doc.get("isUsmca"),
        "is_nafta": doc.get("isNafta"),
        "operationally_revoked": doc.get("operationallyRevoked"),
        "related_rulings": doc.get("relatedRulings"),
        "modifies": doc.get("modifies"),
        "modified_by": doc.get("modifiedBy"),
        "revokes": doc.get("revokes"),
        "revoked_by": doc.get("revokedBy"),
        "document_url": doc.get("url"),
        "importer": importer,
        "header": header,
        "text": "\n".join(lines),
    }


def ruling_raw(ruling_number, *, cache=None, no_cache=False):
    """→ {row…, params, _meta}. One ruling (the ruling number, e.g. "954699")."""
    from ..transport import call_provider

    n = str(ruling_number or "").strip()
    if not n:
        raise SdkError("usage_error", provider="us_cbp", detail="ruling_number is required")
    if not _NUMBER.match(n):
        raise SdkError("usage_error", provider="us_cbp",
                       detail=f"ruling_number must be the numeric ruling number (e.g. 954699), got {n!r}")
    r = call_provider(provider, "detail", {"ruling_number": n}, cache=cache, no_cache=no_cache)
    row = parse_detail(r["data"] or {})
    row["params"] = {"ruling_number": n}
    row["_meta"] = r
    return row


def stat_raw(*, cache=None, no_cache=False):
    """→ {stat{}, params, _meta}. The register's last-update stamp and ruling count."""
    from ..transport import call_provider

    r = call_provider(provider, "stat", {}, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    return {
        "total": doc.get("totalSearchableRulingsCount") or doc.get("totalRulings")
                or doc.get("count") or doc.get("rulings"),
        "stat": doc,
        "params": {},
        "_meta": r,
    }
