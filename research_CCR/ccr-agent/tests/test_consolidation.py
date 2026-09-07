"""Consolidation (item 2, build-guide §2.1a/d) + I6 support independence.

A stable evaluated pattern becomes a committed fact whose `sources` are exactly
the supporting exp_ids; a pattern below min_support produces nothing;
re-confirmation refreshes `last_confirmed_tx`; and support is counted over
root_support-deduplicated experiences (I6), never summed across artifacts.
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
from ccr.consolidation import Consolidator
from ccr.support import root_support, support_count

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REGION = "data-processing"


@pytest.fixture
def rig(tmp_path):
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv, checkpoint_every=32)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    engine = LearningEngine(ledger, AdmissionGate())
    sim = ToolSelectionSimulator(TOOLS, REGIONS, seed=7)
    state = CognitiveState.genesis(REGIONS, TOOLS)
    return ledger, capture, engine, sim, state


def _seed(capture, sim, tool, region, n, start=200):
    for ep in range(start, start + n):
        res = sim.run_episode(tool, region, ep)
        capture.capture(state_summary="s", goal="g", tool=tool, args={"region": region},
                        result=res, outcome_observed=str(res["success"]), signals=res,
                        policy_region=region)


# ---- I6: the single support function -------------------------------------

def test_root_support_counts_the_union_not_the_sum():
    evidence = ["exp:1", "exp:2", "exp:3"]
    fact_from_same = ["exp:2", "exp:3"]          # a fact grown from a subset of evidence
    assert root_support(evidence, fact_from_same) == {"exp:1", "exp:2", "exp:3"}
    assert support_count(evidence, fact_from_same) == 3      # union, NOT 5


def test_gate_support_dedupes_corroborating_overlap(rig):
    ledger, capture, engine, sim, state = rig
    best = sim.best_tool(REGION)
    _seed(capture, sim, best, REGION, 6)
    ev = [e for e in ledger.evaluated() if e.action.policy_region == REGION]
    overlap = [[e.exp_id for e in ev[:2]]]                   # "corroboration" from own evidence
    plain = engine.gate.evaluate_evidence(ev)
    corro = engine.gate.evaluate_evidence(ev, corroborating=overlap)
    assert corro["n"] == plain["n"]                          # no inflation from own-evidence overlap


# ---- consolidation --------------------------------------------------------

def test_stable_pattern_consolidates_to_a_fact(rig):
    ledger, capture, engine, sim, state = rig
    best = sim.best_tool(REGION)
    _seed(capture, sim, best, REGION, 8)                     # >= min_support, high mean
    cons = Consolidator(ledger, min_support=5, min_conf=0.6)
    cands = [c for c in cons.propose_facts(REGION) if f"tool:{best}" in c.content]
    assert cands and cands[0].op == "insert"
    evidence = [e for e in ledger.evaluated()
                if e.action.policy_region == REGION and e.action.steps[-1].tool == best]
    tx, new_state = engine.commit_memory(state, cands[0], evidence)
    assert tx.status == "committed"
    mem_id = tx.delta["mem_id"]
    item = new_state.semantic_memory[mem_id]
    assert item.type == "consolidation" and item.status == "active"
    assert set(item.sources) == {e.exp_id for e in evidence}     # sources = the group (I4)


def test_thin_pattern_below_min_support_produces_nothing(rig):
    ledger, capture, engine, sim, state = rig
    best = sim.best_tool(REGION)
    _seed(capture, sim, best, REGION, 4)                     # 4 < min_support 5
    cons = Consolidator(ledger, min_support=5, min_conf=0.6)
    assert [c for c in cons.propose_facts(REGION) if f"tool:{best}" in c.content] == []


def test_reconfirmation_refreshes_last_confirmed_tx(rig):
    ledger, capture, engine, sim, state = rig
    best = sim.best_tool(REGION)
    _seed(capture, sim, best, REGION, 8)
    cons = Consolidator(ledger, min_support=5, min_conf=0.6)
    cand = [c for c in cons.propose_facts(REGION) if f"tool:{best}" in c.content][0]
    evidence = [e for e in ledger.evaluated()
                if e.action.policy_region == REGION and e.action.steps[-1].tool == best]
    tx1, s1 = engine.commit_memory(state, cand, evidence)
    mem_id = tx1.delta["mem_id"]
    created = s1.semantic_memory[mem_id].last_confirmed_tx
    # propose again with the existing item -> a `confirm`
    cand2 = cons.propose_facts(REGION, existing=s1.semantic_memory)
    conf = [c for c in cand2 if c.op == "confirm" and c.mem_id == mem_id]
    assert conf, "expected a re-confirmation of the existing fact"
    tx2, s2 = engine.commit_memory(s1, conf[0], evidence)
    assert tx2.status == "committed"
    assert s2.semantic_memory[mem_id].last_confirmed_tx == tx2.tx_id != created
