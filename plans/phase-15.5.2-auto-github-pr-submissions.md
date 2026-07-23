<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.5.2: Auto GitHub PR Submissions (default-on materialization + webhook auto-register)

> Paradigm simplification of [`phase-15.5`](phase-15.5-bounty-pr-bot-and-merge-policy.md)'s
> two-command PR flow. Today a contributor runs `submissions create`, then
> `submissions open-pr`, and (fork path) `submissions register-pr`. After
> this phase the happy path is **one command**: `submissions create`
> materializes the PR by default, and fork-path PRs are **auto-registered
> by the webhook via the body marker** — `register-pr` is deleted;
> `open-pr` is demoted to a repair command. A creator-side per-bounty flag
> (`accepts_github_prs`, default on) controls whether the PR lane is
> offered at all. **PRs: exactly one per repo** — one `backend repository` PR
> (flag + composition service + webhook auto-register + endpoint removal)
> and one `logion` PR (CLI flag, `register-pr` removal, rendering).
>
> Non-negotiable rules carried forward, plus one new:
>
> ```text
> GitHub merge != publication approval          (15.5, unchanged)
> GitHub PR    != bounty payout until policy    (15.5, unchanged)
> A submission NEVER fails because its PR failed — PR materialization
> degrades honestly (status + reason in the response), it never aborts.
> Auto-register binds a PR to a submission ONLY when the PR author's
> GitHub id equals the submitter's linked identity. A marker alone is
> never enough.
> ```
>
> The last rule closes a real attack the authenticated `register-pr`
> command used to close: submission ids leak (creator sees them; the
> marker is public in the first PR), so without the author pin anyone
> could open a hostile PR carrying someone else's marker — the owner
> merges "the submission", the merge policy accepts, and the innocent
> submitter is paid for the attacker's code. The author pin is the
> replacement for the command's auth, and it is DB-and-test enforced.

## Rollout safety (why default-on is safe to deploy)

The auto lane fires only when `accepts_github_prs` AND an active
`course_source_links` row AND an active `github_app_installations` row all
hold. Until the App is registered and installed
([15.5.3](phase-15.5.3-logion-bot-github-app-registration-runbook.md)),
no bounty satisfies this — deploying is a no-op for every existing flow.
The `register-pr` endpoint being removed shipped only on the unreleased
`0.2.0` CLI branch; no released client calls it.

## 1. Creator-side flag (`backend repository` PR)

### 1.1 Migration `0039_bounty_accepts_github_prs.py`

(Renumber to the next free revision; chain onto the current head — run
`alembic heads` first.)

```python
def upgrade() -> None:
    op.add_column(
        "bounties",
        sa.Column(
            "accepts_github_prs",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("bounties", "accepts_github_prs")
```

Model: add to `Bounty` in `api/models.py`, after `funding_mode`:

```python
    accepts_github_prs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
```

Extend the `tests/test_database_schema.py` snapshot.

### 1.2 Create + update surface

- `CreateBountyService.execute(...)` gains keyword
  `accepts_github_prs: bool = True`, passed to `bounty_repo.create`.
- `CreateBountyRequest` (controller) gains
  `accepts_github_prs: bool = True`.
- New endpoint (small, creator-only — the only mutable field):

```text
PATCH /v1/bounties/{bounty_id}   auth: bounty creator
      body: {accepts_github_prs: bool} -> 200 GetBountyResponse
```

New service `api/bounties/services/update_bounty.py`
(`UpdateBountyService.execute(bounty_id, agent_id, *, accepts_github_prs)`):
creator-only (`BountyAccessDeniedError` otherwise), allowed in any
non-terminal status, sets the flag, commits. Turning it **off** does not
close already-registered PRs (they stay; the merge policy still governs
them) — it stops **new** materialization/registration only. Pin this in a
test.

### 1.3 Read surface — advertise the lane

`GetBountyResponse` and the list serializer gain one **computed** field:

```python
    github_pr_enabled: bool
    # accepts_github_prs AND active course_source_link AND active
    # installation for that repository. Computed by a small helper
    # `bounty_github_pr_enabled(db, bounty) -> bool` in
    # api/bounties/services/github_pr_availability.py — single source of
    # truth reused by §2 (grep-pin: the three-condition check exists once).
```

