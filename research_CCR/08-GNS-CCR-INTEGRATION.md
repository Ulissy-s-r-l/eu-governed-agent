# 08 — GNS–CCR Integration: Identity, Authority, and Verifiable Lineage

**Continuous Cognitive Runtime (CCR) — Document 8 of the CCR specification series**
**Status:** Working draft v0.1 — personal working document, intended for later refinement toward an arXiv publication
**Depends on:** `00-CCR-SYSTEM-OVERVIEW.md` (§4.4, §10), `01-CCR-FORMAL-MODEL.md` (Defs. 8.1, 10.1–10.2), `03-EXPERIENCE-LEDGER.md` (§5 checkpoints), `07-CCR-SECURITY-MODEL.md` (§7 properties)
**Feeds:** Phase 7–8 implementation, `Continuous-Cognitive-Runtime.md`

---

## 0. Executive Summary

This document specifies the integration between the Continuous Cognitive Runtime and **GNS** — the identity, authority, and provenance layer that binds a learning agent's evolving behavior to a verifiable identity. Documents 00–07 built the cognitive machinery: experiences, state, transactions, causality, benchmarks, and security. What remains is the trust boundary: *who* is this agent, *what authority* does it hold, and *how can a third party verify* that this behavior descends from this history under this mandate? The roadmap's claim — `Agent = Identity + CognitiveState + Experience + Authority + Provenance` — is made operational here.

