"""Grafomem sealing — anchor ledger checkpoints into signed grafomem state.

Implements doc 03 §5.3's deployment rule ("checkpoints must leave the
system") using the grafomem runtime: the ledger's checkpoint Merkle roots are
embedded into a grafomem ExecutionContext and sealed as a signed .gfm CSO
(GFM1 format, Ed25519). Any party holding the .gfm and the public key can
verify the anchor; the anchor binds the checkpoint roots to a key and a time.

Naming (README mapping): grafomem's CSO is the working-state container; here
it carries CCR *evidence*, not learned content.
"""

from __future__ import annotations

import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import grafomem
from grafomem.runtime import ExecutionContext, Governance, Receipt

from .ledger import Checkpoint

SEAL_KEY_ID = "ccr-phase1-seal"
SEAL_MODEL_ID = "ccr-evidence-v1"


class GrafomemSealer:
    """Seals CCR ledger checkpoints into grafomem signed working state."""

    def __init__(self, private_key: Ed25519PrivateKey):
        self.private_key = private_key
        self.governance = Governance(model_id=SEAL_MODEL_ID, norm_budget=10_000.0,
                                     allowed_consent=("tenant", "private", "public"))
        # ExecutionContext with a small working matrix; the checkpoint digest
        # is embedded deterministically (padded) — the .gfm signature is what
        # carries the evidentiary weight, not the matrix values.
        self.ctx = ExecutionContext(model_id=SEAL_MODEL_ID)

    def seal_checkpoint(self, cp: Checkpoint) -> bytes:
        """Embed the checkpoint's tip root in working state and return a
        signed .gfm artifact binding (checkpoint_id, tip_chain_root, key, time)."""
        digest = bytes.fromhex(cp.tip_chain_root)
        vec = np.frombuffer(digest.ljust(64, b"\x00")[:64], dtype=np.uint8).astype(float)
        vec = vec / (np.linalg.norm(vec) or 1.0)
        M = np.outer(vec, vec)                        # rank-1 commitment matrix, d=64
        self.ctx.M = M
        # grafomem capability grammar: ^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$
        self.ctx.capabilities = frozenset({"ccr_ledger.anchor"})
        self.ctx.policy = {"subject_id": cp.checkpoint_id, "policy": "tenant",
                           "expires_at": None}
        return grafomem.sdk.checkpoint(self.ctx, self.private_key, SEAL_KEY_ID)

    def verify_seal(self, gfm_bytes: bytes) -> bool:
        """Load path: verifies the .gfm signature against trusted keys."""
        trusted = {SEAL_KEY_ID: self.private_key.public_key()}
        try:
            grafomem.sdk.load(gfm_bytes, trusted, self.governance)
            return True
        except Exception:
            return False

    def erase_evidence(self, scope: str) -> Receipt:
        """grafomem erasure receipt: proves the erasure *operation* occurred
        (state overwritten, bound to key and time) — not media sanitization."""
        return grafomem.sdk.erase(self.ctx, scope, self.private_key, SEAL_KEY_ID)
