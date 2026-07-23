<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.5.1: Issue-Mention Bounty Bot (`@logion-bot` opens bounties from issues)

> Extends [`phase-15.5`](phase-15.5-bounty-pr-bot-and-merge-policy.md) (shipped:
> webhook plumbing, `GithubAppClient`, installations, merge policy). The
> `logion-bot` GitHub App gains an **issue surface**: mentioning the bot in an
> issue of a linked repo starts a conversation that ends with a funded Logion
> bounty — through the three existing, unchanged services
> (`CreateBountyService` → `OpenBountyService` → `FundBountyService`).
> **No new money code.** **PRs: exactly one per repo** — one `logion`
> (public) PR and one `backend repository` PR. There is no CLI surface (the
> UI is the GitHub issue thread itself); the public PR exists because the
> bot's **behavior layer is public on purpose**: the command grammar,
> parser, and reply copy live in a new public package
> `logion/packages/bot` so anyone can open issues/PRs to improve the bot
> itself. The private PR holds everything that touches policy, money, or
> the DB. Split rule, pinned:
>
> ```text
> public  (logion/packages/bot): what the bot SAYS and PARSES —
>         grammar constants, parse_issue_bot_command, reply templates.
>         Pure, no I/O, zero backend repository references (public-audit).
> private (backend repository):      what the bot DOES — webhook wiring,
>         policy, thread state, bounty/credits services, client calls.
> ```
>
> The private repo consumes the public package via the same vendored
> parity discipline as the 15.3 package-map parser and the 16.11
> `scorecard_digest` (identical fixtures, identical output, golden tests
> in both repos — do not invent a new sharing mechanism).
>
> Non-negotiable product rule, test-pinned:
>
> ```text
> The bot NEVER opens or funds a bounty unless BOTH are true:
>   1. the amount is explicit (a human typed an integer credit amount), and
>   2. the confirmation is explicit (the same human typed `confirm` in a
>      LATER comment, after the bot's confirmation prompt).
> One comment can never do both. Silence, emoji, edits, and reactions are
> never consent.
> ```

## Prerequisites (all already merged — verify, do not rebuild)

| Piece | Where it lives today |
| --- | --- |
| Webhook controller + HMAC + delivery idempotency | `api/webhooks/controllers/github_webhook.py`, `api/webhooks/services/process_github_webhook.py`, `github_webhook_events` table |
| Bot REST client | `api/identity/services/github_app_client.py` (`GithubAppClient`) |
| Installation grants | `github_app_installations` + `GithubAppInstallationRepository.get_active_for_repository` |
| Per-repo client factory | `api/bounties/services/_github_client_factory.py` (`make_github_client_factory`) |
| GitHub identity → user | `GithubIdentity` model (`github_user_id: BigInteger unique`, `github_login`), `GithubIdentityRepository.get_by_github_user_id` |
| Repo → course | `course_source_links` (`repository` indexed, `course_id` unique, `status`) |
| Bounty lifecycle | `CreateBountyService` (draft, owner-only, published-course-only, `USD_CREDIT`), `OpenBountyService` (draft→open, creator-only), `FundBountyService` (open→funded, debits creator credits, idempotent) |
| Events | `CreateEventService.execute(event_type=..., actor_agent_id=..., target_type=..., target_id=..., payload=...)` — flushes, does NOT commit |
| Config | `Settings.github_app_id / github_app_private_key_pem / github_app_webhook_secret / github_app_bot_login` in `api/config.py` |

Denomination: bounty amounts are stored as `reward_amount_cents` in
`USD_CREDIT`, and credits are granted 1:1 with cents
(`api/credits/constants/top_ups.py`: `credit_cents_granted = amount_cents`).
Therefore **`@logion-bot bounty 250` means 250 credits ⇒
`reward_amount_cents = 250`. No conversion factor exists; do not invent
one.** Bot comments always say "credits", never "$" or "USD"
(credits-denomination principle — USD exists only at Stripe/payout
boundaries).

## GitHub App delta (operator step — see phase 15.5.3)

The App needs, **in addition** to the 15.5 floor:

- Repository permission **Issues: Read and write** (to read issue bodies and
  post comments).
- Webhook events **`issues`** and **`issue_comment`**.

