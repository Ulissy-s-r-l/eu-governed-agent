"""The durable tier holds evidence, not CSO content (doc 03 §3.4 / ADR-0010).

This REPLACES the old test_gmp_memory.py, which tested the belief mirror that
ADR-0010 walked back. A test of the removal ("committing writes nothing") would pass
trivially and catch nothing; item C happened precisely because no test forbade a
component mirroring itself. So this is a RULE-SHAPED GUARD: it drives a full commit
sequence touching every CSO component that reaches a durable path today or could, and
asserts the durable tier carries only §3.2 evidence — no belief, policy, strategy, or
calibration state. It must FAIL if any current OR future component mirrors itself.
"""
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
from ccr.strategy import StrategyInducer
from ccr.calibration import CalibrationLoop
from ccr.consolidation import MemoryCandidate
from ccr.contradiction import claim_content, SENSE_RELIABLE
from ccr.gmp_bridge import GMPInMemoryBackend, GMPFactBridge
from ccr.experience import EvaluationBlock

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REF = "simulator-ground-truth"

# The durable tier holds exactly these record kinds (doc 03 §3.2). The guard checks
# against the whole list — NOT "experience only" — so that when the deferred
# gate_decision/checkpoint mirroring (ADR-0010) lands, its facts pass a test they
# should pass, while any CSO-content mirror still fails.
EVIDENCE_KINDS = {"experience", "gate_decision", "annotation", "checkpoint"}


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
            confidence=0.99, channels=[REF], evaluator_ref=f"eval:{REF}")
        out.append(ledger.append(exp))
    return out


def _learn(engine, ledger, capture, state, region, best, second):
    best_ev = _emit(capture, ledger, region, best, 1.0, 8)
    second_ev = _emit(capture, ledger, region, second, 0.5, 4)
    tx, ns = engine.commit(state, region, best_ev[:5] + second_ev[:2])
    assert tx.status == "committed", tx.validation
    return ns


def _evidence_ids(ledger) -> set:
    """Every identifier of a §3.2 evidence record in the ledger — the only subjects
    a durable-tier fact may legitimately carry. Built from all four kinds, so a
    future gate_decision/checkpoint mirror is not falsely flagged."""
    ids = set()
    for line in ledger.backend.read_all():
        entry = json.loads(line)
        assert entry["kind"] in EVIDENCE_KINDS, entry["kind"]   # the ledger itself is evidence-only
        p = entry["payload"]
        for key in ("exp_id", "tx_id", "checkpoint_id", "id"):
            if isinstance(p.get(key), str):
                ids.add(p[key])
    return ids


def test_durable_tier_holds_evidence_only(tmp_path):
    priv, _ = generate_keypair()
    gmp = GMPInMemoryBackend()                      # the durable tier
    backend = CompositeBackend(LocalLedgerBackend(tmp_path / "l.jsonl"),
                               GMPFactBridge(gmp))  # experiences fan out to GMP
    ledger = ExperienceLedger(backend, priv, checkpoint_every=16)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    engine = LearningEngine(ledger, AdmissionGate())
    state = CognitiveState.genesis(REGIONS, TOOLS)

    # -- drive every CSO component through a real commit --------------------
    # policies + strategies: three regions learn a shared ordering
    for region in REGIONS:
        state = _learn(engine, ledger, capture, state, region, "code_runner", "db_query")
    # semantic_memory: an insert, then a superseding insert
    mem_ev = [e for e in ledger.evaluated()
              if e.action.policy_region == REGIONS[0]
              and e.action.steps[-1].tool == "code_runner"]
    cand = MemoryCandidate(op="insert", type="consolidation",
                           content=claim_content("code_runner", REGIONS[0], SENSE_RELIABLE),
                           sources=[e.exp_id for e in mem_ev], confidence=0.9, region=REGIONS[0])
    mtx, state = engine.commit_memory(state, cand, mem_ev)
    assert mtx.status == "committed"
    sup = MemoryCandidate(op="insert", type="consolidation",
                          content=claim_content("code_runner", REGIONS[0], SENSE_RELIABLE) + " v2",
                          sources=[e.exp_id for e in mem_ev], confidence=0.95,
                          region=REGIONS[0], supersedes_mem_id=mtx.delta["mem_id"])
    _, state = engine.commit_memory(state, sup, mem_ev)
    # strategies: induce, commit, boot a new region
    scand = StrategyInducer(ledger, k=3).propose(state)[0]
    sev = [e for e in ledger if e.exp_id in set(scand.sources)]
    stx, state = engine.commit_strategy(state, scand, sev)
    assert stx.status == "committed"
    _, state = engine.commit_strategy_boot(state, "new-region", stx.delta["strategy_id"])
    # evaluation_history: a committed recalibrate
    cal = CalibrationLoop(reference_channel=REF)
    for i in range(20):
        cal.observe("agent-self-report", agreed=(i % 2 == 0), exp_id=f"e{i}")
    rtx, state = engine.recalibrate(state, cal)
    assert rtx.status == "committed"

    # -- the CSO identifiers that MUST NOT appear as durable-tier subjects ---
    cso_ids = set(state.semantic_memory)                          # MemoryItem ids
    cso_ids |= set(state.policies)                               # policy regions
    cso_ids |= set(state.strategies)                            # strategy ids
    cso_ids |= set((state.evaluation_history or {}).get("channels", {}))  # channel keys

    gmp_facts = list(gmp.audit())
    evidence_ids = _evidence_ids(ledger)

    # positive: experiences DID reach the durable tier (the wiring is real, so the
    # guard is not vacuous)
    assert any(f.predicate == "ccr:outcome" for f in gmp_facts)

    # (a) every durable-tier fact derives from a §3.2 evidence record
    for f in gmp_facts:
        assert f.subject in evidence_ids, (f.predicate, f.subject)
    # (b) no fact's subject is a committed CSO identifier
    assert cso_ids and not (cso_ids & {f.subject for f in gmp_facts})
    # (c) no belief-mirror predicate survives
    assert not any(f.predicate.startswith("ccr:mem/") for f in gmp_facts)
