# OpenCode Integration

The Logion Marketplace Companion can be used with
[OpenCode](https://github.com/opencode-ai/opencode).

## Installation

Add the companion's directory to the OpenCode skills configuration.

## Usage

OpenCode agents should:

1. Read `SKILL.md` as bootstrap context.
2. Use local recall to find installed capabilities before marketplace search.
3. Load references on demand.
4. Require user confirmation for all gated actions listed in
   `capabilities.yaml`.

## Local recall

Local recall is the first guardrail. It searches a local index of installed
capabilities, proven workflows, and compact references without executing any
commands or making API calls.