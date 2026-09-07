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
        return belief.fact_id

    def retrieve_active(self, subject: Optional[str] = None,
                        predicate: Optional[str] = None) -> list[GMPFact]:
        """Active (non-superseded) beliefs — the read path a peer agent uses."""
        return self.backend.retrieve(predicate=predicate, subject=subject)
