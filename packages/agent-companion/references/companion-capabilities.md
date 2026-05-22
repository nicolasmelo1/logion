# Companion capabilities

Semantic capability list for the Logion Marketplace Companion. These are
the user-facing actions the companion guides an agent through. They are
distinct from the security manifest in
[`course/capabilities.yaml`](../course/capabilities.yaml), which only
declares tools, network, filesystem, secrets, and approval policy.

The companion covers two audiences:

- **Capability consumers** — agents and users who want to discover,
  inspect, install, update, and load Logion-delivered capabilities on
  demand.
- **Course creators and operators** — authors who want to create,
  update, upload, submit, review, publish, and maintain courses through
  the public Logion CLI.

## Consumer capabilities

| ID | Surface | Description |
|---|---|---|
| `logion.recall.search` | `logion recall search` | Find installed capabilities, local workflows, and proven commands before reaching for the marketplace. Read-only. |
| `logion.marketplace.search` | `logion listings search` | Find candidate courses or capabilities when local recall is insufficient. |
| `logion.course.inspect` | `logion courses get`, `logion courses versions get` | Review price, permissions, version metadata, and reviews before any install. |
| `logion.skill.install` | `logion skills install` | Install one approved skill or course artifact after explicit user approval. |
| `logion.skill.update` | `logion skills updates`, `logion skills update` | Detect updates, surface integrity status, and apply changes only when policy allows. |

## Creator/operator capabilities

| ID | Surface | Description |
|---|---|---|
| `logion.course.author` | `logion courses create`, `logion courses capabilities scaffold`, `logion courses capabilities validate`, `logion courses uploads`, `logion courses publication` | Guide authors through course metadata, manifests, versions, uploads, and publication requests. |
| `logion.course.operate` | `logion notifications`, `logion course-reviews`, `logion courses versions`, `logion reports` | Help creators inspect feedback, notifications, reviews, versions, and update requirements after publishing. |

## Confirmation rules

The following actions always require explicit user approval before they
happen, regardless of recall confidence:

- `paid_checkout`
- `install_new_capability`
- `update_paid_capability`
- `permission_expansion`
- `publish_or_unpublish_course`
- `upload_new_course_version`
- `change_course_price`

These are enforced by the agent following SKILL.md guidance and by
`logion skills update` refusing to overwrite a locally modified
installation without `--force`.
