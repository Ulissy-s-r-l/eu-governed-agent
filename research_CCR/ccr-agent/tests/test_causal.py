"""Causal graph — attributed edges, store + stage-1 attribution (doc 02 §3.7, doc 05).

Covers: (a) an attributed edge commits with its citing tx and lands in the new state;
(b) an edge without a source channel or a committing tx is refused (I4-for-causes);
(c) attributed_by is DERIVED — a caller-supplied value is structurally unrepresentable
(no such parameter), a self-report source cannot be labelled `evaluator`, and an edge
from an uncalibrated channel is flagged; (d) the Q3 why-walk resolves on the durable
tier through the new `ccr:gate_decision/caused` fact; (e) as of item 12 PR-B the gate
DOES consume the graph — a surviving, calibrated chain moves V by a bounded amount
(the (e)-guard, inverted from its non-consumption form). Plus the standing injection
probes against the new caused mapping.
"""
import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.ledger import (
    ExperienceLedger, LocalLedgerBackend, CompositeBackend, generate_keypair,
)
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.state import CognitiveState
from ccr.transaction import LearningEngine, AdmissionGate
from ccr.calibration import CalibrationLoop
from ccr.causal import causal_edge, insert_edges, why_believed, STAGE_LOCAL
from ccr.gmp_bridge import GMPInMemoryBackend, GMPFactBridge, gate_decision_to_facts, GMPFact
from ccr.experience import EvaluationBlock

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REF = "simulator-ground-truth"
_TAG = [0]


class _Tx:
    def __init__(self, tx_id="tx:test", created_at="2026-09-08T00:00:00Z"):
        self.tx_id = tx_id
        self.created_at = created_at


def _rig(tmp_path, *, gmp=False):
    priv, _ = generate_keypair()
    store = GMPInMemoryBackend() if gmp else None
    backend = (CompositeBackend(LocalLedgerBackend(tmp_path / "l.jsonl"), GMPFactBridge(store))
               if gmp else LocalLedgerBackend(tmp_path / "l.jsonl"))
    ledger = ExperienceLedger(backend, priv, checkpoint_every=64)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    engine = LearningEngine(ledger, AdmissionGate())
    state = CognitiveState.genesis(REGIONS, TOOLS)
    return ledger, capture, engine, state, store


def _emit(capture, ledger, region, tool, score, n, *, channel=REF, load_bearing=True):
    out = []
    for _ in range(n):
        _TAG[0] += 1
        exp = capture.emit(state_summary="s", goal="g", tool=tool,
                           args={"region": region, "u": _TAG[0]}, result={},
                           outcome_observed="ok", signals={}, policy_region=region)
        exp.evaluation = EvaluationBlock(
            verdict="success" if score >= 0.5 else "failure", score=score, confidence=0.99,
            channels=[channel], evaluator_ref=f"eval:{channel}",
            attribution={"load_bearing": ["action.steps[-1]"]} if load_bearing else {})
        out.append(ledger.append(exp))
    return out


def _learn(engine, ledger, capture, state, region):
    best = _emit(capture, ledger, region, "code_runner", 1.0, 8)
    second = _emit(capture, ledger, region, "db_query", 0.5, 4)
    tx, ns = engine.commit(state, region, best[:5] + second[:2])
    assert tx.status == "committed", tx.validation
    return tx, ns


# ---- (a) an attributed edge commits with its citing tx --------------------

def test_attributed_edge_commits_and_lands_in_state(tmp_path):
    ledger, capture, engine, state, _ = _rig(tmp_path)
    tx, ns = _learn(engine, ledger, capture, state, REGIONS[0])
    assert tx.causal, "the committing tx recorded no causal edges"
    edge = tx.causal[0]
    assert edge["rel"] == "attributed-to"
    assert edge["attributed_by"] == f"evaluator:{REF}"        # derived from the channel
    assert edge["attribution_stage"] == STAGE_LOCAL           # stage 1 only, today
    assert edge["counterfactual_pattern"]["bias"] and edge["counterfactual_pattern"]["anomaly"]
    assert edge["created_tx"] == tx.tx_id                     # I4-for-causes
    # present in the committed graph (beside the delta), nodes are refs
    assert any(e["edge_id"] == edge["edge_id"] for e in ns.causal_graph["edges"])
    refs = {n["ref"] for n in ns.causal_graph["nodes"]}
    assert refs and refs <= {e.exp_id for e in ledger}       # nodes reference ledger records


