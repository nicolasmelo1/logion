# SPDX-License-Identifier: MIT
#
# install.ps1 — Logion curl installer for PowerShell.
#
# Mirrors install.sh step for step.  Run with:
#   powershell -ExecutionPolicy Bypass -File install.ps1 [options]
#
# Flags:
#   --Channel stable|latest  Release channel (default: stable)
#   --Version VERSION        Pin a specific version
#   --CliOnly                Install only the CLI
#   --SkillOnly              Install only the companion skill bundle
#   --Prefix PATH            Installation prefix for PATH shims
#   --Installer pipx|uv|venv Force a specific installer (default: uv)
#   --DryRun                 Show what would be done without executing
#   --NoModifyPath           Do not edit the user PATH
#   --NoOnboarding           Do not run logion onboarding after install
#   --SetupToken TOKEN      One-time setup token from GitHub sign-in
#   --Quiet                  Suppress informational output
#   --Verbose                Show extra detail
#   --Help                   Print usage and exit
#
# Exit codes:
#   0  success
#   1  generic error
#   2  invalid arguments
#   3  unsupported OS
#   4  missing prerequisite
#   5  download failed
#   6  SHA-256 mismatch
#   7  Python too old
#   8  install failed
#   9  verify failed

[CmdletBinding()]
param(
    [string]$Channel,
    [string]$Version,
    [switch]$CliOnly,
    [switch]$SkillOnly,
    [string]$Prefix,
    [string]$Installer,
    [switch]$DryRun,
    [switch]$NoModifyPath,
    [switch]$NoOnboarding,
    [string]$SetupToken,
    [switch]$Quiet,
    [switch]$Verbose,
    [switch]$Help
)

# ── Resolve script directory & dot-source library ──────────────────────
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
. (Join-Path $ScriptDir "install_lib.ps1")

# ── Build argument list for Parse-Args ──────────────────────────────────
$argList = [System.Collections.ArrayList]::new()
if ($Channel)     { $argList.AddRange(@("--Channel", $Channel)) }
if ($Version)     { $argList.AddRange(@("--Version", $Version)) }
if ($CliOnly)     { $argList.Add("--CliOnly") | Out-Null }
if ($SkillOnly)   { $argList.Add("--SkillOnly") | Out-Null }
if ($Prefix)      { $argList.AddRange(@("--Prefix", $Prefix)) }
if ($Installer)   { $argList.AddRange(@("--Installer", $Installer)) }
if ($DryRun)      { $argList.Add("--DryRun") | Out-Null }
if ($NoModifyPath){ $argList.Add("--NoModifyPath") | Out-Null }
if ($NoOnboarding) { $argList.Add("--NoOnboarding") | Out-Null }
if ($SetupToken)  { $argList.AddRange(@("--SetupToken", $SetupToken)) }
if ($Quiet)       { $argList.Add("--Quiet") | Out-Null }
if ($Verbose)     { $argList.Add("--Verbose") | Out-Null }
if ($Help)        { $argList.Add("--Help") | Out-Null }

# ── Step 1: Parse arguments ──────────────────────────────────────────────
$Opts = Parse-Args -ArgList $argList

if ($Opts.Help) {
    Write-Host @"

Logion Installer

Usage: powershell -ExecutionPolicy Bypass -File install.ps1 [options]

Options:
  --Channel stable|latest  Release channel (default: stable)
  --Version VERSION        Pin a specific version
  --CliOnly                Install only the CLI
  --SkillOnly              Install only the companion skill bundle
  --Prefix PATH            Installation prefix
  --Installer pipx|uv|venv Force a specific installer (default: uv)
  --DryRun                 Show what would be done
  --NoModifyPath           Do not edit the user PATH
  --NoOnboarding           Do not run logion onboarding after install
  --SetupToken TOKEN      One-time setup token from GitHub sign-in
  --Quiet                  Suppress informational output
  --Verbose                Show extra detail
  --Help                   Print this help and exit

Exit codes:
  0  success       1  generic error       2  invalid arguments
  3  unsupported OS 4  missing prerequisite 5  download failed
  6  SHA-256 mismatch  7  Python too old   8  install failed
  9  verify failed

"@
    exit $EXIT_SUCCESS
}

