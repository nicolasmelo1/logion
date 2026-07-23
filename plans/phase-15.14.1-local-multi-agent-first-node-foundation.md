<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.14.1 — Local multi-agent first-node foundation

> **Dogfood status:** this is the founder-operated supply for Phase 15.15–15.16.
> **Honesty boundary:** several isolated agents on one MacBook are several roles
> and failure domains, not independent network operators.

## Goal

Use the founder's existing MacBook and Hermes coding agent to operate the first
complete Logion node with additional isolated agents performing distinct roles:

- consumer/user;
- catalog operator;
- evaluator/runner;
- sponsor;
- contributor;
- auditor/adversary.

No additional physical server is required for the development loop.

## Process model

The existing host Hermes remains the founder/operator console. Other roles run
as containers with separate writable homes:

```text
macOS host
├── existing Hermes operator
├── local Logion API/devrig
├── role-consumer container
├── role-evaluator container
├── role-contributor container
├── role-sponsor container
└── disposable sandbox containers created by the runner
```

Role containers may use Hermes profiles, Codex, Claude Code, Pi, or another
proving-ground driver. Harness choice and network role are orthogonal.

## Isolation requirements

Every role receives:

- a separate container and non-root UID;
- a separate `$HOME`, `LOGION_HOME`, harness config, memory, session store,
  skill inventory, credentials, and observation spool;
- only its role-scoped API key;
- a dedicated checkout/worktree or read-only repository plus writable task
  workspace;
- explicit CPU, memory, PID, disk, wall-time, and model/API budget;
- no host Docker socket, SSH agent, cloud credentials, browser profile, or host
  home mount;
- no access to another role's volume.

The repository under test may be mounted or cloned into a role container. Repo
skills live inside that checkout (`.agents/skills`, `.claude/skills`,
`.pi/skills` as appropriate); user skills live only in that role's home volume.

## Container images

Build one versioned base image containing:

- Logion public CLI, companion, and proving-ground runner;
- Git and the selected harness binaries;
- certificate/runtime dependencies;
- a non-root entrypoint;
- no provider or Logion credentials.

Create thin role profiles through Compose, not bespoke images. Secrets enter at
runtime through Docker secrets or short-lived environment files and are never
baked into layers.

Use `linux/arm64` on Apple Silicon. A role may call a hosted cheap model even
though the harness process is local. Running local model weights is optional,
not required to close the network loop.

## Proposed operator surface

From the canonical workspace:

```bash
make node-dev-up
make node-agent ROLE=consumer HARNESS=hermes
make node-agent ROLE=evaluator HARNESS=codex
make node-agent ROLE=contributor HARNESS=claude-code
make node-dogfood PROGRAM=resource-improvement-v1
make node-status
make node-dev-down
```

`node-dev-up`:

1. validates Docker/Podman, disk, ports, API health, and provider credentials;
2. builds/pulls the pinned role image;
3. creates per-role volumes and throwaway role API keys;
4. starts API dependencies and idle role containers;
5. installs the Logion companion/integration in each requested harness;
6. prints costs, mounts, scopes, credentials expiry, and cleanup command.

`node-agent` opens or submits a prompt to one named role. It does not silently
share the operator conversation, memories, or skills.

`node-dev-down` stops containers. A separate explicit
`node-dev-reset --role ROLE --yes` removes a role's disposable volumes; normal
shutdown preserves them for cross-session testing.

## Founder-operated closed loop

The minimum recurring program is:

1. consumer searches Logion from a fixture or real repository;
2. consumer installs into that repository's native scope;
3. a fresh consumer session discovers and uses it;
4. harness integration writes an attributed local observation;
5. consumer explicitly submits minimum-disclosure feedback;
6. operator sees a qualified problem and drafts a bounty;
7. sponsor explicitly funds it;
8. contributor discovers work and submits a new immutable version;
9. evaluator runs the same bounded case and signs a receipt;
10. operator records disposition; consumer later reruns and submits outcome;
11. auditor verifies lineage and attempts replay, scope confusion, data leak,
    self-dealing, and cross-role access.

All steps use public CLI/API/harness artifacts. Direct database writes and
sharing role credentials invalidate the run.

## What multiple local agents prove

They prove:

- product usability by distinct personas;
- credential and state isolation;
- repository versus user scope behavior;
- real multi-session observation;
- coordinator/runner/job mechanics;
- bounded costs and reproducible failures;
- the full improvement lineage.

They do not prove:

- independent operators;
- issuer diversity;
- resistance to founder collusion;
- external demand or liquidity;
- cross-machine sandbox boundaries.

Public evidence must label issuer/operator as Logion first-party.

## Promotion to an always-on node

After the local loop is stable, move the runner role to one inexpensive CPU
server separate from the API/DB. Keep the Mac operator and remaining roles if
useful. Specialized GPU jobs wait for participant-supplied or sponsor-funded
capacity.

## Required documentation and tests

- `docs/node/local-macos.md`: Docker Desktop and Podman paths, Apple Silicon,
  provider credentials, budgets, commands, troubleshooting, and cleanup.
- `deploy/local-node/compose.yaml`: role services, read-only mounts, networks,
  volumes, limits, health checks, and profiles.
- `deploy/local-node/roles/*.env.example`: non-secret role configuration.
- adversarial test proving no role can read another home or the host keychain;
- proving-ground scenario with at least consumer, contributor, evaluator, and
  sponsor containers;
- restart test proving state persists only in the intended role volume;
- cleanup test proving disposable credentials/volumes are removed.

## Acceptance gates

### Mandatory real-agent scenario

Add `builtin:phase_15_14_1_local_multi_agent_node` and pass it with GPT-5.4-mini
or Claude Haiku against the locally running real API.

- Prompt to host Hermes: “Start the bounded local Logion program. Delegate use
  to consumer, delivery to contributor, verification to evaluator, approval to
  sponsor, and lineage review to auditor. Keep homes, credentials, repository
  scopes, memories, and spools isolated.”
- Actors are the actual Compose services, not role labels in one process. Use
  at least two cheap harness/model configurations.
- Assert non-root containers, API role authorization, repo-only install,
  unreadable cross-volume canaries, bounded spend, signed receipt, first-party
  issuer label, restart persistence, and explicit cleanup.
- Negative cases prove consumer cannot fund, contributor cannot accept its own
  work, auditor cannot read another spool, and no role can access the host
  Docker socket/keychain/home.
- Retain image/Compose digests, versions, sanitized mounts, prompts, API IDs,
  receipt, costs, canary results, and no-500 proof. Scripted Compose tests do
  not close the phase.

- A clean Apple Silicon Mac can start one API/devrig and four role containers
  using a documented command.
- The existing host Hermes can coordinate without its home or credentials being
  mounted into role containers.
- Consumer installs a skill in repository XPTO and a fresh session sees it
  there but not in unrelated repository ABC or the role's user scope.
- Each role submits only actions permitted by its API key.
- The full founder-operated loop completes end to end with bounded spend and a
  first-party label.
- Replacing one local role with a remote independently operated runner requires
  no protocol or coordinator rewrite.
