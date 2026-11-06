"""sg_datagovsg — Singapore data.gov.sg open-data platform (api-open.data.gov.sg; keyless).

Two faces (0.3.46; probed 2026-11-05, tmp/probe-sg-datagovsg-0346/ — catalog p1 +
initiate/poll on the ACRA others-UEN file + the 234 MB ACRA master + a Range GET on
the minted S3 URL; research volume sg-companies-acra, recipe 册 193):

  * datasets — the platform catalog: GET /v2/public/api/datasets?page=N. ONE page per
    call, 10 rows per page, 4,665 datasets across 467 pages (measured), datasetId
    ascending. Each row carries 8 keys: datasetId / createdAt / name / status /
    description / format / lastUpdatedAt / managedByAgencyName. **the upstream has NO
    query surface**: only ?page= is honoured — q/pageSize/limit/rows/agency are ALL
    silently ignored (probed: ?q=ACRA returns the same page-1 rows), there is no
    search route (/v2/public/api/search = 404) and no single-dataset route
    (/v2/public/api/datasets/<id> = 404). --q/--agency/--format are LOCAL contains
    over the fetched page's rows only — whole-catalog discovery is an explicit page
    walk (~467 calls at the polite tier). Beyond the last page the upstream answers
    200 with EMPTY rows and ZEROED totals (not a 404) — the face reports that shape
    honestly; page < 1 is refused locally (the upstream silently clamps page 0 to
    page 1 — a silent answer is never masqueraded as the asked page).

  * dataset_download — minted download coordinates for ONE dataset:
    GET /v1/public/api/datasets/<id>/initiate-download → 201 {data:{message, url}}
    (both probes — the 3.2 MB others-UEN file AND the 234 MB ACRA master — minted the
    URL immediately; the poll channel GET .../poll-download → 201
    {data:{status:"DOWNLOAD_SUCCESS", url}} exists as the fallback and is walked only
    when initiate comes back without a url). The url is a 1-hour S3 signed direct
    link (X-Amz-Expires=3600) on s3.ap-southeast-1.amazonaws.com — the face parses
    the mint time (X-Amz-Date), the window (X-Amz-Expires) and the true file title
    (response-content-disposition filename, e.g.
    EntitiesRegisteredwithOtherUENIssuanceAgencies.csv) out of the minted URL itself,
    so a caller knows exactly when the link dies. **the file body rides the batch
    line** — the SDK stays coordinates-only (the ACRA master file alone is 234 MB);
    caller guidance for the S3 hop: HEAD answers 403, plain GET and Range GET answer
    200/206 with Content-Range total.
    TTL: initiate 30 min (half the 1 h signature window — a cached hit is always
    still live), poll 60 s (status is momentary; poll rounds are fetched no_cache).
    An unknown id answers 404 with a plain {"error": "No table found for dataset ID: …"}
    body → upstream_not_found (the cz_ares posture — a caller error, never retried).

  * **no per-company query surface exists anywhere**: the ACRA BizFile per-entity
    views are a paid wall (out of scope by the keyless-only ruling) — the company
    register of record (ACRA, ~2.13 M entities, UEN keys) rides this platform as
    bulk CSV only. The ACRA family inside the catalog: the master file
    «Entities Registered with ACRA» d_3f960c10fed6145404ca7b821f263b87 (2,127,089
    rows × 8 cols), 27 letter volumes «ACRA Information on Corporate Entities»
    (53-col profiles, cessation-reason 14 values), 8 monthly formation/cessation
    panels, and the others-UEN file d_b1d2b840ab9e993570c037b706b39bb8 — discovery
    via the datasets face (--q ACRA over page walks).

Channel: plain GET, no key, no CAPTCHA, no published quota → polite 0.5 rps /
burst 2 (the platform answers 429 under concurrency — the memory records 20 s
backoff — so the tier stays conservative). ONLY the api-open host is clean:
www.data.gov.sg and api-production.data.gov.sg answer Cloudflare 403 to non-browser
agents (the recipe's gate census) — this provider never touches them.
"""
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from ..errors import SdkError
from ..transport import call_provider

