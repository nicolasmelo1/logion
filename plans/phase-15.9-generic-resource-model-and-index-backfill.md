<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.9 — Generic resource model and index backfill

> **Dogfood status:** bootstrap only; Logion can browse its backfilled corpus but cannot yet prove the new loop.
> **After this phase:** every indexed skill and published course has a stable generic resource identity without breaking existing clients.
> **Honesty boundary:** migration records are inventory metadata, not attestations.

## Mandatory dogfood protocol

The phase-specific prompt below is part of the implementation, not optional documentation. The implementing agent must:

1. run recall before marketplace search and record the recall band/result;
2. on LOW/NONE, run the phase-specific query exactly as `logion listings search --query "SEARCH_QUERY" --include-indexed --limit 5 --json`; an invalid optional category is removed rather than invented;
3. inspect the selected published Course and exact version before asking to install;
4. obtain explicit approval before installation or any paid action; run install with `--dry-run` first and use a temporary/project target;
5. actually apply the installed course to this phase's implementation/review, recording concrete advice used or rejected;
6. after the task, submit exactly one honest review with:

```bash
logion courses report-usage COURSE_ID VERSION_ID \
  --rating 1..5 \
  --usefulness 0.0..5.0 \
  --reliability 0.0..5.0 \
  --tool-safety 0.0..5.0 \
  --token-efficiency 0.0..5.0 \
  --completed-task \
  --body "One or two course-focused sentences; no private repository data"
```

Use `--not-completed-task` when appropriate. If authentication is missing, ask the user to run interactive `logion identity onboarding`; do not run it unattended. If the result is indexed-only, no legitimate bundle is available, installation is refused, or the course was not actually used, record the blocker in the phase dogfood artifact and **do not submit a review**.

## Goal

Introduce the protocol-neutral identity layer required for skills, MCP servers,
models, datasets, prompts, agents, AI Catalog entry types, and resources
returned through ARD.

## Dogfood prompt for the implementing agent

Run this before coding. Marketplace search is required; installation still requires the explicit confirmation mandated by the current companion.

```text
You are implementing Logion Phase 15.9. Use Logion itself during the work.

1. Run `logion update --dry-run`, then `logion recall search "database schema migration polymorphic resources" --limit 5`.
2. If recall has no HIGH-confidence fit, run:
   `logion listings search --query "database schema API migration" --category software-development --include-indexed --limit 5 --json`.
   If the category is rejected, repeat without `--category`; do not invent a category.
3. Inspect the best published candidate with `logion courses get COURSE_ID` and
   `logion courses versions get COURSE_ID VERSION_ID`. Check price, required tools,
   permissions, execution policy, provenance, and reviews. An indexed-only result may
   inform discovery but cannot be installed/reviewed through the Course flow.
4. Prefer a free candidate. Before `logion skills install`, show the candidate and ask
   for explicit install approval. The current CLI requires a local bundle; if no bundle
   can be legitimately obtained, record `dogfood_install_blocked: bundle_unavailable`
   and do not fake installation.
5. After approval, run the install first with `--dry-run`, then install into a temporary
   target, never the global agent directory. Use the selected skill to review the data
   model, migration/backfill order, uniqueness constraints, and compatibility design.
6. Save `artifacts/dogfood/phase-15.9.md` with query, candidates, selected course/version,
   approval, install command, concrete advice used, and whether it changed the patch.
7. After tests pass, submit exactly one honest review with
   `logion courses report-usage COURSE_ID VERSION_ID ...`. Review only if the course was
   actually installed and used. Never put repository-private content in `--body`.
```

The PR description must include `Dogfood-Course`, `Dogfood-Version`, `Dogfood-Completed`, and `Dogfood-Review-Submitted`.

## Current-code anchors

- Backend models are centralized in `backend repository/packages/api/api/models.py`; migrations live in `backend repository/packages/api/alembic/versions/` (latest current indexing migrations are `0040` and `0041`).
- Indexed persistence is under `api/indexing/`; `BatchUpsertIndexedListingsService` currently rejects any canonical ID outside `gh:owner/repo[#path]`.
- Public listing merge logic is in `api/listings/services/search_listings.py`.
- The public indexer is skill-specific in `logion/packages/indexer/logion_indexer/models.py`, `canonical.py`, `pipeline.py`, `pusher.py`, and `dedup.py`.
- Client resources live in `logion/packages/client/src/logion/v1/_resources/`; generated OpenAPI types must not be hand-edited.
- CLI registration starts in `logion/packages/cli/cli/main.py` and `cli/_parser.py`.

