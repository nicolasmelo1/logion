// SPDX-License-Identifier: MIT
//
// check_python.js — standalone Python detection module.
// Used by postinstall.js and testable via node --test.
"use strict";

const { execSync } = require("node:child_process");

const MIN_VERSION = [3, 12];

function detectPython() {
  if (process.env.LOGION_NPM_PYTHON) {
    return process.env.LOGION_NPM_PYTHON;
  }

  const candidates = process.platform === "win32"
    ? ["py", "py -3", "python", "python3"]
    : ["python3", "python"];

  for (const cmd of candidates) {
    try {
      const out = execSync(cmd + " --version", {
        encoding: "utf8",
        timeout: 10000,
        stdio: ["pipe", "pipe", "pipe"],
      }).trim();
      const match = out.match(/Python (\d+)\.(\d+)/);
      if (match) {
        const major = parseInt(match[1], 10);
        const minor = parseInt(match[2], 10);
        if (major > MIN_VERSION[0] || (major === MIN_VERSION[0] && minor >= MIN_VERSION[1])) {
          return { cmd, major, minor, raw: out };
        }
      }
    } catch {
      // not found or too old
    }
  }

  return null;
}

module.exports = { detectPython, MIN_VERSION };