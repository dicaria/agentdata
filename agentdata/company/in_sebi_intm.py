"""in_sebi_intm — SEBI registered intermediaries + the defaulters/expelled brokers register
(www.sebi.gov.in/sebiweb; the company domain's first IN face; research volume
in-sebi-intermediaries, 册 232; faces admitted in 0.3.35, probed first-hand 2026-11-04
tmp/probe-legal-0335/ with the SDK's own polite UA, direct).

Two faces, both the same card-table surface. Registered intermediaries: the index page
(OtherAction.do?doRecognised=yes) lists 37 categories with per-category update stamps; each
category answers a POST /sebiweb/ajax/other/getrecognisedintm.jsp {intmId, search, regNo}
form-fragment. **An empty search over a full category times out server-side** (intmId=30 =
5,011 brokers: the 240s+ whole-category shot died at research time) — the face therefore
REQUIRES exactly one of search (substring, e.g. MOTILAL → 8 rendered rows = 7 cards, the
8th being the empty skeleton) or regNo (the exact
registration-number lookup, INB030484617 → the multi-exchange row set). Cards are
title/value pairs whose FIELD SET VARIES BY CATEGORY and even by row (equity-broker cards:
Name/Trade Name/Registration No./Type/[E-mail/Telephone/Address]/Validity/Exchange Name;
CRA cards: Name/Registration No./Type/E-mail/Telephone/Address/Contact Person/
Correspondence Address/Validity — no Trade Name, no Exchange, regno format IN/CRA/001/1999):
the parser harvests every pair, maps the known labels to snake_case keys and keeps an
unknown label verbatim — nothing is invented. E-mail rides HTML entities (&#64;) — unescaped.
The fragment may end with an EMPTY skeleton card (serial number only, zero fields — pinned
ip1 i9): skipped. One entity legitimately spans multiple cards (one per exchange — the
register's own multi-row shape, kept verbatim; regno+exchange is the dedupe key downstream).

Defaulters & expelled brokers: GET /sebiweb/broker/BrokerAction.do?doBroker=yes answers the
whole negative register in ONE 1.24MB page, 445 cards, no paging, no search — the same card
layout with a Status field (Defaulter 80 / Expelled 215 / "Defaulter and expelled" 150,
pinned 2026-11-04).

Rate: sebi.gov.in publishes no window -> polite 0.5 rps / burst 2 (shared with legal in_sebi
via the host-layer bucket). TTL: recognised 12h (daily-updated registers), brokers 24h
(a frozen-ish historical roster).
"""
import html
import re

from ..errors import SdkError

provider = {
    "id": "in_sebi_intm",
    "baseUrl": "https://www.sebi.gov.in",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "recognised": {"path": "/sebiweb/ajax/other/getrecognisedintm.jsp", "method": "POST",
                       "urlencoded": True, "accept": "text", "idempotent": True, "timeout": 60.0},
        "brokers": {"path": "/sebiweb/broker/BrokerAction.do?doBroker=yes", "accept": "text",
                    "timeout": 90.0},
    },
    "ttl": {"recognised": 12 * 3600, "brokers": 24 * 3600},
}

# the 37 recognised-intermediary categories (the index page's own links, labels verbatim —
# recog_main.html). slug -> (intmId, official label)
CATEGORIES = {
    "aif": (16, "Registered Alternative Investment Funds"),
    "banker_to_issue": (5, "Banker to an Issue"),
    "cra": (7, "Credit Rating Agency - CRA"),
    "custodians": (27, "Registered Custodians"),
    "debenture_trustee": (6, "Debentures Trustee"),
    "designated_dp": (4, "Designated Depository Participants"),
    "dp_cdsl": (18, "Registered Depository Participants - CDSL"),
    "dp_nsdl": (19, "Registered Depository Participants - NSDL"),
    "esg_rating": (47, "Registered ESG Rating Providers"),
    "foreign_vci": (25, "Registered Foreign Venture Capital Investors"),
    "fpi": (29, "FPIs / Deemed FPIs (Erstwhile FIIs/QFIs)"),
    "investment_adviser": (13, "Investment Adviser"),
    "invit": (20, "Registered Infrastructure Investment Trusts"),
    "kra": (8, "KYC (Know Your Client) Registration Agency registered with SEBI"),
    "merchant_bankers": (9, "Merchant Bankers"),
    "mutual_funds": (23, "Registered Mutual Funds"),
    "portfolio_managers": (33, "Registered Portfolio Managers"),
    "qualified_dp": (15, "Qualified Depository Participants"),
    "reit": (42, "Real Estate Investment Trust"),
    "research_analyst": (14, "Research Analyst"),
    "rta": (10, "Registrars to an issue and share Transfer Agents"),
    "sb_commodity_derivative": (2, "Registered Stock Brokers in Commodity Derivative Segment"),
    "sb_currency_derivative": (32, "Registered Stock Brokers in Currency Derivative Segment"),
    "sb_debt": (37, "Registered Stock Brokers in Debt Segment"),
    "sb_equity": (30, "Registered Stock Brokers in equity segment"),
    "sb_equity_derivative": (31, "Registered Stock Brokers in Equity Derivative Segment"),
    "sb_interest_rate_derivative": (38, "Registered Stock Brokers in Interest Rate Derivative Segment"),
    "scsb_direct_debt": (44, "Self-Certified Syndicate Banks under the direct ASBA facility (debt issuances)"),
    "scsb_direct_equity": (34, "Self-Certified Syndicate Banks under the direct ASBA facility (equity issuances)"),
    "scsb_syndicate_debt": (45, "Self-Certified Syndicate Banks under the Syndicate ASBA facility (debt issuances)"),
    "scsb_syndicate_equity": (35, "Self-Certified Syndicate Banks under the Syndicate ASBA facility for other than Retail Category (equity issuances)"),
    "scsb_upi_issuer": (40, "Self Certified Syndicate Banks eligible as Issuer Banks for UPI"),
    "scsb_upi_sponsor": (41, "Self Certified Syndicate Banks eligible as Sponsor Banks for UPI"),
    "sm_reit": (48, "Registered SM REITs"),
    "upi_apps": (43, "List of mobile applications for using UPI in Public Issues"),
    "vault_managers": (46, "Registered Vault Managers"),
    "vcf": (21, "Registered Venture Capital Funds"),
}

