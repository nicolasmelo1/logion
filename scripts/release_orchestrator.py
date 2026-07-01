# SPDX-License-Identifier: MIT
"""Release orchestrator for coordinated multi-package releases.

Builds a :class:`ReleasePlan` from the current repository state,
bumps versions across all three public packages, runs the full
check/build/manifest pipeline, and creates tags + GitHub releases.

Usage::

    python scripts/release_orchestrator.py plan --version 0.1.6 --json
    python scripts/release_orchestrator.py release --version 0.1.6
    python scripts/release_orchestrator.py release \
        --version 0.1.6 --publish-store
    python scripts/release_orchestrator.py release \
        --version 0.1.6 --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from packaging.version import InvalidVersion, Version

REPO_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from release_manifest import COMPANION_COURSE_ID  # noqa: E402

SMOKE_FINDINGS_FILENAME = "release-smoke-findings.md"

_PACKAGE_CONFIG: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "client",
        "packages/client",
        "logion-client-v",
        (),
    ),
    (
        "cli",
        "packages/cli",
        "logion-cli-v",
        (),
    ),
    (
        "companion",
        "packages/agent-companion",
        "logion-companion-v",
        ("companion-bundle", "companion-bundle-verify"),
    ),
)


def _read_pyproject_version(pyproject_dir: str) -> str:
    """Read project.version from a package's pyproject.toml."""
    toml_path = REPO_ROOT / pyproject_dir / "pyproject.toml"
    with toml_path.open("rb") as fh:
        data = tomllib.load(fh)
    return data["project"]["version"]


def _set_pyproject_version(pyproject_dir: str, version: str) -> None:
    """Write project.version into a package's pyproject.toml."""
    toml_path = REPO_ROOT / pyproject_dir / "pyproject.toml"
    text = toml_path.read_text(encoding="utf-8")
    new_text = re.sub(
        r'(version\s*=\s*)"[^"]+"',
        f'\\1"{version}"',
        text,
        count=1,
    )
    if new_text == text:
        raise RuntimeError(
            f"Could not bump version in {toml_path}",
        )
    toml_path.write_text(new_text, encoding="utf-8")


# ── data classes ──────────────────────────────────────────────────


@dataclass(frozen=True)
class ReleasePackage:
    """A single package participating in a release."""

    name: Literal["client", "cli", "companion"]
    path: Path
    current_version: Version
    next_version: Version
    tag_name: str
    build_targets: tuple[str, ...]


@dataclass(frozen=True)
class ReleasePlan:
    """The full plan for a coordinated release."""

    version: Version
    packages: tuple[ReleasePackage, ...]
    changed_paths: tuple[Path, ...]
    tags_to_create: tuple[str, ...]
    manifest_outputs: tuple[Path, ...]
    smoke_findings_path: Path
    publish_store: bool


# ── command runner ────────────────────────────────────────────────


class CommandRunner(Protocol):
    """Run shell commands, returning the CompletedProcess."""

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]: ...


class SubprocessRunner:
    """Real CommandRunner backed by subprocess.run."""

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            check=check,
            capture_output=True,
            text=True,
        )


# ── planner ───────────────────────────────────────────────────────


