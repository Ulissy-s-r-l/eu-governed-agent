# CCR Agent — Missing Components & Build Guide

**Date:** 2026-09-07 · **Scope:** what remains between the current codebase and the full
CCR specification (docs 00–08) · **Audience:** the implementer (you, in two weeks)

This document is the engineering counterpart to the specification series. The specs
(`00-CCR-SYSTEM-OVERVIEW.md` … `08-GNS-CCR-INTEGRATION.md`) say *what* the system is;
this guide says *what is still missing from the code and exactly what it takes to build
it*. Every item below names the spec section it implements, the files it touches, a
concrete code sketch, an acceptance test, and an effort estimate.

Current state of the code: **Phases 1–4 plus the Tier-1 state sweep are complete and
tested** (18 tests, 3 demos, all passing). The experience engine (capture, evaluation,
ledger, Merkle checkpoints, GMP fact bridge, grafomem sealing) works. The transaction
layer (admission gate, propose, validate with held-out replay, commit, forward-only
revert) works for four update targets. The B-vs-C experiment runs, but its C > B rung is
**partially falsified** against an honest B arm (see §0 framing and doc 06 §2.1); D1/D2/D3
hold.
What follows is everything else, in build order.

---

## 0. Framing — what CCR is for, and what it is not

This guide is an engineering plan and can read as though CCR's value is the *learning*. Two decisions
taken this week narrow that, and the guide carries them so no downstream reader re-derives the wrong
claim.

**1. Learning is domain-conditional.** `eu-governed-agent` ADR-0009 records that AML alert triage emits
no correctness signal: ~2% of alerts become SARs, ~4% of SARs receive any feedback, that feedback is
outcome-blind by statute, and the no-file branch — the large majority — receives essentially nothing. B3
is therefore a **Level 2 governed assistant and makes no learning claim.** CCR's learning half is
testable only in domains that *answer back*: the tool-selection simulator, software engineering
(`cc-builder@ulissy` already generates this shape), receivables.

**2. The transferable contribution is the gate, not the learner.** What carries into a regulated
deployment is the transaction discipline: admission that refuses, validation that rejects before commit,
forward-only revert with the harmful transaction still visible, and a provenance path from a committed
policy entry back to its justifying evidence. That is what a supervisor asks for. **Every item below
that hardens the gate has value independent of whether the agent ever learns anything** — read the build
order in that light.

---

## 1. Status snapshot: the 14 CSO components

The Cognitive State Object (doc 02) has fourteen components. "Live" means the component
is written *only* through the transaction machinery and is maintained on every commit.

| # | Component (doc 02) | Schema | Transactional | What's missing | Target |
|---|---|---|---|---|---|
| 1 | header (version, agent_ref, model_ref) | ✅ | ✅ | `agent_ref` is a placeholder DID until Phase 7 | P7 |
| 2 | semantic_memory | ✅ | ✅ | consolidation, contradiction detection, GMP-backed persistence, re-confirmation | Tier 2 |
| 3 | episodic_index | ✅ | ✅ | `pending`/`rejected` bookkeeping at capture time; index pruning policy | Tier 2 |
| 4 | procedural_skills | placeholder | ❌ | **everything** — bodies, triggers, sandboxed validation, lifecycle | P5 (hard) |
| 5 | policy_table | ✅ | ✅ | multi-region confidence floors; strategy promotion | Tier 2 |
| 6 | strategy_library | ✅ (dict) | ❌ | no commit path; no strategy abstraction over policies | Tier 2 |
| 7 | goals | ✅ | ✅ | goal completion detection; goal-driven retrieval | Tier 2 |
| 8 | preferences | ✅ | ✅ | conflict rules between user-set and inferred prefs | Tier 2 |
| 9 | confidence_map + policy | ✅ | ✅ | **decay is computed but never enforced** (no demotion at floor) | Tier 2 |
| 10 | causal_graph | placeholder | ❌ | **everything** — attribution pipeline, edge admission, counterfactual queries | P5 (hard) |
| 11 | evaluation_history | ✅ (dict) | ❌ | not written at all; the calibration loop that reads it is the L4 seed | Tier 2 |
| 12 | provenance_index | ✅ | ✅ | derivation types beyond `"direct"` (consolidated, inferred, merged) | Tier 2 |
| 13 | lineage (parent, commitment, signature) | ✅ | ✅ | single-parent chain only; merge needs multi-parent | P6 |
| 14 | version counter | ✅ | ✅ | — | — |

Beyond the state object, the cross-cutting gaps are: **branching/merge of the state DAG**
(Phase 6), **GNS identity & authority binding** (Phase 7), and **formal verification of
the eleven properties** (Phase 8). Each gets its own section below.

### What "done" means for every item

A component is done when all four hold:

1. Its writes go through `LearningEngine.commit` (never direct mutation) — doc 01 §7.2.
2. Every write leaves a `gate_decision` record in the ledger and updates
   `provenance_index` + `confidence_map` — doc 01 I3/I4.
3. A rejection path exists and is tested (a poisoned/invalid candidate that must not land).
4. The acceptance test named in its section passes in `tests/`.

