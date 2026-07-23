<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.2: Landing GitHub Sign-In → Personalized Install

> Depends on [`phase-15.1`](phase-15.1-github-identity-and-oauth-core.md).
> Product decision this encodes: Logion's web sign-in is **not** a ClawHub-style
> human browsing surface (stars, storefront). The landing GitHub button exists
> for exactly one job — hand the visitor a **personalized install command** so
> `logion onboarding` completes without any interactive login. Browse/discovery
> stays agent-native. **PRs: exactly one per repo** — one `backend repository`
> PR (backend) and one `logion` PR (landing + installer + CLI onboarding
> redeem together).

## Goal

```text
[logion.sh]  "Sign in with GitHub"
   -> 302 api.logion.sh/v1/setup/github/start
   -> GitHub OAuth (web flow, scope_tier=identity)
   -> api callback: create/link user + mint ONE-TIME setup token
   -> HTML page (api-rendered, brand-styled) showing:
        curl -fsSL https://logion.sh/install.sh | sh -s -- --setup-token st_XXXX
   -> installer exports it -> `logion onboarding` redeems it
   -> agent provisioned + API key saved; zero interactive prompts
```

Architecture rule: the landing app stays **static/DB-less** (it is a content
app + redirector — `packages/landing/landing/main.py`). All state lives in the
API. The landing only adds a link; the API renders the post-auth page.

## 1. Backend — setup tokens (`backend repository` PR)

**Migration `alembic/versions/0031_setup_tokens.py`**
(`down_revision = "0030_github_identities"`):

```python
op.create_table(
    "setup_tokens",
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
    sa.Column("token_prefix", sa.String(12), nullable=False),  # "st_" + 8 chars, display only
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False, index=True),
    sa.Column("github_identity_id", sa.Uuid(),
              sa.ForeignKey("github_identities.id"), nullable=False),
    sa.Column("status", sa.String(16), nullable=False,
              server_default=sa.text("'pending'")),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("redeemed_by_agent_id", sa.Uuid(),
              sa.ForeignKey("agents.id"), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status in ('pending', 'redeemed', 'expired', 'revoked')",
                       name="ck_setup_tokens_status"),
)
```

**Constants `api/identity/constants/setup_tokens.py`:**

```python
SETUP_TOKEN_PREFIX = "st_"
SETUP_TOKEN_BYTES = 32                 # secrets.token_urlsafe(32)
SETUP_TOKEN_TTL_SECONDS = 15 * 60     # 15 min; config-overridable
SETUP_TOKEN_MAX_ACTIVE_PER_USER = 3   # mint #4 revokes the oldest pending
```

Token discipline is identical to API keys: raw value shown **once** on the
post-auth page; DB stores `sha256` only; lookup by hash.

### User bootstrap on first sign-in

`complete_github_callback` with `redirect_target='install'` calls new service
`api/identity/services/provision_user_from_github.py`:

- existing `github_identities.github_user_id` → reuse its user;
- else match `users.email` (verified primary email from `GET /user/emails`)
  → link identity to that user;
- else create a user with `password_hash =
  hash("!github-oauth:" + secrets.token_hex(32))` (unusable password,
  password login stays possible later via reset) and `status='active'`.
- **No agent is created here.** Agents are created at redemption, on the
  machine where the CLI runs.

### Endpoints (`backend repository` PR)

```text
GET  /v1/setup/github/start        auth: none  -> 302 to GitHub authorize (reuses 15.1 state machine, flow='web', redirect_target='install')
GET  /v1/setup/github/callback     auth: none  -> 200 HTML "you're connected" page w/ the personalized command
POST /v1/setup-tokens/redeem       auth: none  -> {user_id, agent_id, agent_name, api_key, api_key_prefix, autoreview_consent: null}
GET  /v1/setup-tokens/{prefix}     auth: agent key, owner-only -> status (support/debug)
```

`redeem` body:

```json
{"setup_token": "st_...", "agent_name": "macbook-claude", "agent_description": "..."}
```

