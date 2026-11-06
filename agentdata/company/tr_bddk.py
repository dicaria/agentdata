"""tr_bddk — BDDK (Banking Regulation and Supervision Agency of Türkiye) authorised-
institution card register, www.bddk.org.tr/Kurulus/Liste/{id} (research volume
tr-bddk-kurulus-recipe, 册 237; face admitted in 0.3.40, probed first-hand 2026-11-04
tmp/probe-tr-bddk-0340/ with the SDK's own polite UA, direct).

TWELVE category pages, each server-rendered with the whole category inline (no paging, no
query surface, keyless): banks 77 / financial-leasing 78 / factoring 79 / financing 80 /
financial-holding 81 / asset-management 82 / foreign-bank representatives 83 / independent
audit firms authorised for banks 84 / valuation firms 85 / credit-rating agencies 86 /
professional associations 87 / savings-financing companies 89 — 640 cards in total (live
2026-11-04: 67 + 86 + 118 + 31 + 3 + 44 + 36 + 73 + 169 + 1 + 3 + 9).

The data is NOT in the table: the page's visible rows are four contact lines, and every card
lives in the 13 data-* attributes of a `<button class="detayliGor">` popup trigger:

  data-ad                  the institution's own name (verbatim, Turkish diacritics)
  data-aciklama            the event history — e.g. the 2005 Ak Uluslararası Bankası → Akbank
                           transfer, or "Kurul 01.12.2017 tarih ve 7612 sayılı Kararı" (the
                           board decision quoted in prose; 158 cards carry one)
  data-isFaaliyette        "1" = in operation, "0" = exited the sector (418 / 222 live)
  data-eftKodu             the EFT routing code — the payments join key (343 cards)
  data-isDijital           "(Dijital Banka)" on the six digital banks, empty elsewhere
  data-telefon / data-faks the site's own phone/fax formatting (kept verbatim)
  data-adres / data-webadresi  address / website
  data-sektordenCikisTarihi the exit date dd.mm.yyyy — "-" is the PLACEHOLDER, not a value
                           (426 cards carry the dash; 214 carry a real date)
  data-kurulKarari         the board decision ("01.10.2009 - 3373" / "01.09.2022/10318" —
                           two date/number separators in the wild), "-" on 79 exited cards
                           and empty on all 418 active ones

Postures this face keeps:
  * the register is a LIFETIME register — the exited cards are the screening surface
    (222 exited cards; 8 of them carry no exit date at all, and 79 carry no decision
    number — honest gaps stay null, never invented);
  * same-name cards are NOT collapsed: 640 cards carry 631 distinct (category, name)
    pairs — 9 groups are same-name rows, and they are NOT all the same record (e.g.
    ZİRAAT FİNANSAL KİRALAMA appears twice, once active and once exited with a decision
    number; VFS twice exited with the same decision written two ways). The SDK keeps
    every card as published and reports the duplicate structure in the census;
  * there is NO registration number, MERSIS key or tax id on the cards — the join to
    SPK-listed entities is by name + domain, weaker than the SPK face (the honest note).

Channel: honest agentdata UA, direct, zero extra headers → 200 on all 12 pages (t1,
2026-11-04). Rate: polite 0.5 rps / burst 2 (its own host www.bddk.org.tr — not shared
with the SPK host). TTL: 24h (the register is rebuilt when BDDK publishes).
"""
import html
import re

from ..errors import SdkError

provider = {
    "id": "tr_bddk",
    "baseUrl": "https://www.bddk.org.tr",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "liste": {"path": "/Kurulus/Liste/{cat_id}", "accept": "text", "timeout": 60.0},
    },
    "ttl": {"liste": 24 * 3600},
}

# slug -> (upstream category id, the page's own heading verbatim, live card count 2026-11-04)
CATEGORIES = {
    "bankalar": (77, "Bankalar", 67),
    "finansal_kiralama": (78, "Finansal Kiralama Şirketleri", 86),
    "faktoring": (79, "Faktoring Şirketleri", 118),
    "finansman": (80, "Finansman Şirketleri", 31),
    "finansal_holding": (81, "Finansal Holding Şirketleri", 3),
    "varlik_yonetim": (82, "Varlık Yönetim Şirketleri", 44),
    "yabanci_temsilcilik": (83, "Yabancı Bankaların Türkiye Temsilcilikleri", 36),
    "bagimsiz_denetim": (84, "Bankalarda Bağımsız Denetim Yapmaya Yetkili Kuruluşlar", 73),
    "degerleme": (85, "Bankalara Değerleme Hizmeti Vermeye Yetkili Kuruluşlar", 169),
    "derecelendirme": (86, "Yetkili Derecelendirme Kuruluşları", 1),
    "meslek_birligi": (87, "Meslek Birlikleri", 3),
    "tasarruf_finansman": (89, "Tasarruf Finansman Şirketleri", 9),
}

# the eleven card attributes (the page's data-toggle/data-target are the modal's, not the card's)
_CARD_FIELDS = ("ad", "aciklama", "eftKodu", "isFaaliyette", "isDijital", "telefon", "faks",
                "adres", "webadresi", "sektordenCikisTarihi", "kurulKarari")

_BUTTON_RE = re.compile(r"<button[^>]*\bdetayliGor\b[^>]*>", re.S)
_ATTR_RE = re.compile(r'data-([\w-]+)="([^"]*)"')
_HEAD_RE = re.compile(r"<h[1-3][^>]*>(.*?)</h[1-3]>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_DECISION_NO_RE = re.compile(r"(\d+)\s*sayılı")
_TRAILING_NO_RE = re.compile(r"(\d+)\s*$")

# Turkish fold for the name filter: dotted/dotless i unify to "i" so a query typed on an ASCII
# keyboard still matches "İŞ BANKASI" (the register's own spelling).
_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c", "Â": "a", "â": "a",
})


