<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.2 — Typed evaluators and the skill reference evaluator

> **Dogfood status:** Logion evaluates indexed skills against its real bounded workflow corpus using the public evaluator interface.
> **After this phase:** new resource types plug into one contract without pretending their metrics are interchangeable.
> **Honesty boundary:** scores remain evaluator- and benchmark-specific.

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

Separate the shared execution envelope from type-specific installation, invocation, assertions, and metrics.

## Dogfood prompt for the implementing agent

```text
Find a Logion resource about plugin architecture, adapters, dependency injection, or
Python interfaces. Recall first; if no HIGH result, search
`logion listings search --query "plugin architecture adapter interface Python"
--include-indexed --limit 5 --json`. Follow the mandatory acquisition/reconciliation
protocol and apply it to the evaluator registry and
skill adapter boundaries. Record exact applied advice in
`artifacts/dogfood/phase-16.2.md`. Use the installed skill to review one implementation
diff, then submit one honest feedback report after tests pass.
```

## Evaluator SDK contract

Create `logion/packages/evaluator-sdk/` with a typed interface:

```python
class Evaluator(Protocol):
    descriptor: EvaluatorDescriptor
    def supports(self, resource: ResourceDescriptor, contract: EvalContract) -> SupportDecision: ...
    def prepare(self, ctx: PrepareContext) -> PreparedEvaluation: ...
    def execute(self, ctx: ExecuteContext) -> RawEvaluation: ...
    def normalize(self, raw: RawEvaluation) -> EvalResult: ...
    def cleanup(self, ctx: CleanupContext) -> None: ...
```

Descriptor binds evaluator ID/version/source digest, supported resource/media types, sandbox requirements, network/secrets policy, metric namespaces, and compatibility range. Plugins are discovered from a configured allowlist/entry points; a resource cannot cause arbitrary module import.

## Skill reference evaluator

- Put implementation under `packages/evaluators/skill/` or one package with a clear entry point.
- Resolve an exact `agent_skill` version and verify bundle digest before extraction.
- Create project-scoped install inside the job workspace using existing CLI install helpers as a library; do not shell out to `logion skills install` when a safe library call exists.
- Project contents: fixture repo, control/assisted workspaces, pinned skill, harness projection, and output only. No global `~/.logion` or agent skill directory writes.
- Run control and assisted arms with the same agent/provider/config/budgets. Record any unsupported seed determinism as a limitation.
- Capture declared vs observed capabilities, tool calls, assertion vector, tokens/cost/latency, and cleanup result.
- Skill instructions are untrusted input and cannot modify evaluator policy/assertions.

## Backend/runner files

- Runner: evaluator registry, allowlist config, lifecycle orchestration, evaluator artifact cache, and metrics.
- API: evaluator descriptor registry/read endpoints and job matching constraints; store descriptor digest with result.
- Client/CLI: `logion evaluators list|show|doctor`; administrative registration remains config/deploy controlled in this phase.

## Stable failure taxonomy

`unsupported`, `prepare_failed`, `install_failed`, `policy_denied`, `execution_failed`, `assertion_failed`, `normalize_failed`, `cleanup_failed`, `infrastructure_error`. Cleanup failure cannot turn a failed eval into pass and must remain in receipt limitations.

## Tests

- Fake evaluator lifecycle/order and cleanup-on-every-exit.
- Malicious plugin import/descriptor mismatch, duplicate evaluator ID, incompatible media type, changed source digest.
- Skill archive traversal/symlink, global-state mutation, undeclared network/secret/tool, control/assisted budget mismatch.
- Golden skill fixtures for helpful, no-effect, harmful/regression, timeout, and nondeterministic cases.
- End-to-end one companion scenario through public contract → skill evaluator → runner → result.

## Rollout/acceptance additions

- Only the signed/pinned skill evaluator is allowed in production initially.
- Evaluator upgrades create a new descriptor digest and never overwrite past meaning.
- A fake second resource type passes SDK conformance without coordinator or database schema changes.

## Build

- Evaluator plugin interface keyed by resource type and media type.
- Skill reference evaluator with project-scoped install, baseline/control, assisted run, capability observation, and cleanup.
- Typed metric namespaces and explicit units/directionality.
- Evaluator identity, version, source digest, and environment fingerprint in every result.
- Quarantine for evaluator/resource incompatibility.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_2_skill_evaluator`.

- **Prompt:** “Evaluate whether this indexed debugging skill improves completion
  of the supplied repository task. Compare control and assisted arms, report
  declared/observed capabilities and limitations, and do not change my global
  agent configuration.”
- **Fixtures:** one useful skill, one no-op control, and one skill that requests
  undeclared access; all run with fixed cases/seeds in isolated workspaces.
- **Assertions to add:** `api.typed_eval_result_exists`,
  `api.eval_arms_comparable`, `api.skill_effect_measured`,
  `sandbox.global_agent_state_unchanged`, and
  `api.undeclared_capability_rejected`. Evidence includes per-arm digests and
  metrics, evaluator/version, policy outcome, costs, no 500s, and redaction.

## Gates

- Adding a fake resource evaluator requires no coordinator schema change.
- Skill runs cannot mutate global companion state.
- Baseline and assisted runs share equivalent budgets and inputs.
- Raw assertions remain visible beside any aggregate score.
- All evaluator subprocesses run inside the 15.15 sandbox; the coordinator never imports evaluator plugin code.
- The project-scope install is removed after the run and a canary proves no global installation changed.
