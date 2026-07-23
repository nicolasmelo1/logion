<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.5: Bounty PR Bot & Merge-To-Acceptance Policy

> Implements the bot-PR + merge-payout slices of
> [`phase-15`](phase-15-native-resource-loop-and-first-ard-node.md).
> Depends on 15.1 (`github_identities`) and 15.3 (`course_source_links` — a
> bounty PR needs a linked repo). Uses a **GitHub App** (`logion-bot`), not
> the creator's OAuth token: the bot acts under its own identity, with
> per-repo installation grants, so every action is attributable and
> revocable. **PRs: exactly one per repo** — one `backend repository` PR
> (app auth + webhook + policy) and one `logion` PR (CLI submission surface).

## Non-negotiable product rules (from phase-15)

```text
GitHub merge != publication approval
GitHub PR    != bounty payout until Logion policy accepts it
```

The merge event *triggers* the normal `accept_bounty_submission` policy path;
it never bypasses it. GitHub must not be the only submission path — the
existing Logion-native submission flow keeps working unchanged.
**No new money code in this phase** — payout is whatever
`AcceptBountySubmissionService` already does (payable accrual; cash-out
unchanged), and nothing in this flow touches `courses.status`.

## Branch targets (0.1.x is live; 15.x–17 ship as 0.2.0)

| Deliverable | Repo | Base branch | Notes |
| --- | --- | --- | --- |
| Migration 0033, models, `github_app_auth.py`, `github_app_client.py`, repositories | `backend repository` | `main` | Safe on live: all code is dark until `LOGION_GITHUB_APP_*` env vars are set. |
| `open_submission_pr` / `register_submission_pr` services + controllers | `backend repository` | `main` | Endpoints answer `503 github_app_unconfigured` while env is empty. |
| `POST /v1/webhooks/github` controller + `ProcessGithubWebhookService` + merge policy | `backend repository` | `main` | Webhook endpoint is **dark until the GitHub App is registered**. Registering the `logion-bot` App on GitHub (permissions, webhook URL, secret) is an **operator step gated on the 0.2.0 release** — document it in `production-infrastructure.md`; merging this PR to `main` does not activate anything. |
| CLI `bounties submissions open-pr|register-pr` | `logion` (public) | `0.2.0` | The public CLI's 0.2.0 feature branch; do not target the public `main`. |

One PR per repo: the entire `backend repository` column above is a single PR
against `main`; the CLI is a single PR against `0.2.0`.

## 1. GitHub App + installation state (`backend repository` PR)

App `logion-bot`: permissions `contents: write`, `pull_requests: write`,
`metadata: read`; webhook events `pull_request`, `installation`. No other
permission, ever (auditable floor).

### 1.1 Config — `api/config.py`

Add to `Settings`, after the 15.1 `github_*` block, same `Field` idiom as
`stripe_webhook_secret`:

```python
    github_app_id: str = Field(
        default="", validation_alias="LOGION_GITHUB_APP_ID"
    )
    github_app_private_key_pem: str = Field(
        default="", validation_alias="LOGION_GITHUB_APP_PRIVATE_KEY_PEM"
    )
    github_app_webhook_secret: str = Field(
        default="", validation_alias="LOGION_GITHUB_APP_WEBHOOK_SECRET"
    )
```

Add all three to `packages/infra/deploy/env.example.production` (empty =
feature disabled, same sentinel discipline as `STRIPE_WEBHOOK_SECRET`).

### 1.2 Migration `alembic/versions/0033_github_app_and_submission_prs.py`

All **three** tables in this one migration. `down_revision` chains onto
15.3's migration:

```python
"""GitHub App installations, bounty submission PRs, GitHub webhook events

Revision ID: 0033_github_app_and_submission_prs
Revises: 0032_course_source_links
Create Date: 2026-07-03 12:00:00.000000

Adds the state for the logion-bot GitHub App: installation grants,
the submission<->PR join table, and the webhook idempotency table
(twin of stripe_webhook_events — pattern reused, table not shared).
"""

import sqlalchemy as sa

from alembic import op

revision = "0033_github_app_and_submission_prs"
down_revision = "0032_course_source_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_app_installations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "installation_id", sa.BigInteger(), nullable=False, unique=True
        ),
        sa.Column("account_login", sa.String(255), nullable=False),
        sa.Column("repository", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('active', 'suspended', 'deleted')",
            name="ck_github_app_installations_status",
        ),
    )
    op.create_index(
        "ix_github_app_installations_account_login",
        "github_app_installations",
        ["account_login"],
    )

    op.create_table(
        "bounty_submission_prs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "bounty_submission_id",
            sa.Uuid(),
            sa.ForeignKey("bounty_submissions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("repository", sa.String(255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("head_branch", sa.String(255), nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_by_login", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('open', 'merged', 'closed', 'superseded')",
            name="ck_bounty_submission_prs_status",
        ),
        sa.UniqueConstraint(
            "repository", "pr_number", name="uq_submission_prs_repo_number"
        ),
    )

    op.create_table(
        "github_webhook_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "delivery_id", sa.String(255), nullable=False, unique=True
        ),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("github_webhook_events")
    op.drop_table("bounty_submission_prs")
    op.drop_index(
        "ix_github_app_installations_account_login",
        table_name="github_app_installations",
    )
    op.drop_table("github_app_installations")
```

### 1.3 Models — `api/models.py`

Append after the 15.1 `GithubIdentity` model, matching `StripeWebhookEvent`
/ `Bounty` idioms exactly (`IdMixin`, `TimestampMixin`, `CheckConstraint`):

```python
class GithubAppInstallation(IdMixin, TimestampMixin, Base):
    __tablename__ = "github_app_installations"

    installation_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True
    )
    account_login: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    repository: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'active'")
    )

    __table_args__ = (
        CheckConstraint(
            "status in ('active', 'suspended', 'deleted')",
            name="ck_github_app_installations_status",
        ),
    )


class BountySubmissionPr(IdMixin, TimestampMixin, Base):
    __tablename__ = "bounty_submission_prs"

    bounty_submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bounty_submissions.id"), nullable=False, unique=True
    )
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    head_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    head_sha: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'open'")
    )
    merged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    merged_by_login: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        CheckConstraint(
            "status in ('open', 'merged', 'closed', 'superseded')",
            name="ck_bounty_submission_prs_status",
        ),
        UniqueConstraint(
            "repository", "pr_number", name="uq_submission_prs_repo_number"
        ),
    )


class GithubWebhookEvent(IdMixin, Base):
    __tablename__ = "github_webhook_events"

    delivery_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

Extend `tests/test_database_schema.py`'s snapshot for the three new tables.

### 1.4 App-auth JWT — `api/identity/services/github_app_auth.py` (complete)

No PyJWT. `cryptography` is already a dep after 15.1. Write this file
verbatim:

```python
"""GitHub App authentication: RS256 app JWT + cached installation tokens.

The app JWT is 40 lines of stdlib base64 + `cryptography` RSA signing —
deliberately no PyJWT dependency. Installation tokens are cached
in-process until 60s before their GitHub-reported expiry.
"""

import base64
import json
import threading
import time
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from api.identity.exceptions import GithubAppConfigurationError

