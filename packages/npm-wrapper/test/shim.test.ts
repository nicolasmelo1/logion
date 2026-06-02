// SPDX-License-Identifier: MIT
//
// Tests for bin/logion.js and bin/lgn.js shims
import { describe, test, expect } from "vitest";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const DIST_DIR = path.join(__dirname, "..", "dist");
const BIN_DIR = path.join(DIST_DIR, "bin");

describe("shim", () => {
  test("exits 127 when logion binary not found on PATH", () => {
    const nodeDir = path.dirname(process.execPath);
    const r = spawnSync(process.execPath, [path.join(BIN_DIR, "logion.js")], {
      env: { ...process.env, PATH: nodeDir },
      stdio: "pipe",
      timeout: 15_000,
    });
    expect(r.status).toBe(127);
    const stderr = (r.stderr || Buffer.alloc(0)).toString();
    expect(stderr).toContain("not found");
  });

  test("exits 127 when lgn binary not found on PATH", () => {
    const nodeDir = path.dirname(process.execPath);
    const r = spawnSync(process.execPath, [path.join(BIN_DIR, "lgn.js")], {
      env: { ...process.env, PATH: nodeDir },
      stdio: "pipe",
      timeout: 15_000,
    });
    expect(r.status).toBe(127);
    const stderr = (r.stderr || Buffer.alloc(0)).toString();
    expect(stderr).toContain("not found");
  });

  test("forwards arguments to logion binary when on PATH", () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-shim-test-"));
    const binDir = path.join(tmp, "bin");
    fs.mkdirSync(binDir, { recursive: true });

    // Create a fake logion binary that echoes its args
    const fakePath = path.join(binDir, "logion");
    fs.writeFileSync(fakePath, '#!/bin/sh\necho "args: $@"\n', {
      mode: 0o755,
    });

    const r = spawnSync(
      process.execPath,
      [path.join(BIN_DIR, "logion.js"), "--version"],
      {
        env: { ...process.env, PATH: binDir + path.delimiter + process.env.PATH },
        stdio: "pipe",
        timeout: 15_000,
      }
    );

    fs.rmSync(tmp, { recursive: true, force: true });

    expect(r.status).toBe(0);
    expect(r.stdout.toString()).toContain("args: --version");
  });

  test("propagates exit code from underlying binary", () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-shim-test-"));
    const binDir = path.join(tmp, "bin");
    fs.mkdirSync(binDir, { recursive: true });

    // Create a fake logion binary that exits with code 42
    const fakePath = path.join(binDir, "logion");
    fs.writeFileSync(fakePath, "#!/bin/sh\nexit 42\n", { mode: 0o755 });

    const r = spawnSync(
      process.execPath,
      [path.join(BIN_DIR, "logion.js")],
      {
        env: { ...process.env, PATH: binDir + path.delimiter + process.env.PATH },
        stdio: "pipe",
        timeout: 15_000,
      }
    );

    fs.rmSync(tmp, { recursive: true, force: true });

    expect(r.status).toBe(42);
  });
});