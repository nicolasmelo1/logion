# Release Bundle Layout

> **Frozen contract** — this document defines what is inside the
> Logion Marketplace Companion release tarball and what the receiving
> side can assume. Changes that break the rules here require a
> major-version bump of the companion.

---

## 1. Filename grammar

```
logion-marketplace-companion-<version>.tar.gz
```

`<version>` is a SemVer 2.0 string (e.g. `0.1.0`, `1.2.3`).

The filename is the sole distribution artifact. Sidecar files
(`SKILL.md`, `manifest.json`, `SHA256SUMS.txt`) are also uploaded
to the same GitHub Release for convenience, but the tarball is the
authoritative bundle.

---

## 2. Top-level directory grammar

The tarball extracts to a single top-level directory:

```
logion-marketplace-companion-<version>/
```

No other top-level entries are permitted. The `<version>` in the
directory name **must** match the `<version>` in the filename and in
`manifest.json`.

---

## 3. Required files

All paths are relative to the top-level directory
`logion-marketplace-companion-<version>/`.

| Path | Stability |
|---|---|
| `SKILL.md` | **stable** — removing or renaming is a major-version bump |
| `manifest.json` | **stable** — schema_version tracks format changes |
| `LICENSE` | stable |
| `README.md` | stable |
| `course/capabilities.yaml` | **stable** — removing or renaming is a major-version bump |
| `references/account-and-identity.md` | stable |
| `references/admin-operations.md` | stable |
| `references/bounties.md` | stable |
| `references/course-review-queue.md` | stable |
| `references/creator-course-management.md` | stable |
| `references/notifications-and-reports.md` | stable |
| `references/credits-and-payments.md` | stable |
| `references/referrals.md` | stable |
| `references/troubleshooting.md` | stable |

**SKILL.md content sections:**

The companion `SKILL.md` may gain content sections over time (e.g.
the "After using a Logion course" auto-review prompt). Adding a new
section is an additive change and does **not** require a major-version
bump. Removing or renaming a section that an installed agent relies on
for behavioral guidance would require a major-version bump.

**Stability annotations:**

- **stable** — the file may gain content but the path and purpose will
  not change within a major version. Removing a reference file requires
  a major-version bump.
- **stable with major-bump on rename** — changes to the path or
  structure of `SKILL.md` frontmatter fields that the runtime consumes
  (e.g. `safety.requires_confirmation`) require a major-version bump.

The `course/` and `references/` directories are required but may
contain only the files listed above.

---

## 4. Forbidden files

The following must **not** appear anywhere in the bundle:

- `__pycache__/` or `.pyc` — build artifacts
- `tests/` — developer-only; not shipped
- `evals/` — developer-only; not shipped
- `scripts/` — build machinery; not shipped
- `pyproject.toml` — not a pip package
- `node_modules/` — not applicable
- `.git/`, `.venv/`, `.pytest_cache/`, `.mypy_cache/`,
  `.ruff_cache/` — VCS and tool artifacts

In general, anything not listed in §3 is forbidden.

---

## 5. `manifest.json` schema

`manifest.json` lives at the bundle root and describes the bundle
itself. It is **distinct** from the workspace release manifest — this
one is self-contained.

Schema (schema_version: 1):

```json
{
  "schema_version": 1,
  "bundle_kind": "logion-marketplace-companion",
  "version": "<SemVer string>",
  "generated_at": "<ISO-8601 Z timestamp>",
  "git_commit": "<short SHA or 'unknown'>",
  "minimum_cli_version": "<SemVer string>",
  "skill_name": "logion-marketplace-companion",
  "skill_md_sha256": "<hex sha256 of SKILL.md>",
  "references": [
    {
      "path": "references/<name>.md",
      "sha256": "<hex sha256>",
      "size": <byte count>
    }
  ],
  "capability_manifest": {
    "path": "course/capabilities.yaml",
    "sha256": "<hex sha256>"
  },
  "safety": {
    "requires_confirmation": [
      "spend_credits",
      "top_up_credits",
      "fund_bounty",
      "share_referral_link",
      "creator_cash_out",
      "install_new_capability",
      "update_paid_capability",
      "permission_expansion",
      "publish_or_unpublish_course",
      "upload_new_course_version",
      "change_course_price"
    ]
  }
}
```

**Field semantics:**

- `schema_version` — must be `1`. Increment only when the shape of
  the manifest changes in a way the consumer must handle.
- `bundle_kind` — always `logion-marketplace-companion`.
- `version` — matches the `<version>` in filename and directory name.
- `generated_at` — UTC ISO-8601 with `Z` suffix.
- `git_commit` — short SHA of the commit the bundle was built from.
- `minimum_cli_version` — the earliest CLI version that can install
  this bundle. Computed from the workspace's
  `packages/cli/pyproject.toml` at build time.
- `skill_md_sha256` — sha256 of the `SKILL.md` file contents.
- `references` — one entry per reference file, sorted by path.
  Each entry carries `path`, `sha256`, and `size` (in bytes).
- `capability_manifest` — path and sha256 of
  `course/capabilities.yaml`.
- `safety.requires_confirmation` — the list of actions requiring
  explicit user approval, sourced from `SKILL.md` frontmatter.

**Serialization rules (for determinism):**

- JSON keys sorted alphabetically.
- 2-space indentation.
- Trailing newline (`\n`).
- Timestamps in ISO-8601 `Z` format.

---

## 6. Versioning rules

- The bundle version follows SemVer 2.0 independently of the CLI
  version.
- Compatibility between bundle and CLI is expressed exclusively via
  `minimum_cli_version` in the manifest. The CLI refuses to install a
  bundle whose `minimum_cli_version` exceeds the running CLI's version.
- The version string appears in three places that must agree:
  1. Tarball filename (`logion-marketplace-companion-<version>.tar.gz`)
  2. Top-level directory inside the tarball
     (`logion-marketplace-companion-<version>/`)
  3. `manifest.json` `"version"` field

---

## 7. Stability promise

Within a major version:

- **No reference file will be removed.** Adding a new reference file
  is a minor-version bump.
- **Renaming `SKILL.md`** is a major-version bump.
- **Renaming or removing frontmatter fields that the runtime consumes**
  (`safety.requires_confirmation`, `version`, `name`) is a
  major-version bump.
- **Changing `manifest.json` `schema_version`** signals a breaking
  change to the consumer contract. Consumers must handle unknown
  schema versions by refusing to install.
- **The `LICENSE` file will remain MIT.**
- **Adding new fields to `manifest.json`** is a minor-version bump;
  consumers must ignore unknown fields (open content model).