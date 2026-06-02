// SPDX-License-Identifier: MIT
//
// Tests for bin/logion.js and bin/lgn.js shims
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const { test, describe } = require("node:test");
const assert = require("node:assert/strict");

const BIN_DIR = path.join(__dirname, "..", "bin");

describe("shim", () => {
  test("exits 127 when logion binary not found on PATH", () => {
    // Keep node available but strip everything else
    const nodeDir = path.dirname(process.execPath);
    const r = spawnSync(process.execPath, [path.join(BIN_DIR, "logion.js")], {
      env: { ...process.env, PATH: nodeDir },
      stdio: "pipe",
      timeout: 15000,
    });
    // The shim exits 127 when binary not found
    assert.equal(r.status, 127);
    const stderr = (r.stderr || Buffer.alloc(0)).toString();
    assert.ok(stderr.includes("not found"), "Should mention 'not found'");
  });

  test("exits 127 when lgn binary not found on PATH", () => {
    const nodeDir = path.dirname(process.execPath);
    const r = spawnSync(process.execPath, [path.join(BIN_DIR, "lgn.js")], {
      env: { ...process.env, PATH: nodeDir },
      stdio: "pipe",
      timeout: 15000,
    });
    assert.equal(r.status, 127);
    const stderr = (r.stderr || Buffer.alloc(0)).toString();
    assert.ok(stderr.includes("not found"), "Should mention 'not found'");
  });

  test("forwards arguments to logion binary when on PATH", () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-shim-test-"));
    const binDir = path.join(tmp, "bin");
    fs.mkdirSync(binDir, { recursive: true });

    // Create a fake logion binary that echoes its args
    const fakePath = path.join(binDir, "logion");
    fs.writeFileSync(fakePath, "#!/bin/sh\necho \"args: $@\"\n", { mode: 0o755 });

    const r = spawnSync("node", [path.join(BIN_DIR, "logion.js"), "--version"], {
      env: { ...process.env, PATH: binDir + path.delimiter + process.env.PATH },
      stdio: "pipe",
      timeout: 15000,
    });

    fs.rmSync(tmp, { recursive: true, force: true });

    assert.equal(r.status, 0);
    assert.ok(r.stdout.toString().includes("args: --version"));
  });

  test("propagates exit code from underlying binary", () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-shim-test-"));
    const binDir = path.join(tmp, "bin");
    fs.mkdirSync(binDir, { recursive: true });

    // Create a fake logion binary that exits with code 42
    const fakePath = path.join(binDir, "logion");
    fs.writeFileSync(fakePath, "#!/bin/sh\nexit 42\n", { mode: 0o755 });

    const r = spawnSync("node", [path.join(BIN_DIR, "logion.js")], {
      env: { ...process.env, PATH: binDir + path.delimiter + process.env.PATH },
      stdio: "pipe",
      timeout: 15000,
    });

    fs.rmSync(tmp, { recursive: true, force: true });

    assert.equal(r.status, 42);
  });
});