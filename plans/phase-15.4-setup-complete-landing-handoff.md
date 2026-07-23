<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.4: Setup-Complete Handoff — OAuth Callback Redirects to the Landing

> Depends on [`phase-15.2`](phase-15.2-landing-github-signin-personalized-install.md)
> (shipped: setup tokens, `GET /v1/setup/github/start`, callback, redeem).
> Product decision this encodes: the post-OAuth "here is your personalized
> install command" moment must feel like **logion.sh**, not like a bare API
> page. The API stops rendering end-user HTML on the success path and instead
> redirects to the landing, which renders the normal hero with only the CTA
> context swapped. The raw setup token must never appear in any URL, any
> server log, or the landing server's memory — it travels api → browser via a
> **single-use handoff code carried in a URL fragment**, exactly the way an
> OAuth `code` works. **PRs: exactly one per repo** — one `backend repository` PR
> (handoff table + claim endpoint + callback redirect) and one `logion` PR
> (landing route + template variant + claim JS).

## Goal

```text
[logion.sh]  "Sign in" nav / "pre-authenticated install" CTA
   -> 302 api.logion.sh/v1/setup/github/start          (unchanged, 15.2)
   -> GitHub OAuth (web flow, scope_tier=identity)      (unchanged, 15.2)
   -> api callback: provision/link user + consume state (unchanged, 15.2)
        THEN (new): mint ONE-TIME handoff (sh_..., TTL 120s)
        -> 303 See Other  https://www.logion.sh/setup/complete#hid=sh_XXXX
   -> landing renders the SAME hero page in setup_mode:
        - primary CTA block = "GitHub linked" + masked install command
        - "Sign in" nav item = "connected" status
        - "or sign in with GitHub..." secondary CTA hidden
   -> setup-complete.js reads #hid, strips it via history.replaceState,
      POSTs api.logion.sh/v1/setup/handoff/claim (CORS-scoped)
        -> claim consumes handoff, MINTS the setup token NOW, returns it once
   -> JS injects: curl -fsSL https://logion.sh/install.sh | sh -s -- --setup-token st_XXXX
   -> installer/onboarding redeem path unchanged (15.2)
```

Two architecture rules:

1. The landing stays **static/DB-less** (`packages/landing/landing/main.py`
   is a content app). The setup token never touches the landing server: the
   claim call goes browser → API directly. The landing only ships a template
   variant and ~40 lines of JS.
2. The setup token is minted **at claim time, not at callback time**. The
   handoff row stores only `user_id`/`github_identity_id` — never a raw or
   encrypted token — so the hash-at-rest discipline from 15.2 is preserved
   and the 15-minute token TTL starts when the user can actually see the
   command.

Why a fragment (`#hid=`), not a query param: fragments are never sent to any
server, so the handoff id cannot land in Vercel/API access logs or `Referer`
headers. Why single-use + 120s TTL on top: whatever still leaks (browser
history, screenshots) is worthless after the first claim.

## 1. Backend — setup handoffs (`backend repository` PR)

**Migration `alembic/versions/00XX_setup_handoffs.py`.** Run
`uv run alembic heads` in `packages/api` first: if it prints more than one
head, create a merge revision first (precedent:
`0034_merge_bounty_and_setup_token_heads.py`), then set `down_revision` to
the single head.

```python
op.create_table(
    "setup_handoffs",
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("handoff_hash", sa.String(64), nullable=False, unique=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"),
              nullable=False, index=True),
    sa.Column("github_identity_id", sa.Uuid(),
              sa.ForeignKey("github_identities.id"), nullable=False),
    sa.Column("github_login", sa.String(255), nullable=False),  # display only
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)
```

**Constants `api/setup/constants.py`** (create it; setup domain currently has
none — token constants live in `api/identity/constants/setup_tokens.py`):

```python
SETUP_HANDOFF_PREFIX = "sh_"
SETUP_HANDOFF_BYTES = 32              # secrets.token_urlsafe(32)
SETUP_HANDOFF_TTL_SECONDS = 120       # config-overridable
```

Handoff discipline is identical to OAuth states
(`api/identity/repositories/github_oauth_states.py`): DB stores
`hashlib.sha256(raw).hexdigest()` only; lookup by hash with `for_update=True`;
consume sets `consumed_at`.

