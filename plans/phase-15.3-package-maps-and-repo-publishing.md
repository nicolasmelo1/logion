<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.3: Package Maps & Publish-From-GitHub

> Implements the package-map + repo-publishing slices of
> [`phase-15`](phase-15-native-resource-loop-and-first-ard-node.md).
> Depends on 15.1 (stored OAuth token, `scope_tier='repo'` for private repos).
> **Convergence:** the package-map schema defined here IS the structured-package
> descriptor that [`phase-15.9`](phase-15.9-generic-resource-model-and-index-backfill.md)
> builds evals/bounty contracts on, and its `evals.commands` block is what
> 16.1's eval-backed acceptance executes. Design it once, here.
> **PRs: exactly one per repo** — one `logion` PR (map schema + parser +
> deterministic inference package + CLI publish flow together) and one
> `backend repository` PR (source-link + materializer). Never split a repo's
> work across multiple PRs.

## Goal

A creator points Logion at `owner/repo@ref` + a `logion-package-map.yaml`, and
Logion produces a normal, immutable course version through the **existing**
upload-finalization pipeline (manifest, capability parse, review) — no parallel
publishing path. Local folders and tarballs use the same map; GitHub is just
one *source adapter*.

## 1. Package map schema (`logion` PR)

Single canonical file at repo root: **`logion-package-map.yaml`**.

```yaml
version: 1
package:
  slug: pr-review-pro          # course slug this map publishes to
components:
  capabilities:                # capability records, NOT a provider listing
    pr-review:
      entrypoint: skills/pr-review/SKILL.md
      capabilities_manifest: skills/pr-review/course/capabilities.yaml
      dependencies:
        - capability: diff-reading
          reason: "delegates hunk parsing"
    diff-reading:
      entrypoint: skills/diff-reading/SKILL.md
  runtime:
    include: ["skills/**", ".agents/skills/**"]
    entrypoint: skills/pr-review/SKILL.md
  source:
    include: ["src/**", "docs/**", "package.json"]
    exclude: ["**/.env*", "**/node_modules/**"]
  evals:
    include: ["evals/**", "tests/**"]
    commands:
      verify: "npm test"        # 16.1 consumes; NEVER executed by 15.3
```

**New public module `logion/packages/cli/cli/_package_map.py`** (CLI-local,
mirrors `_course_capabilities.py` conventions):

```python
PACKAGE_MAP_FILENAME = "logion-package-map.yaml"
PACKAGE_MAP_SCHEMA_VERSION = 1
MAX_COMPONENT_CAPABILITIES = 32
MAX_INCLUDE_PATTERNS = 64
_GLOB_RE = re.compile(r"^[A-Za-z0-9_.\-*/]+$")   # no '..', no leading '/'

def parse_package_map(text: str) -> PackageMap: ...
def validate_package_map(pm: PackageMap) -> list[MapWarning]: ...
def resolve_includes(pm: PackageMap, root: Path) -> ResolvedFileSet: ...
```

Validation rules (each one a named test):

- reject unknown top-level keys, unsupported `version`, empty
  `components.capabilities`;
- every `entrypoint`/`capabilities_manifest` must be relative, traversal-free,
  and matched by some include pattern;
- dependency graph must be acyclic and closed over declared capabilities
  (`package_map_dependency_unknown`, `package_map_dependency_cycle`);
- glob patterns validated against `_GLOB_RE`; `exclude` wins over `include`;
- `evals.commands` values are stored as strings, flagged
  `commands_not_executed_locally` — parsing never runs them.

