"""es_oepm — OEPM industrial-property gazette index (Boletín Oficial de la Propiedad
Industrial, sede.oepm.gob.es/apibopiweb; keyless plain SDK UA; the company domain's IP
face No. 2 after jp_jplatpat — trademarks/patents are company-hard-keyed surfaces).

One face (0.3.57; probed 2026-11-12, tmp/probe-sdk-0357/ — oepm-capitulosTomo1/2.json +
oepm-modalidadesTomo1/2.json + oepm-publicacionesBopiTomoYFecha_1_04-11-2026.json + two
empty-body negatives 08-07-11-2026 (weekend) and 04-01-1995 (pre-digital era); research
volume 领域数据源调研 册 258):

  * bopi — one BOPI issue's publication metadata: GET /apibopiweb/publicacionesBopiTomoY
    Fecha/{tomo}/{DD-MM-YYYY}. The payload is small and half-empty BY DESIGN: {id: null,
    fechaPublicacion: null, idPdfUcm / idXmlUcm / idHtmlUcm: the UCM artifact keys,
    tomo}. id and fechaPublicacion arrive null on every measured issue — the UCM ids are
    the real keys (the PDF/XML/HTML documents of the whole issue, a second surface out of
    this face's scope — the kr_law second-surface ruling). idTxtUcm arrives null too on
    the measured issue.
  * **the empty-body negative is a CHANNEL WALL**: a non-publication day (weekend) AND a
    pre-digital date (1995-01-04) both answer HTTP 200 with a ZERO-BYTE body — measured
    2026-11-12. The op declares accept:'text' so the empty body passes the transport as
    "" (the default JSON channel would flag json=None as a suspected WAF — the kr_law
    accept-text posture); the provider maps "" to published=false, never an error.
  * the tomo structure rides along as reference (two tiny taxonomy calls, cached long):
    capitulosTomo{1,2} = the chapter list ([{"13": "1. MARCAS"}, …] — single-key dicts,
    15 items T1 / 16 T2); modalidadesTomo{1,2} = the modality code map ({"1": "M -
    Marca", …} — 14 codes T1 / 8 T2, incl. F transfer / K rename / L license since
    2011). Tomo 1 = marcas (trademarks), tomo 2 = the rest (patents, utility models,
    designs, …) — the face asks for tomo explicitly.
  * NO issue-content surface exists on this API — which publications appeared in the
    issue (by applicant/mark) lives in the UCM artifacts, out of scope. The face is the
    issue index + the decoding dictionaries.

Channel: plain GET, no key, no CAPTCHA, no published rate window → polite 0.5 rps /
burst 2. TTL: issue 24h (daily publication cadence), taxonomies 7d (the chapter/modality
codes are structural). Dates travel DD-MM-YYYY upstream (converted from --date
YYYY-MM-DD locally).
"""
import json
from datetime import date as _date

from ..errors import SdkError
from ..transport import call_provider, now_iso

provider = {
    "id": "es_oepm",
    "baseUrl": "https://sede.oepm.gob.es",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # accept:'text' — a non-publication day answers 200 with a ZERO-BYTE body (weekend
        # AND pre-digital dates both measured); "" is the payload, parsed here. The real
        # JSON issues parse at the provider layer.
        "issue": {"path": "/apibopiweb/publicacionesBopiTomoYFecha/{tomo}/{ddmmyyyy}",
                  "accept": "text", "timeout": 30.0},
        "capitulos_tomo1": {"path": "/apibopiweb/capitulosTomo1", "timeout": 30.0},
        "capitulos_tomo2": {"path": "/apibopiweb/capitulosTomo2", "timeout": 30.0},
        "modalidades_tomo1": {"path": "/apibopiweb/modalidadesTomo1", "timeout": 30.0},
        "modalidades_tomo2": {"path": "/apibopiweb/modalidadesTomo2", "timeout": 30.0},
    },
    "ttl": {"issue": 24 * 3600, "capitulos_tomo1": 7 * 24 * 3600,
            "capitulos_tomo2": 7 * 24 * 3600, "modalidades_tomo1": 7 * 24 * 3600,
            "modalidades_tomo2": 7 * 24 * 3600},
}

