# Evaluation Harness

Local evaluation harness for the Logion Marketplace Companion.

## Directory layout

```
evals/
├── README.md           ← This file
├── scenarios/          ← Eval scenario YAML files
├── catalogs/           ← Capability and query catalogs
├── providers/          ← LLM provider configurations
├── graders/            ← Grading and scoring scripts
└── reports/            ← Generated eval reports (gitignored)
```

## Running evals

Evaluations use `llama.cpp` with GGUF models on Apple Silicon by default.
See `templates/eval.local.example.yaml` for configuration.

```bash
# Run all eval scenarios (requires llama.cpp setup)
python -m pytest tests/ -q

# Package-level verification
make verify
```

## Scenario format

Each scenario is a YAML file in `scenarios/` describing a test interaction:

```yaml
name: scenario-name
description: What this scenario tests
capability: logion.marketplace.search
input:
  query: "video editing"
  local_recall_results: []
expected:
  should_search_marketplace: true
  should_require_confirmation: false
  max_context_tokens: 500
```

## Grading

Graders live in `graders/` and check:

- Local recall is consulted before marketplace search.
- Confirmation gates are respected.
- Context budgets are within limits.
- No secrets or dangerous terms in output.