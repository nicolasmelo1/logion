# Logion

**Open-source developer tooling for the Logion marketplace.**

Logion provides an SDK, CLI, and companion bundle so developers can integrate
with the Logion platform — search listings, manage courses, handle payments,
and more — without building against raw HTTP endpoints.

## Install

```bash
# pipx
pipx install logion-cli
```

<!-- NOTE: `logion.dev` is not yet owned. The installer URL below is a
     placeholder; update it (and the matching addresses in SECURITY.md and
     CODE_OF_CONDUCT.md) once the domain is registered. -->
> **Coming soon:** `curl | sh` installer (`https://logion.dev/install.sh`) and
> `npx logion` wrapper — these endpoints are placeholders and will be
> available once the publishing pipeline is live.

## Quick verification

```bash
logion --version
logion --help
logion listings search "video cuts"
```

## What's in the box

- **SDK** (`packages/client`) — Python SDK for the Logion API
- **CLI** (`packages/cli`) — command-line interface for operators, agents,
  and integrators
- **Companion bundle** ([`packages/agent-companion`](packages/agent-companion/README.md)) —
  AI-agent companion toolkit

## Status badges

![PyPI version](https://img.shields.io/pypi/v/logion-client.svg)
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