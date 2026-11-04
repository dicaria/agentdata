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

    def euvd_vulnerability(self, *, id, execution=None, no_cache=None):
        """security euvd_vulnerability: ENISA EUVD point lookup by CVE or EUVD code (the real API
        host euvdservices.enisa.europa.eu hides behind the SPA shell — /api/v1/* on the public host
        answers shell HTML; record richer than the NVD public face: CVSS vector+score+version, EPSS
        inline, exploitedSince, CVE+GHSA aliases, structured vendor×product×version ranges, and
        attached EU member-state CSAF advisories; dates arrive in Java "MMM d, yyyy, h:mm:ss AM"
        format and are ISO-normalized locally; unknown id = HTTP 404 carried as upstream_not_found
        — probed 2026-11-03)."""
        self._security_only("euvd_vulnerability")
        r = security.euvd.vulnerability_raw(id, cache=self._c._cache,
                                            no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        row = r["row"]
        top_adv = (row["advisories"] or [None])[0]
        top_prod = (row["products"] or [{}])[0]
        exploited = "in the wild since " + row["exploited_since"][:10] if row["exploited_since"] else "no in-the-wild exploitation recorded"
        return self._flat_env(
            tool="euvd_vulnerability",
            input={"id": r["params"]["id"]},
            reason=(f"EUVD {row['euvd_id']} ({', '.join(row['aliases'][:2]) or 'no aliases'}): "
                    f"CVSS {row['base_score']} ({row['base_score_version']}), EPSS {row['epss']}, {exploited}"
                    + (f", {len(row['advisories'])} EU member-state advisory(ies)"
                       + (f" (top: {top_adv['id']} / {top_adv['source']})" if top_adv else "") if row["advisories"] else "")),
            result=row,
            evidence=[{"quote": f"{top_prod.get('vendor') or '—'} {top_prod.get('product') or '—'} {top_prod.get('version') or ''}".strip()
                                + f" — CVSS {row['base_score']}, EPSS {row['epss']}",
                       "url": f"https://euvd.enisa.europa.eu/vulnerabilities/{row['euvd_id']}"}]
                     + [{"quote": f"CSAF advisory {a['id']} ({a['source']}, {a['date_published'] or '—'})",
                         "url": f"https://euvd.enisa.europa.eu/vulnerabilities/{row['euvd_id']}"}
                          for a in row["advisories"][:2]],
            provider_id="euvd", metas=[r["_meta"]],
            query={"source": "raw", "upstream": r["params"]},
        )

    def euvd_exploited(self, *, limit=50, execution=None, no_cache=None):
        """security euvd_exploited: the ENISA EU KEV rolling window — vulnerabilities currently
        exploited in the wild per ENISA/CSA network tracking (probed 2026-11-02: 4 rows; the window
        grows continuously). The full 399,311-row euvd_id↔cve_id mapping is a raw-side 12MB dump,
        NOT this face; limit is a local slice (cisa kev posture)."""
        self._security_only("euvd_exploited")
        r = security.euvd.exploited_raw(limit=limit,
                                        cache=self._c._cache,
                                        no_cache=self._c.no_cache if no_cache is None else bool(no_cache))
        rows = r["rows"]
        top = rows[0] if rows else None
        return self._flat_env(
            tool="euvd_exploited",
            input={"limit": int(limit)},
            reason=(f"EU KEV rolling window: {r['total']} in-the-wild exploited vulnerabilit{'y is' if r['total'] == 1 else 'ies are'} currently tracked by ENISA"
                    + (f", returning {len(rows)}" if len(rows) < r["total"] else "")
                    + (f" — top concern {top['euvd_id']} ({', '.join(top['aliases'][:1]) or '—'}) CVSS {top['base_score']}, exploited since {(top['exploited_since'] or '')[:10]}"
                       if top else " — the window is currently empty")),
            result={"count": r["count"], "total": r["total"], "vulnerabilities": rows},
            evidence=[{"quote": f"{v['euvd_id']} ({', '.join(v['aliases'][:1]) or '—'}): "
                                f"{(v['vendors'] or ['—'])[0]} — CVSS {v['base_score']}, EPSS {v['epss']}, "
                                f"exploited since {(v['exploited_since'] or '—')[:10]}",
                       "url": f"https://euvd.enisa.europa.eu/vulnerabilities/{v['euvd_id']}"}
                      for v in rows[:5]],
            provider_id="euvd", metas=[r["_meta"]],
            query={"source": "raw", "upstream": {}},
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
