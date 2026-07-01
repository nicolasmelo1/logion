# SPDX-License-Identifier: MIT
"""Companion store publication automation.

Reuses the public Logion CLI as the wire protocol for uploading a
companion bundle to the Logion marketplace and requesting publication
review. Does **not** approve its own publication — that step requires
a human reviewer.

Usage::

    python scripts/release_store.py publish-companion \\\\
        --version 0.1.6 \\\\
        --course-id 5ddf32c6-e139-4056-ac94-c4a231bfd932
    python scripts/release_store.py publish-companion \\\\
        --version 0.1.6 \\\\
        --course-id 5ddf32c6-e139-4056-ac94-c4a231bfd932 \\\\
        --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
import tarfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import run as subprocess_run
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parents[1]

BUNDLE_TARBALL_NAME = "logion-marketplace-companion-{version}.tar.gz"

# The Logion API key used by the CLI to authenticate store operations.
# Set as a GitHub Actions secret or environment variable before running
# store publication. The CLI reads this via its standard credential
# resolution (env var takes precedence over stored credentials).
STORE_API_KEY_ENV = "LOGION_API_KEY"

# Accepted publication review statuses that allow the script to
# proceed without error. Any other status fails the release.
_OK_STATUSES = frozenset({"queued", "passed"})

# A UUID-format check for course IDs.  Used with search() to find
# a UUID anywhere in CLI output, and with match() via fullmatch()
# for course_id validation.
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class UploadFileSpec:
    """A single file to upload as part of a companion bundle."""

    upload_path: str
    local_path: Path


@dataclass(frozen=True)
class CompanionStorePublishPlan:
    """The plan for publishing a companion bundle to the store."""

    course_id: str
    version: str
    bundle_tarball: Path
    extracted_dir: Path
    upload_files: tuple[UploadFileSpec, ...]


class CommandRunner(Protocol):
    """Run shell commands, returning the CompletedProcess."""

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
    ) -> CompletedProcess[str]: ...


class SubprocessRunner:
    """Real CommandRunner backed by subprocess.run."""

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
    ) -> CompletedProcess[str]:
        return subprocess_run(
            list(args),
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
        )


class CompanionStorePublisher:
    """Publish a companion bundle to the Logion marketplace store."""

    def __init__(
        self,
        repo_root: Path = REPO_ROOT,
        runner: CommandRunner | None = None,
    ) -> None:
        self._root = repo_root
        self._runner = runner or SubprocessRunner()

    # -- plan ---------------------------------------------------

    def build_plan(
        self,
        version: str,
        course_id: str,
    ) -> CompanionStorePublishPlan:
        """Build a publish plan from the bundle tarball."""
        if not _UUID_RE.fullmatch(course_id):
            raise ValueError(
                f"course_id must be a UUID, got: {course_id!r}",
            )

        tarball = (
            self._root / "dist" / BUNDLE_TARBALL_NAME.format(version=version)
        )
        if not tarball.exists():
            raise FileNotFoundError(
                f"Bundle tarball not found: {tarball}. "
                f"Run `make companion-bundle` first.",
            )

        # Match _list_tarball_files extraction dir naming (strips
        # all suffixes, not just .stem which leaves .tar on .tar.gz).
        tarball_name = tarball.name
        for _suffix in tarball.suffixes:
            tarball_name = tarball_name.rsplit(".", 1)[0]
        extracted_dir = (
            self._root / "dist" / f"companion-extract-{tarball_name}"
        )
        files = self._list_tarball_files(tarball)
        return CompanionStorePublishPlan(
            course_id=course_id,
            version=version,
            bundle_tarball=tarball,
            extracted_dir=extracted_dir,
            upload_files=tuple(files),
        )

    def _list_tarball_files(
        self,
        tarball: Path,
    ) -> list[UploadFileSpec]:
        """List the files inside a companion bundle tarball.

        Files are extracted to ``extracted_dir`` before upload so
        ``local_path`` points to a real on-disk file.
        """
        # Strip all suffixes (.tar.gz → bare name); Path.stem
        # only removes the last suffix, leaving ".tar" behind.
        tarball_name = tarball.name
        for _suffix in tarball.suffixes:
            tarball_name = tarball_name.rsplit(".", 1)[0]
        extract_dir = self._root / "dist" / f"companion-extract-{tarball_name}"
        extract_dir.mkdir(parents=True, exist_ok=True)

        specs: list[UploadFileSpec] = []
        with tarfile.open(tarball, "r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                tar.extract(member, path=extract_dir, filter="data")
                local = extract_dir / member.name
                specs.append(
                    UploadFileSpec(
                        upload_path=member.name,
                        local_path=local,
                    ),
                )
        return specs

    # -- validate ----------------------------------------------

    def validate_bundle(
        self,
        plan: CompanionStorePublishPlan,
    ) -> None:
        """Validate the bundle via the companion verify script."""
        result = self._runner.run(
            [
                "uv",
                "run",
                "python",
                "packages/agent-companion/scripts/verify_bundle.py",
                str(plan.bundle_tarball),
            ],
            cwd=self._root,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Bundle verification failed:\n{result.stderr}",
            )

    # -- upload -------------------------------------------------

    def create_upload(
        self,
        plan: CompanionStorePublishPlan,
    ) -> str:
        """Create an upload session, returning the version_id."""
        cmd = [
            "logion",
            "courses",
            "uploads",
            "create",
            plan.course_id,
        ]
        for spec in plan.upload_files:
            cmd.append("--file")
            cmd.append(
                f"{spec.upload_path}={spec.local_path}",
            )
        result = self._runner.run(cmd, cwd=self._root)
        if result.returncode != 0:
            raise RuntimeError(
                f"uploads create failed:\n{result.stderr}",
            )
        version_id = self._extract_version_id(result.stdout)
        if not version_id:
            raise RuntimeError(
                "Could not determine version_id from uploads create "
                "output. Ensure the configured account is the course "
                "owner.",
            )
        return version_id

    def _extract_version_id(self, output: str) -> str | None:
        """Extract a version_id (UUID) from CLI output."""
        match = _UUID_RE.search(output)
        return match.group(0) if match else None

    def push_upload(
        self,
        plan: CompanionStorePublishPlan,
        version_id: str,
    ) -> None:
        """Push the upload bytes to S3."""
        session_file = (
            plan.extracted_dir.parent / f"upload-session-{version_id}.json"
        )
        cmd = [
            "logion",
            "courses",
            "uploads",
            "push",
            plan.course_id,
            version_id,
            "--session-file",
            str(session_file),
        ]
        for spec in plan.upload_files:
            cmd.append("--file")
            cmd.append(
                f"{spec.upload_path}={spec.local_path}",
            )
        result = self._runner.run(cmd, cwd=self._root)
        if result.returncode != 0:
            raise RuntimeError(
                f"uploads push failed:\n{result.stderr}",
            )

    def complete_upload(
        self,
        plan: CompanionStorePublishPlan,
        version_id: str,
    ) -> None:
        """Mark the upload session as complete."""
        cmd = [
            "logion",
            "courses",
            "uploads",
            "complete",
            plan.course_id,
            version_id,
        ]
        result = self._runner.run(cmd, cwd=self._root)
        if result.returncode != 0:
            raise RuntimeError(
                f"uploads complete failed:\n{result.stderr}",
            )

    # -- publication review -------------------------------------

    def request_publication(
        self,
        course_id: str,
    ) -> None:
        """Request publication review for the course."""
        cmd = [
            "logion",
            "courses",
            "publication",
            "request",
            course_id,
        ]
        result = self._runner.run(cmd, cwd=self._root)
        if result.returncode != 0:
            raise RuntimeError(
                f"publication request failed:\n{result.stderr}",
            )
        status = self._extract_status(result.stdout)
        if status and status not in _OK_STATUSES:
            raise RuntimeError(
                f"Publication review returned status {status!r}, "
                f"expected one of {sorted(_OK_STATUSES)}.",
            )
        self._print_reviewer_followup(course_id)

    def _extract_status(self, output: str) -> str | None:
        """Extract the publication review status from output."""
        for line in output.splitlines():
            lower = line.lower()
            if "status" in lower:
                for word in line.split():
                    word = word.strip('"').strip(",").lower()
                    if word and word.replace("_", "-") in (
                        "queued",
                        "passed",
                        "rejected",
                        "failed",
                        "pending",
                        "in_progress",
                        "in-progress",
                    ):
                        return word.replace("_", "-")
        return None

    def _print_reviewer_followup(self, course_id: str) -> None:
        """Print reviewer follow-up commands (does not self-approve)."""
        print(
            "\nPublication review requested. A reviewer must approve "
            "before the version goes live.\n"
            "Reviewer follow-up commands:\n"
            f"  logion courses publication latest {course_id}\n",
            file=sys.stderr,
        )

    # -- full sequence ------------------------------------------

    def publish(
        self,
        version: str,
        course_id: str,
        *,
        dry_run: bool = False,
    ) -> dict[str, object]:
        """Run the full publish sequence.

        In dry-run mode, prints the commands that would be run but
        does not execute them.
        """
        plan = self.build_plan(version, course_id)

        if dry_run:
            commands = self._dry_run_commands(plan)
            for cmd in commands:
                print(cmd)
            return {
                "dry_run": True,
                "commands": commands,
            }

        self.validate_bundle(plan)
        version_id = self.create_upload(plan)
        self.push_upload(plan, version_id)
        self.complete_upload(plan, version_id)
        self.request_publication(course_id)
        return {
            "dry_run": False,
            "version_id": version_id,
            "course_id": course_id,
            "version": version,
        }

    def _dry_run_commands(
        self,
        plan: CompanionStorePublishPlan,
    ) -> list[str]:
        """Return the commands that would be executed."""
        commands: list[str] = []
        commands.append(
            f"# validate bundle: {plan.bundle_tarball}",
        )
        commands.append(
            f"uv run python "
            f"packages/agent-companion/scripts/verify_bundle.py "
            f"{plan.bundle_tarball}",
        )
        create_cmd = "logion courses uploads create " + plan.course_id
        for spec in plan.upload_files:
            create_cmd += f" --file {spec.upload_path}={spec.local_path}"
        commands.append(create_cmd)
        commands.append(
            "# push_upload <version_id> — version_id from create output",
        )
        push_cmd = f"logion courses uploads push {plan.course_id} <version_id>"
        for spec in plan.upload_files:
            push_cmd += f" --file {spec.upload_path}={spec.local_path}"
        commands.append(push_cmd)
        commands.append(
            f"logion courses uploads complete {plan.course_id} <version_id>",
        )
        commands.append(
            "logion courses publication request " + plan.course_id,
        )
        return commands


# ── CLI ----------------------------------------------------------


def cmd_publish_companion(args: argparse.Namespace) -> int:
    """Publish the companion bundle to the store."""
    import os

    if not args.dry_run and not os.environ.get(STORE_API_KEY_ENV):
        print(
            f"ERROR: {STORE_API_KEY_ENV} is not set. "
            "The store publisher needs a Logion API key to authenticate "
            "course upload and publication request calls.",
            file=sys.stderr,
        )
        return 2

    publisher = CompanionStorePublisher()
    result = publisher.publish(
        version=args.version,
        course_id=args.course_id,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        print(f"Companion {args.version} published to store.")
        print(f"  course_id: {result.get('course_id')}")
        print(f"  version_id: {result.get('version_id')}")
    return 0


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Companion store publication automation",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pub = sub.add_parser(
        "publish-companion",
        help="Publish a companion bundle to the Logion store",
    )
    pub.add_argument("--version", required=True)
    pub.add_argument("--course-id", required=True)
    pub.add_argument("--dry-run", action="store_true")
    pub.set_defaults(func=cmd_publish_companion)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
