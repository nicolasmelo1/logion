---
summary: Author, declare, upload, review, and publish a course safely.
---
# Creating Courses

A practical course bundle contains a manifest, lessons or instructions, skills,
examples, and tests. Keep bundles structured and inspectable. Declare required
capabilities in `course/capabilities.yaml`; publication requires a valid
declaration.

The creator flow is:

1. Create course metadata.
2. Scaffold and validate the capability manifest.
3. Upload an immutable version bundle.
4. Request publication review.
5. Read findings and feedback, then correct and upload a new version if needed.
6. Publish only after review approval.

Paid creators must complete Stripe Connect onboarding before cash-out. Course
pricing and publication changes require explicit creator approval. Do not claim
capabilities, integrations, or guarantees the bundle does not provide.

Use `logion courses --help`, `logion courses capabilities --help`, and
`logion courses publication --help` for the current command surface.
