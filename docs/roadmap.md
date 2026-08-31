# Roadmap — EU Governed Agent

**Status:** draft, 2026-08-31
**Stage:** 2 of the development criteria (research → **roadmap** → execution → approval)
**Owner:** Camilo Ayerbe Posada (Ulissy S.R.L.)
**Inputs:** `docs/project-brief.md` §1–5, `docs/decisions/ADR-0001..0008`,
`GNS-Foundation/grafomem docs/decisions/0001–0005`
**Team:** solo — Camilo + Claude Code

---

## Sequencing principle

Engineering before paperwork. The signed, offline-verifiable artifact is the
only thing in this plan no competitor has; the DORA pack is table stakes every
incumbent already holds. So the technical work goes first and is done properly,
even though the paperwork is faster to ship.

Two consequences follow:

- **The first phase is a design decision, not a build.** P0 below produces a
  resolved schema question, not code. Treating it as an implementation task is
  the main way this roadmap fails.
- **B0.0 (LEI) runs in the background from day one.** It is not paperwork in
  the same sense: it has external processing latency nobody controls, blocks
  nothing, and is a hard prerequisite for appearing in any client's DORA
  Register of Information. Start it, then ignore it.

Per **ADR-0008**, everything built here is a client of a general ledger. Where
the assistant needs something GRAFOMEM Cloud cannot express, that becomes a
Foundation decision record — not a product-side workaround.

---

## P0 — Resolve the relation mechanism *(Foundation, blocking)*

**This is the critical path.** Four Foundation records converge on one absent
primitive: there is no way to express a *relation between attestations*.

| Record | Symptom of the same gap |
|---|---|
| `grafomem 0001` | grounding dimension needs new signed fields |
| `grafomem 0002` | no governance domain; backfill inexpressible |
| `grafomem 0004` | no identity continuity across rotation |
| `grafomem 0005` | custody-managed principals, blocked on 0004 |

`0004` argues these are not four problems but one, seen from four angles, and
proposes a generic edge (`supersedes` / `continues` / `corrects`). It also
records the loop that makes this urgent: a `continues` edge needs a signer that
outlives the rotated key, which wants a stable principal, which is `0005`,
which is blocked on `0004`. **The loop must be broken from the 0004 side.**

**P0 is a design spike, not an implementation.** Its output is a decision.

- **P0.1 — Expressiveness survey.** What a relation edge must express to close
  all four records. Include revocation: `geiant#9` solved it in code for one
  implementation, but whether an *attestation* can express revocation is the
  unasked sibling of 0002.
- **P0.2 — Compatibility analysis.** The additive path against deployed
  verifiers, drawing on the 2026-08-28 unknown-field probe. Determines whether
  a generic edge can ship under the unchanged `cgr.attestation.v3` schema
  string or requires a bump.
- **P0.3 — Migration story.** What `@gns-foundation/cgr-verify`, `@geiant/core`
  and the read surface each need, in what order (expand-contract).
- **P0.4 — Decide.** Flip `0004` to accepted with a `decision_date`, and record
  how `0001`, `0002` and `0005` resolve under it. Regenerate the byte-parity
  golden fixture either way.

**Also fix in P0.2:** `0001` currently cites internal probe evidence no public
reader can reach. Either publish the findings once the mitigation ships, or
restate the record so it stands alone.

**Done when:** `0004` is accepted, `0001`/`0002`/`0005` have a resolution path,
and the fixture is regenerated.

---

## P1 — B0.7 as a general capability

Unblocked by P0. Build the signed-attestation capability **generally**, then use
it for the DORA register entry as its first application — not the reverse.

- **P1.1** — Implement the relation edge as decided in P0.
- **P1.2** — Governance domain + temporal provenance (`decision_date` distinct
  from `created_at`, backfill flag). Per `0002`, temporal provenance is a
  first-class requirement for regulated use, not a dogfooding convenience.
- **P1.3** — Conformance tests in the executable validation suite.
- **P1.4** — **Backfill the eight ADRs**, flagged as backfilled with distinct
  decision and capture timestamps. This is the dogfooding commitment finally
  honoured, and the first real exercise of the new fields.
- **P1.5** — Signed DORA register entry: provider identity, sub-processor
  chain, data-residency claims as signed fields, verifiable offline.

**Watch:** P1.5 depends on **B0.2** (sub-processor chain), which is where the
inference-hosting decision actually gets made — EU-region, EU-domiciled, or
self-hosted. That decision constrains B3 and cannot be deferred past here.

