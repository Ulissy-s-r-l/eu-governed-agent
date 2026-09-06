"""Phase 1 tests: schema, chain integrity, Merkle proofs, GMP bridge, sealing."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.experience import Experience, content_hash
from ccr.ledger import (ExperienceLedger, LocalLedgerBackend, CompositeBackend,
                        generate_keypair, GENESIS_HASH)
from ccr.evaluator import SimulatorGroundTruthEvaluator, SelfReportEvaluator, CompositeEvaluator
from ccr.capture import ExperienceCapture
from ccr.simulator import ToolSelectionSimulator, NaiveAgent
from ccr.gmp_bridge import GMPInMemoryBackend, GMPFactBridge, experience_to_facts
from ccr.grafomem_seal import GrafomemSealer

TOOLS = ["t1", "t2", "t3"]
REGIONS = ["r1", "r2"]


@pytest.fixture
def ledger(tmp_path):
    priv, pub = generate_keypair()
    gmp = GMPInMemoryBackend()
    backend = CompositeBackend(LocalLedgerBackend(tmp_path / "l.jsonl"), GMPFactBridge(gmp))
    return ExperienceLedger(backend, priv, checkpoint_every=4), priv, pub, gmp


def run_episodes(ledger, n, seed=7):
    sim = ToolSelectionSimulator(TOOLS, REGIONS, seed=seed)
    agent = NaiveAgent(TOOLS)
    cap = ExperienceCapture(ledger, SimulatorGroundTruthEvaluator())
    for ep in range(n):
        region = REGIONS[ep % len(REGIONS)]
        tool = agent.select_tool(region)
        res = sim.run_episode(tool, region, ep)
        cap.capture(state_summary=f"s in {region}", goal=f"g {region}", tool=tool,
                    args={"r": region}, result=res,
                    outcome_observed=str(res["success"]), signals=res)
    return sim


# -- schema ----------------------------------------------------------------

def test_record_finalization_and_content_id(ledger):
    lg, *_ = ledger
    run_episodes(lg, 3)
    r = lg.get(0)
    assert r.seq == 0 and r.provenance.prev_hash == GENESIS_HASH
    assert r.exp_id.startswith("sha256:") and r.compute_id() == r.exp_id
    assert r.evaluation.verdict in {"success", "failure"}


def test_canonical_hashing_stable():
    a = {"x": 1, "y": [2, 3]}
    b = {"y": [2, 3], "x": 1}
    assert content_hash(a) == content_hash(b)


# -- chain + signatures -----------------------------------------------------

def test_chain_verifies(ledger):
    lg, *_ = ledger
    run_episodes(lg, 10)
    assert lg.verify_chain()


def test_tamper_breaks_chain(ledger):
    lg, *_ = ledger
    run_episodes(lg, 6)
    lg.get(3).outcome.observed = "forged"
    assert not lg.verify_chain()


def test_wrong_key_fails_verification(ledger):
    lg, priv, pub, gmp = ledger
    run_episodes(lg, 4)
    other_priv, other_pub = generate_keypair()
    r = lg.get(1)
    import cryptography.exceptions
    with pytest.raises(Exception):
        other_pub.verify(bytes.fromhex(r.provenance.signature), r.chain_payload())


def test_persistence_reload(tmp_path):
    priv, pub = generate_keypair()
    backend = LocalLedgerBackend(tmp_path / "l.jsonl")
    lg = ExperienceLedger(backend, priv, checkpoint_every=4)
    run_episodes(lg, 9)
    n, ok = len(lg), lg.verify_chain()
    lg2 = ExperienceLedger(backend, priv, checkpoint_every=4)
    assert len(lg2) == n and lg2.verify_chain() == ok


# -- Merkle checkpoints ------------------------------------------------------

def test_checkpoints_and_inclusion(ledger):
    lg, _, pub, _ = ledger
    run_episodes(lg, 12)          # checkpoint_every=4 → checkpoints at 4, 8, 12
    assert len(lg.checkpoints()) == 3
    for cp in lg.checkpoints():
        assert cp.verify(pub)
    for seq in (0, 5, 11):
        assert lg.verify_inclusion(lg.inclusion_proof(seq))


# -- evaluators ---------------------------------------------------------------

def test_composite_caps_self_report(ledger):
    lg, *_ = ledger
    run_episodes(lg, 1)
    exp = lg.get(0)
    comp = CompositeEvaluator([SimulatorGroundTruthEvaluator(), SelfReportEvaluator()])
    b = comp.evaluate(exp)
    assert 0.0 <= b.score <= 1.0 and b.confidence <= 0.99
    assert set(b.channels) == {"simulator-ground-truth", "agent-self-report"}


# -- GMP bridge ---------------------------------------------------------------

def test_gmp_fact_constellation(ledger):
    lg, _, _, gmp = ledger
    run_episodes(lg, 5)
    facts = gmp.retrieve(predicate="ccr:evaluation")
    assert len(facts) == 5
    assert len(list(gmp.audit())) >= 5 * 6     # 5 base + evaluation per experience
    exp0 = lg.get(0)
    subj_facts = gmp.retrieve(subject=exp0.exp_id)
    assert {f.predicate for f in subj_facts} >= {
        "ccr:goal", "ccr:context", "ccr:action", "ccr:outcome",
        "ccr:provenance", "ccr:evaluation"}


def test_gmp_fact_identity_is_tenant_scoped():
    lg_priv, _ = generate_keypair()
    exp = Experience.__new__(Experience)   # minimal fact identity check
    from ccr.gmp_bridge import GMPFact
    f1 = GMPFact("p", "s", "o", "t", tenant_id="a")
    f2 = GMPFact("p", "s", "o", "t", tenant_id="b")
    assert f1.fact_id != f2.fact_id


# -- grafomem sealing -----------------------------------------------------------

def test_grafomem_seal_roundtrip(ledger):
    lg, *_ = ledger
    run_episodes(lg, 8)
    cp = lg.checkpoint()
    sealer = GrafomemSealer(lg.private_key)
    gfm = sealer.seal_checkpoint(cp)
    assert gfm[:4] == b"GFM1"
    assert sealer.verify_seal(gfm)


def test_grafomem_seal_rejects_tampered_bytes(ledger):
    lg, *_ = ledger
    run_episodes(lg, 8)
    sealer = GrafomemSealer(lg.private_key)
    gfm = bytearray(sealer.seal_checkpoint(lg.checkpoint()))
    gfm[len(gfm) // 2] ^= 0xFF               # flip a payload byte
    assert not sealer.verify_seal(bytes(gfm))
