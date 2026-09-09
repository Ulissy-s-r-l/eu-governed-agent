# 03 — Experience Ledger: Schema, Semantics, and Provenance

**Continuous Cognitive Runtime (CCR) — Document 3 of the CCR specification series**
**Status:** Working draft v0.1 — personal working document, intended for later refinement toward an arXiv publication
**Depends on:** `00-CCR-SYSTEM-OVERVIEW.md` (§5.1, §6.2), `01-CCR-FORMAL-MODEL.md` (Def. 3.1, §4.2), `02-COGNITIVE-STATE-OBJECT.md` (§3.2 episodic_index)
**Feeds:** `04-LEARNING-TRANSACTION.md`, `05-CAUSAL-COGNITIVE-GRAPH.md`, `06-CCR-BENCHMARK.md`, `07-CCR-SECURITY-MODEL.md`

---

## 0. Executive Summary

This document specifies the **Experience Ledger**: the append-only, tamper-evident, provenance-complete store that holds everything a CCR agent has done and observed. If the Cognitive State Object (document 02) is the agent's *current theory of the world*, the ledger is the *evidence base* from which all such theories are derived — and to which any theory can be audited. The distinction was formalized in document 01 (§4.2): the ledger is never versioned, branched, or rolled back, because history does not change; only beliefs about history do. Everything in this document follows from honoring that distinction at record level.

