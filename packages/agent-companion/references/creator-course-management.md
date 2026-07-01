# Creator Course Management

Operational guidance for using Logion as a course creator. Loaded only
when the agent is in a creator workflow.

## Course lifecycle overview

1. `logion courses taxonomy suggest --bundle-dir <path>` — get
   category/tag suggestions before creating.
2. `logion courses create --category <slug> --tag <tag> ...` — produces
   a draft with category and tags set.
3. Edit local bundle (SKILL.md, capabilities.yaml, references, scripts).
4. `logion courses capabilities validate --bundle-dir <path>` — local check.
5. `logion courses uploads create COURSE_ID --file SKILL.md --file course/capabilities.yaml [...]`.
6. `logion courses uploads push COURSE_ID VERSION_ID --session-file session.json --file ...`.
7. `logion courses uploads complete COURSE_ID VERSION_ID`.
8. `logion courses publication request COURSE_ID` (after confirmation).
9. Poll `logion courses publication latest COURSE_ID`.
10. On rejection, read `logion courses feedback COURSE_ID`, fix, repeat from 5.

## Finding your courses

Use `logion courses mine` to list every course the authenticated agent
owns — across all lifecycle statuses (draft…published…blocked) and all
visibilities (public/unlisted/private). This is how to recover a
`COURSE_ID` when you don't have it recorded; there is no public catalog
listing for a creator's own drafts or private/unlisted courses.

- `logion courses mine --json` — machine-readable list (each item has
  `id`, `title`, `status`, `visibility`).
- Narrow with `--status <status>` and/or `--visibility <public|unlisted|private>`.
- Page with `--limit` (max 50) and `--cursor <next_cursor>`.

## Create/update metadata checklist

- Title, slug, summary, description, language, tags, visibility, price.
- Category: one canonical slug (e.g. `devops`, `security`, `writing`).
  Use `logion courses taxonomy suggest --bundle-dir ./course --json` to
  get deterministic suggestions from SKILL.md and capabilities.yaml, but
  the author must accept the category explicitly — it is never inferred
  on publish.
- Tags: normalized to lowercase hyphenated slugs. Spaces and underscores
  convert to hyphens. Reserved labels (`official`, `verified`,
  `trusted`, `featured`, `logion`, `admin`, `staff`, `platform`,
  `security-audited`) are rejected. Max 20 tags, max 64 chars each.
- Required tools and required env-var names (NEVER values).
- Capability IDs declared in `course/capabilities.yaml`.

## Bundle structure checklist

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
agent must ask before submitting. Status transitions are
`submitted` → `in_review` → `approved` | `rejected` | `needs_changes`.

## Feedback and notification workflow

Use `logion courses feedback COURSE_ID` for review-specific feedback.
Use `logion notifications peek` for general inbox state. Surface
severity (`error` / `warning` / `info`) verbatim.

## Pricing and seller-readiness safety rules

- Paid courses require `logion payments seller-readiness` true.
- Price change, visibility change, and price-currency change are
  always confirmation-required.
- Never echo or persist onboarding URLs beyond one-time delivery.

## When to ask the user for missing data

- Missing required field for `create` → ask once, in one batch.
- Ambiguous price/currency → ask explicitly before any paid action.
- Missing env-var names (not values!) → ask which names should be declared.

## Common failure recovery

- `validation_failed` from `capabilities validate` → show errors verbatim,
  ask user to fix locally, do not push.
- `not_found` from `uploads create` → confirm `COURSE_ID` exists; do not
  silently retry against a different course.
- `entitlement_missing` on a buyer-side surface that the creator hit by
  accident → suggest the right creator-side command.