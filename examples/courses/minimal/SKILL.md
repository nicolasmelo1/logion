---
name: minimal
description: A bare-minimum Logion course example. Use as a starting template when authoring a new skill that needs no tools, no network, no filesystem writes, and no env vars. Demonstrates the smallest valid SKILL.md plus capabilities.yaml pairing.
license: MIT
---

# Minimal Logion Course

This is the smallest valid Logion course. It exists as a copy-paste starting point.

## What this course does

Nothing meaningful — it returns the literal string `"hello from minimal logion course"` when an agent reads it.

## Structure

```
minimal/
├── SKILL.md                  # this file
└── course/
    └── capabilities.yaml     # near-empty Logion manifest
```

No `scripts/`, no `references/`, no `assets/`. Add those when your real course needs them.

## When to use this

When you're starting a new course and want a known-good skeleton that already validates against both:

- the agentskills.io SKILL.md frontmatter spec
- the Logion `course/capabilities.yaml` schema

Copy this whole directory, rename it, edit `SKILL.md` and `course/capabilities.yaml`, then run `logion course validate ./your-course/` before uploading.

## What an agent should do here

Nothing — this skill has no behavior. Real skills go in their body where this paragraph is.
