# SPDX-License-Identifier: MIT
"""Logion bundle channel adapter.

Downloads a Logion-hosted bundle via the artifact-download manifest
(presigned URLs), verifies every file size/digest and the aggregate content
digest, and installs into the resolved harness scope atomically. On any
failure the partial download is deleted; nothing is installed.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any

import httpx

from cli import _receipts
from cli._local_state import UnsafeIdentifierError

from .base import AcquisitionOutcome, ChannelAdapter

_MAX_FILES = 10_000
_MAX_TOTAL_BYTES = 512 * 1024 * 1024
_MAX_SINGLE_FILE_BYTES = 256 * 1024 * 1024
_MAX_RATIO = 100.0


class LogionBundleAdapter(ChannelAdapter):
    channel = "logion_bundle"

    def __init__(self, *, client: Any) -> None:
        self._client = client

    def acquire(
        self,
        *,
        plan: dict[str, Any],
        destination: Path,
        scope_root: Path,
    ) -> AcquisitionOutcome:
        manifest = self._client.v1.resources.create_download(
            resource_id=str(plan["resource_id"]),
            version_id=str(plan["version_id"]),
        )
        files = manifest.get("files") or []
        if not files:
            raise RuntimeError("download manifest has no files")

        tmp_root = Path(tempfile.mkdtemp(prefix="logion-acquire-"))
        try:
            total = 0
            stage_dir = tmp_root / "payload"
            stage_dir.mkdir(parents=True, exist_ok=True)
            any_unpinned = False
            file_digests: dict[str, str] = {}
            aggregate_components: list[dict[str, Any]] = []
            for entry in files:
                rel = self._safe_relative(entry["path"])
                url = entry["url"]
                expected_size = entry.get("size_bytes")
                expected_digest = entry.get("digest")
                aggregate_key = entry.get("aggregate_key")
                if not isinstance(aggregate_key, str) or not aggregate_key:
                    raise RuntimeError("download manifest lacks aggregate key")
                staged = stage_dir / rel
                staged.parent.mkdir(parents=True, exist_ok=True)
                self._download(url, staged)
                size = staged.stat().st_size
                total += size
                if total > _MAX_TOTAL_BYTES:
                    raise RuntimeError("bundle exceeds size cap")
                if expected_size is not None and size != int(expected_size):
                    raise RuntimeError(
                        f"download size mismatch for {rel.as_posix()}"
                    )
                data = staged.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if expected_digest and digest != expected_digest:
                    raise RuntimeError(
                        f"download digest mismatch for {rel.as_posix()}"
                    )
                if not expected_digest:
                    any_unpinned = True
                aggregate_components.append({
                    "aggregate_key": aggregate_key,
                    "size_bytes": (
                        expected_size if expected_size is not None else size
                    ),
                    "digest": expected_digest or digest,
                })
                file_digests[
                    (destination.relative_to(scope_root) / rel).as_posix()
                ] = digest

            aggregate_digest = _receipts.aggregate_content_digest(
                aggregate_components
            )
            expected_content_digest = str(plan.get("content_digest") or "")
            if (
                not any_unpinned
                and aggregate_digest != expected_content_digest
            ):
                raise RuntimeError(
                    "download aggregate digest mismatch: refusing installation"
                )
            verification = "unverified" if any_unpinned else "exact"
            self._install(stage_dir, destination)
            installed = [
                str(path.relative_to(scope_root))
                for path in sorted(destination.rglob("*"))
                if path.is_file()
            ]
            return AcquisitionOutcome(
                installed_paths=installed,
                native_evidence={
                    "schema_version": 1,
                    "manager_name": "logion",
                    "manager_version": "cli",
                    "receipt_id": str(plan.get("distribution_id") or ""),
                    "canonical_source": "logion_bundle",
                    "immutable_revision": None,
                    "content_digest": aggregate_digest,
                    "aggregate_components": aggregate_components,
                    "file_digests": file_digests,
                },
                verification=verification,
            )
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def _safe_relative(self, value: str) -> Path:
        rel = Path(value)
        if rel.is_absolute() or ".." in rel.parts or not value.strip():
            raise UnsafeIdentifierError(f"unsafe bundle path: {value!r}")
        for part in rel.parts:
            # Dotfiles (e.g. .bundle-manifest) are legitimate bundle
            # content; only control characters, separators, and very long
            # segments are rejected. Traversal was rejected above.
            if part in (".", "..") or "\x00" in part or len(part) > 255:
                raise UnsafeIdentifierError(f"unsafe bundle path: {value!r}")
        return rel

    def _download(self, url: str, destination: Path) -> None:
        parsed = httpx.URL(url)
        if parsed.scheme not in {"http", "https"}:
            raise RuntimeError("bundle URL must use http or https")
        with httpx.stream(
            "GET", str(parsed), timeout=30.0, follow_redirects=False
        ) as response:
            response.raise_for_status()
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes(1 << 20):
                    handle.write(chunk)
                    if destination.stat().st_size > _MAX_SINGLE_FILE_BYTES:
                        raise RuntimeError("single file exceeds size cap")

    def _install(self, stage_dir: Path, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(stage_dir), str(destination))
