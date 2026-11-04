"""cz_ares — Czech ARES economic-entities register (ares.gov.cz; keyless JSON REST).

Two faces (0.3.32; probed 2026-11-03, tmp/probe-company-0332/; research volume
cz-ares-registry, P1 7/7 — the company master register's 16th country):

  * ekonomicke_subjekty — the single-record face. GET
    /ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/<ico>. The record carries the IČO, the
    structured address with the full administrative code ladder (kodAdresnihoMista is the RUIÁN
    address-point code — the address-graph join key), the legal-form code, the VAT key
    (dic = CZ<ico>), the founding and last-update dates, the CZ-NACE 2008 code list and the
    16-register status matrix (seznamRegistraci — ROS/VR/RES/RZP/NRPZS/RPSH/RCNS/SZR/DPH/SKDPH/
    SD/IR/CEU/RS/RED/MONITOR, each register's own state: ACTIVE/HISTORICAL/NONEXISTENT/DISSOLVED).
    The path parameter is validated against the upstream's own regex [0-9]{8}: a malformed IČO
    answers HTTP 400 with a teaching body
    {"kod":"CHYBA_VSTUPU","subKod":"VSTUP_NEVALIDNI_FORMAT_ICO","popis":"… nesplňuje regulární
    výraz [0-9]{8] …"} — the face refuses locally with that regex quoted. An unknown but
    well-formed IČO answers HTTP 404 {"kod":"NENALEZENO","subKod":"VYSTUP_SUBJEKT_NENALEZEN"},
    carried as upstream_not_found (a clean round trip, not an error).
  * ekonomicke_subjekty_vyhledat — the name search. POST
    /ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/vyhledat with the JSON body
    {"obchodniJmeno": "<word>", "pocet": N, "start": M} (the search endpoint is POST-only — GET
    answers 400). The envelope is {"pocetCelkem": <int>, "ekonomickeSubjekty": [record, …]};
    pocetCelkem is the real total, the rows are one page of it.
    **The upstream folds the record names to ASCII but not the query** — a non-ASCII query
    character is dropped and the match set shifts: "ČEZ" answers the 30 "EZ …" names while the
    ASCII "cez" answers the 46 names containing ČEZ (both measured live). The face therefore folds
    the query itself (NFKD + diacritic strip) and echoes both the original and the folded form.
    **The rows do not share one join key**: the `ico` field is present only for the rows whose
    primary source carries the trade-register identifier; an RZP-primary row carries only the ARES
    surrogate icoId ("ARES_00358750") — and that surrogate is REJECTED by the single-record face's
    [0-9]{8} validator (measured 400). icoId equals the IČO only for the ROS-family rows; `ico` is
    the honest join key and it is null for the others. The rows are heterogeneous on the wire
    (three distinct key sets in a 10-row page), so nothing is assumed present.

Channel: plain GET/POST JSON, no CAPTCHA, no key; ARES publishes no rate window -> polite
0.5 rps / burst 2 (the registry-search family posture).
TTL: search 12h (new entities land in the index); record 7d (the register's own
datumAktualizace moves slowly — ČEZ's last update read 2026-10-08 at probe time).
"""
import re
import unicodedata

from ..errors import SdkError

provider = {
    "id": "cz_ares",
    "baseUrl": "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "detail": {"path": "/ekonomicke-subjekty/{ico}", "notFound": [404], "timeout": 40.0},
        "search": {"path": "/ekonomicke-subjekty/vyhledat", "method": "POST",
                   "idempotent": True, "timeout": 40.0},
    },
    "ttl": {"detail": 7 * 24 * 3600, "search": 12 * 3600},
}

# the upstream's own validator, quoted in the usage_error text: the path parameter must be exactly
# eight digits — the ARES surrogate id ("ARES_00358750") is refused by the same validator
_ICO_RE = re.compile(r"^[0-9]{8}$")

_POCET_CAP = 100  # our politeness cap; the upstream publishes no maximum for pocet


def _fold_ascii(s):
    """Fold a query the way the upstream folds the record names: NFKD + combining-mark strip,
    then drop whatever is still non-ASCII (the upstream's own index is ASCII-folded)."""
    folded = unicodedata.normalize("NFKD", s)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return folded.encode("ascii", "ignore").decode("ascii")


def _norm_ico(ico):
    v = str(ico or "").strip()
    if not _ICO_RE.match(v):
        raise SdkError("usage_error", provider="cz_ares",
                       detail="cz_ares_ekonomicke_subjekty requires ico — exactly eight digits "
                              "(the upstream's own validator: [0-9]{8}; anything else answers "
                              "HTTP 400 VSTUP_NEVALIDNI_FORMAT_ICO). The ARES surrogate id "
                              "('ARES_00358750') is NOT an IČO and is refused by the same "
                              "validator")
    return v


