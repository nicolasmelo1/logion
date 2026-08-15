#!/usr/bin/env node
import { spawn } from "node:child_process";

const command = process.argv.slice(2);
const child = spawn("logion", [...command, "--json"], {
  stdio: "inherit",
  shell: false,
  env: process.env,
});
child.on("error", (error) => {
  if (error.code === "ENOENT") {
    process.stderr.write("Logion CLI is not installed; install logion-cli and retry.\n");
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
