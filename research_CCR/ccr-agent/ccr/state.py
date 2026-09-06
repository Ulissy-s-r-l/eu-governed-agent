"""Cognitive State (minimal) — CCR doc 02, Phase 3–4 slice.

Phase 3–4 needs only ONE behavioral component to prove the transaction
machinery: the policy table (context region -> distribution over tools).
The full 14-component CSO (doc 02) comes later; this is the smallest state
object that lets experience change behavior UNDER CONTROL.

Properties preserved from the full spec:
  - content-addressed commitment, hash-chained to parent (doc 01 Def. 8.1)
  - every entry carries confidence + the tx that produced it (I3/I4)
  - state is READ-ONLY for the agent; only LearningEngine.commit writes
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional

from .experience import canonical_json

GENESIS_COMMITMENT = "GENESIS"


@dataclass
class PolicyEntry:
    region: str
    distribution: dict[str, float]          # strategy/tool -> probability
    confidence: float
    updated_tx: str                         # I4: provenance to committing transaction

    def best(self) -> str:
        return max(self.distribution, key=self.distribution.get)


@dataclass
class CognitiveState:
    version: int
    policies: dict[str, PolicyEntry]
    parent_commitment: str = GENESIS_COMMITMENT
    commitment: str = ""
    update_ref: Optional[str] = None        # tx_id that produced this state

    def body(self) -> dict:
        d = asdict(self)
        d.pop("commitment")
        return d

    def seal(self) -> "CognitiveState":
        self.commitment = "sha256:" + hashlib.sha256(
            canonical_json(self.body())).hexdigest()
        return self

    def policy_for(self, region: str) -> Optional[PolicyEntry]:
        return self.policies.get(region)

    @classmethod
    def genesis(cls, regions: list[str], tools: list[str]) -> "CognitiveState":
        """Uniform policy everywhere: no evidence, no preference."""
        return cls(
            version=0,
            policies={r: PolicyEntry(region=r,
                                     distribution={t: 1.0 / len(tools) for t in tools},
                                     confidence=0.0, updated_tx="genesis")
                      for r in regions},
        ).seal()

    def copy(self) -> "CognitiveState":
        import copy
        return copy.deepcopy(self)
