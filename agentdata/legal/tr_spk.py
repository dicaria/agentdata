"""tr_spk — Turkish Capital Markets Board administrative fines + trading bans (ws.spk.gov.tr
IdariYaptirimlar service; the legal domain's first TR face; research volume tr-spk-ws-api,
册 234; faces admitted in 0.3.36, probed first-hand 2026-11-04 tmp/probe-tr-spk-0336/ with the
SDK's own polite UA, direct).

Two faces, both local full-register scans (the Swagger v2 surface publishes NO query parameters
on these lists — the POST IdariParaCezalari filter body {"yil": …} is silently ignored, pinned
dead at research time; the by-year GET sibling works but is redundant when the whole register
ships in one shot).

Fines: GET /IdariYaptirimlar/api/TumIdariParaCezalari answers the WHOLE register in ONE 1.3MB
shot — 2,281 rows × 14 columns, every column verbatim (id, mkkSicilNo, unvan,
kurulKararTarihi, kurulKararNo, aciklama, yasa, teblig, madde, tutar, davaBilgisi,
yargilamaAsamasi, kurulKarari, ihlal). Behaviours pinned 2026-11-04: karar years span
2016→2026; **1,281 of 2,281 rows are INDIVIDUALS** (mkkSicilNo arrives masked,
"28***449********" — the unmasked MKK registry number is not public here); unvan is null on 6
rows; yasa (1 row) and madde (4 rows) are near-always null — the violation rides teblig (the
communiqué clause) and ihlal; davaBilgisi is Var 682 / Yok 1,599 and yargilamaAsamasi is filled
exactly on the Var rows (Dava açıldı/Yargılama sürüyor 406 / Davanın reddi/Kesin hüküm 263 /
Davanın kabulü/Kesin hüküm 13); tutar is the fine in TL (min 9,321 — max 362,123,139.86).
aciklama carries embedded newlines — kept verbatim. Person names are published in the official
enforcement register — recorded verbatim, no person-level entity (the co_sic/SEBI precedent).

Bans: GET /IslemYasaklari/Kisiler = 295 persons {mkkSicilNo (masked, 16 chars), isimSoyisim};
GET /IslemYasaklari/Sirketler = 3 companies {mersisNo (the 16-digit MERSIS key), unvani};
GET /IslemYasaklari/Sirket/{mersisNo} = the ban edges of one company — one row per banned
equity {pay (the issuer's full name), payKodu (the BIST ticker), kurulKararTarihi,
kurulKararNo; unvan may carry an "(N)" suffix, kept verbatim}. The company wall is enriched
automatically (3 detail GETs on a cold call — the ticker edge is the substance of a ban).
The person-detail sibling /Kisi/{id} answered EMPTY with the masked mkkSicilNo as id (t2,
2026-11-04): its key is the unmasked MKK number, which the public list masks — not shippable.

Channel: research-time probing needed Chrome UA + proxy + Referer (册 234); the SDK layer
disproved all of it — honest agentdata UA, direct, zero extra headers, all seven endpoints 200
(t1/t2, 2026-11-04). Rate: ws.spk.gov.tr publishes no window -> polite 0.5 rps / burst 2 (the
registry-search family posture; the host-layer bucket is shared with tr_spk_borsa on the same
host). TTL: 24h both faces (register posture — new rows land with each Board decision).
"""
from ..errors import SdkError

provider = {
    "id": "tr_spk",
    "baseUrl": "https://ws.spk.gov.tr",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "fines": {"path": "/IdariYaptirimlar/api/TumIdariParaCezalari", "timeout": 90.0},
        "ban_persons": {"path": "/IdariYaptirimlar/api/IslemYasaklari/Kisiler", "timeout": 60.0},
        "ban_companies": {"path": "/IdariYaptirimlar/api/IslemYasaklari/Sirketler", "timeout": 60.0},
        "ban_company_detail": {"path": "/IdariYaptirimlar/api/IslemYasaklari/Sirket/{id}",
                               "timeout": 60.0},
    },
    "ttl": {"fines": 24 * 3600, "ban_persons": 24 * 3600,
            "ban_companies": 24 * 3600, "ban_company_detail": 24 * 3600},
}

# the 14 fines columns, verbatim (the register's own Turkish names — a join onto TR registries
# rides unvan (name) / mkkSicilNo (MKK, masked for persons) / kurulKararNo (the decision key))
_FINE_COLS = ("id", "mkkSicilNo", "unvan", "kurulKararTarihi", "kurulKararNo", "aciklama",
              "yasa", "teblig", "madde", "tutar", "davaBilgisi", "yargilamaAsamasi",
              "kurulKarari", "ihlal")


def fines_rows_from_upstream(data):
    """Upstream bare array → fines rows (pure function; the 15 columns verbatim, embedded
    newlines in aciklama included — nothing is trimmed, translated or invented)."""
    return [{k: r.get(k) for k in _FINE_COLS} for r in (data or []) if isinstance(r, dict)]


