"""edgar_ownership — EDGAR structured ownership filings (13F / Form 4 / Schedule 13D-G; keyless).

The holdings-disclosure layer under the filings line (0.3.75 batch E17, live-probed 2026-11-23,
tmp/probe-e17/): submissions/index/doc from the two existing SEC provider buckets (edgar_cik
submissions + edgar_arch Archives) — zero new buckets; this module adds the enumeration filters,
the document-pick laws and the three structured-XML parsers.

XSL-SHELL LAW (p13f/p13dg): submissions primaryDocument for 13F-HR AND Schedule 13D/G points at
the HUMAN-RENDERED cover ("xslForm13F_X02/primary_doc.xml", "xslSCHEDULE_13G_X02/primary_doc.xml")
— an HTML/JS rendering shell, not the filed XML (ElementTree dies "not well-formed"). The raw
documents sit at the accession root, siblings of that directory — resolved via the edgar_arch
index op (index.json pure-directory law), never via primaryDocument. Form 4's primaryDocument IS
root-level ("wk-form4_*.xml") but the same index-first path is used uniformly.

ROOT-XML PICK LAW (p13f): the 13F information table = root-level *.xml minus primary_doc.xml
(Berkshire 0001193125-26-463399: docs ["60471.xml", "primary_doc.xml"] → "60471.xml"; FTS _id
naming shows numeric-named tables are the norm); prefer a name containing "info" when several
remain, ambiguous → usage_error naming candidates (us_sec_filing_document --list is the
inspection door). 13D/G: prefer primary_doc.xml; Form 4: prefer primaryDocument when root-level,
else a name containing "form4"/"form5".

NAMESPACE LAW (p13f_doc/p13dgc): three schemas, three namespace regimes —
  13F informationTable  (2014+ schema): DEFAULT namespace
      http://www.sec.gov/edgar/document/thirteenf/informationtable → findall("infoTable")
      answers ZERO rows bare; every lookup goes through localname() (rsplit "}") ;
  Schedule 13D/G (2022+ edgarSubmission schema): TWO default namespaces —
      http://www.sec.gov/edgar/schedule13g on 13G/G-A, http://www.sec.gov/edgar/schedule13d on
      13D/13D-A (p13dgx) — root {…}edgarSubmission both; per-filer blocks differ too: G uses
      coverPageHeaderReportingPersonDetails (name/type/citizenship/aggregate/classPercent +
      the four powers INSIDE a reportingPersonBeneficiallyOwnedNumberOfShares wrapper), D uses
      reportingPersons→reportingPersonInfo (every field a direct child, filer CIK present);
      the issuer CIK element spells issuerCik (G) vs issuerCIK (D) → card lookups
      case-insensitive; legacy SC 13D/G filings are HTML → parsed=False;
  Form 4/5 ownershipDocument: NO namespace (plain find() works).
Parsers never assume the tag prefix — localname matching throughout.

VALUE-UNITS LAW: 13F "value" switched from thousands of USD to whole USD with the first quarterly
reporting period of 2023 (SEC release 2022). reportDate >= 2023-01-01 → "usd", else
"usd_thousands" (Berkshire Q3-2026 ALLY 472,572,546 = 12,561,737 sh × ~$37.6 — dollar-consistent,
probed). The card carries value_units so a sum is never unit-ambiguous.

GRANDCHILD-VALUE LAW (pform4c/pform4d): Form 4 wraps transaction-table fields as
<X><value>…</value></X> — and some TWICE: postTransactionAmounts → sharesOwnedFollowingTransaction
→ <value> (a middle-element probe answers its empty text and the field silently vanishes — the
post_shares drop caught by the test_flat_0375 fixture on the first run, fixed before release;
natureOfOwnership likewise rides a <value> wrap, never direct text). The _tv wrap→value pattern
covers both; the wrap name is the OUTER schema element, the value is its leaf.

FORM-STRING LAW (psubforms): submissions carries BOTH families for Schedule 13D/G — the structured
era "SCHEDULE 13D/G(/A)" AND the legacy HTML era "SC 13D/G(/A)" (Royce: 121 SCHEDULE 13G/A + 727
SC 13G/A in one recent window) — the enumeration filter is the eight-string union. STOCK Act PTRs
(pPTR) are NOT EDGAR filings (forms PD/PTXA/PTR all answer zero) — they live in the House/Senate
disclosure systems, out of this batch.

Submissions recent-window boundary: ~1000 newest filings per CIK — years of 13F-HR (4/yr) and
hundreds of Form 4, but a hyperactive insider can age out; older accessions ride
us_sec_filing_document (--cik + --accession + --filename) by hand.
"""
import xml.etree.ElementTree as ET

