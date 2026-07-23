<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.9 — Benchmark and field reconciliation

> **Dogfood status:** Logion compares its dogfood receipts with controlled evals and opens investigation tasks on meaningful divergence.
> **After this phase:** the system can say “works in this benchmark, drifts in these environments” instead of collapsing signals.
> **Honesty boundary:** reconciliation produces hypotheses and evidence, not causal certainty.

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

Turn benchmark/field mismatch into actionable improvement work.

## Dogfood prompt for the implementing agent

```text
Search Logion for a resource about experiment analysis, statistics, drift detection,
or observability diagnosis. Recall first; search the marketplace only on LOW/NONE.
Follow the mandatory acquisition/reconciliation protocol and apply it to the
reconciliation method and synthetic paradox fixtures. Record
`artifacts/dogfood/phase-16.9.md`; submit feedback after a real dogfood divergence is
investigated, not merely after reading the course.
```

## Compatibility contract

Each eval metric may declare an optional `field_proxy` containing receipt field, shared unit/bucket mapping, population/environment filters, direction, minimum sample, window, and comparison method version. Backend rejects proxies with incompatible units, unbounded dimensions, free-form receipt fields, or unavailable privacy threshold.

Reconciliation never joins individual private receipt identities to eval runs. It compares privacy-safe aggregates for a resource digest/environment cohort against benchmark distributions/results.

## Detection/output

- Methods v1: categorical rate delta with interval, ordinal bucket shift, and latency/cost bucket drift. Put implementations in a versioned pure statistics module with golden fixtures.
- Output evidence predicate contains input aggregate/eval digests, method/version, sample sizes, windows, effect size/interval, state `aligned|diverged|insufficient|incompatible`, caveats, and investigation links.
- Multiple testing/correlated metrics are disclosed; do not market p-values as causality.

## Backend/UI/CLI

- Add `api/reconciliation/` contracts, scheduled service/job handler, immutable decisions, investigation records, and optional bounty-draft service call.
- Trigger on new qualifying aggregate, eval attestation, resource version, or scheduled window; idempotency key is inputs+method digest.
- CLI `logion evidence reconcile RESOURCE --policy FILE` and operator investigation/detail views.
- Resource UI keeps benchmark and field panels separate and shows reconciliation between them.

## Tests

- Aligned/diverged/sparse/incompatible, Simpson's paradox, outlier, delayed receipt, changed version, changed proxy/method, minimum cohort suppression, and retry idempotency fixtures.
- Property tests on unit conversion and confidence interval bounds.
- Privacy test proves decision cannot reveal a suppressed cohort or individual receipt.

## Rollout

Shadow-mode alerts on Logion dogfood for four weeks. Human triage labels useful/noisy alerts before any public display. Bounty creation remains a manually approved draft.

## Build

- Join compatible signals by resource digest, metric definition, harness class, and time window.
- Drift and divergence detection with minimum sample and confidence metadata.
- Investigation artifacts linking representative receipts, evals, and environment differences.
- Optional bounty draft; never auto-publish or auto-pay from telemetry alone.
- Version-aware trend views.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_9_evidence_reconciliation`.

- **Prompt:** “Compare this resource's reproducible benchmark evidence with its
  privacy-safe field evidence. Explain any drift and create an investigation
  proposal, but do not downgrade trust or spend money automatically.”
- **Fixtures:** benchmark-pass/field-fail, benchmark-fail/field-pass, aligned,
  stale, and insufficient-cohort cases.
- **Assertions to add:** `api.evidence_drift_detected`,
  `api.reconciliation_explanation_complete`,
  `api.investigation_proposal_unfunded`,
  `api.insufficient_evidence_inconclusive`, and
  `api.no_automatic_trust_or_money_transition`.
- **Evidence:** retain input/evidence digests, classification/rationale,
  proposal state, redaction, exact zero-ledger delta, and no 500s.

## Gates

- Synthetic agreement, drift, sparse, and Simpson's-paradox fixtures behave safely.
- Incompatible metrics are never numerically combined.
- Operators can trace alerts to source evidence.
- Resource updates do not erase history from prior digests.
- Reconciliation code and its exact inputs reproduce every published decision offline.
- No automatic ranking penalty or payout decision consumes reconciliation until a later explicit policy phase.
