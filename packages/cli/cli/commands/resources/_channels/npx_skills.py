# SPDX-License-Identifier: MIT
"""``npx skills`` channel adapter (delegation, argv-only, no shell).

Executes the server-provided argv after validation. Logion does not rewrite
``skills-lock.json``; reconciliation reads it. The adapter discovers the
installed skill directory from the lockfile after execution.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, ClassVar

from .base import AcquisitionOutcome, ChannelAdapter, run_argv


class NpxSkillsAdapter(ChannelAdapter):
    channel = "npx_skills"
    _PROGRAMS: ClassVar[set[str]] = {"npx"}
    _SKILLS_PREFIX: ClassVar[str] = "skills@"

    def acquire(
        self,
        *,
        plan: dict[str, Any],
        destination: Path,
        scope_root: Path,
    ) -> AcquisitionOutcome:
        native = plan.get("native") or {}
        argv = list(native.get("argv") or [])
        self._validate_argv(argv)
        self._require_program("node")
        self._require_program("npx")
        completed = run_argv(argv, cwd=scope_root, timeout_seconds=900)
        if completed.returncode != 0:
            raise RuntimeError(
                "npx skills failed: "
                + (completed.stderr or completed.stdout)[:500].decode(
                    errors="replace"
                )
            )
        evidence = self._read_lockfile_entry(scope_root)
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
            verification=(
                "source_revision"
                if evidence.get("immutable_revision")
                else "unverified"
            ),
        )

    def _validate_argv(self, argv: list[str]) -> None:
        if not argv or argv[0] not in self._PROGRAMS:
            raise RuntimeError("unexpected native argv program")
        if len(argv) < 3 or not argv[1].startswith(self._SKILLS_PREFIX):
            raise RuntimeError("expected `npx skills@x.y.z add ...` argv")

    def _require_program(self, name: str) -> None:
        if shutil.which(name) is None:
            raise RuntimeError(f"native tool unsupported: {name} not found")

    def _read_lockfile_entry(self, scope_root: Path) -> dict[str, Any]:
        lock = scope_root / "skills-lock.json"
        if not lock.is_file():
            return {
                "schema_version": 1,
                "manager_name": "skills",
                "manager_version": "unknown",
                "receipt_id": "",
                "canonical_source": "",
                "immutable_revision": "",
                "content_digest": "",
            }
        try:
            data = json.loads(lock.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        skills = data.get("skills")
        entry: dict[str, Any] = {}
        if isinstance(skills, dict) and skills:
            entry = next(iter(skills.values()))
        elif isinstance(skills, list) and skills:
            entry = skills[0]
        if not isinstance(entry, dict):
            entry = {}
        return {
            "schema_version": 1,
            "manager_name": "skills",
            "manager_version": str(data.get("managerVersion") or "unknown"),
            "receipt_id": str(entry.get("id") or ""),
            "canonical_source": str(entry.get("source") or ""),
            "immutable_revision": str(entry.get("revision") or ""),
            "content_digest": str(entry.get("contentDigest") or ""),
        }
