---
status: superseded-by-relocation
record_date: 2026-08-31
capture_status: not-attested
relocated_to: GNS-Foundation/grafomem docs/decisions/0002-cgr-governance-domain-and-backfill.md
---

# ADR-0007 — CGR governance domain + backfill (RELOCATED to the Foundation)

**Status: Superseded by relocation.**

This is a **CGR schema question about the standard**, not a commercial decision — so per
[ADR-0005](ADR-0005-standard-gns-foundation-products-ulissy.md) (standard → GNS-Foundation,
products → Ulissy) it belongs to the Foundation's decision log, not here.

## New home

- **`GNS-Foundation/grafomem` → `docs/decisions/0002-cgr-governance-domain-and-backfill.md`** — the
  two capture gaps this ADR raised: (a) the capture `domain` enum
  `{deploy-verification, security-scan, adversarial-review}` has no governance/strategy value;
  (b) `cgr.attestation.v3` cannot express backfill (`created_at` is capture time, no distinct
  `decision_date` or `backfilled` flag). The AML decision-time-vs-record-time point (a supervisor
  question) is carried there as a product requirement.
- Its companion — the grounded-score **true-additive vs schema-bump** question — is
  **`GNS-Foundation/grafomem` → `docs/decisions/0001-cgr-grounding-dimension-additive-vs-schema-bump.md`**.

## Corrected reference

An earlier draft of this ADR linked `exec/grounded-score-decision-record.md`. **That path does not
exist** (in this repo or the grafomem repo). The correct references are the two grafomem records
above.

## What stays here

The commercial decisions **ADR-0001…0006 remain in this repo** (Ulissy-side, per ADR-0005). Only
this standard-side schema question relocated.
