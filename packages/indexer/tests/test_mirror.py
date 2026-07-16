"""Tests for bundle mirroring: subtree == runtime.include, caps, licenses."""

from __future__ import annotations

import gzip
import hashlib
import io
import tarfile

from logion_indexer.github_source import BUNDLE_SIZE_CAP_BYTES
from logion_indexer.mirror import (
    BUNDLE_SKIP_RESTRICTED,
    BUNDLE_SKIP_TOO_LARGE,
    build_bundle,
    mirror_bundle_for,
)

FRAGMENT = {
    "version": 1,
    "package": {"slug": "foo"},
    "components": {
        "capabilities": {"foo": {"entrypoint": "skills/foo/SKILL.md"}},
        "runtime": {
            "include": ["skills/foo/**"],
            "entrypoint": "skills/foo/SKILL.md",
        },
    },
}


def _make_tarball(
    files: dict[str, bytes], prefix: str = "octocat-hello-abc"
) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as tar:
        for path, blob in files.items():
            info = tarfile.TarInfo(name=f"{prefix}/{path}")
            info.size = len(blob)
            tar.addfile(info, io.BytesIO(blob))
    return raw.getvalue()


class TestBuildBundle:
    def test_subtree_matches_runtime_include(self) -> None:
        tarball = _make_tarball({
            "README.md": b"top-level readme",
            "skills/foo/SKILL.md": b"foo skill",
            "skills/foo/helper.py": b"print('hi')",
            "skills/bar/SKILL.md": b"bar skill",
        })
        artifact, reason = build_bundle(
            "gh:octocat/hello#skills/foo", tarball, FRAGMENT
        )
        assert reason is None
        assert artifact is not None
        # Only the skills/foo subtree is present in the repack.
        with tarfile.open(
            fileobj=io.BytesIO(gzip.decompress(artifact.data)), mode="r"
        ) as tar:
            names = sorted(m.name for m in tar.getmembers())
        assert names == ["skills/foo/SKILL.md", "skills/foo/helper.py"]

    def test_sha256_and_size(self) -> None:
        tarball = _make_tarball({"skills/foo/SKILL.md": b"foo"})
        artifact, _ = build_bundle("c", tarball, FRAGMENT)
        assert artifact is not None
        expected = f"sha256:{hashlib.sha256(artifact.data).hexdigest()}"
        assert artifact.sha256 == expected
        assert artifact.size_bytes == len(artifact.data)
        assert artifact.meta() == {
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
        }

    def test_deterministic_repack(self) -> None:
        files = {"skills/foo/SKILL.md": b"foo", "skills/foo/x.py": b"y"}
        a1, _ = build_bundle("c", _make_tarball(files), FRAGMENT)
        a2, _ = build_bundle(
            "c", _make_tarball(files, prefix="different-prefix"), FRAGMENT
        )
        assert a1 is not None
        assert a2 is not None
        assert a1.sha256 == a2.sha256

    def test_empty_subtree_skipped(self) -> None:
        tarball = _make_tarball({"other/thing.txt": b"x"})
        artifact, reason = build_bundle("c", tarball, FRAGMENT)
        assert artifact is None
        assert reason is not None


class TestMirrorDecision:
    def test_permissive_license_mirrors(self) -> None:
        tarball = _make_tarball({"skills/foo/SKILL.md": b"foo"})
        artifact, reason = mirror_bundle_for("c", "MIT", FRAGMENT, tarball)
        assert reason is None
        assert artifact is not None

    def test_restricted_license_null(self) -> None:
        tarball = _make_tarball({"skills/foo/SKILL.md": b"foo"})
        artifact, reason = mirror_bundle_for("c", "GPL-3.0", FRAGMENT, tarball)
        assert artifact is None
        assert reason == BUNDLE_SKIP_RESTRICTED

    def test_unknown_license_null(self) -> None:
        tarball = _make_tarball({"skills/foo/SKILL.md": b"foo"})
        artifact, reason = mirror_bundle_for("c", None, FRAGMENT, tarball)
        assert artifact is None
        assert reason == BUNDLE_SKIP_RESTRICTED

    def test_oversize_tarball_skipped(self) -> None:
        big = b"x" * (BUNDLE_SIZE_CAP_BYTES + 1)
        artifact, reason = mirror_bundle_for("c", "MIT", FRAGMENT, big)
        assert artifact is None
        assert reason == BUNDLE_SKIP_TOO_LARGE