from ..errors import SdkError

PROVIDER_IDS = ("edgar_cik", "edgar_arch")  # both buckets already exist (E8/E11); no new quota

_13F_FORMS = ("13F-HR", "13F-HR/A")
_FORM4_FORMS = {"4": ("4",), "4/A": ("4/A",), "5": ("5",), "5/A": ("5/A",)}
_13DG_FORMS = ("SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A",
               "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A")


def localname(tag):
    """Namespace-law pivot: '{ns}infoTable' → 'infoTable'; bare tags pass through."""
    return str(tag).rsplit("}", 1)[-1]


# ---------- submissions enumeration (shared by the three faces) ----------

def enumerate_filings(cik10, forms, *, cache=None, no_cache=False):
    """submissions recent window → newest-first filing rows matching the exact form set:
    [{accession, filing_date, report_date, form, primary_doc}]. report_date '' → None."""
    from ..transport import call_provider
    from . import edgar_cik

    r = call_provider(edgar_cik.provider, "submissions", {"cik10": cik10},
                      cache=cache, no_cache=no_cache)
    recent = ((r.get("data") or {}).get("filings") or {}).get("recent") or {}
    form_l = recent.get("form") or []
    acc_l = recent.get("accessionNumber") or []
    filed_l = recent.get("filingDate") or []
    report_l = recent.get("reportDate") or []
    prim_l = recent.get("primaryDocument") or []
    want = set(forms)
    out = []
    for i, f in enumerate(form_l):
        if f not in want:
            continue
        rep = report_l[i] if i < len(report_l) else None
        prim = prim_l[i] if i < len(prim_l) else None
        out.append({"accession": acc_l[i], "filing_date": filed_l[i] if i < len(filed_l) else None,
                    "report_date": (rep or None), "form": f,
                    "primary_doc": (str(prim) if prim else None)})
    return out, r


# ---------- Archives access (index + doc, both pre-existing edgar_arch ops) ----------

def fetch_dir_rows(cik10, adsh_dashed, *, cache=None, no_cache=False):
    """accession directory → edgar_arch.index_rows (scaffold law inherited: bogus accession
    raises upstream_not_found there)."""
    from ..transport import call_provider
    from . import edgar_arch

    r = call_provider(edgar_arch.provider, "index", {"cik": cik10, "adsh": adsh_dashed.replace("-", "")},
                      cache=cache, no_cache=no_cache)
    return edgar_arch.index_rows(r["data"], adsh_dashed), r


def fetch_doc_text(cik10, adsh_dashed, filename, *, cache=None, no_cache=False):
    """one document body → decoded str (edgar_arch decode chain; bytes never leave the bucket)."""
    from ..transport import call_provider
    from . import edgar_arch

    r = call_provider(edgar_arch.provider, "doc",
                      {"cik": cik10, "adsh": adsh_dashed.replace("-", ""), "filename": filename},
                      cache=cache, no_cache=no_cache)
    meta, inner, _envelope = edgar_arch.split_envelope(r["data"].encode("latin-1"))
    text, _enc = edgar_arch.decode_bytes(inner)
    return text


def _root_xmls(rows):
    return [r["name"] for r in rows if r["name"].lower().endswith(".xml") and "/" not in r["name"]]


def _pick_error(provider, detail):
    raise SdkError("usage_error", provider=provider, detail=detail)


# ---------- per-family document pickers (the XSL-shell law lives here) ----------

def pick_13f_table(rows, adsh_dashed):
    """→ information-table filename. Root-level *.xml minus primary_doc.xml; 'info' in the name
    preferred when several; ambiguous → usage_error naming candidates."""
    names = _root_xmls(rows)
    cand = [n for n in names if n.lower() != "primary_doc.xml"]
    if len(cand) == 1:
        return cand[0]
    withinfo = [n for n in cand if "info" in n.lower()]
    if len(withinfo) == 1:
        return withinfo[0]
    _pick_error("edgar_ownership",
                f"cannot pin the 13F information table under accession {adsh_dashed} "
                f"(root-level xml: {', '.join(names) or 'none'} — the XSL-shell primaryDocument is never "
                "the table); inspect with us_sec_filing_document --cik ... --accession ... --list")


