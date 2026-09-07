"""cgr.cosign.v1 co-signed approval on the learning transaction (item 3).

HighRiskUpdate ⇒ RequiredApproval, enforced via the §5.1 predicate
(risk == "high"). Covers: a high-risk tx without an approver signature is
rejected with the reason in the ledger; the same tx with a valid signature
commits and verifies; stripping the signature from a committed tx breaks
verification; a signature over a DIFFERENT content_digest is rejected; and
low-risk still commits without approval (backward compatible).
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.ledger import ExperienceLedger, LocalLedgerBackend, generate_keypair
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.simulator import ToolSelectionSimulator
from ccr.state import CognitiveState
from ccr.transaction import LearningEngine, AdmissionGate
from ccr import cosign
from ccr.cosign import LocalApprover
from ccr.experience import utcnow, new_id

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REGION = "data-processing"


@pytest.fixture
def rig(tmp_path):
    priv, pub = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv,
                              checkpoint_every=32)
    capture = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    engine = LearningEngine(ledger, AdmissionGate(threshold=0.55, min_evidence=3))
    sim = ToolSelectionSimulator(TOOLS, REGIONS, seed=7)
    state = CognitiveState.genesis(REGIONS, TOOLS)
    for ep in range(24):
        tool = TOOLS[ep % len(TOOLS)]
        res = sim.run_episode(tool, REGION, ep)
        capture.capture(state_summary="s", goal="g", tool=tool,
                        args={"region": REGION}, result=res,
                        outcome_observed=str(res["success"]), signals=res,
                        policy_region=REGION)
    return ledger, engine, state


def _train(ledger):
    ev = [e for e in ledger.evaluated() if e.action.policy_region == REGION]
    return ev[: len(ev) // 2]                       # held-out split (doc 04 §2.2)


def _gate_records(ledger):
    return [json.loads(l) for l in ledger.backend.read_all()
            if json.loads(l)["kind"] == "gate_decision"]


def test_highrisk_without_approver_is_rejected(rig):
    ledger, engine, state = rig
    tx, st = engine.commit(state, REGION, _train(ledger), risk="high")   # no approver
    assert tx.status == "rejected"
    assert tx.validation["approval"]["required"] is True
    assert "approver signature" in tx.validation["approval"]["reason"]
    assert st.version == state.version                                    # unchanged
    assert _gate_records(ledger)[-1]["payload"]["status"] == "rejected"   # in the ledger


def test_highrisk_with_valid_signature_commits_and_verifies(rig):
    ledger, engine, state = rig
    priv, _ = generate_keypair()
    approver = LocalApprover("mlro:jane", priv)
    tx, st = engine.commit(state, REGION, _train(ledger), risk="high", approver=approver)
    assert tx.status == "committed"
    assert st.version == state.version + 1
    assert tx.schema == "cgr.cosign.v1" and tx.approval_mode == "free"
    assert tx.approver_signature and tx.system_signature
    assert tx.validation["approval"]["verdict"] == "ok"
    ok, reason = engine.verify_transaction(asdict(tx))
    assert ok, reason


def test_stripping_the_approval_breaks_verification(rig):
    ledger, engine, state = rig
    priv, _ = generate_keypair()
    tx, _ = engine.commit(state, REGION, _train(ledger), risk="high",
                          approver=LocalApprover("mlro:jane", priv))
    rec = asdict(tx)
    assert engine.verify_transaction(rec)[0]                # valid as committed
    rec["approver_signature"] = None                        # strip it
    ok, reason = engine.verify_transaction(rec)
    assert not ok and "system signature" in reason          # outer sig now fails


def test_signature_over_different_content_digest_is_rejected(rig):
    ledger, engine, state = rig
    priv, _ = generate_keypair()
    key_id = cosign.key_id_for(priv.public_key())

    def bad_approver(cd: str):
        # sign a VALID assertion, but over a different content_digest
        wrong = cosign.build_assertion("b2-256:" + "00" * 32, "mlro:evil", key_id,
                                       "approve", utcnow(), new_id("nonce"))
        return wrong, cosign.sign_assertion(wrong, priv)

    tx, st = engine.commit(state, REGION, _train(ledger), risk="high", approver=bad_approver)
    assert tx.status == "rejected"
    assert "different content_digest" in tx.validation["approval"]["reason"]
    assert st.version == state.version


def test_tampered_signature_is_rejected(rig):
    ledger, engine, state = rig
    priv, _ = generate_keypair()
    key_id = cosign.key_id_for(priv.public_key())

    def forging_approver(cd: str):
        assertion = cosign.build_assertion(cd, "mlro:evil", key_id, "approve",
                                           utcnow(), new_id("nonce"))
        return assertion, "00" * 64                          # not a real signature

    tx, st = engine.commit(state, REGION, _train(ledger), risk="high", approver=forging_approver)
    assert tx.status == "rejected"
    assert "invalid approver signature" in tx.validation["approval"]["reason"]


def test_lowrisk_commits_without_approval(rig):
    ledger, engine, state = rig
    tx, st = engine.commit(state, REGION, _train(ledger))     # risk defaults to low
    assert tx.status == "committed"
    assert tx.validation["approval"]["required"] is False
    assert tx.approver_signature is None
    ok, reason = engine.verify_transaction(asdict(tx))        # system sig still holds
    assert ok, reason
