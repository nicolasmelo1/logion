// SPDX-License-Identifier: MIT
//
// Tests for version pinning and package.json shape
import { describe, test, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const PKG_DIR = path.join(__dirname, "..");
const DIST_DIR = path.join(PKG_DIR, "dist");
const PKG_PATH = path.join(PKG_DIR, "package.json");

describe("version", () => {
  test("package.json version is 0.0.0-placeholder in repo", () => {
    const pkg = JSON.parse(fs.readFileSync(PKG_PATH, "utf8"));
    expect(pkg.version).toBe("0.0.0-placeholder");
  });

  test("version-from-manifest writes real version into package.json", () => {
    const manifestPath = path.join(
      PKG_DIR,
      "..",
      "..",
      "releases",
      "manifest-stable.json"
    );
    expect(fs.existsSync(manifestPath)).toBe(true);
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    const cliVersion = manifest.packages["logion-cli"].version;

    // Run built version-from-manifest
    execSync("node " + path.join(DIST_DIR, "scripts", "version-from-manifest.js"), {
      cwd: PKG_DIR,
      stdio: "pipe",
    });

    const updatedPkg = JSON.parse(fs.readFileSync(PKG_PATH, "utf8"));
    expect(updatedPkg.version).toBe(cliVersion);
    expect(updatedPkg.logionCliVersion).toBe(cliVersion);

    // Restore original version
    const originalPkg = { ...updatedPkg, version: "0.0.0-placeholder" };
    delete originalPkg.logionCliVersion;
    fs.writeFileSync(PKG_PATH, JSON.stringify(originalPkg, null, 2) + "\n");
  });

  test("files array excludes tests", () => {
    const pkg = JSON.parse(fs.readFileSync(PKG_PATH, "utf8"));
    expect(pkg.files).not.toContain("test/");
  });
});