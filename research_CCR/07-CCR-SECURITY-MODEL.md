# 07 — CCR Security Model: Threats, Mitigations, and Recovery

**Continuous Cognitive Runtime (CCR) — Document 7 of the CCR specification series**
**Status:** Working draft v0.1 — personal working document, intended for later refinement toward an arXiv publication
**Depends on:** `00-CCR-SYSTEM-OVERVIEW.md` (§9), `01-CCR-FORMAL-MODEL.md` (§11 invariants), `03-EXPERIENCE-LEDGER.md` (§5 verifiability), `04-LEARNING-TRANSACTION.md` (§2.2 replay)
**Feeds:** `08-GNS-CCR-INTEGRATION.md`, Phase 8 formal verification

---

## 0. Executive Summary

This document specifies the **security model** for the Continuous Cognitive Runtime: the threat model, the attack surface, the mitigation matrix, and the recovery procedures. CCR's continuous learning capability creates a new security frontier — the agent's history becomes part of its attack surface, and every mechanism that makes learning possible (memory, evaluation, policy updates, causal reasoning) is also a vector for manipulation. The architecture's defense is not perimeter-based but *structural*: the admission gate, independent evaluation, versioned reversibility, and provenance chain convert poisoning from a silent compromise into a detectable, attributable, recoverable incident.

The threat model is grounded in demonstrated attacks. MINJA (Memory Injection Attack) achieved a 98.2% mean injection success rate (above 90% in most configurations) and a 76.8% mean attack success rate (ranging 43.3–100% across victim-target pairs) against production-style memory architectures through query-only interaction — no elevated privileges, no direct memory writes, just carefully crafted user queries that the agent's own auto-extraction wrote into long-term memory ([MINJA](https://arxiv.org/html/2503.03704v4), Table 1). MemoryGraft planted fabricated *successful experiences* that agents later imitated, turning the self-improvement mechanism itself into the attack vector ([WorkOS](https://workos.com/blog/ai-agent-memory-poisoning)). The OWASP Top 10 for Agentic Applications (December 2025) classified memory and context poisoning as ASI06, a distinct category from prompt injection precisely because poisoned state persists across sessions ([OWASP](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/)). The security model's job is to map these threats onto CCR's components and specify the defense at each layer.

The model's central commitment is **honest scoping**: CCR's architecture does not eliminate the threat surface — no system that learns from experience can — but it changes the security conversation from "prevent all bad state" (impossible) to "make bad state detectable, attributable, and reversible" (engineering). The mitigations below are layered, and the recovery procedures are tested, because the assumption is that some attacks will succeed; the question is whether the system *knows* it has been compromised and can *prove* when and how.

---

## 1. Threat Model

### 1.1 Assets

The assets under protection are the components of the agent's cognitive state and their integrity:

| Asset | Security property | Compromise consequence |
|---|---|---|
| **Experience ledger** | Immutability, completeness | False history; unprovable lineage |
| **Cognitive state (CSO)** | Integrity, provenance | Poisoned beliefs, policies, skills |
| **Causal graph** | Attribution accuracy | Spurious learning; misattributed causality |
| **Evaluation system** | Verdict integrity | Feedback poisoning; reward hacking |
| **Policy table** | Authorization consistency | Unauthorized action licensing |
| **Identity + authority** | Continuity, scope binding | Authority escalation; identity drift |
| **Provenance chain** | Verifiability | Unaccountable behavior; repudiation |

### 1.2 Adversary capabilities

The threat model assumes four adversary classes, in increasing capability:

