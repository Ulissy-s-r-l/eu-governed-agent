# Handoff — Grafomem / EU governed agent

**Date:** 2026-09-09 · **Purpose:** context for continuing in a new conversation
**Operator:** Camilo Ayerbe Posada — Ulissy S.R.L. (product) / GNS Foundation (standard)

> **Correction (2026-09-09):** the C-rung figure below said "C loses on seed 7"; doc 06 §2.1 records a **3-seed** run in which C loses on **one** seed — fixed. The failed-source-summaries count is raised from five to **six** to include the correction-5 MINJA verification pass, which itself misread the paper's Table 1. Corrections are visible, never silent (method rule 4).

---

## What this project is

A **governed agent assistant for EU regulated finance**. The wedge is AML/KYC
alert triage; the buyer is an MLRO or Head of Financial Crime Compliance; the
first design partner is Iccrea (Rome). Not a personal assistant.

The differentiator is **not** that the agent is more accurate. It is that every
action is attributable, scoped, and reconstructable — and that the system tells
you when it doesn't know. Competitors' models learn to agree with the analyst
because no ground truth for laundering exists.

---

## Working method — keep this

The discipline that produced everything below, and the reason it held:

1. **Spec first, then corpus, then implementations.** Never code against an
   unmerged spec.
2. **Report before implementing** on anything with a design question. Claude
   Code reports; the operator decides; then it builds.
