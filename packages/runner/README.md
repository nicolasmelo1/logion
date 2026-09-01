# logion-runner

Reference isolated runner node for the Logion job system: a separately
deployable process that claims jobs from a coordinator, executes them
inside a sandbox (rootless-style Docker container or a local test
subprocess), uploads output artifacts, and publishes signed execution
receipts.

## Install

```bash
uv pip install logion-runner
```

## Commands

```bash
logion-node enroll --name my-runner --capability cpu --base-url http://127.0.0.1:8000
logion-node doctor
logion-node run --once
logion-node jobs
logion-node rotate-key
```

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `LOGION_NODE_BASE_URL` | `http://127.0.0.1:8000` | Coordinator base URL |
| `LOGION_NODE_STATE_DIR` | `~/.logion-node` | Credentials + run history |
| `LOGION_NODE_RUNNER_NAME` | *(unset)* | Default enrollment name |

Credentials live in `<state-dir>/runner.json` with mode `0600` and hold
the runner key plus the Ed25519 signing private key issued at
enrollment.

## Trust boundary

The runner holds no database credentials, no Docker socket, and no
long-lived API key beyond its own runner key. Jobs run in the sandbox
backend declared by the coordinator's lease; the default docker backend
implements sandbox profile v0 (pinned image digest, read-only root
filesystem, tmpfs workspace, dropped capabilities, non-root UID, no
network).