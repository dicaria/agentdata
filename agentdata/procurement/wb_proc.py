"""wb_proc — World Bank procurement notice stream face provider (search.worldbank.org /api/v2/procnotices; keyless).

procurement register (admitted in 0.3.6; shapes verified by first-hand live probing). Probed live 2026-10-29:
GET /api/v2/procnotices?format=json&notice_type=Contract+Award&rows=2&os=0
  → {rows (echoed), os (echoed), page (echoed), total ("313071" — a string, not a number), procnotices [rows…15 keys]}
  —— **313,071 award notices in full** (MDB buyer universe: IBRD/IDA development projects in 100+ countries).
Row keys: id (OP004xxxxx stable key)/notice_type/noticedate ("28-Oct-2026" form)/notice_status/
project_id (P five-digit key)/project_name/project_ctry_name/bid_reference_no/bid_description/
procurement_group/procurement_method_code/_name/submission_date/notice_text (full HTML text).
Supplier keys hide in the embedded notice_text section: `Awarded Firm(s): NAME (SUPP_ID) address…` — regex-extracted into
{name, supp_id} (**firm name + WB supplier id, both emitted**, probed live 2026-10-29: EASYMANAGEMENT (1137478) etc.);
notice_text itself is not returned on the row face (embedded contact addresses/phones stay out of the face — face values = name + key + project axis).
Params mirrored verbatim: notice_type (default "Contract Award" — the value domain of other notice types is upstream's own, passed through with no local wall)/
rows (page size)/os (offset); filter params in quoted form (%22…%22) give a fake zero-hit — upstream quirk on record, not compensated.
TTL: immutable once notice_status=Published — 7 days; polite tier 1 rps (no published quota, conservative pick).
"""
import re

from ..errors import SdkError

provider = {
    "id": "wb_proc",
    "baseUrl": "https://search.worldbank.org",
    "rate": {"rps": 1, "burst": 2},
    "ops": {
        "procnotices": {"path": "/api/v2/procnotices"},
    },
    "ttl": {"procnotices": 7 * 24 * 3600},
}

# Row narrowing (15 keys → skeleton minus notice_text/notice_lang_name; upstream key names verbatim)
_FIELDS = ("id", "notice_type", "noticedate", "notice_status", "project_ctry_name",
           "project_id", "project_name", "bid_reference_no", "bid_description",
           "procurement_group", "procurement_method_code", "procurement_method_name",
           "submission_date")

# Embedded supplier section of notice_text (after tag stripping): starts at `Awarded Firm(s):`, stops at the Scores/Minimum Qualifying section markers
_AWARD_SEG = re.compile(r"Awarded Firm\(s\)\s*:?\s*(.*?)(?=\s{2,}(?:Scores|Minimum Qualifying|Date Notification)|$)",
                        re.S)
# Pair-by-pair `NAME (SUPP_ID)` inside the section — supplier id is 4-10 digits
_FIRM_PAIR = re.compile(r"([^\(\n]{2,120}?)\s*\((\d{4,10})\)")
_TAG = re.compile(r"<[^>]+>")


def _awarded_firms(notice_text):
    """notice_text HTML → [{name, supp_id}…] (pure function, offline-testable; address/phone sections are not paired in)."""
    seg = _AWARD_SEG.search(_TAG.sub(" ", notice_text or ""))
    if not seg:
        return []
    return [{"name": m.group(1).strip(" ,;:"), "supp_id": m.group(2)}
            for m in _FIRM_PAIR.finditer(seg.group(1))]


def procnotices_from_upstream(data):
    """Upstream response → {rows[], total, count} (pure function, offline-testable)."""
    rows = []
    for r in (data or {}).get("procnotices") or []:
        row = {k: r.get(k) for k in _FIELDS}
        row["awarded_firms"] = _awarded_firms(r.get("notice_text"))
        rows.append(row)
    try:
        total = int(data.get("total")) if data and data.get("total") is not None else None
    except (TypeError, ValueError):
        total = None  # total is echoed as a string — a non-numeric shape is not passed off as a number
    return {"rows": rows, "total": total, "count": len(rows)}


def procnotices_raw(notice_type="Contract Award", *, rows=10, os_=0, cache=None, no_cache=False):
    """→ {rows[], total, count, params, _meta} (os = offset under its upstream name — takes os_ to avoid shadowing the Python built-in).

    notice_type passed through under its upstream name (default Contract Award); rows 1-100 polite tier; os_ ≥0."""
    from ..transport import call_provider

    size = int(rows) if rows is not None else 10
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="wb_proc",
                       detail=f"rows must be 1-100 (polite tier), got '{rows}'")
    off = int(os_ if os_ is not None else 0)
    if off < 0:
        raise SdkError("usage_error", provider="wb_proc", detail=f"os must be ≥0, got '{os_}'")
    params = {"format": "json", "notice_type": notice_type or "Contract Award",
              "rows": size, "os": off}
    r = call_provider(provider, "procnotices", params, cache=cache, no_cache=no_cache)
    return {**procnotices_from_upstream(r["data"]), "params": params, "_meta": r}
