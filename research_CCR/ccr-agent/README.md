# CCR Agent — Phase 1: Experience Engine

**Continuous Cognitive Runtime (CCR) — first implementation milestone**
**Series docs:** `00-CCR-SYSTEM-OVERVIEW.md` … `08-GNS-CCR-INTEGRATION.md`
**Integration target:** GRAFOMEM Cloud / GMP v0.2 / grafomem runtime v1.0

## What this is

Phase 1 of the CCR roadmap: **prove that agent execution can be converted into
structured, evaluated, provenance-sealed experience** — the substrate every later
phase (adaptive memory, policy learning, learning transactions) builds on.

```
Agent loop (tool-selection simulator)
   │  emit: state / goal / action / outcome
   ▼
ExperienceCapture ──► ExperienceRecord (doc 03 schema)
   │
   ▼
ExperienceLedger — append-only, SHA-256 hash-chained, Merkle checkpoints,
   │                Ed25519-signed per record
   ├─► LocalLedgerBackend      (JSONL files; dev + tests)
   └─► GMPFactBridge           (every record → GMP fact, for Grafomem Cloud)
   ▼
OutcomeEvaluator — deterministic simulator ground truth / self-reported /
                   composite; emits confidence-bearing verdicts
   ▼
Evidence sealing — checkpoint Merkle roots anchored into a grafomem
                   ExecutionContext, sealed as signed .gfm (Ed25519)
```

## Terminology mapping (CCR ↔ GRAFOMEM)

| CCR concept (series docs) | GRAFOMEM concept |
|---|---|
| Cognitive State Object (14-component learned state) | mapped **onto** the working-memory tier |
| Working state on hot path | grafomem `CSO` (matrix `M`, read `y = Mq`) |
| Experience Ledger | GMP durable-tier fact store (facts = `(predicate, subject, object, valid_from)`). Holds the §3.2 **evidence** kinds — experience, gate_decision, checkpoint — so the three-way audit join resolves on the durable tier (doc 03 §3.4 / ADR-0010). |
| **CSO content** (semantic_memory, policies, strategies, evaluation_history, …) | **NOT stored in the durable tier — linked by provenance only (doc 03 §3.4 / ADR-0010).** The durable tier holds evidence; committed beliefs are read from the CSO, never from GMP. |
| Signed state transitions | grafomem signed checkpoints / `Receipt` (Ed25519) |
| Provenance chain | GMP `CRYPTOGRAPHIC_PROVENANCE` capability + ledger hash chain |
| Deletion/erasure receipts | grafomem `erase()` receipts (proof the *operation* occurred) |

Naming rule in code: `CSO` = grafomem working state; the CCR learned-state object
is always spelled `CognitiveState` / `CognitiveStateObject`.

## Layout

