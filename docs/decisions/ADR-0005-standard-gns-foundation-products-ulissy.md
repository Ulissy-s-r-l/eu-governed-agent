---
decision_date: 2026-08-29
record_date: 2026-08-31
provenance: backfilled
capture_status: not-attested
---

# ADR-0005 — Standard belongs to GNS-Foundation, products to Ulissy S.R.L.

- **Status:** Accepted
- **Decision date:** 2026-08-29

## Context

The venture has two separable assets: (1) the **standard** — the open, neutral governance/
attestation specification (CGR, the attestation wire format, the verification recipe, the
Foundation issuer identity), whose value depends on being **credibly neutral and vendor-independent**;
and (2) the **products** — the commercial AML/KYC assistant and any other GRAFOMEM-embedded
offerings that are sold. Housing both in one commercial entity would undermine the standard's
neutrality (a standard "owned by the vendor selling against it" is not a standard); splitting
them preserves the neutrality the whole CGR thesis depends on.

## Decision

**The standard belongs to GNS-Foundation; the products belong to Ulissy S.R.L.** GNS-Foundation
holds and stewards the open standard (spec, issuer key/identity, conformance); Ulissy S.R.L.
builds, sells, and contracts the commercial products that embed it
([ADR-0001](ADR-0001-sell-assistant-with-grafomem-embedded.md),
[ADR-0004](ADR-0004-ulissy-srl-eu-contracting-entity.md)).

## Consequences

- The standard stays **credibly neutral** — the Foundation issuer key and conformance authority
  sit in GNS-Foundation, not in the entity that sells products, which is exactly the
  "your reputation isn't signed by your vendor" property CGR markets on.
- Products (Ulissy S.R.L.) consume the standard on the same terms available to any third party —
  no privileged private fork — which keeps the "open standard" claim honest.
- IP, licensing, and governance must be documented per body: Foundation = spec + issuer identity +
  conformance marks; Ulissy = product code, customer contracts, commercial trademarks.
- Enables a future third-party ecosystem (others can build on the standard) without the products
  entity being a gatekeeper — supports eventual standalone-layer adoption deferred in ADR-0001.

## Open sub-questions

- What is the licensing/governance relationship between the two bodies (does Ulissy license the
  standard from the Foundation, or is it open-access with a conformance mark)?
- Who governs changes to the standard, and how is Ulissy's product influence bounded to preserve
  neutrality?
- Where do shared assets (e.g., the `com.grafomem/*` namespace, docs domains) legally sit?
- Trademark split: which marks are Foundation (standard/conformance) vs. Ulissy (product)?
