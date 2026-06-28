---
name: with-eval
description: Reviews code diffs against a structured checklist covering security (sql-injection, hardcoded-secret, unvalidated-input), reliability (missing-error-handling, resource-leak), and correctness (off-by-one, wrong-comparison). Use when reviewing PRs, audit diffs, or any code change where you want a categorised, line-anchored review instead of free-form prose. Ships with a bundled deterministic self-test that catches "faking" agents that rubber-stamp without reading the diff.
license: MIT
compatibility: Requires Python 3.10+ (for the bundled self-test).
metadata:
  author: logion-examples
  version: "0.1.0"
---

# With-Eval: Checklist-Driven PR Review

This skill reviews code diffs against a bundled checklist. The agent reads `references/checklist.md`, walks the diff category by category, and writes a structured review naming any violated categories by their stable code (e.g. `security:sql-injection`, `reliability:missing-error-handling`).

The output format is deliberately structured — one line per finding, with the category code, file path, line number, and a short description. The categories don't change between versions, so reviews are comparable across diffs and across time.

## How the agent uses this skill

When asked to review a diff:

1. Read `references/checklist.md` (loaded on-demand via progressive disclosure — not loaded at activation).
2. Walk the diff against each category in the checklist.
3. For each issue found, write one line in the format:
   ```
   <category-code> <path>:<line> — <short description>
   ```
4. If the diff is clean, write a single line: `no issues`.

That's the entire workflow. The user gets a list of categorised findings or a clean bill of health.

## Example output

For a diff that introduces a string-concatenated SQL query and a hardcoded API key:

```
security:sql-injection users/dao.py:7 — query built via string concatenation with user-supplied `email`
security:hardcoded-secret users/dao.py:4 — API key stored as a string literal
```

## When to use this skill

- Pre-merge PR review (the obvious case).
- Auditing a vendor patch before applying it.
- Self-review before pushing a feature branch.
- Anywhere you'd otherwise get a free-form "looks good 👍" from an agent — this skill forces a categorised answer.

## Capability declarations

- `tools: [file, terminal]` — reads the diff, the checklist, writes the review.
- `filesystem.write: [./evals/reviews, ./evals/reports]` — review output + self-test verdicts (see below).
- No network, no secrets, no human approval. The skill runs entirely locally.

---

## Verifying the skill works: bundled self-test

The skill ships with a small evaluation harness under `evals/` that lets you (or a CI job, or a future bounty-eval) verify the agent **actually applies the checklist** instead of rubber-stamping.

### Why this matters

LLM-driven review can be faked. An agent that says *"the code looks fine"* on every diff appears to be doing review work but isn't. The bundled self-test catches the rubber-stamp pattern: it feeds the agent two known fixtures and mechanically scores its reviews.

### How to run it

```bash
# 1. Ask the agent to review each fixture, writing each review to:
#      evals/reviews/buggy_pr_must_flag_planted_issues.txt
#      evals/reviews/clean_pr_no_false_positives.txt
#
# 2. Run the scorer:
python evals/runner.py
```

For each scenario in `evals/scenarios.json`:
- The runner reads the review the agent wrote.
- Loads the expected outcome from `evals/expected/<scenario>.json`.
- Scores by substring presence:
  - **Buggy fixture** (`verdict: must_flag`): every category in `required_categories` must appear in the review.
  - **Clean fixture** (`verdict: must_pass`): no category in `forbidden_categories` may appear.
- Writes a verdict to `evals/reports/<scenario>.json`. Exits non-zero if any scenario failed.

The runner does **not** call an LLM. The agent has already written the review; the runner is the *check*, not the *reviewer*. Deterministic, cheap, trust-clean.

### What gets planted in `buggy_pr.diff`

| Planted issue | Checklist category |
|---|---|
| SQL query built via string concatenation | `security:sql-injection` |
| API key hardcoded as a string literal | `security:hardcoded-secret` |
| `urlopen` call without try/except | `reliability:missing-error-handling` |
| `range(n + 1)` where `range(n)` is intended | `correctness:off-by-one` |

A faking agent that writes "LGTM" or "no issues" on the buggy fixture fails on all four. An over-eager agent that flags every change fails the clean fixture by mentioning forbidden categories.

### Forward-compat note

This bundled self-test is the same shape future eval-backed marketplace bounties will use: bundled fixtures + bundled expectations + a deterministic scorer. A course that ships a working self-test today is one that supports paid-evaluator bounties tomorrow with no schema change — same fixtures, same scorer, just network evaluators instead of local self-check.

---

## Structure

```
with-eval/
├── SKILL.md                          # this file
├── course/
│   └── capabilities.yaml             # file + terminal; no network, no secrets
├── references/
│   └── checklist.md                  # the review checklist
└── evals/                            # bundled self-test
    ├── scenarios.json                # which fixtures to run, expected outcomes
    ├── fixtures/
    │   ├── clean_pr.diff             # a diff with no issues
    │   └── buggy_pr.diff             # a diff with four planted issues
    ├── expected/
    │   ├── clean_pr.json
    │   └── buggy_pr.json
    ├── runner.py                     # deterministic scorer (no LLM)
    ├── reviews/                      # agent writes its reviews here
    └── reports/                      # runner writes verdicts here
```

## What an author should change when copying

1. `name:` in frontmatter (must match the directory name).
2. `description:` (specific about what your checklist covers).
3. Replace `references/checklist.md` with your domain's checklist. Keep the category codes specific and stable — the self-test depends on substring presence.
4. Replace `evals/fixtures/` with diffs / inputs / artifacts representative of your domain.
5. Update `evals/expected/` with the categories a correct response should (or should not) mention.
6. The runner is generic — substring presence against expected JSON — so you usually don't need to edit it. Adjust only if your scoring rule isn't substring-presence.
