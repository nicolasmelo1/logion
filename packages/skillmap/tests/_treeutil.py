"""Shared helpers for building synthetic trees in inference tests."""

from __future__ import annotations

from collections.abc import Callable

from logion_skillmap.models import TreeEntry


def make_tree(entries: list[tuple[str, str, int | None]]) -> list[TreeEntry]:
    """Build a list of TreeEntry from (path, type, size) tuples."""
    return [TreeEntry(path=p, type=t, size=s) for p, t, s in entries]


def blob_store(files: dict[str, bytes]) -> Callable[[str], bytes]:
    """Create a read_blob callback from a dict of path→bytes."""

    def read_blob(path: str) -> bytes:
        return files.get(path, b"")

    return read_blob


def codes(result) -> list[str]:
    """The needs_review codes on an InferenceResult."""
    return [f.code for f in result.needs_review]
