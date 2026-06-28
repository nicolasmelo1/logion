#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
#
# test_install_lib.bats — integration tests for scripts/install_lib.sh
# functions, sourcing the REAL library (not the install.sh stub used by
# test_install_sh.bats). Guards behaviour that the orchestration tests
# stub out — notably companion-bundle extraction, where a regression
# would silently ship a broken installer and force a re-release.

setup() {
    # shellcheck source=../../scripts/install_lib.sh
    . "${BATS_TEST_DIRNAME}/../../scripts/install_lib.sh"
    WORK="$(mktemp -d)"
}

teardown() {
    rm -rf "${WORK}"
}

# Build a tarball that mirrors package_skill.py output: every file lives
# under a top-level logion-marketplace-companion-<version>/ prefix dir.
_make_prefixed_bundle() {
    _src="${WORK}/src/logion-marketplace-companion-0.1.0"
    mkdir -p "${_src}/course" "${_src}/references"
    printf -- '---\nname: logion\nversion: 0.1.0\n---\n' > "${_src}/SKILL.md"
    printf 'MIT\n' > "${_src}/LICENSE"
    printf 'version: 1\n' > "${_src}/course/capabilities.yaml"
    printf '# ref\n' > "${_src}/references/troubleshooting.md"
    tar -czf "${WORK}/bundle.tar.gz" -C "${WORK}/src" \
        logion-marketplace-companion-0.1.0
}

@test "extract_companion_bundle strips the top-level prefix dir" {
    _make_prefixed_bundle
    run extract_companion_bundle "${WORK}/bundle.tar.gz" "${WORK}/dest"
    [ "$status" -eq 0 ]
    # Bundle files land directly in dest/ (prefix stripped).
    [ -f "${WORK}/dest/SKILL.md" ]
    [ -f "${WORK}/dest/LICENSE" ]
    [ -f "${WORK}/dest/course/capabilities.yaml" ]
    [ -f "${WORK}/dest/references/troubleshooting.md" ]
    # The logion-marketplace-companion-*/ wrapper must NOT remain.
    [ ! -d "${WORK}/dest/logion-marketplace-companion-0.1.0" ]
}

@test "extracted bundle satisfies the skills-install SKILL.md contract" {
    _make_prefixed_bundle
    extract_companion_bundle "${WORK}/bundle.tar.gz" "${WORK}/dest"
    # Exactly what `logion skills install --source <dest>` requires; if
    # this regresses, the curl installer registers no companion.
    [ -f "${WORK}/dest/SKILL.md" ]
}

@test "extract_companion_bundle creates the dest dir when absent" {
    _make_prefixed_bundle
    [ ! -d "${WORK}/dest" ]
    run extract_companion_bundle "${WORK}/bundle.tar.gz" "${WORK}/dest"
    [ "$status" -eq 0 ]
    [ -d "${WORK}/dest" ]
}

@test "install_companion resolves bundle URLs with the companion tag" {
    INSTALL_TMPDIR="${WORK}"
    INSTALL_DRY_RUN=1
    cat > "${WORK}/manifest.json" <<'JSON'
{
  "packages": {
    "logion-cli": {
      "tag": "logion-cli-v0.1.2",
      "version": "0.1.2"
    },
    "logion-companion": {
      "bundle": {
        "url": "release://logion-marketplace-companion-0.1.2.tar.gz"
      },
      "tag": "logion-companion-v0.1.2",
      "version": "0.1.2"
    }
  }
}
JSON

    run install_companion "0.1.2" "logion-cli-v0.1.2"

    [ "$status" -eq 0 ]
    [[ "$output" == *"https://github.com/nicolasmelo1/logion/releases/download/logion-companion-v0.1.2/logion-marketplace-companion-0.1.2.tar.gz"* ]]
    [[ "$output" != *"download/logion-cli-v0.1.2/logion-marketplace-companion-0.1.2.tar.gz"* ]]
}

@test "install_companion fallback URL uses the companion tag" {
    INSTALL_TMPDIR="${WORK}"
    INSTALL_DRY_RUN=1
    cat > "${WORK}/manifest.json" <<'JSON'
{
  "packages": {
    "logion-cli": {
      "tag": "logion-cli-v0.1.2",
      "version": "0.1.2"
    },
    "logion-companion": {
      "tag": "logion-companion-v0.1.2",
      "version": "0.1.2"
    }
  }
}
JSON

    run install_companion "0.1.2" "logion-cli-v0.1.2"

    [ "$status" -eq 0 ]
    [[ "$output" == *"https://github.com/nicolasmelo1/logion/releases/download/logion-companion-v0.1.2/logion-marketplace-companion-0.1.2.tar.gz"* ]]
    [[ "$output" != *"download/logion-cli-v0.1.2/logion-marketplace-companion-0.1.2.tar.gz"* ]]
}

@test "install_companion registers with required CLI metadata" {
    _make_prefixed_bundle
    _bundle_sha="$(sha256sum "${WORK}/bundle.tar.gz" | cut -d' ' -f1)"
    INSTALL_TMPDIR="${WORK}"
    INSTALL_DRY_RUN=0
    HOME="${WORK}/home"
    mkdir -p "${WORK}/bin" "$HOME"
    cat > "${WORK}/bin/logion" <<LOGION_EOF
#!/bin/sh
printf '%s\n' "\$*" >> "${WORK}/logion-calls"
exit 0
LOGION_EOF
    chmod +x "${WORK}/bin/logion"
    PATH="${WORK}/bin:${PATH}"
    export HOME PATH INSTALL_TMPDIR INSTALL_DRY_RUN
    cat > "${WORK}/manifest.json" <<JSON
{
  "packages": {
    "logion-companion": {
      "bundle": {
        "url": "file://${WORK}/bundle.tar.gz",
        "sha256": "${_bundle_sha}"
      },
      "tag": "logion-companion-v0.1.0",
      "version": "0.1.0"
    }
  }
}
JSON

    run install_companion "0.1.0" "logion-cli-v0.1.0"

    [ "$status" -eq 0 ]
    _call="$(cat "${WORK}/logion-calls")"
    [[ "$_call" == *"skills install"* ]]
    [[ "$_call" == *"--course-id logion-marketplace-companion"* ]]
    [[ "$_call" == *"--version-id 0.1.0"* ]]
    [[ "$_call" == *"--install-source logion-marketplace"* ]]
    [[ "$_call" == *"--no-symlink"* ]]
}
