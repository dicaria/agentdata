"""fr_court — French administrative courts judgment monthly archives
(opendata.justice-administrative.fr, keyless).

FR legal face (0.3.61; admitted from the research booklet judgments-corpus 册,
re-probed live 2026-11-16):

CONTRACT:
  1. judgments — the monthly archive zip → every judgment's metadata rows:
     GET /DCE/{yyyy}/{mm}/CE_{yyyymm}.zip (Conseil d'État) or /DCA/{yyyy}/{mm}/CAA_{yyyymm}.zip
     (cours administratives d'appel). One XML per judgment inside; each row carries
     ecli (CE only — CAA archives carry NO Numero_ECLI element, measured 0/24 sample),
     dossier_number, jurisdiction_code/name, lecture_date, decision/appeal type,
     publication_code, solution (Rejet / Annulation … — the outcome, verbatim),
     audience date/role/formation, avocat_requerant.
  2. judgment — one judgment by doc id (the archive file stem, e.g. DCE_503183_20261001
     or DCA_20BX01837_20261007) or by ECLI (CE: ECLI:FR:CECHR:2026:503183.20261001 —
     the dossier+date tail maps onto the same stem) → the full row plus texte_integral
     (the judgment body, upstream HTML).

LIVE LAWS (measured 2026-11-16, tmp/probe-e3/):
  - Accept wall: the host 406s the transport's default Accept: application/json — and
    even application/zip — but serves */* (measured all four shapes the same minute);
    the op rides extra_headers {"Accept": "*/*"} for every archive fetch.
  - the directory paths work even though the data.gouv dataset page lags years behind
    (a dead-looking registry, not a dead source — same family as the BR CEIS 302
    direct-URL clan): CE_202610.zip 2.7MB/791 judgments (updated 2026-11-11),
    CAA_202610.zip 11.3MB/2,340 judgments (updated 2026-11-14); history from 2021-06.
  - the XML has no namespace despite the xsi:noNamespaceSchemaLocation attribute — plain
    tag slicing works; Texte_Integral embeds HTML (<br/> paragraphs) verbatim.
  - CAA zips are ~4× the CE size — the archive face parses metadata only; the full text
    rides the single-judgment face.

Politeness: 0.2/2, concurrency 1 (11MB zips — one at a time), TTL 72h (monthly cadence).
"""
import re
import zipfile

from ..errors import SdkError

provider = {
    "id": "fr_court",
    "baseUrl": "https://opendata.justice-administrative.fr",
    "rate": {"rps": 0.2, "burst": 2},
    "concurrency": 1,
    "ops": {
        "ce_archive": {"path": "/DCE/{year}/{mm}/CE_{ym}.zip", "accept": "bytes", "timeout": 180.0},
        "caa_archive": {"path": "/DCA/{year}/{mm}/CAA_{ym}.zip", "accept": "bytes", "timeout": 180.0},
    },
    "ttl": {"ce_archive": 72 * 3600, "caa_archive": 72 * 3600},
}

_COURTS = {"ce": "ce_archive", "caa": "caa_archive"}
_TAG = lambda name: re.compile(rf"<{name}>(.*?)</{name}>", re.S)


def _text(xml, name):
    m = _TAG(name).search(xml)
    return m.group(1).strip() if m else None


def parse_xml(xml, name=None):
    """One judgment XML → the metadata row (texte_integral excluded)."""
    ecli = _text(xml, "Numero_ECLI")
    return {
        "ecli": ecli,
        "doc_id": (name[:-4] if name and name.lower().endswith(".xml") else
                   _text(xml, "Identification")),
        "dossier_number": _text(xml, "Numero_Dossier"),
        "jurisdiction_code": _text(xml, "Code_Juridiction"),
        "jurisdiction_name": _text(xml, "Nom_Juridiction"),
        "lecture_date": _text(xml, "Date_Lecture"),
        "avocat_requerant": _text(xml, "Avocat_Requerant"),
        "decision_type": _text(xml, "Type_Decision"),
        "appeal_type": _text(xml, "Type_Recours"),
        "publication_code": _text(xml, "Code_Publication"),
        "solution": _text(xml, "Solution"),
        "audience_date": _text(xml, "Date_Audience"),
        "role_number": _text(xml, "Numero_Role"),
        "formation": _text(xml, "Formation_Jugement"),
        "date_maj": _text(xml, "Date_Mise_Jour"),
    }


