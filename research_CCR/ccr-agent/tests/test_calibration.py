"""Per-channel reliability calibration (item 5, doc 02 §3.8, doc 07 §2.2a) and
its commit path, the recalibrate transaction (doc 04 §5B).

A channel that agrees with the reference rises; a garbage/self-consensus channel
never recovers (the permanent negative control); an unobserved channel is
undefined (None), not a default; there is no calibration without a reference
channel.

The gate's trust term reads reliability from COMMITTED state only (doc 04 §5B).
A live loop advises; its numbers become behavioural ONLY through a committed
`recalibrate` tx. The tests below exercise the committed path — NOT a live loop
handed to the gate, which is the wiring §5B forbids.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.calibration import CalibrationLoop, recompute_reliability, reliability_from_state
from ccr.transaction import AdmissionGate, LearningEngine
from ccr.ledger import ExperienceLedger, LocalLedgerBackend, generate_keypair
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.experience import EvaluationBlock
from ccr.state import CognitiveState
from ccr.consolidation import MemoryCandidate

REF = "simulator-ground-truth"
TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]


# ---- the pure loop -------------------------------------------------------

def test_truthful_channel_reliability_rises():
    cal = CalibrationLoop(reference_channel=REF)
    for _ in range(50):
        cal.observe("unit-tests", agreed=True)
    assert cal.reliability("unit-tests") >= 0.9
    assert cal.reliability(REF) == 0.99                    # reference authoritative


def test_garbage_channel_never_recovers_reliability():
    """PERMANENT NEGATIVE CONTROL: a channel whose verdicts are ~random relative
    to the reference must stay near chance and never rise to trustworthy."""
    cal = CalibrationLoop(reference_channel=REF)
    for i in range(200):
        cal.observe("garbage", agreed=(i % 2 == 0))        # ~50% agreement
    assert cal.reliability("garbage") < 0.6                # pinned near chance
    assert cal.reliability("garbage") < cal.reliability(REF)


def test_unobserved_channel_is_undefined_not_default():
    cal = CalibrationLoop(reference_channel=REF)
    assert cal.reliability("never-seen") is None           # doc 02 §3.8: not a default


def test_no_calibration_without_a_reference():
    with pytest.raises(ValueError):
        CalibrationLoop(reference_channel="")              # doc 07 §2.2a


def test_window_recomputes_reliability():
    """§5B invariant 1's engine: reliability re-derives from the recorded window."""
    cal = CalibrationLoop(reference_channel=REF)
    for i in range(40):
        cal.observe("agent-self-report", agreed=(i % 4 == 0), exp_id=f"exp:{i}")
    w = cal.window("agent-self-report")
    assert w["agreements"] == 10 and w["disagreements"] == 30
    assert len(w["exp_ids"]) == 40                         # window keeps exp_ids, not just counts
    assert abs(recompute_reliability(w) - cal.reliability("agent-self-report")) < 1e-12


# ---- fixtures for the committed path --------------------------------------

def _rig(tmp_path):
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    engine = LearningEngine(ledger, AdmissionGate())
    state = CognitiveState.genesis(REGIONS, TOOLS)
    return ledger, capture, engine, state


def _forged_self_report(capture, n=4):
    """n forged 'successes' on the low-trust agent-self-report channel, each
    claiming confidence 0.99 (the account lies)."""
    evidence = []
    for k in range(n):
        exp = capture.emit(state_summary="s", goal="g", tool="db_query", args={},
                           result={"forged": True}, outcome_observed="succeeded",
                           signals={"success": True}, policy_region="data-processing")
        exp.evaluation = EvaluationBlock(verdict="success", score=1.0, confidence=0.99,
                                         channels=["agent-self-report"],
                                         evaluator_ref="eval:agent-self-report")
        exp.exp_id = f"exp:self:{k}"
        evidence.append(exp)
    return evidence


def _self_report_loop():
    cal = CalibrationLoop(reference_channel=REF)
    for i in range(40):                                    # agrees ~25% with the reference
        cal.observe("agent-self-report", agreed=(i % 4 == 0), exp_id=f"exp:{i}")
    return cal


def _mem_candidate(evidence):
    return MemoryCandidate(op="insert", type="consolidation",
                           content="tool:db_query reliable in region:data-processing",
                           sources=[e.exp_id for e in evidence],
                           confidence=0.9, region="data-processing")


# ---- §5B: the committed recalibrate changes the gate ----------------------

