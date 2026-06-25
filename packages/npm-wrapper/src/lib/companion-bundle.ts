// SPDX-License-Identifier: MIT
//
// Dev-rig companion bundle copy support for npm postinstall.
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

type LogFn = (msg: string) => void;

interface CompanionBundle {
  tarball: string;
  srcPath: string;
}

const LOGION_DIR = path.join(os.homedir(), ".logion");

// Stable, locale-independent ordering so tarball selection is deterministic
// across platforms (default Array.sort can be locale-sensitive).
function byCodePoint(a: string, b: string): number {
  if (a < b) {
    return -1;
  }
  if (a > b) {
    return 1;
  }
  return 0;
}

function listBundleSourceEntries(
  sourceDir: string,
  log: LogFn,
): string[] | null {
  try {
    return fs.readdirSync(sourceDir).sort(byCodePoint);
  } catch {
    log(
      `LOGION_COMPANION_BUNDLE_SOURCE=${sourceDir} read failed — ` +
        "skipping companion bundle copy.",
    );
    return null;
  }
}

function findCompanionTarball(
  sourceDir: string,
  entries: string[],
  log: LogFn,
): CompanionBundle | null {
  for (const name of entries) {
    if (!/^logion-marketplace-companion-.*\.tar\.gz$/.test(name)) {
      continue;
    }
    const candidatePath = path.join(sourceDir, name);
    try {
      if (fs.statSync(candidatePath).isFile()) {
        return { tarball: name, srcPath: candidatePath };
      }
    } catch {
      log(`Could not stat companion tarball candidate ${candidatePath}.`);
    }
  }
  return null;
}

function sha256File(filePath: string): string {
  const hash = crypto.createHash("sha256");
  const fd = fs.openSync(filePath, "r");
  const chunkSize = 64 * 1024;
  const buf = Buffer.alloc(chunkSize);
  let bytesRead: number;
  try {
    while ((bytesRead = fs.readSync(fd, buf, 0, chunkSize, null)) > 0) {
      hash.update(buf.subarray(0, bytesRead));
    }
  } finally {
    fs.closeSync(fd);
  }
  return hash.digest("hex");
}

function isBundleSourceDirectory(sourceDir: string, log: LogFn): boolean {
  if (!fs.existsSync(sourceDir)) {
    log(
      `LOGION_COMPANION_BUNDLE_SOURCE=${sourceDir} does not exist — ` +
        "skipping companion bundle copy.",
    );
    return false;
  }

  try {
    if (fs.statSync(sourceDir).isDirectory()) {
      return true;
    }
    log(
      `LOGION_COMPANION_BUNDLE_SOURCE=${sourceDir} is not a directory — ` +
        "skipping companion bundle copy.",
    );
  } catch {
    log(
      `LOGION_COMPANION_BUNDLE_SOURCE=${sourceDir} stat failed — ` +
        "skipping companion bundle copy.",
    );
  }
  return false;
}

function resolveCompanionBundle(
  sourceDir: string,
  log: LogFn,
): CompanionBundle | null {
  if (!isBundleSourceDirectory(sourceDir, log)) {
    return null;
  }

  const entries = listBundleSourceEntries(sourceDir, log);
  if (!entries) {
    return null;
  }

  const bundle = findCompanionTarball(sourceDir, entries, log);
  if (!bundle) {
    log(
      `No companion tarball found in ${sourceDir} — ` +
        "skipping companion bundle copy.",
    );
  }
  return bundle;
}

function copyCompanionBundle(bundle: CompanionBundle, log: LogFn): void {
  // Treat an unset *or empty* LOGION_HOME as "use the default" — matches the
  // historical resolveLogionHome() behavior; `??` alone would keep "".
  const envHome = process.env.LOGION_HOME;
  const logionHome = envHome && envHome.length > 0 ? envHome : LOGION_DIR;
  const bundlesDir = path.join(logionHome, "companion-bundles");
  fs.mkdirSync(bundlesDir, { recursive: true });

  const destPath = path.join(bundlesDir, bundle.tarball);
  fs.copyFileSync(bundle.srcPath, destPath);
  log(`Copied companion bundle to ${destPath}`);

  const sidecarName = bundle.tarball.replace(/\.tar\.gz$/, ".source.json");
  const sidecarPath = path.join(bundlesDir, sidecarName);
  const sidecar = {
    sourcePath: bundle.srcPath,
    sha256: sha256File(destPath),
    installedAt: new Date().toISOString(),
  };
  fs.writeFileSync(sidecarPath, `${JSON.stringify(sidecar, null, 2)}\n`);
  log(`Wrote companion marker ${sidecarPath}`);
}

/**
 * Copy the companion bundle from LOGION_COMPANION_BUNDLE_SOURCE into the
 * local companion-bundles directory.
 */
export function installCompanionBundle(log: LogFn): void {
  const sourceDir = process.env.LOGION_COMPANION_BUNDLE_SOURCE;
  if (!sourceDir) {
    return;
  }

  const bundle = resolveCompanionBundle(sourceDir, log);
  if (!bundle) {
    return;
  }

  try {
    copyCompanionBundle(bundle, log);
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    log(`Warning: companion bundle copy failed: ${msg}.`);
  }
}
