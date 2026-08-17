---
summary: Observe use of natively installed resources and report honest feedback under an explicit consent mode.
---
# Use Observation and Feedback

Logion can learn from a resource you installed with `npx skills`, `npx plugins`,
`hf`, or Logion itself — without reinstalling it through Logion. Three separate
things are involved, and they are deliberately not the same signal:

- **Observation** — a local, privacy-minimized hint that a harness touched an
  installed resource. It means *probably used*.
- **Usage receipt** — a rating-free statement that an attributed version took
  part in a task. Opt-in, uploaded only under an explicit mode.
- **Feedback** — an intentional report with subjective scores. Never produced by
  observation alone.

None of these is a controlled evaluation.

## Consent modes

```text
off         no spool, no upload, no prompt, no network call
local-only  local observation and pending list; nothing is uploaded
prompt      local observation; every upload or submission asks first
auto        one receipt or one feedback report per completed task, no re-asking
```

A harness with no stored mode is `off`: observation is opt-in. Setting
`DO_NOT_TRACK=1` (or `LOGION_DO_NOT_TRACK=1`) forces `off` for every harness
regardless of what is stored. An upstream tool's telemetry being enabled is
never treated as consent for Logion.

## Enabling a harness

Inspect the exact edit before consenting to it:

```bash
logion integrations detect --json
logion integrations enable claude-code --dry-run --json   # prints the config diff
logion integrations enable claude-code --mode prompt
logion integrations status --json
logion integrations disable claude-code
```

Enabling installs one `PostToolUse` hook that runs
`logion usage observe --harness HARNESS --stdin`. The edit is idempotent,
preserves configuration Logion does not own, and refuses to write to a config
file it cannot parse. Disabling removes only the entry Logion installed.

Harnesses that expose no trustworthy local tool-use event report
`inventory_only_observation_unsupported`. Logion still reconciles their
inventory; it does not infer use from installation.

## What the hook records

The hook receives the harness's raw payload — prompts, commands, paths, tool
arguments. Those exist in memory only long enough to match a path against local
inventory, and then they are dropped. The spool line holds opaque identifiers
only: resource, version, installation, scope, channel, harness, event, and a
hashed session key. Attribution that is unknown or ambiguous is dropped rather
than guessed.

```bash
logion usage pending --json                 # includes observation_group_id
logion usage dismiss OBSERVATION_GROUP_ID
```

## Uploading receipts and reporting feedback

```bash
logion usage upload --task-class software-development --outcome completed --yes
logion feedback submit RESOURCE_ID VERSION_ID --rating 4 \
  --usefulness 4 --reliability 4 --tool-safety 5 --token-efficiency 4 \
  --completed-task --task-class software-development \
  --body "Resource-focused notes with no repository-private data"
```

`usage upload` refuses to send under `off` and `local-only`, and requires
`--yes` under `prompt`. Both commands record a local tombstone, so a hook that
fires twice does not become two outbound reports; `--force` revises a feedback
report deliberately.

The acquisition channel is read from the local acquisition receipt for that
exact version. Pass `--acquisition-channel` only when there is no receipt — for
a resource installed before Logion was watching.

Eligible feedback projects to a marketplace Course review through the existing
review rules; the response always names the disposition. Feedback on an openly
installed resource does not create a paid entitlement and is never labelled a
verified buyer review.

Never put a prompt, repository name, source code, customer data, or personal
information in a feedback body.