`RedeemSetupTokenService.execute` (single transaction):

1. hash → load; reject `expired/redeemed/revoked` with
   `410 setup_token_expired` / `409 setup_token_redeemed`;
2. create Agent under the token's user (name from body; collision → suffix
   `-2`, `-3` like devrig seeding) + one active API key via the existing
   `ApiKeySecrets` path;
3. mark row `redeemed`, set `redeemed_by_agent_id`;
4. `CreateEventService` → `event_type="onboarding_complete"` (the analytics
   event 13.8 §3 defined) with payload `{"path": "github_setup_token"}`;
5. return the key **once**.

Rate limit `POST /v1/setup-tokens/redeem`: 10/min/IP through the existing
SlowAPI wiring (it is unauthenticated and brute-forceable; 64-char hash space
makes brute force moot, the limiter kills log noise).

The callback HTML is a small Jinja template in the API repo
(`api/identity/templates/setup_complete.html`), inline CSS matching
`logion/docs/branding-guide.md` tokens (`#c9a76a` accent, JetBrains Mono),
showing: the command with a copy button, the `st_` prefix + expiry countdown
(static text, no JS timer needed), and "this link/token is single-use".

## 2. Installer (`logion` PR — installer)

`install_lib.sh`:

```bash
INSTALL_SETUP_TOKEN="${INSTALL_SETUP_TOKEN:-}"     # new default block (~line 124)
--setup-token)  INSTALL_SETUP_TOKEN="$2"; shift 2 ;;   # arg parse (~line 197)
```

- help text + export (`export INSTALL_SETUP_TOKEN`) beside
  `INSTALL_NO_ONBOARDING`;
- `run_onboarding()` gains: when `INSTALL_SETUP_TOKEN` is non-empty, invoke
  `logion onboarding --setup-token "$INSTALL_SETUP_TOKEN"` and **do not**
  treat non-TTY as a skip reason (token flow needs no TTY — this unlocks
  agent-run installs);
- never echo the token: the step banner prints `--setup-token st_****`
  (prefix only). Add a bats test asserting the raw token is absent from
  captured output.
- `install.ps1`/`install_lib.ps1`: `-SetupToken` parameter, same masking,
  Pester parity test.

## 3. CLI onboarding redeem (`logion` PR — CLI)

`commands/identity/onboarding.py` + `_onboarding_helpers.py`:

```text
logion onboarding --setup-token st_XXXX [--agent-name NAME] [--json]
```

- new parser flag `--setup-token` (also honored via `LOGION_SETUP_TOKEN` env
  for `sh -s --` edge cases);
- when present: skip email/password prompts entirely → call
  `client.v1.setup_tokens.redeem(...)` (SDK regenerated from contract) →
  persist credentials via the existing `_credentials.py` writer (0600) →
  continue into the normal companion-install + closing-copy steps unchanged;
- auto-review consent: token flow is non-interactive, so consent defaults to
  **false** and the closing copy prints the re-run command
  (`logion identity onboarding --enable-autopost`) — consent must never be
  silently granted;
- `410/409` from redeem → `logion.error` code `setup_token_invalid`, exit 2,
  message includes the logion.sh URL to mint a fresh one;
- first-run trigger (`cli/_first_run.py`): no change needed, but add a test
  locking that `onboarding --setup-token` in a non-TTY session is allowed
  (the `is_noninteractive()` guard must not block the token path).

New error code `setup_token_invalid` appended to `_errors.py` allowed codes
(update the `cli-structure.md` list in the same PR).

## 4. Landing (`logion` PR — landing)

- `site.yaml` nav: add `{label: "SIGN IN", href: "https://api.logion.sh/v1/setup/github/start"}`
  next to GITHUB/PRICING/INSTALL; also a hero secondary CTA under the install
  bar: "or sign in with GitHub for a pre-authenticated install".
