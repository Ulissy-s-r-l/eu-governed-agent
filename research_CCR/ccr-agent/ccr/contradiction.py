"""Contradiction detection over semantic_memory (doc 02 §3.1 — the `contested`
status).

SCOPE IS DELIBERATE AND NARROW. "Same subject, incompatible object" is undecidable
over free-text content and NLP-hard in general; it is decidable ONLY per fact-type,
and only for a type whose content carries a parseable structured key with a
polarity. The consolidation fact is such a type — and the ONLY one this codebase
emits (`Consolidator`, doc 02 §3.1):

    tool:<T> reliable in region:<R>      (sense = reliable)
    tool:<T> unreliable in region:<R>    (sense = unreliable)

A contradiction is two ACTIVE items with the SAME (region, tool) key and OPPOSITE
sense — and nothing else. Anything that does not parse into (region, tool, sense)
is NEVER flagged. A general detector that guessed at incompatibility over free text
would false-flag two genuinely-reliable tools for one region, a superseded
predecessor beside its successor, paraphrases, and differently-scoped claims —
manufacturing contested pairs. **A contested state people learn to ignore is worse
than no contested state**, so this detector refuses everything it cannot decide.

The claim templates live HERE so the emitter (`Consolidator`) and the parser cannot
drift: `Consolidator` builds content with `claim_content`, this module parses it
with `parse_claim`.

MUST NOT AUTO-RESOLVE (doc 02 §3.1). Detection's only authority is to MARK a
conflict — set both members `contested`, making neither behavioural. It never
demotes the lower-confidence item, never picks a winner. Resolution is a later
transaction (a supersede) or a human (a cgr.cosign.v1 co-signature), not this code.

THE CONTRADICTION CASE IS MANUFACTURED — AND THE MACHINERY IS NOT. Say both, because
each half alone misleads:

  - MANUFACTURED: the `Consolidator` emits one monotone-positive shape, so no two
    facts it emits in the wild can contradict each other — a region can have several
    reliable tools. The `unreliable` claim exists ONLY so this detector is
    reachable; the system has NOT observed a contradiction. "Contradiction
    detection: built" without this sentence reads as evidence a contradiction was
    found. It was not — the detector exercises a case constructed for it.
  - NOT MANUFACTURED: mark-both, the non-behavioural read (`behavioural_memory`),
    reconcile-on-resolution (`reconcile_contested`), and no-auto-resolve are real
    and load-bearing. They will matter the first time a contested pair arrives from
    a NON-manufactured source — a second emitter, human-asserted facts via cosign,
    a merged branch. Do not read the manufactured trigger as licence to rip the
    detector out as dead code; it is the mechanism waiting for that first real pair.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

SENSE_RELIABLE = "reliable"
SENSE_UNRELIABLE = "unreliable"
_OPPOSITE = {SENSE_RELIABLE: SENSE_UNRELIABLE, SENSE_UNRELIABLE: SENSE_RELIABLE}

# anchored: a decorated variant (e.g. "... (v2)") does NOT parse and is not flagged.
_CLAIM_RE = re.compile(
    r"^tool:(?P<tool>\S+) (?P<sense>reliable|unreliable) in region:(?P<region>\S+)$")


def claim_content(tool: str, region: str, sense: str = SENSE_RELIABLE) -> str:
    """The one place a consolidation claim string is formed (emitter + parser share it)."""
    return f"tool:{tool} {sense} in region:{region}"


def parse_claim(content: Optional[str]) -> Optional[tuple[str, str, str]]:
    """(region, tool, sense) for a structured consolidation claim, else None.
    None is the detector's refusal to decide — an unparseable item is never a
    contradiction party."""
    m = _CLAIM_RE.match(content or "")
    if not m:
        return None
    return (m["region"], m["tool"], m["sense"])


def find_contradictions(semantic_memory: dict) -> list[tuple[str, str]]:
    """All (reliable_id, unreliable_id) pairs among ACTIVE, parseable items that
    share a (region, tool) key with opposite sense. Pure — reads, marks nothing."""
    by_key: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list))
    for mid, item in semantic_memory.items():
        if getattr(item, "status", None) != "active":
            continue
        parsed = parse_claim(getattr(item, "content", ""))
        if parsed is None:
            continue
        region, tool, sense = parsed
        by_key[(region, tool)][sense].append(mid)

    pairs: list[tuple[str, str]] = []
    for senses in by_key.values():
        for a in senses.get(SENSE_RELIABLE, []):
            for b in senses.get(SENSE_UNRELIABLE, []):
                pairs.append((a, b))
    return pairs


def detect_and_mark(state) -> list[tuple[str, str]]:
    """Mark BOTH members of every detected conflict `contested` (doc 02 §3.1).
    Mutates `state.semantic_memory` in place; returns the pairs marked.

    This is the ONLY behavioural effect of detection: present-but-not-behavioural.
    It never touches `confidence` and never deprecates either side — resolution is
    a separate, later transaction. Already-`contested` items are excluded from
    `find_contradictions` (only `active` items are parties), so re-running is
    idempotent and does not re-pair resolved history."""
    pairs = find_contradictions(state.semantic_memory)
    for a, b in pairs:
        state.semantic_memory[a].status = "contested"
        state.semantic_memory[b].status = "contested"
    return pairs


def reconcile_contested(state) -> list[str]:
    """Return a `contested` item to `active` once it has no live conflicting
    partner left (doc 02 §3.1 resolution). A partner is live if it is `active` or
    `contested`; a `deprecated` partner (superseded away) no longer conflicts.

    Without this, `contested` is a one-way ratchet and every long-lived belief
    eventually goes non-behavioural by attrition — the ignore-the-contested-state
    failure arriving slowly. Only ever moves contested→active (never demotes),
    so it cannot become a back-door auto-resolution."""
    sm = state.semantic_memory
    restored: list[str] = []
    for mid, item in sm.items():
        if getattr(item, "status", None) != "contested":
            continue
        parsed = parse_claim(getattr(item, "content", ""))
        if parsed is None:
            continue
        region, tool, sense = parsed
        opposite = (region, tool, _OPPOSITE[sense])
        has_live_conflict = any(
            oid != mid
            and getattr(o, "status", None) in ("active", "contested")
            and parse_claim(getattr(o, "content", "")) == opposite
            for oid, o in sm.items())
        if not has_live_conflict:
            item.status = "active"
            restored.append(mid)
    return restored


def behavioural_memory(state) -> dict:
    """The read-path view: only `active` items drive behaviour. `contested` items
    are present-but-not-behavioural — the memory analogue of the policy read-time
    floor (doc 02 §3.6): held in state, addressable, diffable, but excluded from
    the set a decision reads, exactly as a below-floor policy entry is."""
    return {mid: item for mid, item in state.semantic_memory.items()
            if getattr(item, "status", None) == "active"}