```
ccr/
├── experience.py    # Experience record schema (doc 03 §2), canonical JSON, hashing
├── ledger.py        # Append-only ledger, hash chain, Merkle checkpoints, verification
├── capture.py       # ExperienceCapture: hooks for any agent loop
├── evaluator.py     # Outcome evaluator protocol + implementations (doc 00 §6.7)
├── simulator.py     # Tool-selection environment with ground truth (doc 06 §3.1)
├── gmp_bridge.py    # Experience → GMP fact mapping + bridge backend
├── grafomem_seal.py # Checkpoint sealing into signed .gfm evidence objects
├── state.py         # CognitiveState: versioned policy table, hash-chained (doc 02 slice)
├── transaction.py   # AdmissionGate + LearningEngine + LearningAgent (docs 01 §7, 04)
├── demo_phase1.py   # End-to-end: run agent → capture → evaluate → seal → verify
├── demo_transactions.py  # D1 poison rejected · D2 replay kills regression · D3 revert
└── experiment_bvc.py     # B-vs-C ladder rung (doc 06 §3.1)
tests/
├── test_phase1.py      # Schema, chain integrity, Merkle proofs, GMP bridge, tamper tests
├── test_phase34.py     # Gate, held-out replay, commit, revert, read path
├── test_approval.py    # cgr.cosign.v1 co-signed approval on the transaction
├── test_maintenance.py # confidence-floor: read-time floor + maintenance demotion (doc 04 §5A)
├── test_consolidation.py # consolidation (§2.1a/d) + I6 support independence
├── test_calibration.py   # per-channel reliability + recalibrate tx (doc 07 §2.2a, doc 04 §5B)
├── test_durable_tier.py  # GUARD (no CSO mirror) + §3.2 audit join on the durable tier (doc 03 §3.4)
├── test_contradiction.py # contradiction detection → contested status (doc 02 §3.1)
├── test_strategies.py    # strategy library: cross-region induction + boot prior (doc 02 §3.5)
├── test_causal.py        # causal graph: attributed edges, store + stage-1 (doc 02 §3.7, doc 05)
├── test_counterfactual.py # replay-against-pattern + propagation, item 12 PR-A (doc 05 §4/§6)
├── test_admission_causal.py # gate consumes bounded causal uplift, item 12 PR-B (cap X=0.05)
└── test_properties.py    # Hypothesis property harness — Phase 8 Stage 1 (build-guide §6, item 15)
```
Also in `ccr/`: `cosign.py` (co-signature envelope), `support.py` (I6 `root_support`),
`consolidation.py`, `calibration.py`, `contradiction.py`, `strategy.py`, `causal.py`.
`gmp_bridge.py` maps the §3.2 **evidence** kinds (experience, gate_decision, checkpoint) to
GMP facts; there is no CSO-content mirror (doc 03 §3.4 / ADR-0010).
Suite: **86 tests** (one is a stateful machine running 10k generated operation sequences).

## Run

```bash
pip install grafomem structlog numpy cryptography   # runtime deps
pip install hypothesis                               # property harness (tests/test_properties.py)
python ccr/demo_phase1.py
python -m pytest tests/test_phase1.py -v
```

## The learning half: transactional updates (docs 01 §7, 04)

Phase 3–4 slice: experience now changes behavior — but **only** through the
gate. `ccr/state.py` + `ccr/transaction.py` add:

- **CognitiveState** — versioned policy table, hash-chained commitments,
  per-entry provenance (`updated_tx`). Read-only for the agent; the
  LearningEngine is the only writer.
- **AdmissionGate** — `L(X)` with a **two-term** `V = (w_trust·trust +
  w_info·info)·support` functional and a minimum-evidence threshold. (The
  four-term `V` of doc 01 Def. 6.1 — with `surprise` and `risk` — is **not**
  implemented; there is no risk model here and `surprise` had no consumer, so
  the functional is honestly cut to the two terms actually computed. Threshold
  0.55 is set deliberately below the two-term ceiling of 0.70.)
- **LearningEngine** — propose → validate (invariant check + counterfactual
  replay, do-no-harm) → atomic commit → forward-only revert.
- **LearningAgent** — the read path Phase 1 lacked: decisions are a function
  of committed state.

### Contradiction detection → `contested` (doc 02 §3.1): manufactured case, real machinery

Two halves, because each alone misleads:

- **The case is manufactured.** The `Consolidator` emits one monotone-positive
  claim shape, so **no two facts it emits in the wild can contradict** — a region
  can have several reliable tools. The `unreliable` claim (`max_unreliable`) exists
  *only* to make the detector **reachable**. The system has **not** observed a
  contradiction; "contradiction detection: built" is not evidence one was found.
- **The machinery is not manufactured.** Mark-both, the non-behavioural read
  (`behavioural_memory`, the memory analogue of the confidence-floor read gate),
  reconcile-on-resolution (`reconcile_contested`), and the **MUST-NOT-auto-resolve**
  rule are real and load-bearing. They matter the first time a contested pair
  arrives from a **non-manufactured** source — a second emitter, human-asserted
  facts via `cgr.cosign.v1`, a merged branch. The manufactured trigger is not
  licence to rip the detector out as dead code.