_JWT_TTL_SECONDS = 600  # GitHub max is 10 minutes
_CLOCK_DRIFT_SECONDS = 60
_TOKEN_REFRESH_MARGIN_SECONDS = 60


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def create_app_jwt(
    *, app_id: str, private_key_pem: str, now: int | None = None
) -> str:
    """Return a short-lived RS256 JWT authenticating as the App itself."""
    if not app_id or not private_key_pem:
        raise GithubAppConfigurationError("GitHub App not configured")
    if now is None:
        now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iat": now - _CLOCK_DRIFT_SECONDS,
        "exp": now + _JWT_TTL_SECONDS,
        "iss": app_id,
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + _b64url(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    ).encode("ascii")
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"), password=None
    )
    signature = private_key.sign(
        signing_input, padding.PKCS1v15(), hashes.SHA256()
    )
    return signing_input.decode("ascii") + "." + _b64url(signature)


@dataclass
class _CachedInstallationToken:
    token: str
    expires_at_epoch: float


_token_cache: dict[int, _CachedInstallationToken] = {}
_token_cache_lock = threading.Lock()


def reset_installation_token_cache() -> None:
    """Test hook: clear the in-process installation-token cache."""
    with _token_cache_lock:
        _token_cache.clear()


def create_installation_token(
    *,
    installation_id: int,
    app_id: str,
    private_key_pem: str,
    fetch=None,
    now: float | None = None,
) -> str:
    """Return a cached installation token, minting via the API on miss.

    ``fetch`` is injectable for tests; the default implementation is
    ``GithubAppClient.create_installation_access_token`` (stdlib urllib,
    see github_app_client.py). Cached until expires_at - 60s.
    """
    if now is None:
        now = time.time()
    with _token_cache_lock:
        cached = _token_cache.get(installation_id)
        if (
            cached is not None
            and now
            < cached.expires_at_epoch - _TOKEN_REFRESH_MARGIN_SECONDS
        ):
            return cached.token
    if fetch is None:
        from api.identity.services.github_app_client import (
            fetch_installation_access_token,
        )

        fetch = fetch_installation_access_token
    jwt = create_app_jwt(app_id=app_id, private_key_pem=private_key_pem)
    token, expires_at_epoch = fetch(
        installation_id=installation_id, app_jwt=jwt
    )
    with _token_cache_lock:
        _token_cache[installation_id] = _CachedInstallationToken(
            token=token, expires_at_epoch=expires_at_epoch
        )
    return token
```

Add to `api/identity/exceptions.py` (module created in 15.1):
`GithubAppConfigurationError(Exception)`.

### 1.5 Bot REST client — `api/identity/services/github_app_client.py`

Stdlib-only (`urllib.request`), mirroring 15.1's `github_api_client.py`
(`_GITHUB_USER_AGENT`, `_TIMEOUT_S = 10`, JSON error envelope →
`GithubApiError(status, code)`). Module-level functions (all faked in
tests; **zero live network**):

```python
GITHUB_API_BASE = "https://api.github.com"

def fetch_installation_access_token(*, installation_id: int, app_jwt: str) -> tuple[str, float]:
    # POST /app/installations/{installation_id}/access_tokens
    # Authorization: Bearer {app_jwt}
    # -> (json["token"], parse ISO json["expires_at"] -> epoch float)

class GithubAppClient:
    """All calls authenticated with an installation token."""
    def __init__(self, *, installation_token: str) -> None: ...
    def get_ref(self, *, repository: str, ref: str) -> dict:
        # GET /repos/{repository}/git/ref/heads/{ref} -> {"object": {"sha": ...}}
    def create_ref(self, *, repository: str, branch: str, sha: str) -> dict:
        # POST /repos/{repository}/git/refs  {"ref": f"refs/heads/{branch}", "sha": sha}
        # GitHub answers 422 "Reference already exists" on duplicates —
        # map to GithubRefExistsError (caught by the idempotent retry path).
    def create_pull(self, *, repository: str, title: str, body: str,
                    head: str, base: str, draft: bool = True) -> dict:
        # POST /repos/{repository}/pulls
        # 422 "A pull request already exists" -> GithubPullExistsError
    def list_pulls_by_head(self, *, repository: str, head: str) -> list[dict]:
        # GET /repos/{repository}/pulls?state=open&head={owner}:{branch}
    def get_pull(self, *, repository: str, pr_number: int) -> dict:
        # GET /repos/{repository}/pulls/{pr_number}
    def get_collaborator_permission(self, *, repository: str, username: str) -> str:
        # GET /repos/{repository}/collaborators/{username}/permission
        # -> json["permission"] in {"admin","write","read","none"}; 404 -> "none"
```

Every method: explicit timeout, `User-Agent`,
`Accept: application/vnd.github+json`. Exceptions `GithubRefExistsError`,
`GithubPullExistsError` live beside `GithubApiError` in
`api/identity/exceptions.py`.

### 1.6 Repositories

`api/identity/repositories/github_app_installations.py` — same idiom as
`StripeWebhookEventRepository` (constructor takes `db`, `select()`,
`flush()`):

```python
class GithubAppInstallationRepository:
    def __init__(self, db: Session) -> None: ...
    def get_by_installation_id(self, installation_id: int) -> GithubAppInstallation | None: ...
    def get_active_for_repository(self, repository: str) -> GithubAppInstallation | None:
        # active row where repository == repository (exact "owner/repo")
        # OR (repository IS NULL AND account_login == repository.split("/")[0])
    def upsert_from_webhook(self, *, installation_id: int, account_login: str,
                            repository: str | None, status: str) -> GithubAppInstallation:
        # get_by_installation_id -> update status/account_login/repository, else create; flush
```

`api/bounties/repositories/bounty_submission_prs.py`:

```python
class BountySubmissionPrRepository:
    def __init__(self, db: Session) -> None: ...
    def get_by_submission_id(self, submission_id) -> BountySubmissionPr | None: ...
    def get_by_repo_and_number(self, repository: str, pr_number: int) -> BountySubmissionPr | None: ...
    def create(self, *, bounty_submission_id, repository, pr_number,
               head_branch, head_sha=None, status="open") -> BountySubmissionPr: ...
```

`api/webhooks/repositories/github_webhook_events.py` — literal twin of
`api/payments/repositories/stripe_webhook_events.py` with
`get_by_delivery_id(delivery_id)` and
`create(*, delivery_id, event_type, payload, processed_at=None)`.

## 2. Submission → PR flow (`backend repository` PR)

Extend `create_bounty_submission` with an optional GitHub materialization —
the existing service is **not modified**; PR opening is a separate,
explicit second call:

```text
POST /v1/bounties/{bounty_id}/submissions/{submission_id}/pr        auth: submitter
  -> 202 {pr_url, head_branch, fork_required}
POST /v1/bounties/{bounty_id}/submissions/{submission_id}/pr/register  auth: submitter
  body {pr_number} -> 200 {pr_url, head_branch, pr_number}
