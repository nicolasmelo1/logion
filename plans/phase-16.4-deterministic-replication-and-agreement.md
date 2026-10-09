<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.4 — Deterministic replication and agreement

> **Dogfood status:** Logion submits its own deterministic evaluations to at least two isolated runner identities and reconciles results.
> **After this phase:** the system can distinguish reproducibility, agreement, drift, and contradiction.
> **Honesty boundary:** replication counts only distinct configured authorities; two processes under one operator are not independent nodes.

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

Make reproducibility measurable before adding reputation or ranking.

## Dogfood prompt for the implementing agent

```text
Find a resource about reproducible builds, deterministic testing, consensus pitfalls,
or distributed verification. Recall first, then marketplace-search "reproducible
deterministic testing distributed verification" on LOW/NONE. Follow the mandatory
acquisition/reconciliation protocol and use it to review canonicalization and disagreement
fixtures. Save `artifacts/dogfood/phase-16.4.md`; send one honest feedback report only after two
isolated runner executions reconcile through the implemented code.
```

## Replication policy object

Versioned policy fields: eval contract digest, eligible evaluator digests, minimum total results, minimum distinct operators/independence groups, permitted environment equivalence class (which never spans differing harness stacks or iteration budgets), deadline, deterministic fields, tolerated numeric precision, and decision rule. Policy digest is stored in every reconciliation.

## Canonical result digest

- Build from schema version, contract/subject/evaluator digests, normalized assertion IDs/outcomes, typed metric values in canonical units, and declared deterministic output artifact digests.
- Exclude timestamps, runner ID, cost, logs, and nondeterministic artifacts from equality digest but retain them in attestations.
- Decimal metrics use declared fixed precision; floating values without precision are invalid for deterministic agreement.
- Publish normalization code in `logion-eval-contract`; backend imports it.

## Backend work

- Add `api/replication/` services/repositories/controllers and tables for replication groups, assignments, result memberships, reconciliation decisions, and operator independence groups.
- Fan out assignments only to eligible distinct groups. Do not reveal other results before a runner submits or deadline expires.
- Reconciliation is idempotent and append-only by policy/evidence set digest.
- `drifted` means permitted environment variation/non-equality classified by rules; `contradicted` means assertion/metric outcome conflicts; `inconclusive` covers insufficient eligible evidence.
- Generate a content-addressed disagreement bundle with all disclosure-safe inputs/diffs.

## API/CLI

- Read endpoints expose group, policy, assignments without secret fixtures, individual results, decision, and explanation.
- `logion eval reproduce EVIDENCE_ID --runner ...` creates a new independent attempt; it never overwrites original evidence.
- `logion eval reconcile GROUP_ID --offline` can verify a downloaded bundle using public normalization/policy code.

## Tests

- Canonical digest goldens across Python versions/key order/Unicode/decimal edges.
- 2-of-2 match, 2-of-3 match, same-operator exclusion, evaluator mismatch, environment mismatch, timeout, drift, contradiction, late result, policy revision.
- Information-leak test proves pending runners cannot query peer outputs/hidden fixtures.
- Offline reconciler equals backend decision for golden bundles.

## Rollout

Start with public deterministic fixtures on two Logion-controlled but explicitly same-operator runners to debug mechanics; UI must label them non-independent. Phase exit requires a truly separate operator. Do not implement majority voting for rubric/nondeterministic evals here.

## First nondeterministic subject: does a checked invariant change what an agent ships?

The deterministic fixtures above debug the mechanics. They cannot exercise the
states this phase exists to produce: a fixture that agrees every time never
distinguishes `reproduced` from `drifted`, and a controlled divergence is a
divergence somebody planted. The first subject that *needs* this phase is one
that is nondeterministic by construction, and the obvious one is also a
measurement Logion has a reason to publish.

**The claim under test.** Several tools now ship a machine-checked invariant
file next to the code — Bend's `LAWS.bend`, checked by `bend PROOF.bend` before
commit, is the sharpest statement of it: "AGENTS.md backed by proof". The claim
is behavioural and about an artifact an agent installs: that having invariants a
machine checks, rather than invariants written down, changes what the agent
ships. Nobody has measured it. That is the shape of every claim this product
exists to measure.

