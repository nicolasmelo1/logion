# OpenAI Codex Integration

The Logion Marketplace Companion can be used with
[OpenAI Codex CLI](https://github.com/openai/codex).

## Installation

Export the companion's `SKILL.md` and references to a location accessible
by Codex, or add the companion's path to the Codex context files.

## Usage

Codex agents should:

1. Start from `SKILL.md` as the bootstrap context.
2. Check local recall first before any marketplace API call.
3. Load reference files only when needed.
4. Respect all confirmation gates before acting on sensitive operations.

## Context efficiency

The companion is designed to minimize context usage. Only load the specific
reference files needed for the current workflow step.