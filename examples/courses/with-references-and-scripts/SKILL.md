---
name: with-references-and-scripts
description: Logion course example that bundles a runnable script and a reference doc. Use as a starting template when your skill executes a small subprocess (terminal tool) and produces output files. Demonstrates progressive disclosure across SKILL.md, references/, and scripts/.
license: MIT
compatibility: Requires a POSIX shell (bash, zsh). No network, no env vars.
metadata:
  author: logion-examples
  version: "0.1.0"
---

# Logion Course With References And Scripts

This example shows the larger shape a real course usually takes: a short `SKILL.md` for activation, a `references/` directory for detailed docs the agent loads on demand, and a `scripts/` directory for code the agent runs.

## What this course does

When an agent is asked to "say hello and record it," this skill:

1. Runs `scripts/say-hello.sh` to print a greeting.
2. Writes a timestamped record to `./outputs/hello.log` inside the course bundle.

That's it. It's a stand-in for a real skill that runs a tool and produces an artifact.

## Structure

```
with-references-and-scripts/
├── SKILL.md
├── course/
│   └── capabilities.yaml
├── references/
│   └── usage.md            # loaded only when the agent needs detail
└── scripts/
    └── say-hello.sh        # invoked via the terminal tool
```

## When to use this template

Copy this directory when your real course:

- Has a meaningful body that takes ~50-200 lines to explain.
- Bundles one or two helper scripts (Python or shell).
- Needs to write files into a known subdirectory.

If your course also needs outbound HTTP or env vars, use the upcoming `with-network-and-secrets/` example as a starting point (or extend this one).

## How to invoke

The agent reads this file at activation. To perform the task:

```
bash scripts/say-hello.sh > outputs/hello.log 2>&1
```

For detailed parameters, see [references/usage.md](references/usage.md).

## Capability declarations

This course declares:

- `tools: [file, terminal]` — needs to write a file and run a subprocess.
- `filesystem.read: [.]` — reads its own bundle.
- `filesystem.write: [./outputs]` — writes only under `outputs/`.
- No network, no env vars.

See `course/capabilities.yaml` for the exact manifest.

## What an author should change when copying

1. The `name` field in this frontmatter (must match your directory name).
2. The `description` (be specific about what + when).
3. The body of this file.
4. `references/usage.md` content (or remove the file if you don't need it).
5. `scripts/say-hello.sh` (or replace with your real script).
6. `course/capabilities.yaml` — declare only what you actually need.
