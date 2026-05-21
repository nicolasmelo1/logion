# OpenClaw Integration

The Logion Marketplace Companion can be used with OpenClaw agents.

## Installation

Add the companion's `SKILL.md` path to the agent's skill configuration. Copy
the `course/` and `references/` directories alongside.

## Usage

OpenClaw agents should:

1. Bootstrap from `SKILL.md`.
2. Use local recall before marketplace search.
3. Load reference files on demand only.
4. Respect all safety confirmation gates.

## Context efficiency

The companion minimizes context usage through:

- Single bootstrap `SKILL.md` (~2KB).
- On-demand reference loading.
- Local recall returns top-k compact results.
- Marketplace search is a fallback, not the default.