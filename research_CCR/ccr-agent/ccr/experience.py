"""Experience record schema — CCR doc 03 §2, doc 01 Def. 3.1.

An Experience is the atomic, structured record of one evaluated interaction:
    X_i = <S, G, A, O, E, R, kappa, Lambda, prov, ts>

Design rules (doc 03 §1):
  L1 immutability  — records are frozen; post-append updates are annotations.
  L2 richness      — structured fields, not transcript text.
  L3 verifiability — canonical JSON, content-addressed id, hash-chain link.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA_VER = "ccr-experience/0.1"


def canonical_json(obj: Any) -> bytes:
    """IPLD-style canonical serialization: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str).encode("utf-8")


def content_hash(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj)).hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex[:16]}"


# --------------------------------------------------------------------------
# Field groups (doc 03 §2.1)
# --------------------------------------------------------------------------

@dataclass
class ContextBlock:
    state_summary: str                       # compressed observation state S_i
    environment_ref: str                     # environment/session identifier
    state_version: Optional[str] = None      # committed CSO hash in force (None in Phase 1)
    context_refs: list[str] = field(default_factory=list)   # content-addressed blobs


@dataclass
class GoalBlock:
    statement: str
    source: str = "delegation"               # delegation | user | inferred
    goal_id: str = field(default_factory=lambda: new_id("goal"))
    source_ref: Optional[str] = None         # mandate ref or experience ref


@dataclass
class ActionStep:
    tool: str
    args_digest: str
    result_digest: str


@dataclass
class ActionBlock:
    strategy_ref: Optional[str]
    policy_region: Optional[str]
    steps: list[ActionStep]
    authority_scope: Optional[str] = None    # scope version in force at act time


@dataclass
class OutcomeBlock:
    observed: str
    signals: dict[str, Any] = field(default_factory=dict)   # numeric signals, e.g. tests_passed
    artifacts: list[str] = field(default_factory=list)


@dataclass
class EvaluationBlock:
    verdict: str                             # success | failure | mixed | indeterminate
    score: float                             # outcome score in [0,1]
    confidence: float                        # evaluator confidence c_i in [0,1]
    channels: list[str]                      # e.g. ["simulator-ground-truth"]
    attribution: dict[str, Any] = field(default_factory=dict)
    evaluator_ref: str = "eval:unknown"


@dataclass
class ProvenanceBlock:
    captured_by: str = "ccr-capture/0.1"
    channels: list[str] = field(default_factory=lambda: ["runtime-telemetry"])
    signature: Optional[str] = None          # hex Ed25519 signature (set at ledger append)
    prev_hash: str = "GENESIS"               # hash-chain link to record seq-1


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------

@dataclass
class Experience:
    context: ContextBlock
    goal: GoalBlock
    action: ActionBlock
    outcome: OutcomeBlock
    agent_ref: str = "did:gns:local-dev"
    captured_at: str = field(default_factory=utcnow)
    evaluation: Optional[EvaluationBlock] = None     # None until evaluated (two-tier capture)
    learning_ref: Optional[str] = None               # set by later learning transactions (Phase 4+)
    causal_links: list[str] = field(default_factory=list)
    confidence: float = 1.0
    provenance: ProvenanceBlock = field(default_factory=ProvenanceBlock)
    schema_ver: str = SCHEMA_VER
    seq: int = -1                                    # assigned by ledger at append
    exp_id: str = ""                                 # content hash, assigned by finalize()

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Experience":
        return cls(
            context=ContextBlock(**d["context"]),
            goal=GoalBlock(**d["goal"]),
            action=ActionBlock(
                strategy_ref=d["action"].get("strategy_ref"),
                policy_region=d["action"].get("policy_region"),
                steps=[ActionStep(**s) for s in d["action"]["steps"]],
                authority_scope=d["action"].get("authority_scope"),
            ),
            outcome=OutcomeBlock(**d["outcome"]),
            agent_ref=d.get("agent_ref", "did:gns:local-dev"),
            captured_at=d.get("captured_at", utcnow()),
            evaluation=EvaluationBlock(**d["evaluation"]) if d.get("evaluation") else None,
            learning_ref=d.get("learning_ref"),
            causal_links=d.get("causal_links", []),
            confidence=d.get("confidence", 1.0),
            provenance=ProvenanceBlock(**d.get("provenance", {})),
            schema_ver=d.get("schema_ver", SCHEMA_VER),
            seq=d.get("seq", -1),
            exp_id=d.get("exp_id", ""),
        )

    # -- identity ----------------------------------------------------------

    def body_for_hash(self) -> dict[str, Any]:
        """The hashed body excludes seq, exp_id, and provenance.signature/prev_hash:
        those are assigned by the ledger, and the chain link must not be circular."""
        d = self.to_dict()
        d.pop("seq"); d.pop("exp_id")
        d["provenance"].pop("signature")
        d["provenance"].pop("prev_hash")
        return d

    def compute_id(self) -> str:
        return content_hash(self.body_for_hash())

    def finalize(self, seq: int, prev_hash: str) -> "Experience":
        """Ledger append finalization: assign sequence + chain link, then content-id."""
        self.seq = seq
        self.provenance.prev_hash = prev_hash
        self.exp_id = self.compute_id()
        return self

    def chain_payload(self) -> bytes:
        """Bytes covered by the per-record signature and the chain hash:
        the content id bound to its sequence and predecessor."""
        return f"{self.exp_id}|{self.seq}|{self.provenance.prev_hash}".encode("utf-8")

    def record_hash(self) -> str:
        return "sha256:" + hashlib.sha256(self.chain_payload()).hexdigest()

    def is_evaluated(self) -> bool:
        return self.evaluation is not None
