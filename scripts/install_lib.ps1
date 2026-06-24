# SPDX-License-Identifier: MIT
#
# install_lib.ps1 — PowerShell library for the Logion curl installer.
#
# Functions used by install.ps1 to detect platform, fetch manifests,
# verify checksums, detect Python, bootstrap uv, install packages,
# and update PATH.

# ── Exit codes ──────────────────────────────────────────────────────────
$script:EXIT_SUCCESS         = 0
$script:EXIT_GENERIC         = 1
$script:EXIT_INVALID_ARGS    = 2
$script:EXIT_UNSUPPORTED_OS  = 3
$script:EXIT_MISSING_PREREQ  = 4
$script:EXIT_DOWNLOAD_FAILED = 5
$script:EXIT_SHA256_MISMATCH = 6
$script:EXIT_PYTHON_TOO_OLD  = 7
$script:EXIT_INSTALL_FAILED  = 8
$script:EXIT_VERIFY_FAILED   = 9

# ── Global state (set by Parse-Args, consumed by callers) ───────────────
$script:ManifestBaseUrl = "https://logion.sh/releases"
$script:Manifest        = $null
$script:PythonCmd       = $null
$script:PythonArgs      = @()

# ── Logging ──────────────────────────────────────────────────────────────
function Die {
    <#
    .SYNOPSIS
    Print an error message and exit with the given code.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Message,
        [Parameter(Mandatory)][int]$ExitCode
    )
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit $ExitCode
}

function Info {
    <#
    .SYNOPSIS
    Print an informational message (suppressed in Quiet mode).
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Message
    )
    if (-not $script:Quiet) {
        Write-Host "  $Message"
    }
}

function Warn {
    <#
    .SYNOPSIS
    Print a warning message.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Message
    )
    Write-Host "WARN: $Message" -ForegroundColor Yellow
}

# ── Platform detection ──────────────────────────────────────────────────
function Detect-Platform {
    <#
    .SYNOPSIS
    Detect OS and architecture. Returns a hashtable with Os, Arch, Raw flags.
    #>
    [CmdletBinding()]
    param()

    $os = "unknown"
    $arch = "unknown"

    if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
        $os = "windows"
    } elseif ($IsMacOS) {
        $os = "macos"
    } elseif ($IsLinux) {
        $os = "linux"
    }

    # Architecture
    $cpu = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
    if (-not $cpu) {
        $cpu = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITECTURE")
    }

    switch ($cpu) {
        { $_ -match "arm64|aarch64" } { $arch = "arm64" }
        { $_ -match "x64|x86_64|amd64|AMD64" } { $arch = "x64" }
        { $_ -match "x86|i386|i686" } { $arch = "x86" }
        default { $arch = "unknown" }
    }

    return @{ Os = $os; Arch = $arch }
}

# ── Prerequisite checks ──────────────────────────────────────────────────
function Require-Tools {
    <#
    .SYNOPSIS
    Verify required tools are available. Die if missing.
    #>
    [CmdletBinding()]
    param()

    # We need a way to fetch URLs. PowerShell has Invoke-WebRequest natively,
    # so curl/wget are not strictly required. Check for Python instead.
    $py = Check-Python
    if (-not $py) {
        Die -Message "Python 3.12+ not found. Install Python 3.12+ and re-run." -ExitCode $script:EXIT_PYTHON_TOO_OLD
    }

    $script:PythonCmd  = $py.Cmd
    $script:PythonArgs = $py.Args
    Info -Message "Using Python: $($py.Cmd) $($py.Args -join ' ')"
}

