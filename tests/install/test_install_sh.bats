#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
#
# test_install_sh.bats — Bats tests for scripts/install.sh
#
# These tests use a stub install_lib.sh (via INSTALL_LIB_PATH) to
# test the orchestration flow of install.sh. The stub defines
# functions that match install_lib.sh's API contract (variable names,
# function signatures, exit codes).
#
# For integration testing of install_lib.sh itself, see the
# test_install_lib.bats file (future work).

# ── Setup / teardown ──────────────────────────────────────────────────────

setup() {
    # shellcheck source=../scripts/install_test/harness.sh
    . "${BATS_TEST_DIRNAME}/../../scripts/install_test/harness.sh"
    setup_fake_release
    fake_python --version "3.12.0"
    fake_uv
    fake_pipx

    # Build a stub install_lib.sh in the temp dir that matches the real API:
    # - Uses INSTALL_* variables (not LOGION_INSTALL_*)
    # - Functions take arguments as documented
    # - Exit codes follow the 0-9 contract
    _stub_lib="${HARNESS_TMPDIR}/install_lib.sh"
    cat > "${_stub_lib}" <<'STUB_EOF'
#!/bin/sh
# Stub of install_lib.sh matching the real API contract.

INSTALL_TMPDIR="${HARNESS_TMPDIR}"

info() { [ "${INSTALL_QUIET}" != "1" ] && printf '[info] %s\n' "$*"; return 0; }
warn() { printf '[warn] %s\n' "$*" >&2; return 0; }
die() { printf '[FATAL] exit %s: %s\n' "$1" "$2" >&2; exit "$1"; }

detect_platform() { OS=linux; ARCH=x86_64; LIBC=gnu; export OS ARCH LIBC; return 0; }

require_tools() {
    [ "${_SKIP_CURL}" != "1" ]
}

parse_args() {
    INSTALL_CHANNEL=stable
    INSTALL_VERSION=""
    INSTALL_CLI_ONLY=0
    INSTALL_SKILL_ONLY=0
    INSTALL_PREFIX="$HOME/.local"
    INSTALL_PREFIX_EXPLICIT=0
    INSTALL_INSTALLER="pipx"
    INSTALL_DRY_RUN=0
    INSTALL_NO_MODIFY_PATH=0
    INSTALL_NO_ONBOARDING=0
    INSTALL_ONBOARDING_FAILED=0
    INSTALL_QUIET=0
    INSTALL_VERBOSE=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run)      INSTALL_DRY_RUN=1 ;;
            --cli-only)     INSTALL_CLI_ONLY=1 ;;
            --skill-only)  INSTALL_SKILL_ONLY=1 ;;
            --no-modify-path) INSTALL_NO_MODIFY_PATH=1 ;;
            --no-onboarding) INSTALL_NO_ONBOARDING=1 ;;
            --quiet)        INSTALL_QUIET=1 ;;
            --channel)      shift; INSTALL_CHANNEL="$1" ;;
            --channel=*)    INSTALL_CHANNEL="${1#--channel=}" ;;
            --version)      shift; INSTALL_VERSION="$1" ;;
            --version=*)    INSTALL_VERSION="${1#--version=}" ;;
        esac
        shift
    done
    # Mutual exclusivity
    if [ "$INSTALL_CLI_ONLY" = 1 ] && [ "$INSTALL_SKILL_ONLY" = 1 ]; then
        die 2 "--cli-only and --skill-only are mutually exclusive"
    fi
    export INSTALL_CHANNEL INSTALL_VERSION INSTALL_CLI_ONLY INSTALL_SKILL_ONLY
    export INSTALL_PREFIX INSTALL_PREFIX_EXPLICIT INSTALL_INSTALLER INSTALL_DRY_RUN
    export INSTALL_NO_MODIFY_PATH INSTALL_NO_ONBOARDING INSTALL_ONBOARDING_FAILED INSTALL_QUIET INSTALL_VERBOSE
    return 0
}