---

## 2. Tier 2 — finish the components that already exist

These are components whose schema and commit path landed in the Tier-1 sweep but whose
*semantics* are one commit deep. None requires new architecture; all are ordinary
engineering against the existing transaction machinery. Total estimate: **6–9 days**.

### 2.1 Semantic memory: from storage to memory

**Spec:** doc 02 **§3.1** (`semantic_memory`; §3.2 is `episodic_index`), doc 00 §6.4. **Status:
(a) consolidation + (d) re-confirmation BUILT (2026-09-07)** — `ccr/consolidation.py` groups evaluated
experiences by (region, tool) and emits `insert`/`confirm` memory candidates through the gate
(`LearningEngine.commit_memory`); `sources` = the group's root exp_ids (I4), support counted via the
single `ccr/support.py:root_support` (I6, doc 01 Def. 7.4a). `tests/test_consolidation.py`. (b)
contradiction detection remains; **(c) GMP-backed persistence is BUILT (2026-09-07)** —
`ccr/gmp_memory.py:GMPMemoryStore` is a commit observer on `LearningEngine` that persists a committed
`MemoryItem` as a GMP fact (`ccr:mem/<type>` belief + `ccr:mem/sources` provenance companion);
**`supersedes` maps to the NATIVE GMP `supersede` op (ADR-0008), not a payload flag**; `status` maps to
the native lifecycle (superseded / `valid_until`). `tests/test_gmp_memory.py`.

Four pieces of work, in order:

**(a) Consolidation — episodes become facts.** Today semantic items are inserted by hand.
The real source is a cold-path job that reads the ledger, finds repeated evaluated
patterns, and proposes them as `semantic_memory` candidates. Sketch:

```python
# ccr/consolidation.py
class Consolidator:
    """Cold-path job: evaluated episodes → MemoryItem candidates (doc 02 §3.2)."""
    def __init__(self, ledger, min_support: int = 5, min_conf: float = 0.6): ...
    def propose_facts(self, region: str) -> list[CandidateUpdate]:
        # group evaluated experiences by (region, tool, success-pattern);
        # groups with >= min_support and mean score >= min_conf become
        # CandidateUpdate(op="insert", target="semantic_memory", ...)
        # with justification=[exp_ids of the group]  → provenance free (I4)
```

Because consolidation emits `CandidateUpdate`s, it inherits the gate, validation,
provenance, and revert for free. **Acceptance:** `tests/test_consolidation.py` — 30
episodes with a stable pattern produce a committed fact whose `sources` are exactly the
supporting exp_ids; a pattern with support 4 (< 5) produces nothing. ~1.5 days.

**(b) Contradiction detection.** Before a fact commits, check it against active memory:
same subject, incompatible claim → the candidate must either supersede the old item or
be rejected. This is a new validation branch in `LearningEngine.validate` for
`target="semantic_memory"` (today that branch is invariant-only). The honest Tier-2
version is *syntactic* contradiction (same key, different value — e.g. both items
assert `tool:t1 latency` with different numbers), not semantic inference.
**Acceptance:** committing "t1 latency = 50ms" then "t1 latency = 900ms" without
`supersedes` is rejected with reason recorded; with `supersedes="mem:1"` it commits and
deprecates mem:1. ~1 day.

**(c) GMP-backed persistence.** The `GMPFactBridge` already writes six GMP facts per
experience into grafomem's durable tier. Semantic memory should use GMP as its *store*:
item ↔ fact constellation, supersession ↔ GMP `supersede` op, item id ↔
`BLAKE2b-128(tenant‖predicate‖subject‖object‖valid_from)`. This is what makes
`ccr-agent` a grafomem-native citizen rather than a sidecar: agent memory queries become
GMP `retrieve`, and another grafomem agent with the right capability can read (not
write) this agent's committed beliefs. Sketch:

```python
# ccr/gmp_memory.py
class GMPMemoryStore:
    """Persists committed MemoryItems as GMP fact constellations (doc 02 §3.2,
    gmp-spec v0.2 ops: write/supersede/retrieve/delete)."""
    def __init__(self, gmp_backend, tenant: str): ...
    def on_commit(self, item: MemoryItem, tx: TransactionRecord) -> None:
        # write(item) ; if item.supersedes: supersede(old_fact, new_fact)
    def retrieve_active(self, subject: str) -> list[MemoryItem]: ...
```

Wire it as a commit observer on `LearningEngine` (same pattern as `_record`).
**Acceptance:** after a semantic commit, GMP `retrieve` returns the item and `audit`
shows write+supersede ops in order. ~1.5 days.

**(d) Re-confirmation.** `MemoryItem.last_confirmed_tx` exists but nothing sets it after
creation. When a new episode independently supports an existing active fact, the
consolidator should emit `op="confirm"` — a commit that refreshes `last_confirmed_tx`
and resets the confidence clock (this is what stops good facts from decaying, see 2.4).
~0.5 day.

### 2.2 Evaluation history and the calibration loop (the L4 seed)