This amends the 15.5 rule "contents+PRs+metadata, no other permission,
ever". The new recorded floor is **contents + pull requests + issues +
metadata — no other permission, ever.** Update the sentence in
`maintainer documentation: production-infrastructure.md` (§"GitHub App / Bounty PR webhook
runtime config") in this PR. The code below must degrade gracefully while
the App lacks the new events (it simply never receives them — nothing
crashes).

## 1. Command grammar (pinned as constants + pure parser — `logion` PR, public)

New public package `logion/packages/bot` (import name `logion_bot`),
following the existing public-package layout (own `pyproject.toml`, tests
beside it, wired into the workspace + CI like `packages/indexer`). Three
modules ship in this phase: `logion_bot/commands.py` (constants),
`logion_bot/parser.py`, `logion_bot/replies.py`. The package README states
the contribution surface plainly: *"this package defines what logion-bot
says and understands; the policy that decides what it may DO (ownership,
credits, funding) is server-side and not configurable from here"* — so
public contributions can never weaken the money rules by construction.
`backend repository` vendors these modules with parity golden fixtures
(15.3/16.11 discipline).

### 1.1 Constants — `logion_bot/commands.py` (new file)

```python
"""Command grammar and pinned comment copy for the issue-mention bot.

All user-facing amounts are credits. Never render USD here.
"""

# Matches "@{bot_login}" as a standalone token, case-insensitive.
# bot_login comes from settings.github_app_bot_login (the App slug,
# WITHOUT the "[bot]" suffix GitHub appends to the acting identity).
ISSUE_BOUNTY_COMMANDS = ("bounty", "confirm", "cancel", "help")

# Amount token: integer credits, 1..9_999_999. No decimals, no symbols.
ISSUE_BOUNTY_AMOUNT_RE = r"^[0-9]{1,7}$"

# Optional course disambiguator token: "course:<slug>"
ISSUE_BOUNTY_COURSE_TOKEN_PREFIX = "course:"

ISSUE_BOUNTY_THREAD_STATES = (
    "awaiting_amount",
    "awaiting_confirmation",
    "opened",
    "cancelled",
    "expired",
)
```

### 1.2 Parser — `logion_bot/parser.py` (new, pure)

Pure function, zero I/O, exhaustively unit-tested:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class IssueBotCommand:
    kind: str  # 'bounty' | 'confirm' | 'cancel' | 'help' | 'unknown'
    amount_cents: int | None = None   # credits == cents, 1:1
    course_slug: str | None = None


def parse_issue_bot_command(
    body: str, *, bot_login: str
) -> IssueBotCommand | None:
    """Parse one comment/issue body into at most one bot command.

    Rules (each is a named test):
    - returns None when "@{bot_login}" does not appear as a standalone
      token (substring hits like "@logion-bot-fan" do NOT match);
    - matching is case-insensitive on both the mention and the verb;
    - tokens are read LEFT TO RIGHT after the mention: the first
      recognized verb wins; text before the mention is ignored;
    - "@bot bounty"            -> IssueBotCommand("bounty")
    - "@bot bounty 250"        -> IssueBotCommand("bounty", amount_cents=250)
    - "@bot bounty 250 credits"-> same (a literal "credits" token after the
                                  amount is allowed and ignored)
    - "@bot bounty 250 course:my-slug" -> amount + course_slug
    - "@bot bounty $250" / "250.50" / "250 USD" -> IssueBotCommand("bounty")
      with amount_cents=None (malformed amount == no amount; the bot will
      ask, and the ask-copy explains the accepted format);
    - "@bot confirm" -> IssueBotCommand("confirm")
    - "@bot cancel"  -> IssueBotCommand("cancel")
    - "@bot help" or a mention with no recognized verb ->
      IssueBotCommand("help")  (help is the safe default — it can never
      move money);
    - CRITICAL PIN: "confirm" appearing anywhere in the SAME comment as
      "bounty" is ignored — the parser returns only the "bounty" command.
      ("@bot bounty 250 confirm" proposes; it never confirms.)
    - mentions inside fenced code blocks (``` ... ```) are ignored.
    """
```

Implementation guidance: strip fenced code blocks first (regex over
``` blocks), split on whitespace, find the mention token, then scan
following tokens. Keep it < 80 lines; no markdown library.

## 2. Migration `0038_bounty_issue_threads.py` (`backend repository` PR)

(Renumber to the next free revision; chain `down_revision` onto the current
head — check `alembic heads` first; as of writing the head follows
`0037_bounty_pr_bot_and_github_app` / the funder-ledger revision.)