Backend twin **`api/courses/services/parse_package_map.py`** re-implements the
same rules server-side (backend never trusts the CLI), sharing test vectors
via literal fixtures (12+ YAML fixtures, one per rule, copied verbatim into
both repos' test suites — drift between the two parsers is a test failure).

## 1b. Deterministic map inference — `logion/packages/skillmap` (same `logion` PR)

Authoring the map must be near-zero friction and executable by any model —
or by no model. Inference is **pure and deterministic**: same tree in, same
map out (double-run equality is test-pinned). No pass may call an LLM.

New public stdlib-only package `logion/packages/skillmap`
(`logion_skillmap`), consumed by the CLI here and by the 15.6 indexer.
Single entrypoint:

```python
def infer(tree: Sequence[TreeEntry],
          read_blob: Callable[[str], bytes]) -> InferenceResult
# tree: (path, type, size) triples — from a local os.walk or the GitHub
#       `git/trees/{sha}?recursive=1` payload, source-agnostic.
# read_blob: lazy; only SKILL.md / manifest-sized files are ever read.

@dataclass(frozen=True)
class InferredComponent:
    name: str                # frontmatter `name`, fallback dir slug
    root: str                # skill root dir, ''-rooted, no leading '/'
    entrypoint: str          # <root>/SKILL.md
    summary: str             # frontmatter `description`, fallback ''
    content_sha256: str      # SKILL.md blob hash (dedup key)
    mirrors: tuple[str, ...] # non-canonical paths collapsed into this one

@dataclass(frozen=True)
class InferenceResult:
    package_map: PackageMap                  # same model as _package_map.py
    components: tuple[InferredComponent, ...]
    needs_review: tuple[ReviewFlag, ...]     # (code, path, message)
    source: str    # 'author_map' | 'plugin_manifest' | 'skill_scan'
```

**Precedence (first hit wins):**

1. `logion-package-map.yaml` at root → parse and return
   (`source='author_map'`); inference never overrides an author map;
2. `.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` at
   root → declared skill paths become candidates
   (`source='plugin_manifest'`); declared paths still flow through the
   passes below (a manifest pointing at a deleted dir is dropped with
   `manifest_path_missing`);
3. `SKILL.md` scan (`source='skill_scan'`): every directory containing a
   `SKILL.md`/`skill.md` blob is a candidate skill root; a repo-root
   `SKILL.md` means single-skill repo (component root = repo root).

**Passes over candidates (ordered; each rule a named test):**

- **exclusion** — drop candidates whose path contains any segment of
  `{test, tests, fixtures, fixture, deprecated, node_modules, .git,
  .github}` (`skillmap_excluded_segment`);
- **harness-mirror dedup** — sha256 the `SKILL.md` blob; group candidates
  by hash; one canonical per group chosen by: non-hidden path (no dot-dir
  segment) first, then shortest path, then lexicographic. Losing paths are
  recorded as `mirrors`. Known mirror prefixes (`.claude/skills/`,
  `.agents/skills/`, `.codex/`, `.opencode/`, `.cursor*/`,
  `plugins/*/skills/`) are diagnostics only — **the hash decides, never
  the prefix list**;
- **metadata** — parse SKILL.md YAML frontmatter with the same safe-load
  discipline as `_course_capabilities.py`; `name` → component name
  (fallback: dir slug), `description` → summary; missing/unparsable
  frontmatter keeps the component and flags
  `skillmap_frontmatter_missing`;
- **emission** — one map: `package.slug` = repo/dir name slug
  (caller-overridable); per component `entrypoint` = its `SKILL.md`,
  include = `<root>/**` (repo-root component ⇒ include `**` minus
  excluded segments); component count over
  `MAX_COMPONENT_CAPABILITIES` still emits, flagged
  `skillmap_component_cap_exceeded` (consumer decides: CLI prompts to
  partition, 15.6 indexer lists per-subpath regardless).

**`needs_review` codes are closed questions, not free-form:**
`no_license`, `hidden_tree_only` (all canonical roots under dot-dirs,
e.g. `.agents/skills/**`), `ambiguous_primary_tree` (≥2 disjoint
top-level trees with canonical components), `manifest_path_missing`,
`skillmap_component_cap_exceeded`, `skillmap_frontmatter_missing`.
Every flag has a deterministic default; a dumb agent accepts all
defaults (`--yes`), a capable agent answers the flags. The agent never
constructs the map — it answers closed questions about a constructed map.

**Fixture suite** — recorded `git/trees?recursive=1` payloads plus the
referenced `SKILL.md`/manifest blobs for seven real repos; canonical
component counts and flag sets are pinned at fixture-record time:

| fixture | pattern exercised (must-hold assertions) |
| --- | --- |
| `mattpocock/skills` | `skills/<cat>/<name>/`; `skills/deprecated/**` excluded; `.claude-plugin` manifest precedence |
| `MiniMax-AI/skills` | `skills/` + `plugins/*/skills/`; `.claude/skills/pr-review` (repo self-tooling) never canonical over a visible tree |
| `andrewyng/context-hub` | deep nesting `content/*/skills/**`; `cli/test/fixtures/testskills/**` must not appear |
| `uphiago/recon-skills` | category dirs at root, no `skills/` dir; 169 components; `no_license` flagged |
| `zarazhangrui/frontend-slides` | root `SKILL.md` + `plugins/.../skills/...` mirror → exactly 1 canonical component |
| `affaan-m/ECC` | hidden `.agents/skills/**` primary tree; cross-harness mirrors collapse; `hidden_tree_only` flagged |
| `ComposioHQ/awesome-claude-skills` | flat root dirs + `composio-skills/*`; `no_license` flagged; cap-exceeded flag |

## 1c. Agent Skills spec conformance (invariant, same `logion` PR)

Logion does **not** define a skill format. The skill artifact format is the
Agent Skills spec (agentskills.io — originally Anthropic's, adopted across
~40 clients). Logion's layers (map, capabilities, review, entitlement) wrap
around it; they never modify it. Two invariants, both test-pinned:

- **Every skill component is spec-valid.** `packages/skillmap` ships
  `spec.py` implementing the agentskills.io frontmatter rules verbatim
  (`name`: 1-64 chars, `^[a-z0-9]+(-[a-z0-9]+)*$`, must equal the parent
  directory name; `description`: 1-1024 chars non-empty; optional
  `license`, `compatibility` ≤500 chars, `metadata` str→str map,
  `allowed-tools` string). `infer()` runs it per component; violations are
  `needs_review` flags (`spec_nonconformant:<rule>`), and
  `package-map validate` + the backend materializer run the same check —
  a version whose skill components fail spec validation cannot reach
  `ready` (`422 skill_spec_nonconformant`, listing the rule per file).
  Rule vectors are copied from the `skills-ref` reference test suite and
  pinned; drift against upstream `skills-ref validate` on the seven
  fixture repos is a CI failure.
- **Logion files never enter the skill directory.** `logion-package-map.yaml`
  and `course/capabilities.yaml` live at bundle/repo root, outside every
  component root. Emission refuses to place either inside a component
  subtree (`skillmap_logion_file_inside_skill`); the materializer asserts
  the assembled bundle keeps skill dirs byte-identical to source (hash
  compare per component subtree, `test_skill_dirs_untouched`). A skill
  acquired through Logion must run unmodified in any spec-compatible
  client, and any spec skill must ingest without transformation.

## 2. Backend — source links + materializer (`backend repository` PR)

**Migration `0032_course_source_links.py`:**

```python
op.create_table(
    "course_source_links",
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("course_id", sa.Uuid(), sa.ForeignKey("courses.id"),
              nullable=False, unique=True),          # one live link per course
    sa.Column("provider", sa.String(16), nullable=False,
              server_default=sa.text("'github'")),
    sa.Column("repository", sa.String(255), nullable=False),   # "owner/repo"
    sa.Column("default_ref", sa.String(255), nullable=False),
    sa.Column("package_map_path", sa.String(512), nullable=False,
              server_default=sa.text("'logion-package-map.yaml'")),
    sa.Column("github_identity_id", sa.Uuid(),
              sa.ForeignKey("github_identities.id"), nullable=False),
    sa.Column("status", sa.String(16), nullable=False,
              server_default=sa.text("'active'")),   # active|revoked
    sa.Column("last_synced_ref", sa.String(64), nullable=True),  # commit sha
    sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    ... timestamps ...
    sa.CheckConstraint("provider in ('github',)", name="ck_source_links_provider"),
)
```

Endpoints:

```text
POST   /v1/courses/{course_id}/source-link      owner-only  body: {repository, default_ref, package_map_path?}
GET    /v1/courses/{course_id}/source-link      owner-only
DELETE /v1/courses/{course_id}/source-link      owner-only  (status='revoked')
POST   /v1/courses/{course_id}/versions/from-source   owner-only  body: {ref?}  -> 202 {job_id, version_id}
```

`POST source-link` validation: caller's user must have a `github_identities`
row with `status='active'`; when the repo is private the row must be
`scope_tier='repo'` (else `422 github_scope_insufficient`); Logion resolves
the repo via `GET /repos/{owner}/{repo}` with the stored token to confirm
read access **at link time** and stores nothing but metadata.

**`versions/from-source` is async** — it enqueues job type
`materialize_course_version_from_source` through the existing
`enqueue_job` service (dedupe key `f"from-source:{course_id}:{sha}"`).
Worker service `api/courses/services/materialize_from_source.py`:

1. resolve `ref` → commit `sha` (`GET /repos/.../commits/{ref}`);
2. download tarball (`GET /repos/.../tarball/{sha}`, stdlib urllib, streamed
   to a temp dir, 200 MB hard cap → `422 source_too_large`);
3. locate the map: if `package_map_path` exists at the ref, parse + validate
   it (backend parser, `map_source='author'`); **if absent, run
   `logion_skillmap.infer()` over the extracted tree** (`logion-skillmap`
   is a public package; the API depends on the published wheel, pinned) and
   use the inferred map with all `needs_review` defaults applied
   (`map_source='inferred'`, flags surfaced as version warnings — never a
   hard failure by themselves); resolve include set;
4. assemble the bundle layout the normal pipeline expects (entrypoint
   `SKILL.md`s, `course/capabilities.yaml` from `capabilities_manifest`);
5. feed the existing upload-session finalization path (create session →
   register assets from the temp dir → complete) so manifest generation,
   capability parsing/validation, and `ready` gating are **byte-identical**
   to a manual upload;
6. stamp provenance on the version: `source_provider`, `source_repository`,
   `source_ref_sha`, `map_source` (`'author'|'inferred'`) — nullable
   columns on `course_versions`, same migration;
7. update `last_synced_ref/at`; failure → version `failed` + job error
   surfaced via `GET /courses/{id}/versions/{vid}`.

Capability records rule (parent plan): each `components.capabilities` entry
becomes part of `capabilities_summary` (`component_capabilities` key:
name, entrypoint, dependencies) — the marketplace object stays the course;
the repo never becomes the listing.

## 3. CLI (`logion` PR)

```bash
logion courses source-link set  COURSE_ID --repository owner/repo --ref main [--map PATH] [--json]
logion courses source-link show COURSE_ID [--json]
logion courses source-link remove COURSE_ID [--yes]
logion courses publish-from-repo COURSE_ID [--ref v1.2.0] [--wait] [--json]
logion courses package-map validate [--dir .] [--json]     # CLI-local, no network
logion courses package-map init [--dir .] [--slug SLUG] [--yes] [--json]
                                                            # CLI-local, no network
```

`package-map init` = `logion_skillmap.infer()` over a local walk. Writes
`logion-package-map.yaml` (refuses to overwrite an existing one — author
map wins, exit 1 `map_already_exists`). Without `--yes`, `needs_review`
flags print as closed questions with their defaults; non-interactive TTY
with unanswered flags → exit 2 (an agent then either re-runs with `--yes`
or passes answers). `--json` emits
`{package_map, source, components[], needs_review[]}` without writing —
this is the surface an agent (dumb or capable) drives.

`publish-from-repo` = `from-source` call; `--wait` polls the version until
`ready|failed` (poll helper documented like `payments orders wait`).
Envelope kinds `logion.courses.source-link.*`,
`logion.courses.publish-from-repo`, `logion.courses.package-map.validate`.
Mutating commands gated by the companion's confirmation rules (update
`logion-marketplace-companion.md` mutating list).