def _norm_name(name):
    """-> (original, folded); the folded form is what travels on the wire."""
    raw = str(name or "").strip()
    if not raw:
        raise SdkError("usage_error", provider="cz_ares",
                       detail="cz_ares_ekonomicke_subjekty_vyhledat requires obchodni_jmeno (a name "
                              "word). An empty query is refused locally — upstream it would answer "
                              "the whole register")
    folded = _fold_ascii(raw).strip()
    if not folded:
        raise SdkError("usage_error", provider="cz_ares",
                       detail=f"obchodni_jmeno {raw!r} folds to an empty ASCII query — the upstream "
                              "index is ASCII-folded, so a non-Latin name cannot be searched")
    return raw, folded


def _norm_paging(pocet, start):
    p = 10 if pocet in (None, "") else int(pocet)
    s = 0 if start in (None, "") else int(start)
    if p < 1 or p > _POCET_CAP:
        raise SdkError("usage_error", provider="cz_ares",
                       detail=f"pocet must be 1-{_POCET_CAP} (our politeness cap; the upstream "
                              f"publishes no maximum), got {pocet!r}")
    if s < 0:
        raise SdkError("usage_error", provider="cz_ares",
                       detail=f"start must be a non-negative row offset, got {start!r}")
    return p, s


def _map_sources(raw):
    """dalsiUdaje = the per-register variants of the same subject (one entry per source:
    res / ros / rzp / vr …), each with its own name list, address list, legal form and, for the
    court source, the file number (spisovaZnacka)."""
    out = []
    for u in raw.get("dalsiUdaje") or []:
        if not isinstance(u, dict):
            continue
        names = [n.get("obchodniJmeno") for n in (u.get("obchodniJmeno") or [])
                 if isinstance(n, dict) and n.get("obchodniJmeno")]
        addrs = [a.get("sidlo") for a in (u.get("sidlo") or [])
                 if isinstance(a, dict) and a.get("sidlo")]
        out.append({
            "source": u.get("datovyZdroj") or None,
            "legal_form": u.get("pravniForma") or None,
            "legal_form_ros": u.get("pravniFormaRos") or None,
            "file_number": u.get("spisovaZnacka") or None,
            "names": names,
            "addresses": addrs,
        })
    return out


def _map_row(raw):
    """One search/detail record -> the flat row. Nothing is invented: a field the upstream did not
    send stays null (the rows are heterogeneous on the wire — `ico` is missing on the RZP-primary
    rows)."""
    addr = raw.get("sidlo") or {}
    return {
        "ico": raw.get("ico") or None,
        "ico_id": raw.get("icoId") or None,
        "name": raw.get("obchodniJmeno") or None,
        "legal_form": raw.get("pravniForma") or None,
        "legal_form_ros": raw.get("pravniFormaRos") or None,
        "vat": raw.get("dic") or None,
        "tax_office": raw.get("financniUrad") or None,
        "primary_source": raw.get("primarniZdroj") or None,
        "founded_at": raw.get("datumVzniku") or None,
        "updated_at": raw.get("datumAktualizace") or None,
        "address": addr,
        "address_text": addr.get("textovaAdresa") or None,
        "delivery_address": raw.get("adresaDorucovaci") or None,
        "nace_2008": list(raw.get("czNace2008") or []),
        "nace": list(raw.get("czNace") or []),
        "register_status": dict(raw.get("seznamRegistraci") or {}),
        "sources": _map_sources(raw),
    }


def detail_raw(ico, *, cache=None, no_cache=False):
    """-> the record dict (flat row shape) + params + _meta."""
    from ..transport import call_provider

    v = _norm_ico(ico)
    r = call_provider(provider, "detail", {"ico": v}, cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    row = _map_row(doc)
    row["ico"] = doc.get("ico") or v
    row["sub_register_szr"] = doc.get("subRegistrSzr") or None
    return {**row, "params": {"ico": v}, "_meta": r}


def vyhledat_raw(obchodni_jmeno, *, pocet=None, start=None, cache=None, no_cache=False):
    """-> {total, count, rows, pocet, start, params, _meta}; rows are flat records."""
    from ..transport import call_provider

    raw_name, folded = _norm_name(obchodni_jmeno)
    p, s = _norm_paging(pocet, start)
    r = call_provider(provider, "search",
                      {"obchodniJmeno": folded, "pocet": p, "start": s},
                      cache=cache, no_cache=no_cache)
    doc = r["data"] or {}
    rows = [_map_row(x) for x in (doc.get("ekonomickeSubjekty") or []) if isinstance(x, dict)]
    total = doc.get("pocetCelkem")
    return {
        "total": int(total) if isinstance(total, (int, float)) else None,
        "count": len(rows),
        "rows": rows,
        "pocet": p,
        "start": s,
        "params": {"obchodniJmeno": folded, "pocet": p, "start": s},
        "query_name_original": raw_name,
        "_meta": r,
    }