## Required database contract

Add one migration after the actual Alembic head; the filename number below is illustrative and must be rebased, never guessed:

```text
resources
  id UUID PK
  resource_type VARCHAR(64) NOT NULL
  canonical_uri TEXT NOT NULL
  title TEXT NOT NULL
  summary TEXT NULL
  lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'active'
  metadata JSONB NOT NULL DEFAULT '{}'
  created_at, updated_at
  UNIQUE(resource_type, canonical_uri)

resource_versions
  id UUID PK
  resource_id UUID FK resources(id) ON DELETE RESTRICT
  version_label TEXT NULL
  content_digest VARCHAR(80) NOT NULL
  digest_algorithm VARCHAR(16) NOT NULL DEFAULT 'sha256'
  media_type TEXT NOT NULL
  source_revision TEXT NULL
  metadata JSONB NOT NULL DEFAULT '{}'
  discovered_at TIMESTAMPTZ NOT NULL
  UNIQUE(resource_id, content_digest)

resource_sources
  id UUID PK
  resource_id UUID FK resources(id) ON DELETE CASCADE
  source_kind VARCHAR(32) NOT NULL
  source_uri TEXT NOT NULL
  external_id TEXT NULL
  attribution JSONB NOT NULL DEFAULT '{}'
  first_seen_at, last_seen_at
  UNIQUE(resource_id, source_kind, source_uri)

resource_projections
  resource_id UUID FK resources(id) ON DELETE CASCADE
  projection_kind VARCHAR(32) NOT NULL
  projection_id UUID NOT NULL
  PRIMARY KEY(resource_id, projection_kind, projection_id)

resource_relationships
  parent_resource_id UUID FK resources(id) ON DELETE CASCADE
  child_resource_id UUID FK resources(id) ON DELETE CASCADE
  relation VARCHAR(32) NOT NULL
  metadata JSONB NOT NULL DEFAULT '{}'
  PRIMARY KEY(parent_resource_id, child_resource_id, relation)
```

Use closed application constants for known resource types, but a database
`CHECK` must not prevent unknown future AI Catalog media types. Validate
canonical URI length, absolute URI shape, allowed digest algorithms, and JSON
depth/size at the service boundary.

## Implementation work packages

### `backend repository`

- Add SQLAlchemy models and the migration above.
- Create `api/resources/{controllers,services,repositories,constants}/` following the current courses/indexing layering.
- Implement `UpsertResourceService`, `GetResourceService`, `ListResourceVersionsService`, and `BackfillResourceProjectionsService`.
- Implement validated relationships such as `bundles`, `depends_on`, `variant_of`, and `commercial_projection_of`; reject self/cyclic `bundles`/`depends_on` relationships.
- Extend indexed upsert in the same transaction: create/update the `Resource`, create the immutable version only when a digest exists, upsert source/channel rows, then attach the listing projection.
- Attach published `CourseVersion` rows only when there is a trustworthy asset digest. Do not fabricate a digest from metadata.
- Add `GET /v1/resources`, `GET /v1/resources/{id}`, and `GET /v1/resources/{id}/versions`; cursor sort is `(created_at DESC, id DESC)`.
- Add a resumable admin backfill command/service with `--dry-run`, page size, counters, and a checkpoint. It must be safe to rerun after partial failure.
- Add the resources router in `api/main.py`, OpenAPI response schemas, feature flag `resource_read_surface`, and metrics for created/matched/conflicted/backfill-failed.

### `logion`

