---
decision_date: 2026-08-29
record_date: 2026-08-31
provenance: backfilled
capture_status: not-attested
---

# ADR-0002 — Sequenced beachheads: Italy first, then DE + NL in parallel

- **Status:** Accepted
- **Decision date:** 2026-08-29

## Context

The EU is not one market for AML/KYC go-to-market: supervisory regimes, language, and buying
behaviour differ per member state. We must choose whether to launch broad or sequence. Ulissy
S.R.L. is Italian ([ADR-0004](ADR-0004-ulissy-srl-eu-contracting-entity.md)) — home-market
proximity (language, network, regulator familiarity, first references) lowers the cost of the
first landings. Germany and the Netherlands are large, high-value AML markets with strong
demand but higher entry cost and no home advantage.

## Decision

Sequence the beachheads: **Italy first**, to prove the product and generate the first
reference customers on home ground; **then Germany + the Netherlands in parallel** as the
second wave, once Italy has produced a working reference.

## Consequences

- Early effort, localization, and support concentrate on Italy — faster first references, lower
  burn per landing.
- DE + NL entry is explicitly **gated on a first Italian reference**, not on a calendar — keeps
  the second wave disciplined and reference-led.
- Product and compliance materials are built Italy-first but must be designed to generalize to
  DE/NL (multi-jurisdiction from the start in architecture, even if not in GTM).
- Concentration risk: over-fitting to the Italian regime could slow DE/NL; mitigated by keeping
  the DORA posture ([ADR-0003](ADR-0003-accept-dora-ict-provider-art-30-3.md)) EU-wide, not IT-specific.

## Open sub-questions

- What concretely counts as the "first Italian reference" that unlocks DE + NL?
- DE and NL truly in parallel, or does one lead by a step?
- Which parts of the offering are IT-jurisdiction-specific vs. EU-portable, and who owns the
  per-market localization?