**Spec:** doc 00 §5.4 (L4 meta-learning), doc 02 §3.8, doc 07 §2.2a (reference requirement), doc 06
negative control. **Status: BUILT (2026-09-07)** — `ccr/calibration.py:CalibrationLoop` tracks per-channel
`{reliability, verdicts}` against a **designated reference channel** (Beta posterior mean); the gate's
trust term consumes observed reliability over self-reported confidence (`AdmissionGate.evaluate_evidence(
reliability_of=…)`). **Its non-applicability to reference-less domains (AML per ADR-0009) is stated in the
module docstring**, and `CalibrationLoop` refuses to instantiate without a reference. Permanent negative
control (`tests/test_calibration.py`): a garbage/self-consensus channel never recovers reliability. Writing
`evaluation_history` back through a `recalibrate` transaction remains.
The paragraph below is the original design note.
**Status (historical):** `evaluation_history` is declared and *never written*. This is the highest-
leverage Tier-2 item because it is the seed of meta-learning: the system learning
*which feedback to trust*.

The mechanism: every evaluation channel (`SimulatorGroundTruthEvaluator`,
`SelfReportEvaluator`, future LLM-critic) gets an entry
`{verdicts: int, reliability: float}`. After outcomes are independently observed
(delayed ground truth), the channel's historical agreement rate becomes its reliability,
and the reliability *replaces the hardcoded confidence cap* (`SelfReportEvaluator`'s
0.3 cap becomes learned, bounded). Sketch:

```python
# ccr/calibration.py
class CalibrationLoop:
    """Tracks per-channel verdict reliability; feeds the gate's trust term
    and the evaluators' confidence caps (doc 00 §5.4: L4 as recursion)."""
    def outcome_observed(self, exp_id: str, channel: str,
                         predicted: float, realized: float) -> None: ...
    def reliability(self, channel: str) -> float: ...  # Beta(α,β) posterior mean
```

Two design rules from the specs. (1) Calibration updates to evaluator parameters are
themselves state updates: the reliability table lives in `evaluation_history`, which is
part of the CSO, so it changes *only via commit* — that is the doc-00 claim "the
admission function and evaluator calibration are versioned state" made literal.
(2) The floor: a channel's cap never exceeds ground-truth channels, ever — the negative
control in `experiment_bvc.py` (garbage evaluation collapses C to 0.39) is the
permanent regression test for this loop; if calibration ever lets a garbage channel
recover, the loop is broken by definition. **Acceptance:**
`tests/test_calibration.py` — a channel that agrees with ground truth for 50 outcomes
sees its cap rise; a channel fed random verdicts stays pinned at floor; B-vs-C negative
control still passes. ~2 days.

### 2.3 Strategy library

**Spec:** doc 02 §3.5, doc 00 §6.6. **Status:** `strategies` is an empty dict.

A strategy is a *named, cross-region generalization* over policy rows: "for retrieval
tasks, prefer tools with demonstrated reliability over tools with low latency." Build:
when the same tool-ordering commits in ≥ k regions, propose a `strategies` entry whose
`provenance_index` derivation is `"inferred"` (the first non-`"direct"` derivation type).
Strategies then serve as *priors for new regions* — a region with no history boots from
the strategy instead of uniform. This is the first genuinely generalizing artifact the
system produces, and it must go through the gate like everything else (a strategy
induced from poisoned regions is poison). **Acceptance:** commit consistent orderings
into 3 regions → strategy proposed, gated, committed; a 4th (new) region's initial
policy equals the strategy; a strategy proposed from 2 regions (< k) is rejected.
~1.5 days.

### 2.4 Confidence-floor enforcement

**Spec:** doc 02 §3.6, doc 04 **§5A** (the `maintenance` tx type). **Status: BUILT (2026-09-07)** —
`state.py` now has the §3.6 confidence policy (`floor_commit`/`decay_rate`/`decay_clock`),
read-time `confidence_of`/`below_floor`, and `PolicyEntry.updated_version`; `select_tool` enforces the
read-time floor (below-floor ⇒ uniform); `LearningEngine.maintenance()` emits `maintenance` transactions
demoting below-floor policies to uniform (`tests/test_maintenance.py`, 6 tests). *The historical status
below is retained as a correction record.* — **Historical status (corrected 2026-09-07):** an earlier
draft claimed the confidence machinery existed; in fact it was **unbuilt** — `PolicyEntry` carried a bare
`confidence` float with **no `confidence_of`, no `confidence_map`, no `decay_rate`/`decay_clock`,
no `floor_commit`, and no `status` field**. Decay was **neither computed nor enforced** —
a policy entry drives `select_tool` regardless of confidence, which violates the doc-02 contract that
confidence is behavioral, not decorative. Item 1 is therefore *build §3.6, then enforce it*, not *add a
sweep to existing decay*.