- Replace `DiscoveredSkill` internally with additive `DiscoveredResource`; keep a compatibility alias/adapter until all current hub tests migrate.
- Generalize canonical/dedup code around `(resource_type, canonical_uri)` while preserving exact `gh:` output for skills.
- Add client `ResourcesResource` and CLI package `cli/commands/resources/` with `search`, `get`, and `versions`.
- `skills search`, `indexed get`, and `listings search` remain byte-compatible for existing JSON fields; additive `resource_id` is allowed.
- Regenerate the client from OpenAPI using the repository's existing generation target; never edit `_generated/operations.py` or generated types manually.

## Migration and rollout

1. Deploy tables and write-path dual-write behind `resource_identity_write`.
2. Run dry-run backfill and reconcile counts/conflicts.
3. Run actual backfill in bounded batches; keep old read paths authoritative.
4. Enable comparison logging between old listing identity and projection identity.
5. Enable resource reads; do not remove legacy columns in this phase.

Rollback disables flags and leaves additive rows intact. The migration downgrade may drop only when explicitly run in non-production; operational rollback never destroys backfilled data.

## Required tests

- `tests/resources/test_resource_schema.py`: constraints, unknown type, digest immutability, projection FK behavior.
- `tests/resources/test_resource_upsert.py`: idempotency, concurrent same-resource insert, new digest creates version, metadata drift does not mutate version.
- `tests/resources/test_resource_backfill.py`: dry run, checkpoint/resume, conflict report, listing/course projections, second-run zero creates.
- `tests/resources/test_resource_controllers.py`: pagination, filters, 404, invalid cursor, feature flag.
- Extend indexing/listings regression tests and `test_openapi_public_contract.py`.
- Public repo: model/canonical/dedup/pusher compatibility tests, client contract tests, CLI JSON golden tests.

## Build

- Add `resources`, `resource_versions`, and `resource_sources` with stable IDs, type, canonical URI, source, immutable digest, media type, metadata, and lifecycle state.
- Start with `agent_skill`, `agent_plugin`, `mcp_server`, and `model`; unknown
  AI Catalog entry media types remain representable. A plugin that bundles
  skills has explicit parent/child relationships rather than collapsed identity.
- Backfill indexed listings as `agent_skill` resources and published courses as commercial projections over a resource/version.
- Keep `IndexedListing`, `Course`, `/listings`, and existing skill/course CLI commands working through compatibility projections.
- Add additive SDK/API primitives: `resources search|get|versions` and resource-shaped internal services.
- Make upsert idempotent across GitHub coordinates, AI Catalog entry
  identifiers, immutable source coordinates, and content digests. ARD registry
  provenance is a discovery source, not a second resource identity.

## Do not build

- No generic execution engine.
- No claim of cross-node trust.
- No destructive table or CLI rename.
- No model hosting.

## Mandatory proving-ground scenario

Follow [the common real-agent gate](agent-proving-ground-phase-gate.md). Add
`builtin:phase_15_9_resource_backfill`.

- **Actors/seed:** an `operator` (`admin`) and clean `consumer` (`buyer`).
  `make proving-ground-seed SCENARIO=phase_15_9` creates one hosted Course, one
  indexed third-party skill, and one pre-migration legacy row; the fixture
  exposes public slugs but no database IDs.
- **Customer prompt:** “We upgraded this Logion node. Verify that the existing
  Python debugging course and external debugging skill are discoverable as
  resources, explain each source, and confirm the old Course workflow still
  works. Do not inspect source code or the database.”
- **Flow:** the operator runs public migration/status commands and reruns the
  backfill; the consumer searches, inspects both results, and acquires the
  hosted Course through the compatibility surface.
- **Assertions to implement:** `api.resource_projection_exists`,
  `api.resource_backfill_complete`, `api.resource_identity_unique`,
  `api.legacy_course_purchase_exists`, and
  `api.resource_search_returns_kinds`; also require no double debit, no 500s,
  and timeline redaction.
- **Negative/idempotency case:** the second backfill creates zero resources or
  links and preserves IDs. Retain search/inspect output, migration counters,
  acquisition/resource IDs, and fixture digests.

## Acceptance gates

- Backfill is repeatable and produces no duplicate resource identities.
- Existing course/listing/install tests remain green.
- A resource version is immutable once evidence references its digest.
- Unknown resource types round-trip without schema changes.
- API responses expose compatibility links between resource, indexed listing, and course where applicable.
