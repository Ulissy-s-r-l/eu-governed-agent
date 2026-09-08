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

# doc 02 §3.6 confidence policy (versioned state). decay_clock "commits" ⇒ age is
# measured in state versions since the entry was last set/confirmed.
DEFAULT_CONFIDENCE_POLICY = {
    "floor_commit": 0.55,
    "decay_rate": 0.001,
    "decay_clock": "commits",
}


@dataclass
class PolicyEntry:
    region: str
    distribution: dict[str, float]          # strategy/tool -> probability
    confidence: float
    updated_tx: str                         # I4: provenance to committing transaction
    updated_version: int = 0                # state version when set/confirmed (decay anchor)

    def best(self) -> str:
        return max(self.distribution, key=self.distribution.get)


def confidence_of(entry: PolicyEntry, current_version: int,
                  policy: Optional[dict] = None) -> float:
    """Read-time decayed confidence (doc 02 §3.6): the stored `confidence` is
    immutable; decay is computed here from version-age and the decay policy."""
    p = policy or DEFAULT_CONFIDENCE_POLICY
    age = max(0, current_version - entry.updated_version)
    return max(0.0, entry.confidence * (1.0 - p["decay_rate"] * age))


def below_floor(entry: PolicyEntry, current_version: int,
                policy: Optional[dict] = None) -> bool:
    p = policy or DEFAULT_CONFIDENCE_POLICY
    return confidence_of(entry, current_version, p) < p["floor_commit"]


def is_uniform(distribution: dict[str, float], tol: float = 1e-9) -> bool:
    if not distribution:
        return True
    vals = list(distribution.values())
    return max(vals) - min(vals) < tol


@dataclass
class MemoryItem:
    """A semantic_memory item (doc 02 §3.1). `sources` is mandatory, non-empty,
    and is what makes I6 (support independence) enforceable — a consolidation
    names the root experiences it came from."""
    id: str
    type: str                               # fact | concept | relation | consolidation
    content: str
    confidence: float
    sources: list[str]                      # root exp_ids (I4/I6)
    # doc 02 §3.1: active | deprecated | contested. `contested` = a detected
    # contradiction, present-but-NOT-behavioural (read like below-floor), neither
    # fact superseding the other; MUST NOT be auto-resolved by confidence.
    status: str = "active"
    created_tx: str = ""
    last_confirmed_tx: str = ""


@dataclass
class StrategyRecord:
    """A named cross-region strategy (doc 02 §3.5): the 𝒰 of the formal model.

    PARALLEL FORM (see the item-7 PR): a strategy is a cross-region *ordering* of
    tools, NOT a distribution, and NOT yet interposed between policies and tools.
    Today's `policies` still map region → distribution over tool names directly;
    a strategy is applied as a *prior* — its ordering seeds a new region's first
    policy instead of uniform. The full §3.5 shape (policies over strategy IDs,
    two-hop `select_tool`) is deferred: it changes the hot-path read, the I2
    normalization target, and every distribution-asserting test — a schema
    migration, not this feature."""
    id: str
    name: str
    ordering: list[str]                      # tools best→worst (a ranking, not a distribution)
    support_regions: list[str]              # the regions whose committed policies induced it
    confidence: float
    sources: list[str]                      # root exp_ids across support_regions (I4/I6)
    status: str = "active"                  # active | deprecated
    created_tx: str = ""


def distribution_from_ordering(ordering: list[str]) -> dict[str, float]:
    """Derive a per-region distribution from a strategy's ordering, for use as a
    PRIOR when booting a new region (doc 02 §3.5). Linear rank weights (best gets
    n, worst gets 1), normalized. Deliberately NOT rounded — exact fractions keep
    the sum at 1 within float epsilon, respecting the I2 "distributions sum to 1"
    property (the rounding bug the property harness now guards)."""
    n = len(ordering)
    total = n * (n + 1) / 2                  # sum of 1..n
    return {t: (n - i) / total for i, t in enumerate(ordering)}


@dataclass
class CognitiveState:
    version: int
    policies: dict[str, PolicyEntry]
    parent_commitment: str = GENESIS_COMMITMENT
    commitment: str = ""
    update_ref: Optional[str] = None        # tx_id that produced this state
    confidence_policy: dict = field(         # doc 02 §3.6; versioned state
        default_factory=lambda: dict(DEFAULT_CONFIDENCE_POLICY))
    semantic_memory: dict = field(default_factory=dict)   # id -> MemoryItem (doc 02 §3.1)
    strategies: dict = field(default_factory=dict)        # id -> StrategyRecord (doc 02 §3.5)
    # doc 02 §3.8 / doc 04 §5B committed shape, written ONLY by a recalibrate tx:
    #   {"reference": <channel>,                         # designated once, then immutable
    #    "channels": {c: {"reliability": r, "window": {...}}},
    #    "recalibrated_tx": tx_id, "recalibrated_version": v}
    # The gate's trust term reads reliability from HERE (committed) — never from a
    # live CalibrationLoop. Empty {} = never recalibrated ⇒ gate uses self-report.
    evaluation_history: dict = field(default_factory=dict)

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