```python
op.create_table(
    "bounty_issue_threads",
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("repository", sa.String(255), nullable=False),
    sa.Column("issue_number", sa.Integer(), nullable=False),
    sa.Column("state", sa.String(24), nullable=False,
              server_default=sa.text("'awaiting_amount'")),
    # awaiting_amount | awaiting_confirmation | opened | cancelled | expired
    sa.Column("requested_by_github_user_id", sa.BigInteger(), nullable=False),
    sa.Column("requested_by_login", sa.String(255), nullable=False),
    sa.Column("proposed_amount_cents", sa.Integer(), nullable=True),
    sa.Column("course_id", sa.Uuid(), sa.ForeignKey("courses.id"),
              nullable=True, index=True),
    sa.Column("bounty_id", sa.Uuid(), sa.ForeignKey("bounties.id"),
              nullable=True),
    sa.Column("issue_title", sa.String(512), nullable=False),
    sa.Column("issue_url", sa.String(1024), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    # standard created_at/updated_at like every other table
    sa.CheckConstraint(
        "state in ('awaiting_amount','awaiting_confirmation','opened',"
        "'cancelled','expired')",
        name="ck_bounty_issue_threads_state"),
    sa.CheckConstraint(
        "(state != 'opened') OR (bounty_id IS NOT NULL)",
        name="ck_bounty_issue_threads_opened_has_bounty"),
    sa.CheckConstraint(
        "(state != 'awaiting_confirmation') OR "
        "(proposed_amount_cents IS NOT NULL)",
        name="ck_bounty_issue_threads_confirmation_has_amount"),
    sa.UniqueConstraint("repository", "issue_number",
                        name="uq_bounty_issue_threads_repo_issue"),
)
```

**One thread row per (repository, issue) — forever.** A `cancelled` or
`expired` row is *reused* (reset to `awaiting_amount`/`awaiting_confirmation`
with fresh requester/amount/expiry) when a new `bounty` command arrives; an
`opened` row is terminal — further mentions get the "already opened" reply.
This keeps the unique constraint trivial and makes replays harmless.

Model in `api/models.py` (`BountyIssueThread`, `IdMixin` + `TimestampMixin`,
same idioms as `BountySubmissionPr`). Extend the
`tests/test_database_schema.py` snapshot.

Repository `api/bounties/repositories/bounty_issue_threads.py`:

```python
class BountyIssueThreadRepository:
    def __init__(self, db: Session) -> None: ...
    def get_by_repo_and_issue(self, repository: str,
                              issue_number: int) -> BountyIssueThread | None: ...
    def create(self, *, repository, issue_number, state,
               requested_by_github_user_id, requested_by_login,
               proposed_amount_cents, course_id, issue_title, issue_url,
               expires_at) -> BountyIssueThread:  # flush, no commit
```

Also add to `api/courses/repositories/course_source_links.py`:

```python
    def list_active_by_repository(
        self, repository: str
    ) -> list[CourseSourceLink]:
        """All active links whose repository matches exactly (owner/repo).

        repository is stored verbatim; compare case-insensitively
        (func.lower) because GitHub repo slugs are case-insensitive.
        """
```

## 3. Config — `api/config.py`

One new field, same `Field` idiom, right after `github_app_bot_login`:

```python
    issue_bounty_thread_ttl_hours: int = Field(
        default=72, validation_alias="LOGION_ISSUE_BOUNTY_THREAD_TTL_HOURS"
    )
```

No enable/disable flag: the feature is dark exactly like the rest of 15.5 —
empty `LOGION_GITHUB_APP_*` config means the webhook answers 503 and no
issue event ever arrives.

## 4. `GithubAppClient` extensions — `api/identity/services/github_app_client.py`

Two methods, same `_request` plumbing, timeout, and error mapping as the
existing six:

```python
    def create_issue_comment(
        self, *, repository: str, issue_number: int, body: str
    ) -> dict:
        # POST /repos/{repository}/issues/{issue_number}/comments
        # {"body": body} -> returns the created comment json

    def get_issue(self, *, repository: str, issue_number: int) -> dict:
        # GET /repos/{repository}/issues/{issue_number}
```

## 5. Webhook dispatch — `api/webhooks/services/process_github_webhook.py`

Extend `_dispatch_event` with two branches (keep the existing
`pull_request`/`installation` branches byte-identical):

```python
        elif event_type == "issue_comment":
            self._handle_issue_comment_event(event)
        elif event_type == "issues":
            self._handle_issues_event(event)
```

