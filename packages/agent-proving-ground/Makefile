.PHONY: ci-checks test lint type-check format-check install-hooks

ci-checks: lint type-check test

test:
	uv run pytest -q

lint:
	uv run ruff check agent_proving_ground tests

type-check:
	uv run mypy agent_proving_ground

format-check:
	uv run ruff format --check agent_proving_ground tests
