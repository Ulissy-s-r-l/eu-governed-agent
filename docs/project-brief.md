# Project Brief — EU Governed Agent for Regulated Finance

**Status:** canonical brief (reconciled 2026-08-31 against the ADRs and the Foundation decision log). **Owner:** Camilo Ayerbe Posada (Ulissy S.R.L. / GNS Foundation). **Working name:** TBD.

> Sections 1–5 are the canonical thesis/wedge/clock/architecture/assets. Section 6 defers to the
> ADRs ([docs/decisions/](decisions/README.md)) as the source of truth for the decisions. Sections
> 7–8 are **superseded-in-part** — research is done, build workstreams are about to be re-sequenced
> in `docs/roadmap.md`.

---

## 1. Thesis

Consumer AI assistants are winning on capability and losing on trust. Instinct raised $350M at $2.5B while under public scrutiny for terms permitting training on user data and for retaining email copies after disconnection. That product cannot be sold into an EU regulated financial institution at any price.

The opportunity is not more autonomy. It is **defensible autonomy**: an agent whose every action is attributable, scoped by trust tier, and reconstructable after the fact — because the memory layer was governed from day one rather than audited afterwards.

We already own the substrate. We do not yet own an application.

---

## 2. Vertical and wedge

**Vertical:** EU regulated finance.

**Wedge workflow:** AML / KYC alert triage and disposition drafting.

Rationale:

- Headcount-heavy with false-positive rates above 90% — pain is already budgeted.
- Every disposition already requires a written, defensible rationale. We automate an existing audit burden rather than introducing a new one.
- The human analyst signs. The agent prepares evidence and drafts narrative. This keeps the system outside AI Act Annex III classification.
- The artifact a supervisor asks for **is** the agent's memory: what the system knew, when, on what basis, and who reviewed it.

**Buyer:** MLRO / Head of Financial Crime Compliance, counter-signed by CRO. Not the CIO. This is an existing budget line, not experimental spend.

---

## 3. Regulatory clock (verified 2026-08-29)

| Date | Event | Relevance |
| :---- | :---- | :---- |
| 1 Jul 2025 | AMLA operational, Frankfurt | Rule-setting underway |
| Through 2026 | AMLA issues 23 RTS/ITS | Control logic must absorb evolving Level 2 |
| 10 Jul 2027 | AMLR (EU) 2024/1624 applies in all 27 MS | Single rulebook — hard deadline |
| Jul–Dec 2027 | AMLA selects directly supervised entities | |
| 1 Jan 2028 | AMLA direct supervision begins | |
| 2 Dec 2027 | AI Act Annex III high-risk obligations | Deferred by Digital Omnibus (EU) 2026/1744 |
| 2 Aug 2028 | AI Act Annex I high-risk obligations | Deferred |

**Positioning rule:** do not anchor go-to-market to the AI Act. Its high-risk deadlines moved 16 months on 27 Jul 2026. Anchor to AMLR, DORA, MiFID II record-keeping, MAR surveillance, and model-risk governance — none deferred.

Two corollaries:

- 2026 is the preparation year. Firms are building against standards still landing. Rule-absorbing beats rule-hardcoded.
- AMLA supervision vs national supervision changes the supervisor, not the standard. The addressable market is all obliged entities, not the ~40 selected.
- Grandfathering under the Omnibus favours deployments placed on the market before the new dates, absent substantial modification.

---

## 4. EU-native architecture principles

1. **Jurisdiction is a first-class attribute of memory**, not a config flag. Generalize the existing `role@region-geiant` handle scheme and region-anchored delegation so every attestation carries the supervisory regime it was produced under.
2. **EU-only residency and sovereign deployment by default.** This is the cleanest differentiator against US assistants.
3. **24 official languages.** CDD files and AML narratives are written and read in local language. Real cost, real moat.
4. **Attestations verify identically** for a Frankfurt inspector and a national supervisor.
5. **Human oversight is the ceiling, by design.** We sell less autonomy with proof, not more autonomy. The word is *defensible*, never *extraordinary*.

