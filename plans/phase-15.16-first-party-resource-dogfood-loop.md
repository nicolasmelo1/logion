<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.16 — First-party resource dogfood loop

> **Dogfood — Level 7 (full loop):** this is the first phase where the product uses native acquisition, feedback, discovery, runner, evidence, and bounty rails end to end on recurring Logion work.
> **After this phase:** Logion continuously experiences the product as indexer, consumer, evaluator, sponsor, and verifier.
> **Honesty boundary:** the loop proves utility and catches bugs; authority remains first-party until another operator reproduces it.

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

Make dogfooding an operating system, not a demo.

The first recurring program runs on the 15.14.1/15.15 local multi-agent node.
The founder may manually dispatch initial jobs through the existing host Hermes.
Every container role still has separate credentials, harness home, repository
scope, budget, and public Logion surfaces.

## Dogfood prompt for the implementing agent

This phase dogfoods twice: the implementing agent acquires and uses an indexed resource while building the loop, then the delivered loop schedules real resources.

```text
Search Logion for an acquirable resource about end-to-end testing, dogfooding,
release gates, or experiment design. Recall first with
`logion recall search "end to end dogfood release gate" --limit 5`; on LOW/NONE,
use `logion listings search --query "end to end testing release gate" --include-indexed
--limit 5 --json`. Inspect resource/version/distributions/permissions/feedback, prefer
free, follow the mandatory acquisition protocol, and use the resource to design
the scenario taxonomy, assertions, failure classification, and release gate. Save the
usage record at `artifacts/dogfood/phase-15.16.md`, run the completed canonical loop,
then submit one honest generic feedback report and record its Course projection.
```

## Deliverable: versioned dogfood program

Add `dogfood/programs/resource-improvement-v1.yaml` (or the proving-ground fixture directory chosen by repository convention) with:

- program ID/version, owner, schedule, enabled environments, max parallelism, daily/weekly credit and API-cost ceilings;
- selection policy (resource types, license, tiers, explicit allow/deny digests, freshness);
- scenario families and eval contract IDs;
- sandbox/network/secret profiles;
- evidence publication/redaction policy;
- bounty-draft policy and a separate manual funding gate;
- retention and escalation contacts.

Program config is reviewed in git. Runtime overrides may disable or lower limits, never silently widen permissions or budget.

## Concrete implementation

- Add a proving-ground built-in scenario `resource_improvement_loop.yaml` and assertion types only where current assertions cannot express the flow.
- Add backend `api/dogfood/` services for program sync, scheduled run creation, run/case state, evidence linkage, bounty draft, rerun linkage, and summaries. Use existing jobs, resources, evidence, bounties, notifications, and ledger services; do not issue direct SQL writes across domains.
- Add tables for `dogfood_programs`, `dogfood_runs`, and `dogfood_cases` only; facts such as execution receipts/evidence/bounties remain in their owning tables and are referenced by ID.
- Add internal operator endpoints and a feature-gated admin/landing view; do not expose raw prompts, source archives, secrets, or private artifacts.
- Add CLI/operator commands `logion dogfood programs`, `run`, `status`, `case`, `rerun`, `pause`; `run` defaults to dry-run plan output and needs `--yes` to enqueue.
- Emit a release-smoke adapter that runs one free deterministic case in staging and verifies all linked IDs.

## Initial scenario families

1. **Plan lint/review:** resource assists checking a sanitized plan fixture; deterministic schema/link assertions.
2. **Repository orientation:** read-only synthetic repo; compare required facts against a golden set.
3. **Structured extraction:** documentation fixture to JSON schema; exact/normalized match.
4. **Security review:** planted safe vulnerabilities in a fixture; recall/precision assertions.
5. **CLI help task:** disposable local devrig; agent must discover and invoke a non-mutating command.

Each case runs control and assisted arms with the same model/provider, budget, seed where supported, fixture, timeout, and environment. If equivalence cannot be established, mark `inconclusive`, not improved.

## Bounty automation boundary

