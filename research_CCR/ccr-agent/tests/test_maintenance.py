"""Confidence-floor enforcement (build guide item 1; doc 02 §3.6, doc 04 §5A).

Read-time floor: a decayed-below-floor policy no longer drives behaviour.
Durable demotion: a `maintenance` transaction demotes it to uniform, recorded in
the ledger with its reason, and is revertable. Only policy_table exists today.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.ledger import ExperienceLedger, LocalLedgerBackend, generate_keypair
from ccr.state import CognitiveState, PolicyEntry, below_floor, is_uniform
from ccr.transaction import LearningEngine, LearningAgent, AdmissionGate

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REGION = "data-processing"
LEARNED = {"search_api": 0.1, "code_runner": 0.1, "db_query": 0.7, "web_fetch": 0.1}  # best = db_query


def _engine(tmp_path):
    priv, _ = generate_keypair()
    ledger = ExperienceLedger(LocalLedgerBackend(tmp_path / "l.jsonl"), priv, checkpoint_every=32)
    return ledger, LearningEngine(ledger, AdmissionGate())


def _state_with_learned_policy(version: int) -> CognitiveState:
    """A learned (non-uniform) policy set at version 0; the state observed at
    `version`. Floor 0.55, rate 0.001: conf 0.6 decays below floor by age ~84."""
    st = CognitiveState.genesis(REGIONS, TOOLS)
    st.policies[REGION] = PolicyEntry(region=REGION, distribution=dict(LEARNED),
                                      confidence=0.6, updated_tx="tx:learned",
                                      updated_version=0)
    st.version = version
    return st.seal()


def _last_gate(ledger):
    recs = [json.loads(l) for l in ledger.backend.read_all()
            if json.loads(l)["kind"] == "gate_decision"]
    return recs[-1]["payload"]


def test_above_floor_policy_drives_behaviour(tmp_path):
    st = _state_with_learned_policy(version=0)                 # fresh: above floor
    assert not below_floor(st.policies[REGION], st.version, st.confidence_policy)
    assert LearningAgent(st, TOOLS).select_tool(REGION) == "db_query"


def test_decayed_below_floor_no_longer_drives_behaviour(tmp_path):
    st = _state_with_learned_policy(version=120)               # aged: decayed below floor
    assert below_floor(st.policies[REGION], st.version, st.confidence_policy)
    # read-time floor: falls back to uniform (search_api), NOT the learned db_query
    assert LearningAgent(st, TOOLS).select_tool(REGION) == TOOLS[0]


def test_maintenance_demotes_below_floor_and_records_reason(tmp_path):
    ledger, engine = _engine(tmp_path)
    st = _state_with_learned_policy(version=120)
    tx, new_state = engine.maintenance(st)
    assert tx is not None and tx.status == "committed" and tx.tx_type == "maintenance"
    assert new_state.version == st.version + 1
    # demoted to uniform, evidence-free
    assert is_uniform(new_state.policies[REGION].distribution)
    assert new_state.policies[REGION].confidence == 0.0
    assert tx.admission["skipped"] is True
    # the demotion is in the ledger, with its reason (the decay computation)
    payload = _last_gate(ledger)
    assert payload["tx_type"] == "maintenance"
    assert payload["delta"]["op"] == "demote" and payload["delta"]["to"] == "uniform"
    just = payload["delta"]["justification"][REGION]
    assert just["was"] == "db_query" and just["decayed_confidence"] < just["floor_commit"]
    # behaviour after demotion: uniform (independently of the read-time floor)
    assert LearningAgent(new_state, TOOLS).select_tool(REGION) == TOOLS[0]


def test_maintenance_is_noop_when_nothing_below_floor(tmp_path):
    ledger, engine = _engine(tmp_path)
    st = _state_with_learned_policy(version=0)                 # above floor
    tx, new_state = engine.maintenance(st)
    assert tx is None and new_state is st                      # nothing to do


def test_maintenance_does_not_demote_already_uniform_genesis(tmp_path):
    ledger, engine = _engine(tmp_path)
    st = CognitiveState.genesis(REGIONS, TOOLS)                # uniform, confidence 0.0
    st.version = 500                                           # far below floor by decay...
    st.seal()
    tx, new_state = engine.maintenance(st)
    assert tx is None                                          # ...but already uniform → skip


def test_demotion_is_revertable(tmp_path):
    ledger, engine = _engine(tmp_path)
    st = _state_with_learned_policy(version=120)
    tx_m, demoted = engine.maintenance(st)
    assert is_uniform(demoted.policies[REGION].distribution)
    # revert the maintenance (e.g. decay-rate misconfig): forward-only
    tx_r, restored = engine.revert(demoted, st, incident_evidence=f"maintenance {tx_m.tx_id} "
                                   "demoted on a misconfigured decay_rate")
    assert tx_r.tx_type == "revert" and tx_r.status == "committed"
    assert restored.parent_commitment == demoted.commitment            # forward-only
    # the learned policy content is restored
    assert not is_uniform(restored.policies[REGION].distribution)
    assert restored.policies[REGION].distribution == LEARNED
    assert restored.policies[REGION].best() == "db_query"
