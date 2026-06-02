// SPDX-License-Identifier: MIT
//
// version_from_manifest.js — reads releases/manifest-stable.json and
// writes the CLI version into package.json's "logionCliVersion" and
// "version" fields.  Run as prepublishOnly.
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const PKG_DIR = path.join(__dirname, "..");
const MANIFEST_PATH = path.join(PKG_DIR, "..", "..", "releases", "manifest-stable.json");

function main() {
  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf8"));
  } catch {
    console.error("Could not read manifest at " + MANIFEST_PATH);
    console.error("Run `make release-manifest` to generate it first.");
    process.exit(1);
  }

  const cliPkg = manifest.packages && manifest.packages["logion-cli"];
  if (!cliPkg || !cliPkg.version) {
    console.error("Manifest does not contain logion-cli version.");
    process.exit(1);
  }

  const version = cliPkg.version;
  const pkgPath = path.join(PKG_DIR, "package.json");
  const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));

  pkg.version = version;
  pkg.logionCliVersion = version;

  fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
  console.log("Pinned logion-cli version to " + version + " in package.json");
}

main();