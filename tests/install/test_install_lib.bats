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
