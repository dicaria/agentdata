"""de_inso — German federal insolvency announcements (Insolvenzbekanntmachungen),
neu.insolvenzbekanntmachungen.de/ap/suche.jsf (research volume de-insolvenzbekanntmachungen,
册 225; faces admitted in 0.3.41, probed first-hand 2026-11-04 tmp/probe-de-insolvency-0341/
with the SDK's own polite UA, direct).

THE PORTAL IS A JAVASX FACES (Jakarta Faces) POSTBACK APP, not a query API. The chain is:
GET /ap/suche.jsf -> (ViewState token + the form action) -> POST the form urlencoded ->
the result page. Three measured facts shape the implementation:

  * the form action carries the session: "/ap/suche.jsf;jsessionid=…". The SDK transport keeps
    NO cookie jar, so the session travels in that path segment — the action must be echoed
    verbatim (probed with and without a cookie jar: identical rows, 1,077 for NW 2026-11-02);
  * the ViewState is a one-shot postback token: a stale one silently re-renders the EMPTY search
    form instead of the results — the GET+POST pair is therefore one atomic chain, always
    re-bootstrapped (no session reuse across queries);
  * the POST must carry Origin + Referer (the search face survives without them; the row-level
    detail action does not — the detail popup is out of scope for this face, see below).

THE ROW GRAIN IS THE ANNOUNCEMENT (the event), NOT THE CASE. One case can carry several
announcements on one day ("255 IK 107/25" three times on NW 2026-11-02; "70g IN 97/21" six
times on 2026-11-03) — the SDK never dedupes by case number.

WHAT A ROW CARRIES (six cells, the register's own wording):
  date        "02.11.2026"            Veröffentlichungsdatum
  case        "504 IN 277/26"         aktuelles Aktenzeichen
  court       "Düsseldorf"             Insolvenzgericht
  debtor      "AB Bau-Management GmbH" Name, Vorname / Bezeichnung ("Nachname, Vorname" for people)
  seat        "Düsseldorf"             Sitz / Wohnsitz
  register    "Düsseldorf, HRB 101036" Register — the hard join key; present on ~9% of the rows
              (98 of 1,077 on NW 2026-11-02), empty elsewhere (honest gap, never invented)

THE REGISTER CELL is "<court>, <TYPE> <number>" with TYPE in HRA/HRB/VR/PR/GNR/GSR — that is the
join key against the commercial registers (the "HRB point lookup" face). A register entry needs
court + type + number all three: the upstream rejects a half-filled one ("Der Registereintrag
muss eindeutig belegt sein", measured).

THE AKTENZEICHEN is a quartet "<Abteilung> <AR|IE|IK|IN> <lfd>/<Jahr>" ("504 IN 277/26"). The
Abteilung may be absent ("IN 261/24") — that subset is selected by the upstream's "ohne
Abteilung" checkbox (measured: sign=IN, lfd=261, Jahr=24 + the checkbox = 1 hit; without the
checkbox = 0). The Abteilung token can carry a suffix letter ("3 f IK 484/26") and the number
can carry a trailing decoration ("810 IN 1046/26 K-33-") — both are kept verbatim.

FILTER SEMANTICS (measured, all against the live portal):
  * the name field matches the SURNAME / company designation EXACTLY, case-insensitively:
    "af-media gmbh" -> 1 hit, "AF-Media" -> 0 hits, "AF-Media Gmb" -> 0 hits, "Ali" -> 0 hits.
    A partial token never matches; the first name has its own field (litx_vorname);
  * the seat field (litx_sitzWohnsitz) narrows (name "Ali Moussa" + seat "Hamburg" -> 0 hits
    where the unfiltered name query returns 2);
  * the Insolvenzgericht select is INERT — asking for R3101 (Aachen) returned rows from
    Wuppertal, Gera, Charlottenburg, Darmstadt, Dortmund, Osterode, Frankfurt and Potsdam
    (measured, 32 rows, not one of them Aachen). The face therefore does NOT expose it;
  * the wildcard select ("*" / "+" / "%" / "#") changes the matching operator but never makes a
    partial token match ("AF-Media" -> 0 hits under all four; the full string -> 1 hit under
    all four). The face keeps the default "*" and does not expose it.

THE UPSTREAM REFUSES WIDE WINDOWS: "Ihre Suche ergab zu viele Treffer. Die maximale Trefferzahl
beträgt 1000. Bitte schränken Sie Ihre Suche ein." A single state-day still renders above the
stated cap (NW 2026-11-02 = 1,077 rows; 2026-11-03 = 1,063) while a two-day state window
(~2,140) and an 8-day Berlin window are both refused — so the working grain is ONE STATE x ONE
DAY. The refusal is NOT an error here: the SDK returns it as a structured state with the
upstream's verbatim German sentence plus a narrowing hint.

KNOWN BOUNDARY — the announcement full text is NOT in this face. The row's zoom button opens a
popup whose text comes from the session's Veröffentlichungstext; reproducing it needs a real
browser click (measured 2026-11-04: a plain form post re-renders the list, an AJAX partial
response carries an empty ihd_text, and GET /ap/text.xhtml stays empty). This face therefore
returns the six announcement cells only — the full text is a second-phase (browser-rendered)
surface.

Channel: honest agentdata UA, direct, zero extra headers on the GET, Origin+Referer on the POST.
Rate: polite 0.5 rps / burst 2 (one GET + one POST per query). TTL: 12h for a window that
closed before today, 1h for a window that includes today (announcements are published during
the working day).
"""
import html
import re
from datetime import datetime, timedelta, timezone

