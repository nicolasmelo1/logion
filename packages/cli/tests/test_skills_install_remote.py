# SPDX-License-Identifier: MIT
"""Tests for ``logion skills install`` when --source points to a
tarball, URL, or release-manifest reference.

The CLI handler changes for remote install support (phase 7.6)
are not yet in place.  Tests that exercise future handler paths
are marked ``@pytest.mark.skip`` with a reason.  The
local-tarball test exercises the CURRENT code by expanding a
fixture tarball into a temp directory and delegating to the
existing directory-based install.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from cli._local_state import ensure_layout, installed_dir, read_manifest
from cli.commands.skills.handlers import handle_skills_install

# ── Fixtures ──────────────────────────────────────────────────


def _write_skill_md(
    directory: Path,
    name: str = "test-course",
) -> None:
    """Write a minimal SKILL.md with frontmatter."""
    (directory / "SKILL.md").write_text(
        "---\nname: " + name + "\nsafety:\n"
        "  requires_confirmation:\n"
        "    - spend_credits\n---\n\n"
        "# Test Skill\n\nHello.\n",
        encoding="utf-8",
    )


def _write_capabilities(directory: Path) -> None:
    """Write a minimal capabilities.yaml."""
    cap_dir = directory / "course"
    cap_dir.mkdir(exist_ok=True)
    (cap_dir / "capabilities.yaml").write_text(
        "version: 1\nsummary: test\ncapabilities:\n  - id: test-cap\n",
        encoding="utf-8",
    )


def _write_references(directory: Path) -> None:
    """Write a minimal references/ directory."""
    ref_dir = directory / "references"
    ref_dir.mkdir(exist_ok=True)
    (ref_dir / "account-and-identity.md").write_text(
        "# Account\n\nTest reference.\n",
        encoding="utf-8",
    )


def _build_bundle_directory(
    tmp_path: Path,
    name: str = "test-course",
) -> Path:
    """Create a minimal skill bundle directory on disk."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _write_skill_md(bundle, name)
    _write_capabilities(bundle)
    _write_references(bundle)
    return bundle


def _build_tarball(
    bundle_dir: Path,
    dest_dir: Path,
    version: str = "0.1.0",
    manifest_overrides: dict[str, Any] | None = None,
) -> Path:
    """Build a .tar.gz from *bundle_dir* into *dest_dir*.

    Returns the path to the tarball.  The tarball top-level
    directory is
    ``logion-marketplace-companion-<version>/``.
    """
    arc_prefix = f"logion-marketplace-companion-{version}"
    tar_path = dest_dir / f"{arc_prefix}.tar.gz"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "bundle_kind": "logion-marketplace-companion",
        "version": version,
        "generated_at": "2026-06-01T12:34:56Z",
        "git_commit": "abc1234",
        "minimum_cli_version": "0.1.0",
        "skill_name": "logion-marketplace-companion",
        "skill_md_sha256": hashlib.sha256(
            (bundle_dir / "SKILL.md").read_bytes()
        ).hexdigest(),
        "references": [],
        "capability_manifest": {
            "path": "course/capabilities.yaml",
        },
        "safety": {
            "requires_confirmation": ["spend_credits"],
        },
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)

    manifest_bytes = (
        json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    )

    files_to_add: list[tuple[str, Path | None]] = []
    for child in sorted(bundle_dir.rglob("*")):
        if child.is_file():
            rel = child.relative_to(bundle_dir)
            files_to_add.append((f"{arc_prefix}/{rel}", child))
    files_to_add.append((f"{arc_prefix}/manifest.json", None))

    buf = io.BytesIO()
    with (
        gzip.GzipFile(
            fileobj=buf,
            mode="wb",
            mtime=0,
        ) as gz,
        tarfile.open(fileobj=gz, mode="w") as tf,
    ):
        ti = tarfile.TarInfo(name=arc_prefix + "/")
        ti.mtime = 0
        ti.uid = 0
        ti.gid = 0
        ti.uname = ""
        ti.gname = ""
        ti.mode = 0o755
        ti.type = tarfile.DIRTYPE
        tf.addfile(ti)

        for arc_name, src_path in files_to_add:
            if src_path is None:
                data = manifest_bytes
            else:
                data = src_path.read_bytes()

            ti = tarfile.TarInfo(name=arc_name)
            ti.size = len(data)
            ti.mtime = 0
            ti.uid = 0
            ti.gid = 0
            ti.uname = ""
            ti.gname = ""
            ti.mode = 0o644
            ti.type = tarfile.REGTYPE
            tf.addfile(ti, io.BytesIO(data))

    tar_path.write_bytes(buf.getvalue())
    return tar_path


def _args(
    source: Path,
    course_id: str = "remote-test",
    version_id: str = "0.1.0",
    target: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        source=source,
        course_id=course_id,
        version_id=version_id,
        title=None,
        target=target,
        dry_run=dry_run,
        force=force,
        install_source="manual",
    )


def _expand_tarball(
    tar_path: Path,
    expand_dir: Path,
) -> Path:
    """Expand tarball and return the source directory."""
    expand_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(expand_dir, filter="data")
    top_dirs = [
        p
        for p in expand_dir.iterdir()
        if p.is_dir() and p.name.startswith("logion-marketplace-companion-")
    ]
    assert len(top_dirs) == 1, (
        f"Expected exactly 1 top-level dir, got: {top_dirs}"
    )
    return top_dirs[0]


# ── Tests ─────────────────────────────────────────────────────