$script:Quiet = $Opts.Quiet

# ── Step 2: Detect platform ─────────────────────────────────────────────
$Platform = Detect-Platform
Info -Message "Detected platform: $($Platform.Os) / $($Platform.Arch)"

if ($Platform.Os -eq "unknown") {
    Die -Message "Unsupported operating system" -ExitCode $EXIT_UNSUPPORTED_OS
}

# ── Step 3: Check prerequisites ─────────────────────────────────────────
if (-not $Opts.SkillOnly) {
    Require-Tools
} else {
    Info -Message "Skipping Python prerequisite checks (--SkillOnly)"
}

# ── Step 4: Bootstrap uv (if selected) ───────────────────────────────────
if (-not $Opts.SkillOnly -and $Opts.Installer -eq "uv") {
    Bootstrap-Uv
}

# ── Step 5: Fetch manifest ──────────────────────────────────────────────
$Manifest = Fetch-Manifest -Channel $Opts.Channel

# ── Step 6: Validate manifest ───────────────────────────────────────────
Validate-Manifest -Manifest $Manifest

# ── Step 7: Resolve version ─────────────────────────────────────────────
if (-not $Opts.Version) {
    $Opts.Version = Manifest-GetField -Manifest $Manifest -Field "version" -Package "logion-cli"
    if (-not $Opts.Version) {
        Die -Message "Cannot resolve CLI version from manifest" -ExitCode $EXIT_GENERIC
    }
}
Info -Message "Target version: $($Opts.Version)"

# ── Step 8: Verify Python meets minimum ─────────────────────────────────
$minPython = Manifest-GetField -Manifest $Manifest -Field "minimum_python" -Package "logion-cli"
if (-not $Opts.SkillOnly -and $minPython) {
    Info -Message "Manifest requires Python >= $minPython"
    # Check-Python already validated >= 3.12 during Require-Tools
    # If the manifest requires something higher, re-check
    if ($minPython -match "3\.(\d+)") {
        $requiredMinor = [int]$Matches[1]
        try {
            $verOut = & $script:PythonCmd @script:PythonArgs -c "import sys; print(sys.version_info[:2])" 2>$null
            if ($verOut -match "\((\d+),\s*(\d+)\)") {
                $actualMinor = [int]$Matches[2]
                if ($actualMinor -lt $requiredMinor) {
                    Die -Message "Python 3.$actualMinor found but manifest requires >= $minPython" -ExitCode $EXIT_PYTHON_TOO_OLD
                }
            }
        } catch {
            # Already passed Check-Python, proceed optimistically
        }
    }
}