- **Query-only adversary:** can interact with the agent through normal user interfaces (MINJA's threat model). No elevated privileges, no direct memory writes, no code execution.
- **Tool-compromising adversary:** can compromise a tool or data source the agent uses (e.g., a poisoned API response, a malicious document in a RAG corpus).
- **Evaluator-influencing adversary:** can influence the evaluation signal (e.g., fake user feedback, manipulated test results, adversarial KPI gaming).
- **Insider adversary:** has legitimate access to the agent's infrastructure (e.g., a malicious administrator, a compromised deployment pipeline).

The insider adversary is the hardest to defend against and is addressed primarily through provenance and audit (§5) — the goal is not to prevent insider compromise but to make it *detectable* and *attributable*.

### 1.3 Attack surface

The attack surface is the set of write paths into cognitive state:

1. **Experience capture:** the runtime's telemetry → ledger write path.
2. **Evaluation:** the evaluator's verdict → experience record write path.
3. **Admission:** the gate's decision → transaction initiation path.
4. **Validation:** the validation verdict → commit decision path.
5. **Commit:** the Cognitive State Manager's state write path.
6. **Retrieval:** the memory engine's read path (poisoned content influences behavior without a write).

Each write path is a potential poisoning vector; each read path is a potential influence vector. The security model maps threats to paths and defenses to layers.

---

## 2. Threat Taxonomy

The roadmap's seven threat classes are mapped to attack surface paths and OWASP ASI categories:

| Threat class | Attack path | OWASP ASI | Example |
|---|---|---|---|
| **Experience poisoning** | Experience capture | ASI06 | False experiences inserted via query-only interaction (MINJA) |
| **Feedback poisoning** | Evaluation | ASI06 + ASI09 | Manipulated verdicts; reward hacking; sycophantic evaluators |
| **Memory poisoning** | Commit (semantic memory) | ASI06 | Malicious fact becomes persistent belief |
| **Policy poisoning** | Commit (policy table) | ASI01 + ASI02 | Bad experience causes dangerous strategy update |
| **Recursive self-reinforcement** | Evaluation + admission | ASI10 | Agent generates evidence supporting its own incorrect beliefs |
| **Attribution laundering** | Evaluation → causal graph | ASI09 + ASI10 | A fabricated causal chain justifies a *future* policy update (doc 05 §6) — **feedback poisoning (§2.2) with a compounding lever into recursive self-reinforcement (§2.5)**. **Mitigated (present):** replay (`ccr/causal.py:replay_edge`, PR-A) rejects a forged chain — it must reproduce its `anomaly` on replay or it is deprecated; and admission (PR-B) consumes only **surviving, calibrated** chains as a **bounded uplift**, added to V and **clamped in aggregate at X=0.05** (`AdmissionGate.causal_uplift_cap`) — failed/uncalibrated chains contribute **zero**, and support (roots) is never inflated (I6). The cap is the **safety bound**; γ (`CAUSAL_GAMMA`) only sizes typical influence. **Ceiling — what replay does NOT catch** (same register as the contested ceiling / calibration "undefined, not zero"): replay tests a cause's *propensity* for the anomaly, not *instance* causation; in a **multi-step** trajectory a genuinely-bad step can survive replay while the specific failure came from **upstream** (stages 2–4 + data-flow Q2 close this; the current single-step emitter cannot construct it, so a surviving chain here is true and the ceiling is latent). **Budget caveats:** (a) the `|ΔV| ≤ X` bound is **per-decision, not per-campaign** — multi-decision compounding is §2.5, which this bound does not cover; (b) the "N edges to flip a decision" cost assumes **independent** chains — correlated forgeries (one compromised channel / one poisoned cited experience) cost ≈ **one root**. **Strongest reading:** the **aggregate cap** (`Σ ΔV ≤ X`, hard, enforced at the gate) makes correlated and independent attacks hit the **same ceiling X**, so the one-root cost stays true about attack *cost* but is a **footnote, not a vulnerability**. |
| **Cognitive drift** | Accumulated commits | ASI10 | Gradual behavioral divergence from intended behavior |
| **Identity drift** | Identity layer | ASI03 | Behavior changes so much that original authority assumptions are invalid |

### 2.1 Experience poisoning (MINJA-class)

**Attack:** The adversary crafts queries that induce the agent to generate and store malicious memory entries. MINJA's mechanism: indication prompts guide the agent's reasoning, bridging steps connect attacker queries to victim queries in embedding space, and progressive shortening compresses malicious records so they appear natural ([MINJA](https://arxiv.org/html/2503.03704v4)).

**Why it works against naive systems:** auto-extraction writes to memory without independent validation; the write path trusts the agent's own output.

**CCR defense:**
- **Admission gate (L1):** poisoned experiences must pass the learning-value functional `V(X)` with risk-dependent threshold. A MINJA-style injection (novel but untrustworthy) faces a high threshold.
- **Independent evaluation (L2):** the evaluator is architecturally separate from the acting agent; a poisoned experience that the agent "believes" must still be evaluated independently.
- **Replay validation (L3):** a candidate update justified by a poisoned experience must survive counterfactual replay against held-out history. If the poisoned experience claims "Tool A fails under condition X" but the ledger contains successful uses of Tool A under condition X, replay detects the inconsistency.
- **Provenance (L4):** the poisoned experience's provenance (query-only interaction, no external verification) is recorded and lowers its trust score.

**Residual risk:** a sufficiently sophisticated adversary can craft experiences that pass all gates. The defense is *economic*: the cost of a successful poisoning rises with each layer, and the recovery procedure (§6) limits the damage.

### 2.2 Feedback poisoning

**Attack:** The adversary manipulates the evaluation signal — fake user feedback, compromised test suites, adversarial KPI gaming — to induce the agent to learn incorrect policies.

**Why it works against naive systems:** self-evaluation or single-channel feedback is trusted without cross-checking.

**CCR defense:**
- **Plural evaluation channels (L1):** the evaluator uses multiple channels (deterministic tests, external feedback, model-based critics, human review) with per-channel reliability tracking (document 02, §3.8). A single compromised channel has bounded influence.
- **Evaluator calibration (L2):** channel reliability is versioned state; a channel whose verdicts are later found incorrect is down-weighted — **against a designated reference channel (§2.2a).**
- **Confidence-carrying verdicts (L3):** evaluations emit confidence, and the admission function requires high confidence for high-risk updates.
- **Human-in-the-loop for high-risk (L4):** the validation predicate requires human approval for high-risk policy changes (document 01, §7.5).

**Residual risk:** coordinated multi-channel compromise is possible but expensive; the calibration loop provides detection over time.

### 2.2a Calibration's reference requirement — the trust root it relocates, not removes

*(Added 2026-09-07. This operationalizes what §2.2 above and doc 02 §3.8 leave open: down-weighting "a
channel whose verdicts are later found incorrect" presupposes something to find them incorrect
**against** — and neither section names it.)*

**Reliability is measured against a designated reference channel, trusted for reasons extrinsic to the
system.** A channel's reliability is its agreement rate with a *more-trustworthy* signal; if every
channel's reliability is unestablished, calibrating channel A against channel B needs B's reliability,
which needs A's or C's — circular. The only non-circular floor is a **reference channel** whose
authority comes from **outside** the calibration loop: deterministic tests whose correctness is
definitional, delayed **confirmed real-world outcomes**, or a human oracle taken as authoritative. In the
simulator, `SimulatorGroundTruthEvaluator` **is** that reference by construction.

**Calibration relocates the trust root; it does not remove it.** Its value is exactly this relocation:
from "trust every channel's self-report" (**N** unaudited anchors — the "trust the account" failure of
the standing rule) to "trust **one** designated reference's authority" (one auditable anchor). That is
real progress, and it is also the limit — **the anchor does not disappear.** At the bottom, something is
trusted for reasons the system cannot itself verify.

**Without a reference, calibration degrades to consensus — imitation, not correctness.** With no
extrinsic reference, "found incorrect" can only mean "disagrees with the other channels," so the loop
converges on **inter-channel agreement**, which rewards a channel for matching the majority account
rather than for being right. That is the **AML proxy-label circularity** recorded in
`Ulissy-s-r-l/eu-governed-agent` **ADR-0009**: models trained on analyst dispositions learn to *agree
with the analyst*, because no ground truth for laundering is fed back.

**Criterion, and where it fails.** A reference channel exists **iff the domain produces delayed,
independent, outcome-grounded signals** — confirmed test results, settled receivables, adjudicated
outcomes. **Therefore per-channel calibration is _unbuildable_ where no such signal exists.** The
concrete case is **AML (ADR-0009): no correctness signal arrives**, so no channel can be established as a
reference, the disposition channel's reliability is unestablishable, and the "trust the channel, not the
account" gap **stays open there** — the gate remains stuck trusting the account, because nothing can
contradict it.

**One limit, multiple layers — not three coincidences.** This is the **same structure** as **ADR-0009
gap 3a**: an approver key is bound to a *named person* only by an **external authority** (a QTSP, a
bank's IAM) the system cannot itself verify. Calibration's reference channel and gap 3a's external
identity authority are the same move — pushing the trust root to a point outside the system's own
machinery — and the "trust the channel, not the account" standing rule is the general statement of it.
Where the domain supplies an extrinsic anchor (tests, confirmed outcomes, a vetted authority), the move
succeeds; where it does not (AML correctness, self-asserted identity), the anchor is absent and the gap
is a **stated limit of the domain**, not an unbuilt feature. This is L4's open research question (doc 00
§5.4) made precise: *which feedback is trustworthy* is answerable only relative to a reference the system
must be given.

### 2.3 Memory poisoning

**Attack:** A malicious fact is committed to semantic memory and becomes a persistent belief.

**Why it works against naive systems:** memory writes are trusted; no validation gate.

**CCR defense:**
- **Learning transaction (L1):** memory updates are transactions; they require admission, validation, and commit.
- **Provenance completeness (L2):** every memory item cites its source experiences; a fact without provenance cannot be committed (invariant I4).
- **Confidence decay (L3):** unconfirmed beliefs decay over time (document 02, §3.6); a poisoned fact must be re-confirmed to persist.
- **Rollback (L4):** a discovered poisoned fact triggers a revert transaction; the poisoned state is recoverable.

### 2.4 Policy poisoning

**Attack:** A bad experience causes a dangerous strategy update — e.g., "always use tool X" where tool X is attacker-controlled.

**Why it works against naive systems:** policy updates are automatic; no risk classification.

**CCR defense:**
- **Risk-classed updates (L1):** policy changes are classified by blast radius; high-risk changes require human approval.
- **Causal basis requirement (L2):** policy entries must cite causal chains; a policy update without mechanistic justification is inadmissible (document 05, §4).
- **Replay against regression battery (L3):** the candidate policy is tested against historically critical behaviors; a poisoned policy that breaks critical behaviors is rejected.
- **Authority consistency check (L4):** the policy is checked against the agent's authority scope; a policy licensing out-of-scope actions is rejected (invariant I5).

### 2.5 Recursive self-reinforcement

**Attack:** The agent generates evidence supporting its own incorrect beliefs — e.g., it misinterprets feedback to confirm a false hypothesis, then uses the "confirmed" hypothesis to interpret future feedback.

**Why it works against naive systems:** self-evaluation is circular; no external check.

**CCR defense:**
- **Independent evaluation (L1):** the evaluator is architecturally separate; the agent cannot evaluate its own hypotheses.
- **Cross-channel verification (L2):** multiple evaluation channels must agree; a single self-generated signal is insufficient.
- **Drift monitoring (L3):** behavioral drift is measured over the state DAG (document 01, §12.1); rapid self-reinforcing drift triggers alerts.
- **Human review triggers (L4):** certain patterns (e.g., confidence rising while external validation falls) trigger mandatory human review.

### 2.6 Cognitive drift

**Attack:** Accumulated updates gradually move behavior away from intended behavior, without any single malicious action.

**Why it works against naive systems:** no versioning; no drift measurement.

**CCR defense:**
- **Drift metrics (L1):** drift is defined and measured over the state DAG (document 01, §12.1).
- **Versioned state (L2):** any prior state is recoverable; drift can be rolled back.
- **Baseline comparison (L3):** the genesis state `C_0` is a fixed reference; divergence from `C_0` is monitored.
- **Re-authorization triggers (L4):** when drift exceeds a threshold `ε`, re-authorization is required (document 01, §12.1).

### 2.7 Identity drift

**Attack:** Behavior changes so substantially that the original authority assumptions are no longer valid — the agent is "the same" by identity but not by behavior.

**Why it works against naive systems:** identity is static; behavior is unversioned.

**CCR defense:**
- **Authority-per-state-version (L1):** authority is evaluated against the current state version, not the provisioning state (document 01, §10).
- **State commitment binding (L2):** the identity record includes `StateCommitment`; the agent's current state is cryptographically bound to its identity.
- **Lineage verification (L3):** the full state lineage is verifiable; any break in the chain is detectable.
- **Human approval for high-risk learning (L4):** the roadmap's `HighRiskPolicyChange ⇒ HumanApproval` property binds the human principal into the loop at critical points.

---

## 3. Mitigation Matrix

The mitigations are organized by defense layer, with the threat classes they address:

| Layer | Mechanism | Threats addressed | CCR component |
|---|---|---|---|
| **L1: Write-time controls** | Admission gate, input moderation, trust scoring | Experience poisoning, memory poisoning | Learning Engine |
| **L2: Independent evaluation** | Plural channels, calibration, confidence | Feedback poisoning, recursive self-reinforcement | Outcome Evaluator |
| **L3: Validation** | Replay, regression battery, invariant checks | Policy poisoning, memory poisoning | Learning Transaction |
| **L4: Versioned state** | Commit/branch/rollback, drift monitoring | Cognitive drift, all poisoning classes | Versioning & Rollback |
| **L5: Provenance** | Hash chains, Merkle proofs, signed checkpoints | All classes (attribution) | Provenance Recorder |
| **L6: Authority** | Scope binding, per-version evaluation, human approval | Policy poisoning, identity drift | Identity Layer (GNS) |
| **L7: Monitoring** | Behavioral baselines, anomaly detection, circuit breakers | All classes (detection) | External monitoring |

The matrix is **defense in depth**: no single layer is sufficient, and the layers are designed to fail independently. A MINJA attack must defeat L1 (admission), L2 (evaluation), and L3 (validation) to affect behavior; even then, L4 (rollback) enables recovery, and L5 (provenance) enables attribution.

---

## 4. The MINJA Attack: Detailed Analysis

MINJA is the canonical memory-poisoning attack and deserves detailed treatment because it exposes the exact weakness CCR is designed to close.

### 4.1 Attack mechanism

MINJA operates in three steps ([MINJA](https://arxiv.org/html/2503.03704v4)):

1. **Indication prompts:** the attacker sends queries that guide the agent to generate specific reasoning patterns.
2. **Bridging steps:** the attacker's queries are designed to connect to the victim's likely future queries in the memory's embedding space.
3. **Progressive shortening:** malicious records are compressed so they appear natural and are retrievable.

When the victim later sends a semantically related query, the poisoned memory entries are retrieved and used as in-context demonstrations, influencing the agent's response.

### 4.2 Why naive defenses fail

MINJA's authors evaluated four defense classes and found them insufficient:

- **Adversarial training:** requires task-specific labeled attack data and retraining; limited generalization.
- **Embedding-level sanitization:** malicious and benign records are entangled in embedding space; indistinguishable by similarity.
- **Prompt-level detection:** most applicable but suffers from high false positives (general prompts) or limited generalization (targeted prompts).
- **System-level isolation:** can be circumvented by identity disguise or coordinated attacks.

### 4.3 CCR's structural defense

CCR's defense is not a better filter but a *different architecture*:

- **Admission gate:** MINJA's poisoned records are experiences; they must pass the learning-value functional. A poisoned record has low trust (query-only provenance) and high risk (unverified); the threshold `η` rises accordingly.
- **Independent evaluation:** the evaluator is separate from the agent that generated the record; the record's self-assessment is not trusted.
- **Replay validation:** a candidate update justified by a poisoned record must survive replay against the ledger's full history. MINJA's records are *fabricated*; they will contradict the ledger's ground truth under replay.
- **Provenance:** the record's provenance (query-only, no external verification) is stored and queryable; low-provenance records face higher admission thresholds.

The defense is **structural, not heuristic**: it does not depend on detecting the attack's linguistic signature but on the architectural requirement that all learning pass through validation. MINJA's success against naive systems is precisely because those systems lack the validation gate; CCR's gate is the defense.

---

## 5. Provenance and Attribution

The provenance layer (document 03, §5) is the security model's attribution mechanism. Every experience, evaluation, and state transition is signed and hash-chained; the full lineage is verifiable by third parties. This enables:

- **Post-hoc audit:** any committed update can be traced to its justifying experiences, their evaluations, and the validation record.
- **Tamper detection:** hash-chain verification detects any retroactive modification.
- **Non-repudiation:** signed records cannot be denied by their authors.
- **Incident response:** a discovered poisoning can be traced to its source experience, and all states derived from that experience can be identified and reverted.

The provenance layer's limitations are stated honestly (document 03, §5.3): hash chains provide tamper *evidence*, not tamper *prevention*; integrity is relative to the distribution of signed checkpoints. The security model therefore requires that checkpoints leave the system — held by the principal, anchored in the GNS identity chain, or witnessed by an external transparency service.

---

## 6. Recovery Procedures

Recovery is the security model's final layer: the assumption is that some attacks will succeed, and the question is whether the system can recover.

### 6.1 Detection

Detection is the prerequisite for recovery. The monitoring layer (L7) uses:

- **Behavioral baselines:** established patterns of tool use, response style, decision timing.
- **Anomaly detection:** deviations from baseline trigger alerts.
- **Drift metrics:** rapid or large drift triggers review.
- **Provenance audits:** periodic verification of hash chains and signatures.

### 6.2 Containment

On detection of a suspected compromise:

1. **Circuit breaker:** the agent is paused; no further commits are accepted.
2. **Scope restriction:** the agent's authority scope is narrowed to read-only.
3. **Alert:** the human principal is notified with the evidence bundle.

### 6.3 Recovery

Recovery uses the rollback procedure (document 04, §5):

1. **Identify the compromise point:** trace the poisoned state to its justifying experience via provenance.
2. **Revert:** issue a revert transaction to the last clean state before the compromise.
3. **Selective re-application:** re-apply benign updates committed after the compromise as new transactions.
4. **Post-mortem:** document the attack vector, update the admission function's thresholds, and add the attack pattern to the regression battery.

The recovery guarantee (document 01, Prop. 8.5): any harmful committed update's influence is removable by revert with intact history, and the full recovery is auditable.

---

## 7. Formal Properties

The security model's properties are stated as candidate invariants for formal verification (Phase 8):

| Property | Formal statement | Enforcement |
|---|---|---|
| **No unvalidated commit** | `Committed(ΔC) ⇒ Validate(ΔC) = ⊤` | Guard conjunction (document 01, §7.2) |
| **No unauthorized action** | `Executed(a) ⇒ scope(class(a)) = permit` | Authority guard (document 01, §10.2) |
| **Tamper evidence** | `Modify(record_k) ⇒ ¬VerifyChain(commitment_n) ∀ n ≥ k` | Hash chain (document 03, §5.1) |
| **Recovery completeness** | `Harmful(ΔC_m) ⇒ ∃ revert path to C_{m-1}` | Rollback semantics (document 01, Def. 8.4) |
| **Attribution completeness** | `Committed(ΔC) ⇒ ∃ provenance path to experiences` | Provenance index (document 02, §3.9) |

These properties are **architectural guarantees**, not learning guarantees: they state that the system's *discipline* is enforced, not that its *learning* is correct. The distinction is the security model's epistemological boundary.

---

## 8. Summary and Handoff

The security model specified here maps the demonstrated threat landscape — MINJA's query-only poisoning, MemoryGraft's fabricated experiences, OWASP's ASI06 classification — onto CCR's architecture and specifies the defense at each layer. The model's central claim is that CCR's *structural* properties (admission gate, independent evaluation, validation, versioning, provenance) convert poisoning from a silent, persistent compromise into a detectable, attributable, recoverable incident. The model's honest limitation is that no architecture eliminates the threat surface; the goal is to raise the cost of attack, bound the blast radius, and guarantee recoverability.

Document 08 (`08-GNS-CCR-INTEGRATION.md`) specifies the identity and authority layer that binds these security properties to cryptographic verification, and the research paper (`Continuous-Cognitive-Runtime.md`) will evaluate the security model's claims against the benchmark's threat scenarios.

*Document 07 of the CCR series. Previous: `06-CCR-BENCHMARK.md`. Next: `08-GNS-CCR-INTEGRATION.md` — identity, authority, and lineage.*