**Repository `api/setup/repositories/setup_handoffs.py`:** `create`,
`get_by_hash(hash, for_update=True)`, `consume(row)`. Model in `api/models.py`
following the existing timestamp style.

**Settings (`api/config.py`):**

```python
setup_complete_redirect_url: str = ""   # prod: https://www.logion.sh/setup/complete
setup_cors_allow_origins: str = ""      # prod: https://www.logion.sh,https://logion.sh
```

Both empty by default → **dark launch**: with no redirect URL configured the
callback behaves exactly as today (API-rendered `setup_complete.html`). That
template and `_render_setup_complete_page` are kept as the config-off
fallback; do not delete them.

**CORS (`api/main.py`).** The app currently has no `CORSMiddleware` (only
`SlowAPIMiddleware`, `api/main.py:141`). Add, gated on the setting:

```python
if settings.setup_cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.setup_cors_allow_origins.split(",") if o.strip()],
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["content-type"],
        allow_credentials=False,
        max_age=600,
    )
```

`allow_credentials=False` is load-bearing: the claim endpoint is bearer-by-body,
no cookies exist, and this keeps the CORS grant non-ambient.

### Callback change (`api/setup/controllers/setup_github_callback.py`)

Only the tail changes (today: mint + render, lines ~249–270). After
`state_repo.consume(state_row)`:

```python
if settings.setup_complete_redirect_url:
    handoff = MintSetupHandoffService(db).execute(
        user_id=user_id,
        github_identity_id=github_identity_id,
        github_login=github_user.login,
    )
    db.commit()
    return RedirectResponse(
        url=f"{settings.setup_complete_redirect_url}#hid={handoff.raw_handoff}",
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Cache-Control": "no-store, no-cache, max-age=0"},
    )
# legacy path, unchanged:
token_result = MintSetupTokenService(db, settings).execute(...)
```

Notes for the implementer:

- `db.commit()` must still run on the redirect path — it persists the
  provisioned user/identity, the consumed state, AND the handoff row.
- `#hid=` is a fragment: FastAPI/Starlette pass it through verbatim in the
  `Location` header; nothing special needed.
- Error branches (`error=`, invalid state, GitHub API failures) are
  **unchanged** in this phase — they keep returning the existing API error
  page/JSON. Redirecting errors to a styled landing state is out of scope.
- `MintSetupHandoffService` (new, `api/setup/services/mint_setup_handoff.py`):
  generate `sh_` + `token_urlsafe(32)`, store sha256 hash + TTL, return
  dataclass `{raw_handoff, expires_at}`. No max-active policy needed: one
  handoff per completed OAuth roundtrip, 120s TTL.

### New endpoint — claim

```text
POST /v1/setup/handoff/claim    auth: none, CORS-scoped, rate-limited
body:     {"handoff_id": "sh_..."}
200:      {"setup_token": "st_...", "token_prefix": "st_XXXXXXXX",
           "expires_at": "...", "github_login": "octocat",
           "install_command": "curl -fsSL https://logion.sh/install.sh | sh -s -- --setup-token st_..."}
410:      {"code": "setup_handoff_invalid"}   # not found | expired | consumed — one opaque code, no oracle
422:      body validation (FastAPI default)
```

Controller `api/setup/controllers/claim_setup_handoff.py`, wired in
`api/setup/controllers/router.py`. Copy the SlowAPI pattern from
`redeem_setup_token.py` (`api/identity/rate_limits.py` limiter,
`get_remote_address`): **20/min/IP**. Response headers:
`Cache-Control: no-store, no-cache, max-age=0`.

`ClaimSetupHandoffService.execute(raw_handoff)` — single transaction:

1. hash → `get_by_hash(for_update=True)`; missing, `expires_at < now`, or
   `consumed_at is not None` → raise domain error mapped to
   `410 setup_handoff_invalid` (same code for all three; do not reveal which);
2. `consume(row)`;
3. `MintSetupTokenService(db, settings).execute(user_id=row.user_id,
   github_identity_id=row.github_identity_id)` — reuse as-is; its
   max-3-pending eviction from 15.2 still applies;
