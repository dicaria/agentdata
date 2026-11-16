"""it_agcm — AGCM (Italy's competition authority, www.agcm.it) case register + rating register
(keyless Domino custom endpoints).

IT legal faces (0.3.60; admitted from the research booklet it-agcm-agenda (agenda + rating
registers), re-probed live 2026-11-13 — the live laws below are the ones the booklet did not
carry):

CONTRACT (three flat top-level query parameters, no path segments):
  1. list — GET /dotcmsCustom/getDomino?urlStr=<replica>/<agent>?openagent&view=<view>&anno=&words=<term>
             &separatore=0&fattispecie=&bollettino=&istruttoria=&tipologie=&maxresults=<n>&start=<offset>
     The replica/agent pair rides INSIDE urlStr (the Domino "openagent" address):
       dbconc   = 10.200.70.10:8080/41256297003874BD/ag0101dot   (concentrations)
       dbcons   = 10.200.70.10:8080/C12560D000291394/ag0101dot   (consumer protection)
       dbrating = 10.200.70.10:8080/C1257AEE00509302/ag0101dot   (rating/rating renewal)
     start=-1 is a COUNT probe: the answer is a page carrying <div id="count">N</div> and no table.
     start>=0 is a page of rows (maxresults per page, 200 measured as the practical ceiling).
     The answer is an HTML table: <td data-label="Rif" ...> (the label attribute sometimes
     carries spaces around "=" — the parser tolerates that) and the case cell holds the
     /dettaglio?db=…&uid=…&view=… link.
  2. detail — GET /dotcmsCustom/getDominoDetail?urlStr=<replica>/ag0102dot?openagent&p=<uid>
     The answer is an HTML card: the field skeleton is
     <div style="…font-weight:bold">LABEL</div><div …>VALUE</div> (the value div carries no
     label), grouped under the band headers DATI GENERALI / ISTRUTTORIA / DECISIONE /
     PROVVEDIMENTI COLLEGATI.

LIVE LAWS (measured 2026-11-13, this machine):
  - CLOUDFLARE GATE IS IP-BOUND, NOT FINGERPRINT-BOUND: on DIRECT egress every path answers
    403 with "Cf-Mitigated: challenge" ("Just a moment..."), whatever UA/header set is used
    (Chrome UA and agentdata/… both fail). Through this machine's HTTP(S) proxy egress the
    same URLs answer 200. The SDK's urllib channel inherits HTTPS_PROXY from the environment
    (urllib's getproxies), so the face works here; from a direct-egress network it answers
    upstream_unavailable with a 403. The 403 is NOT retried (transport rule (2): a gate is not
    rate limiting).
  - words is a SINGLE-TOKEN name filter: "SAMSUNG" works, a multi-word name with dots
    ("BPER BANCA") answers HTTP 5000 (Domino's error page). The face therefore refuses a
    multi-token term up front with a usage_error naming the single-token rule.
  - the rating register (dbrating, view vInternetWebdot) carries the company's tax code and
    legal seat in the row itself (Sede legale / Cod fiscale / Società / Data Decisione /
    Esito / Rating / expiry date) — a company-name → Italian tax-code join surface.
  - the rating value is an icon file name (/images/icons/2S0P.gif) — the parser lifts the code
    out of the file name.

Counts (live 2026-11-13): dbconc vw0401 (concentrations) 12,878 · dbconc vw0301 944 ·
dbconc vw0201 1,132 · dbcons vw0301 (consumer) 8,508 · dbrating vInternetWebdot 17,669.
The count drifts with the weekly case calendar (the 12,874 in the booklet is one week older).

Politeness: 0.25/2, concurrency 1, TTL 12h (the register rolls weekly).
"""
import html
import re

from ..errors import SdkError

provider = {
    "id": "it_agcm",
    "baseUrl": "https://www.agcm.it",
    "rate": {"rps": 0.25, "burst": 2},
    "concurrency": 1,
    "ops": {
        "list": {"path": "/dotcmsCustom/getDomino", "accept": "text", "timeout": 40.0},
        "detail": {"path": "/dotcmsCustom/getDominoDetail", "accept": "text", "timeout": 40.0},
    },
    "ttl": {"list": 12 * 3600, "detail": 24 * 3600},
}

_DOM = "10.200.70.10:8080"

