# 06 — CCR Benchmark: Experimental Methodology

**Continuous Cognitive Runtime (CCR) — Document 6 of the CCR specification series**
**Status:** Working draft v0.1 — personal working document, intended for later refinement toward an arXiv publication
**Depends on:** `00-CCR-SYSTEM-OVERVIEW.md` (§19–21), `01-CCR-FORMAL-MODEL.md` (§12 metrics), `02-COGNITIVE-STATE-OBJECT.md` (ablation lattice), `05-CAUSAL-COGNITIVE-GRAPH.md` (RQ5)
**Feeds:** `Continuous-Cognitive-Runtime.md` (research paper), Phase 1–8 development roadmap

---

## 0. Executive Summary

This document specifies the **experimental methodology** for evaluating the Continuous Cognitive Runtime: the benchmark tasks, the system ladder, the metrics, the experimental protocol, and the analysis plan. The architecture (document 00) and formal model (document 01) make claims that are falsifiable only through measurement: that learning can occur without weight updates, that causal memory generalizes better than flat retrieval, that validation-gated commits improve safety without sacrificing performance, and that versioned state enables recovery. This document turns those claims into testable hypotheses with defined procedures, baselines, and success criteria.

The design is grounded in two recent empirical results that shape the methodology. First, **EvoMemBench** (2026) demonstrated that memory systems must be evaluated along two axes — memory scope (in-episode vs. cross-episode) and memory content (knowledge-oriented vs. execution-oriented) — because no single memory form works consistently across settings, and memory can *hurt* easy tasks when it introduces irrelevant evidence ([EvoMemBench](https://arxiv.org/html/2605.18421v2)). This finding directly informs the CCR benchmark's task selection and its metric design: we measure not just *whether* learning helps, but *when* it helps and *when it hurts*. Second, the **ablation-study methodology** from automated AI research (AblationBench) provides the template for decomposing CCR into components and evaluating each contribution independently ([AblationBench](https://arxiv.org/html/2507.08038v2)) — the experimental ladder of document 00 is exactly such a decomposition, and this document makes it rigorous.

The methodology's central commitment is **comparative honesty**: every claim is tested against the strongest available baseline, every metric is pre-registered, and every failure mode is anticipated with a defined response. The goal is not to prove CCR works but to find out *where* it works, *where* it fails, and *why* — the roadmap's RQ1–RQ9 restated as an experimental program.

---

## 1. Research Questions as Hypotheses

The roadmap's nine research questions are restated as falsifiable hypotheses with measurable outcomes:

| RQ | Hypothesis | Primary metric | Success criterion |
|---|---|---|---|
| **RQ1** | Runtime learning without weight updates achieves ≥80% of the performance of fine-tuned baselines on experience-dependent tasks | Task success rate vs. fine-tuned baseline | ≥80% parity on ≥3 task domains |
| **RQ2** | The CSO's 14 components can be ablated to a minimal subset that preserves ≥90% of learning capacity | Learning efficiency (LE) per ablation | Ablated subset with ≤5 components retains ≥90% LE |
| **RQ3** | The admission function `L(X)` improves the signal-to-noise ratio of learning by ≥2× vs. unfiltered accumulation | Learning efficiency per experience | LE_admitted / LE_unfiltered ≥ 2.0 |
| **RQ4** | Validation before commit reduces harmful updates by ≥90% with ≤20% performance cost | Harmful update rate; performance delta | HUR_validated ≤ 0.1 × HUR_unvalidated; perf drop ≤ 20% |
| **RQ5** | Causal-chain retrieval generalizes to unseen contexts ≥15% better than flat semantic retrieval | Transfer success rate on held-out contexts | Causal retrieval ≥ +15% vs. flat retrieval |
| **RQ6** | Versioned state enables rollback to any prior version with 100% fidelity and ≤1s latency | Rollback fidelity; rollback latency | 100% fidelity; latency ≤ 1s |
| **RQ7** | The security model detects and recovers from 100% of simulated poisoning attacks with ≤5% false positive rate | Attack detection rate; false positive rate | Detection = 100%; FPR ≤ 5% |
| **RQ8** | State lineage is verifiable by third parties with ≤O(log n) proof size | Verification time; proof size | Verification ≤ 1s; proof size ≤ O(log n) |
| **RQ9** | Identity continuity is maintained across 10,000+ state transitions with zero false rejections | Lineage verification success rate | 100% verification success at 10K commits |

These hypotheses are **pre-registered**: the metrics, thresholds, and success criteria are fixed before any experiment runs. Deviations from pre-registration are documented as protocol amendments, not silent scope changes — the methodology's defense against HARKing (hypothesizing after results are known).

---

## 2. The Experimental Ladder: Systems A–E

The experimental ladder decomposes CCR into five systems, each a prefix of the full architecture, so that component contributions are measurable:

| System | Components | Hypothesis tested |
|---|---|---|
| **A** | Foundation model + prompt | Baseline: no learning |
| **B** | A + retrieval memory (RAG over ledger) | L1 memory helps |
| **C** | B + experience store + evaluator | Structured experience > raw retrieval — **partially falsified, see §2.1**: holds only when B cannot read truthful outcomes; the real differentiator is evaluation-channel *integrity under forged text*, not structure |
| **D** | C + policy learning (admission + commit) | Validated learning > unvalidated |
| **E** | D + causal graph + versioning + provenance | Full CCR > D |

Each system is implemented as a *restriction* of the full CCR codebase, not a separate implementation: System A is CCR with all learning disabled; System B is CCR with only retrieval enabled; and so on. This ensures that differences between systems are due to the components, not implementation artifacts. The ladder is run on every task domain (§3), and the primary analysis is the *marginal contribution* of each rung: `ΔPerformance(B→A)`, `ΔPerformance(C→B)`, etc.

The ladder's design is informed by AblationBench's methodology for decomposing research contributions ([AblationBench](https://arxiv.org/html/2507.08038v2)): each rung is an ablation of the full system, and the ablation plan is pre-registered with the hypothesis it tests. The ladder is also **bidirectional**: we can ablate from E downward (remove components from the full system) as well as build from A upward, and discrepancies between the two directions are diagnostic — a component that helps when added but doesn't hurt when removed is redundant.

### 2.1 Empirical result — the C→B rung, and why it was reframed (2026-09-06)

The C→B rung was run first (Phase 1 engine, tool-selection task §3.1, 3 seeds, 60 train / 300 test,
ε-greedy). The **pre-registered hypothesis "structured experience > raw retrieval" did not survive an
honest baseline**, and this is recorded here rather than quietly restated — the same honesty discipline
the ledger (doc 03 §5.3) and the learning transaction apply to their own claims.

**What happened.** An initial B arm counted tool *mentions* in retrieved text and ignored the outcome —
that is not RAG, it is noise, and it inflated C's margin. Corrected to a real naive RAG+LLM baseline (B
parses the retrieved transcript for "succeeded" and picks the tool with the most text-derived
successes), the result is:

| Arm | mechanism | mean success |
|---|---|---|
| A | no memory | 0.427 |
| B | naive RAG+LLM (text-derived success counts) | 0.601 |
| C | retrieval over evaluated experience (score×confidence) | 0.612 |

**C − B = +0.011 in the mean; per seed −0.143 / +0.037 / +0.140 — C loses to B on one of three
seeds, and the mean gap is within seed noise.**

**The reframing (falsifiable, and sharper).** When B can read truthful outcome text, B and C compute
almost the same thing from the same ground truth, so **structure alone is not the differentiator**. C's
distinguishing property is that its evaluation lives in a **separate, integrity-bearing channel that
survives *forged* text** — a property a text-reading B cannot have. That is an **adversarial** claim, and
it is tested by the poison condition (D1 in `ccr-agent/`, and RQ on channel integrity, doc 07 §2.2), **not
by B-vs-C over truthful text**. The revised, testable form of the rung:

> **C→B (revised):** structured, separately-evaluated experience beats raw retrieval **only when the raw
> channel can be corrupted** (forged/self-reported outcomes). Over a truthful outcome channel the two are
> empirically indistinguishable on this task. The benchmark's C→B condition must therefore include a
> **text-poisoning arm**, or it measures nothing the honest B baseline does not already achieve.

This does not touch the D-rung (validated > unvalidated) or E-rung claims; it narrows what C→B is
entitled to assert. The prior "C > B > A on every seed" phrasing was an artefact of the crippled B arm.

---

## 3. Benchmark Tasks

Tasks are selected along EvoMemBench's two axes — scope (in-episode vs. cross-episode) and content (knowledge vs. execution) — with the addition of a third axis: **experience dependency** (how much the task benefits from learning). The task suite:

### 3.1 Tool Selection (cross-episode, execution, high experience dependency)

The agent must select among available tools for recurring tasks, where tool reliability varies by context. Ground truth is provided by a deterministic simulator that tracks tool success rates per context. This task tests L3 policy learning directly: the agent must learn `P(tool_success | context)` from experience. Baseline: no learning (random selection). Target: the agent's tool selection converges to the optimal policy within a bounded number of experiences.

### 3.2 Software Debugging (cross-episode, execution, high experience dependency)

The agent debugs recurring failure patterns in a codebase, where the same bug classes recur with variations. Ground truth is provided by test suites. This task tests L2 skill learning: the agent must learn reusable debugging procedures. Baseline: no learning (each bug treated as novel). Target: debugging time decreases with experience, and learned skills transfer to novel bug variants.

### 3.3 Long-Horizon Workflows (cross-episode, execution, high experience dependency)

The agent executes multi-step workflows (e.g., research, deployment, data processing) where efficiency improves with practice. Ground truth is provided by workflow completion time and success rate. This task tests L2+L3: skill acquisition and policy refinement over extended horizons. Baseline: fixed workflow. Target: workflow efficiency improves monotonically with experience.

### 3.4 Research Agents (cross-episode, knowledge, medium experience dependency)

The agent conducts literature reviews, fact-checking, or synthesis tasks where source quality and research strategy matter. Ground truth is provided by expert evaluation or held-out answer keys. This task tests L1+L4: memory of source reliability and meta-learning of research strategies. Baseline: no source memory. Target: research quality (accuracy, citation quality) improves with experience.

### 3.5 Operations Agents (in-episode, execution, high experience dependency)

The agent manages a simulated environment (e.g., server farm, supply chain) where environmental patterns recur within an episode. Ground truth is provided by the simulator's state. This task tests L0+L1: in-context adaptation and episodic memory. Baseline: no memory. Target: the agent adapts to recurring patterns within an episode.

### 3.6 Personal Assistants (cross-episode, knowledge, low experience dependency)

The agent learns user preferences and stable procedures over extended interaction. Ground truth is provided by user satisfaction proxies or explicit feedback. This task tests the *harm* case: memory can hurt when it introduces irrelevant evidence ([EvoMemBench](https://arxiv.org/html/2605.18421v2)). Baseline: no memory. Target: the agent learns preferences without degrading performance on tasks where memory is irrelevant.

---

## 4. Metrics

The metric suite operationalizes the roadmap's §21 metrics with precise definitions:

### 4.1 Learning Efficiency (LE)

\[
LE = \frac{\Delta \mathrm{Performance}}{N_{\mathrm{experiences}}}
\]

where `ΔPerformance` is the performance improvement on a fixed evaluation set between two committed states, and `N_experiences` is the number of ledger experiences between them. LE is computed per commit range and averaged over the experiment. Higher is better; LE = 0 means no learning; LE < 0 means harmful learning.

### 4.2 Retention

\[
\mathrm{Retention}(h) = \mathrm{Perf}(C_{n+h}, \mathrm{task}) - \mathrm{Perf}(C_n, \mathrm{task})
\]

for a task learned before version `n`, measured at horizon `h`. Retention > 0 means learning persists; Retention < 0 means forgetting or interference.

### 4.3 Generalization

Measured as transfer success rate: performance on held-out contexts not present in training experience. For RQ5, this is the key metric: causal retrieval vs. flat retrieval on unseen contexts.

### 4.4 Stability

\[
\mathrm{Stability} = \mathrm{Var}(\mathrm{Perf}(C_n, \mathrm{task})) \text{ over } n
\]

Low variance is better; high variance indicates unstable learning (oscillating policies).

### 4.5 Recovery

Time and fidelity of rollback: `Recovery_time = t_{rollback} - t_{detection}` and `Recovery_fidelity = Perf(C_{restored}) / Perf(C_{pre-harm})`. Fidelity = 1.0 is perfect recovery.

### 4.6 Sample Efficiency

\[
\mathrm{SampleEff} = \frac{N_{\mathrm{experiences}}}{N_{\mathrm{commits}}}
\]

Lower is better: how many experiences are needed per committed update.

### 4.7 Drift

\[
\mathrm{Drift}(C_m, C_n) = d(\pi(\cdot | C_m), \pi(\cdot | C_n))
\]

as defined in document 01 (§12.1), measured over a fixed probe distribution.

### 4.8 Provenance Completeness

Fraction of committed state content with intact derivation paths to the ledger. Target: 1.0.

### 4.9 Safety

Harmful update rate: `HUR = N_{harmful commits} / N_{total commits}`, where harmful is defined by the security model (document 07). Safety-critical tasks have a hard threshold: HUR must be 0.

### 4.10 Cost

Token usage per task (following EvoMemBench's efficiency metric ([EvoMemBench](https://arxiv.org/html/2605.18421v2))): total LLM tokens consumed by the agent and the memory system. Cost is a constraint, not a target: the architecture must be viable within a token budget.

---

## 5. The RQ5 Experiment: Causal vs. Flat Retrieval

RQ5 — the hypothesis that causal memory generalizes better than flat retrieval — is the architecture's most distinctive claim and deserves a dedicated experimental design.

### 5.1 Design

Two systems are compared, identical except for the retrieval mechanism:

- **System E-causal:** full CCR with causal-graph retrieval (Q4 from document 05): given a context, retrieve causal chains from similar contexts.
- **System E-flat:** full CCR with the causal graph replaced by flat semantic retrieval (embedding similarity over experience records).

Both systems use the same ledger, the same evaluator, the same transaction protocol. The only difference is the retrieval mechanism in the Policy Engine.

### 5.2 Task

The task is **context-shifted tool selection**: the agent learns tool policies in a set of training contexts, then is evaluated on *held-out* contexts that are semantically similar but not identical. The held-out contexts are generated by perturbing the training contexts (e.g., changing API endpoints, rate limits, error messages) while preserving the underlying causal structure.

### 5.3 Metric

Transfer success rate: the fraction of held-out contexts where the agent selects the optimal tool (as determined by the simulator's ground truth). The hypothesis is that causal retrieval will outperform flat retrieval because the causal graph encodes *why* a strategy works, not just *that* it worked, enabling transfer to contexts where the surface features differ but the causal mechanism is the same.

### 5.4 Success criterion

Causal retrieval achieves ≥15% higher transfer success rate than flat retrieval, with statistical significance at p < 0.05 (permutation test over 1000 resamples).

### 5.5 Threats to validity

- **Confounding by chain length:** causal chains may be longer or shorter than flat retrieval results. Control: match retrieval depth (number of items retrieved) across conditions.
- **Evaluator bias:** the evaluator may favor causal explanations. Control: use a fixed, pre-registered evaluator with no access to the retrieval mechanism.
- **Task specificity:** the result may not generalize beyond tool selection. Control: replicate on software debugging (§3.2) with the same design.

---

## 6. Experimental Protocol

### 6.1 Pre-registration

Before any experiment runs, the following are pre-registered: hypotheses (§1), task suite (§3), metrics (§4), success criteria, analysis plan, and stopping rules. Pre-registration is stored in the ledger as a signed `protocol` record, and any deviation is documented as an amendment with rationale.

### 6.2 Replication

Each experiment is replicated across **three independent runs** with different random seeds (affecting model sampling, retrieval tie-breaking, and task ordering). Results are reported as mean ± standard deviation across runs. A result is considered robust if the sign of the effect is consistent across all three runs.

### 6.3 Baselines

Every experiment includes the strongest available baseline from the literature:

- For memory: Mem0, A-MEM, Letta (as implemented in EvoMemBench ([EvoMemBench](https://arxiv.org/html/2605.18421v2))).
- For learning: Reflexion, ExpeL, ACE, Memento (as described in document 00).
- For fine-tuning comparison (RQ1): a fine-tuned model on the same task distribution, where feasible.

Baselines are run under the same protocol (same tasks, same metrics, same evaluation) to ensure comparability.

### 6.4 Ablations

The experimental ladder (§2) is the primary ablation. Additional ablations are pre-registered for specific hypotheses:

- **Admission ablation:** System D with admission disabled (all experiences auto-committed) to test RQ3.
- **Validation ablation:** System D with validation disabled (admitted updates auto-committed) to test RQ4.
- **Causal ablation:** System E with flat retrieval (§5) to test RQ5.
- **Versioning ablation:** System E with rollback disabled to test RQ6.

### 6.5 Stopping rules

Experiments run for a fixed number of episodes (pre-registered per task) or until a performance plateau is reached (no improvement over 100 consecutive episodes), whichever comes first. Early stopping for safety (HUR > threshold) is mandatory and pre-registered.

---

## 7. Analysis Plan

### 7.1 Primary analysis

For each hypothesis, the primary metric is compared across conditions (systems, ablations) using paired tests (Wilcoxon signed-rank for non-normal distributions, paired t-test otherwise) with effect sizes reported. Multiple comparisons are corrected using Benjamini-Hochberg.

### 7.2 Secondary analysis

Learning curves (performance vs. experience count) are plotted for each system and task, with area-under-curve (AUC) as a secondary metric for learning speed. Drift trajectories are plotted over version history.

### 7.3 Failure analysis

All failed experiments (where success criteria are not met) are analyzed post-hoc to identify failure modes: Was the task too easy (ceiling effect)? Too hard (floor effect)? Was the baseline too strong? Was the metric insensitive? Failure analysis is documented in the ledger as a `gate_decision` record with `verdict: research` and feeds back into protocol amendments.

---

## 8. Summary and Handoff

The benchmark methodology specified here turns the CCR architecture's claims into a rigorous, pre-registered, replicable experimental program. The design is grounded in the current literature — EvoMemBench's two-axis task organization and efficiency metrics, AblationBench's decomposition methodology — and extends it with the architecture's distinctive requirements: the A–E ladder for component attribution, the RQ5 causal-vs-flat experiment, and the safety-critical thresholds that make the program honest about risk.

The methodology's output is not a single number but a *map*: where CCR helps, where it hurts, where it is safe, and where it is not. That map is the input to the research paper (`Continuous-Cognitive-Runtime.md`) and the development roadmap's Phase 1–8 prioritization.

*Document 06 of the CCR series. Previous: `05-CAUSAL-COGNITIVE-GRAPH.md`. Next: `07-CCR-SECURITY-MODEL.md` — the threat model and mitigation matrix.*