**Historical note — `contested` and semantic_memory no longer reach GMP.** An earlier
build (item C + a contested→GMP mirror) persisted committed beliefs to the durable
tier and quarantined contested ones by a `valid_until` convention. That mirror was
**removed** per **doc 03 §3.4 / ADR-0010**: the durable tier holds evidence, not CSO
content; committed beliefs are read from the CSO, never from GMP. The contested
transitions (`detect_and_mark` / `reconcile_contested`) remain — they are CSO-state
logic — but they write nothing to GMP.

This also **disposes of the contested→GMP ceiling** the removed mirror carried: the
"conventional, not structural" exclusion was a real hole (a convention-unaware
consumer saw a quarantined belief), and it **disappeared with the mirror — it was
never *solved*.** There is no belief in the durable tier to leak. The rule is now
guarded by `tests/test_durable_tier.py`, which fails if any component mirrors CSO
content to GMP.

### Strategy library (doc 02 §3.5): parallel now, interpose later — **Tier 2 complete**

**Design answer (the one item-7 question).** §3.5's end state is *policies over strategy
IDs* with a two-hop `select_tool`. Building that now is a **schema migration disguised
as a feature** — it changes the hot-path read, the I2 normalization target (do
strategies or tools sum to 1?), and every distribution-asserting test. So this build
takes the **parallel form**: a strategy is a cross-region tool **ordering**
(`StrategyRecord`), not a distribution and not interposed; `policies` still map region
→ distribution over tools directly. The learning value of §3.5 — reuse what worked
elsewhere — is delivered by applying a strategy as a **prior**: when the same ordering
has committed in ≥ k=3 regions (`StrategyInducer`), it is committed through the gate,
and a new region's first policy is **booted** from that ordering instead of uniform,
with the boot recorded in the policy entry's provenance. Interpose the full two-hop
form later, when a consumer needs it.

Induction gathers evidence as the **union** of the supporting regions' experiences;
support is counted over `root_support` (I6 — never a per-region sum). A strategy
induced from evidence that fails admission (forged low-trust self-reports) is
**rejected at the gate**, like everything else.

With item 7 in, **Tier 2 is complete** — build-guide items 1–8 have all landed, with
item 15 (the property harness) as the net. The Tier-3 fork (skills / causal graph /
state-DAG) is the next live decision.

### Causal graph (doc 02 §3.7 / doc 05): attributed, not discovered — store + stage-1

`ccr/causal.py` transcribes the attribution the evaluator **already produced**
(`experience.evaluation.attribution`) into `attributed-to` edges. **No causal
inference from observational data** — the graph does not learn structure, it records
claims that came with a source. Edges are inserted **beside the delta** (`tx.causal`
+ `state.causal_graph`) by the citing `commit`/`commit_memory`/`commit_strategy`, and
the **admission gate does not read the graph** (proven by a test: the gate's decision
is identical with and without it). Nodes are **references** into the ledger, never
copies.

- **Stage 1 (local) only.** Today only `SimulatorGroundTruthEvaluator` emits a usable
  (local) attribution, so every edge carries `attribution_stage == "local"`. A graph
  of only local edges reflects the **emitter's limit**, not the domain; stages 2–4 are
  named in `causal.py` and light up when an evaluator emits them.
- **Born falsifiable.** Every edge carries a `counterfactual_pattern` (bias/anomaly) —
  stored with no consumer until the counterfactuals item. It is not pruned: an edge
  *born* falsifiable differs from one retrofitted with a test hook later.
- **`attributed_by` is derived, never supplied.** `causal_edge(experience, tx)` derives
  it from the cited experience's **signed** evaluation channel — a caller-supplied value
  is *structurally unrepresentable* (no such parameter), so a self-report source cannot
  be labelled `evaluator`. It remains **trusted, not verified** (the channel label is
  self-reported-but-signed); an edge whose source channel lacks a committed calibration
  is flagged `uncalibrated` and MUST NOT be read as calibrated (doc 07 §2.2a). The remedy
  (reference-relative pricing) is deferred with the admission wiring.
