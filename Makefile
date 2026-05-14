.PHONY: lint test typecheck mock mock-stop

lint:
	uv run ruff check packages/
	uv run ruff format --check packages/

test:
	uv run pytest packages/ --no-header -q || true

typecheck:
	uv run mypy packages/ --ignore-missing-imports

mock:
	npx @stoplight/prism-cli mock contracts/openapi/v1.json --port 4010 & echo $$! > .prism.pid

mock-stop:
	@if [ -f .prism.pid ]; then kill $$(cat .prism.pid) 2>/dev/null || true; rm -f .prism.pid; fi