# SPDX-License-Identifier: MIT
"""Release orchestrator for coordinated multi-package releases.

Builds a :class:`ReleasePlan` from the current repository state,
bumps versions across all three public packages, runs the full
check/build/manifest pipeline, and creates/pushes tags. Package
publication and GitHub Release asset attachment are handled by
GitHub Actions triggered from those tags.

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
import os
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
SMOKE_FINDINGS_ENV = "SMOKE_FINDINGS"

CHANGELOG_PATH = REPO_ROOT / "releases" / "CHANGELOG.md"

# Conventional Commit types displayed in the changelog, in display order.
_CHANGELOG_SECTIONS: tuple[tuple[str, str], ...] = (
    ("feat", "Features"),
    ("fix", "Bug Fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactors"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("ci", "CI"),
    ("chore", "Chores"),
)

# Maps commit type to changelog section heading.
_TYPE_TO_SECTION: dict[str, str] = dict(_CHANGELOG_SECTIONS)

_PR_RE = re.compile(r"\(#(\d+)\)\s*$")
_COMMIT_RE = re.compile(
    r"^(?P<type>feat|fix|perf|refactor|docs|test|ci|chore|build|revert)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r":\s*(?P<subject>.+?)"
    r"(?:\s+\(#(?P<pr>\d+)\))?\s*$",
)


@dataclass(frozen=True)
class MergedPR:
    """A single merged pull request for changelog purposes."""

    number: int
    author: str
    commit_type: str
    scope: str | None
    subject: str


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


def _porcelain_paths(stdout: str) -> tuple[str, ...]:
    """Extract changed paths from ``git status --porcelain -z`` output."""
    paths: list[str] = []
    parts = [part for part in stdout.split("\0") if part]
    i = 0
    while i < len(parts):
        entry = parts[i]
        if len(entry) < 4:
            i += 1
            continue
        status = entry[:2]
        path = entry[3:].strip()
        paths.append(path)
        if status[0] in {"R", "C"} or status[1] in {"R", "C"}:
            i += 1
        i += 1
    return tuple(paths)


def _find_last_release_tag(
    runner: CommandRunner,
    repo_root: Path,
) -> str | None:
    """Return the most recent ``logion-cli-v*`` tag, or None."""
    result = runner.run(
        ["git", "tag", "--sort=-creatordate", "--list", "logion-cli-v*"],
        cwd=repo_root,
        check=False,
    )
    lines = [line for line in result.stdout.strip().splitlines() if line]
    return lines[0] if lines else None


def _collect_merged_prs(
    runner: CommandRunner,
    repo_root: Path,
    from_tag: str | None,
) -> list[MergedPR]:
    """Collect merged PRs since *from_tag* via ``git log``.

    Uses ``--no-merges`` to get the squashed commit for each PR.
    The commit subject carries the Conventional Commit prefix and the
    PR number in ``(#N)`` form.  The author is the commit's author name.

    Commits without a PR number (e.g. direct pushes or release commits)
    are skipped — they are not user-facing changes.
    """
    rev_range = f"{from_tag}..HEAD" if from_tag else "HEAD"
    result = runner.run(
        [
            "git",
            "log",
            rev_range,
            "--no-merges",
            "--pretty=format:%an|%s",
        ],
        cwd=repo_root,
        check=False,
    )
    prs: list[MergedPR] = []
    for line in result.stdout.strip().splitlines():
        if not line or "|" not in line:
            continue
        author, _, subject = line.partition("|")
        subject = subject.strip()
        match = _COMMIT_RE.match(subject)
        if not match:
            continue
        pr_str = match.group("pr")
        if not pr_str:
            continue
        prs.append(
            MergedPR(
                number=int(pr_str),
                author=author.strip(),
                commit_type=match.group("type"),
                scope=match.group("scope"),
                subject=match.group("subject").strip(),
            )
        )
    return prs


def _format_changelog_entry(
    version: str,
    prs: Sequence[MergedPR],
) -> str:
    """Build a Markdown changelog entry for *version* from *prs*."""
    lines: list[str] = [f"## {version}", ""]

    # Group by section, preserving order within each section.
    sections: dict[str, list[MergedPR]] = {
        heading: [] for _, heading in _CHANGELOG_SECTIONS
    }
    extras: list[MergedPR] = []
    for pr in prs:
        heading = _TYPE_TO_SECTION.get(pr.commit_type)
        if heading and heading in sections:
            sections[heading].append(pr)
        else:
            extras.append(pr)

    # Collect unique authors for the contributor line.
    all_authors = {pr.author for pr in prs}

    for heading in sections:
        items = sections[heading]
        if not items:
            continue
        lines.append(f"### {heading}")
        for pr in items:
            scope = f"**{pr.scope}**: " if pr.scope else ""
            author = f"@{pr.author}"
            lines.append(f"- {scope}{pr.subject} (#{pr.number}) — {author}")
        lines.append("")

    if extras:
        lines.append("### Other")
        for pr in extras:
            lines.append(f"- {pr.subject} (#{pr.number}) — @{pr.author}")
        lines.append("")

    if all_authors:
        # Sort alphabetically, case-insensitive.
        sorted_authors = sorted(all_authors, key=str.lower)
        lines.append(
            f"**Contributors:** {', '.join(f'@{a}' for a in sorted_authors)}"
        )
        lines.append("")

    return "\n".join(lines)


def update_changelog_file(
    changelog_path: Path,
    version: str,
    prs: Sequence[MergedPR],
) -> str:
    """Prepend a new entry to the changelog file and return it.

    If the file has the standard header (lines before the first
    ``## `` section), the new entry is inserted right after it.
    """
    entry = _format_changelog_entry(version, prs)
    if not changelog_path.exists():
        changelog_path.write_text(entry + "\n", encoding="utf-8")
        return entry

    existing = changelog_path.read_text(encoding="utf-8")
    # Find the first "## " section heading.
    insert_pos = existing.find("\n## ")
    if insert_pos == -1:
        # No existing sections — append.
        new_content = existing.rstrip() + "\n\n" + entry + "\n"
    else:
        # Insert after the header, before the first section.
        new_content = (
            existing[: insert_pos + 1]
            + entry
            + "\n"
            + existing[insert_pos + 1 :]
        )
    changelog_path.write_text(new_content, encoding="utf-8")
    return entry


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
        _ = check
        return subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            check=False,
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
        normalized_version = str(next_version)
        for name, pkg_dir, tag_prefix, build_targets in _PACKAGE_CONFIG:
            current = Version(_read_pyproject_version(pkg_dir))
            tag_name = f"{tag_prefix}{normalized_version}"
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

        smoke_findings = os.environ.get(SMOKE_FINDINGS_ENV)
        smoke_findings_path = (
            Path(smoke_findings)
            if smoke_findings
            else self._root / SMOKE_FINDINGS_FILENAME
        )

        return ReleasePlan(
            version=next_version,
            packages=tuple(packages),
            changed_paths=tuple(
                name_to_path[name] for name in changed if name in name_to_path
            ),
            tags_to_create=tuple(tags),
            manifest_outputs=manifest_outputs,
            smoke_findings_path=smoke_findings_path,
            publish_store=publish_store,
        )

    def detect_changed_packages(self) -> tuple[str, ...]:
        """Return the package short-names with uncommitted changes."""
        result = self._runner.run(
            ["git", "status", "--porcelain", "-z"],
            cwd=self._root,
        )
        changed: list[str] = []
        paths = _porcelain_paths(result.stdout)
        for name, pkg_dir, _, _ in _PACKAGE_CONFIG:
            prefix = pkg_dir + "/"
            if any(path.startswith(prefix) for path in paths):
                changed.append(name)
        return tuple(changed)

    def validate_clean_or_release_only_worktree(self) -> None:
        """Ensure the worktree is clean or has only smoke findings."""
        result = self._runner.run(
            ["git", "status", "--porcelain", "-z"],
            cwd=self._root,
        )
        for path in _porcelain_paths(result.stdout):
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
        if self._release_already_applied():
            return
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

    def _release_already_applied(self) -> bool:
        """Return True when a previous run already pushed this release."""
        version = str(self._plan.version)
        if any(
            _read_pyproject_version(str(pkg.path)) != version
            for pkg in self._plan.packages
        ):
            return False
        for tag in self._plan.tags_to_create:
            result = self._runner.run(
                ["git", "tag", "-l", tag],
                cwd=self._root(),
                check=False,
            )
            if result.stdout.strip() != tag:
                return False
        return True

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
            ["uv", "lock"],
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

    # -- changelog ----------------------------------------------

    def update_changelog(self) -> None:
        """Prepend a changelog entry for this release to CHANGELOG.md.

        Collects merged PRs since the last release tag, groups them by
        Conventional Commit type, and inserts the entry after the file
        header.  External contributors are credited by name.
        """
        last_tag = _find_last_release_tag(self._runner, self._root())
        prs = _collect_merged_prs(self._runner, self._root(), last_tag)
        update_changelog_file(
            CHANGELOG_PATH,
            str(self._plan.version),
            prs,
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
        if self._release_already_applied():
            self.run_checks()
            self.verify_smoke_evidence()
            if self._plan.publish_store:
                self.publish_store()
            return {
                "dry_run": False,
                "resumed": True,
                "pushed": False,
                "tagged": False,
                "committed": False,
                "tags": list(self._plan.tags_to_create),
                "manifests": [str(p) for p in self._plan.manifest_outputs],
                "publish_store": self._plan.publish_store,
            }
        self.bump_versions()
        self.run_checks()
        self.build_artifacts()
        self.regenerate_manifests()
        self.update_changelog()
        self.verify_smoke_evidence()
        self.commit_release()
        self.tag_release()
        self.push()
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
