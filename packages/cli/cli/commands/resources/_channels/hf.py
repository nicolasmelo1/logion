# SPDX-License-Identifier: MIT
"""Hugging Face ``hf download`` acquisition adapter."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from cli._json import JsonObject, child, elements

from .base import AcquisitionOutcome, ChannelAdapter, run_argv


class HfAdapter(ChannelAdapter):
    channel = "hf"

    def acquire(
        self, *, plan: JsonObject, destination: Path, scope_root: Path
    ) -> AcquisitionOutcome:
        native = child(plan, "native")
        argv = list(elements(native, "argv"))
        if not argv or argv[:2] != ["hf", "download"]:
            raise RuntimeError(
                "native_tool_unsupported: expected hf download argv"
            )
        if shutil.which("hf") is None:
            raise RuntimeError("native_tool_unsupported: hf not found")
        destination.mkdir(parents=True, exist_ok=True)
        result = run_argv(
            [*argv, "--local-dir", str(destination)],
            cwd=scope_root,
            timeout_seconds=1800,
        )
        if result.returncode:
            raise RuntimeError(
                "hf download failed: "
                + (result.stderr or result.stdout)[:500].decode(
                    errors="replace"
                )
            )
        revision = str(native.get("revision") or "")
        components = []
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(chunk)
                components.append({
                    "path": str(path.relative_to(destination)),
                    "digest": digest.hexdigest(),
                })
        evidence = {
            "schema_version": 1,
            "manager_name": "hf",
            "manager_version": "unknown",
            "receipt_id": revision,
            "canonical_source": str(native.get("upstream_locator") or ""),
            "immutable_revision": revision,
            "content_digest": str(plan.get("content_digest") or ""),
            "files": components,
        }
        installed = [
            str(p.relative_to(scope_root))
            for p in sorted(destination.rglob("*"))
            if p.is_file()
        ]
        return AcquisitionOutcome(
            installed_paths=installed,
            native_evidence=evidence,
            verification="source_revision" if revision else "unverified",
        )
