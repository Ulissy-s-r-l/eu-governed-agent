"""Admission consumption of causal chains — item 12, PR-B (doc 05 / non-negotiable 3).

Edges enter admission as bounded, provenance-carrying EVIDENCE, never as trusted
structure: a surviving, calibrated chain grounding the cited evidence adds a bounded
uplift to V; failed/uncalibrated chains add ZERO; support (roots) is never touched
(I6); and the aggregate cap X is the safety bound — correlated or independent, a
laundering campaign moves V by at most X on one decision.

  X (aggregate cap) = AdmissionGate.causal_uplift_cap = 0.05  (< the honest margin 0.145)
  γ (typical per-chain influence) = ccr.causal.CAUSAL_GAMMA = 0.1  (NOT the safety bound)
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
from ccr.experience import EvaluationBlock

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REF = "simulator-ground-truth"
REGION = "data-processing"
CAP = 0.05
_TAG = [0]


@pytest.fixture
def rig(tmp_path):
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv, checkpoint_every=64)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    sim = ToolSelectionSimulator(TOOLS, REGIONS, seed=7)
    engine = LearningEngine(ledger, AdmissionGate(), replayer=sim)   # replayer wired
    state = CognitiveState.genesis(REGIONS, TOOLS)
    best = max(TOOLS, key=lambda t: sim.reliability(t, REGION))
    assert sim.reliability(best, REGION) >= 0.5                       # success edges survive replay
    return ledger, capture, sim, engine, state, best


def _exp(capture, ledger, tool, verdict="success"):
    _TAG[0] += 1
    e = capture.emit(state_summary="s", goal="g", tool=tool,
                     args={"region": REGION, "u": _TAG[0]}, result={},
                     outcome_observed="ok", signals={}, policy_region=REGION)
    e.evaluation = EvaluationBlock(verdict=verdict, score=1.0 if verdict == "success" else 0.0,
                                   confidence=0.99, channels=[REF], evaluator_ref=f"eval:{REF}",
                                   attribution={"load_bearing": ["action.steps[-1]"]})
    return ledger.append(e)


def _edge(exp, anomaly_verdict, *, eid, conf=0.85, uncalibrated=False, status="active"):
    return {"edge_id": eid, "rel": "attributed-to",
            "from": f"cg:outcome:{exp.exp_id}", "to": f"cg:cause:{exp.exp_id}",
            "confidence": conf, "attributed_by": f"evaluator:{REF}",
            "attribution_stage": "local",
            "counterfactual_pattern": {"bias": "x", "anomaly": f"verdict={anomaly_verdict}"},
            "uncalibrated": uncalibrated, "status": status,
            "created_tx": "tx:e", "created_at": "t"}


# ---- surviving calibrated chain lifts V, within the cap --------------------

def test_calibrated_surviving_chain_lifts_v_within_cap(rig):
    ledger, capture, sim, engine, state, best = rig
    ev = [_exp(capture, ledger, best)]                       # best tool, success
    state.causal_graph["edges"] = [_edge(ev[0], "success", eid="cg-edge:1")]
    base = engine.gate.evaluate_evidence(ev)
    up = engine.gate.evaluate_evidence(ev, causal_uplift=engine._causal_uplift(state, ev))
    dv = up["V"] - base["V"]
    assert dv > 0                                            # the graph moved the decision
    assert dv <= CAP + 1e-9                                  # ...within the safety bound


# ---- poisoned (calibrated but spurious) edge fails replay → gate unmoved ---

def test_poisoned_edge_fails_replay_so_gate_never_sees_it(rig):
    ledger, capture, sim, engine, state, best = rig
    ev = [_exp(capture, ledger, best)]                       # best tool
    # forged: claims the RELIABLE tool caused a FAILURE — calibrated, but spurious
    state.causal_graph["edges"] = [_edge(ev[0], "failure", eid="cg-edge:forged")]
    assert engine._causal_uplift(state, ev) == 0.0          # fails replay → zero, not a floor
    up = engine.gate.evaluate_evidence(ev, causal_uplift=engine._causal_uplift(state, ev))
    assert up["causal_uplift"] == 0.0


# ---- uncalibrated edge contributes ZERO uplift (not a floor) ---------------

def test_uncalibrated_edge_contributes_zero(rig):
    ledger, capture, sim, engine, state, best = rig
    ev = [_exp(capture, ledger, best)]
    state.causal_graph["edges"] = [_edge(ev[0], "success", eid="cg-edge:u", uncalibrated=True)]
    assert engine._causal_uplift(state, ev) == 0.0


# ---- I6: causal uplift never changes support (roots) -----------------------

def test_causal_uplift_never_changes_roots(rig):
    ledger, capture, sim, engine, state, best = rig
    ev = [_exp(capture, ledger, best)]
    state.causal_graph["edges"] = [_edge(ev[0], "success", eid="cg-edge:i6")]
    base = engine.gate.evaluate_evidence(ev)
    up = engine.gate.evaluate_evidence(ev, causal_uplift=engine._causal_uplift(state, ev))
    assert up["roots"] == base["roots"] and up["n"] == base["n"]


# ---- budget: strongest admissible laundering ≤ X --------------------------

def test_budget_bound_is_the_cap(rig):
    ledger, capture, sim, engine, state, best = rig
    ev = [_exp(capture, ledger, best)]
    base = engine.gate.evaluate_evidence(ev)
    # the strongest possible input: an unbounded raw uplift — the gate MUST clamp to X
    up = engine.gate.evaluate_evidence(ev, causal_uplift=10_000.0)
    assert up["causal_uplift"] == CAP
    assert up["V"] - base["V"] <= CAP + 1e-9


# ---- correlated forgery: N chains, one source → ≤ X TOTAL (not N·X) --------

def test_correlated_forgeries_capped_in_aggregate(rig):
    ledger, capture, sim, engine, state, best = rig
    ev = [_exp(capture, ledger, best)]
    # 20 distinct edges, ALL grounding the SAME experience (one compromised source):
    # raw uplift sums them, but the aggregate cap makes the total ≤ X, not 20·(per-edge).
    state.causal_graph["edges"] = [
        _edge(ev[0], "success", eid=f"cg-edge:{i}") for i in range(20)]
    raw = engine._causal_uplift(state, ev)
    assert raw > CAP                                         # uncapped sum exceeds the bound
    up = engine.gate.evaluate_evidence(ev, causal_uplift=raw)
    assert up["causal_uplift"] == CAP                        # ...but the gate caps the total
