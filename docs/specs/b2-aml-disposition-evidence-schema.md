# B2 — AML disposition evidence schema (specification, DRAFT)

- **Status:** **Draft** specification. This is a *schema spec* (in the manner of the Foundation's
  `cgr-attestation-v4-spec.md`), **not a decision record** — the decisions are
  [ADR-0008](../decisions/ADR-0008-b3-best-client-of-general-ledger.md) (B3 is the best client of a
  general ledger) and [ADR-0009](../decisions/ADR-0009-b3-level-2-governed-assistant-no-correctness-signal.md)
  (B3 is a Level 2 governed assistant; no learning claim).
- **Date:** 2026-09-06
- **Uses:** MUST / SHOULD / MAY per RFC 2119.
- Citations follow the primary-source verification convention (`docs/decisions/README.md` →
  "Verifying load-bearing claims").

## 0. What this is — a PROFILE, not a standalone schema

**This is an AML *profile* of a general Foundation record type — working name `cgr.disposition.v1` —
not a standalone AML schema.** The general record — a **signed two-actor decision** (an agent prepares,
a named human approves and signs) — is **upstream in the standard and currently unresolved**: it is the
resolution shape of `GNS-Foundation/grafomem` decision **0009** (the standard expresses one actor where
two are needed). This document specifies **only the AML-specific profile**: the content fields' AML
semantics and the AML vocabularies. Everything general — the two-signature envelope, the person
identity, the canonicalisation — belongs to `cgr.disposition.v1` upstream and is referenced here as a
dependency, not redefined.

**Why a new record type and not `cgr.attestation.v4`.** A disposition is a *signed two-actor decision*,
not a *reputation aggregate*; `v4` cannot carry it (no record class fits, one signer slot, no home for
the content fields — see grafomem 0009). Overloading the attestation would repeat a pattern already
corrected this week. So B2 targets `cgr.disposition.v1`, which reuses `v4`'s JCS canonicalisation and
Ed25519 conventions but has its own field set and a two-signature envelope.

**The readiness seam (respect it).** The **content half (§1-A, §2, §3, §4) depends on nothing
unresolved and is specified in full.** The **actor-binding half (§1-B) is a typed socket, BLOCKED on
grafomem 0009** — named and shape-sketched, **not decided.** A B2 implementation MAY build the content
record now and MUST leave a typed, empty socket for the binding.

---

## 1. The record's fields

### 1-A. Content block (specified in full — depends on nothing unresolved)

| # | Field | Type | Req/Opt | Notes |
|---|---|---|---|---|
| 1 | `alert_ref` | string — opaque case/alert id | **REQUIRED** | The join key to the bank's case system. Opaque, meaningless outside the tenant. Irreducible. |
| 2 | `subject_ref` | string — HMAC pseudonym `SUBJ-<hex>` | **REQUIRED** | Who the disposition is about. **MUST be a pseudonym, never PII** (§2, §3). Irreducible. |
| 3 | `alert_typology` | enum — closed AML vocab (§5.1) | **REQUIRED** | What fired. Irreducible. |
| 4 | `evidence_digest` | object `{alg, root, item_count}` | **REQUIRED** | BLAKE2b-256 Merkle commitment over the evidence set (§2). Irreducible. |
| 5 | `agent_conclusion` | object `{recommendation, rationale_digest \| rationale_ref}` | **REQUIRED** | What the agent concluded and why. Narrative carried by digest/ref, never inline, when it may contain PII (§3). Irreducible. |
| 6 | `disposition_outcome` | enum `{file \| no-file \| escalate}` (§5.2) | **REQUIRED** | The operative result being audited. Irreducible. |
| 7 | `decision_date` | date/datetime | **REQUIRED** | When the human decided. Distinct from `recorded_at` on purpose. Irreducible. |
| 8 | `recorded_at` | datetime | **REQUIRED** | When the record was captured/issued. |
| 9 | `authority_anchor` | object `{procedure_version, model_version}` | **REQUIRED** | "Under what authority": the procedure/rule-set and the agent/model in force. Irreducible. |
| 10 | `agent_identity` | `agent_pk` (Ed25519) | **REQUIRED** | The **preparer** — distinct from the approver (§1-B). Irreducible. |
| 11 | `agent_confidence` | number ∈ [0,1] | OPTIONAL | Triage-quality signal; not defensibility. |
| 12 | `time_to_decision` | duration | OPTIONAL | Oversight-quality signal. |
| 13 | `filing_ref` | string | OPTIONAL | Resulting STR reference when `disposition_outcome = file`. |
| 14 | `prior_alert_refs` | array<string> | OPTIONAL | Case continuity. |

