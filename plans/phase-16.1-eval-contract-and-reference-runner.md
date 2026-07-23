<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.1 — Eval contract and reference runner

> **Dogfood status:** Logion expresses its existing deterministic scenarios as portable eval contracts and runs them through the 15.15 node.
> **After this phase:** an eval is a versioned artifact, not backend-only orchestration.
> **Honesty boundary:** a passing contract proves only its declared assertions and environment.

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

Define the portable unit another runner can execute and reproduce.

## Dogfood prompt for the implementing agent

```text
Search Logion for a resource about evaluation design, test harnesses, golden tests,
or benchmark methodology. Recall first with `logion recall search "evaluation test
harness benchmark design" --limit 5`; on LOW/NONE use `logion listings search
--query "evaluation harness benchmark testing" --include-indexed --limit 5 --json`.
Follow the mandatory acquisition/reconciliation protocol. Use it to critique metric definitions, fixture leakage,
determinism classes, and result schemas. Record use in `artifacts/dogfood/phase-16.1.md`
and submit feedback after the portable contract passes two identical runs.
```

## Package and wire contract

- Add public `logion/packages/eval-contract/` (`logion-eval-contract`) as the only parser, validator, canonicalizer, and result-normalizer. The private API consumes a pinned released version; it must not reimplement parsing.
- Contract media type: `application/vnd.aktp.eval-contract.v1+json`; authoring YAML is normalized to this JSON before hashing.
- Required fields: schema version, subject type/digest constraint, archetype, inputs/fixtures by digest, runtime requirements, steps, metric/assertion definitions, budgets, output paths, redaction, determinism class, and evaluator requirement.
- Result media type contains contract/subject/environment digests, assertion vector, typed metric values, outcome, artifacts, resource usage, and limitations.

Provide complete JSON Schemas plus typed Python models. Closed enums: outcome, assertion operator, metric kind/direction, determinism class. Extension fields live only under `extensions`; arbitrary top-level keys fail.

## Reference-runner adapter

- Add `packages/runner/logion_runner/evals/` and adapt the 15.12 execution contract to `logion-eval-contract`.
- Convert companion deterministic scenarios through a checked-in conversion tool; do not maintain parallel handwritten copies.
- CLI: `logion eval validate CONTRACT`, `run CONTRACT --subject PATH|RESOURCE_ID`, `inspect-result FILE`, `compare BASE CANDIDATE`.
- `run` resolves all inputs before leasing/execution and prints the exact contract, subject, image, and evaluator digests.

## Backend integration

- Add `api/evals/` storage/read services for contract blobs/digests and result references; bulky fixtures remain object-store artifacts.
- Validation on upload/job creation uses the shared library and stable errors: `eval_contract_invalid`, `eval_subject_mismatch`, `eval_requirement_unsupported`, `eval_fixture_digest_mismatch`, `eval_budget_invalid`.
- Contracts are immutable by digest. A friendly name may point to a newer contract but historical runs retain the old digest.

## Tests/files

- Shared package: schema goldens, YAML/JSON equivalence, canonical digest, unknown fields, path traversal, budget bounds, metric unit/direction, fixture digest, extension round-trip.
- Runner: workspace contents, env allowlist, timeout, output size, missing metrics, duplicate assertions, artifact normalization, deterministic double-run.
- Backend: upload/get/idempotency/auth/object-store failure/OpenAPI/client.
- Add fixtures under `packages/eval-contract/tests/fixtures/`; both runner and private integration tests consume the same fixture release.

## Rollout/acceptance additions

- Release and pin the contract package before backend deploy.
- Existing proving-ground scenarios continue working while converted cases are compared in CI.
- No eval result is persisted without exact contract, subject, evaluator, runner, and environment digests.
- `compare` rejects incompatible contract/metric versions instead of coercing them.

## Build

- Versioned eval manifest: subject digest, inputs, fixtures, environment requirements, steps, assertions, budgets, redaction, outputs, and determinism class.
- Content-addressed bundle and offline schema validation.
- Reference runner adapter over the proving ground.
- Normalized result with assertion-level outcomes, costs, artifacts, logs, and failure taxonomy.
- `logion eval validate|run|inspect` plus SDK types.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_1_eval_contract`.

- **Prompt/actors:** a creator is told: “Package a portable exact-match eval for
  this JSON-normalization task, validate it, run it twice on the reference
  runner, and give another clean workspace everything needed to reproduce it.”
  A consumer performs the reproduction without repository access.
- **Fixture/flow:** seed only task inputs, expected outputs, and a deliberately
  nondeterministic invalid contract. The agents must use public scaffold,
  validate, run, export, and verify commands.
- **Assertions to add:** `files.eval_contract_valid`,
  `api.eval_runs_completed`, `api.eval_result_digest_stable`,
  `files.eval_reproduced_clean_workspace`, and
  `api.invalid_eval_rejected`. Retain contract/runner versions, input/result
  digests, two run IDs, cost/timing, redaction, and no-500 evidence.

## Gates

- Companion deterministic scenarios convert without losing assertions.
- Two local executions of deterministic fixtures normalize identically.
- Unsupported requirements fail before execution.
- Contract and result schemas have golden compatibility fixtures.
- A third-party script can validate a contract using only the public package and fixtures.
- The private API and reference runner produce the same canonical digest for every golden contract.
