<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.10 — Native acquisition, artifact delivery, and local inventory

> **Implementation status (2026-07-30): not shipped.** This document is the
> normative future contract and acceptance gate. The current CLI can inspect
> and dry-run only a local source skeleton; the public API does not yet return
> distribution URLs, permissions, acquisition plans, or artifact downloads.
> Therefore non-dry-run acquisition is blocked rather than presented as an
> executable install.
>
> **Dogfood starts here — Level 1 (real acquisition):** the implementing agent must discover a resource in Logion, acquire its actual artifact, use it from a normal agent workflow, and prove that Logion can reconcile the installed copy.
> **After this phase:** a user may acquire through Logion or keep using `npx skills`, `npx plugins`, or `hf download`; Logion records one canonical local inventory either way.
> **Honesty boundary:** acquisition and installation prove possession of an artifact, not usage, usefulness, safety, or entitlement to paid content.

## Why this phase moved before ARD, evidence, and runners

The product cannot dogfood by inspecting metadata while the implementing agent cannot download the selected artifact. More importantly, Logion must not demand that users abandon native ecosystems:

- skills use `npx skills add|use`;
- agent plugins use `npx plugins add`;
- Hugging Face resources use `hf download --revision`;
- Logion-hosted Course/capability artifacts need a real authenticated download path.

Logion's job is to resolve identity, display policy and evidence, produce an acquisition plan, verify the resulting artifact, and remember where it is installed. It is not to replace every upstream package manager.

## Mandatory dogfood prompt for the implementing agent

This prompt is a release gate and runs after the implementation is test-green:

```text
You are implementing Phase 15.10. Dogfood Logion's actual artifact path.

1. Run `logion recall search "artifact acquisition package manager interop" --limit 5`.
2. On LOW/NONE, run:
   `logion listings search --query "artifact acquisition package manager interop"
   --include-indexed --limit 5 --json`.
3. Select one published/free Course resource that has a Logion-hosted bundle and one
   externally indexed skill that recommends `npx skills`.
4. Inspect each resource, exact version, distribution channel, permissions, license,
   expected bytes, digest, source, and acquisition command.
5. Ask for explicit approval before either installation. For both resources run:
   `logion resources acquire RESOURCE_ID --version VERSION_ID --scope repo-root
   --channel auto --dry-run --json`.
6. Acquire the hosted Course through `logion_bundle`. Acquire the external skill by
   allowing Logion to delegate to the displayed `npx skills add ...` command.
7. Run `logion resources inventory --scope repo-root --json` and
   `logion resources reconcile --scope repo-root --json`.
8. Use both resources in harmless, bounded implementation tasks. Confirm the harness
   loads the same files/digests recorded by inventory.
9. Save `artifacts/dogfood/phase-15.10.md` with resource/version IDs, acquisition plans,
   approval, exact executed commands, upstream locator/revision, installed paths,
   digests, reconciliation outcome, and product friction found.
10. Until 15.11 exists, submit `logion courses report-usage` only for the hosted Course
    if it was actually used and the current review eligibility permits it. Do not
    invent a review for the ownerless indexed skill.
```

If this phase cannot download a real hosted Course artifact, it does not pass.

## Dependencies

- 15.9.1 harness resource scope and observation contract.
- 15.3 package maps and source provenance.
- 15.6 mirrored indexed bundles and source attribution.
- 15.9 generic `Resource`, `ResourceVersion`, `ResourceSource`, and compatibility projections.
- Existing `CourseAsset`, object storage, entitlements, `_local_state.py`, install finalization, harness projection, and CLI confirmation helpers.

## Upstream contracts to pin before coding

- `skills` CLI source/README and release: <https://github.com/vercel-labs/skills>
- skills.sh CLI/telemetry documentation: <https://www.skills.sh/docs/cli>
- Vercel plugin entry surface and current plugin repository/spec references: <https://vercel.com/plugin> and <https://github.com/vercel/vercel-plugin>
- Hugging Face `hf download` reference, including `--revision`, `--local-dir`, cache, token, and `--dry-run`: <https://huggingface.co/docs/huggingface_hub/en/package_reference/cli>
- Codex skill discovery and repository/user/admin scopes: <https://developers.openai.com/codex/skills>
- Claude Code project, personal, and plugin scopes: <https://code.claude.com/docs/en/slash-commands>
- Hermes skills and profile isolation: <https://hermes-agent.nousresearch.com/docs/user-guide/features/skills> and <https://hermes-agent.nousresearch.com/docs/user-guide/profiles/>
- Pi project/user skill discovery and `.agents/skills` compatibility: <https://www.mintlify.com/badlogic/pi-mono/coding-agent/skills>

