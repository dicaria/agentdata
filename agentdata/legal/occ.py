"""occ — US Office of the Comptroller of the Currency enforcement-actions provider (occ.gov; keyless).

legal bank-enforcement face (0.3.28; admitted 2026-11-03, probed tmp/probe-legal-0328). Discovery is the
by-year news-release listing (/news-events/newsroom/news-issuances-by-year/news-releases/{YYYY}-news-
releases.html — structured `data-column` rows: Date / ID ("NR 2026-93") / Title) → the monthly
enforcement releases (title contains "Enforcement Actions"; ~11-12 a year, listings verified
2005-2026) → the release body. THE BODY COMES IN TWO SCHEMAS (both parsed):

- **sentence form** (2024-2026 era): intro paragraph "Actions taken against banks are:" then ONE <li> per
  action — "<Action types> against <Bank>, <City>, <State>, for <violations>. The assessed civil money
  penalty is $750 million. Refer to OCC News Release 2026-89. (Docket No. AA-ENF-2026-41)." — the
  action-type words are docket-PDF anchors (/static/enforcement-actions/ea{DOCKET}.pdf), amounts carry
  million/billion multipliers, and a second <ul> under "actions against IAPs:" holds individual
  prohibition orders ("Order of Prohibition against <Name>, <role at bank, location>, for <reason>.
  (Docket …)"). A multi-entity variant lists banks after a colon ("against three subsidiary banks of X,
  City, State : Bank A, City, State ; Bank B … ; and Bank C, City, State.") with one shared allegations
  sentence — exploded into one row per bank.
- **table form** (≤2020 era): per-section <h2> ("Cease and Desist Orders", "Civil Money Penalty Orders",
  "Removal / Prohibition Orders", …) over a 4-column table (No. / Name-Bank-City / State / Date); the
  name and city share one cell (split at the last comma).

Docket No. (AA-ENF-YYYY-NN) is the official key; the same docket joins the EASearch database (1989+,
out of SDK scope). IAP rows are statutory public disclosures (co_sic precedent) — names carried
verbatim.

TTL: listing 12h (a live listing), release 30d (a published release is immutable); polite 0.5 rps.
"""
import re

from ..errors import SdkError

provider = {
    "id": "occ",
    "baseUrl": "https://www.occ.gov",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "listing": {"path": "/news-events/newsroom/news-issuances-by-year/news-releases/{year}-news-releases.html",
                    "accept": "text", "timeoutMs": 60000},
        "release": {"path": "{release_path}", "accept": "text", "notFound": [404],
                    "path_safe": "/", "timeoutMs": 60000},
    },
    "ttl": {"listing": 12 * 3600, "release": 30 * 86400},
}

# The year-listing floor: year pages verified live 2005-2026 (tmp/probe-legal-0328); earlier actions
# (1989+) live in the EASearch database, which stays out of SDK scope.
_YEAR_MIN = 2005

_MONTHS = ("January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December")

_STATES = ("Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
           "Delaware", "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois",
           "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
           "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana",
           "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York",
           "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
           "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
           "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
           "Puerto Rico", "Virgin Islands")
_STATE_RE = "|".join(re.escape(s) for s in _STATES)

_IAP_MARK = "actions against IAPs"
_DOC_RE = re.compile(r'href="([^"]*/static/enforcement-actions/[^"]+\.pdf)"')
_CMP_RE = re.compile(r"civil money penalty (?:is|of)\s+\$([\d,.]+)\s*(million|billion)?", re.I)
_RELATED_RE = re.compile(r"News Release (\d{4}-\d+)")
_DOCKET_RE = re.compile(r"\(Dockets?(?:\s*Nos?\.?)?\s*([^)]+)\)", re.I)


