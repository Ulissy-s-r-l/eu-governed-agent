"""Tool-selection simulator — CCR doc 06 §3.1.

Environment with hidden, context-dependent tool reliabilities. The agent
picks a tool per episode; the simulator returns ground-truth success.
This is the benchmark task Phase 1 instruments: every episode becomes an
experience; the ground truth feeds the deterministic evaluator channel.
"""

from __future__ import annotations

import hashlib
import random


class ToolSelectionSimulator:
    """N tools x M context regions; each (tool, region) pair has a hidden
    success probability. An episode draws a region, the agent picks a tool,
    and the environment samples the outcome."""

    def __init__(self, tools: list[str], regions: list[str], seed: int = 7,
                 noise: float = 0.05):
        self.tools = tools
        self.regions = regions
        self.noise = noise
        # Deterministic hidden reliability table derived from the seed.
        rng = random.Random(seed)
        self._reliability: dict[tuple[str, str], float] = {}
        for t in tools:
            for r in regions:
                self._reliability[(t, r)] = round(rng.uniform(0.1, 0.95), 3)

    def reliability(self, tool: str, region: str) -> float:
        return self._reliability[(tool, region)]

    def best_tool(self, region: str) -> str:
        return max(self.tools, key=lambda t: self._reliability[(t, region)])

    def run_episode(self, tool: str, region: str, episode: int) -> dict:
        if tool not in self.tools:
            raise ValueError(f"unknown tool: {tool}")
        if region not in self.regions:
            raise ValueError(f"unknown region: {region}")
        p = self._reliability[(tool, region)]
        # Deterministic per (episode, tool, region) so runs are reproducible.
        draw = int(hashlib.sha256(f"{episode}|{tool}|{region}".encode()).hexdigest(), 16) % 10_000 / 10_000
        success = draw < p
        return {
            "success": success,
            "region": region,
            "tool": tool,
            "true_reliability": p,
            "optimal": tool == self.best_tool(region),
        }

    def optimal_rate(self) -> float:
        """Expected success of the per-region optimal policy (upper bound)."""
        return sum(max(self._reliability[(t, r)] for t in self.tools)
                   for r in self.regions) / len(self.regions)

    def uniform_rate(self) -> float:
        """Expected success of uniform-random tool selection (System A floor)."""
        return sum(self._reliability.values()) / len(self._reliability)


class NaiveAgent:
    """System A analogue: no memory, picks a tool by fixed preference order."""

    def __init__(self, tools: list[str]):
        self.tools = tools

    def select_tool(self, region: str) -> str:
        return self.tools[0]      # always the same tool — context-blind
