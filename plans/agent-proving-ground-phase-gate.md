<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Agent proving ground — mandatory phase completion gate

Status: normative for Phase 15.9 and every later implementation phase.

This document defines the common part of the end-to-end gate. Each phase must
also define its own named scenario, actors, customer prompt, fixtures, observable
effects, and assertions. A link to this document is not a substitute for that
phase-specific scenario.

## Non-negotiable completion rule

A phase is not complete when unit, integration, or scripted proving-ground tests
pass. It is complete only when all of the following are true:

1. its scenario YAML exists under
   `logion/packages/agent-proving-ground/agent_proving_ground/scenarios/builtin/`;
2. schema, fixture, assertion, adapter, and deterministic runner tests pass;
3. the public Logion API is running locally and the scenario uses
   `api_adapter: local-devrig`;
4. a real cheap agent completes the flow from a customer-like prompt;
5. every required assertion is `passed`, none is `unsupported`, the scenario
   status is `passed`, and `logs.no_500s` passes;
6. the redacted run artifact is attached to the phase/PR evidence.

`scripted`, `local-process`, a mocked API, direct fixture mutation, or a human
performing the missing product step may be used while authoring and debugging.
None can waive the real-agent gate.

## Required driver contract

Every phase scenario must carry both cheap driver configurations:

```yaml
api_adapter: local-devrig
driver_config:
  codex:
    model: gpt-5.4-mini
  claude-code:
    model: claude-haiku-4-5
```

The required merge run uses `codex`/`gpt-5.4-mini` by default. If that provider
is unavailable, `claude-code`/`claude-haiku-4-5` is an acceptable substitute;
the report must record the actual driver and model. “Unavailable” does not
include the model failing to use the product successfully. At least one of the
two real cheap models must pass from a clean run. High-risk changes to install,
identity, consent, money, sandboxing, signatures, or federation should run both
when credentials are available, but one remains the formal phase gate.

Agents use `timeout_seconds: 900` unless the phase justifies another limit.
Individual prompt phases use at most `timeout_seconds: 600`. The run report must
record elapsed time plus provider token/cost metadata when the driver exposes
it. A timeout, provider crash, exhausted context, or missing credential makes
the run `inconclusive`, never `passed`.

## Customer-fidelity rules

- Start from the public entry point a customer would have: the Logion CLI,
  companion skill/plugin, documented native tool, or public HTTP API.
- Give the agent a goal and realistic context, not a sequence of hidden API
  calls, database identifiers, expected command transcript, or implementation
  hints that reveal the answer.
- Put product instructions in the installed Logion artifacts and public help,
  not in a scenario-only system prompt. The system prompt may identify the
  persona, forbid source edits, and tell the agent to stop and report genuine
  product errors.
- Use a fresh per-agent workspace and the role-scoped credentials produced by
  the dev rig. The agent must discover returned IDs from normal command output.
- Agents must not query Postgres, call private test helpers, edit server state,
  or read another persona's workspace. Setup code may create only the external
  fixtures and initial public state explicitly listed by the phase.
- Exercise the real acquisition tool where the feature integrates with one:
  `npx skills`, `npx plugins`, `hf`, or Logion's own artifact installer. A fake
  executable is allowed only for destructive/adversarial fixtures and must
  preserve the real command-line boundary.
- Judge success from API/database/log/file observations after the agent acts,
  not from claims in the agent's final prose.
- Include at least one negative or retry path for idempotency, consent, policy,
  authorization, isolation, or duplicate handling, as applicable.

## Scenario implementation checklist

For `phase_X_Y_<slug>.yaml`, the implementer must:

1. add the YAML to the builtin scenario directory and make it loadable as
   `builtin:phase_X_Y_<slug>`;
2. add minimal reproducible fixtures under
   `logion/packages/agent-proving-ground/tests/fixtures/<scenario>/`;
3. add every missing observed-effect query to
   `agent_proving_ground/api_adapters/_queries.py` and support it in
   `local_devrig.py`;
4. add typed assertions under `agent_proving_ground/assertions/`, register them
   in `assertions/registry.py`, and unit-test both pass and fail outcomes;
5. add a deterministic integration test that runs the same scenario with
   `scripted` only to validate orchestration and assertions;
6. preserve a real-agent test/run target, marked and credential-gated rather
   than silently skipped in the phase evidence;
7. redact secrets and raw private telemetry from transcripts, timeline,
   snapshots, and assertion evidence.

New assertions should express domain outcomes such as
`api.resource_acquisition_exists` or `api.attestation_verified`; do not collapse
the whole scenario into a generic `db.row_exists`. Database assertions may
supplement, but not replace, public/API-observed effects.

## Canonical local run

From `logion/`:

```bash
make dev-up MODE=prod ROLE=admin
make doctor AGENT=codex
uv run logion-agent-proving-ground run \
  builtin:<phase-scenario> \
  --api-adapter local-devrig \
  --agent-driver codex
```

Fallback:

```bash
make doctor AGENT=claude-code
uv run logion-agent-proving-ground run \
  builtin:<phase-scenario> \
  --api-adapter local-devrig \
  --agent-driver claude-code
```

Before either command, reset/seed through the documented dev-rig target for the
scenario. The phase spec must name that target. Reusing unexplained state from a
previous run invalidates the evidence.

## Required retained evidence

The PR or linked run artifact must include:

- scenario name and git SHA;
- API adapter, base URL class (`local-devrig`, never a secret URL), driver, and
  model;
- start/end time and token/cost data when available;
- scenario result, phase results, and all assertion results;
- redacted timeline and agent transcripts;
- fixture versions/content digests;
- API/log snapshots sufficient to diagnose a failed assertion.

Flaky success is failure. After a flaky run, fix the product, prompt surface,
fixture, or assertion and produce two consecutive clean passes with the same
model before closing the phase.
