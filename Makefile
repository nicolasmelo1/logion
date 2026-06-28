SHELL := /bin/bash
ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)
DEVRIG_ENV := $(ROOT)/.devrig/devrig.env
MODE ?= mock
AGENT ?= codex
ROLE ?= seller
LOGION_DEVRIG_API_BASE_URL ?=

.PHONY: lint dead-code dead-code-advisory test typecheck security audit secrets mock mock-stop install-hooks companion-verify companion-bundle companion-bundle-verify public-audit \
	ci-checks check-generated-lock check-root-files check-deps-lock check-doc-links \
	check-skip-reasons check-forbidden-imports check-cli-http \
	check-installer-security \
	update-generated-lock update-deps-lock \
	release-manifest release-manifest-check version-bump-cli version-bump-client version-bump-companion build-check \
	npm-test npm-pack npm-build \
	install-sh-lint install-sh-test install-ps1-lint install-ps1-test install-test \
	scanners-lint scanners-test social-lint social-test \
	bootstrap dev-up dev-api doctor companion start-companion clean-companion \
	dev-logs devrig-lint devrig-test dev-rebuild dev-rebuild-cli dev-rebuild-companion dev-rebuild-npm

lint:
	uv run ruff check packages/
	uv run ruff format --check packages/

dead-code:
	uv run vulture

dead-code-advisory:
	uv run vulture --min-confidence 60 || true

test:
	uv run pytest packages/ tests/ --no-header -q -m "not integration and not docker"

typecheck:
	uv run mypy packages/cli/cli/ packages/client/src/ packages/scanners/logion_scanners/ --ignore-missing-imports

audit:
	uv run pip-audit --skip-editable

bandit:
	uv run bandit -c pyproject.toml -r packages

secrets:
	uv run detect-secrets scan --baseline .secrets.baseline

security: audit bandit secrets

install-hooks:
	git config core.hooksPath .githooks
	@echo "Configured Git hooks path to .githooks"

mock:
	@mkdir -p .devrig
	@if [ -f .prism.pid ] && kill -0 $$(cat .prism.pid) 2>/dev/null; then \
		echo "Prism mock already running on http://127.0.0.1:4010"; \
	else \
		npx @stoplight/prism-cli mock contracts/openapi/v1.json --port 4010 > .devrig/prism.log 2>&1 & echo $$! > .prism.pid; \
		echo "Started Prism mock on http://127.0.0.1:4010 (log: .devrig/prism.log)"; \
	fi

mock-stop:
	@if [ -f .prism.pid ]; then kill $$(cat .prism.pid) 2>/dev/null || true; rm -f .prism.pid; fi

public-audit:
	uv run python scripts/audit_public_safe.py

check-generated-lock:
	uv run python scripts/check_generated_lock.py

check-root-files:
	uv run python scripts/check_root_files.py

check-deps-lock:
	uv run python scripts/check_deps_lock.py

check-doc-links:
	uv run python scripts/check_doc_links.py

check-skip-reasons:
	uv run python scripts/check_pytest_skip_reasons.py

check-forbidden-imports:
	uv run python scripts/check_forbidden_imports.py

check-cli-http:
	uv run python scripts/check_cli_http.py

check-installer-security:
	python3 scripts/check_installer_security.py

# Umbrella target: every static guardrail. Fast (<1s total). Runs in
# CI and as part of the pre-commit hook. Slower checks (test, mypy,
# ruff, security audit) stay separate so this stays cheap.
ci-checks: public-audit check-generated-lock check-root-files check-deps-lock \
	check-doc-links check-skip-reasons check-forbidden-imports check-cli-http \
	check-installer-security

update-generated-lock:
	uv run python scripts/check_generated_lock.py --update

update-deps-lock:
	uv run python scripts/check_deps_lock.py --update

companion-verify:
	uv run make -C packages/agent-companion verify

release-manifest:
	uv run python scripts/release_manifest.py build --channel stable

release-manifest-check:
	uv run python scripts/release_manifest.py check --in releases/manifest-stable.json

npm-test:
	cd packages/npm-wrapper && npm test

npm-pack:
	cd packages/npm-wrapper && npm pack

npm-build:
	cd packages/npm-wrapper && npm ci --ignore-scripts && npm run build && node dist/scripts/version-from-manifest.js && npm pack --dry-run && git checkout package.json

version-bump-cli:
	uv run semantic-release version -c packages/cli/pyproject.toml

version-bump-client:
	uv run semantic-release version -c packages/client/pyproject.toml

version-bump-companion:
	uv run semantic-release version -c packages/agent-companion/pyproject.toml

