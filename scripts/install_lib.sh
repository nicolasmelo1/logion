#!/bin/sh
# SPDX-License-Identifier: MIT
#
# install_lib.sh — POSIX shell installer library for Logion curl installer.
# Sourced by install.sh and the test harness. Not intended to be executed
# directly.

# --- Logging helpers -------------------------------------------------------
# All functions take simple arguments (no printf-style format strings).
# Callers must interpolate variables before passing them.

die() {
    _code="$1"
    shift
    printf 'logion: error: %s\n' "$*" >&2
    exit "$_code"
}

info() {
    [ "$INSTALL_QUIET" = 1 ] && return 0
    printf '%s\n' "$*"
}

warn() {
    printf 'logion: warning: %s\n' "$*" >&2
}

# --- Platform detection -----------------------------------------------------

detect_platform() {
    _kernel="$(uname -s 2>/dev/null)"
    case "$_kernel" in
        Linux)  OS=linux  ;;
        Darwin) OS=darwin ;;
        *)      OS=other  ;;
    esac
    export OS

    _machine="$(uname -m 2>/dev/null)"
    case "$_machine" in
        x86_64|amd64)   ARCH=x86_64 ;;
        aarch64|arm64)  ARCH=arm64  ;;
        *)              ARCH=other  ;;
    esac
    export ARCH

    LIBC=gnu
    if [ "$OS" = "linux" ]; then
        _ldd_out="$(ldd --version 2>&1 || true)"
        case "$_ldd_out" in
            *musl*) LIBC=musl ;;
            *GNU*|*glibc*) LIBC=gnu ;;
            *)      LIBC=gnu ;;
        esac
    fi
    export LIBC

    if [ "$OS" = "other" ] || [ "$ARCH" = "other" ]; then
        die 3 "Unsupported platform: OS=$OS ARCH=$ARCH"
    fi

    return 0
}

# --- Prerequisite tools -----------------------------------------------------

require_tools() {
    _missing=0
    for _tool in curl tar mktemp; do
        if ! command -v "$_tool" >/dev/null 2>&1; then
            warn "Missing required tool: $_tool"
            _missing=1
        fi
    done

    # sha256sum (Linux) or shasum (macOS)
    if command -v sha256sum >/dev/null 2>&1; then
        : # available
    elif command -v shasum >/dev/null 2>&1; then
        : # available
    else
        warn "Missing required tool: sha256sum (or shasum)"
        _missing=1
    fi

    if [ "$_missing" = 1 ]; then
        _hint=""
        case "$OS" in
            linux)
                if command -v apt >/dev/null 2>&1; then
                    _hint="Try: sudo apt install -y curl ca-certificates"
                elif command -v apk >/dev/null 2>&1; then
                    _hint="Try: sudo apk add curl coreutils"
                else
                    _hint="Install curl, sha256sum, and tar via your package manager."
                fi
                ;;
            darwin)
                _hint="Try: brew install curl coreutils"
                ;;
            *)
                _hint="Install curl, a sha256 tool, and tar for your platform."
                ;;
        esac
        die 4 "Missing prerequisite tools. $_hint"
    fi

    return 0
}

# --- Argument parsing -------------------------------------------------------