def test_recalibrate_commit_changes_the_gate_trust_term(tmp_path):
    """The forbidden path made honest: a forged 0.99 self-report admits while the
    channel is uncalibrated; after a committed `recalibrate` prices the channel at
    its OBSERVED ~0.25, the SAME evidence is rejected at the gate. Trust moved
    through committed state — not through a loop handed to the gate."""
    ledger, capture, engine, state = _rig(tmp_path)
    evidence = _forged_self_report(capture)

    # BEFORE: evaluation_history empty ⇒ gate uses self-report ⇒ admits.
    tx_before, s_before = engine.commit_memory(state, _mem_candidate(evidence), evidence)
    assert tx_before.status == "committed"
    assert tx_before.admission["trust"] > 0.9             # took the forged self-report

    # RECALIBRATE: commit the observed ~0.25 for agent-self-report.
    rc, s_cal = engine.recalibrate(s_before, _self_report_loop())
    assert rc.status == "committed" and rc.tx_type == "recalibrate"
    assert rc.admission["skipped"] is True
    assert "circularity" in rc.admission["reason"]        # §5B's own bypass reason

    # AFTER: same evidence, committed reliability now steers the trust term ⇒ reject.
    tx_after, s_after = engine.commit_memory(s_cal, _mem_candidate(evidence), evidence)
    assert tx_after.status == "rejected"
    assert tx_after.admission["trust"] < 0.4              # took the observed ~0.25
    assert tx_after.admission["V"] < tx_before.admission["V"]


def test_uncommitted_loop_does_not_steer_the_gate(tmp_path):
    """A live loop that has observed ~0.25 does NOT change the gate until a
    recalibrate commits. Merely constructing/holding the loop is inert — the
    engine reads committed state, never a loop."""
    ledger, capture, engine, state = _rig(tmp_path)
    evidence = _forged_self_report(capture)
    _live = _self_report_loop()                            # exists, advises, never committed
    tx, _ = engine.commit_memory(state, _mem_candidate(evidence), evidence)
    assert tx.status == "committed"                        # self-report still trusted
    assert tx.admission["trust"] > 0.9
    # committed state is genuinely empty of any reliability the gate could read
    assert reliability_from_state(state.evaluation_history)("agent-self-report") is None


# ---- §5B: invariant re-check ----------------------------------------------

class _StubLoop:
    """A loop whose to_state() we control, to submit tampered reliabilities."""
    def __init__(self, state_dict):
        self._s = state_dict
        self.reference = state_dict["reference"]

    def to_state(self):
        return self._s


def test_invariant_rejects_reliability_that_does_not_recompute(tmp_path):
    """§5B invariant 1: a submitted reliability that does not recompute from its
    recorded window is rejected — the loop cannot smuggle a number the window
    does not support."""
    ledger, capture, engine, state = _rig(tmp_path)
    honest = _self_report_loop().to_state()
    honest["channels"]["agent-self-report"]["reliability"] = 0.95   # tamper: window says ~0.26
    rc, s2 = engine.recalibrate(state, _StubLoop(honest))
    assert rc.status == "rejected"
    assert any("recomputed" in v for v in rc.validation["violations"])
    assert s2 is state                                     # state unchanged on reject


def test_invariant_rejects_channel_outranking_reference(tmp_path):
    """§5B invariant 3: no calibrated channel may outrank the reference."""
    ledger, capture, engine, state = _rig(tmp_path)
    tampered = _self_report_loop().to_state()
    ch = tampered["channels"]["agent-self-report"]
    # make it recompute-consistent AND above the reference by forging the window too
    ch["window"] = {"agreements": 10_000, "disagreements": 0, "exp_ids": [], "prior": [1.0, 1.0]}
    ch["reliability"] = recompute_reliability(ch["window"])          # ~0.9999 > 0.99
    rc, _ = engine.recalibrate(state, _StubLoop(tampered))
    assert rc.status == "rejected"
    assert any("outranks reference" in v for v in rc.validation["violations"])


# ---- §5B: reference persistence & no silent re-anchoring -------------------

def test_first_recalibrate_designates_reference_then_it_is_immutable(tmp_path):
    ledger, capture, engine, state = _rig(tmp_path)
    rc1, s1 = engine.recalibrate(state, _self_report_loop())
    assert rc1.status == "committed"
    assert s1.evaluation_history["reference"] == REF
    assert rc1.validation["reference_designated"] is True

    # a second recalibrate with a DIFFERENT reference must be rejected.
    other = CalibrationLoop(reference_channel="some-other-oracle")
    for i in range(20):
        other.observe("agent-self-report", agreed=(i % 4 == 0), exp_id=f"e:{i}")
    rc2, s2 = engine.recalibrate(s1, other)
    assert rc2.status == "rejected"
    assert "re-anchoring forbidden" in rc2.validation["reason"]
    assert s2 is s1                                        # committed reference stands


# ---- §5B: forward-only, revertable ----------------------------------------

def test_recalibrate_is_revertable(tmp_path):
    ledger, capture, engine, state = _rig(tmp_path)
    rc, s_cal = engine.recalibrate(state, _self_report_loop())
    assert s_cal.evaluation_history["channels"]["agent-self-report"]["reliability"] < 0.4

    tx_rev, s_rev = engine.revert(s_cal, target=state, incident_evidence="rollback calibration")
    assert tx_rev.tx_type == "revert"
    assert s_rev.evaluation_history == {}                  # prior (empty) calibration restored
    assert s_rev.parent_commitment == s_cal.commitment    # forward-only: parented to current
