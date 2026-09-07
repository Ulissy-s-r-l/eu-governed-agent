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
