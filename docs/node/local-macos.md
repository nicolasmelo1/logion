# Local node (macOS) — phase 15.14.1

How to run the bounded local multi-agent node on the founder's MacBook
(Apple Silicon). This page covers the exact commands, mounts, limits,
provider-secret injection, troubleshooting, credential lifetime, and
selective cleanup for the `consumer` and `auditor` role services.

> **Honesty boundary.** Two isolated roles on one MacBook are not
> independent operators. This phase proves isolation, repository
> scoping, restart persistence, and selective reset — nothing more.
> Runner execution, receipts, and the improvement loop live in later
> phases.

## Prerequisites

- Docker Desktop (or Podman) running, linux/arm64 capable
- The local devrig stack up: `make bootstrap`, `make dev-up`, and
  `make dev-api` from the workspace root
- `uv` for building the public CLI wheel

## One-time setup

```bash
# From the logion/ repository root:
cp deploy/local-node/roles/consumer.env.example deploy/local-node/.env
```

Provision one disposable agent API key per role against the local API
(seeded devrig agents) and write each key to its secret file:

```bash
printf '%s' "$CONSUMER_KEY" > deploy/local-node/roles/consumer.api_key
printf '%s' "$AUDITOR_KEY" > deploy/local-node/roles/auditor.api_key
chmod 600 deploy/local-node/roles/*.api_key
```

## Starting the node

```bash
make node-dev-up ROLES=consumer,auditor
```

`node-dev-up` validates the container runtime, builds the pinned
`linux/arm64` role image, installs the disposable API keys as Compose
secrets, starts the requested roles, and prints role IDs, limits,
sanitized mounts, credential status, and cleanup commands.

## Driving a role

```bash
make node-agent ROLE=consumer ARGS='id'            # proves non-root UID
make node-agent ROLE=auditor ARGS='id'
make node-status
```

`node-agent` submits a command only to the named role. It never copies
the operator conversation, host memory, host skills, or another role's
state into the container.

## What isolation means here

Each role gets:

- its own container and non-root UID (consumer `10001`, auditor `10002`);
- its own `$HOME`, `LOGION_HOME`, observation spool, credential file,
  and repository workspace, each on a dedicated named volume;
- its own Compose secret (`/run/secrets/<role>_api_key`) — never an
  image layer, never a shared env var;
- enforced CPU, memory, and PID limits from `compose.yaml`;
- a read-only root filesystem with `/tmp` as the only writable tmpfs.

No role receives the host home, keychain, SSH agent, browser profile,
cloud credentials, or the Docker socket. Skills installed by a role
stay inside that role's volumes; a repository-scoped install is visible
to a fresh session of the same role in that repository and absent
everywhere else.

## Stop, restart, reset

```bash
make node-dev-down                      # preserves named role state
make node-dev-up ROLES=consumer,auditor # restart: state persists
make node-dev-reset ROLE=consumer YES=1 # selective reset
```

Normal stop/start preserves each role's own named-volume state.
`node-dev-reset` requires both an exact role name and `YES=1`; it
removes only that role's disposable volumes and retires its local key
copy (revoke the matching key on the devrig API to finish the
revocation). The other role's state and credential remain valid.

## Credential lifetime

Role API keys are disposable. Treat them as short-lived: reset revokes
the key and the smoke run asserts a revoked key is rejected while the
other role's key still authenticates. Keys never leave the Compose
secret mount at rest.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ERROR: no working container runtime` | Start Docker Desktop; on Podman, start the machine. |
| `roles/consumer.api_key is missing` | Write the role key files shown under one-time setup. |
| `id -u` returns `0` | The role must never run as root — check `user:` in `compose.yaml`. |
| Role cannot reach `http://localhost:8000` | Confirm `make dev-api` is running and `LOGION_BASE_URL` matches. |
| Reset says `refusing ... without YES=1` | That is the guard. Pass `YES=1` and the exact role. |

## Provider secrets

Provider credentials (model APIs the harness might need) are injected
per run as Compose secrets or a short-lived env file outside the image
layers. The pinned image contains none, and no role can read another
role's or the host's.