"""kr_krx — KRX Global listed-company universe + main-index snapshot
(global.krx.co.kr, keyless; 0.3.73 batch E15).

The THREE-SISTER GATE LAW (probed 2026-11-17, re-verified live 2026-11-20 —
tmp/probe-e15/): Korea Exchange runs three portals with three different
postures — data.krx.co.kr is a MEMBER WALL (login alert + Akamai bm_s sensor;
the pykrx era is over), kind.krx.co.kr is WAF-gated (robots + random-path
sensors), global.krx.co.kr is OPEN (robots: Allow: / verbatim). One
institution, one policy per portal — enumerate the portal family before
declaring an exchange dead.

  - THE OTP DOUBLE-STEP GRID (the crown): POST /contents/COM/GenerateOTP.jspx
    with name=form&bld=… mints a base64 one-shot code; POST it back (with a
    1-2s gap — the measured inter-step cadence) to /contents/GLB/99/
    GLB99000001.jspx as {market_gubun, code, bldcode} → block1 = the whole
    universe ONE-SHOT (~2,769 rows × 10 cols, no paging): isu_cd / eng_cor_nm
    / std_ind_cd / ind_nm / lst_stk_vl / cpt / par_pr / iso_cd / no / tot_cnt.
  - THE BLD PATH LAW: the bld is the FULL PATH FORM 'GLB/03/0308/0308010000/
    glb0308010000' (parsed off the hosting page's <form data-bld=…>), NOT the
    endpoint name 'GLB99000001' (that is the form ACTION). A WRONG bld pair
    answers 200 with a ZERO-BYTE body — no error code (the silent-empty law,
    re-hit live during the E15 probe: bld=GLB99000001 → 0 bytes).
  - bld SUFFIX PAIRING: bare name ↔ form (full rows); _01 ↔ tablesubmit (the
    aggregate block: tot_ldr/tot_isu/tot_cnt — 2769/2878 probe day); _02/_03 ↔
    selectbox (industry dictionary — _02 = the 21 top-level DS_CODE classes,
    std_ind_cd is a 2+2+2 six-digit hierarchy). A mismatched pair silently
    falls back to the aggregate — verify row counts, never trust a small
    answer from a form call.
  - market_gubun radio values (parsed off the page): 0 All / 1 KOSPI /
    2 KOSDAQ / 6 KONEX. All=2,769 reconciles with the per-board splits.
  - THE FREE-OTP FAMILY: /main/main.jspx?bld={listed_company_list,
    listing_list, index_list, news_list} answers by plain GET — no OTP. The
    index_list snapshot carries idx_nm / clsprc_idx / cmpr_idx / cmpr_rt /
    updown (~8 main indices, KOSPI/KOSDAQ/KOSPI 200/KRX 300/Korea Value-up).
  - NUMBERS RIDE COMMAS: lst_stk_vl / cpt / par_pr are thousand-separated
    strings — verbatim in rows, plus *_num int companions (the Wiener
    decimal law's Korean sibling). cmpr_rt keeps upstream's own raw
    scientific-notation string verbatim (never re-format it).
  - OTP codes are ONE-SHOT: the grid call is cached under a CODE-LESS key
    (hand-rolled via transport cache_key_for — the code must never enter the
    cache key or every call re-mints and the cache never hits), the OTP mint
    itself always rides cache=None.

Politeness 1 rps, burst 1 (the OTP mint + grid are 2 calls back-to-back with
the measured 2s gap). TTLs: grid 6h (the universe turns over slowly), main
index snapshot 15min (intraday quote).
"""
import json
import time

from ..errors import SdkError

provider = {
    "id": "kr_krx",
    "baseUrl": "https://global.krx.co.kr",
    "rate": {"rps": 1.0, "burst": 1},
    "concurrency": 1,
    "ops": {
        "otp": {"path": "/contents/COM/GenerateOTP.jspx",
                "method": "POST", "urlencoded": True,
                "idempotent": True, "accept": "text", "timeout": 45.0},
        "grid": {"path": "/contents/GLB/99/GLB99000001.jspx",
                 "method": "POST", "urlencoded": True,
                 "idempotent": True, "accept": "text", "timeout": 90.0},
        "main": {"path": "/main/main.jspx",
                 "idempotent": True, "accept": "text", "timeout": 45.0},
    },
    "ttl": {"grid": 21600, "main": 900},
}

# the bld path law: the FULL path form off the hosting page's <form data-bld>,
# never the endpoint name (a wrong pair answers 200 with zero bytes)
_BLD = "GLB/03/0308/0308010000/glb0308010000"

BOARDS = {"all": "0", "kospi": "1", "kosdaq": "2", "konex": "6"}


def _num(v):
    """thousand-separated string → int companion; None when not numeric."""
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    return int(s) if s.isdigit() else None


