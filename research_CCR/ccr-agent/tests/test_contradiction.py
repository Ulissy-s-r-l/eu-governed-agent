"""Contradiction detection over semantic_memory (doc 02 §3.1 — `contested`).

Scoped, per the BUILD B report, to the ONLY fact shape the Consolidator emits: the
structured claim `tool:<T> <sense> in region:<R>`. A contradiction is two ACTIVE
items, same (region, tool), opposite sense. The detector refuses anything it
cannot parse — a general detector that guessed would manufacture contested pairs,
and a contested state people learn to ignore is worse than none.

Invariants under test:
  - detection MARKS both members contested; neither drives behaviour;
  - detection never auto-resolves (never demotes the lower-confidence item);
  - a two-genuinely-reliable-tools case is NOT flagged (the key false positive);
  - resolution (a supersede) clears both marks — contested is not a one-way ratchet;
  - re-confirmation is support, not resolution — a confirm does not un-contest.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.state import CognitiveState, MemoryItem
from ccr.contradiction import (
    claim_content, parse_claim, find_contradictions, detect_and_mark,
    reconcile_contested, behavioural_memory, SENSE_RELIABLE, SENSE_UNRELIABLE,
)
from ccr.ledger import ExperienceLedger, LocalLedgerBackend, generate_keypair
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.transaction import LearningEngine, AdmissionGate
from ccr.consolidation import MemoryCandidate
from ccr.experience import EvaluationBlock

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REGION = "data-processing"


def _item(mid, tool, sense, conf, status="active"):
    return MemoryItem(id=mid, type="consolidation",
                      content=claim_content(tool, REGION, sense),
                      confidence=conf, sources=["exp:1"], status=status,
                      created_tx="tx:x", last_confirmed_tx="tx:x")


def _state_with(*items) -> CognitiveState:
    st = CognitiveState.genesis(REGIONS, TOOLS)
    st.semantic_memory = {it.id: it for it in items}
    return st


# ---- parser: refuses what it cannot decide --------------------------------

def test_parser_reads_structured_claim_and_refuses_free_text():
    assert parse_claim(claim_content("db_query", REGION, SENSE_RELIABLE)) == \
        (REGION, "db_query", SENSE_RELIABLE)
    assert parse_claim("db_query is pretty good here") is None      # free text: refused
    assert parse_claim("tool:db_query reliable in region:data-processing (v2)") is None
    assert parse_claim(None) is None


# ---- detection: mark both; no false positives -----------------------------

def test_opposite_sense_same_key_marks_both_contested():
    a = _item("mem:a", "db_query", SENSE_RELIABLE, 0.9)
    b = _item("mem:b", "db_query", SENSE_UNRELIABLE, 0.3)
    st = _state_with(a, b)
    pairs = detect_and_mark(st)
    assert pairs == [("mem:a", "mem:b")]
    assert st.semantic_memory["mem:a"].status == "contested"
    assert st.semantic_memory["mem:b"].status == "contested"


def test_two_reliable_tools_same_region_is_not_flagged():
    """The key false positive a general detector would produce: a region can have
    more than one reliable tool. Both true — never contested."""
    a = _item("mem:a", "db_query", SENSE_RELIABLE, 0.9)
    b = _item("mem:b", "search_api", SENSE_RELIABLE, 0.9)
    st = _state_with(a, b)
    assert find_contradictions(st.semantic_memory) == []
    assert detect_and_mark(st) == []
    assert all(m.status == "active" for m in st.semantic_memory.values())


def test_unparseable_items_are_never_parties():
    a = MemoryItem(id="mem:a", type="fact", content="db_query is unreliable-ish",
                   confidence=0.3, sources=["exp:1"], status="active")
    b = _item("mem:b", "db_query", SENSE_RELIABLE, 0.9)
    st = _state_with(a, b)
    assert detect_and_mark(st) == []


def test_deprecated_predecessor_is_not_a_party():
    """A superseded predecessor beside its successor is resolved history, not a
    contradiction."""
    old = _item("mem:old", "db_query", SENSE_UNRELIABLE, 0.3, status="deprecated")
    new = _item("mem:new", "db_query", SENSE_RELIABLE, 0.9)
    st = _state_with(old, new)
    assert detect_and_mark(st) == []
    assert st.semantic_memory["mem:new"].status == "active"


# ---- non-behavioural read + no auto-resolution ----------------------------

def test_contested_items_are_not_behavioural():
    a = _item("mem:a", "db_query", SENSE_RELIABLE, 0.9)
    b = _item("mem:b", "db_query", SENSE_UNRELIABLE, 0.3)
    st = _state_with(a, b)
    detect_and_mark(st)
    # present in state, but excluded from the behavioural read view (like below-floor)
    assert set(st.semantic_memory) == {"mem:a", "mem:b"}
    assert behavioural_memory(st) == {}


def test_detection_never_demotes_the_lower_confidence_item():
    """MUST NOT auto-resolve by confidence (doc 02 §3.1): the detector marks, it
    does not pick a winner. Confidences are untouched; neither side is deprecated."""
    a = _item("mem:a", "db_query", SENSE_RELIABLE, 0.95)     # well-attested
    b = _item("mem:b", "db_query", SENSE_UNRELIABLE, 0.20)   # poorly-attested
    st = _state_with(a, b)
    detect_and_mark(st)
    assert st.semantic_memory["mem:a"].confidence == 0.95
    assert st.semantic_memory["mem:b"].confidence == 0.20
    assert st.semantic_memory["mem:a"].status == "contested"     # NOT deprecated
    assert st.semantic_memory["mem:b"].status == "contested"     # NOT demoted away


# ---- resolution clears both marks (not a one-way ratchet) -----------------

def test_reconcile_restores_survivor_when_partner_deprecated():
    a = _item("mem:a", "db_query", SENSE_RELIABLE, 0.9, status="contested")
    b = _item("mem:b", "db_query", SENSE_UNRELIABLE, 0.3, status="contested")
    st = _state_with(a, b)
    # a supersede deprecates b; a's only conflicting partner is now gone.
    st.semantic_memory["mem:b"].status = "deprecated"
    restored = reconcile_contested(st)
    assert restored == ["mem:a"]
    assert st.semantic_memory["mem:a"].status == "active"


def test_reconcile_keeps_contested_while_a_live_partner_remains():
    a = _item("mem:a", "db_query", SENSE_RELIABLE, 0.9, status="contested")
    b = _item("mem:b", "db_query", SENSE_UNRELIABLE, 0.3, status="contested")
    st = _state_with(a, b)
    assert reconcile_contested(st) == []                     # neither freed
    assert st.semantic_memory["mem:a"].status == "contested"
    assert st.semantic_memory["mem:b"].status == "contested"


# ---- end-to-end through commit_memory -------------------------------------

@pytest.fixture
def rig(tmp_path):
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    engine = LearningEngine(ledger, AdmissionGate())
    state = CognitiveState.genesis(REGIONS, TOOLS)
    return ledger, capture, engine, state


def _evidence(capture, tag, score, n=4):
    """n experiences whose authoritative-reference evaluation has the given score
    at high confidence — a confident reference reports low scores for a failing
    tool, so a negative claim can still clear the gate."""
    out = []
    for k in range(n):
        exp = capture.emit(state_summary="s", goal="g", tool="db_query", args={},
                           result={}, outcome_observed="x", signals={},
                           policy_region=REGION)
        exp.evaluation = EvaluationBlock(verdict="v", score=score, confidence=0.99,
                                         channels=["simulator-ground-truth"],
                                         evaluator_ref="eval:ref")
        exp.exp_id = f"exp:{tag}:{k}"
        out.append(exp)
    return out


def _cand(sense, evidence, supersedes=None):
    return MemoryCandidate(op="insert", type="consolidation",
                           content=claim_content("db_query", REGION, sense),
                           sources=[e.exp_id for e in evidence], confidence=0.9,
                           region=REGION, supersedes_mem_id=supersedes)


def test_commit_of_conflicting_claim_marks_both_contested(rig):
    ledger, capture, engine, state = rig
    ev_pos = _evidence(capture, "pos", score=0.95)
    tx1, s1 = engine.commit_memory(state, _cand(SENSE_RELIABLE, ev_pos), ev_pos)
    assert tx1.status == "committed"
    rid = tx1.delta["mem_id"]

    ev_neg = _evidence(capture, "neg", score=0.30)                # low score, high confidence
    tx2, s2 = engine.commit_memory(s1, _cand(SENSE_UNRELIABLE, ev_neg), ev_neg)
    assert tx2.status == "committed"
    uid = tx2.delta["mem_id"]

    assert s2.semantic_memory[rid].status == "contested"
    assert s2.semantic_memory[uid].status == "contested"
    assert tx2.validation["contested_marked"] == [(rid, uid)]
    assert behavioural_memory(s2) == {}                          # neither is behavioural


def test_supersede_resolves_and_restores_the_survivor(rig):
    ledger, capture, engine, state = rig
    ev_pos = _evidence(capture, "pos", score=0.95)
    tx1, s1 = engine.commit_memory(state, _cand(SENSE_RELIABLE, ev_pos), ev_pos)
    rid = tx1.delta["mem_id"]
    ev_neg = _evidence(capture, "neg", score=0.30)
    tx2, s2 = engine.commit_memory(s1, _cand(SENSE_UNRELIABLE, ev_neg), ev_neg)
    uid = tx2.delta["mem_id"]
    assert s2.semantic_memory[rid].status == "contested"

    # a later transaction supersedes the unreliable claim → the reliable one returns
    ev_fix = _evidence(capture, "fix", score=0.95)
    tx3, s3 = engine.commit_memory(s2, _cand(SENSE_RELIABLE, ev_fix, supersedes=uid), ev_fix)
    assert tx3.status == "committed"
    assert s3.semantic_memory[uid].status == "deprecated"       # superseded away
    assert s3.semantic_memory[rid].status == "active"          # survivor restored
    assert rid in tx3.validation["contested_restored"]


def test_confirm_is_support_not_resolution(rig):
    """Re-confirming one side of a contested pair — even raising its confidence
    above the other's — MUST NOT un-contest it (doc 02 §3.1)."""
    ledger, capture, engine, state = rig
    # seed a live contested pair directly in state
    a = _item("mem:a", "db_query", SENSE_RELIABLE, 0.5, status="contested")
    b = _item("mem:b", "db_query", SENSE_UNRELIABLE, 0.5, status="contested")
    state.semantic_memory = {"mem:a": a, "mem:b": b}

    ev = _evidence(capture, "conf", score=0.95)
    confirm = MemoryCandidate(op="confirm", type="consolidation",
                              content=claim_content("db_query", REGION, SENSE_RELIABLE),
                              sources=[e.exp_id for e in ev], confidence=0.99,
                              region=REGION, mem_id="mem:a")
    tx, s2 = engine.commit_memory(state, confirm, ev)
    assert tx.status == "committed"
    assert s2.semantic_memory["mem:a"].confidence == 0.99       # support: confidence refreshed
    assert s2.semantic_memory["mem:a"].status == "contested"   # but still contested
    assert s2.semantic_memory["mem:b"].status == "contested"   # partner untouched
