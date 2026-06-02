// SPDX-License-Identifier: MIT
//
// Thin shim: forward all arguments to the user-installed `logion`
// binary (placed on PATH by postinstall -> pipx/uv/venv).
import { spawnSync } from "node:child_process";

import { which } from "../lib/which.js";

const target = which("logion");
if (!target) {
  process.stderr.write(
    "logion binary not found. Reinstall with " +
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
