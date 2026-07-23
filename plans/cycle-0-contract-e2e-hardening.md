<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Cycle 0: Contract, Compatibility, and E2E Hardening

> **For Hermes:** Execute one concern per PR. Do not merge automatically. Complete the contract gate before resuming feature work or adding an install path for indexed artifacts.

**Goal:** Make the public API contract, SDK, CLI, release artifacts, and proving-ground scenarios verifiably compatible so discovery, publishing, installation, updates, and the Phase 15.1–15.8 flows cannot silently regress.

**Architecture:** Treat the checked-in public OpenAPI schema as the compatibility baseline for `/v1`. The private API may add optional fields, optional parameters, new operations, and new response status codes only when they preserve every previously supported request and response contract. The contract-audit package compares the candidate export against both the public generated surface and a committed compatibility baseline. Agent proving ground exercises the supported path against a real devrig with deterministic seeded data and assertions based on observed effects.

**Tech stack:** FastAPI/OpenAPI 3.1, Pydantic, SQLAlchemy/Alembic, public Python SDK/CLI, contract-audit Python package, agent-proving-ground scenarios, GitHub Actions.

---

## Baseline audit — 2026-07-22

The full audit was run against both the active implementation branches and independent `main` worktrees.

| Scope | Result | Finding |
|---|---|---|
| `main` public `3824c72` vs private `7fd5ecd` | blocked | `search_listings.include_indexed` default is `false` in `logion/contracts/openapi/v1.json` and `true` in the private export. |
| Active public `ee72287` vs private `dddac6f` | blocked | Same default drift plus four private PR #142 admin platform-bounty operations missing from the public generated contract. |
| Both | blocked | Audit labels `RedeemSetupTokenResponse.api_key` as a forbidden response field although this endpoint intentionally delivers a newly minted, single-use credential once. The policy has no explicit, narrowly-scoped one-time-secret exception model. |
| Audit runner | gap | A clean detached-worktree audit required creating public/private venvs manually; `make contract-audit` bootstraps the primary worktrees rather than the `PUBLIC_REPO`/`PRIVATE_REPO` arguments. |

The missing admin operations are expected until the reviewed private PR is merged and its `automation/sync-openapi` PR is merged. They must not be copied into a handwritten public branch.

The current agent-proving-ground suite has 108 passing tests, but its strongest coverage is still scripted execution with `MockApiAdapter`. The existing GitHub bounty scenario is manual and depends on externally supplied IDs. Green harness tests therefore do not yet prove the real CLI → API/devrig → observable-state journeys required below.

## Non-negotiable invariants

1. Existing `/v1` operations, paths, methods, auth schemes, request fields, response status codes, and response fields are never removed or narrowed.
2. Existing request fields never become required, change wire type/format, lose accepted enum values, or gain stricter semantics within `/v1`.
3. Existing response fields never disappear, become required when previously optional, change type/nullability, or lose enum values within `/v1`.
4. New `/v1` operations and optional fields are additive. A destructive change requires a new `/v2` operation family and explicit migration/deprecation documentation.
5. A CLI release declares the API contract range it was generated/tested against. The deployed API continues to accept every supported released CLI range; the release pipeline proves the oldest supported CLI and current CLI against the candidate API.
6. Indexed discovery is not equivalent to a reviewed Logion bundle. No indexed artifact becomes purchasable, entitlement-backed, or silently executable because it was discovered or scanned.
7. A direct-source install is only possible after explicit human confirmation of immutable source coordinates, source URL, content hash where available, disclosed verification state, and declared non-Logion trust boundary.

## Workstream A — make contract audit authoritative

### Task A1: Make audit worktree-aware

**Files:**
- Modify: `canonical maintainer workspace/scripts/bootstrap.sh`
- Modify: `canonical maintainer workspace/Makefile`
- Test: `canonical maintainer workspace/packages/contract-audit/tests/unit/test_cli_smoke.py`

1. Add a bootstrap mode that receives `PUBLIC_REPO` and `PRIVATE_REPO` and creates/synchronizes venvs in those exact paths.
2. Add a regression test that invokes the audit against two temporary repositories and proves no primary-worktree path is assumed.
3. Run:
   ```bash
   make contract-audit-test
   make contract-audit PUBLIC_REPO=<temporary-public> PRIVATE_REPO=<temporary-private>
   ```
