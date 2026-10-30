"""security faces — flat face-method mixin (split per domain in 0.2.6, moved in from client.py _Domain).

Mixed into the root _Domain (assembled via MRO, see client.py); discipline: no __init__, depends only on the
root internals (_flat_env/_c/_request…), method names globally unique across domains (a collision
would shadow another domain's face).
"""
from ..errors import SdkError


from .. import security  # domain-module path call (historical shape, kept for minimal disturbance)

class SecurityFaces:
    def _security_only(self, tool: str):
        if self.name != "security":
            raise SdkError("usage_error", detail=f"{tool} is a security-domain capability (not available on the {self.name} domain)")

    def osv_vulns(self, *, package, ecosystem, version=None, page_token=None,
                  execution=None, no_cache=None):
        """security osv_vulns: open-source package vulnerability query (OSV /v1/query POST with verbatim
        param names; ecosystem closed-set check — upstream silently returns empty for unknown values, so the
        false-negative guard lives locally; version may be omitted = all known vulns;
        paging: a next_page_token present in the response = more to fetch, pass page_token back verbatim to
        continue — upstream paginates past >1000 vulns or >20s (probed 2026-10-28: Linux/Kernel 2719 rows
        with a token)."""
        self._security_only("osv_vulns")
        r = security.osv.query_raw(package, ecosystem, version=version, page_token=page_token,
                                    cache=self._c._cache,
                                    no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        result = {k: x for k, x in r.items() if k != "_meta"}
        pk = r["params"]["package"]
        ver = r["params"].get("version")
        top = (result["vulns"] or [None])[0]
        return self._flat_env(
            tool="osv_vulns",
            input={"package": pk["name"], "ecosystem": pk["ecosystem"],
                   "version": ver, "page_token": r["params"].get("page_token")},
            reason=(f"OSV: {pk['ecosystem']} package \"{pk['name']}\""
                    + (f"@{ver} " if ver else "")
                    + f" has {result['count']} known vulnerabilities"
                    + (f", top concern {top['id']} ({top['summary'] or '—'})" if top else " (zero hits = no known vulnerabilities recorded for this version)")
                    + (" (more available — pass result.next_page_token back as --page-token to continue)" if result.get("next_page_token") else "")),
            result=result,
            evidence=[{"quote": f"{v['id']} = {v['summary'] or '—'}"
                                + (f" (alias {'/'.join(v['aliases'][:2])})" if v["aliases"] else ""),
                       "url": v["advisory_url"] or f"https://osv.dev/vulnerability/{v['id']}"}
                      for v in result["vulns"][:5]],
            provider_id="osv", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def cisa_kev_catalog(self, *, cve=None, ransomware=None, limit=50,
                         execution=None, no_cache=None):
        """security cisa_kev_catalog: the CISA catalog of vulnerabilities exploited in the wild (static feed
        ~1.8MB; cve exact lookup / ransomware=True lists only known ransomware use — both are local
        post-filters, upstream always stays pure with empty params; the catalog updates weekly, catalogVersion
        goes into reason)."""
        self._security_only("cisa_kev_catalog")
        r = security.cisa_kev.catalog_raw(cache=self._c._cache,
                                      no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        all_rows = r["vulnerabilities"]
        rows = all_rows
        if ransomware:
            rows = [v for v in rows if v["known_ransomware_campaign_use"] == "Known"]
        cv = str(cve or "").strip().upper() or None
        if cv:
            rows = [v for v in rows if (v["cve_id"] or "").upper() == cv]
        rows = rows[:max(1, int(limit))]
        result = {"catalog_version": r["catalog_version"], "date_released": r["date_released"],
                  "count_total": r["count_total"], "count": len(rows), "vulnerabilities": rows}
        filters = []
        if cv:
            filters.append(f"CVE {cv}")
        if ransomware:
            filters.append("ransomware use on record")
        return self._flat_env(
            tool="cisa_kev_catalog",
            input={"cve": cve, "ransomware": bool(ransomware), "limit": int(limit)},
            reason=(f"CISA KEV catalog v{r['catalog_version']} (released {r['date_released'] or '—'}, "
                    f"{r['count_total']} entries in total)"
                    + (f", {len(rows)} entries matching {'+'.join(filters)}" if filters else f", returning the first {len(rows)} entries")
                    + " — proven exploitation in the wild = the highest CVE priority tier"),
            result=result,
            evidence=[{"quote": f"{v['cve_id']} = {v['vendor_project'] or '—'} {v['product'] or '—'}: "
                                f"{v['vulnerability_name'] or '—'}"
                                + (" (ransomware use on record)" if v["known_ransomware_campaign_use"] == "Known" else ""),
                       "url": f"https://nvd.nist.gov/vuln/detail/{v['cve_id']}"}
                      for v in result["vulnerabilities"][:5]],
            provider_id="cisa-kev", metas=[r["_meta"]],
            query=({**({"source": "assembled", "assembled_from": {"cve": cv, "ransomware": bool(ransomware)}}),
                    "upstream": {}} if (cv or ransomware) else {"source": "raw", "upstream": {}}),
        )