Record exact tested versions and fixture provenance in the PR. These tools can change; adapters must fail closed on an unsupported state format/version rather than silently misattribute.

## Product contract

### One resource, multiple distributions

A `ResourceVersion` may expose zero or more immutable acquisition distributions:

```text
logion_bundle   authenticated object-store bundle controlled by Logion
npx_skills      upstream Git/git-hosted Agent Skill acquired by `skills`
npx_plugins     upstream agent plugin acquired by `plugins`
hf              model/dataset/space revision acquired by `hf`
git             exact public Git commit for unsupported native managers
manual          metadata-only instruction; Logion does not execute it
```

The `channel` is not the resource identity. The same content may be available through multiple channels. Evidence remains attached to `ResourceVersion.content_digest`.

### Acquisition plan

`GET /v1/resources/{resource_id}/versions/{version_id}/acquisition-plan`
returns the server-owned resource/distribution plan. It never receives or
returns a local path, `scope_id`, or `installation_id`:

```json
{
  "resource_id": "uuid",
  "version_id": "uuid",
  "distribution_id": "uuid",
  "content_digest": "sha256:...",
  "selected_channel": "npx_skills",
  "alternatives": ["logion_bundle", "git"],
  "entitlement": {"required": false, "status": "not_applicable"},
  "license": {"spdx": "MIT", "redistribution_allowed": true},
  "expected": {"bytes": 1234, "files": 4},
  "native": {
    "tool": "skills",
    "tested_version": "x.y.z",
    "argv": ["npx", "skills@x.y.z", "add", "owner/repo", "--skill", "name"],
    "upstream_locator": "https://github.com/owner/repo",
    "revision": "40-char-commit"
  },
  "integrity": {"algorithm": "sha256", "digest": "..."},
  "permissions": {"network": false, "tools": [], "secrets": []},
  "warnings": []
}
```

The public CLI validates that response and combines it locally with the 15.9.1
harness-scope resolver. The resulting local acquisition plan, including its
zero-write dry-run serialization, contains:

```json
{
  "harness": "codex",
  "requested_scope": {"kind": "repo-root"},
  "resolved_target": {
    "scope_kind": "repo-root",
    "scope_id": "opaque-profile-node-scoped-id",
    "relative_path": ".agents/skills/name",
    "precedence": 30
  }
}
```

The CLI may display the resolved absolute path interactively, but it must not
send that path to the acquisition-plan endpoint or persist it in remote
telemetry. Dry-run does not contain `installation_id` or
`native_receipt_digest`; those fields exist only after validated native evidence
is available.

`native.argv` is a display/execution array, never a shell string. User-controlled values cannot become flags without `--`/adapter validation. The server never executes it.

### Local acquisition receipt

Every successful acquisition/reconciliation writes a fixed-schema local record:

```json
{
  "schema_version": 1,
  "resource_id": "uuid",
  "version_id": "uuid",
  "distribution_id": "uuid",
  "resource_type": "agent_skill",
  "content_digest": "sha256:...",
  "channel": "npx_skills",
  "upstream_locator": "owner/repo@commit#skill-name",
  "harness": "codex",
  "scope_kind": "repo-root",
  "scope_id": "opaque-profile-node-scoped-id",
  "installation_id": "opaque-profile-node-scoped-installation-id",
  "native_receipt_digest": "sha256:64-lowercase-hex",
  "native_evidence": {
    "schema_version": 1,
    "manager_name": "skills",
    "manager_version": "x.y.z",
    "receipt_id": "native-lock-or-receipt-id",
    "canonical_source": "https://github.com/owner/repo",
    "immutable_revision": "40-char-commit",
    "content_digest": "sha256:..."
  },
  "target_path": "/workspace/xpto/.agents/skills/skill-name",
  "relative_target_path": ".agents/skills/skill-name",
  "installed_paths": [".agents/skills/skill-name"],
  "projection_paths": [".claude/skills/skill-name"],
  "acquired_at": "RFC3339",
  "verified_at": "RFC3339",
  "verification": "exact|source_revision|unverified"
}
```

