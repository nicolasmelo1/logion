# with-eval — Example Course

A working checklist-driven PR-review skill **bundled with its own self-test**.

This README is for the human reading the example. The `SKILL.md` is the agent-facing artifact.

## What this example actually is

Two things, in one directory, sharing the same artifacts:

1. **A real PR-review skill.** The agent reads `references/checklist.md`, walks a code diff against the listed categories, writes a structured review naming any violated category codes. That's the product.
2. **A self-test that verifies the skill works.** The `evals/` directory ships two fixture diffs (one with planted issues, one clean) plus a deterministic scorer that checks whether the agent's review mentions the planted category codes. That's the safety net.

Most authors copying this template care about #1 — they want to build their own checklist-driven skill (security review, accessibility review, infra review, whatever). The `evals/` harness comes along for free and protects them from shipping a course where the agent rubber-stamps.

## When you'd copy this

Copy this whole directory when your course:

- Has measurable, repeatable behavior — *given input X, the review should mention Y*.
- Uses a stable vocabulary the agent should produce (category codes, severity tags, structured outputs).
- Wants a cheap local pass/fail signal before publication (and a forward path to paid evaluation later).

If your course is pure free-form ("explain this code") or has no objective ground truth, this template will fight you. Pick `with-references-and-scripts/` instead.

## File map (human-readable)

```
with-eval/
├── README.md                    ← you are here
├── SKILL.md                     ← what the agent loads when activated
├── course/capabilities.yaml     ← Logion capability manifest (file + terminal, no network)
├── references/
│   └── checklist.md             ← the actual review checklist (4 categories, stable codes)
└── evals/                       ← the self-test
    ├── scenarios.json           ← list of test scenarios
    ├── fixtures/                ← input diffs (NOT real bugs in the example — synthetic)
    │   ├── clean_pr.diff
    │   └── buggy_pr.diff        ← 4 planted issues, 1 per checklist category
    ├── expected/                ← what a correct review must (or must not) mention
    │   ├── clean_pr.json
    │   └── buggy_pr.json
    ├── runner.py                ← scorer — substring presence, stdlib only, no LLM
    ├── reviews/                 ← agent writes its reviews here (empty in the example)
    └── reports/                 ← runner writes verdicts here (empty in the example)
```

## How to try it locally

```bash
cd path/to/with-eval

# 1. Have the agent (Claude Code, Codex, OpenCode, whatever) read SKILL.md +
#    references/checklist.md, then review each fixture. Tell it to write each
#    review to:
#      evals/reviews/buggy_pr_must_flag_planted_issues.txt
#      evals/reviews/clean_pr_no_false_positives.txt
#
# 2. Run the scorer:
python evals/runner.py
```

Expected on a correctly-applied checklist: both scenarios PASS, exit code 0. If the agent rubber-stamps, the buggy scenario fails with a list of category codes it missed.

The runner does not call any LLM. It just reads the files and does substring matching against the expected JSON. That's deliberate — the eval is itself trust-clean.

## Forward-compat note

The `evals/` shape (fixtures + expectations + deterministic runner) is intentionally the same shape future Logion **eval-backed bounties** will plug into. A course that ships a working self-test today is one that supports paid network-evaluator work tomorrow with no schema change. The local self-check is the same artifact a bounty-funded evaluator would run; only the funding source changes.

## What this is NOT

- It is not a generic eval framework. The runner is ~80 lines of substring-matching. For real eval design, look at `agent-companion/evals/` in the same repo, which has scenario archetypes, LLM judging seams, and the rest.
- It is not a security tool. The checklist is intentionally short (four categories) and the planted issues are deliberate teaching examples, not a real audit.
- It does not call an LLM in the eval loop. The agent (or the user, or CI) writes the review separately; the runner only scores it.

## Caveats worth knowing

- The `evals/fixtures/buggy_pr.diff` contains a realistic-looking fake API key (`sk-prod-...`). It's allowlisted in the repo's `.secrets.baseline` — necessary for the eval's "did you spot the hardcoded secret?" check to land. If you copy this example, you'll need to either keep the same shape and add your own baseline entry, or swap the planted issue for one that doesn't trip secret scanners.
- The runner depends on **exact category-code substrings** appearing in the agent's review. If you want fuzzier scoring (e.g. paraphrase tolerance), the runner is where you'd change it — but consider whether forcing stable codes is actually better for your skill's downstream consumers.