- The program may create an internal finding and a **draft** bounty with evidence links, reproduction command, acceptance assertions, license/delivery lane, suggested reward, and redacted description.
- Human approval is required to publish/fund. Reuse 15.8 sponsorship ledger; no program code debits credits directly.
- Successful submission triggers the same pinned eval contract. Acceptance/payout follows 15.8/16.6 policy; this phase never auto-pays.

## Data, privacy, and cost controls

- Store prompts only for synthetic/public fixtures; hash or redact all other inputs before durable upload.
- API/model calls use a dedicated low-limit project key and per-case budget.
- Report token/API cost separately from runner CPU/storage and bounty spend.
- Stop program on daily cap, repeated infrastructure error, evidence signing failure, or redaction canary detection.

## Tests

- State-machine tests for selection → execution → evidence → draft bounty → improvement → rerun.
- Control/assisted parity, duplicate schedule, retry, partial failure, cap reached, pause, and redaction fixtures.
- Bounty draft contains exact baseline/eval/resource digest; funding cannot occur without existing domain confirmation.
- Proving-ground integration against mock/local devrig and one opt-in remote smoke.
- Public view snapshot proves honesty labels for first-party/inconclusive/failed.

## Canonical loop

1. The consumer discovers a resource and installs it in the target repository's
   native harness scope, never implicitly at user scope.
2. Reconcile the exact version whether Logion or a native manager installed it.
3. Start a fresh harness session, use it, and emit a local minimal observation.
4. Submit intentional feedback under the selected consent policy.
5. The evaluator runs baseline and assisted tasks in its isolated container.
6. Capture assertions, costs, artifacts, failures, and limitations.
7. The auditor verifies and publishes explicitly first-party evidence.
8. The sponsor manually approves a bounty when the problem is actionable.
9. The contributor delivers through the existing PR or hosted-resource path.
10. Rerun and link before/after evidence to disposition and payout.

## Initial corpus

- Skills already indexed by Logion, including the companion's deterministic scenarios.
- Real but bounded workflows: plan linting, repository inspection, documentation checks, structured extraction, and safe code-review fixtures.
- No arbitrary public code execution, production mutations, or unbounded agent autonomy.

## Product surfaces

- Internal dogfood dashboard: queue health, spend, failure taxonomy, evidence, bounties, reruns, and regressions.
- Public resource timeline containing only redacted, disclosure-safe evidence.
- Release gate that exercises one complete loop in staging.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add
`builtin:phase_15_16_full_resource_loop`; this composes Phase 15 but does not
replace its narrower scenarios.

- **Actors:** host Hermes operator plus isolated publisher/consumer, evaluator,
  sponsor, contributor, and auditor containers, each with its own harness home,
  worktree, credentials, and role-scoped public access.
- **Customer prompt:** “Find and install a Logion-distributed capability that
  helps review this repository, use it normally, and later send honest minimal
  feedback if it breaks.” Session two starts only from persisted customer state.
- **Operator/contributor flow:** turn an eligible real feedback cluster into an
  explicitly funded draft; discover the work; submit a fixed immutable version;
  rerun evidence before disposition.
- **Assertions:** compose acquisition, observation, feedback, review projection,
  cluster, bounty, exact ledger, new version, runner/scan receipt, and improved
  outcome. Add `api.full_loop_lineage_complete` and
  `api.original_version_immutable`.
- **Negative/evidence:** no raw prompt upload, automatic funding, pre-evidence
  acceptance, in-place mutation, or self-dealing payout. Retain a
  machine-readable lineage graph whose every edge resolves through public API,
  plus redacted artifacts and no-500 proof.

## Acceptance gates

- At least 20 resources and 5 scenario families run on schedule for two weeks.
- At least one real failure becomes a bounty, lands as an improvement, reruns, and reaches a recorded disposition.
- Operators can trace every public claim to evidence and raw artifacts.
- Monthly CPU/API/storage budget is capped and observable.
- The complete loop runs on the founder's Mac with cheap hosted models and CPU
  containers; no owned accelerator or second physical server is required.
- Every one of the five initial scenario families has a deterministic fixture and named owner.
- The implementing-agent dogfood artifact and review disposition are present in the PR, independently of scheduled product dogfood.