The integration is built on standards that matured considerably during 2025–2026, and the design deliberately rides them rather than inventing parallel machinery. W3C Verifiable Credentials Data Model 2.0 became a full Recommendation in May 2025, and DIDs v1.1 reached Candidate Recommendation in March 2026 ([W3C VC 2.0](https://www.w3.org/TR/vc-data-model-2.0/), [W3C DID 1.1](https://www.w3.org/TR/did-1.1/)). The OpenID Foundation's work on identity management for agentic AI has standardized the vocabulary of delegated authority — on-behalf-of flows, recursive delegation, scope attenuation, and revocation ([OpenID Foundation](https://openid.net/wp-content/uploads/2025/10/Identity-Management-for-Agentic-AI.pdf)) — and NIST published a concept paper on AI agent identity in February 2026 ([Dock](https://www.dock.io/post/ai-agent-identity)). The academic frame comes from *Authenticated Delegation and Authorized AI Agents*, which extends OAuth 2.0/OIDC with agent-ID tokens and delegation tokens to create auditable chains of accountability from human principal to agent action ([arXiv:2501.09674](https://arxiv.org/html/2501.09674v1)).

What GNS adds beyond these standards is the part that has no precedent: **binding identity to a continuously changing cognitive state**. Existing agent-identity work answers "which agent is acting and on whose behalf?" GNS–CCR must additionally answer "which *version* of this agent is acting, what learning produced that version, and was that learning legitimate?" That is the integration's unique burden, and it is discharged by anchoring the state DAG's commitments (document 01, Def. 8.1) into the identity chain.

---

## 1. Division of Labor

The architectural placement decision from document 00 (§4.4) is restated operationally: GNS sits *above* the cognitive runtime and does not understand intelligence. The division of labor:

| Concern | Owner | Mechanism |
|---|---|---|
| Who is this agent? | GNS | DID-bound identity record, key management |
| On whose behalf does it act? | GNS | Delegation chain from human principal |
| What may it do? | GNS | Authority scopes, attenuation, revocation |
| What has it learned? | CCR | Versioned cognitive state, experience ledger |
| Is this behavior legitimate? | **Joint** | State commitments anchored in identity chain |
| What can it prove to third parties? | **Joint** | Verifiable presentations over state + lineage |

The two joint concerns are the integration surface. Legitimacy is joint because it requires both sides: CCR knows the learning history, GNS knows the authority history, and the claim "this behavior is legitimate" is the conjunction "this state descends from validated learning" ∧ "this state was produced under valid authority." Proof to third parties is joint for the same reason — a verifiable presentation (§6) packages CCR's evidence chain inside GNS's credential format.

A hard boundary rule follows: **GNS never evaluates cognitive content, and CCR never mints authority.** The identity layer cannot inspect a policy entry and judge it wise; the cognitive layer cannot widen its own scope. Each side's competence ends exactly where the other's begins, which is what makes the trust properties of document 07 (§7) decomposable into independently verifiable halves.

---

## 2. Agent Identity Record

The agent's identity is anchored in a DID, following the standards trajectory for agent identity ([W3C DID 1.1](https://www.w3.org/TR/did-1.1/)). The identity record of document 01 (Def. 10.1) is instantiated as:

```json
{
  "id": "did:gns:abc123…",
  "controller": "did:gns:human-principal-…",
  "verificationMethod": [
    {"id": "did:gns:abc123…#key-1", "type": "Ed25519VerificationKey2020",
     "controller": "did:gns:abc123…", "publicKeyMultibase": "z…"}
  ],
  "service": [{"type": "CCREndpoint", "serviceEndpoint": "https://…"}],
  "agent_metadata": {
    "origin":       {"created_by": "did:gns:human-principal-…", "created_at": "…", "provisioning_record": "vc:…"},
    "model_ref":    {"family": "…", "version": "…"},
    "state_commitment": "cso:sha256:…",
    "policy_version":   8921,
    "authority_scope_ref": "vc:…",
    "evidence_chain_tip":  "chk:sha256:…"
  }
}
```

Two properties of this record carry the integration's thesis. **`state_commitment` is part of identity**: the DID document binds the agent not just to keys but to its current cognitive-state commitment, so "which agent?" and "which version of the agent?" are answered by the same lookup. The commitment is updated at each commit via a signed identity-chain event (§4), keeping identity and state in lockstep. **`controller` separates ownership from operation**: the human principal controls the DID (can rotate keys, revoke, re-scope) while the agent operates its own verification methods — the pattern the OpenID Foundation's agentic-identity work calls the delegated user sub-identity, where the agent's identity is distinct but inseparable from the user's authority ([OpenID Foundation](https://openid.net/wp-content/uploads/2025/10/Identity-Management-for-Agentic-AI.pdf)).

The standards landscape supports but does not complete this design. No single universally adopted protocol yet defines the complete agent identity model ([Dock](https://www.dock.io/post/ai-agent-identity)); GNS's contribution is the `agent_metadata` binding — state commitment, policy version, evidence chain tip — which existing DID/VC infrastructure can carry as credential claims but does not itself specify.

---

## 3. Delegation and Authority

### 3.1 The delegation chain

Authority flows from the human principal to the agent through a **delegation chain** of signed mandates, following the authenticated-delegation framework's three-token structure — user ID token, agent-ID token, delegation token ([arXiv:2501.09674](https://arxiv.org/html/2501.09674v1)) — recast as verifiable credentials:

```json
{
  "type": ["VerifiableCredential", "DelegationMandate"],
  "issuer": "did:gns:human-principal-…",
  "credentialSubject": {
    "id": "did:gns:abc123…",
    "scope": {
      "permit":  ["tool:calendar.read", "tool:email.send:draft-only", "workflow:research"],
      "deny":    ["tool:payment.*"],
      "escalate": ["policy_change:high_risk", "tool:email.send:external"]
    },
    "constraints": {"expires": "2027-09-06T00:00:00Z", "max_state_drift": "0.35", "reauthorization_on_drift": true},
    "parent_mandate": null
  },
  "proof": {"type": "DataIntegrityProof", "cryptosuite": "eddsa-rdfc-2022", "…": "…"}
}
```

The scope's three-valued logic (`permit`/`deny`/`escalate`) instantiates the authority scope of document 01 (Def. 10.1), and the `constraints` block is where CCR's learning-awareness enters the mandate: `max_state_drift` binds the mandate to the drift metric of document 01 (§12.1), so authority is granted not just to an agent but to an agent *within a behavioral envelope* — cross the drift threshold and re-authorization is required automatically. This is the roadmap's identity-drift defense (document 07, §2.7) expressed as a delegation constraint rather than a monitoring afterthought.

### 3.2 Scope attenuation and recursive delegation

When the agent delegates subtasks to sub-agents, the chain extends under **scope attenuation**: each delegation may only narrow, never widen, the parent's scope ([OpenID Foundation](https://openid.net/wp-content/uploads/2025/10/Identity-Management-for-Agentic-AI.pdf)). Formally, for a delegation chain `M₁ → M₂ → … → Mₖ`, the effective scope is monotone non-increasing: `scope(Mᵢ₊₁) ⊆ scope(Mᵢ)`. The authority guard (document 01, Def. 10.2) verifies the full chain at enforcement time, and each link's credential is recorded in the evidence chain.

### 3.3 The intersection rule

A learning agent creates a subtle authority question that static agents never face: the agent's *capabilities* change as it learns, but its *authority* must not. The integration adopts the two-identity intersection rule from current agent-authorization practice: effective authority at any moment is the strict intersection of the mandate's scope and the principal's own standing permissions — never the union ([Arcade](https://www.arcade.dev/blog/ai-agent-authentication-authorization/)). In CCR terms: a learned skill that *can* invoke a tool does not thereby *may* invoke it; invariant I5 (document 02, §4) checks learned content against the scope at commit time, and the runtime enforce hook checks again at act time against the current mandate. Learning changes competence; only delegation changes authority. That sentence is the integration's core invariant.

### 3.4 Revocation and re-authorization

Mandates are revocable at any time by the principal; revocation is a signed identity-chain event with immediate effect on the enforce hook (pending actions drain or abort per policy). Three events trigger mandatory re-authorization: drift threshold crossing (§3.1), recovery from a security incident (document 07, §6 — post-incident operation requires a fresh mandate), and high-risk policy changes (the `escalate` class routes through human approval, implemented with asynchronous out-of-band approval in the style of CIBA ([OpenID Foundation](https://openid.net/wp-content/uploads/2025/10/Identity-Management-for-Agentic-AI.pdf))).

---

## 4. State Commitments on the Identity Chain

The integration's linchpin is anchoring CCR's state DAG into GNS's identity chain. The mechanism has three parts:

**Commit events.** Every learning-transaction commit (document 04, stage 8) emits a signed identity-chain event binding `⟨parent_commitment, new_commitment, tx_hash, validation_hash⟩` under the agent's key. The identity chain thereby mirrors the state DAG's spine: the DAG records *what changed*; the identity chain records *that the change happened under this identity*. The two structures are independently maintained and cross-referencing, so tampering with either without the other is detectable.

**Checkpoint anchoring.** The ledger's signed Merkle checkpoints (document 03, §5.2) are periodically anchored into the identity chain, which is the concrete implementation of document 03's deployment rule that "checkpoints must leave the system." The identity chain serves as the distribution channel for reference points: any party that has observed the identity chain holds checkpoint commitments against which ledger inclusion and consistency proofs verify. For higher assurance, checkpoints can additionally be witnessed by an external transparency service, following the cosigner model ([Merkle Tree Certificates](https://davidben.github.io/merkle-tree-certs/draft-ietf-plants-merkle-tree-certs.html)).

**Lineage verification.** Verifying that state `C_n` legitimately belongs to agent `did:gns:abc123…` reduces to three mechanical checks: (1) the state DAG chain from genesis verifies per Definition 8.1; (2) each commit event on the identity chain is signed by the DID's current verification method; (3) the two chains cross-reference consistently at every anchor point. All three are signature-and-hash checks — no trusted party, no access to cognitive content required. This is RQ8's "cryptographically verifiable cognitive state" discharged as a verification algorithm.

---

## 5. Evidence Chains and Third-Party Verification

The **evidence chain** is the integration's audit artifact: a self-contained, third-party-verifiable package answering a specific claim about the agent. Three claim types are supported:

**"This action was authorized."** Package: the action's ledger record (with inclusion proof against an anchored checkpoint), the mandate credential active at act time, the delegation chain to the human principal, and the enforce-hook decision record. Verifier checks: signatures, scope containment, chain integrity.

**"This state descends from validated learning."** Package: the state's commitment chain to genesis, each commit's validation record hash, and the identity-chain commit events. Verifier checks: Definition 8.1 chain verification plus signature verification — the property `CommittedUpdate ⇒ ValidatedExperience` made portable.

**"This behavior change traces to these experiences."** Package: the policy/skill item's provenance index entry, the justifying experiences' inclusion proofs, the transaction record, and the causal chain from document 05. This is the end-to-end provenance path of document 03 (§6) packaged for external verification.

The packaging format is a **verifiable presentation** ([W3C VC 2.0](https://www.w3.org/TR/vc-data-model-2.0/)): the agent assembles the relevant credentials and proofs into a presentation signed under its DID, which any verifier can check offline against the DID document and anchored checkpoints. The pattern parallels AgentBound's governance receipts — binding each action to the exact policy snapshot responsible ([AgentBound](https://arxiv.org/html/2606.30970v1)) — extended from action governance to learning governance: every evidence chain binds behavior to the exact *state version* responsible.

---

## 6. Privacy: Selective Disclosure of Cognitive Evidence

Evidence chains create a privacy tension: proving legitimacy seems to require revealing learning history, but an agent's experience ledger may be sensitive (user data, business process detail). The integration resolves this through the VC ecosystem's selective-disclosure machinery, which Data Model 2.0 explicitly supports — selective disclosure of properties, unlinkable presentations, and non-correlatable identification ([W3C VC 2.0](https://www.w3.org/TR/vc-data-model-2.0/)).

Two disclosure modes are defined. **Metadata-only verification** (default): the verifier sees commitments, hashes, signatures, and Merkle proofs — establishing *that* a valid lineage exists — without seeing any experience content. This suffices for most counterparty checks and is the privacy-preserving default. **Predicate proofs** (high-assurance, ZK mode): for claims like "this policy change was approved by a human" or "no committed update ever exceeded scope X," zero-knowledge proofs over the commitment chain can establish the predicate without revealing the chain's contents. The current VC-ZK toolbox (BBS+ signatures, SD-JWT) supports the simpler predicates today, with known practical limits — standard hash/signature primitives are expensive inside ZK circuits, motivating ZK-friendly alternatives like Poseidon hashes in future revisions ([Affinidi](https://www.affinidi.com/blog/how-zero-knowledge-proofs-protect-privacy/), [SD-BLS](https://arxiv.org/pdf/2406.19035)). ZK mode is specified as an extension point, not a Phase 7 requirement.

---

## 7. Protocol Flows

Three protocol flows complete the integration:

**Provisioning.** Principal generates agent DID → issues genesis mandate credential → CCR creates genesis state `C₀` → genesis commitment `Commit₀` is signed and anchored → agent record is live. The genesis event binds identity, authority, and initial state in one signed artifact; everything after is lineage.

**Steady-state operation.** Each commit emits an identity-chain event (§4); each action carries the current `state_commitment` and mandate reference in its envelope (signed, per the enforce hook); checkpoints anchor periodically. Counterparties verify on demand via evidence chains.

**Incident response.** Detection (document 07, §6) → circuit breaker: principal (or automated policy) issues a scope-narrowing or revocation event on the identity chain, effective immediately at all enforce hooks → recovery per document 07 → re-authorization with fresh mandate before resuming learning. The identity chain is the kill switch: because authority flows through it, cutting the chain stops the agent regardless of the cognitive layer's state — the trust layer can halt the adaptive layer without trusting it.

---

## 8. Formal Properties for Phase 8 Verification

The integration's verifiable properties, extending document 07's table:

| Property | Statement | Mechanism |
|---|---|---|
| **Identity–state binding** | `ActingState(C_n) ⇒ state_commitment(DID) = Commit_n` | Commit events (§4) |
| **Delegation soundness** | `Authorized(a) ⇒ ∃ mandate chain M₁→…→Mₖ with scope(Mₖ) ∋ class(a)` | Chain verification (§3.2) |
| **Attenuation** | `scope(Mᵢ₊₁) ⊆ scope(Mᵢ)` for all delegation links | Credential validation |
| **Learning–authority separation** | No commit event can modify any mandate credential | Boundary rule (§1) |
| **Cross-chain consistency** | Every DAG commitment has a corresponding signed identity-chain event | Anchor verification (§4) |
| **Revocation liveness** | A revocation event takes effect at all enforce hooks within bounded time | Protocol flow (§7) |

These six, together with document 07's five, constitute the eleven properties the ProVerif-style Phase 8 verification will target — all stated so as to reduce to signature checks, chain checks, and containment checks over the two chains, none requiring modeling of learned content.

---

## 9. Summary and Handoff

The GNS–CCR integration specified here completes the roadmap's composition `Agent = Identity + CognitiveState + Experience + Authority + Provenance` with standards-based machinery: DID-anchored identity carrying state commitments, VC-based delegation mandates with drift constraints, monotone scope attenuation across recursive delegation, identity-chain anchoring of the state DAG and ledger checkpoints, and verifiable-presentation evidence chains with selective disclosure. The integration's two original contributions are the *state commitment as identity attribute* — making "which version of the agent" a first-class identity question — and the *drift-constrained mandate* — making authority conditional on behavioral envelope, not just identity continuity.

The core invariant bears repeating as the series' trust foundation: **learning changes competence; only delegation changes authority.** Everything in Phase 7–8 implements, and everything in Phase 8 verifies, that sentence.

*Document 08 of the CCR series. Previous: `07-CCR-SECURITY-MODEL.md`. The specification series 00–08 is now complete. Next: `Continuous-Cognitive-Runtime.md` — the research paper synthesizing architecture, formal model, and experimental program.*
