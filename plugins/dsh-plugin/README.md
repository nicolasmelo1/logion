# Logion dsh plugin

A DeepSeek Harness bundle that exposes Logion inside a dsh session. It
contains no business logic and no second API client: every tool shells to
the locally configured `logion` executable with `--json` and renders what
it returns. Credentials stay with that CLI — nothing is ever written into
a Cordis config entry.

## Install

```bash
dsh plugin --profile <name> add @logionsh/dsh-plugin
```

The bundle declares itself through `dsh.bundle.patch`, and its
`cordis.patch.yml` loads the plugin by package name. Loading it registers
these tools:

| Tool | What it does |
| --- | --- |
| `logion_search` | Search the catalog |
| `logion_show` | Inspect one resource's source, revision, digest, license, and publisher-declared permissions |
| `logion_plan` | Preview an acquisition — zero-write |
| `logion_acquire` | Acquire through the native manager, after review |
| `logion_inventory` | List what Logion recorded as installed |
| `logion_reconcile` | Match existing native installs to catalog resources, read-only |

Without the `logion` CLI on PATH, every tool explains how to install it
and does nothing else.

## Honesty boundary

Everything shown here is first-party: what Logion observed and what the
publisher declared. Declared dependencies and services are the
publisher's claims — this plugin neither verifies nor enforces them, and
nothing it displays means "network verified".

## Pins

Tested against `@deepseek-ai/dsh@0.1.0-rc.6` (npm integrity
`sha512-brpZfED7ieRa2PQ5tUxMhHrM1pb2CmKFVM/f6yMULBDMicahk+Z2OsHgTwTDnoiZm23Ftu9rQz0NN4pflaoJcg==`).
dsh is a developer preview: each version bump re-runs the recorded
fixtures before the pin moves.
