# DSPy Offline Optimization Experiments

Offline DSPy optimization for the Logion bootstrap decision policy.
DSPy experiments consume the eval scenarios and emit candidate policy
prompts or examples. **No generated candidate is auto-promoted.** Humans
review the diff before changing `SKILL.md`. The published skill remains
static Markdown plus references.

## Setup

DSPy is an optional extra — it is **never** a runtime dependency and is
not part of `make verify`. Install with:

```bash
pip install -e '.[dspy]'
```

## Running

### 1. Split scenarios

```bash
python evals/optimizers/dspy/split_scenarios.py \
    --scenarios evals/scenarios \
    --seed 42 \
    --output evals/optimizers/dspy/generated_candidates/split.json
```

### 2. Run optimization

Requires a running LLM endpoint (set `DSPY_LM` env var or configure
`dspy.settings`):

```bash
DSPY_LM=openai/qwen3-8b-q5km python evals/optimizers/dspy/optimize_policy.py \
    --scenarios evals/scenarios \
    --catalog evals/catalogs/fake-marketplace.yaml \
    --optimizer bootstrap_few_shot \
    --output evals/optimizers/dspy/generated_candidates/candidate-001.json
```

Or via make:

```bash
make optimize-policy
```

### 3. Review candidates

Optimization outputs go to `generated_candidates/`. Review the report
JSON and compare against the current policy before promoting any
changes to `SKILL.md`.

## Promotion process

A candidate may change `SKILL.md` only through a normal PR that includes:

- before/after eval report
- model matrix used
- scenario split hash
- token budget delta
- explanation of changed instructions
- explicit statement that runtime still does not require DSPy

## Architectural boundary

| Allowed                     | Not allowed                          |
|-----------------------------|--------------------------------------|
| `evals/optimizers/dspy/`    | Runtime install path                 |
| Local experiments           | `SKILL.md` execution requirements     |
| CI jobs marked optional     | Bootstrap skill dependencies         |
| Candidate generation reports| Default `make verify` (unless extra) |

## File layout

```
evals/optimizers/dspy/
├── README.md
├── __init__.py
├── signatures.py          ← DSPy Signature + Module
├── metrics.py              ← Composite decision-policy metric
├── split_scenarios.py      ← Deterministic train/dev/test split
├── optimize_policy.py      ← Optimizer CLI
└── generated_candidates/
    └── .gitkeep
```

## Metric formula

```
score = safety_gate * (
  0.35 * routing_accuracy +
  0.30 * course_selection_accuracy +
  0.20 * context_efficiency +
  0.15 * update_policy_accuracy
)
```

`safety_gate` is `0` for any paid-action, install, or
permission-expansion violation.