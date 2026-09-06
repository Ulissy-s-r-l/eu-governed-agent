"""Experience Ledger — CCR doc 03 §§3–5.

Append-only, hash-chained, Merkle-checkpointed, Ed25519-signed.

  L1 immutability: records are never modified or deleted; corrections are
     annotation events (not yet needed in Phase 1).
  L3 verifiability: every record signed; every checkpoint anchors a Merkle
     root; inclusion proofs are O(log n); full-chain verification is linear.
  §5.3 honesty: this is tamper-EVIDENCE. Integrity is relative to where the
     signed checkpoints live. `GrafomemSealer` (grafomem_seal.py) implements
     the deployment rule "checkpoints must leave the system".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterator, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption,
)

from .experience import Experience, utcnow, canonical_json, new_id

GENESIS_HASH = "GENESIS"


# --------------------------------------------------------------------------
# Keys
# --------------------------------------------------------------------------

def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    priv = Ed25519PrivateKey.generate()
    return priv, priv.public_key()


def pubkey_hex(pub: Ed25519PublicKey) -> str:
    return pub.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


# --------------------------------------------------------------------------
# Checkpoint record (doc 03 §3.2, §5.2)
# --------------------------------------------------------------------------

@dataclass
class Checkpoint:
    checkpoint_id: str
    seq_lo: int                       # first seq covered
    seq_hi: int                       # last seq covered
    merkle_root: str                  # hex root over record hashes in [seq_lo, seq_hi]
    tip_chain_root: str               # root over ALL record hashes 0..seq_hi (running tree)
    created_at: str = field(default_factory=utcnow)
    signature: str = ""               # Ed25519 over canonical payload
    key_id: str = ""

    def payload(self) -> bytes:
        d = asdict(self); d.pop("signature")
        return canonical_json(d)

    def sign(self, priv: Ed25519PrivateKey, key_id: str) -> "Checkpoint":
        self.key_id = key_id
        self.signature = priv.sign(self.payload()).hex()
        return self

    def verify(self, pub: Ed25519PublicKey) -> bool:
        try:
            pub.verify(bytes.fromhex(self.signature), self.payload())
            return True
        except Exception:
            return False


# --------------------------------------------------------------------------
# Merkle tree (RFC 6962-style: leaf = H(0x00‖data), node = H(0x01‖L‖R))
# --------------------------------------------------------------------------

def _leaf(data: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + data).digest()

def _node(l: bytes, r: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + l + r).digest()

def merkle_root(leaves: list[bytes]) -> bytes:
    if not leaves:
        return hashlib.sha256(b"").digest()
    level = [_leaf(l) for l in leaves]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])          # duplicate last (CT-style)
        level = [_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]

def merkle_inclusion_proof(leaves: list[bytes], index: int) -> list[tuple[str, str]]:
    """Return audit path as list of (position, hex-hash): position in {left,right}."""
    proof: list[tuple[str, str]] = []
    level = [_leaf(l) for l in leaves]
    idx = index
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        sib = idx + 1 if idx % 2 == 0 else idx - 1
        pos = "right" if idx % 2 == 0 else "left"
        proof.append((pos, level[sib].hex()))
        idx //= 2
        level = [_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return proof

def verify_inclusion(leaf_data: bytes, index: int, proof: list[tuple[str, str]],
                     root_hex: str, tree_size: int) -> bool:
    node = _leaf(leaf_data)
    idx = index
    # tree size must be padded the same way as construction
    n = tree_size + (tree_size % 2)
    for pos, sib_hex in proof:
        sib = bytes.fromhex(sib_hex)
        node = _node(node, sib) if pos == "right" else _node(sib, node)
        idx //= 2
        n = (n + 1) // 2
    return node.hex() == root_hex


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------

class LedgerBackend:
    """Storage abstraction. Implementations: LocalLedgerBackend, GMPFactBridge."""
    def append(self, line: str) -> None: raise NotImplementedError
    def read_all(self) -> list[str]: raise NotImplementedError


class LocalLedgerBackend(LedgerBackend):
    """JSONL files in a directory. Dev + test backend."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def append(self, line: str) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read_all(self) -> list[str]:
        with open(self.path, encoding="utf-8") as f:
            return [l for l in f.read().splitlines() if l.strip()]


class CompositeBackend(LedgerBackend):
    """Fan-out append to several backends; reads from the first."""
    def __init__(self, *backends: LedgerBackend):
        self.backends = list(backends)

    def append(self, line: str) -> None:
        for b in self.backends:
            b.append(line)

    def read_all(self) -> list[str]:
        return self.backends[0].read_all()


# --------------------------------------------------------------------------
# The ledger
# --------------------------------------------------------------------------