- **Q3 why-walk** (`why_believed`) closes doc 03 §6's `causal_basis → cg-edge` hop, and
  resolves **on the durable tier** via a new `ccr:gate_decision/caused` fact (subject =
  tx_id — never a CSO id; the durable-tier guard stays green).
- **Counterfactuals (guide item 12) — PR-A + PR-B landed.** `ccr/causal.py` has
  **`replay_edge`** (stage-1 replay-against-`counterfactual_pattern` — a forged chain must
  reproduce its anomaly or it is deprecated), **`chain_confidence`** (doc 05 §4 product;
  uncalibrated flag-OR + 0.3 floor ⇒ never laundered upward), **minimal Q2**
  (`scope_for_edge`), **`deprecate_failed_edges`**, and **`admission_uplift`**. **The gate
  now reads the graph** (PR-B): a **surviving, calibrated** chain grounding the cited
  evidence adds a **bounded uplift** to V, **added and clamped in aggregate at X=0.05**
  (`AdmissionGate.causal_uplift_cap`, `< the honest margin 0.145` — causal evidence nudges,
  never decides). **Failed/uncalibrated chains add zero** (not a floor); **support (roots)
  is never inflated** (I6 — causal provenance is structure *over* existing evidence). The
  **cap is the safety bound** (correlated or independent, a campaign moves V by ≤ X on one
  decision); **γ** (`CAUSAL_GAMMA=0.1`) only sizes typical influence. Wired only when the
  engine has a `replayer`; without one the gate reads no uplift. **Replay's stated ceiling**
  (doc 07 row): it tests *propensity*, not *instance* causation — the multi-step
  surviving-false gap stages 2–4 close. **Budget caveats (doc 07):** the bound is
  per-decision not per-campaign (§2.5), and the aggregate cap makes the "one-root"
  correlated-forgery cost a footnote, not a vulnerability. **Still open:** stages 2–4
  emitters, queries Q1/Q4, general (multi-hop) Q2.

`ccr/demo_transactions.py` proves the three properties that differentiate CCR
(none of which require the agent to be good at anything):

| Demo | Property | Result |
|---|---|---|
| **D1** | **Experience poisoning** (not feedback poisoning — see limitations): 4 forged "successes" for the worst tool, submitted through the low-trust `agent-self-report` channel whose confidence is capped at 0.3 **at capture**, are **rejected at the admission gate** — trust 0.3, V=0.35 < 0.55; rejection recorded in the ledger | PASS |
| **D2** | A regression candidate passes admission (V=0.56) but **fails held-out replay** — the candidate's own justifying experiences are excluded, and on the disjoint remainder its tool rates 0.333 < 0.667 incumbent (`code_runner`); never commits, state version unchanged | PASS |
| **D3** | A harmful update **commits on a cold-start region** (agent picks a 0.149-reliability tool), is detected, and is **reverted forward-only** — restored state parented to the harmed state, harmful tx still in the ledger, chain verifies. **It commits because the region has no incumbent history (`inc_rate=None`), so do-no-harm has nothing to compare against** — held-out replay even saw the candidate's true rate (0.0) but could not act (see limitations) | PASS |

## First empirical result: B-vs-C (doc 06 §3.1) — a weaker, honest finding

Three arms on the tool-selection simulator (3 seeds, 60 train / 300 test episodes,
ε-greedy exploration for both learning arms). **B is a real naive RAG+LLM
baseline**: it parses the retrieved trajectory text for "succeeded" and picks the
tool with the most text-derived successes for the region (no structured
evaluation, no confidence). *(An earlier version of B counted tool **mentions**
and ignored the outcome text — that made B near-arbitrary and inflated C's
margin. Corrected here.)*

