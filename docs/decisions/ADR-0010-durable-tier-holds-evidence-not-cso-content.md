---
status: accepted
decision_date: 2026-09-08
record_date: 2026-09-08
provenance: contemporaneous
capture_status: not-attested
---

# ADR-0010 — The durable tier holds evidence, not CSO content

- **Status:** **Accepted**
- **Decision date:** 2026-09-08

## Context

The CCR durable evidence tier — realized in a deployment as the GRAFOMEM Cloud GMP fact store
(the CCR-agent README terminology mapping) — began accumulating **CSO content** one component at a
time, with no rule governing whether it should. A source audit found three different answers arrived
at separately:

- **experiences** reach GMP via `GMPFactBridge` (the legitimate ledger→durable-tier mapping);
- **semantic_memory** reaches GMP via `gmp_memory.py:GMPMemoryStore` (item C) — a copy of CSO
  content into the evidence tier;
- **policies, strategies, evaluation_history, confidence_policy** reach GMP by **no path at all**;
- **contested** beliefs are excluded from the mirror by *convention* (`valid_until` + a marker) that
  a non-conforming consumer ignores.

The specification already states the rule, and states it more strongly than the code assumed. Doc 03
**§1**: *"the ledger does not store beliefs; conclusions, consolidations, and learned content live in
the CSO's semantic memory, which cites ledger records."* Doc 03 **§3.3**: the ledger does not store
*"consolidations (CSO content), policy states (CSO content)."* Doc 03 **§6**: the CSO is **linked** to
the ledger by the provenance chain (`created_tx`, justifying `exp` records, Merkle inclusion), not
stored in it. Doc 00 **§4.3**: learned behaviour *"lives in the CSO … a durable, portable asset."* The
CCR-agent README maps **CSO → working-memory tier**, **Experience Ledger → GMP durable tier**.

Against that, **item C was an undocumented divergence** from §3.3, and the `semantic_memory` +
`contested` mirror it introduced was **undetectably stale**: a mirrored GMP fact carries `valid_from`
(a timestamp) but no `created_tx` and no CSO commitment, so a consumer joining GMP cannot tell which
committed CSO version it is seeing, and a lagged or failed mirror write is invisible.

## Decision

**The durable evidence tier holds evidence — the four doc 03 §3.2 record kinds (`experience`,
`gate_decision`, `annotation`, `checkpoint`) — and nothing else. No CSO component
(`semantic_memory`, `policy_table`, `strategy_library`, `evaluation_history`,
`confidence_map`/`confidence_policy`, or any future document-02 component) is written to the durable
tier. CSO content is *linked* to evidence by the provenance chain, never *copied* into it.** This is
now stated normatively as doc 03 **§3.4**, with §3.3 pointing at it and doc 02 §3.1 carrying a
one-line pointer.

**Rationale.** The transferable unit between agents is **evidence with its provenance**, re-validated
through the *receiving* agent's own admission gate and its own reference-calibrated trust (doc 07
§2.2a) — never a **belief**, which would carry the source agent's trust root sight unseen and would
**federate the contested-leak** the conventional exclusion already permits. Fleet warm-start transfers
the **signed CSO + ledger** (doc 00 §4.3), not mirrored beliefs. Cross-agent belief sharing is **not a
present requirement**; Grafomem Cloud's federation layer is its eventual home if it ever becomes one.
And the CSO is *already* the durable, signed, versioned object (doc 01 Def. 8.1) — a mirror is a
stale-prone copy of the most verifiable thing in the system.

This is the candidate-3 position of the GMP-mirror report. Item C and the contested→GMP mirror are
walked back (a separate change); the "no path" components are retroactively **correct**, not gaps.

## Consequences — the operative constraints

- **The walk-back removes the belief mirror, not just its future use.** `gmp_memory.py` is deleted
  rather than left dormant; a rule-shaped guard test replaces its behavioural tests, asserting that a
  full commit sequence (memory, policy, strategy, recalibrate) writes **no CSO-derived fact** to the
  durable tier.

- **The inversion this rule exposed — the durable tier was INCOMPLETE, not merely uncrossed — is now
  CLOSED (2026-09-08, PR #30).** `gate_decision` records are the change-log that documents **every**
  CSO mutation (admit/reject, the functional's component values, the committed delta), and doc 03 §3.2
  places them **in the ledger precisely** so that *"why did the agent start avoiding Tool A?"* is
  answerable by joining the experience, the gate decision that admitted it, and the transaction that
  committed the policy. Previously `GMPFactBridge.append` admitted `kind == "experience"` **only**, so
  the §3.2 three-way join was satisfiable **only on the local ledger**. The bridge now also maps
  `gate_decision` → `ccr:gate_decision` (subject = tx_id; object = the admission/validation audit
  **including the delta**) plus a `ccr:gate_decision/on` link naming the cited exp_ids, and
  `checkpoint` → `ccr:checkpoint` — so the join resolves **entirely on the durable tier, for committed
  AND rejected transactions** (`tests/test_durable_tier.py`). This is the opposite of the item-C
  mistake: mirror *more evidence* (the SUBJECT stays the tx_id / checkpoint_id; a delta's distribution
  or ordering rides in the OBJECT as evidence), never *any belief* (no fact subject is a CSO id, no
  `ccr:mem/*` predicate — the guard test asserts both). `annotation` is still unmapped: nothing writes
  one today, and designing for a phantom is the mirror mistake in a different costume.

- **DOCUMENTED-OPEN DOOR — a curated belief export (candidate 2) activates only when ALL of:**
  (a) a **concrete consumer** exists with a stated constraint that evidence-sharing through its own
  gate cannot meet; (b) a **§3.3 carve** makes the export sanctioned rather than a divergence;
  (c) a **fact → CSO-commitment freshness link** is upstreamed as a Foundation record per
  [ADR-0008](ADR-0008-b3-best-client-of-general-ledger.md) — **never payload-encoded** (no commitment
  id stuffed into a fact's object); (d) the **contested exclusion is made STRUCTURAL**, not
  conventional — conventional exclusion at federation scale is the D1 poisoning vector with extra
  steps (a consumer that ignores the convention consumes a belief the origin runtime has quarantined).
  Absent all four, the door stays shut.

- **HONESTY LIMIT.** The GMP native `supersede`/`close` operations this design reasons about have only
  ever been exercised against `GMPInMemoryBackend` (demo + tests); **no real Grafomem Cloud GMP
  endpoint is wired in this tree.** "Native op" is a claim about the **GMP v0.2 op model**, not
  observed real-GMP behaviour. Any statement here about what a real GMP consumer sees is a claim about
  the spec, pending a live backend.

- **Cross-reference [ADR-0008](ADR-0008-b3-best-client-of-general-ledger.md).** The candidate-2
  freshness link (fact → CSO commitment) obeys the same constraint: a gap in what the ledger/GMP can
  express is fixed **upstream as a Foundation record**, never patched in the product write path.

## Open sub-questions

- What is the concrete review test that catches a *new* component mirroring itself to GMP — the
  failure mode that produced item C — beyond the guard test this decision ships?
- If cross-agent evidence transfer (not belief) is built, does the receiving gate need anything the
  current admission functional lacks to re-validate *foreign* evidence (e.g. binding foreign
  provenance to the receiver's reference channel)?