**Three arms, one language, one model, the same tasks.**

| Arm | Treatment |
| --- | --- |
| A | The task, and nothing else. |
| B | The task, plus the invariants stated in prose the agent reads. |
| C | The task, plus the same invariants as checks the agent can run and that run in its gate. |

A against C is the interesting number. B is the arm that makes the result mean
anything: without it, C's advantage is indistinguishable from having been handed
more context about the problem, and the honest null hypothesis is that writing
the invariants down at all is the whole effect.

Bend is not an arm. Restricting the tasks to a language expressible in it would
confound the treatment with the novelty of the language and leave a sample too
small to read. It can be a fourth arm over the subset of tasks it can express,
reported on its own and never pooled with the others.

**The oracle is declared before the run.** Each task carries a held-out defect
set — inputs the implementation must handle, fixed in advance, never shown to
the agent in any arm, and checked mechanically against observed state rather
than against the agent's prose. A task whose defects cannot be stated that way
does not belong in the set.

**What replication is for here.** Agent runs vary; a single run per arm is an
anecdote and publishing it would be the exact failure this product names in
other people's hubs. Each arm runs under at least two independently configured
runners, and a difference that does not reproduce is `inconclusive` rather than
a finding. The honesty boundary at the top of this phase applies unchanged: two
processes under one operator are not independent nodes, and a per-arm number
from one operator is a debugging artifact, not a measurement.

**Confounders the report must name, not resolve.** The treated arms carry more
context than A, so length is not held constant and cannot be claimed to be. Who
wrote the invariants, and whether they were written before or after seeing the
defect set, decides the result more than the arms do. In arm C the checker must
be observed to have actually run — a checked invariant nobody ran is arm B with
extra files, and that is the single easiest way for this experiment to report a
false positive.

**Non-goals.** This is not a claim about Bend, about any proof assistant, or
about formal methods. It ranks nothing and no vendor is named in the result. It
produces one number with an interval, or it produces `inconclusive`.

**Exit condition:** one published report says whether a machine-checked
invariant file changed what a cheap agent shipped, arm B stands between arm A
and arm C so the answer is about checking rather than about writing things down,
every arm reproduced across two independently configured runners or is reported
as inconclusive, and the confounders above appear in the report rather than in
the discussion afterwards.

## Build

- Replication policy per eval contract: minimum issuers, environment tolerances, quorum rule, and deadline.
- Canonical normalization for deterministic outputs and assertion vectors.
- Agreement states: pending, reproduced, drifted, contradicted, and inconclusive.
- Disagreement bundle with exact inputs, environments, artifacts, and diffs.
- Retry rules that do not cherry-pick passing results.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_4_replication_agreement`.

- **Actors/prompt:** two independently enrolled runner operators each receive:
  “Claim compatible work, execute exactly the published contract, and submit
  your signed result without seeing another runner's output.” The coordinator
  is asked to explain agreement/disagreement.
- **Fixtures:** one deterministic agreeing case and one controlled divergent
  runner/result fixture; identities, homes, keys, and artifacts are separate.
- **Assertions to add:** `api.replication_distinct_runners`,
  `api.replica_results_independent`, `api.agreement_digest_matches`,
  `api.disagreement_not_finalized`, and
  `api.replication_policy_enforced`. Retain both receipts/digests, agreement
  calculation, conflict outcome, cost, no 500s, and redaction.

## Gates

- Positive, drift, contradiction, timeout, and malicious duplicate fixtures pass.
- UI/API never call same-operator duplication “independent”.
- All individual attestations remain accessible after reconciliation.
- Policy changes create new decisions instead of rewriting old ones.
- Reconciliation result is reproducible offline from its bundle with the API unavailable.
- Same binary run twice under two runner IDs owned by Logion does not satisfy the independent threshold.
- Two results whose harness stacks or iteration budgets differ are never counted as replications of each other, however close their numbers.