from ..errors import SdkError

provider = {
    "id": "de_inso",
    "baseUrl": "https://neu.insolvenzbekanntmachungen.de",
    "rate": {"rps": 0.5, "burst": 2},
    "concurrency": 1,
    "ops": {
        # the search form (ViewState + the action that carries the session id)
        "search_page": {"path": "/ap/suche.jsf", "accept": "text", "timeout": 40.0},
        # the postback: the form fields urlencoded, the action (with ;jsessionid=) as the path
        "search_post": {"path": "{action}", "method": "POST", "urlencoded": True,
                        "accept": "text", "timeout": 120.0, "idempotent": True,
                        "path_safe": "/;=:&?%"},
    },
    "ttl": {"search_post": 12 * 3600},
}

# the portal went online in the first week of January 2022 (the oldest published announcement
# measured: 2022-01-03, Nordrhein-Westfalen) — a window that starts earlier finds nothing.
FIRST_ONLINE = "2022-01-03"

# the sixteen states (upstream codelist scl_bundesland)
STATES = {
    "BW": "Baden-Württemberg", "BY": "Bayern", "BE": "Berlin", "BB": "Brandenburg",
    "HB": "Bremen", "HH": "Hamburg", "HE": "Hessen", "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen", "NW": "Nordrhein-Westfalen", "RP": "Rheinland-Pfalz",
    "SL": "Saarland", "SN": "Sachsen", "ST": "Sachsen-Anhalt", "SH": "Schleswig-Holstein",
    "TH": "Thüringen",
}

# the Gegenstand codes (upstream codelist): what kind of procedural step the announcement is
SUBJECTS = {
    "ABWMASS": "Abweisungen mangels Masse",
    "ENT_AUF_VERF": "Entscheidungen nach Aufhebung des Verfahrens",
    "ENT_RSB": "Entscheidungen im Restschuldbefreiungsverfahren",
    "ENT_VERF": "Entscheidungen im Verfahren",
    "EROEFF": "Eröffnungen",
    "INSO_PLAN": "Überwachte Insolvenzpläne",
    "SICHMASS": "Sicherungsmaßnahmen",
    "SONST": "Sonstiges",
    "VERTVERZ": "Verteilungsverzeichnisse (§ 188 InsO) d. Verw./Treuh.",
}

# the register types (upstream codelist som_registerart)
REGISTER_TYPES = {
    "GNR": "GnR", "GSR": "GsR", "HRA": "HRA", "HRB": "HRB", "PR": "PR", "VR": "VR",
}

# the case-number signs (upstream codelist som_registerzeichen)
AZ_SIGNS = ("AR", "IE", "IK", "IN")