```python
    def _handle_issue_comment_event(self, event: dict) -> None:
        if event.get("action") != "created":
            return  # PIN: edited/deleted comments never trigger commands
        issue = event.get("issue") or {}
        if issue.get("pull_request") is not None:
            return  # PIN: PR conversations are not issues; ignore
        comment = event.get("comment") or {}
        author = comment.get("user") or {}
        if author.get("type") == "Bot":
            return  # PIN: never react to bots (incl. ourselves) — no loops
        HandleIssueMentionService(db=self.db).execute(
            repository=(event.get("repository") or {}).get("full_name", ""),
            issue_number=issue.get("number"),
            issue_title=issue.get("title") or "",
            issue_url=issue.get("html_url") or "",
            author_github_user_id=author.get("id"),
            author_login=author.get("login") or "",
            body=comment.get("body") or "",
        )

    def _handle_issues_event(self, event: dict) -> None:
        if event.get("action") != "opened":
            return  # PIN: issue EDITS never trigger commands
        issue = event.get("issue") or {}
        if issue.get("pull_request") is not None:
            return
        author = issue.get("user") or {}
        if author.get("type") == "Bot":
            return
        HandleIssueMentionService(db=self.db).execute(
            repository=(event.get("repository") or {}).get("full_name", ""),
            issue_number=issue.get("number"),
            issue_title=issue.get("title") or "",
            issue_url=issue.get("html_url") or "",
            author_github_user_id=author.get("id"),
            author_login=author.get("login") or "",
            body=issue.get("body") or "",
        )
```

Delivery idempotency is already handled by `github_webhook_events` — do not
add a second mechanism.

## 6. `HandleIssueMentionService` — `api/bounties/services/handle_issue_mention.py`

Constructor: `(self, db: Session, *, github_client_factory=None)` — default
`make_github_client_factory(db=db)`, tests inject a fake (same seam as
`OpenSubmissionPrService`).

`execute(*, repository, issue_number, issue_title, issue_url,
author_github_user_id, author_login, body) -> None`. Exact order:

1. `command = parse_issue_bot_command(body,
   bot_login=get_settings().github_app_bot_login)`. `None` → return
   silently (most comments mention nobody).
2. Lazy-expire: load the thread row; if it exists in
   `awaiting_amount|awaiting_confirmation` and `expires_at < now` → set
   `state='expired'` first (mirror the `expire_bounty_lazy` idiom).
3. Dispatch on `command.kind`:

### 6.1 `bounty`

1. **Policy gate** — `IssueBountyPolicyService.execute(...)` (§7) returns
   `(course, owner_agent_id)` or a stable reason string. On reason:
   post the matching pinned reply (§9), emit event
   `issue_bounty_refused` with `payload={"reason": ..., "repository": ...,
   "issue_number": ...}`, commit, return. **A refused command never
   creates/keeps a thread in a confirmable state.**
4. Thread row: create if absent; if present and `opened` → post
   `REPLY_ALREADY_OPENED` (with the bounty URL) and return; if present in
   any other state → reset it (new requester, new amount, new expiry).
5. If `command.amount_cents is None` → `state='awaiting_amount'`, post
   `REPLY_ASK_AMOUNT`. If present → `state='awaiting_confirmation'`,
   `proposed_amount_cents=command.amount_cents`, post
   `REPLY_CONFIRM_PROMPT` (quotes amount in credits, course title, and the
   exact confirm command). Either way:
   `expires_at = now + ttl`, `course_id = course.id`,
   `requested_by_github_user_id/login = author`, emit
   `issue_bounty_thread_updated`, commit.

### 6.2 `confirm`

Guards, each with its own pinned reply and named test:

- no thread row, or state not `awaiting_confirmation` →
  `REPLY_NOTHING_TO_CONFIRM`;
- `author_github_user_id != thread.requested_by_github_user_id` →
  `REPLY_CONFIRM_WRONG_USER` (the person who proposed must confirm);
- re-run the §7 policy gate (ownership/link may have changed since the
  proposal) — on reason: refuse exactly like 6.1.

On pass, call `OpenBountyFromIssueService.execute(thread=thread,
actor_agent_id=owner_agent_id)` (§8) and post the success/failure reply it
returns.

### 6.3 `cancel`

Thread in `awaiting_amount|awaiting_confirmation` **and** author matches
`requested_by_github_user_id` → `state='cancelled'`,
`REPLY_CANCELLED`, event `issue_bounty_thread_cancelled`, commit.
Otherwise `REPLY_NOTHING_TO_CANCEL`.

### 6.4 `help` / `unknown`

Post `REPLY_HELP`. No state change. (Safe default: help can never move
money.)