No telemetry or review is sent by creating this record. `native_receipt_digest`
is recomputed from the RFC 8785 canonical JSON bytes of `native_evidence` before
the receipt is accepted; a mismatch fails closed. `native_evidence.manager_name`
and `native_evidence.manager_version` are the single authoritative manager
identity and produce
the 15.9.1 `native_manager` value `<manager_name>@<manager_version>`; the receipt
must not duplicate those fields at top level. `scope_id` and the
installation identity use the profile/node-scoped, domain-separated HMAC
contract from 15.9.1. A plain SHA-256 of `target_path`/repository path is
forbidden. Absolute paths remain local and are never copied into API payloads.
For `verification: exact`, `native_evidence.content_digest` must equal the
top-level immutable resource `content_digest`, and its canonical source/revision
must match the selected distribution. A mismatch is retained only as unlinked
inventory evidence and cannot mint `installation_id`.
`relative_target_path` is the single canonical primary target used by the
15.9.1 installation HMAC. `target_path` is its local absolute rendering;
`installed_paths` and `projection_paths` are lifecycle evidence and do not alter
that installation identity.

## Database and API implementation

### Migration

Add `resource_distributions`:

```text
id UUID PK
resource_version_id UUID FK resource_versions(id) ON DELETE CASCADE
channel VARCHAR(32) NOT NULL
locator TEXT NOT NULL
upstream_revision TEXT NULL
artifact_digest VARCHAR(80) NULL
artifact_size_bytes BIGINT NULL
media_type TEXT NULL
metadata JSONB NOT NULL DEFAULT '{}'
priority SMALLINT NOT NULL DEFAULT 100
enabled BOOLEAN NOT NULL DEFAULT TRUE
created_at, updated_at
UNIQUE(resource_version_id, channel, locator)
```

Do not put ephemeral presigned URLs in this table. A Logion bundle distribution references existing immutable Course assets/object keys through metadata validated by a service.

### `backend repository` files

- Add `api/resources/services/build_acquisition_plan.py`.
- Add `api/resources/services/get_resource_artifact_download.py`.
- Add `api/resources/services/register_resource_distribution.py`.
- Add repository/controller/response types under existing `api/resources/`.
- Reuse `api/storage/services/s3_storage_service.py` for short-lived download URLs.
- Reuse payments entitlement services for paid Course projections.
- Extend Course finalization/publication to create/update `logion_bundle` distributions only after asset manifest and digest validation.
- Extend indexed upsert to create `npx_skills`, `git`, or mirror distributions from trustworthy source/package-map data.
- Add rate limits, object-size caps, audit events, and metrics.

### API endpoints

- `GET /v1/resources/{id}/versions/{version_id}/acquisition-plan`
- `POST /v1/resources/{id}/versions/{version_id}/download` for authorized Logion bundles; response is a short-lived manifest/URL, not raw bytes through FastAPI.
- Admin/internal distribution registration remains behind indexing/publication services; no arbitrary public URL registration endpoint.

Stable errors:

```text
resource_distribution_unavailable
resource_version_digest_missing
resource_artifact_not_redistributable
resource_entitlement_required
resource_entitlement_inactive
resource_artifact_digest_mismatch
resource_native_tool_unsupported
resource_native_tool_version_unsupported
resource_acquisition_channel_denied
```

## CLI and client implementation

### Generated/public client

- Add typed acquisition-plan and artifact-download methods to `logion/packages/client/src/logion/v1/_resources/resources.py`.
- Regenerate OpenAPI operations/types; never hand-edit generated files.

### New CLI package

Add `logion/packages/cli/cli/commands/resources/`:

```text
parser.py
handlers.py
acquire.py
inventory.py
reconcile.py
distributions.py
adapters/base.py
adapters/logion_bundle.py
adapters/npx_skills.py
adapters/npx_plugins.py
adapters/hf.py
```

Commands:

```bash
logion resources distributions RESOURCE_ID --version VERSION_ID --json
logion resources acquire RESOURCE_ID --version VERSION_ID \
  --harness codex|claude|hermes|pi|opencode \
  --scope repo-current|repo-parent|repo-root|user|admin|custom \
  --channel auto|logion_bundle|npx_skills|npx_plugins|hf \
  --dry-run --json
logion resources inventory [--harness HARNESS] [--scope SCOPE|all] [--json]
logion resources reconcile [--from skills|plugins|hf|logion|all] \
  [--harness HARNESS|all] [--scope SCOPE|all] [--dry-run] [--json]
```

