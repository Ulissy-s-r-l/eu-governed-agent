# 05 — Causal Cognitive Graph: Representation, Attribution, and Query Semantics

**Continuous Cognitive Runtime (CCR) — Document 5 of the CCR specification series**
**Status:** Working draft v0.1 — personal working document, intended for later refinement toward an arXiv publication
**Depends on:** `00-CCR-SYSTEM-OVERVIEW.md` (§6.6, P5), `01-CCR-FORMAL-MODEL.md` (Def. 9.1, §9), `02-COGNITIVE-STATE-OBJECT.md` (§3.7), `04-LEARNING-TRANSACTION.md` (§2.2 replay)
**Feeds:** `06-CCR-BENCHMARK.md` (RQ5 experiment), `07-CCR-SECURITY-MODEL.md` (attribution attacks)

---

## 0. Executive Summary

This document specifies the **Causal Cognitive Graph**: the typed, confidence-weighted, provenance-tracked structure that records *why* the agent's behavior changed — not merely *that* it did. Documents 00–04 established the architecture, formal model, state schema, ledger, and transaction protocol; what remains underspecified is the causal layer that connects them. The graph's role was defined abstractly in document 01 (Def. 9.1) as a structure `𝒢^caus = (𝒱_c, ℰ_c, w, prov)` over goals, strategies, outcomes, causes, and learnings. This document answers the implementer's questions: what are the node and edge types, how is the graph built from experience, how are causes attributed, how does the graph serve validation and retrieval, and what are its failure modes?