def pick_13dg_doc(rows, primary_doc):
    """→ (filename, legacy: bool). Structured era: root primary_doc.xml (any other single root xml
    second); legacy HTML era: a root .htm (primaryDocument root-level first)."""
    names = _root_xmls(rows)
    if "primary_doc.xml" in names:
        return "primary_doc.xml", False
    if len(names) == 1:
        return names[0], False
    htm = [r["name"] for r in rows if r["name"].lower().endswith((".htm", ".html"))
           and "/" not in r["name"]]
    prim = str(primary_doc or "")
    if prim and "/" not in prim and prim.lower().endswith((".htm", ".html")) and prim in htm:
        return prim, True
    if len(htm) == 1:
        return htm[0], True
    _pick_error("edgar_ownership",
                f"cannot pin the Schedule 13D/G document (root-level xml: {', '.join(names) or 'none'}, "
                f"htm: {', '.join(htm[:4]) or 'none'}) — inspect with us_sec_filing_document --list")


def pick_form4_doc(rows, primary_doc):
    """→ filename. primaryDocument wins when root-level (the Form 4 XML itself); else root xml
    preferring form4/form5 in the name; else single root xml; else usage_error."""
    prim = str(primary_doc or "")
    names = _root_xmls(rows)
    if prim and "/" not in prim and prim.lower().endswith(".xml"):
        return prim
    pref = [n for n in names if "form4" in n.lower() or "form5" in n.lower()]
    if len(pref) == 1:
        return pref[0]
    if len(names) == 1:
        return names[0]
    _pick_error("edgar_ownership",
                f"cannot pin the ownership document (root-level xml: {', '.join(names) or 'none'}) — "
                "inspect with us_sec_filing_document --list")


# ---------- value-units law ----------

def value_units_13f(report_date):
    """13F value unit by reporting period: 2023-Q1 onward = whole USD; earlier = thousands of USD."""
    return "usd" if (report_date and str(report_date) >= "2023-01-01") else "usd_thousands"


# ---------- 13F informationTable parser ----------

def _f(node, name):
    """direct child (localname) text, stripped; None when absent."""
    for el in node:
        if localname(el.tag) == name:
            t = (el.text or "").strip()
            return t or None
    return None


def _fw(node, wrap, inner):
    """child {wrap} then its child {inner} text (shrsOrPrnAmt→sshPrnamt shape)."""
    for el in node:
        if localname(el.tag) == wrap:
            return _f(el, inner)
    return None


def parse_13f_infotable(xml_text):
    """→ holdings rows (sparse dicts: absent optional fields dropped, nulls never faked).
    Localname-only access — the 2014+ default namespace never bites."""
    root = ET.fromstring(xml_text)
    rows = []
    for it in (el for el in root.iter() if localname(el.tag) == "infoTable"):
        others = [e.text.strip() for e in it
                  if localname(e.tag) == "otherManager" and (e.text or "").strip()]
        row = {
            "name_of_issuer": _f(it, "nameOfIssuer"),
            "title_of_class": _f(it, "titleOfClass"),
            "cusip": _f(it, "cusip"),
            "value": _f(it, "value"),
            "shares": _fw(it, "shrsOrPrnAmt", "sshPrnamt"),
            "shares_type": _fw(it, "shrsOrPrnAmt", "sshPrnamtType"),
            "investment_discretion": _f(it, "investmentDiscretion"),
            "voting_sole": _fw(it, "votingAuthority", "Sole"),
            "voting_shared": _fw(it, "votingAuthority", "Shared"),
            "voting_none": _fw(it, "votingAuthority", "None"),
            "put_call": _f(it, "putCall"),
            "other_manager": others or None,
        }
        rows.append({k: v for k, v in row.items() if v is not None})
    return rows


def _13f_totals(rows):
    vals = []
    for r in rows:
        try:
            vals.append(int(str(r.get("value")).replace(",", "")))
        except (TypeError, ValueError):
            continue
    return len(rows), (sum(vals) if vals else None)


# ---------- Form 4/5 ownershipDocument parser ----------

