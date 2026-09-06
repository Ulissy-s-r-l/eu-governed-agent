"""Phase 3-4 tests: admission gate, replay validation, commit, revert, read path."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.ledger import ExperienceLedger, LocalLedgerBackend, generate_keypair
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.simulator import ToolSelectionSimulator
from ccr.state import CognitiveState
from ccr.transaction import LearningEngine, LearningAgent, AdmissionGate
from ccr.experience import EvaluationBlock

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REGION = "data-processing"


@pytest.fixture
def rig(tmp_path):
    priv, pub = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv,
                              checkpoint_every=32)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    engine = LearningEngine(ledger, AdmissionGate(threshold=0.55, min_evidence=3))
    sim = ToolSelectionSimulator(TOOLS, REGIONS, seed=7)
    state = CognitiveState.genesis(REGIONS, TOOLS)
    # honest evaluated history
    for ep in range(24):
        tool = TOOLS[ep % len(TOOLS)]
        res = sim.run_episode(tool, REGION, ep)
        capture.capture(state_summary="s", goal="g", tool=tool,
                        args={"region": REGION}, result=res,
                        outcome_observed=str(res["success"]), signals=res,
                        policy_region=REGION)
    return ledger, capture, engine, sim, state, priv, pub


def test_genesis_state_is_uniform_and_sealed(rig):
    _, _, _, _, state, _, _ = rig
    p = state.policy_for(REGION)
    assert abs(sum(p.distribution.values()) - 1.0) < 1e-9
    assert state.commitment.startswith("sha256:")


def test_honest_evidence_commits_and_changes_behavior(rig):
    ledger, _, engine, sim, state, *_ = rig
    agent = LearningAgent(state, TOOLS)
    evidence = [e for e in ledger.evaluated() if e.action.policy_region == REGION]
    # held-out replay (doc 04 §2.2): cite a TRAINING SUBSET; the rest is the
    # disjoint held-out set replay validates against. Citing all self-rejects.
    train = evidence[: len(evidence) // 2]
    tx, new_state = engine.commit(state, REGION, train)
    agent.on_state(new_state)
    assert tx.status == "committed"
    assert new_state.version == 1
    assert new_state.parent_commitment == state.commitment
    # the read path: behavior now reflects committed state
    assert agent.select_tool(REGION) == sim.best_tool(REGION)
    # provenance: policy entry cites its committing transaction (I4)
    assert new_state.policy_for(REGION).updated_tx == tx.tx_id


def test_poisoned_self_report_rejected_at_gate(rig):
    ledger, capture, engine, sim, state, *_ = rig
    bad = min(TOOLS, key=lambda t: sim.reliability(t, REGION))
    forged = []
    for _ in range(4):
        exp = capture.emit(state_summary="s", goal="g", tool=bad, args={},
                           result={"forged": True}, outcome_observed="succeeded",
                           signals={"success": True}, policy_region=REGION)
        exp.evaluation = EvaluationBlock(verdict="success", score=1.0,
                                         confidence=0.3,
                                         channels=["agent-self-report"],
                                         evaluator_ref="eval:agent-self-report")
        forged.append(ledger.append(exp))
    tx, new_state = engine.commit(state, REGION, forged)
    assert tx.status == "rejected"
    assert tx.validation["verdict"] == "not_reached"     # died at the gate
    assert new_state.version == state.version            # nothing committed
    # rejection is in the ledger
    kinds = [json.loads(l)["kind"] for l in ledger.backend.read_all()]
    assert "gate_decision" in kinds


def test_replay_kills_regression(rig):
    ledger, _, engine, sim, state, *_ = rig
    evidence = [e for e in ledger.evaluated() if e.action.policy_region == REGION]
    # held-out split: honest commit cites a training subset (see above).
    train = evidence[: len(evidence) // 2]
    tx0, state = engine.commit(state, REGION, train)
    assert tx0.status == "committed"
    mediocre = [t for t in TOOLS if t != sim.best_tool(REGION)][1]
    thin = [e for e in evidence if e.action.steps[-1].tool == mediocre][:3]
    tx2, state2 = engine.commit(state, REGION, thin)
    assert tx2.status == "rejected"
    assert tx2.validation["verdict"] == "reject"
    assert "replay regression" in tx2.validation["reason"]
    assert state2.version == state.version               # unchanged


def test_revert_is_forward_only_and_verifiable(rig):
    ledger, _, engine, sim, state, *_ = rig
    evidence = [e for e in ledger.evaluated() if e.action.policy_region == REGION]
    tx1, s1 = engine.commit(state, REGION, evidence)
    tx2, s2 = engine.revert(s1, state, incident_evidence="test incident")
    assert tx2.tx_type == "revert" and tx2.status == "committed"
    # forward-only: restored state is parented to the HARMED state
    assert s2.parent_commitment == s1.commitment
    assert s2.version == s1.version + 1
    # content equals the ancestor's policies
    assert s2.policies[REGION].distribution == state.policies[REGION].distribution
    # history intact: both transactions recorded, chain still verifies
    assert any(t.tx_id == tx1.tx_id for t in engine.transactions)
    assert ledger.verify_chain()


def test_gate_requires_minimum_evidence(rig):
    ledger, _, engine, sim, state, *_ = rig
    evidence = [e for e in ledger.evaluated() if e.action.policy_region == REGION][:2]
    tx, new_state = engine.commit(state, REGION, evidence)
    assert tx.status == "rejected"                        # n=2 < min_evidence=3
    assert tx.admission["admit"] is False
