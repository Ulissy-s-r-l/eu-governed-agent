# 04 — Learning Transaction: Protocol, Lifecycle, and Rollback

**Continuous Cognitive Runtime (CCR) — Document 4 of the CCR specification series**
**Status:** Working draft v0.1 — personal working document, intended for later refinement toward an arXiv publication
**Depends on:** `00-CCR-SYSTEM-OVERVIEW.md` (§5.3, §7), `01-CCR-FORMAL-MODEL.md` (Defs. 6.1, 7.1–7.5, 8.4), `02-COGNITIVE-STATE-OBJECT.md` (§5 lifecycle), `03-EXPERIENCE-LEDGER.md` (record formats)
**Feeds:** `06-CCR-BENCHMARK.md`, `07-CCR-SECURITY-MODEL.md`

---

## 0. Executive Summary

This document specifies the **Learning Transaction** at protocol level: the complete lifecycle by which a candidate behavioral update travels from proposal to committed state — or to audited rejection. Documents 01–03 established the formal machinery: the guarded transition `C_{n+1} = F(C_n, X_t, E_t)`, the typed update operator ΔC, the validation predicate, and the state DAG. What remains underspecified is the *protocol*: the exact sequence of stages, the record each stage produces, the failure handling at each step, and the semantics of rollback. This document closes that gap.

The design synthesizes two mature transactional traditions, adapted to a domain neither was built for. From **database transactions**, it takes the ACID discipline: atomicity (a learning update commits in full or not at all), consistency (invariants I1–I5 are the constraint check), isolation (candidate states never leak to readers), and durability (committed state is content-addressed and provenance-sealed). From **long-running saga patterns**, it takes the compensation model: because validation can take minutes or hours (simulation, replay, human review), the learning transaction cannot hold a lock for its duration; instead, it stages work in a candidate space and applies compensation — discard, annotate, alert — if a late stage fails. The result is a protocol that is transactional in its *commit semantics* but saga-like in its *execution*, which is the only honest shape for learning pipelines that include simulation and human approval.

A deliberate departure from both traditions: the Learning Transaction has **no rollback of the transaction itself.** Databases roll back uncommitted state; sagas compensate partially executed steps. The Learning Transaction instead has *forward-only recovery*: a harmful committed update is never un-committed (the commit is a fact of history), but a *new* transaction is issued whose payload is a revert (document 01, Def. 8.4). This preserves the integrity of the audit trail — the harmful commit and its reversal are both visible — and it is the protocol-level expression of the ledger's append-only discipline applied to the state DAG.

---

## 1. Transaction Record

The Learning Transaction is a first-class record, the `tx:` object that other documents reference. Its schema:

```json
{
  "tx_id":        "tx:sha256:…",
  "type":         "learn | revert | merge | recalibrate",
  "parent_state": "cso:sha256:…",
  "candidate_state": "cso:sha256:…",

  "motivation": {
    "experiences":  ["exp:sha256:…"],
    "gate_decision": "gd:sha256:…",
    "admission":     {"V_score": 0.74, "threshold": 0.60, "components": {"info_gain": 0.31, "surprise": 0.18, "risk": -0.12, "trust": 0.37}}
  },

  "delta": {
    "op":      "reweight | insert | deprecate | merge",
    "target":  "policy_table | skills | semantic_memory | …",
    "payload": "…",                      // typed content per document 02
    "justification": [{"exp": "…", "weight": 0.6}],
    "risk_class": "low | medium | high"
  },

  "validation": {
    "invariant_check": {"passed": true, "violations": []},
    "replay":          {"suite": "…", "contexts": 127, "regressions": 0, "improvements": 3},
    "regression_battery": {"suite": "critical-behaviors-v3", "passed": 18, "failed": 0},
    "human_approval":  {"approver": "…", "decision": "approve", "rationale": "…", "timestamp": "…"},  // SUPERSEDED — unsigned data; see note below
    "overall":         {"verdict": "commit | reject | escalate", "confidence": 0.92}
  },

  "authority": {
    "scope_version": "scope:…",
    "authorization": "permitted | escalated | denied"
  },

  "status":   "proposed | testing | validated | committed | rejected | failed",
  "timeline": {"proposed_at": "…", "validated_at": "…", "committed_at": "…"},
  "signature": "sig:gns:…"  // SUPERSEDED as the SOLE signature — see note below
}
```