# card label -> row key (the labels seen across categories/registers; an unknown label rides
# verbatim as its own key — the CRA Contact Person/Correspondence Address precedent)
_LABELS = {
    "Name": "name",
    "Trade Name": "trade_name",
    "Registration No.": "registration_no",
    "Type": "type",
    "E-mail": "email",
    "Telephone": "telephone",
    "Address": "address",
    "Contact Person": "contact_person",
    "Correspondence Address": "correspondence_address",
    "Validity": "validity",
    "Exchange Name": "exchange",
    "Status": "status",
}

_INDEX_URL = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognised=yes"

_AJAX_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": _INDEX_URL,
    "Origin": "https://www.sebi.gov.in",
}

# quote style varies BY SURFACE on the same host: the AJAX intermediaries fragment ships
# single-quoted attributes (i8/i9/r2), the brokers page double-quoted (i10) — both accepted
_PAIR_RE = re.compile(r'(?s)<div class=["\']title["\']><span>(.*?)</span></div>\s*'
                      r'<div class=["\']value[^"\']*["\']>\s*<span>(.*?)</span>')


def parse_cards(text):
    """-> the list of card dicts: split on the card-table boundary, harvest every title/value
    pair per card (known labels mapped, unknown labels verbatim), skip the empty skeleton card
    (serial number only) and the fragment scaffolding around the cards."""
    rows = []
    for chunk in text.split("fixed-table-body card-table")[1:]:
        pairs = _PAIR_RE.findall(chunk)
        if not pairs:
            continue   # the empty skeleton card / non-card scaffolding (pinned ip1 i9)
        row = {}
        for label, value in pairs:
            key = _LABELS.get(label.strip(), label.strip())
            if key in row:
                continue   # the first value per label wins (a repeated label is a render echo)
            v = html.unescape(value).strip()
            row[key] = v if v else None
        rows.append(row)
    return rows


def intermediaries_raw(category="sb_equity", *, search=None, regno=None,
                       cache=None, no_cache=False):
    """-> {rows, count, category, category_name, mode, params, _meta}; rows are card dicts.

    Exactly one of search (substring over names — MOTILAL → 7 cards) or regno (the exact
    registration-number lookup, e.g. INB030484617) must be given: an empty search over a full
    category times out server-side (intmId=30's 5,011 brokers) — the wall carries that
    evidence. One entity legitimately spans multiple cards (one per exchange)."""
    from ..transport import call_provider

    if category not in CATEGORIES:
        raise SdkError("usage_error", provider="in_sebi_intm",
                       detail=f"category must be one of the 37 recognised-intermediary categories "
                              f"of sebi.gov.in/sebiweb (see --category choices), got {category!r}")
    q = str(search).strip() if search not in (None, "") else None
    reg = str(regno).strip() if regno not in (None, "") else None
    if q and reg:
        raise SdkError("usage_error", provider="in_sebi_intm",
                       detail="search (substring over the category) and regno (the exact "
                              "registration-number lookup) are mutually exclusive — give exactly one")
    if not q and not reg:
        raise SdkError("usage_error", provider="in_sebi_intm",
                       detail="in_sebi_intermediaries requires --search or --regno: an empty search "
                              "over a full category TIMES OUT server-side (intmId=30 = 5,011 equity "
                              "brokers — the whole-category shot died at research time, 册 232)")
    intm_id, label = CATEGORIES[category]
    params = {"intmId": str(intm_id), "search": q or "", "regNo": reg or ""}
    r = call_provider(provider, "recognised", params, cache=cache, no_cache=no_cache,
                      extra_headers=_AJAX_HEADERS)
    rows = parse_cards(r["data"] or "")
    return {
        "rows": rows,
        "count": len(rows),
        "category": category,
        "category_name": label,
        "mode": "search" if q else "regno",
        "query": q or reg,
        "params": params,
        "_meta": r,
    }


def default_brokers_raw(cache=None, no_cache=False):
    """-> {rows, count, params, _meta}: the whole defaulters & expelled brokers register in one
    GET (445 cards, no paging, no search — pinned 2026-11-04). Cards carry Name/Trade Name/
    Registration No. (INB…)/Exchange Name/Status (Defaulter | Expelled | Defaulter and
    expelled)."""
    from ..transport import call_provider

    # Accept: text/html rides the request exactly as the pinned live shot (i10) — the default
    # application/json Accept is unpinned against this 1.2MB HTML page, not worth the risk
    r = call_provider(provider, "brokers", {}, cache=cache, no_cache=no_cache,
                      extra_headers={"Accept": "text/html"})
    rows = parse_cards(r["data"] or "")
    return {
        "rows": rows,
        "count": len(rows),
        "params": {"doBroker": "yes"},
        "_meta": r,
    }