4. Commit: `fix(contract-audit): bootstrap requested repository paths`.

### Task A2: Separate intentional one-time secret delivery from accidental leakage

**Files:**
- Modify: `canonical maintainer workspace/packages/contract-audit/policy/sensitive-fields.yaml`
- Modify: `canonical maintainer workspace/packages/contract-audit/contract_audit/security.py`
- Modify: `canonical maintainer workspace/packages/contract-audit/contract_audit/models.py`
- Test: `canonical maintainer workspace/packages/contract-audit/tests/unit/test_security.py`
- Test: `backend repository/packages/api/tests/test_setup_tokens.py`

1. Write failing policy tests: a generic `api_key` in a response remains critical; only `redeem_setup_token` may return the single-use value; logging, recall, error payloads, and persisted response models may never contain it.
2. Implement an operation/status/schema-scoped exception with mandatory reason, owner, expiry/review date, and test reference. Do not add a global allowlist for `api_key`.
3. Add a private endpoint test proving the value is delivered only in the intended successful redemption response and cannot be retrieved after redemption.
4. Run audit security and setup-token tests.
5. Commit: `fix(contract-audit): model one-time credential delivery`.

### Task A3: Enforce additive `/v1` compatibility against a committed baseline

**Files:**
- Create: `canonical maintainer workspace/packages/contract-audit/contract_audit/compatibility.py`
- Modify: `canonical maintainer workspace/packages/contract-audit/contract_audit/cli.py`
- Modify: `canonical maintainer workspace/packages/contract-audit/contract_audit/models.py`
- Create: `canonical maintainer workspace/packages/contract-audit/tests/unit/test_compatibility.py`
- Create: `canonical maintainer workspace/packages/contract-audit/policy/api-compatibility.yaml`
- Modify: `backend repository/.github/workflows/pr-safety.yml`
- Modify: `logion/.github/workflows/pr-safety.yml`

1. Export the merge-base public schema for every API-affecting PR, normalized with the same public-pruning rules as the current schema.
2. Add finding codes for removed operation, method/path change, auth narrowing, requiredness tightening, type/format/nullability change, enum-value removal, request-field removal, response-field removal, response-status removal, and changed default that alters omitted-request behavior.
3. Permit only additions: new operation, optional request field, optional response field, enum expansion, and additional response status.
4. Add fixture-driven tests for every forbidden mutation and every permitted additive mutation.
5. Run the compatibility check in private API PR Safety before contract export/sync. Run it in public PR Safety for public contract changes.
6. Commit: `feat(contract-audit): reject destructive v1 changes`.

### Task A4: Repair the current contract drift through the automation boundary

**Files:**
- Private: `backend repository/packages/api/api/listings/controllers/search_listings.py` (already has `include_indexed=True`; verify only)
- Generated public artifacts: automation PR only (`contracts/openapi/v1.json`, generated operations/models, `.generated-files.lock`)
- Public handwritten follow-up: only after generated sync lands

1. Merge private PR #142 only after human approval.
2. Review the resulting `automation/sync-openapi` PR: it must contain all four platform-bounty operations and the `include_indexed=true` default, with no handwritten changes.
3. Verify generated SDK and contract locks via `make ci-checks` in the public repo.
4. Rebase any CLI branch on the merged automation output before adding handwritten resource/CLI code.

## Workstream B — release/API/CLI compatibility

### Task B1: Define supported CLI/API compatibility metadata

**Files:**
- Create: `logion/contracts/api-compatibility.json` (generated through the same automation path)
- Modify: `logion/packages/cli/cli/_versioning.py`
- Modify: `logion/packages/cli/cli/_config.py`
- Modify: private health/capabilities controller discovered during implementation
- Test: `logion/packages/cli/tests/test_version.py`
- Test: `backend repository/packages/api/tests/test_openapi_public_contract.py`