> **Superseded (2026-09-07) — the approval envelope is now `cgr.cosign.v1`.** As drawn above,
> `validation.human_approval` is **unsigned data** and `signature` is the **single, system** signature.
> That is exactly the two-actor gap recorded in `GNS-Foundation/grafomem` decision **0009** (accepted
> 2026-09-06) and resolved by **`cgr.cosign.v1`** (`grafomem/docs/cgr/cgr-cosign-v1-spec.md`): a general
> two-party co-signature envelope. A learning transaction is its **approval-free** case (it approves a
> policy update while the justifying experiences stay raw), under the profile **`cgr.learning-tx.v1`**.
> Concretely, superseding the two fields above:
>
> - `validation.human_approval` becomes an **approval assertion** `{content_digest, approver_id,
>   approver_key_id, approver_act, decision_date, record_nonce, [agent_draft_digest]}` **plus an
>   inner approver signature** over `grafomem.hitl.approval.v1: ‖ JCS(assertion)`, produced with the
>   approver's **self-custodied** key. `content_digest` is `BLAKE2b-256(JCS(content_body))` over the
>   candidate delta + `motivation.admission` + the validation evidence + rationale.
> - `signature` (the single `sig:gns:…`) becomes the **outer `system_signature`**, computed **last** over
>   the whole record **including** the approver signature (nested, not parallel — §2.3 of the cosign spec).
> - Required-ness is the §5.1 predicate `required_when {field: "risk", op: "eq", value: "high"}`: a
>   **high-risk transaction lacking a valid approver signature is REJECTED at validation.** (This is
>   `HighRiskUpdate ⇒ RequiredApproval`, now *enforced* rather than asserted — the property in doc 07 §7.)
> - **Honest limits** (cosign register): stripping the approval yields an *invalid* transaction; an
>   approval-less high-risk transaction is *non-conformant*; a compromised system key can still mint a
>   fresh approval-less transaction — *detectable* against externally-held commitments, not preventable.
>   **Not resolved:** whether the approver key is a *verified named person* (0009 gap 3a).
>
> Implemented in `ccr-agent/ccr/cosign.py` + `LearningEngine.commit`; acceptance in
> `tests/test_approval.py`. The schema above is retained for continuity; treat the two flagged fields as
> the cosign envelope, not as unsigned metadata.

Three fields carry the protocol's core semantics. **`motivation.admission`** records the full admission computation, not just the verdict: the gate's component scores and the threshold in force. This is the audit trail for the admission function itself — if the gate is later found to be miscalibrated, its history of decisions (stored in the ledger as `gate_decision` records, document 03 §3.2) can be replayed under corrected thresholds. **`validation`** is the evidence bundle: each stage's inputs, outputs, and verdicts, stored so that a commit can be re-verified years later without re-running anything. **`status` and `timeline`** implement the lifecycle state machine (§3), with the invariant that `committed` implies `validated` and `validated` implies non-empty `validation` — a state-transition precondition the protocol enforces mechanically.

---

## 2. The Protocol: Nine Stages

The Learning Transaction proceeds through nine stages, five on the hot path and four on the cold path. The hot-path stages (1–2) are bounded-latency and never block on learning (P8). The cold-path stages (3–9) are asynchronous, may involve simulation and human review, and are the only stages that can be slow.

| # | Stage | Actor | Latency class | Failure mode |
|---|---|---|---|---|
| 1 | **Capture** | Experience Capture | Hot path (ms) | Record dropped; ledger retains raw telemetry for retry |
| 2 | **Evaluate** | Outcome Evaluator | Hot path (ms–s) | Evaluation deferred; experience marked `pending_evaluation` |
| 3 | **Admit** | Learning Engine (gate) | Cold path (ms) | Reject → ledger `gate_decision`, no further action |
| 4 | **Propose** | Learning Engine | Cold path (s) | No candidate formed → transaction terminates as `no_op` |
| 5 | **Simulate / Replay** | Learning Engine | Cold path (s–min) | Replay regressions → reject; sandbox unavailable → escalate |
| 6 | **Validate** | Learning Engine + invariant checker | Cold path (s) | Invariant violation → reject; human approval required → escalate |
| 7 | **Authorize** | Authority guard | Cold path (ms) | Out of scope → reject; escalate class → human review |
| 8 | **Commit** | Cognitive State Manager | Cold path (ms) | Atomic write; crash mid-commit → idempotent retry |
| 9 | **Version + Provenance** | Versioning, Provenance Recorder | Cold path (ms) | Ledger append fails → transaction held in `committed_pending_provenance` until sealed |

The stage boundaries are load-bearing. Stages 1–2 produce the experience record; stages 3–7 are the *guarded transition* of document 01 (§7.2) decomposed into operational steps; stages 8–9 are the atomic write and its audit sealing. The critical property is that **no stage after 2 has any effect on the hot path** until stage 8 completes — the isolation guarantee. A candidate state exists in a sandbox namespace, invisible to readers, and is materialized as the new committed state only at commit.

### 2.1 Stage 3: Admission