def _strip(el):
    """HTML fragment → flat one-line text (tags dropped, entities left as-is)."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", el)).strip()


def _amount_with_scale(text):
    """The sentence-form CMP sentence: "$750 million" → 750000000; "$1,250" → 1250; else None."""
    m = _CMP_RE.search(text or "")
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    scale = {"million": 1e6, "billion": 1e9}.get((m.group(2) or "").lower(), 1)
    return int(n * scale)


def _dockets(text):
    """'(Docket No. AA-ENF-2026-46 and AA-ENF-2026-47)' / '(Docket AA-ENF-2023-45)' →
    ['AA-ENF-2026-46', 'AA-ENF-2026-47'] (abbreviated forms like '56, and 57' kept verbatim)."""
    m = _DOCKET_RE.search(text or "")
    if not m:
        return None
    return [d for d in (x.strip(" .,") for x in re.split(r",| and ", m.group(1))) if d]


def _who_where(text):
    """"Bank of America, National Association , Charlotte, North Carolina, for …" →
    (name, city, state) — the state name anchors the split (bank names carry commas; the lazy
    name+city stop at the FIRST ', <state>' boundary). The city/state comma is optional
    ("Jackson Minnesota" ships without one). None when no state anchor."""
    m = (re.search(r",\s*(?P<city>[^,]+?)\s*,\s*(?P<state>%s)\b" % _STATE_RE, text)
         or re.search(r",\s*(?P<city>[^,]+?)\s+(?P<state>%s)\b" % _STATE_RE, text))
    if not m:
        return None, None, None
    before = text[: m.start()].strip().rstrip(",")
    return before or None, m.group("city").strip(), m.group("state")


def list_links(html):
    """Year-listing HTML → ordered [{nr, title, date, path}] (the `data-column` table rows; pure)."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html or "", re.S):
        cells = {m.group(1): _strip(m.group(2))
                 for m in re.finditer(r'<td data-column="([^"]+)"[^>]*>(.*?)</td>', tr, re.S)}
        a = re.search(r'href="([^"]+)"[^>]*>([^<]+)</a>', tr)
        if cells.get("ID") and a:
            out.append({"nr": cells["ID"], "title": a.group(2).strip(),
                        "date": cells.get("Date"), "path": a.group(1)})
    return out


def _abs(href):
    """/static/... anchor → absolute (releases ship both forms across eras)."""
    return "https://www.occ.gov" + href if href.startswith("/") else href


def _common(text, raw):
    """The fields every sentence-form row carries (dockets, CMP amount, docket-PDF links)."""
    m = _RELATED_RE.search(text)
    return {"action_docs": [_abs(h) for h in _DOC_RE.findall(raw)] or None,
            "cmp_amount": _amount_with_scale(text),
            "related_release": m.group(1) if m else None,
            "dockets": _dockets(text)}


def _entity_row(ent):
    """A "; "-separated entity chunk anchored on its state: "The First National Bank of Shiner ,
    Shiner, Texas. The Notices allege…" → ((name, city, state), trailing) — the trailing text
    (the shared allegations riding the final chunk) is returned for the caller."""
    ent = re.sub(r"^and\s+", "", ent.strip(), flags=re.I).strip()
    m = re.match(r"^(?P<who>.+?,\s*[^,]+?,\s*(?:%s))\b" % _STATE_RE, ent)
    if not m:
        return (None, None, None), None
    trailing = ent[m.end():].strip().lstrip(".").strip() or None
    name, city, state = _entity_triple(m.group("who").rstrip(".,"))
    return (name, city, state), trailing


def _entity_triple(blob):
    """"The First National Bank of Shiner , Shiner, Texas" → (name, city, state)."""
    m = re.match(r"^(?P<name>.+?),\s*(?P<city>[^,]+?)\s*,\s*(?P<state>%s)\b\.?$" % _STATE_RE,
                 blob.strip())
    if m:
        return m.group("name").strip(), m.group("city").strip(), m.group("state")
    return blob.strip() or None, None, None


