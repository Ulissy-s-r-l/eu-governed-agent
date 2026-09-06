"""Outcome Evaluator — CCR doc 00 §6.7, doc 01 Def. 5.1.

Architecturally separate from the acting agent (P4): the component that
benefits from a positive evaluation never issues it.

Each evaluator emits an EvaluationBlock with a verdict, score, AND confidence;
confidence travels downstream into admission (Phase 4) and committed state.
"""

from __future__ import annotations

from typing import Protocol

from .experience import Experience, EvaluationBlock


class OutcomeEvaluator(Protocol):
    channel_id: str
    def evaluate(self, exp: Experience) -> EvaluationBlock: ...


class SimulatorGroundTruthEvaluator:
    """Deterministic channel: reads the simulator's ground-truth signal
    (outcome.signals['success']) — the highest-reliability channel."""

    channel_id = "simulator-ground-truth"

    def evaluate(self, exp: Experience) -> EvaluationBlock:
        ok = bool(exp.outcome.signals.get("success", False))
        return EvaluationBlock(
            verdict="success" if ok else "failure",
            score=1.0 if ok else 0.0,
            confidence=0.99,                       # deterministic ground truth
            channels=[self.channel_id],
            attribution={"load_bearing": ["action.steps[-1]"]},
            evaluator_ref=f"eval:{self.channel_id}",
        )


class SelfReportEvaluator:
    """Low-trust channel: takes the agent's own claim about the outcome.
    Confidence is capped low — this is the channel an attacker games (doc 07 §2.2)."""

    channel_id = "agent-self-report"

    def __init__(self, cap: float = 0.3):
        self.cap = cap

    def evaluate(self, exp: Experience) -> EvaluationBlock:
        claimed = bool(exp.outcome.signals.get("agent_claims_success", False))
        return EvaluationBlock(
            verdict="success" if claimed else "failure",
            score=1.0 if claimed else 0.0,
            confidence=min(self.cap, 1.0),
            channels=[self.channel_id],
            attribution={},
            evaluator_ref=f"eval:{self.channel_id}",
        )


class CompositeEvaluator:
    """Multi-channel evaluator (doc 00 §6.7): verdicts combined by
    confidence-weighted vote; a single weak channel cannot dominate."""

    channel_id = "composite"

    def __init__(self, evaluators: list[OutcomeEvaluator]):
        self.evaluators = evaluators

    def evaluate(self, exp: Experience) -> EvaluationBlock:
        blocks = [e.evaluate(exp) for e in self.evaluators]
        total_w = sum(b.confidence for b in blocks) or 1.0
        score = sum(b.score * b.confidence for b in blocks) / total_w
        verdict = ("success" if score >= 0.75 else
                   "failure" if score <= 0.25 else "mixed")
        channels = [c for b in blocks for c in b.channels]
        return EvaluationBlock(
            verdict=verdict,
            score=round(score, 4),
            confidence=round(min(0.99, total_w / len(blocks)), 4),
            channels=channels,
            attribution={"per_channel": {b.channels[0]: b.score for b in blocks}},
            evaluator_ref=f"eval:{self.channel_id}",
        )
