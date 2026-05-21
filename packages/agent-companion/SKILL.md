---
name: logion-marketplace-companion
version: 0.1.0
description: >-
  Companion skill for discovering, acquiring, installing, updating, creating,
  and managing Logion courses/capabilities without loading the whole marketplace
  into context.
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

Small bootstrap skill that helps agents discover, evaluate, install, update,
create, and manage Logion marketplace capabilities while keeping context usage
minimal.

## Runtime policy

1. **Local recall first.** Before searching the Logion marketplace, check
   local recall for installed capabilities, proven workflows, and compact
   local references. Local recall is read-only and never executes commands.
2. **Prefer local.** Prefer existing local tools, skills, and proven workflows
   before reaching for marketplace search.
3. **Search marketplace only when insufficient.** Only search Logion when
   local recall and existing capabilities do not cover the need.
4. **Inspect before acting.** Always review price, permissions, version, and
   reviews before installing or purchasing.
5. **Confirm sensitive actions.** Never install, purchase, publish, upload, or
   change pricing without explicit user approval.
6. **Load selected only.** Only load the specific skill/course the user chose,
   not the entire catalog.
7. **Check updates safely.** Detect and propose updates, but never apply them
   automatically.

## Capabilities

See `course/capabilities.yaml` for the full capability manifest.

## References

- `references/marketplace-flows.md` — consumer discovery, inspection, install,
  and update workflows.
- `references/creator-course-management.md` — course creation, update, upload,
  and publication workflows for creators.
- `references/safety-and-approval.md` — confirmation gates and safety rules.
- `references/low-context-loading.md` — strategies for keeping context small.
- `references/troubleshooting.md` — common errors and recovery steps.