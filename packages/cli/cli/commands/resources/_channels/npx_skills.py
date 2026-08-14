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
        try:
            evidence, installed_paths = self._read_lockfile_entry(
                scope_root, plan
            )
        except TypeError as exc:
            raise RuntimeError("unsupported skills-lock.json schema") from exc
        installed = installed_paths or (
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

    def _read_lockfile_entry(  # noqa: C901 - lockfile schema validation
        self, scope_root: Path, plan: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        lock = scope_root / "skills-lock.json"
        if not lock.is_file():
            raise RuntimeError("skills-lock.json missing after npx skills")
        try:
            data = json.loads(lock.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("skills-lock.json is unreadable") from exc
        skills = data.get("skills")
        entries = list(skills.values()) if isinstance(skills, dict) else skills
        if not isinstance(entries, list):
            raise TypeError("unsupported skills-lock.json schema")
        native = plan.get("native") or {}
        expected_source = str(native.get("upstream_locator") or "")
        expected_revision = str(native.get("revision") or "")
        expected_name = str(native.get("skill_name") or "")
        matches = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            source = str(entry.get("source") or entry.get("locator") or "")
            revision = str(entry.get("revision") or entry.get("commit") or "")
            name = str(
                entry.get("name")
                or entry.get("skill")
                or (
                    Path(str(entry.get("skillPath"))).parent.name
                    if entry.get("skillPath")
                    else ""
                )
            )
            if (
                expected_source
                and source != expected_source
                and expected_source not in source
            ):
                continue
            if (
                expected_revision
                and revision
                and revision != expected_revision
            ):
                continue
            if expected_name and name != expected_name:
                continue
            matches.append(entry)
        if len(matches) != 1:
            raise RuntimeError("skills-lock.json has no unique matching skill")
        entry = matches[0]
        raw_paths = entry.get("paths") or entry.get("installedPaths") or []
        if not raw_paths and isinstance(entry.get("skillPath"), str):
            skill_path = Path(str(entry["skillPath"]))
            raw_paths = [str(Path(".agents/skills") / skill_path.parent.name)]
        if isinstance(raw_paths, str):
            raw_paths = [raw_paths]
        installed: list[str] = []
        for item in raw_paths:
            if not isinstance(item, str):
                continue
            candidate = (scope_root / item).resolve()
            try:
                relative = candidate.relative_to(scope_root.resolve())
            except ValueError as exc:
                raise RuntimeError(
                    "skills-lock.json contains an unsafe installed path"
                ) from exc
            installed.append(relative.as_posix())
        computed_hash = str(entry.get("computedHash") or "")
        content_digest = str(entry.get("contentDigest") or "")
        if not content_digest and computed_hash:
            content_digest = "sha256:" + computed_hash
        evidence = {
            "schema_version": 1,
            "manager_name": "skills",
            "manager_version": str(data.get("managerVersion") or "unknown"),
            "receipt_id": str(
                entry.get("id")
                or entry.get("name")
                or (
                    Path(str(entry.get("skillPath"))).parent.name
                    if entry.get("skillPath")
                    else ""
                )
            ),
            "canonical_source": str(
                entry.get("source") or entry.get("locator") or ""
            ),
            "immutable_revision": str(
                entry.get("revision") or entry.get("commit") or computed_hash
            ),
            "content_digest": content_digest,
        }
        return evidence, installed