parse_args() {
    # Defaults
    INSTALL_CHANNEL=stable
    INSTALL_VERSION=""
    INSTALL_CLI_ONLY=0
    INSTALL_SKILL_ONLY=0
    INSTALL_PREFIX=""
    INSTALL_PREFIX_EXPLICIT=0
    INSTALL_INSTALLER=""
    INSTALL_DRY_RUN=0
    INSTALL_NO_MODIFY_PATH=0
    INSTALL_NO_ONBOARDING=0
    INSTALL_ONBOARDING_FAILED=0
    INSTALL_QUIET=0
    INSTALL_VERBOSE=0

    while [ $# -gt 0 ]; do
        case "$1" in
            --channel)
                shift
                [ $# -gt 0 ] || die 2 "--channel requires an argument"
                INSTALL_CHANNEL="$1"
                shift
                ;;
            --channel=*)
                INSTALL_CHANNEL="${1#--channel=}"
                shift
                ;;
            --version)
                shift
                [ $# -gt 0 ] || die 2 "--version requires an argument"
                INSTALL_VERSION="$(printf '%s' "$1" | sed 's/^v//')"
                shift
                ;;
            --version=*)
                INSTALL_VERSION="$(printf '%s' "${1#--version=}" | sed 's/^v//')"
                shift
                ;;
            --cli-only)
                INSTALL_CLI_ONLY=1
                shift
                ;;
            --skill-only)
                INSTALL_SKILL_ONLY=1
                shift
                ;;
            --prefix)
                shift
                [ $# -gt 0 ] || die 2 "--prefix requires an argument"
                INSTALL_PREFIX="$1"
                INSTALL_PREFIX_EXPLICIT=1
                shift
                ;;
            --prefix=*)
                INSTALL_PREFIX="${1#--prefix=}"
                INSTALL_PREFIX_EXPLICIT=1
                shift
                ;;
            --installer)
                shift
                [ $# -gt 0 ] || die 2 "--installer requires an argument"
                case "$1" in
                    pipx|uv|venv) INSTALL_INSTALLER="$1" ;;
                    *) die 2 "Invalid installer: $1 (choose pipx, uv, or venv)" ;;
                esac
                shift
                ;;
            --installer=*)
                _val="${1#--installer=}"
                case "$_val" in
                    pipx|uv|venv) INSTALL_INSTALLER="$_val" ;;
                    *) die 2 "Invalid installer: $_val (choose pipx, uv, or venv)" ;;
                esac
                shift
                ;;
            --dry-run)
                INSTALL_DRY_RUN=1
                shift
                ;;
            --no-modify-path)
                INSTALL_NO_MODIFY_PATH=1
                shift
                ;;
            --no-onboarding)
                INSTALL_NO_ONBOARDING=1
                shift
                ;;
            --quiet|-q)
                INSTALL_QUIET=1
                shift
                ;;
            --verbose|-v)
                INSTALL_VERBOSE=1
                shift
                ;;
            --help|-h)
                info "Usage: install.sh [options]"
                info ""
                info "Options:"
                info "  --channel <c>      Release channel (default: stable)"
                info "  --version <v>      Specific version to install"
                info "  --cli-only         Install only the CLI package"
                info "  --skill-only       Install only the companion skill"
                info "  --prefix <dir>     Installation prefix (default: \$HOME/.local or /usr/local)"
                info "  --installer <i>    Installer backend: pipx, uv, venv"
                info "  --dry-run          Show what would be done without doing it"
                info "  --no-modify-path   Do not modify shell RC files"
                info "  --no-onboarding    Do not run 'logion onboarding' at the end"
                info "  --quiet            Suppress informational output"
                info "  --verbose          Show extra detail"
                info "  --help             Show this help"
                exit 0
                ;;
            *)
                die 2 "Unknown argument: $1"
                ;;
        esac
    done

    # Mutual exclusivity: --cli-only and --skill-only
    if [ "$INSTALL_CLI_ONLY" = 1 ] && [ "$INSTALL_SKILL_ONLY" = 1 ]; then
        die 2 "--cli-only and --skill-only are mutually exclusive"
    fi

    # Default prefix
    if [ -z "$INSTALL_PREFIX" ]; then
        if [ "$(id -u)" = 0 ]; then
            INSTALL_PREFIX="/usr/local"
        else
            INSTALL_PREFIX="$HOME/.local"
        fi
    fi

    # Default installer
    if [ -z "$INSTALL_INSTALLER" ]; then
        if command -v pipx >/dev/null 2>&1; then
            INSTALL_INSTALLER="pipx"
        elif command -v uv >/dev/null 2>&1; then
            INSTALL_INSTALLER="uv"
        else
            INSTALL_INSTALLER="venv"
        fi
    fi

    export INSTALL_CHANNEL INSTALL_VERSION INSTALL_CLI_ONLY INSTALL_SKILL_ONLY
    export INSTALL_PREFIX INSTALL_PREFIX_EXPLICIT INSTALL_INSTALLER INSTALL_DRY_RUN
    export INSTALL_NO_MODIFY_PATH INSTALL_NO_ONBOARDING INSTALL_ONBOARDING_FAILED INSTALL_QUIET INSTALL_VERBOSE
}

# --- resolve_url helper -----------------------------------------------------