# the 149 register courts (upstream codelist som_registergericht) — the code the register
# lookup needs, keyed by code. The court NAME is the label.
REGISTER_COURTS = {
    "R3101": "Aachen", "Y1201": "Altenburg", "D3101V": "Amberg",
    "D3201V": "Ansbach", "Y1101": "Apolda", "R1901": "Arnsberg",
    "Y1102": "Arnstadt", "Y1303": "Arnstadt - Zweigstelle Ilmenau", "D4102V": "Aschaffenburg",
    "D2102V": "Augsburg", "P3101": "Aurich", "M1305": "Bad Hersfeld",
    "M1202": "Bad Homburg v.d. Höhe", "T2101V": "Bad Kreuznach", "R2108": "Bad Oeynhausen",
    "Y1301": "Bad Salzungen", "D4201V": "Bamberg", "D4301V": "Bayreuth",
    "F1103R": "Berlin", "R2101": "Bielefeld", "R2201": "Bochum",
    "R3201": "Bonn", "P1103": "Braunschweig", "H1101": "Bremen",
    "U1206": "Chemnitz", "D4401V": "Coburg", "R2707": "Coesfeld",
    "G1103": "Cottbus", "M1103": "Darmstadt", "D2201V": "Deggendorf",
    "R2402": "Dortmund", "U1104": "Dresden", "R1202": "Duisburg",
    "R3103": "Düren", "R1101": "Düsseldorf", "Y1105": "Eisenach",
    "Y1106": "Erfurt", "M1602": "Eschwege", "R2503": "Essen",
    "X1112R": "Flensburg", "G1207": "Frankfurt (Oder)", "M1201": "Frankfurt am Main",
    "B8536": "Freiburg im Breisgau", "M1405": "Friedberg (Hessen)", "M1603": "Fritzlar",
    "M1301": "Fulda", "D3304V": "Fürth", "R2507": "Gelsenkirchen",
    "Y1203": "Gera", "M1406": "Gießen", "Y1108": "Gotha",
    "Y1205": "Greiz", "P2204": "Göttingen", "R2103": "Gütersloh",
    "R2602": "Hagen", "K1101R": "Hamburg", "R2404": "Hamm",
    "M1502": "Hanau", "P2305": "Hannover", "Y1109": "Heilbad Heiligenstadt",
    "Y1302": "Hildburghausen", "P2408": "Hildesheim", "D4501V": "Hof",
    "V1102": "Homburg", "D5701V": "Ingolstadt", "R2604": "Iserlohn",
    "Y1206": "Jena", "Y1206V": "Jena - Handels-, Genossenschafts- und Partnerschaftsregister", "T3201V": "Kaiserslautern",
    "M1607": "Kassel", "D2304V": "Kempten (Allgäu)", "X1517R": "Kiel",
    "R1304": "Kleve", "T2210V": "Koblenz", "M1608": "Korbach",
    "R1402": "Krefeld", "R3306": "Köln", "M1203": "Königstein im Taunus",
    "T3304V": "Landau in der Pfalz", "D2404V": "Landshut", "U1308": "Leipzig",
    "R2307": "Lemgo", "M1706": "Limburg a.d. Lahn", "T3104V": "Ludwigshafen am Rhein",
    "X1721R": "Lübeck", "P2507": "Lüneburg", "T2304V": "Mainz",
    "B8535": "Mannheim", "M1809": "Marburg", "Y1304": "Meiningen",
    "D2505V": "Memmingen", "V1104": "Merzig", "T2214V": "Montabaur",
    "R1504": "Mönchengladbach", "Y1110": "Mühlhausen", "D2601V": "München",
    "R2713": "Münster (Westfalen)", "N1105V": "Neubrandenburg", "V1105": "Neunkirchen",
    "G1309": "Neuruppin", "R1102": "Neuss", "Y1111": "Nordhausen",
    "D3310V": "Nürnberg", "M1114": "Offenbach am Main", "P3210": "Oldenburg (Oldenburg)",
    "P3313": "Osnabrück", "V1107": "Ottweiler", "R2809": "Paderborn",
    "D2803V": "Passau", "X1321R": "Pinneberg", "G1312": "Potsdam",
    "Y1209": "Pößneck", "Y1208": "Pößneck - Zweigstelle Bad Lobenstein", "R2204": "Recklinghausen",
    "D3410V": "Regensburg", "N1206V": "Rostock", "Y1210": "Rudolstadt",
    "V1109": "Saarbrücken", "V1110": "Saarlouis", "D4608V": "Schweinfurt",
    "N1308V": "Schwerin", "R3208": "Siegburg", "R2909": "Siegen",
    "Y1113": "Sondershausen", "Y1307": "Sonneberg", "V1111": "St. Ingbert",
    "V1112": "St. Wendel", "P2106": "Stadthagen", "Y1214": "Stadtroda",
    "R2706": "Steinfurt", "W1215": "Stendal", "N1209V": "Stralsund",
    "D3413V": "Straubing", "B8534": "Stuttgart", "Y1112": "Sömmerda",
    "P2613": "Tostedt", "D2910V": "Traunstein", "B8537": "Ulm",
    "V1115": "Völklingen", "V1116": "Wadern", "P2716": "Walsrode",
    "D3508V": "Weiden i.d. OPf", "Y1114": "Weimar", "M1710": "Wetzlar",
    "M1906": "Wiesbaden", "T2408V": "Wittlich", "R1608": "Wuppertal",
    "D4708V": "Würzburg", "T3403V": "Zweibrücken",
}
# The upstream form fields (the search form carries 22 of them + the ViewState; the two
# "sbc_ohne…" checkboxes are absent while unchecked — a checked one is sent as "true").
_FORM = {
    "frm_suche": "frm_suche",
    "frm_suche:cbt_suchen": "Suchen",
    "frm_suche:lsom_bundesland:codelist:scl_bundesland:mysom": "NO_CODE",
    "frm_suche:lsi_insolvenzgerichte:codelist:scl_insolvenzgericht:mysom": "NO_CODE",
    "frm_suche:lsom_gegenstand:codelist:mysom": "NO_CODE",
    "frm_suche:lsom_wildcard:lsom": "0",
    "frm_suche:litx_vorname:text": "",
    "frm_suche:litx_sitzWohnsitz:text": "",
    "frm_suche:litx_firmaNachName:text": "",
    "frm_suche:ldi_datumVon:datumHtml5": "",
    "frm_suche:ldi_datumBis:datumHtml5": "",
    "frm_suche:ir_registereintrag:som_registergericht:mysom": "NO_CODE",
    "frm_suche:ir_registereintrag:som_registerart:mysom": "NO_CODE",
    "frm_suche:ir_registereintrag:itx_registernummer": "",
    "frm_suche:ir_registereintrag:ih_registereintrag": "true",
    "frm_suche:iaz_aktenzeichen:som_registerzeichen:mysom": "NO_CODE",
    "frm_suche:iaz_aktenzeichen:itx_abteilung": "",
    "frm_suche:iaz_aktenzeichen:itx_lfdNr": "",
    "frm_suche:iaz_aktenzeichen:itx_jahr": "",
    "frm_suche:iaz_aktenzeichen:ih_aktenzeichen": "true",
}