> **Correction (2026-09-07), recorded visibly.** An earlier draft of this section claimed
> *"`confidence_of()` computes read-time decay but nothing acts on the floor."* Checked against
> `state.py`: **`confidence_of` does not exist and decay is not computed at all.** This is the **fourth**
> instance this week of a summary that did not survive checking — after 0008 (two→three actors), 0009
> gap 3 (server-only reading, twice), the AMLR Art. 18 citation, and the cosign 7A guard names. The
> pattern is the record's actual subject, not an aside: **a stated summary trusted over the source it
> summarizes.** It is the same shape as the standing rule ("trust the channel, not the account"),
> applied to our own documents — which is why it belongs in the record rather than being quietly fixed.

Two enforcement points, both required by the spec:

1. **Read-time floor (behavioral, doc 02 §3.6 — decay is a read-time computation over an immutable
   store).** Build the confidence policy `{floor_commit, decay_rate, decay_clock: "commits"}` and a
   read-time `confidence_of(entry, current_version)`; **`select_tool` MUST NOT act on a below-floor
   entry — it falls back to uniform.** This closes the "decorative confidence" gap immediately, without
   mutation, without waiting for a sweep.
2. **Durable demotion (commit-time, doc 04 §5A).** `LearningEngine.maintenance(state)` scans for
   below-floor entries and emits **`type: maintenance` transactions** (evidence-free, invariant-validated
   against the recorded decay computation — **not** a `learn`/admission path, which would reject for "no
   evidence"). Per-target: **`policy_table` → revert to uniform**; memory/skills → `status="deprecated"`;
   preferences → dropped. Recorded in the ledger with its reason; revertable. Note the interaction with
   2.1(d): re-confirmation keeps *live* beliefs above the floor, so decay + re-confirmation implement
   "beliefs fade unless re-earned" end to end.

**Only `policy_table` exists in the code today**, so the first implementation's sole live target is
**policy → revert to uniform**; memory/preference demotion is defined (here and doc 04 §5A) and has
nothing to act on yet. **Acceptance:** a policy at low confidence, advance N versions past the floor →
`select_tool` returns uniform (read-time); `maintenance()` emits a `maintenance` tx that demotes it, tx
in the ledger with its reason, and `revert` restores it. *(relative sizing: small)*

### 2.5 Co-signed approval on the learning transaction

**Spec:** `cgr.cosign.v1` (grafomem `docs/cgr/cgr-cosign-v1-spec.md`), doc 04 §1, doc 07 §7 property 1.
**Status:** doc 04's `validation.human_approval` is `{approver, decision, rationale, timestamp}` with
**no signature**; `tx.signature` is one signature, the system's. So `HighRiskUpdate ⇒ RequiredApproval`
currently reduces to an unsigned field an operator can write — the property is *asserted*, not enforced.
This is the same gap found independently in TrueForge's approval event and in `cgr.attestation.v4`,
resolved upstream 2026-09-06 (grafomem decision 0009 **accepted**; `cgr.cosign.v1` specifies the
general two-party co-signature envelope). **Depends on:** nothing in this guide. **Unblocks:** an
enforceable `HighRiskUpdate ⇒ RequiredApproval`.

Wire the envelope into `LearningEngine`:

- `validation.human_approval` becomes an **approval assertion** carrying `{content_digest, approver_id,
  approver_key_id, approver_act, decision_date, record_nonce}`, where `content_digest` is
  `BLAKE2b-256(JCS(candidate update))`.
- The approver signs `grafomem.hitl.approval.v1: ‖ JCS(assertion)` with a **self-custodied** key.
  `gns_browser`'s `signBytesToHex()` already enforces that domain tag and refuses to sign without it —
  reuse the signer; the caller constructs the structured assertion.
- The transaction record's system signature covers the whole artifact **including** the approver
  signature (**nested, not parallel** — parallel would let the approval block be lifted out with the
  transaction still verifying).
- A transaction whose `risk_class` requires approval and lacks a valid approver signature **MUST** be
  rejected at validation, not committed.

**Honest limits** (matching the cosign spec's register): stripping the approval produces an *invalid*
transaction; an approval-less high-risk transaction is *non-conformant* (a verifier rule); a compromised
system key can always mint a fresh approval-less transaction — *detectable* against externally-held
commitments but not preventable. **Tamper-evident and conformance-enforced, not tamper-proof.**

**Not resolved by this item:** whether the approver key belongs to a *verified named person* (0009 gap
3a). The envelope makes the approval attributable to a key; binding that key to an accountable
individual is the separate assurance track.

**Acceptance:** `tests/test_approval.py` — a high-risk candidate without an approver signature is
rejected with the reason recorded in the ledger; the same candidate with a valid signature commits;
stripping the signature from a committed transaction breaks verification; a signature over a *different*
`content_digest` is rejected. ~1.5 days (relative sizing).

---

## 3. The two hard components

These are placeholders in `state.py` (`SkillRecord`, `CausalEdge`) because each needs
a subsystem that does not exist yet. Together they are Phase 5, and they are where the
roadmap stops being "disciplined bookkeeping" and starts being the contribution.

### 3.1 Procedural skills (L2 skill learning)

**Spec:** doc 02 §3.3, doc 00 §5.4 (L2), doc 04 §3 (validation tiers). **Estimate:
5–8 days**, of which the sandbox is half.

A skill is an *executable behavior* extracted from experience — Voyager's skill library
is the reference proof that executable, composable skills can be acquired without weight
updates. The full `SkillRecord`:

```python
# ccr/skills.py
@dataclass
class SkillBody:
    kind: str            # "python" | "plan"        (plans first; code later)
    source: str          # the executable body
    trigger: dict        # {region, goal_pattern, context_predicates}
    stats: dict          # {uses, successes, last_used_tx}

class SkillValidator:
    """The reason skills are hard: validation must EXECUTE the candidate."""
    def validate(self, skill, replay_episodes) -> dict:
        # run the skill in a sandbox against replayed episode contexts;
        # verdict = commit iff success_rate >= incumbent AND no sandbox violation
```

The lifecycle is `shadow → active → deprecated` (the enum already exists). **Shadow**
means the skill runs alongside the incumbent policy and is scored but never decides;
promotion to **active** is a normal commit whose validation evidence is the shadow-run
comparison. This is replay generalized from "re-score table rows" to "re-execute
behavior" — the same `validate()` dispatch gains a `target="skills"` branch.

Build order inside the component:

1. **Plan skills first** (`kind="plan"`): ordered tool sequences with parameters, no
   arbitrary code. Extraction: mine the ledger for repeated successful step-sequences
   in a region (support ≥ n, success ≥ threshold) → candidate. Validation: replay the
   plan against held-out episodes of the same region. No sandbox needed — plans are
   data. ~2 days.
2. **Shadow mode and promotion**: `LearningAgent.select_tool` consults active skills
   before the policy table; shadow skills only log. ~1 day.
3. **Code skills** (`kind="python"`): requires the sandbox — subprocess with
   `resource.setrlimit` (CPU, memory, no network), timeout, and a denylist import
   guard. The validation record must include the sandbox manifest so a rejection is
   auditable. ~2–4 days, and this is the piece that should slip rather than ship
   unsandboxed.

**Acceptance:** `tests/test_skills.py` — a 3-step sequence that succeeds 8/10 in
training is extracted, shadowed, promoted, and measurably beats the policy table on
held-out episodes; a skill whose shadow run regresses is rejected; a code skill
attempting `import os` dies in the sandbox with the violation in the ledger.

### 3.2 Causal graph (Phase 5)

**Spec:** doc 05 (entire), doc 01 Def. 9.1, doc 04 §2.2 (replay consumes it).
**Estimate: 6–10 days.**

The design commitment that keeps this tractable (doc 05 §1): **the graph records
attributed causes, not discovered ones.** No causal discovery over the ledger — every
edge is a claim with a source and a confidence. That converts a research problem into
an engineering problem with four parts:

**(a) Node/edge store inside the CSO.** The `CausalEdge` placeholder grows to the full
doc-05 schema: node types `goal | strategy | action | outcome | cause | learning`;
edge types including `attributed-to` (the consequential one), with `attributed_by`
taking one of CHIEF's four stages — `local`, `planning-control`, `data-flow`,
`deviation-aware` — whose stage sets the edge's initial confidence (a `local`
attribution from a deterministic test outranks a `planning-control` attribution from an
LLM critic). Storage: edge list in the CSO plus an adjacency index rebuilt on load
(the index is derived, so it lives outside the commitment). ~1.5 days.

**(b) Attribution pipeline.** The writer of `attributed-to` edges. Three sources, in
order of evidentiary weight:

```python
# ccr/causal.py
class AttributionPipeline:
    """Evaluators, traces, and humans assert causes; the pipeline turns
    assertions into CandidateUpdate(target='causal_graph') — edges enter
    the graph ONLY through commit (doc 05 C1/C4)."""
    def from_evaluator(self, exp: Experience) -> list[CandidateUpdate]:
        # SimulatorGroundTruthEvaluator already knows the true cause
        # (wrong tool for region) → high-confidence 'local' edges
    def from_trace(self, exp: Experience) -> list[CandidateUpdate]:
        # step-level error signals → 'data-flow' / 'local' at lower confidence
    def from_contrast(self, region: str) -> list[CandidateUpdate]:
        # matched pairs: same goal+context, one differing action dimension,
        # different outcome → 'deviation-aware' candidates. This is the cheap
        # counterfactual: the ledger provides the intervention for free.
```

**(c) Counterfactual query interface.** Replay (doc 04 §2.2) currently re-scores table
rows from raw history; with the graph it should ask "edges say outcome O was caused by
action A in context C — what does the graph claim under A′?" Implementation: walk
`attributed-to` backwards from the outcome, substitute the action node, read off the
claimed outcome distribution, weight by edge confidence (chains multiply — doc 05 C5,
honest uncertainty). ~2 days.

**(d) Consumers.** Two rewirings that make the graph load-bearing rather than
decorative: (i) the admission gate's surprise term reads graph confidence (an outcome
the graph explains is not surprising); (ii) validation uses (c) for policy and skill
candidates. ~2 days.

