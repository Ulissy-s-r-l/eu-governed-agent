"""Property-based harness — Phase 8 Stage 1 (build-guide §6, item 15).

A `RuleBasedStateMachine` drives the real engine with GENERATED operation
sequences — honest captures, forged self-reports, learn/memory commits,
recalibrate, maintenance, revert, and two adversarial moves (a semantic ledger
mutation and a tampered recalibrate). An ORACLE — a plain-Python account of what
must hold — advances in lockstep, so every assertion compares the system against
an independent model rather than against itself.

Properties checked (see each `@invariant`/`@rule`):

  doc 07 §7:
    1. No unvalidated commit        — Committed(ΔC) ⇒ Validate(ΔC)=⊤       [invariant]
    2. Tamper evidence              — Modify(record_k) ⇒ ¬VerifyChain      [rule: tamper_ledger]
    3. Recovery completeness        — every committed state reverts        [rule: revert]
    4. Attribution completeness     — I4 level the code supports today     [rule: commit_memory_*]
    5. No unauthorized action       — EXCLUDED: the authority guard is Phase 7 (nothing to
                                      test yet). First extension of this harness when 7A lands.

  I3 in its EVENTUAL-CONSISTENCY form (NOT the invariant form — a red test on correct
  eventually-consistent behaviour is how a harness loses trust in week one):
    (a) after any maintenance(), no active entry is below floor            [rule: maintenance]
    (b) between runs, no below-floor entry drives behaviour via select_tool [invariant]

  I6 support independence (newest invariant, one enforcing function, self-disclosed as
  silently-lapsing): effective support ≤ |root-experience union|          [rule: commit_*]

  The two escaped bugs, as permanent named properties:
    - No self-referential commitment (genesis_ref): reseal reproduces the commitment; a
      state is never its own parent.                                       [invariant]
    - Distributions sum to 1 (rounding): every committed distribution sums to 1±1e-9,
      every weight ∈ [0,1].                                                [invariant]
"""
import json
import sys
import tempfile
from pathlib import Path

from hypothesis import settings, HealthCheck
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, precondition

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccr.ledger import ExperienceLedger, LocalLedgerBackend, LedgerEntry, generate_keypair
from ccr.evaluator import SimulatorGroundTruthEvaluator
from ccr.capture import ExperienceCapture
from ccr.simulator import ToolSelectionSimulator
from ccr.state import CognitiveState, below_floor
from ccr.transaction import LearningEngine, AdmissionGate, LearningAgent
from ccr.consolidation import MemoryCandidate
from ccr.calibration import CalibrationLoop, recompute_reliability, REFERENCE_RELIABILITY
from ccr.contradiction import claim_content, SENSE_RELIABLE, SENSE_UNRELIABLE
from ccr.support import root_support
from ccr.experience import EvaluationBlock

TOOLS = ["search_api", "code_runner", "db_query", "web_fetch"]
REGIONS = ["api-interaction", "data-processing", "web-research"]
REF = "simulator-ground-truth"
EVIDENCE_FREE = {"maintenance", "recalibrate", "revert"}


class _StubLoop:
    """A loop whose to_state() we control — to submit tampered reliabilities."""
    def __init__(self, state_dict):
        self._s = state_dict
        self.reference = state_dict["reference"]

    def to_state(self):
        return self._s


class CCRStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self._tmp = tempfile.TemporaryDirectory()
        self.priv, _ = generate_keypair()
        self.ledger = ExperienceLedger(
            LocalLedgerBackend(Path(self._tmp.name) / "ledger.jsonl"), self.priv,
            checkpoint_every=8)
        self.capture = ExperienceCapture(self.ledger, SimulatorGroundTruthEvaluator())
        self.engine = LearningEngine(self.ledger, AdmissionGate())
        self.sim = ToolSelectionSimulator(TOOLS, REGIONS, seed=7)
        self.state = CognitiveState.genesis(REGIONS, TOOLS)
        self.states = [self.state]              # every committed state (for revert)
        self.episode = 0
        # ORACLE — the independent account.
        self.oracle_reference = None            # the reference channel, once designated
        self.oracle_committed = 0               # count of committed transactions

    def teardown(self):
        self._tmp.cleanup()

    # -- helpers ------------------------------------------------------------

    def _advance(self, tx, new_state):
        if tx is not None and tx.status == "committed":
            self.state = new_state
            self.states.append(new_state)
            self.oracle_committed += 1
        return tx

    def _region_evidence(self, region):
        return [e for e in self.ledger.evaluated()
                if e.action.policy_region == region]

    # -- capture rules ------------------------------------------------------

    @rule(region=st.sampled_from(REGIONS), tool=st.sampled_from(TOOLS))
    def capture_honest(self, region, tool):
        """An honest, ground-truth-evaluated experience."""
        res = self.sim.run_episode(tool, region, self.episode)
        self.episode += 1
        self.capture.capture(state_summary="s", goal="g", tool=tool,
                             args={"region": region}, result=res,
                             outcome_observed=str(res["success"]), signals=res,
                             policy_region=region)

    @rule(region=st.sampled_from(REGIONS), tool=st.sampled_from(TOOLS))
    def capture_forged(self, region, tool):
        """A forged self-report: claims success at confidence 0.99 regardless of
        truth. Honestly SIGNED (the poison is semantic, not a tamper), so it does
        not break the chain — it is a gate/calibration problem, not an integrity one."""
        exp = self.capture.emit(state_summary="s", goal="g", tool=tool,
                                args={"region": region}, result={"forged": True},
                                outcome_observed="succeeded", signals={"success": True},
                                policy_region=region)
        exp.evaluation = EvaluationBlock(verdict="success", score=1.0, confidence=0.99,
                                         channels=["agent-self-report"],
                                         evaluator_ref="eval:agent-self-report")
        self.ledger.append(exp)

    # -- learning commits ---------------------------------------------------

    @rule(region=st.sampled_from(REGIONS))
    def commit_learn(self, region):
        evidence = self._region_evidence(region)
        if not evidence:
            return
        tx, ns = self.engine.commit(self.state, region, evidence)
        if tx.status == "committed":
            self._check_i6(tx, evidence)
        self._advance(tx, ns)

    @rule(region=st.sampled_from(REGIONS), tool=st.sampled_from(TOOLS),
          sense=st.sampled_from([SENSE_RELIABLE, SENSE_UNRELIABLE]))
    def commit_memory_insert(self, region, tool, sense):
        evidence = [e for e in self._region_evidence(region)
                    if e.action.steps[-1].tool == tool]
        if len(evidence) < 1:
            return
        cand = MemoryCandidate(op="insert", type="consolidation",
                               content=claim_content(tool, region, sense),
                               sources=[e.exp_id for e in evidence],
                               confidence=0.9, region=region)
        tx, ns = self.engine.commit_memory(self.state, cand, evidence)
        if tx.status == "committed":
            self._check_i6(tx, evidence)
            self._check_attribution(ns, tx)
        self._advance(tx, ns)

    @rule(k=st.integers(min_value=0, max_value=10_000))
    def commit_memory_supersede(self, k):
        actives = [mid for mid, m in self.state.semantic_memory.items()
                   if m.status == "active"]
        if not actives:
            return
        target = actives[k % len(actives)]
        old = self.state.semantic_memory[target]
        # fresh support from any evaluated experience in the target claim's region
        region = old.content.split("region:")[-1] if "region:" in old.content else REGIONS[0]
        evidence = self._region_evidence(region)
        if len(evidence) < 1:
            return
        cand = MemoryCandidate(op="insert", type="consolidation",
                               content=old.content, sources=[e.exp_id for e in evidence],
                               confidence=0.9, region=region, supersedes_mem_id=target)
        tx, ns = self.engine.commit_memory(self.state, cand, evidence)
        self._advance(tx, ns)

    # -- calibration --------------------------------------------------------

    @rule(agree=st.integers(min_value=0, max_value=40),
          dis=st.integers(min_value=0, max_value=40))
    def recalibrate(self, agree, dis):
        cal = CalibrationLoop(reference_channel=REF)
        for i in range(agree):
            cal.observe("agent-self-report", agreed=True, exp_id=f"a{i}")
        for i in range(dis):
            cal.observe("agent-self-report", agreed=False, exp_id=f"d{i}")
        tx, ns = self.engine.recalibrate(self.state, cal)
        assert tx.status == "committed", tx.validation
        # ORACLE: the reference is designated once, then immutable.
        if self.oracle_reference is None:
            self.oracle_reference = REF
        assert ns.evaluation_history["reference"] == self.oracle_reference
        self._advance(tx, ns)

    @rule(bump=st.floats(min_value=0.11, max_value=0.5))
    def tampered_recalibrate(self, bump):
        """A submitted reliability that does not recompute from its window must be
        rejected, and the state must not change."""
        cal = CalibrationLoop(reference_channel=REF)
        for i in range(10):
            cal.observe("agent-self-report", agreed=(i % 4 == 0), exp_id=f"e{i}")
        tampered = cal.to_state()
        honest_r = tampered["channels"]["agent-self-report"]["reliability"]
        tampered["channels"]["agent-self-report"]["reliability"] = min(0.999, honest_r + bump)
        before = self.state.commitment
        tx, ns = self.engine.recalibrate(self.state, _StubLoop(tampered))
        assert tx.status == "rejected"
        assert ns.commitment == before                # unchanged on reject
        assert ns is self.state

    # -- maintenance & revert ----------------------------------------------

    @rule()
    def maintenance(self):
        tx, ns = self.engine.maintenance(self.state)
        self._advance(tx, ns)
        # I3(a): after a maintenance sweep, NO active policy entry is below floor.
        for entry in self.state.policies.values():
            if not below_floor(entry, self.state.version, self.state.confidence_policy):
                continue
            # a still-below-floor entry after maintenance is only OK if it is already
            # uniform (nothing to demote) — maintenance targets learned entries.
            vals = list(entry.distribution.values())
            assert max(vals) - min(vals) < 1e-9, (
                "maintenance left a learned entry below floor and non-uniform")

    @rule(k=st.integers(min_value=0, max_value=10_000))
    def revert(self, k):
        """P3 recovery completeness on a RANDOMLY chosen past state, not just tip."""
        target = self.states[k % len(self.states)]
        tx, ns = self.engine.revert(self.state, target, incident_evidence="prop-revert")
        assert tx.tx_type == "revert"
        assert ns.policies == target.policies             # content restored
        assert ns.semantic_memory == target.semantic_memory
        assert ns.evaluation_history == target.evaluation_history
        assert ns.parent_commitment == self.state.commitment   # forward-only
        self.state = ns
        self.states.append(ns)

    # -- adversarial: semantic ledger tamper -------------------------------

    @rule(k=st.integers(min_value=0, max_value=10_000))
    def tamper_ledger(self, k):
        """P2: a SEMANTIC mutation of a committed record (parse → change a field →
        re-serialize; never a byte flip) must make verify_chain() False, and the
        mutated line must still PARSE — so the failure is cryptographic (content-id
        mismatch), not syntactic. Operates on a COPY so the live machine is intact."""
        lines = self.ledger.backend.read_all()
        exp_idx = [i for i, l in enumerate(lines)
                   if json.loads(l)["kind"] == "experience"]
        if not exp_idx:
            return
        i = exp_idx[k % len(exp_idx)]
        d = json.loads(lines[i])
        d["payload"]["outcome"]["observed"] = "TAMPERED_" + str(
            d["payload"]["outcome"]["observed"])            # semantic field change
        lines[i] = json.dumps(d)
        # the mutated line still parses (not a syntactic break)
        assert LedgerEntry.from_line(lines[i]).kind == "experience"
        copy_path = Path(self._tmp.name) / f"tampered_{k}.jsonl"
        copy_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        replica = ExperienceLedger(LocalLedgerBackend(copy_path), self.priv,
                                   checkpoint_every=8)
        assert replica.verify_chain() is False             # detected, cryptographically

    # -- invariants (checked after every rule) -----------------------------

    @invariant()
    def inv_no_unvalidated_commit(self):
        """P1: every committed tx passed validation, and either passed admission or
        is a documented evidence-free type."""
        for tx in self.engine.transactions:
            if tx.status != "committed":
                continue
            assert tx.validation.get("verdict") == "commit", (tx.tx_type, tx.validation)
            evidence_free = tx.tx_type in EVIDENCE_FREE
            admitted = bool(tx.admission.get("admit"))
            assert evidence_free or admitted, (tx.tx_type, tx.admission)

    @invariant()
    def inv_distributions_sum_to_one(self):
        """Escaped-bug property: rounding must not break normalization."""
        for entry in self.state.policies.values():
            total = sum(entry.distribution.values())
            assert abs(total - 1.0) < 1e-9, (entry.region, total)
            assert all(0.0 <= w <= 1.0 for w in entry.distribution.values())

    @invariant()
    def inv_no_self_referential_commitment(self):
        """Escaped-bug property (genesis_ref): reseal is deterministic and a state
        is never its own parent."""
        assert self.state.copy().seal().commitment == self.state.commitment
        assert self.state.commitment != self.state.parent_commitment

    @invariant()
    def inv_below_floor_not_behavioural(self):
        """I3(b): a below-floor policy entry does not drive behaviour — select_tool
        returns the uniform fallback, immediately, without a maintenance sweep."""
        agent = LearningAgent(self.state, TOOLS)
        for region, entry in self.state.policies.items():
            if below_floor(entry, self.state.version, self.state.confidence_policy):
                assert agent.select_tool(region) == TOOLS[0]

    @invariant()
    def inv_reference_immutable(self):
        """Calibration reference, once committed, never changes."""
        ref = (self.state.evaluation_history or {}).get("reference")
        if ref is not None and self.oracle_reference is not None:
            assert ref == self.oracle_reference

    # -- shared checks ------------------------------------------------------

    def _check_i6(self, tx, evidence):
        """I6: the gate's effective support equals the deduped root union — never a
        sum across artifacts. A second summing call site would make roots exceed it."""
        union = root_support([e.exp_id for e in evidence])
        assert tx.admission["roots"] == len(union)
        assert tx.admission["roots"] <= len(evidence)

    def _check_attribution(self, ns, tx):
        """P4 (scoped to I4): a committed MemoryItem names non-empty sources present
        in the ledger, and a created_tx present in the engine's transaction record.
        (doc 02 §3.9's queryable provenance_index does not exist in this tree.)"""
        mem_id = tx.delta.get("mem_id")
        if mem_id is None or mem_id not in ns.semantic_memory:
            return
        item = ns.semantic_memory[mem_id]
        assert item.sources, "committed memory item has empty sources (I4)"
        ledger_ids = {e.exp_id for e in self.ledger}
        assert all(s in ledger_ids for s in item.sources)
        tx_ids = {t.tx_id for t in self.engine.transactions}
        assert item.created_tx in tx_ids


# 10k examples x 20 steps = 200k operations, ~54s locally (< the ~2 min CI budget).
CCRStateMachine.TestCase.settings = settings(
    max_examples=10_000, stateful_step_count=20, deadline=None,
    suppress_health_check=[HealthCheck.too_slow])

TestCCR = CCRStateMachine.TestCase
