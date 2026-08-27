# Local node on macOS

This operator surface runs the bounded `consumer` and `auditor` roles as
separate Linux/arm64 Compose services on Apple Silicon. It proves local role
isolation; it does not prove independent operators or runner isolation.

## Prerequisites

- Docker Desktop **or** Podman machine with a Compose provider;
- at least 5 GiB free disk;
- `uv`, Node.js, and Codex authenticated on the host;
- the canonical maintainer workspace, which exposes the node targets and passes
  its root to the public operator script.

The role image pins the real Codex CLI. At bring-up, `node-dev-up` validates the
runtime, free disk, port/API health, and the requested Codex authentication. If
the local API is not healthy it provisions the canonical devrig and starts the
API, then waits for `/health`.

## Configuration

```bash
cp "$PUBLIC_REPO/deploy/local-node/roles/consumer.env.example" \
  "$PUBLIC_REPO/deploy/local-node/.env"
```

Run these commands from the canonical maintainer workspace.

Use Docker (default):

```bash
CONTAINER_RUNTIME=docker make node-dev-up ROLES=consumer,auditor
```

Use Podman:

```bash
podman machine start
CONTAINER_RUNTIME=podman make node-dev-up ROLES=consumer,auditor
```

`node-dev-up` creates distinct disposable Logion identities and API keys when
absent. It copies the selected Codex `auth.json` into separate role-scoped
Compose secret files. Neither the host auth path nor any host home is mounted.
Secret files, role identity files, and build wheels are ignored by Git.

## Driving roles

```bash
make node-agent ROLE=consumer             # interactive Codex inside consumer
make node-agent ROLE=consumer ARGS='id'   # bounded one-shot command
make node-agent ROLE=auditor ARGS='logion --version'
make node-status
```

The role image contains Git, Logion CLI/companion, and a pinned real Codex
harness. `codex-role` copies only that role's provider secret to tmpfs for the
process lifetime. The retained closing scenario starts Codex in **both** role
containers and requires each process to create evidence from `logion --version`.
Host Codex coordinates the scenario but is not counted as either role process.

## Isolation and limits

Each role has a distinct non-root UID, named home, Logion spool, workspace,
Logion API secret, and Codex auth secret. The root filesystem is read-only;
capabilities are dropped and privilege escalation is disabled. No host home,
Keychain, SSH agent, browser/cloud credential, peer secret, or container socket
is mounted.

Per role, Compose enforces:

- CPU: 1 core;
- memory: 1536 MiB;
- PIDs: 256;
- wall time: 3600 seconds by default (`ROLE_WALL_TIME_SECONDS`).

Wall time is not documentation-only: PID 1 is wrapped by GNU `timeout`, and the
gate reads the live container command plus configured deadline.

The adversarial canary phase seeds unique values at each role's **actual** home,
spool, and workspace, then probes the peer value at those same mount targets. It
also probes the peer's real Compose secret path, the Docker socket, `/Users`, and
macOS Keychain paths. The assertion fails if any required probe is absent.

## Stop, restart, and reset

```bash
make node-dev-down
make node-dev-up ROLES=consumer,auditor
make node-dev-reset ROLE=consumer YES=1
```

Normal down/up preserves named volumes. The restart hook itself executes both
commands between marker snapshots, records old/new container IDs, and fails on
missing or unreachable markers.

Selective reset requires an exact role and `YES=1`. It stops/removes only that
service, rotates the role's API key **server-side**, retains the old key only as
a local revoked test artifact, writes the new key for the next start, and removes
only that role's home/workspace/spool volumes. The smoke proves the old key is
rejected, the new key works, and the auditor remains running and authenticated.

## Evidence retained by the gate

The sealed report contains image/container IDs, Compose and Dockerfile SHA-256,
CLI/Git/Codex versions, sanitized runtime mounts, CPU/memory/PID/wall-time
limits, exact scenario prompts, role agent IDs, non-secret credential
fingerprints and status, all canary results, marker values and digests,
mechanical restart IDs/status, reset/revocation facts, and the no-500 assertion.
It does not point to `/tmp` as its only evidence source.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Runtime unavailable | Start Docker Desktop or `podman machine start`. |
| Port 8000 occupied but unhealthy | Stop the conflicting listener, then rerun. |
| Codex auth missing | Run `codex login` or set `CODEX_AUTH_SOURCE`. |
| A role exits near one hour | Increase `ROLE_WALL_TIME_SECONDS` explicitly and restart. |
| Podman cannot reach the host API | Set `LOGION_BASE_URL` to a host address reachable from the Podman machine. |
| Reset refuses | Pass an exact role plus `YES=1`; the guard is intentional. |
