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

## 8. Cutting a release end-to-end

1. Confirm `main` is green: `gh run list --branch main --limit 3`.
2. Run python-semantic-release locally to compute the next version
   for the package you want to release:

       uv run semantic-release version -c packages/cli/pyproject.toml --print

3. Push the tag created locally:

       uv run semantic-release version -c packages/cli/pyproject.toml
       git push --follow-tags

4. The `release-cli.yml` workflow runs.  Approve the `pypi`
   environment gate when prompted.
5. After `release-cli.yml` completes, `release-npm.yml` triggers
   automatically (via workflow_run).  Approve the `npm` gate.
6. `regenerate-manifest.yml` opens a PR with the new manifest.
   Review and merge.
7. `release-conformance.yml` runs after the manifest merge; if it
   fails, see §emergency-rollback below.

### Cutting a release candidate

1. `git checkout -b rc/cli-0.3.0` (off `main`).
2. `uv run semantic-release version -c packages/cli/pyproject.toml --prerelease`.
3. `git push --follow-tags`.
4. `release-testpypi.yml` publishes to TestPyPI only.

### Emergency rollback

If a release is broken (smoke tests failed; user reports breakage):

1. PyPI: yank the broken version manually
   (`pypi.org/manage/project/logion-cli/release/X.Y.Z/`); document
   why in the project's PyPI page.
2. npm: `npm deprecate @logion/cli@X.Y.Z "broken; use X.Y.W"`.
3. GitHub Release: do NOT delete the tag.  Instead, push a
   higher-version patch tag with the fix; the manifest regenerates
   to point at the new latest.
4. The installer redirect always reads the latest manifest, so a
   re-released patch heals new installs automatically.

Never `git push --force` a release tag.  If a tag was wrong, push a
fresh patch tag; old installs survive because their pin still
resolves.