## 4. Tests

Public: `test_package_map.py` (every validation rule + fixture vectors),
`test_cli_courses_source_link.py`, `test_cli_publish_from_repo.py`
(fake SDK, --wait loop, failure exit 1),
`packages/skillmap/tests/` — `test_precedence.py` (author map > plugin
manifest > scan), `test_exclusion.py`, `test_mirror_dedup.py`
(hash-grouping, canonical-choice ordering), `test_frontmatter.py`,
`test_determinism.py` (double-run byte-equality on every fixture),
`test_fixture_repos.py` (the seven recorded-repo fixtures, pinned counts
and flag sets), `test_cli_package_map_init.py` (write/refuse-overwrite,
`--yes` defaults, exit 2 on unanswered flags, `--json` envelope).

Backend: `test_parse_package_map.py` (same vectors), `test_course_source_links.py`
(link CRUD, scope gating 422, private-repo check, one-link-per-course),
`test_materialize_from_source.py` (tarball fixture on disk — no network:
GithubApiClient faked; asserts the produced version's `capabilities_status`,
provenance columns, dedupe-key idempotency, size cap, traversal fixture
rejected; **mapless tarball → inferred map, `map_source='inferred'`,
flags surfaced as warnings, version still reaches `ready`**),
`test_from_source_endpoint.py` (202 shape, owner-only 403).

