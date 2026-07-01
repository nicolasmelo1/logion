#!/bin/sh
# SPDX-License-Identifier: MIT
#
# harness.sh — Bats-compatible test harness for install.sh.
#
# Provides fake binaries, fake manifests, and file:// URLs so the
# installer can be exercised without network access.

# ── Global state ──────────────────────────────────────────────────────────

HARNESS_TMPDIR=""
HARNESS_BIN_DIR=""
HARNESS_MANIFEST_DIR=""
HARNESS_RELEASE_DIR=""
HARNESS_ORIG_PATH=""

# ── cleanup ────────────────────────────────────────────────────────────────

cleanup() {
    if [ -n "${HARNESS_TMPDIR}" ] && [ -d "${HARNESS_TMPDIR}" ]; then
        rm -rf "${HARNESS_TMPDIR}"
    fi
    if [ -n "${HARNESS_ORIG_PATH}" ]; then
        PATH="${HARNESS_ORIG_PATH}"
        export PATH
    fi
    unset LOGION_INSTALL_BASE_URL 2>/dev/null || true
    unset LOGION_INSTALL_MANIFEST_URL 2>/dev/null || true
    unset LOGION_INSTALL_QUIET 2>/dev/null || true
    unset LOGION_INSTALL_DRY_RUN 2>/dev/null || true
    unset LOGION_INSTALL_CLI_ONLY 2>/dev/null || true
    unset LOGION_INSTALL_SKILL_ONLY 2>/dev/null || true
    unset LOGION_INSTALL_NO_MODIFY_PATH 2>/dev/null || true
    unset LOGION_INSTALL_CHANNEL 2>/dev/null || true
    unset LOGION_INSTALL_VERSION 2>/dev/null || true
}

# ── setup_fake_release ─────────────────────────────────────────────────────
#
# Usage: setup_fake_release [--corrupt-wheel]
#
# Creates the temp directory tree, writes a fake manifest, and
# generates placeholder release tarballs.  Exports file:// URLs as
# LOGION_INSTALL_BASE_URL and LOGION_INSTALL_MANIFEST_URL.
#
# --corrupt-wheel  writes a wheel whose sha256 does NOT match the
#                  manifest entry, so validate_manifest / fetch errors
#                  can be tested.

setup_fake_release() {
    HARNESS_ORIG_PATH="${PATH}"
    HARNESS_TMPDIR="$(mktemp -d)"
    HARNESS_BIN_DIR="${HARNESS_TMPDIR}/bin"
    HARNESS_MANIFEST_DIR="${HARNESS_TMPDIR}/manifest"
    HARNESS_RELEASE_DIR="${HARNESS_TMPDIR}/release"

    mkdir -p "${HARNESS_BIN_DIR}" "${HARNESS_MANIFEST_DIR}" "${HARNESS_RELEASE_DIR}"

    _corrupt_wheel=0
    for _arg in "$@"; do
        case "${_arg}" in
            --corrupt-wheel) _corrupt_wheel=1 ;;
        esac
    done

    # ── Fake wheel ────────────────────────────────────────────────────────
    _wheel_name="logion_cli-0.1.0-py3-none-any.whl"
    _wheel_path="${HARNESS_RELEASE_DIR}/${_wheel_name}"
    printf 'fake-wheel-content' > "${_wheel_path}"

    if [ "${_corrupt_wheel}" = "1" ]; then
        # Overwrite with different content so the sha256 diverges
        printf 'CORRUPTED-wheel-content' > "${_wheel_path}"
    fi

    _wheel_sha256=$(_sha256_file "${_wheel_path}")

    # ── Fake sdist ─────────────────────────────────────────────────────────
    _sdist_name="logion-cli-0.1.0.tar.gz"
    _sdist_path="${HARNESS_RELEASE_DIR}/${_sdist_name}"
    printf 'fake-sdist-content' > "${_sdist_path}"
    _sdist_sha256=$(_sha256_file "${_sdist_path}")

    # ── Fake companion bundle ──────────────────────────────────────────────
    _bundle_name="logion-marketplace-companion-0.1.0.tar.gz"
    _bundle_path="${HARNESS_RELEASE_DIR}/${_bundle_name}"
    printf 'fake-bundle-content' > "${_bundle_path}"
    _bundle_sha256=$(_sha256_file "${_bundle_path}")

    # ── Fake skill markdown ───────────────────────────────────────────────
    _skill_md_name="logion-companion-skill-0.1.0.md"
    _skill_md_path="${HARNESS_RELEASE_DIR}/${_skill_md_name}"
    printf '# Logion Companion Skill\n' > "${_skill_md_path}"
    _skill_md_sha256=$(_sha256_file "${_skill_md_path}")

    # If corrupt mode, put the correct sha256 in the manifest but
    # the wrong content in the file — we already did that above.
    # Re-compute the manifest sha256 from original (non-corrupt) content
    if [ "${_corrupt_wheel}" = "1" ]; then
        # We need the "expected" sha256 (matching the manifest) to differ
        # from the actual file sha256.  Use a fixed bogus hash in the manifest.
        _manifest_wheel_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    else
        _manifest_wheel_sha256="${_wheel_sha256}"
    fi

    # ── Write manifest ────────────────────────────────────────────────────
    _manifest_path="${HARNESS_MANIFEST_DIR}/manifest-stable.json"
    cat > "${_manifest_path}" <<MANIFEST_EOF
{
  "schema_version": 1,
  "generated_at": "2026-01-01T00:00:00+00:00",
  "git_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "channel": "stable",
  "packages": {
    "logion-cli": {
      "version": "0.1.0",
      "tag": "logion-cli-v0.1.0",
      "minimum_python": "3.12",
      "pypi_name": "logion-cli",
      "npm_name": "@logionsh/cli",
      "minimum_client": "0.1.0",
      "wheel": {
        "url": "file://${_wheel_path}",
        "sha256": "${_manifest_wheel_sha256}"
      },
      "sdist": {
        "url": "file://${_sdist_path}",
        "sha256": "${_sdist_sha256}"
      }
    },
    "logion-client": {
      "version": "0.1.0",
      "tag": "logion-client-v0.1.0",
      "minimum_python": "3.12",
      "pypi_name": "logion-client"
    },
    "logion-companion": {
      "version": "0.1.0",
      "tag": "logion-companion-v0.1.0",
      "minimum_python": "3.12",
      "minimum_cli": "0.1.0",
      "course_id": "logion-marketplace-companion",
      "bundle": {
        "url": "file://${_bundle_path}",
        "sha256": "${_bundle_sha256}"
      },
      "skill_md": {
        "url": "file://${_skill_md_path}",
        "sha256": "${_skill_md_sha256}"
      }
    }
  }
}
MANIFEST_EOF

    # Also create a latest manifest (identical packages, different channel)
    _manifest_latest_path="${HARNESS_MANIFEST_DIR}/manifest-latest.json"
    sed 's/"channel": "stable"/"channel": "latest"/' "${_manifest_path}" > "${_manifest_latest_path}"

    # ── Export file:// URLs ───────────────────────────────────────────────
    LOGION_INSTALL_BASE_URL="file://${HARNESS_RELEASE_DIR}"
    LOGION_INSTALL_MANIFEST_URL="file://${_manifest_path}"
    export LOGION_INSTALL_BASE_URL LOGION_INSTALL_MANIFEST_URL

    # Prepend the fake bin dir so our stubs are found first
    PATH="${HARNESS_BIN_DIR}:${PATH}"
    export PATH
}

