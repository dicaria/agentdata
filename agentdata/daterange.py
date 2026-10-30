"""daterange — local validation and end-filling for date ranges (shared by EDGAR FTS / USAspending).

Why it is needed: neither upstream errors on a "wrong" range, it just **silently returns
plausible-looking results** —

- EDGAR: a reversed range (startdt > enddt) returns 200 + total 0; an invalid date returns 200 + total:null.
- USAspending: a reversed range returns 200 + **data from outside the window** (2026-01-01~2025-01-01
  measured to return contracts from 2012–2024).

Both answer with `ok:true`, indistinguishable from "there really is no data". Since the local side
fills in the missing end, it should also enforce validity locally first: whichever end is given
fills the other (the default comes from that source's first covered date / today), and an invalid
format or a reversed range is always a usage_error (exit 2).
"""
from datetime import date

from .errors import SdkError


def resolve(startdt, enddt, *, default_start, provider, label="date range"):
    """-> (start, end, {"startdt": start, "enddt": end}); an invalid format or a reversed range raises usage_error."""
    s = str(startdt or default_start)
    e = str(enddt or date.today().isoformat())
    for name, v in (("startdt", s), ("enddt", e)):
        try:
            date.fromisoformat(v)
        except ValueError:
            raise SdkError("usage_error", provider=provider,
                           detail=f"{name} must be YYYY-MM-DD, got '{v}'"
                                  f" (the upstream does not error on an invalid date, it just silently returns empty results)")
    if s > e:
        raise SdkError("usage_error", provider=provider,
                       detail=f"{label} start/end reversed: {s} > {e}"
                              f" (the upstream does not error — EDGAR returns 0 hits, USAspending returns out-of-window data, so we block it locally)")
    return s, e, {"startdt": s, "enddt": e}
