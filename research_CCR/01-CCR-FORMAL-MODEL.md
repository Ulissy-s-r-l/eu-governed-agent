# 01 — CCR Formal Model: Mathematics and State Transitions

**Continuous Cognitive Runtime (CCR) — Document 1 of the CCR specification series**
**Status:** Working draft v0.1 — personal working document, intended for later refinement toward an arXiv publication
**Depends on:** `00-CCR-SYSTEM-OVERVIEW.md` (architecture, design principles P1–P8)
**Feeds:** `02-COGNITIVE-STATE-OBJECT.md`, `03-EXPERIENCE-LEDGER.md`, `04-LEARNING-TRANSACTION.md`, `05-CAUSAL-COGNITIVE-GRAPH.md`

---

## 0. Executive Summary

This document gives the Continuous Cognitive Runtime its mathematical skeleton. Where document 00 established *what* the architecture is — a layer that converts execution experience into validated, versioned, attributable behavioral change — this document establishes *what that claim formally means*: the spaces, objects, functions, transition relations, and invariants in which the architecture's promises can be stated precisely and, eventually, proved or refuted. The formalization is deliberately conservative. It extends two well-understood frames rather than inventing a new one: the **POMDP view of agency**, in which the agent never sees the true environment state but conditions behavior on its interaction history ([Theory of Agent](https://www.preprints.org/manuscript/202609.0308)), and the **memory-augmented decision process**, in which an explicit, evolving memory enters the policy itself, as formalized by Memento's M-MDP ([Memento](https://arxiv.org/html/2508.16153v2)).

The contribution is not any single equation but the **transition discipline**. In prior memory-augmented formulations, the memory update is a trivial consequence of acting — Memento's case bank grows by append, `M_{t+1} = M_t ∪ {(s_t, a_t, r_t)}`, automatically and unconditionally ([Memento](https://arxiv.org/html/2508.16153v2)). In CCR, the cognitive-state update is a **guarded transition**: a candidate update ΔC must pass an admission function, a validation predicate, and (for high-risk classes) an authorization check before it commits, and the commit itself is recorded in a hash-chained state DAG. The result is a formal object — the *validated cognitive state transition system* — in which the roadmap's research questions become well-posed mathematical questions: RQ2 asks for the minimal state sufficient for learning; RQ3 asks for the characterization of the admission function; RQ6 asks for the algebra of versioning; RQ8 asks whether lineage is verifiable. This document fixes the language in which all of them are stated.

---

## 1. Preliminaries and Notational Conventions

### 1.1 The environment as a POMDP

We model the agent's environment as a partially observable Markov decision process `⟨𝒮, 𝒜, Ω, 𝒯, 𝒵, b₀, ρ⟩`, where `𝒮` is the latent environment state space, `𝒜` the action space (including tool invocations), `Ω` the observation space, `𝒯(s' | s, a)` the transition kernel, `𝒵(o | s', a)` the observation kernel, `b₀` the initial-state prior, and `ρ : 𝒮 × 𝒜 → ℝ` the (possibly latent) reward or task-success function. This choice is forced by the domain: a web agent sees a rendered page, not the server's database; a coding agent sees test output, not the program's semantics; a research agent sees retrieved snippets, not the corpus ([Theory of Agent](https://www.preprints.org/manuscript/202609.0308)). Because the true state is hidden, the agent cannot condition on `s_t` and must instead condition on its **interaction history** `τ_t ≜ ⟨q, a₁, o₁, …, a_{t−1}, o_{t−1}⟩`, where `q` specifies the task or goal; the corresponding belief state is the posterior `b_t = p(s_t | τ_t)`.

The POMDP frame matters to CCR for a reason that goes beyond correctness: it explains *why* deterministic memory is fragile. Under partial observability, each observation is evidence, not truth, and a memory system that stores "API X failed" as ground truth collapses a genuine hypothesis space — permanent outage, rate limiting, transient fault — into a single point estimate, enabling the self-reinforcing error patterns documented in the BeliefMem analysis ([BeliefMem](https://arxiv.org/html/2605.05583v1)). CCR's response appears at two points in this document: confidence attaches to evaluations and learnings rather than being discarded (§5), and the causal graph records *attributed* causes with their provenance rather than asserted ones (§9). The formal model therefore treats all learned content as **evidence-weighted** from the outset, and treats "the agent's knowledge" as a structured belief-bearing object rather than a set of facts.

### 1.2 Conventions

Time is indexed by **decision steps** `t ∈ ℕ` on the hot path and by **commit indices** `n ∈ ℕ` on the cold path; the two clocks are explicitly distinguished because learning is asynchronous (P8 in document 00). We write `X ~ π(· | ctx)` for sampling from a policy, `⟦φ⟧` for the truth value of a predicate, and `H(·)` for a collision-resistant cryptographic hash. All probability statements are with respect to the joint distribution induced by the environment kernels, the foundation model's sampling, and any stochasticity in retrieval and selection policies. Sets are calligraphic (`𝒳, 𝒞, 𝒰`), structured objects are bold or capitalized, and versioned objects carry their version as a subscript. A consolidated symbol table appears in §13.

A note on scope: this document formalizes the *single-agent* CCR. Multi-agent shared learning, federated cognitive state, and cross-agent provenance — listed in the roadmap's future work — require extensions (shared state DAGs, cross-identity attestation) that are deliberately deferred. Where a definition has an obvious multi-agent generalization it is flagged, but no claim in this document depends on it.

---

## 2. The Agent: Formal Definition

### 2.1 The agent tuple

**Definition 2.1 (Agent).** A CCR agent at decision step `t` is the tuple

\[
\mathcal{A}_t = \langle M, C_t, I \rangle
\]

where `M` is the **foundation model** (frozen at runtime; identified by a version tag `v_M`), `C_t` is the **cognitive state** at the current committed version (Definition 4.1), and `I` is the **identity record** (Definition 10.1). The roadmap's finer-grained tuple `⟨M, C_t, P_t, S_t, I⟩` — policies `P_t` and skills `S_t` called out separately — is recovered immediately, because policies and skills are *components of* the cognitive state: `P_t = C_t.policies` and `S_t = C_t.skills`. The compressed form is preferred here because it makes the central structural claim syntactically visible: everything about the agent that changes through experience lives inside exactly one object, and every change to that object passes through the transition machinery of §7–§8.

The identity of the agent over time is then a derived notion rather than a primitive one. Two agent instances `𝒜_t` and `𝒜_{t'}` are **the same agent** if and only if they share the identity record `I` and their cognitive states are connected by an authenticated path in the state DAG (Definition 8.3): `C_t ⇝* C_{t'}` or `C_{t'} ⇝* C_t`. This is the formal content of the roadmap's identity discussion — the agent "is" its lineage, and sameness is a graph property, checkable in time linear in the length of the claimed chain, rather than a metaphysical one.

### 2.2 The effective policy

The agent's observable behavior is its **effective policy** `π_t : Ω × 𝒜 → [0,1]`, defined as a composition of retrieval, conditioning, and generation:

\[
\pi_t(a \mid o, \tau_t) \;=\; \sum_{k \in \mathcal{K}_t} \mu(k \mid o, \tau_t, C_t) \cdot p_M(a \mid o, \tau_t, k, C_t.\mathrm{policies}, C_t.\mathrm{skills})
\]

where `𝒦_t ⊆ Retrieve(C_t, o, τ_t)` is the package of cognitive context retrieved from the committed state (relevant memories, applicable skills, active policies, causal precedents), `μ` is the **retrieval-and-selection distribution** over that package, and `p_M` is the foundation model's action distribution conditioned on the assembled context. This is a direct generalization of Memento's policy decomposition `π(a_t | s_t, M_t) = Σ_c μ(c | s_t, M_t) · p_LLM(a_t | s_t, c)` ([Memento](https://arxiv.org/abs/2508.16153)), with two differences that carry the CCR thesis. First, the retrieval target is not a flat case bank but the full typed cognitive state, so `μ` ranges over heterogeneous artifacts — cases, skills, policy entries, causal paths. Second, `C_t` itself is the output of the validated transition system of §7, whereas Memento's case bank evolves by unconditional append.

**Proposition 2.2 (substrate independence of learning).** For any two foundation models `M, M'` and any committed cognitive state `C_t`, the agent `⟨M', C_t, I⟩` is well-defined. Formally this is trivial — nothing in the tuple constrains `M` — but its operational content is the portability claim of design principle P1: learned behavior is an asset separable from the substrate, and swapping models is a re-instantiation, not a re-learning. The proposition also states, honestly, the limit of the claim: `p_{M'}` may condition on `C_t` *worse* than `p_M` does, so portability of state does not imply preservation of performance. Quantifying that degradation across model swaps is an empirical question for the benchmark document, not a theorem.

---

## 3. Experience: The Formal Object

### 3.1 The experience tuple

**Definition 3.1 (Experience).** An experience is the record

\[
X_i = \langle S_i, G_i, A_i, O_i, E_i, R_i, \kappa_i, \Lambda_i, \pi_i^{prov}, \tau_i^{ts} \rangle
\]

where `S_i` is the observed state/context summary, `G_i` the goal, `A_i` the action (or action sequence for multi-step episodes), `O_i` the observed outcome, `E_i` the evaluation record (Definition 5.1), `R_i` the resulting learning reference (a pointer to a committed update, or `⊥` if none), `κ_i ∈ [0,1]` a confidence estimate, `Λ_i ⊆ ℒ` a set of causal links to predecessor experiences (§9), `π_i^{prov}` the provenance metadata (capturing identity, authority scope in force, and source channels), and `τ_i^{ts}` the timestamp. The experience space `𝒳` is the set of all such records well-formed under the schema of `03-EXPERIENCE-LEDGER.md`.

Two design decisions in this definition deserve explicit justification. First, the inclusion of the evaluation `E_i` *inside* the experience — rather than as a separate record joined by key — reflects the architectural claim that an unevaluated experience is incomplete as an object of learning: it can inform retrieval (L1 behavior) but cannot justify a behavioral update (L2–L4 behavior). The type system of the runtime should make this distinction statically visible. Second, the causal links `Λ_i` are *references*, not inferred structure: they are asserted at capture or enrichment time by identified mechanisms (the agent's own trace, the evaluator's attribution, human annotation) and carry the confidences of those mechanisms. This is what keeps the causal graph honest — every edge is attributable, and an edge whose attribution is discredited can be reweighted without deleting the experiences it connects.

### 3.2 Experience quality and the learning-value functional

Not all experiences are equal, and the admission function of §6 needs a principled quantity to threshold. We define the **learning value** of an experience as a functional of four terms:

\[
V(X_i) \;=\; w_1 \cdot \mathrm{InfoGain}(X_i \mid C_t) \;+\; w_2 \cdot \mathrm{Surprise}(X_i) \;+\; w_3 \cdot \mathrm{Risk}(X_i) \;+\; w_4 \cdot \mathrm{Trust}(X_i)
\]

where `InfoGain` measures the expected reduction in the agent's predictive error about `𝒯` and `ρ` from incorporating `X_i`; `Surprise` measures the outcome's deviation from the agent's prior expectation `|O_i − 𝔼[O | S_i, A_i, C_t]|` (high-surprise outcomes are where learning signal concentrates, a principle with deep roots in both RL's TD error and the test-time-learning literature); `Risk` classifies the blast radius of any update this experience might motivate; and `Trust` aggregates the provenance quality of the experience's sources — evaluator channel reliability, environment integrity signals, and feedback-source history. The weights `w` are themselves part of cognitive state (the L4 recursion of document 00, §5.4) and are therefore versioned and learnable.

This functional is deliberately a *scalarization of incommensurables*, and we state that as a limitation rather than hiding it: information gain, surprise, risk, and trust do not naturally share units, and the choice of `w` encodes policy about what the agent should learn from. CCR's answer is not to pretend the tradeoff away but to make it **explicit, versioned, and auditable** — the weights are inspectable state, every admission decision logs the functional's value, and the experimental program can sweep `w` as a first-class independent variable. The alternative practiced by most existing systems — an implicit, fixed, unlogged admission policy of "store everything" or "store what the LLM decides to write" — has all the same arbitrariness with none of the accountability.

---

## 4. The Cognitive State Object: Formal Definition

### 4.1 The CSO tuple

**Definition 4.1 (Cognitive State Object).** The cognitive state at commit index `n` is the tuple

\[
C_n = \langle \mathrm{mem}_n,\; \mathrm{exp}_n,\; \mathrm{skills}_n,\; \mathrm{pol}_n,\; \mathrm{strat}_n,\; \mathrm{goals}_n,\; \mathrm{prefs}_n,\; \mathrm{conf}_n,\; \mathcal{G}_n^{caus},\; \mathrm{eval}_n,\; \mathrm{prov}_n,\; v_n,\; \mathrm{parent}_n,\; I.\mathrm{ref},\; v_M \rangle
\]

with components: `mem_n` the **semantic/episodic memory content**; `exp_n ⊆ ℒ` the index over the experience ledger (the ledger itself is append-only and lives outside the versioned state — see §4.2); `skills_n` the **skill library**, a set of executable procedures with metadata; `pol_n` the **policy table** (§4.3); `strat_n` named strategy definitions; `goals_n` and `prefs_n` persistent goals and preferences; `conf_n : \mathrm{Content} → [0,1]` the confidence assignment over learned content; `𝒢_n^{caus}` the causal graph (§9); `eval_n` the evaluation-history summary and evaluator calibration state; `prov_n` the provenance accumulator; `v_n ∈ ℕ` the version; `parent_n` the parent state reference(s); and `I.ref`, `v_M` the identity and model references. The **cognitive state space** `𝒞` is the set of all well-formed CSOs satisfying the invariants of §11.

The state space is intentionally *not* factored into independent subspaces with independent update rules, for a reason that is easy to miss: the components are **semantically coupled**. A policy entry in `pol_n` cites causal paths in `𝒢_n^{caus}`; a skill in `skills_n` carries provenance into `prov_n` and confidence in `conf_n`; a memory consolidation in `mem_n` references the raw experiences in `exp_n` it subsumes. Any formalism that let these components drift independently would have to re-impose consistency as an afterthought. CCR instead makes coupling the default and treats **invariant preservation under update** as the central obligation of the transition function (§7.3).

### 4.2 What is versioned and what is not

A subtle but load-bearing distinction: the **experience ledger is not versioned**, while the **cognitive state is**. The ledger `ℒ` is an append-only sequence `ℒ = ⟨X_1, X_2, …⟩` ordered by capture time; experiences are facts of history and are never mutated, only re-interpreted. The cognitive state, by contrast, is a *theory about* history — what the agent currently believes, prefers, and tends to do — and theories legitimately change, branch, and are rolled back. Conflating the two (as systems do when "memory" is both the log and the belief store) makes rollback incoherent: one cannot roll back history, only beliefs. CCR's separation gives rollback a clean semantics (§8.4): reverting to `C_k` changes what the agent will do, while the full ledger `ℒ` remains available, so nothing learned is ever destroyed — it is de-committed, and the reason is preserved.

The index `exp_n ⊆ ℒ` inside the CSO records *which* experiences the state at version `n` has incorporated through committed updates. This yields a useful derived relation: experience `X_i` **grounds** state `C_n` iff `X_i ∈ exp_n` and the commit that incorporated it lies on `C_n`'s ancestry path. Grounding is the formal substrate of the provenance property `CommittedUpdate ⇒ ValidatedExperience` (§11): to audit a state is to enumerate its grounding set and check each element's validation record, and to audit an update is to diff grounding sets across a commit.

### 4.3 Policies and strategy selection

The policy table `pol_n` assigns, to each recognized context region, a distribution over available strategies. Formally, let `𝒰` be the strategy space and `φ : Ω × 𝒳* → 𝒵_c` a **context classifier** mapping observations and retrieved history into a context region `z ∈ 𝒵_c`. Then

\[
\mathrm{pol}_n : \mathcal{Z}_c \times \mathcal{U} \rightarrow [0,1], \qquad \sum_{u \in \mathcal{U}} \mathrm{pol}_n(z, u) = 1
\]

and the roadmap's level-3 learning example is the statement that a validated success of strategy `B` in context `z` commits an update with `pol_{n+1}(z, B) > pol_n(z, B)` and compensating decreases elsewhere. The representation is deliberately neutral between instantiations: the table may be implemented as a softmax over learned Q-values in the style of Memento's retrieval policy `μ*(c | s, M) ∝ exp(Q*(s, M, c)/α)` ([Memento](https://arxiv.org/html/2508.16153v2)), as a contextual-bandit scoring rule with confidence bonuses in the LinUCB style — predicted reward plus an uncertainty bonus that shrinks as evidence accumulates ([LinUCB](https://vdf.ai/resources/linucb/)) — or as a natural-language policy document conditioned on by `p_M` in the style of ACE's playbooks ([ACE](https://arxiv.org/abs/2510.04618)). The formal model constrains the *interface* (distributions over strategies, confidence annotations, provenance, versioned update) and leaves the *representation* to the mechanism layer, exactly as document 00's architecture-mechanism separation requires.

---

## 5. Evaluation: The Formal Treatment

### 5.1 Evaluation records

**Definition 5.1 (Evaluation).** An evaluation of experience `X_i` is the record

\[
E_i = \langle r_i,\; c_i,\; \mathcal{D}_i,\; \mathrm{attr}_i,\; \pi_i^{eval} \rangle
\]

where `r_i ∈ ℝ` (or a structured verdict space) is the **outcome score**, `c_i ∈ [0,1]` the evaluator's **confidence**, `𝒟_i` the set of **channels** contributing to the verdict (deterministic tests, environment reward, model-based critique, human feedback, KPI signals), `attr_i` the **causal attribution** — the evaluator's assessment of which elements of `⟨S_i, G_i, A_i⟩` were load-bearing for `O_i`, feeding the causal graph — and `π_i^{eval}` the provenance of the evaluation itself. The evaluator is modeled as a function family `Eval_θ : 𝒳⁻ → ℰ` parameterized by `θ` (channel weights, critic models, test suites), operating on the *unevaluated* prefix of an experience, and architecturally disjoint from the acting policy (design principle P4).

The explicit confidence term is the formal trace of partial observability inside the learning pipeline. BeliefMem's critique — that deterministic memory collapses hypothesis spaces and locks in self-reinforcing errors — applies with equal force to deterministic *evaluation*: a verdict emitted without confidence forces the admission function to treat a flaky test's pass and a rigorous suite's pass identically ([BeliefMem](https://arxiv.org/html/2605.05583v1)). By carrying `c_i` through every downstream computation (admission in §6, update weighting in §7, policy posterior in §4.3), the model preserves the distinction between "verified" and "asserted" all the way into committed state, where it surfaces as `conf_n`.

### 5.2 Evaluator calibration as state

Because evaluation channels are themselves fallible and drift, the evaluator's parameters `θ` are part of cognitive state — concretely, within `eval_n` — and are updated through the same transaction machinery as everything else. The calibration signal is the evaluator's track record: for each channel `d ∈ 𝒟`, maintain outcome-prediction statistics against later ground truth (where it eventually arrives) and cross-channel agreement rates, yielding per-channel reliability estimates `ρ_d ∈ [0,1]` that weight future verdicts. This closes a loop that most self-improving systems leave open: ACE's helpful/harmful counters on playbook entries ([ACE](https://arxiv.org/abs/2510.04618)) and AWM's binary LM evaluator ([AWM](https://arxiv.org/abs/2409.07429)) both assume the verdict source is fixed and trustworthy, whereas CCR treats verdict-source reliability as a *learned, versioned, auditable* quantity — the system's own defense against the feedback-poisoning threat class, since a channel whose reliability estimate collapses is automatically down-weighted pending investigation.

---

## 6. The Admission Function

**Definition 6.1 (Admission function).** The admission function is the gate

\[
L : \mathcal{X} \times \mathcal{C} \rightarrow \{0, 1\}, \qquad L(X_i, C_n) = \mathbb{1}\big[\, V(X_i) \geq \eta(\mathrm{Risk}(X_i),\, \mathrm{conf}\_n) \,\big]
\]

where `V(X_i)` is the learning-value functional of §3.2 and `η` is a **risk- and calibration-dependent threshold**: candidate updates whose blast radius is large, or which arise when evaluator calibration is poor, face a higher bar. The binary codomain matches the roadmap's RQ3 formulation, but the threshold's dependence on risk and calibration is what makes the function a policy rather than a constant, and RQ3 is thereby refined from "which experiences should become learning" into the well-posed question "what threshold schedule `η` maximizes long-horizon performance subject to safety constraints" — a question the benchmark program can attack directly.

Three properties of `L` are worth stating as design obligations. **Conservatism under uncertainty:** when `c_i` is low, the effective threshold rises, so doubt defaults to non-commitment — the asymmetry that keeps poisoning expensive (a forged experience must clear a bar set for trustworthy ones). **Non-deletion:** rejection is not erasure; rejected experiences remain in the ledger and in research views, so the admission function's false negatives are recoverable by later re-admission under better calibration or additional corroborating experiences — formally, admission is monotone in evidence: if `X_i` is rejected at `C_n` and a later state `C_m` contains corroboration, `L` may admit a *resubmission* of the same candidate. **Auditability:** every gate decision, in either direction, emits a signed record into the provenance stream with the functional's component values, so the gate itself is part of the evidence chain rather than a silent filter.

---

## 7. The Learning Transaction: Update Operators and Guarded Transition

### 7.1 Candidate updates as typed operators

**Definition 7.1 (Candidate update).** A candidate update is a typed, partial operator on cognitive state,

\[
\Delta C = \langle \mathrm{op},\; \mathrm{target},\; \mathrm{payload},\; \mathrm{justification},\; \mathrm{risk} \rangle
\]

where `op ∈ {insert, revise, deprecate, merge, reweight}` is the operation type; `target` addresses a component of the CSO (a memory region, a skill, a policy entry, a strategy, a confidence assignment, a causal subgraph); `payload` carries the new content; `justification ⊆ ℒ × ℰ` is the set of experience–evaluation pairs cited in support; and `risk ∈ {low, medium, high}` is the change's risk classification, determining the validation path of §7.4. We write `C ⊕ ΔC` for the **tentative application** of a candidate to a state, producing a candidate state `Ĉ`. Tentative application is pure: it does not mutate `C`, cannot affect the hot path, and is the object on which validation operates.

The typing of updates is what makes validation tractable. An unconstrained "rewrite the state" operator would force validation to reason about arbitrary state diffs; typed operators let validation dispatch on `op` and `target` — an `insert` into `skills` triggers the skill-regression suite, a `reweight` on `pol` triggers counterfactual replay over the affected context regions, a `deprecate` triggers reachability checks for dependents. This mirrors the role of typed delta items in ACE's curator, where the playbook is updated by localized deltas rather than monolithic rewrites, which is what made their adaptation cheap and their context quality preserved ([ACE](https://arxiv.org/abs/2510.04618)). CCR sharpens the idea: deltas are not just cheap, they are the *unit of validation, commitment, and audit*.

### 7.2 The transition function

**Definition 7.2 (Cognitive state transition).** The raw transition function is

\[
\hat{C}_{n+1} = F(C_n, X_t, E_t) = C_n \oplus \Delta C, \qquad \Delta C = \mathrm{Propose}(C_n, X_t, E_t)
\]

where `Propose` is the Learning Engine's proposal mechanism (reflective insight extraction, workflow induction, delta curation, or policy reweighting — mechanism-neutral by design). The transition is **guarded**:

\[
C_{n+1} = F(C_n, X_t, E_t) \;\;\Longleftrightarrow\;\; L(X_t, C_n) = 1 \;\wedge\; \mathrm{Validate}(C_n, \hat{C}_{n+1}, \Delta C) = \top \;\wedge\; \mathrm{Authorize}(\Delta C, I, C_n) = \top
\]

with the three guards applied in order — admission, validation, authorization — and every guard outcome recorded. If any guard fails, the committed state is unchanged: `C_{n+1} = C_n`, and the failed candidate is retained in a research-visible **rejected-candidates store** with its guard verdicts. Formally, the system's state space therefore includes not just the committed DAG but the full candidate history, which is what makes negative results first-class research artifacts.

The contrast with prior formalizations is the point. In Memento's M-MDP, the memory transition is `M_{t+1} = M_t ∪ {(s_t, a_t, r_t)}` — unconditional, unvalidated, and monotone ([Memento](https://arxiv.org/html/2508.16153v2)). In A-MEM, memory evolution (note reorganization, link generation) is likewise automatic ([A-MEM](https://arxiv.org/abs/2502.12110)). CCR's `F` is the first element of the formal model with no direct precedent in the surveyed literature: a state transition that is *defined but conditionally applied*. Everything in the architecture's safety story reduces, formally, to the conjunction in the guard.

### 7.3 Invariant preservation

**Definition 7.3 (State invariants).** A CSO `C ∈ 𝒞` is well-formed iff it satisfies: **(I1) referential integrity** — every citation (policy→causal path, skill→experience, consolidation→raw experience) resolves within `C` or the ledger; **(I2) normalization** — every `pol(z, ·)` is a probability distribution; **(I3) confidence coherence** — `conf` assigns values in `[0,1]` and committed content carries confidence from its grounding evaluations; **(I4) provenance completeness** — every content item has a derivation path to ledger entries or to the genesis state; **(I5) authority consistency** — no policy or skill in `C` licenses actions outside the authority scope `I.scope` in force at its commit.

**Obligation 7.4 (Invariant-preserving commit).** Commit is permitted only if `Ĉ = C_n ⊕ ΔC` satisfies I1–I5. Validation therefore includes a mechanical invariant-checking stage — cheap, deterministic, and independent of all learned components — that acts as the type system of the state space. Candidates that violate invariants are rejected without consuming simulation budget. This obligation is the formal reason the Cognitive State Manager is the sole writer (document 00, §6.9): concentrating writes concentrates the invariant check at a single, auditable chokepoint.

### 7.4 Validation semantics

**Definition 7.5 (Validation predicate).** `Validate(C_n, Ĉ, ΔC)` is the conjunction of stage verdicts selected by `ΔC.risk`:

\[
\mathrm{Validate} = \mathrm{Inv}(\hat{C}) \;\wedge\; \mathrm{Replay}(\hat{C}, \mathcal{H}) \;\wedge\; \mathrm{Regress}(\hat{C}, \mathcal{B}) \;\wedge\; \big[\mathrm{risk} = \mathrm{high} \Rightarrow \mathrm{HumanApproval}\big]
\]

where `Inv` is the invariant check of Obligation 7.4; `Replay(Ĉ, ℋ)` re-executes a held-out experience set `ℋ ⊆ ℒ` under the candidate state (shadow simulation) and requires non-degradation beyond tolerance on the replay metrics; `Regress(Ĉ, ℬ)` runs the regression battery `ℬ` over historically critical behaviors; and the final clause implements the roadmap's `HighRiskPolicyChange ⇒ HumanApproval` property as a validation stage rather than a convention. Each stage emits a structured verdict with its own confidence, and the conjunction is **evidence-preserving**: the validation record, not just its boolean, is committed alongside the update.

Replay deserves a formal note because it is where counterfactual reasoning enters the model. Given a historical experience `X_j ∈ ℋ` with recorded context `S_j`, replay under `Ĉ` computes the *counterfactual policy distribution* `π̂(· | S_j, Ĉ)` and compares its induced outcome estimate (from simulation, re-execution in a sandbox, or model-based scoring) against both the recorded outcome `O_j` and the incumbent policy's counterfactual `π(· | S_j, C_n)`. The candidate passes only if it does not materially degrade historically successful contexts — the formal encoding of "do no harm to what already worked," which is the runtime analogue of the no-regressions discipline in software deployment, and the mechanism by which CCR avoids the silent capability regressions that unguarded continual learning invites.

---

## 8. Versioned State: The Cognitive State DAG

### 8.1 Commits and the hash chain

**Definition 8.1 (State commitment).** The committed identity of state version `n` is

\[
\mathrm{Commit}*n = H\big(\mathrm{Commit}*{n-1} \;\|\; h(X_{j(n)}) \;\|\; h(\Delta C_n) \;\|\; h(\mathrm{ValidRec}_n) \;\|\; \sigma_{I}\big)
\]

where `j(n)` indexes the motivating experience(s), `ValidRec_n` is the validation record, `σ_I` is the identity layer's signature over the preceding material, and `‖` is canonical serialization. The genesis commitment `Commit_0 = H(C_0 ‖ σ_I)` anchors the chain. This construction is an authenticated, append-only history in the spirit of hash-chained audit logs, specialized to cognitive state: each commitment binds the new state to its parent, its justifying experience, its validated update, and the identity under whose authority the commit occurred, in a single digest ([AgentBound](https://arxiv.org/html/2606.30970v1)).

The binding of the *validation record* into the commitment — not merely the update — is a deliberate strengthening over a bare history hash. It makes the claim "this state arose through validated learning" a property of the commitment itself, verifiable by any party holding the chain head: to verify a state is to verify a chain of (parent, experience, update, validation, signature) tuples, each of which is independently checkable, and none of which can be altered or reordered without invalidating every subsequent digest.

### 8.2 The state DAG

**Definition 8.2 (Cognitive state DAG).** Because updates may be explored in parallel, the general structure is a directed acyclic graph `𝒟 = (𝒱, ℰ)` with vertices `𝒱 ⊆ 𝒞` (committed states) and edges `ℰ = {(C_n, C_m) : C_m ∈ C_n.children}` labeled by the committed update. A **branch** from `C_n` is a pair of children `C_n ⊕ ΔC^A`, `C_n ⊕ ΔC^B` committed under separate transactions; the roadmap's A/B cognitive policies and shadow deployments are branch structures with an experiment protocol layered on top. A **merge** of `C_a` and `C_b` with least common ancestor `C_d` is a commit `C_m` whose update `ΔC_m = \mathrm{Merge}(C_a − C_d, C_b − C_d)` reconciles the two diffs; merge is itself a learning transaction and passes the same guards, with the additional requirement that merged policy tables be re-normalized (I2).

The DAG is the formal object that makes RQ6 well-posed. Versioning questions — snapshot granularity, branch lifetime, merge conflict semantics — are now questions about a concrete structure with a small operation set (`commit`, `branch`, `merge`, `checkout`, `revert`), each with defined preconditions and invariants. It also gives drift its formal home (§12): behavioral drift is a property of paths in `𝒟`, measurable rather than anecdotal.

### 8.3 Lineage and ancestry

**Definition 8.3 (Authenticated ancestry).** We write `C_a ⇝* C_b` iff there exists a path from `C_a` to `C_b` in `𝒟` such that every edge's commitment verifies under Definition 8.1. The **lineage** of a state `C_n` is the maximal verified chain from genesis: `Lin(C_n) = ⟨C_0, …, C_n⟩` with `C_0 ⇝* C_n`. Two states share an agent iff their lineages intersect at a verified common ancestor — which makes identity questions (roadmap RQ9) graph-theoretic: identity persists exactly as far as verified ancestry extends, and a fork creates two agents that share a past, a notion with no clean analogue in unversioned architectures.

### 8.4 Rollback semantics

**Definition 8.4 (Rollback).** A rollback from active state `C_n` to ancestor `C_k` (`C_k ⇝* C_n`) is itself a commit: `C_{n+1} = \mathrm{revert}(C_n, C_k)` whose content equals `C_k`'s content, whose parent is `C_n`, and whose update record carries `op = revert` with justification citing the incident evidence. Rollback is therefore **forward-only in history**: the DAG is never rewritten, the rolled-back-through states remain in the ledger and DAG, and the revert is auditable as a first-class event. This semantics — familiar from version-control practice but absent from every surveyed memory system — is what converts a discovered poisoning or drift incident from an unrecoverable compromise into a recorded recovery, and it composes with the ledger separation of §4.2 to guarantee that reverting beliefs never destroys evidence.

**Proposition 8.5 (Recovery completeness).** For any harmful committed update `ΔC_m` discovered at version `n ≥ m`, there exists a sequence of at most two transactions (revert to `C_{m−1}`'s content, plus any selective re-application of post-`m` benign updates as new validated commits) that restores behavior to a state containing no influence of `ΔC_m`, with full audit trail. The proof sketch is immediate from the DAG structure: content is determined by ancestry, influence is mediated by content, and revert re-points ancestry. The nontrivial engineering content — *detecting* harm at `n` that was committed at `m` — is a monitoring problem for the benchmark and security documents, not a gap in the recovery guarantee.

---

## 9. The Causal Graph: Formalization

**Definition 9.1 (Causal graph).** The causal graph at version `n` is `𝒢_n^{caus} = (𝒱_c, ℰ_c, w, \mathrm{prov})`, where vertices `𝒱_c` are typed nodes — goals, strategies, actions, outcomes, causes, learnings — drawn from the experience ledger and the state; edges `ℰ_c` are typed relations — `motivates`, `selected`, `produced`, `attributed-to`, `replaced-by`, `validated-into`; `w : ℰ_c → [0,1]` assigns each edge a confidence; and `prov` maps each edge to its attribution source. The roadmap's running example is the path `Goal → Strategy_A → Failure → ObservedCause → Strategy_B → Success → ValidatedLearning`, which in this formalism is a **causal chain**: an alternating sequence of ledger-backed nodes and attributed edges whose product of confidences gives the chain's overall confidence.

The causal graph's role in the transition system is to make learning *conditional on explanation*. Formally, a candidate update `ΔC` of `op ∈ {reweight, deprecate}` targeting policy or strategy content is required to cite a causal chain in `𝒢_n^{caus}` whose confidence exceeds a per-risk-class threshold; updates that cannot name their causal justification are inadmissible by construction, whatever their empirical support. This is the formal expression of design principle P5, and it defines the RQ5 experiment precisely: compare generalization of agents whose policy updates are conditioned on causal chains against agents whose updates cite only co-occurrence statistics over the same ledger, holding the ledger and evaluation constant. The hypothesis — causal conditioning transfers better under distribution shift — is thereby reduced to a measurable difference between two instantiations of `Propose`.

Counterfactual replay (§7.4) is the graph's second consumer: replay asks "would the candidate have succeeded where the incumbent did?" and the graph constrains that question to *mechanistically relevant* contexts — those reachable by perturbing nodes on the update's cited causal chain — rather than the whole history, which is what keeps validation computationally feasible as the ledger grows.

---

## 10. Identity and Authority: Formal Interface

**Definition 10.1 (Identity record).** The identity record is

\[
I = \langle \mathrm{pk},\; \mathrm{origin},\; \mathrm{scope},\; \mathrm{delegation},\; \mathrm{evidence} \rangle
\]

with `pk` the public key anchoring signatures `σ_I`; `origin` the provisioning record; `scope : 𝒜 → {permit, deny, escalate}` the **authority scope** mapping action classes to authorization levels; `delegation` the chain of mandates from the human principal; and `evidence` the accumulator for externally checkable attestations. The record is *not* part of cognitive state: it is the trust boundary against which state is evaluated (document 00, §4.4), and it evolves only through delegation events, which are signed and hash-chained in the same style as state commits but on a separate chain, so that authority history and learning history are independently auditable and cross-referenced.

**Definition 10.2 (Authorization guard).** `Authorize(ΔC, I, C_n) = ⊤` iff every action class that the candidate's payload could license — determined by static analysis of the payload against `scope` — is permitted or already requires escalation; candidates that would extend effective authority beyond `scope` are rejected, and candidates in the `escalate` class are converted into human-approval requests. This guard is the formal seat of the roadmap's authority-continuity property `ExecutedAction ⇒ Agent possessed required authority`, with the enforcement split it implies: the *learning* pipeline ensures no committed state licenses out-of-scope action, and the *execution* runtime (the enforce hook of document 00, §4.2) checks each action against `scope` at dispatch time, so that even a compromised cognitive state cannot silently widen the agent's authority. The split matters: authority is checked at both write time and act time, and the two checks are independently verifiable against the signed delegation chain.

---

## 11. Formal Properties and Safety Invariants

The properties below are stated as candidate invariants of the validated cognitive state transition system — the obligations that the Phase 8 formal-verification work (ProVerif-style mechanized checking) will attempt to establish against a protocol model of §7–§8 and §10. They are grouped by the layer that enforces them.

| Property | Formal statement | Enforcing mechanism | Roadmap ref. |
| --- | --- | --- | --- |
| **Update provenance** | `Committed(ΔC) ⇒ ∃X ∈ ℒ, ∃E : Validate(C, C ⊕ ΔC, ΔC) = ⊤ ∧ justification(ΔC) ∋ (X, E)` | Guard conjunction (§7.2) | RQ8 |
| **Identity continuity** | `C_m ∈ children(C_n) ⇒ VerifyChain(Commit_n, Commit_m)` | Commitment construction (§8.1) | §24 |
| **Authority continuity** | `Executed(a) ⇒ scope_{I}(class(a)) = permit` at the acting state version | Runtime enforce hook + authorization guard (§10.2) | §24 |
| **High-risk gate** | `risk(ΔC) = high ∧ Committed(ΔC) ⇒ HumanApproval ∈ ValidRec(ΔC)` | Validation predicate (§7.5) | §24 |
| **No uncommitted influence** | Hot-path policy `π_t` depends only on the last committed state: `π_t = π(· | C_{n(t)})` | Hot/cold separation (P8) |
| **Ledger immutability** | `∀i: ℒ[i]` is append-only; reinterpretation occurs in state, never in ledger | Ledger design (§4.2) | §22 |
| **Recovery completeness** | Any committed update's influence is removable by revert with intact history | Rollback semantics (§8.4, Prop. 8.5) | RQ7 |
| **Invariant preservation** | `Committed(C_n) ⇒ C_n ⊨ I1–I5` | Obligation 7.4 | — |

Two remarks on the status of these properties. First, they are **architectural invariants, not learning guarantees**: they state that whatever the system learns, it learns under discipline — nothing commits without validation, nothing executes without authority, nothing is lost without record. They do not, and cannot, state that what is learned is *good*; that is the empirical burden of the benchmark program. The distinction is the formal version of document 00's core claim that CCR contributes trustworthiness rather than raw capability. Second, the properties are deliberately stated to be **mechanically checkable**: each reduces to signature verification, chain verification, or record inspection, which is what makes the Phase 8 verification program realistic rather than aspirational — the system was designed so that its trust properties live in its logs, not in the internals of any learned component.

The converse question — which desirable properties are *not* establishable architecturally — deserves equal clarity. No architectural invariant can guarantee admission-function quality (`L` may be miscalibrated and still satisfy every property above), evaluation soundness (a compromised evaluator that passes its own provenance checks defeats the conjunction in the guard), or drift boundedness (§12 defines drift but does not bound it; bounds are policy). The threat-model document owns these residual risks; the formal model's job is to make the boundary between "guaranteed by construction" and "defended by calibration and monitoring" exact.

---

## 12. Drift, Learning Metrics, and the Formal RQ2 Statement

### 12.1 Drift

**Definition 12.1 (Behavioral drift).** Given a behavior distance `d` on policy distributions (e.g., expected total variation over a probe context distribution `𝒫_probe`), the **drift** along a lineage path is `D(C_m, C_n) = d(π(· | C_m), π(· | C_n))`, and the **accumulated drift rate** over a path is `δ(C_m ⇝* C_n) = Σ_{edges} d(π_{k}, π_{k+1})`. Drift is defined on *paths*, not pairs, which matters: a lineage that wanders and returns has high accumulated drift but low net drift, and the two quantities answer different safety questions (how much has behavior churned versus how far is it from origin). Both are computable from the DAG and the committed validation records, given a probe distribution — the choice of `𝒫_probe` is a benchmark design decision for `06-CCR-BENCHMARK.md`, and the formal model's requirement is only that probes are fixed ex ante and versioned, so that drift measurements are comparable across versions.

The identity-drift threat of the roadmap's threat model is now statable precisely: there may exist a divergence threshold `ε` beyond which the authority scope granted at provisioning no longer matches the agent's effective behavior — `D(C_0, C_n) > ε` — at which point the formal model prescribes re-authorization: a delegation-renewal event on the identity chain, gated by human review. This converts "identity drift" from a vague unease into a monitored quantity with a defined trigger, and it is only possible because drift is a function of a *versioned lineage* rather than an unversioned accumulation.

### 12.2 Learning efficiency and retention

The roadmap's evaluation metrics become well-defined against the formal objects. **Learning efficiency** is `LE = ΔPerf / N_exp`, where `ΔPerf` is the performance delta on a fixed benchmark suite between two committed versions and `N_exp` the number of ledger experiences between them; because both terms are version-anchored, `LE` is a property of a *commit range*, comparable across systems and ablations. **Retention** over horizon `h` is `Perf(C_n, task) − Perf(C_{n+h}, task)` for a task learned before `n`; stability and interference appear as the sign and size of retention across unrelated intervening updates. **Sample efficiency** is the number of grounding experiences per committed policy improvement, `|exp_{n} \ exp_{m}| / |\{commits in (m, n] targeting pol\}|`. **Provenance completeness** is the fraction of committed state content with intact derivation paths to the ledger — target: 1.0 by invariant I4, so this metric functions as a continuous audit of the invariant's enforcement.

### 12.3 RQ2 as a minimization problem

The formal frame lets RQ2 — the minimum persistent state for continuous learning — be stated as an information-theoretic question about the tuple of Definition 4.1. Define a **state ablation** `C^{-K}` as the CSO with component set `K` removed (and all citations repaired), and define the learning capacity retained as the performance of the ablated agent on the experimental ladder of document 00 relative to the full state. RQ2 is then: find the minimal `K*` such that `C^{-K*}` preserves learning capacity within tolerance — a submodular-looking optimization over the fourteen components of the CSO, executable directly on the experimental ladder (System C ≈ `C^{-{pol, caus, version, prov}}`, System D ≈ `C^{-{caus, version, prov}}`, System E = full). The formal model contributes the guarantee that such ablations are *well-defined*: because all cross-component references are typed citations under invariant I1, removing a component has a determinate meaning, and the ablation hierarchy is a lattice, not an ad hoc list of systems.

---

## 13. Summary of the Model and Symbol Table

The formal model can be compressed into four sentences. The agent `𝒜_t = ⟨M, C_t, I⟩` acts in a POMDP through an effective policy that composes frozen model generation with retrieval over committed cognitive state (§2). Experience arrives as structured, evaluated, provenance-bearing records `X_i` whose learning value is scored by an explicit functional (§3, §5). Learning is a guarded transition `C_{n+1} = F(C_n, X_t, E_t)` permitted only when admission, validation, and authorization all pass, producing a candidate-then-commit discipline with typed, invariant-checked updates (§6, §7). History is a hash-chained, signed state DAG in which identity, recovery, drift, and audit are graph properties (§8, §10–§12). Every other construct in the series — the CSO schema, the ledger format, the transaction protocol, the causal graph operations, the benchmark harness, the security model, and the GNS integration — is a specialization or an implementation of these definitions.

| Symbol | Meaning | First defined |
| --- | --- | --- |
| `𝒜_t = ⟨M, C_t, I⟩` | Agent at step `t`: model, cognitive state, identity | Def. 2.1 |
| `π_t(a | o, τ_t)` | Effective policy: retrieval `μ` composed with model distribution `p_M` |
| `X_i = ⟨S,G,A,O,E,R,κ,Λ,prov,ts⟩` | Experience record | Def. 3.1 |
| `V(X_i)` | Learning-value functional (info gain, surprise, risk, trust) | §3.2 |
| `C_n` | Cognitive State Object at commit `n` (14 components) | Def. 4.1 |
| `ℒ` | Append-only experience ledger | §4.2 |
| `pol_n : 𝒵_c × 𝒰 → [0,1]` | Policy table over context regions and strategies | §4.3 |
| `E_i = ⟨r, c, 𝒟, attr, prov⟩` | Evaluation record with confidence and channels | Def. 5.1 |
| `L(X_i, C_n) ∈ {0,1}` | Admission function with risk/calibration-dependent threshold | Def. 6.1 |
| `ΔC = ⟨op, target, payload, justification, risk⟩` | Typed candidate update | Def. 7.1 |
| `F(C_n, X_t, E_t)` | Guarded transition function | Def. 7.2 |
| `Validate` | Invariant ∧ replay ∧ regress ∧ (high-risk ⇒ human) | Def. 7.5 |
| `Commit_n` | Hash-chained, signed state commitment | Def. 8.1 |
| `𝒟 = (𝒱, ℰ)`, `⇝*` | State DAG; verified ancestry | Defs. 8.2–8.3 |
| `𝒢_n^{caus}` | Typed, confidence-weighted causal graph | Def. 9.1 |
| `I`, `Authorize` | Identity record; authority guard | Defs. 10.1–10.2 |
| `D(·,·)`, `δ(·)` | Net and accumulated behavioral drift | Def. 12.1 |

**Open formal problems** carried forward: the convergence conditions (if any) of the guarded transition process under non-stationary environments; the sample complexity of admission-threshold calibration; the interaction between confidence propagation in `𝒢^{caus}` and the evaluator-calibration loop; and the merge-semantics problem for concurrent cognitive branches, which is the weakest-developed part of the model and the likeliest place for the Phase 6 implementation to force revisions. These are stated here so that the series' remaining documents can attack them explicitly rather than discover them accidentally.

*Document 01 of the CCR series. Previous: `00-CCR-SYSTEM-OVERVIEW.md`. Next: `02-COGNITIVE-STATE-OBJECT.md` — the CSO schema, invariants I1–I5 in concrete form, and state-transition semantics at field level.*