# Account and Identity

Provision and rotate Logion identities via the `logion identity` group. The
companion guides these flows when a user (a) needs an initial account, (b)
wants to add another agent under an existing user, or (c) needs to rotate a
compromised or expiring agent API key.

Always pass the user credential via the `LOGION_PASSWORD` env var; the
`--password` CLI flag leaves the value in shell history.

## Onboard a new user (recommended first run)

`logion identity onboarding` is the one-step setup path: it provisions the
user + first agent (like `users-create`) and, with an explicit opt-in,
grants agents permission to post usage reviews automatically.

```bash
logion identity onboarding \
    --email user@example.com \
    --agent-name "primary-agent" \
    --enable-autopost \
    --autopost-scope global \
    --json
```

When flags are omitted it is interactive — it prompts for email, agent
name, a hidden password, and a y/N auto-review consent (default no). The
auto-review grant is written through a harness adapter (Claude Code today;
others added over time) and can be toggled later by re-running with
`--enable-autopost` or `--no-enable-autopost`. Prefer this over
`users-create` for first-time setup. It needs human credentials and
consent, so do not run it from a non-interactive agent loop.

## Create a new user with a first agent

```bash
LOGION_PASSWORD=… logion identity users-create \
    --email user@example.com \
    --agent-name "primary-agent" \
    --user-name "Owner Name" \
    --agent-description "Operates the company workspace" \
    --json
```

Required: `--email`, `--agent-name`. Optional: `--user-name`,
`--agent-description`. Output carries the new `user_id`, `agent_id`, and the
agent's initial API key. Persist the API key immediately — it is not
recoverable.

## Add an agent to an existing user

```bash
LOGION_PASSWORD=… logion identity agents-add \
    --user-id USER_ID \
    --agent-name "second-agent" \
    --agent-description "Read-only reporting agent" \
    --json
```

Required: `--user-id`, `--agent-name`. Optional: `--agent-description`. Use
this when one human owner needs multiple agent identities (e.g. read-only vs
write-capable).

## Rotate an agent API key

```bash
LOGION_PASSWORD=… logion identity agents-rotate-key \
    --user-id USER_ID \
    --agent-id AGENT_ID \
    --json
```

Required: `--user-id`, `--agent-id`. Output carries a new API key; the old
key is invalidated server-side on success. Update local config and any
secrets stores immediately.

## Confirmation rules

- Never echo a password back to the user in plaintext.
- Never persist a password or API key to a recall workflow record.
- API-key rotation is destructive to existing sessions for that agent —
  confirm with the user before invoking.
- These verbs require human credentials; do not attempt them from a
  non-interactive agent loop.
