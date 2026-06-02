// SPDX-License-Identifier: MIT
//
// Tiny PATH-based `which` helper.  Finds an executable on PATH
// without pulling in the (stdlib-shadowing) `which` npm package.
"use strict";

const path = require("node:path");
const fs = require("node:fs");

module.exports = function which(cmd) {
  const pathDirs = (process.env.PATH || "").split(path.delimiter);
  const exts = process.platform === "win32" ? [".exe", ".cmd", ".bat", ""] : [""];
  for (const dir of pathDirs) {
    for (const ext of exts) {
      const candidate = path.join(dir, cmd + ext);
      try {
        if (fs.statSync(candidate).isFile() || fs.statSync(candidate).isSymbolicLink()) {
          return candidate;
        }
      } catch {
        // not found, continue
      }
    }
  }
  return null;
};