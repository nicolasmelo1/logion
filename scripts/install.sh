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
else
    . "$(dirname "$0")/install_lib.sh"
fi

# ── Temporary directory & cleanup ──────────────────────────────────────────

INSTALL_TMPDIR="$(mktemp -d)"
export INSTALL_TMPDIR

_cleanup() {
    if [ -n "${INSTALL_TMPDIR}" ] && [ -d "${INSTALL_TMPDIR}" ]; then
        rm -rf "${INSTALL_TMPDIR}"
    fi
}
trap _cleanup EXIT

# ── Main flow ─────────────────────────────────────────────────────────────

step=1

step_info() {
    # shellcheck disable=SC2153
    if [ "${LOGION_INSTALL_QUIET}" != "1" ]; then
        info "Step ${step}/12: $1"
    fi
    step=$((step + 1))
}

# 1/12  Detect platform
step_info "Detecting platform"
if ! detect_platform; then
    die 3 "Platform detection failed"
fi

# 2/12  Verify required tools (curl, shasum/sha256sum, etc.)
step_info "Verifying required tools"
if ! require_tools; then
    die 4 "Required tool check failed"
fi

# 3/12  Parse CLI arguments (--dry-run, --cli-only, --skill-only, etc.)
step_info "Parsing arguments"
if ! parse_args "$@"; then
    die 2 "Argument parsing failed"
fi

# 4/12  Fetch the release manifest
step_info "Fetching release manifest"
if ! fetch_manifest; then
    die 5 "Failed to fetch manifest"
fi

# 5/12  Validate the manifest (schema, checksums)
step_info "Validating manifest"
if ! validate_manifest; then
    die 5 "Manifest validation failed"
fi

# 6/12  Check that Python meets the minimum version
step_info "Checking Python version"
if ! check_python; then
    die 7 "Python version check failed"
fi

# 7/12  Bootstrap uv (Python package runner)
step_info "Bootstrapping uv"
if ! bootstrap_uv; then
    die 4 "uv bootstrap failed"
fi

# 8/12  Install the CLI
if [ "${LOGION_INSTALL_SKILL_ONLY}" = "1" ]; then
    # --skill-only: skip install_cli, just verify logion is on PATH
    step_info "Verifying logion is on PATH (--skill-only)"
    if ! command -v logion >/dev/null 2>&1; then
        die 1 "logion not found on PATH (required for --skill-only)"
    fi
else
    step_info "Installing logion CLI"
    if ! install_cli; then
        die 8 "CLI installation failed"
    fi
fi

# 9/12  Install the companion skill bundle
if [ "${LOGION_INSTALL_CLI_ONLY}" = "1" ]; then
    # --cli-only: skip install_companion
    step_info "Skipping companion (--cli-only)"
else
    step_info "Installing logion companion"
    if ! install_companion; then
        die 8 "Companion installation failed"
    fi
fi

# 10/12 Update PATH in shell config
step_info "Updating PATH"
if ! update_path; then
    die 1 "PATH update failed"
fi

# 11/12 Verify the installation
step_info "Verifying installation"
if ! verify_install; then
    die 9 "Installation verification failed"
fi

# 12/12 Print next steps
step_info "Next steps"
if ! print_next_steps; then
    die 1 "Failed to print next steps"
fi