# Translate release:// URLs to real download URLs.
# release://<asset> → ${LOGION_INSTALL_BASE_URL}/<asset> (dev/test)
#   or https://github.com/nicolasmelo1/logion/releases/download/<tag>/<asset> (prod)
resolve_url() {
    _raw_url="$1"
    _tag="$2"

    case "$_raw_url" in
        release://*)
            _asset="${_raw_url#release://}"
            if [ -n "${LOGION_INSTALL_BASE_URL:-}" ]; then
                printf '%s/%s' "$LOGION_INSTALL_BASE_URL" "$_asset"
            else
                printf 'https://github.com/nicolasmelo1/logion/releases/download/%s/%s' "$_tag" "$_asset"
            fi
            ;;
        *)
            # Already a full URL (file://, https://, etc.)
            printf '%s' "$_raw_url"
            ;;
    esac
}

# --- Manifest fetching -----------------------------------------------------

fetch_manifest() {
    _manifest_url="${LOGION_INSTALL_MANIFEST_URL:-https://logion.sh/releases/manifest-${INSTALL_CHANNEL}.json}"

    if [ -n "$INSTALL_VERSION" ]; then
        _tag="logion-cli-v${INSTALL_VERSION}"
        _tag_url="https://logion.sh/releases/manifest-${INSTALL_CHANNEL}.json"
        # When --version is given, fetch the manifest from the version-specific tag
        _tag_url="https://github.com/nicolasmelo1/logion/releases/download/${_tag}/manifest-${INSTALL_CHANNEL}.json"
        info "Fetching manifest for version $INSTALL_VERSION ..."
        if ! curl -fsSL "$_tag_url" -o "$INSTALL_TMPDIR/manifest.json" 2>/dev/null; then
            die 5 "Failed to download manifest for version $INSTALL_VERSION from $_tag_url"
        fi
    else
        info "Fetching $INSTALL_CHANNEL manifest ..."
        if ! curl -fsSL "$_manifest_url" -o "$INSTALL_TMPDIR/manifest.json" 2>/dev/null; then
            die 5 "Failed to download manifest from $_manifest_url"
        fi
    fi

    return 0
}

# --- Manifest field parser --------------------------------------------------