# replica → (replica id, the Domino agent of the list endpoint, the Domino agent of the detail endpoint)
REPLICAS = {
    "dbconc": {"id": "41256297003874BD", "agent": "ag0101dot", "detail_agent": "ag0102dot",
               "label": "Concentrazioni (concentration control)"},
    "dbcons": {"id": "C12560D000291394", "agent": "ag0101dot", "detail_agent": "ag0102dot",
               "label": "Pratiche di tutela del consumatore (consumer protection)"},
    "dbrating": {"id": "C1257AEE00509302", "agent": "ag0101dot", "detail_agent": "ag0102dot",
                 "label": "Rating di credito (credit rating register)"},
}

# the views measured live (view → the count measured on 2026-11-13)
VIEWS = {
    "dbconc": {"vw0401": "concentration cases", "vw0301": "abuse of dominance", "vw0201": "unfair terms"},
    "dbcons": {"vw0301": "consumer protection cases"},
    "dbrating": {"vInternetWebdot": "credit rating decisions"},
}

_REF_LIST = "https://www.agcm.it/dotcmsCustom/dominoAngular.html"
_REF_DETAIL = "https://www.agcm.it/dotcmsCustom/dominoDetail.html"

_COUNT = re.compile(r'id=["\']count["\'][^>]*>\s*(\d+)')
_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_CELL = re.compile(r'<td([^>]*)>(.*?)</td>', re.S)
_LABEL = re.compile(r'data-label\s*=\s*"([^"]*)"', re.I)
_LINK = re.compile(r'<a href="([^"]*)"[^>]*>(.*?)</a>', re.S)
_IMG = re.compile(r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"', re.I)
# the detail card skeleton: <div …font-weight:bold">LABEL</div><div …>VALUE</div>
_DETAIL_FIELD = re.compile(
    r'<div[^>]*font-weight:bold[^>]*>\s*(.*?)\s*</div>\s*<div[^>]*>(.*?)</div>', re.S)
_DETAIL_LINK = re.compile(r'<li>\s*<a href="([^"]*)"[^>]*>(.*?)</a>', re.S)


def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _replica(name):
    r = REPLICAS.get(str(name or "").lower())
    if r is None:
        raise SdkError("usage_error", provider="it_agcm",
                       detail=f"unknown replica {name!r} — pick one of {sorted(REPLICAS)}")
    return r


def _url_str(replica, agent="ag0101dot"):
    return f"{_DOM}/{replica['id']}/{agent}?openagent"


def _check_words(words):
    """The words filter is a single token (a multi-word name answers HTTP 5000 upstream)."""
    w = str(words or "").strip()
    if w and len(w.split()) > 1:
        raise SdkError("usage_error", provider="it_agcm",
                       detail=("the AGCM words filter is a SINGLE token — a multi-word name "
                               f"({w!r}) answers HTTP 5000 upstream; pass one name token "
                               "(e.g. 'UNICREDIT') and filter the rows locally"))
    return w


def count_from_html(text):
    """The count page → the count (pure function — split out for offline testing)."""
    m = _COUNT.search(text or "")
    return int(m.group(1)) if m else None


def rows_from_html(html_text):
    """A page of rows → row dicts (label → text; the label attribute may carry spaces)."""
    out = []
    for tr in _ROW.findall(html_text or ""):
        cells = _CELL.findall(tr)
        if not cells:
            continue
        row = {}
        for attrs, body in cells:
            lm = _LABEL.search(attrs)
            label = lm.group(1).strip() if lm else None
            link = _LINK.search(body)
            img = _IMG.search(body)
            value = _text(body)
            cell = {"value": value}
            if link:
                cell["href"] = html.unescape(link.group(1))
                cell["text"] = _text(link.group(2))
                cell["link_text"] = _text(link.group(2))
            if img:
                cell["icon"] = html.unescape(img.group(1))
                cell["icon_code"] = img.group(2)
            row[label or f"col{len(row) + 1}"] = cell
        if row:
            out.append(row)
    return out


def detail_from_html(html_text):
    """The detail card → the field skeleton + the linked provvedimenti (pure function)."""
    fields = {}
    for label, value in _DETAIL_FIELD.findall(html_text or ""):
        key = _text(label)
        if not key:
            continue
        fields.setdefault(key, _text(value))
    provvedimenti = [{"href": html.unescape(h), "text": _text(t)}
                     for h, t in _DETAIL_LINK.findall(html_text or "")]
    return {"fields": fields, "provvedimenti": provvedimenti}


def _list_params(replica, view, words="", start=0, maxresults=10, **extra):
    p = {"urlStr": _url_str(replica), "view": view, "anno": extra.get("anno", ""),
         "words": words, "separatore": extra.get("separatore", "0"),
         "fattispecie": extra.get("fattispecie", ""), "bollettino": extra.get("bollettino", ""),
         "istruttoria": extra.get("istruttoria", ""), "tipologie": extra.get("tipologie", ""),
         "maxresults": str(maxresults), "start": str(start)}
    return p


def _call(op, params, cache, no_cache):
    from ..transport import call_provider
    return call_provider(provider, op, params, cache=cache, no_cache=no_cache,
                          extra_headers={"Referer": _REF_LIST if op == "list" else _REF_DETAIL,
                                         "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"})


def count_raw(replica="dbconc", view="vw0401", *, words="", cache=None, no_cache=False):
    """→ {count, rows[], params, _meta}. The count probe is start=-1 (the upstream's own
    count channel — the answer carries <div id="count">N</div> and no table)."""
    r = _replica(replica)
    v = str(view or "").strip()
    if v not in VIEWS[r["id"].lower() if r["id"] in VIEWS else str(replica).lower()]:
        # the view list is keyed by the replica NAME
        if v not in VIEWS.get(str(replica).lower(), {}):
            raise SdkError("usage_error", provider="it_agcm",
                           detail=f"unknown view {view!r} for replica {replica!r} — "
                                  f"known views: {sorted(VIEWS.get(str(replica).lower(), {}))}")
    w = _check_words(words)
    res = _call("list", _list_params(r, v, w, start=-1, maxresults=1), cache, no_cache)
    return {
        "count": count_from_html(res.get("data") or ""),
        "rows": [],
        "params": {"replica": str(replica).lower(), "view": v, "words": w},
        "_meta": res,
    }


def cases_raw(replica="dbconc", view="vw0401", *, words="", start=0, maxresults=10,
              cache=None, no_cache=False):
    """→ {rows[], params, _meta}. The rows are the register's own cells (label → value);
    the case cell carries the /dettaglio link (db + uid + view), which is the detail key."""
    r = _replica(replica)
    v = str(view or "").strip()
    known = VIEWS.get(str(replica).lower(), {})
    if v not in known:
        raise SdkError("usage_error", provider="it_agcm",
                       detail=f"unknown view {view!r} for replica {replica!r} — known views: {sorted(known)}")
    w = _check_words(words)
    try:
        st = int(start)
        mr = int(maxresults)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="it_agcm",
                       detail=f"start/maxresults must be integers, got start={start!r} maxresults={maxresults!r}")
    if st < 0:
        raise SdkError("usage_error", provider="it_agcm",
                       detail="start is the row offset (>= 0); use the count probe for the register size")
    if not 1 <= mr <= 200:
        raise SdkError("usage_error", provider="it_agcm",
                       detail=f"maxresults must be 1..200 (upstream page ceiling), got {mr}")
    res = _call("list", _list_params(r, v, w, start=st, maxresults=mr), cache, no_cache)
    return {
        "rows": rows_from_html(res.get("data") or ""),
        "params": {"replica": str(replica).lower(), "view": v, "words": w, "start": st,
                   "maxresults": mr},
        "_meta": res,
    }


def detail_raw(replica="dbconc", uid="", *, cache=None, no_cache=False):
    """→ {fields{}, provvedimenti[], params, _meta}. The detail card of one case
    (uid = the 32-hex unid the list rows carry in their /dettaglio link)."""
    r = _replica(replica)
    u = str(uid or "").strip()
    if not u:
        raise SdkError("usage_error", provider="it_agcm", detail="uid is required (the 32-hex unid from a list row)")
    res = _call("detail", {"urlStr": _url_str(r, r["detail_agent"]), "p": u}, cache, no_cache)
    doc = detail_from_html(res.get("data") or "")
    if not doc["fields"] and not doc["provvedimenti"]:
        raise SdkError("upstream_not_found", provider="it_agcm",
                       detail=f"the detail card for uid {u} is empty — the uid may belong to another replica")
    doc["params"] = {"replica": str(replica).lower(), "uid": u}
    doc["_meta"] = res
    return doc
