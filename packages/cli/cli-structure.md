# CLI Structure — Phase 6.7 Surface Audit

This document maps every CLI verb to its JSON envelope kind and key behaviors,
providing a 1:1 invariant reference for the agent companion.

## Top-level commands

| Command | Subcommands | Notes |
|---|---|---|
| `health` | (leaf) | Ping server |
| `identity` | `users-create`, `agents-add`, `agents-rotate-key` | Auth lifecycle |
| `listings` | `search` | Marketplace search (default limit: 20) |
| `notifications` | `unread-count`, `list`, **`peek`** | peek: cheap count-first helper |
| `courses` | `create`, `get`, `update`, `uploads`, `publication`, `reviews`, `capabilities`, `feedback`, `versions` | Full CRUD + review/feedback |
| `payments` | `seller-readiness`, `onboarding-link`, `checkout`, `orders` | orders: `get` (v1 envelope) + `wait` (poll) |
| `reports` | `create`, `list`, `get` | User-directed only; --target-type validated |
| `course-reviews` | `list`, `get`, `approve`, `reject` | Admin review pipeline |
| `admin` | (leaf) | Admin diagnostics |
| `bounties` | `create`, `list`, `get`, `open`, `fund`, `cancel`, `payout`, `submissions`, `workspace` | Read paths use v1 envelope |
| `skills` | `install`, `installed`, **`inspect`**, `updates`, `update`, **`verify`**, **`search`** | New: inspect (marketplace-aware), verify (provenance), search (marketplace) |
| `recall` | `search`, `record` | Recall index |

## JSON envelope protocol

All `--json` output for read commands follows the v1 envelope:

```json
{
  "version": "v1",
  "kind": "logion.<group>.<verb>",
  "data": { ... }
}
```

Error output follows:

```json
{
  "version": "v1",
  "kind": "logion.error",
  "error": "<code>",
  "message": "<human-readable>"
}
```

## New in Phase 6.7

| Verb | Kind | Key behavior |
|---|---|---|
| `skills search` | `logion.skills.search` | Marketplace search with entitlement annotation; default limit 5 |
| `skills inspect` | `logion.skills.inspect` | Local manifest + remote metadata merge; shows provenance fields |
| `skills verify` | `logion.skills.verify` | Re-check entitlement status for installed skills |
| `skills install` | (updated) | Provenance fields written to manifest |
| `payments orders get` | `logion.payments.orders.get` | v1 envelope |
| `payments orders wait` | (new) | Poll until order reaches terminal state |
| `notifications peek` | `logion.notifications.peek` | Cheap count-first: lists only if unread > 0 |
| `reports list` | `logion.reports.list` | v1 envelope |
| `reports get` | `logion.reports.get` | v1 envelope |
| `bounties list` | `logion.bounties.list` | v1 envelope |
| `bounties get` | `logion.bounties.get` | v1 envelope |
| `courses reviews list` | `logion.courses.reviews.list` | v1 envelope |
| `courses reviews summary` | `logion.courses.reviews.summary` | New: aggregate stats from paginated reviews |
| `courses feedback` | `logion.courses.feedback` | v1 envelope |

## Compact defaults

| Verb | Default limit | Rationale |
|---|---|---|
| `listings search` | 20 | Marketplace browse |
| `skills search` | 5 | Agent context budget |
| `notifications list` | 10 | Quick scan |
| `notifications peek` | 5 | Only when unread > 0 |
| `reports list` | 10 | Moderate |
| `recall search` | 5 | Agent budget |

## Provenance fields (skills install/inspect)

Every installed manifest now includes:
- `source`: "logion" | "local"
- `entitlement_status`: "active" | "expired" | "unknown" | "missing"
- `license_scope`: grant scope descriptor
- `official_update_channel`: bool
- `last_verified_at`: ISO-8601 timestamp or "never"