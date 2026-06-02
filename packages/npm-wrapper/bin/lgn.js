#!/usr/bin/env node
// SPDX-License-Identifier: MIT
//
// Short alias shim: prefer `lgn` on PATH, fall back to `logion`.
"use strict";

const { spawnSync } = require("node:child_process");
const which = require("./_which");

const target = which("lgn") || which("logion");
if (!target) {
  console.error(
    "lgn/logion binary not found.  Reinstall with `npm install -g @logion/cli` " +
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