# ── Argument parsing ────────────────────────────────────────────────────
function Parse-Args {
    <#
    .SYNOPSIS
    Parse installer command-line arguments into a hashtable.
    #>
    [CmdletBinding()]
    param(
        [string[]]$ArgList
    )

    $opts = @{
        Channel      = "stable"
        Version      = $null
        CliOnly      = $false
        SkillOnly    = $false
        Prefix       = $null
        Installer    = "uv"
        DryRun       = $false
        NoModifyPath = $false
        NoOnboarding = $false
        Quiet        = $false
        Verbose      = $false
        Help         = $false
    }

    $i = 0
    while ($i -lt $ArgList.Count) {
        $arg = $ArgList[$i]
        switch -Regex ($arg) {
            "^--Channel$" {
                $i++
                if ($i -ge $ArgList.Count) { Die -Message "--Channel requires a value" -ExitCode $script:EXIT_INVALID_ARGS }
                if ($ArgList[$i] -notin @("stable","latest")) { Die -Message "--Channel must be stable or latest" -ExitCode $script:EXIT_INVALID_ARGS }
                $opts.Channel = $ArgList[$i]
            }
            "^--Version$" {
                $i++
                if ($i -ge $ArgList.Count) { Die -Message "--Version requires a value" -ExitCode $script:EXIT_INVALID_ARGS }
                $opts.Version = $ArgList[$i] -replace "^v", ""
            }
            "^--Version=(.+)$" {
                $opts.Version = $Matches[1] -replace "^v", ""
            }
            "^--Channel=(.+)$" {
                if ($Matches[1] -notin @("stable","latest")) { Die -Message "--Channel must be stable or latest" -ExitCode $script:EXIT_INVALID_ARGS }
                $opts.Channel = $Matches[1]
            }
            "^--Prefix=(.+)$" {
                $opts.Prefix = $Matches[1]
            }
            "^--Installer=(.+)$" {
                if ($Matches[1] -notin @("pipx","uv","venv")) { Die -Message "--Installer must be pipx, uv, or venv" -ExitCode $script:EXIT_INVALID_ARGS }
                $opts.Installer = $Matches[1]
            }
            "^--CliOnly$"    { $opts.CliOnly = $true }
            "^--SkillOnly$"  { $opts.SkillOnly = $true }
            "^--Prefix$" {
                $i++
                if ($i -ge $ArgList.Count) { Die -Message "--Prefix requires a value" -ExitCode $script:EXIT_INVALID_ARGS }
                $opts.Prefix = $ArgList[$i]
            }
            "^--Installer$" {
                $i++
                if ($i -ge $ArgList.Count) { Die -Message "--Installer requires a value" -ExitCode $script:EXIT_INVALID_ARGS }
                if ($ArgList[$i] -notin @("pipx","uv","venv")) { Die -Message "--Installer must be pipx, uv, or venv" -ExitCode $script:EXIT_INVALID_ARGS }
                $opts.Installer = $ArgList[$i]
            }
            "^--DryRun$"     { $opts.DryRun = $true }
            "^--NoModifyPath$" { $opts.NoModifyPath = $true }
            "^--NoOnboarding$" { $opts.NoOnboarding = $true }
            "^--Quiet$"      { $opts.Quiet = $true; $script:Quiet = $true }
            "^--Verbose$"    { $opts.Verbose = $true }
            "^--Help$"       { $opts.Help = $true }
            "^-[h?]$"        { $opts.Help = $true }
            default {
                Die -Message "Unknown argument: $arg" -ExitCode $script:EXIT_INVALID_ARGS
            }
        }
        $i++
    }

    # Mutual exclusivity
    if ($opts.CliOnly -and $opts.SkillOnly) {
        Die -Message "--CliOnly and --SkillOnly are mutually exclusive" -ExitCode $script:EXIT_INVALID_ARGS
    }

    $script:OnboardingFailed = $false

    $script:LastOpts = $opts

    return $opts
}

# ── Shim helpers ────────────────────────────────────────────────────────
function Get-ShimBinDir {
    [CmdletBinding()]
    param([hashtable]$Opts)

    if ($Opts.Prefix) {
        return [System.IO.Path]::Combine($Opts.Prefix, "bin")
    }
    return [System.IO.Path]::Combine($HOME, ".local", "bin")
}

function New-LogionShim {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][hashtable]$Opts,
        [Parameter(Mandatory)][string]$VenvDir
    )

    $binDir = Get-ShimBinDir -Opts $Opts
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null

    if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
        $target = [System.IO.Path]::Combine($VenvDir, "Scripts", "logion.exe")
        $shim = [System.IO.Path]::Combine($binDir, "logion.cmd")
        Set-Content -Path $shim -Value "@echo off`r`n`"$target`" %*`r`n" -NoNewline
    } else {
        $target = [System.IO.Path]::Combine($VenvDir, "bin", "logion")
        $shim = [System.IO.Path]::Combine($binDir, "logion")
        Set-Content -Path $shim -Value "#!/bin/sh`nexec `"$target`" `"$@`"`n" -NoNewline
        chmod +x $shim 2>$null
    }

    Info -Message "Created logion shim in $binDir"
}

function Resolve-ReleaseUrl {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][string]$Tag
    )

    if ($Url -notmatch "^release://") {
        return $Url
    }

    $asset = $Url -replace "^release://", ""
    if ($env:LOGION_INSTALL_BASE_URL) {
        return "$($env:LOGION_INSTALL_BASE_URL.TrimEnd('/'))/$asset"
    }
    return "https://github.com/nicolasmelo1/logion/releases/download/$Tag/$asset"
}