def _tv(node, wrap, inner="value"):
    """first descendant {wrap} → first descendant {inner} text (transactionDate/value shape)."""
    for el in node.iter():
        if localname(el.tag) == wrap:
            for sub in el.iter():
                if localname(sub.tag) == inner:
                    t = (sub.text or "").strip()
                    return t or None
            return None
    return None


def _bool01(v):
    return {"1": True, "0": False}.get(str(v).strip()) if v is not None else None


def parse_form4(xml_text):
    """→ {issuer, owners[], rows[]} — rows = flattened transaction lines (non-derivative first,
    then derivative), owner name carried on every row; sparse-dict law as in 13F."""
    root = ET.fromstring(xml_text)
    if localname(root.tag) != "ownershipDocument":
        return None
    issuer_el = None
    for el in root.iter():
        if localname(el.tag) == "issuer":
            issuer_el = el
            break
    issuer = None
    if issuer_el is not None:
        issuer = {"name": _f(issuer_el, "issuerName"), "cik": _f(issuer_el, "issuerCik"),
                  "ticker": _f(issuer_el, "issuerTradingSymbol")}
        issuer = {k: v for k, v in issuer.items() if v is not None} or None

    owners = []
    owner_names = []
    for ow in (el for el in root.iter() if localname(el.tag) == "reportingOwner"):
        o = {"name": _tv(ow, "reportingOwnerId", "reportingOwnerName"),
             "cik": _tv(ow, "reportingOwnerId", "reportingOwnerCik"),
             "is_director": _bool01(_tv(ow, "reportingOwnerRelationship", "isDirector")),
             "is_officer": _bool01(_tv(ow, "reportingOwnerRelationship", "isOfficer")),
             "is_ten_percent_owner": _bool01(_tv(ow, "reportingOwnerRelationship", "isTenPercentOwner")),
             "officer_title": _tv(ow, "reportingOwnerRelationship", "officerTitle"),
             "is_other": _bool01(_tv(ow, "reportingOwnerRelationship", "isOther")),
             "other_text": _tv(ow, "reportingOwnerRelationship", "otherText")}
        owners.append({k: v for k, v in o.items() if v is not None})
        if o.get("name"):
            owner_names.append(o["name"])

    def tx_rows(kind_wrap, kind):
        out = []
        for t in (el for el in root.iter() if localname(el.tag) == kind_wrap):
            row = {"kind": kind,
                   "security_title": _tv(t, "securityTitle"),
                   "transaction_date": _tv(t, "transactionDate"),
                   "transaction_code": _tv(t, "transactionCoding", "transactionCode"),
                   "equity_swap_involved": _bool01(_tv(t, "transactionCoding", "equitySwapInvolved")),
                   "transaction_form_type": _tv(t, "transactionCoding", "transactionFormType"),
                   "shares": (_tv(t, "transactionShares") if kind == "non_derivative"
                              else _tv(t, "transactionDerivativeSecurities")),
                   "price_per_share": _tv(t, "transactionPricePerShare"),
                   "acquired_disposed": _tv(t, "transactionAcquiredDisposedCode"),
                   # postTransactionAmounts is a double wrapper: the count sits in the GRANDCHILD
                   # <sharesOwnedFollowingTransaction><value>N</value> (pform4c) — stopping at the
                   # middle element answers its empty text (the post_shares drop, caught by the
                   # test_flat_0375 fixture, fixed before release)
                   "post_shares": _tv(t, "sharesOwnedFollowingTransaction"),
                   "direct_or_indirect": _tv(t, "directOrIndirectOwnership"),
                   "nature_of_ownership": _tv(t, "natureOfOwnership")}
            if kind == "derivative":
                row["exercise_date"] = _tv(t, "exerciseDate")
                row["expiration_date"] = _tv(t, "expirationDate")
                row["underlying_security_title"] = _tv(t, "underlyingSecurityTitle")
                row["underlying_security_shares"] = _tv(t, "underlyingSecurityShares")
            row["owner"] = owner_names[0] if owner_names else None
            out.append({k: v for k, v in row.items() if v is not None})
        return out

    rows = tx_rows("nonDerivativeTransaction", "non_derivative") + \
        tx_rows("derivativeTransaction", "derivative")
    return {"issuer": issuer, "owners": owners, "rows": rows}


# ---------- Schedule 13D/G edgarSubmission parser ----------

