"""Experience Capture — CCR doc 00 §6.1, doc 04 stage 1.

Instruments any agent loop through two hooks (doc 00 §4.2):
  emit()    — record raw material of an experience (hot path, cheap)
  seal()    — attach evaluation and hand the record to the ledger

Design: fidelity under non-interference. emit() does no model calls and no
hashing beyond digests; all enrichment happens off the hot path.
"""

from __future__ import annotations

from typing import Any, Optional

from .experience import (
    Experience, ContextBlock, GoalBlock, ActionBlock, ActionStep,
    OutcomeBlock, content_hash,
)
from .evaluator import OutcomeEvaluator
from .ledger import ExperienceLedger


class ExperienceCapture:
    """The bridge between an agent runtime and the Experience Ledger."""

    def __init__(self, ledger: ExperienceLedger, evaluator: Optional[OutcomeEvaluator] = None,
                 agent_ref: str = "did:gns:local-dev",
                 environment_ref: str = "env:default"):
        self.ledger = ledger
        self.evaluator = evaluator
        self.agent_ref = agent_ref
        self.environment_ref = environment_ref

    # -- hot-path hook ------------------------------------------------------

    def emit(self,
             state_summary: str,
             goal: str,
             tool: str,
             args: dict[str, Any],
             result: dict[str, Any],
             outcome_observed: str,
             signals: Optional[dict[str, Any]] = None,
             strategy_ref: Optional[str] = None,
             policy_region: Optional[str] = None,
             goal_source: str = "delegation",
             goal_id: Optional[str] = None,
             authority_scope: Optional[str] = None,
             state_version: Optional[str] = None) -> Experience:
        """Capture one decision cycle. Cheap: digests args/result, no evaluation."""
        step = ActionStep(
            tool=tool,
            args_digest=content_hash(args),
            result_digest=content_hash(result),
        )
        exp = Experience(
            context=ContextBlock(
                state_summary=state_summary,
                environment_ref=self.environment_ref,
                state_version=state_version,
            ),
            goal=GoalBlock(statement=goal, source=goal_source,
                           **({"goal_id": goal_id} if goal_id else {})),
            action=ActionBlock(strategy_ref=strategy_ref, policy_region=policy_region,
                               steps=[step], authority_scope=authority_scope),
            outcome=OutcomeBlock(observed=outcome_observed, signals=signals or {}),
            agent_ref=self.agent_ref,
        )
        return exp

    # -- cold-path seal -----------------------------------------------------

    def seal(self, exp: Experience, evaluate: bool = True) -> Experience:
        """Evaluate (if an evaluator is attached) and append to the ledger.
        Returns the finalized, signed, chained record."""
        if evaluate and self.evaluator is not None and not exp.is_evaluated():
            exp.evaluation = self.evaluator.evaluate(exp)
        return self.ledger.append(exp)

    def capture(self, *args, **kwargs) -> Experience:
        """Convenience: emit + seal in one call (for simple loops)."""
        return self.seal(self.emit(*args, **kwargs))
