---
status: proposed
record_date: 2026-08-31
capture_status: not-attested
---

# ADR-0007 — CGR governance domain + backfill expression (schema gaps)

- **Status:** **Proposed** (open — do not treat as decided)
- **Record date:** 2026-08-31

## Context

Recording decisions [ADR-0001..0006](README.md) to GRAFOMEM Cloud via `grafomem-cgr` was
**not possible** this session: the `cgr.attestation.v3` capture schema cannot express what these
records require. Two distinct gaps surfaced.

### Gap (a) — no governance/strategy domain

The capture `domain` is an **enum locked to `{deploy-verification, security-scan,
adversarial-review}`** — dev-loop capability domains. There is no `governance` / `strategy` /
`compliance` value, so six EU business/legal/GTM decisions have no truthful domain to be filed
under. Forcing them into `adversarial-review` (or any dev domain) would misattribute strategy
decisions into a dev-review domain and pollute the reputation substrate. We declined to do that.

### Gap (b) — no way to express backfill

`cgr.attestation` records **`created_at` = capture time** only. There is **no distinct
`decision_date`** and **no `backfilled` / provenance flag**. A decision made 2026-08-29 and
recorded 2026-08-31 (this exact case) would be indistinguishable from one captured the moment it
was made — the record would silently imply contemporaneous capture, which is false.

## Open schema questions (unresolved)

1. **Domain vocabulary** — does CGR add a `governance`/`strategy` domain (or a domain taxonomy
   that isn't a fixed dev-loop enum), and how is it kept from diluting the score semantics
   (governance records should be recordable but non-scoring, cf. `verifiability_tag: rule`)?
2. **Backfill / temporal provenance** — does the signed body gain distinct `decision_date` +
   a `backfilled`/`recorded_at` provenance, so "when decided" ≠ "when recorded" is first-class
   and tamper-evident, not stuffed into free-text?

## Relationship to the true-additive vs schema-bump tradeoff

This is a **second instance** of the same design question raised in
[`exec/grounded-score-decision-record.md`](../../../grafomem/exec/grounded-score-decision-record.md)
*(referenced by path; not present in this repo)*: new signed-body fields (here: `decision_date`,
`backfilled`, and possibly a domain-vocab field) can be added **true-additive** (a v3.1 superset —
existing verifiers already recanonicalize the whole non-envelope body and accept unknown fields,
so signatures still verify) **vs.** a **schema bump** to v4 with golden regeneration. The
forward-compat probe (2026-08-27) showed the additive path is open for verification; the open part
is the *scoring/semantics* contract, not the wire format. This ADR does **not** resolve which path
CGR takes — it records that governance-domain + backfill are the concrete fields forcing the
choice.

## Product requirement (not just a dogfooding issue) — flag for B0.7

The backfill gap (b) is a **product requirement**, not merely an internal capture inconvenience.
In an **AML disposition**, *when the analyst decided* vs *when the decision was recorded* is a
**regulatory distinction** a supervisor will ask about (timeliness of SAR/STR filing,
decision-vs-record lag, audit reconstruction). A compliance product whose attestations cannot
separate decision-time from record-time is not supervisable on that axis. **Flagged for B0.7.**

## Status

Proposed. Not resolved this session. No capture/attestation performed (deferred pending the
schema decision).
