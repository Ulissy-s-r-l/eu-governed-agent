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
| [0009](ADR-0009-b3-level-2-governed-assistant-no-correctness-signal.md) | B3 is a Level 2 governed assistant; AML does not emit a correctness signal | Accepted | 2026-09-06 |
| [0010](ADR-0010-durable-tier-holds-evidence-not-cso-content.md) | The durable tier holds evidence, not CSO content (GMP mirror rule) | Accepted | 2026-09-08 |
| [0011](ADR-0011-verifier-tier-decomposition.md) | "Did the agent learn?" is well-posed only against a named reference: the four-tier decomposition (refines 0009) | Accepted | 2026-09-09 |

*Numbering: `0007` is skipped-in-place — it was used and relocated to the Foundation. Numbers are permanent; `0012` is the next record.*

## Proposed (unnumbered — number assigned on acceptance)

Proposed records are titled by **slug**, with **no number reserved** (assigning a number before
acceptance re-creates the cross-repo numbering ambiguity — `GNS-Foundation/grafomem` already has an
in-flight `0011`). On acceptance, the record takes the next free number and moves into the table above.

| Slug | Title | Status | Decision date |
|---|---|---|---|
| [weight-plasticity-gated-offline-transaction](ADR-weight-plasticity-gated-offline-transaction.md) | Weight plasticity is a gated, offline, revertable transaction — never an online reflex (pairs with 0011) | Proposed | — |

## Format

Each ADR carries: title, status, decision date, context, decision, consequences, and open
sub-questions. Statuses: **Proposed** → **Accepted** → (later) **Superseded by ADR-NNNN** /
**Deprecated**. To change a recorded decision, add a new ADR that supersedes it rather than
editing the old one in place.

## Verifying load-bearing claims

This repo inherits the Foundation's **primary-source verification** convention (see
`GNS-Foundation/grafomem` → `docs/decisions/README.md`, "Primary-source verification"). A
**load-bearing external claim** — a regulatory citation (article number **and** heading), a legal
effect, a deployment/topology fact, a claim about another system — must be **verified against a
primary source** (EUR-Lex for EU law, the official spec text, code/deploy metadata) **before it
enters an ADR, the roadmap, or the pitch**; not a summary, a research report, or another of our own
records. Cite what was verified, at the granularity verified (heading + operative sentence; one
citation does not carry two claims). This bar is load-bearing *in the pitch*, not only in the record —
it was added after the **AMLR Art. 18** citation propagated from a research report into the roadmap and
into `grafomem` decision 0009 unchecked (Art. 18 is "Outsourcing"; the named-MLRO-is-accountable claim
is Art. 11 + Recital 38, with AI Act Art. 14 for oversight).

## Capture

These decisions are **intended** to be attested to GRAFOMEM Cloud via `grafomem-cgr` as
**backfilled** governed decisions — carrying the decision date and the capture timestamp as
**distinct** fields, flagged `backfilled` / non-contemporaneous so the record never implies
contemporaneous capture. **That attestation has NOT happened yet — capture is deferred** (every
ADR here shows `capture_status: not-attested`). It is blocked on a CGR schema question — the
capture schema has no governance domain and cannot express backfill — now recorded upstream as
`GNS-Foundation/grafomem` → `docs/decisions/0002`. Once that resolves, the decisions can be attested
honestly; until then they stand on the **signed git history** of this repo.
