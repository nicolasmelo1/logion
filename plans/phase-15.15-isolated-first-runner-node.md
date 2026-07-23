<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.15 — Isolated first runner node

> **Dogfood — Level 6 (execution):** Logion becomes the first functional runner and applies attributed, feedback-bearing resources to bounded Logion work in isolated environments.
> **After this phase:** one inexpensive CPU server can claim jobs, run deterministic or agent-assisted tasks, upload artifacts, and publish execution evidence.
> **Honesty boundary:** this is a Logion-operated runner; it does not establish decentralization or independent agreement.

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

Reuse the proving ground and job system to operate one real node without owning an H100/H200/B200 fleet.

Phase 15.14.1 is a dependency. The first target is the founder's MacBook, not
Hetzner: keep the existing host Hermes as operator and run isolated consumer,
evaluator, contributor, sponsor, and auditor agents in rootless Docker/Podman
containers. A remote CPU server is a later deployment of the same node package.

## Dogfood prompt for the implementing agent

```text
Find and use a Logion resource about containers, sandboxing, least privilege,
untrusted-code execution, or worker architecture. Run recall first:
`logion recall search "sandbox untrusted code container worker" --limit 5`.
If LOW/NONE, search:
`logion listings search --query "sandbox untrusted code container security"
--include-indexed --limit 5 --json`.
Inspect the exact resource/version, distribution, and permissions. Follow the mandatory
acquisition protocol and use it to attack this
phase's isolation design and Docker/runner configuration. Document adopted and
rejected advice in `artifacts/dogfood/phase-15.15.md`. Exercise the acquired resource
inside the new runner on a harmless fixture if its declared requirements permit it.
Submit one honest review after the task; never review an indexed-only or unused item.
```

## Architecture and trust boundary

The API is coordinator only. The runner is a separately deployed process with no database credentials, no Docker socket, no production filesystem mount, and no long-lived API key. It communicates over authenticated HTTPS:

```text
API/coordinator → offer/lease → runner
runner → heartbeat + artifact PUT + signed receipt → API
runner → ephemeral sandbox/container → resource + fixture
```

For v0, the runner may poll; do not add a message broker. Extend the current durable `Job` domain only if its state machine can preserve external leases cleanly; otherwise add `execution_jobs` rather than overloading scanner handler semantics.

## Job and receipt contract

- States: `queued → leased → running → succeeded|failed|timed_out|cancelled|inconclusive`; lease expiry returns a job to queued with attempt increment until max attempts.
- Job contains contract digest, resource/version/digest, required runner capabilities, sandbox profile, artifact upload grants, wall/CPU/memory/output limits, and idempotency key.
- Receipt contains job/attempt/runner, exact input digests, image/runtime digest, environment fingerprint, commands/tool calls, timestamps, resource usage, exit/outcome, assertion vector, output artifact digests, and redactions applied.
- Receipt is JCS-canonicalized and signed by the runner key. Coordinator verifies before accepting. A late receipt is stored as late evidence but cannot win settlement automatically.

## Concrete file plan

### Coordinator (`backend repository`)

- Add migration/models for runner identities, execution jobs/attempts, leases, receipts, and artifact grants.
- Add `api/runners/` and `api/executions/` layered packages with enrollment, poll/lease, heartbeat, upload-complete, submit-receipt, cancel, and operator read services.
- Add controllers under `/v1/runners/*` using runner authentication distinct from agent/user API keys.
- Add job recovery to the existing worker sweep without allowing both the internal `JobRunner` and external runner to execute one job.
- Add settings/feature flags, audit events, rate limits, and metrics.

### Reference runner (`logion`)

- Create `packages/runner/` as a separately installable package; do not bury network polling in the CLI process.
- Reuse `packages/agent-proving-ground/agent_proving_ground/{runner,artifacts,timeline,redaction,assertions}` through adapters. Do not copy them.
- Modules: config/key store, coordinator client, lease loop, sandbox backend interface, Docker/Podman backend, local test backend, artifact uploader, receipt builder/signer, and CLI.
- Commands exposed through the package or Logion CLI: `logion node enroll`, `doctor`, `run --once`, `jobs`, `rotate-key`.

### Infrastructure

- Add `deploy/local-node/compose.yaml`, a pinned multi-architecture agent image,
  per-role read-only policy/config, separate named homes, and disposable
  repository worktrees.
- Add `make node-dev-up`, `node-dev-down`, `node-agent ROLE=...`,
  `node-run-once ROLE=...`, and `node-doctor`. They must work on Apple Silicon.
- Add a dedicated runner-host Terraform module or an explicit extension of current Hetzner modules, a runner-only cloud-init, firewall egress policy, systemd/container unit, log rotation, and deploy/rollback doctor checks.
- Never co-reside untrusted execution with API/DB in production. Founder laptop
  is bootstrap/development-only and uses separate throwaway role credentials.

