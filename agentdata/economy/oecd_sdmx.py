"""oecd_sdmx — OECD SDMX 3.0-style REST data service (sdmx.oecd.org/public/rest; keyless).

One face: sdmx_series — one dataflow × one dot-separated key over an optional period window.
The 2026-11-02 ruling "OECD needs a key" was a misdiagnosis and is overturned by first-hand
probing (2026-11-03, tmp/probe-economy-0326/): the whole service is keyless, the wall was
the request FORM —

  * the dataflow reference must use the DSD@DF spelling the catalog itself carries:
    OECD.ECO.MAD,DSD_EO@DF_EO,1.5 (the bare DF_EO spelling answers
    404 "Could not find Dataflow and/or DSD related with this data request");
  * the KEY must carry EXACTLY as many dot-separated segments as the DSD has dimensions
    (DSD_EO: REF_AREA.MEASURE.FREQ = 3; a short key is a 403 "Not enough key values in
    query, expecting 12 got 6" on the bigger DSDs) — an EMPTY segment is the wildcard.

So the face always walks the structure first (/datastructure/{agency}/{DSD}/{version}?
references=none, SDMX-JSON) to read the dimension order, validates the key segment count
locally with the dimension list in the error message, then pulls the data through the SDMX
generic-CSV channel (Accept: application/vnd.sdmx.data+csv;version=1.0.0 — the same channel
as imf_sdmx / bis; the columns between DATAFLOW and TIME_PERIOD are the key dimensions,
attributes ride along as extra columns).

Verified anchors (2026-11-03): DSD_EO@DF_EO 1.5 DEU.. 2024-2027 -> 238,358 B CSV (EO 119,
quarterly projections, MEASURE FBGSQ in PT_B1GQ); DSD_NAAG@DF_NAAG_I 1.0 A.DEU... 2023+ ->
28 rows (GDP chapter, MEASURE B1GQ_R_POP in USD_PPP_PS, DEU 2025 = 61,900.5).

Rate: no published limit -> polite 0.5 rps / burst 2. TTL: structure 7 days (DSDs are
near-static), data 24h (the EO family moves quarterly, NAAG annually).
"""
import csv
import io
import json

from ..errors import SdkError

provider = {
    "id": "oecd_sdmx",
    "baseUrl": "https://sdmx.oecd.org/public/rest",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # path_safe: the structure ref carries slashes (agency/DSD/version); the flow ref
        # carries commas and the @ of the DSD@DF spelling — both must stay literal in the path
        "structure": {"path": "/datastructure/{structure}", "accept": "text", "path_safe": "/"},
        "sdmx_series": {"path": "/data/{flow}/{key}/all", "accept": "text", "notFound": [404],
                        "path_safe": ",@"},
    },
    "ttl": {"structure": 7 * 24 * 3600, "sdmx_series": 24 * 3600},
}

_STRUCT_ACCEPT = {"Accept": "application/vnd.sdmx.structure+json;version=1.0"}
_CSV_ACCEPT = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}


def _parse_flow(flow):
    """'OECD.ECO.MAD,DSD_EO@DF_EO,1.5' -> (agency, dsd, df, version|None); the DSD@DF spelling
    is REQUIRED — it is the form the catalog carries and the only one the data endpoint
    resolves for agency-prefixed flows."""
    t = str(flow or "").strip()
    parts = [p.strip() for p in t.split(",")]
    if len(parts) not in (2, 3) or not all(parts):
        raise SdkError("usage_error", provider="oecd_sdmx",
                       detail=f"--flow must be the catalog form \"agency,DSD@DF[,version]\" "
                              f"(e.g. OECD.ECO.MAD,DSD_EO@DF_EO,1.5), got {flow!r}")
    agency, dsd_df = parts[0], parts[1]
    if "@" not in dsd_df:
        raise SdkError("usage_error", provider="oecd_sdmx",
                       detail=f"--flow must carry the DSD@DF spelling (e.g. OECD.SDD.NAD,"
                              f"DSD_NAAG@DF_NAAG_I,1.0), got {flow!r} — the bare DF id answers "
                              f"404 \"Could not find Dataflow and/or DSD\" upstream")
    dsd, df = dsd_df.split("@", 1)
    if not dsd or not df:
        raise SdkError("usage_error", provider="oecd_sdmx",
                       detail=f"--flow malformed: {flow!r} (expected agency,DSD@DF[,version]; "
                              f"the agency may carry dots — OECD.ECO.MAD is the normal form)")
    version = parts[2] if len(parts) == 3 else None
    return agency, dsd, df, version