class ReleasePlanner:
    """Build a :class:`ReleasePlan` from the repository state."""

    def __init__(
        self,
        repo_root: Path = REPO_ROOT,
        runner: CommandRunner | None = None,
    ) -> None:
        self._root = repo_root
        self._runner = runner or SubprocessRunner()

    def load(
        self,
        version: str,
        publish_store: bool,
    ) -> ReleasePlan:
        """Create a :class:`ReleasePlan` for *version*."""
        try:
            next_version = Version(version)
        except InvalidVersion as exc:
            raise ValueError(
                f"Not a valid SemVer version: {version!r}",
            ) from exc

        packages: list[ReleasePackage] = []
        tags: list[str] = []
        for name, pkg_dir, tag_prefix, build_targets in _PACKAGE_CONFIG:
            current = Version(_read_pyproject_version(pkg_dir))
            tag_name = f"{tag_prefix}{version}"
            packages.append(
                ReleasePackage(
                    name=name,  # type: ignore[arg-type]
                    path=self._root / pkg_dir,
                    current_version=current,
                    next_version=next_version,
                    tag_name=tag_name,
                    build_targets=build_targets,
                ),
            )
            tags.append(tag_name)

        changed = self.detect_changed_packages()

        manifest_outputs = (
            self._root / "releases" / "manifest-stable.json",
            self._root / "releases" / "manifest-latest.json",
        )

        # Map package short-names to their paths for changed_paths.
        name_to_path = {
            name: self._root / pkg_dir
            for name, pkg_dir, _, _ in _PACKAGE_CONFIG
        }

        return ReleasePlan(
            version=next_version,
            packages=tuple(packages),
            changed_paths=tuple(
                name_to_path[name] for name in changed if name in name_to_path
            ),
            tags_to_create=tuple(tags),
            manifest_outputs=manifest_outputs,
            smoke_findings_path=self._root / SMOKE_FINDINGS_FILENAME,
            publish_store=publish_store,
        )

    def detect_changed_packages(self) -> tuple[str, ...]:
        """Return the package short-names with uncommitted changes."""
        result = self._runner.run(
            ["git", "status", "--porcelain"],
            cwd=self._root,
        )
        changed: list[str] = []
        for name, pkg_dir, _, _ in _PACKAGE_CONFIG:
            prefix = pkg_dir + "/"
            if any(
                line.strip().split(maxsplit=1)[-1].startswith(prefix)
                for line in result.stdout.splitlines()
                if line.strip()
            ):
                changed.append(name)
        return tuple(changed)

    def validate_clean_or_release_only_worktree(self) -> None:
        """Ensure the worktree is clean or has only smoke findings."""
        result = self._runner.run(
            ["git", "status", "--porcelain"],
            cwd=self._root,
        )
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            path = line.strip().split(maxsplit=1)[-1]
            if path == SMOKE_FINDINGS_FILENAME:
                continue
            raise RuntimeError(
                f"Worktree is dirty (unexpected: {path}). "
                f"Only {SMOKE_FINDINGS_FILENAME} is allowed.",
            )


# ── executor ──────────────────────────────────────────────────────


@dataclass
class _ExecutionContext:
    """Mutable state tracking what the executor has done."""

    pushed: bool = False
    tagged: bool = False
    committed: bool = False
    manifest_commands: list[str] = field(default_factory=list)
    tag_commands: list[str] = field(default_factory=list)