Every posted comment goes through one private helper
`_post(client, repository, issue_number, body)` that catches
`GithubApiError`, logs `github.issue_bounty.comment_failed`, and never
raises — a failed comment must not 5xx the webhook (GitHub would retry and
replay the command; the delivery-id table protects state, but don't rely on
it for comment side effects).

## 7. `IssueBountyPolicyService` — `api/bounties/services/issue_bounty_policy.py`

Same shape as `MergeAcceptancePolicyService`: returns a result or a stable
reason string; **who may open == who may pay == the course owner.**

```python
@dataclass(frozen=True)
class IssueBountyPolicyResult:
    course: Course
    owner_agent_id: uuid.UUID


class IssueBountyPolicyService:
    """Decides whether a GitHub user may open a bounty on this repo's course.

    Returns IssueBountyPolicyResult or a stable reason string:
      repo_not_linked | course_ambiguous | course_not_published |
      author_not_linked | author_not_course_owner
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.source_link_repo = CourseSourceLinkRepository(db)
        self.course_repo = CourseRepository(db)
        self.identity_repo = GithubIdentityRepository(db)
        self._agent_repo = AgentRepository(db)

    def execute(self, *, repository: str, author_github_user_id: int,
                course_slug: str | None):
        links = self.source_link_repo.list_active_by_repository(repository)
        if not links:
            return "repo_not_linked"
        if course_slug is not None:
            links = [l for l in links
                     if self.course_repo.get(l.course_id).slug == course_slug]
        if len(links) != 1:
            return "course_ambiguous"   # reply lists the slugs (§9)
        course = self.course_repo.get(links[0].course_id)
        if course.status != CourseStatus.PUBLISHED:
            return "course_not_published"
        identity = self.identity_repo.get_by_github_user_id(
            author_github_user_id
        )
        if identity is None or identity.status != "active":
            return "author_not_linked"
        owner_user_id = self._agent_repo.get_user_id(course.owner_agent_id)
        if owner_user_id != identity.user_id:
            return "author_not_course_owner"
        return IssueBountyPolicyResult(
            course=course, owner_agent_id=course.owner_agent_id
        )
```

Rationale (record in the module docstring): `CreateBountyService` already
enforces owner-only + published-only, and `FundBountyService` debits the
*creator's* credits — so the mention author must resolve (via
`github_identities.github_user_id`, never via login string) to the course
owner's user. Resolution by `github_user_id` is deliberate: logins are
mutable and reassignable; the numeric id is not. **Non-owners get a polite
refusal — v0 does not let third parties fund bounties from an issue**
(that is the 15.8 platform-funded lane and a future "anyone-funds" lane,
out of scope here).

## 8. `OpenBountyFromIssueService` — `api/bounties/services/open_bounty_from_issue.py`

`execute(*, thread: BountyIssueThread, actor_agent_id: uuid.UUID) -> str`
(returns the reply body to post). Exact order:

1. Compose:
   - `title = f"[issue #{thread.issue_number}] {thread.issue_title}"[:255]`
   - `description = (f"Opened from {thread.issue_url} by "
     f"@{thread.requested_by_login} via logion-bot.\n\n"
     f"<!-- logion:issue_bounty_thread:{thread.id} -->")`
2. `bounty = CreateBountyService(self.db).execute(
   creator_agent_id=actor_agent_id, course_id=thread.course_id,
   title=title, description=description,
   reward_amount_cents=thread.proposed_amount_cents)` — draft.
3. `OpenBountyService(self.db).execute(bounty.id, actor_agent_id)` — open.
4. `FundBountyService(self.db).execute(bounty.id, actor_agent_id)` — funded.
   - `InsufficientCreditBalanceError` → the bounty **stays open and
     unfunded** (that is a legal, fundable-later state); set
     `thread.state='opened'`, `thread.bounty_id=bounty.id`, emit
     `issue_bounty_opened_unfunded`, commit, and return
     `REPLY_OPENED_UNFUNDED` (says: bounty exists, funding failed for
     insufficient credits, top up at https://logion.sh and run
     `logion bounties fund <id> --yes`). Honest partial success, never
     silent.
5. Success: `thread.state='opened'`, `thread.bounty_id=bounty.id`, emit
   `issue_bounty_opened` (`actor_agent_id=actor_agent_id`,
   `target_type="bounty"`, `target_id=bounty.id`,
   `payload={"repository": ..., "issue_number": ...,
   "amount_cents": ..., "thread_id": str(thread.id)}`), commit, return
   `REPLY_OPENED` with `https://logion.sh/bounties/{bounty.id}` and the
   amount in credits.