_DATE_RE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_capitulos(data):
    """capitulosTomo{N} → an ordered chapter list — pure. Upstream shape: a LIST of
    single-key dicts [{"13": "1. MARCAS"}, …] (the map key is the chapter code)."""
    out = []
    for entry in data if isinstance(data, list) else []:
        if isinstance(entry, dict):
            for code, nombre in entry.items():
                out.append({"code": str(code), "nombre": nombre})
                break  # single-key dicts by contract; a drifted shape takes the first key
    return out


def parse_modalidades(data):
    """modalidadesTomo{N} → the modality code map (code → name) — pure, verbatim."""
    return {str(k): v for k, v in (data or {}).items()} if isinstance(data, dict) else {}


def bopi_raw(tomo, date, cache=None, no_cache=False):
    """one BOPI issue's publication metadata + the tomo's chapter/modality reference
    lists. A non-publication day (weekend / pre-digital date) answers published=false —
    the empty 200 body IS the upstream's no-issue signal, never an error."""
    try:
        tomo = int(tomo)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="es_oepm",
                       detail="--tomo must be 1 (marcas / trademarks) or 2 (patents, utility models, designs, …)")
    if tomo not in (1, 2):
        raise SdkError("usage_error", provider="es_oepm",
                       detail=f"--tomo {tomo} is outside the register (1 = marcas, 2 = the rest)")
    if not _DATE_RE.match(str(date or "")):
        raise SdkError("usage_error", provider="es_oepm",
                       detail="--date must be YYYY-MM-DD (zero-padded), e.g. 2026-11-04")
    y, m, d = str(date).split("-")
    try:
        _date(int(y), int(m), int(d))
    except ValueError:
        raise SdkError("usage_error", provider="es_oepm",
                       detail=f"--date {date} is not a real calendar date")
    if str(date) > _date.today().isoformat():
        raise SdkError("usage_error", provider="es_oepm",
                       detail=(f"--date {date} is in the future — the gazette has not reached that "
                               "day; use a date up to today (BOPI publishes weekdays)"))
    ddmmyyyy = f"{d}-{m}-{y}"
    res = call_provider(provider, "issue", {"tomo": tomo, "ddmmyyyy": ddmmyyyy},
                        cache=cache, no_cache=no_cache)
    body = (res["data"] or "").strip() if isinstance(res["data"], str) else res["data"]
    reference = {"capitulos": parse_capitulos(call_provider(
        provider, f"capitulos_tomo{tomo}", {}, cache=cache, no_cache=no_cache)["data"]),
        "modalidades": parse_modalidades(call_provider(
            provider, f"modalidades_tomo{tomo}", {}, cache=cache, no_cache=no_cache)["data"])}
    params = {"tomo": tomo, "date": str(date)}
    if not body:
        # weekend / gazette holiday / pre-digital era — the upstream's own no-issue signal
        # (200 + zero-byte body, measured 2026-11-12 on both a Saturday and 1995-01-04)
        return {"date": str(date), "tomo": tomo, "published": False, "issue": None,
                "reference": reference, "params": params,
                "_meta": {"status": 200, "fetched_at": res["fetched_at"]}}
    try:
        issue = json.loads(body)
    except ValueError:
        raise SdkError("upstream_unavailable", provider="es_oepm",
                       detail=(f"issue {tomo}/{ddmmyyyy} answered a non-JSON body "
                               f"({body[:80]!r}) — the channel contract drifted; re-probe"))
    return {"date": str(date), "tomo": tomo, "published": True, "issue": issue,
            "reference": reference, "params": params, "_meta": res}