manifest_get_field() {
    _file="$1"
    _path="$2"

    if command -v jq >/dev/null 2>&1; then
        # jq requires quoting keys with hyphens:
        # .packages.logion-cli.version → .packages["logion-cli"].version
        _jq_path="$(printf '%s' "$_path" | sed 's/\.\([a-zA-Z0-9_]*-[a-zA-Z0-9_-]*\)/.["\1"]/g')"
        jq -r "$_jq_path" "$_file" 2>/dev/null
        return $?
    fi

    _json_python=""
    if command -v python3 >/dev/null 2>&1; then
        _json_python=python3
    elif command -v python >/dev/null 2>&1; then
        _json_python=python
    fi

    if [ -n "$_json_python" ]; then
        # Convert jq-style path to python dict navigation
        # '.packages."logion-cli".version' → d["packages"]["logion-cli"]["version"]
        _py_path="$(printf '%s' "$_path" | "$_json_python" -c "
import sys, re, json
p = sys.stdin.read().strip()
if p.startswith('.'):
    p = p[1:]
# Split on dots respecting quoted segments
parts = []
current = ''
in_quote = False
quote_char = ''
i = 0
while i < len(p):
    c = p[i]
    if in_quote:
        if c == quote_char:
            in_quote = False
            parts.append(current)
            current = ''
            # skip next dot
            if i + 1 < len(p) and p[i+1] == '.':
                i += 1
        else:
            current += c
    elif c in ('\"', \"'\"):
        in_quote = True
        quote_char = c
    elif c == '.':
        if current:
            parts.append(current)
            current = ''
    else:
        current += c
    i += 1
if current:
    parts.append(current)
print(json.dumps(parts))
" 2>/dev/null)"
        "$_json_python" -c "
import json, sys
d = json.load(open(sys.argv[1]))
result = d
for key in json.loads(sys.argv[2]):
    result = result[key]
if result is None:
    print('null')
else:
    print(result)
" "$_file" "$_py_path" 2>/dev/null
        return $?
    fi

    # awk fallback: simple single-level field extraction
    # Best-effort for dot-notation paths on deterministic JSON
    _clean_path="$(printf '%s' "$_path" | sed 's/^\.//')"
    _field_name="$(printf '%s' "$_clean_path" | sed 's/\./,/g; s/"//g')"
    awk -v path="$_field_name" '
    BEGIN { depth = 0; target_depth = split(path, parts, ",") }
    /{/ { depth++ }
    /}/ { depth-- }
    {
        for (i = 1; i <= target_depth; i++) {
            key = parts[i]
            if ($0 ~ "\"" key "\"" && depth == i) {
                # Found the key, next line or same line may have value
            }
        }
    }
    ' "$_file" 2>/dev/null
    return $?
}

# --- Manifest validation ----------------------------------------------------

# validate_manifest <file>
validate_manifest() {
    _mfile="${1:-$INSTALL_TMPDIR/manifest.json}"

    if [ ! -f "$_mfile" ]; then
        die 5 "Manifest file not found: $_mfile"
    fi

    _sv="$(manifest_get_field "$_mfile" '.schema_version')"
    if [ -z "$_sv" ] || [ "$_sv" = "null" ]; then
        die 5 "Manifest missing required field: schema_version"
    fi

    # Use bracket notation for keys with hyphens (jq-compatible)
    _cv="$(manifest_get_field "$_mfile" '.packages["logion-cli"].version')"
    if [ -z "$_cv" ] || [ "$_cv" = "null" ]; then
        die 5 "Manifest missing required field: packages.logion-cli.version"
    fi

    info "Manifest validated: schema_version=$_sv cli_version=$_cv"
}

# --- Python detection -------------------------------------------------------

check_python() {
    _py_found=""
    _py_major=0
    _py_minor=0

    # If LOGION_INSTALL_PYTHON is set, use it directly
    if [ -n "${LOGION_INSTALL_PYTHON:-}" ] && command -v "${LOGION_INSTALL_PYTHON}" >/dev/null 2>&1; then
        _py_found="${LOGION_INSTALL_PYTHON}"
        printf '%s\n' "$_py_found"
        return 0
    fi

    for _py_cmd in python3 python py; do
        if command -v "$_py_cmd" >/dev/null 2>&1; then
            _ver="$("$_py_cmd" --version 2>/dev/null | head -1)"
            # Parse "Python X.Y.Z"
            _py_major="$(printf '%s' "$_ver" | sed 's/Python \([0-9]*\)\..*/\1/' 2>/dev/null)"
            _py_minor="$(printf '%s' "$_ver" | sed 's/Python [0-9]*\.\([0-9]*\).*/\1/' 2>/dev/null)"
            _py_major="${_py_major:-0}"
            _py_minor="${_py_minor:-0}"

            if [ "$_py_major" -gt 3 ] || { [ "$_py_major" -eq 3 ] && [ "$_py_minor" -ge 12 ]; }; then
                _py_found="$(command -v "$_py_cmd")"
                break
            fi
        fi
    done

    if [ -n "$_py_found" ]; then
        printf '%s\n' "$_py_found"
        return 0
    fi

    _hint=""
    case "$OS" in
        linux)
            if command -v apt >/dev/null 2>&1; then
                _hint="Try: sudo apt install python3.12"
            elif command -v apk >/dev/null 2>&1; then
                _hint="Try: sudo apk add python3"
            else
                _hint="Install Python >= 3.12 via your package manager."
            fi
            ;;
        darwin)
            _hint="Try: brew install python@3.12"
            ;;
        *)
            _hint="Install Python >= 3.12 for your platform."
            ;;
    esac
    die 7 "Python >= 3.12 not found. $_hint"
}

# --- Bootstrap uv -----------------------------------------------------------

bootstrap_uv() {
    # If the requested installer is uv and pipx is present but uv is not,
    # we must still install uv. Only short-circuit if the chosen installer
    # can already run.
    if [ "$INSTALL_INSTALLER" = "pipx" ] && command -v pipx >/dev/null 2>&1; then
        return 0
    fi
    if [ "$INSTALL_INSTALLER" = "uv" ] && command -v uv >/dev/null 2>&1; then
        return 0
    fi
    # For venv backend, we still need uv/pipx for the install step
    if command -v pipx >/dev/null 2>&1 && command -v uv >/dev/null 2>&1; then
        return 0
    fi

    # Need to install uv
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi

    info "Installing uv (Python package manager) ..."
    if ! curl -fsSL https://astral.sh/uv/install.sh | sh; then
        die 8 "Failed to bootstrap uv"
    fi

    # uv installer adds to $HOME/.local/bin; ensure it is on PATH
    case ":$PATH:" in
        *:"$HOME/.local/bin":*) ;;
        *) PATH="$HOME/.local/bin:$PATH"; export PATH ;;
    esac

    if ! command -v uv >/dev/null 2>&1; then
        die 8 "uv was installed but cannot be found on PATH"
    fi

    info "uv installed successfully"
}

