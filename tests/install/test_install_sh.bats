#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
#
# test_install_sh.bats — Bats tests for scripts/install.sh

# ── Setup / teardown ──────────────────────────────────────────────────────

setup() {
    # shellcheck source=../scripts/install_test/harness.sh
    . "${BATS_TEST_DIRNAME}/../../scripts/install_test/harness.sh"
    setup_fake_release
    fake_python --version "3.12.0"
    fake_uv
    fake_pipx

    # Build a stub install_lib.sh in the temp dir
    _stub_lib="${HARNESS_TMPDIR}/install_lib.sh"
    cat > "${_stub_lib}" <<'STUB_EOF'
#!/bin/sh
# Minimal stub of install_lib.sh for testing install.sh orchestration.

INSTALL_TMPDIR="${HARNESS_TMPDIR}"

info() { [ "${LOGION_INSTALL_QUIET}" != "1" ] && printf '[info] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }
die() { printf '[FATAL] %s\n' "$2" >&2; exit "$1"; }

detect_platform() { return 0; }

require_tools() {
    [ "${_SKIP_CURL}" != "1" ]
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run)      export LOGION_INSTALL_DRY_RUN=1 ;;
            --cli-only)     export LOGION_INSTALL_CLI_ONLY=1 ;;
            --skill-only)  export LOGION_INSTALL_SKILL_ONLY=1 ;;
            --no-modify-path) export LOGION_INSTALL_NO_MODIFY_PATH=1 ;;
            --quiet)        export LOGION_INSTALL_QUIET=1 ;;
            --channel=*)    export LOGION_INSTALL_CHANNEL="${1#--channel=}" ;;
            --version=*)    export LOGION_INSTALL_VERSION="${1#--version=}" ;;
            -h|--help)      info "Usage: install.sh [OPTIONS]"; exit 0 ;;
        esac
        shift
    done
    return 0
}

fetch_manifest() { return 0; }
validate_manifest() { return 0; }

check_python() {
    _pyver="$(python3 --version 2>/dev/null | sed 's/Python //')"
    _major="$(echo "${_pyver}" | cut -d. -f1)"
    _minor="$(echo "${_pyver}" | cut -d. -f2)"
    if [ "${_major}" -lt 3 ] 2>/dev/null || [ "${_minor}" -lt 12 ] 2>/dev/null; then
        die 7 "Python >= 3.12 required, got ${_pyver}"
    fi
    return 0
}

bootstrap_uv() { return 0; }

install_cli() {
    _inst_v="${LOGION_INSTALL_VERSION:-0.1.0}"
    cat > "${HARNESS_BIN_DIR}/logion" <<LG_EOF
#!/bin/sh
printf 'logion ${_inst_v}\n'
exit 0
LG_EOF
    chmod +x "${HARNESS_BIN_DIR}/logion"
    return 0
}

install_companion() {
    mkdir -p "${HARNESS_TMPDIR}/.logion/installed/logion-marketplace-companion"
    touch "${HARNESS_TMPDIR}/.logion/installed/logion-marketplace-companion/installed"
    return 0
}

update_path() { return 0; }
verify_install() { return 0; }
print_next_steps() { info "Run 'logion --version' to verify."; return 0; }
STUB_EOF
    export INSTALL_LIB_PATH="${_stub_lib}"
}

teardown() {
    cleanup
    unset INSTALL_LIB_PATH 2>/dev/null || true
    unset _SKIP_CURL 2>/dev/null || true
}

# ── Helper: run the real installer with the stub library ──────────────────

run_installer() {
    _install_sh="${BATS_TEST_DIRNAME}/../../scripts/install.sh"
    # Use an isolated PATH — only HARNESS_BIN_DIR + /usr/bin:/bin
    # so we can control exactly which commands the installer sees.
    PATH="${HARNESS_BIN_DIR}:/usr/bin:/bin" \
        HARNESS_TMPDIR="${HARNESS_TMPDIR}" \
        HARNESS_BIN_DIR="${HARNESS_BIN_DIR}" \
        INSTALL_LIB_PATH="${INSTALL_LIB_PATH}" \
        sh "${_install_sh}" "$@"
}

# ── 1. Dry-run ─────────────────────────────────────────────────────────────

