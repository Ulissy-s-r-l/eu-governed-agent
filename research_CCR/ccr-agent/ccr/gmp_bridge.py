"""GMP bridge — map CCR experiences into GRAFOMEM GMP v0.2 durable facts.

GMP atom: fact = (predicate, subject, object, valid_from), tenant-scoped,
content-derived identity  fact_id = BLAKE2b-128(tenant ‖ P ‖ S ‖ O ‖ valid_from).

Mapping (doc 03 → GMP):
  subject    = exp_id          (the experience is the subject of discourse)
  predicate  = a fact aspect   (goal / action / outcome / evaluation / provenance)
  object     = the aspect payload (JSON)
  valid_from = captured_at     (event time — bi-temporal ready)

One experience becomes a small constellation of facts, so GMP's native
supersession (evaluation updates) and audit operations apply per aspect.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from .experience import Experience, canonical_json
from .ledger import LedgerBackend, LedgerEntry

GMP_DEFAULT_TENANT = "ccr:default"


@dataclass
class GMPFact:
    predicate: str
    subject: str
    obj: str
    valid_from: str
    tenant_id: str = GMP_DEFAULT_TENANT
    importance: float = 0.5
    sequence: int = 0
    valid_until: Optional[str] = None
    superseded_by: Optional[str] = None

    @property
    def fact_id(self) -> str:
        """GMP §1.2: tenant-scoped, content-derived identity (BLAKE2b-128)."""
        blob = f"{self.tenant_id}‖{self.predicate}‖{self.subject}‖{self.obj}‖{self.valid_from}"
        return "blake2b128:" + hashlib.blake2b(blob.encode(), digest_size=16).hexdigest()


def experience_to_facts(exp: Experience, tenant_id: str = GMP_DEFAULT_TENANT) -> list[GMPFact]:
    """Explode one experience record into its GMP fact constellation."""
    s = exp.exp_id or exp.compute_id()
    vf = exp.captured_at

    def fact(pred: str, payload: Any, importance: float = 0.5) -> GMPFact:
        return GMPFact(predicate=pred, subject=s,
                       obj=canonical_json(payload).decode(), valid_from=vf,
                       tenant_id=tenant_id, importance=importance, sequence=exp.seq)

    facts = [
        fact("ccr:goal",    {"statement": exp.goal.statement, "source": exp.goal.source}, 0.6),
        fact("ccr:context", {"state_summary": exp.context.state_summary,
                             "environment_ref": exp.context.environment_ref,
                             "state_version": exp.context.state_version}, 0.5),
        fact("ccr:action",  {"strategy_ref": exp.action.strategy_ref,
                             "policy_region": exp.action.policy_region,
                             "tools": [st.tool for st in exp.action.steps]}, 0.7),
        fact("ccr:outcome", {"observed": exp.outcome.observed,
                             "signals": exp.outcome.signals}, 0.8),
        fact("ccr:provenance", {"captured_by": exp.provenance.captured_by,
                                "prev_hash": exp.provenance.prev_hash,
                                "seq": exp.seq}, 0.9),
    ]
    if exp.evaluation is not None:
        facts.append(fact("ccr:evaluation", {
            "verdict": exp.evaluation.verdict,
            "score": exp.evaluation.score,
            "confidence": exp.evaluation.confidence,
            "channels": exp.evaluation.channels,
        }, importance=0.9))
    return facts


class GMPInMemoryBackend:
    """Minimal in-memory GMP-style store: write / retrieve / audit / flush /
    supersede, with tenant scoping. Used to test the bridge without a server;
    swap for the Grafomem Cloud GMP endpoint in production (same fact model)."""

    def __init__(self, tenant_id: str = GMP_DEFAULT_TENANT):
        self.tenant_id = tenant_id
        self._facts: dict[str, GMPFact] = {}

    # GMP §2 operations (subset used by the bridge)
    def write(self, fact: GMPFact) -> str:
        self._facts[fact.fact_id] = fact          # idempotent by identity (GMP §1.2)
        return fact.fact_id

    def supersede(self, old_ref: str, fact: GMPFact) -> str:
        if old_ref in self._facts:
            self._facts[old_ref].superseded_by = fact.fact_id
        return self.write(fact)

    def retrieve(self, predicate: Optional[str] = None,
                 subject: Optional[str] = None) -> list[GMPFact]:
        out = []
        for f in self._facts.values():
            if f.tenant_id != self.tenant_id or f.superseded_by:
                continue
            if predicate and f.predicate != predicate:
                continue
            if subject and f.subject != subject:
                continue
            out.append(f)
        return sorted(out, key=lambda f: f.sequence)

    def audit(self) -> Iterator[GMPFact]:
        """All facts incl. superseded (GMP §2 audit)."""
        return iter(sorted(self._facts.values(), key=lambda f: f.sequence))

    def flush(self) -> None:
        return None


class GMPFactBridge(LedgerBackend):
    """LedgerBackend fan-out: every appended experience also lands in a GMP
    store as a fact constellation. Read path stays on the local ledger;
    GMP is the durable, queryable, tenant-scoped evidence tier."""

    def __init__(self, store: GMPInMemoryBackend):
        self.store = store
        self.facts_written = 0

    def append(self, line: str) -> None:
        entry = LedgerEntry.from_line(line)
        if entry.kind != "experience":
            return
        exp = Experience.from_dict(entry.payload)
        for f in experience_to_facts(exp, tenant_id=self.store.tenant_id):
            self.store.write(f)
            self.facts_written += 1

    def read_all(self) -> list[str]:
        return []          # bridge is write-only; primary backend owns reads