The design is grounded in a recent empirical result that directly validates the architectural choice. The CHIEF framework (2026) demonstrated that treating agent execution logs as flat sequences fails at failure attribution, while reconstructing them into a **hierarchical causal graph** and applying counterfactual screening substantially outperforms eight baselines on the Who&When benchmark ([CHIEF](https://arxiv.org/html/2602.23701v1)). CHIEF's machinery — hierarchical causal-graph construction, oracle-guided backtracking, and counterfactual screening — is adapted here into **our** four attribution stages (local, planning-control, data-flow, deviation-aware) for the `attributed-to` edge type: the stage decomposition is ours, while CHIEF's counterfactual-screening machinery and its counterfactual patterns are the inspiration for the graph's edge semantics. The deeper theoretical anchor is Pearl's counterfactual machinery: the abduction–intervention–prediction procedure that computes "what would have happened had a different action been taken, with everything else held constant" ([Counterfactual Credit Assignment](https://arxiv.org/html/2011.09464v2)), which is exactly the question the learning transaction's replay stage (document 04, §2.2) asks of the graph.

The design commitment that shapes everything below: **the graph records attributed causes, not discovered ones.** CCR does not run causal discovery over the ledger; it records the causal attributions that evaluators, traces, and humans assert, with their provenance and confidence. This is a deliberate narrowing — causal discovery from observational agent data is an open research problem — and it keeps the graph honest: every edge is a claim with a source, not a fact with a guarantee.

---

## 1. Design Requirements

The graph schema is derived from five requirements, traced to prior documents. **C1 — Attribution with provenance:** every causal edge records *who* attributed it (evaluator, agent trace, human) and with what confidence (document 01, Def. 9.1). **C2 — Typed structure:** the graph must distinguish goals, strategies, actions, outcomes, causes, and learnings, and the relations between them (document 02, §3.7). **C3 — Counterfactual support:** the graph must answer "what would have happened if…" queries for the replay stage (document 04, §2.2), which requires that edges encode *mechanistic* claims, not mere temporal succession. **C4 — Versioned evolution:** the graph is part of the CSO and participates in commit/branch/merge semantics (document 02, §5). **C5 — Honest uncertainty:** edge confidence must propagate to chain confidence, so that a long chain of weak attributions is not mistaken for a strong one (document 01, §9).

A consequence worth stating before any types are introduced: **the graph is not a causal discovery engine.** It does not infer causal structure from observational data; it records the causal claims that the system's evaluators and traces assert. The distinction matters because it determines what the graph *is* — a provenance-tracked record of attributed mechanisms — and what it is *not* — a learned structural causal model. The former is implementable today; the latter is a research direction that the graph's schema is designed to accommodate if and when discovery methods mature.

---

## 2. Node and Edge Types

### 2.1 Node types

The graph has six node types, corresponding to the roadmap's conceptual chain `Goal → Strategy → Action → Outcome → Cause → Learning`:

| Node type | Content | Source | Example |
|---|---|---|---|
| `goal` | The objective pursued | `exp.goal` | "Resolve the API timeout" |
| `strategy` | The approach selected | `exp.action.strategy_ref` | "Retry with exponential backoff" |
| `action` | The concrete steps taken | `exp.action.steps` | Tool calls, arguments |
| `outcome` | The observed result | `exp.outcome` | "Success after 3 retries" |
| `cause` | The attributed reason | `exp.evaluation.attribution` | "Rate limiter triggered at step 2" |
| `learning` | The resulting update | `tx.delta` | "Policy reweight: backoff ↑" |

Each node carries a reference (`ref`) into the ledger or CSO — the graph does not duplicate content, it indexes it. A `goal` node's `ref` points to the experience that recorded it; a `learning` node's `ref` points to the transaction that committed it. This is the same content-addressing discipline as the CSO (document 02): the graph is a *view* over immutable records, not a store of mutable content.

### 2.2 Edge types

Edges are typed relations with confidence and provenance:

| Edge type | Meaning | Example |
|---|---|---|
| `motivates` | Goal → Strategy: the goal motivated this strategy selection | `goal:resolve-timeout → strategy:backoff` |
| `selected` | Strategy → Action: the strategy was instantiated as these steps | `strategy:backoff → action:retry-3x` |
| `produced` | Action → Outcome: the steps produced this result | `action:retry-3x → outcome:success` |
| `attributed-to` | Outcome → Cause: the outcome is attributed to this cause | `outcome:failure → cause:rate-limit` |
| `replaced-by` | Strategy → Strategy: one strategy superseded another | `strategy:naive-retry → strategy:backoff` |
| `validated-into` | Learning → (Strategy|Policy|Skill): the learning was committed as this update | `learning:tx-abc → policy:rate-limit-region` |

The `attributed-to` edge is the graph's most consequential type and the one that carries the CHIEF inheritance. Its `attributed_by` field records which of **our** four attribution stages (adapted from CHIEF's screening machinery) produced the claim: `local` (the error originated at this step), `planning-control` (the planner failed to adapt), `data-flow` (a data corruption propagated from upstream), or `deviation-aware` (the error was irreversible) ([CHIEF](https://arxiv.org/html/2602.23701v1)). This is not merely bibliographic: the four stages have different evidentiary weights, and the edge's confidence is set by the stage that produced it — a `local` attribution from a deterministic test is stronger than a `planning-control` attribution from an LLM critic.

### 2.3 Edge record

```json
{
  "edge_id":      "cg-edge:sha256:…",
  "rel":          "attributed-to",
  "from":         "cg:outcome:…",
  "to":           "cg:cause:…",
  "confidence":   0.74,
  "attributed_by": "evaluator:unit-tests | agent-trace | human:…",
  "attribution_stage": "local | planning-control | data-flow | deviation-aware",
  "counterfactual_pattern": {
    "bias":    "rate limiter triggered at step 2",
    "anomaly": "subsequent retries failed"
  },
  "created_tx":   "tx:sha256:…",
  "created_at":   "2026-09-06T…Z"
}
```

The `counterfactual_pattern` field is the schema's direct borrowing from CHIEF: each edge records the *bias* (the upstream deviation) and the *anomaly* (the downstream observable error) that the edge claims are causally linked ([CHIEF](https://arxiv.org/html/2602.23701v1)). This pattern is what makes the edge *testable*: a replay that holds the bias constant and observes the anomaly fail to occur is evidence against the edge, and the graph's confidence propagation (§4) is designed to receive such evidence.

---

## 3. Attribution: From Evaluation to Edge

Attribution is the process by which an evaluation's `attribution` field (document 03, §2.2) becomes a graph edge. The process is staged as our four attribution stages, wrapping CHIEF's counterfactual-screening machinery:

1. **Local attribution:** does the outcome's anomaly originate at the action step itself? If the step received valid inputs and produced an incorrect output, the cause is local. This is the cheapest and most confident attribution, and it is the default for deterministic evaluation channels (unit tests, tool verification).
2. **Planning-control attribution:** if the error is non-local, is it a control-flow failure — the planner repeating a failed strategy despite error signals? This requires inspecting the trajectory's loop structure, which the experience record's `action.steps` preserve.
3. **Data-flow attribution:** if not control-flow, did a data corruption propagate from upstream? The graph's `produced` edges form the data-flow path, and backtracking along them identifies the step where valid inputs were first corrupted.
4. **Deviation-aware screening:** is the error reversible? If a later step self-corrected (the trajectory returned to a valid state), the deviation is assigned minimal responsibility. This stage is the graph's defense against attributing causality to transient noise.

Each stage produces a candidate `attributed-to` edge with a confidence derived from the stage's reliability and the evaluator's channel reliability (document 02, §3.8). The edge is not committed to the graph until the learning transaction that cites it commits — the graph is versioned state, and edge insertion is a transaction operation like any other. This is the mechanism that prevents a single bad evaluation from permanently distorting the causal record: the edge exists, but its confidence is low, and a subsequent re-evaluation (a new transaction) can supersede it.

---

## 4. Confidence Propagation and Chain Semantics

A **causal chain** is an alternating sequence of nodes and edges from a goal to a learning: `goal → motivates → strategy → selected → action → produced → outcome → attributed-to → cause → … → validated-into → learning`. The chain's **overall confidence** is the product of its edge confidences, adjusted for node reliability:

\[
\mathrm{conf}(\mathrm{chain}) = \prod_{e \in \mathrm{chain}} \mathrm{conf}(e) \cdot \prod_{n \in \mathrm{chain}} \mathrm{reliability}(n)
\]

where `reliability(n)` is 1.0 for ledger-backed nodes (the ledger is immutable) and the evaluator's channel reliability for `cause` nodes. The product form is deliberate: it penalizes long chains of weak attributions, which is the correct behavior — a five-hop chain of 0.8-confidence edges has overall confidence ≈ 0.33, and the system should treat it accordingly. The alternative (max or mean) would let a single strong edge carry a chain of speculation, which is exactly the failure mode the confidence-carrying design exists to prevent.

Chain confidence is consumed at three points. The **Policy Engine** uses it to weight strategy evidence: a policy entry's `causal_basis` field cites chains, and the entry's confidence is bounded by the weakest chain in its basis. The **Learning Engine** uses it during proposal: a candidate update that cites a low-confidence chain is either rejected or assigned a higher validation burden. The **Provenance Recorder** uses it during audit: a chain's confidence is part of the evidence bundle, so an auditor can see not just *what* the agent learned but *how confidently* the system attributed the cause.

---

## 5. Query Patterns

The graph serves four query patterns, each consumed by a different module:

**Q1 — Context-conditioned strategy evidence** (Policy Engine): given a context region, return all chains from goals in that region to learnings, ranked by chain confidence. This is the policy table's evidence base: `pol(z, u)` is informed by the chains that pass through strategy `u` in region `z`.

**Q2 — Counterfactual replay scoping** (Learning Engine): given a candidate update ΔC, return the set of historical experiences that are *mechanistically relevant* to the update — those reachable by perturbing nodes on the update's cited causal chains. This is the replay stage's scope restriction (document 04, §2.2): replay does not run over the whole ledger, only over the subgraph that the update's justification touches.

**Q3 — Failure explanation** (Provenance Recorder / audit): given a failed outcome, return the attributed cause chain with full provenance — the "why did the agent do that?" query. The chain is returned with each edge's `attributed_by` and `counterfactual_pattern`, so the explanation is inspectable, not just asserted.

**Q4 — Generalization transfer** (Learning Engine): given a new context, find chains from *similar* contexts (by embedding similarity over goal and strategy nodes) whose learnings might transfer. This is the RQ5 experiment's query: does causal-chain retrieval (Q4) beat flat semantic retrieval for transfer to unseen contexts? The experiment is specified in document 06.

---

## 6. Failure Modes and Mitigations

The causal graph has three characteristic failure modes, each with a designed mitigation:

**Spurious attribution:** the evaluator attributes causality to a step that was merely temporally prior. The mitigation is the `deviation-aware` stage (§3): reversible errors are discounted, and the `counterfactual_pattern` on each edge makes the attribution *falsifiable* — a replay that contradicts the pattern lowers the edge's confidence.

**Attribution laundering:** an attacker who can influence evaluations can insert a false causal chain that justifies a malicious policy update. The mitigation is the transaction's guard conjunction: the edge is inserted by a transaction, the transaction is validated, and the validation includes replay against the cited chain's counterfactual pattern. A forged chain must survive replay to affect behavior.

**Chain bloat:** over time, the graph accumulates edges, and chain queries become expensive. The mitigation is the same consolidation discipline as the ledger (document 03, §4): low-confidence, superseded chains are deprecated (not deleted) by transaction, and hot-path queries operate over the active subgraph. The full graph remains auditable; the active subgraph remains fast.

---

## 7. Summary and Handoff

The Causal Cognitive Graph specified here is a typed, confidence-weighted, provenance-tracked record of attributed mechanisms, built from evaluation attributions through our four attribution stages (wrapping CHIEF's counterfactual-screening machinery), queried by the Policy Engine, Learning Engine, and Provenance Recorder, and versioned as part of the CSO. Its design is the operationalization of design principle P5 — causality over correlation — with the honesty constraint that all edges are attributed, not discovered. The graph's two borrowings are load-bearing: CHIEF's counterfactual-screening machinery gives the `attributed-to` edge its semantics (decomposed into our four attribution stages), and Pearl's counterfactual procedure gives the replay stage its theoretical foundation.

Document 06 (`06-CCR-BENCHMARK.md`) specifies the RQ5 experiment that tests whether this graph's chains generalize better than flat retrieval, and document 07 (`07-CCR-SECURITY-MODEL.md`) will return to the attribution-laundering threat as a formal security property.

*Document 05 of the CCR series. Previous: `04-LEARNING-TRANSACTION.md`. Next: `06-CCR-BENCHMARK.md` — the experimental methodology that tests the architecture's claims.*
