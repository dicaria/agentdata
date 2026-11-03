"""ca_sema — Canada SEMA sanctions listings provider (Global Affairs Canada sema-lmes.xml; keyless).

legal sanctions-roster face (0.3.21; admitted 2026-11-02, probed tmp/probe-debar-0321). Shape measured 2026-11-02:
GET /world-monde/assets/office_docs/international_relations-relations_internationales/sanctions/sema-lmes.xml
  → <data-set><record>… — the Consolidated Canadian Autonomous Sanctions List under the Special Economic
Measures Act, **5,708 live records** (persons 3,526 with GivenName / entities 2,181 via EntityOrShip — of which
**731 ships carrying an IMO number**; the census-era 11,328 counted cumulative history). Tags are **bilingual
paired names** (Country-Pays, LastName-NomDeFamille, GivenName-Prenom, Aliases-Alias, DateOfBirthOrShipBuildDate-…,
EntityOrShip-EntiteOuNavire, TitleOrShipType-…, ShipIMONumber-…, Schedule-Annexe, Item-NumeroDarticle,
DateOfListing-…); values are bilingual too ("Syria / Syrie", ship types "General Cargo/Multi Purpose | Cargo
classique/navire polyvalent" — the **| separates the language halves**). Aliases are semicolon-delimited where
multiple (222 records). Schedule references the SEMA schedule ("1, Part 1" 1,945 / "1, Part 2" 1,062 / "Part 1"
742 / "1.1" 731…; 329 records carry none). Listing dates run 2008→2026 (2026 already at 518).
**Accept content-negotiation gate** (pinned 2026-11-02): the asset answers 406 to Accept: application/json —
the op overrides Accept to text/xml (ext 8); the plain agentdata UA passes.
Screening = local full-register scan (upstream has no query surface), cache 24h.
TTL: 24h; polite tier 0.2 rps (single-file face, 2.9MB).
"""
import xml.etree.ElementTree as ET

from ..errors import SdkError

provider = {
    "id": "ca_sema",
    "baseUrl": "https://www.international.gc.ca",
    "rate": {"rps": 0.2, "burst": 1},
    "ops": {
        "listings": {
            "path": "/world-monde/assets/office_docs/international_relations-relations_internationales/sanctions/sema-lmes.xml",
            "accept": "text",  # XML surface — the raw text comes back and this module parses it
            "timeoutMs": 120000,  # 2.9MB XML
        },
    },
    "ttl": {"listings": 24 * 3600},
}

# Accept content-negotiation gate (pinned 2026-11-02): application/json → 406 Not Acceptable;
# text/xml (and */*) → 206/200 — ext-8 override over the transport's default JSON Accept
_XML_ACCEPT = {"Accept": "text/xml, */*"}

# bilingual paired tag names (upstream verbatim — the EN/FR halves live in one element name)
_T = {
    "country": "Country-Pays",
    "last_name": "LastName-NomDeFamille",
    "given_name": "GivenName-Prenom",
    "aliases": "Aliases-Alias",
    "dob_or_ship_build": "DateOfBirthOrShipBuildDate-DateDeNaissanceOuDateDeConstructionDuNavire",
    "entity_or_ship": "EntityOrShip-EntiteOuNavire",
    "title_or_ship_type": "TitleOrShipType-TitreOuTypeDeNavire",
    "ship_imo": "ShipIMONumber-NumeroOMIDuNavire",
    "schedule": "Schedule-Annexe",
    "item": "Item-NumeroDarticle",
    "date_of_listing": "DateOfListing-DateDinscription",
}


def _txt(rec, key):
    el = rec.find(_T[key])
    return (el.text or "").strip() if el is not None and el.text else None


def rows_from_xml(text):
    """XML raw text → sanction-listing rows (pure function, offline-testable). Each record becomes
    {kind, name, matched faces…}: kind = ship (IMO present) / entity (EntityOrShip) / person (GivenName×LastName);
    name = the assembled display form ("Khazalbek Bakhtibekovich Atabekov" for persons, the EntityOrShip value
    otherwise); aliases = semicolon-split; every other field verbatim bilingual."""
    if not text:
        return []
    root = ET.fromstring(text)
    rows = []
    for rec in root.findall("record"):
        imo = _txt(rec, "ship_imo")
        entity = _txt(rec, "entity_or_ship")
        given, last = _txt(rec, "given_name"), _txt(rec, "last_name")
        if imo:
            kind = "ship"
        elif entity:
            kind = "entity"
        else:
            kind = "person"
        if kind == "person":
            name = " ".join(x for x in (given, last) if x) or None
        else:
            name = entity
        aliases = []
        for el in rec.findall(_T["aliases"]):
            aliases.extend(a.strip() for a in (el.text or "").split(";") if a.strip())
        rows.append({
            "kind": kind,
            "name": name,
            "aliases": aliases,
            "country": _txt(rec, "country"),            # bilingual verbatim ("Syria / Syrie")
            "dob_or_ship_build": _txt(rec, "dob_or_ship_build"),
            "title_or_ship_type": _txt(rec, "title_or_ship_type"),  # person title OR ship type (bilingual)
            "ship_imo": imo,                             # the join key onto shipping rosters (THETIS-MRV family)
            "schedule": _txt(rec, "schedule"),
            "item": _txt(rec, "item"),
            "date_of_listing": _txt(rec, "date_of_listing"),
        })
    return rows


def filter_rows(rows, name=None, country=None):
    """Local register scan (pure function). name: contains (case-insensitive) over name **and** aliases
    (matched_on echoes the hit face); country: contains over the bilingual country cell ("Syria" and "Syrie"
    both hit the "Syria / Syrie" row)."""
    needle = str(name or "").strip().lower() or None
    cn_needle = str(country or "").strip().lower() or None
    hits = []
    for r in rows:
        if cn_needle and cn_needle not in str(r.get("country") or "").lower():
            continue
        if not needle:
            hits.append({**r, "matched_on": None})
            continue
        if needle in str(r.get("name") or "").lower():
            hits.append({**r, "matched_on": "name"})
            continue
        alias = next((a for a in r.get("aliases") or [] if needle in a.lower()), None)
        if alias:
            hits.append({**r, "matched_on": "alias"})
    return hits


def sanctions_raw(name=None, *, country=None, limit=20, cache=None, no_cache=False):
    """Full-register scan (pulls the whole XML, caches 24h, then scans locally)
    → {rows, total_matched, scanned_rows, limit_applied, params, _meta}.

    name = contains over name + aliases; country = contains over the bilingual country cell.
    No filter → enumerate from the register head."""
    from ..transport import call_provider

    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 100:
        raise SdkError("usage_error", provider="ca_sema",
                       detail=f"limit must be 1-100 (local payload wall), got '{limit}'")
    r = call_provider(provider, "listings", {}, cache=cache, no_cache=no_cache,
                      extra_headers=_XML_ACCEPT)
    rows = rows_from_xml(r["data"])
    hits = filter_rows(rows, name=name, country=country)
    return {"rows": hits[:size], "total_matched": len(hits), "scanned_rows": len(rows),
            "limit_applied": size,
            "params": {"name": name, "country": country}, "_meta": r}
