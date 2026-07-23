<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Phase 15.5.3: Operator Runbook — Register the `logion-bot` GitHub App

> **Operator (human) runbook, not a code phase.** This is the 15.5
> rollout step recorded in `maintainer documentation: production-infrastructure.md`
> ("register the `logion-bot` App on GitHub"), expanded to every click and
> every field. Doing this activates the already-deployed 15.5 webhook code
> (`POST /v1/webhooks/github` answers `503 github_app_unconfigured` until
> the env vars are set). It also pre-provisions the
> [15.5.1](phase-15.5.1-issue-mention-bounty-bot.md) permissions/events so
> no re-approval round-trip is needed later — **changing an App's
> permissions after installation requires every installer to re-approve**,
> so we ask for the full floor now.
>
> When done: delete this plan file (plans lifecycle) and fold any
> corrections into the `production-infrastructure.md` GitHub App block.

## Before you start (5 min)

1. **Name availability.** GitHub App names are unique across ALL of
   GitHub (max 34 chars). Check `https://github.com/apps/logion-bot` —
   404 means the slug is free. If taken, fallback: `logion-sh-bot`.
   Whatever slug GitHub assigns, `LOGION_GITHUB_APP_BOT_LOGIN` must be set
   to that slug (the code default is `logion-bot`), and the bot will
   comment as `<slug>[bot]`.
2. **Generate the webhook secret** on your machine and keep it in your
   clipboard/password manager:

   ```bash
   openssl rand -hex 32
   ```

3. **Decide the webhook target.** Two valid choices:
   - **Production (recommended for your test):**
     `https://api.logion.sh/v1/webhooks/github` — the endpoint is live,
     dark, HMAC-gated; garbage deliveries are rejected with 400.
   - Local testing instead: create a channel at `https://smee.io` (click
     **Start a new channel**), use the smee URL as the webhook URL, and run
     `npx smee-client --url <smee-url> --target http://localhost:8000/v1/webhooks/github`
     with the same secret in your local `.env`. You can change the
     webhook URL later in the App settings at any time.

## Part A — Register the App (github.com)

1. Go to <https://github.com> logged in as **your personal account** (the
   app lives under your account for now; transferring to an org later is
   supported by GitHub).
2. Click your **profile photo** (top-right) → **Settings**.
3. Left sidebar, bottom: **Developer settings**.
4. Left sidebar: **GitHub Apps** → click **New GitHub App** (green button,
   top-right).