# ── Helper: sha256 a file (portable) ───────────────────────────────────────

_sha256_file() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d' ' -f1
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    else
        echo "ERROR: Neither shasum nor sha256sum available" >&2
        return 1
    fi
}

# ── fake_python ────────────────────────────────────────────────────────────
#
# Usage: fake_python --version <version>
#
# Creates a "python3" script in HARNESS_BIN_DIR that prints the
# supplied version string and exits 0.

fake_python() {
    _py_version="3.12.0"
    if [ "$1" = "--version" ]; then
        _py_version="$2"
    fi
    cat > "${HARNESS_BIN_DIR}/python3" <<PYTHON_EOF
#!/bin/sh
printf 'Python ${_py_version}\n'
exit 0
PYTHON_EOF
    chmod +x "${HARNESS_BIN_DIR}/python3"
}

# ── fake_pipx ─────────────────────────────────────────────────────────────
#
# Creates a "pipx" script that records invocations to
# HARNESS_TMPDIR/pipx-calls.log and pretends to succeed.

fake_pipx() {
    cat > "${HARNESS_BIN_DIR}/pipx" <<PIPX_EOF
#!/bin/sh
echo "\$@" >> "${HARNESS_TMPDIR}/pipx-calls.log"
exit 0
PIPX_EOF
    chmod +x "${HARNESS_BIN_DIR}/pipx"
}

# ── fake_uv ────────────────────────────────────────────────────────────────
#
# Creates a "uv" script that records invocations to
# HARNESS_TMPDIR/uv-calls.log and pretends to succeed.

fake_uv() {
    cat > "${HARNESS_BIN_DIR}/uv" <<UV_EOF
#!/bin/sh
echo "\$@" >> "${HARNESS_TMPDIR}/uv-calls.log"
exit 0
UV_EOF
    chmod +x "${HARNESS_BIN_DIR}/uv"
}

# ── fake_logion_preinstalled ───────────────────────────────────────────────
#
# Creates a "logion" script in HARNESS_BIN_DIR that prints a
# version string (default 0.1.0).

fake_logion_preinstalled() {
    _lg_version="${1:-0.1.0}"
    cat > "${HARNESS_BIN_DIR}/logion" <<LG_EOF
#!/bin/sh
if [ "\$1" = "--version" ] || [ "\$1" = "version" ]; then
    printf 'logion ${_lg_version}\n'
else
    printf 'logion (fake)\n'
fi
exit 0
LG_EOF
    chmod +x "${HARNESS_BIN_DIR}/logion"
}

# ── install_fake_logion_at ─────────────────────────────────────────────────
#
# Usage: install_fake_logion_at <version>
#
# Creates a "logion" script that reports the given version,
# simulating what install_cli leaves behind.

install_fake_logion_at() {
    _installed_version="$1"
    fake_logion_preinstalled "${_installed_version}"
}

# ── fake_logion_version_output ─────────────────────────────────────────────
#
# Prints the expected stdout of `logion --version` for the
# given version. Useful for assertions.

fake_logion_version_output() {
    _v="${1:-0.1.0}"
    printf 'logion %s\n' "${_v}"
}