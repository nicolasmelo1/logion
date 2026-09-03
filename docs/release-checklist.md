# Release Checklist

Checklist for major Logion releases. Every item must be checked or
explicitly waived before shipping.

## Code Health

- [ ] `make lint`, `make typecheck`, and `make test` pass on `main`.
- [ ] `make agent-proving-ground-verify` passes (unit + scripted/mock
      integration tests, no network or paid providers).
- [ ] `make release-manifest-check` passes.

## Agent Proving Ground

The proving ground is the release gate that proves the product promise
with real agents. See
[`packages/agent-proving-ground/README.md`](../packages/agent-proving-ground/README.md).

- [ ] Run `make dev-up MODE=prod ROLE=admin` (point
      `LOGION_DEVRIG_API_BASE_URL` at the API target under test).
- [ ] Run `make doctor AGENT=codex` (or the driver you will use).
- [ ] Run `make agent-proving-ground-release`
      (`native_use_observation_and_feedback` with a real agent driver;
      override the scenario with `LOGION_PROVING_GROUND_SCENARIO=...` and the
      driver with `LOGION_PROVING_GROUND_AGENT_DRIVER=opencode` etc.).
      The gate scenario is the loop the release is about. `marketplace_loop`
      drives the Courses rails, which are Loop C and target 0.3; run it when
      those rails changed, not as the gate for a release that does not ship
      them.
- [ ] Confirm `files.observation_from_live_hook` passed. This is the one
      assertion that separates a harness delivering a payload from an agent
      typing one, and every other observation assertion is green either way.
- [ ] Attach `report.json` and the artifact archive from
      `.runs/proving-ground/release/`.
- [ ] Confirm no required assertion failed.
- [ ] Confirm no assertion came back `unsupported`. An optional assertion
      that could not run is a declared gap, not a pass, and it appears in the
      report with that status. Name each one in the release notes or waive it.
- [ ] Read the scenario's `kind`. A `rig` scenario is an integration test and
      is not evidence about anything an agent did:
      `logion-agent-proving-ground list` prints the kind and the agent-phase
      count for each.
- [ ] If the run is `failed` or `inconclusive`, attach a waiver (see
      below) with a follow-up issue, or rerun until conclusive.

Status policy:

- `passed` permits release.
- `failed` blocks release unless explicitly waived.
- `inconclusive` must be rerun or explicitly waived with a reason.

## Waiver Format

Waivers should be rare and must expire. Do not normalize skipping the
proving-ground gate. Attach `proving-ground-waiver.md` to the release:

```markdown
# Proving Ground Waiver

- Scenario:
- Run id:
- Status: failed | inconclusive
- Release:
- Owner:
- Reason:
- Evidence:
- Follow-up issue:
- Expiration:
```
