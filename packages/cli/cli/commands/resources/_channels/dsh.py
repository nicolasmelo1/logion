# SPDX-License-Identifier: MIT
"""Delegated DeepSeek Harness plugin acquisition channel."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .base import AcquisitionOutcome, ChannelAdapter, run_argv

_DSH_REVISION = re.compile(r"^[0-9a-f]{40}$")


def _profile_dir(root: Path, profile: str) -> Path:
    return root / ".dsh" / "profiles" / profile


class DshChannelAdapter(ChannelAdapter):
    """Use dsh's profile plugin manager and read its native state."""

    channel = "dsh"

    def acquire(
        self, *, plan: dict[str, Any], destination: Path, scope_root: Path
    ) -> AcquisitionOutcome:
        del destination
        native = plan.get("native") or {}
        argv = [str(value) for value in native.get("argv") or []]
        self._validate_argv(argv, native)
        if shutil.which("dsh") is None:
            raise RuntimeError(
                "resource_native_tool_unsupported: dsh not found"
            )
        result = run_argv(argv, cwd=scope_root, timeout_seconds=900)
        if result.returncode:
            detail = (result.stderr or result.stdout)[:500].decode(
                errors="replace"
            )
            raise RuntimeError(f"dsh plugin acquisition failed: {detail}")
        profile = self._profile(argv)
        evidence, installed = self._read_state(scope_root, profile, native)
        return AcquisitionOutcome(
            installed_paths=installed,
            native_evidence=evidence,
            verification="source_revision",
        )

    @staticmethod
    def _validate_argv(argv: list[str], native: dict[str, Any]) -> None:
        if len(argv) < 5 or argv[:3] != ["dsh", "plugin", "--profile"]:
            raise RuntimeError(
                "resource_native_tool_unsupported: invalid dsh argv"
            )
        if any(
            not token
            or (token.startswith("--") and token not in {"--profile"})
            for token in argv[3:]
        ):
            raise RuntimeError("invalid dsh plugin argv")
        if argv[4] != "add" or len(argv) != 6:
            raise RuntimeError(
                "dsh acquisition requires `plugin --profile NAME add PACKAGE`"
            )
        revision = str(native.get("revision") or "")
        if not _DSH_REVISION.fullmatch(revision):
            raise RuntimeError(
                "dsh distribution requires an immutable 40-character revision"
            )

    @staticmethod
    def _profile(argv: list[str]) -> str:
        return argv[3]

    def _read_state(
        self, root: Path, profile: str, native: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        directory = _profile_dir(root, profile)
        manifest_path = directory / "package.json"
        profile_path = directory / "dsh.profile"
        try:
            package = json.loads(manifest_path.read_text(encoding="utf-8"))
            profile_manifest = json.loads(
                profile_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("unsupported dsh profile state") from exc
        if not isinstance(package, dict) or not isinstance(
            profile_manifest, dict
        ):
            raise TypeError("unsupported dsh profile state")
        bundles = (
            (profile_manifest.get("dsh") or {})
            .get("profile", {})
            .get("bundles")
        )
        deps = package.get("dependencies")
        if not isinstance(bundles, list) or not isinstance(deps, dict):
            raise TypeError("unsupported dsh profile state")
        locator = str(native.get("upstream_locator") or "")
        matches = [
            str(item)
            for item in bundles
            if isinstance(item, str)
            and (item == locator or item.rsplit("/", 1)[-1] == locator)
        ]
        if len(matches) != 1:
            raise RuntimeError(
                "dsh profile state has no unique matching bundle"
            )
        name = matches[0]
        installed_manifest = directory / "node_modules" / name / "package.json"
        try:
            installed = json.loads(
                installed_manifest.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "dsh plugin package manifest missing or invalid"
            ) from exc
        revision = str(
            installed.get("gitHead") or native.get("revision") or ""
        )
        if not _DSH_REVISION.fullmatch(revision):
            raise RuntimeError("dsh plugin has no immutable revision")
        expected = str(native.get("revision") or "")
        if revision != expected:
            raise RuntimeError("dsh plugin revision does not match the plan")
        return (
            {
                "schema_version": 1,
                "manager_name": "dsh",
                "manager_version": str(native.get("tested_version") or ""),
                "receipt_id": name,
                "canonical_source": str(
                    installed.get("repository") or locator
                ),
                "immutable_revision": revision,
                "content_digest": str(native.get("content_digest") or ""),
            },
            [str(installed_manifest.parent.relative_to(root))],
        )