```

### 2.1 Constants — `api/bounties/constants/github_pr.py`

```python
BOUNTY_PR_MARKER_TEMPLATE = "<!-- logion:bounty_submission:{submission_id} -->"
BOUNTY_PR_BRANCH_TEMPLATE = "logion/bounty-{bounty_hex8}-{submission_hex8}"
BOUNTY_PR_TITLE_TEMPLATE = "[Logion bounty] {title}"
```

Branch name is **constant and deterministic**:
`f"logion/bounty-{bounty.id.hex[:8]}-{submission.id.hex[:8]}"` — idempotent
retries find the existing branch. The **marker, not the title, is the join
key**.

### 2.2 Exceptions — extend `api/bounties/exceptions.py`

```python
class BountyPrError(BountiesDomainError):
    """Base for bounty-PR domain failures; carries a stable code."""
    code = "bounty_pr_error"

class BountyPrNoSourceLinkError(BountyPrError):
    code = "bounty_pr_no_source_link"

class BountyPrAppNotInstalledError(BountyPrError):
    code = "bounty_pr_app_not_installed"

class BountyPrSubmissionStatusError(BountyPrError):
    code = "bounty_pr_submission_not_submitted"

class BountyPrMarkerMissingError(BountyPrError):
    code = "bounty_pr_marker_missing"
```

Controllers map `BountyPrError` → `422` with `detail=exc.code` (named 422
codes, one per precondition).

### 2.3 `api/bounties/services/open_submission_pr.py` (full body)

```python
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.bounties.constants.github_pr import (
    BOUNTY_PR_BRANCH_TEMPLATE,
    BOUNTY_PR_MARKER_TEMPLATE,
    BOUNTY_PR_TITLE_TEMPLATE,
)
from api.bounties.exceptions import (
    BountyPrAppNotInstalledError,
    BountyPrNoSourceLinkError,
    BountyPrSubmissionStatusError,
    SubmissionAccessDeniedError,
    SubmissionNotFoundError,
)
from api.bounties.repositories.bounties import BountyRepository
from api.bounties.repositories.bounty_submission_prs import (
    BountySubmissionPrRepository,
)
from api.bounties.repositories.bounty_submissions import (
    BountySubmissionRepository,
)
from api.courses.repositories.course_source_links import (  # 15.3
    CourseSourceLinkRepository,
)
from api.identity.exceptions import (
    GithubPullExistsError,
    GithubRefExistsError,
)
from api.identity.repositories.agents import AgentRepository
from api.identity.repositories.github_app_installations import (
    GithubAppInstallationRepository,
)
from api.identity.repositories.github_identities import (  # 15.1
    GithubIdentityRepository,
)
from api.notifications.services.create_event import CreateEventService

logger = logging.getLogger(__name__)


@dataclass
class OpenSubmissionPrResult:
    pr_url: str | None
    head_branch: str
    fork_required: bool


class OpenSubmissionPrService:
    def __init__(self, db: Session, *, github_client_factory) -> None:
        # github_client_factory(repository: str) -> GithubAppClient with an
        # installation token for that repo; controllers build the real one,
        # tests inject a fake.
        self.db = db
        self._client_factory = github_client_factory
        self.bounty_repo = BountyRepository(db)
        self.sub_repo = BountySubmissionRepository(db)
        self.pr_repo = BountySubmissionPrRepository(db)
        self.source_link_repo = CourseSourceLinkRepository(db)
        self.installation_repo = GithubAppInstallationRepository(db)
        self.identity_repo = GithubIdentityRepository(db)
        self._agent_repo = AgentRepository(db)

    def execute(
        self,
        *,
        bounty_id: uuid.UUID,
        submission_id: uuid.UUID,
        agent_id: uuid.UUID,
    ) -> OpenSubmissionPrResult:
        submission = self.sub_repo.get(submission_id)
        if submission is None or submission.bounty_id != bounty_id:
            raise SubmissionNotFoundError("Submission not found")
        if submission.submitter_agent_id != agent_id:
            raise SubmissionAccessDeniedError(
                "Only the submitter can open a PR for a submission"
            )
        if submission.status != "submitted":
            raise BountyPrSubmissionStatusError(
                "Only submitted submissions can open a PR"
            )
        bounty = self.bounty_repo.get(bounty_id)

        source_link = self.source_link_repo.get_active_by_course_id(
            bounty.course_id
        )
        if source_link is None:
            raise BountyPrNoSourceLinkError(
                "Bounty course has no active source link"
            )
        repository = source_link.repository

        installation = self.installation_repo.get_active_for_repository(
            repository
        )
        if installation is None:
            raise BountyPrAppNotInstalledError(
                "logion-bot is not installed on the linked repository"
            )

        head_branch = BOUNTY_PR_BRANCH_TEMPLATE.format(
            bounty_hex8=bounty.id.hex[:8],
            submission_hex8=submission.id.hex[:8],
        )

        # Idempotent short-circuit: PR row already exists -> return it.
        existing = self.pr_repo.get_by_submission_id(submission.id)
        if existing is not None:
            return OpenSubmissionPrResult(
                pr_url=self._pr_url(repository, existing.pr_number),
                head_branch=existing.head_branch,
                fork_required=False,
            )

        client = self._client_factory(repository)

        # Fork path: contents:write on the linked repo does not give the
        # *contributor* push access. If the submitter's GitHub identity is
        # missing or has no push permission, the bot cannot host their
        # branch — they must fork, open the PR themselves (with the marker
        # in the body), and call register.
        if self._fork_required(client, repository, agent_id):
            return OpenSubmissionPrResult(
                pr_url=None, head_branch=head_branch, fork_required=True
            )

        base_ref = source_link.default_ref
        head_sha = client.get_ref(repository=repository, ref=base_ref)[
            "object"
        ]["sha"]
        try:
            client.create_ref(
                repository=repository, branch=head_branch, sha=head_sha
            )
        except GithubRefExistsError:
            pass  # deterministic name: retry finds the existing branch

        marker = BOUNTY_PR_MARKER_TEMPLATE.format(
            submission_id=submission.id
        )
        body = (
            f"{marker}\n\n"
            f"Bounty: https://logion.sh/bounties/{bounty.id}\n"
            f"Submission: https://logion.sh/bounties/{bounty.id}"
            f"/submissions/{submission.id}\n\n"
            "Merging this PR triggers Logion's bounty acceptance policy; "
            "merge alone is neither publication nor payout."
        )
        try:
            pull = client.create_pull(
                repository=repository,
                title=BOUNTY_PR_TITLE_TEMPLATE.format(title=bounty.title),
                body=body,
                head=head_branch,
                base=base_ref,
                draft=True,
            )
        except GithubPullExistsError:
            pulls = client.list_pulls_by_head(
                repository=repository,
                head=f"{repository.split('/')[0]}:{head_branch}",
            )
            pull = pulls[0]  # same branch -> same PR (idempotent retry)

        self.pr_repo.create(
            bounty_submission_id=submission.id,
            repository=repository,
            pr_number=pull["number"],
            head_branch=head_branch,
            head_sha=head_sha,
        )
        CreateEventService(self.db).execute(
            event_type="bounty_pr_opened",
            actor_agent_id=agent_id,
            target_type="bounty_submission",
            target_id=submission.id,
            payload={
                "repository": repository,
                "pr_number": pull["number"],
                "head_branch": head_branch,
            },
        )
        self.db.commit()
        return OpenSubmissionPrResult(
            pr_url=pull["html_url"],
            head_branch=head_branch,
            fork_required=False,
        )

    def _fork_required(self, client, repository, agent_id) -> bool:
        user_id = self._agent_repo.get_user_id(agent_id)
        identity = (
            None
            if user_id is None
            else self.identity_repo.get_active_by_user_id(user_id)
        )
        if identity is None:
            return True
        permission = client.get_collaborator_permission(
            repository=repository, username=identity.github_login
        )
        return permission not in ("write", "admin")

    def _pr_url(self, repository: str, pr_number: int) -> str:
        return f"https://github.com/{repository}/pull/{pr_number}"
