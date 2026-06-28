# @logionsh/cli

Thin npm wrapper around the canonical [`logion-cli`](https://pypi.org/project/logion-cli/) Python package.

## Install

```bash
npm install -g @logionsh/cli
# or
npx @logionsh/cli --help
```

## Requirements

- Node ≥ 22
- Python ≥ 3.12 on the host (the wrapper auto-detects `python3` or `py`)
- One of `pipx`, `uv`, or the wrapper falls back to a managed venv

## What this package does

On install, the postinstall hook:

1. Finds a working Python 3.12+.
2. Installs `logion-cli==<pinned-version>` from PyPI via `pipx`/`uv`/venv.
3. Shims the `logion` and `lgn` binaries onto your PATH.

The pinned PyPI version is baked into the npm tarball at publish
time, so `npm install -g @logionsh/cli@0.3.0` always installs the
exact matching Python package.

## Why not pure Node?

The canonical implementation is Python — the CLI is part of a
three-package Python workspace and shares code with the Python SDK.
A pure-Node port would double the codebase and drift from the source
of truth. This wrapper exists so JS-ecosystem users don't need to
think about Python package managers.

## Environment variables

| Variable                     | Purpose                                  |
| ---------------------------- | ---------------------------------------- |
| `LOGION_NPM_SKIP_INSTALL`    | Set to `1` to skip postinstall (CI/test) |
| `LOGION_NPM_FORCE_INSTALLER` | Force `pipx`, `uv`, or `venv`            |
| `LOGION_NPM_PYTHON`          | Override Python binary path              |

See https://github.com/nicolasmelo1/logion for the full project.