This is how agents discover that the default will work — no flag needed on
the happy path.

## 2. Submission-time materialization (`backend repository` PR)

### 2.1 Request/response contract

`CreateBountySubmissionRequest` gains:

```python
    github_pr: bool | None = None
    # None (default) = auto: materialize when github_pr_enabled
    # True           = require the lane; if unavailable the SUBMISSION
    #                  still succeeds and the block carries the reason
    # False          = never materialize
```

`CreateBountySubmissionResponse` gains a nested block (always present):

```python
class SubmissionGithubPrBlock(BaseModel):
    status: str
    # 'opened' | 'fork_required' | 'disabled' | 'skipped' | 'failed'
    pr_url: str | None = None
    head_branch: str | None = None
    pr_body: str | None = None      # fork_required only: paste-ready body
    reason: str | None = None
    # disabled -> 'creator_disabled' | 'no_source_link' | 'app_not_installed'
    # skipped  -> 'client_opt_out'
    # failed   -> the BountyPrError.code or 'github_error'
```

### 2.2 `CreateSubmissionWithPrService` — `api/bounties/services/create_submission_with_pr.py`

Thin composition; **neither inner service is modified**:

```python
@dataclass
class CreateSubmissionWithPrResult:
    submission: BountySubmission
    github_pr: dict  # the §2.1 block


class CreateSubmissionWithPrService:
    def __init__(self, db: Session, *, github_client_factory=None) -> None:
        self.db = db
        self._client_factory = (
            github_client_factory or make_github_client_factory(db=db)
        )

    def execute(self, *, bounty_id, submitter_agent_id, title, description,
                proposed_course_version_id=None, evidence=None,
                github_pr: bool | None = None) -> CreateSubmissionWithPrResult:
        submission = CreateBountySubmissionService(self.db).execute(
            bounty_id=bounty_id,
            submitter_agent_id=submitter_agent_id,
            title=title,
            description=description,
            proposed_course_version_id=proposed_course_version_id,
            evidence=evidence,
        )  # commits internally; the submission EXISTS from here on

        if github_pr is False:
            return CreateSubmissionWithPrResult(
                submission, {"status": "skipped", "reason": "client_opt_out"}
            )
        bounty = BountyRepository(self.db).get(bounty_id)
        enabled, disabled_reason = bounty_github_pr_availability(
            self.db, bounty
        )  # ('creator_disabled'|'no_source_link'|'app_not_installed')
        if not enabled:
            return CreateSubmissionWithPrResult(
                submission, {"status": "disabled", "reason": disabled_reason}
            )
        try:
            result = OpenSubmissionPrService(
                self.db, github_client_factory=self._client_factory
            ).execute(
                bounty_id=bounty_id,
                submission_id=submission.id,
                agent_id=submitter_agent_id,
            )
        except BountyPrError as exc:
            return CreateSubmissionWithPrResult(
                submission, {"status": "failed", "reason": exc.code}
            )
        except GithubApiError:
            logger.exception("bounty.submission_pr.github_error")
            return CreateSubmissionWithPrResult(
                submission, {"status": "failed", "reason": "github_error"}
            )
        if result.fork_required:
            return CreateSubmissionWithPrResult(
                submission,
                {"status": "fork_required",
                 "head_branch": result.head_branch,
                 "pr_body": result.pr_body},
            )
        return CreateSubmissionWithPrResult(
            submission,
            {"status": "opened", "pr_url": result.pr_url,
             "head_branch": result.head_branch},
        )
```

The controller `create_bounty_submission` switches to this service and
serializes the block; its existing exception mapping is untouched (all
submission-side errors still 404/403/422 exactly as today — only PR-side
errors are swallowed into the block).

### 2.3 `OpenSubmissionPrService` — one additive change

`OpenSubmissionPrResult` gains `pr_body: str | None = None`, populated in
the `fork_required` branch with the exact body the contributor must paste
(the marker + bounty/submission links + the 15.5 "merge != payout" line —
build it with the same private helper the non-fork branch uses; grep-pin:
the body template exists once). Nothing else changes; `open-pr` keeps
working as the repair command.

## 3. Webhook auto-register (`backend repository` PR)

### 3.1 Dispatch — `api/webhooks/services/process_github_webhook.py`

