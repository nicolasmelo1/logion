// SPDX-License-Identifier: MIT
//
// Cross-platform `which` — searches PATH for a binary, honouring
// PATHEXT on win32. Returns the absolute path or null.
import fs from "node:fs";
import path from "node:path";

function candidatesForName(name: string): string[] {
  if (process.platform !== "win32") {
    return [name];
  }
  const pathext = (process.env.PATHEXT ?? ".EXE;.CMD;.BAT;.COM")
    .split(";")
    .filter(Boolean);
  if (path.extname(name)) {
    return [name];
  }
  return [name, ...pathext.map((ext) => name + ext.toLowerCase())];
}

export function which(name: string): string | null {
  const rawPath = process.env.PATH ?? "";
  const dirs = rawPath.split(path.delimiter).filter(Boolean);
  for (const dir of dirs) {
    for (const candidate of candidatesForName(name)) {
      const full = path.join(dir, candidate);
      try {
        const stat = fs.statSync(full);
        if (stat.isFile()) {
          return full;
        }
      } catch {
        // not present in this dir
      }
    }
  }
  return null;
}
