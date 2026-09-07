"""cgr.cosign.v1 — the two-party co-signature envelope, applied to the learning
transaction (approval-free mode).

Spec: grafomem `docs/cgr/cgr-cosign-v1-spec.md` (accepted via decision 0009).
This module implements the envelope primitives the LearningEngine uses:

  - content_digest        BLAKE2b-256 over JCS(content_body)  (§2.1)
  - approval_assertion    {content_digest, approver_id, approver_key_id,
                           approver_act, decision_date, record_nonce,
                           [agent_draft_digest]}                (§1, §6)
  - approver signature    Ed25519 over DOMAIN_TAG ‖ JCS(assertion), self-custodied
  - predicate required-ness  {field, op, value} over content_body  (§5.1)
  - system signature      computed by the engine, LAST, over the whole record
                          INCLUDING the approver signature (nested, §2.3)

The engine never holds the approver's key: an `Approver` produces the signed
assertion; the engine verifies it. `LocalApprover` is the self-custody
simulation used in tests and dev.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

from .experience import canonical_json, new_id, utcnow

# --- constants (from the spec / gns_browser signer contract) --------------
SCHEMA = "cgr.cosign.v1"
DOMAIN_TAG = b"grafomem.hitl.approval.v1:"          # §9, the gns_browser prefix
LEARNING_TX_PROFILE = "cgr.learning-tx.v1"
APPROVAL_MODE_FREE = "free"
# cgr.learning-tx.v1 required-ness (§5.1 predicate): approval REQUIRED for high risk
REQUIRED_WHEN = {"field": "risk", "op": "eq", "value": "high"}


# --- digests --------------------------------------------------------------

def b2_256(data: bytes) -> str:
    return "b2-256:" + hashlib.blake2b(data, digest_size=32).hexdigest()


def content_digest(content_body: dict) -> str:
    """BLAKE2b-256 over the JCS-canonical content body (§2.1)."""
    return b2_256(canonical_json(content_body))


# --- approval assertion + signatures --------------------------------------

def build_assertion(cd: str, approver_id: str, approver_key_id: str,
                    approver_act: str, decision_date: str, record_nonce: str,
                    agent_draft_digest: Optional[str] = None) -> dict:
    a = {
        "content_digest": cd,
        "approver_id": approver_id,
        "approver_key_id": approver_key_id,
        "approver_act": approver_act,
        "decision_date": decision_date,
        "record_nonce": record_nonce,
    }
    if agent_draft_digest is not None:        # §6: present only for modify/override
        a["agent_draft_digest"] = agent_draft_digest
    return a


def _approval_signing_bytes(assertion: dict) -> bytes:
    return DOMAIN_TAG + canonical_json(assertion)


def sign_assertion(assertion: dict, approver_priv: Ed25519PrivateKey) -> str:
    return approver_priv.sign(_approval_signing_bytes(assertion)).hex()


def _pub_from_key_id(key_id: str) -> Ed25519PublicKey:
    if not key_id.startswith("ed25519:"):
        raise ValueError(f"unsupported approver_key_id: {key_id}")
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_id.split(":", 1)[1]))


def verify_assertion(assertion: dict, signature_hex: str, approver_key_id: str) -> bool:
    """Independently verifiable with only the approver's public key (§3.1)."""
    try:
        _pub_from_key_id(approver_key_id).verify(
            bytes.fromhex(signature_hex), _approval_signing_bytes(assertion))
        return True
    except Exception:
        return False


def key_id_for(pub: Ed25519PublicKey) -> str:
    from .ledger import pubkey_hex
    return "ed25519:" + pubkey_hex(pub)


# --- §5.1 predicate required-ness -----------------------------------------

_ORDER_OPS = {"lt", "lte", "gt", "gte"}


def _resolve(field_path: str, body: dict):
    """Resolve a dot-path to a SCALAR. Returns (value, resolved). A missing or
    non-scalar path is (None, False) — it cannot trigger a requirement it cannot
    evaluate (§5.1)."""
    cur: Any = body
    for part in field_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return (None, False)
        cur = cur[part]
    if isinstance(cur, (dict, list)):
        return (None, False)
    return (cur, True)


def predicate_required(pred: dict, content_body: dict) -> tuple[bool, bool]:
    """(required, resolved). `resolved=False` ⇒ predicate_unresolved (§5.1):
    surfaced by the caller so a misspelled path is not silently non-triggering."""
    val, resolved = _resolve(pred["field"], content_body)
    if not resolved:
        return (False, False)
    op, lit = pred["op"], pred["value"]
    if op in _ORDER_OPS and not isinstance(val, (int, float)):
        return (False, False)          # ordering ops are numbers-only (§5.1)
    if op == "eq":  return (val == lit, True)
    if op == "ne":  return (val != lit, True)
    if op == "in":  return (val in lit, True)
    if op == "lt":  return (val < lit, True)
    if op == "lte": return (val <= lit, True)
    if op == "gt":  return (val > lit, True)
    if op == "gte": return (val >= lit, True)
    raise ValueError(f"unknown predicate op: {op}")


# --- system (outer) signature over the whole record incl. approver sig -----

# envelope keys excluded from the system's signed body (§2.3)
_ENVELOPE_KEYS = ("system_signature", "evidence_ref")


def system_signing_bytes(record_dict: dict) -> bytes:
    body = {k: v for k, v in record_dict.items() if k not in _ENVELOPE_KEYS}
    return canonical_json(body)


def sign_system(record_dict: dict, system_priv: Ed25519PrivateKey) -> str:
    return system_priv.sign(system_signing_bytes(record_dict)).hex()


def verify_system(record_dict: dict, system_pub: Ed25519PublicKey) -> bool:
    sig = record_dict.get("system_signature")
    if not sig:
        return False
    try:
        system_pub.verify(bytes.fromhex(sig), system_signing_bytes(record_dict))
        return True
    except Exception:
        return False


# --- Approver (self-custody): produces a signed assertion; engine verifies --

Approver = Callable[[str], tuple[dict, str]]   # content_digest -> (assertion, signature)


class LocalApprover:
    """Self-custody simulation: holds an Ed25519 key and signs assertions.
    In production this is the operator's own client (e.g. gns_browser); the
    engine only ever receives (assertion, signature)."""

    def __init__(self, approver_id: str, priv: Ed25519PrivateKey,
                 act: str = "approve", agent_draft_digest: Optional[str] = None):
        self.approver_id = approver_id
        self.priv = priv
        self.key_id = key_id_for(priv.public_key())
        self.act = act
        self.agent_draft_digest = agent_draft_digest

    def __call__(self, cd: str) -> tuple[dict, str]:
        assertion = build_assertion(
            cd, self.approver_id, self.key_id, self.act, utcnow(),
            new_id("nonce"), self.agent_draft_digest)
        return assertion, sign_assertion(assertion, self.priv)