```

Contributor pushes to the branch with **their own git credentials** —
Logion never proxies contributor pushes.

### 2.4 `api/bounties/services/register_submission_pr.py`

Same constructor shape (`db`, `github_client_factory`). `execute(*,
bounty_id, submission_id, agent_id, pr_number)`:

1. same submission lookup / submitter / `submitted`-status /
   source-link / installation preconditions as 2.3 (same exceptions);
2. idempotent: existing PR row with the same `(repository, pr_number)` →
   return it; existing row with a different number →
   `BountySubmissionConflictError`;
3. `pull = client.get_pull(repository=..., pr_number=pr_number)`; the bot
   verifies the canonical marker:
   `if BOUNTY_PR_MARKER_TEMPLATE.format(submission_id=submission.id) not in
   (pull.get("body") or ""): raise BountyPrMarkerMissingError(...)`;
4. `pr_repo.create(... head_branch=pull["head"]["ref"],
   head_sha=pull["head"]["sha"])`;
5. `CreateEventService(...).execute(event_type="bounty_pr_registered",
   actor_agent_id=agent_id, target_type="bounty_submission",
   target_id=submission.id, payload={"repository": ..., "pr_number": ...})`;
   `self.db.commit()`; return `(pr_url, head_branch, pr_number)`.

Every bot action emits an `events` row
(`event_type="bounty_pr_opened|registered"`, target bounty submission).

### 2.5 Controllers

Two new files under `api/bounties/controllers/`, wired into
`api/bounties/controllers/router.py`, mirroring
`accept_bounty_submission.py` (same `DatabaseSession` /
`AuthenticatedAgent` annotated deps, same exception→status mapping plus
`BountyPrError` → 422 with `detail=exc.code`).

`open_submission_pr.py`:

```python
router = APIRouter(
    prefix="/bounties/{bounty_id}/submissions", tags=["bounties"]
)


class OpenSubmissionPrResponse(BaseModel):
    pr_url: str | None
    head_branch: str
    fork_required: bool


def _github_client_factory(db: Session):
    settings = get_settings()
    if not settings.github_app_id or not settings.github_app_private_key_pem:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="github_app_unconfigured",
        )

    def factory(repository: str) -> GithubAppClient:
        installation = GithubAppInstallationRepository(
            db
        ).get_active_for_repository(repository)
        token = create_installation_token(
            installation_id=installation.installation_id,
            app_id=settings.github_app_id,
            private_key_pem=settings.github_app_private_key_pem,
        )
        return GithubAppClient(installation_token=token)

    return factory


@router.post(
    "/{submission_id}/pr",
    response_model=OpenSubmissionPrResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Open a draft bounty PR on the linked repository",
    operation_id="open_bounty_submission_pr",
    responses={...401/403/404/422/503 with ErrorResponse...},
)
def open_bounty_submission_pr(
    bounty_id: uuid.UUID,
    submission_id: uuid.UUID,
    db: DatabaseSession,
    agent: AuthenticatedAgent,
):
    try:
        result = OpenSubmissionPrService(
            db, github_client_factory=_github_client_factory(db)
        ).execute(
            bounty_id=bounty_id,
            submission_id=submission_id,
            agent_id=agent.id,
        )
    except SubmissionNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
    except SubmissionAccessDeniedError as exc:
        raise HTTPException(403, str(exc)) from None
    except BountyPrError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, exc.code
        ) from None
    return OpenSubmissionPrResponse(
        pr_url=result.pr_url,
        head_branch=result.head_branch,
        fork_required=result.fork_required,
    )
```

`register_submission_pr.py`: `POST /{submission_id}/pr/register`, body
`RegisterSubmissionPrRequest(pr_number: int)`, `operation_id
"register_bounty_submission_pr"`, 200 response
`{pr_url, head_branch, pr_number}`; same mapping. Re-export contract:
`make export-openapi` → `make sync-public-contract` so the generated SDK
grows `client.v1.bounties.open_submission_pr(bounty_id=..., submission_id=...)`
and `.register_submission_pr(bounty_id=..., submission_id=..., pr_number=...)`.

## 3. Webhook + merge policy (`backend repository` PR)

```text
POST /v1/webhooks/github        auth: HMAC X-Hub-Signature-256
```

### 3.1 Exceptions — extend `api/webhooks/exceptions.py`

Beside the Snyk twins: `GithubWebhookConfigurationError`,
`GithubWebhookInvalidSignatureError`, `GithubWebhookInvalidPayloadError`
(plain `Exception` subclasses, same docstring style).

### 3.2 Controller — `api/webhooks/controllers/github_webhook.py`

Mirror `stripe_webhook.py` **exactly** (same decomposition; the service
verifies, the controller only maps exceptions):

```python
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from api.config import get_settings
from api.core.responses import ErrorResponse
from api.database import get_db
from api.webhooks.exceptions import (
    GithubWebhookConfigurationError,
    GithubWebhookInvalidPayloadError,
    GithubWebhookInvalidSignatureError,
)
from api.webhooks.services.process_github_webhook import (
    ProcessGithubWebhookService,
)

router = APIRouter(tags=["webhooks"])