@dataclass
class LedgerEntry:
    kind: str                          # experience | checkpoint | annotation | gate_decision
    payload: dict

    def to_line(self) -> str:
        return canonical_json(asdict(self)).decode("utf-8")

    @classmethod
    def from_line(cls, line: str) -> "LedgerEntry":
        d = json.loads(line)
        return cls(kind=d["kind"], payload=d["payload"])


class ExperienceLedger:
    """Append-only experience ledger with per-record signatures and Merkle checkpoints.

    Trust model (doc 03 §5.3): tamper-EVIDENCE via hash chain + signatures.
    Integrity holds against any party that keeps the signed checkpoints.
    """

    def __init__(self, backend: LedgerBackend, private_key: Ed25519PrivateKey,
                 key_id: str = "ccr-ledger", checkpoint_every: int = 16,
                 agent_ref: str = "did:gns:local-dev"):
        self.backend = backend
        self.private_key = private_key
        self.public_key = private_key.public_key()
        self.key_id = key_id
        self.checkpoint_every = checkpoint_every
        self.agent_ref = agent_ref
        self._records: list[Experience] = []
        self._checkpoints: list[Checkpoint] = []
        self._reload()

    # -- persistence / recovery -------------------------------------------

    def _reload(self) -> None:
        for line in self.backend.read_all():
            entry = LedgerEntry.from_line(line)
            if entry.kind == "experience":
                self._records.append(Experience.from_dict(entry.payload))
            elif entry.kind == "checkpoint":
                self._checkpoints.append(Checkpoint(**entry.payload))

    # -- writes ------------------------------------------------------------

    def append(self, exp: Experience) -> Experience:
        """Finalize (seq, chain link, content id), sign, and persist. Append-only."""
        seq = len(self._records)
        prev = self._records[-1].record_hash() if self._records else GENESIS_HASH
        exp.agent_ref = self.agent_ref
        exp.finalize(seq=seq, prev_hash=prev)
        exp.provenance.signature = self.private_key.sign(exp.chain_payload()).hex()
        self.backend.append(LedgerEntry("experience", exp.to_dict()).to_line())
        self._records.append(exp)
        if seq > 0 and (seq + 1) % self.checkpoint_every == 0:
            self.checkpoint()
        return exp

    def checkpoint(self) -> Checkpoint:
        """Anchor a signed Merkle checkpoint over the full record history."""
        n = len(self._records)
        if n == 0:
            raise RuntimeError("cannot checkpoint an empty ledger")
        hashes = [bytes.fromhex(r.record_hash().split(":", 1)[1]) for r in self._records]
        lo = max(0, n - self.checkpoint_every)
        cp = Checkpoint(
            checkpoint_id=new_id("chk"),
            seq_lo=lo,
            seq_hi=n - 1,
            merkle_root=merkle_root(hashes[lo:]).hex(),
            tip_chain_root=merkle_root(hashes).hex(),
        ).sign(self.private_key, self.key_id)
        self.backend.append(LedgerEntry("checkpoint", asdict(cp)).to_line())
        self._checkpoints.append(cp)
        return cp

    # -- reads (projections) ------------------------------------------------

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[Experience]:
        return iter(self._records)

    def get(self, seq: int) -> Experience:
        return self._records[seq]

    def by_goal(self, goal_id: str) -> list[Experience]:
        return [r for r in self._records if r.goal.goal_id == goal_id]

    def evaluated(self) -> list[Experience]:
        return [r for r in self._records if r.is_evaluated()]

    def checkpoints(self) -> list[Checkpoint]:
        return list(self._checkpoints)

    # -- verification ---------------------------------------------------------

    def verify_chain(self) -> bool:
        """Linear walk: signatures, content ids, and hash links (doc 03 §5.1)."""
        prev = GENESIS_HASH
        for r in self._records:
            if r.provenance.prev_hash != prev:
                return False
            if r.compute_id() != r.exp_id:
                return False
            try:
                self.public_key.verify(bytes.fromhex(r.provenance.signature),
                                       r.chain_payload())
            except Exception:
                return False
            prev = r.record_hash()
        return True

    def inclusion_proof(self, seq: int) -> dict:
        """Merkle inclusion proof for a record against the latest checkpoint tip."""
        if not self._checkpoints:
            raise RuntimeError("no checkpoint yet; call checkpoint() first")
        hashes = [bytes.fromhex(r.record_hash().split(":", 1)[1]) for r in self._records]
        leaf = hashes[seq]
        return {
            "exp_id": self._records[seq].exp_id,
            "seq": seq,
            "proof": merkle_inclusion_proof(hashes, seq),
            "tree_size": len(hashes),
            "root": self._checkpoints[-1].tip_chain_root,
            "checkpoint_id": self._checkpoints[-1].checkpoint_id,
        }

    def verify_inclusion(self, proof: dict) -> bool:
        leaf = bytes.fromhex(
            self._records[proof["seq"]].record_hash().split(":", 1)[1])
        return verify_inclusion(leaf, proof["seq"], proof["proof"],
                                proof["root"], proof["tree_size"])
