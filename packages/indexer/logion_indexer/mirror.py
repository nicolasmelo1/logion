"""Bundle mirroring: GitHub tarball -> component subtree -> deterministic tar.

For permissive-license repos we mirror the skill so the marketplace can
serve it even if the upstream repo disappears.  The mirrored subtree is
*exactly* the paths named by the inferred map's ``components.runtime.include``
globs — mirroring and mapping must never disagree.  The repack is
deterministic (sorted members, zeroed mtime/uid/gid) so the same commit
always yields the same sha256.
"""

from __future__ import annotations

import fnmatch
import gzip
import hashlib
import io
import tarfile
from dataclasses import dataclass

from .github_source import BUNDLE_SIZE_CAP_BYTES, is_permissive_license

# Reasons a bundle was not mirrored (display signals; item stays link-only).
BUNDLE_SKIP_RESTRICTED = "bundle_restricted_license"
BUNDLE_SKIP_TOO_LARGE = "bundle_too_large"
BUNDLE_SKIP_NO_TARBALL = "bundle_no_tarball"
BUNDLE_SKIP_EMPTY = "bundle_empty_subtree"


@dataclass
class BundleArtifact:
    """A mirrored bundle: metadata plus the repacked bytes."""

    canonical: str
    sha256: str
    size_bytes: int
    data: bytes

    def meta(self) -> dict:
        """The ``{sha256, size_bytes}`` metadata carried on the item."""
        return {"sha256": self.sha256, "size_bytes": self.size_bytes}


def _runtime_includes(inferred_map: dict | None) -> list[str]:
    """Extract ``components.runtime.include`` globs from a fragment."""
    if not isinstance(inferred_map, dict):
        return []
    components = inferred_map.get("components")
    if not isinstance(components, dict):
        return []
    runtime = components.get("runtime")
    if not isinstance(runtime, dict):
        return []
    include = runtime.get("include") or []
    if not isinstance(include, list):
        return []
    return [str(p) for p in include]


def _strip_top_prefix(name: str) -> str:
    """Drop the GitHub tarball's ``owner-repo-sha/`` top-level directory."""
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else ""


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def build_bundle(
    canonical: str,
    tarball_bytes: bytes,
    inferred_map: dict | None,
) -> tuple[BundleArtifact | None, str | None]:
    """Repack the component subtree from a GitHub tarball.

    Returns ``(artifact, None)`` on success or ``(None, reason)`` when no
    bundle is produced.  The subtree is the set of files matched by the
    map's ``components.runtime.include`` globs.
    """
    if len(tarball_bytes) > BUNDLE_SIZE_CAP_BYTES:
        return None, BUNDLE_SKIP_TOO_LARGE

    includes = _runtime_includes(inferred_map)
    if not includes:
        return None, BUNDLE_SKIP_EMPTY

    selected: list[tuple[str, bytes]] = []
    try:
        with tarfile.open(
            fileobj=io.BytesIO(tarball_bytes), mode="r:gz"
        ) as src:
            for member in src.getmembers():
                if not member.isfile():
                    continue
                rel = _strip_top_prefix(member.name)
                if not rel or not _matches_any(rel, includes):
                    continue
                fh = src.extractfile(member)
                if fh is None:
                    continue
                selected.append((rel, fh.read()))
    except (tarfile.TarError, OSError):
        return None, BUNDLE_SKIP_NO_TARBALL

    if not selected:
        return None, BUNDLE_SKIP_EMPTY

    data = _repack_deterministic(selected)
    if len(data) > BUNDLE_SIZE_CAP_BYTES:
        return None, BUNDLE_SKIP_TOO_LARGE

    sha256 = f"sha256:{hashlib.sha256(data).hexdigest()}"
    return (
        BundleArtifact(
            canonical=canonical,
            sha256=sha256,
            size_bytes=len(data),
            data=data,
        ),
        None,
    )


def _repack_deterministic(files: list[tuple[str, bytes]]) -> bytes:
    """Pack ``(path, bytes)`` pairs into a reproducible ``.tar.gz``."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for path, blob in sorted(files, key=lambda pair: pair[0]):
            info = tarfile.TarInfo(name=path)
            info.size = len(blob)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(blob))
    out = io.BytesIO()
    # mtime=0 keeps the gzip header byte-identical across runs.
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0) as gz:
        gz.write(raw.getvalue())
    return out.getvalue()


def mirror_bundle_for(
    canonical: str,
    license_spdx: str | None,
    inferred_map: dict | None,
    tarball_bytes: bytes | None,
) -> tuple[BundleArtifact | None, str | None]:
    """Decide-and-build a bundle for one component.

    Non-permissive / unknown licenses stay link-only.  A missing tarball
    or an empty/oversized subtree is reported as a skip reason.
    """
    if not is_permissive_license(license_spdx):
        return None, BUNDLE_SKIP_RESTRICTED
    if not tarball_bytes:
        return None, BUNDLE_SKIP_NO_TARBALL
    return build_bundle(canonical, tarball_bytes, inferred_map)