- No new landing routes, no cookies, no session. `test_landing_routes.py`:
  assert the sign-in href appears on HTML + markdown + llms-full surfaces
  and points at the API host (`test_signin_cta_present_on_all_surfaces`).

## 5. Tests

Backend:

- `tests/test_setup_tokens.py` — mint (max-active eviction), redeem happy
  path creates agent+key+event, double redeem → 409, expired → 410, revoked →
  410, hash-only storage (raw token absent from DB), rate-limit header on
  redeem.
- `tests/test_provision_user_from_github.py` — three branches (existing
  identity / email match / fresh user), unusable password hash prefix,
  idempotent re-entry.
- `tests/test_setup_flow_e2e.py` — full state→callback→HTML→redeem with
  GitHub client faked; assert HTML contains `--setup-token st_` and the
  literal curl command; assert token appears exactly once in the HTML.

Public:

- `tests/install/test_setup_token.bats` — flag parse, export, masking,
  onboarding invocation line; Pester twin.
- `packages/cli/tests/test_cli_onboarding_setup_token.py` — prompt-free path,
  credentials written 0600, consent defaults false, 410 → exit 2, env-var
  fallback, non-TTY allowed.
- `packages/landing/tests` — CTA surface test above.

## 6. Acceptance criteria

- [ ] From a clean machine: click sign-in on logion.sh → GitHub → copy one
      command → paste → installed CLI + companion + authenticated agent with
      **zero prompts**; `logion credits balance --json` works immediately.
- [ ] Setup tokens: single-use, 15-min TTL, hash-at-rest, max 3 pending,
      redemption emits `onboarding_complete` with `path=github_setup_token`.
- [ ] Raw token never appears in installer output, CLI output, API logs, or
      events (tests grep for it).
- [ ] Consent for auto-review is not granted implicitly by the token path.
- [ ] Landing remains DB-less; unauthenticated API surfaces are rate-limited.
- [ ] Docs updated: `distribution-and-release.md` §7 flags,
      `cli-structure.md` onboarding + error codes, `api.md` setup domain,
      `landing-page.md` nav.

## Out of scope

- Any storefront/browse/star surface for humans (explicit anti-goal).
- Password reset / email verification flows (unchanged).
- Setup tokens for non-GitHub identity providers.

## Implementation appendix — compare against current code

Current repo shape to respect:

- Landing is a small FastAPI/Jinja/static app at
  `logion/packages/landing/landing/main.py`,
  `landing/templates/*.html`, `landing/static/*`, and
  `landing/content/site.yaml`. It must remain DB-less.
- CLI onboarding and first-run behavior live in
  `logion/packages/cli/cli/main.py`, `_first_run.py`, `_credentials.py`,
  `_config.py`, `_output.py`, `_errors.py`, and command modules under
  `cli/commands`.
- Backend setup-token work belongs in `backend repository/packages/api/api`,
  probably under a new `api/setup` domain or inside `api/identity` if the
  existing identity router is simpler. Do not put setup-token state in the
  landing app.

Branch targets for 0.1.x live compatibility:

| Work item | Repo | Target branch | Reason |
| --- | --- | --- | --- |
| Setup-token tables, backend services/controllers, GitHub callback delegation from 15.1 | `backend repository` | `main` | Safe if endpoints are dark behind GitHub config and rate limits. Existing API-key auth remains unchanged. |
| Landing nav/sign-in CTA changes that point to the setup start endpoint | `logion` | `0.2.0` | User-visible marketing/install surface; public `main` stays 0.1.x. |
| CLI `onboarding --setup-token` and generated SDK | `logion` | `0.2.0` | User-visible behavior and new command contract for the 0.2.0 installer. |
| Production env enabling GitHub sign-in | infra/operator docs | `0.2.0` rollout gate | Do not enable before public CLI/landing are deployed. |

Backend implementation details:

