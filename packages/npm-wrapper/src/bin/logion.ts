// SPDX-License-Identifier: MIT
//
// Thin shim: forward all arguments to the user-installed `logion`
// binary (placed on PATH by postinstall -> pipx/uv).  We do not
// re-implement the CLI in Node; we just exec it.
"use strict";

const { spawnSync } = require("node:child_process");
const { which } = require("../lib/which");

const target = which("logion");
if (!target) {
  console.error(
    "logion binary not found.  Reinstall with `npm install -g @logion/cli` " +
      "or install directly via `pipx install logion-cli`."
  );
  process.exit(127);
}

const r = spawnSync(target, process.argv.slice(2), { stdio: "inherit" });
if (r.error) {
  console.error(r.error.message);
  process.exit(1);
}
process.exit(r.status ?? 1);