---

## P2 — Clear the operational debt

Not feature work, but the system is not in a clean state until it is done.

- **P2.1 — Rotation window.** Follow
  `grafomem-internal/claude/geiant-rotation-day-runbook.md`. One window: mint
  replacement identity, stage on Railway, verify a breadcrumb end-to-end, then
  merge `geiant#9`, then verify enforcement bites. Step 4 is the rollback point.
- **P2.2 — Merge `geiant#9`.** Inside the window only. Outside it, this is an
  outage by construction: `mcp-perception` and `geiant` both run the denylisted
  `agent_pk`.
- **P2.3 — Source-of-truth for design material.** Four unversioned directories
  surfaced on 2026-08-31. Upstream is a claude.ai Project, mirrored to disk by
  hand, with derivative public copies maintained manually and no defined
  process. Worth a Foundation record.

*If P0 resolves toward a `continues` edge, P2.1 gets materially better — the
replacement agent inherits a linked chain instead of starting at `block_index
0`. Sequencing P2 after P0 is deliberate.*

---

## P3 — B3, the reference application

The AML alert triage and disposition-drafting workflow. Narrow and deep: one
workflow, fully governed, that a compliance officer can sign off on.

Constrained by **ADR-0008**: no AML-specific assumptions in the write path.
Anything the workflow needs that the ledger cannot express goes back to P0's
mechanism as a Foundation record.

*Not specified further here.* Scoping B3 in detail before the Iccrea
conversation is building against an unvalidated premise — the workflow shape
should absorb what that conversation returns.

---

## P4 — B0.1–B0.6, the DORA pack

Deliberately last, per the sequencing principle. Document work, no engineering
dependencies, fast once the technical story is settled.

Register data sheet · sub-processor chain with LEIs (**decided in P1**) ·
Article 30(2)/(3) contract schedule · exit plan · incident-notification
protocol · security and resilience evidence.

Assume **Art. 30(3)** applies: a live AML triage system supports a regulatory
function.

**External input required — not answerable in-house.** Three commercial/legal questions gate this
window: cross-border registration / VAT / supervisory-notification from an Italian S.R.L., and the
local-subsidiary threshold (ADR-0004 (a)/(b)); and whether Ulissy S.R.L.'s corporate form /
capitalization carries Art. 30(3) liability at target contract sizes (ADR-0003). These need an
**Italian commercialista** and likely **counsel** — they cannot be answered by the team. They are
**P4-window** questions, **not P0 blockers**; the corporate-form one gates the pack's *credibility*,
since a bank's third-party-risk review assesses it directly.

---

## P5 — Iccrea

Discovery, not a sale. The question is whether the liability argument —
AMLR Art. 18 makes responsibility non-transferable, so who is at fault when an
agent acts — lands with an MLRO.

**Horizon: autumn 2026.**

**Honest note on sequencing.** P0–P4 ahead of P5 is your call and it is
defensible: you would rather walk in having built the thing than having pitched
it, and after 2026-08-31 you have a working system rather than a deck —
jurisdiction scoping held against a live leaked key for 164 days.

But the risk P5 retires is *commercial*, not technical, and it is the risk that
determines whether P3 is worth building at all. A perfect signed artifact
de-risks the *second* meeting — the third-party-risk review — not the first.
If the schedule slips, consider holding P5 at its date and letting P4 slide
rather than the reverse.

---

## Dependency summary

```
B0.0 (LEI) ──────────────── background, start immediately, blocks nothing
                            └── prerequisite for P4 and P1.5

P0 (relation mechanism) ─── CRITICAL PATH
  └── P1 (B0.7 general) ─── B0.2 hosting decision lands here
        └── P1.5 register entry
  └── P2 (rotation + #9) ── improves if P0 gives a `continues` edge
        └── P3 (B3) ─────── shape informed by P5
              └── P4 (DORA pack)

P5 (Iccrea) ─────────────── autumn; commercial risk, not technical
```

---

## What would change this plan

- **P0 resolves toward a schema bump** rather than additive → P1 grows a
  coordinated ecosystem migration and the timeline extends materially.
- **The Iccrea conversation happens early** → P3's shape should absorb it
  before P3 starts, not after.
- **A second writer appears for GRAFOMEM Cloud** → ADR-0008's open question
  resolves toward the layer leading, and P3 drops in priority.
- **P0 stalls** → nothing downstream moves. This is the single point of
  failure in the plan, and the argument for time-boxing P0.4 with an explicit
  decision date rather than letting it stay open.