# ── Manifest fetch ──────────────────────────────────────────────────────
function Fetch-Manifest {
    <#
    .SYNOPSIS
    Download the release manifest for the given channel.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Channel
    )

    $url = "$script:ManifestBaseUrl/manifest-$Channel.json"
    Info -Message "Fetching manifest from $url"

    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -ErrorAction Stop
        $manifest = $response.Content | ConvertFrom-Json -AsHashtable
    } catch {
        Die -Message "Failed to fetch manifest from ${url}: $($_.Exception.Message)" -ExitCode $script:EXIT_DOWNLOAD_FAILED
    }

    $script:Manifest = $manifest
    return $manifest
}

# ── Manifest field access ────────────────────────────────────────────────
function Manifest-GetField {
    <#
    .SYNOPSIS
    Read a field from the manifest, optionally from a specific package.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][hashtable]$Manifest,
        [Parameter(Mandatory)][string]$Field,
        [string]$Package
    )

    if ($Package) {
        if ($Manifest.packages.ContainsKey($Package)) {
            $pkg = $Manifest.packages[$Package]
            if ($pkg.ContainsKey($Field)) {
                return $pkg[$Field]
            }
        }
        return $null
    }

    if ($Manifest.ContainsKey($Field)) {
        return $Manifest[$Field]
    }
    return $null
}

# ── Manifest validation ─────────────────────────────────────────────────
function Validate-Manifest {
    <#
    .SYNOPSIS
    Verify the manifest has the required structure.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][hashtable]$Manifest
    )

    $requiredTopLevel = @("schema_version", "channel", "packages")
    foreach ($field in $requiredTopLevel) {
        if (-not $Manifest.ContainsKey($field)) {
            Die -Message "Manifest missing required field: $field" -ExitCode $script:EXIT_GENERIC
        }
    }

    if ($Manifest.schema_version -ne 1) {
        Die -Message "Unsupported manifest schema_version: $($Manifest.schema_version)" -ExitCode $script:EXIT_GENERIC
    }

    if (-not $Manifest.packages.ContainsKey("logion-cli")) {
        Die -Message "Manifest missing logion-cli package entry" -ExitCode $script:EXIT_GENERIC
    }

    return $true
}

# ── Python detection ────────────────────────────────────────────────────
function Check-Python {
    <#
    .SYNOPSIS
    Find a Python 3.12+ interpreter. Returns @{ Cmd; Args } or $null.
    #>
    [CmdletBinding()]
    param()

    $minMajor = 3
    $minMinor = 12

    # Candidate commands in order
    $candidates = @()
    if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
        $candidates = @(
            @{ Cmd = "py"; Args = @("-3.12") },
            @{ Cmd = "python3"; Args = @() },
            @{ Cmd = "python";  Args = @() }
        )
    } else {
        $candidates = @(
            @{ Cmd = "python3"; Args = @() },
            @{ Cmd = "python";  Args = @() }
        )
    }

    foreach ($c in $candidates) {
        $resolved = Get-Command $c.Cmd -ErrorAction SilentlyContinue
        if (-not $resolved) { continue }

        try {
            $allArgs = $c.Args + @("-c", "import sys; print(sys.version_info[:2])")
            $result = & $c.Cmd @allArgs 2>$null
            if ($LASTEXITCODE -ne 0 -or -not $result) { continue }

            if ($result -match "\((\d+),\s*(\d+)\)") {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -gt $minMajor -or ($major -eq $minMajor -and $minor -ge $minMinor)) {
                    return @{ Cmd = $c.Cmd; Args = $c.Args }
                }
            }
        } catch {
            continue
        }
    }

    return $null
}

