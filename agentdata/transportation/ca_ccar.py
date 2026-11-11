"""ca_ccar — Canadian Civil Aircraft Register (Transport Canada CCARCS-RIACC), keyless.

transportation aviation axis (0.3.54 founding batch, 册 292; probed first-hand 2026-11-10
tmp/probe-ca-ccar/ with the SDK's own polite UA, direct). THE REGISTER IS A WEBFORMS APP, but the
measured shape is a stateless GET pair — no ViewState dance needed:

  * search: RchSimpRes.aspx?cn=|..|&mn=|..|&sn=|..|&on=|owner|&m=|mark|&rfr=RchSimp.aspx&print=y —
    the POST search form 302-redirects to this URL with every criterion pipe-wrapped (`|value|`,
    empty = `||`); the bare GET answers identically (measured: same first row with and without the
    form bootstrap, no cookies). `print=y` = the printable rendition carrying the WHOLE result set
    in one page (269 rows for an AIR CANADA anywhere-match, 365KB; the interactive page shows
    10/page and its markup carries no pager links);
  * aircraft: ADet.aspx?id=<n>&hs=N&l=eng — the per-aircraft record in four blocks (aircraft /
    manufacturer / registration / registered owner), label:value rows in col-md divs (NOT th/td;
    the block headers are the parse anchors).

Match semantics: the pipe-wrapped value is a CONTAINS match (the form's ddl match-type 0 =
Anywhere; the Ending/Exact/Beginning modes are form-only and never surface in the result URL —
measured). At least one criterion required — a bare empty query would drag the whole register and
is walled locally (politeness cap 200 rows; total_matched always reported).

The ADet id space is ~500k with holes (册 292) — a not-found id is a legal empty, never a guess.
The owner block carries name+address verbatim from the public register (public-register
precedent: us_fmcsa company_officer_1/2); nothing is enriched on top.
"""
import html as _html
import re

from ..errors import SdkError

provider = {
    "id": "ca_ccar",
    "baseUrl": "https://wwwapps.tc.gc.ca",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        "search": {"path": "/Saf-Sec-Sur/2/CCARCS-RIACC/RchSimpRes.aspx", "accept": "text", "timeout": 60.0},
        "aircraft": {"path": "/Saf-Sec-Sur/2/CCARCS-RIACC/ADet.aspx", "accept": "text", "timeout": 40.0},
    },
    "ttl": {"search": 21600, "aircraft": 21600},  # the register rolls slowly; day-scale TTL
}

# 管道包裹形：|value|（空 = ||）；五槽 cn/mn/sn/on/m（common name / model / serial / owner / mark）
_FIELDS = (("common_name", "cn"), ("model_name", "mn"), ("serial_number", "sn"),
           ("owner", "on"), ("mark", "m"))

_ROW_RE = re.compile(r'ADet\.aspx\?id=(\d+)[^>]*>([^<]*)</a>.*?</td>(.*?)</tr>', re.S)

# 档案页标签 -> 行键（块内四块：Aircraft / Manufacturer / Registration / Registered Owner）
_BLOCKS = ("Aircraft Information", "Manufacturer Information", "Registration Information",
           "Registered Owner Information")
_LABELS = {
    "mark": "mark", "common name": "common_name", "model name": "model_name",
    "serial no.": "serial_number",
    "basis for eligibility for registration": "eligibility_basis",
    "category": "category", "engine": "engine",
    "max take-off weight": "max_take_off_weight", "24 bit address": "address_24bit",
    "regional office": "regional_office", "year imported": "year_imported",
    "base of operations": "base_of_operations",
    "manufacturer": "manufacturer", "country of manufacture": "country_of_manufacture",
    "year of manufacture": "year_of_manufacture",
    "type of registration": "type_of_registration",
    "owner registered since": "owner_registered_since",
    "latest certificate of registration issued": "latest_certificate_issued",
    "name": "owner_name", "address": "owner_address", "city": "owner_city",
    "province": "owner_province", "postal code": "owner_postal_code", "country": "owner_country",
}
_PAIR_RE = re.compile(
    r'<strong>\s*([^<]*?)\s*</strong>\s*</div>\s*<div class="col-md-\d[^"]*"[^>]*>\s*(.*?)\s*</div>',
    re.S)