provider = {
    "id": "sg_datagovsg",
    "baseUrl": "https://api-open.data.gov.sg",
    "rate": {"rps": 0.5, "burst": 2},
    "ops": {
        # params: page (query string — the path carries no placeholder, every param
        # lands in the query; the upstream honours page and silently ignores the rest)
        "catalog": {"path": "/v2/public/api/datasets", "accept": "json", "timeout": 60.0},
        # params: id (d_ + 32 hex, validated locally; unknown ids answer a plain
        # 404 {"error": ...} — declared notFound → upstream_not_found)
        "initiate": {"path": "/v1/public/api/datasets/{id}/initiate-download",
                     "accept": "json", "notFound": [404], "timeout": 60.0},
        "poll": {"path": "/v1/public/api/datasets/{id}/poll-download",
                 "accept": "json", "notFound": [404], "timeout": 60.0},
    },
    # initiate: half the 1 h signature window (a cached hit is always still live);
    # poll: status is momentary — the raw fn walks rounds with no_cache anyway
    "ttl": {"catalog": 24 * 3600, "initiate": 1800, "poll": 60},
}

_ID_RE = re.compile(r"^d_[0-9a-f]{32}$")
_FILENAME_RE = re.compile(r'filename="?([^";]+)"?')
_AMZ_DATE_FMT = "%Y%m%dT%H%M%SZ"
_POLL_ROUNDS = 5
_POLL_WAIT_S = 4.0


def _fold(s):
    """NFKC + casefold + whitespace collapse — the local contains filter fold."""
    return " ".join(unicodedata.normalize("NFKC", str(s or "")).split()).casefold()


