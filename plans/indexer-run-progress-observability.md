<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Indexer Run Progress Observability Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make every production indexer run externally inspectable while it is active and leave a durable, aggregate receipt when it completes or fails.

**Architecture:** Reuse the existing `indexing_runs.stats` JSON field rather than adding a new event table. The private API will expose authenticated admin operations to update and read a still-open run. The public indexer will open the run before discovery, publish redacted aggregate snapshots at bounded stage and adapter boundaries, record final completion in a `finally` block, and emit the same structured progress lines to stderr. This preserves a low-write aggregate audit trail while making failure state, current stage, elapsed time, counts, and adapter errors observable.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic, pytest, `logion-indexer` CLI, existing admin indexing API.

---

## Acceptance criteria

- An admin can retrieve an indexing run during and after execution through `GET /v1/admin/indexing/runs/{run_id}`.
- An open run accepts `PATCH /v1/admin/indexing/runs/{run_id}/progress` with a validated aggregate snapshot; a closed run returns `409` and a missing run returns `404`.
- The snapshot stores only aggregate fields: `stage`, `status`, `discovered`, `resolved`, `deduped`, `created`, `updated`, `skipped`, `errors`, `partial`, `adapter_counts`, `adapter_errors`, `started_at`, and `updated_at`. No raw request bodies, credentials, HTML, stack traces, or unbounded per-item lists may be persisted.
- `logion-indexer run` opens its audit run before discovery; it writes snapshots at `discovering`, after each adapter, `enriching`, `planning`, `pushing`, and terminal `completed` or `failed` states.
- Terminal state is written even when discovery, planning, or push raises unexpectedly. The process keeps its correct non-zero exit code; a failure to publish progress must not mask the primary pipeline error.
- Human output is line-buffered, machine-readable JSON Lines on stderr, prefixed `indexer-progress `; ordinary final `run:` summary remains stable.
- Progress writes are bounded: per adapter plus stage transitions and successful push batches, never per listing.
- The existing `completion` endpoint remains the authoritative close operation and persists the terminal aggregate stats.
- Tests cover API authorization, validation, open/closed lifecycle, aggregate-only persistence, successful CLI checkpoints, adapter partial failure, unexpected failure, and progress-write failure tolerance.

---

### Task 1: Define the backend progress and read contracts

**Objective:** Add the admin-only API surface that persists and retrieves aggregate snapshots without schema changes.

**Files:**
- Create: `backend repository/packages/api/api/indexing/controllers/get_indexing_run.py`
- Create: `backend repository/packages/api/api/indexing/controllers/update_indexing_run_progress.py`
- Create: `backend repository/packages/api/api/indexing/services/get_indexing_run.py`
- Create: `backend repository/packages/api/api/indexing/services/update_indexing_run_progress.py`
- Modify: `backend repository/packages/api/api/indexing/repositories/indexing_runs.py`
- Modify: existing indexing controller registration module
- Test: `backend repository/packages/api/tests/indexing/test_indexing_run_progress.py`

**Step 1: Write failing API tests**

Cover:
- `GET` returns `run_id`, `status`, `stats`, `created_at`, `updated_at`, and `closed_at` for an admin-created run.
- non-admin receives `403`; unknown IDs receive `404`.
- `PATCH /progress` updates only an open run, returns the persisted snapshot, and a later `GET` returns the same data.
- closed runs return `409` on progress writes.
- Pydantic rejects unknown properties, negative counts, malformed timestamps, an unbounded adapter error list, and values outside the fixed stage/status literals.

**Step 2: Run focused test and verify failure**

Run:
```bash
cd $HOME/workspaces/personal/backend repository
env -u VIRTUAL_ENV uv run pytest packages/api/tests/indexing/test_indexing_run_progress.py -q
```

Expected: collection or route failures before implementation.

**Step 3: Implement minimal validated contracts**

