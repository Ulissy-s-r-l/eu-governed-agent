---
status: proposed
decision_date:
record_date: 2026-09-09
provenance: contemporaneous
capture_status: not-attested
---

# ADR-XXXX — Weight plasticity is a gated, offline, revertable transaction — never an online reflex

- **Status:** **Proposed** (unnumbered; the ADR number is assigned on acceptance — do not cite a
  number for this record until then)
- **Decision date:** — (proposed)

> **Paired with** [ADR-0011](ADR-0011-verifier-tier-decomposition.md): 0011 says **where** learning is
> real (the four tiers); this record says **how deep** it is allowed to go. Neither stands alone.
> **Source text:** the distillation path is taken from the CCR synthesis paper §11
> (`research_CCR/Continuous-Cognitive-Runtime.md`), kept aligned so the two cannot drift (this PR
> updates §11 to the two-source formulation below).
> **Placement:** CCR is deliberately unpublished research (the project handoff), a category outside
> [ADR-0005](ADR-0005-standard-gns-foundation-products-ulissy.md)'s standard/product split; this
> record lives in `eu-governed-agent` **by decision, not by default**.

## Context

CCR keeps learning in a versioned, validated cognitive state and freezes the model weights. The
question this record settles is whether weights may *ever* change, and if so under what discipline.
The answer is that weight plasticity is admissible **only** as a gated, offline, revertable
transaction — the same machinery as any ΔC — and **never** as an online reflex on live experience.

## Decision

**The distillation pipeline.**

    experience/corpus → training corpus → offline weight update
      → weight admission through the same transaction machinery as any ΔC,
        with human co-signature on admission (cgr.cosign.v1; risk == "high" by definition)
      → deployment as a new versioned v_M, forward-only rollback
        (prior weights are an ancestor in the state DAG; reverting is a new commit, not a time machine)

**Corpus admissibility — two sources, stated normatively.** The distillation corpus has **exactly two
admissible sources**:

1. **Gate-passed experience**, restricted to **Tier-A/B** domains — ledger experiences that have
   already passed the experience-admission gate.
2. **Supervised-constructed examples that are not experience at all** — e.g. refusal behaviour trained
   from *correct examples* of refusal, authored and approved as a curated set, entering through
   ordinary supervised construction. (This is what synthesis §11 means by "outside the gate.")

**Tier-D experience is admissible through neither source.** Weight admission then gates the resulting
update **as a whole**. This is how §11 coheres with "no Tier-D corpus admissible under any gate": a
Tier-D *disposition* may be taught only via source (2) from correct examples — never from Tier-D
*experience* — and the trained update still faces weight admission. (The earlier phrase "the same
admission discipline as any other learning" is **dropped** in favour of this two-source language, in
both this record and §11.)

**The online reflex is rejected twice over.** (1) No reference exists at reflex timescale to gate
against — a weight update with no named reference is **inadmissible by construction** under ADR-0011's
standing rule. (2) Weights are **undiffable** — there is nothing to revert *to* in the contents, only
the whole prior artifact — which is exactly why the update must be **offline and gated**, so it is
verifiable *first* and permitted *second*.

**Tier-D domains are frozen forever, whatever the vertical.** No corpus drawn from Tier-D *experience*
is admissible for weight updates under any gate, in any domain. AML disposition-correctness is **one
example** of a Tier-D domain — never the definition of the constraint.

## The dependency, stated plainly

**The one thing that does not exist is a training/validation harness with a reference rich enough to
gate weights — and per ADR-0011 that reference must be Tier-A.** The Tier-A domains we actually have
today, with their status:

- **The CCR simulator** (`research_CCR/ccr-agent/ccr/simulator.py`) — **in-tree**, a mechanical
  ground-truth oracle (tool-selection); the only live Tier-A domain in the CCR codebase.
- **cc-builder** — the CGR deploy/build role (CI/tests as oracle, `grafomem-cgr`); a genuine Tier-A
  domain we control, but **not wired** into the CCR distillation harness (cross-repo).
- **Meridian** — the synthetic receivables simulator (an invoice *pays or defaults*: near-total
  coverage, unambiguous binary); a **simulated-oracle** Tier-A domain, **not yet wired**, cross-repo
  (`grafomem`/CGR).

The consequence, not softened: **as written, the distillation path is a research claim about domains
we control — the simulator, and prospectively cc-builder and Meridian — not yet about the product.**
The product (B3/AML) is Tier B/D and supplies no Tier-A reference for weight gating. No other
candidate Tier-A domain was found in the tree.

## Consequences

- **CCR's answer to lifelong learning is the governed release, not the plastic layer** (build-guide §0
  gains this sentence).
- **Build guide item 20 — Distillation path** (ledger → corpus → weight admission as transaction);
  spec anchor: this record's slug; deps: 5, 6, 15, 19, and ADR-0011's Tier-A rule; Tier: horizon
  (post-Tier-3).
- Weight admission is a `cgr.cosign.v1` high-risk approval by definition — it inherits that envelope's
  co-signature and audit requirements.

## Open sub-questions

- **Corpus selection policy.** From source (1): which gate-passed Tier-A/B experiences earn
  training-set membership? From source (2): who authors, and who approves, supervised-constructed
  examples?
- **Regression-suite composition.** What must not degrade — specifically the forgetting test — before
  a weight update is admissible?
- **Who co-signs a weight admission?** (A named, accountable approver, per `cgr.cosign.v1`.)
- **Cadence.** Accumulation threshold, fixed schedule, or drift alarm?
