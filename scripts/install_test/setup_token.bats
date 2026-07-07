#!/usr/bin/env bats
# SPDX-License-Identifier: MIT
#
# setup_token.bats — tests for --setup-token flag in install_lib.sh

setup() {
    load ./harness.sh
    setup_fake_release
    # Source the installer library under test
    # shellcheck source=/dev/null
    source "${BATS_TEST_DIRNAME}/../install_lib.sh"
}

teardown() {
    cleanup
}

# ── Argument parsing ───────────────────────────────────────────────────

@test "--setup-token is parsed and exported to INSTALL_SETUP_TOKEN" {
    parse_args --setup-token st_abc123def
    [ "${INSTALL_SETUP_TOKEN}" = "st_abc123def" ]
}

@test "--setup-token=VALUE form is parsed" {
    parse_args --setup-token=st_xyz789
    [ "${INSTALL_SETUP_TOKEN}" = "st_xyz789" ]
}

@test "INSTALL_SETUP_TOKEN defaults to empty" {
    parse_args
    [ "${INSTALL_SETUP_TOKEN}" = "" ]
}

@test "--setup-token requires a value" {
    # --setup-token as the last arg without a value should fail
    run parse_args --setup-token
    [ "$status" -ne 0 ]
}

# ── Token masking in output ────────────────────────────────────────────

@test "raw token is absent from step output (only prefix visible)" {
    # Use DryRun so we don't actually install anything
    parse_args --dry-run --setup-token st_supersecret123
    # Capture the step banner for onboarding — the raw token must not appear
    run run_onboarding
    # The full raw token must NOT be in the output
    ! echo "$output" | grep -q "st_supersecret123"
    # But the 3-char prefix IS in the output (masked form: st_***)
    echo "$output" | grep -q "st_\*"
}

# ── Non-interactive bypass ────────────────────────────────────────────

@test "onboarding runs with --setup-token even in non-interactive mode" {
    # Create a fake logion binary that records invocation
    cat > "${HARNESS_BIN_DIR}/logion" <<FAKE_LOGION
#!/bin/sh
echo "LOGION_INVOKED_WITH: \$*" >> "${HARNESS_TMPDIR}/onboarding.log"
exit 0
FAKE_LOGION
    chmod +x "${HARNESS_BIN_DIR}/logion"

    # Simulate non-interactive environment
    export CI=true
    parse_args --setup-token st_test123

    run run_onboarding
    [ "$status" -eq 0 ]

    # Verify logion was called with --setup-token
    grep -q -- "--setup-token st_test123" "${HARNESS_TMPDIR}/onboarding.log"
}

@test "onboarding skips in non-interactive mode without --setup-token" {
    # Create a fake logion binary that should NOT be invoked
    cat > "${HARNESS_BIN_DIR}/logion" <<FAKE_LOGION
#!/bin/sh
echo "SHOULD_NOT_BE_CALLED" >> "${HARNESS_TMPDIR}/onboarding.log"
exit 0
FAKE_LOGION
    chmod +x "${HARNESS_BIN_DIR}/logion"

    # Simulate non-interactive environment
    export CI=true
    parse_args

    run run_onboarding
    # Should skip (not fail)
    [ "$status" -eq 0 ]
    # logion should NOT have been called
    [ ! -f "${HARNESS_TMPDIR}/onboarding.log" ]
}

# ── Help text ──────────────────────────────────────────────────────────

@test "--setup-token appears in help output" {
    run parse_args --help
    [ "$status" -eq 0 ]
    echo "$output" | grep -q -- "--setup-token"
}