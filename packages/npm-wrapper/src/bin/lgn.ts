// SPDX-License-Identifier: MIT
//
// Short alias shim: prefer `lgn` on PATH, fall back to `logion`.
import { spawnSync } from "node:child_process";

import { which } from "../lib/which.js";

const target = which("lgn") ?? which("logion");
if (!target) {
  process.stderr.write(
    "lgn/logion binary not found. Reinstall with " +
      "`npm install -g @logion/cli` or install directly via " +
      "`pipx install logion-cli`.\n",
  );
  process.exit(127);
}

const r = spawnSync(target, process.argv.slice(2), { stdio: "inherit" });
if (r.error) {
  process.stderr.write(`${r.error.message}\n`);
  process.exit(1);
}
process.exit(r.status ?? 1);
