"""Per-channel reliability calibration (item 5, doc 02 §3.8, doc 07 §2.2a).

A channel that agrees with the reference rises; a garbage/self-consensus channel
never recovers (the permanent negative control); an unobserved channel is
undefined (None), not a default; there is no calibration without a reference
channel; and the gate's trust term uses observed reliability over self-report.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.calibration import CalibrationLoop
from ccr.transaction import AdmissionGate
from ccr.ledger import ExperienceLedger, LocalLedgerBackend, generate_keypair
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.experience import EvaluationBlock

REF = "simulator-ground-truth"


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


def test_gate_trust_uses_observed_reliability_over_self_report(tmp_path):
    """A forged self-report claiming confidence 0.99 must be trusted at its
    OBSERVED reliability, not its self-reported one (trust the channel, not the account)."""
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())

    cal = CalibrationLoop(reference_channel=REF)
    for i in range(40):                                    # 'agent-self-report' agrees ~25%
        cal.observe("agent-self-report", agreed=(i % 4 == 0))

    evidence = []
    for k in range(4):
        exp = capture.emit(state_summary="s", goal="g", tool="db_query", args={},
                           result={"forged": True}, outcome_observed="succeeded",
                           signals={"success": True}, policy_region="data-processing")
        exp.evaluation = EvaluationBlock(verdict="success", score=1.0, confidence=0.99,
                                         channels=["agent-self-report"],
                                         evaluator_ref="eval:agent-self-report")
        exp.exp_id = f"exp:self:{k}"
        evidence.append(exp)

    gate = AdmissionGate()
    self_report = gate.evaluate_evidence(evidence)                       # trusts 0.99
    calibrated = gate.evaluate_evidence(evidence, reliability_of=cal.reliability)
    assert self_report["trust"] > 0.9                     # took the forged self-report
    assert calibrated["trust"] < 0.4                      # took the observed ~0.25
    assert calibrated["V"] < self_report["V"]             # and it lowers the score