**Irreducible content core:** 1, 2, 3, 4, 5, 6, 7, 9, 10 — strip any and a supervisor cannot
reconstruct *which alert, on whom, what the agent saw, what it concluded and why, the result, when
decided, under what authority, prepared by what*.

**`decision_date` vs `recorded_at` (normative).** They are **distinct on purpose**: `decision_date` is
when the accountable human decided; `recorded_at` is when the wire record was minted. `decision_date <
recorded_at` means the record is backfilled/non-contemporaneous and MUST be readable as such (a
supervisor treats a same-day sign-off and a reconstructed-later one differently). *(Note the general
record inherits the temporal-field discipline that grafomem 0009 gap 5 flags — a substantive dated
decision is neither a v4 "rule" record nor a pooled aggregate; `cgr.disposition.v1` carries
`decision_date`/`recorded_at` natively, which is one reason it is a new record type.)*

### 1-B. Actor-binding block — TYPED SOCKET, **BLOCKED on grafomem 0009** (shape sketched, NOT decided)

These three fields are the second actor — the accountable human. They are **the irreducible actor
half** and they are exactly grafomem 0009's two-actor requirement. **They are specified here only as a
socket; their contents and mechanism are 0009's to resolve. Do not fill them in an implementation
beyond leaving the typed slot.**

| # | Field | Type (sketch) | Req/Opt | Blocked on |
|---|---|---|---|---|
| 15 | `approver_identity` | a **named-person principal** (natural-person id + key reference) | REQUIRED *(socket)* | **0009 gap 3** — no accountable/verified natural-person identity exists yet |
| 16 | `approver_act` | enum `{approve \| modify \| override}` | REQUIRED *(socket)* | **0009 gap 1** — no approver field in the model |
| 17 | `approver_signature` | Ed25519 signature over the canonical record + fields 15-16, by the approver's **self-custodied** key | REQUIRED *(socket)* | **0009 gaps 1-2** — one signer slot today; no second-signer slot |

**Sketch (not a decision).** The approver's self-custodied key co-signs the canonical serialization of
§1-A plus fields 15-16, producing a **second signature** distinct from the issuer/system signature — a
**two-signature envelope**. A self-custody client and a `grafomem.hitl.approval.v1` domain-separated
signer already exist (`gns_browser`); the person→key binding is expected to be bootstrapped at
enrolment. **What is NOT decided here and must not be:** whether the approver co-signs one envelope or a
*linked* approver-attestation; and how the natural-person identity is made accountable + verified
(assurance). Both are 0009's, informed by the identity-assurance research. Until 0009 resolves, a B2
disposition is honestly *"agent prepared X; a human approved (recorded in the case system); captured
here"* — useful and Level-2-complete, but **not yet non-repudiable as to the person.**

---

## 2. The evidence digest

**Purpose.** Make *what the agent saw at decision time* **reconstructable and tamper-evident** without
placing any transaction PII in the record.

**Computation (normative).**
1. Assemble the **evidence set** presented to the agent — transactions, screening/sanctions hits, prior
   SARs, customer-profile snapshot — as an ordered list of items.
2. Replace any PII **identifier** inside an item (account, customer, counterparty) with its **HMAC
   pseudonym** (§3).
3. For each item, compute a **content commitment** `BLAKE2b-256(canonical_item_bytes ‖ sep ‖
   tenant_id)`.
4. Combine the per-item commitments into a **Merkle root** → `evidence_digest = {alg: "blake2b-256",
   root, item_count}`. A Merkle tree (not a flat hash) is REQUIRED so the bank can **selectively
   disclose** a single item to a supervisor with a membership proof, without revealing the rest.

**What a supervisor does with it.** Re-compute the root from the evidence set in the bank's own case
system and confirm it matches `evidence_digest.root` → proof the disposition rested on **exactly this
evidence, unaltered**; any post-hoc addition/removal/alteration changes the root.

