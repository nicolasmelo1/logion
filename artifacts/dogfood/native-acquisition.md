# Native acquisition dogfood record

Date: 2026-08-14

## Hosted Logion bundle

- Resource: `822e3a53-183d-4791-a2c0-9f127ff88cf8`
- Version: `3bebade9-17bf-4a21-8095-da5048817cc3`
- Distribution: `23f1ccc9-8834-453b-a985-fdfb016b2051`
- Channel: `logion_bundle`
- Content digest: `sha256:1dcfe83b5f89ab11b6c0c00ec0a89ee6f1ed3727019b152f383a2fead42d92f3`
- Harness/scope: Codex, repository root
- Verification: `exact`
- Installed paths:
  - `.agents/skills/course/.bundle-manifest`
  - `.agents/skills/course/LICENSE`
  - `.agents/skills/course/SKILL.md`
  - `.agents/skills/course/course/capabilities.yaml`
- Evidence: presigned MinIO download, per-file size/SHA-256 checks, and client recomputation of the backend aggregate digest.

## Native `npx skills` acquisition

Executed in a fresh temporary Git repository:

```text
npx --yes skills@latest add vercel-labs/skills --skill find-skills
```

Acquired through Logion with:

```text
logion resources acquire 4dad2e8e-534a-445a-b516-27132ac24d09 \
  --version 7eefbf54-50cb-4586-aef3-00fa8e353216 \
  --harness codex --scope repo-root --channel npx_skills \
  --no-dry-run --yes --json
```

- Resource: `4dad2e8e-534a-445a-b516-27132ac24d09`
- Version: `7eefbf54-50cb-4586-aef3-00fa8e353216`
- Distribution: `39b37508-2783-4ca3-b6c9-5ce01bb9e8b4`
- Source: `vercel-labs/skills`
- Skill: `find-skills`
- Native manager: `skills@latest` (see follow-up below)
- Manager state: `skills-lock.json`, `computedHash=b146008599c31057cef1c145774cea5d5afb30e8f43fa802e47a4b461419aaaf`
- Installed path: `.agents/skills/find-skills`
- Verification: `source_revision` using the manager's immutable computed hash

## Inventory and reconciliation

Executed against the same fresh repository:

```text
logion resources inventory --harness codex --scope repo-root --json
logion resources reconcile --from skills --scope repo-root --json
```

Observed outcome:

- Inventory found `find-skills` in `repo-root` scope without global installation.
- Reconciliation matched `vercel-labs/skills` to resource `4dad2e8e-534a-445a-b516-27132ac24d09` and version `7eefbf54-50cb-4586-aef3-00fa8e353216`.
- No reinstall, deletion, upload, telemetry, or manager-lock rewrite was performed by reconciliation.
- A repeated acquire resolved to the same installation identity.

## Bounded use

The installed bundle was inspected through its native Codex skill location. No usage report or review was submitted for the ownerless indexed skill.

## Follow-up

The `npx skills` acquisition above ran before the adapter required an
immutable manager pin. It recorded a floating `skills@latest` spec, which
is no longer accepted: the adapter now refuses a dist-tag and derives
`manager_version` from the pinned `skills@x.y.z` it executes, and it reads
the lockfile through the strict name-keyed parser. This leg must be re-run
against a pinned distribution before it counts as evidence.