def _dim_names(head):
    """The key-dimension columns of the SDMX generic CSV: between DATAFLOW and TIME_PERIOD
    (the boundary rule, not a fixed list — the DSDs vary from 3 to 12 dimensions)."""
    names = []
    for col in head:
        if col == "DATAFLOW":
            continue
        if col == "TIME_PERIOD":
            break
        names.append(col)
    return names


def _structure_dims(text, flow):
    """SDMX-JSON structure answer -> the ordered dimension ids."""
    try:
        payload = json.loads(text)
        dsd = payload["data"]["dataStructures"][0]
        dims = dsd["dataStructureComponents"]["dimensionList"]["dimensions"]
        return [d["id"] for d in sorted(dims, key=lambda x: int(x.get("position", 0)))]
    except (ValueError, KeyError, IndexError, TypeError):
        raise SdkError("upstream_unavailable", provider="oecd_sdmx",
                       detail=f"The OECD structure answer for {flow} is not the SDMX-JSON "
                              f"dimension list: {str(text)[:120]!r}")


def _parse_rows(text):
    """SDMX generic CSV -> rows ({flow, dims, period, value, attributes})."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        raise SdkError("upstream_unavailable", provider="oecd_sdmx",
                       detail="The OECD SDMX CSV answer was empty")
    head = lines[0].split(",")
    if "TIME_PERIOD" not in head or "OBS_VALUE" not in head:
        raise SdkError("upstream_unavailable", provider="oecd_sdmx",
                       detail=f"The OECD SDMX answer is not the generic CSV table "
                              f"(head {lines[0][:120]!r})")
    dims = _dim_names(head)
    rows = []
    for rec in csv.DictReader(io.StringIO("\n".join(lines))):
        try:
            value = float(rec.get("OBS_VALUE"))
        except (TypeError, ValueError):
            value = None
        out = {"flow": (rec.get("DATAFLOW") or "").split(":")[-1].split("(")[0] or None,
               "dims": {d: rec.get(d) for d in dims if rec.get(d) not in (None, "")},
               "period": rec.get("TIME_PERIOD"),
               "value": value,
               "unit_measure": rec.get("UNIT_MEASURE") or None,
               "obs_status": rec.get("OBS_STATUS") or None,
               "unit_mult": rec.get("UNIT_MULT") or None,
               "currency": rec.get("CURRENCY") or None,
               "price_base": rec.get("PRICE_BASE") or None,
               "adjustment": rec.get("ADJUSTMENT") or None}
        rows.append(out)
    return rows


def sdmx_series_raw(flow, key, *, start=None, end=None, cache=None, no_cache=False):
    """-> {total, count, rows, dimensions, params, _meta}; /data/{flow}/{key}/all.
    flow = the catalog form agency,DSD@DF[,version]; key = dot-separated with EXACTLY one
    segment per DSD dimension, an empty segment = wildcard (DSD_EO: DEU.. = Germany, all
    measures, all frequencies); start / end = the upstream startPeriod / endPeriod bounds.
    The structure is walked first to validate the segment count (the short-key 403 wall)."""
    from ..transport import call_provider

    agency, dsd, df, version = _parse_flow(flow)
    segs = [s.strip().upper() for s in str(key or "").split(".")]
    structure_ref = f"{agency}/{dsd}" + (f"/{version}" if version else "")
    rs = call_provider(provider, "structure", {"structure": structure_ref},
                       cache=cache, no_cache=no_cache, extra_headers=_STRUCT_ACCEPT)
    dims = _structure_dims(rs["data"], flow)
    if len(segs) != len(dims):
        raise SdkError("usage_error", provider="oecd_sdmx",
                       detail=f"the key needs EXACTLY {len(dims)} dot-separated segments for "
                              f"{dsd}@{df} ({'.'.join(dims)}), got {len(segs)} "
                              f"({key!r}) — an empty segment is the wildcard")
    flow_ref = f"{agency},{dsd}@{df}" + (f",{version}" if version else "")
    s = str(start).strip() if start else None
    e = str(end).strip() if end else None
    params = {"flow": flow_ref, "key": ".".join(segs)}
    if s:
        params["startPeriod"] = s
    if e:
        params["endPeriod"] = e
    r = call_provider(provider, "sdmx_series", params, cache=cache, no_cache=no_cache,
                      extra_headers=_CSV_ACCEPT)
    rows = _parse_rows(r["data"])
    rows.sort(key=lambda x: (x.get("period") or ""))
    return {"total": len(rows), "count": len(rows), "rows": rows, "dimensions": dims,
            "params": {"flow": flow_ref, "key": ".".join(segs), "start": s, "end": e},
            "_meta": r}
