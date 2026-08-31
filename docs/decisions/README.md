# Decision log — EU Governed Agent (AML/KYC wedge)

Architecture/strategy decision records (ADRs), one file per decision. ADR-0001…0006 were
**made in conversation on 2026-08-29** and recorded here on 2026-08-31 (backfilled); ADR-0008 was
decided and recorded on 2026-08-31. **None are yet attested to GRAFOMEM Cloud** — capture is
deferred (see the [capture note](#capture)). Each ADR's `capture_status` front-matter field is the
source of truth for its state.

| ADR | Title | Status | Decision date |
|---|---|---|---|
| [0001](ADR-0001-sell-assistant-with-grafomem-embedded.md) | Sell the assistant with GRAFOMEM embedded (not the layer standalone) | Accepted | 2026-08-29 |
| [0002](ADR-0002-sequenced-beachheads-italy-then-de-nl.md) | Sequenced beachheads: Italy first, then DE + NL in parallel | Accepted | 2026-08-29 |
| [0003](ADR-0003-accept-dora-ict-provider-art-30-3.md) | Accept DORA ICT third-party provider status; design for Art. 30(3) | Accepted | 2026-08-29 |
| [0004](ADR-0004-ulissy-srl-eu-contracting-entity.md) | Ulissy S.R.L. is the contracting entity for all EU markets | Accepted | 2026-08-29 |
| [0005](ADR-0005-standard-gns-foundation-products-ulissy.md) | Standard belongs to GNS-Foundation, products to Ulissy S.R.L. | Accepted | 2026-08-29 |
| [0006](ADR-0006-defer-eic-digital-europe-assessment.md) | EIC/Digital Europe assessment deferred pending a first reference | Accepted (defer) | 2026-08-29 |
| [0007](ADR-0007-cgr-governance-domain.md) | CGR governance domain + backfill (relocated to Foundation) | **Relocated** → `GNS-Foundation/grafomem` docs/decisions/0002 | — |
| [0008](ADR-0008-b3-best-client-of-general-ledger.md) | B3 is built as the best possible client of a general ledger | Accepted | 2026-08-31 |

*Numbering: `0007` is skipped-in-place — it was used and relocated to the Foundation. Numbers are permanent; `0008` is the next record.*

## Format

Each ADR carries: title, status, decision date, context, decision, consequences, and open
sub-questions. Statuses: **Proposed** → **Accepted** → (later) **Superseded by ADR-NNNN** /
**Deprecated**. To change a recorded decision, add a new ADR that supersedes it rather than
editing the old one in place.

## Capture

These decisions are **intended** to be attested to GRAFOMEM Cloud via `grafomem-cgr` as
**backfilled** governed decisions — carrying the decision date and the capture timestamp as
**distinct** fields, flagged `backfilled` / non-contemporaneous so the record never implies
contemporaneous capture. **That attestation has NOT happened yet — capture is deferred** (every
ADR here shows `capture_status: not-attested`). It is blocked on a CGR schema question — the
capture schema has no governance domain and cannot express backfill — now recorded upstream as
`GNS-Foundation/grafomem` → `docs/decisions/0002`. Once that resolves, the decisions can be attested
honestly; until then they stand on the **signed git history** of this repo.
