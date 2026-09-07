"""Per-channel reliability calibration (build-guide §2.2, doc 02 §3.8, doc 07 §2.2a).

Replaces a channel's SELF-REPORTED confidence with an OBSERVED reliability — the
standing rule "trust the channel, not the account" made operational.

    reliability(c) = agreement rate of channel c's verdicts with a DESIGNATED
                     REFERENCE CHANNEL, as a Beta(α, β) posterior mean.

THE REFERENCE IS EXTRINSIC — AND SO IS THE LIMIT (doc 07 §2.2a). Calibration does
not remove the trust root; it RELOCATES it, from N unaudited self-reports to ONE
auditable reference. That reference is trusted for reasons OUTSIDE this system:
deterministic tests whose correctness is definitional, delayed confirmed
real-world outcomes, or a vetted oracle. In the simulator,
`SimulatorGroundTruthEvaluator` is such a reference by construction.

**Where no reference exists, this loop is UNBUILDABLE — do not instantiate it.**
A reference exists iff the domain produces delayed, independent, outcome-grounded
signals. **AML has none (Ulissy-s-r-l ADR-0009: no correctness signal arrives)**:
there, "found incorrect" could only mean "disagrees with the other channels," so
the loop would converge on inter-channel *consensus* — imitation, not correctness,
the ADR-0009 proxy-label circularity. Calibrating against a non-reference channel
and reading the result as reliability is exactly the error this module exists to
prevent. This is the same extrinsic-trust limit as identity assurance (ADR-0009
gap 3a), appearing at the evaluation layer.
"""
from __future__ import annotations

from typing import Optional


class CalibrationLoop:
    def __init__(self, reference_channel: str, prior: tuple[float, float] = (1.0, 1.0)):
        if not reference_channel:
            raise ValueError(
                "CalibrationLoop requires a designated reference channel (doc 07 §2.2a). "
                "Without one, calibration degrades to consensus/imitation — see the module "
                "docstring and ADR-0009. Do not instantiate against a non-reference domain.")
        self.reference = reference_channel
        self._a: dict[str, float] = {}       # agreements + prior_a
        self._b: dict[str, float] = {}       # disagreements + prior_b
        self._prior = prior

    def observe(self, channel: str, agreed: bool) -> None:
        """One verdict of `channel` compared to the reference on the same experience."""
        a = self._a.get(channel, self._prior[0])
        b = self._b.get(channel, self._prior[1])
        if agreed:
            a += 1.0
        else:
            b += 1.0
        self._a[channel], self._b[channel] = a, b

    def reliability(self, channel: str) -> Optional[float]:
        """Beta posterior mean of agreement with the reference. The reference is
        authoritative by construction. Returns None for a channel never observed
        (undefined, NOT a default — doc 02 §3.8: a consumer must not read an
        unobserved channel as calibrated)."""
        if channel == self.reference:
            return 0.99
        if channel not in self._a:
            return None
        a, b = self._a[channel], self._b[channel]
        return a / (a + b)

    def verdicts(self, channel: str) -> int:
        a = self._a.get(channel, self._prior[0])
        b = self._b.get(channel, self._prior[1])
        return int(a + b - (self._prior[0] + self._prior[1]))

    def to_state(self) -> dict:
        """`evaluation_history.channels` shape (doc 02 §3.8): channel -> {reliability, verdicts}."""
        chans = set(self._a) | {self.reference}
        return {c: {"reliability": self.reliability(c), "verdicts": self.verdicts(c)}
                for c in chans}