def _fetch_zip(court, year, month, *, cache=None, no_cache=False):
    from ..transport import call_provider

    op = _COURTS[court]
    ym = f"{year:04d}{month:02d}"
    params = {"year": f"{year:04d}", "mm": f"{month:02d}", "ym": ym}
    # Accept wall (live 2026-11-16): the host 406s the transport's default
    # Accept: application/json — and even application/zip — but serves */*.
    r = call_provider(provider, op, params, cache=cache, no_cache=no_cache,
                      extra_headers={"Accept": "*/*"})
    try:
        return zipfile.ZipFile(io_bytes(r["data"])), ym, r
    except zipfile.BadZipFile:
        raise SdkError("upstream_unavailable", provider="fr_court",
                       detail=f"the {court.upper()} {ym} archive did not answer a zip "
                              f"(no such month yet?)")


def io_bytes(latin1_body):
    """The transport's bytes channel returns the body as a latin-1 string — recover it."""
    return __import__("io").BytesIO(latin1_body.encode("latin-1"))


def judgments_raw(year=None, month=None, court="ce", *, cache=None, no_cache=False):
    """→ {rows[], total, court, year, month, params, _meta}. One court-month archive."""
    try:
        year, month = int(year), int(month)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="fr_court",
                       detail="year and month are required (e.g. year=2026, month=10)")
    if court not in _COURTS:
        raise SdkError("usage_error", provider="fr_court",
                       detail=f"court must be one of {sorted(_COURTS)} (ce=Conseil d'État, "
                              f"caa=cours administratives d'appel), got {court!r}")
    zf, ym, r = _fetch_zip(court, year, month, cache=cache, no_cache=no_cache)
    rows = []
    for name in sorted(n for n in zf.namelist() if n.lower().endswith(".xml")):
        try:
            rows.append(parse_xml(zf.read(name).decode("utf-8", "replace"), name))
        except Exception:
            continue
    return {
        "rows": rows,
        "total": len(rows),
        "court": court,
        "year": year,
        "month": month,
        "archive": f"{'CE' if court == 'ce' else 'CAA'}_{ym}.zip",
        "params": {"court": court, "year": year, "month": month},
        "_meta": r,
    }


_STEM = re.compile(r"^(DCE|DCA)_[A-Za-z0-9]+_(\d{8})$")
_ECLI = re.compile(r"^ECLI:FR:(CE|CAA)[A-Z]*:(\d{4}):([A-Za-z0-9]+)\.(\d{8})$")


def judgment_raw(doc_id=None, *, cache=None, no_cache=False):
    """→ {row…, texte_integral, params, _meta}. One judgment, full text.

    doc_id takes the archive stem (DCE_503183_20261001 / DCA_20BX01837_20261007) or a
    CE ECLI (ECLI:FR:CECHR:2026:503183.20261001 — the dossier+date tail maps to the stem).
    """
    key = str(doc_id or "").strip()
    if not key:
        raise SdkError("usage_error", provider="fr_court", detail="doc_id is required")
    court = year = month = None
    m = _ECLI.match(key)
    if m:
        court = m.group(1).lower()
        year, month = int(m.group(2)), int(m.group(4)[4:6])
        key = f"D{court.upper()}_{m.group(3)}_{m.group(4)}"
    else:
        m = _STEM.match(key)
        if m:
            court = {"DCE": "ce", "DCA": "caa"}[m.group(1)]
            year, month = int(m.group(2)[:4]), int(m.group(2)[4:6])
    if court is None:
        raise SdkError("usage_error", provider="fr_court",
                       detail=f"doc_id must be an archive stem (DCE_…/DCA_…) or a CE ECLI, got {key!r}")
    zf, _ym, r = _fetch_zip(court, year, month, cache=cache, no_cache=no_cache)
    target = f"{key}.xml"
    if target not in zf.namelist():
        raise SdkError("not_found", provider="fr_court",
                       detail=f"{key} is not in the {court.upper()} {year}-{month:02d} archive")
    xml = zf.read(target).decode("utf-8", "replace")
    row = parse_xml(xml, target)
    row["texte_integral"] = _text(xml, "Texte_Integral")
    row["params"] = {"doc_id": key}
    row["_meta"] = r
    return row