def _parse_bank_li(raw):
    """One sentence-form bank action <li> → one row (the multi-entity variant explodes per bank)."""
    text = _strip(raw)
    ms = re.match(r"^(?P<types>.+?)\s+against\s+(?P<rest>.*)$", text, re.I)
    if not ms:
        return [{"kind": "bank", "action_types": None, "name": None, "city": None, "state": None,
                 "violations": text, "raw": True, **_common(text, raw)}]
    types = ms.group("types").strip()
    rest = ms.group("rest")
    # the multi-entity variant: "… against <holder>, <City>, <State> : B1, C, S ; B2, C, S ; and B3, C, S."
    mm = re.match(r"^(?P<holder>[^:]+):\s*(?P<list>.+)$", rest)
    if mm and ";" in mm.group("list"):
        holder, hcity, hstate = _who_where(mm.group("holder").strip())
        rows = []
        shared = None                       # the allegations sentence rides the final chunk
        for chunk in re.split(r";\s+", mm.group("list")):
            (name, city, state), trailing = _entity_row(chunk)
            if name is None:
                continue                    # tail text after the list (dockets etc.)
            if trailing and shared is None:
                shared = trailing
            rows.append({"kind": "bank", "multi": True, "action_types": types,
                         "holder": holder, "holder_city": hcity, "holder_state": hstate,
                         "name": name, "city": city, "state": state,
                         "violations": None, **_common(text, raw)})
        if rows:
            if shared:
                for row in rows:
                    row["violations"] = shared.rstrip(".").strip()
            return rows
    # simple form: TYPES against WHO, CITY, STATE, for VIOLATIONS. …
    name, city, state = _who_where(rest)
    mfor = re.search(r",\s*for\s+(.*?)(?:\.\s+The assessed|\.\s+Refer to|\.\s+\(Docket|\.\s*$)",
                     rest, re.S)
    return [{"kind": "bank", "multi": False, "action_types": types,
             "name": name, "city": city, "state": state,
             "violations": mfor.group(1).strip() if mfor else None,
             **_common(text, raw)}]


def _parse_iap_li(raw):
    """One sentence-form IAP action <li> → a prohibition row.

    "Order of Prohibition against Jennifer Hamblin, Vault Teller at a Cincinnati, Ohio, branch of
    Fifth Third Bank, N.A., for embezzling customer funds. … (Docket No. AA-ENF-2026-43)" →
    name = the first comma chunk; role = the rest up to the ", for " / ", based on " hinge; reason =
    the tail past the hinge (extra sentences kept, the docket tail cut); city/state = the first
    state anchor in the role."""
    text = _strip(raw)
    ms = re.match(r"^(?P<types>.+?)\s+against\s+(?P<rest>.*)$", text, re.I)
    if not ms:
        return {"kind": "iap", "action_types": None, "name": None, "role": None, "reason": None,
                "city": None, "state": None, **_common(text, raw)}
    rest = ms.group("rest")
    name, sep, tail = rest.partition(",")
    name = name.strip()
    role, reason = None, None
    if sep:
        mhinge = re.search(r",\s+(?:for|based on)\s+(.*)$", tail, re.S)
        if mhinge:
            role = tail[: mhinge.start()].strip()
            reason = re.sub(r"\.\s+\(Docket.*$", "", mhinge.group(1),
                            flags=re.S).strip().rstrip(".").strip() or None
        else:
            role = re.sub(r"\.\s+\(Docket.*$", "", tail,
                          flags=re.S).strip().rstrip(".").strip() or None
    city = state = None
    if role:
        _, city, state = _who_where(role)
    return {"kind": "iap", "action_types": ms.group("types").strip(),
            "name": name or None, "role": role, "reason": reason,
            "city": city, "state": state, **_common(text, raw)}