`_handle_pull_request_event` currently returns unless `action == "closed"`.
Restructure:

```python
    def _handle_pull_request_event(self, event: dict) -> None:
        action = event.get("action")
        pull = event.get("pull_request") or {}
        repository = (event.get("repository") or {}).get("full_name", "")
        if action in ("opened", "edited", "reopened"):
            RegisterPrFromWebhookService(db=self.db).execute(
                repository=repository,
                pr_number=pull.get("number"),
                pr_body=pull.get("body") or "",
                author_github_user_id=(pull.get("user") or {}).get("id"),
                author_type=(pull.get("user") or {}).get("type"),
                head_branch=(pull.get("head") or {}).get("ref"),
                head_sha=(pull.get("head") or {}).get("sha"),
            )
        elif action == "closed":
            ...  # existing HandleBountyPrMergedService call, byte-identical
```

`edited` is included on purpose: a contributor who forgot the marker adds
it by editing the PR body — the next delivery registers it. No new webhook
events are needed (`pull_request` is already subscribed).

### 3.2 `RegisterPrFromWebhookService` — `api/bounties/services/register_pr_from_webhook.py`

Marker constant (add beside the existing templates in
`api/bounties/constants/github_pr.py`):

```python
BOUNTY_PR_MARKER_RE = (
    r"<!--\s*logion:bounty_submission:"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s*-->"
)
```

`execute(...)` — exact guard order, every rejection emits
`CreateEventService(event_type="pr_register_rejected",
target_type="bounty_submission", target_id=submission.id,
payload={"reason": ..., "repository": ..., "pr_number": ...})` + commit,
except the first two (no submission to attribute to — log only):

1. no marker match in `pr_body` → return silently (almost every PR on
   earth; not even a log at info level — use debug);
2. `author_type == "Bot"` → return silently (our own bot-opened PRs from
   §2 carry the marker; without this guard every happy-path PR would
   double-process. The bot-opened path already created its row, so guard
   3 would also catch it — this guard just skips the work);
3. submission (by marker uuid) does not exist, or an existing
   `bounty_submission_prs` row already covers this submission:
   - same `(repository, pr_number)` → idempotent no-op (redeliveries,
     edits after registration);
   - different PR → reason `submission_already_has_pr`;
   - no submission → log `github.pr_register.unknown_submission`, return;
4. `submission.status != "submitted"` → reason `submission_not_open`;
5. bounty's course has no active source link, or
   `source_link.repository.lower() != repository.lower()` → reason
   `repository_mismatch` (a marker on a PR in the WRONG repo must never
   bind — the merge policy operates per-repo);
6. `bounty.accepts_github_prs is False` → reason `creator_disabled`;
7. **the author pin**: resolve the submitter →
   `AgentRepository.get_user_id(submission.submitter_agent_id)` →
   `GithubIdentityRepository.get_by_user_id(user_id)`; identity missing or
   `status != 'active'` → reason `submitter_identity_missing`;
   `identity.github_user_id != author_github_user_id` → reason
   `author_not_submitter`. Compare the **numeric id**, never the login
   (logins are mutable and reassignable).
8. All pass → `BountySubmissionPrRepository.create(
   bounty_submission_id=submission.id, repository=repository,
   pr_number=pr_number, head_branch=head_branch, head_sha=head_sha)`,
   emit `bounty_pr_registered`
   (`actor_agent_id=submission.submitter_agent_id`), commit;
