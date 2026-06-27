---
name: with-scripts
description: Bundled Gmail CLI example demonstrating the scripts/ entrypoint + src/ implementation split. Use as a template when your course ships real code that goes beyond a single shell script. Shows how to organize a course bundle that owns its codebase — no runtime package installation, all dependencies stdlib-only. Replaces the "tell the user to npm install my CLI" anti-pattern.
license: Logion Standard Course License v1.0
compatibility: Requires Python 3.10+ and a valid GMAIL_OAUTH_TOKEN environment variable.
metadata:
  author: logion-examples
  version: "0.1.0"
---

# With-Scripts: Bundled Gmail CLI Example

This example shows how to ship a real working tool inside a Logion course bundle. The course **owns its codebase** — there is no `pip install`, no `npm install`, no transitive dependency tree. Everything the agent needs to call the Gmail API lives in this bundle and was reviewed once when the course was published.

This is the canonical pattern for replacing *"tell the user to install my CLI from npm"* with *"the course bundles the CLI."*

## Structure

```
with-scripts/
├── SKILL.md                  # this file
├── course/
│   └── capabilities.yaml     # file + terminal + web; gmail.googleapis.com; OAuth env
├── scripts/                  # thin entrypoints the agent invokes
│   ├── search.sh             # search messages
│   └── list-labels.sh        # list user labels
└── src/
    └── gmailcli/             # actual implementation
        ├── __init__.py
        ├── __main__.py       # python -m gmailcli {search,labels}
        ├── api.py            # Gmail REST client (stdlib urllib only)
        └── auth.py           # reads OAuth token from env
```

`scripts/` holds short entrypoints — bash wrappers that set `PYTHONPATH` and invoke the Python module. `src/` holds the real implementation. The separation is deliberate:

- The agent only invokes `scripts/search.sh "query"`. Simple, discoverable surface.
- The bulk of the logic — API calls, error handling, JSON parsing — lives in `src/gmailcli/`. Reviewable, testable, organized.
- The bundle stays self-contained: stdlib only (`urllib.request`, `json`), no `pip install` anywhere.

## When to use this template

Copy this structure when your course:

- Ships a non-trivial amount of code (more than one short script).
- Wants `scripts/` to remain a clean surface for the agent to discover commands.
- Has real implementation worth organizing into modules.

If your course is a single 50-line script, the simpler `with-references-and-scripts/` example is a better starting point.

## How to use

### 1. Obtain a Gmail OAuth token

The course **does not** authenticate. The user obtains a token externally — via the [Google OAuth playground](https://developers.google.com/oauthplayground), their own auth flow, or another tool — and exports it.

This is the trust-clean pattern: OAuth is the user's separate, informed consent decision, **outside** Logion's trust loop. The course only reads the token from `GMAIL_OAUTH_TOKEN`.

### 2. Export the token and invoke

```
export GMAIL_OAUTH_TOKEN="ya29...."
bash scripts/search.sh "from:alice subject:invoice"
bash scripts/list-labels.sh
```

Both print JSON to stdout. The agent should redirect output if persistence is needed.

## Capability declarations

- `tools: [file, terminal, web]` — reads its own bundle, runs Python, makes HTTPS calls.
- `network.allow_domains: [gmail.googleapis.com]` — exactly the one host the bundled code contacts.
- `secrets.env: [GMAIL_OAUTH_TOKEN]` — the only env var the bundle reads.
- No `filesystem.write` — output goes to stdout.
- No `human_approval` — the user already consented by exporting the token.

## What an author should change when copying

1. `name:` in frontmatter (must match the directory name).
2. `description:` (specific about what, when, why).
3. Replace `src/gmailcli/` with your own package directory.
4. Update `scripts/*.sh` entrypoints to dispatch to your package.
5. Update `course/capabilities.yaml` to declare only what your code actually does — drop the network domain if you don't need it, etc.
6. Keep the stdlib-only constraint. If you find yourself wanting `pip install`, see the "Self-contained bundle rule" in `examples/courses/README.md`.
