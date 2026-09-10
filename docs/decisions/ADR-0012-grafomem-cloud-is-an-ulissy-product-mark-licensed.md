---
decision_date: 2026-09-10
record_date: 2026-09-10
provenance: recorded-while-scoping-the-standard/product-separation; the code facts were RE-DERIVED from GNS-Foundation/grafomem at 137dc51 on 2026-09-10, not transcribed from the earlier working note
capture_status: not-attested
---

# ADR-0012 — GRAFOMEM Cloud is an Ulissy product; the "Grafomem" mark is licensed, not owned

- **Status:** Accepted
- **Decision date:** 2026-09-10
- **Renumbered** from `ADR-0011` before merge — that number was already claimed by an unmerged PR
  (`ADR-0011-verifier-tier-decomposition`). See the numbering note in the
  [decision log](README.md).

## Context

[ADR-0005](ADR-0005-standard-gns-foundation-products-ulissy.md) split the venture's two assets:
**the standard belongs to GNS-Foundation, the products belong to Ulissy S.R.L.** It left four
sub-questions open, three of which this record answers in part: the licensing relationship between
the bodies, where shared assets sit, and the trademark split.

Scoping the separation surfaced that the split is a decision on paper and not yet a fact in the
code. This record states the product-side position; the Foundation-side counterpart is
[`GNS-Foundation/grafomem` → `docs/decisions/0012`](https://github.com/GNS-Foundation/grafomem/blob/main/docs/decisions/0012-product-code-resident-in-the-foundation-repo-by-exception.md),
which grants the code a time-limited residency exception. The two records must be read together and
must not drift.

## The entanglement finding

Recorded here in full — this is a product-side liability, so it belongs in the product repo's own
record and not only upstream. Verified against `GNS-Foundation/grafomem` at commit `137dc51` on
2026-09-10, stated at the granularity measured.

**1. `GNS-Foundation/grafomem` is PUBLIC.** `gh repo view` reports `visibility: PUBLIC`. `LICENSE`
is `MIT License / Copyright (c) 2026 GNS Foundation`.

**2. The product code lives in it.** `src/aml/cloud/` holds **82 Python modules at its top level**
(`src/aml/cloud/*.py`); 92 tracked files in total, the balance being 7 `migrations/` and 5
`templates/` files. `src/aml/static/portal/` holds 3 files (`index.html`, `portal.css`,
`portal.js`). This is GRAFOMEM Cloud — decision trail, erasure proof, governance gateway, tenant
management, billing, the portal.

**3. It is not merely public, it is distributed.** `pyproject.toml` finds packages under `src/`, so
`aml.cloud` ships inside the public **PyPI `grafomem`** wheel, and `[tool.setuptools.package-data]`
ships `static/portal/*` and `cloud/templates/*.yaml` alongside it — intentionally, so the portal
mounts on deployed containers. Every release puts the product code in reach of `pip install
grafomem`, under an MIT grant, under the Foundation's copyright line.

**4. Four import paths run standard -> product** — the Foundation-side code depending on the
Ulissy-side code, which is the wrong direction:

| # | Importer (Foundation side) | Target (Ulissy side) | Binding |
|---|---|---|---|
| 1 | `src/aml/provenance.py:48` | `aml.cloud.identity.SigningIdentity` | **module-level** |
| 2 | `src/aml/backends/interface.py:97` | `aml.cloud.identity.SigningIdentity` | **module-level** |
| 3 | `src/aml/cli.py:599,603,606` | `aml.cloud.identity.EnvIdentity` | function-local |
| 4 | `src/aml/cgr/validate.py:211` | `aml.cloud.decision_trail.DecisionTrailService` | function-local |

Path 4 sits inside the CGR package itself and is the one that blocked a standalone Python verifier;
it has been inverted, with a static import-boundary test holding the line at zero.
`src/aml/server/` is a fifth and far larger surface (~70 import sites in `app.py`, plus `auth.py`
and `mcp.py`), named and held out of scope.

**Caution on "four".** These four were re-derived from source for this record; the working note that
first reported the finding was not available to reproduce verbatim. *Four* is therefore a
re-derivation that agrees with the figure carried forward, not a transcription of it. If the
original enumeration differed, the difference should be reconciled before this ADR is accepted —
flagged rather than smoothed, per the primary-source convention this repo inherits.

## Decision

1. **GRAFOMEM Cloud is an Ulissy S.R.L. product.** The code at `src/aml/cloud` and
   `src/aml/static/portal`, the **`grafomem-deamon`** production service
   (`python -m aml.cloud.erasure_daemon` — the GDPR erasure sweeper and SIEM exporter), the
   `cloud.grafomem.com` console (`grafomem-web/cloud-v2`), and the hosted service sold to customers
   are Ulissy assets — irrespective of which repository currently
   holds the files. Consistent with ADR-0004 (Ulissy is the EU contracting entity) and ADR-0003
   (Ulissy carries DORA ICT third-party provider status): the entity that contracts and carries the
   regulatory status is the entity that owns the product.

2. **The "Grafomem" mark is licensed, not owned.** The mark stays with GNS-Foundation, which
   licenses it to Ulissy S.R.L. for the product name **"GRAFOMEM Cloud"**. This is the answer to
   ADR-0005's trademark sub-question for this mark: **Foundation owns, Ulissy licenses**. The mark
   sits with the neutral body for the same reason the issuer key does — a mark controlled by the
   vendor is a vendor's mark, and the neutrality claim is load-bearing in the pitch.

3. **The Foundation retains the standard entire** — specification, issuer key and identity,
   conformance suite and authority, `cgr-verify` and the reference verifiers. Ulissy consumes them
   on terms available to any third party, with no privileged private fork, which is what keeps
   ADR-0005's "open standard" claim honest when a customer or a regulator checks it.

4. **The code's present location is an exception, not a claim.** Residency in the Foundation's repo
   confers nothing on the Foundation and waives nothing for Ulissy; see grafomem 0012.

### The assignment instrument

The decisions above are **the entities' decision** and are recorded as taken. What remains is
execution: the **assignment instrument is pending execution by counsel.** Its *direction* is a
counsel question, not a re-opening of the decision — whether Ulissy assigns to the Foundation, the
Foundation assigns to Ulissy, or the code is licensed one way and never assigned, turns on
authorship, the engagement it was written under, and on what the already-executed MIT publication
(findings 1 and 3) did to the options.

**Authorship entity:** *to be supplied by the operator and recorded here.* Its absence does not
qualify the decision above; it is an input counsel needs, not a condition on what the entities have
decided.

## Consequences

- **The ownership story survives diligence being run in the wrong order.** A bank, an investor or an
  acquirer will read the public repository before it reads any ADR. Today that reader finds 82
  product modules under a Foundation copyright line. From here they also find two records that name
  it, price it, and record the decision the entities have taken — which is a governance artefact
  rather than a discrepancy someone else gets to discover.
- **The neutrality claim is defended by what the Foundation holds, not by the directory tree.** Spec,
  issuer key, conformance, verifiers, mark. That is the defensible version and it is now written on
  both sides.
- **Cost, stated plainly.** While the exception stands, Ulissy's principal product asset is
  published and distributed under someone else's copyright line on an irrevocable MIT grant. That is
  a real cost, not a formality, and it is accepted knowingly and temporarily — not because it is
  harmless, but because moving code between two legal entities before the instrument exists would
  create a worse record than the one it fixed.
- **The MIT publication is the one irreversible piece.** Everything else here can be renegotiated;
  releases already made cannot be recalled. It is therefore the first question for counsel, not the
  last.
- **No commercial dependency.** This record does **not** gate bank contact. Iccrea and any other
  counterparty conversation proceeds on its own timetable; the separation spike upstream says the
  same.

## Production posture, as of 2026-09-10

Recorded because a governance record that describes the intended split without the operational
reality is only half a record, and because this line was first drafted wrongly (see
[Consequences](#consequences) of the correction in the Foundation's decision log):

- **Deploy gate present but vacuous:** `healthcheckPath=/health` returns a static `ok` without
  touching the database, so a broken instance can take traffic. `railway.toml` **is** applied —
  an earlier claim that it was not, and that no gate existed, was wrong and is corrected here.
- **Single replica**, no container overlap on deploy, and startup DB steps that log-and-continue:
  a failed migration does not stop a deploy.
- Two production services (`grafomem`, `grafomem-deamon`) deploy the same commit.

To be **corrected visibly here** when the gate moves to `/readyz`.

### Promotion model — decided 2026-09-10

**Production stays on `main` with auto-deploy. `grafomem-staging` tracks `main` as a mirror, not a
gate.** A merge to `main` deploys production directly; staging shows the same commit but nothing
waits on it.

**The release-branch model is deferred, not rejected.** Under it, `grafomem` and `grafomem-deamon`
would track a `release` branch and the operator would promote with `git push origin main:release`
after staging validation — turning staging from a mirror into a gate.

**Revisit trigger, stated so the deferral has an end:** before the **HMAC production run** and
before **Iccrea contact**, whichever comes first. Both raise the cost of a bad deploy above what
auto-deploy-on-merge is worth — the first because it migrates credential storage, the second because
an outage during a bank conversation is not a technical event.

**Cost accepted meanwhile:** every merge to `main` — including docs-only merges, until watch paths
land — deploys production, on a single replica, behind a healthcheck that does not touch the
database. The rollback is a Railway redeploy of the previous good commit.

## Open sub-questions

- **The assignment instrument and its direction** — with counsel. Load-bearing, unresolved.
- **Effect of the executed MIT publication** on the assignment, and whether a `NOTICE` or
  per-directory copyright correction is warranted for code released to date.
- **Mark status** — whether "Grafomem" is registered, in whose name, in which classes and
  jurisdictions. Unverified. The licence in Decision 2 is stated over whatever rights exist and
  should be restated against the register once checked.
- **Adjacent namespace assets** — the PyPI `grafomem` name and the `com.grafomem/*` MCP namespace
  carry the same unanswered ownership question (ADR-0005 lists this).
- **Whether `src/aml/server/` follows the product** on extraction — open upstream in the separation
  design spike; it materially changes what Ulissy would end up owning.
- **Which body's licence terms cover the extracted product code** once it leaves an MIT repo.
- **Data residency.** Production runs in **`us-east4`** (Railway, `multiRegionConfig`
  `us-east4-eqdc4a`). For an EU-contracting entity selling an AML/KYC product into EU beachheads
  (ADR-0002, ADR-0004) that is a live question, not a deployment detail. Options: a Railway EU
  region; an EU deployment offered on Enterprise only; or both, with the default following the
  customer. **Operator decides — not acted on.**
- **The SIEM exporter has no destination.** `grafomem-deamon` runs `SiemExporter` alongside the
  erasure sweeper, and `SIEM_WEBHOOK_URL` is **unset** on that service — so audit events are
  exported nowhere. For a product whose pitch rests on auditability, where those events are meant to
  land is a commercial and compliance question, not a config default. **Operator decides the
  destination; no placeholder has been set** — a placeholder would make an unmonitored pipeline look
  configured, which is the failure mode worth avoiding here.
