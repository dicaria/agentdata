"""kr_hometax — Korea NTA hometax business-registration status (휴폐업/tax type) provider (keyless anonymous single-shot).

company roster (admitted in 0.3.11, probe tmp/probe-co-kr/). Shape verified 2026-10-30:
POST to the bare domain hometax.go.kr/wqAction.do?actionId=ATTABZAA001R08&screenId=UTEABAAA13&
popupYn=false&realScreenId= (the actionId family lives in the query string) + a seven-field flat JSON body
(dongCode = middle-2 digits of the 10-digit number, txprDscmNo = the 10-digit business number,
the other four constants) →
{resultMsg{result S/F}, trtCntn full status sentence, smpcBmanTrtCntn concise status + 폐업일자,
smpcBmanEnglTrtCntn English version, txprNm always null when anonymous (no owner-name leak),
trtEndCd, nrgtTxprYn}.

**Harvest-recipe deltas (two SDK-layer reversals, 2026-10-30 elimination probe)**: (1) the EverSafe
trailing token (42-char hash appended to the JSON body) is **NOT required** — a bare POST without it
still returns 200 result=S with the correct state (the old recipe was defensive redundancy; the
hometaxbot k4 confusion is a smokescreen); (2) a browser UA is **NOT required** — urllib's default
UA passes (not in the FAA/JFTC header-fingerprint gate family). (3) The response is **UTF-8 JSON**
(Content-Type self-evident; the old cp949 observation belonged to a different action — the SDK face
decodes UTF-8 via http_json and is correct).

**Four-state semantics (every result=S shape is a legal answer, not an error)**: operating =
「부가가치세 일반과세자 입니다.」 (VAT general taxpayer) or the 간이/과세특례 variants; closed =
「폐업자 (…, 폐업일자:YYYY-MM-DD)」 (ISO date regex-extracted); unregistered =
「국세청에 등록되지 않은…」 (registered=False); 휴업 (suspended) same sentence family.
Positioning = status-column enrichment over lists (the batch-100-건 actionId has drifted, unexplored).
TTL: status changes slowly — 7 days; politeness 0.5 rps (conservative tier for a government
real-name-grade query gate).
"""
import re

from ..errors import SdkError

provider = {
    "id": "kr_hometax",
    "baseUrl": "https://hometax.go.kr",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # actionId family inline in the path query string (POST read semantics: the seven fields are not path
        # params, they go in the JSON body; idempotent participates in retries)
        "biz_status": {"path": "/wqAction.do?actionId=ATTABZAA001R08&screenId=UTEABAAA13"
                               "&popupYn=false&realScreenId=",
                       "method": "POST", "idempotent": True, "timeoutMs": 30000},
    },
    "ttl": {"biz_status": 7 * 86400},
}

_BIZNO_RE = re.compile(r"^\d{10}$")
_CLOSED_DATE_RE = re.compile(r"폐업일자[:：]?\s*(\d{4}-\d{2}-\d{2})")
_UNREGISTERED_MARK = "국세청에 등록되지 않은"
_CLOSED_MARK = "폐업"


def _bizno(v):
    """'124-81-00998'/'1248100998' → 10-digit string (Korean business number 3-2-5 hyphens optional)."""
    norm = re.sub(r"[\s-]", "", str(v or ""))
    if not _BIZNO_RE.match(norm):
        raise SdkError("usage_error", provider="kr_hometax",
                       detail=f"business registration number must be 10 digits (3-2-5 hyphens optional, e.g. 124-81-00998), got {v!r}")
    return norm


def parse_status(data, biz_no):
    """Upstream JSON → four-state normalization (operating/closed/unregistered/other; registered bit + closed ISO date extracted).

    Every result=S shape is a legal answer (unregistered is S too, not an error — same semantics as VIES INVALID);
    result≠S or a malformed shape → state='error', verbatim passthrough, never faked.
    """
    d = data or {}
    result = ((d.get("resultMsg") or {}).get("result")) or None
    trt = (d.get("trtCntn") or "").strip() or None
    simple = (d.get("smpcBmanTrtCntn") or "").strip() or None
    english = (d.get("smpcBmanEnglTrtCntn") or "").strip() or None
    blob = " ".join(x for x in (trt, simple) if x)
    m = _CLOSED_DATE_RE.search(blob)
    closed_date = m.group(1) if m else None
    if result == "S" and blob:
        if _UNREGISTERED_MARK in blob:
            state, registered = "unregistered", False
        elif _CLOSED_MARK in blob or closed_date:
            state, registered = "closed", True
        else:
            state, registered = "active", True
    else:
        state, registered = "error", None
    return {
        "biz_no": biz_no,
        "result": result,
        "state": state,                # active | closed | unregistered | error
        "registered": registered,      # None = malformed shape, never self-answered
        "tax_type": trt,               # full status sentence (tax type: 일반/간이/과세특례…)
        "simple_status": simple,       # concise status + 폐업일자
        "english_status": english,     # English status sentence
        "closed_date": closed_date,    # 폐업일자 ISO (always present on closed rows; operating/unregistered = None)
        "trt_end_cd": d.get("trtEndCd"),
    }


def biz_status_raw(biz_no, *, cache=None, no_cache=False):
    """→ {status, _meta} (four-state normalized; txprNm stays null when anonymous and is not carried in upstream response values)."""
    from ..transport import call_provider

    norm = _bizno(biz_no)
    params = {
        "dongCode": norm[3:5],   # middle-2-digit segment of the 10-digit number (district code)
        "txprDscmNo": norm,       # the 10-digit business number
        "inqrTrgtClCd": "1",
        "mobYn": "N",
        "psbSearch": "Y",
        "pubcUserNo": "",
        "userReqInfoVO": {},
    }
    r = call_provider(provider, "biz_status", params, cache=cache, no_cache=no_cache)
    return {"status": parse_status(r["data"], norm), "_meta": r}
