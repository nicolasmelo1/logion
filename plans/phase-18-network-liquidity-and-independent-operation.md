<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 18 — Network liquidity and independent operation

> **Dogfood status:** Logion remains an active sponsor, consumer, and runner, but phase success requires useful activity that Logion did not execute or manually coordinate.
> **After this phase:** the network has credible non-founder supply and demand for evaluation and improvement work.
> **Honesty boundary:** transaction volume and node count are reported by distinct operator and economic activity, not inflated process counts.

## Mandatory dogfood protocol

The phase-specific prompt below is implementation work, not optional documentation. The implementing agent must exercise the interoperable resource loop delivered by 15.10–15.11:

1. run local recall, then `logion listings search --query "SEARCH_QUERY" --include-indexed --limit 5 --json` only on LOW/NONE;
2. inspect the exact `ResourceVersion`, distributions, evidence, permissions, license, and acquisition plan—not only a Course projection;
3. obtain explicit approval, run `logion resources acquire RESOURCE_ID --version VERSION_ID --scope repo-root --channel auto --dry-run --json`, then acquire through the recommended Logion or native channel;
4. run `logion resources reconcile --scope repo-root --json` and require exact version attribution;
5. use the resource in the normal harness on this phase's real task and verify it appears in `logion usage pending --json`;
6. submit exactly one intentional post-task report:

```bash
logion feedback submit RESOURCE_ID VERSION_ID \
  --rating 1..5 \
  --usefulness 0.0..5.0 \
  --reliability 0.0..5.0 \
  --tool-safety 0.0..5.0 \
  --token-efficiency 0.0..5.0 \
  --completed-task \
  --task-class TASK_CLASS \
  --body "One or two resource-focused sentences; no private repository data" \
  --json
```

Use `--not-completed-task` when appropriate. Record the feedback ID and `course_review_projection` disposition. A native external installation is valid dogfood; Logion must not require reinstalling it. If acquisition, exact attribution, consent, or actual use is absent, record the blocker and **do not submit feedback/review**. Passive observation alone never justifies a rating.

## Goal

Prove that the system can become a network rather than a SaaS product with decorative federation.

## Dogfood prompt for the implementing agent

```text
Find a Logion resource about marketplace liquidity, mechanism design, two-sided network
operations, or unit economics. Recall first; on LOW/NONE search "marketplace liquidity
mechanism design unit economics". Follow the mandatory acquisition/reconciliation
protocol and use it to critique incentives/concentration metrics
against the prior 90 days of redacted network data. Save
`artifacts/dogfood/phase-18.md`. Submit one honest feedback report after a concrete operator or
sponsor workflow is improved. This dogfood may not create fake jobs, subsidized self-
dealing, a token, or a paid action without separate explicit approval.
```

## Product contracts

### Public work discovery

- AKTP job/bounty events advertise exact resource/eval contract, eligibility, deadline, required capabilities/independence, artifact disclosure, sponsor/node origin, reward display, settlement method/status, and terms digest.
- Foreign rewards are display-only until an operator explicitly accepts the origin/terms. CLI never represents them as guaranteed or escrowed by Logion.
- Search/filter by CPU/GPU/API requirements, evaluator/resource type, reward/currency, deadline, issuer/sponsor policy, and disclosure needs.

### Sponsor controls

- Per-job/program/month hard budgets, accepted runner/evaluator issuers, minimum independence, geographic/data constraints, max price, cancellation/dispute, and settlement mode.
- Funding uses node-local existing credits/ledger only for Logion-origin work. Foreign settlement is linked/receipted, never posted into Logion ledger as if local.
- Sponsor sees estimate, worst-case cap, coordinator fee, runner/evaluator allocations, and acceptance policy before confirmation.

### Runner/evaluator market

- Runner advertises capacity windows and immutable offer/pricing snapshots; operator sets allow/deny resource/evaluator/sponsor/origin.
- Matching prioritizes hard compatibility and sponsor cap; no opaque reputation score. Past conformance, completion, disputes, and reproducibility are separate evidence filters.
- Human evaluator/reviewer jobs use conflict disclosure, rubric, calibration fixtures, double-review/escalation, and privacy constraints.

## Backend/CLI/operations

- Add `api/network_market/` only for matching/offers/agreements; reuse jobs, bounties, federation, authority, ledger, and evidence domains.
- Immutable work agreement binds offer, sponsor policy, runner/evaluator, price/fee, terms, contract, deadlines, and dispute policy before execution.
- CLI: `jobs discover|inspect|accept|decline`, sponsor `jobs open|fund|status`, runner `offers|availability|earnings`; confirmation for every economic commitment.
- Abuse controls: identity/rate limits, sponsor funding proof, job/resource allowlists, malware/illegal-content reporting, kill switches, dispute/fraud holds, concentration alerting.