_VIEWSTATE_RE = re.compile(r'name="jakarta\.faces\.ViewState"[^>]*value="([^"]*)"')
_ACTION_RE = re.compile(r'<form id="frm_suche"[^>]*action="([^"]*)"')
_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_ERROR_RE = re.compile(r"Fehler in Feld '([^']+)':\s*([^<]{3,300})")
_TOO_MANY_RE = re.compile(r'id="otx_zuVieleTreffer"[^>]*>(.*?)</span>', re.S)
_NO_HITS_RE = re.compile(r'id="otx_keineTreffer"[^>]*>(.*?)</span>', re.S)

# "<Abteilung> <SIGN> <lfd>/<Jahr>" — the Abteilung may be absent ("IN 261/24"), may carry a
# suffix letter ("3 f IK 484/26"), and the number may carry a trailing decoration
# ("810 IN 1046/26 K-33-").
_AZ_RE = re.compile(
    r"^(?:(?P<abt>[0-9]{1,4}\s?[a-z]?)\s+)?(?P<sign>AR|IE|IK|IN)\s+"
    r"(?P<lfd>[0-9]+)\s*/\s*(?P<jahr>[0-9]{2,4})(?P<rest>.*)$")
# "<court>, <TYPE> <number>"
_REG_RE = re.compile(r"^(?P<court>[^,]+),\s*(?P<type>[A-Z]{2,3})\s+(?P<number>[0-9A-Za-z/\-]+)$")


