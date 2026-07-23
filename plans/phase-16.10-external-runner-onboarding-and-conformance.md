<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.10 — External runner onboarding and conformance

> **Dogfood status:** Logion follows the public onboarding path for every new internal runner; there is no privileged hidden path.
> **After this phase:** another operator can launch a useful CPU node from documentation and pass conformance without manual database edits.
> **Honesty boundary:** conformance establishes protocol behavior and isolation claims tested by fixtures, not operator trustworthiness.

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

Remove founder-operated infrastructure as a prerequisite for network growth.

## Dogfood prompt for the implementing agent

```text
Find a Logion resource about developer onboarding, deployment runbooks, container
distribution, or conformance testing. Recall first; on LOW/NONE search the store for
"developer onboarding deployment runbook conformance". Follow the mandatory
acquisition/reconciliation protocol and use it while following the clean-room
runner setup from scratch. Record every unclear step in
`artifacts/dogfood/phase-16.10.md`, fix the docs/product, repeat, and submit feedback
once the clean-room node completes a fixture.
```

## Distribution artifacts

- Publish versioned OCI image by immutable digest, SBOM, provenance/signature, checksums, release notes, and supported architecture matrix.
- Provide `docker compose` for workstation/server, a minimal systemd path, `.env.example` with no real secrets, and optional Terraform example outside Logion production modules.
- Bootstrap command creates local key, begins enrollment, prints capability/permission/cost summary, and requires operator confirmation before accepting work.
- Upgrade verifies image signature/digest, drains, preserves key/job state, migrates local state, health-checks, and rolls back on failure.

## Public conformance suite

Create `packages/runner-conformance/` runnable against any node. It must test protocol/version negotiation, enrollment challenge, capability probe, job lease/heartbeat, deterministic result, receipt signature, artifact upload, cancellation, timeout, malformed job refusal, sandbox canaries, coordinator outage/recovery, and key rotation.

Output is a signed conformance report with suite/image/platform digests and per-test results. Publishing is opt-in. Passing does not make an operator trusted; it marks protocol capabilities probed.

## Operator UX/runbooks

- Document prerequisites, ports/egress, expected disk/RAM/CPU, no-GPU starter configuration, key backup/rotation/revocation, pricing hints, allowlists, spend/earning tax caveat, log redaction, support bundle, and uninstall.
- Dashboard/CLI shows active/queued/recent jobs, per-job resource use, rejected requirements, estimated/actual compensation, coordinator fees, receipt/evidence links, version status, and drain/revoke.
- Support bundle is local-redacted and previewed before sharing.

## Tests/release gates

- CI builds image, generates SBOM, scans/signs, boots compose, and runs conformance with no source-tree mount.
- Clean VM test follows documentation verbatim under an hour; record human/agent timing and manual interventions.
- Upgrade N-1→N and rollback with queued/running job fixtures; corrupt state/key and disk-full diagnostics.
- Uninstall removes containers/config but preserves keys/history by default and clearly offers explicit destructive removal separately.

## Rollout

First onboard a second Logion-controlled host using only public docs, then an invited independent operator. Public onboarding stays approval-gated until abuse/settlement support is ready.

## Build

- Containerized reference runner and minimal deployment profiles for a workstation and inexpensive server.
- Enrollment, key custody, capability declaration, pricing, allowlists, upgrade, backup, and revocation runbooks.
- Public conformance suite including sandbox escape attempts, lease races, malformed jobs, and reproducibility fixtures.
- Operator dashboard/CLI for jobs, costs, receipts, earnings, and failures.
- Compatibility matrix and rolling protocol-version policy.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_10_clean_runner_onboarding`.

- **Prompt:** in a blank checkout/home, an operator receives only: “Using the
  public Logion documentation, install a CPU reference runner, enroll it
  against this local node, pass conformance, and execute the sample job.”
- **Fidelity:** no private repo, preinstalled editable package, hidden command
  sequence, or copied credentials. The agent must discover installation and
  troubleshooting from released/public artifacts.
- **Assertions to add:** `files.runner_installed_from_public_artifact`,
  `api.runner_conformance_passed`, `api.clean_runner_job_completed`,
  `security.runner_has_no_server_credentials`, and
  `files.onboarding_requires_no_source_tree`.
- **Evidence:** retain docs/release versions, install transcript, conformance
  cases, receipt, elapsed time/cost, redaction, and no 500s.

## Gates

- A clean-room operator completes setup in under one hour.
- Conformance needs no Logion production credentials.
- One independent operator completes and verifies a replicated job.
- Upgrade and rollback preserve pending jobs and signing identity.
- Published image has verifiable provenance/SBOM and runs without repository checkout.
- The independent operator's successful report identifies a distinct operator/independence group.