3. **Verify against source, never summarise from memory.** This is a written
   convention in `grafomem/docs/decisions/README.md` and mirrored in
   `eu-governed-agent`'s ADR log. It exists because **six** confident
   summaries failed their source in one week — including a regulatory
   citation (AMLR Art. 18) that reached two repos and the pitch, and the
   correction-5 MINJA verification pass, which itself misread Table 1
   (reported a 57–99% attack range for the true 43.3–100%, and ">95%
   injection" for the source's "above 90% for most").
4. **Corrections are visible, never silent.** Records carry what they got
   wrong and how it propagated.
5. **Non-vacuity probes.** Every guard is proven to fail before it is trusted —
   flip the assertion, watch it break, restore. This caught two tests that
   were green and proving nothing.
6. **Signed commits, PRs unmerged.** Claude Code prepares; the operator merges.
   Production writes, key material, and schema changes affecting deployed
   verifiers require explicit approval.

**Watch for:** stacked PRs. Merging a base with `--delete-branch` auto-closes
anything stacked on it, and a closed PR whose base is gone cannot be reopened.
Retarget to `main` first. This bit twice.

---

## The thesis (arrived at five times independently)

> A system that trusts an **account** of what happened, rather than a **channel
> that can contradict it**, cannot be audited.

Instances found this week, all from unrelated directions:

- AML vendors train on analyst disposition labels because no ground truth
  exists — their models learn to *agree*, not to be correct.
- Four systems record human approval as unsigned metadata (TrueForge's
  approval event, `cgr.attestation.v4`, CCR's learning transaction, grafomem's
  capture path) — because no primitive for a bound approval existed.
- CCR's admission gate read a channel's *self-reported* confidence.
- Calibration replaces N self-reports with one designated reference — it
  **relocates** the trust root, it does not remove it.
- Identity assurance: a key claims to be a person; someone must vouch,
  extrinsically.

The refined form: **every verifying system bottoms out in something trusted
for reasons outside itself. The engineering question is how few such anchors
you need and whether they are auditable.**

---

## Repos

| Repo | Visibility | Holds |
|---|---|---|
| `GNS-Foundation/grafomem` | **public** | the standard: specs, decision records, conformance corpora, reference verifier |
| `GNS-Foundation/grafomem-internal` | private | working material, runbooks, incident records, paper drafts |
| `GNS-Foundation/geiant` | public | agent runtime, delegation certs, audit chain, enforcement |
| `Ulissy-s-r-l/eu-governed-agent` | private | product: brief, ADRs, roadmap, B2 spec, CCR research |

**ADR-0005 boundary:** the standard belongs to GNS-Foundation, products to
Ulissy S.R.L. Commercial and product decisions do not go in the public repo.
This has needed correcting three times — check placement every time.

---

## State of the standard (essentially complete)

- **`cgr.attestation.v4`** — specified, 58-vector conformance corpus, two
  independent implementations (JS reference + `@geiant/core`) passing in both
  modes. **Live in production** since the emission bump.
- **`cgr.cosign.v1`** — the two-party co-signature envelope that closes the
  two-actor gap. Specified, amended twice by its own implementations, 28-vector
  corpus, two independent verifiers, zero verdict disagreements.
  **Published as `@gns-foundation/cgr-verify@0.5.0`** and consumer-verified
  from a clean install.
- **Foundation decision records 0001–0011** on `main`.

### Key design facts worth not re-deriving

- The cosign envelope is **nested**, not parallel: the system signs *including*
  the approver signature. Parallel detached signatures would let the approval
  block be lifted out with the record still verifying.
- Strippability, stated honestly: stripping produces an **invalid** record; an
  approver-less bound record is **non-conformant**; a compromised issuer can
  mint a fresh approver-less record — **detectable, not preventable**.
  Tamper-evident and conformance-enforced, not tamper-proof.
- **Predicate-based conditional required-ness** (0010): a profile can require
  the approver signature only when a predicate over `content_body` holds.
  An unresolvable predicate **MUST reject** — this was a fail-open, found by
  writing the corpus before any implementation.
- **Issuer pinning** (0011): the verifier MUST check `issuer_key_id` against a
  caller-supplied trusted set. No default, no trust-everything path. Found
  because two implementations *agreed* — and the agreement was luck, not
  specification. That is the more useful finding: agreement normally reads as
  confirmation.
- Assurance tier is **surfaced, never gated** — enforcement is the relying
  party's job.

---

## State of the product (not started)

**B3 — the AML triage assistant — does not exist.** Not a line.

- **B2** (disposition evidence schema) is authored in
  `eu-governed-agent/docs/specs/`. Content fields specified; the approver
  socket was blocked on `cgr.cosign.v1`, which is **now unblocked**.
- **B0.0 — the LEI for Ulissy S.R.L. — not started.** External latency,
  blocks nothing, hard prerequisite for any bank's DORA Register of
  Information. Should be running in the background.
- **B0.1–0.6** (the DORA pack) — not started. Deliberately last.
- **Iccrea** — not contacted.
- **Harness decision** — open. TrueForge (MIT, TypeScript agent harness) is a
  candidate; its approval event records status and reason but **no actor**,
  which was one of the four instances of the thesis.

---

## Decisions already taken (do not relitigate)

- **ADR-0008 (product):** B3 is built as the best possible **client of a
  general ledger**, not the ledger's only client. No AML-specific assumptions
  in the write path. Anything the assistant needs that the ledger cannot
  express becomes a Foundation record.
- **ADR-0009 (product):** B3 is a **Level 2** governed assistant and makes **no
  learning claim**. AML emits no correctness signal: ~2% of alerts become SARs,
  ~4% of SARs get any feedback, that feedback is outcome-blind by statute, and
  the no-file branch (the large majority) gets nothing. **Never tell a bank the
  agent learns** — your own record contradicts it.
- **Entity:** Ulissy S.R.L. contracts with banks; single Italian entity serves
  all 27 Member States.
- **Markets:** Italy first, then Germany and the Netherlands in parallel.
- **DORA:** ICT third-party provider status accepted by design; assume
  Art. 30(3) applies.
- **Regulatory basis:** AMLR Art. 11 + Recital 38 + AI Act Art. 14 — **not**
  Art. 18, which is *Outsourcing* and mandates no signature. That miscitation
  reached two repos before verification caught it.

---

## Open, in priority order

1. **Gap 3a — a verified named person.** The cosign envelope attributes a
   *key*; binding it to an accountable individual is unresolved. Research
   concluded: **bank-vouches** (the bank asserts its own MLRO's identity and
   role) is the working answer, with QES as an optional persuasion upgrade —
   **no EU rule mandates a signature technology**. Gated on Iccrea discovery.
2. **Nothing has ever run against a real Grafomem Cloud endpoint.**
   ADR-0010's honesty limit: all durable-tier verification is against an
   in-memory backend. Whether a live GMP honours `valid_until`, native
   `supersede`, and the retrieve semantics is **unverified** — and the
   three-way audit join is the thing a supervisor would be shown.
3. **`cgr.disposition.v1`** — B2's general profile. Specified in shape, not
   authored. The **profile registry does not exist** (§11 Q3); the corpus pins
   a test fixture marked as not-the-contract.
4. **Deploy downtime** — every grafomem redeploy takes production down ~25–30
   min (single replica, no healthcheck-gated handoff). A DORA operational
   resilience question, and it invalidates "rollback is immediate."
5. **`tenant_api_keys.api_key` is plaintext** — one DB read compromises every
   tenant. Fix shape scoped: HMAC-SHA256 with a pepper, hash in place, portal
   shows the key once.
6. **Python verifier not on PyPI** — only the JS side is published.

---

## CCR (Continuous Cognitive Runtime) — parallel research

A specification series (docs 00–08) plus a working Python implementation in
`eu-governed-agent/research_CCR/ccr-agent`. **Unpublished, deliberately** —
differentiating because unbuilt.

**Built:** capture, evaluation, ledger with Merkle checkpoints, admission gate,
propose/validate/commit, forward-only revert, co-signed high-risk approval,
confidence floor, consolidation, calibration, contradiction detection
(`contested`), causal graph store and bounded admission consumption. ~86 tests
plus a property harness.

**Findings worth keeping:**

- **The C rung was falsified.** "Structured experience > raw retrieval" does
  not survive an honest baseline (C−B = +0.011 mean; 3 seeds, C loses on one). The
  differentiator is **evaluation-channel integrity under adversarial input**,
  not structure. Recorded in doc 06 §2.1.
- **§3.1's four tiers** (A: mechanical oracle / B: named human reference /
  C: sparse outcomes / D: frozen dispositions) are the paper's best
  contribution. *The measurable space for dynamic agentic learning is the set
  of behaviour changes for which a reference can be named.*
