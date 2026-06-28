// SPDX-License-Identifier: MIT
//
// postinstall.ts — detect Python, install logion-cli into the npm-managed venv.
//
// Environment variables:
//   LOGION_NPM_SKIP_INSTALL=1   — skip CLI install only (still handles companion)
//   LOGION_NPM_FORCE_INSTALLER  — force "pipx", "uv", or "venv" (default: venv)
//   LOGION_NPM_PYTHON           — override Python binary path
//   LOGION_NPM_SKIP_ONBOARDING=1 — do not print onboarding pointer
//   LOGION_COMPANION_BUNDLE_SOURCE — directory containing companion tarball
//                                    (dev rig only; copies bundle to
//                                     $LOGION_HOME/companion-bundles/ or
//                                     ~/.logion/companion-bundles/)
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { detectPython, type PythonInfo } from "../lib/check-python";
import { installCompanionBundle } from "../lib/companion-bundle";
import { which } from "../lib/which";

type Installer = "pipx" | "uv" | "venv";

const HOME = os.homedir();
const LOGION_DIR = path.join(HOME, ".logion");
const MANAGED_VENV_DIR = path.join(LOGION_DIR, "npm-managed-venv");
const MARKER_PATH = path.join(LOGION_DIR, "npm-wrapper-installer.json");
const PLACEHOLDER_VERSION = "0.0.0-placeholder";

interface InstallerMarker {
  installer: Installer;
  version: string;
  installedAt: string;
}

function log(msg: string): void {
  process.stderr.write(`[logion-postinstall] ${msg}\n`);
}

function packageRoot(): string {
  // __dirname = dist/scripts → package root is two levels up.
  return path.join(__dirname, "..", "..");
}

function getPinnedVersion(): string | null {
  const pkgPath = path.join(packageRoot(), "package.json");
  const raw = fs.readFileSync(pkgPath, "utf8");
  const pkg = JSON.parse(raw) as {
    version?: string;
    logionCliVersion?: string;
  };
  if (pkg.logionCliVersion && pkg.logionCliVersion.length > 0) {
    return pkg.logionCliVersion;
  }
  if (!pkg.version || pkg.version === PLACEHOLDER_VERSION) {
    return null;
  }
  return pkg.version;
}

function writeMarker(installer: Installer, version: string): void {
  const marker: InstallerMarker = {
    installer,
    version,
    installedAt: new Date().toISOString(),
  };
  fs.mkdirSync(LOGION_DIR, { recursive: true });
  fs.writeFileSync(MARKER_PATH, `${JSON.stringify(marker, null, 2)}\n`);
}

function runChecked(file: string, args: string[]): void {
  const r = spawnSync(file, args, { stdio: "inherit" });
  if (r.error) {
    throw r.error;
  }
  if (r.status !== 0) {
    throw new Error(
      `${file} ${args.join(" ")} exited with status ${String(r.status)}`,
    );
  }
}

function installViaPipx(version: string): void {
  log(`Installing logion-cli==${version} via pipx...`);
  runChecked("pipx", ["install", "--force", `logion-cli==${version}`]);
}

function installViaUv(version: string): void {
  log(`Installing logion-cli==${version} via uv tool...`);
  runChecked("uv", [
    "tool",
    "install",
    "--reinstall",
    `logion-cli==${version}`,
  ]);
}

function venvBin(name: string): string {
  if (process.platform === "win32") {
    return path.join(MANAGED_VENV_DIR, "Scripts", `${name}.exe`);
  }
  return path.join(MANAGED_VENV_DIR, "bin", name);
}

function installViaVenv(version: string, py: PythonInfo): void {
  log(`Installing logion-cli==${version} via managed venv...`);
  runChecked(py.cmd, [...py.args, "-m", "venv", "--clear", MANAGED_VENV_DIR]);
  runChecked(venvBin("pip"), ["install", `logion-cli==${version}`]);
}

function verifyInstall(version: string, installer: Installer): void {
  const target = installer === "venv" ? venvBin("logion") : which("logion");
  if (!target || !fs.existsSync(target)) {
    log("Warning: logion binary was not found after install.");
    return;
  }
  const r = spawnSync(target, ["--version"], {
    encoding: "utf8",
    timeout: 10_000,
  });
  if (r.status !== 0 || !r.stdout.includes(version)) {
    log(
      `Warning: installed version did not match requested ${version} ` +
        `(got: ${r.stdout.trim() || "<no output>"}).`,
    );
  }
}

function pickInstaller(forced: string | undefined): Installer | null {
  if (forced === "pipx" || forced === "uv" || forced === "venv") {
    return forced;
  }
  if (forced !== undefined && forced.length > 0) {
    return null;
  }
  return "venv";
}

function maybePrintOnboardingPointer(): void {
  if (process.env.LOGION_NPM_SKIP_ONBOARDING === "1") {
    return;
  }
  if (process.env.CI || process.env.LOGION_NONINTERACTIVE) {
    return;
  }
  log("Next: run `logion onboarding` to set up your agent.");
}

function main(): void {
  // Companion bundle install runs even when the CLI install is skipped
  // (dev rig sets LOGION_NPM_SKIP_INSTALL=1 but still needs the bundle
  // copied into $LOGION_HOME/companion-bundles/).
  installCompanionBundle(log);

  if (process.env.LOGION_NPM_SKIP_INSTALL === "1") {
    log("LOGION_NPM_SKIP_INSTALL=1 — skipping CLI install.");
    return;
  }

  const version = getPinnedVersion();
  if (!version) {
    log(
      "No pinned version found (package.json still has " +
        `${PLACEHOLDER_VERSION}). Run ` +
        "`node dist/scripts/version-from-manifest.js` first or set " +
        "LOGION_NPM_SKIP_INSTALL=1.",
    );
    process.exit(1);
  }

  const py = detectPython();
  if (!py) {
    log(
      "Error: Python 3.12+ not found. " +
        "Install Python 3.12+ or set LOGION_NPM_PYTHON.",
    );
    log("See: https://www.python.org/downloads/");
    log("Or set LOGION_NPM_SKIP_INSTALL=1 to skip the Python CLI install.");
    process.exit(1);
  }

  log(`Using Python: ${py.cmd} ${py.args.join(" ")}`.trim());

  const forced = process.env.LOGION_NPM_FORCE_INSTALLER;
  const installer = pickInstaller(forced);
  if (!installer) {
    log(`Error: unknown installer '${forced ?? ""}'. Use pipx, uv, or venv.`);
    process.exit(1);
  }

  if (installer === "pipx") {
    installViaPipx(version);
  } else if (installer === "uv") {
    installViaUv(version);
  } else {
    installViaVenv(version, py);
  }

  writeMarker(installer, version);
  verifyInstall(version, installer);
  maybePrintOnboardingPointer();
  log(`Installed logion-cli ${version} via ${installer}.`);
}

main();