def _de_today():
    """Today in GERMANY (the portal publishes by the German working day: MEZ in winter, MESZ in
    summer — the local date is not always the UTC date). The EU DST rule: the last Sunday of
    March 01:00 UTC to the last Sunday of October 01:00 UTC."""
    now = datetime.now(timezone.utc)
    year = now.year
    def last_sunday(month):
        d = datetime(year, month, 31 if month in (3, 10) else 30, tzinfo=timezone.utc)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    dst_start = last_sunday(3).replace(hour=1)
    dst_end = last_sunday(10).replace(hour=1)
    offset = 2 if dst_start <= now < dst_end else 1
    return (now + timedelta(hours=offset)).date().isoformat()


def _text(v):
    """HTML -> plain text (entities unescaped, tags dropped), whitespace collapsed."""
    if v is None:
        return None
    s = html.unescape(_TAG_RE.sub(" ", v))
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _cell(row, name):
    """One span of a result row -> its plain text (or None when the cell is empty)."""
    m = re.search(r'otx_%s"[^>]*>(.*?)</span>' % re.escape(name), row, re.S)
    return _text(m.group(1)) if m else None


def _criteria(page):
    """The upstream's own echo of the criteria it actually applied (the page repeats them)."""
    out = {}
    for key in ("bundeslandValue", "datumValue", "insogerichtValue", "gegenstandValue",
                "firmaNachnameValue", "wildcardValue", "zeitpunktValue"):
        m = re.search(r'id="otx_%s"[^>]*>(.*?)</span>' % key, page, re.S)
        if m:
            val = _text(m.group(1))
            if val:
                out[key.replace("Value", "")] = val
    return out


def parse_page(page):
    """The result page -> {"state", "rows", "message", "criteria"}. The three upstream states are
    a result table, "Keine Treffer" (otx_keineTreffer) and the too-many-hits refusal
    (otx_zuVieleTreffer). A form validation error raises usage_error with the upstream's
    own German sentence."""
    page = page or ""
    m = _TOO_MANY_RE.search(page)
    if m:
        return {"state": "too_many_hits", "rows": [],
                "message": _text(m.group(1)),
                "criteria": _criteria(page)}
    if _NO_HITS_RE.search(page):
        return {"state": "no_hits", "rows": [], "message": None, "criteria": _criteria(page)}
    i = page.find('id="tbl_ergebnis"')
    if i < 0:
        err = _ERROR_RE.search(page)
        if err:
            raise SdkError("usage_error", provider="de_inso",
                           detail=(f"the portal rejected the query — Fehler in Feld "
                                   f"'{err.group(1)}': {err.group(2).strip()}"))
        raise SdkError("upstream_unavailable", provider="de_inso",
                       detail="the result page carried neither a result table nor a "
                              "no-hits / too-many-hits marker — the portal's page shape changed")
    table = page[i:page.find("</table>", i)]
    rows = []
    for raw in _ROW_RE.findall(table):
        if "otx_datum" not in raw:
            continue
        rows.append(_map_row(raw))
    return {"state": "ok", "rows": rows, "message": None, "criteria": _criteria(page)}