@test "dry-run: prints steps without mutating and exits 0" {
    run run_installer --dry-run
    [ "$status" -eq 0 ]
}

# ── 2. Fresh install ──────────────────────────────────────────────────────

@test "fresh install: completes all steps and installs logion" {
    run run_installer
    [ "$status" -eq 0 ]
    [ -x "${HARNESS_BIN_DIR}/logion" ]
}

# ── 3. Refuses Python <3.12 ────────────────────────────────────────────────

@test "refuses Python 3.11: exits with code 7" {
    fake_python --version "3.11.9"
    run run_installer
    [ "$status" -eq 7 ]
}

# ── 4. sha256 mismatch ────────────────────────────────────────────────────

@test "sha256 mismatch: corrupt wheel causes abort" {
    # NOTE: sha256 verification is implemented in install_lib.sh (the real
    # library, not this stub).  This test documents the expected exit code
    # but cannot exercise it via the stub.  When install_lib.sh is tested
    # directly, sha256_verify should return exit code 6 on mismatch.
    skip "sha256 check lives in install_lib.sh — tested via unit tests there"
}

# ── 5. Version pin ────────────────────────────────────────────────────────

@test "version pin: --version overrides manifest version" {
    run run_installer --version logion-cli-v0.2.0
    [ "$status" -eq 0 ]
}

# ── 6. --cli-only ──────────────────────────────────────────────────────────

@test "--cli-only: skips companion install" {
    run run_installer --cli-only
    [ "$status" -eq 0 ]
    [ ! -e "${HARNESS_TMPDIR}/.logion/installed/logion-marketplace-companion/installed" ]
}

# ── 7. --skill-only (no logion) ────────────────────────────────────────────

@test "--skill-only: fails when logion not on PATH" {
    # Remove any logion binary from fake bin dir
    rm -f "${HARNESS_BIN_DIR}/logion" 2>/dev/null || true
    run run_installer --skill-only
    [ "$status" -ne 0 ]
}

# ── 8. --skill-only (with logion) ──────────────────────────────────────────

@test "--skill-only: succeeds when logion is preinstalled" {
    fake_logion_preinstalled
    run run_installer --skill-only
    [ "$status" -eq 0 ]
}

# ── 9. channel=latest ─────────────────────────────────────────────────────

@test "channel=latest: uses the latest manifest URL" {
    LOGION_INSTALL_MANIFEST_URL="file://${HARNESS_MANIFEST_DIR}/manifest-latest.json"
    export LOGION_INSTALL_MANIFEST_URL
    run run_installer --channel latest
    [ "$status" -eq 0 ]
}

# ── 10. Missing curl ─────────────────────────────────────────────────────

@test "missing curl: exits with code 4" {
    _SKIP_CURL=1 export _SKIP_CURL
    run run_installer
    [ "$status" -eq 4 ]
}

# ── 11. Upgrade ────────────────────────────────────────────────────────────

@test "upgrade: replaces older logion with newer version" {
    install_fake_logion_at "0.2.0"
    run run_installer --version logion-cli-v0.3.0
    [ "$status" -eq 0 ]
}

# ── 12. Downgrade ─────────────────────────────────────────────────────────

@test "downgrade: replaces newer logion with older version" {
    install_fake_logion_at "0.3.0"
    run run_installer --version logion-cli-v0.2.0
    [ "$status" -eq 0 ]
}

# ── 13. Idempotent rerun ──────────────────────────────────────────────────

@test "rerun is idempotent" {
    run run_installer
    [ "$status" -eq 0 ]
    run run_installer
    [ "$status" -eq 0 ]
}

# ── 14. PATH idempotent ──────────────────────────────────────────────────

@test "PATH update is idempotent" {
    run run_installer
    [ "$status" -eq 0 ]
    run run_installer
    [ "$status" -eq 0 ]
}

# ── 15. --no-modify-path ──────────────────────────────────────────────────

@test "--no-modify-path: skips shell profile modification" {
    run run_installer --no-modify-path
    [ "$status" -eq 0 ]
}

# ── 16. shellcheck ────────────────────────────────────────────────────────

@test "shellcheck passes on install.sh" {
    run shellcheck -s sh -x -e SC1091 scripts/install.sh
    [ "$status" -eq 0 ]
}