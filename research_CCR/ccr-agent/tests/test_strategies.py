"""Strategy library — cross-region generalization (doc 02 §3.5, build-guide §2.3,
item 7). PARALLEL form: a strategy is a cross-region tool ORDERING, induced when the
same ordering has committed in ≥ k regions, applied as a PRIOR that boots a new
region's first policy. Not interposed between policies and tools (see the PR).

  1. three consistent regions → strategy proposed, gated, committed; sources = the
     deduped root UNION across regions (I6 — union, not sum);
  2. two regions (< k) → nothing;
  3. a fourth, new region boots from the strategy ordering, not uniform; provenance
     records the boot;
  4. inconsistent orderings → no strategy (no ordering reaches k);
  5. a strategy induced from poisoned evidence is rejected at the gate.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.ledger import ExperienceLedger, LocalLedgerBackend, generate_keypair
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.state import CognitiveState, PolicyEntry, is_uniform
from ccr.transaction import LearningEngine, AdmissionGate
from ccr.strategy import StrategyInducer, ordering_of
from ccr.experience import EvaluationBlock

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]


@pytest.fixture
def rig(tmp_path):
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv,
                              checkpoint_every=64)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    engine = LearningEngine(ledger, AdmissionGate())
    state = CognitiveState.genesis(REGIONS, TOOLS)
    return ledger, capture, engine, state


_TAG = [0]


def _emit(capture, ledger, region, tool, score, n):
    out = []
    for _ in range(n):
        _TAG[0] += 1
        exp = capture.emit(state_summary="s", goal="g", tool=tool,
                           args={"region": region, "u": _TAG[0]}, result={},
                           outcome_observed="x", signals={}, policy_region=region)
        exp.evaluation = EvaluationBlock(
            verdict="success" if score >= 0.5 else "failure", score=score,
            confidence=0.99, channels=["simulator-ground-truth"],
            evaluator_ref="eval:simulator-ground-truth")
        out.append(ledger.append(exp))
    return out


def _learn(engine, ledger, capture, state, region, best, second):
    """Commit a learned policy for `region` with ordering [best, second] — via the
    real gate + held-out replay (cite a training subset, leave held-out)."""
    best_ev = _emit(capture, ledger, region, best, 1.0, 8)
    second_ev = _emit(capture, ledger, region, second, 0.5, 4)
    train = best_ev[:5] + second_ev[:2]                # rest is held-out
    tx, ns = engine.commit(state, region, train)
    assert tx.status == "committed", tx.validation
    assert ordering_of(ns.policies[region])[:2] == [best, second]
    return ns


# ---- 1. induction → gate → commit; I6 union not sum -----------------------

def test_consistent_regions_induce_a_committed_strategy(rig):
    ledger, capture, engine, state = rig
    for region in REGIONS:                              # all three share [code_runner, db_query]
        state = _learn(engine, ledger, capture, state, region, "code_runner", "db_query")

    cands = StrategyInducer(ledger, k=3).propose(state)
    assert len(cands) == 1
    cand = cands[0]
    assert cand.ordering == ["code_runner", "db_query"]
    assert sorted(cand.support_regions) == sorted(REGIONS)

    evidence = [e for e in ledger if e.exp_id in set(cand.sources)]
    tx, ns = engine.commit_strategy(state, cand, evidence)
    assert tx.status == "committed"
    strat = ns.strategies[tx.delta["strategy_id"]]
    assert strat.ordering == ["code_runner", "db_query"]
    assert strat.status == "active"

    # I6: support is the deduped root UNION, never a per-region sum.
    assert tx.admission["roots"] == len(set(cand.sources))
    # tripwire — a duplicated experience must NOT inflate support (union, not sum)
    doubled = engine.gate.evaluate_evidence(evidence + [evidence[0]])
    assert doubled["roots"] == len(set(cand.sources))


# ---- 2. below k → nothing -------------------------------------------------

def test_two_regions_below_k_propose_nothing(rig):
    ledger, capture, engine, state = rig
    for region in REGIONS[:2]:                          # only two share the ordering
        state = _learn(engine, ledger, capture, state, region, "code_runner", "db_query")
    assert StrategyInducer(ledger, k=3).propose(state) == []


# ---- 3. boot a new region from the strategy prior -------------------------

def test_new_region_boots_from_strategy_not_uniform(rig):
    ledger, capture, engine, state = rig
    for region in REGIONS:
        state = _learn(engine, ledger, capture, state, region, "code_runner", "db_query")
    cand = StrategyInducer(ledger, k=3).propose(state)[0]
    evidence = [e for e in ledger if e.exp_id in set(cand.sources)]
    tx, state = engine.commit_strategy(state, cand, evidence)
    strat_id = tx.delta["strategy_id"]

    NEW = "receivables-region"                          # not in genesis → unlearned
    assert state.policy_for(NEW) is None
    btx, bs = engine.commit_strategy_boot(state, NEW, strat_id)
    assert btx.status == "committed"
    entry = bs.policies[NEW]
    assert not is_uniform(entry.distribution)           # booted from the ordering, not uniform
    assert ordering_of(entry)[:2] == ["code_runner", "db_query"]
    # provenance: the policy cites the boot tx; the delta names the strategy
    assert entry.updated_tx == btx.tx_id
    assert btx.delta["strategy_id"] == strat_id


# ---- 4. inconsistent orderings → no strategy ------------------------------

def test_inconsistent_orderings_induce_nothing(rig):
    """Reported behavior: with three DIFFERENT orderings, no single ordering reaches
    k, so the inducer proposes nothing. (It does not pick a 'winner' by support —
    that would need its own gate pass and is out of scope for the parallel form.)"""
    ledger, capture, engine, state = rig
    pairs = [("code_runner", "db_query"), ("db_query", "web_fetch"),
             ("web_fetch", "search_api")]
    for region, (best, second) in zip(REGIONS, pairs):
        state = _learn(engine, ledger, capture, state, region, best, second)
    assert StrategyInducer(ledger, k=3).propose(state) == []


# ---- 5. poisoned strategy rejected at the gate ----------------------------

def test_strategy_from_poisoned_evidence_is_rejected(rig):
    """A strategy whose supporting evidence is forged low-trust self-reports must be
    rejected at the admission gate, with the rejection recorded — strategies go
    through the gate like everything else."""
    ledger, capture, engine, state = rig
    # forged self-reports (confidence 0.3) for three regions
    forged = []
    for region in REGIONS:
        for _ in range(5):
            _TAG[0] += 1
            exp = capture.emit(state_summary="s", goal="g", tool="code_runner",
                               args={"region": region, "u": _TAG[0]},
                               result={"forged": True}, outcome_observed="succeeded",
                               signals={"success": True}, policy_region=region)
            exp.evaluation = EvaluationBlock(verdict="success", score=1.0, confidence=0.3,
                                             channels=["agent-self-report"],
                                             evaluator_ref="eval:agent-self-report")
            forged.append(ledger.append(exp))
    # hand-set committed policies with a shared ordering (they could not have been
    # gated from this poison — that is the point; we test the STRATEGY gate here).
    for region in REGIONS:
        state.policies[region] = PolicyEntry(
            region=region, distribution={"code_runner": 0.7, "db_query": 0.3},
            confidence=0.8, updated_tx="hand-set", updated_version=0)
    state.seal()

    cand = StrategyInducer(ledger, k=3).propose(state)[0]
    evidence = [e for e in ledger if e.exp_id in set(cand.sources)]
    tx, ns = engine.commit_strategy(state, cand, evidence)
    assert tx.status == "rejected"
    assert tx.validation["verdict"] == "not_reached"    # died at the gate
    assert ns.version == state.version                  # nothing committed
    assert "gate_decision" in [json.loads(l)["kind"] for l in ledger.backend.read_all()]
