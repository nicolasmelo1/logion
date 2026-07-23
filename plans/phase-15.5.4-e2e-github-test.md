<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.5.4: Real end-to-end GitHub flow (local-first)

> **Goal.** Prove the entire GitHub-native loop end to end, against a
> **local** API, with a **real** GitHub App, a **real** private repo, and
> **two real GitHub accounts** — but **no real money** (local credits, local
> Stripe). This is the acceptance test for the whole 15.5.x line
> (bounty PR bot 15.5, issue-mention bot 15.5.1, auto-PR submissions 15.5.2)
> plus the missing course→repo link half of
> [15.3](phase-15.3-package-maps-and-repo-publishing.md).
>
> It runs **manually** (the operator drives it; LLM spend via the
> proving-ground agent drivers is acceptable — not automated, never in CI).
> It is expressed as a new **agent-proving-ground scenario** backed by a new
> **GitHub adapter + GitHub assertions**, plus one **product** build (the
> `course source-link` write path).
>
> **This document is written to be executed by an autonomous agent with no
> prior context.** Every stage lists exact files, signatures, error codes,
> tests, and verification commands. Where a signature must be confirmed, the
> exact discovery command is given. Do the stages in order. Do NOT skip the
> "Verify" step at the end of each stage.

---

## 0. Ground truth (read this first — it is why this phase exists)

Facts established by investigation on 2026-07-13 (re-confirm with the grep in
each stage if in doubt):

1. **`course_source_links` exists but has no write path.** Table + model
   (`backend repository/packages/api/api/models.py`, class `CourseSourceLink`,
   ~line 1827), migration (`.../alembic/versions/0035_course_source_links_and_provenance.py`),
   and repository (`.../api/courses/repositories/course_source_links.py`) are
   all on `origin/main`. But `upsert_for_course` is called **only from tests**.
   The bounty PR flow reads it: `open_submission_pr.py:91`
   `source_link = self.source_link_repo.get_by_course_id(bounty.course_id)` →
   `source_link.repository`. With no row, `open-pr` raises
   `BountyPrNoSourceLinkError`. **Stage 1 builds the write path.**
2. **`courses source-link` and `publish-from-repo` CLI do NOT exist** anywhere
   in `logion` (no branch, no tag). Only `courses package-map validate|init`
   (local, no network) + the `logion-skillmap` package shipped. **Stage 1b
   builds the CLI.**
3. **agent-proving-ground has no GitHub surface.** Its "PR" is
   `bounties claim/submit`; no git, no github.com, no OAuth. **Stage 2 builds
   the GitHub observer + assertions + scenario.**