# ── Bootstrap uv ─────────────────────────────────────────────────────────
function Bootstrap-Uv {
    <#
    .SYNOPSIS
    Ensure uv is available; install it if missing (via official installer).
    #>
    [CmdletBinding()]
    param()

    $uv = Get-Command "uv" -ErrorAction SilentlyContinue
    if ($uv) {
        Info -Message "uv already installed: $($uv.Source)"
        return
    }

    Info -Message "Bootstrapping uv..."

    if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
        # Windows: use the official PowerShell install script
        $installScript = "https://astral.sh/uv/install.ps1"
        $installerPath = Join-Path ([System.IO.Path]::GetTempPath()) "uv-install.ps1"
        try {
            Invoke-WebRequest -Uri $installScript -OutFile $installerPath
            & $installerPath
        } catch {
            Die -Message "Failed to bootstrap uv: $($_.Exception.Message)" -ExitCode $script:EXIT_INSTALL_FAILED
        } finally {
            Remove-Item -Path $installerPath -Force -ErrorAction SilentlyContinue
        }
    } else {
        # Unix: shell out to the official curl installer
        try {
            & sh -c "curl -LsSf https://astral.sh/uv/install.sh | sh"
            if ($LASTEXITCODE -ne 0) {
                Die -Message "Failed to bootstrap uv (exit $LASTEXITCODE)" -ExitCode $script:EXIT_INSTALL_FAILED
            }
        } catch {
            Die -Message "Failed to bootstrap uv: $($_.Exception.Message)" -ExitCode $script:EXIT_INSTALL_FAILED
        }
    }

    # Re-check
    $uv = Get-Command "uv" -ErrorAction SilentlyContinue
    if (-not $uv) {
        # Maybe it landed in ~/.local/bin or ~/cargo/bin — add to session
        $paths = @(
            [System.IO.Path]::Combine($HOME, ".local", "bin"),
            [System.IO.Path]::Combine($HOME, ".cargo", "bin")
        )
        foreach ($p in $paths) {
            if (Test-Path $p) {
                $env:PATH = "$p$([System.IO.Path]::PathSeparator)$env:PATH"
            }
        }
        $uv = Get-Command "uv" -ErrorAction SilentlyContinue
    }
    if (-not $uv) {
        Die -Message "uv still not found after bootstrap" -ExitCode $script:EXIT_MISSING_PREREQ
    }

    Info -Message "uv bootstrapped successfully"
}

# ── Install CLI ──────────────────────────────────────────────────────────
function Install-Cli {
    <#
    .SYNOPSIS
    Install the logion-cli Python package using the configured installer.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][hashtable]$Opts,
        [Parameter(Mandatory)][string]$Version
    )

    $pypiName = "logion-cli"
    $pkgSpec = "${pypiName}==${Version}"

    Info -Message "Installing $pkgSpec via $($Opts.Installer)..."

    if ($Opts.DryRun) {
        Info -Message "[DRY RUN] Would install $pkgSpec via $($Opts.Installer)"
        return
    }

    switch ($Opts.Installer) {
        "uv" {
            $uvArgs = @("tool", "install", "--reinstall", $pkgSpec)
            if ($Opts.Prefix) { $uvArgs = @("tool", "install", "--reinstall", "--python", $script:PythonCmd, $pkgSpec) }
            & uv @uvArgs
            if ($LASTEXITCODE -ne 0) {
                Die -Message "uv tool install failed for $pkgSpec" -ExitCode $script:EXIT_INSTALL_FAILED
            }
        }
        "pipx" {
            Get-Command "pipx" -ErrorAction SilentlyContinue | Out-Null
            if (-not $?) {
                Die -Message "pipx not found; use --Installer uv or install pipx" -ExitCode $script:EXIT_MISSING_PREREQ
            }
            & pipx install --force $pkgSpec
            if ($LASTEXITCODE -ne 0) {
                Die -Message "pipx install failed for $pkgSpec" -ExitCode $script:EXIT_INSTALL_FAILED
            }
        }
        "venv" {
            $logionDir = [System.IO.Path]::Combine($HOME, ".logion")
            $venvDir   = [System.IO.Path]::Combine($logionDir, "installer-managed-venv")
            if (-not (Test-Path $venvDir)) {
                Info -Message "Creating managed venv at $venvDir"
                & $script:PythonCmd @script:PythonArgs -m venv $venvDir
                if ($LASTEXITCODE -ne 0) {
                    Die -Message "venv creation failed" -ExitCode $script:EXIT_INSTALL_FAILED
                }
            }
            # Determine venv pip path
            if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
                $pipBin = [System.IO.Path]::Combine($venvDir, "Scripts", "pip.exe")
            } else {
                $pipBin = [System.IO.Path]::Combine($venvDir, "bin", "pip")
            }
            & $pipBin install $pkgSpec
            if ($LASTEXITCODE -ne 0) {
                Die -Message "venv pip install failed for $pkgSpec" -ExitCode $script:EXIT_INSTALL_FAILED
            }
            New-LogionShim -Opts $Opts -VenvDir $venvDir
        }
        default {
            Die -Message "Unknown installer: $($Opts.Installer)" -ExitCode $script:EXIT_INVALID_ARGS
        }
    }

    Info -Message "Installed $pkgSpec"
}

