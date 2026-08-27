<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.14.1 — Local multi-agent first-node foundation

> **Dogfood status:** this supplies the local role-isolation substrate used by
> Phase 15.15 and later by Phase 15.16.
> **Honesty boundary:** isolated roles on one MacBook are not independent
> operators, and this phase does not yet prove runner execution or an
> improvement loop.

## Goal

On the founder's existing MacBook, let host Hermes start and coordinate at
least two real agent containers with separate homes, credentials, repository
scopes, and runtime limits.

This phase prepares a node. It does not operate the complete node: job leasing,
sandbox execution, and signed runner receipts begin in 15.15; feedback-driven
bounty selection and the recurring improvement loop remain in 15.14 and 15.16.

## Exact phase boundary

### Required here

- one versioned, non-root role image;
- one Compose stack with `consumer` and `auditor` role profiles;
- separate role homes, Logion/harness state, repository workspaces,
  observation spools, and API credentials;
- explicit CPU, memory, PID, and wall-time limits;
- no host home, keychain, SSH agent, browser profile, cloud credentials, or
  Docker/Podman socket inside a role;
- start, status, role-agent, stop, and explicit per-role reset commands;
- one repository-scoped install visible in a fresh session of the same role but
  absent from another repository, user scope, and the other role;
- restart persistence and selective reset/revocation.

### Deferred to named phases

- runner enrollment, offers, leases, job state, disposable execution
  sandboxes, artifact upload, execution receipts, and receipt signing: **15.15**;
- evaluator contracts and normalized results: **16.1–16.2**;
- sponsor funding, contributor delivery/acceptance, feedback clustering,
  bounty recommendation, rerun, and complete improvement lineage:
  **15.14/15.16**;
- remote machines and independently operated roles: **16.3+**.

Do not add placeholder production implementations for deferred behavior. The
15.14.1 scenario ends after isolation, repository scope, restart, and reset are
proven.

## Process model

```text
macOS host
├── existing Hermes operator (never mounted into a role)
├── local Logion API/devrig
├── role-consumer container
└── role-auditor container
```

The two roles are actual Compose services, not labels or subprocesses sharing
one home. The Compose/image pattern must be reusable by the evaluator,
contributor, and sponsor profiles added by later phases, but those profiles are
not required to close 15.14.1.

“Role” is an operator-side container profile in this phase, not a new Logion
authorization model. Each role authenticates as a distinct seeded agent using
the existing public API authorization rules. Do not add generic RBAC, runner
credentials, admin impersonation, or bounty-specific permissions here.

## Isolation contract

Each role receives:

- its own container and non-root UID;
- its own `$HOME`, `LOGION_HOME`, harness config, memory/session store, skill
  inventory, credential file, observation spool, and repository workspace;
- a distinct disposable agent API key injected only into that role;
- a read-only repository checkout or dedicated worktree plus its own writable
  task directory;
- enforced CPU, memory, PID, and wall-time limits;
- no volume, secret, or ambient credential belonging to another role or host.

The same role keeps its intended named-volume state across normal stop/start.
Reset targets exactly one role: it deletes that role's disposable state and
revokes its credential without changing the other role.

Repository skills stay inside the checkout (`.agents/skills`,
`.claude/skills`, `.pi/skills` as appropriate). User-scope skills, if any, stay
inside that role's home volume and never appear in another role.

## Image and Compose deliverables

Build one pinned `linux/arm64` base image containing only what the role smoke
needs:

- the Logion public CLI and companion;
- Git and one gate-approved real-agent harness;
- certificate/runtime dependencies;
- a non-root entrypoint;
- no baked-in provider, Logion, GitHub, cloud, or host credentials.

Do not install the Phase 15.15 runner package or give a role access to the host
container socket. Runtime secrets enter through Compose secrets or an explicit
short-lived environment file outside the image layers.

Required files:

- `deploy/local-node/compose.yaml`;
- `deploy/local-node/roles/consumer.env.example`;
- `deploy/local-node/roles/auditor.env.example`;
- `docs/node/local-macos.md`.

The documentation covers Docker Desktop and Podman, Apple Silicon, the exact
commands, mounts and limits, provider-secret injection, troubleshooting,
credential lifetime, and selective cleanup.

## Operator surface

From the canonical workspace:

```bash
make node-dev-up ROLES=consumer,auditor
make node-agent ROLE=consumer
make node-agent ROLE=auditor
make node-status
make node-dev-down
make node-dev-reset ROLE=consumer YES=1
```

`node-dev-up` validates the local container runtime, disk, ports, API health,
and the one requested provider credential; builds or pulls the pinned image;
creates distinct homes and agent keys; starts the local devrig and requested
roles; and prints role IDs, limits, sanitized mounts, credential status, and
cleanup commands.

`node-agent` opens or submits a prompt only to the named role. It never copies
the operator conversation, host memory, host skills, or another role's state.

`node-dev-down` preserves named role state. `node-dev-reset` requires both an
exact role and `YES=1`; it removes only that role's disposable volume and
revokes only that role's API key.