def _grid_call(gubun, cache, no_cache):
    """the OTP double-step with a CODE-LESS cache key — the one-shot code must
    never enter the key (it would defeat the cache: every call re-mints), so
    the grid rides hand-rolled cache.get/set around the two live steps."""
    from ..transport import call_provider, cache_key_for

    ttl = provider["ttl"]["grid"]
    key = None
    if cache is not None:
        key = cache_key_for("grid", {"market_gubun": gubun, "bldcode": _BLD},
                            scope=provider["baseUrl"])
        if not no_cache:
            hit = cache.get(provider["id"], key, ttl)
            if hit:
                return {"ok": True, "data": hit["payload"], "from_cache": True,
                        "fetched_at": hit["fetched_at_iso"], "provider": provider["id"]}
    otp = call_provider(provider, "otp", {"name": "form", "bld": _BLD},
                        cache=None, no_cache=True)
    code = (otp["data"] or "").strip()
    if not code:
        raise SdkError("upstream_unavailable", provider="kr_krx",
                       detail="GenerateOTP.jspx answered an empty code — the OTP gate may have moved; re-probe")
    time.sleep(2)  # the measured inter-step gap (shorter gaps flaked in probing)
    r = call_provider(provider, "grid",
                      {"market_gubun": gubun, "code": code, "bldcode": _BLD},
                      cache=None, no_cache=True)
    if not r.get("data"):
        # the silent-empty law: a wrong bld pair answers 200 with ZERO bytes —
        # with the pinned correct pair this shape means the gate changed
        raise SdkError("upstream_unavailable", provider="kr_krx",
                       detail="the grid answered 200 with an empty body (the wrong-bld silent-empty shape) — "
                              "the OTP grid may have moved; re-probe")
    if cache is not None and key is not None:
        cache.set(provider["id"], key, r["data"], ttl)
    return r


def listed(*, board="all", industry=None, limit=None, cache=None, no_cache=False):
    """→ {board, total_count, row_count, rows[], params, _meta}; the KRX Global
    listed universe ONE-SHOT (~2,769 rows × 10 cols via the OTP double-step —
    isu_cd / eng_cor_nm / std_ind_cd + ind_nm industry / lst_stk_vl listed
    shares / cpt capital / par_pr par value / iso_cd currency). board picks
    market_gubun (all/kospi/kosdaq/konex — All reconciles with the board
    splits); industry filters std_ind_cd by PREFIX (the 2+2+2 six-digit
    hierarchy: '07' wholesale, '0746', '074604' all legal). Numbers keep their
    verbatim comma strings plus *_num int companions."""
    b = str(board or "all").strip().lower()
    if b not in BOARDS:
        raise SdkError("usage_error", provider="kr_krx",
                       detail=f"--board must be one of {'/'.join(BOARDS)} (all/kospi/kosdaq/konex), got \"{board}\"")
    gubun = BOARDS[b]
    r = _grid_call(gubun, cache, no_cache)
    try:
        d = json.loads(r["data"])
        block = d.get("block1") or []
    except (ValueError, AttributeError):
        raise SdkError("upstream_unavailable", provider="kr_krx",
                       detail="the grid body is not the {block1:[…]} JSON envelope — the OTP grid may have moved; re-probe")
    rows = []
    ind = str(industry).strip() if industry else None
    for x in block:
        if not isinstance(x, dict):
            continue
        if ind and not str(x.get("std_ind_cd") or "").startswith(ind):
            continue
        row = dict(x)
        for src, dst in (("lst_stk_vl", "lst_stk_vl_num"), ("cpt", "cpt_num"),
                         ("par_pr", "par_pr_num")):
            n = _num(x.get(src))
            if n is not None:
                row[dst] = n
        rows.append(row)
    total = int(block[0].get("tot_cnt")) if block and str(block[0].get("tot_cnt") or "").isdigit() else len(rows)
    out = rows
    if limit is not None and int(limit) >= 0:
        out = rows[: int(limit)]
    return {"board": b, "total_count": total, "row_count": len(rows),
            "rows": out, "params": {"board": b, "industry": ind},
            "_meta": r}


def indices(*, cache=None, no_cache=False):
    """→ {row_count, rows[], params, _meta}; the main-index snapshot off the
    free-OTP family (GET main.jspx?bld=index_list — no OTP dance): the main
    indices (KOSPI / KOSDAQ / KOSPI 200 / KRX 300 / Korea Value-up — 5 on the
    probe day, the set drifts) with idx_nm / clsprc_idx close / cmpr_idx
    change / cmpr_rt rate / updown. cmpr_rt keeps upstream's raw
    scientific-notation string verbatim."""
    from ..transport import call_provider

    r = call_provider(provider, "main", {"bld": "index_list"},
                      cache=cache, no_cache=no_cache)
    try:
        d = json.loads(r["data"])
        rows = d.get("output") or []
    except (ValueError, AttributeError):
        raise SdkError("upstream_unavailable", provider="kr_krx",
                       detail="main.jspx did not answer the {output:[…]} envelope — the free-OTP family may have moved; re-probe")
    return {"row_count": len(rows), "rows": rows,
            "params": {"bld": "index_list"}, "_meta": r}