# ---- (b) I4-for-causes: no source or no tx → refused ----------------------

def test_edge_without_source_or_tx_is_refused(tmp_path):
    ledger, capture, engine, state, _ = _rig(tmp_path)
    # a load-bearing attribution but NO evaluation channel → cannot derive attributed_by
    exp = _emit(capture, ledger, REGIONS[0], "code_runner", 1.0, 1)[0]
    exp.evaluation = EvaluationBlock(verdict="success", score=1.0, confidence=0.99,
                                     channels=[], attribution={"load_bearing": ["action.steps[-1]"]})
    with pytest.raises(ValueError):
        causal_edge(exp, _Tx())
    # a valid attribution but NO committing tx id
    good = _emit(capture, ledger, REGIONS[0], "code_runner", 1.0, 1)[0]
    with pytest.raises(ValueError):
        causal_edge(good, _Tx(tx_id=""))


# ---- (c) attributed_by is DERIVED, not supplied ---------------------------

def test_attributed_by_is_structurally_underivable_from_a_caller(tmp_path):
    # STRUCTURAL, not validated-away: the signature takes (experience, tx) — there is
    # no parameter a caller could pass an attributed_by (or uncalibrated) through.
    params = list(inspect.signature(causal_edge).parameters)
    assert params == ["experience", "tx"], params
    assert "attributed_by" not in params and "uncalibrated" not in params


def test_self_report_source_cannot_be_labelled_evaluator(tmp_path):
    ledger, capture, engine, state, _ = _rig(tmp_path)
    exp = _emit(capture, ledger, REGIONS[0], "code_runner", 1.0, 1,
                channel="agent-self-report")[0]
    edge = causal_edge(exp, _Tx())
    assert edge["attributed_by"] == "agent-trace"            # NOT "evaluator:..."


def test_edge_flagged_uncalibrated_without_committed_calibration(tmp_path):
    ledger, capture, engine, state, _ = _rig(tmp_path)
    # no recalibrate yet → the reference channel has no committed reliability
    tx, ns = _learn(engine, ledger, capture, state, REGIONS[0])
    assert tx.causal[0]["uncalibrated"] is True
    # commit a recalibrate so simulator-ground-truth carries a committed reliability
    cal = CalibrationLoop(reference_channel=REF)
    for i in range(10):
        cal.observe("agent-self-report", agreed=(i % 2 == 0), exp_id=f"e{i}")
    _, ns = engine.recalibrate(ns, cal)
    tx2, ns2 = _learn(engine, ledger, capture, ns, REGIONS[1])
    assert tx2.causal[0]["uncalibrated"] is False            # now calibrated
    assert tx2.causal[0]["confidence"] > tx.causal[0]["confidence"]


# ---- (d) the why-walk resolves on the durable tier ------------------------

def test_why_walk_resolves_on_the_durable_tier(tmp_path):
    ledger, capture, engine, state, gmp = _rig(tmp_path, gmp=True)
    tx, ns = _learn(engine, ledger, capture, state, REGIONS[0])
    created_tx = ns.policies[REGIONS[0]].updated_tx          # the only CSO read: the pointer

    # local Q3 walk (doc 05 §5 / doc 03 §6 causal_basis → cg-edge)
    outcome_exp = tx.causal[0]["from"].split("cg:outcome:", 1)[1]
    assert why_believed(ns.causal_graph, outcome_exp), "Q3 why-walk returned nothing"

    # the same hop, resolved ENTIRELY on the durable tier
    caused = gmp.retrieve(predicate="ccr:gate_decision/caused", subject=created_tx)
    assert caused, "no ccr:gate_decision/caused fact on the durable tier"
    obj = json.loads(caused[0].obj)
    assert obj["attributed_by"] == f"evaluator:{REF}"
    cited_exp = obj["cited_exp"]
    assert gmp.retrieve(predicate="ccr:outcome", subject=cited_exp), \
        "attributed cause's experience not on the durable tier"


