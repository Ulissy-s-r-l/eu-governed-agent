"""Consolidation — evaluated episodes → semantic_memory facts (build-guide §2.1a/d,
doc 02 §3.1).

A cold-path pass over the ledger's evaluated experiences: group by
(region, tool, success-pattern); groups with enough support and a high enough
mean score become `fact`/`consolidation` candidates whose `sources` are exactly
the supporting `exp_id`s (I4). Because it emits candidates that go through the
gate, consolidation inherits admission, validation, provenance, and revert.

Support independence (I6, doc 01 Def. 7.4a): a candidate's `sources` are named
so that a later consumer can dedupe — a fact consolidated from a policy's own
evidence is not independent corroboration of that policy. Enforcement lives in
one place, `ccr.support.root_support`, called by the gate; consolidation's only
duty here is to *name the roots honestly*.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from .experience import Experience
from .ledger import ExperienceLedger


@dataclass
class MemoryCandidate:
    op: str                          # insert | confirm
    type: str                        # fact | consolidation
    content: str
    sources: list[str]               # root exp_ids (I4/I6)
    confidence: float
    region: str
    mem_id: Optional[str] = None     # target item for `confirm`


class Consolidator:
    """Distils repeated evaluated patterns into memory candidates."""

    def __init__(self, ledger: ExperienceLedger,
                 min_support: int = 5, min_conf: float = 0.6):
        self.ledger = ledger
        self.min_support = min_support
        self.min_conf = min_conf

    def _groups(self, region: str) -> dict[str, list[Experience]]:
        groups: dict[str, list[Experience]] = defaultdict(list)
        for e in self.ledger.evaluated():
            if e.action.policy_region != region:
                continue
            tool = e.action.steps[-1].tool
            groups[tool].append(e)
        return groups

    def propose_facts(self, region: str,
                      existing: Optional[dict] = None) -> list[MemoryCandidate]:
        """Groups with >= min_support and mean score >= min_conf become fact
        candidates. If an active fact for the same (region, tool) already exists
        (`existing`: id -> MemoryItem), emit a `confirm` instead of a duplicate
        `insert` (build-guide §2.1d re-confirmation)."""
        out: list[MemoryCandidate] = []
        existing = existing or {}
        for tool, group in self._groups(region).items():
            if len(group) < self.min_support:
                continue
            mean = sum(e.evaluation.score for e in group) / len(group)
            if mean < self.min_conf:
                continue
            sources = [e.exp_id for e in group]
            content = f"tool:{tool} reliable in region:{region}"
            prior = next((mid for mid, m in existing.items()
                          if getattr(m, "content", None) == content
                          and getattr(m, "status", "") == "active"), None)
            if prior is not None:
                out.append(MemoryCandidate(op="confirm", type="consolidation",
                                           content=content, sources=sources,
                                           confidence=round(mean, 4), region=region,
                                           mem_id=prior))
            else:
                out.append(MemoryCandidate(op="insert", type="consolidation",
                                           content=content, sources=sources,
                                           confidence=round(mean, 4), region=region))
        return out
