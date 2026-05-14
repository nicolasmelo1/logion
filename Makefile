SHELL := /bin/bash
ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)

.PHONY: lint test typecheck security audit secrets mock mock-stop

lint:
	uv run ruff check packages/
	uv run ruff format --check packages/

test:
	uv run pytest packages/ --no-header -q -m "not integration"

typecheck:
	uv run mypy packages/ --ignore-missing-imports

audit:
	uv run pip-audit

bandit:
	uv run bandit -c pyproject.toml -r packages

secrets:
	uv run detect-secrets scan --baseline .secrets.baseline

security: audit bandit secrets

mock:
	npx @stoplight/prism-cli mock contracts/openapi/v1.json --port 4010 & echo $$! > .prism.pid

mock-stop:
	@if [ -f .prism.pid ]; then kill $$(cat .prism.pid) 2>/dev/null || true; rm -f .prism.pid; fi