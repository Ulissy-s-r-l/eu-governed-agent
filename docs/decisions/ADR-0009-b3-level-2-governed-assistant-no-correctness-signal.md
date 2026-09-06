---
status: accepted
decision_date: 2026-09-06
record_date: 2026-09-06
provenance: contemporaneous
capture_status: not-attested
---

# ADR-0009 — B3 is a Level 2 governed assistant; AML does not emit a correctness signal

- **Status:** **Accepted**
- **Decision date:** 2026-09-06

> Cross-refs: [ADR-0008](ADR-0008-b3-best-client-of-general-ledger.md) (B3 is the best client of a
> general ledger), the roadmap P3 (B3 = AML alert triage + disposition drafting), and
> `GNS-Foundation/grafomem` decision 0009 (the two-actor / attestable-disposition standard gap).
> Citations in this record follow the Foundation's primary-source verification convention (see
> `docs/decisions/README.md` → "Verifying load-bearing claims").

## Context

B3 is the AML alert-triage and disposition-drafting reference application. Before committing to its
shape we tested one assumption that would decide whether it can be built as a *learning* system:
**does AML alert triage produce a resolution signal — a later determination of whether a disposition
was correct?** CGR's economics depend on joining decisions to **resolved outcomes**; if AML
dispositions do not resolve, there is nothing to evaluate, and outcome-grounded policy learning is
unbuildable in this domain *regardless of architecture*. The research (2026-09-06) established that
AML triage does **not** natively emit a usable correctness signal.

**The comparison that frames it.** CGR's proven domain is receivables (the Meridian sim): an invoice
**pays or defaults** — near-total coverage, **30–90 day** latency, unambiguous binary. AML sits in the
opposite corner:

- **~2% of alerts become SARs**, and **~4% of filed SARs receive any law-enforcement feedback**
  (Bank Policy Institute, 2018 survey of large banks — the most-cited hard number; treat both figures
  as **indicative base rates**, not audited). Whether a specific STR led to investigation or
  prosecution is, in practice, **unknowable to the filer** (FIU-analysis and criminal-investigation
  confidentiality).
- The statutory feedback duty — **AMLD6 (Directive (EU) 2024/1640) Art. 42** (*primary-verified,
  EUR-Lex*) — is **annual, aggregate, and about reporting quality** (quality/timeliness/description/
  documentation), explicitly **"not … each report,"** and says nothing about outcomes. Italy's UIF is
  the strongest EU regime and is still per-reporter aggregate; Germany and the Netherlands are weaker.
- **The no-file branch — the overwhelming majority of alerts — receives essentially nothing.** A wrong
  no-file surfaces only via **supervisory look-backs** (sample-based, risk-timed, multi-year gaps) or
  **enforcement actions** (rare, years late). There is **no positive-confirmation channel** that a
  "not suspicious" close was correct.

**The circularity finding (structural, not an oversight).** Because **no ground truth for laundering
exists** in real financial data, AML vendors and in-house models train on **analyst disposition
labels** (alert closed/escalated) and, at best, **filed-SAR flags** — a *filing decision*, not a
confirmation. So the models **learn to imitate the analyst, not to be correct**; the academic
literature names this proxy-label **circularity bias** (e.g. arXiv 2112.07508). This is inherent to the
domain's absent ground truth, not a defect any vendor can engineer away.

**Two signals, never to be conflated.** AML triage emits an **abundant, low-latency
analyst-*agreement* signal** (QA sampling days–weeks; four-eyes contemporaneous; escalation reversals;
disposition labels) and a **near-absent, high-latency true-*correctness* signal** (confirmed laundering
/ conviction / backtested confirmed case — months-to-years-to-never, and for no-file ≈ zero). CGR needs
the second; the domain supplies the first.

## Decision

**B3 is a Level 2 governed assistant. It makes no learning or accuracy claim.**

B3 provides:
- **Reusable skills** — evidence gathering and narrative drafting — and the governed disposition
  workflow (triage → drafted disposition → human review).
- **An attestable, human-signed disposition** (agent prepares X; a named, accountable natural person
  decides and signs — the standard gap tracked in `grafomem` 0009).

B3 does **not** claim to learn what a *correct* disposition is, nor to optimise accuracy against AML
outcomes, because the domain does not supply the outcome-grounded correctness signal such a claim would
require. **B3 is explicitly not built as a Level 3 (validated-policy-update) system in AML.**

## Consequences

- **Level 2 needs no resolution signal.** Reusable skills and an attestable human-signed disposition
  stand entirely without any determination of whether the disposition was later confirmed correct.
  Nothing about B3's value depends on the AML feedback gap.
- **The regulation rewards defensible process and human accountability, not model accuracy.** The
  operative requirements are a named, accountable natural person and exercised human oversight —
  **AMLR (Reg. (EU) 2024/1624) Art. 11 (Compliance functions) + Recital 38** (responsibility rests
  ultimately with the management body) and **AI Act (Reg. (EU) 2024/1689) Art. 14 (Human oversight)**
  (*primary-verified*). None rewards accuracy-optimisation. So building to *governance* rather than to
  *accuracy* is aligned with what a supervisor actually assesses.
- **The consequence that is an advantage — honesty as a moat.** CGR's `verifiability_tag` and
  evidence-gating can represent this domain **honestly**: a disposition's CGR score **stays UNPROVEN on
  analyst-agreement alone** and moves only on **confirmed outcomes**, which are rare and late.
  Competitors present **imitation (analyst-agreement) as accuracy**; B3 instead tells an MLRO the truth
  about what is and is not known. Under supervisory scrutiny — and under DORA/model-risk validation —
  the honest position is the **stronger** one and the one that survives.
- **A narrow, honest Level 3 remains possible later, if tiered — not now.** Where a true-correctness
  signal does arrive (escalation reversals; a confirmed-case backtest), CGR's evidence-gating is the
  right mechanism to admit it as **rare, high-verifiability** evidence without letting analyst-agreement
  masquerade as it. This is a trickle, not a training loop, and it is **not** part of B3's scope or
  claim today.

## Open sub-questions

- What is the concrete review test that keeps an accuracy/learning claim from creeping back into B3's
  copy, UI, or sales materials — given the commercial pull to claim "our AI learns"?
- If a client (e.g. an MLRO) *wants* an accuracy narrative, what is the honest reframing that satisfies
  the want without the overclaim (defensible process + human accountability + "unproven until
  confirmed")?
- When the rare true-correctness signal arrives, exactly how is it tiered against analyst-agreement in
  the CGR evidence model, and who confirms it? (Deferred; not in B3 scope now.)