**Two primitives, two jobs (normative — do not conflate).**
- **Identifiers → HMAC pseudonym.** Precedent: [`src/aml/cloud/invoice_pseudonym.py`](https://github.com/GNS-Foundation/grafomem/blob/main/src/aml/cloud/invoice_pseudonym.py)
  in grafomem — `pseudo = "OUT-" + HMAC_SHA256(k_tenant, ref)[:24 hex]`, `k_tenant = HMAC_SHA256(master,
  DOMAIN + tenant_id)`: deterministic, per-tenant, domain-separated, non-reversible,
  **equality-joinable within a tenant only**. This is the right primitive for `subject_ref` and for
  PII identifiers inside evidence items. (B2 uses a `SUBJ-` prefix rather than `OUT-`; same construction.)
- **Content → BLAKE2b/Merkle commitment.** Precedent: [`src/aml/provenance.py`](https://github.com/GNS-Foundation/grafomem/blob/main/src/aml/provenance.py)
  in grafomem — BLAKE2b, tenant-separated content commitments. This is the right primitive for the
  evidence-content digest — **tamper-evidence over content, not a joinable label.**

Using HMAC where a content hash is needed (or vice-versa) is a spec violation: HMAC gives joinability
(wrong for content integrity), a content hash gives no join (wrong for identifiers).

---

## 3. PII boundary (normative)

**MUST NEVER appear in the record:** customer / beneficial-owner names; account / IBAN / card numbers;
transaction amounts, dates, counterparties, or descriptions; the STR narrative text if it contains any
of the above; customer-profile content; screening-hit content; any free text that could re-identify a
person.

**What appears instead:**
- identifiers → **HMAC pseudonyms** (`subject_ref`, evidence item-ids);
- evidence content → **BLAKE2b/Merkle digests** only;
- the agent's rationale / STR narrative → **`rationale_digest`** (content commitment) or a
  **`rationale_ref`** case-system locator — **never inline** when it may contain PII;
- case pointers → **opaque locators** (`alert_ref`, `filing_ref`), meaningless outside the tenant.

**How a supervisor reaches the underlying evidence.** Not from the record. The record **points and
commits**; the supervisor resolves `alert_ref` / locators in **the bank's own case-management system,
under the bank's access controls**, then verifies the resolved evidence against the attested digests.
The record stays a **minimised, portable, tamper-evident index** — aligned with GDPR data-minimisation
and with DORA audit-access being exercised against the bank's systems, not against a PII-bearing record.

---

## 4. AML-specific vocabularies

These are the genuinely AML-specific, product-side part of B2 (per [ADR-0008](../decisions/ADR-0008-b3-best-client-of-general-ledger.md)).

### 4.1 `alert_typology` (closed, extend by versioning)

A closed enum of the triage typologies B3 handles; extended only by a version bump. Initial set
(illustrative, to be finalised against the detection ruleset in scope):

```
structuring | rapid_movement | unusual_pattern | sanctions_hit | pep_exposure |
adverse_media | high_risk_jurisdiction | third_party_funding | cash_intensive | other
```

`other` is permitted but SHOULD be rare; a growing `other` share is a signal the vocabulary needs a
versioned addition.

### 4.2 `disposition_outcome` (closed)

```
file      — an STR/SAR will be filed (see filing_ref when known)
no-file   — closed as not reportable; the documented decision NOT to file
escalate  — referred upward (e.g. L1 → L2 → MLRO) without a terminal file/no-file yet
```

Exactly one value per record. `no-file` is a first-class, fully-recorded outcome — **not** an absence
of a record (the no-file branch is where accountability most needs a durable, reconstructable trail;
see ADR-0009).

---

## 5. Relationship to the upstream general record (summary)

| Belongs to `cgr.disposition.v1` (upstream, general, **unresolved** — grafomem 0009) | Belongs to this B2 profile (product-side) |
|---|---|
| the two-signature envelope; `approver_identity`/`approver_act`/`approver_signature`; the natural-person identity + assurance | `alert_typology` and `disposition_outcome` vocabularies |
| `decision_date`/`recorded_at`, `authority_anchor`, `agent_identity` as general fields | AML semantics of each content field; the PII boundary applied to AML evidence |
| the evidence-digest and PII-boundary **primitives** (BLAKE2b/Merkle; HMAC pseudonym) | which AML evidence classes populate the evidence set |
| JCS canonicalisation, Ed25519 conventions (from v4) | mapping to STR/AMLR operational reality |

**Net:** author §1-A / §2 / §3 / §4 now as the B2 profile of `cgr.disposition.v1`. §1-B stays a typed
socket until grafomem 0009 resolves the general two-actor envelope upstream.
