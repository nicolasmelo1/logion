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

@test "install_companion registers companion with required skill metadata" {
    INSTALL_TMPDIR="${WORK}"
    mkdir -p "${WORK}/bin"
    cat > "${WORK}/manifest.json" <<JSON
{
  "packages": {
    "logion-companion": {
      "bundle": {
        "url": "file://${WORK}/bundle.tar.gz"
      },
      "tag": "logion-companion-v0.1.0",
      "version": "0.1.0"
    }
  }
}
JSON
    _make_prefixed_bundle
    cat > "${WORK}/bin/curl" <<CURL
#!/bin/sh
cp "${WORK}/bundle.tar.gz" "\$4"
CURL
    cat > "${WORK}/bin/logion" <<LOGION
#!/bin/sh
printf 'LOGION_AUTO_UPDATE=%s\n' "\${LOGION_AUTO_UPDATE:-}" >> "${WORK}/logion-calls.log"
printf '%s\n' "\$*" >> "${WORK}/logion-calls.log"
exit 0
LOGION
    chmod +x "${WORK}/bin/curl" "${WORK}/bin/logion"

    HOME="${WORK}/home" PATH="${WORK}/bin:${PATH}" run install_companion "0.1.0" "logion-cli-v0.1.0"

    [ "$status" -eq 0 ]
    grep -F "LOGION_AUTO_UPDATE=0" "${WORK}/logion-calls.log"
    grep -F "skills install --source ${WORK}/home/.logion/installed/logion-marketplace-companion/0.1.0 --course-id logion-marketplace-companion --version-id 0.1.0 --title Logion Marketplace Companion --force" "${WORK}/logion-calls.log"
}

@test "install_cli clears existing pipx venv before reinstalling" {
    mkdir -p "${WORK}/bin"
    cat > "${WORK}/bin/pipx" <<PIPX
#!/bin/sh
printf '%s\n' "\$*" >> "${WORK}/pipx-calls.log"
exit 0
PIPX
    chmod +x "${WORK}/bin/pipx"

    LOGION_INSTALL_RETRIES=1
    PATH="${WORK}/bin:${PATH}" run install_cli "0.1.4" "pipx"

    [ "$status" -eq 0 ]
    sed -n '1p' "${WORK}/pipx-calls.log" | grep -F "uninstall logion-cli"
    sed -n '2p' "${WORK}/pipx-calls.log" | grep -F "install --force logion-cli==0.1.4 --pip-args=--no-cache-dir"
}

@test "install_cli retries transient pipx resolver misses" {
    mkdir -p "${WORK}/bin"
    cat > "${WORK}/bin/pipx" <<PIPX
#!/bin/sh
printf '%s\n' "\$*" >> "${WORK}/pipx-calls.log"
if [ "\$1" = "install" ]; then
    count_file="${WORK}/pipx-install-count"
    count=0
    [ -f "\$count_file" ] && count="\$(cat "\$count_file")"
    count="\$((count + 1))"
    printf '%s\n' "\$count" > "\$count_file"
    [ "\$count" -lt 3 ] && exit 1
fi
exit 0
PIPX
    cat > "${WORK}/bin/sleep" <<'SLEEP'
#!/bin/sh
exit 0
SLEEP
    chmod +x "${WORK}/bin/pipx" "${WORK}/bin/sleep"

    LOGION_INSTALL_RETRIES=3
    PATH="${WORK}/bin:${PATH}" run install_cli "0.1.7" "pipx"

    [ "$status" -eq 0 ]
    [ "$(cat "${WORK}/pipx-install-count")" -eq 3 ]
    grep -F "retrying" <<<"$output"
}
