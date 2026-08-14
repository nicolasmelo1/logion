# Native acquisition dogfood record

Date: 2026-08-14 (re-run against a live devrig after the acquisition path
was fixed end to end; supersedes the earlier record whose native leg used a
floating `skills@latest` spec that is no longer accepted)

Environment: local devrig — PostgreSQL 17 and MinIO in Docker, the Logion
API on `http://localhost:8000`, `node` v22.22.1, `npx`, and the public CLI
run from this repository.

## Hosted Logion bundle

- Resource: `ee3f2e01-d42d-440b-abca-be3a5919a18e`
- Version: `8cc2ac00-9e44-4fda-9f9e-c2e2ae461eea`
- Channel: `logion_bundle`
- Content digest: `sha256:7eb211cfa7578b989209800e4be24b24cb4dcf321a8adce18bbfd3e409b12d01`
- Harness/scope: Codex, repository root
- Verification: `exact`
- Installed paths:
  - `.agents/skills/hosted-code-review/.bundle-manifest`
  - `.agents/skills/hosted-code-review/LICENSE`
  - `.agents/skills/hosted-code-review/SKILL.md`
  - `.agents/skills/hosted-code-review/course/capabilities.yaml`

The dry-run was inspected first and reported the channel, digest, expected
permissions (`network=False`), the `download` operation, and
`verification expectation: exact` — the same distribution the executable
path then used.

Evidence: presigned MinIO download, per-file size and SHA-256 checks, and
client recomputation of the backend's aggregate digest over the object keys
the manifest now exposes as `aggregate_key`.

## Native `npx skills` acquisition

```text
logion resources acquire c8f0a79d-4c92-4cc5-b51c-5b5df35dd757 \
  --harness codex --scope repo-root --channel npx_skills \
  --no-dry-run --yes --json
```

Logion delegated to the server-provided argv, executed without a shell:

```text
npx skills@1.5.22 add vercel-labs/skills --skill find-skills
```

- Source: `vercel-labs/skills`, skill `find-skills`
- Native manager: `skills@1.5.22` (an immutable pin; a dist-tag is refused)
- Manager state: `skills-lock.json`, left exactly as the manager wrote it
- Manager content digest:
  `sha256:b146008599c31057cef1c145774cea5d5afb30e8f43fa802e47a4b461419aaaf`
- Installed path: `.agents/skills/find-skills`
- Verification: `unverified`

The verification level is honest rather than flattering: the lockfile
records a `computedHash` but no commit, and a content hash is not an
immutable revision, so this acquisition does not claim `source_revision`.

## Inventory and reconciliation

```text
logion resources inventory --harness codex --scope repo-root --json
logion resources reconcile --from skills --scope repo-root --json
```

- Inventory listed the hosted install from its receipt as `exact` /
  `validated-local-receipt`, in `repo-root` scope only.
- Reconcile matched two entries and reported zero drifted, unresolved, or
  ambiguous: the receipt Logion wrote, and the manager's own
  `skills-lock.json` entry resolved back to its catalog resource
  (`vercel-labs/skills` → `canonical_source`). Both normative directions.
- Re-running the hosted acquisition returned the same `installation_id`
  and left no `.logion-incoming` or `.logion-backup` directory behind.
- Appending a line to an installed file moved it out of `matched` and into
  `drifted` with `digest-mismatch:.agents/skills/hosted-code-review/SKILL.md`.
- No telemetry, review, or manager-state rewrite was performed.

## Product friction found

Everything below was found by doing this, not by reading code:

- Publishing a course never registered a resource projection, so no hosted
  course had a `logion_bundle` distribution and every acquisition plan
  answered `resource_distribution_unavailable`.
- The download manifest omitted the object keys the version's pinned
  `content_hash` is aggregated over, so a client could verify each file but
  never reproduce the digest it was promised.
- The indexed bundle upload could be performed but never completed: the
  presigned URL signed only the content type, while completion required
  sha256 metadata on the object.
- The `npx_skills` plan emitted `skills@latest` with no tested version, and
  passed `gh:owner/repo@sha` where the CLI expects `owner/repo --skill name`.
