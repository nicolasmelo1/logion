---
name: logion-marketplace-companion
version: 0.1.0
description: >-
  Compact bootstrap skill for recall-first Logion discovery, inspection,
  install, update, and creator-course-management routing without loading
  the whole marketplace.
required_tools:
  - terminal
  - file
required_env: []
safety:
  requires_confirmation:
    - paid_checkout
    - install_new_capability
    - update_paid_capability
    - permission_expansion
    - publish_or_unpublish_course
    - upload_new_course_version
    - change_course_price
---

# Logion Marketplace Companion

Use Logion only as a fallback or explicit browse/acquire path. Keep bootstrap
context small; load only the selected skill artifact.

## When to use Logion

Use Logion when local recall is insufficient and the task needs a missing,
specialized capability, or when the user explicitly asks to browse, search,
acquire, install, or update from Logion.

## When not to use Logion

Do not use Logion when an existing local tool, installed skill, prior proven
workflow, or project-local command already covers the task well enough.

## Decision tree

0. Run the Local Recall Guardrail before marketplace search.
1. If recall returns a high-confidence local match, or an existing local
   skill/tool already satisfies the task, use that local path first.
2. If recall returns a medium-confidence match, present it as a candidate or
   use it as context only; do not execute automatically.
3. If the user explicitly asks to browse/search/acquire from Logion, search
   via `logion listings search` after noting recall is being bypassed or
   supplemented.
4. Search Logion via `logion listings search` only when local recall is
   insufficient for a missing, specialized capability.
5. Inspect candidates via `logion courses get` before recommending
   installation.
6. Prefer free or local equivalents when quality is comparable.
7. Ask for explicit user approval before `logion skills install`.
8. Ask for explicit user approval before any paid checkout
   (`logion payments checkout-start`).
9. Ask for explicit user approval before `logion skills update` calls that
   change price, permissions, required tools, or execution policy.
10. Load only the selected skill artifact, never the whole catalog.
11. Only call commands listed under "Implemented safe discovery commands",
    "Implemented mutating commands", or "Creator commands" below.

## Local Recall Guardrail

Recall is read-only fuzzy lookup over installed capabilities, prior successful
workflows or commands, local companion references, and project-local known
commands when available. If no recall command exists yet, manually inspect
those same local sources only. Recall never implies automatic execution.
Routing is band-based: HIGH suppresses marketplace; MEDIUM presents a
candidate; LOW allows marketplace fallback; NONE proceeds to marketplace.

## Safe discovery commands

Start with CLI help so the agent can discover what exists before guessing:
```bash
logion --help
logion health --help
logion identity --help
logion listings --help
logion notifications --help
logion courses --help
logion courses versions --help
logion payments --help
logion reports --help
logion course-reviews --help
logion bounties --help
LOGION_ENABLE_ADMIN=1 logion admin --help  # gated
```

Implemented safe discovery commands:
```bash
logion listings search --query "video cuts" --limit 5
logion courses get COURSE_ID
logion courses versions get COURSE_ID VERSION_ID
logion notifications unread-count
logion notifications list --unread-only --limit 20
logion recall search "video cuts" --limit 5  # read-only
logion skills installed
logion skills inspect COURSE_ID
logion skills updates
logion skills search "video cuts" --limit 5
logion courses reviews list --course-id COURSE_ID
logion courses reviews summary --course-id COURSE_ID
logion courses publication latest COURSE_ID --json
logion courses feedback COURSE_ID --json
logion payments seller-readiness --json
```

Implemented mutating commands (require explicit approval):
```bash
logion skills install --source ./BUNDLE --course-id COURSE_ID --version-id VERSION_ID
logion skills update COURSE_ID --version-id VERSION_ID --source ./BUNDLE
logion recall record --id WORKFLOW_ID --title TITLE --command CMD
logion courses capabilities scaffold --bundle-dir ./new-course
logion courses capabilities validate --bundle-dir ./new-course --json
logion courses create --title ... --slug ... --json
logion courses update COURSE_ID --json
logion courses uploads create COURSE_ID --file ... --json
logion courses uploads push COURSE_ID VERSION_ID --session-file session.json --file ... --json
logion courses uploads complete COURSE_ID VERSION_ID --json
logion courses publication request COURSE_ID --json
```

Creator commands (require explicit approval for destructive actions):
```bash
logion courses capabilities print --bundle-dir ./new-course --json
logion payments onboarding-link --json
```

## Course inspection checklist

Check course fit, version, price, permissions, required tools, execution
policy, reviews, and whether a comparable free or local option already exists.
Use `references/marketplace-flows.md` and `references/safety-and-approval.md`
for detailed review steps.

## Install/update approval rules

Never install, purchase, or update on your own. Explicit user approval is
required before install, before paid checkout, and before updates that change
price, permissions, required tools, or execution policy.

## Context budget rules

Keep this file compact. Do not load the marketplace catalog. Load references
only when needed: `references/marketplace-flows.md`,
`references/low-context-loading.md`, `references/safety-and-approval.md`,
`references/creator-course-management.md`, or `references/troubleshooting.md`.

## Troubleshooting

If recall is weak, refine the task and inspect candidates before recommending
anything. If commands fail or metadata is unclear, use
`references/troubleshooting.md`.