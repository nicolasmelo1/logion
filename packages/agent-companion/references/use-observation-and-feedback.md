# Use observation and resource feedback

Load this when the user wants Logion to learn from a resource they already
installed natively (`npx skills`, `npx plugins`, `hf`, or a vendor plugin), or
when you need to report feedback for something that is not a Logion Course.

## Ground rules

- Observation means *probably used*. Feedback means *someone reported an
  outcome*. Neither is an evaluation. Never describe an inventory scan as
  observed use.
- Never enable a harness integration on your own. Show the diff, then ask.
- Never put a prompt, repository name, source code, customer data, or personal
  information in a feedback body.

## Enabling observation (requires approval)

```bash
logion integrations detect --json
logion integrations enable HARNESS --dry-run --json     # shows the config diff
```

Show the user the `plan.diff` and the mode you propose, then ask. Only after
approval:

```bash
logion integrations enable HARNESS --mode prompt
```

Modes: `off` (nothing), `local-only` (spool only), `prompt` (asks before every
upload or submission), `auto` (one report per completed task). No stored mode
means `off`. `DO_NOT_TRACK=1` forces `off` everywhere — do not try to work
around it.

Harnesses with no trustworthy tool-use hook return
`inventory_only_observation_unsupported`. That is an honest result: reconcile
inventory and report use explicitly instead of inventing an event.

## At the end of a meaningful task

```bash
logion usage pending --json
```

Match only resources you actually used in this session. Each entry carries the
`observation_group_id` you need to dismiss it:

```bash
logion usage dismiss OBSERVATION_GROUP_ID
```

Dismiss (do not rate) when the outcome is unknown or the resource was only read
incidentally.

Then report. Under `prompt`, show the proposed scores and body and ask first:

```bash
logion feedback submit RESOURCE_ID VERSION_ID --rating N \
  --usefulness N --reliability N --tool-safety N --token-efficiency N \
  --completed-task|--not-completed-task \
  --body "resource-focused notes, nothing private"
```

A coarse task class is also required. Run `logion feedback submit --help`, or
read `logion docs read use-observation-and-feedback`, for the exact flag and
the accepted values.

The acquisition channel is resolved from the local receipt. Pass
`--acquisition-channel` only if Logion says there is no receipt. A repeat
submission for the same version and task class is refused; use `--force` only
when your assessment genuinely changed.

Rating-free receipts are separate and only for `prompt` (with `--yes`) or
`auto`: run `logion usage upload` with the same task class flag, an
`--outcome`, and `--yes`.

## Reading the response

`projection_disposition` explains what happened to the marketplace review:

- `projected` — an eligible Course review was created.
- `not_a_course` — the resource has no Course projection; the feedback is still
  recorded and useful.
- `ineligible` — a Course exists but this exact version does not project.
- `paid_entitlement_missing` — the artifact is a paid Course and no entitlement
  permits a marketplace review.
- `self_review` — the reporter owns the resource.

Never describe generic feedback on an openly installed resource as a verified
buyer review.
