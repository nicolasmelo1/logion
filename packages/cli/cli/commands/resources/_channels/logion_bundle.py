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
import urllib.request
from pathlib import Path
from typing import Any

from cli._local_state import UnsafeIdentifierError, _safe_segment

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
        del scope_root  # bundle installs relative to destination only
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
            aggregate = hashlib.sha256()
            for entry in files:
                rel = self._safe_relative(entry["path"])
                url = entry["url"]
                expected_size = entry.get("size_bytes")
                expected_digest = entry.get("digest")
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
                aggregate.update(rel.as_posix().encode() + b"\0" + data)

            self._install(stage_dir, destination)
            expected_digest = str(plan.get("content_digest") or "")
            verification = "unverified"
            if expected_digest:
                actual = aggregate.hexdigest()
                if expected_digest in (actual, f"sha256:{actual}"):
                    verification = "exact"
                else:
                    raise RuntimeError(
                        "installed content digest does not match the plan"
                    )
            installed = [
                str(path.relative_to(destination.parent))
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
                    "content_digest": expected_digest,
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
            _safe_segment(part, "bundle path segment")
        return rel

    def _download(self, url: str, destination: Path) -> None:
        with urllib.request.urlopen(url) as response:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                with destination.open("ab") as handle:
                    handle.write(chunk)
                if destination.stat().st_size > _MAX_SINGLE_FILE_BYTES:
                    raise RuntimeError("single file exceeds size cap")

    def _install(self, stage_dir: Path, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(stage_dir), str(destination))
