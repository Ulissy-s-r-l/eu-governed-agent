"""The durable tier holds evidence, not CSO content (doc 03 §3.4 / ADR-0010).

The durable tier mirrors the §3.2 EVIDENCE kinds — experience, gate_decision,
checkpoint (annotation has no writer yet) — and NO CSO content. Two things are
tested here, and they pull in opposite directions on purpose:

  - the GUARD: no component mirrors itself (no fact subject is a CSO id, no
    ccr:mem/* predicate) — the check item C lacked;
  - the JOIN: the §3.2 three-way audit (experience ↔ gate_decision ↔ policy
    provenance) now resolves ENTIRELY on the durable tier, for committed AND
    rejected transactions — the join the pre-mirror code could satisfy only
    locally.

Mirroring MORE evidence (gate_decision, checkpoint) is exactly ADR-0010's rule;
mirroring ANY belief is exactly what it forbids. Both are asserted below.
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
# against the whole list — NOT "experience only" — so gate_decision/checkpoint facts
# pass while any CSO-content mirror still fails.
EVIDENCE_KINDS = {"experience", "gate_decision", "annotation", "checkpoint"}

_TAG = [0]


def _emit(capture, ledger, region, tool, score, n, *, channel=REF, conf=0.99):
    out = []
    for _ in range(n):
        _TAG[0] += 1
        exp = capture.emit(state_summary="s", goal="g", tool=tool,
                           args={"region": region, "u": _TAG[0]}, result={},
                           outcome_observed="x", signals={}, policy_region=region)
        exp.evaluation = EvaluationBlock(
            verdict="success" if score >= 0.5 else "failure", score=score,
            confidence=conf, channels=[channel], evaluator_ref=f"eval:{channel}")
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
    gate_decision/checkpoint fact is not falsely flagged."""
    ids = set()
    for line in ledger.backend.read_all():
        entry = json.loads(line)
        assert entry["kind"] in EVIDENCE_KINDS, entry["kind"]   # the ledger is evidence-only
        p = entry["payload"]
        for key in ("exp_id", "tx_id", "checkpoint_id", "id"):
            if isinstance(p.get(key), str):
                ids.add(p[key])
    return ids


@pytest.fixture
def built(tmp_path):
    """Drive every CSO component through a real commit against a GMP-wired engine,
    plus a poison rejection, and return the durable tier + the artifacts the join
    and guard assertions need."""
    priv, _ = generate_keypair()
    gmp = GMPInMemoryBackend()
    backend = CompositeBackend(LocalLedgerBackend(tmp_path / "l.jsonl"),
                               GMPFactBridge(gmp))
    ledger = ExperienceLedger(backend, priv, checkpoint_every=16)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    engine = LearningEngine(ledger, AdmissionGate())
    state = CognitiveState.genesis(REGIONS, TOOLS)

    # policies + strategies: three regions learn a shared ordering
    for region in REGIONS:
        state = _learn(engine, ledger, capture, state, region, "code_runner", "db_query")
    # semantic_memory: insert then superseding insert
    mem_ev = [e for e in ledger.evaluated()
              if e.action.policy_region == REGIONS[0]
              and e.action.steps[-1].tool == "code_runner"]
    cand = MemoryCandidate(op="insert", type="consolidation",
                           content=claim_content("code_runner", REGIONS[0], SENSE_RELIABLE),
                           sources=[e.exp_id for e in mem_ev], confidence=0.9, region=REGIONS[0])
    mtx, state = engine.commit_memory(state, cand, mem_ev)
    sup = MemoryCandidate(op="insert", type="consolidation",
                          content=claim_content("code_runner", REGIONS[0], SENSE_RELIABLE) + " v2",
                          sources=[e.exp_id for e in mem_ev], confidence=0.95,
                          region=REGIONS[0], supersedes_mem_id=mtx.delta["mem_id"])
    _, state = engine.commit_memory(state, sup, mem_ev)
    # strategies: induce, commit, boot
    scand = StrategyInducer(ledger, k=3).propose(state)[0]
    sev = [e for e in ledger if e.exp_id in set(scand.sources)]
    stx, state = engine.commit_strategy(state, scand, sev)
    _, state = engine.commit_strategy_boot(state, "new-region", stx.delta["strategy_id"])
    # evaluation_history: a committed recalibrate
    cal = CalibrationLoop(reference_channel=REF)
    for i in range(20):
        cal.observe("agent-self-report", agreed=(i % 2 == 0), exp_id=f"e{i}")
    _, state = engine.recalibrate(state, cal)
    # a REJECTED tx that still cites evidence: forged low-trust self-reports
    forged = _emit(capture, ledger, REGIONS[1], "web_fetch", 1.0, 4,
                   channel="agent-self-report", conf=0.3)
    poison = MemoryCandidate(op="insert", type="consolidation",
                             content=claim_content("web_fetch", REGIONS[1], SENSE_RELIABLE),
                             sources=[e.exp_id for e in forged], confidence=0.9, region=REGIONS[1])
    rtx, state = engine.commit_memory(state, poison, forged)
    assert rtx.status == "rejected"

    return {
        "gmp": gmp, "ledger": ledger, "state": state,
        "region": REGIONS[0], "reject_tx": rtx.tx_id,
        "strategy_tx": stx.tx_id, "strategy_id": stx.delta["strategy_id"],
    }