## Sandbox profile v0

- Rootless container, read-only base filesystem, tmpfs workspace, non-root UID, dropped capabilities, `no-new-privileges`, seccomp/AppArmor where available.
- No host network by default; network-enabled profile uses destination allowlist and DNS controls.
- CPU, memory, PID, file-size, disk, wall-time, and log-byte limits.
- Environment starts empty except allowlisted values. Secrets are short-lived job-scoped files/env values and are redacted from logs/receipts.
- Resource bundle and eval inputs are mounted read-only; only `/workspace/out` is writable/exported.
- Image is pinned by digest. No `latest`, privileged mode, host PID/IPC, host mounts, or Docker socket.

## Required adversarial fixtures/tests

- Read `/etc`, parent paths, host home, cloud metadata, coordinator token, and canary env.
- Fork bomb, disk fill, giant stdout, timeout ignoring SIGTERM, background child, symlink escape, archive traversal, DNS rebinding, and artifact digest mismatch.
- Lease loss during execution, duplicate runner claim, coordinator outage, upload interruption/resume, cancellation, and late receipt.
- Proving-ground happy fixture proves assertions/timeline/artifacts survive adapter integration.
- Infra tests assert separate service, firewall, no privileged/docker socket, limits, and secret file permissions.

## Rollout and operator runbook

1. Local fake coordinator + local backend.
2. Founder Mac Compose node against the locally running real API, with one
   isolated container per role and bounded hosted-model calls.
3. Staging runner with only repository-owned deterministic fixtures and zero secrets/network.
4. Staging container backend for indexed free skills allowlisted by digest.
5. Dedicated production runner with one-job concurrency and hard daily spend cap.
6. Raise concurrency only from measured CPU/memory/queue data.

Kill switches exist at global runner, operator, resource digest, sandbox profile, and job type levels. Rollback stops leasing; running containers are cancelled; receipts already issued remain verifiable.

## Build

- Define a runner contract: capabilities, supported resource types, sandbox profile, job lease, input digests, output artifacts, receipt, and terminal status.
- Deploy a dedicated low-cost runner separate from the API host; allow a local developer runner for debugging.
- Reuse proving-ground drivers, assertions, timelines, redaction, and durable artifacts.
- Create an ephemeral project scope per job; resolve exact resource versions and dependencies before execution.
- Deny ambient credentials and host filesystem access; inject scoped short-lived secrets only for explicitly approved jobs.
- Start with skills and deterministic fixtures. MCP execution and model evaluation remain disabled by default.
- Add `logion node doctor|run|jobs` for the operator path.
- Document how host Hermes dispatches prompts to each isolated role and how
  results return without sharing harness homes, credentials, or repository state.

## Cost rule

The coordinator never promises compute it does not own. Jobs declare requirements; runners bring compatible compute. GPU work waits for an external or explicitly funded runner.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add
`builtin:phase_15_15_isolated_runner`.

- **Actors/seed:** host Hermes `node_operator`, plus real isolated `consumer`,
  `evaluator`, `contributor`, `sponsor`, and `auditor` containers; the runner is
  the real first-party process, not only an LLM persona. Seed one deterministic job plus
  filesystem escape, undeclared network, secret-read, oversized-output, and
  timeout fixtures.
- **Customer prompt:** “Use my enrolled Logion node to execute the portable
  checker for this resource. Show and verify the receipt. Then try the untrusted
  fixture under the same published policy and explain why it was contained.”
- **Assertions to implement:** `api.runner_enrolled`,
  `api.runner_job_completed`, `api.runner_receipt_published`,
  `crypto.runner_receipt_valid`, `sandbox.canary_not_exfiltrated`,
  `sandbox.forbidden_effect_blocked`, and
  `api.runner_job_terminal_once`.
- **Boundary/evidence:** adversarial jobs produce typed terminal outcomes and
  never receive catalog, funding, or Logion issuer authority. Retain runner
  identity/version, sandbox profile, input/output digests, receipt/signature,
  resource/cost measurements, canary checks, redaction, and no-500 proof.

## Acceptance gates

- A fresh runner completes a signed fixture job from claim through artifact upload.
- Cancellation, timeout, lease loss, retry, and duplicate submission are safe.
- A malicious fixture cannot read host secrets or mutate the API service.
- Runner receipts bind resource, environment, inputs, outputs, and assertion results.
- Public runner package can be installed and complete the conformance fixture without access to either repository's source tree.
- On an Apple Silicon Mac, the documented Compose stack starts all five roles,
  isolates homes/credentials/repository scopes, and completes one signed CPU
  job without a local GPU.
- The production deploy check proves the API host and runner host are different machines/security domains.
- p95 coordinator poll/heartbeat endpoints remain within the API benchmark budget at one runner and synthetic 100-runner load.