5. Fill the form **exactly** as follows (anything not listed: leave the
   default / empty):

   | Field | Value |
   | --- | --- |
   | **GitHub App name** | `logion-bot` (or the fallback from step 1) |
   | **Description** (optional) | `Opens Logion bounty PRs and issue-mention bounties for linked courses. Merge != payout; Logion policy decides.` |
   | **Homepage URL** | `https://logion.sh` |
   | **Identifying and authorizing users → Callback URL** | leave **empty** (we never do user OAuth through the App — user identity is 15.1's separate OAuth app) |
   | **Expire user authorization tokens** | leave as-is (irrelevant, no user auth) |
   | **Request user authorization (OAuth) during installation** | **unchecked** |
   | **Enable Device Flow** | **unchecked** |
   | **Post installation → Setup URL** | leave empty |
   | **Redirect on update** | **unchecked** |
   | **Webhook → Active** | **checked** ✓ |
   | **Webhook URL** | `https://api.logion.sh/v1/webhooks/github` (or your smee URL) |
   | **Webhook secret** | paste the `openssl rand -hex 32` value |
   | **SSL verification** | **Enable SSL verification** (default — keep) |

6. **Permissions** section — expand **Repository permissions** and set
   (via each row's `Access:` dropdown):

   | Permission | Access | Why |
   | --- | --- | --- |
   | **Contents** | **Read and write** | create bounty branches (15.5) |
   | **Issues** | **Read and write** | read mentions + post bot comments (15.5.1) |
   | **Pull requests** | **Read and write** | open draft bounty PRs (15.5) |
   | **Metadata** | Read-only | forced mandatory by GitHub |

   Every other Repository permission stays **No access**. **Organization
   permissions** and **Account permissions**: all **No access**. This is
   the recorded floor: *contents + issues + pull requests + metadata — no
   other permission, ever.*

7. **Subscribe to events** — check exactly these four boxes (they only
   appear after the permissions above are selected; `installation`
   events are always delivered to GitHub Apps and have no checkbox):

   - ☑ **Issues**
   - ☑ **Issue comment**
   - ☑ **Pull request**

   (Nothing else — not "Push", not "Issue comment reaction", etc.)

8. **Where can this GitHub App be installed?** → select **Any account**
   (creators must be able to install it on their own repos/orgs; "Only on
   this account" would limit it to you).
9. Click **Create GitHub App**.

## Part B — Collect the credentials (App settings page)

You land on the App's **General** settings page
(`https://github.com/settings/apps/logion-bot`).

1. **App ID** — shown in the "About" box at the top (a small integer).
   Copy it → this is `LOGION_GITHUB_APP_ID`.
2. Scroll to **Private keys** → click **Generate a private key**. A
   `logion-bot.YYYY-MM-DD.private-key.pem` file downloads. This is the
   only copy — store it in the password manager immediately.
3. Ignore **Client ID / Client secrets** (only used for user OAuth, which
   we don't do here). Do NOT create a client secret.
4. Optional, nice for trust: **Display information** → upload a logo
   (the bot's avatar on every PR/comment) and set a badge background
   color.

## Part C — Configure production

All edits go into the gitignored
`backend repository/packages/infra/.env.production` (placeholders for these
four keys already exist in `env.example.production` lines 76–79).

1. The PEM is multiline but the env file is line-based. Docker Compose v2
   expands `\n` escape sequences inside **double-quoted** `env_file`
   values, and the API passes the string straight to
   `load_pem_private_key` — so flatten the key to one line:

   ```bash
   awk 'NF {printf "%s\\n", $0}' logion-bot.*.private-key.pem
   ```

   and set:

   ```bash
   LOGION_GITHUB_APP_ID=123456
   LOGION_GITHUB_APP_PRIVATE_KEY_PEM="[REDACTED PRIVATE KEY HEADER]\nMIIE...\n-----END RSA PRIVATE KEY-----\n"
   LOGION_GITHUB_APP_WEBHOOK_SECRET=<the openssl value>
   LOGION_GITHUB_APP_BOT_LOGIN=logion-bot
   ```

   (double quotes on the PEM line are load-bearing.)
2. Upload + validate + restart:

   ```bash
   uv run logion-infra env upload
   uv run logion-infra env validate-remote
   # then the usual deploy/restart path for the api service
   ```

3. **Verify the key survived the quoting** (this is the step that catches
   `\n` mistakes) — SSH into the app host first (`ssh -i
   ~/.ssh/logion_deploy deploy@<app-host-ip>`, IP from `terraform output
   app_host_ip`); this does NOT work from your laptop, and on the host the
   compose file has a non-default name:

   ```bash
   cd /opt/logion
   docker compose --env-file .env.production -f docker-compose.prod.yaml \
     exec api python -c "
   from api.config import get_settings
   from api.identity.services.github_app_auth import create_app_jwt
   s = get_settings()
   print(create_app_jwt(app_id=s.github_app_id,
                        private_key_pem=s.github_app_private_key_pem)[:20])"
   ```

   A JWT prefix prints → key parses and signs. A `ValueError: Could not
   deserialize` → the PEM lost its newlines; redo step 1.
4. Verify the endpoint is no longer dark: an unsigned
   `curl -X POST https://api.logion.sh/v1/webhooks/github -d '{}'` must
   now answer **400 Invalid signature** (was **503** before config).
5. Export credentials to the password manager:
   `make infra-export-credentials`.

## Part D — Install the App on a test repository

1. Pick/create a throwaway repo under your account (e.g.
   `nicolasmelo1/logion-bot-smoke`) — ideally one already linked to a
   course via `logion courses link` (15.3) so the whole flow is real.
2. Go to `https://github.com/apps/logion-bot` (the public App page) →
   click **Install** (or App settings → **Install App** in the left
   sidebar → **Install** next to your account).
3. On the install screen choose **Only select repositories** → select the
   test repo → click **Install**.
4. This fires an `installation` webhook. Verify it landed:
   - GitHub side: App settings → **Advanced** → **Recent Deliveries** —
     the `installation` delivery shows a green ✓ **200**. (This page also
     has **Redeliver**, your main debugging tool.)
   - Logion side: one row in `github_app_installations` with
     `status='active'` and your login, e.g.

     ```sql
     select installation_id, account_login, repository, status
     from github_app_installations;
     ```

     and the structured log line `github.webhook.processed`.

## Part E — Smoke test

**Today (15.5 code, already deployed):** the PR flow.

1. On a course linked to the test repo, create + open + fund a small
   bounty and a submission via the CLI, then
   `logion bounties submissions open-pr <bounty> <submission> --yes` —
   a **draft PR** authored by `logion-bot[bot]` appears on the repo with
   the `<!-- logion:bounty_submission:... -->` marker. (After
   [15.5.2](phase-15.5.2-auto-github-pr-submissions.md) ships,
   `submissions create` materializes the PR by itself and `open-pr` is
   only the repair path — retest the one-command flow then.)
2. Merge it **as the course owner's GitHub login** → within seconds the
   submission flips to `accepted` and the payable accrues (check
   `logion bounties get <id>`). Merge by any other account must instead
   produce a `merge_policy_rejected` event and change nothing.

**After 15.5.1 ships:** the issue flow.

1. Open an issue on the test repo, comment `@logion-bot bounty 250`.
2. Bot replies asking for confirmation (250 credits, course named).
3. Comment `@logion-bot confirm` → bot replies with the bounty URL;
   `logion bounties get <id>` shows `funded`, reward 250 credits.
4. Negative checks worth one minute each: `@logion-bot bounty 250 confirm`
   in a single comment must NOT open; a comment from a non-owner account
   must get the polite refusal.

If a delivery shows a red ✗ in **Recent Deliveries**: the response body
tells you which side failed (`Invalid signature` = secret mismatch between
the App form and `.env.production`; `503` = env not loaded; timeout =
Caddy/route problem). Fix, then **Redeliver** — the delivery-id
idempotency table makes redelivery safe.

## Part F — Close out

- [ ] App registered with exactly the Part A §6–7 permission/event floor.
- [ ] Private key + webhook secret in the password manager; the
      downloaded `.pem` deleted from `~/Downloads`.
- [ ] `503 github_app_unconfigured` gone; unsigned POST answers 400.
- [ ] Installation row present; PR smoke test green (both the owner-merge
      accept and the non-owner reject).
- [ ] `maintainer documentation: production-infrastructure.md` GitHub App block updated
      with: the final App slug, the amended permission floor
      (+ Issues) and event list (+ issues, issue_comment) — this edit
      ships with the 15.5.1 PR; if you registered with a fallback slug,
      also update `LOGION_GITHUB_APP_BOT_LOGIN` there and in
      `env.example.production`.
- [ ] Delete this plan file.

## Reference

- Registering a GitHub App (fields above follow this doc):
  <https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app>
- Managing private keys:
  <https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps>
- Webhook delivery debugging / redelivery:
  <https://docs.github.com/en/apps/creating-github-apps/writing-code-for-a-github-app/using-webhooks-with-github-apps>

## Cross-cutting improvement contract

This phase is governed by [`community-improvements-and-funded-bounties.md`](../maintainer documentation: community-improvements-and-funded-bounties.md). A community improvement proposal is **unfunded by default** and may accept a free GitHub PR/submission, retain contributor attribution and evidence, and merge upstream or become a maintained derivative with lineage. Funding is an explicit prospective conversion: only a confirmed funded bounty creates escrow, payout, or `sh.logion.bounty.accepted.v1`; an unpaid acceptance uses `sh.logion.improvement.accepted.v1` and must write no ledger/payable row. Publication review remains independent in both lanes.
