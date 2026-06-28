// SPDX-License-Identifier: MIT
//
// Thin shim: forward all arguments to the Python CLI installed by
// postinstall into the npm-managed venv.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const managedVenvDir = path.join(os.homedir(), ".logion", "npm-managed-venv");
const target =
  process.platform === "win32"
    ? path.join(managedVenvDir, "Scripts", "logion.exe")
    : path.join(managedVenvDir, "bin", "logion");

if (!fs.existsSync(target)) {
  process.stderr.write(
    "logion binary not found in the npm-managed environment. " +
      "Reinstall with `npm install -g @logionsh/cli` or rerun " +
      "`npx @logionsh/cli`.\n",
  );
  process.exit(127);
}

const r = spawnSync(target, process.argv.slice(2), { stdio: "inherit" });
if (r.error) {
  process.stderr.write(`${r.error.message}\n`);
  process.exit(1);
}
process.exit(r.status ?? 1);
