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
  test("skips CLI install when LOGION_NPM_SKIP_INSTALL=1", () => {
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
    expect(r.stderr.toString()).toContain("skipping CLI install");
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
      try {
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

        expect(r.stderr.toString()).toContain("pipx");
      } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
      }
    });
  });

  test("uses uv when LOGION_NPM_FORCE_INSTALLER=uv", () => {
    withPinnedVersion(() => {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
      try {
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

        expect(r.stderr.toString()).toContain("uv");
      } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
      }
    });
  });

  test("handles companion bundle even when LOGION_NPM_SKIP_INSTALL=1", () => {
    withPinnedVersion(() => {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
      try {
        const binDir = path.join(tmp, "bin");
        fs.mkdirSync(binDir, { recursive: true });

        const pyPath = makeFakeBin(binDir, "python3", "Python 3.12.0");
        makeFakeBin(binDir, "pipx", "pipx 1.7.0");
        makeFakeBin(binDir, "logion", "logion-cli 0.1.0");

        // Create a fake companion bundle source directory.
        const companionSource = path.join(tmp, "companion-source");
        fs.mkdirSync(companionSource, { recursive: true });
        const tarballName = "logion-marketplace-companion-0.1.0.tar.gz";
        fs.writeFileSync(
          path.join(companionSource, tarballName),
          "fake-companion-content",
        );

        const logionHome = path.join(tmp, "logion-home");
        fs.mkdirSync(logionHome, { recursive: true });

        const result = spawnSync(
          process.execPath,
          [path.join(SCRIPTS_DIR, "postinstall.js")],
          {
            env: {
              ...process.env,
              LOGION_NPM_SKIP_INSTALL: "1",
              LOGION_NPM_FORCE_INSTALLER: "pipx",
              LOGION_NPM_PYTHON: pyPath,
              LOGION_COMPANION_BUNDLE_SOURCE: companionSource,
              LOGION_HOME: logionHome,
              HOME: tmp,
              USERPROFILE: tmp,
              PATH: binDir + path.delimiter + (process.env.PATH ?? ""),
            },
            stdio: "pipe",
            timeout: 15_000,
          },
        );
        expect(result.status).toBe(0);
        expect(result.stderr.toString()).toContain("skipping CLI install");

        // Companion bundle should still be copied.
        const bundlesDir = path.join(logionHome, "companion-bundles");
        const destTarball = path.join(bundlesDir, tarballName);
        expect(fs.existsSync(destTarball)).toBe(true);
      } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
      }
    });
  });

  test("copies companion bundle when LOGION_COMPANION_BUNDLE_SOURCE is set", () => {
    withPinnedVersion(() => {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
      try {
        const binDir = path.join(tmp, "bin");
        fs.mkdirSync(binDir, { recursive: true });

        const pyPath = makeFakeBin(binDir, "python3", "Python 3.12.0");
        makeFakeBin(binDir, "pipx", "pipx 1.7.0");
        makeFakeBin(binDir, "logion", "logion-cli 0.1.0");

        // Create a fake companion bundle source directory.
        const companionSource = path.join(tmp, "companion-source");
        fs.mkdirSync(companionSource, { recursive: true });
        const tarballName = "logion-marketplace-companion-0.1.0.tar.gz";
        fs.writeFileSync(
          path.join(companionSource, tarballName),
          "fake-companion-content",
        );

        // LOGION_HOME points to a temp directory.
        const logionHome = path.join(tmp, "logion-home");
        fs.mkdirSync(logionHome, { recursive: true });

        const result = spawnSync(
          process.execPath,
          [path.join(SCRIPTS_DIR, "postinstall.js")],
          {
            env: {
              ...process.env,
              LOGION_NPM_FORCE_INSTALLER: "pipx",
              LOGION_NPM_PYTHON: pyPath,
              LOGION_COMPANION_BUNDLE_SOURCE: companionSource,
              LOGION_HOME: logionHome,
              HOME: tmp,
              USERPROFILE: tmp,
              PATH: binDir + path.delimiter + (process.env.PATH ?? ""),
            },
            stdio: "pipe",
            timeout: 15_000,
          },
        );
        expect(result.status).toBe(0);

        // Companion bundle should be copied to $LOGION_HOME/companion-bundles/
        const bundlesDir = path.join(logionHome, "companion-bundles");
        const destTarball = path.join(bundlesDir, tarballName);
        expect(fs.existsSync(destTarball)).toBe(true);

        // Sidecar marker should exist.
        const sidecarName = tarballName.replace(/\.tar\.gz$/, ".source.json");
        const sidecarPath = path.join(bundlesDir, sidecarName);
        expect(fs.existsSync(sidecarPath)).toBe(true);
        const sidecar = JSON.parse(
          fs.readFileSync(sidecarPath, "utf8"),
        ) as Record<string, unknown>;
        expect(sidecar.sourcePath).toBe(
          path.join(companionSource, tarballName),
        );
        expect(typeof sidecar.sha256).toBe("string");
        expect(sidecar.sha256).toHaveLength(64);
      } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
      }
    });
  });

  test("does not copy companion when LOGION_COMPANION_BUNDLE_SOURCE is unset", () => {
    withPinnedVersion(() => {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
      try {
        const binDir = path.join(tmp, "bin");
        fs.mkdirSync(binDir, { recursive: true });

        const pyPath = makeFakeBin(binDir, "python3", "Python 3.12.0");
        makeFakeBin(binDir, "pipx", "pipx 1.7.0");
        makeFakeBin(binDir, "logion", "logion-cli 0.1.0");

        const logionHome = path.join(tmp, "logion-home");
        fs.mkdirSync(logionHome, { recursive: true });

        const result = spawnSync(
          process.execPath,
          [path.join(SCRIPTS_DIR, "postinstall.js")],
          {
            env: {
              ...process.env,
              LOGION_NPM_FORCE_INSTALLER: "pipx",
              LOGION_NPM_PYTHON: pyPath,
              // Intentionally NOT setting LOGION_COMPANION_BUNDLE_SOURCE
              LOGION_HOME: logionHome,
              HOME: tmp,
              USERPROFILE: tmp,
              PATH: binDir + path.delimiter + (process.env.PATH ?? ""),
            },
            stdio: "pipe",
            timeout: 15_000,
          },
        );
        expect(result.status).toBe(0);

        // No companion-bundles directory should be created.
        const bundlesDir = path.join(logionHome, "companion-bundles");
        expect(fs.existsSync(bundlesDir)).toBe(false);
      } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
      }
    });
  });

  test("falls back to ~/.logion when LOGION_HOME is unset for companion bundle", () => {
    withPinnedVersion(() => {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logion-test-"));
      try {
        const binDir = path.join(tmp, "bin");
        fs.mkdirSync(binDir, { recursive: true });

        const pyPath = makeFakeBin(binDir, "python3", "Python 3.12.0");
        makeFakeBin(binDir, "pipx", "pipx 1.7.0");
        makeFakeBin(binDir, "logion", "logion-cli 0.1.0");

        // Set up companion source.
        const companionSource = path.join(tmp, "companion-source");
        fs.mkdirSync(companionSource, { recursive: true });
        const tarballName = "logion-marketplace-companion-0.1.0.tar.gz";
        fs.writeFileSync(
          path.join(companionSource, tarballName),
          "fake-content",
        );

        // Override HOME (and USERPROFILE for Windows runners) so we don't
        // pollute real ~/.logion.
        const fakeHome = path.join(tmp, "home");
        fs.mkdirSync(fakeHome, { recursive: true });

        const result = spawnSync(
          process.execPath,
          [path.join(SCRIPTS_DIR, "postinstall.js")],
          {
            env: {
              ...process.env,
              HOME: fakeHome,
              USERPROFILE: fakeHome,
              LOGION_NPM_FORCE_INSTALLER: "pipx",
              LOGION_NPM_PYTHON: pyPath,
              LOGION_COMPANION_BUNDLE_SOURCE: companionSource,
              // Intentionally NOT setting LOGION_HOME
              PATH: binDir + path.delimiter + (process.env.PATH ?? ""),
            },
            stdio: "pipe",
            timeout: 15_000,
          },
        );
        expect(result.status).toBe(0);

        // Should fall back to $HOME/.logion/companion-bundles/
        const bundlesDir = path.join(fakeHome, ".logion", "companion-bundles");
        expect(fs.existsSync(bundlesDir)).toBe(true);
      } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
      }
    });
  });
});