`acquire` execution order:

1. Fetch and validate plan.
2. Detect the harness and resolve scope from the current working directory.
   Inside a Git repository the default is the root of the nearest containing
   Git worktree; there is no silent fallback to `user`. `system` is
   inventory-only.
3. Display price/entitlement, license, bytes, digest, native tool/version, permissions, paths, and exact argv.
4. `--dry-run` performs no download, package-manager execution, config write, or inventory mutation.
5. Ask explicit confirmation unless caller already supplied the normal approved non-interactive flag.
6. Execute adapter without a shell.
7. Discover actual installed paths/output using adapter-specific state.
8. Verify revision/digest to the strongest available level.
9. Write inventory atomically.
10. Project to the selected harness's native directory using native manager
    behavior first; Logion must not create duplicate copies.

Both directions are normative: Logion must install a catalog resource into the
requested native harness scope, and it must reconcile a resource installed
directly through a native manager without moving or reinstalling it.

### Logion bundle adapter

- Download manifest and files to a temporary directory.
- Verify every file size/digest and aggregate content digest before installation.
- Call existing install/finalization libraries rather than duplicating `_install_helpers.py`.
- Record Course/version/resource provenance in the manifest.
- Delete partial/temp data on failure; keep resumable cache only when content-addressed.

### `npx skills` adapter

- Verify `node`/`npx` and supported `skills` version.
- Use documented `npx skills add <source> --skill <name>` arguments,
  repository scope by default. Never interpret “project” as user-global.
- Do not pass `-y` unless the outer Logion approval has already been obtained and the full argv was displayed.
- Read `skills-lock.json`, canonical skill directory, symlinks/copies, and manager output after completion.
- Preserve upstream lock entries and files. Logion adds its own local inventory; it does not rewrite `skills-lock.json` unless compatibility requires a bit-exact, tested field update.
- Also reconcile resources installed before Logion by reading the lockfile and exact source metadata.

### `npx plugins` adapter

- Treat a plugin as a distinct `agent_plugin` resource; bundled skills remain child/source relationships, not duplicate Course ownership.
- Use the plugin manager's official manifest/state and supported agent projections.
- Never infer a plugin ID from directory basename alone.
- Reconcile existing plugin installs without rewriting their manager files.

### `hf` adapter

- Produce `hf download REPO_ID --revision COMMIT` or an `hf://...@COMMIT` locator.
- Default acquisition plan is metadata/files explicitly required by the consuming eval/workflow. Never download all model weights from index/search.
- Run `hf download --dry-run` as part of Logion dry-run when available.
- Read Hub cache revision/snapshot metadata and verify commit/file metadata.
- Tokens stay in the native `hf` credential path and are never copied into Logion inventory.

## Reconciliation and identity rules

Attribution priority:

1. exact Logion resource/version marker;
2. exact native lock/manifest source plus immutable revision;
3. exact content digest;
4. canonical source plus verified subpath/name;
5. unresolved.

Never fuzzy-link by display name. Multiple candidates produce `ambiguous` with candidate IDs and no attribution.

`reconcile` may:

- create/update local inventory;
- mark missing/drifted installations;
- improve verification when a digest becomes available.

It may not:

- upload telemetry;
- submit feedback/review;
- delete native manager state;
- upgrade/downgrade artifacts;
- claim ownership or entitlement.

## Security and privacy

- All archives use traversal, symlink, decompression-ratio, file-count, type, and size defenses already used by Course upload/install paths.
- Native command invocation uses argv, sanitized environment, cwd pinned to project, timeout, output cap, and no secret logging.
- The acquisition plan is untrusted server/source metadata until client validation.
- Logion-hosted paid artifacts require entitlement; external public copies do not silently mint entitlement.
- Local inventory stores no prompts, tool inputs, user identity, tokens, or repository contents.

## Tests

### Backend

- Hosted free/paid/expired entitlement plans and downloads.
- Presigned URL expiry, object/digest mismatch, non-redistributable license, disabled distribution.
- Course publication creates one idempotent bundle distribution.
- Indexed source creates exact native distribution; ambiguous/missing revision is quarantined or manual-only.
- OpenAPI and generated-client contract.