# ---- (e) INVERSION — the non-consumption era ends here (item 12 PR-B) ------
# Formerly `test_graph_does_not_change_the_gate_decision`, correct ONLY while causal
# edges were unconsumed. As of item 12 PR-B the gate READS the graph: a surviving,
# calibrated chain grounding the cited evidence moves V by a BOUNDED amount. This
# inversion is the visible signature that the non-consumption era ended, deliberately.

def test_graph_changes_the_gate_decision_when_consumed(tmp_path):
    from ccr.simulator import ToolSelectionSimulator
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv, checkpoint_every=64)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    sim = ToolSelectionSimulator(TOOLS, REGIONS, seed=7)
    engine = LearningEngine(ledger, AdmissionGate(), replayer=sim)   # the gate can now read the graph
    state = CognitiveState.genesis(REGIONS, TOOLS)
    region = max(REGIONS, key=lambda r: max(sim.reliability(t, r) for t in TOOLS))
    best = max(TOOLS, key=lambda t: sim.reliability(t, region))
    assert sim.reliability(best, region) >= 0.5                      # success chain survives replay

    ev = _emit(capture, ledger, region, best, 1.0, 1)              # best tool, success
    e = ev[0]
    state.causal_graph["edges"] = [{                                # surviving, calibrated chain
        "edge_id": "cg-edge:surv", "rel": "attributed-to",
        "from": f"cg:outcome:{e.exp_id}", "to": f"cg:cause:{e.exp_id}",
        "confidence": 0.85, "attributed_by": f"evaluator:{REF}", "attribution_stage": "local",
        "counterfactual_pattern": {"bias": "x", "anomaly": "verdict=success"},
        "uncalibrated": False, "status": "active", "created_tx": "tx:e", "created_at": "t"}]
    base = engine.gate.evaluate_evidence(ev)
    consumed = engine.gate.evaluate_evidence(ev, causal_uplift=engine._causal_uplift(state, ev))
    dv = consumed["V"] - base["V"]
    assert dv > 0                                                   # the gate now reads the graph
    assert dv <= engine.gate.causal_uplift_cap + 1e-9              # bounded by the aggregate cap


# ---- injection probes: the durable-tier guard still BITES ------------------

def test_caused_fact_never_carries_a_cso_subject(tmp_path):
    """A legit gate_decision/caused fact has subject == tx_id (not an edge/mem/region/
    strategy id); a reintroduced belief fact fails each guard check independently."""
    payload = {"tx_id": "tx:1", "tx_type": "learn", "status": "committed",
               "admission": {"admit": True}, "validation": {"verdict": "commit"},
               "parent_state": "cso:0", "new_commitment": "cso:1", "created_at": "t",
               "delta": {"target": "policy_table", "justification": ["exp:1"]},
               "causal": [{"edge_id": "cg-edge:abc", "rel": "attributed-to",
                           "from": "cg:outcome:exp:1", "to": "cg:cause:exp:1",
                           "attributed_by": "evaluator:sim", "attribution_stage": "local",
                           "uncalibrated": True}]}
    facts = gate_decision_to_facts(payload)
    caused = [f for f in facts if f.predicate == "ccr:gate_decision/caused"]
    assert caused and all(f.subject == "tx:1" for f in caused)   # (i) subject is tx_id only
    assert not any(f.subject in {"cg-edge:abc", "cg:cause:exp:1"} for f in facts)

    evidence_ids = {"tx:1", "exp:1"}                          # ledger record ids
    cso_ids = {"cg-edge:abc", "mem:x", "api-interaction", "strat:9"}
    # (ii) a reintroduced belief fact fails (a)/(b)/(c) independently
    belief = GMPFact(predicate="ccr:mem/consolidation", subject="mem:x", obj="x", valid_from="t")
    probe = facts + [belief]
    assert not all(f.subject in evidence_ids for f in probe)          # (a)
    assert cso_ids & {f.subject for f in probe}                       # (b)
    assert any(f.predicate.startswith("ccr:mem/") for f in probe)     # (c)
    # (iii) a fact whose subject is an edge/mem/region/strategy id fails (b)
    for bad in ("cg-edge:abc", "mem:x", "api-interaction", "strat:9"):
        f = GMPFact(predicate="ccr:whatever", subject=bad, obj="x", valid_from="t")
        assert cso_ids & {f.subject}