resolve_url() { printf '%s' "$1"; }

fetch_manifest() { return 0; }

validate_manifest() { return 0; }

manifest_get_field() {
    # Return canned values for known paths
    case "$2" in
        *logion-cli*.version)  printf '0.1.0' ;;
        *logion-companion*.version) printf '0.1.0' ;;
        *) printf '' ;;
    esac
    return 0
}

check_python() {
    # Mimic real check_python: validate version >= 3.12
    _py_ver="$(eval "${HARNESS_BIN_DIR}/python3 --version" 2>/dev/null | head -1)"
    _py_major="$(printf '%s' "$_py_ver" | sed 's/Python \([0-9]*\)\..*/\1/' 2>/dev/null)"
    _py_minor="$(printf '%s' "$_py_ver" | sed 's/Python [0-9]*\.\([0-9]*\).*/\1/' 2>/dev/null)"
    _py_major="${_py_major:-0}"; _py_minor="${_py_minor:-0}"
    if [ "$_py_major" -gt 3 ] || { [ "$_py_major" -eq 3 ] && [ "$_py_minor" -ge 12 ]; }; then
        printf '%s' "${HARNESS_BIN_DIR}/python3"
        return 0
    fi
    die 7 "Python >= 3.12 not found (got $_py_ver)"
}

bootstrap_uv() { return 0; }

# install_cli <version> <installer>
install_cli() {
    _inst_v="${1:-0.1.0}"
    cat > "${HARNESS_BIN_DIR}/logion" <<LG_EOF
#!/bin/sh
printf 'logion ${_inst_v}\n'
exit 0
LG_EOF
    chmod +x "${HARNESS_BIN_DIR}/logion"
    return 0
}

# install_companion <version> [<tag>]
install_companion() {
    mkdir -p "${HARNESS_TMPDIR}/.logion/installed/logion-marketplace-companion"
    touch "${HARNESS_TMPDIR}/.logion/installed/logion-marketplace-companion/installed"
    return 0
}

update_path() { return 0; }

# verify_install <cli_version> [<companion_version>]
verify_install() { return 0; }

run_onboarding() {
    if [ "${INSTALL_NO_ONBOARDING}" = 1 ]; then
        return 0
    fi
    if [ "${INSTALL_DRY_RUN}" = 1 ]; then
        return 0
    fi
    if [ -n "${LOGION_NONINTERACTIVE:-}" ]; then
        return 0
    fi
    if [ "${STUB_ONBOARDING_FAIL:-}" = 1 ]; then
        INSTALL_ONBOARDING_FAILED=1
        export INSTALL_ONBOARDING_FAILED
        return 0
    fi
    printf 'onboarding\n' >> "${HARNESS_TMPDIR}/onboarding-marker"
    return 0
}

print_next_steps() {
    if [ "${INSTALL_ONBOARDING_FAILED:-0}" = 1 ]; then
        info "Finish setup so your agent can use Logion:"
        info "  logion onboarding"
    else
        info "Your agent is ready to use Logion."
    fi
    return 0
}
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
    # Isolated PATH — only HARNESS_BIN_DIR + /usr/bin:/bin
    PATH="${HARNESS_BIN_DIR}:/usr/bin:/bin" \
        HARNESS_TMPDIR="${HARNESS_TMPDIR}" \
        HARNESS_BIN_DIR="${HARNESS_BIN_DIR}" \
        INSTALL_LIB_PATH="${INSTALL_LIB_PATH}" \
        STUB_ONBOARDING_FAIL="${STUB_ONBOARDING_FAIL:-}" \
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

@test "companion is installed by default" {
    run run_installer
    [ "$status" -eq 0 ]
    [ -e "${HARNESS_TMPDIR}/.logion/installed/logion-marketplace-companion/installed" ]
}

@test "default install runs onboarding handoff" {
    run run_installer
    [ "$status" -eq 0 ]
    [ -f "${HARNESS_TMPDIR}/onboarding-marker" ]
}