## 5. Acceptance criteria

- [ ] A creator with a linked private repo publishes a new version with one
      CLI command; the version passes through the unchanged review pipeline
      and carries `source_repository` + `source_ref_sha` provenance.
- [ ] The identical package map validates locally (CLI) and server-side with
      the same 12+ shared fixtures.
- [ ] `evals.commands` are stored, surfaced, and provably never executed in
      this phase (test asserts no subprocess call in the materializer).
- [ ] Logion-native tarball upload keeps working with zero behavior change
      (regression suite untouched).
- [ ] Repo/private-ness respected: insufficient scope → 422, revoked link →
      409, no repo content persisted beyond the materialized bundle.
- [ ] A repo with **no** map publishes end-to-end: `publish-from-repo`
      against a mapless ref materializes via `logion_skillmap.infer()`
      defaults and the version carries `map_source='inferred'`.
- [ ] `logion_skillmap.infer()` is deterministic (double-run equality) and
      reproduces the pinned component counts/flags for all seven recorded
      repo fixtures; LLM calls are structurally impossible (no network,
      stdlib-only, pinned in `pyproject.toml`).
- [ ] `logion courses package-map init --yes --json` produces a valid map
      (passes `package-map validate`) on every fixture without any
      interactive input.
- [ ] Spec conformance holds end-to-end: every skill component in a
      `ready` version passes the agentskills.io frontmatter rules
      (`skills-ref` vectors pinned), skill directories are byte-identical
      between source and materialized bundle, and no Logion file is
      emitted inside a component root.

