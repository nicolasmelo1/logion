# SPDX-License-Identifier: MIT
"""Delegated ``npx plugins`` acquisition adapter."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from cli._json import JsonObject, child, require_str_array

from .._catalog_reconciliation import normalize_locator
from .base import AcquisitionOutcome, ChannelAdapter, run_argv


class NpxPluginsAdapter(ChannelAdapter):
    channel = "npx_plugins"

    def acquire(
        self, *, plan: JsonObject, destination: Path, scope_root: Path
    ) -> AcquisitionOutcome:
        # Executed argv: reject a wrong-typed entry rather than
        # coercing it into a command-line argument.
        argv = require_str_array(child(plan, "native"), "argv")
        if not argv or argv[:2] != ["npx", "plugins"]:
            raise RuntimeError(
                "native_tool_unsupported: expected npx plugins argv"
            )
        if shutil.which("node") is None or shutil.which("npx") is None:
            raise RuntimeError("native_tool_unsupported: node/npx not found")
        result = run_argv(argv, cwd=scope_root, timeout_seconds=900)
        if result.returncode:
            raise RuntimeError(
                "npx plugins failed: "
                + (result.stderr or result.stdout)[:500].decode(
                    errors="replace"
                )
            )
        evidence = self._read_state(scope_root, plan)
        installed = (
            [
                str(p.relative_to(scope_root))
                for p in sorted(destination.rglob("*"))
                if p.is_file()
            ]
            if destination.is_dir()
            else []
        )
        return AcquisitionOutcome(
            installed_paths=installed,
            native_evidence=evidence,
            verification="source_revision"
            if evidence.get("immutable_revision")
            else "unverified",
        )

    def _read_state(self, root: Path, plan: JsonObject) -> JsonObject:
        candidates = [
            root / ".agents/plugins/manifest.json",
            root / ".claude/plugins.json",
            root / "plugins.json",
        ]
        expected = str((child(plan, "native")).get("upstream_locator") or "")
        for path in candidates:
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            entries = (
                data.get("plugins", data) if isinstance(data, dict) else data
            )
            if isinstance(entries, dict):
                entries = list(entries.values())
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                source = str(
                    entry.get("source")
                    or entry.get("locator")
                    or entry.get("repository")
                    or ""
                )
                # Exact identity only; never infer a plugin from a
                # substring or from a directory basename.
                if expected and normalize_locator(source) != normalize_locator(
                    expected
                ):
                    continue
                return {
                    "schema_version": 1,
                    "manager_name": "plugins",
                    "manager_version": str(
                        data.get("version")
                        if isinstance(data, dict)
                        else "unknown"
                    ),
                    "receipt_id": str(
                        entry.get("id") or entry.get("name") or ""
                    ),
                    "canonical_source": source,
                    "immutable_revision": str(
                        entry.get("revision") or entry.get("commit") or ""
                    ),
                    "content_digest": str(entry.get("contentDigest") or ""),
                }
        raise RuntimeError("native manager state has no matching plugin entry")