| Arm | Mechanism | Mean success |
|---|---|---|
| **A** | no memory (fixed tool) | 0.427 |
| **B** | naive RAG+LLM: text-derived success counts | 0.601 |
| **C** | retrieval over **evaluated** experiences (score×confidence) | **0.612** |

**The ordering C > B > A holds only in the mean, and thinly: C−B = +0.011.**
Per seed, C−B = **−0.143 (seed 7) / +0.037 / +0.140** — **C loses to B on 1 of 3
seeds**, and the mean gap is within seed noise.

**Honest reading:** when B can read truthful outcome text, **structure alone is
not the differentiator** — B and C are computing almost the same thing from the
same ground-truth outcomes. C's real edge is the **separate evaluation channel**
that survives *forged* text — which is what **D1** tests, not B-vs-C. The prior
"C > B > A on every seed (C−B ≈ +0.10)" claim was an artefact of the crippled B
arm and does not survive an honest baseline.

*(A prior "negative control" — replacing C's scores with random noise collapses C
to ≈0.39 — was reported from an earlier harness and is **not re-run here**; it
speaks to C's scores being load-bearing, which is consistent with, but distinct
from, the finding above.)*

Every C-arm ledger verifies its hash chain end-to-end.

## Stated limitations (architectural, not bugs)

- **Cold-start: replay cannot protect a region it has never seen** *(compensating control added by
  item 1)*. Do-no-harm compares a candidate against the *incumbent's* held-out rate. In a region with
  no incumbent history, `inc_rate` is `None` and the comparison is vacuous, so a
  harmful candidate commits on admission alone (this is exactly what D3 shows).
  Held-out replay may even observe the candidate's true (poor) rate and still be
  unable to act, because there is nothing to compare it to. A region must be seen
  before replay can defend it. **Compensating control (item 1 — confidence-floor
  enforcement):** thin cold-start evidence yields **low confidence by construction**
  (`propose()` sets confidence ≈ `n_experiences / 20`), so a cold-start harmful
  commit lands **below `floor_commit`**, and the **read-time floor prevents it from
  reaching behaviour** — the agent falls back to uniform. So the harm still *commits*
  (replay can't stop it), but it **does not drive behaviour**; a `maintenance` run then
  demotes the committed defect durably. Limitation plus stated control, not limitation
  alone.
- **Channel poisoning: closed where a reference channel exists, open where none does**
  *(compensating control added by item 5)*. The risk: a channel's *self-reported*
  confidence is not evidence of reliability — a forged evaluation block claiming
  `confidence=0.99` (any channel label) would yield trust 0.99 → V≈0.695 and walk the
  0.55 gate. **Compensating control (item 5 — per-channel calibration, doc 07 §2.2a):**
  where the deployment has a **designated reference channel** (a domain with delayed,
  independent, outcome-grounded signals — tests, confirmed outcomes, a vetted oracle),
  `CalibrationLoop` measures each channel's **observed** reliability against it and the
  gate's trust term uses that over the self-report (tested: a forged 0.99 self-report is
  trusted at its observed ~0.25). **The gate reads that reliability from COMMITTED state
  only (doc 04 §5B):** a live loop advises but cannot steer the gate; its numbers become
  behavioural exclusively through a committed `recalibrate` transaction whose invariant
  re-check recomputes each reliability from its recorded observation window, holds the
  reference channel unchanged, and forbids any channel outranking the reference. So the
  control is not just *available* — it is *non-bypassable by an uncommitted loop*, and
  auditable/revertable once committed. **Still open where no reference exists** — AML per
  ADR-0009 has no correctness signal, so no channel can be established as a reference,
  calibration degrades to consensus/imitation, and the account-vs-channel gap stays open
  there. Same extrinsic-trust limit as identity assurance (ADR-0009 gap 3a). Closed with
  a reference; open without one.

## What this still does not include

Phases 5–8: the causal graph, branching/merge (the state DAG is a linear chain
today), GNS identity binding, and formal verification. The learning taxonomy
is at L3 (policy learning); L2 skill learning and L4 meta-learning remain.
