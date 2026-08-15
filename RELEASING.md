# Releasing — Operator Runbook

This document describes how to cut, roll back, and yank Logion package releases.

## 1. Cut a release for logion-cli

```bash
# 1. Bump the version
make version-bump-cli

# 2. Build the manifest
make release-manifest

# 3. Verify the manifest
make release-manifest-check

# 4. Commit and tag
git add -A
git commit -m "release(cli): logion-cli vX.Y.Z"
git tag logion-cli-vX.Y.Z

# 5. Push
git push origin main --follow-tags
```

The CI pipeline publishes the wheel to PyPI and the manifest to GitHub Releases.

## 2. Cut a release for logion-client

```bash
make version-bump-client
make release-manifest
make release-manifest-check
git add -A
git commit -m "release(client): logion-client vX.Y.Z"
git tag logion-client-vX.Y.Z
git push origin main --follow-tags
```

## 3. Cut a release for the companion

```bash
make version-bump-companion
make release-manifest
make release-manifest-check
git add -A
git commit -m "release(companion): logion-companion vX.Y.Z"
git tag logion-companion-vX.Y.Z
git push origin main --follow-tags
```

## 3b. Cut a release for a harness plugin

Plugins under `plugins/` version independently of the CLI: they are
installed by the harness's own package manager, and a plugin fix should
not force a CLI release. They are deliberately **not** part of the
coordinated `make release`.

```bash
# Bump "version" in plugins/dsh-plugin/package.json, then:
(cd plugins/dsh-plugin && npm test && npm pack --dry-run)
git add -A
git commit -m "release(dsh-plugin): @logionsh/dsh-plugin vX.Y.Z"
git tag dsh-plugin-vX.Y.Z
git push origin main --follow-tags
```

The tag triggers `release-dsh-plugin.yml`, which refuses to publish when
the manifest version disagrees with the tag.

Verify from a real harness afterwards:

```bash
DSH_HOME="$PWD/.dsh" dsh plugin --profile default add @logionsh/dsh-plugin
```

## 4. Cutting a release candidate

Pre-release versions use the `-rc.N` suffix (e.g. `0.2.0-rc.1`).

```bash
# Manually bump the version in the package's pyproject.toml to the RC version
# then:
make release-manifest
make release-manifest-check
git add -A
git commit -m "release(cli): logion-cli v0.2.0-rc.1"
git tag logion-cli-v0.2.0-rc.1
git push origin main --follow-tags
```

RC releases are published to TestPyPI only. Promote to stable by removing the
suffix and following the normal release flow.

## 5. Emergency rollback

If a release introduces a critical defect:

1. **Do not delete the tag** — it is already public on PyPI/GitHub.
2. Bump a patch fix and release through the normal flow.
3. If no fix is ready immediately, add a note to `releases/CHANGELOG.md`
   marking the broken version as retracted.
4. Update `releases/manifest-stable.json` if the broken version needs to be
   flagged (add a `retracted: true` field in a future schema version, or
   document it in the changelog).

## 6. Yanking a PyPI release

```bash
twine yank logion-client X.Y.Z --reason "critical bug"
```

Yanking removes the release from the PyPI index but keeps the files available
for existing pinned installs. It is reversible:

```bash
twine yank logion-client X.Y.Z --reason "critical bug" --unyank
```

After yanking, rebuild the manifest so the entry reflects the yanked state and
commit the update.

## 7. Publishing to PyPI (one-time setup)

Each publishable package (`logion-cli`, `logion-client`) needs a Trusted
Publisher configuration on PyPI before the CI workflow can upload.

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new pending publisher:
   - **PyPI Project Name:** `logion-cli` (or `logion-client`)
   - **Owner:** `nicolasmelo1`
   - **Repository:** `logion`
   - **Workflow:** `release-cli.yml` (or `release-client.yml`)
   - **Environment name:** `pypi`
3. Submit. PyPI will verify the OIDC claim on the next matching tag push.
4. In the GitHub repo settings, create an Environment named `pypi`
   with required reviewers set to the maintainer team. This adds a
   human-approval gate on every PyPI publish.

