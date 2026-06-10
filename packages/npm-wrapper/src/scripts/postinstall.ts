// SPDX-License-Identifier: MIT
//
// postinstall.ts — detect Python, install logion-cli via pipx/uv/venv.
//
// Environment variables:
//   LOGION_NPM_SKIP_INSTALL=1   — skip CLI install only (still handles companion)
//   LOGION_NPM_FORCE_INSTALLER  — force "pipx", "uv", or "venv"
//   LOGION_NPM_PYTHON           — override Python binary path
//   LOGION_COMPANION_BUNDLE_SOURCE — directory containing companion tarball
//                                    (dev rig only; copies bundle to
//                                     $LOGION_HOME/companion-bundles/ or
//                                     ~/.logion/companion-bundles/)
import { spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { detectPython, type PythonInfo } from "../lib/check-python";
import { which } from "../lib/which";

type Installer = "pipx" | "uv" | "venv";

const HOME = os.homedir();
const LOGION_DIR = path.join(HOME, ".logion");
const MANAGED_VENV_DIR = path.join(LOGION_DIR, "npm-managed-venv");
const MARKER_PATH = path.join(LOGION_DIR, "npm-wrapper-installer.json");
const LOCAL_BIN = path.join(HOME, ".local", "bin");
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

function linkOrCopy(src: string, dest: string): void {
  if (fs.existsSync(dest)) {
    fs.unlinkSync(dest);
  }
  try {
    fs.symlinkSync(src, dest);
  } catch {
    // Windows without dev-mode/admin: fall back to copy.
    fs.copyFileSync(src, dest);
  }
}

function shimNamesFor(base: string): string[] {
  return process.platform === "win32" ? [`${base}.exe`] : [base];
}

function installViaVenv(version: string, py: PythonInfo): void {
  log(`Installing logion-cli==${version} via managed venv...`);
  runChecked(py.cmd, [...py.args, "-m", "venv", MANAGED_VENV_DIR]);
  runChecked(venvBin("pip"), ["install", `logion-cli==${version}`]);

  fs.mkdirSync(LOCAL_BIN, { recursive: true });

  for (const base of ["logion", "lgn"] as const) {
    const src = venvBin(base);
    if (!fs.existsSync(src)) {
      continue;
    }
    for (const destName of shimNamesFor(base)) {
      const dest = path.join(LOCAL_BIN, destName);
      try {
        linkOrCopy(src, dest);
      } catch (error) {
        const msg = error instanceof Error ? error.message : String(error);
        log(
          `Warning: could not create shim ${dest}: ${msg}. ` +
            `Add ${LOCAL_BIN} to PATH manually.`,
        );
      }
    }
  }
}

function verifyInstall(version: string): void {
  const target = which("logion");
  if (!target) {
    log(
      "Warning: logion not on PATH yet. " +
        "Ensure your installer's bin directory is exported.",
    );
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
  if (which("pipx")) {
    return "pipx";
  }
  if (which("uv")) {
    return "uv";
  }
  return "venv";
}

function sortCodePoint(a: string, b: string): number {
  if (a < b) {
    return -1;
  }
  if (a > b) {
    return 1;
  }
  return 0;
}

function listBundleSourceEntries(sourceDir: string): string[] | null {
  try {
    return fs.readdirSync(sourceDir).sort(sortCodePoint);
  } catch {
    log(
      `LOGION_COMPANION_BUNDLE_SOURCE=${sourceDir} read failed — ` +
        "skipping companion bundle copy.",
    );
    return null;
  }
}

function findCompanionTarball(
  sourceDir: string,
  entries: string[],
): { tarball: string; srcPath: string } | null {
  for (const name of entries) {
    if (!/^logion-marketplace-companion-.*\.tar\.gz$/.test(name)) {
      continue;
    }
    const candidatePath = path.join(sourceDir, name);
    try {
      if (fs.statSync(candidatePath).isFile()) {
        return { tarball: name, srcPath: candidatePath };
      }
    } catch {
      log(`Could not stat companion tarball candidate ${candidatePath}.`);
    }
  }
  return null;
}

function resolveLogionHome(): string {
  const value = process.env.LOGION_HOME;
  return value === undefined || value.length === 0 ? LOGION_DIR : value;
}

function sha256File(filePath: string): string {
  const hash = crypto.createHash("sha256");
  const fd = fs.openSync(filePath, "r");
  const chunkSize = 64 * 1024;
  const buf = Buffer.alloc(chunkSize);
  let bytesRead: number;
  try {
    while ((bytesRead = fs.readSync(fd, buf, 0, chunkSize, null)) > 0) {
      hash.update(buf.subarray(0, bytesRead));
    }
  } finally {
    fs.closeSync(fd);
  }
  return hash.digest("hex");
}

/**
 * Copy the companion bundle from LOGION_COMPANION_BUNDLE_SOURCE into the
 * local companion-bundles directory.
 *
 * - If LOGION_COMPANION_BUNDLE_SOURCE is set, look for
 *   `logion-marketplace-companion-*.tar.gz` in that directory.
 * - Copy it to `$LOGION_HOME/companion-bundles/` (falling back to
 *   `~/.logion/companion-bundles/` when LOGION_HOME is unset).
 * - Write a per-tarball sidecar (replacing `.tar.gz` with `.source.json`)
 *   containing the source path and a SHA-256 of the tarball.
 * - If LOGION_COMPANION_BUNDLE_SOURCE is unset, do nothing (existing
 *   release path stays unchanged for users installing from npm registry).
 */
function installCompanionBundle(): void {
  const sourceDir = process.env.LOGION_COMPANION_BUNDLE_SOURCE;
  if (!sourceDir) {
    return;
  }

  if (!fs.existsSync(sourceDir)) {
    log(
      `LOGION_COMPANION_BUNDLE_SOURCE=${sourceDir} does not exist — ` +
        "skipping companion bundle copy.",
    );
    return;
  }

  // Validate that sourceDir is actually a directory.
  try {
    const stat = fs.statSync(sourceDir);
    if (!stat.isDirectory()) {
      log(
        `LOGION_COMPANION_BUNDLE_SOURCE=${sourceDir} is not a directory — ` +
          "skipping companion bundle copy.",
      );
      return;
    }
  } catch {
    log(
      `LOGION_COMPANION_BUNDLE_SOURCE=${sourceDir} stat failed — ` +
        "skipping companion bundle copy.",
    );
    return;
  }

  const entries = listBundleSourceEntries(sourceDir);
  if (!entries) {
    return;
  }

  const bundle = findCompanionTarball(sourceDir, entries);
  if (!bundle) {
    log(
      `No companion tarball found in ${sourceDir} — ` +
        "skipping companion bundle copy.",
    );
    return;
  }

  try {
    // Determine destination: $LOGION_HOME/companion-bundles/ or
    // ~/.logion/companion-bundles/ if LOGION_HOME is unset.
    const logionHome = resolveLogionHome();
    const bundlesDir = path.join(logionHome, "companion-bundles");
    fs.mkdirSync(bundlesDir, { recursive: true });

    const destPath = path.join(bundlesDir, bundle.tarball);
    fs.copyFileSync(bundle.srcPath, destPath);
    log(`Copied companion bundle to ${destPath}`);

    // Write sidecar marker with source path and SHA-256.
    // Hash in chunks to avoid loading the entire tarball into memory.
    const sha256 = sha256File(destPath);

    const sidecar = {
      sourcePath: bundle.srcPath,
      sha256,
      installedAt: new Date().toISOString(),
    };
    const sidecarName = bundle.tarball.replace(/\.tar\.gz$/, ".source.json");
    const sidecarPath = path.join(bundlesDir, sidecarName);
    fs.writeFileSync(sidecarPath, `${JSON.stringify(sidecar, null, 2)}\n`);
    log(`Wrote companion marker ${sidecarPath}`);
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    log(`Warning: companion bundle copy failed: ${msg}.`);
  }
}

function main(): void {
  // Companion bundle install runs even when the CLI install is skipped
  // (dev rig sets LOGION_NPM_SKIP_INSTALL=1 but still needs the bundle
  // copied into $LOGION_HOME/companion-bundles/).
  installCompanionBundle();

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
    log(
      "Or set LOGION_NPM_SKIP_INSTALL=1 and install manually: " +
        "pipx install logion-cli",
    );
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
  verifyInstall(version);
  log(`Installed logion-cli ${version} via ${installer}.`);
}

main();