def rows_from_release(html):
    """Release HTML → {"form": "sentences"|"tables", "rows": [...]} (pure function).

    sentences: bank <li> before the IAP marker, IAP <li> after; tables: <h2> section + 4-column
    tables (No./Name-Bank-City/State/Date), header rows skipped."""
    if not html:
        return {"form": None, "rows": []}
    if _IAP_MARK in html or "Actions taken against banks are" in html:
        i = html.find(_IAP_MARK)
        bank_html, iap_html = (html[:i], html[i:]) if i >= 0 else (html, "")
        rows = []
        for li in re.findall(r"<li[^>]*>(.*?)</li>", bank_html, re.S):
            if " against " in li:
                rows.extend(_parse_bank_li(li))
        for li in re.findall(r"<li[^>]*>(.*?)</li>", iap_html, re.S):
            if " against " in li:
                rows.append(_parse_iap_li(li))
        return {"form": "sentences", "rows": rows}
    if "<h2" in html and "<table" in html:
        rows = []
        parts = re.split(r"<h2[^>]*>([^<]+)</h2>", html)
        for i in range(1, len(parts), 2):
            section = _strip(parts[i])
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", parts[i + 1], re.S):
                cells = [_strip(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
                if len(cells) >= 4 and cells[0] and cells[0] != "No.":
                    who, city = cells[1], None
                    if "," in who:
                        who, _, city = who.rpartition(",")
                        who, city = who.strip(), city.strip()
                    rows.append({"kind": "order", "order_type": section,
                                 "ea_no": cells[0], "who": who or None,
                                 "city": city or None, "state": cells[2] or None,
                                 "date": cells[3] or None,
                                 "action_docs": [_abs(h) for h in _DOC_RE.findall(tr)] or None})
        return {"form": "tables", "rows": rows}
    return {"form": None, "rows": []}


def _enf_releases(links):
    """Listing rows → the enforcement releases (title carries "Enforcement Actions"; order kept)."""
    return [l for l in links if "Enforcement Actions" in l["title"]]


def _release_month(rel):
    """A listing row → its release month ("February"), from the title when present (2026-era
    "OCC Announces Enforcement Actions for February 2026") else the listing date MM/DD/YYYY
    (2020/2010-era titles carry no month)."""
    m = re.search(r"for (" + "|".join(_MONTHS) + r")\s+\d{4}", rel["title"])
    if m:
        return m.group(1)
    md = re.match(r"(\d{1,2})/\d{1,2}/\d{4}$", rel.get("date") or "")
    return _MONTHS[int(md.group(1)) - 1] if md else None


def enforcements_raw(year=None, *, month=None, all_year=False, cache=None, no_cache=False):
    """Resolve + fetch enforcement releases for one year → {year, form, rows, releases_in_year,
    selected, params, _meta}.

    year defaults to the current calendar year; month (January..December) picks that month's release
    (default = the latest enforcement release of the year); all_year=True walks every enforcement
    release of the year. Rows carry their release_nr; rows_from_release detects the sentence vs table
    schema per release."""
    from datetime import datetime, timezone

    from ..transport import call_provider

    this_year = datetime.now(timezone.utc).year
    y = int(year) if year else this_year
    if y < _YEAR_MIN or y > this_year + 1:
        raise SdkError("usage_error", provider="occ",
                       detail=f"year must be {_YEAR_MIN}-{this_year + 1} (the by-year listing pages; "
                              f"actions since 1989 live in the EASearch database, out of SDK scope), "
                              f"got {year}")
    mon = None
    if month:
        mon = next((m for m in _MONTHS if m.lower() == str(month).strip().lower()), None)
        if mon is None:
            raise SdkError("usage_error", provider="occ",
                           detail=f"month must be a full month name ({', '.join(_MONTHS[:3])}, …), "
                                  f"got '{month}'")

    idx = call_provider(provider, "listing", {"year": y}, cache=cache, no_cache=no_cache)
    releases = _enf_releases(list_links(idx["data"]))
    if not releases:
        raise SdkError("upstream_not_found", provider="occ",
                       detail=f"no enforcement-actions releases on the {y} news-release listing "
                              f"(listings verified {_YEAR_MIN}+; earlier actions live in EASearch)")
    if mon is not None:
        hit = [r for r in releases if _release_month(r) == mon]
        if not hit:
            have = ", ".join(f"{r['nr']} ({_release_month(r) or '?'})" for r in releases)
            raise SdkError("upstream_not_found", provider="occ",
                           detail=f"no {mon} {y} enforcement release on the listing; "
                                  f"available: {have}")
        chosen = hit
    elif all_year:
        chosen = releases
    else:
        chosen = releases[-1:]                             # the latest of the year
    rows = []
    forms = []
    r = None
    for rel in chosen:
        r = call_provider(provider, "release", {"release_path": rel["path"]},
                          cache=cache, no_cache=no_cache)
        parsed = rows_from_release(r["data"])
        if parsed["form"] is None:
            raise SdkError("upstream_unavailable", provider="occ",
                           detail=f"{rel['nr']} parsed to neither the sentence nor the table shape "
                                  f"(upstream format change?)")
        forms.append(parsed["form"])
        for row in parsed["rows"]:
            rows.append({**row, "release_nr": rel["nr"], "release_title": rel["title"]})
    return {"year": y,
            "form": forms[0] if len(set(forms)) == 1 else "mixed",
            "count": len(rows), "rows": rows,
            "releases_in_year": [{k: r2[k] for k in ("nr", "title", "date", "path")}
                                 for r2 in releases],
            "selected": [{"nr": rel["nr"], "title": rel["title"], "path": rel["path"]}
                         for rel in chosen],
            "params": {"year": y, "month": mon,
                       "release_path": [rel["path"] for rel in chosen]},
            "_meta": r}