def _fold(s):
    """Turkish-insensitive lowercase fold (search only — rows keep their verbatim spelling)."""
    return str(s or "").translate(_FOLD).lower()


def _clean(v):
    """attribute value -> value or None ("" and the upstream's "-" placeholder are empties)."""
    if v is None:
        return None
    s = html.unescape(v).strip()
    if not s or s == "-":
        return None
    return s


def _heading(text):
    """the page's own category heading (verbatim, entities unescaped) — the label of record."""
    m = _HEAD_RE.search(text or "")
    if not m:
        return None
    h = _clean(_TAG_RE.sub("", m.group(1)))
    return h


def rows_from_upstream(text):
    """One category page -> (rows, heading). Every card keeps the register's own wording;
    the only derivations are the booleans (active / digital) and the decision number."""
    heading = _heading(text)
    rows = []
    for tag in _BUTTON_RE.findall(text or ""):
        raw = {}
        for k, v in _ATTR_RE.findall(tag):
            raw.setdefault(k, v)
        name = _clean(raw.get("ad"))
        if not name:
            continue
        description = _clean(raw.get("aciklama"))
        decision = _clean(raw.get("kurulKarari"))
        decision_no = None
        if decision:
            m = _TRAILING_NO_RE.search(decision)
            if m:
                decision_no = int(m.group(1))
        if decision_no is None and description:
            m = _DECISION_NO_RE.search(description)
            if m:
                decision_no = int(m.group(1))
        faaliyet = _clean(raw.get("isFaaliyette"))
        rows.append({
            "name": name,
            "active": True if faaliyet == "1" else (False if faaliyet == "0" else None),
            "exit_date": _clean(raw.get("sektordenCikisTarihi")),
            "decision": decision,
            "decision_no": decision_no,
            "eft_code": _clean(raw.get("eftKodu")),
            "digital": bool(_clean(raw.get("isDijital"))),
            "phone": _clean(raw.get("telefon")),
            "fax": _clean(raw.get("faks")),
            "address": _clean(raw.get("adres")),
            "website": _clean(raw.get("webadresi")),
            "description": description,
        })
    return rows, heading


def institutions_raw(name=None, *, category="all", eft=None, status="all", limit=20,
                     cache=None, no_cache=False):
    """The register -> {rows, total_matched, scanned_rows, census, limit_applied, params,
    _meta, _metas}. category="all" scans the twelve category pages (the whole 640-card
    register); a single category slug fetches just that page. The upstream has NO query
    surface — every filter below is local."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="tr_bddk",
                       detail=f"limit must be 1-100 (local payload wall), got {limit!r}")
    cat = str(category or "all").strip().lower() or "all"
    if cat != "all" and cat not in CATEGORIES:
        raise SdkError("usage_error", provider="tr_bddk",
                       detail=f"category must be 'all' or one of {sorted(CATEGORIES)}, got {category!r}")
    st = str(status or "all").strip().lower() or "all"
    if st not in ("all", "active", "exited"):
        raise SdkError("usage_error", provider="tr_bddk",
                       detail=f"status must be one of ['all', 'active', 'exited'], got {status!r}")
    eft_code = str(eft).strip() if eft not in (None, "") else None
    if eft_code is not None and not eft_code.isdigit():
        raise SdkError("usage_error", provider="tr_bddk",
                       detail=f"eft must be the numeric EFT routing code (data-eftKodu), got {eft!r}")
    needle = _fold(name) or None

    slugs = sorted(CATEGORIES) if cat == "all" else [cat]
    scanned, metas, by_cat, labels = [], [], {}, {}
    for slug in slugs:
        cid, label, _n = CATEGORIES[slug]
        r = call_provider(provider, "liste", {"cat_id": cid}, cache=cache, no_cache=no_cache)
        rows, heading = rows_from_upstream(r["data"])
        labels[slug] = heading or label
        for x in rows:
            x["category"] = slug
            x["category_label"] = heading or label
        by_cat[slug] = len(rows)
        scanned.extend(rows)
        metas.append(r)

    hits = []
    for x in scanned:
        if needle and needle not in _fold(x.get("name")):
            continue
        if eft_code is not None:
            have = str(x.get("eft_code") or "")
            if not (have == eft_code or (have.isdigit() and have.lstrip("0") == eft_code.lstrip("0"))):
                continue
        if st == "active" and x.get("active") is not True:
            continue
        if st == "exited" and x.get("active") is not False:
            continue
        hits.append(x)

    seen = {}
    for x in scanned:
        seen.setdefault((x["category"], _fold(x.get("name"))), 0)
        seen[(x["category"], _fold(x.get("name")))] += 1
    census = {
        "total": len(scanned),
        "by_category": by_cat,
        "categories_scanned": slugs,
        "active": sum(1 for x in scanned if x.get("active") is True),
        "exited": sum(1 for x in scanned if x.get("active") is False),
        "with_eft": sum(1 for x in scanned if x.get("eft_code")),
        "with_exit_date": sum(1 for x in scanned if x.get("exit_date")),
        "with_decision": sum(1 for x in scanned if x.get("decision")),
        "with_description": sum(1 for x in scanned if x.get("description")),
        "with_website": sum(1 for x in scanned if x.get("website")),
        "digital_banks": sum(1 for x in scanned if x.get("digital")),
        "duplicate_name_groups": sum(1 for v in seen.values() if v > 1),
    }
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(scanned),
            "census": census, "limit_applied": size,
            "params": {"name": name or None, "category": cat, "eft": eft_code, "status": st},
            "_meta": metas[0], "_metas": metas}