Use a strict Pydantic model with non-negative integer counters, `adapter_counts: dict[str, int]` limited to 64 keys, and `adapter_errors: dict[str, str]` limited to 64 sanitized single-line values of at most 500 characters. Allow only the fixed lifecycle states `running`, `completed`, and `failed`, and stages `discovering`, `enriching`, `planning`, `pushing`, and `completed`.

Do not add a migration: `IndexingRun.stats` is already JSON and `TimestampMixin.updated_at` already gives update time. Extend the repository with an open-only update that refuses a closed row. Keep completion as the only operation that sets `closed_at`.

**Step 4: Re-run focused tests**

Expected: all progress endpoint tests pass.

**Step 5: Commit**

```bash
git add packages/api/api/indexing packages/api/tests/indexing
git commit -m "feat(indexing): expose run progress"
```

---

### Task 2: Add an aggregate progress reporter to the public indexer

**Objective:** Publish durable, redacted checkpoints and structured stderr output while the CLI advances through the pipeline.

**Files:**
- Create: `logion/packages/indexer/logion_indexer/progress.py`
- Modify: `logion/packages/indexer/logion_indexer/cli.py`
- Modify: `logion/packages/indexer/logion_indexer/pusher.py`
- Test: `logion/packages/indexer/tests/test_progress.py`
- Test: `logion/packages/indexer/tests/test_cli_diagnostics.py`
- Test: `logion/packages/indexer/tests/test_pusher.py`

**Step 1: Write failing unit tests**

Cover:
- A reporter emits a redacted `indexer-progress {json}` stderr line with a stable, sorted JSON object.
- It sends only aggregate counters and bounded per-adapter summaries to `PATCH /v1/admin/indexing/runs/{id}/progress`.
- `Pusher` emits a callback after every successful batch so long pushes advance persisted counters.
- A progress API error is emitted as a local diagnostic but does not raise or change the main command’s result.

**Step 2: Run focused tests and verify failure**

Run:
```bash
cd $HOME/workspaces/personal/logion
env -u VIRTUAL_ENV uv run --package logion-indexer pytest packages/indexer/tests/test_progress.py packages/indexer/tests/test_cli_diagnostics.py packages/indexer/tests/test_pusher.py -q
```

Expected: import and behavior failures before implementation.

**Step 3: Implement the reporter**

Create `RunProgress` as a small dataclass that owns the run ID, `RunStats`, stage, adapter counts/errors, and start time. It must:

1. construct an aggregate snapshot;
2. sanitize adapter errors through the existing `_safe_detail` logic or an extracted shared helper;
3. write a deterministic JSON Lines record to stderr with `flush=True`;
4. call the new progress endpoint through `Transport.patch`; and
5. catch and report progress publication errors without interrupting the pipeline.

Add an optional progress callback to `Pusher.push_serialized`/`push_batch`; call it only after a batch response has been absorbed. Preserve the existing public behavior when no callback is supplied.

**Step 4: Re-run focused tests**

Expected: all tests pass and no credentials appear in output or fake transport call logs.

**Step 5: Commit**

```bash
git add packages/indexer/logion_indexer packages/indexer/tests
git commit -m "feat(indexer): report aggregate run progress"
```

---

### Task 3: Wire full-run lifecycle and terminal failure receipts

**Objective:** Ensure `run` publishes checkpoints from before discovery through either completion or a durable failed terminal state.

**Files:**
- Modify: `logion/packages/indexer/logion_indexer/cli.py`
- Test: `logion/packages/indexer/tests/test_cli_diagnostics.py`

**Step 1: Write failing command-level tests**

Cover:
- `cmd_run` opens a run before `_discover_all` and reports `discovering` before the first adapter begins.
- It reports an adapter-boundary aggregate after each configured seed source.
- It reports `enriching`, `planning`, and `pushing` stage transitions in order.
- An adapter partial failure yields terminal `completed` with `partial=true` and its sanitized adapter error in `adapter_errors`.
- An unexpected `build_indexing_plan` or push failure yields terminal `failed`, preserves the original exception/non-zero result, and calls the existing completion endpoint with `partial=true` when the audit run was opened.

