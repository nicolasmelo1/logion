// SPDX-License-Identifier: MIT
//
// Tests for version pinning and package.json shape.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { describe, expect, test } from "vitest";

const PKG_DIR = path.join(__dirname, "..");
const DIST_DIR = path.join(PKG_DIR, "dist");
const PKG_PATH = path.join(PKG_DIR, "package.json");

describe("version", () => {
  test("package.json version is 0.0.0-placeholder in repo", () => {
    const pkg = JSON.parse(fs.readFileSync(PKG_PATH, "utf8")) as {
      version: string;
    };
    expect(pkg.version).toBe("0.0.0-placeholder");
  });

  test("version-from-manifest writes real version into package.json", () => {
    const manifestPath = path.join(
      PKG_DIR,
      "..",
      "..",
      "releases",
      "manifest-stable.json",
    );
    expect(fs.existsSync(manifestPath)).toBe(true);
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8")) as {
      packages: Record<string, { version: string }>;
    };
    const cliVersion = manifest.packages["logion-cli"].version;

    const original = fs.readFileSync(PKG_PATH, "utf8");
    try {
      const r = spawnSync(
        process.execPath,
        [path.join(DIST_DIR, "scripts", "version-from-manifest.js")],
        { cwd: PKG_DIR, stdio: "pipe" },
      );
      expect(r.status).toBe(0);

      const updated = JSON.parse(fs.readFileSync(PKG_PATH, "utf8")) as {
        version: string;
        logionCliVersion: string;
      };
      expect(updated.version).toBe(cliVersion);
      expect(updated.logionCliVersion).toBe(cliVersion);
    } finally {
      fs.writeFileSync(PKG_PATH, original);
    }
  });

  test("files array excludes tests", () => {
    const pkg = JSON.parse(fs.readFileSync(PKG_PATH, "utf8")) as {
      files: string[];
    };
    expect(pkg.files).not.toContain("test/");
  });
});
