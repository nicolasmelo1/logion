# Logion Marketplace Companion

> First-party companion package for discovering, acquiring, installing,
> updating, creating, and managing Logion courses and capabilities.

## Overview

This package provides a small bootstrap skill (`SKILL.md`) and supporting
references, templates, scripts, and tests for the **Logion Marketplace
Companion**. The companion prioritizes local recall over marketplace search,
keeps context usage minimal, and requires explicit confirmation before
sensitive actions.

## Quick start

```bash
# Install dev dependencies
uv sync

# Run all verification checks
make verify

# Run tests only
make test

# Check package structure
make package-check
```

## Product contract

- **One always-on companion skill** — `SKILL.md` is the bootstrap.
- **Two user groups:**
  1. Capability consumers (discover, install, update).
  2. Course creators/operators (author, publish, manage).
- **No runtime dependency** on DSPy, GEPA, cloud models, or private backends.
- **Local recall first** — read-only fuzzy search before marketplace API.

## Package layout

```
packages/agent-companion/
├── README.md                 ← This file
├── pyproject.toml            ← Python project config and dev deps
├── Makefile                  ← Guardrail targets
├── SKILL.md                  ← Bootstrap skill (always loaded)
├── course/
│   └── capabilities.yaml     ← Capability manifest
├── references/               ← On-demand reference docs
├── templates/                ← Example configs
├── scripts/                  ← Packaging and update scripts
├── tests/                    ← Structural and integration tests
├── evals/                    ← Eval harness and scenarios
└── vendor/                   ← Agent-specific integration notes
```

## License

See the root repository for license information.