## Out of scope

- Executing evals (16.1), bot PRs (15.5), auto-publish on push/webhooks
  (explicitly: publishing stays a human/agent command; no GitHub Actions
  business logic per the parent plan's Don'ts).
- LLM-assisted map inference of any kind — inference is deterministic by
  contract; a future "smart suggestions" layer would sit on top of
  `needs_review`, never inside `logion_skillmap`.

## Implementation appendix — compare against current code

Current repo shape to respect:

- Course upload/version/publish behavior is already in
  `backend repository/packages/api/api/courses/controllers`,
  `api/courses/services`, `api/courses/repositories`, `api/models.py`, and
  tests under `backend repository/packages/api/tests`.
- Background jobs exist under `api/jobs/*`; use that queue/runner style for
  source materialization. Do not invent a second worker framework.
- Public CLI course commands live in `logion/packages/cli/cli/commands`
  and shared bundle parsing exists in `_course_bundle.py` and
  `_course_capabilities.py`.
- Scanners live in `logion/packages/scanners/logion_scanners`; this phase only
  prepares bundles for the existing review pipeline.

Branch targets for 0.1.x live compatibility:

| Work item | Repo | Target branch | Reason |
| --- | --- | --- | --- |
| `course_source_links` table, nullable provenance columns on `course_versions`, backend parser/materializer/endpoints | `backend repository` | `main` | Safe when endpoints require owner auth and linked GitHub identity. Existing upload flow stays unchanged. |
| Contract/OpenAPI export | `backend repository` / workspace docs | `main` | Safe contract addition; generated public client waits for 0.2.0 branch. |
| CLI `courses source-link *`, `publish-from-repo`, package-map local validation, generated SDK | `logion` | `0.2.0` | New user-facing publishing surface must not appear on public 0.1.x `main`. |
| `packages/skillmap` (`logion-skillmap`, stdlib-only, published to PyPI) | `logion` | `0.2.0` | Shared inference dependency of the 0.2.0 CLI and the 15.6 indexer; API consumes the published wheel. |
| Docs/installer copy that teaches repo publishing | `logion` docs | `0.2.0` | Marketing/user docs align with the 0.2.0 CLI. |

Backend implementation steps:

1. Inspect latest Alembic revision. Create migration after it:
   `course_source_links` with `id`, `course_id unique fk courses.id`,
   `provider='github'`, `repository_owner`, `repository_name`,
   `repository_full_name`, `default_ref`, `map_path`, `last_synced_ref`,
   `last_synced_sha`, `last_synced_at`, `status active|revoked`,
   timestamps. Add check constraints and index `repository_full_name`.
2. Same migration adds nullable columns to `course_versions`:
   `source_provider`, `source_repository`, `source_ref`, `source_ref_sha`,
   `source_map_path`.
