#!/usr/bin/env node
// SPDX-License-Identifier: MIT
//
// Escape hatch for running Logion by hand from inside a dsh session. The
// plugin itself registers the `logion_*` tools; this only forwards argv.
import { spawn } from "node:child_process";

const command = process.argv.slice(2);
// `--json` is what the plugin's own tools request, but a human running
// this wrapper may want the human-readable output, so it is only added
// when it was not already asked for.
const argv = command.includes("--json") ? command : [...command, "--json"];

const child = spawn("logion", argv, {
  stdio: "inherit",
  shell: false,
});
child.on("error", (error) => {
  if (error.code === "ENOENT") {
    process.stderr.write(
      "Logion CLI is not installed; install logion-cli and retry.\n",
    );
    process.exitCode = 127;
    return;
  }
  process.stderr.write(`Unable to start Logion CLI: ${error.message}\n`);
  process.exitCode = 1;
});
child.on("exit", (code, signal) => {
  if (signal) process.exitCode = 1;
  else process.exitCode = code ?? 1;
});
