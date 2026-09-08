"""GMP bridge — map CCR EVIDENCE into GRAFOMEM GMP v0.2 durable facts.

GMP atom: fact = (predicate, subject, object, valid_from), tenant-scoped,
content-derived identity  fact_id = BLAKE2b-128(tenant ‖ P ‖ S ‖ O ‖ valid_from).

The bridge maps the doc 03 §3.2 EVIDENCE record kinds — and only those. Per doc 03
§3.4 / ADR-0010 the durable tier holds evidence, never CSO content:

  experience   → constellation: subject = exp_id, predicate = aspect
                 (goal/context/action/outcome/evaluation/provenance).
  gate_decision→ subject = tx_id, predicate "ccr:gate_decision", object = the
                 admission/validation audit (§3.2 "auditable, including its
                 refusals"); plus a "ccr:gate_decision/on" link naming the tx's
                 cited exp_ids so the three-way join (experience ↔ gate_decision ↔
                 policy provenance) resolves ON THE DURABLE TIER, not only locally.
  checkpoint   → subject = checkpoint_id, predicate "ccr:checkpoint", object =
                 {merkle_root, seq range, signature ref}.
  annotation   → NOT mapped. Nothing writes an annotation record today (ledger.py:
                 "not yet needed in Phase 1"); designing a mapping for a phantom is
                 exactly the CSO-content-mirror mistake in a different costume. Add
                 it when a writer exists.

THE LINE BETWEEN EVIDENCE AND MIRROR (the rule that keeps this on the right side of
ADR-0010): a gate_decision's `delta` may contain a strategy ordering or a policy
distribution. That is **evidence about a change** and belongs in the OBJECT of the
gate_decision fact. The SUBJECT stays the `tx_id` — never a CSO component id — and no
predicate is `ccr:mem/*`. A fact whose subject is a mem/policy/strategy/channel id, or
whose predicate mirrors a belief, is a CSO mirror (item C) and is forbidden;
`tests/test_durable_tier.py` guards this.
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


def gate_decision_to_facts(payload: dict,
                           tenant_id: str = GMP_DEFAULT_TENANT) -> list[GMPFact]:
    """A gate_decision record → its audit fact (§3.2 "auditable, including its
    refusals"); a `ccr:gate_decision/on` link naming the cited exp_ids (when the tx
    cited evidence); and a `ccr:gate_decision/caused` fact per attributed causal edge
    the tx inserted (doc 05 §3), so the doc 03 §6 causal hop closes on the durable
    tier. Subject is always the tx_id — the delta's CSO content (a distribution, a
    strategy ordering, an edge) rides in the OBJECT as evidence about the change,
    never as a subject or a belief predicate (doc 03 §3.4 / ADR-0010)."""
    tx_id = payload["tx_id"]
    vf = payload.get("created_at", "")
    delta = payload.get("delta") or {}
    audit = {
        "tx_type": payload.get("tx_type"),
        "status": payload.get("status"),
        "admission": payload.get("admission"),           # verdict + component values
        "validation_verdict": (payload.get("validation") or {}).get("verdict"),
        "parent_state": payload.get("parent_state"),
        "new_commitment": payload.get("new_commitment"),  # None for a rejected tx
        "delta": delta,                                  # what changed — EVIDENCE about the
    }                                                     # change (may hold a distribution/
    #                                                     ordering); the subject stays tx_id.
    facts = [GMPFact(predicate="ccr:gate_decision", subject=tx_id,
                     obj=canonical_json(audit).decode(), valid_from=vf,
                     tenant_id=tenant_id, importance=0.9)]
    # cited evidence: policy commits carry `justification`; memory/strategy carry
    # `sources`. Present on rejections too (both set delta before the gate check),
    # so the join resolves for what the system DECLINED to learn, not only commits.
    cited = delta.get("justification") or delta.get("sources") or []
    if cited:
        facts.append(GMPFact(predicate="ccr:gate_decision/on", subject=tx_id,
                             obj=canonical_json(sorted(cited)).decode(), valid_from=vf,
                             tenant_id=tenant_id, importance=0.9))
    # causal hop (doc 05 §3): the attributed edges this tx inserted, so the doc 03 §6
    # `causal_basis → cg-edge` walk closes on the durable tier. Subject stays the
    # tx_id; `cited_exp` (the outcome node's ledger ref) lets a consumer hop to the
    # experience facts. The edge is EVIDENCE about a change; never a CSO subject.
    for edge in (payload.get("causal") or []):
        cited_exp = str(edge.get("from", "")).split("cg:outcome:", 1)[-1]
        facts.append(GMPFact(
            predicate="ccr:gate_decision/caused", subject=tx_id,
            obj=canonical_json({
                "edge_id": edge.get("edge_id"), "rel": edge.get("rel"),
                "from": edge.get("from"), "to": edge.get("to"),
                "attributed_by": edge.get("attributed_by"),
                "attribution_stage": edge.get("attribution_stage"),
                "uncalibrated": edge.get("uncalibrated"),
                "cited_exp": cited_exp,
            }).decode(), valid_from=vf, tenant_id=tenant_id, importance=0.9))
    return facts


def checkpoint_to_fact(payload: dict,
                       tenant_id: str = GMP_DEFAULT_TENANT) -> GMPFact:
    """A checkpoint record → one anchoring fact (§5.2). Subject = checkpoint_id."""
    obj = {
        "merkle_root": payload.get("merkle_root"),
        "tip_chain_root": payload.get("tip_chain_root"),
        "seq_lo": payload.get("seq_lo"),
        "seq_hi": payload.get("seq_hi"),
        "signature": payload.get("signature"),           # signature ref (evidence, public)
        "key_id": payload.get("key_id"),
    }
    return GMPFact(predicate="ccr:checkpoint", subject=payload["checkpoint_id"],
                   obj=canonical_json(obj).decode(), valid_from=payload.get("created_at", ""),
                   tenant_id=tenant_id, importance=0.95,
                   sequence=payload.get("seq_hi", 0))


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

    def close(self, fact_id: str, at: Optional[str]) -> None:
        """Bi-temporal close/reopen: set `valid_until` on a fact (or clear it with
        None). Unlike `supersede`, this names NO successor — it marks a fact
        present-but-not-currently-valid. The CCR contested-status mapping (doc 02
        §3.1) uses this to quarantine a belief without asserting a replacement.
        `fact_id` is unchanged (valid_until is not part of content identity)."""
        if fact_id in self._facts:
            self._facts[fact_id].valid_until = at

    def retrieve(self, predicate: Optional[str] = None,
                 subject: Optional[str] = None) -> list[GMPFact]:
        out = []
        for f in self._facts.values():
            # excluded: other tenants; superseded (structural); or bi-temporally
            # closed (valid_until set) — the latter is how a contested belief drops
            # out of the current-validity view (doc 02 §3.1). A full store would
            # compare valid_until to query time; this minimal store treats any set
            # valid_until as "closed as of now".
            if f.tenant_id != self.tenant_id or f.superseded_by or f.valid_until:
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
    """LedgerBackend fan-out: every appended EVIDENCE record (experience,
    gate_decision, checkpoint — doc 03 §3.2) also lands in a GMP store as facts.
    Read path stays on the local ledger; GMP is the durable, queryable,
    tenant-scoped evidence tier. CSO content is never mirrored (doc 03 §3.4)."""

    def __init__(self, store: GMPInMemoryBackend):
        self.store = store
        self.facts_written = 0

    def append(self, line: str) -> None:
        entry = LedgerEntry.from_line(line)
        if entry.kind == "experience":
            facts = experience_to_facts(
                Experience.from_dict(entry.payload), tenant_id=self.store.tenant_id)
        elif entry.kind == "gate_decision":
            facts = gate_decision_to_facts(entry.payload, tenant_id=self.store.tenant_id)
        elif entry.kind == "checkpoint":
            facts = [checkpoint_to_fact(entry.payload, tenant_id=self.store.tenant_id)]
        else:
            return                                    # annotation: no writer today
        for f in facts:
            self.store.write(f)
            self.facts_written += 1

    def read_all(self) -> list[str]:
        return []          # bridge is write-only; primary backend owns reads
