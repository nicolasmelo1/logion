# Troubleshooting

Diagnose CLI failures without guessing. Load this reference when the user
asks why a `logion` command failed, mentions a specific error code, or
the CLI returned an error envelope. Common triggers: `auth_missing` (no
API key), `entitlement_expired` (renewal needed), `not_found` (wrong id
or no permission), `confirmation_required` (`--yes` was missing). The
CLI emits a stable error envelope when `--json` is passed; the `code`
field is the machine-readable category.

## Error envelope

```json
{"version": "v1", "kind": "logion.error",
 "data": {"code": "<code>", "message": "<human>", "exit_code": N}}
```

Allowed `code` values:

- `auth_missing` — no API key in env or config; run `logion identity --help`
  if the user needs to provision an agent.
- `entitlement_missing` — buyer attempted an action on a course they have
  no entitlement for; route to `logion courses purchase` after
  confirmation, ensuring sufficient credit balance first.
- `entitlement_expired` — entitlement exists but expired; refresh via
  `logion skills verify COURSE_ID --json` or guide the user to renew.
- `unsafe_identifier` — the supplied id contains characters disallowed in
  filesystem segments. Do NOT retry with a stripped version; ask the user
  for the correct id.
- `not_found` — the resource id does not exist (or the caller lacks
  permission to see it). Re-check the id via `logion <group> list` /
  `logion <group> get`.
- `validation_failed` — arguments fail server-side validation; the message
  identifies the failing field. Surface the message and fix locally.
- `server_error` — transient backend failure. Surface and ask the user
  whether to retry; do not silent-retry.
- `confirmation_required` — local confirmation gate was not satisfied
  (e.g. `--yes` missing on an interactive guard). Re-present the action
  with full context and re-ask.
- `top_up_timeout` — `credits top-ups wait` exceeded its `--wait-timeout`.
  Try again with a longer timeout or call `credits top-ups get` directly.

## Exit codes

- `0` — success.
- `1` — backend / domain / runtime failure (most `server_error`,
  `not_found`, `entitlement_*`).
- `2` — user-input / validation / confirmation / timeout
  (`unsafe_identifier`, `validation_failed`, `confirmation_required`,
  `top_up_timeout`).

## Common failure patterns

**Skill install reports `entitlement_missing` on a free course.** Free
courses still produce an entitlement; the local manifest may be stale. Run
`logion skills verify COURSE_ID --json` and retry.

**`courses uploads push` says the session expired.** Sessions expire after
the `expires_at` returned by `uploads create`. Run `uploads create` again
to start a fresh session; previously uploaded files do NOT need to be
re-pushed — `push` resumes from `remaining`.

**`courses publication request` says "no version to review".** The course
has no version with a completed upload. Run `courses uploads complete` for
the most recent version first.

**`credits top-ups wait` exits 2 even though Stripe shows the payment completed.**
The timeout fired before settlement reached the API. Re-run with a longer
`--wait-timeout` or just call `credits top-ups get` once.

**Bounty contributor sees no balance after `accept`.** The accept step
accrues a payable balance directly; the contributor cashes out with
`logion payments cash-out`. The legacy `bounties payout` command was
removed — if a script still references it, drop the call.

## What is NOT a CLI issue

- Network errors are surfaced with `server_error`. Check connectivity
  before assuming the API is down.
- 401s become `auth_missing`. Verify the API key in env / config rather
  than re-running the same command.
- A "command not found" for `logion <group>` may mean the group is gated.
  `admin` requires `LOGION_ENABLE_ADMIN=1`; see `admin-operations.md`.