---

## 5. Assets already in hand

- **GRAFOMEM** — governed runtime memory framework; open conformance standard and executable validation suite (`GNS-Foundation/grafomem`).
- **CGR** — Capability-Grounded Reputation: signed, offline-verifiable agent track records from resolved outcomes. Beta(1,1) posterior scoring, `cgr.attestation.v3` (18 signed fields, JCS/Ed25519). Paper draft v0.1.
- **Grounded (Uncertainty) Score** — second CGR dimension under design; the schema decision is recorded as `GNS-Foundation/grafomem` → `docs/decisions/0001` (grounding dimension: true-additive vs schema-bump).
- **GEIANT Perception** — live MCP server with trust tiers (`seedling | navigator | trailblazer | sovereign`) and EU AI Act Art. 9/12/13/14 compliance tooling.
- **GNS** — identity and delegation layer.
- **IETF drafts** — SEAT/RATS attestation standards work.
- **`cc-builder@ulissy` dogfood ledger** — a real agent accumulating a signed track record. Arguably a stronger first proof than any deck.

**As of 2026-08-31 (this project's own governed development record):**

- **Five Foundation decision records on `main`** (`GNS-Foundation/grafomem` → `docs/decisions/` `0001`–`0005`): grounding dimension (`0001`), governance domain + backfill (`0002`), principal identity is not stable (`0003`), no identity-continuity across rotation (`0004`), custody-managed principals (`0005`). These formalize the CGR schema's open questions as the standard's own decision log.
- **Revocation enforcement written but not yet merged** — the mechanism exists in code; landing it is pending.
- **`0004`'s relation mechanism now gates `B0.7`.** `0004` shows that `0001`/`0002`/`0004` are three faces of one absent primitive — the schema has **no general way to express a relation between attestations** (`supersedes` / `continues` / `corrects`). The signed register entry (B0.7) depends on that relation primitive, not merely on a field addition.

---

## 6. Decisions

The decisions were made **2026-08-29**. Their canonical records — context, consequences, and open
sub-questions — are the ADRs in **[docs/decisions/](decisions/README.md)**; this section
cross-links them rather than restating them.

- **Sell the assistant, with GRAFOMEM embedded** as its governance layer (not the layer standalone) → [ADR-0001](decisions/ADR-0001-sell-assistant-with-grafomem-embedded.md)
- **Sequenced beachheads: Italy first, then Germany + the Netherlands in parallel** → [ADR-0002](decisions/ADR-0002-sequenced-beachheads-italy-then-de-nl.md)
- **Accept DORA ICT third-party-provider status; design for Art. 30(3)** → [ADR-0003](decisions/ADR-0003-accept-dora-ict-provider-art-30-3.md)
- **Ulissy S.R.L. is the single EU contracting entity** (one Italian entity serves all 27 MS) → [ADR-0004](decisions/ADR-0004-ulissy-srl-eu-contracting-entity.md)
- **Standard belongs to GNS-Foundation, products to Ulissy S.R.L.** → [ADR-0005](decisions/ADR-0005-standard-gns-foundation-products-ulissy.md)

Each ADR carries that decision's consequences and channel/capacity flags (e.g. the wave-two
commercial-load flag on ADR-0002, and the "separation must be real, not nominal" governance
condition on ADR-0005) as its open sub-questions.

### Still open

- [ ] **Non-dilutive funding: EIC Accelerator / Digital Europe fit assessment.** **DEFERRED (2026-08-29) — agreed, not decidable yet** → [ADR-0006](decisions/ADR-0006-defer-eic-digital-europe-assessment.md). Both programmes want evidence of traction and a credible first customer, so the assessment is worth more after the Iccrea conversation than before it. Eligibility is already protected by the Ulissy S.R.L. domicile decision (ADR-0004), so nothing is lost by waiting. Revisit once wave one produces a reference or a clear refusal.

