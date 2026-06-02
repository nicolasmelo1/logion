# SPDX-License-Identifier: MIT
"""Tests for verify_bundle.py — bundle layout verification.

Verifies that verify_bundle.py correctly rejects bundles with
extra files or missing references.
"""

from __future__ import annotations

import gzip
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

COMPANION_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = COMPANION_ROOT.parent.parent
PACKAGE_SCRIPT = COMPANION_ROOT / "scripts" / "package_skill.py"
VERIFY_SCRIPT = COMPANION_ROOT / "scripts" / "verify_bundle.py"

BUNDLE_KIND = "logion-marketplace-companion"
VERSION = "0.1.0"


def _run_build(out_dir: Path) -> Path:
    """Build a valid tarball and return its path."""
    result = subprocess.run(
        [
            sys.executable,
            str(PACKAGE_SCRIPT),
            "build",
            "--out",
            str(out_dir),
            "--version",
            VERSION,
            "--release",
        ],
        capture_output=True,
        text=True,
        cwd=str(COMPANION_ROOT),
    )
    assert result.returncode == 0, (
        f"Build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return out_dir / f"{BUNDLE_KIND}-{VERSION}.tar.gz"


def _read_tarball(tarball: Path) -> bytes:
    """Read tarball bytes."""
    return tarball.read_bytes()


def _write_tarball(path: Path, data: bytes) -> None:
    """Write tarball bytes to a file."""
    path.write_bytes(data)


def _add_file_to_tarball(
    tarball_bytes: bytes,
    new_path: str,
    new_data: bytes,
) -> bytes:
    """Add a file to an existing tarball, return new bytes."""
    buf = io.BytesIO()
    with (
        gzip.GzipFile(fileobj=io.BytesIO(tarball_bytes), mode="rb") as gz_in,
        tarfile.open(fileobj=gz_in, mode="r:") as tar_in,
        tarfile.open(fileobj=buf, mode="w:gz") as tar_out,
    ):
        # Copy all existing members
        for member in tar_in.getmembers():
            if member.isfile():
                f = tar_in.extractfile(member)
                assert f is not None
                data = f.read()
                # Preserve deterministic metadata
                member.mtime = 0
                member.uid = 0
                member.gid = 0
                member.uname = ""
                member.gname = ""
                tar_out.addfile(member, io.BytesIO(data))
            else:
                member.mtime = 0
                member.uid = 0
                member.gid = 0
                member.uname = ""
                member.gname = ""
                tar_out.addfile(member)

        # Add new file with deterministic metadata
        info = tarfile.TarInfo(name=new_path)
        info.size = len(new_data)
        info.mtime = 0
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mode = 0o644
        info.type = tarfile.REGTYPE
        tar_out.addfile(info, io.BytesIO(new_data))
    return buf.getvalue()


def _remove_file_from_tarball(
    tarball_bytes: bytes, remove_path_prefix: str
) -> bytes:
    """Remove a file from a tarball, return new bytes."""
    buf = io.BytesIO()
    with (
        gzip.GzipFile(fileobj=io.BytesIO(tarball_bytes), mode="rb") as gz_in,
        tarfile.open(fileobj=gz_in, mode="r:") as tar_in,
        tarfile.open(fileobj=buf, mode="w:gz") as tar_out,
    ):
        for member in tar_in.getmembers():
            if member.name == remove_path_prefix:
                continue
            if member.isfile():
                f = tar_in.extractfile(member)
                assert f is not None
                data = f.read()
                member.mtime = 0
                member.uid = 0
                member.gid = 0
                member.uname = ""
                member.gname = ""
                tar_out.addfile(member, io.BytesIO(data))
            else:
                member.mtime = 0
                member.uid = 0
                member.gid = 0
                member.uname = ""
                member.gname = ""
                tar_out.addfile(member)
    return buf.getvalue()


def _run_verify(tarball_path: Path) -> int:
    """Run verify_bundle.py on a tarball, return exit code."""
    result = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            str(tarball_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(COMPANION_ROOT),
    )
    return result.returncode


class TestVerifyBundleRejectsExtraFiles:
    """Adding an unexpected file fails verification."""

    def test_verify_bundle_rejects_extra_files(self, tmp_path: Path) -> None:
        # Build a valid tarball first
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        tarball = _run_build(build_dir)
        tarball_bytes = _read_tarball(tarball)

        # Add an unexpected file to the tarball
        prefix = f"{BUNDLE_KIND}-{VERSION}"
        extra_path = f"{prefix}/unexpected_file.txt"
        extra_data = b"This should not be here"
        mutated_bytes = _add_file_to_tarball(
            tarball_bytes, extra_path, extra_data
        )

        # Write mutated tarball
        mutated_path = tmp_path / "mutated.tar.gz"
        _write_tarball(mutated_path, mutated_bytes)

        # Verify should fail
        exit_code = _run_verify(mutated_path)
        assert exit_code != 0, (
            "verify_bundle should reject tarballs with unexpected extra files"
        )


class TestVerifyBundleRejectsMissingReference:
    """Removing a reference file fails verification."""

    def test_verify_bundle_rejects_missing_reference(
        self, tmp_path: Path
    ) -> None:
        # Build a valid tarball first
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        tarball = _run_build(build_dir)
        tarball_bytes = _read_tarball(tarball)

        # Remove references/troubleshooting.md from the tarball
        prefix = f"{BUNDLE_KIND}-{VERSION}"
        remove_path = f"{prefix}/references/troubleshooting.md"
        mutated_bytes = _remove_file_from_tarball(tarball_bytes, remove_path)

        # Also update manifest.json to remove the reference
        # entry so the manifest is still valid JSON.
        # We need to re-pack with the updated manifest.
        with (
            gzip.GzipFile(
                fileobj=io.BytesIO(mutated_bytes), mode="rb"
            ) as gz_in,
            tarfile.open(fileobj=gz_in, mode="r:") as tar_in,
        ):
            # Read current manifest
            manifest_f = tar_in.extractfile(f"{prefix}/manifest.json")
            assert manifest_f is not None
            manifest = json.loads(manifest_f.read())

            # Remove troubleshooting from references
            manifest["references"] = [
                r
                for r in manifest["references"]
                if r["path"] != "references/troubleshooting.md"
            ]

            manifest_bytes = (
                json.dumps(manifest, sort_keys=True, indent=2) + "\n"
            ).encode("utf-8")

            # Rebuild tarball without troubleshooting
            # and with updated manifest

            def _make_tar() -> bytes:
                gz_buf = io.BytesIO()
                with (
                    gzip.GzipFile(
                        fileobj=gz_buf, mode="wb", mtime=0
                    ) as gz_out,
                    tarfile.open(fileobj=gz_out, mode="w") as tar_out,
                ):
                    members = tar_in.getmembers()
                    for m in members:
                        if m.name in (
                            remove_path,
                            f"{prefix}/manifest.json",
                        ):
                            continue
                        if m.isfile():
                            f = tar_in.extractfile(m)
                            assert f is not None
                            data = f.read()
                            m.mtime = 0
                            m.uid = 0
                            m.gid = 0
                            m.uname = ""
                            m.gname = ""
                            tar_out.addfile(
                                m,
                                io.BytesIO(data),
                            )
                        else:
                            m.mtime = 0
                            m.uid = 0
                            m.gid = 0
                            m.uname = ""
                            m.gname = ""
                            tar_out.addfile(m)

                    # Add updated manifest
                    info = tarfile.TarInfo(name=(f"{prefix}/manifest.json"))
                    info.size = len(manifest_bytes)
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mode = 0o644
                    info.type = tarfile.REGTYPE
                    tar_out.addfile(
                        info,
                        io.BytesIO(manifest_bytes),
                    )
                return gz_buf.getvalue()

            final_bytes = _make_tar()

        mutated_path = tmp_path / "missing_reference.tar.gz"
        _write_tarball(mutated_path, final_bytes)

        # Verify should fail because required reference
        # file is missing
        exit_code = _run_verify(mutated_path)
        assert exit_code != 0, (
            "verify_bundle should reject tarballs with missing reference files"
        )