def parse_13dg(xml_text):
    """→ stake card | None (None = not the 2022+ structured schema — legacy HTML filings ride
    parsed=False rows with doc_url only). Localname-only access (schedule13g default ns)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    if localname(root.tag) != "edgarSubmission":
        return None

    def first(name):
        want = name.lower()  # case-insensitive: 13G spells issuerCik, 13D issuerCIK (p13dgx)
        for el in root.iter():
            if localname(el.tag).lower() == want:
                t = (el.text or "").strip()
                if t:
                    return t
        return None

    filers = []
    for det in (el for el in root.iter()
                if localname(el.tag) == "coverPageHeaderReportingPersonDetails"):
        # 13G/G-A layout (p13dgx element dump): name/citizenship/aggregate/classPercent/type are
        # DIRECT children carrying text (_f); the four voting/dispositive powers live INSIDE the
        # reportingPersonBeneficiallyOwnedNumberOfShares wrapper (_fw) — _tv's value-inner
        # probe answers None on every one of them (the filers[{}] empty-card collision,
        # caught on the first live smoke, fixed before release).
        flr = {"name": _f(det, "reportingPersonName"),
               "type": _f(det, "typeOfReportingPerson"),
               "citizenship": _f(det, "citizenshipOrOrganization"),
               "aggregate_shares": _f(det, "reportingPersonBeneficiallyOwnedAggregateNumberOfShares"),
               "class_percent": _f(det, "classPercent"),
               "sole_voting": _fw(det, "reportingPersonBeneficiallyOwnedNumberOfShares", "soleVotingPower"),
               "shared_voting": _fw(det, "reportingPersonBeneficiallyOwnedNumberOfShares", "sharedVotingPower"),
               "sole_dispositive": _fw(det, "reportingPersonBeneficiallyOwnedNumberOfShares", "soleDispositivePower"),
               "shared_dispositive": _fw(det, "reportingPersonBeneficiallyOwnedNumberOfShares", "sharedDispositivePower"),
               "excludes_certain_shares": _f(det, "aggregateAmountExcludesCertainSharesFlag")}
        filers.append({k: v for k, v in flr.items() if v is not None})
    for rp in (el for el in root.iter() if localname(el.tag) == "reportingPersonInfo"):
        # 13D layout (p13dgx D dump): formData→reportingPersons→reportingPersonInfo — every field
        # a DIRECT child (no power wrapper), filer CIK present here but absent in the G layout.
        flr = {"name": _f(rp, "reportingPersonName"),
               "cik": _f(rp, "reportingPersonCIK"),
               "type": _f(rp, "typeOfReportingPerson"),
               "citizenship": _f(rp, "citizenshipOrOrganization"),
               "shares": _f(rp, "aggregateAmountOwned"),
               "class_percent": _f(rp, "percentOfClass"),
               "sole_voting": _f(rp, "soleVotingPower"),
               "shared_voting": _f(rp, "sharedVotingPower"),
               "sole_dispositive": _f(rp, "soleDispositivePower"),
               "shared_dispositive": _f(rp, "sharedDispositivePower"),
               "excludes_certain_shares": _f(rp, "isAggregateExcludeShares")}
        filers.append({k: v for k, v in flr.items() if v is not None})
    card = {"schema": first("schemaVersion") or "edgarSubmission",
            "issuer_name": first("issuerName"),
            "issuer_cik": first("issuerCik"),
            "class_title": first("securitiesClassTitle"),
            "amendment_no": first("amendmentNo"),
            "filers": filers,
            "signature_date": first("date"),
            "submission_type": first("submissionType")}
    return {k: v for k, v in card.items() if v is not None}


# ---------- face-level fetchers ----------

def _doc_url(cik10, adsh_dashed, filename):
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/"
            f"{adsh_dashed.replace('-', '')}/{filename}")


def _enumerate_or_raise(cik10, forms, cache, no_cache, tool):
    filings, meta = enumerate_filings(cik10, forms, cache=cache, no_cache=no_cache)
    if not filings:
        from . import edgar_arch  # noqa: F401  (error rides the family provider id)
        raise SdkError("upstream_not_found", provider="edgar_ownership",
                       detail=f"no {', '.join(forms)} filings in the submissions recent window "
                              f"for CIK {int(cik10)} (~1000 newest filings; either this registrant "
                              "never files this form family or its filings predate the window — "
                              f"{tool} rides the CIK that carries the filing: issuers AND filers "
                              "both appear, Form 4 under the issuer, 13F under the institution)")
    return filings, meta


def fetch_13f_filings(cik10, *, limit=1, cache=None, no_cache=False):
    """→ {cik, filings: [{accession, filing_date, report_date, form, is_amendment, value_units,
    holdings_total, value_total, rows[]}], filings_scanned, _meta} — newest-first, XSL-shell-safe."""
    filings, meta = _enumerate_or_raise(cik10, _13F_FORMS, cache, no_cache, "us_sec_13f_holdings")
    cards = []
    for f in filings[:max(1, int(limit))]:
        dashed = f["accession"]
        rows, _im = fetch_dir_rows(cik10, dashed, cache=cache, no_cache=no_cache)
        fname = pick_13f_table(rows, dashed)
        xml_text = fetch_doc_text(cik10, dashed, fname, cache=cache, no_cache=no_cache)
        holdings = parse_13f_infotable(xml_text)
        total, vsum = _13f_totals(holdings)
        cards.append({**{k: f[k] for k in ("accession", "filing_date", "report_date", "form")},
                      "is_amendment": f["form"].endswith("/A"),
                      "value_units": value_units_13f(f["report_date"]),
                      "information_table": fname,
                      "holdings_total": total, "value_total": vsum,
                      "rows": holdings})
    return {"cik": cik10, "filings": cards, "filings_scanned": len(cards), "_meta": meta}


def fetch_form4_filings(cik10, *, form="4", limit=5, cache=None, no_cache=False):
    """→ {cik, form, filings: [{accession, filing_date, form, issuer, owners, rows[]}],
    filings_scanned, _meta} — rows flattened transaction lines, newest filings first."""
    forms = _FORM4_FORMS.get(form)
    if forms is None:
        raise SdkError("usage_error", provider="edgar_ownership",
                       detail=f"form must be one of {', '.join(_FORM4_FORMS)} (got \"{form}\")")
    filings, meta = _enumerate_or_raise(cik10, forms, cache, no_cache, "us_sec_form4_transactions")
    cards = []
    for f in filings[:max(1, int(limit))]:
        dashed = f["accession"]
        rows, _im = fetch_dir_rows(cik10, dashed, cache=cache, no_cache=no_cache)
        fname = pick_form4_doc(rows, f["primary_doc"])
        xml_text = fetch_doc_text(cik10, dashed, fname, cache=cache, no_cache=no_cache)
        parsed = parse_form4(xml_text)
        if parsed is None:  # not the ownershipDocument schema (should not happen on forms 4/5)
            continue
        cards.append({**{k: f[k] for k in ("accession", "filing_date", "form")},
                      "document": fname, "doc_url": _doc_url(cik10, dashed, fname),
                      **parsed})
    return {"cik": cik10, "form": form, "filings": cards,
            "filings_scanned": len(cards), "_meta": meta}


def fetch_13dg_filings(cik10, *, limit=5, cache=None, no_cache=False):
    """→ {cik, filings: [{accession, filing_date, form, doc_url, parsed, schema?, issuer_name?,
    issuer_cik?, filers[]?}], filings_scanned, structured_total, _meta} — legacy HTML era rides
    parsed=False (metadata + doc_url, never a fabricated stake)."""
    filings, meta = _enumerate_or_raise(cik10, _13DG_FORMS, cache, no_cache, "us_sec_13dg_stakes")
    cards = []
    structured = 0
    for f in filings[:max(1, int(limit))]:
        dashed = f["accession"]
        rows, _im = fetch_dir_rows(cik10, dashed, cache=cache, no_cache=no_cache)
        fname, legacy = pick_13dg_doc(rows, f["primary_doc"])
        card = {**{k: f[k] for k in ("accession", "filing_date", "form")},
                "document": fname, "doc_url": _doc_url(cik10, dashed, fname)}
        if legacy:
            card["parsed"] = False
            cards.append(card)
            continue
        xml_text = fetch_doc_text(cik10, dashed, fname, cache=cache, no_cache=no_cache)
        parsed = parse_13dg(xml_text)
        if parsed is None:
            card["parsed"] = False  # xml that is not the edgarSubmission schema (hybrid eras)
        else:
            card["parsed"] = True
            card.update(parsed)
            structured += 1
        cards.append(card)
    return {"cik": cik10, "filings": cards, "filings_scanned": len(cards),
            "structured_total": structured, "_meta": meta}
