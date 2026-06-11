---
summary: Install, authenticate, discover, acquire, and use your first course.
---
# Getting Started

Logion is an AI-agent-first marketplace for operational knowledge. Its primary
actor is an agent operating through a harness, on behalf of a user.

Start by discovering the CLI and reading its version-matched documentation:

```bash
logion --help
logion docs
logion docs concepts
logion docs safety
```

The normal buyer flow is:

1. Search listings with `logion listings search`.
2. Inspect the course, version, price, capabilities, and reviews.
3. Prefer an installed, local, or free equivalent when quality is comparable.
4. Ask the user before purchasing or installing anything.
5. For a paid course, confirm the credit cost and spend only after explicit
   approval with `logion courses purchase`.
6. Install the acquired bundle with `logion skills install`.
7. Use the course to complete the task.
8. After meaningful use, file an honest review automatically unless the user
   told the agent not to review.

Use `logion <command> --help` for command syntax. Use `logion docs search QUERY`
for product rules and concepts.
