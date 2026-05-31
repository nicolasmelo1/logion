SHELL := /bin/bash

.PHONY: test lint format-check typecheck package-check eval eval-llama-cpp download-models split-scenarios optimize-policy optimize-policy-llama-cpp optimize-references optimize-references-llama-cpp verify

# Override defaults via env, e.g.:
#   make eval-llama-cpp MODEL=qwen3-8b-q5km LLAMA_EXTRA_ARGS="-m .models/Qwen3-8B-GGUF/Qwen3-8B-Q4_K_M.gguf"
CONFIG ?= evals/providers/llama_cpp_local.example.yaml
MODEL ?= qwen3-8b-q5km
LLAMA_EXTRA_ARGS ?=

test:
	uv run python -m pytest tests/ -q

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

typecheck:
	uv run python -m mypy scripts/package_skill.py --ignore-missing-imports

package-check:
	uv run python scripts/package_skill.py

eval:
	uv run python evals/run_eval.py \
		--provider fake \
		--scenarios evals/scenarios \
		--catalog evals/catalogs/fake-marketplace.yaml

download-models:
	bash evals/scripts/download_llama_cpp_models.sh

eval-llama-cpp:
	LLAMA_EXTRA_ARGS="$(LLAMA_EXTRA_ARGS)" \
		bash evals/scripts/run_llama_cpp_eval.sh "$(CONFIG)" "$(MODEL)"

# --- DSPy offline optimization (requires [dspy] extra) ---

SPLIT_SEED ?= 42
SPLIT_OUTPUT ?= evals/optimizers/dspy/generated_candidates/split.json
OPTIMIZER ?= bootstrap_few_shot
OPTIMIZER_OUTPUT ?= evals/optimizers/dspy/generated_candidates/candidate-$(shell date +%Y%m%d-%H%M%S).json

# Per-slot context size override forwarded to the llama_cpp runner
# scripts (LOGION_DSPY_CTX_SIZE).  Default 16384 covers GEPA + most
# MIPROv2 runs; bump to 32768 when the MIPROv2 proposer prompt
# overflows because the signature carries large input fields (e.g.
# `current_policy_text` shipping the full SKILL.md).
CTX_SIZE ?= 16384

split-scenarios:
	uv run python evals/optimizers/dspy/split_scenarios.py \
		--scenarios evals/scenarios \
		--seed $(SPLIT_SEED) \
		--output $(SPLIT_OUTPUT)

# ``optimize-policy`` depends on the phony ``split-scenarios`` target
# (not the file output) so changing SPLIT_SEED or the scenarios dir
# regenerates the split instead of silently reusing a stale one.
optimize-policy: split-scenarios
	uv run --group dspy python evals/optimizers/dspy/optimize_policy.py \
		--split $(SPLIT_OUTPUT) \
		--catalog evals/catalogs/fake-marketplace.yaml \
		--optimizer $(OPTIMIZER) \
		--output $(OPTIMIZER_OUTPUT)

# Boot llama-server for $(MODEL) from $(CONFIG) and run DSPy optimization
# against it. Override OPTIMIZER, SPLIT_OUTPUT, OPTIMIZER_OUTPUT,
# LLAMA_EXTRA_ARGS, LOGION_DSPY_REUSE_SPLIT as needed.
optimize-policy-llama-cpp:
	LOGION_DSPY_OPTIMIZER="$(OPTIMIZER)" \
	LOGION_DSPY_SPLIT="$(SPLIT_OUTPUT)" \
	LOGION_DSPY_OUTPUT="$(OPTIMIZER_OUTPUT)" \
	LOGION_DSPY_SEED="$(SPLIT_SEED)" \
	LOGION_DSPY_CTX_SIZE="$(CTX_SIZE)" \
	LLAMA_EXTRA_ARGS="$(LLAMA_EXTRA_ARGS)" \
		bash evals/scripts/run_llama_cpp_dspy_optimize.sh "$(CONFIG)" "$(MODEL)" "$(OPTIMIZER)"

# --- Phase 6.11: reference-routing optimization ---

REF_ROUTING_SCENARIOS ?= evals/scenarios_reference_routing/scenarios.yaml
REF_ROUTING_OUTPUT ?= evals/optimizers/dspy/generated_candidates/ref-candidate-$(shell date +%Y%m%d-%H%M%S).json

optimize-references:
	uv run --group dspy python evals/optimizers/dspy/optimize_references.py \
		--scenarios $(REF_ROUTING_SCENARIOS) \
		--optimizer $(OPTIMIZER) \
		--seed $(SPLIT_SEED) \
		--output $(REF_ROUTING_OUTPUT)

# Boot llama-server for $(MODEL) from $(CONFIG) and run reference-routing
# optimization against it.  Override OPTIMIZER, REF_ROUTING_OUTPUT,
# LLAMA_EXTRA_ARGS, LOGION_DSPY_REF_OUTPUT as needed.
optimize-references-llama-cpp:
	LOGION_DSPY_OPTIMIZER="$(OPTIMIZER)" \
	LOGION_DSPY_REF_OUTPUT="$(REF_ROUTING_OUTPUT)" \
	LOGION_DSPY_SEED="$(SPLIT_SEED)" \
	LOGION_DSPY_CTX_SIZE="$(CTX_SIZE)" \
	LOGION_REF_ROUTING_SCENARIOS="$(REF_ROUTING_SCENARIOS)" \
	LLAMA_EXTRA_ARGS="$(LLAMA_EXTRA_ARGS)" \
		bash evals/scripts/run_llama_cpp_dspy_optimize_references.sh "$(CONFIG)" "$(MODEL)" "$(OPTIMIZER)"

verify: lint format-check typecheck test package-check eval