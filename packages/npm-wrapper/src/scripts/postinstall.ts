// SPDX-License-Identifier: MIT
//
// postinstall.ts — detect Python, install logion-cli via pipx/uv/venv.
//
// Environment variables:
//   LOGION_NPM_SKIP_INSTALL=1   — skip postinstall entirely (CI/test)
//   LOGION_NPM_FORCE_INSTALLER  — force "pipx", "uv", or "venv"
//   LOGION_NPM_PYTHON           — override Python binary path
"use strict";

const { execSync, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const { detectPython } = require("../lib/check-python");

const MANAGED_VENV_DIR = path.join(os.homedir(), ".logion", "npm-managed-venv");

function log(msg) {
  process.stderr.write("[logion-postinstall] " + msg + "\n");
}

function getPinnedVersion() {
  // __dirname = dist/scripts → need to go up 2 levels to reach package root
  const pkg = JSON.parse(
    fs.readFileSync(path.join(__dirname, "..", "..", "package.json"), "utf8")
  );
  // At publish time, version-from-manifest writes the real version.
  // For local dev, use the package version as fallback.
  return pkg.logionCliVersion || pkg.version.replace(/^0\.0\.0-placeholder$/, "0.1.0");
}

function hasCommand(cmd) {
  try {
    execSync(process.platform === "win32" ? `where ${cmd}` : `which ${cmd}`, {
      encoding: "utf8",
      stdio: "pipe",
      timeout: 5000,
    });
    return true;
  } catch {
    return false;
  }
}

function installViaPipx(version) {
  log("Installing logion-cli==" + version + " via pipx...");
  execSync("pipx install --force logion-cli==" + version, { stdio: "inherit" });
}

function installViaUv(version) {
  log("Installing logion-cli==" + version + " via uv tool...");
  execSync("uv tool install --reinstall logion-cli==" + version, {
    stdio: "inherit",
  });
}

function installViaVenv(version, pythonCmd) {
  log("Installing logion-cli==" + version + " via managed venv...");
  const venvDir = MANAGED_VENV_DIR;

  // Create venv
  execSync(pythonCmd + " -m venv " + JSON.stringify(venvDir), {
    stdio: "inherit",
  });

  // Install into venv
  const pipPath =
    process.platform === "win32"
      ? path.join(venvDir, "Scripts", "pip.exe")
      : path.join(venvDir, "bin", "pip");
  execSync(
    JSON.stringify(pipPath) + " install logion-cli==" + version,
    { stdio: "inherit" }
  );

  // Ensure a symlink exists in a user-local bin directory
  const binDir = path.join(os.homedir(), ".local", "bin");
  fs.mkdirSync(binDir, { recursive: true });

  const srcBin =
    process.platform === "win32"
      ? path.join(venvDir, "Scripts", "logion.exe")
      : path.join(venvDir, "bin", "logion");

  const destLink = path.join(binDir, "logion");
  try {
    if (fs.existsSync(destLink)) fs.unlinkSync(destLink);
    fs.symlinkSync(srcBin, destLink);
  } catch {
    log(
      "Warning: could not create symlink at " +
        destLink +
        ". You may need to add " +
        binDir +
        " to PATH."
    );
  }

  // Also symlink `lgn` alias
  const lgnSrc =
    process.platform === "win32"
      ? path.join(venvDir, "Scripts", "lgn.exe")
      : path.join(venvDir, "bin", "lgn");
  const lgnDest = path.join(binDir, "lgn");
  if (fs.existsSync(lgnSrc)) {
    try {
      if (fs.existsSync(lgnDest)) fs.unlinkSync(lgnDest);
      fs.symlinkSync(lgnSrc, lgnDest);
    } catch {
      // best-effort
    }
  }
}

function verifyInstall(version) {
  try {
    const out = execSync("logion --version", {
      encoding: "utf8",
      timeout: 10000,
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
    if (!out.includes(version)) {
      log(
        "Warning: installed version (" +
          out +
          ") does not match requested (" +
          version +
          ")"
      );
    }
  } catch {
    log(
      "Warning: could not verify logion-cli installation. The binary may not be on PATH yet."
    );
  }
}

function main() {
  if (process.env.LOGION_NPM_SKIP_INSTALL === "1") {
    log("LOGION_NPM_SKIP_INSTALL=1 — skipping postinstall.");
    return;
  }

  const version = getPinnedVersion();
  const info = detectPython();

  if (!info) {
    log("Error: Python 3.12+ not found. Install Python 3.12+ or set LOGION_NPM_PYTHON.");
    log("See: https://www.python.org/downloads/");
    log(
      "You can also set LOGION_NPM_SKIP_INSTALL=1 and install logion-cli manually with: pipx install logion-cli"
    );
    process.exit(1);
  }

  log("Using Python: " + info.cmd);

  const forceInstaller = process.env.LOGION_NPM_FORCE_INSTALLER;

  if (forceInstaller === "pipx" || (!forceInstaller && hasCommand("pipx"))) {
    installViaPipx(version);
    verifyInstall(version);
    log("Installed logion-cli " + version + " via pipx.");
    return;
  }

  if (forceInstaller === "uv" || (!forceInstaller && hasCommand("uv"))) {
    installViaUv(version);
    verifyInstall(version);
    log("Installed logion-cli " + version + " via uv.");
    return;
  }

  if (forceInstaller === "venv" || !forceInstaller) {
    installViaVenv(version, info.cmd);
    verifyInstall(version);
    log("Installed logion-cli " + version + " via managed venv.");
    return;
  }

  log("Error: unknown installer '" + forceInstaller + "'. Use pipx, uv, or venv.");
  process.exit(1);
}

main();