#!/usr/bin/env python3
"""Run the reviewed software-factory revision, never an sf found on PATH."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

REVISION = "b06be44f6c982dac58b898778d7dba224d9ed7b1"
SOURCE = "https://github.com/nicolasmelo1/software-factory"
ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / ".local" / "software-factory" / REVISION


def digest(binary: Path) -> str:
    return hashlib.sha256(binary.read_bytes()).hexdigest()


def verify_source(install: Path) -> None:
    metadata = tomllib.loads((install / ".crates.toml").read_text())
    expected = f"(git+{SOURCE}?rev={REVISION}#{REVISION})"
    owners = [key for key, bins in metadata["v1"].items() if "sf" in bins]
    if len(owners) != 1 or not owners[0].endswith(expected):
        raise ValueError(
            "sf Cargo provenance does not match the reviewed revision"
        )


def verify(install: Path) -> Path:
    binary = install / "bin" / "sf"
    verify_source(install)
    receipt = json.loads((install / "verified.json").read_text())
    if receipt != {"revision": REVISION, "sha256": digest(binary)}:
        raise ValueError("sf binary differs from its verified installation")
    if binary.is_symlink() or not os.access(binary, os.X_OK):
        raise ValueError(
            "sf must be an executable regular installation, not a symlink"
        )
    return binary


def ensure_installed(install: Path) -> Path:
    if not install.exists():
        # Partial installations stay untrusted; never fall back to PATH.
        install.mkdir(parents=True)
        subprocess.run(
            [
                "cargo",
                "install",
                "--git",
                SOURCE,
                "--rev",
                REVISION,
                "--locked",
                "--root",
                str(install),
                "--bin",
                "sf",
            ],
            check=True,
        )
        verify_source(install)
        (install / "verified.json").write_text(
            json.dumps({
                "revision": REVISION,
                "sha256": digest(install / "bin" / "sf"),
            })
        )
    return verify(install)


def main() -> int:
    try:
        binary = ensure_installed(INSTALL)
        return subprocess.run(
            [str(binary), *sys.argv[1:]], cwd=ROOT
        ).returncode
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"Pinned sf unavailable: {exc}", file=sys.stderr)
        print(
            f"Remove {INSTALL} and retry to rebuild; PATH sf is never used.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
