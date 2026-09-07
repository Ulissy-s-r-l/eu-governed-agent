"""GMP-backed semantic-memory persistence (item C, build-guide §2.1c, doc 02 §3.1).

A committed MemoryItem becomes a durable GMP fact; `supersedes` uses the NATIVE
GMP supersede op (ADR-0008), so a superseded belief drops out of `retrieve`
while remaining in `audit`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.ledger import ExperienceLedger, LocalLedgerBackend, generate_keypair
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.simulator import ToolSelectionSimulator
from ccr.state import CognitiveState
from ccr.transaction import LearningEngine, AdmissionGate
from ccr.consolidation import Consolidator, MemoryCandidate
from ccr.gmp_bridge import GMPInMemoryBackend
from ccr.gmp_memory import GMPMemoryStore
from ccr.contradiction import claim_content, SENSE_RELIABLE, SENSE_UNRELIABLE
from ccr.experience import EvaluationBlock

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REGION = "data-processing"


@pytest.fixture
def rig(tmp_path):
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv, checkpoint_every=32)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    store = GMPMemoryStore(GMPInMemoryBackend())
    engine = LearningEngine(ledger, AdmissionGate(), memory_store=store)
    sim = ToolSelectionSimulator(TOOLS, REGIONS, seed=7)
    state = CognitiveState.genesis(REGIONS, TOOLS)
    best = sim.best_tool(REGION)
    for ep in range(200, 208):
        res = sim.run_episode(best, REGION, ep)
        capture.capture(state_summary="s", goal="g", tool=best, args={"region": REGION},
                        result=res, outcome_observed=str(res["success"]), signals=res,
                        policy_region=REGION)
    return ledger, engine, store, sim, state, best


def _consolidate(ledger, engine, state, best):
    cons = Consolidator(ledger, min_support=5, min_conf=0.6)
    cand = [c for c in cons.propose_facts(REGION) if f"tool:{best}" in c.content][0]
    evidence = [e for e in ledger.evaluated()
                if e.action.policy_region == REGION and e.action.steps[-1].tool == best]
    return engine.commit_memory(state, cand, evidence)


def test_committed_fact_is_persisted_and_queryable(rig):
    ledger, engine, store, sim, state, best = rig
    tx, new_state = _consolidate(ledger, engine, state, best)
    mem_id = tx.delta["mem_id"]
    facts = store.retrieve_active(subject=mem_id)
    preds = {f.predicate: f for f in facts}
    assert "ccr:mem/consolidation" in preds                 # the belief fact
    assert "ccr:mem/sources" in preds                       # I4 provenance as a companion fact
    belief = preds["ccr:mem/consolidation"]
    assert belief.obj == new_state.semantic_memory[mem_id].content
    assert belief.importance == new_state.semantic_memory[mem_id].confidence


def test_supersede_uses_the_native_op(rig):
    ledger, engine, store, sim, state, best = rig
    tx1, s1 = _consolidate(ledger, engine, state, best)
    old_mem = tx1.delta["mem_id"]
    assert store.retrieve_active(subject=old_mem)            # active before

    # a corrected belief that supersedes the first (native GMP supersede op)
    evidence = [e for e in ledger.evaluated()
                if e.action.policy_region == REGION and e.action.steps[-1].tool == best]
    corrected = MemoryCandidate(op="insert", type="consolidation",
                                content=f"tool:{best} reliable in region:{REGION} (v2)",
                                sources=[e.exp_id for e in evidence], confidence=0.9,
                                region=REGION, supersedes_mem_id=old_mem)
    tx2, s2 = engine.commit_memory(s1, corrected, evidence)
    new_mem = tx2.delta["mem_id"]

    active = {f.predicate for f in store.retrieve_active(subject=old_mem)}
    assert "ccr:mem/consolidation" not in active            # old belief dropped from retrieve
    assert store.retrieve_active(subject=new_mem)           # new belief active
    # but the old fact is still in the audit trail (superseded, not deleted)
    audited = [f for f in store.backend.audit() if f.superseded_by]
    assert audited, "superseded fact must remain in the audit trail"


# ---- contested reaches GMP (doc 02 §3.1) ----------------------------------

def _evidence(capture, tag, score, region, n=4):
    out = []
    for k in range(n):
        exp = capture.emit(state_summary="s", goal="g", tool="db_query", args={},
                           result={}, outcome_observed="x", signals={},
                           policy_region=region)
        exp.evaluation = EvaluationBlock(verdict="v", score=score, confidence=0.99,
                                         channels=["simulator-ground-truth"],
                                         evaluator_ref="eval:ref")
        exp.exp_id = f"exp:{tag}:{k}"
        out.append(exp)
    return out


def _cand(sense, evidence, region, supersedes=None):
    return MemoryCandidate(op="insert", type="consolidation",
                           content=claim_content("db_query", region, sense),
                           sources=[e.exp_id for e in evidence], confidence=0.9,
                           region=region, supersedes_mem_id=supersedes)


def _contested_pair(tmp_path):
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv, checkpoint_every=32)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    store = GMPMemoryStore(GMPInMemoryBackend())
    engine = LearningEngine(ledger, AdmissionGate(), memory_store=store)
    state = CognitiveState.genesis(REGIONS, TOOLS)
    ev_pos = _evidence(capture, "pos", 0.95, REGION)
    tx1, s1 = engine.commit_memory(state, _cand(SENSE_RELIABLE, ev_pos, REGION), ev_pos)
    ev_neg = _evidence(capture, "neg", 0.30, REGION)
    tx2, s2 = engine.commit_memory(s1, _cand(SENSE_UNRELIABLE, ev_neg, REGION), ev_neg)
    return ledger, capture, engine, store, s2, tx1.delta["mem_id"], tx2.delta["mem_id"]


def test_contested_belief_drops_from_the_retrieve_path(tmp_path):
    """The durable tier must not serve a belief the runtime has quarantined: a
    contested belief drops out of the standard `retrieve` (CCR read) path."""
    _, _, _, store, s2, rid, uid = _contested_pair(tmp_path)
    assert s2.semantic_memory[rid].status == "contested"    # in-state quarantined
    assert s2.semantic_memory[uid].status == "contested"
    # standard GMP query path (what a peer agent reads) no longer serves either
    # belief (or its provenance) — only the contested marker remains, as the signal
    for mid in (rid, uid):
        preds = {f.predicate for f in store.retrieve_active(subject=mid)}
        assert "ccr:mem/consolidation" not in preds         # belief quarantined
        assert "ccr:mem/sources" not in preds               # provenance quarantined too
    # the contested marker is present and names the partner
    markers = {m.subject: m.obj
               for m in store.backend.retrieve(predicate=GMPMemoryStore.CONTESTED_PRED)}
    assert markers.get(rid) == uid and markers.get(uid) == rid


def test_contested_exclusion_is_conventional_not_structural(tmp_path):
    """HONESTY TEST: the exclusion is a CCR convention (contested ⇒ valid_until),
    not a GMP primitive. A convention-UNAWARE consumer — reading the audit view
    rather than the CCR read path — still sees the contested belief. This documents
    the ceiling of what GMP-without-a-contested-primitive allows."""
    _, _, _, store, s2, rid, uid = _contested_pair(tmp_path)
    # a naive consumer that does not know the convention: it reads the raw audit
    # stream, not retrieve/retrieve_active.
    audited_beliefs = [f for f in store.backend.audit()
                       if f.predicate == "ccr:mem/consolidation"
                       and f.subject in (rid, uid)]
    assert audited_beliefs, "audit-view consumer STILL sees the contested belief"
    # each such belief is bi-temporally closed — the ONLY signal a careful naive
    # consumer could honor; a careless one serves it anyway.
    assert all(f.valid_until is not None for f in audited_beliefs)


def test_reconciliation_returns_the_survivor_to_the_gmp_read_path(tmp_path):
    """A contested belief whose partner is superseded away returns to the
    behavioral path in GMP, mirroring reconcile_contested in state."""
    ledger, capture, engine, store, s2, rid, uid = _contested_pair(tmp_path)
    before = {f.predicate for f in store.retrieve_active(subject=rid)}
    assert "ccr:mem/consolidation" not in before            # quarantined while contested

    ev_fix = _evidence(capture, "fix", 0.95, REGION)
    tx3, s3 = engine.commit_memory(
        s2, _cand(SENSE_RELIABLE, ev_fix, REGION, supersedes=uid), ev_fix)
    assert s3.semantic_memory[rid].status == "active"        # survivor restored in-state
    # survivor's belief is back in the GMP read path
    preds = {f.predicate for f in store.retrieve_active(subject=rid)}
    assert "ccr:mem/consolidation" in preds
    # both contested markers are closed (dropped from the current-validity view)
    assert store.backend.retrieve(predicate=GMPMemoryStore.CONTESTED_PRED) == []
