"""jp_jplatpat — J-PlatPat three-face IP search (JPO official portal www.j-platpat.inpit.go.jp,
zero-credential break-in; register 2026-11-04, re-verified live 2026-11-12, probes
tmp/probe-sdk-0356/p2_*). Company-domain IP faces (trademark/patent/design), the JP pillar of
the IP axis (DE/AU/ES/BR/CA precedents).

THE HASH GATE (client-side, not a server challenge): the SPA serves no cookies; the client
self-mints U=uuid4 / L="ja" / D="S0101" / S="www" / T=YYYYMMDDHHmmssSSS, then
POST /app/docgw/wsc1101 {"SERVICE_ID": "<WST0303|WSP0103|WSD0203>"} →
{"RSLT_INFO":{"RSLT_CD":0},"ECRL":105,"ECKY":"JPP2022"} (all three service ids answer the
SAME pair — one cached hash bootstraps all three faces). Z = sha256 over the ECRL bit-scheme
concat: bit0=extra(""), bit1=U, bit2=T, bit3=L, bit4=D, bit5=S, bit6=ECKY — ECRL=105 =
0b1101001 → sha256(U + "ja" + "JPP2022") (bits 1,3,6 ride — bit4 D does NOT: 0b1101001 reads
1,1,0,1,0,0,1). The Z value only has to MATCH the cookie set sent
(same-call consistency); U/T may be fresh per call, so the search cache stays keyed on the
deterministic body alone.

THREE FACES, same GET_LISTINFO contract ("SEARCH_TYPE":"1", "DISP_ID":"S0000",
NUM_TYPE always [], no paging keys — a PAGE/OFFSET key is answered C90001-E):
  trademark /app/tradeapi/wst0303 — 41-key rows, holder field APPN_RIGHT_HOLDER_HOLDER[],
    year dimension PER_APP_Y_BY, class facets PER_DIVISION (Nice)/TRADEMARK_TYPE/APP_TYPE;
  patent /app/comsrch/wsp0103 — 37-key rows, holder APPN_RIGHT_HOLDER[], + NUM_LST_MAX_CNT:0,
    year dimension KNOWN_Y_BY, facets PER_FI (the browser body also carries top-level
    OTID:null, but a null is stripped by the transport's params filter and ≡ key absent —
    back-to-back A/B 2026-11-12 answered identically, so the face sends the body without OTID);
  design /app/dtaapi/wsd0203 — 27-key rows, holder APPN_RIGHT_HOLDER[], year PER_APP_Y_BY,
    facets PER_CLASSIFY.
Holder names are NAME-LEVEL joins (no 法人番号; align against the NTA bulk register for a hard
key). Japanese katakana must ride FULL-WIDTH; latin letters normalize themselves (half-width
"POWER" matches full-width stored "Ｐｏｗｅｒ" rows).

YEAR SLICE = the enumeration key: FILTER_INFO{ITEM, COND, COMPAR_COND_SIGN} — the SIGN is
mandatory (a COND without SIGN is silently ignored — 2020 answered identically to 2019,
measured); "=" / ">=" / "<=" / ">" all verified live. 3,000-row per-call cap, no paging keys;
AUTO_NARROW_FLG=1 lets the upstream narrow silently and report the PRE-narrow total in
RSLT_INFO.AUTO_NARROW.AUTO_NARROW_PREV_COUNT_CNT (free counting — patent "ソニー" KNOWN_Y_BY
2024 narrowed to 1,265 live 2026-11-12). Beyond the cap: C90003-E hard error (rows 0) — the
caller slices by year, then by facet bucket (FILTER_INFO.FILTER_BY_HIT_CNT per bucket).

ERROR CODES: RSLT_CD 0 = ok; C10006-I = auto-narrow notice (rows follow the narrowed count);
C90001-E = schema violation (the face only sends the verified shape — treat as upstream
drift, raise); RSLT_CD 8 = captcha trigger (measured only under abnormal traffic — raise,
never retry through it). Rate: 4s/request (rps 0.25) — the polite cadence never triggers the
captcha. TTL: hash 30min (upstream doesn't state validity, measured stable well beyond);
search bodies deterministic → cached 24h.
"""
import hashlib
import time as _time
import uuid as _uuid

from ..errors import SdkError

