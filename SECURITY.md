# Security policy

## Reporting a vulnerability

Please report security issues by email to **contact@dicaria.com** rather than
opening a public GitHub issue. Include a description of the issue, the steps
to reproduce it, and the affected version (the commit SHA on `main` is
sufficient).

You should receive an acknowledgement within five business days.

## Scope

- The SDK is a client. It stores no secrets beyond the credentials you
  configure yourself (for example the `AGENTDATA_API_KEY` environment
  variable). Reports about credential handling in the SDK are in scope.
- Vulnerabilities in upstream data sources belong to those sources. The
  [rate-limits ledger](docs/domains/rate-limits.md) documents each upstream
  this SDK touches.
- The hosted corpus service and its credentials are covered by the service
  agreement; report issues for that channel through the same email.
