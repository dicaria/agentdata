"""tr_spk_borsa — SPK publicly-listed companies directory (ws.spk.gov.tr HalkaAcikSirket
service; the company domain's first TR face; research volume tr-spk-ws-api, 册 234; face
admitted in 0.3.36, probed first-hand 2026-11-04 tmp/probe-tr-spk-0336/ with the SDK's own
polite UA, direct).

One face — listed. Two one-shot lists + a single-record channel:
GET /HalkaAcikSirket/api/Sirketler/Borsa = 628 exchange-traded rows; GET …/BorsaDisi = 121
non-exchange rows — 749 total, no paging, no query surface (local scan family). Rows carry
10 columns verbatim (adresIl, webSitesi, telefon, faks, ePosta, kepAdresi, id, mersisNo,
mkkSicilNo, unvani): **mersisNo is the 16-digit MERSIS key** (the join onto TR registries;
6 Borsa + 2 BorsaDisi rows ship it empty -> null); mkkSicilNo arrives as "" OR null
inconsistently (both -> null); kepAdresi (3 rows) and unvani (8 rows) carry trailing
whitespace upstream — stripped, the only normalisation. **The lifecycle status rides INLINE in
unvani** — "(İFLAS NEDENİYLE) TASFİYE HALİNDE …" prefixes 1 Borsa / 15 BorsaDisi rows (no
separate status column; nothing is split out — the name is the register's own wording).

GET /HalkaAcikSirket/api/Sirket/{mersisNo} = the single-record channel: {sirketVarmi, mesaj,
sirket}. sirket adds tur (the segment in the register's wording), faaliyetDurumu and the full
street adres the lists lack. **The existence flag LIES (pinned 2026-11-04, t2)**: a MERSIS
number that is NOT in the listed register also answers sirketVarmi=true — with an all-null
sirket shell (unvani/mersisNo/faaliyetDurumu all null, id 0). The honest negative signal is
the null shell, not the flag; the face says so in its reason and returns the shell verbatim.

Channel: honest agentdata UA, direct, zero extra headers — all endpoints 200 (t1/t2,
2026-11-04; the research-time Chrome UA + proxy + Referer suite was disproved at the SDK
layer). Rate: polite 0.5 rps / burst 2 (the host-layer bucket is shared with legal tr_spk on
the same host). TTL: 24h (register posture).
"""
from ..errors import SdkError

provider = {
    "id": "tr_spk_borsa",
    "baseUrl": "https://ws.spk.gov.tr",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "borsa": {"path": "/HalkaAcikSirket/api/Sirketler/Borsa", "timeout": 60.0},
        "borsadisi": {"path": "/HalkaAcikSirket/api/Sirketler/BorsaDisi", "timeout": 60.0},
        "sirket": {"path": "/HalkaAcikSirket/api/Sirket/{id}", "timeout": 60.0},
    },
    "ttl": {"borsa": 24 * 3600, "borsadisi": 24 * 3600, "sirket": 24 * 3600},
}

# the 11 list columns verbatim; "" (and null) -> null, strings stripped (kepAdresi/unvani
# carry trailing whitespace upstream — pinned 2026-11-04)
_COLS = ("adresIl", "webSitesi", "telefon", "faks", "ePosta", "kepAdresi", "id",
         "mersisNo", "mkkSicilNo", "unvani")


def rows_from_upstream(data, segment):
    """Upstream bare array -> listed-company rows (pure function; segment = borsa|borsadisi,
    stamped on each row so the merged scan stays self-describing)."""
    out = []
    for r in (data or []):
        if not isinstance(r, dict):
            continue
        row = {"segment": segment}
        for k in _COLS:
            v = r.get(k)
            if isinstance(v, str):
                v = v.strip() or None   # "" -> null; trailing whitespace stripped
            row[k] = v
        out.append(row)
    return out


def _norm_mersis(mersis):
    m = str(mersis or "").strip()
    if not m:
        raise SdkError("usage_error", provider="tr_spk_borsa",
                       detail="mersis is required for the single-record channel (the 16-digit "
                              "MERSIS number, from listed rows)")
    if not (len(m) == 16 and m.isdigit()):
        raise SdkError("usage_error", provider="tr_spk_borsa",
                       detail=f"mersis must be exactly 16 digits (the register's own MERSIS "
                              f"shape, e.g. 0470003286100012), got {mersis!r}")
    return m


def listed_raw(name=None, *, segment="all", mersis=None, limit=20, cache=None, no_cache=False):
    """-> single record ({mersis, found, sirket, _meta}) when mersis is given, else the merged
    local scan ({rows, total_matched, scanned, limit_applied, params, _meta, _metas}).

    mersis (the single-record channel) is mutually exclusive with the scan filters. In the scan,
    name = contains (case-insensitive) over unvani; segment = borsa | borsadisi | all (default
    both walls). found mirrors sirket.unvani being set — sirketVarmi alone is NOT the negative
    signal (pinned live: a MERSIS outside the register also answers sirketVarmi=true with an
    all-null shell)."""
    from ..transport import call_provider

    if mersis not in (None, ""):
        if name or segment != "all":
            raise SdkError("usage_error", provider="tr_spk_borsa",
                           detail="mersis (single-record channel) and the scan filters "
                                  "(name/segment) are mutually exclusive — give exactly one")
        m = _norm_mersis(mersis)
        r = call_provider(provider, "sirket", {"id": m}, cache=cache, no_cache=no_cache)
        doc = r["data"] or {}
        sirket = doc.get("sirket") if isinstance(doc, dict) else None
        if not isinstance(sirket, dict):
            raise SdkError("upstream_unavailable", provider="tr_spk_borsa",
                           detail="the single-record channel carried no sirket object — the "
                                  "upstream shape may have changed")
        card = {}
        for k in ("tur", "faaliyetDurumu", "adres", "adresIl", "webSitesi", "telefon",
                  "faks", "ePosta", "kepAdresi", "id", "mersisNo", "mkkSicilNo", "unvani"):
            v = sirket.get(k)
            if isinstance(v, str):
                v = v.strip() or None
            card[k] = v
        return {"mersis": m, "sirketVarmi": doc.get("sirketVarmi"), "found": card["unvani"] is not None,
                "sirket": card, "params": {"id": m}, "_meta": r}

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="tr_spk_borsa",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    if segment not in ("all", "borsa", "borsadisi"):
        raise SdkError("usage_error", provider="tr_spk_borsa",
                       detail=f"segment must be borsa, borsadisi or all (the two one-shot "
                              f"lists), got {segment!r}")
    needle = str(name or "").strip().lower() or None
    rows, metas = [], []
    walls = (("borsa",) if segment == "borsa" else
             ("borsadisi",) if segment == "borsadisi" else ("borsa", "borsadisi"))
    for wall in walls:
        r = call_provider(provider, wall, {}, cache=cache, no_cache=no_cache)
        metas.append(r)
        rows += rows_from_upstream(r["data"], wall)
    hits = [r for r in rows if not needle or needle in str(r.get("unvani") or "").lower()]
    return {"rows": hits[:size], "total_matched": len(hits),
            "scanned": {w: sum(1 for r in rows if r["segment"] == w) for w in walls},
            "limit_applied": size,
            "params": {"name": name, "segment": segment},
            "_meta": metas[0], "_metas": metas}