The design synthesizes three mature engineering traditions, each contributing a layer. From **event sourcing**, the ledger takes its core semantics: the log is the source of truth, state is a derived projection, and any view can be rebuilt by replay ([Microsoft Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing), [Emergent Mind](https://www.emergentmind.com/topics/event-sourced-state-management)). From **transparency logs** — Certificate Transparency's append-only Merkle tree (RFC 6962) — it takes verifiable inclusion and consistency proofs: the ability to prove that a record is in the log, and that today's log is a superset of yesterday's, without trusting the operator ([RFC 6962](https://datatracker.ietf.org/doc/rfc6962/)). From **compliance audit practice**, it takes the honest framing of what the cryptography does and does not prove: hash chains provide tamper *evidence*, not tamper *prevention*, and integrity is always a claim relative to a commitment held by someone else ([Regure](https://www.getregure.com/blog/hash-chain-audit-trails-what-they-prove/), [FinQub](https://finqub.io/learn/tamper-evident-audit-trail/)). The ledger's job in CCR is to make every learning claim checkable against an unforgeable history — and this document specifies exactly how.

---

## 1. Design Requirements

The ledger schema is derived from six requirements, traced to the series' prior documents. **L1 — Immutability:** experiences are facts of history; once appended, a record is never modified or deleted (document 01, §4.2). Corrections are new records that reference the old, following the compliance-ledger pattern in which corrections are appended events pointing at the corrected record ([ChequeDB](https://chequedb.com/resources/blog/immutable-audit-trails-101-what-financial-compliance-actually-requires)). **L2 — Structured richness:** a record must capture state, goal, action, outcome, evaluation, and provenance — transcript logs are inputs to experience construction, not substitutes for it (document 00, P3). **L3 — Verifiability by third parties:** any party holding a signed ledger commitment must be able to verify inclusion, consistency, and non-repudiation without access to the full log (RQ8). **L4 — Query efficiency at scale:** the ledger grows unboundedly; retrieval must be served by derived indexes, never by scanning the log (LongMemEval-V2 scales to 115M tokens of history). **L5 — Rejection visibility:** rejected and failed experiences are stored with the same fidelity as admitted ones, because the admission function's calibration depends on its own history of refusals (document 01, §6). **L6 — Honest security claims:** the ledger's guarantees must be stated relative to their trust assumptions, with the tamper-evidence/tamper-proof distinction made explicit rather than elided ([Regure](https://www.getregure.com/blog/hash-chain-audit-trails-what-they-prove/)).

One requirement is conspicuously absent: **the ledger does not store beliefs.** Conclusions, consolidations, and learned content live in the CSO's semantic memory, which cites ledger records but is itself versioned and revisable. Keeping the ledger free of interpretation is what allows the same history to be re-evaluated under a better evaluator, re-admitted under a recalibrated admission function, and re-consolidated under an improved summarizer — the event-sourcing insight that new projections are built from old events without migrating the source of truth ([Aakash Sharan](https://aakashsharan.com/event-sourcing-patterns-pitfalls/)).

---

## 2. The Experience Record: Field-Level Schema

### 2.1 Core record

```json
{
  "exp_id":     "exp:sha256:…",
  "seq":        104211,
  "agent_ref":  "did:gns:…",
  "captured_at": "2026-09-06T14:22:07.311Z",

  "context": {
    "state_summary":   "…",                  // compressed observation state S_i
    "context_refs":    ["blob:sha256:…"],    // large artifacts (traces, pages, tool I/O)
    "environment_ref": "env:…",              // environment/session identifier
    "state_version":   "cso:sha256:…"        // the committed CSO under which this occurred
  },

  "goal": {
    "goal_id":   "goal:…",
    "statement": "…",
    "source":    "delegation | user | inferred",
    "source_ref":"mandate:… | exp:…"
  },

  "action": {
    "strategy_ref":  "strategy:…",
    "policy_region": "api-interaction/rate-limited",
    "steps": [ {"tool": "…", "args_digest": "sha256:…", "result_digest": "sha256:…"} ],
    "authority_scope": "scope-version:…"     // the authority in force at act time
  },

  "outcome": {
    "observed":   "…",
    "signals":    {"tests_passed": 14, "tests_failed": 1, "latency_ms": 830},
    "artifacts":  ["blob:sha256:…"]
  },

  "evaluation": {
    "verdict":    "success | failure | mixed | indeterminate",
    "score":      0.62,
    "confidence": 0.78,
    "channels":   ["unit-tests", "lm-critic"],
    "attribution": {"load_bearing": ["action.steps[2]"], "incidental": ["…"]},
    "evaluator_ref": "eval:…"
  },

  "learning_ref": "tx:sha256:… | null",      // set when this experience grounds a committed update
  "causal_links": ["cg-edge:…"],
  "confidence": 0.81,

  "provenance": {
    "captured_by":  "experience-capture/0.3",
    "channels":     ["runtime-telemetry", "tool-trace"],
    "signature":    "sig:gns:…",
    "prev_hash":    "sha256:…"               // hash of record seq-1 → hash chain
  }
}
```

### 2.2 Field-group rationale

The field groups correspond one-to-one with the tuple `X_i = ⟨S, G, A, O, E, R, κ, Λ, prov, ts⟩` of document 01 (Def. 3.1), and each group carries one design decision worth defending. In **`context`**, `state_version` is the single most consequential field: it pins the experience to the exact committed cognitive state under which the agent acted, which is what makes counterfactual replay (document 01, §7.5) well-defined — replay asks "what would state `Ĉ` have done here?" and the question is only meaningful if the record states what the incumbent state *was*. Large observation payloads (full pages, stack traces, tool outputs) are externalized to content-addressed blobs and referenced by digest, keeping the record itself small and hashable.

In **`goal`**, the `source` distinction (delegated / user-supplied / inferred) is a security field, not bookkeeping: inferred goals are hypotheses about intent, and an attacker who can steer goal inference steers everything downstream; the field lets the admission function and the authority guard treat goal provenance as a first-class risk signal. In **`action`**, `authority_scope` records the scope *version* in force at act time — the schema-level support for the authority-continuity invariant (`ExecutedAction ⇒ required authority held`), making every action checkable against a specific signed scope rather than against whatever scope happens to be current at audit time.

In **`evaluation`**, the record stores the verdict *and its confidence and channels* together (document 01, §5.1), because a verdict without its evidentiary basis is not auditable. The `attribution` sub-structure captures the evaluator's judgment of which action steps were load-bearing — the raw material from which the Causal Graph's `attributed-to` edges are built (document 02, §3.7). Finally, `learning_ref` is the back-pointer that closes the loop: when a learning transaction commits an update justified by this experience, the transaction's hash is written here, so the ledger and the state DAG are **cross-linked in both directions** — state cites experiences as justification, experiences cite transactions as consequence. Note that writing `learning_ref` is the *only* post-append field update permitted, and it is itself an append: the update is recorded as a new ledger event (§3.2) that annotates the original record's index entry, never editing the record body, preserving L1.

---

## 3. Ledger Semantics

### 3.1 Append-only log with derived views

The ledger is, physically, an append-only sequence of content-addressed records ordered by `seq`. All reading happens through **derived projections**: indexes by goal, by outcome, by cause, by time, by state version — the `episodic_index` views of document 02 (§3.2) are exactly such projections. This is the CQRS/event-sourcing split applied to agent memory: the write model is the log, the read models are projections, and projections are *rebuildable* — if an index corrupts or a better indexing scheme is invented, it is regenerated by replaying the log, with no migration of the source of truth ([Hossein Nejati](https://hosseinnejati.medium.com/cqrs-event-sourcing-together-how-they-work-in-practice-a3e9193a0e54), [Emergent Mind](https://www.emergentmind.com/topics/event-sourced-state-management)). The practical consequence for CCR: the hot path never touches the raw ledger; it reads projections over *incorporated* experiences (those named by the current CSO's grounding set), which bounds read cost independently of total history size.

Three event-sourcing pitfalls are accepted knowingly and mitigated by design. **Projection lag:** learning-path projections may lag the log; the admission gate reads a version-pinned snapshot so lag never produces inconsistent gate decisions. **Log growth:** consolidation (§4) compacts interpretation, not data; the raw log's growth is a storage-cost line item, accepted as the price of auditability and partially offset by externalizing large payloads to blobs. **Event schema evolution:** records carry a `schema_ver` (inherited from the CSO's versioning discipline), and replay-based projection rebuilding makes schema upgrades a routine operation rather than a migration crisis — the recognized advantage of event-sourced stores when read-side schemas change ([Aakash Sharan](https://aakashsharan.com/event-sourcing-patterns-pitfalls/)).

### 3.2 Ledger events beyond experiences

The ledger interleaves four record types in one ordered sequence, all sharing the hash chain and signature discipline:

| Record type | Content | Why it belongs in the ledger |
|---|---|---|
| `experience` | The record of §2 | The primary content |
| `annotation` | Post-hoc updates: `learning_ref` assignment, evaluator re-scores, correction pointers | Corrections must be events, not edits (L1) |
| `gate_decision` | Admission outcomes: admit/reject, the functional's component values, threshold in force | The gate must be auditable, including its refusals (document 01, §6) |
| `checkpoint` | Periodic signed Merkle root over the log prefix (§5.2) | Anchors third-party verifiability |

Putting gate decisions *in* the ledger rather than in a side log is a deliberate unification: the question "why did the agent start avoiding Tool A?" is answerable only by joining the experience, the gate decision that admitted it, and the transaction that committed the resulting policy — and the join is trivial when all three live in one ordered, hash-chained sequence. The checkpoint records are the ledger's interface to the outside world and are detailed in §5.

### 3.3 What the ledger deliberately does not store

The ledger does not store: embeddings (derived, regenerable), **CSO content — consolidations, policy states, strategies, evaluation history, confidence policy (see §3.4)** — or raw model prompts/responses beyond digests and externalized blobs. The last exclusion deserves justification, since conversation logs are what most agent systems call "memory." Full transcripts are privacy-toxic and mostly redundant: the experience record's structured fields capture what was attempted and what happened, and the externalized `context_refs`/`artifacts` blobs retain raw material where it is evidentially needed. The principle is **evidential sufficiency, not archival completeness**: the ledger stores what is needed to evaluate, validate, audit, and re-derive — and no more. Deployments with regulatory retention obligations may extend blob retention policy; the schema's obligation is only that every stored claim can be traced to evidence, not that every byte ever seen is kept.

### 3.4 The durable tier and the CSO: evidence vs. state

§3.3 states the exclusion as a list; this section states it as a **rule**, because implementations reach for it component by component and drift otherwise. The durable evidence tier — realized in a deployment as the GRAFOMEM Cloud GMP fact store (the terminology mapping in the CCR-agent README) — holds **evidence**: the four §3.2 record kinds (`experience`, `gate_decision`, `annotation`, `checkpoint`) and nothing else. **CSO content is *linked* to that evidence, never *copied* into it** — the same position §1 already states ("the ledger does not store beliefs; conclusions, consolidations, and learned content live in the CSO's semantic memory, which cites ledger records").

**Normative.** No CSO component — `semantic_memory`, `policy_table`, `strategy_library`, `evaluation_history`, `confidence_map`/`confidence_policy`, or any future component of document 02 — may be written to the durable evidence tier. The CSO is its own durable, versioned, hash-chained object (document 01, Def. 8.1); a copy of it in the evidence tier is a second source of truth that can only go stale, and — because a mirrored fact carries `valid_from` but no CSO commitment — go stale **undetectably**. The relationship between the two is the provenance chain of §6: a CSO entry names its `created_tx` (a `gate_decision` in the ledger) and its justifying `exp` records, proven present by Merkle inclusion. That reference *is* the linkage; there is nothing to mirror.

**Cross-agent transfer follows from this, it is not an exception to it.** The transferable unit between agents is **evidence with its provenance**, re-validated through the *receiving* agent's own admission gate and its own reference-calibrated trust (document 07 §2.2a) — never a *belief*, which would import the source agent's trust root sight unseen. Fleet warm-start transfers the **signed CSO plus its ledger** (document 00 §4.3), not a belief mirror. A *curated belief export* — a durable projection of CSO conclusions for some external consumer — is **not** part of this architecture; if a concrete consumer ever requires one, it is a **future amendment to §3.3 with its own freshness and integrity discipline**, not a mirror bolted onto the commit path.

---

## 4. Consolidation: Managing Unbounded Growth

A continuously learning agent appends forever, so the ledger's scaling story is architectural, not aspirational. The mechanism is **consolidation with provenance-preserving compaction**: periodic cold-path processes distill spans of raw experiences into CSO semantic-memory items of `type: consolidation` (document 02, §3.1), which cite their source experiences by hash. This follows the finding of LongMemEval-V2 that trajectory histories consolidated into events and strategy notes substantially outperform raw-slice retrieval (42.8% on the Small tier — LME-V2-Small — for plain RAG over trajectories, 40.1% overall, vs. stronger results for consolidated memory designs) ([LongMemEval-V2](https://arxiv.org/html/2605.12493v1)) — and it respects the immutability constraint: consolidation never deletes or edits ledger records; it creates *derived* knowledge in the versioned state that points back into the immutable log.

Retrieval tiers follow from the split. Hot-path retrieval operates over consolidations and incorporated-experience projections; cold-path processes (validation replay, causal analysis, research) can always descend to raw records by hash. The design thus separates **access frequency** (consolidations serve the common case) from **evidential authority** (raw records remain the ground truth), which is precisely the separation that lets Memento-style curation pressure (small curated memory beating large accumulated memory ([Memento](https://arxiv.org/html/2508.16153v2))) be applied to the *interpretation layer* without ever destroying evidence. Blob payloads have their own lifecycle: hot storage for recent artifacts, cold/archive storage by age and reference count, with the digest in the ledger record guaranteeing that any retrieved blob is bit-identical to what was captured.

---

## 5. Verifiability: Chains, Trees, and Checkpoints

### 5.1 Per-record hash chain

Every record embeds `prev_hash`, the hash of its predecessor, forming a SHA-256 chain over the full sequence — the pattern already standard in agent audit-trail implementations (e.g., the Hermes agent's hash-chained action log with `sequence, prev_hash, hash` fields and a `verify_chain()` operation ([Hermes Agent issue #487](https://github.com/NousResearch/hermes-agent/issues/487))). Chain walking detects any retroactive modification: altering record *k* invalidates every hash from *k+1* forward. Each record is additionally signed under the agent's GNS identity, binding content to identity at capture time.

### 5.2 Merkle tree and signed checkpoints

The chain alone does not give efficient *inclusion* proofs, so periodically (every `k` records or `T` seconds, whichever first) the ledger computes a Merkle root over the new span, extends a running append-only Merkle tree over the full log, and appends a signed `checkpoint` record containing the new root — directly adapting Certificate Transparency's Signed Tree Head discipline ([RFC 6962](https://datatracker.ietf.org/doc/rfc6962/), [ACM Queue](https://spawn-queue.acm.org/doi/10.1145/2668152.2668154)). Two proof types become cheap. **Inclusion proofs**: any experience can be proven present in the log with a `O(log n)` Merkle audit path from leaf to a checkpoint root — the mechanism by which a committed update's justification can be *shown* to a third party without exposing the log. **Consistency proofs**: any two checkpoints can be proven append-compatible (the later log is a superset of the earlier) with an `O(log n)` path, so an auditor holding an old signed root can verify the log was never rewritten ([ct-merkle](https://github.com/rozbb/ct-merkle), [RFC 6962](https://datatracker.ietf.org/doc/rfc6962/)).

This construction is what the state-DAG commitments of document 01 (Def. 8.1) anchor *into*: a state's commitment references `h(X_j)` for its justifying experiences, and those experiences are provably in the ledger via inclusion proofs against a signed checkpoint — so the full claim "this state came from this experience through this validated update" decomposes into signature verification, hash-chain verification, and Merkle proof verification, all mechanical.

### 5.3 The honesty clause: tamper-evident, not tamper-proof

The ledger's security claims are stated precisely, because overstating them is the standard failure of audit-trail marketing. Hash chains and Merkle trees do not *prevent* modification: an attacker with full storage access can rewrite records and recompute every subsequent hash, producing an internally consistent fabrication ([Regure](https://www.getregure.com/blog/hash-chain-audit-trails-what-they-prove/)). What the construction guarantees is that **modification cannot be made consistent with commitments held elsewhere** — the signed checkpoints and CSO commitments that the agent, its principal, or counterparties have already seen. Integrity is therefore relative to *distributed reference points*: the ledger is exactly as trustworthy as the distribution of its checkpoints.

This yields a concrete deployment rule rather than a vague caveat: **checkpoints must leave the system.** Options, in increasing strength: the principal holds periodic signed checkpoints; checkpoints are anchored into the GNS identity chain (the natural CCR default, document 08); or checkpoints are witnessed by an external transparency service, following the cosigner model in which independent parties refuse to follow anything but a single append-only view, making split-view attacks detectable ([Merkle Tree Certificates, IETF draft](https://davidben.github.io/merkle-tree-certs/draft-ietf-plants-merkle-tree-certs.html)). A CCR deployment whose checkpoints never leave the operator's infrastructure has *self-consistency*, not *integrity* — a distinction the security model (document 07) will formalize as a deployment-level requirement.

---

## 6. The Provenance Chain End-to-End

With documents 01–03 in place, the full provenance chain for a single learned behavior can now be spelled out as a verifiable path across three structures. Consider the claim: *"the agent now avoids Tool A under rate-limit conditions."* The audit path is:

```text
policy_table entry (CSO, versioned)
  └─ provenance_index → created_tx: tx:abc        [learning transaction, doc 04]
       └─ validation record: val:…                 [tests + replay + approval, doc 04]
       └─ justification → exp:…, exp:…             [ledger records, this document]
            └─ Merkle inclusion proof → checkpoint  [§5.2]
       └─ causal_basis → cg-edge:…                 [attributed cause, doc 05]
  └─ CSO commitment → parent chain → genesis       [doc 01, §8.1]
  └─ signature → did:gns:… (identity + authority)  [doc 08]
```

Every hop is a hash reference, a signature check, or a Merkle proof — no hop requires trusting an operator's say-so. In PROV-O terms, the policy entry is an *Entity* `wasGeneratedBy` the transaction (*Activity*) `used` the experiences (*Entities*) `wasAssociatedWith` the agent identity (*Agent*), with `actedOnBehalfOf` reaching the human principal through the delegation chain ([PROV-O](https://travesia.mcu.es/bitstream/10421/7484/1/PROV-O.pdf)). The chain is also *bitemporal* in effect: the ledger's `seq` and timestamps give event time, while CSO versions give belief time — so the audit can distinguish "what the agent knew when it acted" (the experience's `state_version`) from "what the agent knows now," which is exactly the distinction that incident investigation and drift analysis (document 01, §12) require.

---

## 7. Summary and Handoff

The Experience Ledger specified here is the system's ground truth: an append-only, hash-chained, Merkle-checkpointed sequence of structured experience records, gate decisions, annotations, and checkpoints, in which corrections are events, interpretations live elsewhere, and every security claim is stated relative to the distribution of its signed commitments. Its three borrowings are now load-bearing walls: event sourcing supplies the write/read split and replay semantics; transparency logs supply inclusion and consistency proofs; compliance audit practice supplies the honesty about what the cryptography proves. Document 04 (`04-LEARNING-TRANSACTION.md`) specifies the `tx:` objects that consume this ledger — the only machinery permitted to turn its contents into behavioral change — and document 07 will return to §5.3's trust assumptions as formal security requirements.

*Document 03 of the CCR series. Previous: `02-COGNITIVE-STATE-OBJECT.md`. Next: `04-LEARNING-TRANSACTION.md` — the validation, commit, and rollback protocol at record level.*
