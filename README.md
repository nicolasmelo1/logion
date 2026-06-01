# Logion

**Open-source developer tooling for the Logion marketplace.**

Logion provides an SDK, CLI, and companion bundle so developers can integrate
with the Logion platform — search listings, manage courses, handle payments,
and more — without building against raw HTTP endpoints.

## Install

```bash
# curl | sh (recommended)
curl -fsSL https://logion.dev/install.sh | sh
```

```bash
# pipx
pipx install logion-cli
```

```bash
# npx (no install required)
npx logion --help
```

## Quick verification

```bash
logion --version
logion --help
logion listings search "video cuts"
```

## What's in the box

- **SDK** ([`packages/client`](packages/client/README.md)) — Python SDK for
  the Logion API
- **CLI** ([`packages/cli`](packages/cli/README.md)) — command-line interface
  for operators, agents, and integrators
- **Companion bundle** ([`packages/agent-companion`](packages/agent-companion/README.md)) —
  AI-agent companion toolkit

## Status badges

![PyPI version](https://img.shields.io/pypi/v/logion-client.svg)
![npm version](https://img.shields.io/npm/v/logion-client.svg)
![License](https://img.shields.io/github/license/nicolasmelo1/logion.svg)
![Tests](https://img.shields.io/github/actions/workflow/status/nicolasmelo1/logion/pr-safety.yml.svg?branch=main)

## Documentation

- [OpenAPI contract & mock server](docs/openapi-sync.md) — how the API
  contract is synced and how to run a local mock
- [Agent companion](packages/agent-companion/README.md) — AI-agent toolkit
  guide

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, mock-server
usage, commit conventions, and the PR checklist.

## License

MIT — see [LICENSE](LICENSE).