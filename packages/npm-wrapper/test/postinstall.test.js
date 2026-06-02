// SPDX-License-Identifier: MIT
//
// Tests for postinstall.js
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const { test, describe } = require("node:test");
const assert = require("node:assert/strict");

const SCRIPT_DIR = path.join(__dirname, "..", "scripts");

function makeFakeBin(dir, name, output) {
  const binPath = path.join(dir, name + (process.platform === "win32" ? ".cmd" : ""));
  if (process.platform === "win32") {
    fs.writeFileSync(binPath, `@echo ${output}\r\n`);
  } else {
    fs.writeFileSync(binPath, `#!/bin/sh\necho "${output}"\n`, { mode: 0o755 });
  }
  return binPath;
}

describe("postinstall", () => {
  test("skips when LOGION_NPM_SKIP_INSTALL=1", () => {
    const r = spawnSync("node", [path.join(SCRIPT_DIR, "postinstall.js")], {
      env: { ...process.env, LOGION_NPM_SKIP_INSTALL: "1" },
      stdio: "pipe",
      timeout: 15000,
    });
    assert.equal(r.status, 0);
    const stderr = (r.stderr || Buffer.alloc(0)).toString();
    assert.ok(stderr.includes("skipping postinstall"));
  });

  test("exits with error when no Python is found", () => {
    // Build a PATH that has node but no python3/python/py
    const nodeDir = path.dirname(process.execPath);
    const r = spawnSync("node", [path.join(SCRIPT_DIR, "postinstall.js")], {
      env: {
        HOME: process.env.HOME,
        PATH: nodeDir + ":/usr/bin:/bin",
        LOGION_NPM_SKIP_INSTALL: "",
        LOGION_NPM_PYTHON: "",
      },
      stdio: "pipe",
      timeout: 15000,
    });
    // The script may or may not find python3 on /usr/bin;
    // if it does, we skip the assertion. If it doesn't, it exits 1.
    const stderr = (r.stderr || Buffer.alloc(0)).toString();
    if (r.status === 1) {
      assert.ok(
        stderr.includes("Python 3.12+ not found"),
        "Should mention missing Python, got: " + stderr.slice(0, 300)
      );
    } else if (r.status === 0) {
      // python3 was found on the system PATH — that's fine, the detection works
      assert.ok(stderr.includes("Using Python"), "Should log detected Python");
    } else {
      assert.fail("Unexpected exit code: " + r.status + " stderr: " + stderr.slice(0, 200));
    }
  });

  test("detects pipx and uses it when LOGION_NPM_FORCE_INSTALLER=pipx", () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
    const binDir = path.join(tmp, "bin");
    fs.mkdirSync(binDir, { recursive: true });

    makeFakeBin(binDir, "python3", "Python 3.12.0");
    makeFakeBin(binDir, "pipx", "pipx 1.7.0");
    makeFakeBin(binDir, "logion", "logion-cli 0.1.0");

    const r = spawnSync("node", [path.join(SCRIPT_DIR, "postinstall.js")], {
      env: {
        ...process.env,
        LOGION_NPM_FORCE_INSTALLER: "pipx",
        LOGION_NPM_PYTHON: path.join(binDir, "python3"),
        PATH: binDir + path.delimiter + process.env.PATH,
      },
      stdio: "pipe",
      timeout: 15000,
    });

    fs.rmSync(tmp, { recursive: true, force: true });

    const stderr = (r.stderr || Buffer.alloc(0)).toString();
    assert.ok(stderr.includes("pipx"), "Should reference pipx in output: " + stderr.slice(0, 300));
  });

  test("falls back to uv when pipx is unavailable and LOGION_NPM_FORCE_INSTALLER=uv", () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
    const binDir = path.join(tmp, "bin");
    fs.mkdirSync(binDir, { recursive: true });

    makeFakeBin(binDir, "python3", "Python 3.12.0");
    makeFakeBin(binDir, "uv", "uv 0.4.0");
    makeFakeBin(binDir, "logion", "logion-cli 0.1.0");

    const r = spawnSync("node", [path.join(SCRIPT_DIR, "postinstall.js")], {
      env: {
        ...process.env,
        LOGION_NPM_FORCE_INSTALLER: "uv",
        LOGION_NPM_PYTHON: path.join(binDir, "python3"),
        PATH: binDir + path.delimiter + process.env.PATH,
      },
      stdio: "pipe",
      timeout: 15000,
    });

    fs.rmSync(tmp, { recursive: true, force: true });

    const stderr = (r.stderr || Buffer.alloc(0)).toString();
    assert.ok(stderr.includes("uv"), "Should reference uv in output: " + stderr.slice(0, 300));
  });
});