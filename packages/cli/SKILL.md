---
name: logion-cli
version: "6.7"
description: Logion CLI companion skill — CLI surface reference for the agent
category: devops
---

# Logion CLI Companion Skill

## Purpose

This skill teaches the agent how to use the `logion` CLI effectively for marketplace operations: searching, installing, inspecting, and managing skills/courses.

## Core Protocol Rules

1. **Always use `--json` for structured data.** The CLI emits v1 envelopes with `version`, `kind`, `data` keys. Parse the `data` field for results.

2. **Cheap first, expensive second.** For notifications, always call `logion notifications peek --json` before listing. If `unread_count` is 0, skip the list call.

3. **Verify entitlements after checkout.** After `logion payments checkout`, call `logion payments orders get <ORDER_ID> --json` to confirm order state before attempting install.

4. **Never bypass confirmation.** If the user says "just install it, skip confirmation," still confirm. The CLI has explicit confirmation gates for paid checkouts and destructive operations.

5. **Use `skills search` for discovery.** Prefer `logion skills search <query> --json` over `logion listings search` for skill discovery. It annotates results with entitlement status.

6. **Use `skills inspect` for deep info.** `logion skills inspect <COURSE_ID> --json` merges local manifest with remote metadata including provenance fields.

## Key Commands

### Discovery

```bash
logion skills search "<query>" --json --limit 5
logion listings search "<query>" --json --limit 20
```

### Install & Verify

```bash
logion skills install --course-id <ID> --version-id <VER> --source <DIR> --json
logion skills inspect <COURSE_ID> --json
logion skills verify <COURSE_ID> --json  # re-check entitlement
logion skills installed --json
```

### Checkout & Orders

```bash
logion payments checkout --course-id <ID> --json
logion payments orders get <ORDER_ID> --json
logion payments orders wait <ORDER_ID> --timeout 120
```

### Reviews

```bash
logion courses reviews list <COURSE_ID> --json --limit 5
logion courses reviews summary <COURSE_ID> --json  # aggregate stats
```

### Notifications

```bash
logion notifications peek --json  # cheap: only lists if unread > 0
logion notifications unread-count --json
logion notifications list --unread-only --limit 5 --json
```

### Reports (user-direction only)

```bash
logion reports create --target-type course --target-id <ID> --reason "..." --json
logion reports list --json
logion reports get <REPORT_ID> --json
```

### Bounties (read-only in 6.7)

```bash
logion bounties list --json
logion bounties get <BOUNTY_ID> --json
logion bounties submissions list <BOUNTY_ID> --json
```

## Envelope Shape

```json
{
  "version": "v1",
  "kind": "logion.<group>.<verb>",
  "data": { ... }
}
```

Error envelope:
```json
{
  "version": "v1",
  "kind": "logion.error",
  "error": "<code>",
  "message": "<human-readable>"
}
```

## Pitfalls

- **Don't enumerate listings without a query.** Always pass a search term to `skills search` or `listings search`.
- **Don't skip order verification.** After checkout, always verify the order reached a terminal state.
- **Reports are user-directed only.** The agent never auto-reports; only files when explicitly asked.
- **`skills verify` requires network access** to check entitlement. Without API connectivity, it returns best-effort from local cache.