4. commit; return the raw token **once** plus `github_login` off the row.

`FOR UPDATE` + the consumed check make concurrent double-claims resolve to
exactly one winner; the loser gets 410.

### Security invariants (test-enforced)

- Raw handoff never persisted (hash only); raw setup token never persisted
  (unchanged from 15.2) and **never present in any URL** — the redirect
  `Location` contains only `#hid=sh_...`.
- Handoff single-use, 120s TTL; claiming does not extend the setup token TTL.
- Claim response and callback redirect both `no-store`.
- CORS allows only the configured landing origins, only `POST`/`OPTIONS`,
  no credentials.

## 2. Landing (`logion` PR)

### Copy — `landing/content/site.yaml`

New top-level block (all user-facing strings live here, none in JS):

```yaml
setup_complete:
  nav_status: connected            # replaces "Sign in" in the header nav
  heading: GitHub linked
  cta_label: Your personalized install
  claiming: linking your GitHub account…
  masked_command: "curl -fsSL https://logion.sh/install.sh | sh -s -- --setup-token ••••••••"
  warning: >-
    Keep this token private. It grants access to your account and this page
    will not be shown again. If you lose it, sign in again at logion.sh to
    mint a new one.
  expired: >-
    This link was already used or has expired. Sign in with GitHub again to
    get a fresh install command.
  retry_label: sign in with GitHub again
  retry_href: https://api.logion.sh/v1/setup/github/start
  noscript: >-
    JavaScript is required to receive your one-time install token. Enable it
    and reload, or sign in again from logion.sh.
```

Mark the hero secondary CTA that must disappear (`hero.cta.secondary`, the
"or sign in with GitHub for a pre-authenticated install" item, site.yaml
~line 54) with `setup_hide: true`, and the nav `Sign in` item
(`links.primary`, ~line 456) with `setup_swap: nav_status`.

### Route — `landing/main.py`

```python
@app.get("/setup/complete", response_class=HTMLResponse, include_in_schema=False)
def setup_complete(request: Request) -> Response:
    resp = templates.TemplateResponse(request, "index.html", _ctx(setup_mode=True))
    resp.headers["Cache-Control"] = "no-store, no-cache, max-age=0"
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp
```

- `_ctx` (line ~298) gains `setup_mode: bool = False` default and
  `api_base = os.environ.get("LOGION_API_BASE_URL", "https://api.logion.sh")`
  so local dev can point at a local API.
- Do **not** add `/setup/complete` to `sitemap_xml()` (line ~128). Add
  `Disallow: /setup/` to `robots_txt()` (line ~112).
- Every other route keeps `setup_mode=False`; the rendered landing pages must
  be byte-identical to today when the flag is off (test-locked).

### Template variant — `index.html` + `base.html`

All conditionals key off `setup_mode`; when false, zero output change.

- `templates/index.html`, hero CTA block (lines ~88–115):
  - `{% if setup_mode %}`: render the setup variant of the primary CTA —
    heading `setup_complete.heading` (with the check style reused from
    existing status markup), label `setup_complete.cta_label`, and a
    `<code id="setup-command" class="cta-cmd">{{ setup_complete.masked_command }}</code>`
    inside the same `copy-cta` structure so the existing
    `data-copy-command` handler in `static/app.js` keeps working. The button
    starts `disabled` with `data-copy-command=""` (nothing real to copy until
    claimed). Below it, a status region
    `<p id="setup-status" aria-live="polite">{{ setup_complete.claiming }}</p>`
    and a hidden warning block `<div id="setup-warning" hidden>{{ setup_complete.warning }}</div>`.
  - secondary loop (line ~110):
    `{% if not (setup_mode and link.get("setup_hide")) %}` around each item.
  - add `{% if setup_mode %}<script src="/static/setup-complete.js" defer
    data-api-base="{{ api_base }}"></script>{% endif %}` and a
    `<noscript>{{ setup_complete.noscript }}</noscript>` inside the setup CTA
    block.
- `templates/base.html`, primary nav (lines ~142–146): items with
  `setup_swap` render, when `setup_mode`, as
  `<span id="setup-nav-status" class="...same classes...">{{ setup_complete.nav_status }}</span>`
  instead of the anchor.

