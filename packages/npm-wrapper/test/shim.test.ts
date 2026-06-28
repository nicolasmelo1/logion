// SPDX-License-Identifier: MIT
//
// Tests for the built dist/bin/logion.js shim.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { describe, expect, test } from "vitest";

const BIN_DIR = path.join(__dirname, "..", "dist", "bin");

function makeManagedLogion(home: string, body: string): void {
  const logionPath =
    process.platform === "win32"
      ? path.join(home, ".logion", "npm-managed-venv", "Scripts", "logion.exe")
      : path.join(home, ".logion", "npm-managed-venv", "bin", "logion");
  fs.mkdirSync(path.dirname(logionPath), { recursive: true });
  fs.writeFileSync(logionPath, body, { mode: 0o755 });
}

describe("shim", () => {
  test("exits 127 when managed logion binary is missing", () => {
    const nodeDir = path.dirname(process.execPath);
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-shim-test-"));
    const r = spawnSync(process.execPath, [path.join(BIN_DIR, "logion.js")], {
      env: {
        ...process.env,
        HOME: tmp,
        USERPROFILE: tmp,
        PATH: nodeDir,
      },
      stdio: "pipe",
      timeout: 15_000,
    });
    fs.rmSync(tmp, { recursive: true, force: true });
    expect(r.status).toBe(127);
    expect(r.stderr.toString()).toContain("npm-managed environment");
  });

  test("forwards arguments to npm-managed logion binary", () => {
    if (process.platform === "win32") {
      // POSIX shell-script fixtures don't run on Windows runners.
      return;
    }
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-shim-test-"));
    makeManagedLogion(tmp, '#!/bin/sh\necho "args: $*"\n');

    const r = spawnSync(
      process.execPath,
      [path.join(BIN_DIR, "logion.js"), "--version"],
      {
        env: {
          ...process.env,
          HOME: tmp,
          USERPROFILE: tmp,
        },
        stdio: "pipe",
        timeout: 15_000,
      },
    );

    fs.rmSync(tmp, { recursive: true, force: true });

    expect(r.status).toBe(0);
    expect(r.stdout.toString()).toContain("args: --version");
  });

  test("ignores unrelated logion binaries on PATH", () => {
    if (process.platform === "win32") {
      return;
    }
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-shim-test-"));
    const staleBinDir = path.join(tmp, "stale-bin");
    fs.mkdirSync(staleBinDir, { recursive: true });
    fs.writeFileSync(
      path.join(staleBinDir, "logion"),
      '#!/bin/sh\necho "stale: $*"\n',
      { mode: 0o755 },
    );
    makeManagedLogion(tmp, '#!/bin/sh\necho "managed: $*"\n');

    const r = spawnSync(
      process.execPath,
      [path.join(BIN_DIR, "logion.js"), "--version"],
      {
        env: {
          ...process.env,
          HOME: tmp,
          USERPROFILE: tmp,
          PATH: staleBinDir + path.delimiter + (process.env.PATH ?? ""),
        },
        stdio: "pipe",
        timeout: 15_000,
      },
    );

    fs.rmSync(tmp, { recursive: true, force: true });

    expect(r.status).toBe(0);
    expect(r.stdout.toString()).toContain("managed: --version");
    expect(r.stdout.toString()).not.toContain("stale");
  });

  test("propagates exit code from underlying binary", () => {
    if (process.platform === "win32") {
      return;
    }
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-shim-test-"));
    makeManagedLogion(tmp, "#!/bin/sh\nexit 42\n");

    const r = spawnSync(process.execPath, [path.join(BIN_DIR, "logion.js")], {
      env: {
        ...process.env,
        HOME: tmp,
        USERPROFILE: tmp,
      },
      stdio: "pipe",
      timeout: 15_000,
    });

    fs.rmSync(tmp, { recursive: true, force: true });

    expect(r.status).toBe(42);
  });
});