**Acceptance:** `tests/test_causal.py` — evaluator attributions produce edges whose
confidence ordering matches the CHIEF stage ordering; contrast pairs from the simulator
(the ground truth is known!) recover the true cause as the highest-confidence edge;
a chain of three weak edges (0.5³) yields path confidence ≤ 0.125; no edge exists that
did not come through a commit.

---

## 4. Phase 6 — the state DAG: branching & merge

**Spec:** doc 02 §5, doc 00 §6.9 (`getState/proposeCommit/finalizeCommit/getLineage`).
**Estimate: 4–6 days.**

Today the lineage is a linear chain (`parent_commitment: str`). Branching is needed for
two spec'd behaviors: experimental commits (try a risky learning on a branch, merge if
it validates, abandon if not) and concurrent agents sharing a genesis.

1. **Format change:** `parent_commitment: str` → `parents: list[str]`. This changes the
   commitment body, so it is a **schema version bump** (`model_ref.schema: "cso/2"`) —
   the commitment function must be versioned so old states still verify. Do this first;
   everything else is combinatorics on top. ~1 day.
2. **Branch:** trivial — `commit` onto any ancestor commitment. The engine needs a
   `state_store` (commitment → serialized CSO) so branches can fork from non-tip
   states; today states live in caller memory. Add `ccr/state_store.py` (content-
   addressed by commitment; this is also what makes `getState(version)` real). ~1 day.
