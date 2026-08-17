#!/usr/bin/env python3
"""Modify one installed file so the next reconcile must report drift.

Drives the negative path of the acquisition scenario: an artifact Logion
installed and vouched for is edited outside Logion. Reconcile has to stop
reporting it as matched and report it as drifted instead — silently
keeping the old verification level would mean the receipt attests to bytes
that are no longer on disk.

Usage: tamper_installed_artifact.py ACQUIRE_ARTIFACT SCOPE_ROOT
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from agent_proving_ground._json import elements


def _receipt(path: Path) -> dict:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if envelope.get("kind") != "logion.resources.acquire":
        raise SystemExit(f"not an acquire artifact: {path}")
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise SystemExit(f"acquire artifact has no receipt object: {path}")
    return data


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: tamper_installed_artifact.py ACQUIRE_ARTIFACT SCOPE_ROOT"
        )
    receipt = _receipt(Path(sys.argv[1]))
    scope_root = Path(sys.argv[2]).resolve()
    installed = [str(p) for p in elements(receipt, "installed_paths")]
    if not installed:
        raise SystemExit("receipt lists no installed paths to tamper with")

    target = scope_root / sorted(installed)[0]
    if not target.is_file():
        raise SystemExit(f"installed file is missing already: {target}")
    original = target.read_bytes()
    target.write_bytes(original + b"\n<!-- edited outside logion -->\n")

    print(  # noqa: T201
        json.dumps({
            "tampered_path": str(target.relative_to(scope_root)),
            "original_bytes": len(original),
        })
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