### CLI

- Plan rendering and `--dry-run` zero-write/zero-exec.
- Fake executable adapters assert exact argv and shell is never used.
- Hosted bundle happy path, partial download, digest mismatch, traversal, resume/cleanup.
- Recorded `skills` fixtures: repository/user, symlink/copy, multiple skills,
  lock drift, pre-existing installation, unknown manager version.
- Recorded `plugins` manifest/state fixtures and unsupported agent.
- Recorded `hf download --dry-run`/cache fixtures, exact revision, gated token non-leak, oversized plan.
- Ambiguous identity never links; second reconcile is zero-change.
- Exact discovery/scope fixtures for Codex, Claude, Hermes, and Pi as specified
  in 15.9.1, including precedence and unsupported-scope failures.
- Install the same resource in fixture repositories `xpto` and `acme`; verify
  distinct receipts and no repository/user-scope leakage.
- Launch a fresh real harness session and assert native discovery of the exact
  installed version.
- Scope isolation and existing `skills install/list/inspect/update/prune` regressions.

## Rollout

1. Hosted free Course bundles.
2. Existing indexed skill reconciliation without executing `npx`.
3. Delegated `npx skills` acquisition.
4. Plugin reconciliation/acquisition.
5. HF metadata/selective-file acquisition.
6. Paid hosted bundles after entitlement and red-team tests.

Feature flags exist per channel. Metrics include planned/started/succeeded/failed acquisition, bytes, verification level, reconcile matched/ambiguous/drifted, native tool/version, and channel—but no user project paths.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add
`builtin:phase_15_10_native_acquisition`.

- **Actors/fixtures:** a fresh `buyer` and separate `operator`.
  `make proving-ground-seed SCENARIO=phase_15_10` publishes a small hosted
  bundle, repositories `xpto` and `acme`, isolated user homes, and local Git
  fixtures accepted by the real `npx skills` and `npx plugins` CLIs. No fake
  `logion`, `npx`, harness, or adapter executable.
- **Customer prompt:** “I need a lightweight code-review capability. Search
  Logion, install the best suitable option for Codex in repository xpto—not
  globally—show what was installed, then reconcile anything already present.
  Start a fresh Codex session and prove it discovers the capability. Do not call
  Logion's HTTP API directly.”
- **Flow:** acquire the hosted resource, install the indexed skill through real
  `npx skills`, rerun safely, then use public inventory/reconcile commands.
- **Assertions to implement:** `api.resource_acquisition_exists`,
  `api.resource_distribution_selected`, `api.native_install_reconciled`,
  `files.inventory_receipt_matches`,
  `files.installed_artifact_digest_matches`, and
  `api.acquisition_idempotent`; require no 500s.
- **Negative case/evidence:** an advertised digest mismatch fails closed and
  creates no success receipt or entitlement. Retain native tool version/output,
  distribution, receipt/artifact digests, and proof of zero duplicate state.

## Acceptance criteria

- [ ] A published free Course discovered through Logion downloads and installs without a manually supplied `--source` directory.
- [ ] A resource installed directly with `npx skills add` is reconciled to the exact Logion `ResourceVersion` without reinstalling it.
- [ ] Codex, Claude, Hermes, and Pi adapters declare and test native locations,
      scope precedence, observation capability, and failure behavior.
- [ ] Installing in repository `xpto` creates nothing in the user scope or
      another repository; a fresh target harness discovers the exact version.
- [ ] A Vercel plugin installed with `npx plugins add` and an HF revision downloaded with `hf download --revision` can appear in local inventory without Logion owning their download path.
- [ ] Every acquisition dry-run is zero-write and shows exact channel, revision, bytes, permissions, argv, and verification expectation.
- [ ] No fuzzy name attribution, shell invocation, ambient credential copy, or hidden telemetry occurs.
- [ ] Existing Course/skills CLI and entitlement behavior remain compatible.
- [ ] The mandatory dogfood artifact contains one real hosted acquisition and one real native-manager acquisition.

## Out of scope

Usage observation, telemetry upload, feedback/reviews (15.11), ARD (15.12), signed scan evidence (15.13), MCP execution, arbitrary model evaluation, automatic upgrades, and funding decisions.