class TestSkillsInstallFromLocalTarball:
    """Install from a local .tar.gz by expanding then
    delegating."""

    def test_installs_from_expanded_tarball(
        self,
        tmp_path: Path,
    ) -> None:
        """Expanding a tarball and installing its contents
        succeeds end-to-end."""
        bundle_dir = _build_bundle_directory(tmp_path)
        tar_path = _build_tarball(bundle_dir, tmp_path)
        home = ensure_layout(tmp_path / "home")

        source_dir = _expand_tarball(tar_path, tmp_path / "exp")
        args = _args(
            source=source_dir,
            course_id="tarball-course",
            version_id="0.1.0",
            target=home,
        )
        rc = handle_skills_install(args)
        assert rc == 0

        dest = installed_dir("tarball-course", "0.1.0", home)
        assert (dest / "SKILL.md").is_file()
        assert (dest / "course" / "capabilities.yaml").is_file()
        assert (dest / "references" / "account-and-identity.md").is_file()

    def test_manifest_json_is_local_state_not_bundle(
        self,
        tmp_path: Path,
    ) -> None:
        """The manifest.json in the installed dir is local
        state written by the install handler, not the bundle's
        metadata manifest."""
        bundle_dir = _build_bundle_directory(tmp_path)
        tar_path = _build_tarball(bundle_dir, tmp_path)
        home = ensure_layout(tmp_path / "home")

        source_dir = _expand_tarball(tar_path, tmp_path / "exp")
        args = _args(
            source=source_dir,
            course_id="manifest-test",
            version_id="0.1.0",
            target=home,
        )
        rc = handle_skills_install(args)
        assert rc == 0

        local = read_manifest("manifest-test", "0.1.0", home)
        assert local is not None
        assert local["course_id"] == "manifest-test"


@pytest.mark.skip(
    reason="pending phase-7.6 CLI handler extension for URL source support"
)
class TestSkillsInstallFromUrl:
    """Install from a remote tarball URL with sha256
    verification."""

    def test_skills_install_from_url_downloads_and_installs(
        self,
        tmp_path: Path,
    ) -> None:
        """Simulated download + install from a URL succeeds."""
        bundle_dir = _build_bundle_directory(tmp_path)
        _build_tarball(bundle_dir, tmp_path)

        class _FakeResponse:
            def read(self) -> bytes:
                return b""

            def __enter__(self) -> _FakeResponse:
                return self

            def __exit__(
                self,
                *args: object,
            ) -> None:
                pass

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeResponse(),
        ):
            pass

    def test_skills_install_from_url_verifies_sha256(
        self,
        tmp_path: Path,
    ) -> None:
        """sha256 mismatch between expected and actual tarball
        aborts the install before extraction."""
        bundle_dir = _build_bundle_directory(tmp_path)
        _build_tarball(bundle_dir, tmp_path)

        class _FakeResponse:
            def read(self) -> bytes:
                return b"\x00"

            def __enter__(self) -> _FakeResponse:
                return self

            def __exit__(
                self,
                *args: object,
            ) -> None:
                pass

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeResponse(),
        ):
            pass


@pytest.mark.skip(
    reason="pending phase-7.6 CLI handler extension for "
    "minimum_cli_version check"
)
class TestSkillsInstallRefusesOldCliVersion:
    """A bundle whose minimum_cli_version exceeds the running
    CLI version must be rejected."""

    def test_refuses_bundle_with_high_minimum_cli_version(
        self,
        tmp_path: Path,
    ) -> None:
        """Bundle with minimum_cli_version: 99.0 is refused."""
        bundle_dir = _build_bundle_directory(tmp_path)
        tar_path = _build_tarball(
            bundle_dir,
            tmp_path,
            manifest_overrides={
                "minimum_cli_version": "99.0.0",
            },
        )
        home = ensure_layout(tmp_path / "home")
        source_dir = _expand_tarball(tar_path, tmp_path / "exp")
        args = _args(
            source=source_dir,
            course_id="old-cli-course",
            version_id="0.1.0",
            target=home,
        )
        # Handler should read manifest.json from the bundle,
        # compare minimum_cli_version against the running CLI
        # version, and refuse install with a clear error.
        # Exercise deferred to handler extension.
        assert args is not None


@pytest.mark.skip(
    reason="pending phase-7.6 CLI handler extension for "
    "manifest reference resolution"
)
class TestSkillsInstallManifestReference:
    """Resolve --source
    logion-marketplace-companion@0.1.2 via the release
    manifest."""

    def test_manifest_reference_resolves_to_url(
        self,
        tmp_path: Path,
    ) -> None:
        """--source logion-marketplace-companion@0.1.2 resolves
        via releases/manifest-stable.json to a download URL."""
        bundle_dir = _build_bundle_directory(tmp_path)
        tar_path = _build_tarball(bundle_dir, tmp_path)
        tar_bytes = tar_path.read_bytes()
        tar_sha = hashlib.sha256(tar_bytes).hexdigest()

        fake_manifest: dict[str, Any] = {
            "schema_version": 1,
            "channel": "stable",
            "packages": {
                "logion-companion": {
                    "version": "0.1.0",
                    "bundle": {
                        "url": (
                            "https://github.com/example/"
                            "releases/download/"
                            "logion-companion-v0.1.0/"
                            "logion-marketplace-companion"
                            "-0.1.0.tar.gz"
                        ),
                        "sha256": tar_sha,
                    },
                },
            },
        }

        class _FakeResponse:
            def __init__(self, data: bytes) -> None:
                self._data = data

            def read(self) -> bytes:
                return self._data

            def __enter__(self) -> _FakeResponse:
                return self

            def __exit__(
                self,
                *args: object,
            ) -> None:
                pass

        with (
            patch(
                "cli.commands.skills."
                "_install_helpers"
                ".resolve_release_manifest",
                return_value=fake_manifest,
            ),
            patch(
                "urllib.request.urlopen",
                return_value=_FakeResponse(tar_bytes),
            ),
        ):
            pass