Admission is the first cold-path decision and the cheapest rejection point. The Learning Engine computes the learning-value functional `V(X_i)` (document 01, §3.2) against the current committed state, compares it to the risk- and calibration-dependent threshold `η`, and emits a binary verdict. The full computation — component scores, threshold, verdict — is written to the ledger as a `gate_decision` record (document 03, §3.2), so the gate is auditable in both directions. Rejection is *terminal* for this transaction but not for the experience: the record remains in the ledger, tagged `rejected_at_admission`, and may be resubmitted later under better calibration or corroborating evidence (document 01, §6, non-deletion property).

### 2.2 Stage 5: Simulation and Replay

Replay is the transaction's most distinctive stage and the one with no database analogue. Given the candidate state `Ĉ = C_n ⊕ ΔC` and a held-out set of historical experiences `ℋ ⊆ ℒ`, the Learning Engine re-executes each `X_j ∈ ℋ` under `Ĉ` — the counterfactual question "what would the candidate have done here?" — and compares the candidate's counterfactual policy distribution `π̂(· | S_j, Ĉ)` against the recorded outcome `O_j` and the incumbent's counterfactual `π(· | S_j, C_n)`. The candidate passes only if it does not materially degrade historically successful contexts beyond a tolerance `ε_regress`. This is the formal "do no harm" check: a candidate that improves the motivating context but silently degrades three others is rejected, with the regression list recorded in the validation bundle.

Replay is computationally expensive — it is the cold path's main cost center — and the protocol makes it *configurable by risk class*. Low-risk updates (preference tweaks, confidence floor adjustments) may skip replay or run it against a small random sample. High-risk updates (policy changes licensing new action classes) require full replay against the regression battery plus a shadow deployment (§4). The tolerance `ε_regress` and the sampling policy are versioned state, not protocol constants — the system learns how much validation is enough, and that learning is itself auditable.

### 2.3 Stage 8: Commit

Commit is the only stage that mutates committed state, and it is atomic: the Cognitive State Manager constructs the new CSO by applying ΔC to a snapshot of `C_n`, runs the invariant check (Obligation 7.4) one final time against the constructed object, computes the commitment hash (Def. 8.1), appends the transaction record to the ledger, and publishes the new state as the active version. The operation is idempotent — retrying a commit with the same `tx_id` produces the same state or fails cleanly — which makes crash recovery straightforward: a commit interrupted before publication is simply retried from the transaction record.

The commit stage is where the hot path *first sees* the update. Before commit, readers see `C_n`; after commit, they see `C_{n+1}`. There is no intermediate visible state. This is the isolation guarantee in its operational form: the hot path never reads a half-constructed candidate, and the transition from old to new behavior is a single atomic pointer swap, not a gradual drift.

---

## 3. The Lifecycle State Machine

The transaction's status field implements a finite state machine, the `OBSERVED → EVALUATED → CANDIDATE → TESTING → VALIDATED → COMMITTED` lifecycle of the roadmap, extended with the failure states:

```text
PROPOSED
   │ (admission pass)
   ▼
CANDIDATE
   │ (replay + regression)
   ▼
TESTING
   │ (invariant check + human approval if required)
   ▼
VALIDATED
   │ (authorization)
   ▼
COMMITTED  ──────►  (terminal; state DAG extended)

Any stage may instead transition to:
   REJECTED  (gate or validation verdict; terminal, research-visible)
   FAILED    (infrastructure error; terminal, retryable)
   ESCALATED (human review required; pauses until approval)
```

Two properties of this machine deserve emphasis. **Terminal states are absorbing:** once `COMMITTED`, `REJECTED`, or `FAILED`, the transaction record is immutable — a new transaction is required to change anything. This is the protocol-level enforcement of forward-only recovery. **Every transition is recorded:** the ledger's `gate_decision` and `annotation` record types (document 03, §3.2) capture not just the final status but the path, so the lifecycle itself is auditable. The machine is deliberately small — six states plus three terminals — because the trust-critical code path must be small enough to verify (document 00, §6.9).

---

## 4. Deployment Topologies: Shadow, Canary, and Branch

The Learning Transaction's validation stage admits three deployment topologies, borrowed from ML deployment practice and mapped onto the state DAG:

**Shadow validation** (the default for medium- and high-risk updates): the candidate state `Ĉ` runs alongside the incumbent `C_n` on live traffic, but its actions are logged, not executed. The two states' decisions are compared on the same inputs — the shadow sees what the incumbent saw and says what it would have done — and divergence is measured before any commit. This is the ML shadow-deployment pattern ([JFrog ML](https://www.qwak.com/post/shadow-deployment-vs-canary-release-of-machine-learning-models), [APXML](https://apxml.com/courses/monitoring-managing-ml-models-production/chapter-4-automated-retraining-updates/advanced-deployment-patterns)) lifted from model weights to cognitive state. In CCR, shadow validation is a *branch*: the candidate is a child of `C_n` in the DAG, its shadow run generates experiences tagged `shadow: true`, and the branch is either merged (commit) or abandoned (no merge; the branch tip remains research-visible).