def _amz_iso(v):
    """20261105T083439Z → 2026-11-05T08:34:39Z (None stays None)."""
    try:
        return datetime.strptime(str(v), _AMZ_DATE_FMT).replace(
            tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return None


def parse_mint(url):
    """the minted S3 signed URL → dict(host, path, filename, minted_at, expires_at,
    expires_in) — pure. The signature params carry everything a caller needs."""
    parts = urlsplit(url or "")
    q = parse_qs(parts.query)
    disp = (q.get("response-content-disposition") or [""])[0]
    mf = _FILENAME_RE.search(disp)
    amz_date = (q.get("X-Amz-Date") or [""])[0]
    try:
        expires = int((q.get("X-Amz-Expires") or ["3600"])[0])
    except ValueError:
        expires = 3600
    minted_at = _amz_iso(amz_date)
    expires_at = None
    if minted_at:
        try:
            dt = datetime.strptime(amz_date, _AMZ_DATE_FMT).replace(tzinfo=timezone.utc)
            expires_at = (dt + timedelta(seconds=expires)).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            expires_at = None
    return {"host": parts.netloc or None, "path": parts.path or None,
            "filename": mf.group(1) if mf else None, "minted_at": minted_at,
            "expires_at": expires_at, "expires_in": expires}


def catalog_raw(page=1, q=None, agency=None, fmt=None, limit=20, cache=None,
                no_cache=False):
    """one catalog page, locally filtered. --page is a real upstream param (the only
    one); --q/--agency/--format are LOCAL contains/exact over the fetched page's rows
    — the upstream has no query surface beyond ?page=. Beyond the last page the
    upstream answers 200 with empty rows and zeroed totals — returned honestly with
    the beyond_range flag, never an error."""
    try:
        page = int(page)
    except (TypeError, ValueError):
        raise SdkError("usage_error", provider="sg_datagovsg",
                       detail="--page must be an integer (1..catalog pages); the "
                              "upstream silently clamps junk to page 1 and this face "
                              "refuses to guess")
    if page < 1:
        raise SdkError("usage_error", provider="sg_datagovsg",
                       detail="--page starts at 1 (the upstream silently answers "
                              "page 1 for page=0 — this face refuses to show the "
                              "asked page as something it is not)")
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20
    if not 1 <= limit <= 100:
        raise SdkError("usage_error", provider="sg_datagovsg",
                       detail="limit must be 1-100 (local slice wall; the upstream "
                              "page is fixed at 10 rows)")
    wall = limit
    res = call_provider(provider, "catalog", {"page": str(page)},
                        cache=cache, no_cache=no_cache)
    doc = res["data"] if isinstance(res.get("data"), dict) else {}
    body = doc.get("data") or {}
    rows = body.get("datasets") or []
    census = {"catalog_pages": body.get("pages") if body.get("pages") is not None else 0,
              "catalog_total": body.get("totalRowCount") if body.get("totalRowCount") is not None else 0,
              "page_rows": len(rows), "page": page}
    beyond_range = bool(census["catalog_pages"] == 0 and not rows
                        and not census["catalog_total"])

    def _contains(field, needle):
        return needle in _fold(field)
    qq = _fold(q) if q else None
    ag = _fold(agency) if agency else None
    ff = str(fmt).strip().upper() if fmt else None
    kept = []
    for r in rows:
        if qq is not None and not (_contains(r.get("name"), qq)
                                   or _contains(r.get("description"), qq)):
            continue
        if ag is not None and not _contains(r.get("managedByAgencyName"), ag):
            continue
        if ff is not None and str(r.get("format") or "").strip().upper() != ff:
            continue
        kept.append(r)
    return {"page": page, "rows": kept[:wall], "total_matched": len(kept),
            "scanned_rows": len(rows), "beyond_range": beyond_range,
            "census": census,
            "limit_applied": min(wall, len(kept)),
            "params": {"page": page, "q": q, "agency": agency, "fmt": fmt},
            "_meta": res}


def download_raw(dataset_id, cache=None, no_cache=False):
    """minted download coordinates for one dataset: initiate → (only when the
    initiate answer carries no url) a short no_cache poll walk. The 1 h S3 signature
    is parsed for mint time, window and true file title. Unknown id → 404 →
    upstream_not_found (cz_ares posture). The file BODY rides the batch line — this
    face is coordinates-only by design."""
    nid = str(dataset_id or "").strip()
    if not _ID_RE.match(nid):
        raise SdkError("usage_error", provider="sg_datagovsg",
                       detail=("--id must be a data.gov.sg datasetId as issued — "
                               "'d_' + 32 hex chars, e.g. "
                               "d_3f960c10fed6145404ca7b821f263b87; take ids from the "
                               "sg_datagovsg_datasets face"))
    res = call_provider(provider, "initiate", {"id": nid}, cache=cache,
                        no_cache=no_cache)
    doc = res["data"] if isinstance(res.get("data"), dict) else {}
    data = doc.get("data") or {}
    url = data.get("url")
    polled = False
    rounds = 0
    if not url:
        for i in range(_POLL_ROUNDS):
            time.sleep(_POLL_WAIT_S)
            rounds = i + 1
            pres = call_provider(provider, "poll", {"id": nid}, no_cache=True)
            pdoc = pres["data"] if isinstance(pres.get("data"), dict) else {}
            pdata = pdoc.get("data") or {}
            if pdata.get("url"):
                url = pdata["url"]
                polled = True
                break
            status = str(pdata.get("status") or "").upper()
            if "FAIL" in status or "ERROR" in status:
                raise SdkError("upstream_unavailable", provider="sg_datagovsg",
                               detail=(f"the platform reports {pdata.get('status')} "
                                       f"for {nid} — the mint died upstream; retry "
                                       "later"))
        if not url:
            raise SdkError("upstream_unavailable", provider="sg_datagovsg",
                           detail=(f"no download URL minted for {nid} after "
                                   f"{rounds} poll rounds — the platform is still "
                                   "preparing the file; retry later"))
    mint = parse_mint(url)
    return {"dataset_id": nid, "minted_via": "poll" if polled else "initiate",
            "download_url": url, "message": data.get("message"), **mint,
            "census": {"poll_rounds": rounds}, "params": {"id": nid},
            "_meta": res}
