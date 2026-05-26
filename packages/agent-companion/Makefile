SHELL := /bin/bash

.PHONY: test lint format-check typecheck package-check eval verify

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

verify: lint format-check typecheck test package-check eval