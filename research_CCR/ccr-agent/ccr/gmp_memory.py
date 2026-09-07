"""GMP-backed persistence for semantic_memory (build-guide §2.1c, doc 02 §3.1).

Makes a committed `MemoryItem` a durable, queryable GMP fact rather than an
in-process object. Per ADR-0008 (B3 is the best client of a *general* ledger),
`MemoryItem.supersedes` maps to GMP's **native `supersede` op** — not to a flag
encoded in the fact payload. Encoding lifecycle around the ledger is the
product-side workaround ADR-0008 forbids; the native op is the general-client
answer.

Mapping (every MemoryItem field has a home):
  - belief fact:   predicate = "ccr:mem/<type>", subject = item.id,
                   obj = item.content, valid_from = commit time,
                   importance = item.confidence
  - provenance:    a companion fact "ccr:mem/sources" (subject = item.id,
                   obj = the root exp_ids) — I4, mirroring the experience
                   bridge's separate `ccr:provenance` fact rather than
                   payload-encoding provenance
  - status:        NATIVE lifecycle — `active` = a live, non-superseded fact;
                   `deprecated`-with-successor = native `supersede`;
                   `deprecated`-without-successor (future memory demotion, not
                   exercised today) = `valid_until` (bi-temporal close)
  - supersedes:    NATIVE `supersede(old_ref, new_fact)` op
"""
from __future__ import annotations

from typing import Optional

from .experience import canonical_json
from .gmp_bridge import GMPFact, GMP_DEFAULT_TENANT


def memory_item_to_facts(item, valid_from: str,
                         tenant: str = GMP_DEFAULT_TENANT) -> tuple[GMPFact, GMPFact]:
    belief = GMPFact(predicate=f"ccr:mem/{item.type}", subject=item.id,
                     obj=item.content, valid_from=valid_from, tenant_id=tenant,
                     importance=item.confidence)
    provenance = GMPFact(predicate="ccr:mem/sources", subject=item.id,
                         obj=canonical_json(item.sources).decode(),
                         valid_from=valid_from, tenant_id=tenant, importance=0.9)
    return belief, provenance


class GMPMemoryStore:
    """Commit observer: persists committed MemoryItems as GMP facts."""

    def __init__(self, backend, tenant: str = GMP_DEFAULT_TENANT):
        self.backend = backend
        self.tenant = tenant
        self._belief_ref: dict[str, str] = {}       # mem_id -> current belief fact_id
        self._constellation: dict[str, list[str]] = {}   # mem_id -> [belief, provenance] fact_ids

    def on_commit(self, item, tx, op: str = "insert",
                  supersedes_mem_id: Optional[str] = None) -> str:
        """Persist a committed MemoryItem. `insert` writes; `insert` that
        supersedes another belief uses the native supersede op; `confirm` writes
        a fresh confirmation of the same belief (idempotent by identity unless
        the commit time differs)."""
        vf = tx.created_at
        belief, provenance = memory_item_to_facts(item, vf, self.tenant)
        prior = supersedes_mem_id and self._belief_ref.get(supersedes_mem_id)
        if prior:
            self.backend.supersede(prior, belief)   # NATIVE op (ADR-0008)
        else:
            self.backend.write(belief)
        self.backend.write(provenance)
        self._belief_ref[item.id] = belief.fact_id
        self._constellation[item.id] = [belief.fact_id, provenance.fact_id]
        return belief.fact_id

    def retrieve_active(self, subject: Optional[str] = None,
                        predicate: Optional[str] = None) -> list[GMPFact]:
        """Active (non-superseded, non-contested) beliefs — the read path a peer
        agent uses. Excludes contested beliefs because `retrieve` honors
        `valid_until` and `mark_contested` closes them there."""
        return self.backend.retrieve(predicate=predicate, subject=subject)

    # -- contested status (doc 02 §3.1) ---------------------------------------
    # NOT a supersession (neither fact wins, no successor), so NOT the native
    # supersede op. A contested belief is QUARANTINED via `valid_until` (present,
    # not currently assertable) plus a `ccr:mem/contested` marker recording the
    # partner. This is a CONVENTION, not a GMP primitive: it closes the belief for
    # the standard `retrieve` path, but the audit view still surfaces it — see the
    # test with a convention-unaware consumer.
    CONTESTED_PRED = "ccr:mem/contested"

    def mark_contested(self, mem_id: str, partner_id: str, tx) -> None:
        """Quarantine `mem_id`'s whole fact constellation (belief + provenance):
        close each bi-temporally and write an open marker naming the conflicting
        `partner_id`. Mirrors detect_and_mark."""
        for fact_id in self._constellation.get(mem_id, []):
            self.backend.close(fact_id, tx.created_at)
        marker = GMPFact(predicate=self.CONTESTED_PRED, subject=mem_id,
                         obj=partner_id, valid_from=tx.created_at,
                         tenant_id=self.tenant, importance=0.9)
        self.backend.write(marker)

    def clear_contested(self, mem_id: str, tx) -> None:
        """Resolution (mirrors reconcile_contested): reopen `mem_id`'s constellation
        and close its contested marker(s). The conflicting partner's marker is
        closed too — the contest is over for both — but the partner's constellation
        is left as-is (a superseded partner stays structurally superseded)."""
        for fact_id in self._constellation.get(mem_id, []):
            self.backend.close(fact_id, None)                # reopen
        for marker in self.backend.retrieve(predicate=self.CONTESTED_PRED,
                                            subject=mem_id):
            self.backend.close(marker.fact_id, tx.created_at)
            partner = marker.obj
            for pm in self.backend.retrieve(predicate=self.CONTESTED_PRED,
                                            subject=partner):
                if pm.obj == mem_id:
                    self.backend.close(pm.fact_id, tx.created_at)
