"""Counterfactuals — item 12, PR-A (mitigation; NO admission change).

replay-against-`counterfactual_pattern` for stage-1 edges, chain-confidence
propagation (doc 05 §4), minimal Q2. The gate reads none of this yet — that is PR-B.

Covers: a forged (spurious) chain FAILS replay and a true one SURVIVES (doc 05 §6
made executable); propagation never lifts an uncalibrated edge (flag + arithmetic);
`deprecate_failed_edges` drops the spurious edge and keeps the true one; minimal Q2.
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
from ccr.causal import (
    causal_edge, replay_edge, chain_confidence, scope_for_edge,
    deprecate_failed_edges, REPLAY_TAU,
)
from ccr.experience import EvaluationBlock

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REF = "simulator-ground-truth"
REGION = "data-processing"
_TAG = [0]


class _Tx:
    def __init__(self, tx_id="tx:cf", created_at="2026-09-08T00:00:00Z"):
        self.tx_id = tx_id
        self.created_at = created_at


@pytest.fixture
def rig(tmp_path):
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv, checkpoint_every=64)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    sim = ToolSelectionSimulator(TOOLS, REGIONS, seed=7)
    state = CognitiveState.genesis(REGIONS, TOOLS)
    return ledger, capture, sim, state


def _failure_edge(ledger, capture, tool):
    """An edge claiming `tool` caused a FAILURE in REGION (anomaly=verdict=failure)."""
    _TAG[0] += 1
    exp = capture.emit(state_summary="s", goal="g", tool=tool,
                       args={"region": REGION, "u": _TAG[0]}, result={},
                       outcome_observed="failed", signals={}, policy_region=REGION)
    exp.evaluation = EvaluationBlock(verdict="failure", score=0.0, confidence=0.99,
                                     channels=[REF], evaluator_ref=f"eval:{REF}",
                                     attribution={"load_bearing": ["action.steps[-1]"]})
    ledger.append(exp)
    return causal_edge(exp, _Tx()), exp


# ---- replay: forged fails, true survives (doc 05 §6) ----------------------

def test_true_failure_chain_survives_forged_fails(rig):
    ledger, capture, sim, state = rig
    worst = min(TOOLS, key=lambda t: sim.reliability(t, REGION))   # genuinely unreliable
    best = max(TOOLS, key=lambda t: sim.reliability(t, REGION))    # genuinely reliable
    assert sim.reliability(worst, REGION) < REPLAY_TAU <= sim.reliability(best, REGION), \
        "seed precondition: need a tool below and a tool above the recurrence threshold"

    true_edge, true_exp = _failure_edge(ledger, capture, worst)    # worst really fails a lot
    forged_edge, forged_exp = _failure_edge(ledger, capture, best)  # best rarely fails → spurious

    r_true = replay_edge(true_edge, true_exp, sim)
    r_forged = replay_edge(forged_edge, forged_exp, sim)
    assert r_true["survives"] is True                              # anomaly recurs → holds
    assert r_forged["survives"] is False                          # anomaly does not recur → spurious
    assert r_true["anomaly_recurrence"] > r_forged["anomaly_recurrence"]


# ---- propagation never lifts an uncalibrated edge (doc 05 §4, 1B) ----------

def test_propagation_never_launders_uncalibrated_upward(rig):
    ledger, capture, sim, state = rig
    e_uncal, _ = _failure_edge(ledger, capture, "code_runner")     # minted uncalibrated (0.3 prior)
    assert e_uncal["uncalibrated"] is True and e_uncal["confidence"] == 0.3
    e_cal = dict(e_uncal, edge_id="cg-edge:cal", confidence=0.891, uncalibrated=False)

    c_uncal = chain_confidence([e_uncal])
    c_cal = chain_confidence([e_cal])
    c_mixed = chain_confidence([e_uncal, e_cal])
    assert c_uncal == {"confidence": 0.3, "uncalibrated": True}
    assert c_cal["uncalibrated"] is False
    # a calibrated neighbour cannot lift the uncalibrated chain: flag stays set AND
    # the value only drops (0.3 × 0.891 < 0.891) — arithmetic laundering is impossible
    assert c_mixed["uncalibrated"] is True
    assert c_mixed["confidence"] < c_cal["confidence"]


# ---- deprecate failed edges (doc 05 §6 chain-bloat / spurious drop) --------

def test_deprecate_failed_edges_drops_spurious_keeps_true(rig):
    ledger, capture, sim, state = rig
    worst = min(TOOLS, key=lambda t: sim.reliability(t, REGION))
    best = max(TOOLS, key=lambda t: sim.reliability(t, REGION))
    true_edge, _ = _failure_edge(ledger, capture, worst)
    forged_edge, _ = _failure_edge(ledger, capture, best)
    state.causal_graph["edges"] = [true_edge, forged_edge]

    deprecated = deprecate_failed_edges(state, ledger, sim)
    assert forged_edge["edge_id"] in deprecated
    assert true_edge["edge_id"] not in deprecated
    status = {e["edge_id"]: e["status"] for e in state.causal_graph["edges"]}
    assert status[forged_edge["edge_id"]] == "deprecated"
    assert status[true_edge["edge_id"]] == "active"


# ---- minimal Q2 -----------------------------------------------------------

def test_scope_for_edge_is_the_cited_experience(rig):
    ledger, capture, sim, state = rig
    edge, exp = _failure_edge(ledger, capture, "db_query")
    assert scope_for_edge(edge) == [exp.exp_id]