def filter_fines(rows, name=None, year=None):
    """Local register scan (pure function). name: contains (case-insensitive) over unvan;
    year: exact over the first four chars of kurulKararTarihi (the Board-decision year)."""
    needle = str(name or "").strip().lower() or None
    yr = str(year).strip() if year not in (None, "") else None
    if yr is not None and not (len(yr) == 4 and yr.isdigit()):
        raise SdkError("usage_error", provider="tr_spk",
                       detail=f"year must be a 4-digit Board-decision year (2016-2026 span, "
                              f"pinned 2026-11-04), got {year!r}")
    hits = []
    for r in rows:
        if yr and str(r.get("kurulKararTarihi") or "")[:4] != yr:
            continue
        if needle and needle not in str(r.get("unvan") or "").lower():
            continue
        hits.append(r)
    return hits


def fines_raw(name=None, *, year=None, limit=20, cache=None, no_cache=False):
    """Full-register scan (pulls the whole 2,281-row fine register in ONE GET, caches 24h,
    scans locally) -> {rows, total_matched, scanned_rows, census, limit_applied, params, _meta}.

    name = contains over unvan (company or person — 1,281 of 2,281 rows are individuals with a
    masked mkkSicilNo); year = the Board-decision year. No filter -> enumerate from the head."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="tr_spk",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    r = call_provider(provider, "fines", {}, cache=cache, no_cache=no_cache)
    rows = fines_rows_from_upstream(r["data"])
    hits = filter_fines(rows, name=name, year=year)
    persons = sum(1 for x in rows if x.get("mkkSicilNo"))
    years = sorted({str(x.get("kurulKararTarihi") or "")[:4] for x in rows if x.get("kurulKararTarihi")})
    census = {
        "persons": persons,                      # masked mkkSicilNo = an individual subject
        "firms": len(rows) - persons,
        "dava_var": sum(1 for x in rows if x.get("davaBilgisi") == "Var"),
        "year_min": years[0] if years else None,
        "year_max": years[-1] if years else None,
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "census": census, "limit_applied": size,
            "params": {"name": name, "year": year}, "_meta": r}


def bans_raw(name=None, *, type=None, limit=20, cache=None, no_cache=False):
    """Both ban walls in one call (persons 295 + companies 3, each company enriched with its
    ban edges — the banned BIST ticker) -> {rows, total_matched, scanned, limit_applied, params,
    _meta, _metas}.

    rows are heterogeneous on purpose: kind=person rows carry the upstream {mkkSicilNo (masked),
    isimSoyisim} verbatim; kind=company rows carry {mersisNo, unvani} plus bans = the detail
    endpoint's rows verbatim ({pay, payKodu, kurulKararTarihi, kurulKararNo, unvan}). name =
    contains over isimSoyisim / unvani / pay (the banned issuer — screening the issuer name
    hits the banned party's row); type = person|company exact."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="tr_spk",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    if type not in (None, "", "person", "company"):
        raise SdkError("usage_error", provider="tr_spk",
                       detail=f"type must be person or company (the two ban walls), got {type!r}")
    needle = str(name or "").strip().lower() or None
    metas = []
    rp = call_provider(provider, "ban_persons", {}, cache=cache, no_cache=no_cache)
    rc = call_provider(provider, "ban_companies", {}, cache=cache, no_cache=no_cache)
    metas += [rp, rc]
    persons = [{"kind": "person", **{k: x.get(k) for k in ("mkkSicilNo", "isimSoyisim")}}
               for x in (rp["data"] or []) if isinstance(x, dict)]
    companies = []
    for x in (rc["data"] or []):
        if not isinstance(x, dict) or not x.get("mersisNo"):
            continue
        rd = call_provider(provider, "ban_company_detail", {"id": x["mersisNo"]},
                           cache=cache, no_cache=no_cache)
        metas.append(rd)
        companies.append({"kind": "company",
                          **{k: x.get(k) for k in ("mersisNo", "mkkSicilNo", "unvani")},
                          "bans": [b for b in (rd["data"] or []) if isinstance(b, dict)]})
    rows = persons + companies
    hits = []
    for r in rows:
        if type and r["kind"] != type:
            continue
        if needle:
            hay = " ".join(str(r.get(k) or "") for k in ("isimSoyisim", "unvani"))
            hay += " " + " ".join(str(b.get("pay") or "") for b in r.get("bans") or [])
            if needle not in hay.lower():
                continue
        hits.append(r)
    return {"rows": hits[:size], "total_matched": len(hits),
            "scanned": {"persons": len(persons), "companies": len(companies)},
            "limit_applied": size,
            "params": {"name": name, "type": type or None},
            "_meta": rp, "_metas": metas}