3. **Merge:** three-way per component with explicit conflict policy, because different
   CSO components merge differently: `policies` — keep the row with higher confidence,
   record both in `provenance_index` (derivation `"merged"`); `semantic_memory` — union,
   conflicts become *both* items with a contradiction flag for the next consolidation
   pass; `goals/preferences` — union with user-sourced beating inferred; `lineage` —
   two parents. The merge result is a commit with `tx_type="merge"` and both parents.
   ~2–3 days.
4. **Merge validation:** a merge commit must pass the same validation as a learn commit
   (replay the merged policy table — a merge can regress even when both parents are
   individually fine). ~1 day.

**Acceptance:** `tests/test_dag.py` — fork at v3, commit divergent policies on both
branches, merge; the merged state verifies, lists both parents, replays clean; a merge
whose replay regresses is rejected.

---

## 5. Phase 7 — GNS identity & authority binding

**Spec:** doc 08 (entire), doc 07 §§4–5. **Estimate: 5–8 days**, dominated by the
delegation chain verifier.

This is where `agent_ref="did:gns:local-dev"` would become real — but the scoping in earlier drafts
assumed a GNS that provides DID documents, VC-style mandates, and a stable controller. **It does not.**
Verified this week and recorded in grafomem decision records 0003, 0005, 0008, 0009:

- there are no `did:gns:` identity records carrying `state_commitment`;
- there are no VC mandate credentials;
- principals are **ephemeral** — `setup-agent.ts` mints one in memory, signs the cert, discards the
  secret (0003) — so doc 08 §2's `controller` separating ownership from operation has nothing to
  attach to;
- GNS derives `human` by **absence** (not in the agent table ⇒ human), not by a positive verified
  assertion (0009 gap 3);
- no lineage or succession record exists in any of the three systems (0008).

Phase 7 is therefore **binding plus building the layer being bound to.** Split it:

### 7A — port what already exists (in geiant, not GNS)

Some of Phase 7 is deployed today, in geiant's `mcp-audit`, and should be **reused, not rebuilt**.
*(Table verified against the code, not a summary — `packages/mcp-audit/src/chain.ts` and
`.../supabase/migrations/20260320_agent_audit.sql`.)*

| Doc 08 concept | Where it already exists (verified) |
|---|---|
| Scope attenuation (§3, `scope(Mᵢ₊₁) ⊆ scope(Mᵢ)`) | `delegation_certificates`: `h3_cells TEXT[]`, `facets TEXT[]`, `max_depth INTEGER` (default 0, CHECK 0–5), `constraints JSONB` (`20260320_agent_audit.sql:20-36`) |
| Authority guard at execution (doc 01 §10.2) | `chain.ts`: **`checkJurisdiction`** (H3, `:122`), **`checkFacet`** (`:135`), **`checkToolAllowed`** (`:182`), `checkRevocation` (`:157`), `isDelegationCertActive` (`:113`) — and `checkFacet`/`checkToolAllowed` are called **live** in `middleware.ts:267,273` |
| Property 9, learning–authority separation | The **A2** rule, enforced live (`middleware.ts:134`, grafomem 0006): an agent absent from `agent_registry` is denied; registration is by explicit provisioning only, so an agent cannot widen its own scope |
| Checkpoint exfiltration (doc 03 §5.3) | `grafomem_seal.py` signed `.gfm`; geiant epoch anchoring (`gcrumbs`/`agent_epochs`) |

*(Correction from the earlier draft: the guard functions are `checkJurisdiction` / `checkFacet` /
`checkToolAllowed`, **not** `checkTool` / `checkH3` — verified in `chain.ts`.)*

Porting means calling geiant's verifier from CCR's authority guard rather than writing a second one; the
scope algebra and the cert format already exist and are in production.

### 7B — genuinely new, and blocked upstream

