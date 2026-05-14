SHELL := /bin/bash
ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)
SPEC := $(ROOT)/contracts/openapi/v1.json
GEN_DIR := src/logion/v1/_types/generated
GEN_FILE := $(GEN_DIR)/v1.py

.PHONY: generate-models check-models lint test typecheck

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
		--extra-fields allow
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
		--extra-fields allow; \
	uv run ruff format "$$tmpfile"; \
	sed '1,3d' "$$tmpfile" > "$$tmpfile.clean"; \
	diff "$$tmpfile.clean" <(sed '1,3d' $(GEN_FILE))

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

test:
	uv run pytest tests/ -v -m "not integration"

typecheck:
	uv run mypy src/ --ignore-missing-imports