# ---- the guard: evidence in, CSO content NEVER ----------------------------

def test_durable_tier_holds_evidence_only(built):
    gmp, ledger, state = built["gmp"], built["ledger"], built["state"]
    gmp_facts = list(gmp.audit())
    evidence_ids = _evidence_ids(ledger)

    # positive: experiences, gate_decisions AND checkpoints all reached the tier
    preds = {f.predicate for f in gmp_facts}
    assert "ccr:outcome" in preds                       # experience evidence
    assert "ccr:gate_decision" in preds                 # the change-log (incl. refusals)
    assert "ccr:checkpoint" in preds                    # transparency anchors

    cso_ids = set(state.semantic_memory) | set(state.policies) | set(state.strategies)
    cso_ids |= set((state.evaluation_history or {}).get("channels", {}))

    # (a) every durable-tier fact derives from a §3.2 evidence record
    for f in gmp_facts:
        assert f.subject in evidence_ids, (f.predicate, f.subject)
    # (b) no fact's subject is a committed CSO identifier
    assert cso_ids and not (cso_ids & {f.subject for f in gmp_facts})
    # (c) no belief-mirror predicate
    assert not any(f.predicate.startswith("ccr:mem/") for f in gmp_facts)


def test_gate_decision_object_carries_delta_but_never_as_subject(built):
    """Subject-line probe: a gate_decision object may CONTAIN a strategy ordering
    (evidence about the change), but no fact's SUBJECT is the strategy id."""
    gmp, strat_tx, strat_id = built["gmp"], built["strategy_tx"], built["strategy_id"]
    gd = gmp.retrieve(predicate="ccr:gate_decision", subject=strat_tx)
    assert gd
    assert "code_runner" in json.dumps(json.loads(gd[0].obj))   # ordering is in the OBJECT
    # ...yet the strategy id appears as NO fact's subject, anywhere in the store
    assert gmp.retrieve(subject=strat_id) == []
    assert not any(f.subject == strat_id for f in gmp.audit())


# ---- the join: §3.2 three-way audit, resolved on the durable tier ---------

def _resolve_join(gmp, tx_id):
    """experience ↔ gate_decision ↔ cited evidence — ENTIRELY from the durable tier,
    no local ledger reads. Returns the audit object; raises if any hop is empty."""
    gd = gmp.retrieve(predicate="ccr:gate_decision", subject=tx_id)
    assert gd, f"no gate_decision fact for {tx_id} on the durable tier"
    on = gmp.retrieve(predicate="ccr:gate_decision/on", subject=tx_id)
    assert on, f"no cited-evidence link for {tx_id}"
    cited = json.loads(on[0].obj)
    assert cited, "cited-evidence list is empty"
    for exp_id in cited:
        assert gmp.retrieve(predicate="ccr:outcome", subject=exp_id), \
            f"cited experience {exp_id} not on the durable tier"
    return json.loads(gd[0].obj)


def test_gate_decision_join_resolves_on_durable_tier(built):
    """policy region → created_tx → gate_decision fact → cited exp_ids → experiences,
    all from GMP. This is the join the pre-mirror code could not satisfy."""
    gmp, state, region = built["gmp"], built["state"], built["region"]
    created_tx = state.policies[region].updated_tx      # the only CSO read: the pointer
    audit = _resolve_join(gmp, created_tx)
    assert audit["status"] == "committed"
    assert audit["new_commitment"]                      # a committed tx anchors a state


def test_gate_decision_join_resolves_for_a_rejected_tx(built):
    """A supervisor asking what the system DECLINED to learn, and on what evidence,
    needs the same join — with status rejected and no new_commitment to anchor on."""
    gmp, reject_tx = built["gmp"], built["reject_tx"]
    audit = _resolve_join(gmp, reject_tx)
    assert audit["status"] == "rejected"
    assert audit["new_commitment"] is None              # the join does not depend on a commit
