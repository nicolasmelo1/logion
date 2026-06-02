// SPDX-License-Identifier: MIT
//
// version-from-manifest.ts — reads releases/manifest-stable.json and
// writes the CLI version into package.json's "logionCliVersion" and
// "version" fields. Run as prepublishOnly.
import fs from "node:fs";
import path from "node:path";

// __dirname = dist/scripts → up 2 for package root, up 4 for repo root.
const PKG_DIR = path.join(__dirname, "..", "..");
const MANIFEST_PATH = path.join(
  PKG_DIR,
  "..",
  "..",
  "releases",
  "manifest-stable.json",
);

interface Manifest {
  packages: Record<string, { version: string }>;
}

function main(): void {
  let manifest: Manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, "utf8")) as Manifest;
  } catch {
    process.stderr.write(`Could not read manifest at ${MANIFEST_PATH}\n`);
    process.stderr.write("Run `make release-manifest` to generate it.\n");
    process.exit(1);
  }

  const cliPkg = manifest.packages["logion-cli"];
  if (!cliPkg?.version) {
    process.stderr.write("Manifest does not contain logion-cli version.\n");
    process.exit(1);
  }

  const version = cliPkg.version;
  const pkgPath = path.join(PKG_DIR, "package.json");
  const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8")) as {
    version?: string;
    logionCliVersion?: string;
  };

  pkg.version = version;
  pkg.logionCliVersion = version;

  fs.writeFileSync(pkgPath, `${JSON.stringify(pkg, null, 2)}\n`);
  process.stdout.write(
    `Pinned logion-cli version to ${version} in package.json\n`,
  );
}

main();
