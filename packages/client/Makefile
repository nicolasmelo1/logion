SHELL := /bin/bash
# env -u: git exports GIT_DIR/GIT_INDEX_FILE to hook subprocesses, which
# makes --show-toplevel resolve to this directory instead of the repo root.
ROOT := $(shell env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git rev-parse --show-toplevel 2>/dev/null || pwd)
SPEC := $(ROOT)/contracts/openapi/v1.json
GEN_DIR := src/logion/v1/_types/generated
GEN_FILE := $(GEN_DIR)/v1.py
OPS_FILE := src/logion/v1/_generated/operations.py

.PHONY: generate-models check-models generate-operations check-operations generate-client check-client lint test typecheck

generate-models:
	uv run datamodel-codegen \
		--input $(SPEC) \
		--output $(GEN_FILE) \
		--output-model-type pydantic_v2.BaseModel \
		--field-constraints \
		--use-schema-description \
		--use-default-kwarg \
		--snake-case-field \
		--target-python-version 3.12 \
		--use-annotated \
		--enum-field-as-literal all \
		--allow-extra-fields
	uv run python scripts/postprocess_models.py $(GEN_FILE)
	uv run ruff format $(GEN_FILE)

check-models:
	@set -e; \
	tmpfile=$$(mktemp /tmp/logion-models-XXXXXX.py); \
	trap 'rm -f "$$tmpfile" "$$tmpfile.clean"' EXIT; \
	uv run datamodel-codegen \
		--input $(SPEC) \
		--output "$$tmpfile" \
		--output-model-type pydantic_v2.BaseModel \
		--field-constraints \
		--use-schema-description \
		--use-default-kwarg \
		--snake-case-field \
		--target-python-version 3.12 \
		--use-annotated \
		--enum-field-as-literal all \
		--allow-extra-fields; \
	uv run python scripts/postprocess_models.py "$$tmpfile"; \
	uv run ruff format "$$tmpfile"; \
	sed '1,3d' "$$tmpfile" > "$$tmpfile.clean"; \
	diff "$$tmpfile.clean" <(sed '1,3d' $(GEN_FILE))

generate-operations:
	uv run python scripts/generate_operations.py
	uv run ruff format $(OPS_FILE)
	uv run ruff check --fix $(OPS_FILE)

check-operations:
	uv run python scripts/generate_operations.py --check

generate-client: generate-models generate-operations

check-client: check-models check-operations

lint:
	uv run ruff check src/ tests/ scripts/
	uv run ruff format --check src/ tests/ scripts/

test:
	uv run pytest tests/ -v -m "not integration"

typecheck:
	uv run mypy src/ --ignore-missing-imports