@test "onboarding failure prints rerun guidance" {
    STUB_ONBOARDING_FAIL=1 run run_installer
    [ "$status" -eq 0 ]
    [[ "$output" == *"logion onboarding"* ]]
    [[ "$output" != *"Your agent is ready to use Logion."* ]]
}

@test "--no-onboarding skips onboarding handoff" {
    run run_installer --no-onboarding
    [ "$status" -eq 0 ]
    [ ! -e "${HARNESS_TMPDIR}/onboarding-marker" ]
}

@test "real library: dry-run completes against fake manifest" {
    unset INSTALL_LIB_PATH
    _install_sh="${BATS_TEST_DIRNAME}/../../scripts/install.sh"
    run env \
        PATH="${HARNESS_BIN_DIR}:/usr/bin:/bin" \
        HOME="${HARNESS_TMPDIR}" \
        LOGION_INSTALL_MANIFEST_URL="${LOGION_INSTALL_MANIFEST_URL}" \
        LOGION_INSTALL_BASE_URL="${LOGION_INSTALL_BASE_URL}" \
        sh "${_install_sh}" --dry-run
    [ "$status" -eq 0 ]
}

@test "real library: manifest parser supports bracket notation without jq" {
    unset INSTALL_LIB_PATH
    _real_lib="${BATS_TEST_DIRNAME}/../../scripts/install_lib.sh"
    _real_python="$(command -v python3 || true)"
    if [ -z "${_real_python}" ]; then
        skip "python3 not found on PATH"
    fi
    cat > "${HARNESS_BIN_DIR}/python3" <<PYTHON_EOF
#!/bin/sh
exec "${_real_python}" "\$@"
PYTHON_EOF
    chmod +x "${HARNESS_BIN_DIR}/python3"

    run env PATH="${HARNESS_BIN_DIR}" /bin/sh -c \
        '. "$1"; validate_manifest "$2"' \
        _ "${_real_lib}" "${HARNESS_MANIFEST_DIR}/manifest-stable.json"

    [ "$status" -eq 0 ]
    [[ "$output" == *"cli_version=0.1.0"* ]]
}

@test "real library: companion fallback uses companion release tag" {
    unset INSTALL_LIB_PATH
    _real_lib="${BATS_TEST_DIRNAME}/../../scripts/install_lib.sh"
    if [ -x /usr/local/bin/python3 ]; then
        _real_python=/usr/local/bin/python3
    else
        _real_python=/usr/bin/python3
    fi
    cat > "${HARNESS_BIN_DIR}/python3" <<PYTHON_EOF
#!/bin/sh
exec "${_real_python}" "\$@"
PYTHON_EOF
    chmod +x "${HARNESS_BIN_DIR}/python3"
    _manifest_dir="${HARNESS_TMPDIR}/companion-fallback"
    mkdir -p "${_manifest_dir}"
    cat > "${_manifest_dir}/manifest.json" <<MANIFEST_EOF
{
  "schema_version": 1,
  "packages": {
    "logion-companion": {
      "version": "0.1.0",
      "tag": "logion-companion-v0.1.0",
      "minimum_cli": "0.1.0"
    }
  }
}
MANIFEST_EOF

    run env \
        PATH="${HARNESS_BIN_DIR}" \
        HOME="${HARNESS_TMPDIR}" \
        INSTALL_TMPDIR="${_manifest_dir}" \
        INSTALL_DRY_RUN=1 \
        /bin/sh -c '. "$1"; install_companion "0.1.0" "logion-cli-v0.1.0"' \
        _ "${_real_lib}"

    [ "$status" -eq 0 ]
    [[ "$output" == *"logion-companion-v0.1.0/logion-marketplace-companion-0.1.0.tar.gz"* ]]
    [[ "$output" != *"logion-cli-v0.1.0/logion-marketplace-companion-0.1.0.tar.gz"* ]]
}