1. Define a machine-readable API compatibility document with `api_major`, `minimum_supported_cli`, `current_cli`, deprecation windows, and contract digest.
2. Expose the API major/version/digest from a non-sensitive health/capabilities response.
3. Have the CLI warn (not fail) when it is below the minimum supported version, fail closed only for incompatible API majors, and include remediation through `logion update`.
4. Pin the compatibility metadata to the coordinated release manifest rather than inferring it from package version strings.
5. Commit independently in the generated-contract automation and handwritten CLI PRs.

### Task B2: Exercise supported release pairs

**Files:**
- Create: `logion/scripts/test_cli_api_compatibility.py`
- Modify: `logion/.github/workflows/pr-safety.yml`
- Modify: `logion/.github/workflows/release-all.yml`
- Test fixtures: `logion/tests/fixtures/cli_api_compatibility/`

1. Build a matrix from the release manifest: current CLI + candidate API and oldest supported CLI + candidate API.
2. Execute discovery, course retrieval, publishing preflight, purchase/install preflight, and update-check calls through each released CLI wheel against the candidate devrig API.
3. Fail CI when a supported old CLI receives a wire incompatibility, schema validation error, changed required parameter, or unexpected non-2xx response.
4. Test that an intentionally unsupported CLI gets the documented upgrade warning.

### Task B3: Make CLI update reproducible

**Files:**
- Modify: `logion/packages/cli/cli/commands/update.py` and its helpers discovered by the existing tests
- Modify: `logion/packages/cli/tests/test_cli_update.py`
- Modify: `logion/scripts/install_test/` fixtures/helpers
- Test: `logion/packages/agent-proving-ground/tests/integration/test_cli.py`

1. Cover dry-run, no-op/current version, upgrade, interrupted download, checksum failure, rollback, and post-update `--version`/`health` verification.
2. Ensure update preserves user config and installed-skill state across a CLI version change.
3. Add a proving-ground phase using the installer fixture, never the live production installer.

## Workstream C — proving-ground E2E matrix

### Task C1: Deterministic catalog fixture with more than 100 mixed records

**Files:**
- Create: private devrig seed helper under `backend repository/packages/api/api/scripts/`
- Create: `logion/packages/agent-proving-ground/agent_proving_ground/scenarios/builtin/listings_pagination.yaml`
- Create: `logion/packages/agent-proving-ground/tests/integration/test_listings_pagination.py`
- Modify: `logion/packages/agent-proving-ground/agent_proving_ground/api_adapters/_queries.py`

1. Seed at least 120 published and indexed records, with deliberately interleaved timestamps, equal sort keys, exact query matches beyond page one, and one claimed record excluded by contract.
2. Test every supported sort across pages, no duplicate IDs, no omitted IDs, cursor mismatch rejection, indexed-only and published-only filters, and a query whose exact match appears after the first physical source page.
3. Run against `local-devrig`; mock-only tests do not satisfy this requirement.

### Task C2: Publishing E2E as a release gate

**Files:**
- Modify: `logion/packages/agent-proving-ground/agent_proving_ground/scenarios/builtin/marketplace_loop.yaml`
- Modify: `logion/packages/agent-proving-ground/tests/integration/test_marketplace_loop.py`
- Modify: API assertions under `logion/packages/agent-proving-ground/agent_proving_ground/assertions/api.py`

1. Preserve the existing creator → upload → request review → admin approval sequence.
2. Assert the exact created course/version/manifest belongs to the run, is publicly searchable, is purchasable after approval, and retains a stable capability disclosure.
3. Add negative assertions for draft and `human_review` courses being unavailable to buyers before approval.

### Task C3: Phase 15.1–15.8 scenario coverage

**Files:**
- Create scenario YAML files under `logion/packages/agent-proving-ground/agent_proving_ground/scenarios/builtin/`
- Create corresponding integration tests under `logion/packages/agent-proving-ground/tests/integration/`
- Extend API/GitHub assertions only where an observed-effect query is absent

Implement independently reviewable scenarios:

| Scope | Required observed effects |
|---|---|
| 15.1 identity/OAuth | linked identity, device/web handoff state, token scope isolation and denied wrong-user redemption |
| 15.2 personalized install | setup token handoff, no credential in URL/log/recall, install completes only after explicit action |
| 15.3 package maps/repo publishing | pinned repository/ref provenance, package-map validation, normal review gate |
| 15.4 setup completion | one-time fragment claim, replay rejection, CORS/redirect boundary |
| 15.5 GitHub App bounty bot | issue mention, confirmation safety pin, idempotent webhook, submitted PR and merge policy |
| 15.6 external indexer | adapter-scoped run report, canonical dedup, source/count reconciliation, no incompatible identity coercion |
| 15.7 observation/discovery | indexed detail, scan at pinned commit, capability profile, failed observation does not imply verified/installable |
| 15.8 platform bounty | admin create/fund/accept/reject, ledger balance, no merge-webhook auto-accept, improving tier and attribution |

Each scenario must use run-unique identifiers, local-devrig role keys, baseline filtering, and assertions that query the actual API/observer rather than transcript text.

## Workstream D — safe indexed verification and consented direct-source installation

### Task D1: Bounded verification queue

**Files:**
- Create private verification job/model/service/controller modules under `backend repository/packages/api/api/indexing/`
- Create migration under `backend repository/packages/api/alembic/versions/`
- Modify: `backend repository/packages/api/api/jobs/handlers/`
- Test: `backend repository/packages/api/tests/indexing/test_indexed_verification_queue.py`

1. Add immutable verification requests and attempts with listing ID, canonical source URL, resolved commit/tree digest, bundle/content SHA-256, scanner policy/version, queued/running/succeeded/failed/superseded state, timestamps, and sanitized failure summary.
2. Allow only bounded admin/operator dispatches of 10 or 100 records; use row locking, per-item savepoints, rate limits, and idempotency key `(listing_id, source_commit, scanner_policy_digest)`.
3. Mark a result superseded when the upstream ref no longer resolves to the pinned commit. Never overwrite a prior result or treat a changed branch head as the verified content.
4. Publish verification status as evidence, not as publication approval. A successful verification does not make an indexed artifact entitlement-backed or purchasable.

### Task D2: Direct-source install proposal and confirmation

**Files:**
- Create public SDK/CLI resource and commands only after an additive API contract sync
- Modify: `logion/packages/cli/cli/commands/indexed/`
- Modify: `logion/packages/cli/cli/commands/skills/`
- Modify: `logion/packages/cli/cli/_local_state.py`
- Test: `logion/packages/cli/tests/test_cli_indexed.py`
- Test: `logion/packages/cli/tests/test_skills_install_remote.py`

1. `logion indexed inspect LISTING_ID` must expose source URL, resolved immutable ref, hash if available, verification timestamp/policy/result, license, declared capability evidence, and a clear statement that the artifact is not a reviewed Logion course.
2. `logion indexed install-source LISTING_ID` must be a two-step flow: render a no-write proposal first; then require an interactive explicit confirmation or a typed `--confirm-source <full-source-digest>` in non-interactive mode.
3. The installer clones/downloads only the pinned immutable revision, verifies the advertised hash, writes a separate `external_source` local manifest, and opens/prints the canonical source before confirmation. It must never reuse course entitlement paths or claim a Logion review.
4. Reject mutable refs, missing pin/hash, path traversal/symlink escapes, changed source after proposal, unsupported archive types, and absent confirmation.
5. Add an E2E scenario with a local Git fixture proving decline leaves no files, confirmation installs the pinned revision, an upstream branch change does not alter the installed bytes, and `skills verify` reports the external trust state.

## Final acceptance gate

Before Cycle 0 is complete:

```bash
# Workspace
make contract-audit-lint
make contract-audit-test
make contract-audit

# Public
make ci-checks
uv run pytest packages/ tests/ -m 'not integration'
uv run ruff check packages/
uv run ruff format --check packages/
uv run mypy packages/ --ignore-missing-imports

# Private
make ci-checks

# Real E2E, on a clean migrated local devrig
uv run logion-agent-proving-ground run builtin:marketplace_loop --api-adapter local-devrig ...
uv run logion-agent-proving-ground run builtin:listings_pagination --api-adapter local-devrig ...
```

Required result: contract audit has no unclassified critical/high findings; all supported old/current CLI compatibility pairs pass; the >100-record listing scenario proves complete, duplicate-free pagination; publication and every Phase 15.1–15.8 scenario report observed-effect success; and direct-source install remains consented, pinned, and explicitly outside the reviewed-course trust boundary.