@router.post(
    "/webhooks/github",
    status_code=status.HTTP_200_OK,
    summary="Handle logion-bot GitHub App webhook events.",
    operation_id="github_webhook",
    responses={
        200: {"description": "Successful response"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
)
async def github_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Handle logion-bot GitHub App webhook events."""
    settings = get_settings()
    payload = await request.body()
    sig_header = request.headers.get("x-hub-signature-256", "")
    delivery_id = request.headers.get("x-github-delivery", "")
    event_type = request.headers.get("x-github-event", "")

    try:
        ProcessGithubWebhookService(db=db).execute(
            payload=payload,
            sig_header=sig_header,
            delivery_id=delivery_id,
            event_type=event_type,
            webhook_secret=settings.github_app_webhook_secret,
        )
    except GithubWebhookConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        ) from None
    except GithubWebhookInvalidSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        ) from None
    except GithubWebhookInvalidPayloadError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        ) from None

    return Response(status_code=status.HTTP_200_OK)
```

Register in `api/webhooks/controllers/router.py` beside the Stripe/Snyk
routers.

### 3.3 `api/webhooks/services/process_github_webhook.py` (full body)

Twin of `ProcessStripeWebhookService` — same method decomposition, same
log event names adapted (`github.webhook.received|duplicate|processed|failed`,
13.8 structured-log conventions), same `IntegrityError` duplicate-skip.
Reuse the **pattern, not the table**: the idempotency key is the
`X-GitHub-Delivery` UUID in `github_webhook_events`.

```python
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.bounties.services.handle_bounty_pr_merged import (
    HandleBountyPrMergedService,
)
from api.identity.repositories.github_app_installations import (
    GithubAppInstallationRepository,
)
from api.webhooks.exceptions import (
    GithubWebhookConfigurationError,
    GithubWebhookInvalidPayloadError,
    GithubWebhookInvalidSignatureError,
)
from api.webhooks.repositories.github_webhook_events import (
    GithubWebhookEventRepository,
)

logger = logging.getLogger(__name__)

INSTALLATION_STATUS_BY_ACTION = {
    "created": "active",
    "unsuspend": "active",
    "suspend": "suspended",
    "deleted": "deleted",
}


class ProcessGithubWebhookService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._repo = GithubWebhookEventRepository(db)

    def execute(
        self,
        *,
        payload: bytes,
        sig_header: str,
        delivery_id: str,
        event_type: str,
        webhook_secret: str | None,
    ) -> None:
        if not webhook_secret:
            raise GithubWebhookConfigurationError(
                "Webhook secret not configured"
            )

        self._verify_signature(
            payload=payload,
            sig_header=sig_header,
            webhook_secret=webhook_secret,
        )
        event = self._parse_payload(payload)
        if not delivery_id:
            raise GithubWebhookInvalidPayloadError(
                "Missing X-GitHub-Delivery header"
            )

        existing = self._create_or_get_webhook_event(
            delivery_id=delivery_id,
            event_type=event_type,
            payload=event,
        )
        if existing is not None and existing.processed_at is not None:
            logger.info(
                "github.webhook.duplicate",
                extra={"delivery_id": delivery_id, "event_type": event_type},
            )
            return
        logger.info(
            "github.webhook.received",
            extra={"delivery_id": delivery_id, "event_type": event_type},
        )
        try:
            self._dispatch_event(event_type=event_type, event=event)
        except Exception:
            logger.exception(
                "github.webhook.failed",
                extra={"delivery_id": delivery_id, "event_type": event_type},
            )
            raise
        self._mark_webhook_event_processed(existing, delivery_id)
        logger.info(
            "github.webhook.processed",
            extra={"delivery_id": delivery_id, "event_type": event_type},
        )

    def _verify_signature(
        self, *, payload: bytes, sig_header: str, webhook_secret: str
    ) -> None:
        if not sig_header or not sig_header.startswith("sha256="):
            raise GithubWebhookInvalidSignatureError("Invalid signature")
        expected = sig_header[len("sha256=") :]
        computed = hmac.new(
            webhook_secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(computed, expected):
            raise GithubWebhookInvalidSignatureError("Invalid signature")

    def _parse_payload(self, payload: bytes) -> dict:
        try:
            event = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            raise GithubWebhookInvalidPayloadError(
                "Invalid payload"
            ) from None
        if type(event) is not dict:
            raise GithubWebhookInvalidPayloadError("Invalid payload")
        return event

    def _create_or_get_webhook_event(
        self, *, delivery_id: str, event_type: str, payload: dict
    ):
        existing = self._repo.get_by_delivery_id(delivery_id)
        if existing is not None:
            return existing
        try:
            self._repo.create(
                delivery_id=delivery_id,
                event_type=event_type,
                payload=payload,
                processed_at=None,
            )
        except IntegrityError:
            self.db.rollback()
            return self._repo.get_by_delivery_id(delivery_id)
        return None

    def _mark_webhook_event_processed(self, existing, delivery_id) -> None:
        webhook_event = existing or self._repo.get_by_delivery_id(
            delivery_id
        )
        if webhook_event is not None:
            webhook_event.processed_at = datetime.now(tz=UTC)
        self.db.commit()

    def _dispatch_event(self, *, event_type: str, event: dict) -> None:
        if event_type == "pull_request":
            self._handle_pull_request_event(event)
        elif event_type == "installation":
            self._handle_installation_event(event)
        else:
            # Unknown events: log + 200 — never 5xx GitHub into a
            # retry storm.
            logger.info(
                "github.webhook.ignored", extra={"event_type": event_type}
            )

    def _handle_pull_request_event(self, event: dict) -> None:
        if event.get("action") != "closed":
            return
        pull = event.get("pull_request") or {}
        repository = (event.get("repository") or {}).get("full_name", "")
        HandleBountyPrMergedService(db=self.db).execute(
            repository=repository,
            pr_number=pull.get("number"),
            merged=bool(pull.get("merged")),
            merged_by_login=((pull.get("merged_by") or {}).get("login")),
            merged_at=pull.get("merged_at"),
            head_sha=(pull.get("head") or {}).get("sha"),
        )

    def _handle_installation_event(self, event: dict) -> None:
        action = event.get("action", "")
        status = INSTALLATION_STATUS_BY_ACTION.get(action)
        if status is None:
            return
        installation = event.get("installation") or {}
        account = installation.get("account") or {}
        repositories = event.get("repositories") or []
        repository = (
            repositories[0].get("full_name")
            if len(repositories) == 1
            else None  # null = org-wide / multi-repo grant
        )
        GithubAppInstallationRepository(self.db).upsert_from_webhook(
            installation_id=installation.get("id"),
            account_login=account.get("login", ""),
            repository=repository,
            status=status,
        )
        self.db.commit()
```

### 3.4 `api/bounties/services/handle_bounty_pr_merged.py`

The merge event *triggers* the normal policy path. **System actor
adaptation:** `AcceptBountySubmissionService.execute(bounty_id,
submission_id, agent_id)` identifies its acceptor via
`bounty.creator_agent_id != agent_id → SubmissionAccessDeniedError`; there
is no separate system principal, so once (and only once) the merge policy
has verified the merger's GitHub login, the webhook invokes acceptance
**as `agent_id=bounty.creator_agent_id`** — the policy check is the
authorization, the creator agent id is just the actor the unchanged
service requires. All of the service's own guards (funded/in_review,
single accepted submission, idempotent re-accept) still run.

```python
class HandleBountyPrMergedService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.pr_repo = BountySubmissionPrRepository(db)
        self.sub_repo = BountySubmissionRepository(db)
        self.bounty_repo = BountyRepository(db)

    def execute(
        self,
        *,
        repository: str,
        pr_number: int | None,
        merged: bool,
        merged_by_login: str | None,
        merged_at: str | None,
        head_sha: str | None,
    ) -> None:
        if pr_number is None:
            return
        pr_row = self.pr_repo.get_by_repo_and_number(repository, pr_number)
        if pr_row is None or pr_row.status != "open":
            return  # unknown PRs never move money

        if not merged:
            pr_row.status = "closed"
            self.db.commit()
            return

        pr_row.status = "merged"
        pr_row.merged_at = datetime.now(tz=UTC)
        pr_row.merged_by_login = merged_by_login
        pr_row.head_sha = head_sha or pr_row.head_sha

        submission = self.sub_repo.get(pr_row.bounty_submission_id)
        bounty = self.bounty_repo.get(submission.bounty_id)

        reason = MergeAcceptancePolicyService(self.db).execute(
            bounty=bounty,
            submission=submission,
            merged_by_login=merged_by_login,
        )
        if reason is not None:
            CreateEventService(self.db).execute(
                event_type="merge_policy_rejected",
                target_type="bounty_submission",
                target_id=submission.id,
                payload={
                    "reason": reason,
                    "repository": repository,
                    "pr_number": pr_number,
                    "merged_by_login": merged_by_login,
                },
            )
            self.db.commit()  # bounty untouched; creator can still
            return            # accept manually in Logion

        # Existing policy path — commits internally, accrues the
        # contributor payable. No new money code.
        AcceptBountySubmissionService(self.db).execute(
            bounty_id=bounty.id,
            submission_id=submission.id,
            agent_id=bounty.creator_agent_id,
        )
```

### 3.5 `api/bounties/services/merge_acceptance_policy.py`

```python
class MergeAcceptancePolicyService:
    """Returns None when the merge may accept the submission, else a
    stable rejection-reason string (recorded on the event)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.course_repo = CourseRepository(db)
        self._agent_repo = AgentRepository(db)
        self.identity_repo = GithubIdentityRepository(db)

    def execute(self, *, bounty, submission, merged_by_login) -> str | None:
        if submission.status != "submitted":
            return "submission_not_submitted"
        if bounty.status != BOUNTY_STATUS_FUNDED:
            return "bounty_not_funded"
        if not merged_by_login:
            return "merger_unknown"
        course = self.course_repo.get(bounty.course_id)
        owner_user_id = self._agent_repo.get_user_id(course.owner_agent_id)
        identity = (
            None
            if owner_user_id is None
            else self.identity_repo.get_active_by_user_id(owner_user_id)
        )
        if identity is None:
            return "owner_github_identity_missing"
        # GitHub logins are case-insensitive.
        if identity.github_login.lower() != merged_by_login.lower():
            return "merger_not_course_owner"
        return None
```

The merger must be the **course owner's** linked `github_login` (15.1
identity) — a random maintainer's merge does **not** accept. Any failure →
`merge_policy_rejected` event with the reason; the bounty is left
untouched (the creator can still accept manually in Logion).

## 4. CLI (`logion` PR, base branch `0.2.0`)

Single-file command module idiom (`cli/commands/bounties.py`): add two
sub-parsers to the existing `submissions` sub-group and two handlers.
Envelope kinds `logion.bounties.submissions.open-pr|register-pr`. Both are
mutating → companion confirmation-gated (`require_yes`; update the
mutating list in `logion-marketplace-companion.md`).

In `register()`, after the withdraw parser:

```python
    # submissions open-pr
    sop = sub_sub.add_parser(
        "open-pr",
        help="Open a draft GitHub PR for a submission",
        parents=[COMMON_PARSER],
    )
    sop.add_argument("bounty_id", metavar="BOUNTY_ID")
    sop.add_argument("submission_id", metavar="SUBMISSION_ID")
    sop.add_argument("--yes", action="store_true")
    sop.set_defaults(handler=handle_submissions_open_pr)

    # submissions register-pr
    srp = sub_sub.add_parser(
        "register-pr",
        help="Register a fork-opened GitHub PR for a submission",
        parents=[COMMON_PARSER],
    )
    srp.add_argument("bounty_id", metavar="BOUNTY_ID")
    srp.add_argument("submission_id", metavar="SUBMISSION_ID")
    srp.add_argument("--pr-number", required=True, type=int)
    srp.add_argument("--yes", action="store_true")
    srp.set_defaults(handler=handle_submissions_register_pr)
```

Handlers (mirror `handle_submissions_accept`'s shape exactly —
validate ids, `require_yes`, `resolve_config_from_args`, `make_client`,
`try/except/else/finally` with `handle_error` and `client.close()`):

```python
FORK_NEXT_STEPS = """\
This repository requires a fork:
  1. Fork the repository on GitHub and push your work to branch:
       {head_branch}
  2. Open a PR from your fork; keep the Logion marker in the PR body.
  3. Run: logion bounties submissions register-pr {bounty_id} \
{submission_id} --pr-number N --yes
"""


def handle_submissions_open_pr(args: argparse.Namespace) -> int:
    """Execute the bounties submissions open-pr command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.submission_id, "SUBMISSION_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(
        args.yes, "open a draft PR for this submission"
    )
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.bounties.open_submission_pr(
            bounty_id=args.bounty_id,
            submission_id=args.submission_id,
        )
        data = to_data(result)
        if config.json_output:
            emit_json("logion.bounties.submissions.open-pr", data)
        elif data.get("fork_required"):
            print(
                FORK_NEXT_STEPS.format(
                    head_branch=data.get("head_branch", ""),
                    bounty_id=args.bounty_id,
                    submission_id=args.submission_id,
                )
            )
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_submissions_register_pr(args: argparse.Namespace) -> int:
    """Execute the bounties submissions register-pr command."""
    # same two validate_uuid_id calls, then:
    refusal = require_yes(args.yes, "register this PR for the submission")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.bounties.register_submission_pr(
            bounty_id=args.bounty_id,
            submission_id=args.submission_id,
            pr_number=args.pr_number,
        )
        if config.json_output:
            emit_json(
                "logion.bounties.submissions.register-pr", to_data(result)
            )
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
```

No `--json` exemptions (`JSON_EXEMPT_COMMANDS == frozenset()` stays).
SDK methods come from the regenerated contract (section 2.5); document the
subgroup in `cli-structure.md`.

## 5. Tests

### 5.1 Backend — `tests/test_github_app_auth.py`

Fixture RSA keypair is **generated in-test** with `cryptography` (never a
checked-in real key):

```python
import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from api.identity.exceptions import GithubAppConfigurationError
from api.identity.services import github_app_auth
from api.identity.services.github_app_auth import (
    create_app_jwt,
    create_installation_token,
    reset_installation_token_cache,
)


@pytest.fixture(scope="module")
def rsa_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")


def _decode_segment(segment: str) -> dict:
    padded = segment + "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def test_app_jwt_header_and_claims(rsa_pem):
    jwt = create_app_jwt(app_id="12345", private_key_pem=rsa_pem, now=1000)
    header_b64, claims_b64, signature_b64 = jwt.split(".")
    assert _decode_segment(header_b64) == {"alg": "RS256", "typ": "JWT"}
    claims = _decode_segment(claims_b64)
    assert claims == {"iat": 940, "exp": 1600, "iss": "12345"}
    assert signature_b64  # non-empty, urlsafe, unpadded
    assert "=" not in signature_b64


def test_app_jwt_unconfigured_raises(rsa_pem):
    with pytest.raises(GithubAppConfigurationError):
        create_app_jwt(app_id="", private_key_pem=rsa_pem)
    with pytest.raises(GithubAppConfigurationError):
        create_app_jwt(app_id="1", private_key_pem="")


def test_installation_token_cache_expiry(rsa_pem):
    reset_installation_token_cache()
    calls = []

    def fake_fetch(*, installation_id, app_jwt):
        calls.append(installation_id)
        return (f"tok-{len(calls)}", 1000.0)  # expires_at epoch

    kwargs = dict(
        installation_id=7,
        app_id="1",
        private_key_pem=rsa_pem,
        fetch=fake_fetch,
    )
    # frozen clock: fresh mint, then cache hit before expires_at-60s,
    # then re-mint at/after the margin.
    assert create_installation_token(now=100.0, **kwargs) == "tok-1"
    assert create_installation_token(now=900.0, **kwargs) == "tok-1"
    assert create_installation_token(now=940.0, **kwargs) == "tok-2"
    assert calls == [7, 7]
```

Also verify the signature cryptographically in one test: load the public
key from the fixture and `public_key.verify(sig, signing_input,
PKCS1v15(), SHA256())` does not raise.

### 5.2 Backend — `tests/test_open_submission_pr.py`

Use the `_make_session()` sqlite/StaticPool helper idiom from
`tests/test_snyk_webhook.py`, plus its user/agent seeding helpers. GitHub
client **fully faked**:

```python
class FakeGithubAppClient:
    def __init__(self):
        self.refs: dict[str, str] = {}
        self.pulls: list[dict] = []
        self.permission = "write"

    def get_ref(self, *, repository, ref):
        return {"object": {"sha": "base-sha"}}

    def create_ref(self, *, repository, branch, sha):
        if branch in self.refs:
            raise GithubRefExistsError("Reference already exists")
        self.refs[branch] = sha
        return {"ref": f"refs/heads/{branch}"}

    def create_pull(self, *, repository, title, body, head, base, draft):
        for pull in self.pulls:
            if pull["head"]["ref"] == head:
                raise GithubPullExistsError("A pull request already exists")
        pull = {
            "number": len(self.pulls) + 1,
            "title": title,
            "body": body,
            "draft": draft,
            "html_url": f"https://github.com/{repository}/pull/1",
            "head": {"ref": head, "sha": "base-sha"},
        }
        self.pulls.append(pull)
        return pull

    def list_pulls_by_head(self, *, repository, head):
        branch = head.split(":", 1)[1]
        return [p for p in self.pulls if p["head"]["ref"] == branch]

    def get_pull(self, *, repository, pr_number):
        return self.pulls[pr_number - 1]

    def get_collaborator_permission(self, *, repository, username):
        return self.permission
```

Named tests (each seeds a course + active `course_source_links` row +
active `github_app_installations` row + funded bounty + submitted
submission unless the test removes one piece):

- `test_open_pr_requires_source_link` — no source-link row →
  `pytest.raises(BountyPrNoSourceLinkError)`.
- `test_open_pr_requires_app_installation` — no installation row →
  `BountyPrAppNotInstalledError`.
- `test_open_pr_requires_submitted_status` — submission status
  `withdrawn` → `BountyPrSubmissionStatusError`. (3× 422 preconditions.)
- `test_branch_name_is_deterministic` — result.head_branch ==
  `f"logion/bounty-{bounty.id.hex[:8]}-{submission.id.hex[:8]}"`.
- `test_pr_body_contains_marker_and_is_draft` — fake client's recorded
  pull has `draft is True` and
  `f"<!-- logion:bounty_submission:{submission.id} -->" in body`.
- `test_open_pr_idempotent_retry` — call `execute` twice; fake records
  exactly one branch + one pull; second result has the same `pr_url`;
  exactly one `bounty_submission_prs` row.
- `test_fork_path_returns_fork_required` — `fake.permission = "read"` →
  `fork_required is True`, `pr_url is None`, no branch/pull created.
- `test_register_verifies_marker` — seed a fake pull whose body lacks the
  marker → `RegisterSubmissionPrService` raises
  `BountyPrMarkerMissingError`; with the marker → row created with the
  pull's head branch/sha and a `bounty_pr_registered` event exists
  (`select(Event).where(Event.type == "bounty_pr_registered")`).
- `test_open_pr_emits_event` — `Event` row with `type ==
  "bounty_pr_opened"`, `target_id == submission.id`.

### 5.3 Backend — `tests/test_github_webhook.py`

Recorded-payload fixtures: builder helpers that mirror GitHub's documented
shapes (keep them minimal but structurally faithful — these stand in for
recorded webhook deliveries):

```python
def _signed(body: dict, secret: str) -> tuple[bytes, str]:
    raw = json.dumps(body).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, f"sha256={sig}"


def _pull_request_closed_payload(
    *, repository, pr_number, merged, merged_by_login
) -> dict:
    return {
        "action": "closed",
        "repository": {"full_name": repository},
        "pull_request": {
            "number": pr_number,
            "merged": merged,
            "merged_by": {"login": merged_by_login},
            "merged_at": "2026-07-03T12:00:00Z",
            "head": {"ref": "logion/bounty-x", "sha": "head-sha"},
        },
    }


def _installation_payload(*, action, installation_id, login, repos) -> dict:
    return {
        "action": action,
        "installation": {
            "id": installation_id,
            "account": {"login": login},
        },
        "repositories": [{"full_name": r} for r in repos],
    }
```

Named tests (drive `ProcessGithubWebhookService.execute` directly, snyk
test style; seed full bounty state with the existing bounty test helpers):

- `test_bad_signature_rejected` — tampered body vs signature →
  `GithubWebhookInvalidSignatureError` (controller maps to 400); missing
  `sha256=` prefix likewise.
- `test_replay_skipped_by_delivery_id` — deliver the same
  `delivery_id` twice; second call returns early, exactly one
  `github_webhook_events` row, `processed_at` set once, and acceptance
  side effects happen once.
- `test_merge_by_owner_accepts_and_accrues_payable` — course owner user
  has an active `GithubIdentity(github_login="owner-login")`; funded
  bounty; PR row seeded via `BountySubmissionPrRepository`; deliver
  `pull_request.closed merged=true merged_by=owner-login` → submission
  `status == "accepted"`, bounty `status == "awarded"`, one
  `CreatorPayableBalance` row with `source == "bounty_award"` and
  `amount_cents == gross - gross * 1500 // 10000` (assert through the
  existing bounty test helpers), PR row
  `status == "merged"` with `merged_by_login` recorded.
- `test_merge_by_non_owner_records_rejection_and_no_state_change` —
  `merged_by="random-maintainer"` → `Event` row
  `type == "merge_policy_rejected"` with
  `payload["reason"] == "merger_not_course_owner"`; submission still
  `submitted`, bounty still `funded`, zero payable rows; PR row is
  `merged` (fact recorded, money untouched).
- `test_unfunded_bounty_no_acceptance` — bounty `open` →
  rejection event with `reason == "bounty_not_funded"`, no payable.
- `test_unknown_pr_ignored` — no `bounty_submission_prs` row → no events,
  no exceptions, webhook row marked processed.
- `test_installation_lifecycle_upserts` — deliver
  `installation.created` (single repo → `repository` set), then
  `suspend`, then `deleted` with fresh delivery ids; one
  `github_app_installations` row whose `status` walks
  `active → suspended → deleted`.
- `test_unknown_event_logged_and_processed` — `event_type="star"` → no
  exception, row marked processed (never 5xx GitHub into retry storms).

### 5.4 Backend — `tests/test_merge_is_not_publication.py`

```python
def test_merge_acceptance_does_not_touch_course_status(db):
    # seed published course (status="published", published_at set),
    # a ready CourseVersion, funded bounty, submitted submission,
    # PR row, owner github identity
    before_status = course.status
    before_published_at = course.published_at
    version_count = db.scalar(
        select(func.count()).select_from(CourseVersion)
    )
    # deliver the merged pull_request webhook (owner login)
    ...
    db.refresh(course)
    assert submission.status == "accepted"
    assert course.status == before_status
    assert course.published_at == before_published_at
    assert (
        db.scalar(select(func.count()).select_from(CourseVersion))
        == version_count
    )
```

A merged PR whose acceptance succeeds still requires a new course version
+ review before buyers see it — this test is the tripwire.

### 5.5 CLI — `tests/test_cli_bounties_pr.py` (public repo)

Extend the `FakeBountiesResource` pattern from `test_cli_bounties.py`:

```python
    def open_submission_pr(self, **kwargs):
        self.last_call = ("open_submission_pr", kwargs)
        return self.open_pr_response  # test-settable dict

    def register_submission_pr(self, **kwargs):
        self.last_call = ("register_submission_pr", kwargs)
        return {"pr_url": "https://github.com/o/r/pull/2",
                "head_branch": "logion/bounty-x", "pr_number": 2}
```

Named tests:

- `test_open_pr_parser_and_call` — `main(["bounties", "submissions",
  "open-pr", BID, SID, "--yes"])` returns 0 and the fake saw
  `("open_submission_pr", {"bounty_id": BID, "submission_id": SID})`.
- `test_open_pr_requires_yes` — without `--yes` exit code 2 and no SDK
  call (confirmation gating).
- `test_open_pr_json_envelope` — with `--json`, stdout parses as JSON with
  `kind == "logion.bounties.submissions.open-pr"`.
- `test_open_pr_fork_rendering` — fake returns
  `{"fork_required": True, "pr_url": None, "head_branch": "logion/bounty-x"}`;
  human output contains `"requires a fork"`, the branch name, and
  `"register-pr"`.
- `test_register_pr_parser_envelope_and_gating` — `--pr-number 2`
  forwarded as int; `--yes` required; `--json` kind is
  `logion.bounties.submissions.register-pr`.
- `test_invalid_uuid_exits_2` — both commands reject malformed ids before
  any network.

## 6. Acceptance criteria

- [ ] Contributor: submit in Logion → one command opens a draft PR on the
      linked repo; creator merges on GitHub; submission flips to accepted and
      payout accrues through the unchanged bounty policy — with the owner-login
      merge gate enforced.
- [ ] Webhook is HMAC-verified, delivery-idempotent, and logs
      received/duplicate/processed/failed like the Stripe webhook.
- [ ] Non-owner merges, unfunded bounties, and unknown PRs never move money;
      each records an auditable event with a reason.
- [ ] Logion-native (non-GitHub) submissions still work end-to-end unchanged.
- [ ] App permission set is exactly contents+PRs+metadata (documented in
      `maintainer documentation: api.md` webhooks section + a new `production-infrastructure.md`
      env block, including the operator App-registration step gated on 0.2.0).

## Out of scope

- Running `evals.commands` on PR heads (16.1 eval-backed acceptance).
- Bounties on indexed/unowned listings (15.8).
- Auto-merging, CI orchestration, or any GitHub Actions business logic.

## 7. Implementation appendix — compare against current code

Current repo shape to respect:

- Bounty submission state and payout flow already live in
  `backend repository/packages/api/api/bounties`. Extend the existing submission
  services instead of adding a parallel PR-submission domain.
- GitHub user identity comes from 15.1 under `api/identity`; this phase should
  read `github_identities`, not duplicate OAuth/token storage.
- Course repository provenance comes from 15.3 `course_source_links`; the PR
  bot must require that link for repo target resolution.
- Existing webhook code lives under `api/webhooks`; GitHub webhook routing can
  live there or in bounties, but signature verification must be isolated in a
  small service and covered by unit tests.
- Public CLI bounty commands are in
  `logion/packages/cli/cli/commands/bounties.py`; admin/shared helpers are in
  `_config.py`, `_credentials.py`, `_output.py`, and `_errors.py`.

Branch target reminder:

- `backend repository` backend changes may target `main` because every GitHub App
  path is dark until `LOGION_GITHUB_APP_*` settings and the webhook secret are
  configured.
- `logion` public CLI and companion/docs changes target `0.2.0`; do not expose
  `bounties submissions open-pr|register-pr` on public 0.1.x `main`.
- GitHub App registration in GitHub's UI is an operator rollout step for
  0.2.0, not a side effect of merging backend code.

Implementation order for a less capable agent:

1. Add schema/model/repository for `bounty_submission_prs` first. It should
   reference `bounty_submissions`, store `repository`, `pull_request_number`,
   `pull_request_url`, `head_ref`, `base_ref`, `status`, `opened_by_agent_id`,
   `merged_by_login`, `merged_at`, and timestamps. Add a unique constraint on
   `(repository, pull_request_number)` and one active PR per submission.
2. Add settings for GitHub App id, installation id, private key, webhook
   secret, bot login, and API base URL in `api/config.py`.
3. Add `github_app_auth.py` for JWT generation using `cryptography`; keep it
   dependency-compatible with 15.1. Add focused tests for issued-at skew,
   expiry, and PEM parse errors.
4. Add `github_app_client.py` with stdlib HTTP calls: create installation
   token, create pull request, get pull request, comment on pull request if
   needed. Every method accepts timeout and maps GitHub errors to stable
   domain exceptions.
5. Add `OpenSubmissionPrService`: require bounty submission owner, active
   source link, and GitHub App config; create PR from requested head/base or
   return existing active PR idempotently.
6. Add `RegisterSubmissionPrService`: lets a contributor attach an already
   opened PR. Verify repository matches the course source link. Do not accept
   arbitrary repo URLs.
7. Add GitHub webhook controller: verify `X-Hub-Signature-256`; ignore
   unsupported event types; for closed PR with `merged=true`, call merge
   policy service.
8. Merge policy: load PR row, bounty submission, bounty, course source link,
   course owner's 15.1 GitHub identity; accept only if `merged_by.login`
   equals the owner's linked `github_login`. Random maintainers, bot merges,
   and platform bounties from 15.8 must not auto-accept.
9. Acceptance side effect should call the existing
   `AcceptBountySubmissionService` or the narrowest existing internal method
   so payout/status/event behavior remains identical to manual acceptance.
10. Add CLI commands in the existing bounties module. Commands must support
    `--json`, use generated SDK methods, and preserve current bounty command
    behavior.

Minimum tests:

- Model/repository tests for unique PR mapping and status transitions.
- GitHub App auth/client tests with monkeypatched HTTP; no network.
- Service tests for open idempotency, register validation, unconfigured 503,
  source-link missing, and unauthorized submitter.
- Webhook tests for signature success/failure, ignored events, merged by owner
  acceptance, merged by non-owner rejection, duplicate webhook idempotency.
- CLI tests for parser, fake SDK calls, JSON envelopes, and stable error
  mapping.

## Cross-cutting improvement contract

This phase is governed by [`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md). A community improvement proposal is **unfunded by default** and may accept a free GitHub PR/submission, retain contributor attribution and evidence, and merge upstream or become a maintained derivative with lineage. Funding is an explicit prospective conversion: only a confirmed funded bounty creates escrow, payout, or `sh.logion.bounty.accepted.v1`; an unpaid acceptance uses `sh.logion.improvement.accepted.v1` and must write no ledger/payable row. Publication review remains independent in both lanes.
