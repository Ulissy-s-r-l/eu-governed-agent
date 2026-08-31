---
decision_date: 2026-08-29
record_date: 2026-08-31
provenance: backfilled
capture_status: not-attested
---

# ADR-0003 — Accept DORA ICT third-party provider status; design for Art. 30(3)

- **Status:** Accepted
- **Decision date:** 2026-08-29

## Context

Under the EU Digital Operational Resilience Act (DORA), a company supplying ICT services to
financial entities is an **ICT third-party service provider**, and the contracts with those
financial entities must satisfy DORA's contractual requirements — including **Article 30(3)**,
the enhanced provisions for services supporting **critical or important functions** (audit and
access rights, incident cooperation, subcontracting conditions, exit strategies, service levels,
etc.). We could try to position out of scope, or accept the status and build for it.

## Decision

**Accept ICT third-party service-provider status under DORA, and design the product and
contracts for Article 30(3)** from the outset — treating the AML/KYC assistant as potentially
supporting a critical or important function at the customer, and meeting the enhanced contractual
requirements rather than arguing scope.

## Consequences

- Customer contracts (via Ulissy S.R.L., [ADR-0004](ADR-0004-ulissy-srl-eu-contracting-entity.md))
  must carry the DORA Art. 30(2)/(3) clauses: audit & access rights, incident reporting/cooperation,
  subcontracting controls, exit/transition support, defined service levels, data/location terms.
- The product must be *evidenceable* for resilience and auditability — GRAFOMEM's attestation +
  audit chain ([ADR-0001](ADR-0001-sell-assistant-with-grafomem-embedded.md)) become directly
  load-bearing for the DORA story (auditable decisions, incident traceability).
- Register-of-information obligations: customers must list us in their ICT-provider register;
  we should make being registered easy (standard clauses, an information pack).
- Accepting the status is a **sales asset**, not just a cost: "DORA-ready, Art. 30(3)-designed"
  is a differentiator into risk/compliance buyers — and it's coherent with the embedded-governance
  positioning.
- Ongoing obligation, not one-time: subcontractor chain (incl. any LLM/cloud providers) must be
  disclosed and controlled to remain compliant.

## Open sub-questions

- Do we self-classify as supporting a "critical or important function," or leave that to each
  financial-entity customer's own determination (which drives whether 30(3) applies)?
- Could we ever be designated a **critical ICT third-party provider** (direct ESA oversight) at
  scale, and does that change the design?
- Which subcontractors (LLM inference, hosting) must be named, and what exit strategy do we
  commit to contractually?
- Do the DE/NL regimes add anything beyond DORA that Italy-first work should pre-empt?
- **Is Ulissy S.R.L.'s current corporate form / capitalization adequate to carry Art. 30(3)
  liability at target contract sizes?** *(Relocated from ADR-0004 — a DORA-liability question, not a
  contracting-entity one.)* A bank's third-party-risk function will assess this **directly**, so it
  must be answered **before** the DORA pack (P4) is credible — not discovered inside a client's due
  diligence. Not answerable in-house; needs an Italian commercialista and likely counsel (see
  `docs/roadmap.md` P4).