# --- SHA-256 verification ---------------------------------------------------

sha256_verify() {
    _file="$1"
    _expected="$2"

    if [ "${LOGION_INSTALL_SKIP_VERIFY:-0}" = 1 ]; then
        warn "SHA-256 verification skipped (LOGION_INSTALL_SKIP_VERIFY=1)"
        return 0
    fi

    _actual=""

    if command -v sha256sum >/dev/null 2>&1; then
        _actual="$(sha256sum "$_file" | awk '{print $1}')"
    elif command -v shasum >/dev/null 2>&1; then
        _actual="$(shasum -a 256 "$_file" | awk '{print $1}')"
    else
        die 4 "No sha256 tool available"
    fi

    if [ "$_actual" != "$_expected" ]; then
        die 6 "SHA-256 mismatch for $_file: expected $_expected, got $_actual"
    fi

    info "SHA-256 verified: $_file"
}

# --- CLI installation -------------------------------------------------------

# install_cli <version> <installer>
install_cli() {
    _version="$1"
    _installer="$2"

    info "Installing logion-cli==$_version via $_installer ..."

    if [ "$INSTALL_DRY_RUN" = 1 ]; then
        info "[dry-run] Would install logion-cli==$_version via $_installer"
        return 0
    fi

    case "$_installer" in
        pipx)
            if ! command -v pipx >/dev/null 2>&1; then
                die 4 "pipx not found"
            fi
            if ! pipx install --force "logion-cli==$_version" --pip-args="--no-cache-dir"; then
                die 8 "pipx install logion-cli==$_version failed"
            fi
            ;;
        uv)
            if ! command -v uv >/dev/null 2>&1; then
                die 4 "uv not found"
            fi
            if ! uv tool install "logion-cli==$_version" --force; then
                die 8 "uv tool install logion-cli==$_version failed"
            fi
            ;;
        venv)
            _python="$(check_python)"
            _venv_dir="$INSTALL_PREFIX/logion-cli"
            mkdir -p "$_venv_dir" 2>/dev/null || true
            if ! "$_python" -m venv "$_venv_dir"; then
                die 8 "Failed to create virtual environment at $_venv_dir"
            fi
            # shellcheck disable=SC1091
            if ! . "$_venv_dir/bin/activate"; then
                die 8 "Failed to activate virtual environment at $_venv_dir"
            fi
            if ! pip install --no-cache-dir "logion-cli==$_version"; then
                die 8 "pip install logion-cli==$_version failed"
            fi
            deactivate 2>/dev/null || true
            # Create wrapper script
            _bindir="$INSTALL_PREFIX/bin"
            mkdir -p "$_bindir" 2>/dev/null || true
            printf '#!/bin/sh\nexec "%s/bin/logion" "$@"\n' "$_venv_dir" > "$_bindir/logion"
            chmod +x "$_bindir/logion"
            ;;
        *)
            die 2 "Unknown installer: $_installer"
            ;;
    esac

    info "logion-cli==$_version installed successfully"
}

# --- Companion installation -------------------------------------------------