## Bounded foundation smoke

The closing run is exactly:

1. Host Hermes starts the local devrig plus `consumer` and `auditor` services.
2. Both services prove their non-root UID, runtime limits, distinct state
   directories, and distinct authenticated agent identities.
3. Consumer installs one harmless checked-in skill fixture into repository
   `XPTO` using the public CLI.
4. A fresh consumer session sees the fixture in `XPTO`, but not in repository
   `ABC` or consumer user scope; auditor cannot see it or read consumer
   canaries, credentials, home, spool, or workspace.
5. Neither role can read host-home/keychain/socket canaries.
6. Normal stop/start preserves only each role's own intended named-volume state.
7. Resetting consumer removes its disposable state and revokes its old key;
   auditor state and credential remain valid.

No bounty is drafted or funded. No contributor delivers anything. No evaluator
claims a job. No execution or attestation receipt is created.

## What this phase proves

- two real agent processes can use Logion without sharing homes or credentials;
- repository and user installation scopes remain distinct inside a container;
- host and cross-role canaries are unreadable;
- resource limits are active;
- normal restart and explicit selective reset have different, predictable
  effects.

It does not prove runner isolation, execution safety, signed evidence,
independent operation, issuer diversity, resistance to founder collusion,
external demand, funding, delivery, or improvement lineage.

## Required tests

- Compose/config test for non-root users, read-only base filesystems, dropped
  capabilities, no privileged mode/socket/host-home mounts, separate volumes,
  separate secrets, and declared limits;
- adversarial canary test for host and cross-role homes, credentials, spools,
  and workspaces;
- repository-scope test using `XPTO` and `ABC` plus a fresh session;
- restart test proving state persists only in the intended role volume;
- selective-reset test proving one role's state and key are removed while the
  other role remains usable.

Scripted configuration tests support diagnosis but do not replace the retained
real-agent scenario below.

## Acceptance gates

### Mandatory real-agent scenario

Add `builtin:phase_15_14_1_local_multi_agent_node` and pass it with GPT-5.4-mini
or Claude Haiku against the locally running real API.

- **Prompt to host Hermes:** “Start the bounded 15.14.1 foundation smoke with
  consumer and auditor as separate Compose services. Prove non-root execution,
  limits, credential/home isolation, repository-only install, restart
  persistence, and selective consumer reset. Stop before runner jobs, receipts,
  bounties, funding, or delivery.”
- Actors are the actual `consumer` and `auditor` services. One allowed cheap
  harness/model configuration is sufficient.
- Negative cases prove cross-volume and host canaries unreadable, the fixture
  absent from `ABC`, user scope, and auditor, and the reset consumer credential
  rejected while auditor remains usable.
- Retain image/Compose digests, versions, sanitized mounts and limits, prompts,
  role agent IDs, credential fingerprints/status (never secrets), scope checks,
  canary results, restart/reset results, and no-500 proof.

The canonical policy requires exactly these assertions:
`sandbox.roles_run_non_root`, `sandbox.real_harness_uses_logion`,
`sandbox.role_resource_limits_enforced`,
`files.install_scoped_to_repository`,
`sandbox.cross_volume_canary_unreadable`,
`api.role_credentials_isolated`, `api.state_survives_restart`,
`files.role_cleanup_complete`, and `logs.no_500s`.

- [ ] The documented command starts the local API/devrig plus consumer and
      auditor as actual non-root Compose services.
      (proof: assertion:sandbox.roles_run_non_root)
- [ ] Both role services run a gate-approved real-agent harness inside their
      containers, and each harness process invokes the installed Logion CLI.
      Host-side drivers coordinate but do not count as either role process.
      (proof: assertion:sandbox.real_harness_uses_logion)
- [ ] Both role services run with the declared CPU, memory, PID, and wall-time
      limits.
      (proof: assertion:sandbox.role_resource_limits_enforced)
- [ ] Host Hermes can coordinate without mounting host or cross-role homes,
      credentials, spools, workspaces, keychain, or container socket.
      (proof: assertion:sandbox.cross_volume_canary_unreadable)
- [ ] Consumer and auditor receive distinct credentials; selective reset
      revokes consumer's old credential without invalidating auditor.
      (proof: assertion:api.role_credentials_isolated)
- [ ] A fresh consumer session sees the fixture in repository `XPTO`, but not
      in repository `ABC`, consumer user scope, or auditor scope.
      (proof: assertion:files.install_scoped_to_repository)
- [ ] Normal stop/start preserves each role's intended state without making it
      visible to the other role.
      (proof: assertion:api.state_survives_restart)
- [ ] Explicit consumer reset removes only consumer disposable state while
      auditor remains usable.
      (proof: assertion:files.role_cleanup_complete)

## Implementation stop rule

Once every criterion and the canonical scenario above pass, stop. Changes to
runner/coordinator domains, execution receipts, eval contracts, improvements,
bounties, ledger funding, contribution delivery, or remote-node deployment are
out of scope even if they appear next in the roadmap.
