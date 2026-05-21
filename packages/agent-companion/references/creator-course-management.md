# Creator Course Management

Agent-assisted workflows for creating, updating, uploading, and publishing
Logion courses.

## Create course

1. Gather course metadata: title, description, capabilities, pricing.
2. Generate or validate the course manifest (`capabilities.yaml`).
3. Create the course directory with required files (SKILL.md, references,
   course/manifest).
4. Validate package structure with `python scripts/package_skill.py --check`.

## Update course

1. Inspect the existing course manifest.
2. Propose changes based on user instructions.
3. Validate updated manifest and files.
4. Never auto-upload or auto-publish changes.

## Upload new version

1. Package the course using `python scripts/package_skill.py`.
2. Upload the package through Logion CLI (`logion courses upload`).
3. Requires explicit user confirmation before upload.

## Publish / unpublish

1. Request publication review through Logion CLI.
2. Wait for approval status.
3. Never publish or unpublish without explicit user confirmation.

## Pricing changes

1. Show current and proposed pricing.
2. Require explicit confirmation.
3. Apply through Logion CLI after confirmation.

## Local recall for creators

Local recall can suggest previously successful authoring/upload workflows, but
recall results are read-only and cannot upload, publish, or change pricing by
themselves.