### Claim script — `landing/static/setup-complete.js`

Plain ES5-ish vanilla JS, no dependencies, mirroring the existing
`app.js`/`terminal-demo.js` style. Exact behavior:

1. `var params = new URLSearchParams(location.hash.slice(1));
   var hid = params.get("hid");`
2. Immediately strip the fragment:
   `history.replaceState(null, "", location.pathname + location.search);`
   (do this even if `hid` is missing).
3. No `hid` → render the expired state (step 6) and stop.
4. `fetch(apiBase + "/v1/setup/handoff/claim", {method: "POST", headers:
   {"content-type": "application/json"}, body: JSON.stringify({handoff_id: hid})})`
   where `apiBase = document.currentScript.dataset.apiBase`.
5. On 200: set `#setup-command.textContent = data.install_command`; set the
   copy button's `data-copy-command` to the same string and remove
   `disabled`; unhide `#setup-warning`; set `#setup-status.textContent = ""`;
   if `#setup-nav-status` exists, set its `textContent` to
   `"@" + data.github_login`. **Always assign via `textContent`, never
   `innerHTML`** (`github_login` is remote data).
6. On any non-200 / network error: `#setup-status` gets the
   `setup_complete.expired` copy plus a retry link built from
   `retry_label`/`retry_href` (render these into `data-` attributes on the
   CTA block so JS never hard-codes copy).
7. Never write the token to `localStorage`/`sessionStorage`/cookies/console.

### Deploy ordering (flip is config-only)

1. Ship + deploy the `logion` landing PR — `/setup/complete` goes live inert
   (visiting it directly just shows the expired state).
2. Ship + deploy the `backend repository` PR — migration runs; behavior still
   legacy because the settings are empty.
3. Set `SETUP_COMPLETE_REDIRECT_URL` + `SETUP_CORS_ALLOW_ORIGINS` in
   `packages/infra/.env.production` → flow flips. Rollback = unset both.

## 3. Tests

Backend (`backend repository/packages/api/tests/test_setup_handoffs.py`):

- mint stores hash only (raw `sh_` string absent from DB), TTL ≈120s;
- callback with `setup_complete_redirect_url` set → 303, `Location` is
  `<url>#hid=sh_...`, `no-store` header, no HTML body with a token, and **no
  setup token minted yet** (`setup_tokens` count unchanged);
- callback with setting empty → legacy HTML path byte-compatible (reuse the
  15.2 e2e assertions);
- claim happy path: consumes handoff, mints setup token for the right
  user/identity, returns raw token + prefix + `github_login` +
  `install_command` containing `--setup-token st_`;
- second claim → 410 `setup_handoff_invalid`; expired → 410; unknown → 410
  (all three byte-identical bodies);
- concurrent double-claim (two sessions, `for_update`) → exactly one 200;
- rate-limit fires on claim; `no-store` on claim response;
- CORS: `OPTIONS` preflight from a configured origin → allowed; from
  `https://evil.example` → no `access-control-allow-origin`; middleware
  absent entirely when the setting is empty.

Landing (`logion/packages/landing/tests/test_landing_routes.py` additions):

- `GET /setup/complete` → 200, `Cache-Control: no-store`, `X-Robots-Tag:
  noindex`, contains `setup-complete.js`, the masked command, the noscript
  copy, does **not** contain the pre-auth secondary CTA label, nav shows
  `connected` and not `Sign in`;
- `GET /` (setup_mode off) is unchanged: still shows `Sign in` + pre-auth
  CTA, does not reference `setup-complete.js` (regression lock);
- `/sitemap.xml` does not list `/setup/complete`; `robots.txt` disallows
  `/setup/`;
- static file `/static/setup-complete.js` is served and contains no hardcoded
  copy strings and no `innerHTML`.

## 4. Acceptance criteria

- [ ] Full flow on prod config: click sign-in on logion.sh → GitHub → land on
      `www.logion.sh/setup/complete` showing the branded hero with the
      personalized command; copy button works; nav reads `@<login>`.
- [ ] Address bar after load: `https://www.logion.sh/setup/complete` — no
      `code=`, no `state=`, no `hid`, no token.
