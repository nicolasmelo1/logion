// SPDX-License-Identifier: MIT
//
// Tests for version pinning and package.json shape
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { execSync } = require("node:child_process");
const { test, describe } = require("node:test");
const assert = require("node:assert/strict");

const PKG_DIR = path.join(__dirname, "..");
const PKG_PATH = path.join(PKG_DIR, "package.json");

describe("version", () => {
  test("package.json version is 0.0.0-placeholder in repo", () => {
    const pkg = JSON.parse(fs.readFileSync(PKG_PATH, "utf8"));
    assert.equal(pkg.version, "0.0.0-placeholder");
  });

  test("version_from_manifest writes real version into package.json", () => {
    // Read manifest
    const manifestPath = path.join(PKG_DIR, "..", "..", "releases", "manifest-stable.json");
    assert.ok(fs.existsSync(manifestPath), "manifest-stable.json should exist");
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    const cliVersion = manifest.packages["logion-cli"].version;

    // Run version_from_manifest
    execSync("node " + path.join(PKG_DIR, "scripts", "version_from_manifest.js"), {
      cwd: PKG_DIR,
      stdio: "pipe",
    });

    const updatedPkg = JSON.parse(fs.readFileSync(PKG_PATH, "utf8"));
    assert.equal(updatedPkg.version, cliVersion);
    assert.equal(updatedPkg.logionCliVersion, cliVersion);

    // Restore original version
    const originalPkg = { ...updatedPkg, version: "0.0.0-placeholder" };
    delete originalPkg.logionCliVersion;
    fs.writeFileSync(PKG_PATH, JSON.stringify(originalPkg, null, 2) + "\n");
  });

  test("files array excludes tests", () => {
    const pkg = JSON.parse(fs.readFileSync(PKG_PATH, "utf8"));
    assert.ok(!pkg.files.includes("test/"), "test/ should not be in files array");
  });
});