def _map_row(raw):
    """One result row -> the flat record. The six upstream cells keep their own wording; the
    derivations are the ISO date, the case-number quartet and the register triple."""
    az = _cell(raw, "azAkt")
    reg = _cell(raw, "register")
    row = {
        "date": _cell(raw, "datum"),
        "case_number": az,
        "court": _cell(raw, "Gericht"),
        "debtor": _cell(raw, "schuldner"),
        "seat": _cell(raw, "Sitz"),
        "register": reg,
    }
    row["date_iso"] = _iso_de(row["date"])
    dept = sign = seq = year = None
    if az:
        m = _AZ_RE.match(az.strip())
        if m:
            dept = (m.group("abt") or "").strip() or None
            sign = m.group("sign")
            seq = m.group("lfd")
            year = m.group("jahr")
    row["case_department"] = dept
    row["case_sign"] = sign
    row["case_sequence"] = seq
    row["case_year"] = year
    reg_court = reg_type = reg_number = None
    if reg:
        m = _REG_RE.match(reg.strip())
        if m:
            reg_court = m.group("court").strip()
            reg_type = m.group("type")
            reg_number = m.group("number")
    row["register_court"] = reg_court
    row["register_type"] = reg_type
    row["register_number"] = reg_number
    return row


def _iso_de(d):
    """dd.mm.yyyy -> YYYY-MM-DD (None when the upstream's wording is not that shape)."""
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})$", (d or "").strip())
    if not m:
        return None
    return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))