# ── Install companion ────────────────────────────────────────────────────
function Install-Companion {
    <#
    .SYNOPSIS
    Install the logion-companion skill bundle.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][hashtable]$Opts,
        [Parameter(Mandatory)][string]$Version,
        [hashtable]$Manifest
    )

    $companionDir = if ($Opts.Prefix) {
        [System.IO.Path]::Combine($Opts.Prefix, "logion-companion")
    } else {
        [System.IO.Path]::Combine($HOME, ".logion", "companion")
    }

    Info -Message "Installing logion-companion v$Version to $companionDir"

    if ($Opts.DryRun) {
        Info -Message "[DRY RUN] Would install companion v$Version"
        return
    }

    # Try to get bundle URL from manifest
    $bundleInfo = $null
    if ($Manifest -and $Manifest.packages.ContainsKey("logion-companion")) {
        $comp = $Manifest.packages["logion-companion"]
        if ($comp.ContainsKey("bundle")) {
            $bundleInfo = $comp["bundle"]
        }
    }

    New-Item -ItemType Directory -Path $companionDir -Force | Out-Null

    if ($bundleInfo -and $bundleInfo.ContainsKey("url") -and $bundleInfo.ContainsKey("sha256")) {
        $tag = if ($Manifest.packages["logion-companion"].ContainsKey("tag")) {
            $Manifest.packages["logion-companion"]["tag"]
        } else {
            "logion-companion-v$Version"
        }
        $bundleUrl = Resolve-ReleaseUrl -Url $bundleInfo["url"] -Tag $tag
        $expectedSha = $bundleInfo["sha256"]

        $tmpFile = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "logion-companion-$Version.tar.gz")
        Info -Message "Downloading companion bundle from $bundleUrl"
        try {
            Invoke-WebRequest -Uri $bundleUrl -OutFile $tmpFile -UseBasicParsing -ErrorAction Stop
        } catch {
            Die -Message "Failed to download companion bundle: $($_.Exception.Message)" -ExitCode $script:EXIT_DOWNLOAD_FAILED
        }

        # SHA-256 verification
        $hash = (Get-FileHash -Path $tmpFile -Algorithm SHA256).Hash.ToLower()
        if ($hash -ne $expectedSha.ToLower()) {
            Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
            Die -Message "SHA-256 mismatch for companion bundle (expected $expectedSha, got $hash)" -ExitCode $script:EXIT_SHA256_MISMATCH
        }
        Info -Message "SHA-256 verified for companion bundle"

        # Extract
        try {
            tar -xzf $tmpFile -C $companionDir
        } catch {
            Die -Message "Failed to extract companion bundle: $($_.Exception.Message)" -ExitCode $script:EXIT_INSTALL_FAILED
        }
        Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
    } else {
        # No bundle in manifest — install via pip as fallback
        $pkgSpec = "logion-companion==$Version"
        Info -Message "No bundle URL in manifest; installing $pkgSpec via pip"
        switch ($Opts.Installer) {
            "uv" {
                & uv pip install $pkgSpec
                if ($LASTEXITCODE -ne 0) {
                    Die -Message "uv pip install failed for companion" -ExitCode $script:EXIT_INSTALL_FAILED
                }
            }
            default {
                Die -Message "Companion bundle not available and pip fallback only supported with --Installer uv" -ExitCode $script:EXIT_INSTALL_FAILED
            }
        }
    }

    Info -Message "Installed logion-companion v$Version"
}

# ── PATH update ──────────────────────────────────────────────────────────
function Update-Path {
    <#
    .SYNOPSIS
    Ensure the Logion bin directory is on the user's PATH (idempotent).
    #>
    [CmdletBinding()]
    param(
        [string]$BinDir
    )

    if (-not $BinDir) {
        # Default bin locations
        if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
            $BinDir = [System.IO.Path]::Combine($HOME, ".local", "bin")
        } else {
            $BinDir = [System.IO.Path]::Combine($HOME, ".local", "bin")
        }
    }

    # Check current session PATH
    $pathParts = $env:PATH -split [System.IO.Path]::PathSeparator
    $alreadyInSession = $pathParts -contains $BinDir

    if ($alreadyInSession) {
        Info -Message "$BinDir already in current PATH"
    } else {
        $env:PATH = "${BinDir}$([System.IO.Path]::PathSeparator)$env:PATH"
        Info -Message "Added $BinDir to current session PATH"
    }

    # Persist to user environment (idempotent)
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    # Guard against $null PATH on fresh profiles (#18)
    if ($null -eq $userPath -or $userPath -eq "") {
        $userPathParts = @()
    } else {
        $userPathParts = $userPath -split [System.IO.Path]::PathSeparator
    }
    if ($userPathParts -notcontains $BinDir) {
        $newUserPath = "${BinDir}$([System.IO.Path]::PathSeparator)$userPath"
        [Environment]::SetEnvironmentVariable("PATH", $newUserPath, "User")
        Info -Message "Added $BinDir to persistent user PATH"
    } else {
        Info -Message "$BinDir already in persistent user PATH"
    }
}

