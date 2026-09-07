"""I6 support independence (doc 01 Def. 7.4a) — the SINGLE support-counting
function.

A candidate's effective support is the **union of root experience ids** across
everything it cites — its own justification and any corroborating artifact
(a consolidated fact, a strategy, a prior policy). Count the union, never the
sum: a fact grown from a policy's own evidence adds no independent support.

This lives in one function on purpose. Two implementations WILL drift, and the
over-support returns silently the moment one call site sums per-artifact counts
instead of unioning root exp_ids. Every place that weighs evidence — the
admission functional and the validation support terms — MUST call this.
"""
from __future__ import annotations

from typing import Iterable


def root_support(*exp_id_groups: Iterable[str]) -> set[str]:
    """Union of root `exp_id`s across all cited artifacts (I6).

    Each argument is a collection of ledger `exp_id`s: a candidate's
    justification, a fact's `sources`, a strategy's grounding, etc. The result
    is their set union — duplicates across artifacts collapse to one root.
    """
    roots: set[str] = set()
    for group in exp_id_groups:
        roots.update(group)
    return roots


def support_count(*exp_id_groups: Iterable[str]) -> int:
    """|root_support(...)| — the number of independent root experiences."""
    return len(root_support(*exp_id_groups))
