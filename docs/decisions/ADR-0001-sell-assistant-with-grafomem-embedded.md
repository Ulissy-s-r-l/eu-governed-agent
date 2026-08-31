---
decision_date: 2026-08-29
record_date: 2026-08-31
provenance: backfilled
capture_status: not-attested
---

# ADR-0001 — Sell the assistant with GRAFOMEM embedded (not the layer standalone)

- **Status:** Accepted
- **Decision date:** 2026-08-29

## Context

GRAFOMEM (the governance/attestation layer — CGR, signed decision trail, audit chain) can
be taken to market either as a **standalone layer** other vendors integrate, or **embedded**
inside a finished product the customer actually buys. The EU AML/KYC wedge needs a buyer who
feels the pain today (compliance/onboarding teams), not a platform team evaluating middleware.
Selling infrastructure standalone into regulated FS is a long, reference-gated motion; selling a
working assistant that *happens to be* governed is a product sale.

## Decision

Go to market with **the assistant (the AML/KYC governed agent) as the product, with GRAFOMEM
embedded** as its governance substrate. GRAFOMEM is the moat and the compliance story, not the
SKU. We do **not** lead with, or separately sell, the governance layer standalone in this wedge.

## Consequences

- The sellable unit is an outcome (governed AML/KYC assistance), not middleware — shortens the
  buyer's evaluation and lands with the team that has the budget and the pain.
- GRAFOMEM's differentiators (attestation, audit chain, CGR) become *proof points inside a demo*
  rather than a product the buyer must themselves integrate.
- Roadmap and pricing are set at the assistant level; the layer's capabilities are exposed only
  as far as they serve the assistant's compliance narrative.
- Standalone-layer licensing is deferred, not foreclosed — it can follow once the embedded
  product creates reference customers and the standard has adoption ([ADR-0005](ADR-0005-standard-gns-foundation-products-ulissy.md)).

## Open sub-questions

- Where exactly is the embed boundary — which GRAFOMEM surfaces are exposed to the customer
  (audit export? verify?) vs. internal only?
- Does any future standalone-layer motion risk channel conflict with the embedded product?
- What is the minimum GRAFOMEM feature set that must be embedded for the compliance claim to hold?