def _txt(s):
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse_rows(page):
    """The print rendition rows: mark anchor + five trailing cells (common name / model / serial /
    owner / owner-registered-since). The header row carries no ADet anchor and cannot match."""
    rows = []
    for m in _ROW_RE.finditer(page):
        cells = [_txt(c) for c in re.split(r"</td>", m.group(3))[:-1]]
        rows.append({
            "adet_id": m.group(1),
            "mark": _txt(m.group(2)),
            "common_name": cells[0] if len(cells) > 0 else None,
            "model_name": cells[1] if len(cells) > 1 else None,
            "serial_number": cells[2] if len(cells) > 2 else None,
            "owner": cells[3] if len(cells) > 3 else None,
            "owner_registered_since": cells[4] if len(cells) > 4 else None,
        })
    return rows


def parse_aircraft(page):
    """The four blocks, each label:value pair mapped through _LABELS; unmapped labels ride along
    snake_cased under extra_fields (never dropped, never guessed)."""
    pos = [page.find(b) for b in _BLOCKS]
    if not all(p >= 0 for p in pos):
        return None
    out = {}
    order = sorted(range(len(_BLOCKS)), key=lambda i: pos[i])
    for k, i in enumerate(order):
        seg_end = pos[order[k + 1]] if k + 1 < len(order) else len(page)
        seg = page[pos[i]:seg_end]
        for pm in _PAIR_RE.finditer(seg):
            label, value = _txt(pm.group(1)), _txt(pm.group(2))
            if not label:
                continue
            key = _LABELS.get(label.rstrip(":").strip().lower())
            if key:
                out.setdefault(key, value or None)
            elif value:
                snake = re.sub(r"[^a-z0-9]+", "_", label.rstrip(":").strip().lower()).strip("_")
                out.setdefault("extra_fields", {}).setdefault(snake, value)
    return out


def search_raw(*, owner=None, mark=None, common_name=None, model_name=None, serial_number=None,
               limit=200, cache=None, no_cache=False):
    """CCAR contains-search -> {rows, total_matched, limit_applied, params, _meta}.

    Every criterion is optional BUT at least one is required (the empty query would drag the whole
    register; walled locally). The print rendition carries the whole result set — total_matched is
    the true count even when rows are capped."""
    from ..transport import call_provider

    vals = {"common_name": common_name, "model_name": model_name, "serial_number": serial_number,
            "owner": owner, "mark": mark}
    logical = {k: (str(v).strip() or None) for k, v in vals.items() if str(v or "").strip()}
    if not logical:
        raise SdkError("usage_error", provider="ca_ccar",
                       detail="ca_ccar_search requires at least one of owner/mark/common_name/"
                              "model_name/serial_number (a bare empty query would drag the whole register)")
    try:
        size = int(limit) if limit is not None else 200
    except (TypeError, ValueError):
        size = None
    if size is None or not 1 <= size <= 500:
        raise SdkError("usage_error", provider="ca_ccar",
                       detail=f"limit must be 1-500 (local payload wall), got {limit!r}")
    params = {"rfr": "RchSimp.aspx", "print": "y"}
    for k, q in _FIELDS:
        v = logical.get(k)
        params[q] = f"|{v}|" if v else "||"
    r = call_provider(provider, "search", params, cache=cache, no_cache=no_cache)
    rows = parse_rows(r["data"] or "")
    return {
        "rows": rows[:size],
        "total_matched": len(rows),
        "limit_applied": size,
        "params": dict(logical),        # the criteria echo (snake keys, unpiped)
        "upstream_params": params,      # the wire truth — the pipe-wrapped five-slot set, replayable
        "_meta": r,
    }


def aircraft_raw(*, adet_id, cache=None, no_cache=False):
    """CCAR per-aircraft record -> {aircraft, params, _meta} — the four blocks in one flat dict;
    a not-found id parses to None and surfaces as a legal empty (the id space has holes)."""
    from ..transport import call_provider

    aid = str(adet_id).strip()
    if not aid.isdigit():
        raise SdkError("usage_error", provider="ca_ccar",
                       detail=f"adet_id must be the numeric ADet id (e.g. 538042), got {adet_id!r}")
    params = {"id": aid, "hs": "N", "l": "eng"}
    r = call_provider(provider, "aircraft", params, cache=cache, no_cache=no_cache)
    return {
        "aircraft": parse_aircraft(r["data"] or ""),
        "params": {"adet_id": aid},
        "_meta": r,
    }
