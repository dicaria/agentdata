# Terms of Use — agentdata GitHub Repository

Version 0.1 · 2026-10-30

These terms ("Terms") apply to your use of this repository, hosted at
https://github.com/dicaria/agentdata. They govern the things the code license
does not: access to hosted services, the boundary between code and data, and
names. The code itself is licensed under the license file in the repository
root ("LICENSE"). These Terms do not restrict what LICENSE grants you, and
LICENSE does not grant you anything these Terms reserve.

## 1. What this SDK is

`agentdata` is a Python client for public-domain company intelligence. It gives
you one consistent interface to two families of APIs:

- **Enrichment (local, free, no credentials).** The SDK calls public
  government and open-data APIs directly from your machine. You deal with the
  upstream source yourself; dicaria is not a party to that exchange.
- **Corpus (hosted).** Some commands query a hosted corpus service operated by
  dicaria. Those require credentials issued by dicaria and are governed by
  the separate service agreement under which the credentials were issued.
  Nothing in this repository is an offer or availability commitment for that
  service.

## 2. Data rights stay with the upstream sources

The SDK is a query channel. It does not grant you any rights in the data it
returns. Each dataset is governed by the terms of its upstream source — a
government agency, registry, or open-data publisher. That includes attribution
requirements, rate limits, and, for some sources, non-commercial restrictions.
You are responsible for reading and complying with the terms of each source
you query. The per-source rate limits the SDK enforces by default are
documented in `docs/domains/rate-limits.md`.

## 3. Fair use

Do not bypass the SDK's built-in rate limiting, and do not use the SDK to
place a load on an upstream source that a reasonable direct user of that
source would not place.

## 4. No warranty

The software and documentation in this repository are provided by the terms of
LICENSE. Upstream sources change their interfaces, availability, and data
without notice; the SDK may stop working against any source at any time.
Nothing here is a commitment that any particular source, dataset, or command
will remain available or accurate.

## 5. Limitation of liability

To the maximum extent permitted by law, dicaria is not liable for any damages
arising from use of this repository, the SDK, or data retrieved through it.

## 6. Trademarks

"agentdata", "dicaria", and related names and marks are not licensed to you
under LICENSE or these Terms, beyond what is needed to describe the origin of
the software.

## 7. Changes to these Terms

These Terms may be revised by committing a new version to this repository.
The version you received the code under continues to govern that copy.

---
*Version 0.1 · 2026-10-30. Governing-law and dispute-resolution provisions
will be added in a later revision.*
