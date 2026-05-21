SHELL := /bin/bash

.PHONY: test lint format-check typecheck package-check verify

test:
	uv run python -m pytest tests/ -q

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

typecheck:
	uv run python -m mypy scripts/package_skill.py scripts/check_updates.py --ignore-missing-imports

package-check:
	uv run python scripts/package_skill.py

verify: lint format-check typecheck test package-check