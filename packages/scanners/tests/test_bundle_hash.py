"""Tests for bundle_hash order independence and edge cases."""

from __future__ import annotations

import tempfile
from pathlib import Path

from logion_scanners.runner import bundle_hash


class TestBundleHashOrderIndependence:
    """bundle_hash must be deterministic regardless of filesystem
    enumeration order."""

    def test_same_content_same_hash(self) -> None:
        """Two identical directory trees must produce the same hash."""
        with (
            tempfile.TemporaryDirectory() as tmp1,
            tempfile.TemporaryDirectory() as tmp2,
        ):
            d1 = Path(tmp1)
            d2 = Path(tmp2)
            # Write same files in different creation order
            (d1 / "aaa.txt").write_text("content-a")
            (d1 / "zzz.txt").write_text("content-z")

            (d2 / "zzz.txt").write_text("content-z")
            (d2 / "aaa.txt").write_text("content-a")

            assert bundle_hash(d1) == bundle_hash(d2)

    def test_different_content_different_hash(self) -> None:
        """Different content must produce different hashes."""
        with (
            tempfile.TemporaryDirectory() as tmp1,
            tempfile.TemporaryDirectory() as tmp2,
        ):
            d1 = Path(tmp1)
            d2 = Path(tmp2)
            (d1 / "file.txt").write_text("hello")
            (d2 / "file.txt").write_text("world")

            assert bundle_hash(d1) != bundle_hash(d2)

    def test_different_filename_different_hash(self) -> None:
        """Same content in differently-named files must differ."""
        with (
            tempfile.TemporaryDirectory() as tmp1,
            tempfile.TemporaryDirectory() as tmp2,
        ):
            d1 = Path(tmp1)
            d2 = Path(tmp2)
            (d1 / "alpha.txt").write_text("same")
            (d2 / "beta.txt").write_text("same")

            assert bundle_hash(d1) != bundle_hash(d2)

    def test_empty_directory(self) -> None:
        """Empty directory should still produce a stable hash."""
        with tempfile.TemporaryDirectory() as tmp:
            h1 = bundle_hash(Path(tmp))
            h2 = bundle_hash(Path(tmp))
            assert h1 == h2
            assert len(h1) == 64  # SHA-256 hex

    def test_nested_directories(self) -> None:
        """Nested subdirectories should be included in hash."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            sub = d / "sub" / "deep"
            sub.mkdir(parents=True)
            (sub / "file.txt").write_text("nested")
            h = bundle_hash(d)
            assert len(h) == 64

    def test_subdirs_order_independent(self) -> None:
        """Files in different subdirs must be order-independent."""
        with (
            tempfile.TemporaryDirectory() as tmp1,
            tempfile.TemporaryDirectory() as tmp2,
        ):
            d1 = Path(tmp1)
            d2 = Path(tmp2)

            (d1 / "a").mkdir()
            (d1 / "b").mkdir()
            (d1 / "a" / "x.txt").write_text("x")
            (d1 / "b" / "y.txt").write_text("y")

            (d2 / "b").mkdir()
            (d2 / "a").mkdir()
            (d2 / "b" / "y.txt").write_text("y")
            (d2 / "a" / "x.txt").write_text("x")

            assert bundle_hash(d1) == bundle_hash(d2)