6. Any `BountiesDomainError` from steps 2–3 → thread goes back to
   `awaiting_confirmation` is WRONG — instead set `state='cancelled'`,
   emit `issue_bounty_open_failed` with the error string, and return
   `REPLY_OPEN_FAILED`. (A failed open must not leave a confirmable thread
   pointing at half-created state; the user re-runs the command.)

All three inner services commit internally (existing behavior) — do not
wrap them in an outer transaction; the thread-state commit happens after,
and step 6's failure handling covers the gap. Note in a comment that a
crash between step 3 and 5 leaves an open unfunded bounty and a
non-`opened` thread; the next `confirm` re-runs the policy and creates a
second draft — acceptable v0 wart, recorded, NOT silently deduped.

## 9. Pinned replies — `logion_bot/replies.py` (public)

Every bot comment is a module constant (templates with named fields), so
copy is test-pinned and greppable. Required set (final copy at
implementation, but each MUST include the elements listed):

| Constant | Must contain |
| --- | --- |
| `REPLY_ASK_AMOUNT` | ask for amount in **credits**; the exact command format `@{bot} bounty <amount>`; accepted format = whole number of credits; TTL note |
| `REPLY_CONFIRM_PROMPT` | amount in credits, course title, "this will debit {amount} credits from your Logion balance", the exact confirm command `@{bot} confirm`, the cancel command, TTL note |
| `REPLY_OPENED` | bounty URL, amount in credits, "funded" |
| `REPLY_OPENED_UNFUNDED` | bounty URL, "open but unfunded — insufficient credits", top-up pointer + `logion bounties fund` command |
| `REPLY_OPEN_FAILED` | the stable error code, "nothing was funded" |
| `REPLY_ALREADY_OPENED` | existing bounty URL |
| `REPLY_NOTHING_TO_CONFIRM` | how to start (`@{bot} bounty <amount>`) |
| `REPLY_CONFIRM_WRONG_USER` | "only @{login} (who proposed) can confirm" |
| `REPLY_CANCELLED` / `REPLY_NOTHING_TO_CANCEL` | — |
| `REPLY_HELP` | the four commands, one line each |
| `REPLY_REFUSED_REPO_NOT_LINKED` | pointer to linking docs (15.3 `logion courses link`) |
| `REPLY_REFUSED_COURSE_AMBIGUOUS` | the active course slugs + `course:<slug>` syntax |
| `REPLY_REFUSED_COURSE_NOT_PUBLISHED` | — |
| `REPLY_REFUSED_AUTHOR_NOT_LINKED` | pointer to `logion auth` GitHub linking |
| `REPLY_REFUSED_NOT_OWNER` | "only the course owner can open a creator-funded bounty" |

Rule pinned by test: **no reply constant contains `$` or the string
"USD"** (grep-pin over the module).

## 10. Cross-node scope note (recorded decision — no subphase)

A bounty opened by this bot is an ordinary creator-funded bounty. That
means it composes with the network phases **with zero code in this phase**:

- when [15.17](phase-15.17-aktp-evidence-and-improvement-feed-v0.md)
  lands, bot-opened bounties appear in `/v1/node/bounties.json`
  automatically (they are "open, publicly visible bounties on the Logion
  node"), with canonical target `gh:{owner}/{repo}[#subpath]` — the same
  repo the issue lives in. Discovery across nodes is 15.14's job, not the
  bot's.
- a bot that opens bounties **on foreign nodes** is rejected, not
  deferred: 15.14's hard boundary is `money and the final acceptance
  decision are local to the node that opened it`, and v0 has no
  cross-node submission/identity. A foreign node runs its own bot against
  its own money; our announcements are how its users discover our
  bounties.

Do not add node-awareness to any service in this phase (grep-pin: nothing
under `api/bounties/services/` introduced here imports from the nodes/
indexing domains).

## 11. Tests — `tests/test_issue_bounty_bot.py` (+ parser file)

Follow `tests/test_github_webhook.py` idioms exactly: sqlite
`_make_session()` helper, seeded user/agent/course helpers, signed-payload
builders, drive `ProcessGithubWebhookService.execute` for end-to-end tests
and the services directly for unit tests. `FakeGithubAppClient` grows
`create_issue_comment` (records `(repository, issue_number, body)` into
`self.comments`).

Payload builders:

```python
def _issue_comment_payload(*, repository, issue_number, body, author_id,
                           author_login, author_type="User",
                           is_pull_request=False) -> dict:
    issue = {"number": issue_number, "title": "Fix the flaky test",
             "html_url": f"https://github.com/{repository}/issues/{issue_number}"}
    if is_pull_request:
        issue["pull_request"] = {"url": "..."}
    return {"action": "created", "repository": {"full_name": repository},
            "issue": issue,
            "comment": {"body": body,
                        "user": {"id": author_id, "login": author_login,
                                 "type": author_type}}}
```

### 11.1 Parser — `logion/packages/bot/tests/test_parser.py` (public) + parity

One test per rule in §1.2 lives in the PUBLIC package, plus a golden
fixture file (`tests/fixtures/commands.jsonl`: body → expected command)
that is byte-identical in both repos, with a parity test on each side
(15.3/16.11 discipline — a drifted vendored copy fails CI in both).
Additional named tests:

- `test_confirm_in_same_comment_as_bounty_is_ignored` — the money pin.
- `test_mention_in_code_block_ignored`.
- `test_substring_login_does_not_match` — `@logion-bot-fan bounty 5` → None.
- `test_amount_bounds` — `0` rejected (no amount), `9999999` ok,
  `10000000` rejected.
- `test_dollar_and_decimal_amounts_rejected` — `$250`, `250.50`,
  `250 USD` → `kind='bounty'`, `amount_cents=None`.

### 11.2 The two-step invariant (the phase's reason to exist)

- `test_bounty_with_amount_asks_for_confirmation_and_opens_nothing` —
  deliver `@bot bounty 250` from the owner; assert: zero `Bounty` rows,
  thread `awaiting_confirmation` with `proposed_amount_cents == 250`, one
  bot comment containing `"250 credits"` and the confirm command.
- `test_confirm_opens_funds_and_replies` — then deliver `@bot confirm`
  (fresh delivery id); assert: one `Bounty` row with
  `reward_amount_cents == 250`, `status == "funded"`, creator ==
  course owner agent, one confirmed `BountyFunding`, creator's credit
  account debited 250, thread `opened` with `bounty_id` set, reply
  contains the bounty URL.
- `test_bounty_without_amount_asks_amount` — `@bot bounty` → thread
  `awaiting_amount`, reply asks in credits, zero bounties.
- `test_one_shot_bounty_confirm_does_not_open` — `@bot bounty 250 confirm`
  → identical assertions to the first test (this is the pin from §1.2).
- `test_confirm_before_any_proposal_refused` — `@bot confirm` on a bare
  issue → `REPLY_NOTHING_TO_CONFIRM`, zero bounties.
- `test_confirm_by_different_user_refused` — proposal by owner, confirm
  by another linked user → `REPLY_CONFIRM_WRONG_USER`, zero bounties,
  thread still `awaiting_confirmation`.
- `test_expired_thread_requires_restart` — freeze `expires_at` in the
  past; `@bot confirm` → thread flips `expired`, `REPLY_NOTHING_TO_CONFIRM`,
  zero bounties.

### 11.3 Policy matrix (one test per reason)

`test_refused_repo_not_linked`, `test_refused_course_not_published`,
`test_refused_author_not_linked` (no `github_identities` row),
`test_refused_author_not_course_owner` (linked user who owns nothing),
`test_refused_course_ambiguous_lists_slugs` (two active links, reply
contains both slugs) + `test_course_token_disambiguates`
(`course:slug-b` → proceeds against course B). Each asserts zero
`Bounty` rows and an `issue_bounty_refused` event with the exact reason.

### 11.4 Money-safety and webhook hygiene

- `test_insufficient_credits_leaves_open_unfunded_bounty` — owner balance
  100, confirm 250 → bounty `status == "open"`, zero `BountyFunding`,
  thread `opened`, reply is `REPLY_OPENED_UNFUNDED`.
- `test_replayed_confirm_delivery_creates_one_bounty` — same delivery id
  twice → one bounty, one funding (delivery idempotency).
- `test_second_confirm_new_delivery_does_not_double_open` — confirm again
  with a fresh delivery id after `opened` → `REPLY_ALREADY_OPENED`
  (via 6.2 guard: state is no longer `awaiting_confirmation`), still one
  bounty.
- `test_pr_comment_ignored` — `is_pull_request=True` → no comments, no
  thread.
- `test_bot_comment_ignored` — `author_type="Bot"` → nothing (loop guard).
- `test_edited_comment_ignored` / `test_issue_edit_ignored` —
  `action="edited"` on both event types → nothing.
- `test_comment_post_failure_does_not_5xx` — fake client raises
  `GithubApiError` on `create_issue_comment` → webhook still returns
  normally, state committed, failure logged.
- `test_no_usd_in_replies` — grep-pin over
  `issue_bounty_replies` module source: no `$`, no `USD` substring
  (allow `USD_CREDIT`? No — replies never name the internal currency
  code either).
- `test_issue_mention_services_import_no_node_modules` — grep-pin for §10.

### 11.5 Events

`test_events_emitted_per_transition` — one `Event` row each for
`issue_bounty_thread_updated`, `issue_bounty_opened`,
`issue_bounty_refused`, `issue_bounty_thread_cancelled` across a scripted
conversation.

## 12. Acceptance criteria

- [ ] On a linked repo with the App installed, the course owner can go
      from a plain issue to a **funded** bounty with exactly two comments
      (`@logion-bot bounty 250` → bot prompt → `@logion-bot confirm`), and
      the resulting bounty is indistinguishable from one created via the
      CLI (same services, same ledger entries, same events).
- [ ] No bounty is ever created or funded without an explicit integer
      credit amount AND an explicit later-comment confirmation from the
      same GitHub user — pinned by the one-shot, wrong-user,
      no-proposal, expired, and replay tests.
- [ ] Non-owners, unlinked repos/authors, unpublished courses, and
      ambiguous repos get attributable refusals (comment + event with
      stable reason) and zero state change.
- [ ] Insufficient credits produces an open-unfunded bounty and an honest
      comment — never a silent failure, never a negative balance.
- [ ] The bot never reacts to bots, PR threads, or edits; a failed GitHub
      comment never turns into a webhook retry storm.
- [ ] All bot copy is denominated in credits (grep-pinned no `$`/USD).
- [ ] `maintainer documentation: production-infrastructure.md` permission floor updated
      to contents+PRs+issues+metadata and events +`issues`/`issue_comment`.
- [ ] The bot's grammar, parser, and reply copy live in the public
      `logion/packages/bot` package (README states the behavior/policy
      split), vendored into `backend repository` with parity goldens; `make
      public-audit` passes — a stranger can improve the bot's UX by PR
      without ever seeing the private repo.
- [ ] Existing 15.5 flows (PR open/register, merge acceptance,
      installation lifecycle) untouched — full existing webhook test file
      passes without modification.

## Out of scope

- Third-party/non-owner funding from issues; platform-funded (15.8)
  bounties via mention; any new money code.
- Cross-node bot behavior (§10 — announcement-side comes free with 15.14;
  foreign-node opening is rejected by 15.14's hard boundary).
- Reacting to issue *closure* (no auto-cancel of bounties), issue labels,
  or slash-command style UX.
- Editing/deleting bot comments; localization of replies.
- CLI surface (none needed; conversation lives on GitHub).

## Implementation order for a less capable agent

0. Scaffold `logion/packages/bot` (pyproject, README with the
   behavior/policy split statement, CI wiring copied from
   `packages/indexer`).
1. `parse_issue_bot_command` in the public package + its test file +
   golden fixtures. Pure function, no DB — get the full §11.1 matrix
   green first. Then vendor into `backend repository` with the parity test.
2. Migration + `BountyIssueThread` model + repository +
   `list_active_by_repository` + schema-snapshot update.
3. `GithubAppClient.create_issue_comment/get_issue` (copy the `create_pull`
   method shape) + extend the existing client fake.
4. `IssueBountyPolicyService` + §11.3 tests (drive the service directly).
5. Reply constants module in the public package (+ vendored copy) + the
   no-USD grep-pin test on both sides.
6. `OpenBountyFromIssueService` + the §11.4 money tests (drive directly,
   fake client).
7. `HandleIssueMentionService` wiring the state machine + §11.2 tests.
8. Webhook `_dispatch_event` branches + end-to-end signed-payload tests +
   hygiene tests (§11.4 webhook rows).
9. `production-infrastructure.md` edit (§"GitHub App" block: permissions,
   events, new env var `LOGION_ISSUE_BOUNTY_THREAD_TTL_HOURS`).
10. Run the FULL existing bounty + webhook test suites; nothing may change.

## Cross-cutting improvement contract

This phase is governed by [`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md). A community improvement proposal is **unfunded by default** and may accept a free GitHub PR/submission, retain contributor attribution and evidence, and merge upstream or become a maintained derivative with lineage. Funding is an explicit prospective conversion: only a confirmed funded bounty creates escrow, payout, or `sh.logion.bounty.accepted.v1`; an unpaid acceptance uses `sh.logion.improvement.accepted.v1` and must write no ledger/payable row. Publication review remains independent in both lanes.
