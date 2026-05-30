# Admin Operations

Gated administrative commands. The `logion admin` group is hidden unless
the environment variable `LOGION_ENABLE_ADMIN` is truthy. The companion
guides these flows only when the user has explicitly identified themselves
as a platform administrator AND has set the env var.

Run discovery first:

```bash
LOGION_ENABLE_ADMIN=1 logion admin --help
LOGION_ENABLE_ADMIN=1 logion admin courses --help
LOGION_ENABLE_ADMIN=1 logion admin users --help
LOGION_ENABLE_ADMIN=1 logion admin agents --help
LOGION_ENABLE_ADMIN=1 logion admin reports --help
```

## Courses (admin view)

```bash
LOGION_ENABLE_ADMIN=1 logion admin courses list --json
LOGION_ENABLE_ADMIN=1 logion admin courses get COURSE_ID --json
LOGION_ENABLE_ADMIN=1 logion admin courses block COURSE_ID --yes --json
```

`block` sets the course status to blocked, making it invisible to buyer
discovery. Confirm with the user before invoking; explain that buyers
holding entitlements may be affected.

## Users

```bash
LOGION_ENABLE_ADMIN=1 logion admin users get USER_ID --json
LOGION_ENABLE_ADMIN=1 logion admin users billing-exemption USER_ID --enabled true --yes --json
LOGION_ENABLE_ADMIN=1 logion admin users suspend USER_ID --yes --json
LOGION_ENABLE_ADMIN=1 logion admin users unsuspend USER_ID --yes --json
```

`suspend` blocks the user from authenticating; their agents lose API access.
Confirm and surface the reason before invoking.

## Agents

```bash
LOGION_ENABLE_ADMIN=1 logion admin agents get AGENT_ID --json
LOGION_ENABLE_ADMIN=1 logion admin agents suspend AGENT_ID --yes --json
LOGION_ENABLE_ADMIN=1 logion admin agents unsuspend AGENT_ID --yes --json
```

## Reports (moderation queue)

```bash
LOGION_ENABLE_ADMIN=1 logion admin reports list --json
LOGION_ENABLE_ADMIN=1 logion admin reports get REPORT_ID --json
LOGION_ENABLE_ADMIN=1 logion admin reports resolve REPORT_ID \
    --resolution-notes "Removed reported content; warned user." --yes --json
LOGION_ENABLE_ADMIN=1 logion admin reports dismiss REPORT_ID \
    --dismissal-notes "Insufficient evidence of abuse." --yes --json
```

`resolve` and `dismiss` close moderation tickets. Both are auditable; the
notes are part of the permanent record.

## Safety rules

- Every mutating admin command (`block`, `suspend`, `unsuspend`,
  `billing-exemption`, `resolve`, `dismiss`) requires explicit user
  confirmation before invocation. The `--yes` flag skips the local prompt
  — companion agents should leave it off and surface what is about to
  happen.
- Never invoke admin verbs on behalf of a user who has not explicitly
  identified themselves as an administrator.
- Admin actions are visible to other platform staff; reproduce the affected
  IDs in the confirmation prompt so the user can verify scope.
