---
status: accepted
decision_date: 2026-09-09
record_date: 2026-09-09
provenance: contemporaneous
capture_status: not-attested
---

# ADR-0011 — "Did the agent learn?" is well-posed only against a named reference: the four-tier decomposition

- **Status:** **Accepted**
- **Decision date:** 2026-09-09

> **Refines** [ADR-0009](ADR-0009-b3-level-2-governed-assistant-no-correctness-signal.md): 0009's
> *Level 2* maps to **Tier B**, and 0009's finding that *"AML does not emit a correctness signal"* is
> the **Tier-D property** of the disposition-correctness domain. 0009 already forbids overclaiming
> against that property, and its claim line — *a disposition's CGR score stays UNPROVEN on
> analyst-agreement alone* — stands unchanged and is stronger than any restatement here.
> **Paired with** [ADR-weight-plasticity-gated-offline-transaction](ADR-weight-plasticity-gated-offline-transaction.md)
> (Proposed): this record says **where** learning is real; that one says **how deep** it may go.
> Neither stands alone.
> **Source text:** the tier definitions are taken from the CCR synthesis paper §3.1
> (`research_CCR/Continuous-Cognitive-Runtime.md`); the two are kept aligned deliberately so they
> cannot drift.
> **Placement:** CCR is deliberately unpublished research (the project handoff), a category outside
> [ADR-0005](ADR-0005-standard-gns-foundation-products-ulissy.md)'s standard/product split; this
> record lives in `eu-governed-agent` **by decision, not by default**.

## Context

CCR treats learning as a guarded transaction, and P4 makes the evaluator independent of the learner.
Implementation forced the prior question P4 does not answer: an independent evaluator evaluates
*against what?* "Did the agent learn?" is not a well-posed question until a **reference** is named — a
thing the change can be measured against that is not the learner's own say-so.

This is the runtime-layer form of a problem the RL-with-verifiable-rewards (RLVR) literature has been
moving toward: the frontier has shifted from *"make the evaluator independent of the policy"* to
*"find a reference that survives being optimized against"* — the verifier, not the policy, becomes the
attack surface, and the Rubrics-as-Rewards line is one attempt to supply a reference that does not
collapse under optimization pressure. The tier decomposition below is that insight applied where CCR
lives: at the runtime learning layer, per domain.

## Decision

The space of behaviour changes **partitions into four tiers by reference availability**, each with a
different honest claim (synthesis §3.1):

- **Tier A — verifiable by construction.** A mechanical oracle exists: tests pass, builds compile,
  transactions reconcile, invariants hold. Learning claims are **real** and the admission gate's
  numbers **mean what they say** — the reference is the environment itself.
- **Tier B — human-as-reference.** Correctness is a judgment. The agent can learn *a named
  reference's* documented patterns, preferences, and procedural completeness — **measurably** — but a
  declining override rate is an **alarm to investigate, not a KPI to optimize** (Goodhart applies to
  the reference as much as to the learner). P4 answers **who** evaluates; the tier answers **against
  what**.
- **Tier C — sparse outcomes.** Outcomes arrive rarely and late. Calibration claims are licensed
  **only on the slice where outcomes exist**, never across the domain.
- **Tier D — disposition correctness.** The right behaviour is a fixed disposition (refusal classes,
  hard constraints). The correct measurement is **undefined-not-zero**, permanently: the absence of a
  learning signal is by design. These domains are **frozen, not trainable**.

**Standing rule — every learning claim ships with its reference named.** A claim without a named
reference is not registered (this is the rule §7 of the paper obeys for every hypothesis).

### Tier-B boundary (normative — MUST NOT)

A Tier-B learner **may** learn documented procedure, evidence-assembly completeness, and the bank's
*written* policy. It **MUST NOT** learn the analyst's **disposition tendencies** (the close/escalate
lean). Disposition correctness is **Tier-D material**, and learning to reproduce the analyst's
disposition is exactly the failure mode this project exists to avoid — *"models learn to agree with
the analyst, not to be correct"* (ADR-0009). This is stated as a prohibition, not an observation.

## Illustrative appendix — the B3 instance (non-normative)

> **This appendix is ILLUSTRATIVE.** The **normative**, per-step classification for the B3 product is
> authored in the B3 product-definition document (roadmap item 6, `eu-governed-agent`) when that is
> written, and **that document supersedes this appendix.** It is included here to make the tier
> decomposition concrete, not to fix B3's contract.

The B3 invariant-core workflow — **ingest → evidence assembly → disposition drafting → analyst cosign
→ audit walk → governance reporting** — classified step by step. Through-line prohibition (all steps):
**disposition correctness is Tier D; the agent may never learn analyst disposition tendencies nor
claim a disposition is *correct*.**

