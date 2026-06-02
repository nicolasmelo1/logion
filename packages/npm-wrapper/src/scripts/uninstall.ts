// SPDX-License-Identifier: MIT
//
// uninstall.ts — best-effort cleanup of logion-cli installed via
// pipx, uv, or managed venv.  Never blocks npm uninstall on errors.
"use strict";

const { execSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

const MANAGED_VENV_DIR = path.join(os.homedir(), ".logion", "npm-managed-venv");

function log(msg) {
  process.stderr.write("[logion-uninstall] " + msg + "\n");
}

function tryCommand(cmd) {
  try {
    execSync(cmd, { encoding: "utf8", stdio: "pipe", timeout: 10000 });
    return true;
  } catch {
    return false;
  }
}

function main() {
  // Remove managed venv
  if (fs.existsSync(MANAGED_VENV_DIR)) {
    try {
      fs.rmSync(MANAGED_VENV_DIR, { recursive: true, force: true });
      log("Removed managed venv at " + MANAGED_VENV_DIR);
    } catch (e) {
      log("Warning: could not remove managed venv: " + e.message);
    }
  }

  // Remove symlinks from ~/.local/bin (both Unix and Windows names)
  const binDir = path.join(os.homedir(), ".local", "bin");
  const names = process.platform === "win32"
    ? ["logion", "logion.exe", "logion.cmd", "lgn", "lgn.exe", "lgn.cmd"]
    : ["logion", "lgn"];
  for (const name of names) {
    const link = path.join(binDir, name);
    try {
      if (fs.existsSync(link) && fs.lstatSync(link).isSymbolicLink()) {
        fs.unlinkSync(link);
      }
    } catch {
      // best-effort
    }
  }

  // Try pipx uninstall
  if (tryCommand("pipx --version")) {
    tryCommand("pipx uninstall logion-cli");
    log("Attempted pipx uninstall of logion-cli.");
  }

  // Try uv tool uninstall
  if (tryCommand("uv --version")) {
    tryCommand("uv tool uninstall logion-cli");
    log("Attempted uv tool uninstall of logion-cli.");
  }
}

main();