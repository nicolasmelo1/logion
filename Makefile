.PHONY: lint test typecheck mock mock-stop

lint:
	uv run ruff check packages/
	uv run ruff format --check packages/

test:
	@echo "No tests yet. Run 'uv run pytest packages/' once tests are added."

typecheck:
	@echo "Type checking not configured yet. Add mypy to dev dependencies first."

mock:
	npx @stoplight/prism-cli mock contracts/openapi/v1.json --port 4010 & echo $$! > .prism.pid

mock-stop:
	@if [ -f .prism.pid ]; then kill $$(cat .prism.pid) 2>/dev/null || true; rm -f .prism.pid; fi