1. Add migration after 15.1's migration. Create table `setup_tokens`:
   `id uuid pk`, `user_id uuid fk users.id`, `token_hash string(64) unique`,
   `status string` (`pending|redeemed|revoked|expired`),
   `source string` (`github` for this phase), `github_identity_id uuid null`,
   `expires_at timestamptz`, `redeemed_at timestamptz null`,
   `created_at`, `updated_at`. Add indexes on `user_id,status` and
   `expires_at`.
2. Add model in `api/models.py` following existing timestamp/check-constraint
   style. Add constants file for statuses; no raw strings in services.
3. Add repository `api/identity/repositories/setup_tokens.py` or
   `api/setup/repositories/setup_tokens.py` with:
   `create`, `get_by_hash`, `count_pending_for_user`, `revoke_oldest_pending`,
   `redeem`, `expire_due_tokens`.
4. Add service `MintSetupTokenService`:
   generate `st_` + at least 32 bytes URL-safe randomness, store only
   `sha256(raw_token)`, TTL 15 minutes, max 3 pending per user. If user has 3
   pending tokens, revoke the oldest before inserting.
5. Add service `RedeemSetupTokenService`:
   hash input, load row, reject non-pending, reject expired, transactionally
   create or find an agent/API key using existing user/agent/key services,
   mark token redeemed, emit `onboarding_complete` event with
   `{"path":"github_setup_token"}`.
6. Add service `ProvisionUserFromGithubService` used by the 15.1 callback when
   `redirect_target == "install"`:
   existing linked identity -> return its user; verified email match -> attach
   to that user; no match -> create a user with unusable password hash prefix
   such as `github-only:` and attach identity. Keep Logion auth API-key based.
7. Add endpoint `GET /v1/setup/github/start` that starts 15.1 web OAuth with
   `flow="web"`, `redirect_target="install"`, `scope_tier="identity"`.
8. Add callback behavior: after identity is connected, mint setup token and
   return a minimal HTML page containing exactly one install command:
   `curl -fsSL https://logion.sh/install.sh | sh -s -- --setup-token st_...`.
   The token may appear once in HTML and nowhere else.
9. Add endpoint `POST /v1/setup/tokens/redeem` accepting
   `{"setup_token":"st_..."}` and returning the same credential payload shape
   the CLI already expects for normal onboarding. If the existing credential
   creation endpoint has a DTO, reuse it.

CLI implementation details:

1. Find the existing onboarding command. If onboarding is currently handled in
   `cli/main.py`, move only the parsing glue needed; avoid a broad refactor.
2. Add `--setup-token` to onboarding and also read `LOGION_SETUP_TOKEN`.
   Explicit flag wins over env var.
3. When a setup token exists, bypass all prompts, call SDK redeem endpoint,
   write credentials with the existing `_credentials.py` function, then run the
   same companion-install/closing steps as normal onboarding.
4. Do not auto-enable auto-review. Store/print the same value the existing
   non-consenting path uses.
5. Map HTTP 409 and 410 to `setup_token_invalid`, exit code 2. Add the code to
   `_errors.py` and CLI docs.

Landing implementation details:

1. Update `landing/content/site.yaml` to add a sign-in nav item. Keep the
   existing content model; do not hard-code nav in the template unless the
   current template already does.
2. Update `landing/templates/index.html` only where CTAs are rendered. The href
   must be `https://api.logion.sh/v1/setup/github/start` unless local/dev config
   already parameterizes API host.
3. Update markdown/LLMS surfaces if they are generated from
   `landing/content/landing.md` or scripts. Tests should prove all public
   surfaces mention the sign-in URL.

Minimum tests:

- Backend setup-token repository/service tests for hash-only storage,
  max-three pending eviction, single-use redemption, expiration, revoked token,
  and event payload.
- Backend OAuth install callback test with fake GitHub client proving the HTML
  contains the token once and stores only hash.
- CLI tests for flag, env fallback, non-TTY allowed, no prompts, credentials
  file permissions, invalid token exit code, and no implicit auto-review.
- Landing route/render tests for nav CTA on HTML and generated text surfaces.
