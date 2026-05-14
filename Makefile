.PHONY: lint test typecheck mock mock-stop

lint:
	uv run ruff check packages/
	uv run ruff format --check packages/

test:
	uv run pytest packages/

typecheck:
	uv run mypy packages/ --ignore-missing-imports

mock:
	npx @stoplight/prism-cli mock contracts/openapi/v1.json --port 4010

mock-stop:
	pkill -f "prism-cli mock" || true