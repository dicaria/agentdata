"""agentdata.errors — the closed error set (docs/domains/api.md sections 8.3/9.4; CLI exit codes 0/1/2).

- Upstream/availability family (exit 1): upstream_unavailable / upstream_rate_limited / upstream_not_found /
  thirdparty_upstream_unavailable / thirdparty_rate_limited / capability_unavailable / rate_limited
- Usage family (exit 2): usage_error / op_unknown / resolve_kind_unknown /
  corpus-contract 4xx (undeclared_field / bad_value / unauthenticated / forbidden …)
New entries require adversarial review (the same closed-set discipline as the Node side).
"""


class SdkError(Exception):
    def __init__(self, code, provider=None, status=None, detail=None, retry_after=None):
        super().__init__(detail or code)
        self.code = code
        self.provider = provider
        self.status = status
        self.detail = detail or code
        self.retry_after = retry_after

    # —— exit-code families (contract: upstream/availability family 1, usage family 2) ——
    EXIT1 = {
        "upstream_unavailable", "upstream_rate_limited", "upstream_not_found",
        "thirdparty_upstream_unavailable", "thirdparty_rate_limited",
        "capability_unavailable", "rate_limited",
    }

    @property
    def exit_code(self) -> int:
        return 1 if self.code in self.EXIT1 else 2

    def to_dict(self):
        err = {"code": self.code, "message": self.detail}
        if self.provider:
            err["provider"] = self.provider
        if self.retry_after:
            err["retry_after"] = self.retry_after
        return {"ok": False, "error": err}