# ── Verify installation ──────────────────────────────────────────────────
function Verify-Install {
    <#
    .SYNOPSIS
    Verify the logion CLI is on PATH and reports the expected version.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$ExpectedVersion
    )

    $logion = Get-Command "logion" -ErrorAction SilentlyContinue
    if (-not $logion) {
        # Also check for the short alias
        $logion = Get-Command "lgn" -ErrorAction SilentlyContinue
    }

    if (-not $logion) {
        Warn -Message "logion command not found on PATH. Open a new terminal or add ~/.local/bin to PATH."
        return $false
    }

    try {
        $versionOutput = & $logion.Source --version 2>$null
        if ($versionOutput -match $ExpectedVersion) {
            Info -Message "Verified: logion $ExpectedVersion is on PATH"
            return $true
        } else {
            Warn -Message "logion version mismatch: expected $ExpectedVersion, got $versionOutput"
            return $false
        }
    } catch {
        Warn -Message "Could not verify logion version: $($_.Exception.Message)"
        return $false
    }
}

# ── Onboarding handoff ───────────────────────────────────────────────────
function Run-Onboarding {
    <#
    .SYNOPSIS
    Run logion onboarding unless disabled or unsafe for prompts.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory)][hashtable]$Opts)

    if ($Opts.NoOnboarding) {
        Info -Message "Skipping onboarding (--NoOnboarding)."
        return
    }
    if ($Opts.DryRun) {
        Info -Message "[DRY RUN] Would run: logion onboarding"
        return
    }
    $logion = Get-Command logion -ErrorAction SilentlyContinue
    if (-not $logion) {
        Warn -Message "logion not on PATH; run 'logion onboarding' later."
        $script:OnboardingFailed = $true
        return
    }
    if (-not [Environment]::UserInteractive -or $env:LOGION_NONINTERACTIVE -or $env:CI) {
        Info -Message "Non-interactive; run 'logion onboarding' to finish setup."
        return
    }

    Info -Message "Running 'logion onboarding' ..."
    try {
        & $logion.Source onboarding
        if ($LASTEXITCODE -ne 0) {
            $script:OnboardingFailed = $true
            Warn -Message "onboarding did not complete; run 'logion onboarding' later."
        }
    } catch {
        $script:OnboardingFailed = $true
        Warn -Message "onboarding did not complete; run 'logion onboarding' later."
    }
}

# ── Print next steps ─────────────────────────────────────────────────────
function Print-NextSteps {
    <#
    .SYNOPSIS
    Print post-install instructions.
    #>
    [CmdletBinding()]
    param(
        [string]$Version
    )

    Write-Host ""
    if ($script:LastOpts -and $script:LastOpts.CliOnly) {
        Write-Host "✓ Logion CLI v$Version installed successfully." -ForegroundColor Green
    } else {
        Write-Host "✓ Logion CLI v$Version and companion installed successfully." -ForegroundColor Green
    }
    Write-Host ""
    if ($script:OnboardingFailed -or -not [Environment]::UserInteractive -or $env:LOGION_NONINTERACTIVE -or $env:CI) {
        Write-Host "Finish setup so your agent can use Logion:"
        Write-Host "  logion onboarding"
    } elseif ($script:LastOpts -and $script:LastOpts.NoOnboarding) {
        Write-Host "Onboarding skipped (--NoOnboarding)."
    } else {
        Write-Host "Your agent is ready to use Logion."
    }
    Write-Host ""
    Write-Host "Documentation: https://logion.sh/docs"
    Write-Host "If 'logion' is not found, open a new terminal or add ~/.local/bin to PATH."
    Write-Host "Report issues:  https://github.com/nicolasmelo1/logion/issues"
    Write-Host ""
}
