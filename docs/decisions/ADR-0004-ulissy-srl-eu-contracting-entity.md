---
decision_date: 2026-08-29
record_date: 2026-08-31
provenance: backfilled
capture_status: not-attested
---

# ADR-0004 — Ulissy S.R.L. is the contracting entity for all EU markets

- **Status:** Accepted
- **Decision date:** 2026-08-29

## Context

The EU governed agent needs a single legal entity to sign customer contracts, carry the DORA
ICT-provider obligations ([ADR-0003](ADR-0003-accept-dora-ict-provider-art-30-3.md)), invoice,
and hold commercial liability across member states. Ulissy S.R.L. is an existing Italian
operating company already used as the operating entity in the GRAFOMEM ecosystem. The
alternative — per-market entities or a non-EU contracting party — adds cost, complexity, and
regulatory friction for EU financial-entity customers who prefer an EU counterparty.

## Decision

**Ulissy S.R.L. is the single contracting entity for all EU markets** (Italy, then Germany +
the Netherlands per [ADR-0002](ADR-0002-sequenced-beachheads-italy-then-de-nl.md)). All customer
agreements, DORA contractual provisions, and invoicing run through Ulissy S.R.L.

## Consequences

- One EU-resident counterparty for every customer — simpler for DORA (an EU ICT provider), for
  data-processing terms, and for procurement in regulated FS.
- Ulissy S.R.L. carries the commercial and DORA contractual liability across all three markets;
  its contracts must be multi-jurisdiction-ready even while GTM is Italy-first.
- Cross-border selling into DE/NL from an Italian entity is a freedom-of-services matter, not a
  new-entity matter — no per-market subsidiary is created for launch.
- Clean separation from the standard-holding body: products/contracts sit in Ulissy S.R.L.,
  the standard sits in GNS-Foundation ([ADR-0005](ADR-0005-standard-gns-foundation-products-ulissy.md)).

## Open sub-questions

- Does selling into DE/NL from an Italian S.R.L. trigger any local registration, VAT, or
  supervisory-notification requirements we must pre-clear?
- At what revenue/headcount does a local subsidiary in DE or NL become warranted?
- Is Ulissy S.R.L.'s current corporate form/capitalization adequate to carry DORA Art. 30(3)
  liability at target contract sizes?