After the one-time setup, pushing a version tag triggers the publish
workflow automatically:

```bash
git tag logion-cli-v0.1.0
git push origin logion-cli-v0.1.0
```

The release workflow (`.github/workflows/release-cli.yml` or
`release-client.yml`) verifies the tag matches the pyproject version,
builds sdist + wheel, validates with `twine check`, publishes to PyPI
via OIDC Trusted Publishing, and attaches the wheel, sdist, and
SHA256SUMS to the GitHub Release.

If the version already exists on PyPI, the publish step skips
(`skip-existing: true`) rather than failing.

## Release orchestration

The preferred release entrypoint is the **Release all Logion packages**
GitHub Actions workflow (`.github/workflows/release-all.yml`). It bumps
`logion-client`, `logion-cli`, and `logion-agent-companion` to the same
version, regenerates both release manifests, commits the release, creates
the package tags, and optionally publishes the first-party companion to the
Logion store.

Package publishing is GitHub Actions-owned:

- `logion-client-vX.Y.Z` triggers the client PyPI publisher.
- `logion-cli-vX.Y.Z` triggers the CLI PyPI publisher and npm wrapper
  publisher.
- `logion-companion-vX.Y.Z` triggers the companion bundle publisher.

### GitHub Actions release

1. Prepare smoke evidence:

   ```bash
   make release-smoke-input VERSION=X.Y.Z
   ```

   If `release-smoke-findings.md` does not exist yet, the command creates a
   template and exits. Fill it with real smoke evidence, then rerun the same
   command. On success, it validates the file and prints the base64 string for
   the workflow input.

3. Run the **Release all Logion packages** workflow with:
   - `version`: `X.Y.Z`
   - `smoke_findings_base64`: the output from `make release-smoke-input`
   - `publish_store`: enabled for first-party companion publication

The workflow is the single release entrypoint. It coordinates the repo
mutation and tag push; the pushed tags trigger the package-specific publisher
workflows.

### Local fallback

The same release path is exposed locally through Make targets for owner
fallback/debugging:

```bash
# Plan only — no mutations, safe to run anytime
make release-plan VERSION=X.Y.Z

# Validate without pushing
make release-dry-run VERSION=X.Y.Z

# Full release: preflight → bump → check → build → manifest →
# smoke gate → commit → tag → push → GitHub releases
make release VERSION=X.Y.Z

# Also publish the companion to the marketplace store
PUBLISH_STORE=1 make release VERSION=X.Y.Z
```

### Preconditions

- `main` is green and up to date with `origin/main`.
- `make ci-checks` passes.
- `make install-test` passes.
- `gh auth status` succeeds (release mode only).
- A release smoke findings file exists (release mode only).

### Smoke evidence

Before running `make release`, prepare and validate smoke evidence:

```bash
python scripts/release_smoke.py init --version X.Y.Z --out findings.md
# Run manual smoke per the release-smoke-checklist, then:
python scripts/release_smoke.py check findings.md --version X.Y.Z
```

At least three harnesses must be recorded (including Codex and Claude
Code). Every release-blocker finding must have a linked issue URL.

### Store publication

Store publication is opt-in via the workflow's `publish_store` input or
local `PUBLISH_STORE=1`. The store publisher uploads the companion bundle
as a new course version through the public CLI, requests publication review,
and stops before human approval:

```bash
PUBLISH_STORE=1 make release VERSION=X.Y.Z
# or directly:
make release-store VERSION=X.Y.Z
```

### Smoke installer before announcement

```bash
TMP_HOME="$(mktemp -d)"
HOME="$TMP_HOME" LOGION_INSTALL_MANIFEST_URL="<manifest-url>" sh scripts/install.sh --dry-run
```

For PowerShell, run the Pester suite and one manual `-DryRun` install.

### Rollback

- PyPI: yank the broken version; do not delete history.
- npm: deprecate the broken version.
- GitHub Release: keep tags immutable; publish a patch tag.
- Manifest: update stable/latest through reviewed PR.
- Store: do not unpublish; upload a new version with a fix.
