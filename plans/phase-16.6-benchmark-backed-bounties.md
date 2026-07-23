<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.6 — Benchmark-backed bounties

> **Dogfood status:** platform-funded bounties from 15.8 use before/after eval contracts and independent reruns where economical.
> **After this phase:** payout criteria can reference reproducible improvement instead of reviewer intuition alone.
> **Honesty boundary:** benchmarks are scoped objectives, not universal product quality.

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

Connect the improvement economy to verifiable outcomes while retaining human acceptance for ambiguous work.

## Dogfood prompt for the implementing agent

```text
Search Logion for a resource about test-driven bounties, benchmark design, acceptance
criteria, or secure payment workflows. Recall first and marketplace-search only on
LOW/NONE. Follow the mandatory acquisition/reconciliation protocol and use it to review a real platform-funded bounty's
before/after contract. Record `artifacts/dogfood/phase-16.6.md`; submit one honest
feedback report after the candidate-evaluation fixture completes. Do not spend/fund credits as
part of dogfood without a separate explicit approval.
```

## Bounty schema extension

Add an optional immutable `evaluation_policy` snapshot to Bounty (or normalized table): target resource/version/digest, baseline attestation IDs/digest, eval contract digest, metric/assertion requirements, minimum delta, regression constraints, accepted evaluator/issuer policy, replication requirement, budget ceiling, and decision mode `human|automatic|hybrid`.

Existing course/indexed bounties without evaluation policy behave exactly as before. Evaluation policy can be attached only before opening/funding; edits create a new draft or cancel/refund per current domain policy.

## Candidate flow

1. Submission pins candidate artifact/source commit and computes digest.
2. Service creates candidate resource version without changing the public/current projection.
3. Scheduler runs baseline/candidate under the same contract/environment policy.
4. Authority service evaluates attestations; comparison service applies deltas/regressions.
5. Produce `bounty_evaluation_decision` with full explanation.
6. Automatic mode may mark technical criteria satisfied only; payout service remains the single idempotent money path and checks dispute window/fraud/manual holds.

## Code plan

- Extend `api/bounties/models/services/repositories/controllers` without duplicating eval/authority logic.
- Add services `AttachEvaluationPolicy`, `ScheduleSubmissionEvaluation`, `EvaluateSubmissionCriteria`, and `FinalizeEvaluatedSubmission`.
- Extend client/CLI bounty create/show/submission review surfaces with contract and evidence IDs; require an explicit confirmation summary before funding.
- Existing GitHub PR and hosted-resource delivery lanes both produce candidate digest/version.
- Notification/admin audit surfaces include evaluation failures, conflicts, and manual overrides.

## Invariants

- Candidate cannot supply/modify the evaluator, policy, hidden fixtures, baseline, or accepted issuers.
- Failed/missing assertions cannot be omitted by aggregate score.
- Human override records actor, reason, prior machine decision, and cannot rewrite attestations.
- Sponsor, author, contributor, runner, evaluator, and recipient attribution stay separate.

## Tests

- Backward compatibility, policy immutability, baseline pinning, weaker-contract substitution, hidden-fixture access, regression despite score gain, conflicting attestation, retry/double payout, refund/cancel race, override audit.
- End-to-end platform-sponsored indexed listing → PR candidate → two evals → accepted decision → payout fixture.
- Ledger remains balanced under every terminal path.

## Build

- Bounty target includes resource/version, baseline evidence, eval contract, required deltas, regression constraints, issuers, and budget.
- Candidate evaluation produces linked before/after attestations.
- Settlement policy supports automatic, human, and hybrid decisions.
- Preserve original author, contributor, sponsor, evaluator, and runner attribution separately.
- Dispute window and evidence-preserving manual override.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_6_benchmark_bounty`.

- **Actors/prompt:** a sponsor says, “Create and explicitly fund a bounty whose
  acceptance requires this portable eval and minimum score.” Two contributors
  submit a regression and a genuine improvement through the normal work path.
- **Assertions to add:** `api.bounty_eval_contract_bound`,
  `api.regression_submission_rejected`,
  `api.improved_submission_accepted`,
  `api.acceptance_evidence_reproducible`, and
  `db.exact_credit_ledger`.
- **Negative/evidence:** prose or creator self-score cannot override the failed
  eval, and retries cannot pay twice. Retain baseline/candidate/result digests,
  threshold decisions, contributor separation, receipts, ledger, no 500s, and
  redaction.

## Gates

- Existing course and indexed-listing bounties remain compatible.
- A candidate cannot choose a weaker benchmark or omit failed assertions.
- Payout is idempotent and auditable from funding through disposition.
- A negative fixture blocks automatic payout.
- Technical pass does not publish a resource or merge a PR; existing acceptance/publication boundaries remain explicit.
- Every payout can be recomputed from immutable funding, policy, evidence, decision, dispute, and payout records.