DID records carrying `state_commitment`, VC mandates, drift-constrained mandates, and a stable
`controller`. These depend on decisions **still open**: 0005 (custody-managed principals, proposed),
0008 (where lineage lives), and **0009 gap 3a** (a verified named-person identity, gated on the
assurance track). **Do not schedule 7B against the current spec text** — doc 08 describes the target
system in the present tense; a status line distinguishing *deployed* from *specified* belongs in doc 08
itself.

The four bindings below are **7B** (new), except binding 3 (authority guard), whose enforcement machinery
is the 7A port above. In the doc-08 order:

1. **Identity–state binding (doc 08 §4):** every state commit emits a signed *commit
   event* onto the GNS identity chain carrying `Commit_n`; `agent_ref` resolves to a
   DID document whose service endpoint can authenticate the state. Code: a
   `GNSIdentityChain` class (append-only, signed — reuse the ledger's hash-chain
   machinery rather than inventing a second one) and a hook in `_apply` that emits the
   event. The grafomem sealer (`grafomem_seal.py`) is the pattern: checkpoints already
   leave the system as signed `.gfm` objects; commit events do the same onto the
   identity chain.
2. **Delegation mandates (doc 08 §3):** VC-style credentials
   `M₁→…→Mₖ` with monotone attenuation (`scope(Mᵢ₊₁) ⊆ scope(Mᵢ)`) — including the
   *drift-constrained mandate* (authority conditional on behavioral envelope, not just
   identity continuity). The verifier is pure signature+containment checking; the hard
   part is the scope algebra (set containment over action classes).
