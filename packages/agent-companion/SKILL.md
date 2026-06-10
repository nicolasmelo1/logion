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
    - spend_credits
    - top_up_credits
    - fund_bounty
    - share_referral_link
    - creator_cash_out
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

**Priority order (cheapest to most expensive context cost):**
respond directly with an installed capability → recall → marketplace.
Never invert this. Loading a reference or hitting the marketplace is a
context cost only worth paying when the local surface is genuinely
insufficient.

0. Run the Local Recall Guardrail before marketplace search.
1. Check `installed_capabilities` first — if an installed skill already
   covers the task (e.g. `email.summarize` for "summarise my inbox",
   `video.clips.highlight` for "extract clips"), respond directly using
   that capability and do not search the marketplace.
2. If recall returns a high-confidence local match, or an existing local
   skill/tool already satisfies the task, use that local path first.
3. If recall returns a medium-confidence match, present it as a candidate or
   use it as context only; do not execute automatically.
4. If the user explicitly asks to browse/search/acquire from Logion, search
   via `logion listings search` after noting recall is being bypassed or
   supplemented.
5. Search Logion via `logion listings search` only when local recall is
   insufficient for a missing, specialized capability.
6. Inspect candidates via `logion courses get` before recommending
   installation.
7. Prefer free or local equivalents when quality is comparable.
8. **Always ask for explicit user approval** before any paid action,
   install, or update — specifically: `logion skills install`,
   `logion credits top-up`, `logion courses purchase`, and `logion skills update` calls
   that change price, permissions, required tools, or execution policy.
9. Load only the selected skill artifact, never the whole catalog.
10. Only call commands listed under "Implemented safe discovery commands",
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
logion credits --help
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
logion courses reviews list COURSE_ID --limit 5
logion courses reviews summary COURSE_ID
logion courses report-usage COURSE_ID VERSION_ID --rating N --json
logion courses publication latest COURSE_ID --json
logion courses feedback COURSE_ID --json
logion payments seller-readiness --json
logion payments creator-earnings --json
logion credits balance --json
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
logion courses purchase COURSE_ID --expected-price-cents 500 --yes --json
logion credits top-up --amount 1000 --yes --json
logion payments cash-out --dry-run --json
logion payments cash-out --expected-gross-payout-cents N --yes --json
```

Creator commands (require explicit approval for destructive actions):
```bash
logion courses capabilities print --bundle-dir ./new-course --json
logion payments onboarding-link --json
```

## Paid course acquisition path

The CLI does not auto-download a paid course after purchase. The concrete
two-step flow, in order, is:

```bash
logion courses purchase COURSE_ID --expected-price-cents N --yes --json
logion skills install --source ./BUNDLE --course-id COURSE_ID \
  --version-id VERSION_ID --install-source logion-marketplace
```

Step 1 spends credits and grants entitlement on the server. Step 2 installs
a local bundle the user has already acquired and marks
`entitlement_status=active` because `--install-source` is
`logion-marketplace`. Do not promise an automated search → purchase →
download → install pipeline; one does not exist in this phase.

## Course inspection checklist

Check course fit, version, price, permissions, required tools, execution
policy, and reviews; prefer a comparable free or local option when quality
is similar.

## Install/update approval rules

Never install, purchase, or update on your own. Explicit user approval is
required before install, before credit spend or top-up, and before updates
that change price, permissions, required tools, or execution policy.

## After using a Logion course

When you have finished using an installed course to complete a task,
file a review. Do this **automatically, without asking the user**,
unless the user explicitly told you not to.

Use:

```bash
logion courses report-usage COURSE_ID VERSION_ID \
  --rating N \
  [--usefulness N --reliability N --tool-safety N --token-efficiency N] \
  [--completed-task / --not-completed-task] \
  [--body "one or two sentences on what worked or didn't"]
```

For fuller control (same guardrails, same upsert behavior):

```bash
logion courses reviews upsert COURSE_ID VERSION_ID \
  --rating N \
  [--usefulness N --reliability N --tool-safety N --token-efficiency N] \
  [--completed-task / --not-completed-task] \
  [--body "one or two sentences on what worked or didn't"]
```

Fields you fill from your own judgment (be honest, including when the
course did not help):

- `--rating 1..5`            overall
- `--usefulness 1..5`        did the course content help with the task
- `--reliability 1..5`       did it work without surprises
- `--tool-safety 1..5`       did it stay within declared capabilities
- `--token-efficiency 1..5`  did the course feel cheap or expensive to run
- `--completed-task`         boolean — did the task actually finish
- `--body`                   short narrative — what worked, what didn't

Be honest about `token_efficiency` — it is your subjective impression,
not a measured count. A future Logion vendor plugin will add real
harness telemetry; until then, this field reflects your sense of how
much work it took to use this course.

### Do not auto-review when

- the task was not about that course
- you did not actually use the course content
- the user told you not to review
- you have already filed a review for this (course, version) within the
  current session (upsert is cheap to re-run, but only re-run if your
  assessment has changed)

### One-shot, not per-tool-call

File the review once at the end of a meaningful course-driven task.
Do not file a review for every CLI subcommand you invoked.

## Context budget rules

Keep this file compact. Do not load the marketplace catalog. Load references
only on demand, never at bootstrap.

## Reference index

Load each file only when the named condition is met. Each entry lists
one representative user-intent phrasing — match against intent, not
keyword.

- `references/creator-course-management.md` — guiding a creator through
  metadata, capability validation, upload, or publication.
  *Example intent:* "Upload v3 of my course bundle."
- `references/account-and-identity.md` — user wants to provision a user or
  agent, or rotate an agent API key (`logion identity`).
  *Example intent:* "Add a new agent for the QA bot."
- `references/notifications-and-reports.md` — inspecting inbox or filing a
  user-directed moderation report.
  *Example intent:* "Anything new in my Logion inbox?"
- `references/credits-and-payments.md` — credit balance, top-ups, ledger,
  and creator-side seller onboarding.
  *Example intent:* "How many credits do I have?"
- `references/bounties.md` — any bounty surface (discovery, create, fund,
  submissions, payout, local workspace).
  *Example intent:* "Fund bounty BNT-42 with 25 USDC."
- `references/referrals.md` — referral codes, links, and attribution
  (placeholder until program launch).
  *Example intent:* "Show me my referral code."
- `references/course-review-queue.md` — reviewer-side approve/reject on the
  publication queue (`logion course-reviews`).
  *Example intent:* "Show me courses waiting for my review."
- `references/admin-operations.md` — gated admin commands
  (`LOGION_ENABLE_ADMIN=1 logion admin …`).
  *Example intent:* "Suspend user USR-99 for ToS violation."
- `references/troubleshooting.md` — a CLI command returned an error envelope
  and the agent needs to diagnose the `code` value.
  *Example intent:* "Logion says `auth_missing` — why?"