9. best-effort courtesy comment on the PR via the client factory
   ("Registered as Logion submission `{id}`. Merging triggers Logion's
   bounty acceptance policy; merge alone is neither publication nor
   payout." — constant in `github_pr.py`). `GithubApiError` here is
   logged and swallowed — a failed comment never fails the delivery.

### 3.3 Endpoint removal

Delete `POST .../pr/register`: controller
`register_submission_pr.py`, service `register_submission_pr.py`, their
tests, and the SDK method (regenerate: `make export-openapi` →
`make sync-public-contract`). `open_submission_pr` endpoint stays
(repair). Update `maintainer documentation: api.md`'s bounty-PR section: the register
flow is now "open the PR with the marker; the webhook registers it".

## 4. CLI (`logion` PR, base branch `0.2.0`)

In `cli/commands/bounties.py`:

1. `submissions create` gains a mutually exclusive pair:
   `--github-pr` (`dest="github_pr", action="store_const", const=True`) /
   `--no-github-pr` (`const=False`), default `None` (auto). Forward via the
   existing `only_not_none` kwargs. Rendering (human mode) appends after
   the submission block, one branch per `github_pr.status`:
   - `opened` → `PR opened: {pr_url}`;
   - `fork_required` → the fork instructions (reuse/adapt
     `FORK_NEXT_STEPS`, now ending with "open the PR — Logion registers
     it automatically" instead of a `register-pr` command) **plus** the
     paste-ready `pr_body`;
   - `disabled`/`skipped`/`failed` → one honest line with the reason.
   `--json`: the block passes through verbatim in the envelope data.
2. **Delete** the `register-pr` sub-parser, `handle_submissions_register_pr`,
   and its tests. `open-pr` stays; change its help string to
   `"Retry GitHub PR materialization for a submission (repair)"` and its
   fork-path rendering to the same no-register instructions.
3. `create` (bounty) gains `--no-github-prs`
   (`dest="accepts_github_prs", action="store_false", default=True`).
4. `get`/`list` render `github_pr_enabled` (one line:
   `GitHub PRs: enabled|disabled`).
5. Docs: `cli-structure.md` — remove `register-pr`, note the auto flow;
   companion marketplace-loop doc: the contributor flow is now
   "submit → (fork+open PR if asked) → done".

## 5. Tests

### 5.1 Backend — `tests/test_create_submission_with_pr.py`

Seed idiom + `FakeGithubAppClient` from `tests/test_open_submission_pr.py`.

- `test_auto_opens_pr_when_enabled` — default (`github_pr=None`), all
  three conditions hold → submission created AND block
  `status=='opened'` with URL; exactly one PR row.
- `test_submission_survives_pr_failure` — fake client raises on
  `create_pull` → submission exists + `status=='failed'`,
  `reason=='github_error'`; re-running `open-pr` (repair) succeeds. **The
  never-fail pin.**
- `test_opt_out_skips` — `github_pr=False` → `skipped/client_opt_out`,
  zero GitHub calls.
- `test_disabled_reasons_matrix` — creator flag off / no source link / no
  installation → `disabled` with the matching reason, zero GitHub calls
  (three sub-tests).
- `test_fork_required_returns_paste_ready_body` — permission "read" →
  `fork_required`, `pr_body` contains the exact marker for the new
  submission id.
- `test_explicit_true_when_unavailable_still_submits` — `github_pr=True`
  with no link → submission created, `disabled/no_source_link` (the flag
  raises no error).

### 5.2 Backend — `tests/test_register_pr_from_webhook.py`

Drive `ProcessGithubWebhookService.execute` with signed
`pull_request` payloads (extend the existing builders with
`action="opened"`, `body=`, `user=`).

- `test_marker_pr_by_submitter_auto_registers` — fork-path submission,
  submitter's identity `github_user_id=111`, PR authored by id 111 with
  the marker → PR row created, `bounty_pr_registered` event, courtesy
  comment recorded on the fake client.
- `test_author_pin_rejects_impostor` — same marker, PR authored by id
  999 → NO row, `pr_register_rejected` with
  `reason=='author_not_submitter'`. Then the impostor's PR gets merged by
  the owner → **nothing happens** (no row ⇒ merged handler ignores it):
  the end-to-end attack test.
- `test_submitter_identity_missing_rejected` — no `github_identities`
  row → `submitter_identity_missing`, no PR row.
- `test_wrong_repository_rejected` — marker PR on a different repo →
  `repository_mismatch`.
- `test_creator_disabled_rejected` — `accepts_github_prs=False` →
  `creator_disabled`; and via PATCH mid-flight: flag flipped off AFTER a
  PR row exists → merged handler still processes that PR (the §1.2 pin).
- `test_edited_body_registers_late_marker` — `opened` without marker
  (silent), then `edited` with marker → registered once.
- `test_duplicate_and_redelivery_idempotent` — same PR delivered
  `opened` then `edited` then redelivered → exactly one row, one event.
- `test_second_pr_for_same_submission_rejected` —
  `submission_already_has_pr`.
- `test_no_marker_silent` / `test_bot_author_silent` — zero rows, zero
  events, delivery marked processed.
- `test_comment_failure_does_not_fail_delivery`.
- `test_closed_action_still_routes_to_merge_handler` — the existing merge
  tests keep passing byte-identical (regression gate).

### 5.3 Backend — flag surface

`tests/test_bounty_accepts_github_prs.py` — create default true; create
with false; PATCH creator-only (403 for others); `github_pr_enabled`
computed matrix (2×2×2 over flag/link/installation — helper tested once,
serializer asserted to call it).

### 5.4 CLI — `tests/test_cli_bounties_pr.py` (rework)

- `test_create_submission_renders_opened_pr` /
  `..._renders_fork_instructions_with_body` /
  `..._renders_disabled_reason` (fake SDK returns each block).
- `test_no_github_pr_flag_forwarded` — `--no-github-pr` →
  `github_pr=False` in kwargs; `--github-pr` → `True`; neither → absent.
- `test_register_pr_command_gone` — `["bounties","submissions",
  "register-pr", ...]` exits 2 with argparse error.
- `test_open_pr_help_says_repair` + existing open-pr tests updated for
  the new fork rendering.
- `test_bounty_create_no_github_prs_flag` +
  `test_bounty_get_renders_github_pr_enabled`.

## 6. Acceptance criteria

- [ ] Collaborator happy path is ONE command: `submissions create` on a
      PR-enabled bounty returns a draft PR URL; the fork path is one
      command + one GitHub action (open PR with the provided body), with
      zero further CLI steps — the webhook registers it.
- [ ] A submission never fails or rolls back because PR materialization
      failed; every non-opened outcome is reported with a stable reason.
- [ ] The author pin holds end-to-end: a marker PR authored by anyone but
      the submitter's linked GitHub id is never registered, and merging
      it moves no money (attack test).
- [ ] The creator flag gates new materialization/registration (default
      on), is PATCH-able by the creator only, is advertised as computed
      `github_pr_enabled`, and never disables bounties themselves.
- [ ] `register-pr` is gone from CLI, API, SDK, and docs; `open-pr`
      remains as documented repair; all 15.5 merge-policy tests pass
      unmodified.
- [ ] Deploying `backend repository` before the App exists changes no
      observable behavior (rollout-safety section).

## Out of scope

- Bot-side forking or pushing code on the contributor's behalf (GitHub
  Apps cannot fork to user accounts; the 15.1 token is identity-scoped —
  deliberate).
- A client-side persisted "always/never GitHub PRs" preference (the
  default derives from the bounty's advertised state; no hidden client
  state).
- Auto-closing registered PRs when a submission is withdrawn (webhook →
  GitHub write-backs beyond the courtesy comment).
- Any change to merge policy, acceptance, payout, or 15.5.1's issue
  surface.

## Implementation order for a less capable agent

1. Migration + model + snapshot; `bounty_github_pr_availability` helper +
   its matrix test (§5.3).
2. Bounty create/PATCH/read-surface changes + remaining §5.3 tests.
3. `OpenSubmissionPrResult.pr_body` (additive) + adjust its existing
   tests.
4. `CreateSubmissionWithPrService` + controller switch + §5.1 tests.
5. `BOUNTY_PR_MARKER_RE` + `RegisterPrFromWebhookService` + dispatch
   restructure + §5.2 tests (the attack test before anything else).
6. Delete register endpoint/service/tests; `make export-openapi` →
   `make sync-public-contract`; `maintainer documentation: api.md` update.
7. CLI PR: flags, rendering, deletions, §5.4 tests, docs.
8. Full bounty + webhook suites green; 15.5 merge tests unmodified.

## Cross-cutting improvement contract

This phase is governed by [`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md). A community improvement proposal is **unfunded by default** and may accept a free GitHub PR/submission, retain contributor attribution and evidence, and merge upstream or become a maintained derivative with lineage. Funding is an explicit prospective conversion: only a confirmed funded bounty creates escrow, payout, or `sh.logion.bounty.accepted.v1`; an unpaid acceptance uses `sh.logion.improvement.accepted.v1` and must write no ledger/payable row. Publication review remains independent in both lanes.
