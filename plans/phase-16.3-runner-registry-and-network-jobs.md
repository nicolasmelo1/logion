<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 16.3 — Runner registry and network jobs

> **Dogfood status:** the Logion node advertises only capabilities its runner actually proves through conformance jobs.
> **After this phase:** external runners can bring CPU/GPU/API-backed compute and claim compatible work.
> **Honesty boundary:** registration is not endorsement; capabilities are claims until probed.

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

Open job execution without turning Logion into a GPU infrastructure company.

## Dogfood prompt for the implementing agent

```text
Find and use a resource about distributed workers, leases, idempotent jobs, or queue
reliability. Recall first, then search the store for "distributed worker job lease
idempotency" on LOW/NONE. Follow the mandatory acquisition/reconciliation protocol and
use it to review the job state machine and race tests. Record it in
`artifacts/dogfood/phase-16.3.md`; submit feedback after the lease-expiry and
duplicate-completion tests pass. Do not report an unused result.
```

## Enrollment and authentication

- Runner operator starts enrollment as an authenticated user/admin and receives a one-time, short-lived challenge.
- Runner generates Ed25519 key locally, signs challenge, and submits public key plus descriptor. Private key never reaches Logion.
- Coordinator issues runner ID and scoped credential/certificate limited to runner endpoints. Store only hashes where bearer credentials exist.
- Capability claims include CPU architecture/count, RAM/disk, GPU vendor/model/VRAM, container backend, network profiles, evaluator descriptor digests, max concurrency, regions, and pricing hints.
- Conformance results mark each capability `claimed|probed|suspended`; scheduler uses only `probed`.

## API endpoints/services

Under `api/runners/` and `api/executions/` implement: enrollment start/complete, descriptor update, conformance offer/result, job poll/claim, heartbeat, receipt submit, runner revoke, operator list/detail. Add per-runner rate limits and audit events.

Lease transaction must use row locking/compare-and-set. Claim input contains job ID, attempt, expected version, and runner ID. Receipt submission has an idempotency key `(job_id, attempt, runner_id, receipt_digest)`. A different digest for the same terminal attempt is a conflict requiring operator review.

## Scheduler

- Pure matching function consumes job requirements and probed runner descriptors; cover it with table-driven tests.
- Match hard constraints first; optional cost/latency preferences only among valid runners.
- No runner available leaves `queued_no_capacity` with an observable reason. It never falls back to coordinator execution.
- GPU/model/API costs require a sponsor-provided max amount before offer.
- Same operator independence group is carried forward for Phase 16.4.

## Runner/client changes

- Extend the 15.15 runner with enrollment/key store, long polling with jitter/backoff, descriptor probes, multiple execution slots, drain mode, and upgrade protocol.
- Persist active leases locally so restart can heartbeat/resume or explicitly abandon.
- CLI operator commands: `node enroll`, `status`, `capabilities`, `drain`, `jobs`, `revoke`.

## Database/migration

Tables/columns: runner operators, runners, runner keys, capability snapshots, conformance runs, external job attempts, leases, and pricing snapshots. Historical descriptors/keys are immutable. Index open jobs by state/requirements summary and leases by expiry.

## Race/security tests

- Two runners claim same job, same runner retries claim, lease expires during heartbeat, terminal receipt races cancellation, stale attempt submits, conflicting digest, coordinator restart.
- Forged runner ID/key, revoked key, replayed challenge, capability downgrade, price changed after offer, artifact grant reuse.
- Synthetic 100 runners/10k queued jobs benchmark with bounded DB queries and no full-table scan.

## Rollout

Logion runner enrolls through the public path first. Then allowlisted independent staging operator; then public CPU enrollment with manual approval. GPU capability remains disabled until a real provider passes probes and sponsor caps are live.

## Build

- Runner identity, operator, endpoint, capability claims, sandbox profiles, pricing hints, and status.
- Signed challenge enrollment and periodic conformance probes.
- Leased job claim/heartbeat/complete protocol with idempotency and replay protection.
- Capability-aware matching; coordinator never schedules an incompatible job.
- Scoped artifact upload and receipt submission.
- Quotas, allowlists, kill switch, and per-sponsor spend ceilings.

## Mandatory proving-ground scenario

Use [the common gate](agent-proving-ground-phase-gate.md) and add
`builtin:phase_16_3_network_runner_job`.

- **Actors/prompt:** an independent runner operator follows only public
  onboarding: “Enroll this CPU runner, advertise its actual capabilities,
  claim one compatible job, complete it, and recover safely if the lease is
  deliberately interrupted.” A submitter offers the job through public CLI/API.
- **Assertions to add:** `api.runner_capabilities_registered`,
  `api.job_leased_to_eligible_runner`, `api.lease_recovered_once`,
  `api.network_job_receipt_exists`, `api.job_terminal_once`, and
  `security.runner_credentials_least_privilege`.
- **Negative/evidence:** an incompatible/GPU job is never leased and a stale
  worker cannot complete after lease loss. Retain enrollment/job/lease IDs,
  capability and receipt digests, timing/cost, redaction, and no 500s.

## Gates

- A clean external runner completes a public CPU fixture.
- Lease expiry and duplicate completion cannot double-pay or duplicate authority.
- GPU jobs remain unscheduled when no compatible runner exists.
- Operators can revoke a runner without invalidating historical receipts.
- No database, object-store master, GitHub, Stripe, or Logion agent credential is present on an external runner.
- Pricing shown at offer time is snapshotted and cannot be increased by the completion response.