build-check:
	rm -rf dist/
	uv run python packages/cli/scripts/sync_docs.py
	uv build --package logion-cli --wheel --sdist
	uv build --package logion-client --wheel --sdist
	uv run twine check dist/*
	@echo "✅ Build check passed"

install-sh-lint: check-installer-security
	shellcheck -s sh -x -e SC1091 scripts/install.sh scripts/install_lib.sh scripts/install_test/harness.sh

install-sh-test: install-sh-lint
	bats tests/install/test_install_sh.bats

install-ps1-lint:
	pwsh -NoLogo -NoProfile -Command '$$paths = @("scripts/install.ps1", "scripts/install_lib.ps1", "tests/install/test_install_ps1.Tests.ps1"); foreach ($$path in $$paths) { Invoke-ScriptAnalyzer -Path $$path -Severity Error -EnableExit; Invoke-ScriptAnalyzer -Path $$path -IncludeRule PSAvoidUsingInvokeExpression -EnableExit }'

install-ps1-test: install-ps1-lint
	pwsh -NoLogo -NoProfile -Command 'if (-not $$env:TEMP) { $$env:TEMP = if ($$env:TMPDIR) { $$env:TMPDIR } else { [System.IO.Path]::GetTempPath() } }; $$out = Join-Path $$env:TEMP "logion-pester-results.xml"; Invoke-Pester -Path tests/install/test_install_ps1.Tests.ps1 -EnableExit -OutputFile $$out -OutputFormat NUnitXml'

install-test: install-sh-test install-ps1-test

companion-bundle:
	uv run python packages/agent-companion/scripts/package_skill.py build --out dist/ --version $(shell python -c "import tomllib,pathlib; print(tomllib.loads(pathlib.Path('packages/agent-companion/pyproject.toml').read_text())['project']['version'])") --release

companion-bundle-verify:
	uv run python packages/agent-companion/scripts/verify_bundle.py dist/logion-marketplace-companion-$(shell python -c "import tomllib,pathlib; print(tomllib.loads(pathlib.Path('packages/agent-companion/pyproject.toml').read_text())['project']['version'])").tar.gz

# ── scanners package targets ──────────────────────────────────
scanners-lint:
	uv run ruff check packages/scanners/
	uv run ruff format --check packages/scanners/

scanners-test:
	uv run pytest packages/scanners/tests/ -q --no-header -m "not docker"

scanners-test-integration:
	uv run pytest packages/scanners/tests/ -q --no-header -m docker

# ── social-management package targets ─────────────────────────
social-lint:
	uv run ruff check packages/social-management/
	uv run ruff format --check packages/social-management/

social-typecheck:
	uv run mypy packages/social-management/ --ignore-missing-imports

social-test:
	uv run pytest packages/social-management/tests/ -q --no-header

social-arch:
	uv run pytest packages/social-management/tests/test_social_architecture.py -q --no-header

bootstrap:
	uv sync --all-packages --all-groups
	uv run python scripts/devrig.py bootstrap

dev-up:
	uv run python scripts/devrig.py env --mode $(MODE) --role $(ROLE) $(if $(LOGION_DEVRIG_API_BASE_URL),--api-base-url $(LOGION_DEVRIG_API_BASE_URL),) --write $(DEVRIG_ENV)
	@if [ "$(MODE)" = "mock" ]; then $(MAKE) mock; else echo "Using production API via personal Logion account"; fi

dev-api:
	@if [ "$(MODE)" = "prod" ]; then \
		uv run python scripts/devrig.py env --mode prod --role $(ROLE) $(if $(LOGION_DEVRIG_API_BASE_URL),--api-base-url $(LOGION_DEVRIG_API_BASE_URL),) --write $(DEVRIG_ENV); \
		echo "Production mode does not start a local API. Current base URL:"; \
		grep LOGION_BASE_URL $(DEVRIG_ENV); \
	else \
		npx @stoplight/prism-cli mock contracts/openapi/v1.json --port 4010; \
	fi

doctor:
	uv run python scripts/devrig.py doctor --env-file $(DEVRIG_ENV) --agent $(AGENT)

companion:
	uv run python scripts/devrig.py companion --env-file $(DEVRIG_ENV) --agent $(AGENT) --role $(ROLE)

start-companion:
	uv run python scripts/devrig.py launch --env-file $(DEVRIG_ENV) --agent $(AGENT) --role $(ROLE)

clean-companion:
	uv run python scripts/devrig.py clean

dev-logs:
	@if [ -f .devrig/prism.log ]; then tail -f .devrig/prism.log; else echo "No Prism log yet at .devrig/prism.log"; fi

devrig-lint: lint

devrig-test: test

dev-rebuild: bootstrap clean-companion companion

dev-rebuild-cli: bootstrap

dev-rebuild-companion: clean-companion companion

dev-rebuild-npm: npm-build
