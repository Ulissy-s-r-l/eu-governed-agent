---
decision_date: 2026-08-29
record_date: 2026-08-31
provenance: backfilled
capture_status: not-attested
---

# ADR-0006 — EIC / Digital Europe assessment deferred pending a first reference

- **Status:** Accepted (decision is to **defer**)
- **Decision date:** 2026-08-29

## Context

EU non-dilutive / blended funding — the European Innovation Council (EIC Accelerator) and the
Digital Europe Programme — is available and thematically aligned (digital, compliance, resilience).
But these instruments are time-expensive to pursue (long applications, panels, milestones) and
are far stronger with a **demonstrated reference customer** than with a pre-revenue pitch. The
question is whether to invest in a funding assessment now or after commercial proof.

## Decision

**Defer the EIC / Digital Europe funding assessment** until there is a **first reference
customer** (the Italy-first landing of [ADR-0002](ADR-0002-sequenced-beachheads-italy-then-de-nl.md)).
Do not open the application workstream before that milestone.

## Consequences

- Near-term focus and cash stay on shipping the product and landing the first Italian reference,
  not on grant-writing.
- The eventual EIC/Digital Europe application is expected to be **stronger** (a real reference,
  DORA-ready posture from [ADR-0003](ADR-0003-accept-dora-ict-provider-art-30-3.md), a clear EU
  entity in [ADR-0004](ADR-0004-ulissy-srl-eu-contracting-entity.md)).
- **Timing risk:** specific EIC/Digital Europe cut-off dates and calls are not being tracked while
  deferred — a desirable window could pass. Mitigation: a lightweight calendar watch on call
  deadlines even during deferral, so the reopen isn't purely reactive.
- This is a **defer, not a decline** — the assessment is explicitly revisited at the first-reference
  trigger.

## Open sub-questions

- What exactly re-triggers the assessment — the same "first Italian reference" as ADR-0002, or a
  stronger bar (paying, referenceable, live-in-production)?
- Who holds the lightweight watch on EIC/Digital Europe deadlines during the deferral?
- Would Ulissy S.R.L. or GNS-Foundation be the applicant, and does the split
  ([ADR-0005](ADR-0005-standard-gns-foundation-products-ulissy.md)) affect eligibility?
