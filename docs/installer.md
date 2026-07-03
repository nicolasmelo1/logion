# Logion Installer

Run the one-liner to install the Logion CLI and companion bundle, then hand
off to onboarding so your agent can use Logion:

```bash
curl -fsSL https://logion.sh/install.sh | sh
```

For the paranoid path (inspect before running):

```bash
curl -fsSLO https://github.com/nicolasmelo1/logion/releases/download/installer-v1/install.sh
echo "<expected sha256>  install.sh" | sha256sum -c
sh install.sh
```

Windows (PowerShell):

```powershell
irm https://logion.sh/install.ps1 | iex
```

Interactive shell installs run `logion onboarding` after verification. In
CI/non-interactive shells the installer never prompts; it prints the same
`logion onboarding` command for you to run later.

## Options

```text
USAGE
    install.sh [OPTIONS]

OPTIONS
    --channel <stable|latest>     manifest channel              [default: stable]
    --version <tag>               pin a specific CLI tag
    --cli-only                    skip companion install
    --skill-only                  skip CLI install
    --prefix <path>               install prefix                [default: ~/.local]
    --installer <pipx|uv|venv>    force Python installer
    --dry-run                     print actions without executing
    --no-modify-path              skip PATH-update step
    --no-onboarding               skip onboarding handoff
    --quiet                       suppress informational output
    --verbose                     log every command
    -h, --help                    print usage and exit
```

## Environment variables

| Variable | Purpose |
|---|---|
| `LOGION_INSTALL_BASE_URL` | Override release URL base (tests) |
| `LOGION_INSTALL_MANIFEST_URL` | Override manifest URL (tests) |
| `LOGION_INSTALL_PYTHON` | Pin Python interpreter path |
| `LOGION_INSTALL_SKIP_VERIFY` | Skip sha256 verification (dev only) |
| `LOGION_NONINTERACTIVE` | Skip interactive onboarding prompts |
| `LOGION_NPM_SKIP_ONBOARDING` | Suppress npm postinstall onboarding pointer |
| `CI` | Skip interactive onboarding and npm pointer in CI |


## Companion and onboarding behavior

The companion bundle is installed by default. Use `--cli-only` when you only
want the CLI. Use `--skill-only` only when `logion` is already on `PATH` and
you want to install the companion without reinstalling the CLI.

With `--cli-only`, the onboarding handoff still runs but is invoked as
`logion onboarding --no-companion`, so it does not re-add the companion you
opted out of.

Use `--no-onboarding` on POSIX installers or `--NoOnboarding` in PowerShell to
skip the final `logion onboarding` handoff. The handoff is best-effort: a
failed onboarding run prints a warning and leaves the install intact.

The npm wrapper does not run interactive onboarding during `npm install`.
Instead, successful non-CI installs print:

```text
Next: run `logion onboarding` to set up your agent.
```

Set `LOGION_NPM_SKIP_ONBOARDING=1` to suppress that pointer.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic error / abort |
| 2 | Invalid arguments |
| 3 | Unsupported OS / arch |
| 4 | Missing prerequisite (curl / sha256 / Python) |
| 5 | Download failed |
| 6 | sha256 mismatch |
| 7 | Python version too old (< 3.12) |
| 8 | Install command failed (pipx/uv/venv) |
| 9 | Post-install verification failed |

## Installer versioning

The installer is versioned independently via `installer-vN` tags
(e.g. `installer-v1`). Each tag's GitHub Release contains:

- `install.sh` + `install.sh.sha256`
- `install.ps1` + `install.ps1.sha256`
- `release-notes.md`

The redirect at `https://logion.sh/install.sh` points at the raw
`scripts/install.sh` on `main` (the `installer-v*` release assets back
the direct-GitHub download path shown above). The installer reads the
package manifest from the relevant package tag, **not** from its own
tag.

## Threat model

By default, channel installs fetch `https://logion.sh/releases/manifest-<channel>.json`.
Version-pinned installs fetch the manifest from that package's tagged
GitHub Release. The manifest is the chain anchor: every downloaded
artifact is sha256-verified against it. The manifest itself is trusted
through the selected HTTPS origin or GitHub release tag.

## Fallback

If `logion.sh` is unreachable, use the direct GitHub Release URL:

```bash
curl -fsSL https://github.com/nicolasmelo1/logion/releases/latest/download/install.sh | sh
```
