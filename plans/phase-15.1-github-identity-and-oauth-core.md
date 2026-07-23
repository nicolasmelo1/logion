<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.1: GitHub Identity & OAuth Core

> Implements the OAuth slice of
> [`phase-15-native-resource-loop-and-first-ai-catalog-ard-node.md`](phase-15-native-resource-loop-and-first-ai-catalog-ard-node.md).
> Everything downstream (15.2 personalized install, 15.3 repo publishing,
> 15.5 bounty PR bot, 15.9 claim verification) consumes the
> `github_identities` record this phase creates. **PRs: exactly one per
> repo** — one `backend repository` PR (backend) and one `logion` PR (CLI +
> synced contract). Never more than one PR per repo in this phase.

## Goal

A user can link exactly one GitHub identity to their Logion user, via either
the **web flow** (browser redirect — consumed by 15.2's landing button) or the
**device flow** (CLI/agent-first — no browser on the same machine required).
The stored token is encrypted at rest, scoped minimally, refreshable, and
revocable. Nothing else: no repo reads (15.3), no bot (15.5), no claim logic
(15.9).

## Non-negotiable rules

- GitHub login **never creates marketplace trust**: it is identity linkage +
  future provenance verification, nothing more.
- Scope floor: `read:user user:email`. The `repo` scope is requested **only**
  when the creator opts into private-repo publishing (15.3 passes
  `scope_tier="repo"`); never by default.
- Tokens are never logged, never returned by any API response, and never enter
  the recall index (the CLI already masks secret-like fields —
  `_local_state.py` `mask_secrets`).

## 1. Backend — data model (`backend repository` PR)

**Migration `alembic/versions/0030_github_identities.py`**
(`down_revision = "0029_entitlement_acquisition_count_index"`):

```python
def upgrade() -> None:
    op.create_table(
        "github_identities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("github_user_id", sa.BigInteger(),
                  nullable=False, unique=True),
        sa.Column("github_login", sa.String(255), nullable=False),
        sa.Column("access_token_ciphertext", sa.LargeBinary(),
                  nullable=False),
        sa.Column("refresh_token_ciphertext", sa.LargeBinary(),
                  nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("scope_tier", sa.String(16), nullable=False,
                  server_default=sa.text("'identity'")),
        sa.Column("status", sa.String(16), nullable=False,
                  server_default=sa.text("'active'")),
        sa.Column("connected_at", sa.DateTime(timezone=True),
                  nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope_tier in ('identity', 'repo')",
            name="ck_github_identities_scope_tier"),
        sa.CheckConstraint(
            "status in ('active', 'revoked', 'expired')",
            name="ck_github_identities_status"),
    )
    op.create_index("ix_github_identities_github_login",
                    "github_identities", ["github_login"])

    op.create_table(
        "github_oauth_states",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("flow", sa.String(16), nullable=False),  # 'web'|'device'
        sa.Column("scope_tier", sa.String(16), nullable=False),
        sa.Column("redirect_target", sa.String(32), nullable=False,
                  server_default=sa.text("'none'")),  # 'none'|'install'
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
```

**`api/models.py`** — mirror both tables (`GithubIdentity`,
`GithubOauthState`), matching the CheckConstraint style used by `User`/
`Bounty`. `users` gains a `github_identity` relationship
(`uselist=False`, `back_populates="user"`).

Constraints encoded above, spelled out:

- one GitHub identity per user (`user_id` UNIQUE) and one Logion user per
  GitHub account (`github_user_id` UNIQUE) — re-linking a GitHub account that
  is attached to another user is a `409` (`github_identity_conflict`), never a
  silent move.
- `state_hash` = `sha256(state_token)`; the raw `state` never touches the DB
  (same discipline as API-key hashing).

## 2. Backend — token crypto (`backend repository` PR)

**New dependency (deliberate pinning exception):** `cryptography` (Fernet),
pinned narrow (`cryptography>=44.0.2,<44.1`). Record the rationale in the PR
description — supply-chain rule is "only widen/bump on CVE", adding a
maintained crypto primitive for reversible token storage qualifies as a
justified addition, stdlib has no AEAD.

**New file `api/identity/services/github_token_crypto.py`:**

```python
from cryptography.fernet import Fernet, InvalidToken

class GithubTokenCrypto:
    def __init__(self, key: str) -> None:      # settings.github_token_encryption_key
        self._fernet = Fernet(key.encode())

    def encrypt(self, token: str) -> bytes: ...
    def decrypt(self, ciphertext: bytes) -> str:  # raises GithubTokenCorruptError
```

**`api/config.py` additions** (same `Field(validation_alias=...)` pattern):

```python
github_oauth_client_id: str = Field(default="", validation_alias="LOGION_GITHUB_OAUTH_CLIENT_ID")
github_oauth_client_secret: str = Field(default="", validation_alias="LOGION_GITHUB_OAUTH_CLIENT_SECRET")
github_token_encryption_key: str = Field(default="", validation_alias="LOGION_GITHUB_TOKEN_ENCRYPTION_KEY")
github_oauth_state_ttl_seconds: int = Field(default=600, validation_alias="LOGION_GITHUB_OAUTH_STATE_TTL_SECONDS")
```

Add all four to `packages/infra/deploy/env.example.production` (empty =
GitHub integration disabled; endpoints answer `503 github_oauth_unconfigured`
— same sentinel discipline as the Stripe webhook secret).

## 3. Backend — GitHub HTTP client (`backend repository` PR)

**New file `api/identity/services/github_api_client.py`** — stdlib-only
(`urllib.request`, mirroring `api/observability/alerting.py`; no `httpx`):

```python
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_API_BASE = "https://api.github.com"
_GITHUB_USER_AGENT = "Logion API (+https://logion.sh)"
_TIMEOUT_S = 10

class GithubApiClient:
    def exchange_code(self, *, code: str) -> GithubTokenResponse: ...
    def create_device_code(self, *, scope: str) -> GithubDeviceCodeResponse: ...
    def poll_device_token(self, *, device_code: str) -> GithubTokenResponse: ...
    def get_authenticated_user(self, *, token: str) -> GithubUser:  # GET /user
    def refresh(self, *, refresh_token: str) -> GithubTokenResponse: ...
```

Every method: explicit timeout, JSON error envelope →
`GithubApiError(status, code)`. Unit tests monkeypatch `urllib.request.urlopen`
— **zero live network in tests** (same rule as `test_alerting.py`).

## 4. Backend — endpoints (`backend repository` PR)

New controller package `api/identity/controllers/github/` mounted under the
existing identity router:

```text
POST /v1/identity/github/authorize        auth: agent key   -> {authorize_url, state_expires_at}
GET  /v1/identity/github/callback         auth: none (state) -> 302 or minimal HTML (see 15.2)
POST /v1/identity/github/device           auth: agent key   -> {user_code, verification_uri, interval, device_state}
POST /v1/identity/github/device/poll      auth: agent key   -> 202 pending | 200 {github_login, scope_tier}
GET  /v1/identity/github                  auth: agent key   -> {github_login, scope_tier, status, connected_at}
DELETE /v1/identity/github                auth: agent key   -> 204 (revoke: status='revoked', ciphertexts nulled)
```

Services (one file each, matching `bounties/services/*` granularity):
`begin_github_authorization.py`, `complete_github_callback.py`,
`begin_github_device_flow.py`, `poll_github_device_flow.py`,
`get_github_identity.py`, `revoke_github_identity.py`.

`complete_github_callback` sequence (single transaction):

1. hash incoming `state`, load `github_oauth_states` row; reject when missing,
   expired, or `consumed_at IS NOT NULL` (`400 github_state_invalid`);
2. `exchange_code` → `get_authenticated_user`;
3. upsert `github_identities` under the two UNIQUE constraints (conflict →
   409, mapped by the global error handler);
4. set `consumed_at`, emit an `events` row via `CreateEventService`
   (`event_type="github_identity_connected"`, `target_type="user"`,
   payload `{"github_login": ..., "scope_tier": ...}` — **never** the token);
5. if `redirect_target == 'install'`, delegate to the 15.2 setup-token
   service, else 302 to `https://logion.sh/connected`.

Rate limit: reuse the SlowAPI signup limiter bucket for
`/identity/github/device` (5/min per key) — device polling is the abuse
surface.

## 5. CLI (`logion` PR)

New subcommands under the existing `identity` package
(`commands/identity/github.py` + parser wiring):

```bash
logion identity github connect [--scope-tier identity|repo] [--json]
logion identity github status  [--json]
logion identity github disconnect [--yes] [--json]
```

`connect` runs the **device flow**: calls `POST .../device`, prints

```text
Open https://github.com/login/device and enter code: ABCD-1234
```

then polls `POST .../device/poll` every `interval` seconds (max 900 s,
exit code 2 `confirmation_required` on timeout). Envelope kinds:
`logion.identity.github.connect|status|disconnect`. `--json` on all three
(the CLI contract test enforces `JSON_EXEMPT_COMMANDS == frozenset()` — do
not add exemptions).

SDK: regenerate from the updated OpenAPI contract
(`make export-openapi` in backend repository → `make sync-public-contract`);
`client.v1.identity.github_*` methods come from the generator.

## 6. Tests

Backend (`packages/api/tests/`):

- `test_github_identity_model.py` — UNIQUE constraint pair, scope/status
  CHECKs, ciphertext round-trip via `GithubTokenCrypto`.
- `test_github_oauth_web_flow.py` — authorize returns a GitHub URL embedding
  `client_id`, `state`, exact scopes; callback happy path creates identity +
  event; expired/replayed/consumed state → 400; conflicting github_user_id →
  409; unconfigured secrets → 503.
- `test_github_oauth_device_flow.py` — device begin/poll pending (202) /
  granted (200); poll after grant is idempotent.
- `test_github_token_crypto.py` — encrypt/decrypt, tampered ciphertext →
  `GithubTokenCorruptError`, wrong key → same error.
- `test_github_api_client.py` — urlopen monkeypatched: token exchange
  payloads, error envelope mapping, timeout parameter present.
- extend `tests/test_database_schema.py` snapshot for the two new tables.

CLI (`packages/cli/tests/`):

- `test_cli_identity_github.py` — parser registration, device-flow polling
  loop with a fake SDK (pending→granted), `disconnect` requires `--yes`,
  all three emit v1 envelopes, token never appears in any output (assert on
  captured stdout).

## 7. Acceptance criteria

- [ ] A user can link GitHub via device flow from the CLI and via web flow
      (callback), and `GET /v1/identity/github` reflects it.
- [ ] Tokens stored only as Fernet ciphertext; no response, log line, or
      event payload ever contains a token (greppable test asserts this).
- [ ] One-to-one linkage enforced both directions with 409 on conflict.
- [ ] Unconfigured GitHub secrets degrade to 503 `github_oauth_unconfigured`;
      nothing else breaks.
- [ ] `make ci-check` (api) green incl. new migration; contract re-exported;
      public CLI + SDK green; docs: new section in `maintainer documentation: api.md`
      (identity domain) and `cli-structure.md` (identity github subgroup).

## Out of scope

- Personalized install handoff (15.2), repo selection/reads (15.3), GitHub
  App/bot (15.5), ownership verification (15.9).
- GitHub as a login/password replacement — Logion auth remains API-key based.

## Implementation appendix — compare against current code

Current repo shape to respect:

- Private API lives in `backend repository/packages/api/api`. Domains already use
  the pattern `controllers/`, `services/`, `repositories/`, `constants/`,
  `exceptions.py`, and are wired through each domain's `controllers/router.py`
  and `api/main.py`.
- Existing auth/user primitives are in `api/identity/*`, `api/models.py`, and
  `api/database.py`; do not create a second auth stack.
- Public CLI lives in `logion/packages/cli/cli`, uses argparse, command modules
  under `cli/commands`, shared config/credentials helpers in `_config.py`,
  `_credentials.py`, `_output.py`, `_errors.py`, and first-run logic in
  `_first_run.py`.
- The public SDK is generated under `logion/packages/client/src/logion/v1`.
  Do not hand-edit generated client files except as part of the normal
  contract sync.

Branch targets for 0.1.x live compatibility:

| Work item | Repo | Target branch | Reason |
| --- | --- | --- | --- |
| Alembic migration `0030_github_identities.py`, `GithubIdentity`, `GithubOauthState`, repositories, services, controllers, settings | `backend repository` | `main` | Safe on live because all endpoints return `503 github_oauth_unconfigured` until GitHub env vars and encryption key are configured. Existing 0.1.x flows are untouched. |
| OpenAPI export and shared docs describing new backend endpoints | `backend repository` / workspace docs | `main` | Contract can expose dark endpoints; clients cannot use them successfully until configured. |
| Public CLI commands `logion identity github *`, generated SDK, installer docs that advertise GitHub link | `logion` | `0.2.0` | Public `main` is 0.1.x. Do not ship user-visible CLI commands before 0.2.0. |
| Operator setup of GitHub OAuth App client id/secret and Fernet key in production | `backend repository` infra/docs | gated for `0.2.0` rollout | Merging backend code to `main` must not activate the flow. Actual env injection is release work. |

Concrete backend file plan:

1. Add settings to `backend repository/packages/api/api/config.py` using the same
   Pydantic `Field` style already used for Stripe, database, CORS, and storage:
   `github_oauth_client_id`, `github_oauth_client_secret`,
   `github_oauth_redirect_uri`, `github_token_encryption_key`,
   `github_oauth_authorize_url`, `github_oauth_token_url`,
   `github_device_code_url`, `github_api_base_url`. Defaults for URLs should
   point to GitHub; secrets default to empty/`None`.
2. Add models at the bottom of `api/models.py`, near identity-related models
   if present. Use existing `uuid_column`, timestamp, relationship, and
   `CheckConstraint` idioms from `Course`, `Bounty`, and `User`. Add
   `User.github_identity = relationship(..., uselist=False)`.
3. Add migration after the current latest migration. Before writing the file,
   inspect `backend repository/packages/api/alembic/versions` and set
   `down_revision` to the actual latest revision, not the example if the repo
   advanced.
4. Add `api/identity/constants/github_identity_status.py` and
   `github_scope_tier.py` with string constants. Do not scatter raw strings.
5. Add `api/identity/repositories/github_identities.py` with methods:
   `get_by_user_id`, `get_by_github_user_id`, `get_active_by_user_id`,
   `upsert_for_user`, `revoke_for_user`, `mark_expired`.
6. Add `api/identity/repositories/github_oauth_states.py` with
   `create_state`, `get_by_hash`, `consume`, `delete_expired`.
7. Add `api/identity/services/github_token_crypto.py`, `github_api_client.py`,
   `github_oauth_service.py`, `github_device_flow_service.py`, and
   `github_identity_service.py`. Keep HTTP calls stdlib `urllib.request` unless
   the API package already has a shared HTTP client. Every external call gets a
   short timeout.
8. Add controllers:
   `api/identity/controllers/github_oauth.py` for web start/callback,
   `api/identity/controllers/github_device.py` for device begin/poll, and
   `api/identity/controllers/github_identity.py` for status/disconnect. Wire
   them through the existing identity router. If there is no identity router,
   create `api/identity/controllers/router.py` following
   `api/bounties/controllers/router.py`, then include it in `api/main.py`.
9. Reuse current user/API-key dependency helpers for authenticated endpoints.
   The web start endpoint may be anonymous only when it is explicitly part of
   15.2 setup-token flow; otherwise require the normal user context.
10. Add event emission through the existing analytics/events service used by
    marketplace actions. If the current event API differs, wrap it in a tiny
    helper inside the service rather than leaking event details into the
    controller.

Controller response shapes to implement exactly:

```json
GET /v1/identity/github
{
  "connected": true,
  "github_login": "octocat",
  "scope_tier": "identity",
  "status": "active",
  "connected_at": "2026-07-03T12:00:00Z"
}
```

```json
POST /v1/identity/github/device
{
  "device_code": "server-only-id",
  "user_code": "ABCD-1234",
  "verification_uri": "https://github.com/login/device",
  "expires_in": 900,
  "interval": 5
}
```

```json
POST /v1/identity/github/device/poll
// 202 while pending
{"status": "pending", "interval": 5}
// 200 when granted
{"status": "connected", "github_login": "octocat", "scope_tier": "identity"}
```

Error mapping:

- missing GitHub config or token encryption key -> HTTP 503,
  `detail.code = "github_oauth_unconfigured"`;
- expired/replayed OAuth state -> HTTP 400, `github_oauth_state_invalid`;
- GitHub account already linked to another user -> HTTP 409,
  `github_identity_conflict`;
- revoked/expired identity on status -> HTTP 200 with `connected=false`;
- token decrypt failure -> mark identity `expired`, return HTTP 409,
  `github_token_invalid`.

Concrete CLI file plan:

1. If `cli/commands/identity.py` does not exist, create it and follow the
   command-registration pattern in `cli/commands/bounties.py` and
   `cli/commands/admin.py`.
2. Register `identity github connect|status|disconnect` from
   `cli/main.py` or the existing parser registry in `_parser.py`.
3. Use `_config.py` to resolve API base URL, `_credentials.py` for the current
   API key, `_output.py` for JSON/text envelopes, `_errors.py` for stable exit
   codes. Do not print raw SDK exceptions.
4. Poll device flow with `time.sleep(interval)`, cap total wall time at
   `expires_in`, and make tests monkeypatch the sleep function.
5. `disconnect` must require `--yes` in non-JSON text mode just like other
   destructive commands; return exit code 2 with `confirmation_required` when
   missing.

Minimum tests a GLM implementer should write before declaring done:

- API model/repository tests for uniqueness, status transitions, state hashing,
  and consumed-state replay.
- Controller tests with monkeypatched GitHub HTTP responses; never hit the
  network.
- Schema snapshot/OpenAPI test updated so generated SDK includes endpoints.
- CLI parser tests proving the commands appear in `--help`.
- CLI behavior tests with fake SDK: pending->connected, timeout,
  disconnect without `--yes`, JSON envelope names, and stdout/stderr do not
  contain `access_token`, `refresh_token`, or the fake token values.

## Cross-cutting improvement contract

This phase is governed by [`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md). A community improvement proposal is **unfunded by default** and may accept a free GitHub PR/submission, retain contributor attribution and evidence, and merge upstream or become a maintained derivative with lineage. Funding is an explicit prospective conversion: only a confirmed funded bounty creates escrow, payout, or `sh.logion.bounty.accepted.v1`; an unpaid acceptance uses `sh.logion.improvement.accepted.v1` and must write no ledger/payable row. Publication review remains independent in both lanes.
