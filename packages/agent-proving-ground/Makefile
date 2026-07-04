.PHONY: ci-checks test lint type-check format-check install-hooks

ci-checks: lint type-check test

test:
	uv run pytest -q

lint:
	uv run ruff check src tests

type-check:
	uv run mypy src

format-check:
	uv run ruff format --check src tests