## Metrics and anti-gaming definitions

Define distinct operator from verified independence-group ownership/control, not runner count. Useful work requires accepted result linked to a non-test resource/eval and non-reversed settlement or documented volunteer outcome. Repeat sponsor/operator requires activity in separate calendar windows.

Dashboard metrics: distinct active operators/sponsors, repeat rate, external share, job fill/completion/reproduction/dispute/refund, time-to-first-offer/completion, spend/earnings/fees by origin, concentration HHI/top share, subsidy share, and coordinator/manual-touch rate. Exclude fixtures, self-dealing, reversed, and synthetic load.

## Manual bootstrap runbook

Founder may personally operate the first node/runner and recruit/assist first operators, but every intervention is logged (`setup`, `debug`, `matching`, `acceptance`, `settlement`). Success requires the manual-touch rate to decline and Phase exit excludes Logion-operated work from independent counts.

## Tests/security/economics

- Offer race, price change, cap exceed, cancellation, timeout, partial result, dispute, refund, double settlement, foreign event, identity collusion fixture, self-dealing exclusion.
- Ledger balance and fee disclosure properties.
- Sybil/concentration simulations inform limits but do not become a magical trust score.
- Incident drills for malicious job, compromised runner/sponsor, leaked fixture, settlement outage, and protocol spam.

## Rollout stages

1. Invite-only volunteer CPU jobs with no economic promise.
2. Logion-sponsored capped CPU bounties with invited independent runners.
3. Repeat external sponsors on one proven resource category.
4. External/GPU offers only when a sponsor requests and funds them.
5. Public discovery after support, disputes, abuse, and unit economics meet written gates.

## Preconditions

- Phase 16 independent verification exit gate is met.
- At least one resource category has recurring demand.
- Runner unit economics and sponsor budgets are observed from real dogfood usage.

## Build

- Public job/bounty discovery through AKTP feeds referenced from AI Catalog
  entries and/or ARD results via the tested optional extension.
- Sponsor controls for budgets, accepted issuers, required runners, and settlement policy.
- Runner pricing/availability hints and transparent coordinator fees.
- Reviewer/evaluator participation where assertions require judgment.
- Portable receipts and node-local settlement records; no token or mandatory global payment rail.
- Health metrics by distinct operators, repeat sponsors, completion latency, reproduction rate, disputes, and concentration.

## Do not build

- No speculative token, points economy, or subsidized fake volume.
- No permissionless arbitrary-code queue before abuse controls are proven.
- No expensive owned GPU fleet to manufacture supply.
- No global reputation score.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_18_independent_liquidity`. This scenario validates mechanics and
measurement; it cannot replace the real multi-month exit metrics below.

- **Actors/prompts:** an external-style sponsor publishes funded work from a
  customer problem; two independent runner/contributor personas discover,
  evaluate, and deliver it; a node operator reconciles evidence and payout
  without source-tree or founder-only intervention. Prompts describe business
  goals, not internal endpoints.
- **Fixtures:** legitimate cross-party activity plus founder-controlled,
  self-dealing, duplicate-identity, circular-payout, subsidized, and unpaid
  attempts that must be excluded from liquidity metrics.
- **Assertions to add:** `api.independent_work_discovered`,
  `api.independent_delivery_accepted`,
  `db.independent_payout_exact`,
  `api.self_dealing_excluded_from_metrics`,
  `api.node_operates_without_founder_credentials`, and
  `api.liquidity_metric_recomputes`.
- **Evidence:** retain actor/ownership classification, discovery-to-payout
  lineage, receipts/ledger, inclusion/exclusion rationale, node runbook result,
  costs, redaction, and no 500s. Passing proves the counter and workflow are
  honest; only observed production cohorts over the required window prove
  network liquidity.

## Exit gate

For three consecutive months, at least three non-Logion operators complete useful work, two repeat sponsors fund jobs or bounties, one improvement is independently reproduced and settled, and no single operator is required for verification of historical evidence.

Additionally, at least 50% of qualifying completed work and 50% of qualifying sponsor spend must be non-Logion, no operator exceeds the documented concentration ceiling without public disclosure, and fewer than 25% of qualifying jobs require founder intervention after onboarding. These thresholds may be revised only before the measurement window starts and with the old/new rationale recorded.
