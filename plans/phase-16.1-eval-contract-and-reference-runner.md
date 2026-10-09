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
- The environment digest is computed over **closed, named fields — the ordered harness stack (outermost orchestrator first, each layer with id and version), model id and version, and the declared iteration budget** — not over an opaque blob and not over prose in `limitations`. A result belongs to a stack and a budget, not to a bare harness name; see [Why the pair is part of the result's identity](#why-the-pair-is-part-of-the-results-identity) and [A pair is not always a pair](#a-pair-is-not-always-a-pair).

Provide complete JSON Schemas plus typed Python models. Closed enums: outcome, assertion operator, metric kind/direction, determinism class. Extension fields live only under `extensions`; arbitrary top-level keys fail.

## Reference-runner adapter

- Add `packages/runner/logion_runner/evals/` and adapt the [15.15](phase-15.15-isolated-first-runner-node.md) job/receipt contract to `logion-eval-contract`.
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

## The contract is an artifact, and it is contestable

An attestation is worth exactly what its verifier is worth. A scorecard saying
"this does what it promises" is a function of the contract that produced it, so
a slop contract yields a slop scorecard — and an index of slop with a trust
badge on it is worse than no index.

This is the field's live failure mode, not a hypothetical. Practitioners report
verifiers that expect an output format the agent cannot infer from the task
prompt, and reference solutions that fail against their own benchmark a quarter
of the time. The published record agrees: re-annotating MMLU found 6.49% of
questions defective across all subjects and 57% in one; a review of 445
benchmarks found only 16% used any statistical test; and a study of 60
benchmarks found keeping a test set private did **not** protect against
saturation — only expert curation did.

The consequence for this phase: a contract carries a digest and a version, so it
is an artifact like any other, and it belongs in the same index as the subjects
it measures. `api/resources/constants/resource_types.py` accepts unknown values
for forward compatibility and the column is a plain `VARCHAR(64)`, so adding an
`eval_contract` type is a constant, not a migration.

What that buys:

- **A contract can be contested.** "This contract's reference solution fails a
  quarter of the time" is evidence about an artifact, which is machinery this
  roadmap already builds. It needs no new subsystem.
- **It is the best-shaped bounty in the system.** Repairing a broken oracle is
  bounded, deliverable, and success is checkable by re-running — more checkable
  than most bounties against a skill.
- **A scorecard must carry the contract digest and the contract's standing.** A
  pass under a contested contract is not a pass under a reproduced one, and
  presenting them identically is the same error as blending evidence layers.

This does **not** make Logion an eval library. The index of artifacts stays the
product: a contract with no subject measures nothing, and nobody installs a
contract. What changes is that the thing every claim depends on stops being
invisible. Publishing a defect in someone else's contract is a measurement about
someone else's artifact and follows
[the measurement publication playbook](../maintainer documentation: measurement-publication-playbook.md)
unchanged — author contacted first, rebuttal published verbatim, nothing true
and reproducible removed on request.

### Rank contracts by disclosed properties, never by a score

If Logion measures evaluators, the obvious next question is what measures the
measurer, and the regress has to stop by **policy**, not by adding another layer.
`16.5` already stops it: *"AKTP carries evidence; authority is local,
issuer-aware, and policy-versioned"* — the consumer computes the verdict.

The binding consequence: **never publish an aggregate "eval quality score."** A
single number makes Logion the terminal authority on who is allowed to measure,
which is precisely the position `positioning-and-independence.md` exists to
refuse, and it would be a badge in everything but name.

Publish the **declared properties** instead, and let a consumer weigh them under
its own policy:

- is there a control group? is there any statistical test?
- is there a held-out set? is there a contamination check?
- **does the reference solution pass its own benchmark?**
- who has reproduced it, when, and under which model-harness pair?

This is the disclosure standard [arXiv:2605.23950](https://arxiv.org/abs/2605.23950)
proposes and that nothing in the field implements. It is also the cheapest
subject type to bootstrap: unlike a skill, a benchmark has inbound citations,
replication literature and published critique, so the free evidence layer is
already written by other people. That property is what makes `eval_contract` and
`model` the fastest path to
[`public-answer-surface.md`](public-answer-surface.md)'s rule that the box never
returns an empty screen.

### Why the pair is part of the result's identity

Harness-induced variance can exceed model-induced variance to the point of
reversing model rankings, and the same model scores materially differently under
different scaffolds on the same benchmark
([arXiv:2605.23950](https://arxiv.org/abs/2605.23950)).

So harness and model are not limitations to disclose at the end of a report; they
are part of what the result *is*. Two requirements follow:

- `logion eval compare BASE CANDIDATE` **fails closed** when the pair differs,
  rather than rendering the comparison with a caveat.
- The version-over-version chart required by `release-0.2.md` must refuse to plot
  two points across differing pairs without saying so on the chart. Otherwise a
  harness upgrade renders as an artifact improvement, on the most important
  public visual the project has.

Ranking **models** is out of scope and stays out: it is the most expensive thing
available and the most saturated (Artificial Analysis, LMArena, HELM, OpenRouter),
and `release-0.2.md` already fixes models as metadata-first. If model ranking ever
enters, it enters as **model-harness pair** ranking.

**Correction, 2026-08-27.** An earlier version of this section claimed nobody
publishes pair rankings. That is wrong: Warp Factories advertises benchmark
comparisons across models *and* harnesses, orchestrating third-party harnesses
by name (`claude code`, `codex`, `cursor`, "any MCP-capable coding agent"). The
distinction that survives is the subject, not the axis — Warp's own page says
those benchmarks measure "your factory's agents executing your specific
workflows, **not third-party artifact quality**", and the results stay private
to the customer. What is unoccupied is a **public, reproducible pair-qualified
measurement about an artifact its publisher does not control**, which is what
the observation envelope's first-class `harness` field and the closed environment
fields above are for. See
[`positioning-and-independence.md`](positioning-and-independence.md).

### A pair is not always a pair

**Added 2026-09-02.** The section above is right that harness and model are part
of the result's identity, and wrong that a *pair* is enough to express it. A
harness can be wrapped by another harness, and the wrapper moves the number more
than most subjects do.

[arXiv:2609.01481](https://arxiv.org/abs/2609.01481) (Harness-of-Harness) runs
existing coding-agent harnesses inside an outer planner/developer/QA loop that
keeps versioned project state across iterations. Holding the inner harness and
the model constant, it reports an average relative gain of 52.25% (maximum
82.86%) after three iterations across three harness-model pairs; FrontierSWE
dominance rising 44% to 71% at three iterations and 72.67% at ten against a
27.33% baseline; and GameCraft-Bench 49.58 to 71.52 under Codex + GPT-5.5
(high). Its own pass-controlled comparison — 71.52 against 58.24 at equal passes
and comparable token usage — is the admission that matters here: the honest
comparison had to hold the *budget* fixed, not just the pair.

Two consequences bind this phase:

- **The environment is a stack, not a pair.** "Codex + GPT-5.5" and "Codex under
  a three-iteration orchestrator + GPT-5.5" declare the same pair and are not
  the same environment. A result that records only the innermost harness is true
  in every field it carries and wrong in what it attributes: the orchestrator's
  gain renders as the subject's.
- **The budget is part of the identity.** The same stack at three iterations and
  at ten is two results, and nothing in the schema stops them from being
  compared.

This is the failure the pair rule already refuses, one layer out. It is cheapest
to close here: `release-0.2.md` records that evidence recorded at 0.2 is
permanent, and a result whose environment cannot name the orchestrator is
permanently uninterpretable rather than merely incomplete.

**What stays out.** A harness stack is not a new subject type. Indexing an
orchestrator as a `Resource`, so that a published measurement whose subject *is*
a harness stack has somewhere to attach, is a real gap and it belongs to
whichever phase owns the citation layer. This phase only has to record the
environment it ran in.

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

## Implementation guide

Everything above is *why*. This section is *what to type*, in order. It is
binding: where it disagrees with a summary bullet earlier in this file, this
section wins. Do not begin at step 4 because it looks like the interesting part
— each step's "done when" is the precondition of the next.

### Repository conventions you must obey

These are enforced, not stylistic. A PR that violates them fails before review.

- Line length 79. `ruff` config lives in each package's `pyproject.toml`.
- `typing.Any` is banned repo-wide via `flake8-tidy-imports`. Use a
  `TypedDict`/dataclass for a known shape, `JsonValue`/`JsonObject` from the
  package's `_json` module at a JSON boundary, or a `TypeVar`.
- `max-complexity = 12`.
- The public package must not import from the private repository, ever. The
  dependency arrow is one-way: `logion-eval-contract` knows nothing about
  `api/`.
- New public packages join the workspace with `[tool.uv.sources]` entries, the
  way `packages/runner/pyproject.toml` declares `logion-client`.

### Step 1 — `packages/eval-contract/`, the shared library

The only parser, validator, canonicalizer and result-normalizer in the system.
The private API imports a **pinned released version**; it does not reimplement
any of this, and a second implementation of canonicalization is the specific
defect `api.canonical_digest_agrees` exists to catch.

Create, in the public repository:

```text
packages/eval-contract/
  pyproject.toml                     name = "logion-eval-contract"
  logion_eval_contract/
    __init__.py
    _json.py                         JsonValue/JsonObject, copied pattern
    schema/
      eval-contract.v1.schema.json
      eval-result.v1.schema.json
    models.py                        typed models, closed enums
    parse.py                         YAML|JSON -> model, fails closed
    canonical.py                     JCS canonicalization + digest
    normalize.py                     raw run output -> EvalResult
    errors.py                        the five stable error codes
  tests/
    fixtures/                        the shared fixture release
    test_schema_golden.py
    test_yaml_json_equivalence.py
    test_canonical_digest.py
    test_unknown_fields.py
    test_path_traversal.py
    test_budget_bounds.py
    test_metric_unit_direction.py
    test_fixture_digest.py
    test_extension_roundtrip.py
```

**Contract media type:** `application/vnd.aktp.eval-contract.v1+json`.
Authoring YAML is normalized to this JSON *before* hashing, so the digest of a
YAML file and of its JSON normalization are identical. A test must prove that.

**Required top-level contract fields.** All required; absence is an error, not
a default:

`schema_version`, `subject` (`{type, digest_constraint}`), `archetype`,
`inputs`, `fixtures` (each by digest), `runtime_requirements`, `steps`,
`metrics`, `assertions`, `budgets`, `outputs`, `redaction`,
`determinism_class`, `evaluator_requirement`.

**Required top-level result fields:**

`contract_digest`, `subject_digest`, `environment` (the closed fields below),
`environment_digest`, `assertion_vector`, `metrics` (typed values), `outcome`,
`artifacts`, `resource_usage`, `limitations`.

`environment` carries the fields themselves and not only their digest. A digest
alone tells `compare` that two results differ and never which field differed,
which is the difference between refusing a comparison and explaining it.

**Closed enums.** Any value outside these fails validation:

| Enum | Values |
| --- | --- |
| `outcome` | `passed`, `failed`, `errored`, `skipped` |
| `assertion operator` | `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `matches` |
| `metric kind` | `count`, `ratio`, `duration_ms`, `tokens`, `cost_usd` |
| `metric direction` | `higher_is_better`, `lower_is_better` |
| `determinism_class` | `deterministic`, `seeded`, `nondeterministic` |
| `contract standing` | `unreviewed`, `contested`, `reproduced`, `superseded` |

**Extension rule.** Extra keys live only under `extensions`. An arbitrary
top-level key fails. This is what `unknown_field_rejected` in the evidence
contract observes.

**The environment digest is computed over closed, named fields only** —
`harness_stack`, `model_id`, `model_version`, `iteration_budget` — never over an
opaque blob and never over prose in `limitations`. Read
[Why the pair is part of the result's identity](#why-the-pair-is-part-of-the-results-identity)
and [A pair is not always a pair](#a-pair-is-not-always-a-pair) before touching
this; they are the reason the fields are closed.

`harness_stack` is an ordered list, outermost first, of
`{harness_id, harness_version}`, with at least one entry; the innermost entry is
the harness that actually invoked the subject. `iteration_budget` is how many
planning/coding/testing passes over one subject the outermost layer was
permitted — `1` for a single-shot run, never inferred, and never omitted.

A runner that cannot name every layer above it **refuses to emit a result**
rather than reporting the innermost harness alone. That refusal is runner-side
and deliberately not a sixth API error code: `api.invalid_eval_rejected` is
keyed by the five codes in [step 4](#step-4--apievals-backend-integration-private-repository),
and widening that set would weaken the assertion rather than strengthen it.

**Done when:** `logion-eval-contract` builds, its test suite passes, and the
same golden contract expressed as YAML and as JSON produces one identical
digest.

### Step 2 — `packages/runner/logion_runner/evals/`, the adapter

Adapts the **existing** 15.15 job/receipt contract. Do not invent a parallel
execution path, and do not copy proving-ground code — 15.15 reuses
`agent_proving_ground/{runner,artifacts,timeline,redaction,assertions}` through
adapters and this follows the same rule.

What exists already and must be reused as-is:

- `logion_runner.job.Lease` — carries `contract_digest`, `sandbox_profile`,
  `sandbox_profile_digest`, `input_digests`, `limits`, `artifacts`,
  `idempotency_key`.
- `logion_runner.receipt_builder.ReceiptInput` — already has `contract_digest`,
  `input_digests`, `output_artifacts`, `assertion_vector_digest`,
  `environment_fingerprint`, `redactions_applied`.
- `logion_runner.sandbox.profiles` — profile v0, digest-pinned image only.

So the eval adapter is a *mapping*, not a new runtime: an `EvalContract`
resolves to a `Lease`-shaped job, and an `EvalResult` is normalized from the
outcome the existing receipt already describes.

**CLI.** Exposed through the `logion-node` entry point in
`packages/runner/pyproject.toml`:

| Command | Behaviour | Exit code |
| --- | --- | --- |
| `logion eval validate CONTRACT` | offline schema + semantic validation | `0` valid, `2` invalid |
| `logion eval run CONTRACT --subject PATH\|RESOURCE_ID` | resolve, lease, execute | `0` ran, `2` rejected pre-execution, `1` execution error |
| `logion eval inspect-result FILE` | print normalized result | `0`/`2` |
| `logion eval compare BASE CANDIDATE` | compare two results | `0` comparable, `3` **refused** |

`run` **resolves every input before leasing or executing**, and prints the exact
contract, subject, image and evaluator digests it resolved. A run that leases
first and resolves later cannot satisfy `rejected_before_execution: true`.

`compare` **fails closed with exit `3`** when the environment differs between
the two results — a differing harness stack, model, or iteration budget. It does
not render the comparison with a caveat. This is not a preference; a caveat is
what lets a harness upgrade, or one extra orchestration pass, read as an artifact
improvement.

**Done when:** two executions of a `deterministic` golden contract produce byte-
identical normalized results, and `compare` exits `3` across a differing stack, a
differing model, and a differing budget.

### Step 3 — the conversion tool

Companion deterministic scenarios become eval contracts through a checked-in
tool. **Do not hand-maintain parallel copies** — the whole point is that one
source of truth converts.

The tool must emit, per conversion: `source_scenario`, `source_assertion_ids`,
`converted_assertion_ids`, `dropped_assertion_count`, `added_assertion_count`,
`conversion_tool_version`. Both counts must be `0`.

Counting alone is insufficient and the gate reflects that: a converter that
drops one assertion and invents another keeps the count identical, so the
**identity sets** are compared, not their sizes.

**Done when:** every existing companion deterministic scenario converts with
both counts at `0`, and CI compares converted cases against the originals while
the original scenarios keep working.

### Step 4 — `api/evals/`, backend integration (private repository)

Storage and read services for contract blobs/digests and result references.
Bulky fixtures stay object-store artifacts; do not put them in Postgres.

**Validation on upload and on job creation uses the shared library.** The five
stable error codes, all returning **HTTP 422**:

`eval_contract_invalid`, `eval_subject_mismatch`,
`eval_requirement_unsupported`, `eval_fixture_digest_mismatch`,
`eval_budget_invalid`.

Each must reject **before** any job row is created. `api.invalid_eval_rejected`
is keyed by these five codes, so a run that exercises four of them does not
close the criterion.

**Contracts are immutable by digest.** A friendly name may point at a newer
contract; historical runs keep the old digest. There is no update-in-place path.

**`eval_contract` is a resource type, not a migration.**
`api/resources/constants/resource_types.py` accepts unknown values for forward
compatibility and the column is a plain `VARCHAR(64)`. Adding the constant is
the whole change. A contract is indexed **alongside** the subjects it measures,
in the same index — that is what `indexed_alongside_subject` observes.

**A result carries the contract digest *and* the contract's standing.** A pass
under a `contested` contract is not a pass under a `reproduced` one, and
rendering them identically is the defect
`api.eval_contract_indexed` exists to catch.

**Never accept these from the client** on `submit_eval_result` —
`phase-integrity.yaml` fails the build if the request body declares them:
`contract_standing`, `reproduced_by`, `independence_group`,
`environment_verified`, `issuer_id`. A runner reporting its own eval result is
the party with the motive to declare it reproduced.

**Done when:** upload/get/idempotency/auth/object-store-failure tests pass,
OpenAPI regenerates, and the generated client syncs.

### Step 5 — the proving-ground scenario

Add `packages/agent-proving-ground/agent_proving_ground/scenarios/builtin/eval_contract_reference_runner.yaml`
and the assertion handlers. Creating this file **activates the phase**, so the
gate goes red until every assertion below retains the facts its evidence
contract in `packages/contract-audit/policy/phase-integrity.yaml` names. That is
intended; do not create the file first to "see what happens".

The nine required assertions, their evidence contracts already written:

`files.eval_contract_valid`, `api.eval_runs_completed`,
`api.eval_result_digest_stable`, `files.eval_reproduced_clean_workspace`,
`api.invalid_eval_rejected`, `files.converted_scenario_assertions_preserved`,
`api.canonical_digest_agrees`, `api.eval_contract_indexed`, `logs.no_500s`.

Read the `"16.1"` block under `evidence_contracts:` before writing a handler.
It is the list of facts each handler must emit, typed as
`{"ok": true, "value": ...}` or `{"ok": false, "failure": "unreachable"}`.
`status: "passed"` in a report is a claim by the party with the motive and the
auditor does not consult it.

Every `mutations:` entry in that block names a test in
`packages/contract-audit/tests/unit/test_evidence_contract.py` that **does not
exist yet**. Writing them is part of this phase: each one proves the auditor
actually fails when that fact is wrong.

**The customer prompt may not name a path.** `customer_fidelity` in the policy
forbids `/Users/`, `/home/`, `${LOGION_PUBLIC_REPO_PATH}`, `uv run`,
`packages/` and `tests/fixtures/` in a goal. A customer reaches the product
through the artifact on their `PATH`; a goal naming the checkout is a replay
recipe, not a customer prompt.

**Done when:** `make runner-evidence` produces a retained local-devrig run and
`artifacts/phase-gates/phase-16.1.json` seals it with `status: passed`, no
caveats and no unsupported assertions.

### Order of operations, and what blocks what

```text
1 eval-contract library  ──┬──> 2 runner adapter ──┐
                           │                       ├──> 5 scenario + gate
                           ├──> 3 conversion tool ─┤
                           └──> 4 api/evals ───────┘
```

Steps 2, 3 and 4 are independent of each other and all depend on step 1. Step 5
depends on all four. **Release and pin the contract package before the backend
deploy** — step 4 consuming an unreleased step 1 is how the two canonicalization
implementations drift apart without anyone noticing.

### Things that will look like improvements and are not

- **Do not publish an aggregate "eval quality score."** Rank by disclosed
  properties. A single number makes Logion the terminal authority on who may
  measure, which contradicts `16.5` and is a badge in everything but name.
- **Do not make `compare` render across differing environments**, however loud
  the caveat. A differing harness stack, model, or iteration budget all refuse.
- **Do not flatten a harness stack to its innermost harness** to make a result
  fit a pair-shaped field. Refuse the result instead.
- **Do not reimplement parsing or canonicalization in the private API.** Import
  the pinned package.
- **Do not widen `resource_types.py` into a migration.** It is a constant.
- **Do not add a message broker.** v0 polls, exactly as 15.15 does.
- **Do not let the reproduction step see either checkout.** If it can, it proves
  the package is redundant rather than sufficient.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:eval_contract_reference_runner`.

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

Each gate names the check that proves it; see `DEFERRED.md` for
what the markers below leave unproven.

- [ ] Companion deterministic scenarios convert without losing assertions.
      (proof: assertion:files.converted_scenario_assertions_preserved)
- [ ] Two local executions of deterministic fixtures normalize identically.
      (proof: assertion:api.eval_result_digest_stable)
- [ ] Unsupported requirements fail before execution.
      (proof: assertion:api.invalid_eval_rejected)
- [ ] Contract and result schemas have golden compatibility fixtures.
      (proof: assertion:files.eval_contract_valid)
- [ ] A third-party script can validate a contract using only the public package
      and fixtures.
      (proof: assertion:files.eval_reproduced_clean_workspace)
- [ ] The private API and reference runner produce the same canonical digest for
      every golden contract.
      (proof: assertion:api.canonical_digest_agrees)
- [ ] An eval contract is addressable as a resource in the same index as its
      subjects, and a result carries both the contract digest and that
      contract's standing.
      (proof: assertion:api.eval_contract_indexed)
- [ ] An eval result names its full harness stack, model, and iteration budget
      as closed fields, and the environment digest is computed over exactly
      those fields.
      (proof: unspecified:no assertion inspects the environment field set; api.eval_result_digest_stable proves the digest is stable, not what it is computed over)
- [ ] `logion eval compare` exits `3` when the harness stack, the model, or the
      iteration budget differs between base and candidate.
      (proof: unspecified:no proving-ground assertion exercises compare across differing environments)
