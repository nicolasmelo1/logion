# Logion Installer

Run the one-liner to install the Logion CLI and companion bundle:

```bash
curl -fsSL https://logion.dev/install.sh | sh
```

For the paranoid path (inspect before running):

```bash
curl -fsSLO https://github.com/nicolasmelo1/logion/releases/download/installer-v1/install.sh
echo "<expected sha256>  install.sh" | sha256sum -c
sh install.sh
```

Windows (PowerShell):

```powershell
irm https://logion.dev/install.ps1 | iex
```

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

The redirect at `https://logion.dev/install.sh` points at the latest
`installer-v*` release. The installer reads the package manifest from
the relevant package tag, **not** from its own tag.

## Threat model

The manifest URL is bound to a tagged GitHub Release. The trust anchor
is "GitHub knows the tag". The manifest's integrity is the chain anchor
— every downloaded artifact is sha256-verified against the manifest.
The manifest itself is not sha256-verified (it is the root of trust
derived from the tag pointer).

## Fallback

If `logion.dev` is unreachable, use the direct GitHub Release URL:

```bash
curl -fsSL https://github.com/nicolasmelo1/logion/releases/latest/download/install.sh | sh
```