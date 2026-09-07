"""Learning Transaction — CCR doc 01 §§6-7, doc 04. The learning half.

This is the mechanism Phase 1 deliberately did not have: a controlled,
transactional path from stored experience to validated behavioral change.

  Admission gate  L(X)  — doc 01 Def. 6.1: learning-value functional with a
                          trust- and risk-dependent threshold.
  Propose               — candidate update ΔC from evaluated experiences.
  Validate              — invariant check + counterfactual replay against
                          held-out ledger history (do-no-harm, doc 04 §2.2).
  Commit                — atomic state transition, hash-chained, recorded.
  Revert                — forward-only recovery (doc 01 Def. 8.4).

The agent reads ONLY committed state. Candidates never touch the hot path.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional

from .experience import Experience, canonical_json, new_id, utcnow
from .ledger import ExperienceLedger, LedgerEntry
from .state import CognitiveState, PolicyEntry
from . import cosign


# --------------------------------------------------------------------------
# Candidate update (doc 01 Def. 7.1)
# --------------------------------------------------------------------------

@dataclass
class CandidateUpdate:
    op: str                                # reweight | insert | deprecate | revert
    target: str                            # "policy_table"
    region: str
    distribution: dict[str, float]         # proposed new distribution
    confidence: float
    justification: list[str]               # exp_ids cited in support
    risk: str = "low"                      # low | medium | high


@dataclass
class TransactionRecord:
    tx_id: str
    tx_type: str                           # learn | revert
    parent_state: str
    status: str                            # committed | rejected
    admission: dict
    validation: dict
    delta: Optional[dict]
    new_commitment: Optional[str]
    created_at: str = field(default_factory=utcnow)
    # --- cgr.cosign.v1 envelope (approval-free mode) ----------------------
    schema: Optional[str] = None           # "cgr.cosign.v1" once co-signed
    profile: Optional[str] = None          # "cgr.learning-tx.v1"
    approval_mode: Optional[str] = None    # "free"
    content_body: Optional[dict] = None    # what content_digest is over
    content_digest: Optional[str] = None   # BLAKE2b-256 over JCS(content_body)
    approval_assertion: Optional[dict] = None   # the approver's signed statement
    approver_signature: Optional[str] = None    # inner (self-custodied) signature
    system_signature: Optional[str] = None      # outer; computed LAST, incl. approver sig


# --------------------------------------------------------------------------
# Admission gate (doc 01 Def. 6.1)
# --------------------------------------------------------------------------

class AdmissionGate:
    """L(X): should this evidence modify future behavior?

    TWO-TERM functional (the four-term V of doc 01 Def. 6.1 is NOT implemented
    here — see the note below):

        V(X) = (w_trust * trust + w_info * info) * support

      trust   = mean evaluation confidence (poison self-reports are capped at
                0.3 at capture, so they cannot lift V on their own).
      info    = mean evaluation score (did the tool actually work).
      support = min(1, n / min_evidence): thin evidence is discounted.

    Why two terms, not four (honest scope): the doc's `surprise` (novelty /
    evaluator disagreement as a learning signal) and `risk` have **no consumer
    in this experiment** — there is no risk model here, and a "consistency"
    surrogate for surprise was computed and then discarded in the prior code.
    Rather than invent a risk model to match a docstring, the functional is cut
    to the two terms actually computed. Restore the four-term V when a concrete
    risk model and a real surprise signal exist.

    Threshold (deliberate, not accidental): the two-term ceiling is
    (w_trust + w_info) * 1 = 0.70. The threshold 0.55 sits between:
      - the poison floor: trust≤0.3, info=1.0, support=1 → V ≈ 0.35  (REJECTED)
      - the honest floor: trust≈0.99, info≈1.0, support=1 → V ≈ 0.695 (ADMITTED)
    i.e. ~0.15 margin below the honest case and ~0.20 above the poison case.
    It MUST stay below the 0.70 ceiling or nothing admits; keep the two in sync
    if the weights change.
    """

    def __init__(self, threshold: float = 0.55, min_evidence: int = 3,
                 w_trust: float = 0.5, w_info: float = 0.2):
        self.threshold = threshold
        self.min_evidence = min_evidence
        self.w_trust, self.w_info = w_trust, w_info
        self.ceiling = w_trust + w_info            # 0.70 with the defaults
        assert threshold < self.ceiling, (
            f"threshold {threshold} >= two-term ceiling {self.ceiling}: nothing admits")

    def evaluate_evidence(self, evidence: list[Experience]) -> dict:
        """Score a set of supporting experiences for a candidate update."""
        n = len(evidence)
        if n == 0:
            return {"V": 0.0, "admit": False, "reason": "no evidence"}
        trust = sum(e.evaluation.confidence for e in evidence) / n
        scores = [e.evaluation.score for e in evidence]
        info = sum(scores) / n
        support = min(1.0, n / self.min_evidence)
        V = (self.w_trust * trust + self.w_info * info) * support
        admit = V >= self.threshold and n >= self.min_evidence
        return {"V": round(V, 4), "threshold": self.threshold, "admit": admit,
                "trust": round(trust, 4), "info": round(info, 4),
                "support": round(support, 4), "ceiling": self.ceiling, "n": n}


# --------------------------------------------------------------------------
# Learning engine
# --------------------------------------------------------------------------

class LearningEngine:
    """Proposes, validates, commits, and reverts cognitive-state updates.
    The ONLY writer of behavioral state (doc 00 §6.9)."""

    def __init__(self, ledger: ExperienceLedger, gate: Optional[AdmissionGate] = None,
                 replay_tolerance: float = 0.05):
        self.ledger = ledger
        self.gate = gate or AdmissionGate()
        self.replay_tolerance = replay_tolerance
        self.transactions: list[TransactionRecord] = []

    # -- propose (doc 04 stage 4) -------------------------------------------

    def propose(self, state: CognitiveState, region: str,
                evidence: list[Experience]) -> Optional[CandidateUpdate]:
        """Build a candidate policy update for `region` from evaluated
        experiences mentioning that region, success-weighted."""
        per_tool: dict[str, list[float]] = {}
        for e in evidence:
            if not e.is_evaluated():
                continue
            tool = e.action.steps[-1].tool
            per_tool.setdefault(tool, []).append(
                e.evaluation.score * e.evaluation.confidence)
        if not per_tool:
            return None
        weights = {t: sum(s) for t, s in per_tool.items()}
        total = sum(weights.values()) or 1.0
        dist = {t: round(w / total, 4) for t, w in weights.items()}
        conf = min(0.99, sum(len(s) for s in per_tool.values()) / 20.0)
        return CandidateUpdate(op="reweight", target="policy_table",
                               region=region, distribution=dist,
                               confidence=conf,
                               justification=[e.exp_id for e in evidence])

    # -- validation (doc 01 Def. 7.5) ----------------------------------------

    def validate(self, state: CognitiveState, cand: CandidateUpdate) -> dict:
        """Invariant check + counterfactual replay (do-no-harm).

        Replay (doc 04 §2.2 — HELD-OUT): re-score the candidate's preferred tool
        vs the incumbent's preferred tool against evaluated ledger history for
        this region, EXCLUDING the experiences cited in cand.justification. The
        candidate must not be materially worse than the incumbent on evidence it
        did not itself train on — otherwise replay is in-sample and validates a
        candidate against its own justifying data.
        """
        checks = {"invariant": False, "replay": False}

        # I2 normalization
        total = sum(cand.distribution.values())
        checks["invariant"] = abs(total - 1.0) < 1e-6
        if not checks["invariant"]:
            return {"verdict": "reject", "reason": f"distribution sums to {total}",
                    "checks": checks}

        # Replay against HELD-OUT evaluated history: region records NOT cited as
        # justification for this candidate.
        cited = set(cand.justification)
        history = [e for e in self.ledger.evaluated()
                   if e.action.policy_region == cand.region and e.exp_id not in cited]
        held_out_n = len(history)
        def rate(tool: str) -> Optional[float]:
            rs = [e.evaluation.score for e in history
                  if e.action.steps[-1].tool == tool]
            return sum(rs) / len(rs) if rs else None

        cand_tool = max(cand.distribution, key=cand.distribution.get)
        incumbent = state.policy_for(cand.region)
        cand_rate = rate(cand_tool)
        inc_rate = rate(incumbent.best()) if incumbent else None

        if cand_rate is None:
            return {"verdict": "reject",
                    "reason": "no held-out replay evidence for candidate",
                    "checks": checks, "held_out_n": held_out_n}
        if inc_rate is not None and cand_rate < inc_rate - self.replay_tolerance:
            return {"verdict": "reject",
                    "reason": (f"replay regression: candidate {cand_tool} "
                               f"rate={cand_rate:.3f} < incumbent "
                               f"{incumbent.best()} rate={inc_rate:.3f}"),
                    "checks": checks, "cand_rate": cand_rate, "inc_rate": inc_rate,
                    "held_out_n": held_out_n}
        checks["replay"] = True
        # COLD-START LIMITATION (recorded, not hidden): when inc_rate is None the
        # incumbent has NO held-out history in this region, so do-no-harm has
        # nothing to compare against — replay cannot protect a region it has
        # never seen. The candidate commits on the strength of admission alone.
        cold_start = inc_rate is None
        return {"verdict": "commit", "checks": checks,
                "cand_rate": cand_rate, "inc_rate": inc_rate,
                "held_out_n": held_out_n, "cold_start_no_incumbent": cold_start}

    # -- commit (doc 04 stage 8) ---------------------------------------------

    def commit(self, state: CognitiveState, region: str,
               evidence: list[Experience], *, rationale: str = "",
               risk: Optional[str] = None,
               approver: Optional["cosign.Approver"] = None,
               ) -> tuple[TransactionRecord, CognitiveState]:
        """Full transaction: admit -> propose -> validate -> co-sign -> commit/reject.
        Always returns (tx, state): the state is the NEW state on commit,
        the UNCHANGED input state on any rejection (doc 01 §7.2 guard).

        Co-signature (cgr.cosign.v1, approval-free mode): the candidate + its
        admission + validation evidence + rationale form the `content_body`; a
        §5.1 predicate makes an approver signature REQUIRED when `risk == "high"`.
        `approver` is a self-custody signer (content_digest -> (assertion, sig));
        the engine never holds the approver key. A high-risk transaction lacking
        a valid approver signature is REJECTED at validation, not committed. The
        system signature is computed LAST, over the whole record including the
        approver signature (nested)."""
        admission = self.gate.evaluate_evidence(evidence)
        tx = TransactionRecord(tx_id=new_id("tx"), tx_type="learn",
                               parent_state=state.commitment, status="rejected",
                               admission=admission, validation={}, delta=None,
                               new_commitment=None)
        if not admission["admit"]:
            tx.validation = {"verdict": "not_reached", "reason": "admission gate"}
            self._record(tx)
            return tx, state

        cand = self.propose(state, region, evidence)
        if cand is None:
            tx.validation = {"verdict": "reject", "reason": "no candidate formed"}
            self._record(tx)
            return tx, state
        tx.delta = asdict(cand)

        if risk is not None:
            cand.risk = risk
            tx.delta = asdict(cand)
        validation = self.validate(state, cand)
        tx.validation = validation
        if validation["verdict"] != "commit":
            self._record(tx)
            return tx, state

        # -- co-signature envelope (cgr.cosign.v1, approval-free) --------------
        # content_body = delta + admission + validation evidence + rationale + risk
        # (fuller scope: the approver signs what they reviewed, not just the delta).
        content_body = {
            "delta": asdict(cand), "admission": admission,
            "validation": validation, "rationale": rationale, "risk": cand.risk,
        }
        cd = cosign.content_digest(content_body)
        required, resolved = cosign.predicate_required(cosign.REQUIRED_WHEN, content_body)

        approval_block: dict = {"required": required, "predicate_resolved": resolved,
                                "predicate": cosign.REQUIRED_WHEN}
        assertion = sig = None
        if approver is not None:
            assertion, sig = approver(cd)
            # the approval MUST bind THIS content, and the signature MUST verify
            if assertion.get("content_digest") != cd:
                approval_block.update(verdict="reject",
                                      reason="approver signature over a different content_digest")
                tx.validation = {**validation, "approval": approval_block, "verdict": "reject"}
                self._record(tx); return tx, state
            if not cosign.verify_assertion(assertion, sig, assertion.get("approver_key_id", "")):
                approval_block.update(verdict="reject", reason="invalid approver signature")
                tx.validation = {**validation, "approval": approval_block, "verdict": "reject"}
                self._record(tx); return tx, state
            approval_block.update(verdict="ok", approver_id=assertion.get("approver_id"))
        elif required:
            # §5.1 / §7.2: predicate satisfied, no approver signature → NON-CONFORMANT.
            approval_block.update(verdict="reject",
                                  reason="high-risk update requires an approver signature (cgr.cosign.v1 §5.1)")
            tx.validation = {**validation, "approval": approval_block, "verdict": "reject"}
            self._record(tx); return tx, state

        tx.validation = {**validation, "approval": approval_block}

        # atomic commit: new state, hash-chained commitment
        new_state = state.copy()
        new_state.version = state.version + 1
        new_state.parent_commitment = state.commitment
        new_state.policies[region] = PolicyEntry(
            region=region, distribution=cand.distribution,
            confidence=cand.confidence, updated_tx=tx.tx_id)
        new_state.update_ref = tx.tx_id
        new_state.seal()

        tx.status = "committed"
        tx.new_commitment = new_state.commitment
        # attach the cosign envelope, then compute the SYSTEM signature LAST over
        # the whole record INCLUDING the approver signature (nested, §2.3).
        tx.schema = cosign.SCHEMA
        tx.profile = cosign.LEARNING_TX_PROFILE
        tx.approval_mode = cosign.APPROVAL_MODE_FREE
        tx.content_body = content_body
        tx.content_digest = cd
        tx.approval_assertion = assertion
        tx.approver_signature = sig
        tx.system_signature = cosign.sign_system(asdict(tx), self.ledger.private_key)

        self._record(tx)
        return tx, new_state

    # -- verify a co-signed transaction (cgr.cosign.v1 verifier, §8) ----------

    def verify_transaction(self, record: dict) -> tuple[bool, str]:
        """Verify a recorded transaction's envelope. Order mirrors spec §8:
        system signature (catches a stripped/altered approver signature), then
        content integrity, then the approver signature binds this content."""
        sys_pub = self.ledger.private_key.public_key()
        if not cosign.verify_system(record, sys_pub):
            return (False, "system signature invalid — record altered or approver "
                           "signature stripped")
        cb = record.get("content_body")
        if cb is not None and cosign.content_digest(cb) != record.get("content_digest"):
            return (False, "content_digest does not match content_body")
        a, s = record.get("approval_assertion"), record.get("approver_signature")
        if a is not None:
            if a.get("content_digest") != record.get("content_digest"):
                return (False, "approver assertion binds a different content_digest")
            if not s or not cosign.verify_assertion(a, s, a.get("approver_key_id", "")):
                return (False, "approver signature invalid")
        return (True, "ok")

    # -- revert (doc 01 Def. 8.4, doc 04 §5) ----------------------------------

    def revert(self, state: CognitiveState, target: CognitiveState,
               incident_evidence: str) -> tuple[TransactionRecord, CognitiveState]:
        """Forward-only rollback: a NEW commit whose content equals the
        ancestor's, parented to the CURRENT state. History is never rewritten."""
        tx = TransactionRecord(tx_id=new_id("tx"), tx_type="revert",
                               parent_state=state.commitment, status="committed",
                               admission={"reason": incident_evidence},
                               validation={"verdict": "commit",
                                           "note": "ancestor state previously validated"},
                               delta={"op": "revert",
                                      "target_commitment": target.commitment},
                               new_commitment=None)
        new_state = target.copy()
        new_state.version = state.version + 1
        new_state.parent_commitment = state.commitment
        new_state.update_ref = tx.tx_id
        new_state.seal()
        tx.new_commitment = new_state.commitment
        self._record(tx)
        return tx, new_state

    def _record(self, tx: TransactionRecord) -> None:
        self.transactions.append(tx)
        # gate decisions and outcomes are ledger events (doc 03 §3.2)
        self.ledger.backend.append(
            LedgerEntry("gate_decision", asdict(tx)).to_line())


# --------------------------------------------------------------------------
# Learning agent — the read path that closes the loop
# --------------------------------------------------------------------------

class LearningAgent:
    """Selects tools from COMMITTED cognitive state at decision time.
    This is the read path Phase 1 lacked: behavior is a function of the
    committed state, and the state changes only through transactions."""

    def __init__(self, state: CognitiveState, tools: list[str]):
        self.state = state
        self.tools = tools

    def select_tool(self, region: str) -> str:
        policy = self.state.policy_for(region)
        if policy is None:
            return self.tools[0]
        return policy.best()

    def on_state(self, new_state: CognitiveState) -> None:
        self.state = new_state
