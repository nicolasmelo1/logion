# SPDX-License-Identifier: MIT
"""``npx skills`` channel adapter (delegation, argv-only, no shell).

Executes the server-provided argv after validation. Logion does not
rewrite ``skills-lock.json``; it reads it to discover what the manager
installed and to attribute the result. Attribution is exact on source and
skill name, and the manager's ``computedHash`` is treated as a content
digest — never as an immutable revision.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, ClassVar

from ._skills_lock import (
    UnsupportedLockfileError,
    manager_version_from_argv,
    parse_skills_lock,
    select_entry,
)
from .base import AcquisitionOutcome, ChannelAdapter, run_argv


def _skill_from_locator(locator: str) -> str:
    """The `#skill` fragment a catalog locator may carry."""
    return locator.partition("#")[2]


class NpxSkillsAdapter(ChannelAdapter):
    channel = "npx_skills"
    _PROGRAMS: ClassVar[set[str]] = {"npx"}
    _ALLOWED_FLAGS: ClassVar[set[str]] = {"-y", "--yes"}

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
        # The lockfile records no manager version, so the identity comes
        # from the immutable spec we are about to execute.
        manager_version = manager_version_from_argv(argv)
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
        evidence, installed_paths = self._read_lockfile_entry(
            scope_root, plan, manager_version
        )
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
            # A content hash is not a revision. Only an immutable VCS
            # revision recorded by the manager earns source_revision.
            verification=(
                "source_revision"
                if evidence.get("immutable_revision")
                else "unverified"
            ),
        )

    def _validate_argv(self, argv: list[str]) -> None:
        if not argv or argv[0] not in self._PROGRAMS:
            raise RuntimeError("unexpected native argv program")
        rest = [
            token for token in argv[1:] if token not in self._ALLOWED_FLAGS
        ]
        if len(rest) < 2 or not rest[0].startswith("skills@"):
            raise RuntimeError("expected `npx skills@x.y.z add ...` argv")

    def _require_program(self, name: str) -> None:
        if shutil.which(name) is None:
            raise RuntimeError(f"native tool unsupported: {name} not found")

    def _read_lockfile_entry(
        self, scope_root: Path, plan: dict[str, Any], manager_version: str
    ) -> tuple[dict[str, Any], list[str]]:
        lock = scope_root / "skills-lock.json"
        if not lock.is_file():
            raise RuntimeError("skills-lock.json missing after npx skills")
        native = plan.get("native") or {}
        locator = str(native.get("upstream_locator") or "")
        try:
            entry = select_entry(
                parse_skills_lock(lock),
                expected_source=locator,
                expected_name=str(
                    native.get("skill_name") or _skill_from_locator(locator)
                ),
            )
        except UnsupportedLockfileError as exc:
            raise RuntimeError(str(exc)) from exc

        # The manager records no commit, so a plan revision can only be
        # contradicted, never confirmed, by the lockfile.
        expected_revision = str(native.get("revision") or "")
        if (
            expected_revision
            and entry.revision
            and entry.revision != expected_revision
        ):
            raise RuntimeError(
                "skills-lock.json revision does not match the plan: "
                f"{entry.revision!r} != {expected_revision!r}"
            )
        installed: list[str] = []
        for item in entry.installed_paths:
            candidate = (scope_root / item).resolve()
            try:
                relative = candidate.relative_to(scope_root.resolve())
            except ValueError as exc:
                raise RuntimeError(
                    "skills-lock.json contains an unsafe installed path"
                ) from exc
            installed.append(relative.as_posix())
        evidence = {
            "schema_version": 1,
            "manager_name": "skills",
            "manager_version": manager_version,
            "receipt_id": entry.name,
            "canonical_source": entry.source,
            "immutable_revision": entry.revision,
            "content_digest": entry.content_digest,
        }
        return evidence, installed
