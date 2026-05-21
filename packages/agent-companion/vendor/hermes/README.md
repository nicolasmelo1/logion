# Hermes Agent Integration

The Logion Marketplace Companion is designed to work as a first-class skill
in [Hermes Agent](https://github.com/nousresearch/hermes).

## Installation

Hermes loads skills from `~/.hermes/skills/`. The companion installs into:

```
~/.hermes/skills/logion-marketplace-companion/
├── SKILL.md
├── references/
└── course/
    └── capabilities.yaml
```

## Context budget

The companion is designed for low context usage:

- **Bootstrap** (SKILL.md): ~2KB, always loaded.
- **References**: loaded on demand, ~1-2KB each.
- **Local recall**: top-5 results, compact summaries only.
- **Marketplace search**: top-5 results, metadata only.

Hermes should load the skill, check local recall first, and only load
reference files when the workflow requires them.

## Local recall

The companion uses Hermes's local recall guardrail before reaching for the
Logion marketplace API. See `references/low-context-loading.md` for details.