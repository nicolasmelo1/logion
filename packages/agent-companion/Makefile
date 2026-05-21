SHELL := /bin/bash
ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)/packages/agent-companion

.PHONY: test lint format-check typecheck package-check verify

test:
	python -m pytest tests/ -q

lint:
	ruff check .

format-check:
	ruff format --check .

typecheck:
	python -m mypy scripts/package_skill.py scripts/check_updates.py --ignore-missing-imports

package-check:
	python scripts/package_skill.py

verify: lint format-check typecheck test package-check