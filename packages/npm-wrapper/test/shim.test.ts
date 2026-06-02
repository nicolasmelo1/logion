// SPDX-License-Identifier: MIT
//
// Tests for the built dist/bin/{logion,lgn}.js shims.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { describe, expect, test } from "vitest";

const BIN_DIR = path.join(__dirname, "..", "dist", "bin");

describe("shim", () => {
  test("exits 127 when logion binary not found on PATH", () => {
    const nodeDir = path.dirname(process.execPath);
    const r = spawnSync(process.execPath, [path.join(BIN_DIR, "logion.js")], {
      env: { ...process.env, PATH: nodeDir },
      stdio: "pipe",
      timeout: 15_000,
    });
    expect(r.status).toBe(127);
    expect(r.stderr.toString()).toContain("not found");
  });

  test("exits 127 when lgn binary not found on PATH", () => {
    const nodeDir = path.dirname(process.execPath);
    const r = spawnSync(process.execPath, [path.join(BIN_DIR, "lgn.js")], {
      env: { ...process.env, PATH: nodeDir },
      stdio: "pipe",
      timeout: 15_000,
    });
    expect(r.status).toBe(127);
    expect(r.stderr.toString()).toContain("not found");
  });

  test("forwards arguments to logion binary when on PATH", () => {
    if (process.platform === "win32") {
      // POSIX shell-script fixtures don't run on Windows runners.
      return;
    }
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-shim-test-"));
    const binDir = path.join(tmp, "bin");
    fs.mkdirSync(binDir, { recursive: true });
    fs.writeFileSync(
      path.join(binDir, "logion"),
      '#!/bin/sh\necho "args: $*"\n',
      { mode: 0o755 },
    );

    const r = spawnSync(
      process.execPath,
      [path.join(BIN_DIR, "logion.js"), "--version"],
      {
        env: {
          ...process.env,
          PATH: binDir + path.delimiter + (process.env.PATH ?? ""),
        },
        stdio: "pipe",
        timeout: 15_000,
      },
    );

    fs.rmSync(tmp, { recursive: true, force: true });

    expect(r.status).toBe(0);
    expect(r.stdout.toString()).toContain("args: --version");
  });

  test("propagates exit code from underlying binary", () => {
    if (process.platform === "win32") {
      return;
    }
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-shim-test-"));
    const binDir = path.join(tmp, "bin");
    fs.mkdirSync(binDir, { recursive: true });
    fs.writeFileSync(path.join(binDir, "logion"), "#!/bin/sh\nexit 42\n", {
      mode: 0o755,
    });

    const r = spawnSync(process.execPath, [path.join(BIN_DIR, "logion.js")], {
      env: {
        ...process.env,
        PATH: binDir + path.delimiter + (process.env.PATH ?? ""),
      },
      stdio: "pipe",
      timeout: 15_000,
    });

    fs.rmSync(tmp, { recursive: true, force: true });

    expect(r.status).toBe(42);
  });
});
