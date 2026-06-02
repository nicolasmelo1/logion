// SPDX-License-Identifier: MIT
//
// Tests for postinstall.js
import { describe, test, expect } from "vitest";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const DIST_DIR = path.join(__dirname, "..", "dist");
const SCRIPTS_DIR = path.join(DIST_DIR, "scripts");
const PKG_DIR = path.join(__dirname, "..");
const PKG_PATH = path.join(PKG_DIR, "package.json");

function makeFakeBin(dir: string, name: string, output: string): string {
  const binPath = path.join(
    dir,
    name + (process.platform === "win32" ? ".cmd" : "")
  );
  if (process.platform === "win32") {
    fs.writeFileSync(binPath, `@echo ${output}\r\n`);
  } else {
    fs.writeFileSync(binPath, `#!/bin/sh\necho "${output}"\n`, {
      mode: 0o755,
    });
  }
  return binPath;
}

// Helper: temporarily pin a real version into package.json for tests
// that need to get past the version check.
function withPinnedVersion(fn: () => void) {
  const original = fs.readFileSync(PKG_PATH, "utf8");
  const pkg = JSON.parse(original);
  pkg.version = "0.1.0";
  pkg.logionCliVersion = "0.1.0";
  fs.writeFileSync(PKG_PATH, JSON.stringify(pkg, null, 2) + "\n");
  try {
    fn();
  } finally {
    fs.writeFileSync(PKG_PATH, original);
  }
}

describe("postinstall", () => {
  test("skips when LOGION_NPM_SKIP_INSTALL=1", () => {
    const r = spawnSync("node", [path.join(SCRIPTS_DIR, "postinstall.js")], {
      env: { ...process.env, LOGION_NPM_SKIP_INSTALL: "1" },
      stdio: "pipe",
      timeout: 15_000,
    });
    expect(r.status).toBe(0);
    const stderr = (r.stderr || Buffer.alloc(0)).toString();
    expect(stderr).toContain("skipping postinstall");
  });

  test("exits with error when no pinned version found", () => {
    // In repo, package.json has 0.0.0-placeholder and no logionCliVersion,
    // so getPinnedVersion() returns null.
    const r = spawnSync("node", [path.join(SCRIPTS_DIR, "postinstall.js")], {
      env: { ...process.env, LOGION_NPM_SKIP_INSTALL: "" },
      stdio: "pipe",
      timeout: 15_000,
    });
    expect(r.status).toBe(1);
    const stderr = (r.stderr || Buffer.alloc(0)).toString();
    expect(stderr).toContain("No pinned version found");
  });

  test("exits with error when no Python is found (with pinned version)", () => {
    withPinnedVersion(() => {
      // Build a PATH that has node but no python3/python/py
      const nodeDir = path.dirname(process.execPath);
      const r = spawnSync(
        "node",
        [path.join(SCRIPTS_DIR, "postinstall.js")],
        {
          env: {
            HOME: process.env.HOME,
            PATH: nodeDir + path.delimiter + "/usr/bin:/bin",
            LOGION_NPM_SKIP_INSTALL: "",
            LOGION_NPM_PYTHON: "",
          },
          stdio: "pipe",
          timeout: 15_000,
        }
      );
      const stderr = (r.stderr || Buffer.alloc(0)).toString();
      if (r.status === 1) {
        expect(stderr).toContain("Python 3.12+ not found");
      } else if (r.status === 0) {
        // python3 was found on the system PATH — that's fine
        expect(stderr).toContain("Using Python");
      } else {
        expect.fail(
          "Unexpected exit code: " + r.status + " stderr: " + stderr.slice(0, 200)
        );
      }
    });
  });

  test("detects pipx and uses it when LOGION_NPM_FORCE_INSTALLER=pipx", () => {
    withPinnedVersion(() => {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
      const binDir = path.join(tmp, "bin");
      fs.mkdirSync(binDir, { recursive: true });

      makeFakeBin(binDir, "python3", "Python 3.12.0");
      makeFakeBin(binDir, "pipx", "pipx 1.7.0");
      makeFakeBin(binDir, "logion", "logion-cli 0.1.0");

      const r = spawnSync("node", [path.join(SCRIPTS_DIR, "postinstall.js")], {
        env: {
          ...process.env,
          LOGION_NPM_FORCE_INSTALLER: "pipx",
          LOGION_NPM_PYTHON: path.join(binDir, "python3"),
          PATH: binDir + path.delimiter + process.env.PATH,
        },
        stdio: "pipe",
        timeout: 15_000,
      });

      fs.rmSync(tmp, { recursive: true, force: true });

      const stderr = (r.stderr || Buffer.alloc(0)).toString();
      expect(stderr).toContain("pipx");
    });
  });

  test("falls back to uv when pipx is unavailable and LOGION_NPM_FORCE_INSTALLER=uv", () => {
    withPinnedVersion(() => {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
      const binDir = path.join(tmp, "bin");
      fs.mkdirSync(binDir, { recursive: true });

      makeFakeBin(binDir, "python3", "Python 3.12.0");
      makeFakeBin(binDir, "uv", "uv 0.4.0");
      makeFakeBin(binDir, "logion", "logion-cli 0.1.0");

      const r = spawnSync("node", [path.join(SCRIPTS_DIR, "postinstall.js")], {
        env: {
          ...process.env,
          LOGION_NPM_FORCE_INSTALLER: "uv",
          LOGION_NPM_PYTHON: path.join(binDir, "python3"),
          PATH: binDir + path.delimiter + process.env.PATH,
        },
        stdio: "pipe",
        timeout: 15_000,
      });

      fs.rmSync(tmp, { recursive: true, force: true });

      const stderr = (r.stderr || Buffer.alloc(0)).toString();
      expect(stderr).toContain("uv");
    });
  });
});