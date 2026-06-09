# Usage Reference

This file is loaded by the agent **only when needed** — agentskills.io's progressive disclosure model means `SKILL.md` is the activation surface and `references/` files are loaded on demand to keep context small.

## Running the script

```bash
bash scripts/say-hello.sh [name]
```

- `name` (optional, positional) — defaults to `"world"`. The greeting will be `"hello, <name>!"`.

## Output format

The script writes one log line to stdout (and the agent should redirect to `outputs/hello.log`):

```
[2026-06-08T12:34:56Z] hello, <name>!
```

## Failure modes

- If `outputs/` does not exist, the agent should create it before invoking the script (the skill body explains this).
- If the script is not executable, the agent should invoke it via `bash scripts/say-hello.sh` rather than `./scripts/say-hello.sh`.

## When to load this file

The agent should load this reference only if the SKILL.md body does not give enough detail to answer the user's question. Loading it preemptively wastes context.
