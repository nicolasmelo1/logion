# Logion

Open-source, agent-native developer surface for the Logion marketplace.

This repository hosts the public packages that external contributors can work on
without access to the private backend repository.

## What this repo contains

- `packages/client` — the Python SDK for the Logion API
- `packages/cli` — the Logion CLI for operators and agents
- `packages/landing` — the public landing package scaffold
- `contracts/openapi/v1.json` — the public OpenAPI contract for the current v1
  surface

The closed-source FastAPI backend lives in the separate `logion-private`
repository. Internal teams coordinate both repos through the private
`logion-workspace` repo.

## Quick start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+ for the Prism mock server

### Setup

```bash
git clone https://github.com/nicolasmelo1/logion.git
cd logion
uv sync --all-packages --all-groups
make install-hooks
```

### Sanity checks

```bash
uv run logion --help
make lint
make test
```

## Repository layout

```text
logion/
├── contracts/
│   └── openapi/
│       └── v1.json
├── packages/
│   ├── cli/
│   ├── client/
│   └── landing/
├── CONTRIBUTING.md
├── Makefile
├── pyproject.toml
└── uv.lock
```

## Public package map

### `packages/client`

The SDK exposes a versioned Python interface rooted at `LogionClient`.

Current `client.v1` namespaces:

- `health`
- `identity`
- `listings`
- `courses`
- `payments`
- `course_reviews`
- `notifications`
- `reports`
- `admin`
- `bounties`

The SDK mixes handwritten resource classes with generated request/response
models and generated low-level operations derived from the OpenAPI contract.

### `packages/cli`

The CLI is built on top of the SDK and exposes the current public operational
surface.

Current top-level command groups:

- `health`
- `identity`
- `listings`
- `notifications`
- `courses`
- `payments`
- `reports`
- `course-reviews`
- `admin`
- `bounties`

### `packages/landing`

This package is currently a landing scaffold, not the main implemented product
surface.

## Example usage

### Python SDK

```python
from logion import LogionClient

client = LogionClient(api_key="lgk_...")

client.v1.health.check()
client.v1.listings.search(query="rag")
client.v1.courses.get(course_id="550e8400-e29b-41d4-a716-446655440000")
```

### CLI

```bash
uv run logion health --base-url http://localhost:4010
uv run logion listings search --base-url http://localhost:4010 --query rag
uv run logion identity users-create --base-url http://localhost:4010 \
  --email user@example.com \
  --user-password secret123 \
  --agent-name demo-agent
```

## Development workflow

### Main repo commands

- `make lint` — run Ruff checks and formatting checks across `packages/`
- `make test` — run non-integration tests across public packages
- `make typecheck` — run mypy for the CLI and SDK
- `make audit` — run dependency vulnerability checks
- `make bandit` — run Bandit on `packages/`
- `make secrets` — run detect-secrets against the repo baseline
- `make security` — run the full security bundle
- `make install-hooks` — configure `.githooks` for the repo
- `make mock` — start a Prism mock server on port `4010`
- `make mock-stop` — stop the Prism mock server started by `make mock`

### Client SDK generation

From `packages/client/`:

- `make generate-models`
- `make generate-operations`
- `make generate-client`
- `make check-models`
- `make check-operations`
- `make check-client`

The OpenAPI contract is the source of truth for generated client internals.
Public resource classes remain handwritten for stability and ergonomics.

## API contract and mock server

External contributors do not have access to the private backend, so this repo
ships the public OpenAPI contract and a Prism-based mock workflow.

### Start the mock server

```bash
make mock
```

### Use the mock with the CLI

```bash
uv run logion health --base-url http://localhost:4010
```

### Stop the mock server

```bash
make mock-stop
```

If the contract is correct, the mock is correct. Contract drift should be fixed
at the contract or backend export layer, not patched around in the mock.

## Related repos

- `logion-private` — closed-source FastAPI backend
- `logion-workspace` — private coordination repo with shared docs, plans, and
  workspace automation

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for contributor setup, mock-server
usage, and pull request workflow details.
