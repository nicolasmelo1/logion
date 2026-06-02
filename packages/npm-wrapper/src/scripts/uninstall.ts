// SPDX-License-Identifier: MIT
//
// uninstall.ts — best-effort cleanup of artefacts created by this
// npm wrapper. Only acts on installations we recorded in the marker
// file to avoid clobbering a pre-existing pipx/uv install of
// `logion-cli` that the user manages themselves.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { which } from "../lib/which";

const HOME = os.homedir();
const LOGION_DIR = path.join(HOME, ".logion");
const MANAGED_VENV_DIR = path.join(LOGION_DIR, "npm-managed-venv");
const MARKER_PATH = path.join(LOGION_DIR, "npm-wrapper-installer.json");
const LOCAL_BIN = path.join(HOME, ".local", "bin");

type Installer = "pipx" | "uv" | "venv";

interface InstallerMarker {
  installer: Installer;
  version: string;
}

function log(msg: string): void {
  process.stderr.write(`[logion-uninstall] ${msg}\n`);
}

function readMarker(): InstallerMarker | null {
  try {
    const raw = fs.readFileSync(MARKER_PATH, "utf8");
    return JSON.parse(raw) as InstallerMarker;
  } catch {
    return null;
  }
}

function tryRun(file: string, args: string[]): void {
  const r = spawnSync(file, args, { encoding: "utf8", timeout: 10_000 });
  if (r.status !== 0) {
    log(`Warning: ${file} ${args.join(" ")} exited ${String(r.status)}.`);
  }
}

function removeManagedVenv(): void {
  if (!fs.existsSync(MANAGED_VENV_DIR)) {
    return;
  }
  try {
    fs.rmSync(MANAGED_VENV_DIR, { recursive: true, force: true });
    log(`Removed managed venv at ${MANAGED_VENV_DIR}`);
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    log(`Warning: could not remove managed venv: ${msg}`);
  }
}

function removeShims(): void {
  const names =
    process.platform === "win32"
      ? ["logion.exe", "lgn.exe", "logion.cmd", "lgn.cmd"]
      : ["logion", "lgn"];
  for (const name of names) {
    const link = path.join(LOCAL_BIN, name);
    try {
      const stat = fs.lstatSync(link);
      if (stat.isSymbolicLink() || stat.isFile()) {
        fs.unlinkSync(link);
      }
    } catch {
      // not present — fine
    }
  }
}

function main(): void {
  const marker = readMarker();
  if (!marker) {
    removeShims();
    return;
  }

  if (marker.installer === "venv") {
    removeManagedVenv();
    removeShims();
  } else if (marker.installer === "pipx" && which("pipx")) {
    log("Uninstalling logion-cli via pipx...");
    tryRun("pipx", ["uninstall", "logion-cli"]);
  } else if (marker.installer === "uv" && which("uv")) {
    log("Uninstalling logion-cli via uv tool...");
    tryRun("uv", ["tool", "uninstall", "logion-cli"]);
  }

  try {
    fs.unlinkSync(MARKER_PATH);
  } catch {
    // ignore
  }
}

main();