def _iso_date(value, label):
    """A caller-supplied date -> YYYY-MM-DD, validated against the portal's online window."""
    s = str(value or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if not m:
        raise SdkError("usage_error", provider="de_inso",
                       detail=f"{label} must be an ISO date (YYYY-MM-DD), got {value!r}")
    if not (1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31):
        raise SdkError("usage_error", provider="de_inso",
                       detail=f"{label} is not a real calendar date: {value!r}")
    if s < FIRST_ONLINE:
        raise SdkError("usage_error", provider="de_inso",
                       detail=f"{label} {s} is before the portal went online ({FIRST_ONLINE}) — "
                              "the federal announcements start in the first week of January 2022")
    return s


def parse_az(value):
    """The case number as published -> the quartet the upstream form wants.
    "<Abteilung> <SIGN> <lfd>/<Jahr>" — the Abteilung may be absent."""
    s = str(value or "").strip()
    if not s:
        return None
    m = _AZ_RE.match(s)
    if not m:
        raise SdkError("usage_error", provider="de_inso",
                       detail=(f"the case number must read '<Abteilung> <SIGN> <lfd>/<Jahr>' "
                               f"with SIGN in {list(AZ_SIGNS)} (e.g. '504 IN 277/26', "
                               f"'IN 261/24'), got {value!r}"))
    return {
        "department": (m.group("abt") or "").strip() or None,
        "sign": m.group("sign"),
        "sequence": m.group("lfd"),
        "year": m.group("jahr"),
        "suffix": (m.group("rest") or "").strip() or None,
        "verbatim": s,
    }


def resolve_register_court(value):
    """A register court given as the upstream code (R1101) or as the court name ("Düsseldorf")
    -> the upstream code. An unknown value is a usage error."""
    s = str(value or "").strip()
    if not s:
        return None
    if s in REGISTER_COURTS:
        return s
    folded = s.casefold()
    for code, name in REGISTER_COURTS.items():
        if name.casefold() == folded:
            return code
    raise SdkError("usage_error", provider="de_inso",
                   detail=(f"register court {value!r} is unknown — give the upstream code "
                           f"(e.g. R1101) or one of the 149 court names (e.g. 'Düsseldorf')"))


def _bootstrap():
    """GET the search form -> (viewstate, action). The action carries the session id and is
    echoed verbatim; the ViewState is a one-shot postback token."""
    from ..transport import call_provider
    r = call_provider(provider, "search_page", {}, cache=None, no_cache=True,
                      extra_headers={"Accept": "text/html"})
    page = r["data"] or ""
    vs = _VIEWSTATE_RE.search(page)
    act = _ACTION_RE.search(page)
    if not vs or not act:
        raise SdkError("upstream_unavailable", provider="de_inso",
                       detail="the search form came back without a ViewState / form action — "
                              "the portal's page shape changed")
    return vs.group(1), act.group(1), r


def _post(fields):
    """The one atomic chain: bootstrap the form, post it, return the result page."""
    from ..transport import call_provider
    viewstate, action, boot = _bootstrap()
    params = dict(_FORM)
    params.update(fields)
    params["jakarta.faces.ViewState"] = viewstate
    r = call_provider(provider, "search_post", {"action": action, **params},
                      cache=None, no_cache=True,
                      extra_headers={"Accept": "text/html",
                                     "Origin": provider["baseUrl"],
                                     "Referer": provider["baseUrl"] + "/ap/suche.jsf"})
    return r["data"] or "", [boot, r]


def _ttl_for(date_to):
    """A window that closed before today is settled -> 12h; a window that includes today keeps
    growing while the courts publish -> 1h."""
    return 3600 if date_to >= _de_today() else 12 * 3600


def _census(rows, state, criteria):
    cases = {r.get("case_number") for r in rows if r.get("case_number")}
    debtors = {r.get("debtor") for r in rows if r.get("debtor")}
    return {
        "announcements": len(rows),
        "distinct_cases": len(cases),
        "distinct_debtors": len(debtors),
        "with_case_number": sum(1 for r in rows if r.get("case_number")),
        "with_register": sum(1 for r in rows if r.get("register")),
        "with_seat": sum(1 for r in rows if r.get("seat")),
        "duplicate_case_rows": len(rows) - len(cases),
        "state_applied": criteria.get("bundesland") or "all states",
        "window_applied": criteria.get("datum"),
        "queried_at": criteria.get("zeitpunkt"),
    }


def _run(logical, fields, limit, cache, no_cache, date_to):
    """One portal query with the logical cache in front of it. The upstream's page depends on
    the FILTER values only — the session id in the path would otherwise blow the cache key up
    (every bootstrap mints a new session), so the caching happens here, keyed by the filters."""
    from ..transport import cache_key_for
    key = cache_key_for("de_inso_search", logical)
    ttl = _ttl_for(date_to)
    if not no_cache and cache is not None:
        hit = cache.get("de_inso", key, ttl)
        if hit:
            # a copy, not the stored dict itself: the cached entry must not be mutated
            # retroactively (the first caller's fresh envelope would flip to from_cache)
            payload = dict(hit["payload"])
            payload["from_cache"] = True
            payload["_meta"] = {"ok": True, "from_cache": True, "provider": "de_inso",
                                "fetched_at": hit["fetched_at_iso"]}
            payload["_metas"] = [payload["_meta"]]
            return payload
    page, metas = _post(fields)
    parsed = parse_page(page)
    rows = parsed["rows"]
    size = int(limit)
    payload = {
        "state": parsed["state"],
        "message": parsed["message"],
        "rows": rows[:size],
        "total_matched": len(rows),
        "scanned_rows": len(rows),
        "criteria": parsed["criteria"],
        "census": _census(rows, None, parsed["criteria"]),
        "limit_applied": size,
        "params": dict(logical),
        "from_cache": False,
        "_meta": metas[-1],
        "_metas": metas,
    }
    if not no_cache and cache is not None:
        cache.set("de_inso", key, payload, ttl)
    return payload


def search_raw(*, state=None, subject=None, date_from=None, date_to=None, name=None,
               first_name=None, seat=None, az=None, limit=20, cache=None, no_cache=False):
    """The federal insolvency announcements -> {rows, total_matched, state, message, census,
    limit_applied, params, _meta, _metas}. Every filter is the portal's own; the name field
    matches the surname / company designation EXACTLY (case-insensitively). The upstream
    refuses a window above its own cap — that answer comes back as state="too_many_hits"
    with the upstream's verbatim German sentence, not as an error."""
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 2000:
        raise SdkError("usage_error", provider="de_inso",
                       detail=f"limit must be 1-2000 (local payload wall), got {limit!r}")
    st = str(state or "").strip().upper() or None
    if st is not None and st not in STATES:
        raise SdkError("usage_error", provider="de_inso",
                       detail=f"state must be one of {sorted(STATES)}, got {state!r}")
    sb = str(subject or "").strip().upper() or None
    if sb is not None and sb not in SUBJECTS:
        raise SdkError("usage_error", provider="de_inso",
                       detail=f"subject must be one of {sorted(SUBJECTS)}, got {subject!r}")
    today = _de_today()
    d_from = _iso_date(date_from, "date_from") or today
    d_to = _iso_date(date_to, "date_to") or today
    if d_from > d_to:
        raise SdkError("usage_error", provider="de_inso",
                       detail=f"date_from {d_from} is after date_to {d_to}")
    nm = str(name or "").strip() or None
    fn = str(first_name or "").strip() or None
    stt = str(seat or "").strip() or None
    quartet = parse_az(az)

    fields = dict(_FORM)
    fields["frm_suche:ldi_datumVon:datumHtml5"] = d_from
    fields["frm_suche:ldi_datumBis:datumHtml5"] = d_to
    if st:
        fields["frm_suche:lsom_bundesland:codelist:scl_bundesland:mysom"] = st
    if sb:
        fields["frm_suche:lsom_gegenstand:codelist:mysom"] = sb
    if nm:
        fields["frm_suche:litx_firmaNachName:text"] = nm
    if fn:
        fields["frm_suche:litx_vorname:text"] = fn
    if stt:
        fields["frm_suche:litx_sitzWohnsitz:text"] = stt
    if quartet:
        fields["frm_suche:iaz_aktenzeichen:som_registerzeichen:mysom"] = quartet["sign"]
        fields["frm_suche:iaz_aktenzeichen:itx_lfdNr"] = quartet["sequence"]
        fields["frm_suche:iaz_aktenzeichen:itx_jahr"] = quartet["year"]
        if quartet["department"]:
            fields["frm_suche:iaz_aktenzeichen:itx_abteilung"] = quartet["department"]
        else:
            # the cases whose number carries no Abteilung (the upstream's "ohne Abteilung"
            # checkbox — measured: "IN 261/24" resolves only with it)
            fields["frm_suche:sbc_ohneAbteilung"] = "true"

    logical = {"face": "search", "state": st, "subject": sb, "date_from": d_from,
               "date_to": d_to, "name": nm, "first_name": fn, "seat": stt,
               "az": quartet["verbatim"] if quartet else None}
    return _run(logical, fields, size, cache, no_cache, d_to)


def register_lookup_raw(*, register_court=None, register_type=None, register_number=None,
                        date_from=None, date_to=None, limit=20, cache=None, no_cache=False):
    """The register point lookup -> the same envelope shape as search_raw. The upstream demands
    the register entry UNAMBIGUOUS: court + type + number all three (a half-filled entry is
    rejected with "Der Registereintrag muss eindeutig belegt sein" — measured)."""
    size = int(limit) if limit is not None else 20
    if not 1 <= size <= 2000:
        raise SdkError("usage_error", provider="de_inso",
                       detail=f"limit must be 1-2000 (local payload wall), got {limit!r}")
    court = resolve_register_court(register_court)
    rtype = str(register_type or "").strip().upper() or None
    if rtype is not None and rtype not in REGISTER_TYPES:
        raise SdkError("usage_error", provider="de_inso",
                       detail=f"register_type must be one of {sorted(REGISTER_TYPES)}, "
                              f"got {register_type!r}")
    rnum = str(register_number or "").strip() or None
    if not (court and rtype and rnum):
        raise SdkError("usage_error", provider="de_inso",
                       detail=("the register entry needs all three parts — register_court, "
                               "register_type and register_number (the upstream rejects a "
                               "half-filled entry: 'Der Registereintrag muss eindeutig belegt sein')"))
    today = _de_today()
    d_from = _iso_date(date_from, "date_from") or today
    d_to = _iso_date(date_to, "date_to") or today
    if d_from > d_to:
        raise SdkError("usage_error", provider="de_inso",
                       detail=f"date_from {d_from} is after date_to {d_to}")

    fields = dict(_FORM)
    fields["frm_suche:ldi_datumVon:datumHtml5"] = d_from
    fields["frm_suche:ldi_datumBis:datumHtml5"] = d_to
    fields["frm_suche:ir_registereintrag:som_registergericht:mysom"] = court
    fields["frm_suche:ir_registereintrag:som_registerart:mysom"] = rtype
    fields["frm_suche:ir_registereintrag:itx_registernummer"] = rnum

    logical = {"face": "register_lookup", "register_court": court, "register_type": rtype,
               "register_number": rnum, "date_from": d_from, "date_to": d_to}
    return _run(logical, fields, size, cache, no_cache, d_to)
