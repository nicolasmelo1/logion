// SPDX-License-Identifier: MIT
//
// Tests for the built dist/scripts/postinstall.js entry point.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { describe, expect, test } from "vitest";

const DIST_DIR = path.join(__dirname, "..", "dist");
const SCRIPTS_DIR = path.join(DIST_DIR, "scripts");
const PKG_DIR = path.join(__dirname, "..");
const PKG_PATH = path.join(PKG_DIR, "package.json");

function makeFakeBin(dir: string, name: string, output: string): string {
  const ext = process.platform === "win32" ? ".cmd" : "";
  const binPath = path.join(dir, name + ext);
  if (process.platform === "win32") {
    fs.writeFileSync(binPath, `@echo ${output}\r\n`);
  } else {
    fs.writeFileSync(binPath, `#!/bin/sh\necho "${output}"\n`, {
      mode: 0o755,
    });
  }
  return binPath;
}

function withPinnedVersion(fn: () => void): void {
  const original = fs.readFileSync(PKG_PATH, "utf8");
  const pkg = JSON.parse(original) as Record<string, unknown>;
  pkg.version = "0.1.0";
  pkg.logionCliVersion = "0.1.0";
  fs.writeFileSync(PKG_PATH, `${JSON.stringify(pkg, null, 2)}\n`);
  try {
    fn();
  } finally {
    fs.writeFileSync(PKG_PATH, original);
  }
}

describe("postinstall", () => {
  test("skips when LOGION_NPM_SKIP_INSTALL=1", () => {
    const r = spawnSync(
      process.execPath,
      [path.join(SCRIPTS_DIR, "postinstall.js")],
      {
        env: { ...process.env, LOGION_NPM_SKIP_INSTALL: "1" },
        stdio: "pipe",
        timeout: 15_000,
      },
    );
    expect(r.status).toBe(0);
    expect(r.stderr.toString()).toContain("skipping postinstall");
  });

  test("exits with error when no pinned version found", () => {
    const r = spawnSync(
      process.execPath,
      [path.join(SCRIPTS_DIR, "postinstall.js")],
      {
        env: { ...process.env, LOGION_NPM_SKIP_INSTALL: "" },
        stdio: "pipe",
        timeout: 15_000,
      },
    );
    expect(r.status).toBe(1);
    expect(r.stderr.toString()).toContain("No pinned version found");
  });

  test("exits with error when no Python is found", () => {
    withPinnedVersion(() => {
      // Restrict PATH to only the node bin dir so detection is
      // deterministic across runner environments.
      const nodeDir = path.dirname(process.execPath);
      const r = spawnSync(
        process.execPath,
        [path.join(SCRIPTS_DIR, "postinstall.js")],
        {
          env: {
            HOME: process.env.HOME ?? os.homedir(),
            USERPROFILE: process.env.USERPROFILE ?? os.homedir(),
            PATH: nodeDir,
            LOGION_NPM_SKIP_INSTALL: "",
            LOGION_NPM_PYTHON: "",
          },
          stdio: "pipe",
          timeout: 15_000,
        },
      );
      const stderr = r.stderr.toString();
      expect(r.status).toBe(1);
      expect(stderr).toContain("Python 3.12+ not found");
    });
  });

  test("uses pipx when LOGION_NPM_FORCE_INSTALLER=pipx", () => {
    withPinnedVersion(() => {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
      const binDir = path.join(tmp, "bin");
      fs.mkdirSync(binDir, { recursive: true });

      const pyPath = makeFakeBin(binDir, "python3", "Python 3.12.0");
      makeFakeBin(binDir, "pipx", "pipx 1.7.0");
      makeFakeBin(binDir, "logion", "logion-cli 0.1.0");

      const r = spawnSync(
        process.execPath,
        [path.join(SCRIPTS_DIR, "postinstall.js")],
        {
          env: {
            ...process.env,
            LOGION_NPM_FORCE_INSTALLER: "pipx",
            LOGION_NPM_PYTHON: pyPath,
            PATH: binDir + path.delimiter + (process.env.PATH ?? ""),
          },
          stdio: "pipe",
          timeout: 15_000,
        },
      );

      fs.rmSync(tmp, { recursive: true, force: true });

      expect(r.stderr.toString()).toContain("pipx");
    });
  });

  test("uses uv when LOGION_NPM_FORCE_INSTALLER=uv", () => {
    withPinnedVersion(() => {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
      const binDir = path.join(tmp, "bin");
      fs.mkdirSync(binDir, { recursive: true });

      const pyPath = makeFakeBin(binDir, "python3", "Python 3.12.0");
      makeFakeBin(binDir, "uv", "uv 0.4.0");
      makeFakeBin(binDir, "logion", "logion-cli 0.1.0");

      const r = spawnSync(
        process.execPath,
        [path.join(SCRIPTS_DIR, "postinstall.js")],
        {
          env: {
            ...process.env,
            LOGION_NPM_FORCE_INSTALLER: "uv",
            LOGION_NPM_PYTHON: pyPath,
            PATH: binDir + path.delimiter + (process.env.PATH ?? ""),
          },
          stdio: "pipe",
          timeout: 15_000,
        },
      );

      fs.rmSync(tmp, { recursive: true, force: true });

      expect(r.stderr.toString()).toContain("uv");
    });
  });
});
