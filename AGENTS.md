# AGENTS.md

Orientation for AI coding assistants (Claude, Cursor, Aider, Codex,
others) contributing to this repository.

If you are a human, [`CONTRIBUTING.md`](CONTRIBUTING.md) is the
authoritative document. This file is the AI-facing summary plus the
guardrails you will fail CI on if you ignore.

---

## What Logion is

Logion is an AI-agent-first marketplace for operational knowledge.
Creators publish reusable course bundles that buyer agents purchase
through entitlements. Contributors improve courses through funded
bounties. Trust comes from publication review, provenance, admin
moderation, reports, ratings, and update history.

This repository (`logion/`) holds the **public developer surface**:

- `packages/client/` — Python SDK
- `packages/cli/` — command-line interface
- `packages/agent-companion/` — first-party companion skill bundle
- `packages/landing/` — public web scaffold
- `contracts/openapi/v1.json` — public API contract

The backend that serves this contract is private. This repo never
references private repo names, internal docs, or internal milestone
vocabulary. See **Guardrails** below for the enforced rules.

---

## Hard rules (CI will reject violations)

Every rule below is enforced by a script in `scripts/` and by the
`pre-commit` hook (set up with `make install-hooks`). Running
`make ci-checks` locally reproduces what CI runs.

1. **No internal planning vocabulary.** The full forbidden-pattern
   table lives in `scripts/audit_public_safe.py`. It covers
   milestone-numbering words, forward-looking commitment words, sister
   private repo names, internal doc directory names, and a small set of
   LLM-tell phrases. Use the audit script as the source of truth; do
   not restate the patterns elsewhere.
2. **Generated files are immutable from PRs.** Listed in
   `.generated-files.lock` with SHA-256s. The contract
   (`contracts/openapi/v1.json`) and the generated client code under
   `packages/client/src/logion/v1/_generated/` and
   `packages/client/src/logion/v1/_types/generated/` are produced by an
   upstream sync workflow. If a change requires touching them, it
   is the wrong change — open a Discussion proposing the API change
   instead.
3. **No new top-level files without updating `.allowed-root-files`.**
   Discovery files (`NOTES.md`, `PLAN.md`, `SUMMARY.md`, `ANALYSIS.md`,
   `RESEARCH.md`, etc.) are the single most recognizable AI-PR smell
   and are blocked. Put work-in-progress in a Discussion or a PR
   description, not a tracked file.
4. **No dependency changes without updating `.deps.lock.json`.**
   Both files must change in the same commit (`make update-deps-lock`).
   Reviewers treat the diff as a permission gate against supply-chain
   drift.
5. **Documentation links must resolve.** `scripts/check_doc_links.py`
   walks every `.md` file and asserts that referenced repo-relative
   paths exist. Fabricated module paths fail CI.
6. **No imports of package internals from outside the package.**
   `logion.v1._internal`, `logion.v1._generated`, and
   `logion.v1._types.generated` are private. Consumers go through
   `logion.v1` and its handwritten resources.
7. **`pytest.skip`, `mark.skip`, and `mark.xfail` require `reason=`.**
   Same for `# type: ignore[code]` and `# noqa: RULE` — no blanket
   forms. If you need to disable something, explain why.
8. **PR titles follow Conventional Commits.** Enforced both locally
   (`commit-msg` hook) and in CI (`pr-title.yml`). Format:
   `type(scope): summary` — e.g. `fix(cli): handle empty tag list`.

---

## Working model

- **Branch naming:** `<type>/<short-slug>` (e.g. `fix/cli-empty-tags`,
  `feat/listings-filter`).
- **Conventional Commit types:** `feat`, `fix`, `docs`, `refactor`,
  `test`, `chore`, `perf`, `build`, `ci`, `revert`.
- **Run before committing:** `make ci-checks`. The pre-commit hook
  runs this for you if installed.
- **Test command:** `uv run pytest packages/ tests/ -m "not integration"`.
- **Lint/format:** `uv run ruff check packages/` and
  `uv run ruff format --check packages/`.
- **Type check:** `uv run mypy packages/ --ignore-missing-imports`.

---

## What good PRs look like

- **Small.** One concern per PR. If a refactor and a bugfix want to
  ride together, split them.
- **No restated-code comments.** Comments explain *why*, not *what*.
  Good: `# uv.lock pin avoids resolver flap on macOS`. Bad:
  `# increment the counter`.
- **No new abstractions for a one-shot change.** Three similar lines
  beats a premature helper.
- **No half-finished implementations.** If a function is named
  `_compute_X` and not called yet, do not commit it.
- **No prose padding.** Cut adverbs. State the change in the PR
  description; do not summarize the diff.
- **Tests next to the code they cover.** Asserts target behavior,
  not implementation detail.

---

## What to do when you are not sure

Ask in a [Discussion](https://github.com/nicolasmelo1/logion/discussions)
rather than guessing. A wrong PR is more expensive to review than a
question, especially for changes that touch the API contract, the
release workflow, or any of the guardrail scripts in `scripts/`.

If you suspect a guardrail is wrong, propose a fix to the guardrail in
its own PR; do not bypass it.

---

## Pointers

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — full contributor guide.
- [`SECURITY.md`](SECURITY.md) — security-disclosure process.
- [`docs/openapi-sync.md`](docs/openapi-sync.md) — how the contract
  flows in, how to run the local mock.
- [`packages/agent-companion/README.md`](packages/agent-companion/README.md) —
  companion bundle architecture.
- [`scripts/`](scripts/) — every guardrail referenced above.
