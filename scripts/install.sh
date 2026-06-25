#!/bin/sh
# SPDX-License-Identifier: MIT
#
# install.sh — Curl-able installer for Logion.
#
# Sources install_lib.sh for all helper functions; this file
# only orchestrates the step-by-step flow.
#
# Override the library path with INSTALL_LIB_PATH for testing.

# shellcheck source=./install_lib.sh
# ── Source the function library ──────────────────────────────────────────

if [ -n "${INSTALL_LIB_PATH}" ]; then
    . "${INSTALL_LIB_PATH}"
elif [ -f "$(dirname "$0")/install_lib.sh" ]; then
    . "$(dirname "$0")/install_lib.sh"
else
    _lib_tmpdir="$(mktemp -d)"
    _lib_path="$_lib_tmpdir/install_lib.sh"
    if ! curl -fsSL https://logion.sh/install_lib.sh -o "$_lib_path"; then
        printf 'logion: error: failed to download install_lib.sh\n' >&2
        exit 5
    fi
    # shellcheck source=/dev/null
    . "$_lib_path"
fi

# ── Temporary directory & cleanup ──────────────────────────────────────────

INSTALL_TMPDIR="$(mktemp -d)"
export INSTALL_TMPDIR

_cleanup() {
    if [ -n "${INSTALL_TMPDIR}" ] && [ -d "${INSTALL_TMPDIR}" ]; then
        rm -rf "${INSTALL_TMPDIR}"
    fi
    if [ -n "${_lib_tmpdir:-}" ] && [ -d "${_lib_tmpdir}" ]; then
        rm -rf "${_lib_tmpdir}"
    fi
}
trap _cleanup EXIT

# ── Main flow ─────────────────────────────────────────────────────────────

step=1

step_info() {
    if [ "${INSTALL_QUIET}" != "1" ]; then
        info "Step ${step}/13: $1"
    fi
    step=$((step + 1))
}

# 1/13  Detect platform
step_info "Detecting platform"
if ! detect_platform; then
    die 3 "Platform detection failed"
fi

# 2/13  Parse CLI arguments (--dry-run, --cli-only, --skill-only, etc.)
step_info "Parsing arguments"
if ! parse_args "$@"; then
    die 2 "Argument parsing failed"
fi

# 3/13  Verify required tools (curl, shasum/sha256sum, etc.)
step_info "Verifying required tools"
if ! require_tools; then
    die 4 "Required tool check failed"
fi

# 4/13  Fetch the release manifest
step_info "Fetching release manifest"
if ! fetch_manifest; then
    die 5 "Failed to fetch manifest"
fi

# 5/13  Validate the manifest (schema, checksums)
step_info "Validating manifest"
if ! validate_manifest "$INSTALL_TMPDIR/manifest.json"; then
    die 5 "Manifest validation failed"
fi

# Resolve CLI version and companion version from the manifest
CLI_VERSION="$(manifest_get_field "$INSTALL_TMPDIR/manifest.json" '.packages["logion-cli"].version')"
CLI_TAG="logion-cli-v${INSTALL_VERSION:-$CLI_VERSION}"
COMPANION_VERSION="$(manifest_get_field "$INSTALL_TMPDIR/manifest.json" '.packages["logion-companion"].version')"
export CLI_VERSION CLI_TAG COMPANION_VERSION

# 6/13  Check Python/backend only when installing the CLI
if [ "${INSTALL_SKILL_ONLY}" != "1" ]; then
    step_info "Checking Python version"
    if ! check_python; then
        die 7 "Python version check failed"
    fi

    # 7/13  Bootstrap uv (only when needed)
    if [ "$INSTALL_INSTALLER" = "uv" ]; then
        step_info "Bootstrapping uv"
        if ! bootstrap_uv; then
            die 4 "uv bootstrap failed"
        fi
    elif [ "$INSTALL_INSTALLER" = "pipx" ]; then
        step_info "Verifying pipx is available"
        if ! command -v pipx >/dev/null 2>&1; then
            die 4 "pipx not found; use --installer uv or --installer venv, or install pipx"
        fi
    fi
else
    step_info "Skipping Python/backend checks (--skill-only)"
fi

# 8/13  Install the CLI
if [ "${INSTALL_SKILL_ONLY}" = "1" ]; then
    # --skill-only: skip install_cli, just verify logion is on PATH
    step_info "Verifying logion is on PATH (--skill-only)"
    if ! command -v logion >/dev/null 2>&1; then
        die 1 "logion not found on PATH (required for --skill-only)"
    fi
else
    step_info "Installing logion CLI"
    _install_ver="${INSTALL_VERSION:-$CLI_VERSION}"
    if ! install_cli "$_install_ver" "$INSTALL_INSTALLER"; then
        die 8 "CLI installation failed"
    fi
fi

# 9/13  Install the companion skill bundle
if [ "${INSTALL_CLI_ONLY}" = "1" ]; then
    # --cli-only: skip install_companion
    step_info "Skipping companion (--cli-only)"
else
    step_info "Installing logion companion"
    _comp_ver="${COMPANION_VERSION:-$_install_ver}"
    if ! install_companion "$_comp_ver" "$CLI_TAG"; then
        die 8 "Companion installation failed"
    fi
fi

# 10/13 Update PATH in shell config
if [ "${INSTALL_SKILL_ONLY}" = "1" ]; then
    step_info "Skipping PATH update (--skill-only)"
else
    step_info "Updating PATH"
    if ! update_path; then
        die 1 "PATH update failed"
    fi
fi

# 11/13 Verify the installation
step_info "Verifying installation"
_install_ver="${INSTALL_VERSION:-$CLI_VERSION}"
_comp_ver="${COMPANION_VERSION:-}"
if ! verify_install "$_install_ver" "$_comp_ver"; then
    die 9 "Installation verification failed"
fi

# 12/13 Run onboarding (unless --no-onboarding / non-interactive / --skill-only)
if [ "${INSTALL_SKILL_ONLY}" = "1" ]; then
    step_info "Skipping onboarding (--skill-only)"
else
    step_info "Onboarding"
    run_onboarding || true
fi

# 13/13 Print next steps
step_info "Next steps"
if ! print_next_steps; then
    die 1 "Failed to print next steps"
fi
