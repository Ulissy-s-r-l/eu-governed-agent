# Decision log — EU Governed Agent (AML/KYC wedge)

Architecture/strategy decision records (ADRs), one file per decision. All six below were
**made in conversation on 2026-08-29** and recorded here (and attested to GRAFOMEM Cloud) after
the fact — see each ADR's decision date and the [capture note](#capture) below.

| ADR | Title | Status | Decision date |
|---|---|---|---|
| [0001](ADR-0001-sell-assistant-with-grafomem-embedded.md) | Sell the assistant with GRAFOMEM embedded (not the layer standalone) | Accepted | 2026-08-29 |
| [0002](ADR-0002-sequenced-beachheads-italy-then-de-nl.md) | Sequenced beachheads: Italy first, then DE + NL in parallel | Accepted | 2026-08-29 |
| [0003](ADR-0003-accept-dora-ict-provider-art-30-3.md) | Accept DORA ICT third-party provider status; design for Art. 30(3) | Accepted | 2026-08-29 |
| [0004](ADR-0004-ulissy-srl-eu-contracting-entity.md) | Ulissy S.R.L. is the contracting entity for all EU markets | Accepted | 2026-08-29 |
| [0005](ADR-0005-standard-gns-foundation-products-ulissy.md) | Standard belongs to GNS-Foundation, products to Ulissy S.R.L. | Accepted | 2026-08-29 |
| [0006](ADR-0006-defer-eic-digital-europe-assessment.md) | EIC/Digital Europe assessment deferred pending a first reference | Accepted (defer) | 2026-08-29 |
| [0007](ADR-0007-cgr-governance-domain.md) | CGR governance domain + backfill (relocated to Foundation) | **Relocated** → `GNS-Foundation/grafomem` docs/decisions/0002 | — |

## Format

Each ADR carries: title, status, decision date, context, decision, consequences, and open
sub-questions. Statuses: **Proposed** → **Accepted** → (later) **Superseded by ADR-NNNN** /
**Deprecated**. To change a recorded decision, add a new ADR that supersedes it rather than
editing the old one in place.

## Capture

Each decision is also attested to GRAFOMEM Cloud via `grafomem-cgr` as a **backfilled** governed
decision: the record carries the **decision date (2026-08-29)** and the **capture timestamp**
(when it was actually recorded) as **distinct** fields, and is flagged `backfilled` /
non-contemporaneous. The attestation does not imply the decision was captured on the day it was
made. See the project report for the attested decision IDs.