class ReleaseExecutor:
    """Execute a :class:`ReleasePlan` step by step."""

    def __init__(
        self,
        plan: ReleasePlan,
        runner: CommandRunner | None = None,
    ) -> None:
        self._plan = plan
        self._runner = runner or SubprocessRunner()
        self._ctx = _ExecutionContext()

    # -- helpers ------------------------------------------------

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self._runner.run(
            ["git", *args],
            cwd=self._plan.packages[0].path.parent.parent,
        )

    # -- preflight ----------------------------------------------

    def preflight(self) -> None:
        """Run all preflight gates."""
        ReleasePlanner(
            repo_root=self._root(),
            runner=self._runner,
        ).validate_clean_or_release_only_worktree()
        self._validate_no_conflicting_tags()
        self._validate_smoke_findings_exist()

    def _validate_no_conflicting_tags(self) -> None:
        for tag in self._plan.tags_to_create:
            result = self._runner.run(
                ["git", "tag", "-l", tag],
                cwd=self._plan.packages[0].path.parent.parent,
                check=False,
            )
            existing = result.stdout.strip()
            if existing:
                raise RuntimeError(
                    f"Tag {tag} already exists",
                )

    def _validate_smoke_findings_exist(self) -> None:
        if not self._plan.smoke_findings_path.exists():
            raise RuntimeError(
                f"Release smoke findings file not found: "
                f"{self._plan.smoke_findings_path}",
            )

    # -- bump ---------------------------------------------------

    def bump_versions(self) -> None:
        """Bump all package pyproject.toml files to the release version."""
        version_str = str(self._plan.version)
        for pkg in self._plan.packages:
            rel = pkg.path.relative_to(
                self._plan.packages[0].path.parent.parent,
            )
            _set_pyproject_version(str(rel), version_str)

    # -- checks -------------------------------------------------

    def run_checks(self) -> None:
        """Run the full check/build sequence via make."""
        steps = [
            ["uv", "lock", "--check"],
            ["make", "ci-checks"],
            ["make", "install-test"],
            ["make", "npm-test"],
            ["make", "companion-bundle"],
            ["make", "companion-bundle-verify"],
            ["make", "release-manifest"],
            ["make", "release-manifest-check"],
        ]
        for step in steps:
            result = self._runner.run(step, cwd=self._root())
            if result.returncode != 0:
                raise RuntimeError(
                    f"Step failed: {' '.join(step)}\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}",
                )

    def _root(self) -> Path:
        return self._plan.packages[0].path.parent.parent

    # -- build artifacts ----------------------------------------

    def build_artifacts(self) -> None:
        """Build companion bundle (already done in run_checks)."""
        # companion-bundle is part of the check sequence;
        # this method is a hook for future artifact-only steps.

    # -- manifests ----------------------------------------------

    def regenerate_manifests(self) -> None:
        """Regenerate stable and latest manifests."""
        for manifest_path in self._plan.manifest_outputs:
            channel = "stable" if "stable" in manifest_path.name else "latest"
            cmd = [
                "uv",
                "run",
                "python",
                "scripts/release_manifest.py",
                "build",
                "--channel",
                channel,
                "--out",
                str(manifest_path),
            ]
            self._ctx.manifest_commands.append(" ".join(cmd))
            result = self._runner.run(cmd, cwd=self._root())
            if result.returncode != 0:
                raise RuntimeError(
                    f"Manifest build failed: {result.stderr}",
                )

    # -- smoke --------------------------------------------------

    def verify_smoke_evidence(self) -> None:
        """Verify the release smoke findings file passes the gate."""
        cmd = [
            "uv",
            "run",
            "python",
            "scripts/release_smoke.py",
            "check",
            str(self._plan.smoke_findings_path),
            "--version",
            str(self._plan.version),
        ]
        result = self._runner.run(cmd, cwd=self._root())
        if result.returncode != 0:
            raise RuntimeError(
                f"Smoke evidence gate failed:\n{result.stderr}",
            )

    # -- git ----------------------------------------------------

    def commit_release(self) -> None:
        """Commit the version bump and manifest changes."""
        result = self._runner.run(
            ["git", "add", "-A"],
            cwd=self._root(),
        )
        if result.returncode != 0:
            raise RuntimeError("git add failed")
        result = self._runner.run(
            [
                "git",
                "commit",
                "-m",
                f"chore(release): {self._plan.version}",
            ],
            cwd=self._root(),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git commit failed: {result.stderr}",
            )
        self._ctx.committed = True

    def tag_release(self) -> None:
        """Create annotated git tags for every package."""
        for tag in self._plan.tags_to_create:
            cmd = [
                "git",
                "tag",
                "-a",
                tag,
                "-m",
                f"Release {tag}",
            ]
            self._ctx.tag_commands.append(" ".join(cmd))
            result = self._runner.run(cmd, cwd=self._root())
            if result.returncode != 0:
                raise RuntimeError(
                    f"git tag failed for {tag}: {result.stderr}",
                )
        self._ctx.tagged = True

    def push(self) -> None:
        """Push commits and tags to origin."""
        result = self._runner.run(
            ["git", "push", "origin", "main"],
            cwd=self._root(),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git push failed: {result.stderr}",
            )
        result = self._runner.run(
            ["git", "push", "--tags", "origin"],
            cwd=self._root(),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git push --tags failed: {result.stderr}",
            )
        self._ctx.pushed = True

    # -- GitHub releases ----------------------------------------

    def create_github_releases(self) -> None:
        """Create GitHub releases for every tag via ``gh``."""
        for tag in self._plan.tags_to_create:
            cmd = [
                "gh",
                "release",
                "create",
                tag,
                "--title",
                tag,
                "--notes",
                f"Release {tag}",
                "--target",
                "main",
            ]
            result = self._runner.run(cmd, cwd=self._root())
            if result.returncode != 0:
                raise RuntimeError(
                    f"gh release create failed for {tag}: {result.stderr}",
                )

    # -- store publication -------------------------------------

    def publish_store(self) -> None:
        """Publish the companion bundle to the store (opt-in)."""
        if not self._plan.publish_store:
            return

        course_id = COMPANION_COURSE_ID
        cmd = [
            "uv",
            "run",
            "python",
            "scripts/release_store.py",
            "publish-companion",
            "--version",
            str(self._plan.version),
            "--course-id",
            course_id,
        ]
        result = self._runner.run(cmd, cwd=self._root())
        if result.returncode != 0:
            raise RuntimeError(
                f"Store publication failed: {result.stderr}",
            )

    # -- full release sequence ---------------------------------

    def execute(
        self,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run the full release sequence.

        In dry-run mode only plans and validates — no mutations.
        """
        if dry_run:
            self.preflight()
            return {
                "dry_run": True,
                "tags": list(self._plan.tags_to_create),
                "manifests": [str(p) for p in self._plan.manifest_outputs],
                "publish_store": self._plan.publish_store,
            }

        self.preflight()
        self.bump_versions()
        self.run_checks()
        self.build_artifacts()
        self.regenerate_manifests()
        self.verify_smoke_evidence()
        self.commit_release()
        self.tag_release()
        self.push()
        self.create_github_releases()
        if self._plan.publish_store:
            self.publish_store()
        return {
            "dry_run": False,
            "pushed": self._ctx.pushed,
            "tagged": self._ctx.tagged,
            "committed": self._ctx.committed,
            "tags": list(self._plan.tags_to_create),
            "manifests": [str(p) for p in self._plan.manifest_outputs],
            "publish_store": self._plan.publish_store,
        }


# ── JSON serialization -------------------------------------------


def plan_to_json(plan: ReleasePlan) -> str:
    """Serialize a :class:`ReleasePlan` to JSON."""
    return (
        json.dumps(
            {
                "version": str(plan.version),
                "packages": [
                    {
                        "name": p.name,
                        "path": str(p.path),
                        "current_version": str(p.current_version),
                        "next_version": str(p.next_version),
                        "tag_name": p.tag_name,
                        "build_targets": list(p.build_targets),
                    }
                    for p in plan.packages
                ],
                "changed_paths": [str(p) for p in plan.changed_paths],
                "tags_to_create": list(plan.tags_to_create),
                "manifest_outputs": [str(p) for p in plan.manifest_outputs],
                "smoke_findings_path": str(plan.smoke_findings_path),
                "publish_store": plan.publish_store,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


# ── CLI ----------------------------------------------------------


def cmd_plan(args: argparse.Namespace) -> int:
    """Build and optionally print a release plan as JSON."""
    planner = ReleasePlanner()
    plan = planner.load(args.version, args.publish_store)
    if args.json:
        print(plan_to_json(plan))
    else:
        print(f"Release plan for v{plan.version}:")
        for pkg in plan.packages:
            print(
                f"  {pkg.name}: {pkg.current_version} "
                f"-> {pkg.next_version} ({pkg.tag_name})",
            )
        print(f"  Tags: {', '.join(plan.tags_to_create)}")
        print(
            f"  Manifests: {', '.join(str(p) for p in plan.manifest_outputs)}"
        )
        print(f"  Publish store: {plan.publish_store}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    """Execute a release."""
    planner = ReleasePlanner()
    plan = planner.load(args.version, args.publish_store)
    executor = ReleaseExecutor(plan)
    result = executor.execute(dry_run=args.dry_run)
    if args.dry_run:
        print("Dry-run mode — no mutations performed.")
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Release {plan.version} completed successfully.")
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Release orchestrator for Logion",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    plan_p = sub.add_parser("plan", help="Build a release plan")
    plan_p.add_argument("--version", required=True)
    plan_p.add_argument("--json", action="store_true")
    plan_p.add_argument("--publish-store", action="store_true")
    plan_p.set_defaults(func=cmd_plan)

    release_p = sub.add_parser("release", help="Execute a release")
    release_p.add_argument("--version", required=True)
    release_p.add_argument("--publish-store", action="store_true")
    release_p.add_argument("--dry-run", action="store_true")
    release_p.set_defaults(func=cmd_release)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