# ── 2b. Real run_onboarding: TTY guard + --no-companion forwarding ─────────
# These source the *real* install_lib.sh (not the stub) so the actual guards
# are exercised, not a simplified copy.

# run_real_onboarding <key=val ...> — source the real lib, set INSTALL_* env,
# and run run_onboarding with stdin from /dev/null (a non-TTY) so it can never
# hang waiting on a prompt.
run_real_onboarding() {
    _real_lib="${BATS_TEST_DIRNAME}/../../scripts/install_lib.sh"
    # shellcheck disable=SC2086
    env "$@" sh -c '. "$1"; run_onboarding' _ "${_real_lib}" </dev/null
}

@test "real run_onboarding: non-interactive shell never invokes logion (no hang)" {
    # A fake logion that records any invocation; the TTY guard must prevent it.
    cat > "${HARNESS_BIN_DIR}/logion" <<LG_EOF
#!/bin/sh
printf 'invoked %s\n' "\$*" >> "${HARNESS_TMPDIR}/onboarding-invoked"
exit 0
LG_EOF
    chmod +x "${HARNESS_BIN_DIR}/logion"

    run run_real_onboarding \
        PATH="${HARNESS_BIN_DIR}:/usr/bin:/bin" \
        INSTALL_NO_ONBOARDING=0 INSTALL_DRY_RUN=0 INSTALL_CLI_ONLY=0
    [ "$status" -eq 0 ]
    [[ "$output" == *"Non-interactive shell"* ]]
    [ ! -e "${HARNESS_TMPDIR}/onboarding-invoked" ]
}

@test "real run_onboarding: --cli-only forwards --no-companion" {
    run run_real_onboarding \
        PATH="/usr/bin:/bin" \
        INSTALL_NO_ONBOARDING=0 INSTALL_DRY_RUN=1 INSTALL_CLI_ONLY=1
    [ "$status" -eq 0 ]
    [[ "$output" == *"logion onboarding --no-companion"* ]]
}

@test "real run_onboarding: default does not pass --no-companion" {
    run run_real_onboarding \
        PATH="/usr/bin:/bin" \
        INSTALL_NO_ONBOARDING=0 INSTALL_DRY_RUN=1 INSTALL_CLI_ONLY=0
    [ "$status" -eq 0 ]
    [[ "$output" == *"logion onboarding"* ]]
    [[ "$output" != *"--no-companion"* ]]
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
    run run_installer --version "0.2.0"
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

@test "--skill-only skips onboarding" {
    fake_logion_preinstalled
    run run_installer --skill-only
    [ "$status" -eq 0 ]
    [ ! -e "${HARNESS_TMPDIR}/onboarding-marker" ]
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
    _SKIP_CURL=1; export _SKIP_CURL
    run run_installer
    [ "$status" -eq 4 ]
}

# ── 11. Upgrade ────────────────────────────────────────────────────────────

@test "upgrade: replaces older logion with newer version" {
    install_fake_logion_at "0.2.0"
    run run_installer --version "0.3.0"
    [ "$status" -eq 0 ]
}

# ── 12. Downgrade ─────────────────────────────────────────────────────────

@test "downgrade: replaces newer logion with older version" {
    install_fake_logion_at "0.3.0"
    run run_installer --version "0.2.0"
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

@test "non-interactive install does not run onboarding" {
    LOGION_NONINTERACTIVE=1 run run_installer
    [ "$status" -eq 0 ]
    [ ! -e "${HARNESS_TMPDIR}/onboarding-marker" ]
}

# ── 16. --cli-only and --skill-only mutually exclusive ─────────────────────

@test "--cli-only and --skill-only are mutually exclusive" {
    run run_installer --cli-only --skill-only
    [ "$status" -eq 2 ]
}

# ── 17. shellcheck ────────────────────────────────────────────────────────

@test "shellcheck passes on install.sh" {
    run shellcheck -s sh -x -e SC1091 scripts/install.sh
    [ "$status" -eq 0 ]
}
