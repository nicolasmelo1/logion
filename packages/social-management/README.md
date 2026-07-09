# logion-social-management

Local agent tool for running Logion's Discord + X presence.

A small, low-maintenance CLI that lets agents (Claude, Codex, Hermes)
help run Logion's socials from local credentials. **Local execution
only — not a production service. No autonomous posting: every X write
requires explicit operator confirmation.**

## What it does

- **Discord (free primary):** post via per-channel incoming webhooks;
  read recent messages via a bot token (read-only triage;
  agents draft replies, they never auto-send).
- **X / Twitter (manual cadence, official API):** post via the official
  `POST /2/tweets` endpoint using the founder-provided API token, but
  gate every write behind (a) a monthly budget cap, (b) a running spend
  estimate, and (c) an explicit `--confirm` flag. There is no scheduler
  and no autoposting — a human triggers each post.

## Install

```bash
# from the logion repo root (uv workspace)
uv sync --all-packages
uv run logion-social --help
```

## Usage

```bash
# Discord webhook post (dry-run)
uv run logion-social discord post --channel general --text "gm" --dry-run

# Discord webhook post from a file (preserves newlines)
uv run logion-social discord post --channel announcements --file /path/to/post.txt --dry-run

# Discord webhook post (live)
uv run logion-social discord post --channel general --text "gm"

# Discord read recent messages (requires bot token)
uv run logion-social discord read --limit 50

# Discord read alerts channel
uv run logion-social discord read --channel alerts --limit 20

# X post dry-run (no network, no cost)
uv run logion-social x post --text "Smarter, together." --dry-run

# X post from a file (preserves newlines)
uv run logion-social x post --file /path/to/post.txt --dry-run

# X post with confirmation (spends money)
uv run logion-social x post --text "Smarter, together." --confirm

# Content queue
uv run logion-social queue add --platform x --target x --text "draft"
uv run logion-social queue list
```

## Environment variables

All loaded from the environment or `.env.local` (a simple `KEY=value`
file; existing env vars take precedence over the file).

### Discord

| Env var | Meaning |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Bot token for read-only triage (optional) |
| `DISCORD_GUILD_ID` | Numeric guild/server id |
| `DISCORD_WEBHOOK_ANNOUNCEMENTS` | Incoming webhook URL for the `announcements` slot |
| `DISCORD_WEBHOOK_GENERAL` | Incoming webhook URL for the `general` slot |
| `DISCORD_WEBHOOK_SUPPORT` | Incoming webhook URL for the `support` slot |
| `DISCORD_WEBHOOK_CREATORS` | Incoming webhook URL for the `creators` slot |
| `DISCORD_WEBHOOK_ALERTS` | Incoming webhook URL for the `alerts` slot |
| `DISCORD_CHANNEL_SUPPORT` | Channel id used by `discord read --channel support` |
| `DISCORD_CHANNEL_ALERTS` | Channel id used by `discord read --channel alerts` |

The five webhook slots (`announcements`, `general`, `support`,
`creators`, `alerts`) are the CLI's stable `--channel` vocabulary. Each env var
holds a webhook URL pointing at whatever Discord channel you created
the webhook in — the slot name and the channel name need not match.
See the operational setup guide for the real slot-to-channel mapping.

### X / Twitter

| Env var | Meaning |
| --- | --- |
| `X_BACKEND` | `api` or `off` (default `off`) |
| `X_API_KEY` | OAuth1.0a consumer key |
| `X_API_SECRET` | OAuth1.0a consumer secret |
| `X_ACCESS_TOKEN` | OAuth1.0a user access token |
| `X_ACCESS_SECRET` | OAuth1.0a user access secret |
| `X_BEARER_TOKEN` | Optional OAuth2 bearer (alternative to the 4 OAuth1 keys) |
| `X_MONTHLY_BUDGET_CENTS` | Hard monthly cap in cents (e.g. `500` = $5.00) |

## Cost model

X moved to pay-per-use with no free posting tier. Cost assumptions:

- **~$0.015/post (1.5¢)** for link-free bodies (rounded to 2¢).
- **~$0.20/post (20¢)** when the body contains a URL (the link tax).
- **~$0.005/read** (1¢) — reads are not gated, FYI only.

The tool estimates cost, enforces `X_MONTHLY_BUDGET_CENTS`, flags
link-posts loudly, and refuses to post without `--confirm`. Prefer
link-free bodies (put the link in a reply or the profile).