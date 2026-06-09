---
name: with-eval
description: PR review checklist with a bundled deterministic eval that catches "faking" agents. Use as a template when your course has measurable behavior worth verifying locally before publication. The agent reviews a code diff against the bundled checklist; the eval runner mechanically scores the review by checking whether planted issues were flagged. No LLM is required in the scoring loop — deterministic substring presence against bundled expectations.
license: MIT
compatibility: Requires Python 3.10+.
metadata:
  author: logion-examples
  version: "0.1.0"
---

# With-Eval: PR Review With Anti-Faking Eval

This example shows how to bundle an evaluation harness alongside a course. The evaluation tests one specific thing: **does the agent actually apply the checklist, or does it rubber-stamp?**

The checklist itself is a methodology — structured prompts the agent follows when reviewing a code diff. The eval verifies the agent isn't faking by feeding it a known-buggy diff with planted issues, then mechanically checking the agent's review output for those issues.

## Why this pattern matters

Most LLM-driven workflows can be faked. An agent that says *"the code looks fine"* on every PR appears to be doing review work but isn't. Bundled evals are the cheapest defense: deterministic ground truth that catches the rubber-stamp pattern before publication.

This is also the seam future eval-backed bounty work will plug into. A course that ships a working eval today is a course that supports bounty-funded improvement tomorrow — same fixtures, same scoring, same ground truth, just paid evaluators instead of local self-check.

## Structure

```
with-eval/
├── SKILL.md                          # this file
├── course/
│   └── capabilities.yaml             # file + terminal; no network, no secrets
├── references/
│   └── checklist.md                  # the actual review checklist
└── evals/
    ├── scenarios.json                # which fixtures to run, expected outcomes
    ├── fixtures/
    │   ├── clean_pr.diff             # a diff with no issues
    │   └── buggy_pr.diff             # a diff with four planted issues
    ├── expected/
    │   ├── clean_pr.json             # must NOT mention planted categories
    │   └── buggy_pr.json             # MUST mention all four planted categories
    ├── runner.py                     # deterministic scorer (no LLM)
    ├── reviews/                      # agent writes its reviews here
    └── reports/                      # runner writes verdicts here
```

## How the agent uses this course

When asked to review a diff, the agent:

1. Loads `references/checklist.md` (progressive disclosure — not loaded at activation).
2. Reads the diff (either supplied by the user, or one of `evals/fixtures/*.diff` for self-check).
3. Walks the diff against each checklist category.
4. Writes a structured review to `evals/reviews/<scenario>.txt` (when running the bundled eval) or to wherever the user asks.

The review **must** mention any checklist category code (e.g. `security:sql-injection`) that the diff violates. The categories are deliberately specific so the eval can mechanically check whether they were addressed.

## How the eval works

```
python evals/runner.py
```

For each scenario in `evals/scenarios.json`:

1. The runner reads `evals/reviews/<scenario>.txt` (the review the agent wrote).
2. Loads the expected outcome from `evals/expected/<scenario>.json`.
3. Scores by substring presence:
   - **Buggy fixture** (`verdict: must_flag`): every category in `required_categories` must appear in the review.
   - **Clean fixture** (`verdict: must_pass`): no category in `forbidden_categories` may appear.
4. Writes a verdict to `evals/reports/<scenario>.json`.
5. Exits non-zero if any scenario failed.

The runner does **not** call an LLM. It does not need one — the agent has already produced the review; the runner is the *check*, not the *reviewer*. This keeps the eval cheap, deterministic, and trust-clean.

## What gets planted in `buggy_pr.diff`

The buggy fixture intentionally introduces four issues, one per checklist category:

| Planted issue | Checklist category code |
|---|---|
| SQL query built via string concatenation | `security:sql-injection` |
| API key hardcoded as a string literal | `security:hardcoded-secret` |
| `urlopen` call without try/except | `reliability:missing-error-handling` |
| `range(n + 1)` where `range(n)` is intended | `correctness:off-by-one` |

The agent's review of `buggy_pr.diff` **must** mention each of these category codes (verbatim) to pass the eval. A faking agent that writes "LGTM" on both diffs fails this scenario.

## How to run the eval yourself

```bash
# 1. Ask the agent (or your model) to review each fixture, writing to:
#      evals/reviews/buggy_pr_must_flag_planted_issues.txt
#      evals/reviews/clean_pr_no_false_positives.txt

# 2. Run the scorer:
python evals/runner.py
```

Verdicts land in `evals/reports/`. Exit code 0 = all scenarios passed.

## Capability declarations

- `tools: [file, terminal]` — reads bundle files, runs Python.
- `filesystem.write: [./evals/reviews, ./evals/reports]` — agent writes reviews here; runner writes reports here.
- No network, no secrets, no human approval. The eval runs entirely locally against bundled fixtures.

If you later want the runner to call an external LLM (rather than scoring whatever review the agent already wrote), add the appropriate `network.allow_domains` and `secrets.env`. But consider whether deterministic scoring against bundled expectations is sufficient — it usually is, and it's the harder-to-game design.

## What an author should change when copying

1. `name:` in frontmatter (must match the directory name).
2. Replace `references/checklist.md` with your domain's checklist. Keep the category codes specific and stable.
3. Replace `evals/fixtures/` with diffs / inputs / artifacts from your domain.
4. Replace `evals/expected/` with the categories a correct response should mention (or avoid).
5. The runner is generic — substring presence against expected JSON — so you usually don't need to edit it. Adjust only if your scoring rule isn't substring-presence.