---

## 7. Research workstreams

> **Superseded-in-part (2026-08-31): R1–R4 are complete** (delivered 2026-08-29). Retained below
> for reference; the forward-looking, sequenced plan lives in `docs/roadmap.md` (once it exists).

**R1 — Incumbent landscape.** Who sits in AML alert triage at EU institutions today. What they are shipping on agentic AI. Where the unclaimed gap is.

**R2 — AMLA Level 2 mapping.** The 23 RTS/ITS: which ones constrain evidence format, CDD procedure, and record-keeping. Which are published, which pending.

**R3 — Buyer discovery.** Cooperative and regional banking groups across the EU (BCC, Sparkassen, Volksbanken, Rabobank locals, Spanish cajas, Crédit Agricole regionals). Sizing, procurement pattern, existing vendor lock-in.

**R4 — DORA obligations on us as a provider.** Contractual, exit, audit-rights, and register-of-information consequences of selling into scope.

---

## 8. Build workstreams (Claude Code)

> **Superseded-in-part (2026-08-31):** B0–B4 below are workstreams, not yet a sequenced roadmap,
> and are **about to be re-sequenced**. Treat them as the pre-roadmap inventory; the forward-looking
> plan is **`docs/roadmap.md`** (once it exists).

### Development criteria

Four stages, in order. Nothing skips ahead.

1. **Research.** Understand the landscape before committing to a shape. *Status: complete for this project — R1–R4 delivered 2026-08-29.*
2. **Define roadmap.** Convert findings into sequenced, scoped work with dependencies made explicit. *Status: next. B0–B4 below are workstreams, not yet a roadmap — they lack sequencing, sizing and acceptance criteria. Their sequenced form is `docs/roadmap.md`.*
3. **Execution — real practice.** Cowork (Claude) plans and drafts; **Claude Code runs in auto mode and lands work directly** — implementing, opening PRs, and merging within the session. There is **no blanket return-for-approval gate**; the throughput of auto mode is the working default. What *does* require Camilo's explicit approval **before it lands**, without exception, is anything in these three carve-outs:
   - **Key material** — signing keys, seeds, credentials, custody artifacts.
   - **Production writes** — deploys, publishing, and any capture/attestation to GRAFOMEM Cloud (an attestation is a durable public claim).
   - **Schema changes affecting deployed verifiers** — the `cgr.attestation` wire format, where a change can break consumers in the wild.

   These carve-outs are not hypothetical: **today (2026-08-31) produced all three** — key material (Foundation seed custody + SSH-signed commits), production writes (merges that auto-deploy and the registry publish), and a deployed-verifier schema question (`0001`/`0002`) — each handled under the gate. The gate is narrow and load-bearing, and it is the same human-oversight principle the product sells.
4. **Dogfood to GRAFOMEM Cloud from day one.** Every Camilo + Claude agent interaction on this project is captured to GRAFOMEM Cloud via the `grafomem-cgr` MCP server. The project's own development record becomes a signed, verifiable track record — the strongest available demonstration that the thing works, produced as a by-product of building it.

*Prerequisite for stage 4:* `grafomem-cgr` must be connected as an MCP server in each surface that needs it — the Claude app (Settings → Connectors) and Claude Code (`claude mcp add`) are configured separately. Capture is not retroactive; it begins at connection. *(Note: capture of governance/backfilled decisions is itself blocked on `docs/decisions/0002`; see §5.)*

### Workstreams

### B0 — DORA Register Pack *(first, ahead of everything else)*

**Rationale.** The DORA Register of Information is the only existing, mandatory, structured regulatory artifact that describes an ICT provider's identity, behaviour and supply chain. Every EU financial entity must maintain it and submit it to its competent authority. It therefore does two jobs at once:

1. **Sales.** Arriving with a complete pack converts a months-long third-party risk negotiation into a short one, and out-professionalizes every startup competitor. Pays off whether or not the first design-partner conversation succeeds.
2. **Standard.** It is the first surface on which to *demonstrate* signed, independently verifiable provider claims rather than argue for them in the abstract. A running verifiable register entry is a far stronger input to the AMLA Art. 26(5) / Art. 9(4) consultations than a position paper.

**B0.0 — Blocker: obtain an LEI for Ulissy S.R.L.** Without a Legal Entity Identifier the company cannot be entered in any bank's Register of Information at all. Low cost, few days, hard prerequisite. Do this first. Capture EUID as well where applicable.

**B0.1 — Register data sheet.** Structured entity and service data matching the ESAs' register templates: legal entity identity (LEI/EUID, registered address), service description, the client function supported and its criticality classification, data-processing and data-storage locations, start/end dates, notice periods, applicable law.

**B0.2 — Sub-processor chain with LEIs.** Full ICT supply chain, each subcontractor LEI/EUID-identified, per Delegated Regulation (EU) 2025/532. **Design constraint, not a disclosure exercise:** if agent inference calls a non-EU foundation-model API, that provider appears in a supervisor-submitted register as part of the supply chain for a critical-or-important AML function. The inference-hosting decision (EU-region / EU-domiciled provider / self-hosted) is therefore determined here, before B3, not optimized later.

**B0.3 — Article 30 contract schedule.** Pre-drafted clause set covering both Art. 30(2) (all contracts) and Art. 30(3) (critical-or-important functions). Assume Art. 30(3) applies: a live AML triage system supports a regulatory function. Includes audit and access rights for the entity, its auditors and competent authorities; quantitative and qualitative performance targets and SLAs; incident assistance terms; TLPT participation where in scope; data access, recovery and return in an accessible format on termination or insolvency. Consider any published standard contractual clauses.

**B0.4 — Exit plan.** Executable, not narrative: transition period, data export format, assisted migration, service continuity during handover.

**B0.5 — Incident notification protocol.** Defined timelines and channels flowing through to the entity's DORA major-incident reporting obligations.

**B0.6 — Security and resilience evidence.** Due-diligence questionnaire responses, ISO 27001 / SOC 2 status or roadmap, encryption and data-residency attestations, DPA/GDPR terms.

**B0.7 — Signed register entry (the standard-setting piece).** Produce the above as a CGR-signed artifact: provider identity, sub-processor chain and data-residency claims as signed fields, independently verifiable offline. **Depends on the CGR schema question now in the Foundation decision log** — `GNS-Foundation/grafomem` → `docs/decisions/0001` (true-additive vs schema-bump) and `0002` (governance domain + backfill). As of 2026-08-31, `0004` shows the common cause is the absence of a relation mechanism between attestations, and **`0004`'s relation primitive now gates B0.7** — a signed register entry that supersedes a prior one needs a `supersedes`/`continues` edge the schema does not yet have. Resolving `0001`/`0002`/`0004` together is the prerequisite.

*Note: B0.1–B0.6 are deliverable without B0.7 and should not be blocked by it. Ship the conventional pack first; add the signed layer as the differentiator.*

### B1–B4

- **B1** — Jurisdiction-scoped attestation: extend CGR/GEIANT so region and supervisory regime are signed fields. Interacts with the schema question in `docs/decisions/0001`.
- **B2** — AML disposition evidence schema: what the agent must record for a narrative to be defensible under AMLR.
- **B3** — Reference application: single workflow, end to end, governed.
- **B4** — Conformance suite extension: AMLR/DORA evidence assertions added to the GRAFOMEM executable validation suite.

---

## 9. Sources

- Digital Omnibus on AI, Regulation (EU) 2026/1744 — OJ 24 Jul 2026, in force 27 Jul 2026.
- AMLR, Regulation (EU) 2024/1624 — applies 10 Jul 2027.
- AMLA Regulation, Regulation (EU) 2024/1620 — operational 1 Jul 2025.
- AMLD6, Directive (EU) 2024/1640.
