SHELL := /bin/bash

.PHONY: test lint format-check typecheck package-check eval eval-llama-cpp download-models verify

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

verify: lint format-check typecheck test package-check eval