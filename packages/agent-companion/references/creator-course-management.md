---
# Creator Course Management

Operational guidance for using Logion as a course creator. Loaded only
when the agent is in a creator workflow.

## Course lifecycle overview

1. `logion courses create` — produces a draft.
2. Edit local bundle (SKILL.md, capabilities.yaml, references, scripts).
3. `logion courses capabilities validate --bundle-dir <path>` — local check.
4. `logion courses uploads create COURSE_ID --file SKILL.md --file course/capabilities.yaml [...]`.
5. `logion courses uploads push COURSE_ID VERSION_ID --session-file session.json --file ...`.
6. `logion courses uploads complete COURSE_ID VERSION_ID`.
7. `logion courses publication request COURSE_ID VERSION_ID` (after confirmation).
8. Poll `logion courses publication latest COURSE_ID`.
9. On rejection, read `logion courses publication feedback COURSE_ID VERSION_ID`, fix, repeat from 4.

## Create/update metadata checklist

- Title, slug, summary, description, language, tags, visibility, price.
- Required tools and required env-var names (NEVER values).
- Capability IDs declared in `course/capabilities.yaml`.

## Bundle structure

```
course-bundle/
├── SKILL.md
├── course/
│   └── capabilities.yaml
├── references/
├── templates/
└── scripts/
```

## Capability manifest checklist

- Every `capability_id` has a `required_tools` list.
- Every `capability_id` declares `required_env` as names only.
- No environment values, API keys, or tokens.
- No filesystem paths outside the bundle root.

## Upload/version workflow

Uploads are 3-phase: `create` → `push` → `complete`. The CLI returns a
`session.json` from `create`; `push` is idempotent — partial pushes
resume from `remaining`. Never call `complete` before all
`expected_files` are pushed.

## Publication review workflow

Submission is in `safety.requires_confirmation` as
`publish_or_unpublish_course` and `upload_new_course_version`. The
agent must ask before submitting. Status transitions: `submitted` →
`in_review` → `approved` | `rejected` | `needs_changes`.

## Feedback and notification workflow

Use `logion courses publication feedback COURSE_ID VERSION_ID` for
review-specific feedback. Use `logion notifications peek` for general
inbox state. Surface severity (`error` / `warning` / `info`) verbatim.

## Pricing and seller-readiness safety rules

- Paid courses require `logion payments seller-readiness` true.
- Price, visibility, and price-currency changes are confirmation-required.
- Never echo or persist onboarding URLs beyond one-time delivery.

## When to ask the user for missing data

- Missing required field for `create` → ask once, in one batch.
- Ambiguous price/currency → ask explicitly before any paid action.
- Missing env-var names (not values!) → ask which names should be declared.

## Common failure recovery

- `validation_failed` → show errors verbatim, ask user to fix locally, do not push.
- `not_found` from `uploads create` → confirm `COURSE_ID` exists; do not silently retry.
- `entitlement_missing` on a buyer-side surface → suggest the right creator-side command.