**Canary validation** (for high-risk updates after shadow pass): the candidate state is committed but with a restricted authority scope — it may act only in a bounded context region or for a bounded fraction of decisions, with the incumbent handling the rest. This is the ML canary pattern ([MarkTechPost](https://www.marktechpost.com/2026/03/21/safely-deploying-ml-models-to-production-four-controlled-strategies-a-b-canary-interleaved-shadow-testing/)) adapted to state: the canary is a committed state with a narrowed `authority_scope`, monitored for a defined window, and either promoted (scope widened) or reverted. The authority guard (document 01, §10.2) is what makes canary states safe: the canary cannot exceed its narrowed scope even if its policies would like to.

**Branch-and-compare** (for A/B cognitive policies): two candidate states are branched from the same parent, run in parallel (shadow or canary), and compared on a defined metric. The winner is merged; the loser is abandoned. This is the roadmap's Phase 6 branching made operational, and it is the natural topology for the experimental ladder of document 06 — System D vs. System E is a branch-and-compare.

---

## 5. Rollback: Forward-Only Recovery

Rollback is not a transaction state but a *new transaction type*: `type: revert`, whose payload is a full-state replacement with an ancestor's content. The semantics are forward-only (document 01, Def. 8.4): the revert commit is appended to the DAG with its parent being the *current* state, not the target ancestor. History is never rewritten; the harmful commit and its reversal are both visible.

The revert transaction's validation is deliberately lighter than a learning transaction's: the invariant check runs (the restored content must be well-formed), replay is skipped (the ancestor state is already validated), and authorization is checked against the *current* scope (the agent must still hold authority to act under the restored state). This asymmetry is justified: revert is a *recovery* operation, not a *learning* one, and its risk profile is different — the failure mode is not "bad new behavior" but "stale restored behavior," which is why the revert transaction records the incident evidence in its justification field, so the rollback itself is explainable.

For the case where a harmful update is discovered *after* subsequent benign updates have been committed on top of it, the protocol supports **selective revert**: the revert transaction targets the ancestor *before* the harmful update, and the benign updates are re-applied as new learning transactions (with their original justification and validation records cited as precedent). This is the saga compensation pattern in reverse: instead of compensating a failed step, the system compensates a *discovered-harmful* step by replaying the good steps that followed it. The process is auditable end-to-end: the revert transaction cites the harmful transaction, the re-application transactions cite the revert, and the full recovery is a connected subgraph of the DAG.

---

## 6. Failure Handling and Idempotency

The protocol is designed for partial failure at every stage. Each stage's output is a record written to the ledger *before* the next stage begins, so a crash at any point leaves a resumable trail. The idempotency key is the transaction ID: retrying any stage with the same `tx_id` is a no-op if the stage already succeeded. Compensation (the saga term) is minimal by design: the only stage with external side effects is commit, and commit is atomic, so there is nothing to compensate before commit and nothing to compensate after — the failure model is "retry or reject," never "undo partial work."

The one exception is human approval (stage 6): an approval request that is never answered leaves the transaction in `ESCALATED` indefinitely. The protocol handles this with a timeout: after a configurable window, the transaction transitions to `FAILED` with reason `approval_timeout`, and the candidate is discarded. The timeout is versioned state, not a constant, because the right window depends on the deployment context — a personal assistant may wait hours, a trading agent milliseconds.

---

## 7. Summary and Handoff

The Learning Transaction specified here is a nine-stage, saga-shaped, ACID-commit protocol with forward-only recovery, shadow/canary/branch validation topologies, and a six-state lifecycle machine. Its design is the operationalization of document 01's guarded transition: the guard conjunction (admission ∧ validation ∧ authorization) is now a pipeline with defined stages, records, and failure modes. The protocol's two borrowings are load-bearing: from databases, the atomic commit and invariant enforcement; from sagas, the staged execution and the refusal to hold locks across long-running validation. The departure from both — forward-only recovery instead of rollback — is the protocol-level expression of the append-only discipline that runs through the entire series.

Document 05 (`05-CAUSAL-COGNITIVE-GRAPH.md`) specifies the causal machinery that the transaction's replay stage queries, and document 06 (`06-CCR-BENCHMARK.md`) specifies the experimental ladder that tests whether the transaction's guarantees translate into measurable learning improvements.

*Document 04 of the CCR series. Previous: `03-EXPERIENCE-LEDGER.md`. Next: `05-CAUSAL-COGNITIVE-GRAPH.md` — the causal representation and its role in validation.*
