<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.7 — Evidence search and issuer-aware ranking

> **Dogfood status:** Logion's internal resource selection uses the same evidence filters and ranking explanation exposed publicly.
> **After this phase:** consumers can find resources by evidence without accepting a universal leaderboard.
> **Honesty boundary:** defaults are product policy, visibly labeled and replaceable by the caller.

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

Make accumulated evidence useful at selection time.

## Selection-contract boundary

Follow the decision record in
[`asm-logion-collaboration-and-protocol-convergence-gate.md`](asm-logion-collaboration-and-protocol-convergence-gate.md).
This phase implements local policy over typed claims; it does not define a
second public service-value/selection manifest.

- If the projects converge, pin the agreed ASM revision, keep its declared
  selection facts under their original issuer/digest, and treat its selector as
  a public reference profile that callers may replace.
- If the projects share only primitives, implement only those accepted
  primitives and keep the remaining Logion ranking inputs internal/generic.
- If the projects remain independent, do not advertise ASM compatibility or
  publish a competing protocol. Evidence ranking still works over Logion's
  generic claim model.

No imported ASM/registry score is authority. Hard eligibility inputs,
observations, evals, and local policy remain distinct in the explanation.

## Dogfood prompt for the implementing agent

```text
Find a resource about search ranking, information retrieval, explainable scoring, or
decision systems. Recall first; on LOW/NONE search the marketplace for "information
retrieval explainable ranking evidence". Follow the mandatory acquisition/reconciliation
protocol and use it to design/query the dogfood corpus.
Record which ranking advice changed code in `artifacts/dogfood/phase-16.7.md`; submit
one honest feedback report after the selected resource and explanation are used in a real
Logion workflow.
```

## Query model

- Extend `/v1/resources` or add `/v1/evidence/search` using cursor pagination and typed filters: subject/type/version, predicate/version, outcome, evaluator, issuer, independence group, issued range/freshness, replication state, metric name/range/unit, feedback/field/eval source, acquisition channel, and authority-policy decision.
- No generic JSONPath/filter language in v1. Validate bounded repeatable query params to protect indexes.
- Search returns evidence summaries and resource aggregates calculated for a named ranking profile/policy version; raw attestations remain separately fetchable.

## Ranking profile

Versioned profile has hard eligibility constraints, local authority policy, evidence freshness/coverage rules, typed metric normalizers, explicit weights/tie-breaks, and missing-data policy. Profiles are organization-owned or public built-ins. A result includes an explanation object with each candidate's inputs, exclusions, contributions, uncertainty, and final stable sort key.

Do not average incompatible benchmarks, units, evaluator versions, resource versions, intentional feedback, passive usage, field aggregates, or eval predicates. Default missing evidence is `unknown` and receives no fabricated neutral/pass value. “Used by me/my organization” is a local inventory/receipt filter, not a global popularity score.

## Backend/database

- Add evidence search projections/materialized aggregates only after benchmark proves necessary. Source-of-truth remains immutable evidence.
- Add indexes on subject/predicate/issuer/issued_at/outcome and selective JSONB metric indexes based on real queries.
- Add `api/ranking/` pure profile evaluator, repository query builder, saved profiles, and explanation serializer.
- Cache key includes query, cursor, profile digest, authority policy digest, and evidence high-watermark.

## Client/CLI/UI

- `logion resources search --evidence ... --ranking-profile ... --explain --json`.
- `logion resources compare ID... --metric ...` prints benchmark/evaluator/unit/context beside values.
- Resource page shows coverage (`n attestations`, issuers, freshness), uncertainty, contradictions, and selected local policy.

## Tests/benchmarks

- Golden ordering/explanation, missing evidence, unknown issuer, incompatible metric, policy/profile revision, tie cursor stability, contradiction, stale evidence, and pagination under concurrent insert.
- Property test: explanation contributions recompute final score/order.
- Benchmark at target corpus and 10× synthetic size; set query count/p95 budgets before adding materialization.

## Build

- Query by resource type, version, predicate, evaluator, issuer, freshness, agreement, cost, and outcome.
- Local ranking profiles with weights, hard constraints, and versioned explanations.
- Evidence coverage and uncertainty indicators.
- Compare endpoint that returns raw metric units and benchmark context.
- Saved organizational policies; no public global reputation number.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_7_evidence_ranking`.

- **Prompt:** two buyers ask: “Choose the best compatible code-review resource
  for my stated policy and explain the ranking using concrete evidence,
  issuer, freshness, and limitations.” One profile trusts Logion scans; the
  other requires two independent eval issuers.
- **Fixtures:** candidates separate popularity, price, fresh evidence, stale
  evidence, incompatible permissions, and unknown issuers.
- **Assertions to add:** `api.evidence_filters_applied`,
  `api.ranking_profile_changes_order`,
  `api.ranking_explanation_complete`,
  `api.untrusted_evidence_not_authoritative`, and
  `api.incompatible_resource_excluded`. Retain query/profile/result digests,
  explanations, no 500s, and redaction.

## Gates

- Every ordering explains included/excluded evidence and weights.
- Changing trusted issuers predictably changes results.
- Missing evidence sorts as unknown, never safe or failed.
- Search latency and pagination remain bounded on the dogfood corpus.
- Two profiles can order the same evidence differently and both explanations are reproducible offline.
- Ranking never changes an evidence or authority record.
- No public Logion selection descriptor duplicates an independently governed
  ASM descriptor; the collaboration decision and pinned revision are visible
  when an ASM reference profile is used.
