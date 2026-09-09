# Continuous Cognitive Runtime: A Runtime Architecture for Persistent Learning in Agentic AI

**Working paper — synthesis of the CCR specification series (documents 00–08)**
**Project context:** Grafomem / GNS-GEO Identity
**Date:** 2026-09-06 · **revised 2026-09-09** (verifier-tier decomposition folded into §3/§5.2/§7.4/§11; admission function aligned with the implemented gate; causal-graph surface lessons from implementation; distillation path closes §11; citation corrections in §2.5)

**Corrections log — 2026-09-10 (ADR-0011 alignment):**
- **§11 distillation corpus — two-source formulation.** The parenthetical "(assembled under the same admission discipline as any other learning)" is replaced with the two admissible sources — (i) gate-passed Tier-A/B experience, (ii) supervised-constructed non-experience — with Tier-D experience admissible through neither. This makes the paper normatively agree with `eu-governed-agent` ADR-weight-plasticity-gated-offline-transaction (proposed), so the two cannot drift. The §3.1 tiers are the source text for that ADR and ADR-0011.

**Corrections log — 2026-09-09 (citation-verification pass, sources re-checked):**
- **LongMemEval-V2 figures disambiguated** — 40.1% is the plain-RAG **overall** accuracy; 42.8% is the plain-RAG **LME-V2-Small tier**. Both are real, both the plain-RAG baseline; each is now stated with its condition here and in docs 00 and 03 (previously "40.1%" vs "42.8%" appeared for the same quantity with no distinction).
- **CHIEF attribution stages** — the four-stage decomposition (local / planning-control / data-flow / deviation-aware) is **ours**; CHIEF contributes the machinery (hierarchical causal graph, oracle-guided backtracking, counterfactual screening). Doc 05 and the build guide, which had attributed the four stages to CHIEF, were corrected to match this synthesis.
- **OWASP** — retitled to "OWASP Top 10 for Agentic Applications (December 2025)" (was "2026 Agentic AI Top 10"); the ASI06 identifier is unchanged. Fixed here and in docs 00 and 07.
- **Zylos** — the claim "continual-learning benchmarks document exactly these failure modes" was downgraded to "practitioner reports document these failure modes," and the source is marked **non-peer-reviewed**; a same-specificity primary source is a pending citation pass.
- **MINJA figures corrected** — ">95% injection success" → "98.2% mean injection success rate, above 90% in most configurations"; ">70% attack success" → "76.8% mean attack success rate, ranging 43.3–100% across victim-target pairs" (source: [MINJA](https://arxiv.org/html/2503.03704v4), Table 1). Applied in §2.4, doc 07 §0, and doc 00 (§4.2, §9) — the two doc-00 mentions were also **repointed from the secondary [MINJA analysis] blog to the primary paper**, since a precise Table-1 figure must be sourced to the primary. *Correction to the correction:* the correction-5 verification pass was itself imprecise — it reported a "57–99%" attack-success range (the per-configuration aggregate, not the source min/max of 43.3–100%) and confirmed ">95%" as an injection **floor**, whereas the source supports only "above 90% for most configurations" (min ISR 80.0%). Both are fixed above; corrections apply to corrections.

---

## Abstract

Large language model agents can plan, use tools, and retrieve from memory, but they do not *learn* in the sense that matters for long-horizon autonomy: their behavior does not durably improve as a consequence of what they experience. The standard remedy — periodic fine-tuning of model weights — is slow, expensive, unsafe to run continuously, and hostile to accountability. We propose the **Continuous Cognitive Runtime (CCR)**, an architectural layer between a frozen foundation model and the agent runtime that converts execution experience into persistent, validated, versioned, and cryptographically attributable behavioral change. CCR rests on three abstractions: the **Experience** record, which structures what happened with evaluation and provenance; the **Cognitive State Object (CSO)**, which holds everything the agent has learned as an explicit, versioned artifact; and the **Learning Transaction**, a guarded, atomic state transition that admits only validated updates. We formalize the architecture as a validated cognitive state transition system over a POMDP, specify its components at schema level, and define an experimental program — a five-system ladder, six task domains, and ten metrics — to test where runtime learning suffices and where it fails. We ground every design decision in the current literature: MemGPT/Letta, Reflexion, ExpeL, Voyager, Agent Workflow Memory, A-MEM, Dynamic Cheatsheet, ACE, GEPA, and Memento each validate one or two CCR mechanisms while omitting the validation gate, versioned reversibility, causal structure, and identity-bound provenance that CCR integrates. The architecture's claim is not that it learns better than any of these systems, but that it learns *accountably* — and that accountability is the precondition for deploying continuously learning agents in any setting where behavior must be auditable, reversible, and attributable.

---

## 1. Introduction

### 1.1 The agentic transition and the learning gap

The past three years have produced a rapid transition from language models that answer questions to agents that act: they plan multi-step workflows, invoke tools, browse the web, write and execute code, and operate for hours or days on open-ended tasks. The architectural pattern is now standard — a foundation model wrapped in an agent runtime that manages planning, tool orchestration, and context assembly — and it works well enough that the frontier of difficulty has moved from "can the agent act?" to "can the agent improve?" The answer, in deployed systems, is largely no. Agents can be given memory — vector stores, conversation logs, retrieval-augmented context — but memory is not learning. An agent that recalls "Tool A failed yesterday" has memory; an agent that concludes "under context X, prefer Tool B because Tool A fails with high probability under these conditions" has learned. The distance between those two sentences is the research problem this paper addresses.

The standard remedy for behavioral improvement is fine-tuning: collect demonstrations or rewards, update weights, redeploy. This works but has three disqualifying properties for continuous deployment. First, it is **slow and expensive**: fine-tuning cycles are measured in days or weeks, not the seconds-to-minutes timescale of agent experience. Second, it is **unsafe to run continuously**: online gradient updates on live experience invite catastrophic forgetting, reward hacking, and poisoning, and practitioner reports document these failure modes ([Zylos Research](https://zylos.ai/research/2026-04-09-continual-learning-catastrophic-forgetting-ai-agents/) — a non-peer-reviewed practitioner report; a primary source at the same specificity is a pending citation pass). Third, it is **unaccountable**: a weight update is an opaque, high-dimensional change; one cannot audit *what* was learned, *from which experiences*, *under whose authority*, or *how to undo it*. Any deployment context that requires auditability — which is to say, any serious one — cannot accept continuous fine-tuning as the learning mechanism.

### 1.2 The hypothesis

We propose that a large and practically important class of agent learning can occur **outside model weights**, in a runtime layer that manages the agent's persistent cognitive state. The hypothesis is:

\[
\mathrm{Agent}*{t+1} = \mathrm{FoundationModel} + \mathrm{CognitiveState}*{t+1}
\]

where the foundation model remains frozen and all learning is expressed as updates to an explicit, versioned, validated state object. This is not a claim that weight updates are never necessary — the question of when they are is one of our research questions — but that they are not the *default* venue for learning, and that the runtime layer is the right default for a large class of experience-dependent improvements: which tools to use, which strategies to prefer, which procedures to reuse, which sources to trust.

### 1.3 Contributions

This paper makes four contributions. **(1) Architecture:** the Continuous Cognitive Runtime, a four-layer stack (foundation model → agent runtime → cognitive runtime → identity/authority) with eleven modules organized into experience, memory, learning, and control planes (§4). **(2) Formal model:** a validated cognitive state transition system over a POMDP, with typed update operators, an admission function, a validation predicate, and a hash-chained state DAG (§5). **(3) Specifications:** the Cognitive State Object, Experience Ledger, Learning Transaction, Causal Cognitive Graph, and GNS identity integration at schema and protocol level (§6). **(4) Experimental program:** a pre-registered methodology with a five-system ladder, six task domains, ten metrics, and nine research questions restated as falsifiable hypotheses (§7). The architecture is grounded throughout in the strongest comparable systems from the literature, and we are explicit about what it does and does not claim over them (§8).

---

## 2. Related Work

### 2.1 Agent memory systems

The closest philosophical ancestor is **MemGPT/Letta**, which pioneered the OS-inspired view of agent memory: tiered storage, self-editing memory blocks, and persistent agent state in a database, with the explicit framing of the LLM as a process and memory as its address space ([MemGPT](https://www.letta.com/blog/deeplearning-ai-llms-as-operating-systems-agent-memory/)). Letta's AgentState records made agents stoppable, restartable, and portable ([Letta](https://blog.stackademic.com/letta-platform-for-stateful-llm-agents-a83b58a1c926)). CCR inherits this framing wholesale; the divergence is that MemGPT's memory writes are agent-initiated edits without an independent evaluation gate, and there is no transactional validation between "the agent decided to remember this" and "this now conditions all future behavior." **A-MEM** builds a self-organizing Zettelkasten memory network with link generation and memory evolution ([A-MEM](https://arxiv.org/abs/2502.12110)), but evolution there means reorganization of stored content, not validated behavioral change with lineage. **Mem0** and its research variant provide production-grade memory extraction and retrieval, and the security analysis of their attack surface (MINJA) is foundational to our threat model (§9).

### 2.2 Experiential learning without weight updates

A convergent set of results demonstrates that meaningful learning can occur at the runtime layer. **Reflexion** showed that verbal reflection on failures, carried in an episodic buffer, improves performance substantially without weight updates, reaching 91% pass@1 on HumanEval ([Reflexion](https://arxiv.org/abs/2303.11366)). **ExpeL** generalized this to cross-task experiential learning, extracting transferable insights from success/failure pools ([ExpeL](https://www.alphaxiv.org/abs/2308.10144)). **Voyager** demonstrated open-ended skill acquisition in Minecraft through an ever-growing executable skill library with zero-shot transfer ([Voyager](https://arxiv.org/abs/2305.16291)). **Agent Workflow Memory** induced reusable workflows from trajectories, both offline and online, improving relative success rates by 24.6% on Mind2Web and 51.1% on WebArena ([AWM](https://arxiv.org/abs/2409.07429)). **Dynamic Cheatsheet** endowed black-box models with persistent evolving memory, doubling Claude 3.5 Sonnet's AIME accuracy ([Dynamic Cheatsheet](https://arxiv.org/abs/2504.07952)). **ACE** treated contexts as evolving playbooks with a Generator–Reflector–Curator loop, gaining +10.6% on agent benchmarks ([ACE](https://arxiv.org/abs/2510.04618)). **GEPA** showed that reflective prompt evolution can outperform reinforcement learning with up to 35× fewer rollouts ([GEPA](https://arxiv.org/abs/2507.19457)). **Memento** formalized the pattern as a memory-augmented MDP with case-based reasoning, reaching top-1 on GAIA validation with frozen weights ([Memento](https://arxiv.org/html/2508.16153v2)).

These systems collectively establish that runtime learning is *viable*. What they do not establish is that it is *accountable*: none has an admission gate, versioned reversibility, causal structure, or identity-bound provenance. The gap is not capability but discipline, and it is the gap CCR fills.

### 2.3 Causal reasoning in agents

The **CHIEF** framework (2026) demonstrated that treating agent execution logs as flat sequences fails at failure attribution, while reconstructing them into a hierarchical causal graph with counterfactual screening substantially outperforms eight baselines on the Who&When benchmark ([CHIEF](https://arxiv.org/html/2602.23701v1)). We adapt CHIEF's pipeline — hierarchical causal graph construction, oracle-guided backtracking, counterfactual screening — into four attribution stages in CCR's causal graph: local, planning-control, data-flow, deviation-aware (§6). The stage decomposition is ours; the counterfactual-screening machinery it wraps is CHIEF's. The theoretical anchor is Pearl's counterfactual machinery: the abduction–intervention–prediction procedure that computes "what would have happened had a different action been taken" ([Counterfactual Credit Assignment](https://arxiv.org/html/2011.09464v2)). The **Causal Agent** framework maintains persistent causal graph structures in memory ([Causal Agent](https://arxiv.org/html/2408.06849v2)), but populates them from external causal analysis tasks rather than the agent's own evaluated history.

### 2.4 Security and identity

**MINJA** (Memory Injection Attack) achieved a 98.2% mean injection success rate (above 90% in most configurations) and a 76.8% mean attack success rate (ranging 43.3–100% across victim-target pairs) against production-style memory architectures through query-only interaction ([MINJA](https://arxiv.org/html/2503.03704v4), Table 1). **MemoryGraft** planted fabricated successful experiences that agents later imitated ([WorkOS](https://workos.com/blog/ai-agent-memory-poisoning)). The **OWASP Top 10 for Agentic Applications (December 2025)** classified memory and context poisoning as ASI06 ([OWASP](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/)). On identity, W3C Verifiable Credentials 2.0 and DIDs 1.1 provide the standards substrate ([W3C VC 2.0](https://www.w3.org/TR/vc-data-model-2.0/), [W3C DID 1.1](https://www.w3.org/TR/did-1.1/)); the OpenID Foundation's agentic-identity work standardizes delegated authority ([OpenID Foundation](https://openid.net/wp-content/uploads/2025/10/Identity-Management-for-Agentic-AI.pdf)); and the authenticated-delegation framework extends OAuth 2.0/OIDC with agent-ID and delegation tokens ([arXiv:2501.09674](https://arxiv.org/html/2501.09674v1)). **AgentBound** binds actions to policy snapshots via governance receipts ([AgentBound](https://arxiv.org/html/2606.30970v1)).

### 2.5 Benchmarks

**LongMemEval-V2** formalizes agent memory evaluation with `Insert(trajectory)` and `Query(question)` operations over histories reaching 115M tokens, where questions are constructed to be near-unanswerable without the trajectory history (a simple RAG baseline reaches 40.1% overall, while consolidated memory designs perform substantially better) ([LongMemEval-V2](https://arxiv.org/html/2605.12493v1)). **AblationBench** studies automated planning of ablation studies ([AblationBench](https://arxiv.org/html/2507.08038v2)); §7 borrows its discipline — contributions decomposed along explicit axes — rather than its automation machinery. The task-domain axes used in §7.2 (scope × content, plus an experience-dependency axis we add) are ours; we know of no published benchmark that fixes them, and we say so rather than borrow authority.

---

## 3. The Problem: Memory Is Not Learning

The dominant pattern in deployed agents is a loop of the form *prompt → LLM → reasoning → tool/action → result → response*, optionally augmented with retrieval over stored history. This pattern has a structural limitation that no amount of retrieval sophistication removes: **storing information is not equivalent to learning from it.** A store that cannot alter behavior is an archive, and the field's rapid accumulation of memory infrastructure has widened the gap by making it easy to mistake storage sophistication for adaptation.

The distinction is empirically consequential. Systems that only retrieve (RAG-style) plateau quickly on experience-dependent tasks, while systems that *transform* experience — into reflections, skills, workflows, or playbook entries — show compounding gains. In LongMemEval-V2, a plain RAG baseline over trajectories reached just 40.1% overall accuracy, while memory designs that consolidate trajectories into events and strategy notes performed substantially better ([LongMemEval-V2](https://arxiv.org/html/2605.12493v1)). The transformation is the learning; the storage is the substrate.

The core research question is therefore: **what runtime architecture allows an agent to convert execution experience into persistent, validated behavioral change?** The question has four sub-requirements that existing systems do not jointly satisfy: **admission control** (not every experience should modify behavior — failures can be noise, successes accidental, feedback adversarial), **versioned reversibility** (any committed change can be rolled back), **causal structure** (learning records *why* a change followed, not just *that* it did), and **attributability** (every transition is bound to an identity with a verifiable evidence chain). These four properties are what a system needs to survive the security realities of §9 and the accountability requirements of real deployment, and they are what cannot be retrofitted cheaply onto a retrieve-and-stuff memory layer. There is also a fifth requirement, subtler than the four because it concerns not the machinery but the *claim*: the learning must be **referenceable** — every learning claim must name the reference against which improvement is measured. The space this requirement carves out is the subject of §3.1, and it turns out to partition the whole question of where agents can learn at all.

### 3.1 The space partitions by reference availability

"Did the agent learn?" is only well-posed against a reference. That observation, which implementation forced on us (§8.1), partitions the space of behavior changes into four tiers with different honest claims:

- **Tier A — verifiable by construction.** Domains with a mechanical oracle: tests pass, builds compile, transactions reconcile, invariants hold. Here learning claims are real and the admission gate's numbers mean what they say — the reference is the environment itself.
- **Tier B — human-as-reference.** Domains where correctness is a judgment: the agent can learn *a named reference's* documented patterns, preferences, and procedural completeness — measurably — but a declining override rate is an alarm to investigate, not a KPI to optimize (Goodhart applies to the reference as much as to the learner).
- **Tier C — sparse outcomes.** Domains where outcomes arrive rarely and late: calibration claims are licensed only on the slice where outcomes exist, not across the domain.
- **Tier D — disposition correctness.** Domains where the right behavior is a fixed disposition (refusal classes, hard constraints): the correct measurement is *undefined-not-zero* — the absence of a learning signal is permanent and by design; these domains are frozen, not trainable.

The standing rule, which every experimental claim in §7 obeys: **every learning claim ships with its reference named.** The tiers reappear throughout the paper — they condition the evaluation model (§5.2), qualify the hypotheses (§7.4), and define where weight updates are permitted at all (§11).

---

## 4. The CCR Architecture

### 4.1 The layered stack

CCR claims a specific position in the agentic stack, justified by the layers' different rates of change, trust requirements, and ownership:

```text
HUMAN PRINCIPAL — goals · oversight · high-risk approvals
        │ delegation
        ↓
IDENTITY + AUTHORITY (GNS) — identity · delegation · evidence · authority scopes
        ↓
AGENT RUNTIME — planning · tool orchestration · execution · context assembly
        ↓
CONTINUOUS COGNITIVE RUNTIME (CCR)
  Experience Plane:  Experience Capture · Experience Ledger
  Memory Plane:      Memory Engine · Skill Manager · Policy Engine · Causal Graph
  Learning Plane:    Outcome Evaluator · Learning Engine
  Control Plane:     Cognitive State Manager · Versioning & Rollback · Provenance Recorder
        ↓
FOUNDATION MODEL (frozen weights) — general reasoning · language · world knowledge
```

The foundation model changes on the scale of months and is owned by a lab; the agent runtime changes on the scale of deployments and is owned by the integrator; the cognitive state changes on the scale of *individual experiences* and is owned, in a meaningful sense, by the agent's principal; the identity layer changes on the scale of delegation events and must be verifiable by third parties. Forcing these rates into one artifact is the root cause of fragility, opacity, and unaccountability.

### 4.2 Design principles

Eight principles govern the architecture:

**P1 — Separation of stable intelligence from adaptive state.** The foundation model is the reasoning substrate and remains frozen; everything that changes because experience happened lives in the cognitive state. This buys model independence, instant rollback, and a clean security boundary.

**P2 — Learning is a transaction, not a side effect.** Every behavioral modification passes through capture → evaluate → propose → simulate/replay → validate → commit → version → provenance, and exists in a lifecycle state machine. A change that fails validation is retained for research but exerts zero behavioral influence.

**P3 — Experience is a first-class object.** The atomic unit is the structured experience record `X_i = ⟨S, G, A, O, E, R⟩` with confidence, causal links, and provenance — not an interaction transcript.

**P4 — Evaluation is independent of the learner.** The Evaluator is architecturally separate from the acting agent; the component that benefits from a positive evaluation never issues it. Independence is necessary but not sufficient — the harder question is what the independent evaluator evaluates *against*. That is the reference problem of §3.1: in Tier A the environment answers it; in Tier B the named human reference does; in Tier D the question is correctly unasked.

**P5 — Causality over correlation.** Learning records preserve causal links because causal structure enables generalization, counterfactual validation, and meaningful rollback.

**P6 — Reversibility and lineage by construction.** Every state has a content-addressed identity, a parent pointer, and a complete derivation history; branching, A/B policies, and rollback are consequences of the representation.

**P7 — Identity and authority bound to state.** Authority scopes are evaluated against state versions; high-risk policy changes route through human approval.

**P8 — Hot path never blocks on learning.** Execution runs synchronously; learning runs asynchronously on a cold path; committed state versions are picked up by subsequent reasoning cycles.

### 4.3 The experience loop

The runtime dataflow separates a **hot path** (observe → reason → act → observe result → evaluate, running at interactive latency) from a **cold path** (learning pipeline, running asynchronously). The paths are joined only by the **admission gate** — the architectural embodiment of the question "should this experience modify future behavior?" — which applies the admission function `L(X)`. Admitted experiences trigger a learning transaction; rejected ones are archived with reasons. The hot path reads only committed state, so concurrent learning experiments cannot perturb live behavior.

---

## 5. Formal Model

### 5.1 The agent

A CCR agent at decision step `t` is `𝒜_t = ⟨M, C_t, I⟩`, where `M` is the frozen foundation model, `C_t` the cognitive state, and `I` the identity record. The agent's observable behavior is its effective policy:

\[
\pi_t(a \mid o, \tau_t) = \sum_{k \in \mathcal{K}_t} \mu(k \mid o, \tau_t, C_t) \cdot p_M(a \mid o, \tau_t, k, C_t.\mathrm{policies}, C_t.\mathrm{skills})
\]

where `𝒦_t ⊆ Retrieve(C_t, o, τ_t)` is the retrieved cognitive context, `μ` the retrieval distribution, and `p_M` the model's action distribution. This generalizes Memento's policy decomposition to full typed cognitive state.

### 5.2 Experience

An experience is `X_i = ⟨S_i, G_i, A_i, O_i, E_i, R_i, κ_i, Λ_i, π_i^{prov}, τ_i^{ts}⟩` with evaluation `E_i = ⟨r_i, c_i, 𝒟_i, attr_i, π_i^{eval}⟩` carrying confidence and channels. The learning-value functional, as implemented (reference values: threshold 0.55, `w_trust = 0.5`, `w_info = 0.2`, ceiling 0.70, `min_evidence = 3`):

\[
V(X_i) = \big(w_{\mathrm{trust}} \cdot \mathrm{Trust}(X_i) + w_{\mathrm{info}} \cdot \mathrm{Info}(X_i)\big) \cdot \mathrm{support}(X_i)
\]

The load-bearing term is **support**: `support(X_i) = min(1, n / min\_evidence)`, where `n` is the size of the *union* of root supports behind the experience — union, not sum, so correlated evidence arriving through one channel costs like one root, not nine (invariant I6; this is the structural anti-poisoning term, §9). A risk term enters the *authorization* stage of the learning transaction rather than the value functional — risk gates the change, it does not inflate its apparent value. The weights `w` remain versioned cognitive state (the L4 meta-learning recursion). The earlier linear four-term formulation in the specification series is superseded by this one; the support factor is absent from it, and the support factor is where the defense lives.

### 5.3 The Cognitive State Object

The CSO is a 14-component tuple: `C_n = ⟨mem, exp, skills, pol, strat, goals, prefs, conf, 𝒢^{caus}, eval, prov, v, parent, I.ref, v_M⟩`. The critical distinction is that the **experience ledger is not versioned** (history is immutable) while the **cognitive state is** (theories about history are revisable). This separation gives rollback clean semantics: reverting to `C_k` changes what the agent will do, while the full ledger remains available.

### 5.4 The guarded transition

The cognitive-state transition is:

\[
C_{n+1} = F(C_n, X_t, E_t) \iff L(X_t, C_n) = 1 \wedge \mathrm{Validate}(C_n, \hat{C}_{n+1}, \Delta C) = \top \wedge \mathrm{Authorize}(\Delta C, I, C_n) = \top
\]

with typed update operators `ΔC = ⟨op, target, payload, justification, risk⟩`, invariant preservation obligations (I1–I5), and a validation predicate that includes invariant checking, counterfactual replay, regression testing, and human approval for high-risk changes. The contrast with prior work is the point: Memento's memory transition is `M_{t+1} = M_t ∪ {(s_t, a_t, r_t)}` — unconditional append; CCR's `F` is defined but conditionally applied.

### 5.5 Versioned state

The state commitment is `Commit_n = H(Commit_{n-1} ‖ h(X_{j(n)}) ‖ h(ΔC_n) ‖ h(ValidRec_n) ‖ σ_I)`, forming a hash-chained DAG. Rollback is forward-only: a revert is a new commit whose content equals an ancestor's, preserving full history. The recovery guarantee (Prop. 8.5): any harmful committed update's influence is removable by revert with intact history.

### 5.6 Causal graph

The causal graph `𝒢^{caus} = (𝒱_c, ℰ_c, w, prov)` has six node types (goal, strategy, action, outcome, cause, learning) and six edge types, with every edge carrying confidence and attribution provenance. Chain confidence is the product of edge confidences — penalizing long chains of weak attributions. The graph serves four query patterns: strategy evidence, counterfactual replay scoping, failure explanation, and generalization transfer.

Three constraints from implementation belong in the model, because without them the graph is an attack surface rather than an asset. **(1) Attribution is derived, not declared.** An edge's `attributed_by` field is computed from the signed evaluation channel; it is *structurally unrepresentable as a caller-supplied parameter*, so a caller can no more assert authorship of an attribution than of a signature. **(2) Edges are born falsifiable.** Every edge carries a `counterfactual_pattern` (bias, anomaly) at creation — the prediction under which the attribution would be wrong — and attributed edges are subject to replay-against-pattern before they carry weight; edges that fail replay are deprecated, not deleted (the failure record is itself evidence). **(3) Influence is capped in aggregate.** Causal edges may modulate admission — a surviving, calibrated, grounds-citing edge adds an uplift `trust_e · (1 + γ · conf)`, reference `γ = 0.1` — but the *sum* of causal uplift applied to any single gate decision is hard-capped (`ΣΔV ≤ 0.05`), enforced inside the gate. The cap is what survives correlated forgery: twenty edges sharing one channel still hit the same aggregate ceiling. Both caveats are stated in their register: the cap sizes *typical* influence — it is a conventional bound, not a structural one, and it is per-decision, not per-campaign.

### 5.7 Identity and authority

The identity record `I = ⟨pk, origin, scope, delegation, evidence⟩` is DID-anchored, with authority as a three-valued scope (`permit`/`deny`/`escalate`) evaluated per state version. The core invariant: **learning changes competence; only delegation changes authority.**

---

## 6. Specifications

The full specifications are given in the companion documents; this section summarizes the key schemas.

**Cognitive State Object (document 02):** field-level schema for all 14 components, with provenance as a structural field (not a log), confidence as a first-class decaying quantity, supersession replacing mutation, and content-addressed self-certification. The CSO is a read-mostly object: six legal operations (`read`, `propose`, `commit`, `branch`, `merge`, `revert`), no update-in-place, no delete.

**Experience Ledger (document 03):** append-only, hash-chained, Merkle-checkpointed sequence of experience records, gate decisions, annotations, and checkpoints. Event-sourcing semantics: the log is truth, all reads are rebuildable projections. Verifiability: per-record SHA-256 chains, periodic signed Merkle checkpoints (Certificate Transparency-style), inclusion and consistency proofs. Honest security framing: tamper-*evident*, not tamper-*proof*; checkpoints must leave the system.

**Learning Transaction (document 04):** nine-stage protocol (capture → evaluate → admit → propose → simulate/replay → validate → authorize → commit → version+provenance), six-state lifecycle machine, three deployment topologies (shadow, canary, branch-and-compare), forward-only rollback with selective re-application. Saga-shaped execution with ACID commit semantics.

**Causal Cognitive Graph (document 05):** CHIEF's counterfactual-screening machinery adapted into our four-stage attribution pipeline for edge construction; counterfactual patterns on every edge making attributions falsifiable by replay; confidence propagation penalizing speculative chains; derived (not declared) attribution and aggregate-capped admission influence per §5.6.

**Security Model (document 07):** seven threat classes mapped to OWASP ASI categories; seven defense layers (write-time controls → monitoring); MINJA deep-dive showing why structural defenses succeed where heuristic filters fail; recovery procedures with circuit breakers, scope restriction, and four-step rollback.

**GNS Integration (document 08):** DID-anchored identity with state commitments as identity attributes; VC-based delegation mandates with drift constraints; identity-chain anchoring of state DAG and ledger checkpoints; verifiable-presentation evidence chains with selective disclosure.

---

## 7. Experimental Program

### 7.1 The system ladder

Five systems, each a restriction of the full CCR codebase:

| System | Components | Tests |
| --- | --- | --- |
| A | Foundation model + prompt | Baseline |
| B | A + retrieval memory | L1 memory helps |
| C | B + experience store + evaluator | Structured evaluation > raw retrieval **only where the raw channel can be corrupted**; over a truthful outcome channel B and C are indistinguishable — **partially falsified, see doc 06 §2.1** (C−B = +0.011 mean over 3 seeds; C loses to an honest B on one seed) |
| D | C + policy learning | Validated learning > unvalidated |
| E | D + causal graph + versioning + provenance | Full CCR |

### 7.2 Task domains

Six domains organized on two axes we define here (scope: single-task ↔ cross-session; content: episodic ↔ semantic/strategic) plus a third, experience dependency — how much of the task's difficulty is invisible without history: tool selection, software debugging, long-horizon workflows, research agents, operations agents, personal assistants (the harm case). The axes are ours; we claim no external benchmark authority for them (§2.5).

### 7.3 Metrics

Ten metrics: learning efficiency (LE), retention, generalization, stability, recovery, sample efficiency, drift, provenance completeness, safety (harmful update rate), and cost (token budget).

### 7.4 Key experiments

**RQ1:** Runtime learning achieves ≥80% of fine-tuned baseline performance on experience-dependent tasks **in Tier-A domains** (mechanical oracle present). In Tier-B domains the analogue is stated against the named human reference: ≥80% of the reference's documented judgment patterns reproduced, with the reference's override rate reported as a monitored alarm, not optimized. In Tier-C domains the claim is restricted to the calibrated slice. Tier-D domains carry no RQ1 claim — there is nothing to learn (§3.1).

**RQ3:** Admission gate improves learning signal-to-noise by ≥2× (Tier A; in Tier B, signal-to-noise is measured against the named reference's override record).

**RQ4:** Validation reduces harmful updates by ≥90% with ≤20% performance cost. In Tier A, "harmful" is oracle-defined (regression, invariant violation). In Tier B, "harmful" means *divergence from the named reference* — the oracle is the reference, and the pre-registration names it per domain. In Tier D, harmful-update rate is not a statistic: the domains are frozen, so the rate is undefined, not zero.

**RQ5:** Causal-chain retrieval generalizes ≥15% better than flat retrieval on context-shifted tasks.

**RQ7:** Security model detection rate against a **pre-registered, published** poisoning-attack corpus (MINJA-style query-only injection, forged-outcome text, and memory-graft variants), with the **detection rate and false-positive rate reported, not asserted**, and the corpus fixed and citable *before* the run. The claim is deliberately not "100%": a detection rate measured against attacks the authors designed is tautological, so RQ7 is registered against a corpus the authors did not construct to be caught, and the rate is whatever the run yields — the pre-registration fixes the corpus and the metric, not the outcome.

All hypotheses are pre-registered with metrics, thresholds, and success criteria fixed before experiments run. Per §3.1, every hypothesis above ships with its reference named: the tier each claim lives in, and for Tier-B claims the identity of the human reference, is part of the pre-registration — a claim without a named reference is not registered.

---

## 8. What CCR Does Not Claim

CCR does not claim better raw task performance than Memento on deep research, better memory organization than A-MEM, or better prompt optimization than GEPA — those are mechanism-level comparisons that the architecture explicitly defers. CCR modules are designed to *host* such mechanisms; the claim is at the architecture level: whatever mechanisms win those comparisons, deploying them for continuous learning in accountable systems will require the transactional, versioned, provenance-bearing envelope that only CCR currently specifies. If that claim is wrong — if validation gating costs more performance than it protects — the experimental ladder is constructed precisely to detect it.

### 8.1 What implementation has already taught

This synthesis describes the architecture as specified; the reference implementation (public, specification-driven, with conformance-style test discipline throughout) has already moved several parts of it past the paper's original framing — and not only by refinement: it **falsified one of the ladder's hypotheses** and **exposed one blind spot** as well as sharpening three mechanisms. §5.2/§5.6 above are stated in the post-implementation form. The refinements:

- **The admission function's defense is a separate term, not a weight.** The support factor (union-not-sum root support, §5.2) is what makes correlated low-trust evidence expensive; it is absent from the specification series' linear formulation.
- **Every channel that feeds the gate is a surface — including the causal one.** The causal graph's influence on admission required the three constraints of §5.6 (derived attribution, born-falsifiable edges, aggregate cap), each motivated by a specific forgery class found during implementation, none present in the original specification.
- **The evaluation model is tiered, not uniform.** P4's independent evaluator answers "who evaluates"; implementation forced the prior question — "against what reference?" — and §3.1's four tiers are the answer. The verifier problem known from RL with verifiable rewards (the verifier, not the policy, becomes the attack surface) reappears at the runtime layer: in Tier B the reference itself is the component that must be protected from optimization pressure.

And the two that are not improvements:

- **A hypothesis was falsified: the C rung.** The ladder claimed "structured experience > raw retrieval." Run against an *honest* B arm (one that can read truthful outcome text), C−B was +0.011 in the mean over three seeds and C *lost* to B on one seed (doc 06 §2.1). The advantage is real only where the raw outcome channel can be corrupted; over a truthful channel B and C are empirically indistinguishable. The original phrasing was an artefact of a crippled B arm, and the ladder claim (§7.1) and the C→B benchmark condition were both narrowed accordingly. The differentiator is evaluation-channel *integrity under forged text*, not structure per se.
- **Replay is blind at cold start.** Simulation/replay validates a proposed update against the incumbent's history — so it cannot protect a region with *no* incumbent history: the very first commit in a fresh domain has nothing to replay against. This is a genuine gap, not a tuning problem. The compensating control is the read-time confidence floor (a low-history region is treated as low-confidence at read time), which *bounds* the exposure rather than closing it — a mitigation, not a fix, and named as one.

---

## 9. Security and Trust

Continuous learning converts the agent's history into part of its attack surface. CCR's defense is structural: the admission gate, independent evaluation, validation, versioning, and provenance convert poisoning from a silent, persistent compromise into a detectable, attributable, recoverable incident. The MINJA attack succeeds against naive systems because they lack the validation gate; CCR's gate is the defense. But the gate is also the target: every channel that feeds it — evaluation, provenance, and causal attribution alike — is a surface, and the defense must therefore live in the gate's arithmetic (union-not-sum support, §5.2; the aggregate uplift cap, §5.6), not only around it. The honest limitation: no architecture eliminates the threat surface; the goal is to raise attack cost, bound blast radius, and guarantee recoverability.

---

## 10. Cryptographic Cognitive Lineage

The state commitment chain and identity-chain anchoring make the claim "this state came from this previous state through this experience and this validated update" *provable to a third party*. Lineage verification reduces to three mechanical checks: DAG chain verification, identity-chain signature verification, and cross-chain consistency — no trusted party, no access to cognitive content required. Evidence chains are delivered as W3C verifiable presentations with selective disclosure for privacy.

---

## 11. Discussion

**When CCR suffices:** experience-dependent improvements where the foundation model's reasoning is adequate but the agent's strategy, tool choice, or procedure is suboptimal — tool selection, debugging patterns, workflow optimization, preference learning.

**When fine-tuning is necessary:** when the model's core reasoning about the domain is deficient (not just its strategy), when the required knowledge is too voluminous for context injection, or when latency constraints preclude retrieval. CCR's experience ledger is, in fact, an unusually high-quality data source for such retraining — and the architecture makes that sentence operational rather than aspirational:

**The distillation path.** Weight plasticity is a **gated, offline, revertable transaction — never an online reflex.** The pipeline is: experience ledger → curated training corpus (from **two admissible sources**: (i) gate-passed experience restricted to Tier-A/B domains, and (ii) supervised-constructed examples that are not experience at all — e.g. refusal trained from correct examples; **Tier-D experience is admissible through neither**) → offline weight update → weight admission through the same transaction machinery as any ΔC, with human co-signature on the admission → deployment as a new, versioned `v_M` with forward-only rollback (the prior weights are an ancestor in the DAG, and reverting is a new commit, not a time machine). The online alternative fails twice over: no reference exists at reflex timescale to gate against, and a weight update is undiffable — there is nothing to revert *to* in the contents, only the whole prior artifact. Offline, gated admission is what makes the update verifiable *first* and permitted *second* — the architecture does not make the unverifiable update safer; it makes the update verifiable, then allows it. Tier-D domains (§3.1) are frozen *with respect to the CCR gate*: no corpus drawn from Tier-D **experience** is admissible for weight updates through the gate, because the gate has no reference against which to evaluate it — which is what makes the domain Tier-D. That is a claim about the learning *signal*, not about trainability in general: absence of an admissible experience corpus does not imply absence of a trainable one. Refusal behaviour, for instance, is trainable from *correct examples* — but that is a curated corpus of correct dispositions entering through ordinary supervised construction, not evaluated experience passing the CCR admission gate.

**The unified answer.** §3.1's partition and this path together answer the question the introduction poses — where can agents learn at all, and how deep: *the measurable space for dynamic agentic learning is the set of behavior changes for which a reference can be named* — held at the runtime layer by default, admitted to the weight layer only through the same gate, and everywhere subject to admission, reversibility, causal falsifiability, and attribution.

**Limitations:** the cold path adds latency and cost (validation, simulation, replay); the admission function's calibration is an open problem; merge semantics for concurrent branches is the weakest-specified operation; the architecture assumes a cooperative deployment environment (the insider adversary is addressed through provenance and audit, not prevention).

**Scalability:** ledger growth is managed by consolidation with provenance-preserving compaction; the hot path reads projections, not raw history; the causal graph is queried over the active subgraph.

**Multi-agent learning:** deferred to future work; the state DAG generalizes to shared structures, and cross-agent provenance requires cross-identity attestation.

---

## 12. Future Work

Multi-agent shared learning, federated cognitive state, decentralized learning, formal verification of the eleven security properties (Phase 8, ProVerif), autonomous skill discovery, and the open formal problems: convergence conditions of the guarded transition under non-stationarity, sample complexity of admission-threshold calibration, and confidence propagation in the causal graph.

---

## 13. Conclusion

The Continuous Cognitive Runtime is an architecture for making agent learning *accountable*: persistent, validated, reversible, and attributable. Its claim is not that it learns better than any existing system, but that it learns *under discipline* — and that discipline is the precondition for deploying continuously learning agents in any setting where behavior must be auditable. The architecture is specified, the formal model is stated, the security model is mapped, and the experimental program is pre-registered — with each hypothesis tied to the reference tier in which it is testable. The remaining work is to build it and find out where it works; the reference implementation has begun, and its first lessons are already folded back into §5 and §8.1.

The roadmap's closing image stands: the cognitive runtime would manage the evolving state of intelligent processes much as an operating system manages the state of computational processes. Operating systems did not make hardware faster; they made computation *ownable, interruptible, and accountable*. CCR aims at the same contribution one level up the stack: not to make models smarter, but to make their learning **persistent, validated, reversible, and attributable** — the properties without which "an agent that learns from what it just did" remains a demo rather than an institution.

---

*This paper synthesizes the CCR specification series (documents 00–08). The series is available as working documents; the experimental program is pre-registered in the ledger.*