- **Stage-1 replay tests propensity, not instance causation.** In a
  single-step tree they coincide; multi-step, a surviving-false chain is
  constructible. A known ceiling, stated before anything depended on it.
- **Correlated forgery:** N edges from one compromised channel cost ~one root.
  Fixed with an aggregate cap (ΣΔV ≤ 0.05 against a 0.145 margin), not
  per-edge dedup — the cap bounds regardless of attack shape.
- **ADR-0010:** the durable tier holds **evidence**; CSO content is linked by
  provenance, **never copied**. Found because a mirror had been built one
  commit at a time against a rule doc 03 §1 already stated.

---

## Immediate next steps (agreed sequence)

1. **ADR-0011 / ADR-0012-candidate** — the verifier-tier decomposition and
   weight plasticity as a gated offline transaction. Docs only.
   *Open review points:* repo placement under ADR-0005 (general → grafomem,
   B3 table → eu-governed-agent); which ADR-0009 is being refined (there are
   two); the tiers are documentation until the reference registry enforces
   them; and 0012's distillation harness needs a Tier-A domain — name it.
2. **TrueForge capture-hooks spike** — one day, converts the harness question
   from opinion to fact.
3. **B3 product definition** — informed by the spike.
4. **B3 narrow slice** — one alert type, one analyst, one signed disposition
   end to end.

Background, starting now: **B0.0 (LEI)** and **gap-3a enrolment**.

---

## The honest position

Seven days produced a standard that is specified, corpus-tested,
dual-implemented, published, and live in production — and a product that does
not exist. That was a deliberate choice, made twice, with the reasoning
recorded. But the substrate keeps generating tractable, satisfying problems and
the product has no such gravity because it is unstarted.

The shortest honest path to something demonstrable: wire to a real Grafomem
Cloud tenant (retires ADR-0010's honesty limit), then build B3 narrow.
