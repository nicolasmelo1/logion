# Logion Course Examples

This directory contains reference course bundles you can copy as a starting point. Each example is a runnable, valid Logion course that passes both:

1. **The agentskills.io SKILL.md spec** — frontmatter requires `name` (≤64 chars, lowercase + digits + hyphens, must match the directory name) and `description` (≤1024 chars). Optional fields: `license`, `compatibility`, `metadata`, `allowed-tools`. See https://agentskills.io/specification.
2. **The Logion capability schema** — a `course/capabilities.yaml` file declaring exactly what the course is allowed to do (tools, network domains, filesystem paths, env vars, human-approval requirement). See the comment block in `course/capabilities.yaml` files for the full schema; the matching client-side template lives at `packages/cli/cli/templates/course_capabilities.template.yaml`.

The Logion Marketplace Companion at `../packages/agent-companion/` is itself a course and the most complete worked example.

## Examples in this directory

| Directory | When to copy this |
|---|---|
| `minimal/` | Smallest course that validates against both specs. Pure SKILL.md + a near-empty capability manifest. Use when your skill needs no tools, no network, no filesystem writes. |
| `with-references-and-scripts/` | Skill that bundles one `scripts/` helper and a `references/` doc. Declares `tools: [file, terminal]` and `filesystem.write: [./outputs]`. Use when your skill executes a small subprocess and produces files. |
| `with-scripts/` | **The "course owns its codebase" pattern.** Bundled Gmail CLI with a `scripts/` entrypoint + `src/gmailcli/` real implementation (stdlib-only). Declares `tools: [file, terminal, web]`, `network.allow_domains: [gmail.googleapis.com]`, `secrets.env: [GMAIL_OAUTH_TOKEN]`. Use when your course ships non-trivial code that deserves organization into modules. This is the canonical replacement for the "tell the user to `npm install` my CLI" anti-pattern. |
| `with-eval/` | PR review checklist + a bundled deterministic eval. The eval scores agent reviews against fixtures with planted issues — catches "faking" agents that rubber-stamp. Declares `tools: [file, terminal]`, no network, no secrets. Use as a template when your course has measurable behavior worth verifying locally before publication. Also previews the shape future eval-backed bounty work will plug into (same fixtures + same scorer become bounty-eval ground truth). |

(A `with-network-and-secrets/` example — focused demonstration of `network.allow_domains` + `secrets.env` — is planned but not yet in this directory.)

## Validating a course before upload

```
logion course validate ./path/to/course
```

This runs both layers' validators and prints any errors. Run it before `logion courses versions upload`.

## Self-contained bundle rule

A Logion course bundle must be self-contained. Your `SKILL.md` and bundled scripts **must not** instruct the agent or user to install third-party packages at runtime:

- ❌ no `npm install`, `yarn add`, `pnpm add`
- ❌ no `pip install`, `pipx install`, `uv pip install`
- ❌ no `brew install`, `apt-get install`, `dnf install`, `pacman -S`
- ❌ no `cargo install`, `go install`, `gem install`
- ❌ no `curl ... | bash`, `wget ... | sh`, `bash <(curl ...)`
- ❌ no `git clone` of an external repo for the purpose of running its code

These are blocked by the automated review pipeline (`runtime_install_attempt` agent-scanner check). Your course will be rejected before reaching human review.

**Why.** Logion's whole trust model is that `course/capabilities.yaml` declares exactly what your course does, and review verifies that. A `npm install` runs whatever the package author currently ships — at install time, well after Logion's review saw your SKILL.md. The transitive dependency tree is unpinned, unscanned, and updates continuously. This is the exact pattern behind the ClawHub Jan 2026 supply-chain incident (341 typosquatted skills delivering Atomic Stealer).

**Allowed.** Your course may:

- Invoke tools that already exist on the user's machine (`bash`, `python3`, `node`, `git`, `jq`, …) — declare them via the agentskills.io `compatibility` field.
- Bundle your own code, in any language, inside the course.
- Make outbound HTTP requests to hostnames you list in `network.allow_domains`.
- Read/write files within the paths you list in `filesystem`.

**If you need an external binary**, you have two clean options:

1. **Bundle it.** Ship a static binary in `assets/`. Reviewed once, runs forever as-is.
2. **Declare it as a pre-existing requirement.** `compatibility: "Requires gccli — install yourself before using this course"`. The user installs separately, outside Logion's trust loop. Your course fails loudly if the binary isn't present.

The line: a course may **assume** an environment, but it may **not extend** the environment.

## License

MIT — same as the rest of `logion/`.


## Licensing note

These example bundles ship with `LICENSE` files using the Logion Standard Course License v1.0 so the publication artifact is explicit. Replace them with MIT/Apache-2.0/etc. for free courses, or keep the Logion license for paid distribution.