# ── Step 9: Install CLI ──────────────────────────────────────────────────
if (-not $Opts.SkillOnly) {
    $cliVersion = Manifest-GetField -Manifest $Manifest -Field "version" -Package "logion-cli"
    if (-not $cliVersion) { $cliVersion = $Opts.Version }

    # SHA-256 verification of wheel if manifest includes it
    $wheelInfo = Manifest-GetField -Manifest $Manifest -Field "wheel" -Package "logion-cli"
    if ($wheelInfo -and -not ($wheelInfo.url -match "^release://")) {
        if ($Opts.DryRun) {
            Info -Message "[DRY RUN] Would download and verify wheel from $($wheelInfo.url)"
        } else {
            $tmpWheel = [System.IO.Path]::Combine(
                [System.IO.Path]::GetTempPath(),
                "logion-cli-$cliVersion.whl"
            )
            Info -Message "Downloading wheel from $($wheelInfo.url)"
            try {
                Invoke-WebRequest -Uri $wheelInfo.url -OutFile $tmpWheel -UseBasicParsing -ErrorAction Stop
            } catch {
                Die -Message "Failed to download logion-cli wheel: $($_.Exception.Message)" -ExitCode $EXIT_DOWNLOAD_FAILED
            }

            $hash = (Get-FileHash -Path $tmpWheel -Algorithm SHA256).Hash.ToLower()
            if ($hash -ne $wheelInfo.sha256.ToLower()) {
                Remove-Item $tmpWheel -Force -ErrorAction SilentlyContinue
                Die -Message "SHA-256 mismatch for logion-cli wheel (expected $($wheelInfo.sha256), got $hash)" -ExitCode $EXIT_SHA256_MISMATCH
            }
            Info -Message "SHA-256 verified for logion-cli wheel"

            # Install from local wheel
            switch ($Opts.Installer) {
                "uv"   { & uv tool install --reinstall $tmpWheel; if ($LASTEXITCODE -ne 0) { Die -Message "uv wheel install failed" -ExitCode $EXIT_INSTALL_FAILED } }
                "pipx" { & pipx install --force $tmpWheel; if ($LASTEXITCODE -ne 0) { Die -Message "pipx wheel install failed" -ExitCode $EXIT_INSTALL_FAILED } }
                "venv" {
                    $logionDir = [System.IO.Path]::Combine($HOME, ".logion")
                    $venvDir   = [System.IO.Path]::Combine($logionDir, "installer-managed-venv")
                    # Create the venv if it doesn't exist yet (#26: use $script:PythonCmd)
                    if (-not (Test-Path -Path $venvDir)) {
                        Info -Message "Creating managed venv at $venvDir"
                        & $script:PythonCmd @script:PythonArgs -m venv $venvDir
                        if ($LASTEXITCODE -ne 0) { Die -Message "Failed to create venv at $venvDir" -ExitCode $EXIT_INSTALL_FAILED }
                    }
                    if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
                        $pipBin = [System.IO.Path]::Combine($venvDir, "Scripts", "pip.exe")
                    } else {
                        $pipBin = [System.IO.Path]::Combine($venvDir, "bin", "pip")
                    }
                    & $pipBin install $tmpWheel
                    if ($LASTEXITCODE -ne 0) { Die -Message "venv pip wheel install failed" -ExitCode $EXIT_INSTALL_FAILED }
                    New-LogionShim -Opts $Opts -VenvDir $venvDir
                }
            }
            Remove-Item $tmpWheel -Force -ErrorAction SilentlyContinue
        }
    } else {
        # No wheel in manifest — install from PyPI
        Install-Cli -Opts $Opts -Version $cliVersion
    }
}

# ── Step 10: Install companion ───────────────────────────────────────────
if (-not $Opts.CliOnly) {
    $companionVersion = Manifest-GetField -Manifest $Manifest -Field "version" -Package "logion-companion"
    if ($companionVersion) {
        Install-Companion -Opts $Opts -Version $companionVersion -Manifest $Manifest
    } else {
        Warn -Message "logion-companion not found in manifest; skipping companion install"
    }
}

# ── Step 11: Update PATH ────────────────────────────────────────────────
if (-not $Opts.NoModifyPath -and -not $Opts.SkillOnly) {
    $binDir = if ($Opts.Prefix) {
        [System.IO.Path]::Combine($Opts.Prefix, "bin")
    } else {
        [System.IO.Path]::Combine($HOME, ".local", "bin")
    }
    Update-Path -BinDir $binDir
}

# ── Step 12: Verify installation ────────────────────────────────────────
if (-not $Opts.SkillOnly) {
    $verified = Verify-Install -ExpectedVersion $Opts.Version
    if (-not $verified -and -not $Opts.DryRun) {
        Warn -Message "Installation verification failed; the CLI may not be on PATH yet"
        # Don't hard-exit; just warn — user may need a new shell
    }
}

# ── Step 13: Run onboarding handoff ─────────────────────────────────────
$onboardingFailed = $false
if (-not $Opts.SkillOnly) {
    Run-Onboarding -Opts $Opts -Failed ([ref]$onboardingFailed)
} else {
    Info -Message "Skipping onboarding (--SkillOnly)"
}

# ── Step 14: Print next steps ────────────────────────────────────────────

Print-NextSteps -Version $Opts.Version -Opts $Opts -OnboardingFailed $onboardingFailed

exit $EXIT_SUCCESS
