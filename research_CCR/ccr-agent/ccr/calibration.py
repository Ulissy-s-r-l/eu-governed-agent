"""Per-channel reliability calibration (build-guide §2.2, doc 02 §3.8, doc 07 §2.2a,
doc 04 §5B).

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

CALIBRATION ADVISES; IT DOES NOT STEER (doc 04 §5B). This loop is a *live* object.
Its numbers become behavioural — readable by the admission gate's trust term —
ONLY through a committed `recalibrate` transaction (`LearningEngine.recalibrate`),
which reads `to_state()` and writes it into `evaluation_history`. An uncommitted
loop is "an account of reliability, not a belief about it": the gate never reads it
directly. The window this loop retains per channel (raw agreement/disagreement
tallies + the exp_ids observed) is what §5B's first invariant recomputes from — a
recalibrate that cannot be re-derived from its recorded window is rejected, so
counts alone would not suffice.
"""
from __future__ import annotations

from typing import Callable, Optional

# The reference is authoritative by construction; its "reliability" is a fixed
# sentinel ceiling, not an observed rate. No calibrated channel may outrank it
# (doc 04 §5B invariant 3).
REFERENCE_RELIABILITY = 0.99


class CalibrationLoop:
    def __init__(self, reference_channel: str, prior: tuple[float, float] = (1.0, 1.0)):
        if not reference_channel:
            raise ValueError(
                "CalibrationLoop requires a designated reference channel (doc 07 §2.2a). "
                "Without one, calibration degrades to consensus/imitation — see the module "
                "docstring and ADR-0009. Do not instantiate against a non-reference domain.")
        self.reference = reference_channel
        self._prior = prior
        # OBSERVATION WINDOW per channel (doc 04 §5B): raw tallies + exp_id list,
        # NOT just α/β — the invariant re-check recomputes reliability from these.
        self._agree: dict[str, int] = {}
        self._disagree: dict[str, int] = {}
        self._exps: dict[str, list[str]] = {}

    def observe(self, channel: str, agreed: bool,
                exp_id: Optional[str] = None) -> None:
        """One verdict of `channel` compared to the reference on the same
        experience. `exp_id`, when given, is recorded in the window as provenance."""
        if agreed:
            self._agree[channel] = self._agree.get(channel, 0) + 1
        else:
            self._disagree[channel] = self._disagree.get(channel, 0) + 1
        if exp_id is not None:
            self._exps.setdefault(channel, []).append(exp_id)

    def _observed(self, channel: str) -> bool:
        return channel in self._agree or channel in self._disagree

    def reliability(self, channel: str) -> Optional[float]:
        """Beta posterior mean of agreement with the reference. The reference is
        authoritative by construction. Returns None for a channel never observed
        (undefined, NOT a default — doc 02 §3.8: a consumer must not read an
        unobserved channel as calibrated)."""
        if channel == self.reference:
            return REFERENCE_RELIABILITY
        if not self._observed(channel):
            return None
        return recompute_reliability(self.window(channel))

    def verdicts(self, channel: str) -> int:
        """Raw observation count in the window (excludes the Beta prior)."""
        return self._agree.get(channel, 0) + self._disagree.get(channel, 0)

    def window(self, channel: str) -> dict:
        """The recorded observation window for `channel` — the provenance a
        `recalibrate` tx carries and re-checks against (doc 04 §5B)."""
        return {
            "agreements": self._agree.get(channel, 0),
            "disagreements": self._disagree.get(channel, 0),
            "exp_ids": list(self._exps.get(channel, [])),
            "prior": list(self._prior),
        }

    def to_state(self) -> dict:
        """Committed `evaluation_history` shape (doc 02 §3.8, doc 04 §5B):

            {"reference": <channel>,
             "channels": {c: {"reliability": r, "window": {...}}}}

        The reference is named so a later recalibrate can verify it is unchanged;
        each channel carries its window so the invariant re-check can recompute."""
        chans = set(self._agree) | set(self._disagree) | {self.reference}
        return {
            "reference": self.reference,
            "channels": {
                c: {"reliability": self.reliability(c),
                    "window": self.window(c)}
                for c in chans
            },
        }


def recompute_reliability(window: dict) -> float:
    """Re-derive a channel's Beta posterior-mean reliability from its recorded
    observation window. This is the function doc 04 §5B's invariant 1 runs: a
    submitted reliability MUST equal this recomputation from the recorded window,
    or the recalibrate is rejected."""
    a = window["agreements"]
    d = window["disagreements"]
    pa, pb = window.get("prior", (1.0, 1.0))
    return (a + pa) / (a + d + pa + pb)


def reliability_from_state(evaluation_history: Optional[dict]) -> Callable[[str], Optional[float]]:
    """The gate's trust term reads reliability from COMMITTED state ONLY (doc 04
    §5B). This returns the `channel -> reliability|None` callable the engine wires
    into the gate on every commit path — sourced from `state.evaluation_history`,
    never from a live loop. An unrecalibrated state (no `channels`) yields a
    callable that returns None for every channel, so the gate falls back to
    self-reported confidence exactly as before any recalibrate."""
    channels = (evaluation_history or {}).get("channels", {})

    def _reliability_of(channel: Optional[str]) -> Optional[float]:
        if channel is None:
            return None
        entry = channels.get(channel)
        return entry.get("reliability") if entry else None

    return _reliability_of