3. Add model/repository:
   `api/courses/repositories/course_source_links.py`. Methods:
   `get_by_course_id`, `upsert_for_course`, `remove_for_course`,
   `mark_synced`, `mark_revoked`.
4. Add package-map parser in
   `api/courses/services/package_map.py`. Use `yaml.safe_load` if PyYAML is
   already available in API dependencies; otherwise add a justified dependency
   only if the repo already uses YAML elsewhere. Validate with structured
   errors, not regex-only parsing.
5. Package-map schema:
   top-level `schema_version: 1`, `components.capabilities[]` with
   `name`, `entrypoint`, optional `description`, optional `dependencies`,
   optional `include`, optional `exclude`, optional `evals.commands[]`.
   Reject absolute paths, `..`, symlinks escaping root, duplicate names,
   missing entrypoints, and include sets over the 200 MB cap.
6. Add GitHub repo read helper using the 15.1 stored token:
   resolve repo metadata, resolve ref to SHA, download tarball by SHA with
   timeout and byte cap. Use temp dirs and always clean up.
7. Add `SetCourseSourceLinkService`: require owner of course; require active
   GitHub identity; private repo requires `scope_tier='repo'`; check repo read
   access at link time; store metadata only.
8. Add `MaterializeCourseVersionFromSourceService`: use existing upload
   finalization service path. The acceptance criterion is that a repo-produced
   version and a manual upload-produced version pass through the same manifest,
   capability, and review code.
9. Add job handler type `materialize_course_version_from_source` in
   `api/jobs/types.py` and runner registration. Dedupe key:
   `from-source:{course_id}:{sha}`.
10. Add controllers:
    `GET/PUT/DELETE /v1/courses/{course_id}/source-link` and
    `POST /v1/courses/{course_id}/versions/from-source`. Wire them into the
    courses router.

Endpoint shapes:

```json
PUT /v1/courses/{course_id}/source-link
{
  "repository": "owner/repo",
  "ref": "main",
  "map_path": "logion.package.yaml"
}
```

```json
POST /v1/courses/{course_id}/versions/from-source
{
  "ref": "v1.2.0",
  "map_path": "logion.package.yaml"
}
```

Response for `from-source` is HTTP 202:

```json
{
  "job_id": "...",
  "course_id": "...",
  "status": "queued",
  "dedupe_key": "from-source:..."
}
```

Error mapping:

- no active GitHub link -> `409 github_identity_required`;
- private repo with identity scope -> `422 github_scope_insufficient`;
- no repo read access -> `403 github_repository_inaccessible`;
- package-map invalid -> `422 package_map_invalid` with an array of
  `{path, code, message}`;
- tarball too large -> `422 source_too_large`;
- path traversal/symlink escape -> `422 package_map_unsafe_path`.

CLI implementation steps:

1. Extend the existing courses command module; do not create a new top-level
   command.
2. Add `package-map validate` as CLI-local. Reuse the same validation fixtures
   as backend by placing fixtures in a shared test fixture directory or copying
   vectors explicitly with a comment that both suites must stay identical.
3. `publish-from-repo --wait` polls the existing course-version/job status
   endpoint. Use a max timeout and return exit 1 if the version fails.
4. All commands support `--json`; envelope names are exactly those listed in
   section 3.
5. Update companion mutating-command list so agent confirmation covers
   source-link set/remove and publish-from-repo.

Minimum tests:

- Backend parser tests for valid map, duplicate capability, missing
  entrypoint, absolute path, traversal, symlink escape, oversized include,
  eval commands retained but not executed.
- Backend source-link tests for owner-only, one link per course, private-scope
  gate, revoked GitHub identity, repo access failure.
- Backend materializer tests with tarball fixtures and fake GitHub client. Add
  an assertion that no subprocess runner is called for `evals.commands`.
- CLI tests for parser, JSON envelopes, fake SDK calls, local validation, and
  `--wait` success/failure.
- Regression test proving normal tarball upload still creates a ready version.

## Cross-cutting improvement contract

This phase is governed by [`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md). A community improvement proposal is **unfunded by default** and may accept a free GitHub PR/submission, retain contributor attribution and evidence, and merge upstream or become a maintained derivative with lineage. Funding is an explicit prospective conversion: only a confirmed funded bounty creates escrow, payout, or `sh.logion.bounty.accepted.v1`; an unpaid acceptance uses `sh.logion.improvement.accepted.v1` and must write no ledger/payable row. Publication review remains independent in both lanes.
