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
| Experience Ledger | GMP durable-tier fact store (facts = `(predicate, subject, object, valid_from)`) |
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
├── test_durable_tier.py  # GUARD: durable tier holds evidence only, no CSO mirror (doc 03 §3.4)
├── test_contradiction.py # contradiction detection → contested status (doc 02 §3.1)
├── test_strategies.py    # strategy library: cross-region induction + boot prior (doc 02 §3.5)
└── test_properties.py    # Hypothesis property harness — Phase 8 Stage 1 (build-guide §6, item 15)
```
Also in `ccr/`: `cosign.py` (co-signature envelope), `support.py` (I6 `root_support`),
`consolidation.py`, `calibration.py`, `contradiction.py`, `strategy.py`. `gmp_bridge.py` maps
**experiences** (evidence) to GMP facts; there is no CSO-content mirror (doc 03 §3.4 / ADR-0010).
Suite: **65 tests** (one is a stateful machine running 10k generated operation sequences).

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