# install_companion <version> [<cli-tag>]
install_companion() {
    _version="$1"
    _cli_tag="${2:-logion-cli-v$_version}"
    _manifest="$INSTALL_TMPDIR/manifest.json"

    # Read companion bundle URL and sha256 from manifest under "logion-companion"
    _bundle_url="$(manifest_get_field "$_manifest" '.packages["logion-companion"].bundle.url')"
    _bundle_sha="$(manifest_get_field "$_manifest" '.packages["logion-companion"].bundle.sha256')"

    # Translate release:// URLs
    _bundle_url="$(resolve_url "$_bundle_url" "$_cli_tag")"

    if [ -z "$_bundle_url" ] || [ "$_bundle_url" = "null" ]; then
        # Construct tarball URL from known pattern
        _bundle_url="https://github.com/nicolasmelo1/logion/releases/download/$_cli_tag/logion-marketplace-companion-$_version.tar.gz"
    fi
    if [ -z "$_bundle_sha" ] || [ "$_bundle_sha" = "null" ]; then
        warn "No SHA-256 found in manifest for companion; verification will be skipped"
        _bundle_sha=""
    fi

    info "Installing logion-marketplace-companion==$_version ..."

    if [ "$INSTALL_DRY_RUN" = 1 ]; then
        info "[dry-run] Would download and install companion from $_bundle_url"
        return 0
    fi

    _dest_dir="$HOME/.logion/installed/logion-marketplace-companion/$_version"
    _tarball="$INSTALL_TMPDIR/companion.tar.gz"

    if ! curl -fsSL "$_bundle_url" -o "$_tarball"; then
        die 5 "Failed to download companion tarball from $_bundle_url"
    fi

    if [ -n "$_bundle_sha" ]; then
        sha256_verify "$_tarball" "$_bundle_sha"
    fi

    mkdir -p "$_dest_dir" 2>/dev/null || true
    if ! tar -xzf "$_tarball" -C "$_dest_dir"; then
        die 8 "Failed to extract companion tarball"
    fi

    # Register with logion CLI
    if command -v logion >/dev/null 2>&1; then
        if ! logion skills install --source "$_dest_dir"; then
            warn "logion skills install --source $_dest_dir failed (companion extracted but not registered)"
        fi
    else
        warn "logion CLI not on PATH; companion extracted to $_dest_dir but not registered"
    fi

    info "logion-marketplace-companion==$_version installed to $_dest_dir"
}

# --- PATH update ------------------------------------------------------------

update_path() {
    if [ "$INSTALL_NO_MODIFY_PATH" = 1 ]; then
        return 0
    fi

    # Skip for root unless prefix was explicitly given
    if [ "$(id -u)" = 0 ] && [ "$INSTALL_PREFIX_EXPLICIT" != 1 ]; then
        return 0
    fi

    # Use the custom prefix bin dir if --prefix was set, otherwise default
    if [ "$INSTALL_PREFIX_EXPLICIT" = 1 ]; then
        _bin_dir="$INSTALL_PREFIX/bin"
    else
        _bin_dir="$HOME/.local/bin"
    fi

    # shellcheck disable=SC2016  # intentional: literal $HOME and $PATH for rc file
    _path_line="export PATH=\"$_bin_dir:\$PATH\""
    _shell_name=""
    _rc_file=""

    # Detect current shell
    if [ -n "${ZSH_VERSION:-}" ]; then
        _shell_name="zsh"
    elif [ -n "${BASH_VERSION:-}" ]; then
        _shell_name="bash"
    fi

    # Also check $SHELL
    if [ -z "$_shell_name" ]; then
        case "${SHELL:-}" in
            */zsh)  _shell_name="zsh"  ;;
            */bash) _shell_name="bash" ;;
            */fish) _shell_name="fish" ;;
        esac
    fi

    # shellcheck disable=SC2016  # intentional: literal $HOME for fish rc file
    _fish_line="fish_add_path $_bin_dir"

    case "$_shell_name" in
        bash)
            _rc_file="$HOME/.bashrc"
            _add_line="$_path_line"
            ;;
        zsh)
            _rc_file="$HOME/.zshrc"
            _add_line="$_path_line"
            ;;
        fish)
            _rc_file="$HOME/.config/fish/config.fish"
            _add_line="$_fish_line"
            ;;
        *)
            # Cannot determine shell; warn and skip
            warn "Cannot determine shell type; manually add $_bin_dir to your PATH"
            return 0
            ;;
    esac

    # Check for idempotency
    if [ -f "$_rc_file" ] && grep -q "$_bin_dir" "$_rc_file" 2>/dev/null; then
        info "PATH entry already present in $_rc_file"
        return 0
    fi

    if [ "$INSTALL_DRY_RUN" = 1 ]; then
        info "[dry-run] Would add PATH line to $_rc_file"
        return 0
    fi

    # Ensure directory exists (for fish)
    _rc_dir="$(dirname "$_rc_file")"
    if [ ! -d "$_rc_dir" ]; then
        mkdir -p "$_rc_dir" 2>/dev/null || true
    fi

    printf '\n%s\n' "$_add_line" >> "$_rc_file"
    info "Added PATH entry to $_rc_file"
}

