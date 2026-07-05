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
- [ ] Run `make agent-proving-ground-release` (marketplace_loop with a
      real agent driver; override with
      `LOGION_PROVING_GROUND_AGENT_DRIVER=opencode` etc.).
- [ ] Confirm the admin/operator phase ran with admin capability, or
      attach a waiver explaining why it was unsupported.
- [ ] Attach `report.json` and the artifact archive from
      `.runs/proving-ground/release/`.
- [ ] Confirm the skill/course usage report assertion passed.
- [ ] Confirm no required assertion failed.
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
