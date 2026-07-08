"""Network-gated GitHub fetch helpers for real-repo fixture tests.

Tests shell out to the ``gh`` CLI so they reuse its auth + rate limits.
Each repo is pinned to an immutable commit SHA and fetched as a single
tarball (one network call), extracted in memory — so a fetched tree never
drifts as the upstream default branch moves, and we avoid hundreds of
per-blob requests. Tests skip when ``gh``/network is unavailable.
"""

from __future__ import annotations

import functools
import io
import json
import subprocess
import tarfile
from collections.abc import Callable

from logion_skillmap.models import TreeEntry


class GitHubUnavailable(RuntimeError):
    """Raised when the gh CLI / network is not usable for fixtures."""


def _gh_json(path: str) -> dict:
    proc = _run(["gh", "api", path], text=True)
    return json.loads(proc)


def _run(cmd: list[str], *, text: bool) -> str | bytes:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=text,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise GitHubUnavailable(str(exc)) from exc
    if proc.returncode != 0:
        err = proc.stderr if text else proc.stderr.decode("utf-8", "replace")
        raise GitHubUnavailable(err.strip() or "gh api failed")
    return proc.stdout


@functools.lru_cache(maxsize=1)
def gh_available() -> bool:
    """True if ``gh`` can reach the authenticated GitHub API."""
    try:
        _gh_json("rate_limit")
    except (GitHubUnavailable, json.JSONDecodeError):
        return False
    return True


def resolve_sha(repo: str, ref: str) -> str:
    """Resolve ``repo``'s ``ref`` (branch/tag) to an immutable commit SHA."""
    return _gh_json(f"repos/{repo}/commits/{ref}")["sha"]


def fetch_repo(
    repo: str, sha: str
) -> tuple[list[TreeEntry], Callable[[str], bytes]]:
    """Fetch ``repo`` at pinned ``sha`` as a tarball → ``(tree, read_blob)``.

    The whole tree is extracted in memory in one call; ``read_blob``
    serves file bytes from that map.
    """
    raw = _run(
        ["gh", "api", f"repos/{repo}/tarball/{sha}"],
        text=False,
    )
    assert isinstance(raw, bytes)
    blobs: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            # Strip the leading "<owner>-<repo>-<sha>/" component.
            rel = member.name.split("/", 1)[1] if "/" in member.name else ""
            if not rel:
                continue
            handle = tf.extractfile(member)
            if handle is None:
                continue
            blobs[rel] = handle.read()

    tree = [
        TreeEntry(path=path, type="blob", size=len(data))
        for path, data in sorted(blobs.items())
    ]

    def read_blob(path: str) -> bytes:
        return blobs.get(path, b"")

    return tree, read_blob
