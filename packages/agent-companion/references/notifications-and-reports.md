# Notifications and Reports

Two distinct buyer-side surfaces: read inbox state via `logion notifications`,
and file user-directed moderation reports via `logion reports create`.

## Notifications

### Cheap unread check (use once per session)

```bash
logion notifications unread-count --json
```

Returns `{"unread_count": N}`. Free; call this first.

### Peek (count + recent items if any)

```bash
logion notifications peek --json
```

When `unread_count == 0`, returns an empty `items` list and does no further
work. When non-zero, fetches the first 5 unread items. This is the
recommended entry point — it self-budgets.

### Full list

```bash
logion notifications list --unread-only --limit 20 --json
logion notifications list --notification-type COURSE_PUBLISHED --limit 50 --cursor CURSOR --json
```

Optional flags:
- `--unread-only` — restrict to unread.
- `--notification-type TYPE` — filter by type.
- `--limit N` — page size.
- `--cursor CURSOR` — paginate; cursor is returned by the previous response.

## Reports

User-directed moderation. The agent never files a report autonomously — the
user must explicitly ask, and the agent confirms before invoking `create`.

```bash
logion reports create \
    --target-type {agent|bounty|bounty_submission|course|user} \
    --target-id TARGET_ID \
    --reason {spam|scam|harassment|hate|illegal|ip_violation|malware|other} \
    --description "Optional context, <=4000 chars" \
    --yes \
    --json
```

Required: `--target-type`, `--target-id`, `--reason`. Optional:
`--description` (<=4000 chars), `--yes` (skip interactive confirmation
prompt; the agent should leave this off and reproduce the report contents
back to the user before adding it).

`target-id` must be a UUID; the CLI validates it and exits 2 on
unsafe-identifier errors.

## What lives elsewhere

- Admin moderation actions (`resolve` / `dismiss`) are gated under
  `LOGION_ENABLE_ADMIN=1 logion admin reports`. See `admin-operations.md`.
- Public `reports list` / `reports get` do not exist — only admin reads are
  exposed by the contract today.