- [ ] Refresh after claim → styled "already used / expired" state with a
      working retry link (never a raw API error page).
- [ ] Raw setup token appears in exactly one place: the claim JSON response.
      Never in URLs, DB, logs, or landing server memory (tests grep).
- [ ] With both settings unset, prod behavior is bit-for-bit the 15.2 flow.
- [ ] Landing remains DB-less; claim endpoint is rate-limited and CORS-scoped.
- [ ] Docs updated: `api.md` setup domain (handoff endpoint),
      `landing-page.md` (new route + setup_mode), infra env var reference for
      the two new settings.

## Out of scope

- Redirecting OAuth **error** branches to a styled landing state (callback
  error handling unchanged).
- Removing the API-rendered `setup_complete.html` (kept as config-off
  fallback).
- Any dashboard/session/cookie on the landing; token revocation UI; non-GitHub
  providers; changes to redeem/installer/CLI (15.2 contracts untouched).
- CSP for the landing (none exists today; adding one is separate work).

## Implementation appendix — compare against current code

Anchors verified against the repos on 2026-07-07:

- Callback: `backend repository/packages/api/api/setup/controllers/setup_github_callback.py`
  — the tail to change is the mint+render block (`MintSetupTokenService` ...
  `HTMLResponse`, lines ~249–270). Everything above (state validation, GitHub
  exchange, provisioning, `state_repo.consume`) stays byte-identical.
- Token mint service: `api/identity/services/mint_setup_token.py` returns
  `MintSetupTokenResult(raw_token, token_prefix, expires_at)` — reuse from the
  claim service unmodified.
- Hash/consume pattern to copy for handoffs:
  `api/identity/repositories/github_oauth_states.py` (sha256 hexdigest,
  `get_by_hash(for_update=True)`, `consume`).
- Rate-limit pattern to copy:
  `api/setup/controllers/redeem_setup_token.py` lines 10–28 (SlowAPI limiter
  from `api.identity.rate_limits`, `request` param kept for the decorator).
- App middleware insertion point: `api/main.py:141`
  (`app.add_middleware(SlowAPIMiddleware)`).
- Alembic: heads have forked before (see
  `0034_merge_bounty_and_setup_token_heads.py`); always `uv run alembic heads`
  before picking `down_revision`.
- Landing app: `logion/packages/landing/landing/main.py` — Jinja env line
  ~199, `_ctx` line ~298, `index` route line ~427, `robots_txt` line ~112,
  `sitemap_xml` line ~128. Vercel rewrites everything to `api/index`
  (`packages/landing/vercel.json`), so a new FastAPI route needs no Vercel
  config change.
- Hero CTA markup: `landing/templates/index.html` lines ~88–115
  (`copy-cta`, `data-copy-command`, `cta-cmd`, secondary loop). Header nav:
  `landing/templates/base.html` lines ~142–146 (`links.primary` loop).
- Copy source: `landing/content/site.yaml` — pre-auth secondary CTA ~lines
  53–55, nav `Sign in` ~lines 456–457. Keep `landing/content/landing.md`
  line 31 (markdown/LLM surface) as-is: it describes the sign-in *entry*
  point, which does not change.
- Copy-button behavior lives in `landing/static/app.js` keyed on
  `data-copy-command` — the setup variant reuses it; `setup-complete.js` only
  fills the attribute.

Branch targets:

| Work item | Repo | Target branch | Reason |
| --- | --- | --- | --- |
| `setup_handoffs` migration, claim endpoint, callback redirect, CORS | `backend repository` | `main` | Dark behind `setup_complete_redirect_url`/`setup_cors_allow_origins`; empty settings = current behavior. |
| Landing route `/setup/complete`, template variant, `setup-complete.js`, `site.yaml` copy | `logion` | `main` | Additive route, inert until the API redirects to it; `GET /` output is regression-locked unchanged. |
| Env flip (`SETUP_COMPLETE_REDIRECT_URL`, `SETUP_CORS_ALLOW_ORIGINS`) | infra (`packages/infra/.env.production`, gitignored values) | rollout gate | Flip only after both deploys; rollback = unset. |