| # | Step | Tier | Named reference | MAY learn (measurably) | MUST NEVER learn/claim | Deployment-dependent |
|---|---|---|---|---|---|---|
| 1 | Ingest / normalize | **A** | Alert schema + enrichment lookups (mechanical) | Extraction/normalization that reduces malformed records — verifiable against schema | That an alert is "worth attention" (→ disposition, Tier D) | Enrichment sources vary per bank |
| 2 | Evidence assembly | **B** | The bank's *written* evidence-assembly checklist/policy | Which evidence items policy requires; assembly **completeness** vs the checklist | That assembled evidence proves/disproves laundering (Tier D) | Checklist is per-bank |
| 3 | Disposition drafting | **B** (form) / **D** (correctness) | Bank's *written* narrative standard **+ the reviewer's *written return reasons*** (missing element, policy not cited, evidence not linked) | Narrative structure, required elements, policy-cited reasoning completeness. **A draft returned for a missing element is a Tier-B signal.** | The analyst's close/escalate tendencies; that the drafted disposition is correct. **A reviewer changing the disposition (close↔escalate) is a Tier-D event and MUST NOT enter any learning channel.** | Narrative standard per-bank |
| 4 | Analyst cosign | **A — verify-only, no learnable signal** | `cgr.cosign.v1` envelope (cryptographic) | *(nothing learnable — verify only:* whether a valid, bound, fresh cosign occurred*)* | That a cosign = correctness (it proves a named person approved, not that they were right) | No (standard) |
| 5 | Audit walk (three-way join) | **A — verify-only, no learnable signal** | Audit-chain + join verification (mechanical) | *(nothing learnable — verify only:* audit-trail completeness/verifiability*)* | Correctness of the underlying disposition | No (standard) |
| 6 | Governance reporting | **B** (format) **+ sparse B** (FIU report-quality feedback) | Regulatory template; the FIU's **report-quality** feedback under Directive (EU) 2024/1640 (AMLD6) — see citation note | Report completeness/format conformance; procedural response to report-quality feedback | That report-quality feedback = disposition correctness (Tier-D confusion). **Tier C is *not* licensed here** — the feedback carries no laundering outcome | Templates per jurisdiction |

**Citation note (Row 6).** The FIU report-quality feedback is classified **sparse Tier B** (the FIU is
a named human reference judging *reporting quality*, arriving annually/aggregated — sparse); it is
**not Tier C**, because Tier C requires a laundering **outcome** the feedback does not carry. The
enabling instrument is **Directive (EU) 2024/1640 (AMLD6)**; the **article number is deliberately not
pinned** — on primary-source check the OJ text and a secondary mirror disagreed on Article 42's
heading ("Feedback to obliged entities" vs "Disclosure to FIUs"), and the OJ text retrieved allows
feedback *"individual or aggregated,"* which does not match the "annual, aggregate, not each report"
characterization carried in ADR-0009. Per the primary-source convention, the instrument is cited
without an article number pending a direct OJ confirmation. **This also flags a likely miscitation in
ADR-0009 (which asserts "Art. 42, primary-verified") — recorded as a finding for a separate 0009
correction pass, not fixed here.**

## Honesty clause (required)

1. **This is documentation, not constraint — yet.** Until build-guide item 19 (the Reference
   Registry) ships, the tier scheme is **documented, not enforced**: *"a class-D signal cannot produce
   a reliability"* is true nowhere in the code today. This record states the intent; it does not imply
   the constraint is live.
2. **The positioning sentence is INTERNAL until item 19 enforces the tiers.** Until then, the
   **bank-facing** claim remains ADR-0009's *"no learning or accuracy claim"* — so the record and the
   pitch cannot diverge. The internal positioning sentence must not become external copy before the
   registry makes it true.

## Consequences

- **Positioning sentence (internal, per the honesty clause):** *"B3 does not learn whether it is
  right; it does learn your policy, your analysts' documented patterns, and its own procedural
  completeness — measurably, with the reference named."*
- **Roadmap §P3** gains a subsection stating which tiers B3 claims (Tier A on the mechanical steps,
  Tier B on the judgment steps with the named reference, Tier D on disposition correctness — no claim).
- **Build guide:** a §0 standing point, and **item 19 — the Reference Registry**: every learnable
  signal declares its class (A/B/C/D) and its reference **at registration**; a class-D signal **cannot
  produce a reliability** — enforced once built, not merely documented. (Items 16–18 — 7A port, 7B GNS
  identity, ProVerif stage 2 — are unchanged.)
- **README** one-liner.
- **Rejected alternative:** undifferentiated "learning" — a single notion of "the agent learned" with
  no reference named. Rejected because it is exactly what lets analyst-agreement masquerade as accuracy.

## Open sub-questions

- **The Tier-B alarm threshold is OPEN.** At what override-rate decline does the alarm fire, and over
  what window? This needs real analyst data and is deliberately not fixed here — setting it from
  intuition would reintroduce the Goodhart failure the tier is meant to prevent.
- What is the concrete review test that keeps a Tier-D signal (disposition tendency) out of a
  registered learnable channel, beyond the registry's declaration check?
- Which named reference is authoritative when the bank's written policy and a senior reviewer's
  return reasons disagree (Row 2/3)?
