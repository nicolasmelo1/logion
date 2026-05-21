# Safety and Approval

Confirmation gates and safety rules for the Logion Marketplace Companion.

## Confirmation-required actions

The following actions require explicit user approval before proceeding:

- `paid_checkout` — Any purchase or paid transaction.
- `install_new_capability` — Installing any capability not currently present.
- `update_paid_capability` — Updating a paid capability (may change price or
  terms).
- `permission_expansion` — Any action that expands the permissions of an
  installed capability.
- `publish_or_unpublish_course` — Publishing or unpublishing a course.
- `upload_new_course_version` — Uploading a new version of an existing course.
- `change_course_price` — Changing the price of any course.

## Local recall safety

- Local recall is read-only. It never executes commands.
- Recall results include `danger_flags` for commands that require elevated
  privileges or that modify state.
- Secrets, tokens, and credentials are masked or excluded from recall results.
- Confidence scores from recall never bypass confirmation gates.

## General safety rules

- Never auto-apply updates to paid capabilities.
- Never install capabilities without showing metadata and price first.
- Never publish course content without explicit user confirmation.
- Never include secrets, API keys, or tokens in packaged artifacts.
- Always validate manifests before packaging or uploading.