3. **Authority guard at execution:** doc 01 §10.2's `Executed(a) ⇒ scope(class(a)) =
   permit`, enforced in the hot path — `LearningAgent.select_tool` gains an authority
   check against the current mandate *at the current state version*. The enforcement
   point matters: authority is evaluated against the state under which the action
   executes, which is what makes the identity chain a kill switch (doc 08 §7:
   revocation halts the agent without trusting the cognitive layer).
4. **Key rotation as a lineage event:** rotation is a signed event on the identity
   chain, never an edit; old states remain verifiable under old keys.

**GRAFOMEM consistency note:** capability strings must keep matching grafomem's regex
`^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$` (this is why the sealer uses `ccr_ledger.anchor`, not
`ccr:ledger-anchor`), and erase/revocation receipts flow through grafomem's
`Governance`/`ExecutionContext` so a revoked agent leaves a grafomem-native receipt.

**Acceptance:** `tests/test_gns.py` — a commit emits a verifiable identity-chain event;
a delegated credential with widened scope is rejected (attenuation); a revoked mandate
blocks `select_tool` immediately; states signed pre-rotation still verify.

---

## 6. Phase 8 — formal verification of the eleven properties

**Spec:** doc 07 §7 (five properties) + doc 08 §8 (six properties) = the eleven.
**Estimate: 8–12 days** including the intermediate step; a full ProVerif model is the
ceiling, not the floor.

The eleven, all stated so as to reduce to signature checks, chain checks, and
containment checks over the two chains — none requires modeling learned content:

| # | Property | Source | Reduces to |
|---|---|---|---|
| 1 | No unvalidated commit | doc 07 §7 | guard conjunction in `commit()` |
| 2 | No unauthorized action | doc 07 §7 | authority guard (Phase 7.3) |
| 3 | Tamper evidence | doc 07 §7 | hash-chain verification |
| 4 | Recovery completeness | doc 07 §7 | forward-only revert (already demoed, D3) |
| 5 | Attribution completeness | doc 07 §7 | `provenance_index` coverage |
| 6 | Identity–state binding | doc 08 §8 | commit events (Phase 7.1) |
| 7 | Delegation soundness | doc 08 §8 | chain verification (Phase 7.2) |
| 8 | Attenuation | doc 08 §8 | credential validation |
| 9 | Learning–authority separation | doc 08 §8 | no commit event modifies mandates |
| 10 | Cross-chain consistency | doc 08 §8 | anchor verification |
| 11 | Revocation liveness | doc 08 §8 | protocol flow (bounded time) |

Do it in two stages:

**Stage 1 — property-based testing (Hypothesis), ~3 days.** Each property becomes a
stateful Hypothesis test that generates random operation sequences (commits, poisons,
reverts, rotations, revocations) and asserts the property after every step. Properties
1, 3, 4, 5 are testable *today* against the current code — this stage starts now and
acts as the regression harness for Phases 5–7. This is the honest intermediate: it is
not mechanized proof, but it will catch real bugs (it would have caught the
`genesis_ref` self-reference bug found in the Tier-1 sweep).

**Stage 2 — ProVerif/Tamarin model, ~5–9 days.** Model only the two chains (state DAG,
identity chain) and the three check types; learned content stays abstract per doc 08
§8. The model's processes: `Ledger`, `StateDAG`, `IdentityChain`, `Adversary`
(Dolev–Yao minus the agent's signing key). Deliverable: mechanized proofs or explicit
attack traces for all eleven.

**Acceptance:** `tests/test_properties.py` (Hypothesis, all applicable properties,
≥10k examples each) and `verification/ccr.pv` with the eleven lemmas.

---

## 7. Build order, effort, critical path

> **This is a dependency graph, not a schedule.** CCR is one of several parallel tracks (B3, the
> identity-assurance track, the `cgr.cosign.v1` corpus and implementations, buyer discovery). It has no
> dedicated builder. The ordering below is a **dependency graph**, not a schedule; the relative sizing in
> the section bodies is for comparing items against each other, **not for forecasting a date**. (A prior
> "≈ 44–54 working days" total has been removed for this reason.)

| Order | Item | Section | Depends on |
|---|---|---|---|
| 1 | Confidence-floor enforcement | 2.4 | — |
| 2 | Consolidation + re-confirmation | 2.1a/d | — |
| 3 | **Co-signed approval on the transaction** | **2.5 (new)** | — |
| 4 | Contradiction detection | 2.1b | 2 |
| 5 | Evaluation history + calibration | 2.2 | — |
| 6 | Per-channel reliability (closes the standing rule) | 2.2 | 5 |
| 7 | Strategy library | 2.3 | 2 |
| 8 | GMP-backed memory persistence | 2.1c | 2 |
| 9 | Skills: plans, shadow, promotion | 3.1 | — |
| 10 | Skills: code sandbox | 3.1 | 9 |
| 11 | Causal graph: store + attribution | 3.2 | — |
| 12 | Causal graph: counterfactuals | 3.2 | 11 |
| 13 | State DAG: parents format + store | 4 | — |
| 14 | State DAG: merge + validation | 4 | 13 |
| 15 | Hypothesis property tests (stage 1) — ✅ **BUILT** (`tests/test_properties.py`) | 6 | — |
| 16 | **Phase 7A — port existing authority machinery** | **§5 / C** | 13 |
| 17 | Phase 7B — GNS identity layer | 5 | 16, 0005, 0008, 0009 gap 3a |
| 18 | ProVerif model (stage 2) | 6 | 15, 16 |

Items 3 and 6 are placed early deliberately: both close the "trust the channel, not the account"
standing rule below, and both have value whether or not anything later is built.

Critical path reasoning *(kept verbatim; parenthetical item numbers retargeted to the table above)*:
items 1–6 are independent of everything and should all land before the hard components, because the hard
components *use* them — skill validation consumes the calibration loop's reliability scores, and
causal-edge admission consumes the confidence machinery. The DAG format change (13) should land *before*
GNS (16–17) because identity-chain anchoring signs parents, and signing a format about to change wastes
the anchor. Property tests (15) start the day after Tier 2 and grow with every later merge.

### Standing rules (apply to every item above)

- **One write path.** Anything that mutates state goes through `LearningEngine.commit`.
  If a component "needs" a direct write, the component is wrong, not the rule.
- **Rejection is a feature.** Every new commit path ships with its rejection test in
  the same change (the D1/D2/D3 discipline).
- **Naming:** `CSO` unqualified means grafomem's working-state matrix; CCR's state is
  always spelled `CognitiveState` in prose touching grafomem.
- **GRAFOMEM-native by default:** durable facts through GMP ops, evidence through
  signed `.gfm` objects, capabilities matching `^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$`.
- **Checkpoints leave the system.** Any new sealing/anchoring path must exfiltrate the
  root (grafomem seal or identity chain), per doc 03/07 — tamper-evidence requires the
  anchor to outlive the machine.
- **The evaluator is load-bearing.** The B-vs-C negative control (garbage evaluation →
  collapse to chance) is the permanent guard test for every learning-path change.
- **Trust the channel, not the account.** No component may accept a self-reported confidence
  as evidence of reliability. The admission gate currently reads `evaluation.confidence` with
  no channel verification — a forged block claiming `confidence=0.99` yields V ≈ 0.695 and
  walks through a 0.55 threshold. Per-channel reliability tracking (doc 07 §2.2) is
  unimplemented, and until it is, D1 defends *experience* poisoning and not *feedback*
  poisoning. This is the project's actual thesis, and it arrived three times independently this
  week — CCR's gate trusting self-reported confidence; AML vendors training on analyst
  disposition labels because no ground truth exists (so their models learn to *agree with* the
  analyst rather than to be correct); and four separate systems recording human approval as
  unsigned metadata. All three are one failure: **the system trusts an account of what happened
  rather than a channel that can contradict it.**

---

*Build guide for the `ccr-agent` implementation. Companion to the CCR specification
series (`00-CCR-SYSTEM-OVERVIEW.md` … `08-GNS-CCR-INTEGRATION.md`) and the project
`README.md`. Status: 18/18 tests, D1/D2/D3 passing. **B-vs-C: the C > B rung is partially
falsified** — against an honest B arm, C−B = +0.011 mean across three seeds and C loses on
seed 7 (doc 06 §2.1). Structured evaluation and raw retrieval are indistinguishable over a
truthful outcome channel; the differentiator is **evaluation-channel integrity under
adversarial input** (which D1 tests, and B-vs-C does not).*
