---
status: accepted
decision_date: 2026-08-31
record_date: 2026-08-31
provenance: contemporaneous
capture_status: not-attested
---

# ADR-0008 — B3 is built as the best possible client of a general ledger

- **Status:** **Accepted**
- **Decision date:** 2026-08-31

> **Numbering note.** This is `ADR-0008`, not `ADR-0007`. `ADR-0007` was used and then **relocated
> to the Foundation** (it is now a stub pointing at `GNS-Foundation/grafomem`
> `docs/decisions/0002`). Per this log's convention, **numbers are permanent** — a relocated or
> superseded record keeps its number and is never reused — so the next record is `0008`.

## Context

B3 in the build plan is the **reference application**: a single AML disposition workflow, end to
end, governed. There is a standing temptation to build it as *the* product — to let the AML use
case shape the ledger it writes to. The alternative is to build B3 as **one client of a general
ledger** that happens to be the first and best one.

GRAFOMEM Cloud is a **general ledger** for governed agent memory and reputation; the AML assistant
is an application on top of it. The architectural question — does the product surface lead and pull
the governance layer along, or does the governance layer lead with the product as one option —
should not be prematurely resolved in code. It should be **decided by market outcome**, and the
build should preserve both futures until then.

## Decision

**The agent assistant is designed as one client of GRAFOMEM Cloud, not as its only client.**
GRAFOMEM Cloud is a general ledger; the assistant is its **first and best** client. Whether the
product surface leads (and pulls the governance layer) or the governance layer leads (with the
product as an option) is **left to be decided by market outcome rather than by architecture**.

## Consequences — the operative constraints

- **No AML-specific or product-specific assumptions in the write path.** What B3 writes to the
  ledger must be expressible for any governed agent, not only an AML analyst.
- **Anything the assistant needs that the ledger cannot express becomes a Foundation decision
  record, not a product-side workaround.** This has already happened **four times** — `GNS-Foundation/grafomem`
  `docs/decisions/` `0001` (grounding dimension), `0002` (governance domain + backfill), `0003`
  (principal identity is not stable), `0004` (no identity-continuity across rotation). A gap in the
  ledger is fixed *in the ledger*, upstream, not patched around in the product.
- **"Key gateway" means first and best client, not sole client.** The assistant's privileged
  position is that it exercises the ledger hardest and earliest — not that it owns it.
- **Cost asymmetry.** Designing B3 as the product surface today would be **cheap now and expensive
  to reverse**; the **general-client shape costs little and preserves both futures.** The cheap
  reversible choice is the general-client one.
- **Cross-reference [ADR-0005](ADR-0005-standard-gns-foundation-products-ulissy.md).** A Foundation
  standard whose only real client is the Ulissy product is *a vendor format with a foundation logo*.
  This constraint — a genuinely general write path, with gaps pushed upstream as Foundation records
  — is **what keeps ADR-0005's separation substantive** rather than nominal.

## Open sub-questions

- What is the concrete test for "product-specific assumption in the write path" that a B3 code
  review applies — how do we catch a leak of AML semantics into the ledger before it lands?
- The four upstream records (`0001`–`0004`) are a *demonstration* of this constraint working; is
  the rate at which the assistant surfaces ledger gaps a signal worth tracking (a healthy general
  ledger should keep producing them for a while, then taper)?
- Market outcome decides product-leads vs. layer-leads — what observable would settle it, and who
  watches for it?