4. **Prod deploy is red since 2026-07-11** (post-`a393d44` image is unhealthy
   at `/health`; deploy script's 60-try loop times out → exit 1). So 15.5.1
   (issue bot) and 15.5.2 (auto-PR) are on `main` but **not live on prod**.
   Local-first sidesteps this. Fixing the deploy is a **separate** task, NOT a
   prerequisite here.
5. **Deployed vs main:** 15.5 (PR + merge policy, PRs #118/#121) IS deployed
   at `a393d44`. Everything after is on-main-only.

---

## 1. Product build: course→repo link (`course_source_links` write path)

**Convention (from 15.3): exactly one PR per repo.** One `backend repository` PR
(Stage 1a), one `logion` PR (Stage 1b). Never split a repo's work.

### Stage 1a — Backend endpoints (`backend repository`, branch off `origin/main`, target `main`)

Branch: `git -C backend repository checkout -b feat/phase-15.5.5-course-source-link origin/main`

**Reference files to read before writing (match their exact style):**
- Controller style: `packages/api/api/courses/controllers/update_course.py`
  (uses `APIRouter(prefix="/courses", tags=["courses"])`,
  `DatabaseSession = Annotated[Session, Depends(get_db)]`,
  `AuthenticatedAgent = Annotated[Agent, Depends(get_authenticated_agent)]`,
  Pydantic request/response models, maps service exceptions to `HTTPException`).
- Router registration: `packages/api/api/courses/controllers/router.py`
  (one `router` per controller file, `router.include_router(...)`).
- Repository (already exists, DO NOT modify): `packages/api/api/courses/repositories/course_source_links.py`. Relevant methods:
  - `get_by_course_id(course_id: uuid.UUID) -> CourseSourceLink | None`
  - `upsert_for_course(*, course_id, provider, repository, default_ref, package_map_path, github_identity_id) -> CourseSourceLink`
  - `remove_for_course(course_id) -> bool` (sets `status='revoked'`)
- GitHub identity repo: `packages/api/api/identity/repositories/github_identities.py`
  - `get_active_by_user_id(user_id: uuid.UUID) -> GithubIdentity | None`
  - `GithubIdentity` has `.scope_tier` (str, e.g. `'repo'`) and `.id`.
- Ownership: a course row has `owner_agent_id`. The authenticated principal is
  an `Agent` (`get_authenticated_agent`). **CONFIRM the Agent→user link:**
  `grep -n "class Agent" -A25 packages/api/api/models.py` — find the FK to
  users (e.g. `user_id`); GitHub identities are keyed by `user_id`. Use it to
  resolve `get_active_by_user_id(agent.user_id)`.
- Course ownership check pattern: read how `UpdateCourseService`
  (`packages/api/api/courses/services/update_course.py`) loads the course and
  raises `CourseAccessDeniedError` when the caller is not the owner. Reuse
  `CourseAccessDeniedError` from `api/courses/exceptions.py`.
- Repo read-access check at link time uses the **user's stored OAuth token**
  (15.1), NOT the App client. **Find the helper:** `grep -rn "def .*repos\|/repos/\|list_repositories\|get_repository" packages/api/api/identity/services/` — 15.1 resolves repos with the stored token during the install/repo-picker flow. Reuse that client to `GET /repos/{owner}/{repo}`. If no single-repo getter exists, add a minimal one in the same 15.1 service module (do not invent a new module). If access fails/404 → `github_repository_inaccessible`.

**FILE TO CREATE:** `packages/api/api/courses/services/set_course_source_link.py`

```python
# Skeleton — fill imports from the reference files above.
import uuid
from dataclasses import dataclass
from sqlalchemy.orm import Session

from api.courses.exceptions import CourseAccessDeniedError
from api.courses.repositories.courses import CourseRepository
from api.courses.repositories.course_source_links import (
    CourseSourceLinkRepository,
)
from api.identity.repositories.github_identities import (
    GithubIdentityRepository,
)

DEFAULT_MAP_PATH = "logion-package-map.yaml"


class GithubIdentityRequiredError(Exception):     # -> 409 github_identity_required
    ...
class GithubScopeInsufficientError(Exception):    # -> 422 github_scope_insufficient
    ...
class GithubRepositoryInaccessibleError(Exception):  # -> 403 github_repository_inaccessible
    ...


@dataclass
class SetSourceLinkInput:
    course_id: uuid.UUID
    repository: str          # "owner/repo", validated: exactly one "/", no spaces
    ref: str                 # default "main" (caller supplies)
    package_map_path: str | None = None


class SetCourseSourceLinkService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.courses = CourseRepository(db)
        self.links = CourseSourceLinkRepository(db)
        self.identities = GithubIdentityRepository(db)

    def execute(self, *, agent, data: SetSourceLinkInput):
        course = self.courses.get(data.course_id)
        if course is None:
            raise CourseAccessDeniedError(...)          # 404/403 per existing convention
        if course.owner_agent_id != agent.id:
            raise CourseAccessDeniedError(...)
        identity = self.identities.get_active_by_user_id(agent.user_id)  # CONFIRM attr
        if identity is None:
            raise GithubIdentityRequiredError(...)
        # Determine repo private-ness via the 15.1 stored-token client:
        repo_meta = <15.1 client>.get_repo(data.repository)   # GET /repos/{owner}/{repo}
        if repo_meta is None:
            raise GithubRepositoryInaccessibleError(...)
        if repo_meta.private and identity.scope_tier != "repo":
            raise GithubScopeInsufficientError(...)
        return self.links.upsert_for_course(
            course_id=course.id,
            provider="github",
            repository=data.repository,
            default_ref=data.ref,
            package_map_path=data.package_map_path or DEFAULT_MAP_PATH,
            github_identity_id=identity.id,
        )
```

**FILE TO CREATE:** `packages/api/api/courses/controllers/course_source_link.py`
Three routes on a single `router = APIRouter(prefix="/courses", tags=["courses"])`:

```text
PUT    /courses/{course_id}/source-link
        body: {repository: str, ref: str = "main", package_map_path: str | None}
        -> 200 SourceLinkResponse {course_id, provider, repository, default_ref,
                                   package_map_path, status, github_identity_id}
GET    /courses/{course_id}/source-link   -> 200 SourceLinkResponse | 404
DELETE /courses/{course_id}/source-link   -> 204 (idempotent; revoked)
```

Exception→HTTP mapping (in the controller, matching update_course.py try/except):
- `CourseAccessDeniedError` → `403` (reuse existing detail/code)
- `GithubIdentityRequiredError` → `409` detail `github_identity_required`
- `GithubScopeInsufficientError` → `422` detail `github_scope_insufficient`
- `GithubRepositoryInaccessibleError` → `403` detail `github_repository_inaccessible`

Validate `repository` with a Pydantic `field_validator`: regex
`^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`.

**FILE TO EDIT:** `packages/api/api/courses/controllers/router.py`
Add `from api.courses.controllers.course_source_link import router as course_source_link_router`
and `router.include_router(course_source_link_router)` (place AFTER the
`purchase_router` line; static path `/courses/{course_id}/source-link` does not
collide with `/courses/mine`).

**FILE TO CREATE:** `packages/api/tests/test_course_source_links_endpoints.py`
Follow the existing test style (`grep -l "get_authenticated_agent\|client.put" packages/api/tests/test_update_course.py` for the auth-fixture + TestClient pattern). Cases (each a named test):
- `test_put_creates_link_owner` — owner PUT → 200, row present, `status='active'`.
- `test_put_upsert_replaces` — second PUT same course → same row updated (one-per-course).
- `test_put_non_owner_403`.
- `test_put_no_github_identity_409` (code `github_identity_required`).
- `test_put_private_repo_insufficient_scope_422` (identity `scope_tier != 'repo'`, faked repo_meta.private=True).
- `test_put_repo_inaccessible_403` (faked 15.1 client returns None).
- `test_get_returns_link_and_404_when_absent`.
- `test_delete_revokes_idempotent`.
Fake the 15.1 repo-metadata client (monkeypatch the service attribute or inject) so tests do NOT hit github.com.

**Contract/OpenAPI export:** after routes compile, run the repo's contract
export (`grep -n "contract-export\|openapi" backend repository/Makefile` — likely
`make contract-export` at workspace root or in backend repository). Commit the
regenerated `contracts/openapi/v1.json` (or wherever it lands) in the SAME PR.

**Verify Stage 1a:**
```bash
cd backend repository
uv run pytest packages/api/tests/test_course_source_links_endpoints.py -q
uv run ruff check packages/api/api/courses
# manual: start local API, PUT a link, GET it back (see Stage 3 §3)
```

### Stage 1b — CLI (`logion`, branch off the CLI mainline, target the 0.2.0 line)

> New user-facing surface must NOT appear on public `0.1.x` main (15.3 branch
> policy). Confirm the current CLI release branch/tag with
> `git -C logion log --oneline -3` and `cat logion/packages/cli/pyproject.toml | grep version` (was `0.1.13`). Create branch `feat/phase-15.5.5-source-link-cli`.

**Reference files:**
- Command package: `logion/packages/cli/cli/commands/courses/` (it is a
  package). Parser wiring: `.../courses/parser.py` (`register_*` calls) and
  `.../courses/parser_sections.py`. Package-map subcommand for style:
  `.../courses/package_map.py` (`register_package_map`).
- Common flags: `logion/packages/cli/cli/_options.py` (`COMMON_PARSER`:
  `--api-key --base-url --json --timeout --max-retries --no-onboarding`).
- Envelope/output helpers: read how `package_map.py` prints JSON envelopes.
- SDK: the generated client the CLI calls (grep for how `courses purchase`
  calls the SDK — `grep -rn "def .*purchase\|courses" logion/packages/cli/cli/commands/courses/*.py` and follow to the SDK package). The SDK is generated from the contract — find the generation command: `grep -rn "generate\|openapi" logion/Makefile logion/packages/*/pyproject.toml`.

**FILE TO CREATE:** `logion/packages/cli/cli/commands/courses/source_link.py`
Register a `source-link` subparser with three actions:
```
logion courses source-link set    COURSE_ID --repository owner/repo --ref main [--map PATH] [--json]
logion courses source-link show   COURSE_ID [--json]
logion courses source-link remove COURSE_ID [--yes]
```
- `set` → SDK `PUT /courses/{id}/source-link`; envelope kind
  `logion.courses.source-link.set`.
- `show` → `GET`; kind `logion.courses.source-link.show`; exit non-zero on 404
  with a clear message.
- `remove` → `DELETE`; kind `logion.courses.source-link.remove`; gated by
  `--yes` (destructive-confirm like other remove commands).

**FILE TO EDIT:** `logion/packages/cli/cli/commands/courses/parser.py`
Import and call `register_source_link(sub)` alongside the other `register_*`
calls (add `source-link` to the registered subgroup list).

**SDK regeneration:** run the generation command found above so the SDK exposes
the three new operations (operation ids `set_course_source_link`,
`get_course_source_link`, `delete_course_source_link` — match the backend
`operation_id`s). Commit generated SDK in the same PR.

**Companion mutating list:** add `courses source-link set` and
`courses source-link remove` to the companion's mutating-command list.
`grep -rn "mutating\|source-link\|package-map" logion/**/logion-marketplace-companion.md` (or the companion markdown under `logion/packages/*/`), and add the two entries next to the existing mutating course commands.

**FILE TO CREATE:** `logion/packages/cli/tests/test_cli_courses_source_link.py`
Style: copy an existing CLI test that uses the fake SDK
(`grep -l "fake" logion/packages/cli/tests/test_cli_courses_*.py`). Cases:
- `set` calls SDK PUT with parsed args; prints/JSON-envelopes the result.
- `show` renders the link; 404 → exit 1.
- `remove` requires `--yes`; calls DELETE.

**Verify Stage 1b:**
```bash
cd logion
uv run pytest packages/cli/tests/test_cli_courses_source_link.py -q
uv run logion courses source-link --help    # shows set/show/remove
```

---

## 2. agent-proving-ground: GitHub observer + assertions + scenario (`logion`, same 0.2.0-line branch or a dedicated one)

**Reference (read first):**
- Structure: `logion/packages/agent-proving-ground/agent_proving_ground/`.
- Assertions registry: `assertions/registry.py` (maps `type` string → class).
- Assertion classes: `assertions/api.py`, `assertions/db.py`, etc. (each has a
  `check(world, params) -> AssertionOutcome`-style method — read one to copy
  the signature exactly).
- Real query handlers: `api_adapters/_queries.py` (`_q_<query_type>` methods on
  `LogionApiQueries`, baseline-delta filtering via `_baseline_ids`).
- Mock handlers: `api_adapters/mock.py` (a `match`/`case` on query type).
- Redaction: `redaction.py` already scrubs `gh[pousr]_` and `github_token=`.
  Keep the `timeline.no_unredacted_secret` final assertion.
- Scenario schema: `scenarios/schema.py` (`ScenarioSpec/AgentSpec/PhaseSpec/AssertionSpec`, `devrig_role` enum = seller|buyer|admin).
- Template scenario: `scenarios/builtin/marketplace_loop.yaml`.
- README authoring section: `packages/agent-proving-ground/README.md`.

### Stage 2a — GitHub observer

**FILE TO CREATE:** `packages/agent-proving-ground/agent_proving_ground/api_adapters/github_observer.py`
A small class that queries **github.com** via the `gh` CLI (subprocess) or REST
with a token from env. It is an OBSERVER used by assertions — it does NOT
replace the Logion adapter.
```python
class GithubObserver:
    def __init__(self, *, token: str, repo: str) -> None: ...
    def pr_exists(self, *, head_branch: str | None = None, marker: str | None = None) -> dict | None: ...
    def pr_state(self, pr_number: int) -> str: ...        # "open"|"merged"|"closed"
    def pr_body_contains(self, pr_number: int, needle: str) -> bool: ...
    def issue_comments(self, issue_number: int) -> list[dict]: ...   # for bot-comment match
    def installation_delivered(self) -> bool: ...          # optional; App Recent Deliveries
```
Token env keys: `LOGION_PROVING_GROUND_GH_TOKEN_CREATOR`,
`LOGION_PROVING_GROUND_GH_TOKEN_BUYER`. If a token is absent, observer methods
return a sentinel that makes dependent assertions `unsupported` (skipped if
`optional: true`, failed otherwise) — mirror the `RoleKeyStore`
missing-key behavior in `_queries.py`.

### Stage 2b — New assertion types

**FILE TO EDIT:** `assertions/registry.py` — register these `type` strings.
**FILE TO EDIT:** `assertions/api.py` (or a new `assertions/github.py`) — the classes.
**FILE TO EDIT:** `api_adapters/_queries.py` — add `_q_<type>` handlers.
**FILE TO EDIT:** `api_adapters/mock.py` — add a `case` per type returning deterministic fixture data.

| assertion `type` | params | passes when |
| --- | --- | --- |
| `api.source_link_exists` | `course`, `repository` | GET source-link returns active link to `repository` |
| `api.bounty_submission_pr_opened` | `bounty`, `submission` | submission has `github_pr.status == "opened"` and a `pr_url` |
| `api.bounty_submission_accepted` | `bounty`, `submission` | submission `status == "accepted"` |
| `api.bounty_submission_rejected` | `bounty`, `submission` | submission not accepted after PR close |
| `github.pr_exists` | `marker` or `head_branch` | observer.pr_exists(...) is not None |
| `github.pr_merged` | `pr_number` (or resolve by marker) | observer.pr_state == "merged" |
| `github.pr_closed_unmerged` | `pr_number` | observer.pr_state == "closed" (not merged) |
| `github.issue_bot_comment_matches` | `issue`, `pattern` | some comment author is `<bot>[bot]` and body matches regex |
| `github.installation_delivered` | (none) | observer.installation_delivered() (optional:true) |

For the `api.*` ones, reuse the existing Logion query plumbing (they hit
`/v1/courses/{id}/source-link`, `/v1/bounties/{id}/submissions`). For the
`github.*` ones, the handler constructs a `GithubObserver` from env token +
the scenario's repo (pass repo via assertion params or scenario `env`).

**FILE TO EDIT (tests):** `packages/agent-proving-ground/tests/` — add unit
tests for each new assertion against the mock adapter (copy an existing
assertion unit test). `make agent-proving-ground-test` must pass.

### Stage 2c — Scenario

**FILE TO CREATE:** `scenarios/builtin/github_bounty_e2e.yaml`
```yaml
schema_version: "1"
name: github_bounty_e2e
description: Full GitHub-native loop — publish, link repo, issue-mention bounty, PR, merge/accept, close/reject.
api_adapter: local-devrig
agents:
  - {id: creator,  role: Course creator/owner, driver: claude-code, devrig_role: seller}
  - {id: buyer,    role: Buyer/worker,          driver: claude-code, devrig_role: buyer}
  - {id: operator, role: Admin observer,        driver: scripted,    devrig_role: admin}
phases:
  - id: link_repo          # after course published + repo created out-of-band (Stage 3 §1-3)
    actor: creator
    goal: "Link the published course to the test repo via `logion courses source-link set`."
    assertions:
      - {type: api.source_link_exists, params: {course: "${COURSE_ID}", repository: "${REPO}"}}
  - id: issue_bounty
    actor: creator
    goal: "Open an issue and comment `@<bot> bounty 250`, then `@<bot> confirm`."
    assertions:
      - {type: github.issue_bot_comment_matches, params: {issue: "${ISSUE_1}", pattern: "confirm|250 credits"}}
      - {type: api.bounty_exists, params: {status: funded}}
  - id: submit_pr
    actor: buyer
    goal: "Do the work and `logion bounties submissions create <BOUNTY> --github-pr`."
    assertions:
      - {type: api.bounty_submission_pr_opened, params: {bounty: "${BOUNTY_1}", submission: "${SUB_1}"}}
      - {type: github.pr_exists, params: {marker: "logion:bounty_submission"}}
  - id: merge_accept
    actor: creator
    goal: "Merge the PR as the course owner."
    assertions:
      - {type: github.pr_merged, params: {pr_number: "${PR_1}"}}
      - {type: api.bounty_submission_accepted, params: {bounty: "${BOUNTY_1}", submission: "${SUB_1}"}}
      - {type: api.credit_balance_changed, params: {role: buyer, direction: increase}}
  - id: close_reject       # second bounty/submission opened out-of-band or in earlier phases
    actor: creator
    goal: "Close the second PR without merging."
    assertions:
      - {type: github.pr_closed_unmerged, params: {pr_number: "${PR_2}"}}
      - {type: api.bounty_submission_rejected, params: {bounty: "${BOUNTY_2}", submission: "${SUB_2}"}}
final_assertions:
  - {type: timeline.no_unredacted_secret}
```
Placeholders (`${...}`) are resolved from scenario `env`/run outputs — follow
how `marketplace_loop.yaml` threads ids (it uses per-run unique slugs from
`LOGION_PROVING_GROUND_RUN_ID`). If the framework has no id-threading, the
operator supplies them via env before the run; document that in the scenario
description.

**Verify Stage 2:**
```bash
cd logion
make agent-proving-ground-verify        # lint+typecheck+dead-code+test
uv run logion-agent-proving-ground validate builtin:github_bounty_e2e
```

---

## 3. Operator setup + the 12-step manual run

### 3.0 Accounts / tokens / tunnel (once)
| Role | GitHub | Logion home |
| --- | --- | --- |
| Creator/owner | `nicolasmelo12+logion@gmail.com` (`nicolas-logion`) | `LOGION_HOME=~/.logion-creator` |
| Buyer/worker | `nicolasmelo1` (`nicolasmelo12@gmail.com`) | `LOGION_HOME=~/.logion-buyer` |

- `gh` is logged in as `nicolasmelo1` → buyer git side.
- Creator: make a **fine-grained PAT** on `nicolasmelo12+logion` scoped to the
  one test repo (Contents RW, Issues RW, Pull requests RW, Metadata R); use via
  `GH_TOKEN=<pat> gh ...`.
- Tunnel: `ngrok http 8000` (or a `smee.io` channel per the 15.5.3 runbook).

### 3.1 Local rig + local App (Stage 0 of the run)
```bash
make dev-up MODE=prod          # local API on :8000; writes .devrig/devrig.env
make dev-seed                  # local credits to seller/buyer
ngrok http 8000                # note https://<id>.ngrok.app
```
Register GitHub App **`logion-bot-local`** (DO NOT touch prod `logion-bot`):
same permissions/events as 15.5.3 (Contents RW, Issues RW, Pull requests RW,
Metadata R; events Issues, Issue comment, Pull request), webhook URL
`https://<id>.ngrok.app/v1/webhooks/github`, fresh `openssl rand -hex 32`
secret. Put the four `LOGION_GITHUB_APP_*` vars (incl.
`LOGION_GITHUB_APP_BOT_LOGIN=logion-bot-local`) into `canonical maintainer workspace/.env.local`,
restart local API (`make dev-api`). Verify: unsigned
`curl -X POST http://localhost:8000/v1/webhooks/github -d '{}'` → **400**
(not 503).

### 3.2 The 12 steps
`L_CREATOR="LOGION_HOME=~/.logion-creator logion --base-url http://localhost:8000"`
`L_BUYER="LOGION_HOME=~/.logion-buyer logion --base-url http://localhost:8000"`

1. **Onboard + link GitHub.** `$L_CREATOR identity onboarding --email nicolasmelo12+logion@gmail.com --agent-name creator`; same for buyer. Then `$L_CREATOR identity github ...` (creator, request `repo` scope for private) and `$L_BUYER identity github ...`.
2. **Create private repo (creator).** `GH_TOKEN=<pat> gh repo create nicolas-logion/logion-bounty-smoke --private --clone`. Seed a `SKILL.md` (inspiration: browse an existing skill) + `logion-package-map.yaml` (`logion courses package-map init`). Install `logion-bot-local` on this repo → **Only select repositories**. Confirm the `installation` delivery is green 200 (App → Advanced → Recent Deliveries) and a `github_app_installations` row appears locally.
3. **Publish course (creator).** `$L_CREATOR courses create --title "Bounty Smoke" --slug bounty-smoke-<runid>`; upload content via `courses uploads create/complete/push` (tarball — NOT publish-from-repo, which is out of scope). Then link the repo: `$L_CREATOR courses source-link set <COURSE_ID> --repository nicolas-logion/logion-bounty-smoke --ref main`.
4. **Buyer acquires.** `$L_BUYER courses purchase <COURSE_ID> --yes`.
5. **Issue-mention bounty (creator, on GitHub).** Open an issue; comment `@logion-bot-local bounty 250`. Bot replies asking to confirm (250 credits, course named). Comment `@logion-bot-local confirm` → bot replies with bounty URL; `$L_CREATOR bounties get <id>` shows `funded`, reward 250. **Negative:** a single `@logion-bot-local bounty 250 confirm` comment must NOT open; a non-owner comment must get the polite refusal.
6. **Buyer submits.** `$L_BUYER bounties submissions create <BOUNTY_ID> --title "fix" --github-pr`.
7. **PR materializes** as a draft by `logion-bot-local[bot]` carrying `<!-- logion:bounty_submission:... -->`. If buyer lacks push access, follow the CLI's fork-required instructions (fork, push to the printed branch, open PR with the marker).
8. **Owner merges.** `GH_TOKEN=<pat> gh pr merge <n> --merge` (as creator). Within seconds submission → `accepted`, payable accrues; `$L_CREATOR bounties get <id>` and `$L_BUYER payments cash-out`/balance confirm.
9. **Second bounty (creator):** new issue → `@logion-bot-local bounty N` → confirm.
10. **Buyer submits** the second (repeat 6-7).
11. **Owner closes without merging** (`gh pr close <n>`): submission must NOT be accepted, no payout. Verify via `bounties get`.
12. **Negative merge policy:** merge by any non-owner → `merger_not_course_owner`, nothing changes.

### 3.3 Teardown
Delete the test repo (`gh repo delete nicolas-logion/logion-bounty-smoke --yes`),
uninstall `logion-bot-local`, `make dev-reset` (truncate local marketplace
tables), stop ngrok.

---

## 4. Acceptance criteria
- [x] Stage 1a: `test_course_source_links_endpoints.py` green; routes in OpenAPI; owner-only + scope + repo-access errors correct. (PR backend repository#129)
- [x] Stage 1b: `courses source-link set/show/remove` work against local API; SDK regenerated; companion mutating list updated. (PR logion#188; `set`/`show` exercised live 2026-07-15)
- [x] Stage 2: `make agent-proving-ground-verify` green; `validate builtin:github_bounty_e2e` passes; new assertions unit-tested.
- [x] `open-pr` no longer raises `BountyPrNoSourceLinkError` once a link exists. (PRs #3/#4/#6 opened on nicolas-logion/logion-bounty-smoke)
- [x] Local run 2026-07-15: local endpoint 400 (not 503); installation row 146760369 present; issue-mention bounty funds (d18942b7, 9d6d4aa6, 4c0d0480 — 250 credits each); owner-merge accepts + payable accrues (submission 3ecc1824 accepted, 213 cents accrued); close-unmerged rejects (PR #4, submission 2db049c9 not accepted); non-owner merge → `merger_not_course_owner` (PR #6 merged by nicolasmelo1, `merge_policy_rejected` event, nothing changed).
- [x] No real money moved (credits via local admin-grant ledger; Stripe untouched); no secret leaks (api.log, issue comments, PR bodies scanned clean).
- [ ] Test repo deleted, `logion-bot-local` uninstalled. (teardown pending)

## 5. Out of scope
- Full `publish-from-repo` materializer (rest of 15.3) — separate phase.
- Fixing the prod deploy pipeline — separate task (post-`a393d44` image unhealthy at `/health`; needs a live repro to read `docker logs`).

## 6. PR plan (one per repo — 15.3 convention)
1. `backend repository` PR (branch `feat/phase-15.5.5-course-source-link`): Stage 1a + contract export.
2. `logion` PR: Stage 1b (CLI + SDK + companion) **and** Stage 2 (proving-ground observer + assertions + scenario) — both are in the `logion` repo; keep as one PR on the 0.2.0 line, or split CLI vs proving-ground if reviewers prefer.
3. `canonical maintainer workspace` PR: this plan file.

## 7. Reference
- 15.3 endpoint/schema design: [phase-15.3](phase-15.3-package-maps-and-repo-publishing.md)
- App registration / smee option: [phase-15.5.3](phase-15.5.3-logion-bot-github-app-registration-runbook.md)
- Bounty PR + merge policy (deployed): [phase-15.5](phase-15.5-bounty-pr-bot-and-merge-policy.md)
- Issue-mention bot (on main): [phase-15.5.1](phase-15.5.1-issue-mention-bounty-bot.md)
- Auto-PR submissions (on main): [phase-15.5.2](phase-15.5.2-auto-github-pr-submissions.md)
- Proving-ground authoring: `logion/packages/agent-proving-ground/README.md`

## Cross-cutting improvement contract

This phase is governed by [`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md). A community improvement proposal is **unfunded by default** and may accept a free GitHub PR/submission, retain contributor attribution and evidence, and merge upstream or become a maintained derivative with lineage. Funding is an explicit prospective conversion: only a confirmed funded bounty creates escrow, payout, or `sh.logion.bounty.accepted.v1`; an unpaid acceptance uses `sh.logion.improvement.accepted.v1` and must write no ledger/payable row. Publication review remains independent in both lanes.