# --- Installation verification ----------------------------------------------

# verify_install <cli_version> [<companion_version>]
verify_install() {
    _cli_ver="$1"
    _comp_ver="${2:-}"

    info "Verifying installation ..."

    if [ "$INSTALL_DRY_RUN" = 1 ]; then
        info "[dry-run] Would verify logion --version == $_cli_ver"
        return 0
    fi

    if ! command -v logion >/dev/null 2>&1; then
        die 9 "logion CLI not found on PATH after installation"
    fi

    _got_ver="$(logion --version 2>/dev/null | head -1)"
    if [ -z "$_got_ver" ]; then
        die 9 "logion --version returned empty output"
    fi

    info "logion --version: $_got_ver"

    # Optionally verify companion
    if [ -n "$_comp_ver" ] && [ "$INSTALL_CLI_ONLY" != 1 ]; then
        if command -v logion >/dev/null 2>&1; then
            _installed="$(logion skills installed 2>/dev/null || true)"
            if [ -z "$_installed" ]; then
                warn "logion skills installed returned no output"
            else
                info "Installed skills:"
                printf '%s\n' "$_installed"
            fi
        fi
    fi

    return 0
}

# --- Onboarding handoff -----------------------------------------------------

# run_onboarding invokes `logion onboarding` unless opted out or unsafe.
# It is best-effort: warn on failures, but never hard-fail the installer.
run_onboarding() {
    # Honor --cli-only: onboarding installs/syncs the companion by default, so
    # forward --no-companion to avoid re-adding what --cli-only opted out of.
    _onboarding_arg=""
    _onboarding_cmd="logion onboarding"
    if [ "${INSTALL_CLI_ONLY}" = 1 ]; then
        _onboarding_arg="--no-companion"
        _onboarding_cmd="logion onboarding --no-companion"
    fi

    if [ "${INSTALL_NO_ONBOARDING}" = 1 ]; then
        info "Skipping onboarding (--no-onboarding)."
        return 0
    fi
    if [ "${INSTALL_DRY_RUN}" = 1 ]; then
        info "[dry-run] Would run: ${_onboarding_cmd}"
        return 0
    fi
    if ! command -v logion >/dev/null 2>&1; then
        warn "logion not on PATH; skipping onboarding. Run '${_onboarding_cmd}' later."
        INSTALL_ONBOARDING_FAILED=1
        export INSTALL_ONBOARDING_FAILED
        return 0
    fi
    if [ ! -t 0 ] || [ ! -t 1 ] || [ -n "${LOGION_NONINTERACTIVE:-}" ] || [ -n "${CI:-}" ]; then
        info "Non-interactive shell; run '${_onboarding_cmd}' to finish setup."
        return 0
    fi

    info "Running '${_onboarding_cmd}' ..."
    # shellcheck disable=SC2086 # _onboarding_arg is a single optional flag
    if ! logion onboarding ${_onboarding_arg}; then
        warn "onboarding did not complete; run '${_onboarding_cmd}' later."
        INSTALL_ONBOARDING_FAILED=1
        export INSTALL_ONBOARDING_FAILED
    fi
    return 0
}

# --- Next steps -------------------------------------------------------------

print_next_steps() {
    info ""
    if [ "${INSTALL_CLI_ONLY}" = "1" ]; then
        info "✅ Logion installed (CLI only)."
    else
        info "✅ Logion installed (CLI + companion)."
    fi
    info ""
    if [ "${INSTALL_NO_ONBOARDING}" = 1 ]; then
        info "Onboarding skipped (--no-onboarding). Run 'logion onboarding' to finish setup."
    elif [ "${INSTALL_ONBOARDING_FAILED}" = 1 ] || [ ! -t 0 ] || [ ! -t 1 ] || [ -n "${LOGION_NONINTERACTIVE:-}" ] || [ -n "${CI:-}" ]; then
        info "Finish setup so your agent can use Logion:"
        info "  logion onboarding"
    else
        info "Your agent is ready to use Logion."
    fi
    info ""
    info "Docs: https://logion.sh/docs"
    info "You may need to open a new terminal for PATH changes to take effect."
}
