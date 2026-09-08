"""Strategy induction — cross-region generalization (doc 02 §3.5, build-guide §2.3,
item 7).

PARALLEL FORM (design answer, see the item-7 PR). §3.5's end state is
policies-over-strategy-IDs with a two-hop `select_tool`; that is a schema migration
(hot-path read, I2 target, every distribution-asserting test). This build delivers
the *learning value* of §3.5 — reusing what worked in one region as a prior in
another — WITHOUT touching the hot path: a strategy is a cross-region tool ORDERING,
induced when the same ordering has committed in ≥ k regions, and applied by BOOTING
a new region's first policy from that ordering instead of uniform. Interpose later.

Induction reads COMMITTED policies (the orderings that actually won) and the ledger
(the experiences that justify them, for the gate). A strategy generalized from two
regions is an anecdote with a name — below k, nothing is proposed.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .ledger import ExperienceLedger
from .state import CognitiveState, PolicyEntry, is_uniform


@dataclass
class StrategyCandidate:
    name: str
    ordering: list[str]                      # tools best→worst
    support_regions: list[str]
    sources: list[str]                       # root exp_ids across support_regions (I4/I6)
    confidence: float


def ordering_of(entry: PolicyEntry) -> list[str]:
    """A policy entry's tool ordering, best→worst. Ties broken by tool name so the
    ordering is deterministic and two regions with the same preferences group."""
    return sorted(entry.distribution, key=lambda t: (-entry.distribution[t], t))


class StrategyInducer:
    """Proposes cross-region strategy candidates from committed policies."""

    def __init__(self, ledger: ExperienceLedger, k: int = 3):
        self.ledger = ledger
        self.k = k                            # min regions sharing an ordering

    def _region_exps(self, region: str) -> list[str]:
        return [e.exp_id for e in self.ledger.evaluated()
                if e.action.policy_region == region]

    def propose(self, state: CognitiveState) -> list[StrategyCandidate]:
        """Group LEARNED (non-uniform) regions by identical ordering; a group of
        ≥ k regions becomes one candidate. `sources` is the union of the group's
        root exp_ids — the gate counts support over that union (I6), never a
        per-region sum."""
        by_ordering: dict[tuple, list[str]] = defaultdict(list)
        for region, entry in state.policies.items():
            if is_uniform(entry.distribution):
                continue                      # never learned — no ordering to generalize
            by_ordering[tuple(ordering_of(entry))].append(region)

        out: list[StrategyCandidate] = []
        for ordering, regions in by_ordering.items():
            if len(regions) < self.k:
                continue                      # below k: an anecdote with a name
            regions = sorted(regions)
            # union of root exp_ids across the supporting regions (dedup by set)
            sources = sorted({eid for r in regions for eid in self._region_exps(r)})
            confidence = sum(state.policies[r].confidence for r in regions) / len(regions)
            out.append(StrategyCandidate(
                name="→".join(ordering), ordering=list(ordering),
                support_regions=regions, sources=sources,
                confidence=round(confidence, 4)))
        return out
