# Logion

Open-source developer tooling for the Logion marketplace.

This repository contains the public SDK, CLI, and API contract used to build
against Logion.

## What is here

- `packages/client` — Python SDK for the Logion API
- `packages/cli` — command-line interface for operators, agents, and integrators
- `packages/landing` — public landing package scaffold
- `contracts/openapi/v1.json` — public OpenAPI contract for the current v1 API

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

## Package overview

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

The SDK combines handwritten resource classes with generated request/response
models and generated low-level operations derived from the OpenAPI contract.

### `packages/cli`

The CLI is built on top of the SDK and exposes the operational surface of the
current public API.

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

This package is currently a landing scaffold.

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
  --password secret123 \
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

This repo ships the public OpenAPI contract and a Prism-based mock workflow so
contributors can work on the SDK and CLI without depending on a live backend.

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
at the contract or export layer, not patched around in the mock.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for contributor setup, mock-server
usage, and pull request workflow details.