**Step 2: Run the narrowed command tests and verify failure**

Run:
```bash
cd $HOME/workspaces/personal/logion
env -u VIRTUAL_ENV uv run --package logion-indexer pytest packages/indexer/tests/test_cli_diagnostics.py -q
```

**Step 3: Implement lifecycle control**

Refactor only enough to expose progress boundaries:

- Have discovery accept an optional callback invoked once before each adapter and once after either success or failure.
- Open the remote run before discovery in non-dry-run `cmd_run`.
- Use `try`/`except`/`finally` so a terminal snapshot is attempted after every path. Never swallow the primary exception and never claim success if completion fails.
- On normal terminal flow, pass the complete aggregate snapshot to `close_run` so the database receipt is self-contained.
- In `--dry-run`, emit local checkpoints but do not open, update, or close a server-side audit run.

**Step 4: Re-run narrowed tests**

Expected: lifecycle ordering, terminal receipts, partial handling, and graceful progress failure behavior pass.

**Step 5: Commit**

```bash
git add packages/indexer/logion_indexer/cli.py packages/indexer/tests/test_cli_diagnostics.py
git commit -m "fix(indexer): persist terminal run receipts"
```

---

### Task 4: Update operator documentation and coordinated contracts

**Objective:** Document how to follow an active run and retrieve its aggregate receipt, keeping the three repositories aligned.

**Files:**
- Modify: relevant `logion` indexer README or package documentation
- Modify: `canonical maintainer workspace/maintainer documentation: api.md`
- Modify: `canonical maintainer workspace/plans/phase-15.6-external-skillhub-indexer.md` only if its endpoint inventory needs a current-shape correction
- Test: existing documentation-link and public-audit checks

**Step 1: Add concise operator instructions**

Document the JSON Lines stderr records and the authenticated admin `GET /v1/admin/indexing/runs/{run_id}` endpoint. State explicitly that counters are aggregate, progress is checkpoint-based rather than per listing, and adapter errors are sanitized/bounded.

**Step 2: Verify documentation checks**

Run:
```bash
cd $HOME/workspaces/personal/logion
make ci-checks
cd $HOME/workspaces/personal/canonical maintainer workspace
make doctor
```

**Step 3: Commit each repository independently**

```bash
git add <changed-files>
git commit -m "docs: document indexer run progress"
```

---

### Task 5: Full verification, PRs, CI, and review closure

**Objective:** Verify the cross-repository feature end-to-end and publish reviewable PRs without auto-merging.

**Files:** all changed files from Tasks 1–4.

**Step 1: Run repository verification**

```bash
cd $HOME/workspaces/personal/backend repository
env -u VIRTUAL_ENV uv run pytest packages/api/tests/indexing -q
env -u VIRTUAL_ENV uv run ruff check packages/api/api/indexing packages/api/tests/indexing
env -u VIRTUAL_ENV uv run ruff format --check packages/api/api/indexing packages/api/tests/indexing
env -u VIRTUAL_ENV uv run mypy packages/api/api/indexing

cd $HOME/workspaces/personal/logion
env -u VIRTUAL_ENV uv run --package logion-indexer pytest packages/indexer/tests -q
make ci-checks
```

**Step 2: Inspect actual diffs**

Run `git diff --check`, `git diff --stat origin/main...HEAD`, and inspect the exact changed files. Ensure no raw exception trace, secret, or per-item payload can be persisted or logged.

**Step 3: Push branches and open PRs**

Create one PR per repository on `feat/indexer-run-progress`, link them to each other, and include validation output. Do not auto-merge.

**Step 4: Drive CI and reviews to green**

Check CI, wait for automated reviews on the current SHA, read all review comments, fix all valid root causes, rerun local checks, push, and re-check. End only with green CI and no unresolved valid comments.