provider = {
    "id": "jp_jplatpat",
    "baseUrl": "https://www.j-platpat.inpit.go.jp",
    "rate": {"rps": 0.25, "burst": 2},          # 4s/request — the RSLT_CD=8 captcha guard
    "concurrency": 1,
    "ops": {
        "hash": {"path": "/app/docgw/wsc1101", "method": "POST", "idempotent": True},
        "trademark": {"path": "/app/tradeapi/wst0303", "method": "POST", "idempotent": True, "timeout": 60.0},
        "patent": {"path": "/app/comsrch/wsp0103", "method": "POST", "idempotent": True, "timeout": 90.0},
        "design": {"path": "/app/dtaapi/wsd0203", "method": "POST", "idempotent": True, "timeout": 60.0},
    },
    "ttl": {"hash": 30 * 60, "trademark": 24 * 3600, "patent": 24 * 3600, "design": 24 * 3600},
}

_YEAR_SIGNS = ("=", ">=", "<=", ">")

# the three faces differ in exactly three places: endpoint, holder field, filter bucket names
_FACES = {
    "trademark": {"holder": "APPN_RIGHT_HOLDER_HOLDER", "year_item": "PER_APP_Y_BY",
                  "max": ["FILTER_MAXIMUM_CNT_PER_APP_Y_BY", "FILTER_MAXIMUM_CNT_APP_TYPE",
                          "FILTER_MAXIMUM_CNT_PER_DIVISION", "FILTER_MAXIMUM_CNT_TRADEMARK_TYPE"]},
    "patent": {"holder": "APPN_RIGHT_HOLDER", "year_item": "KNOWN_Y_BY",
               "max": ["FILTER_MAXIMUM_CNT_KNOWN_Y_BY", "FILTER_MAXIMUM_CNT_PER_FI"]},
    "design": {"holder": "APPN_RIGHT_HOLDER", "year_item": "PER_APP_Y_BY",
               "max": ["FILTER_MAXIMUM_CNT_PER_APP_Y_BY", "FILTER_MAXIMUM_CNT_PER_CLASSIFY"]},
}


def _create_hash(ecrl, ecky, extra=""):
    """ECRL seven-bit concat scheme (bit0=extra ""/bit1=U/bit2=T/bit3=L/bit4=D/bit5=S/bit6=ECKY);
    ECRL=105 = 0b1101001 → bits 1,3,6 ride (bit4 D does NOT) → sha256(U + "ja" + "JPP2022")."""
    u = str(_uuid.uuid4())
    t = _time.strftime("%Y%m%d%H%M%S") + "000"
    cookies = {"U": u, "L": "ja", "D": "S0101", "S": "www", "T": t}
    bits = ("0" * 7 + bin(int(ecrl))[2:])[-7:]
    p = ""
    for bit, val in ((0, extra), (1, u), (2, t), (3, cookies["L"]), (4, cookies["D"]),
                     (5, cookies["S"]), (6, ecky)):
        if bits[bit] == "1":
            p += val
    cookies["Z"] = hashlib.sha256(p.encode("utf-8")).hexdigest()
    return cookies


def _hash_pair(cache, no_cache):
    """→ {ECRL, ECKY} from wsc1101 (cached 30min; all three service ids answer the same pair)."""
    from ..transport import call_provider
    r = call_provider(provider, "hash", {"SERVICE_ID": "WST0303"}, cache=cache, no_cache=no_cache)
    d = r["data"] or {}
    ecrl, ecky = d.get("ECRL"), d.get("ECKY")
    if not ecrl or not ecky:
        raise SdkError("upstream_unavailable", provider="jp_jplatpat",
                       detail="wsc1101 answered without ECRL/ECKY (the hash-gate contract may have changed)")
    return ecrl, ecky


def _body(face, keyword, year=None, year_sign=None):
    """The verified request body per face (class _D trademark / Ib patent / lD design)."""
    f = _FACES[face]
    filt = {}
    for key in f["max"]:
        filt[key] = 10
    if year is not None:
        filt["ITEM"] = f["year_item"]
        filt["COND"] = str(year)
        filt["COMPAR_COND_SIGN"] = year_sign
    si = {"AUTO_NARROW_FLG": 1, "SEARCH_COND": [{"NUM_TYPE": [], "KEYWD": keyword}],
          "SEARCH_OPTN": {"FILTER_INFO": filt}}
    body = {"DISP_ID": "S0000", "SEARCH_TYPE": "1",
            "SIMPLE_SEARCH_DISP": si, "SEARCH_RSLT_MAX_CNT": 3000,
            "NUM_LST_MAX_CNT": 3000, "INPUT_NUM_LST": [], "SORT_INFO": {"ITEM": None, "SORT_ORDER": 0}}
    if face == "trademark":
        body["SEARCH_TARGET_TYPE"] = {"APP_REG_INFO": 1, "BUL": 0}
    if face == "patent":
        # the browser body also carries top-level OTID:null, but a null is stripped by the
        # transport's params filter and ≡ key absent (A/B-verified 2026-11-12) — not sent
        body["NUM_LST_MAX_CNT"] = 0
    return body


