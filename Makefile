SHELL := /bin/bash
ROOT := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)

.PHONY: lint test typecheck security audit secrets mock mock-stop install-hooks companion-verify companion-bundle companion-bundle-verify public-audit \
	ci-checks check-generated-lock check-root-files check-deps-lock check-doc-links \
	check-skip-reasons check-forbidden-imports \
	check-installer-security \
	update-generated-lock update-deps-lock \
	release-manifest release-manifest-check version-bump-cli version-bump-client version-bump-companion build-check \
	npm-test npm-pack npm-build \
	install-sh-lint install-sh-test install-ps1-lint install-ps1-test install-test

lint:
	uv run ruff check packages/
	uv run ruff format --check packages/

test:
	uv run pytest packages/ tests/ --no-header -q -m "not integration"

typecheck:
	uv run mypy packages/cli/cli/ packages/client/src/ --ignore-missing-imports

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
	npx @stoplight/prism-cli mock contracts/openapi/v1.json --port 4010 & echo $$! > .prism.pid

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

check-installer-security:
	python3 scripts/check_installer_security.py

# Umbrella target: every static guardrail. Fast (<1s total). Runs in
# CI and as part of the pre-commit hook. Slower checks (test, mypy,
# ruff, security audit) stay separate so this stays cheap.
ci-checks: public-audit check-generated-lock check-root-files check-deps-lock \
	check-doc-links check-skip-reasons check-forbidden-imports \
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
