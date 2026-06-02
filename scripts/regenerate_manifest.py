# SPDX-License-Identifier: MIT
"""Regenerate release manifests and open a PR if they changed.

Wrapper around ``release_manifest.py build`` that rebuilds both channels
(stable and latest), then uses ``git diff --quiet`` to decide whether
a pull request is needed.  Designed to be called from CI
(``regenerate-manifest.yml``) but also works locally.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCRIPT = REPO_ROOT / "scripts" / "release_manifest.py"
RELEASES_DIR = REPO_ROOT / "releases"

CHANNELS = ("stable", "latest")
MANIFEST_FILES = [RELEASES_DIR / f"manifest-{ch}.json" for ch in CHANNELS]


def _run(
    cmd: list[str],
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print(f"FAIL: manifest build failed (exit {result.returncode})")
        print(result.stderr)
        sys.exit(1)
    return result


def main() -> None:
    """Rebuild manifests and report if a PR is needed."""
    for channel in CHANNELS:
        out = RELEASES_DIR / f"manifest-{channel}.json"
        _run([
            "uv",
            "run",
            "python",
            str(MANIFEST_SCRIPT),
            "build",
            "--channel",
            channel,
            "--out",
            str(out),
        ])

    diff_result = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            "--",
            *[str(f) for f in MANIFEST_FILES],
        ],
        cwd=str(REPO_ROOT),
    )
    if diff_result.returncode != 0:
        # Files changed — CI will open a PR
        print("CHANGED: manifest files differ from HEAD.")
    else:
        print("NOCHANGE: manifests are up to date.")


if __name__ == "__main__":
    main()