def rows_from_upstream(data):
    """search response → {rows (verbatim), total, auto_narrow (None|{count, prev_count})}
    (pure function)."""
    ri = data.get("RSLT_INFO") or {}
    auto = ri.get("AUTO_NARROW") or None
    return {"rows": list(data.get("SEARCH_RSLT_LIST") or []),
            "total": ri.get("SEARCH_HIT_CNT"),
            "auto_narrow": ({"count": auto.get("AUTO_NARROW_COUNT_CNT"),
                             "prev_count": auto.get("AUTO_NARROW_PREV_COUNT_CNT"),
                             "date_item": auto.get("AUTO_NARROW_DATE_ITEM")} if auto else None)}


def _search_raw(face, keyword, year, year_sign, cache, no_cache):
    from ..transport import call_provider

    kw = str(keyword or "").strip()
    if not kw:
        raise SdkError("usage_error", provider="jp_jplatpat",
                       detail=f"jp_{face}_search requires q (a keyword — company name, mark, "
                              "or invention title; katakana FULL-WIDTH)")
    if year is not None and not year_sign:
        raise SdkError("usage_error", provider="jp_jplatpat",
                       detail="year requires year_sign ('='|'>='|'<='|'>') — a COND without a SIGN is "
                              "silently ignored by the upstream (measured: 2020 answered as unfiltered)")
    if year_sign and year is None:
        raise SdkError("usage_error", provider="jp_jplatpat",
                       detail="year_sign requires year")
    if year_sign and year_sign not in _YEAR_SIGNS:
        raise SdkError("usage_error", provider="jp_jplatpat",
                       detail=f"year_sign must be one of {'|'.join(_YEAR_SIGNS)}, got '{year_sign}'")
    ecrl, ecky = _hash_pair(cache, no_cache)
    cookies = _create_hash(ecrl, ecky)
    cookie_hdr = "; ".join(f"{k}={v}" for k, v in cookies.items())
    r = call_provider(provider, face, _body(face, kw, year, year_sign),
                      cache=cache, no_cache=no_cache, extra_headers={"Cookie": cookie_hdr})
    d = r["data"] or {}
    ri = d.get("RSLT_INFO") or {}
    msg = str(ri.get("MSG_ID") or "")
    if ri.get("RSLT_CD") == 8:
        raise SdkError("upstream_limited", provider="jp_jplatpat",
                       detail="RSLT_CD=8 — the captcha gate tripped (abnormal traffic); slow down and "
                              "retry much later (never retry through it)")
    if msg.endswith("C90001-E"):
        raise SdkError("upstream_unavailable", provider="jp_jplatpat",
                       detail="C90001-E schema rejection on the verified body — the upstream contract "
                              "has changed (schema drift, not a caller error)")
    out = rows_from_upstream(d)
    out["params"] = {"q": kw, "year": year, "year_sign": year_sign, "face": face}
    out["_meta"] = r
    return out


def trademark_search_raw(q, *, year=None, year_sign=None, cache=None, no_cache=False):
    """trademark face (wst0303; 41-key rows, holder APPN_RIGHT_HOLDER_HOLDER, Nice
    PER_DIVISION facets)."""
    return _search_raw("trademark", q, year, year_sign, cache, no_cache)


def patent_search_raw(q, *, year=None, year_sign=None, cache=None, no_cache=False):
    """patent face (wsp0103; 37-key rows, holder APPN_RIGHT_HOLDER, FI facets)."""
    return _search_raw("patent", q, year, year_sign, cache, no_cache)


def design_search_raw(q, *, year=None, year_sign=None, cache=None, no_cache=False):
    """design face (wsd0203; 27-key rows, holder APPN_RIGHT_HOLDER, classify facets)."""
    return _search_raw("design", q, year, year_sign, cache, no_cache)
