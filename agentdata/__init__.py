"""AgentData SDK — two API families over domain data: corpus (hosted) + third-party realtime enrichment (local, keyless).

Contract: docs/domains/api.md (cross-domain charter) + per-domain API docs. Zero third-party dependencies (stdlib-only, floor 3.10).

    from agentdata import Client
    c = Client()                                     # zero config: enrichment runs locally, usable immediately
    c.healthcare.rxnav_rxcui_by_name(name="atorvastatin")               # flat panel command (the only surface since 0.3.0)
    c.healthcare.fda_drug_shortages(search='openfda.manufacturer_name.exact:"Fresenius Kabi"')
    c.company.gleif_lei_records(lei="5493001KJTIIGC8Y1R12")                  # company likewise (gleif parent face split in two)
    c.company.gleif_direct_parent(lei="5493001KJTIIGC8Y1R12")
    c.company.ted_notices_search(query="organisation-name-buyer=Siemens* AND organisation-country-buyer=DEU")
    c.esg.eiti_payments(eiti_id="11111111-…")                        # esg likewise
    c.esg.climatetrace_sources(owner_ids="E100000001492", year=2023)
    c.legal.gb_ec_donations(query="Keystone")                       # legal likewise (UK EC donations/loans split in two + TNA case law)
    c.legal.dgcomp_cases_search(name="Google", instrument="SA")
    c.legal.lda_filings(client_name="Google LLC", limit=25)          #   page_size hard-clamped to 25 upstream
    c.procurement.br_pncp_contracts(data_inicial="20260101", cnpj="…")  # procurement, seventh domain (founding pair + wb/NY trio + UNGM/NY OGS)
    c2 = Client(base_url="https://…", api_key="mk_live_…")   # corpus family: hosted
    c2.company.search(filters={"qtype": "专精特新小巨人"}, limit=100)

CLI: seven domains executable (`agentdata healthcare fda_drug_shortages --search …`
`agentdata company ted_notices_search --query 'organisation-name-buyer=Siemens*'`,
`agentdata esg climatetrace_sources --owner-ids E…`, `agentdata procurement br_pncp_contracts --data-inicial 20260101`).
Upstream parameter names verbatim + our defaults.
"""
from .client import Client
from .errors import SdkError

__version__ = "0.3.19"  # version bumps with each release; per-batch narratives live in the internal ledger (MAPPING.md) and MR descriptions (not exported)

__all__ = ["Client", "SdkError", "__version__"]
