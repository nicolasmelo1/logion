// SPDX-License-Identifier: MIT
//
// detectPython — locate a Python 3.12+ interpreter, honouring the
// LOGION_NPM_PYTHON override. Always returns the same shape so
// callers can rely on `.cmd` / `.args`.
import { spawnSync } from "node:child_process";

import { which } from "./which";

export interface PythonInfo {
  /** Executable path (or short name resolvable via PATH). */
  cmd: string;
  /** Extra args to prepend (e.g. `["-3"]` for the Windows `py` launcher). */
  args: string[];
}

const MIN_MAJOR = 3;
const MIN_MINOR = 12;

interface Candidate {
  cmd: string;
  args: string[];
}

function candidates(): Candidate[] {
  if (process.platform === "win32") {
    return [
      { cmd: "py", args: ["-3"] },
      { cmd: "python3", args: [] },
      { cmd: "python", args: [] },
    ];
  }
  return [
    { cmd: "python3", args: [] },
    { cmd: "python", args: [] },
  ];
}

function probeVersion(cmd: string, args: string[]): boolean {
  const r = spawnSync(
    cmd,
    [...args, "-c", "import sys;print(sys.version_info[:2])"],
    { encoding: "utf8", timeout: 5000 },
  );
  if (r.status !== 0 || !r.stdout) {
    return false;
  }
  const m = /\((\d+),\s*(\d+)\)/.exec(r.stdout);
  if (!m) {
    return false;
  }
  const major = Number(m[1]);
  const minor = Number(m[2]);
  if (major > MIN_MAJOR) {
    return true;
  }
  return major === MIN_MAJOR && minor >= MIN_MINOR;
}

export function detectPython(): PythonInfo | null {
  const override = process.env.LOGION_NPM_PYTHON;
  if (override && override.trim().length > 0) {
    return { cmd: override, args: [] };
  }
  for (const c of candidates()) {
    const resolved = which(c.cmd);
    if (!resolved) {
      continue;
    }
    if (probeVersion(resolved, c.args)) {
      return { cmd: resolved, args: c.args };
    }
  }
  return null;
}
