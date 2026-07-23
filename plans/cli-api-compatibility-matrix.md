<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# CLI/API Compatibility Matrix Implementation Plan

> **For Hermes:** Execute one concern per PR. Do not merge automatically.

**Goal:** Make API/CLI compatibility explicit, machine-readable, tested against candidate APIs, and safe for compatible old CLI releases.

**Architecture:** Keep `/health` as liveness only. Add an additive public `/v1/capabilities` endpoint that returns a typed compatibility envelope. The private exporter derives the public OpenAPI digest from the same canonical public-schema transform used for sync. The public CLI parses this metadata without making it mandatory for legacy APIs: it warns below the minimum CLI version, and fails only on a valid incompatible API major. Candidate-API CI runs the candidate CLI plus the declared oldest supported released CLI in isolated environments.

**Tech stack:** FastAPI/OpenAPI 3.1, Pydantic, Python packaging metadata, public CLI/SDK, GitHub Actions, local devrig.

---

## Decisions

- `api_major` is an explicit protocol decision, but CI requires an API-major change to carry the corresponding versioned path/migration decision.
- `contract_digest` is automatic: computed from canonical public OpenAPI bytes at runtime and checked against the exported artifact.
- `capabilities` stay explicit declarations because they are product guarantees, but CI validates their registry/schema and stable ordering.
- CLI release support is automatic from a versioned release manifest: the release workflow writes/validates the current CLI version, and CI rejects a release if the API compatibility manifest is stale. The minimum supported version is explicit support policy. It is preserved by default; a release may advance it only through an explicit `workflow_dispatch` choice naming the new minimum and an acknowledgement of the dropped range. If a candidate API cannot pass the declared oldest-supported CLI matrix, the release stops with an actionable compatibility-drift error rather than silently dropping support.
- Missing/malformed metadata is warning/informational only for the CLI. A valid API-major mismatch is the sole compatibility failure.


## Task 1: Factor canonical public OpenAPI rendering in the private API

**Files:**
- Create: `backend repository/packages/api/api/core/public_openapi.py`
- Modify: `backend repository/scripts/export_openapi.py`
- Test: `backend repository/packages/api/tests/test_openapi_public_contract.py`

1. Write failing tests proving exporter output and the shared helper produce byte-identical canonical public JSON and digest.
2. Move public-path pruning, schema pruning, normalization and render helpers from the script into importable API-core code without widening public paths.
3. Keep the script as the command wrapper and preserve current artifact output exactly.
4. Run focused export/OpenAPI tests and `make check-public-contract`.

## Task 2: Add the public capabilities endpoint in the private API

**Files:**
- Create: `backend repository/packages/api/api/capabilities/constants.py`
- Create: `backend repository/packages/api/api/capabilities/controllers/get_api_capabilities.py`
- Create: `backend repository/packages/api/api/capabilities/controllers/router.py`
- Modify: `backend repository/packages/api/api/main.py`
- Test: `backend repository/packages/api/tests/test_api_capabilities.py`
- Test: `backend repository/packages/api/tests/test_openapi_public_contract.py`

1. Add failing HTTP tests for anonymous success, schema shape, sorted capabilities, valid semver ordering, and absence of operational/sensitive fields.
2. Implement static API-owned values (`api_major=1`, minimum/current supported CLI versions, stable capabilities) and compute the digest from the live public OpenAPI schema using Task 1 helper.
3. Mount exactly `/v1/capabilities`; satisfy one-controller/one-route, local-schema, operation-id and router-boundary rules.
4. Prove `/health` remains unchanged, and public export exposes typed capabilities.

## Task 3: Export a versioned compatibility artifact and sync it

**Files:**
- Modify: `backend repository/scripts/export_openapi.py`
- Modify: `backend repository/Makefile`
- Generated public artifacts via sync only: `logion/contracts/openapi/v1.json`, generated SDK models/operations, `.generated-files.lock`
- Create through sync: `logion/contracts/api-compatibility.json`
- Test: private exporter tests and public artifact-lock tests

1. Have the private export command write `api-compatibility.json` beside the public OpenAPI target using the same metadata and digest as `/v1/capabilities`.
2. Ensure `--check-public` checks both artifacts and `--sync-public` copies both.
3. Merge private PR; use `automation/sync-openapi` to update the public artifacts. Never hand-edit locked generated files.
4. Run full contract audit against private main and the generated public candidate.

## Task 4: Add SDK and CLI compatibility behavior

**Files:**
- Add generated SDK surface only via Task 3 sync
- Create: `logion/packages/cli/cli/_compatibility.py`
- Modify: `logion/packages/cli/cli/commands/health/handlers.py`
- Modify: `logion/packages/cli/tests/test_cli_health.py`
- Create: `logion/packages/cli/tests/test_compatibility.py`

1. Add pure parsing/comparison tests first: valid SemVer, old compatible CLI warning, incompatible major error, malformed/missing metadata compatibility.
2. Use the capabilities SDK endpoint after normal health succeeds; preserve `health --json` stdout as parseable health JSON and send diagnostics to stderr.
3. Return nonzero only when `api_major != supported_major`; warn with `logion update` remediation when CLI is below the advertised minimum.
4. Do not add networking to parser startup, help/docs/update, or local-only commands.

## Task 5: Exercise release pairs in candidate-API CI

**Files:**
- Modify: private candidate/deploy workflow discovered during implementation
- Create or modify: `backend repository/scripts/test_cli_api_compatibility.py`
- Modify: public release workflow tests if applicable
- Test fixtures: private/public temporary isolated install fixtures

1. The release workflow defaults to preserving the declared minimum supported CLI and updates `current_cli_version` from the validated release tag/`pyproject.toml` version.
2. When a release operator intentionally drops an old CLI, require `workflow_dispatch` inputs selecting `advance-minimum`, naming the new minimum, and acknowledging the dropped range; reject inconsistent or missing input.
3. Start/deploy the candidate API and retrieve `/v1/capabilities`.
4. Install current CLI from the candidate public revision and `logion-cli==minimum_cli_version` in separate venvs.
5. For each pair set `LOGION_BASE_URL` to candidate, then run `logion health --json` and public listings discovery smoke calls.
6. Fail on wire/schema/non-2xx regressions for either supported CLI. If the oldest pair fails, emit an actionable compatibility-drift failure; never silently advance the minimum. Add an intentional mismatched-major fixture proving the documented failure path.
7. Keep release credentials out of logs and use local/devrig candidate endpoints for PR CI.

## Acceptance

- Private API tests, boundary tests, exporter checks and full audit pass.
- Sync PR is generated automatically and public generated-lock checks pass.
- Public CLI parser, health and compatibility tests pass.
- Candidate matrix proves current + oldest supported CLI against the candidate API.
- No internal, rollout, secret, source-tree or deployment metadata is exposed.
