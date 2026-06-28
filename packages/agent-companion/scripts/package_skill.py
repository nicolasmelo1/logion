#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and build the Logion Marketplace Companion skill package.

Subcommands:
  validate  — structural, manifest, and secret checks.
  build     — produce a deterministic release tarball + sidecar files.

Exits 0 on success, 1 on failure.

Usage:
    python scripts/package_skill.py validate
    python scripts/package_skill.py build \\
        --out dist/ --version 0.1.0 --release
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

BUNDLE_KIND = "logion-marketplace-companion"

REQUIRED_DIRS = [
    "course",
    "references",
    "scripts",
    "tests",
]

REQUIRED_FILES = [
    "SKILL.md",
    "LICENSE",
    "course/capabilities.yaml",
    "references/creator-course-management.md",
    "references/account-and-identity.md",
    "references/notifications-and-reports.md",
    "references/credits-and-payments.md",
    "references/bounties.md",
    "references/course-review-queue.md",
    "references/admin-operations.md",
    "references/troubleshooting.md",
    "references/referrals.md",
]

# High-confidence secret patterns: always FAIL the check.
SECRET_PATTERNS_CRITICAL = [
    "-----BEGIN",
    "ghp_",
    "gho_",
    "sk-",
    "AKIA",
    "private_key",
    "api_key",
    "apikey",
    "auth_token",
    "bearer ",
]

# Low-confidence patterns: WARN in source/asset files,
# FAIL only inside SKILL.md body.
SECRET_PATTERNS_LOW = [
    "secret",
    "token",
    "password",
    "credential",
]

MAX_SKILL_SIZE_KB = 16

# ── Files included in the release bundle (relative to companion) ────

BUNDLE_SKILL_REF_FILES = [
    "references/account-and-identity.md",
    "references/admin-operations.md",
    "references/bounties.md",
    "references/course-review-queue.md",
    "references/creator-course-management.md",
    "references/notifications-and-reports.md",
    "references/credits-and-payments.md",
    "references/troubleshooting.md",
    "references/referrals.md",
]

BUNDLE_FILES: list[tuple[str, Path]] = [
    # (tarball-relative path, source absolute path)
    ("SKILL.md", ROOT / "SKILL.md"),
    (
        "course/capabilities.yaml",
        ROOT / "course" / "capabilities.yaml",
    ),
    ("LICENSE", ROOT / "LICENSE"),
    ("README.md", ROOT / "README.md"),
]
for _ref in BUNDLE_SKILL_REF_FILES:
    BUNDLE_FILES.append((_ref, ROOT / _ref))


# ── Validation helpers (existing logic, preserved) ──────────────────


def _check_structure(report: list[str]) -> bool:
    """Verify all required directories and files exist."""
    ok = True
    for d in REQUIRED_DIRS:
        if not (ROOT / d).is_dir():
            report.append(f"MISSING directory: {d}/")
            ok = False
        else:
            report.append(f"OK directory: {d}/")

    for f in REQUIRED_FILES:
        if not (ROOT / f).is_file():
            report.append(f"MISSING file: {f}")
            ok = False
        else:
            report.append(f"OK file: {f}")
    return ok


def _check_skill_md(report: list[str]) -> bool:
    """Verify SKILL.md has frontmatter and is within size budget."""
    ok = True
    skill_path = ROOT / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        report.append("FAIL SKILL.md missing frontmatter")
        ok = False
    else:
        report.append("OK SKILL.md has frontmatter")

    lines = content.splitlines()
    frontmatter_end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter_end = i
            break

    if frontmatter_end is None:
        report.append("FAIL SKILL.md frontmatter not closed")
        return False

    body = "\n".join(lines[frontmatter_end + 1 :])

    size_kb = len(content.encode("utf-8")) / 1024
    if size_kb > MAX_SKILL_SIZE_KB:
        report.append(
            f"FAIL SKILL.md size {size_kb:.1f}KB exceeds "
            f"budget {MAX_SKILL_SIZE_KB}KB"
        )
        ok = False
    else:
        report.append(f"OK SKILL.md size {size_kb:.1f}KB within budget")

    for pattern in SECRET_PATTERNS_CRITICAL:
        if pattern.lower() in body.lower():
            report.append(
                f"FAIL SKILL.md body contains "
                f"critical secret pattern: {pattern}"
            )
            ok = False

    for pattern in SECRET_PATTERNS_LOW:
        if pattern.lower() in body.lower():
            report.append(
                f"WARN SKILL.md body contains "
                f"low-confidence pattern: {pattern}"
            )

    return ok


def _check_capabilities(report: list[str]) -> bool:
    """Verify the canonical capability manifest.

    The detailed schema validation lives in
    ``packages/cli/cli/_course_capabilities.py``.  Here we only
    confirm the file parses as version-1 YAML.
    """
    import yaml

    cap_path = ROOT / "course" / "capabilities.yaml"
    try:
        data = yaml.safe_load(cap_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.append("FAIL course/capabilities.yaml not found")
        return False
    except (OSError, yaml.YAMLError) as exc:
        report.append(f"FAIL course/capabilities.yaml read/parse: {exc}")
        return False

    if not isinstance(data, dict):
        report.append("FAIL course/capabilities.yaml is not a mapping")
        return False

    if data.get("version") != 1:
        report.append(
            "FAIL course/capabilities.yaml: version must be exactly 1"
        )
        return False

    report.append("OK course/capabilities.yaml parses as version 1")
    if "summary" in data:
        report.append("OK capabilities.yaml has key: summary")
    return True


# Files where low-confidence patterns are acceptable.
_LOW_PATTERN_ALLOWLIST = {
    "capabilities.yaml",
    "account-and-identity.md",
    "troubleshooting.md",
}

# Files that reference secret pattern names for documentation
# or test assertions — not actual secrets.
_SECRET_NAME_SKIP_FILES = {
    "package_skill.py",
    "test_package_skill.py",
    "test_skill_structure.py",
    "test_capability_manifest.py",
    "capabilities.yaml",
}


def _should_skip_path(
    path: Path, skip_dirs: set[str], skip_exts: set[str]
) -> bool:
    """Return True if this path should be skipped during checks."""
    if path.is_dir():
        return True
    if path.suffix in skip_exts:
        return True
    if any(part in skip_dirs for part in path.parts):
        return True
    if path.name in _SECRET_NAME_SKIP_FILES:
        return True
    rel = path.relative_to(ROOT)
    return rel.parts[0] == "tests" and path.suffix == ".py"


def _check_no_secrets(report: list[str]) -> bool:
    """Verify no runtime files contain critical secrets."""
    ok = True
    skip_dirs = {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "evals",
    }
    skip_exts = {".pyc", ".pyo", ".gguf", ".bin"}

    for path in ROOT.rglob("*"):
        if _should_skip_path(path, skip_dirs, skip_exts):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # nosec B110,B112
            continue

        text_lower = text.lower()
        rel = path.relative_to(ROOT)

        for pattern in SECRET_PATTERNS_CRITICAL:
            if pattern.lower() in text_lower:
                report.append(
                    f"FAIL {rel} contains critical secret pattern: {pattern}"
                )
                ok = False

        if path.name in _LOW_PATTERN_ALLOWLIST:
            continue

        for pattern in SECRET_PATTERNS_LOW:
            if pattern.lower() in text_lower:
                report.append(
                    f"WARN {rel} contains low-confidence pattern: {pattern}"
                )

    return ok


# ── Build helpers ──────────────────────────────────────────────────


def _file_sha256(path: Path) -> str:
    """Return hex sha256 of file contents."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_frontmatter_safety() -> list[str]:
    """Extract safety.requires_confirmation from SKILL.md."""
    import yaml

    content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        print("ERROR: SKILL.md missing frontmatter opening ---")
        sys.exit(1)
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        print("ERROR: SKILL.md frontmatter not closed")
        sys.exit(1)
    fm = "\n".join(lines[1:end])
    data = yaml.safe_load(fm)
    if not isinstance(data, dict):
        print("ERROR: SKILL.md frontmatter is not a mapping")
        sys.exit(1)
    safety = data.get("safety", {})
    if not isinstance(safety, dict):
        print("ERROR: SKILL.md safety is not a mapping")
        sys.exit(1)
    requires = safety.get("requires_confirmation", [])
    if not isinstance(requires, list):
        print("ERROR: SKILL.md safety.requires_confirmation is not a list")
        sys.exit(1)
    return requires


def _read_cli_version() -> str:
    """Read the CLI version from packages/cli/cli/_version.py.

    Tries importing the module first; falls back to reading the
    version directly from pyproject.toml (the canonical source).
    """
    try:
        from cli._version import __version__

        return __version__  # noqa: TRY300
    except ImportError:
        pass
    # Fallback: read the canonical version from pyproject.toml.
    import tomllib

    pyproject = REPO_ROOT / "packages" / "cli" / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return data["project"]["version"]
    except (KeyError, FileNotFoundError, OSError) as exc:
        print(f"ERROR: Cannot determine CLI version: {exc}")
        sys.exit(1)


def _git_short_sha() -> str:
    """Return short git SHA of HEAD, or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(REPO_ROOT),
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _build_manifest(
    version: str,
    cli_version: str,
    git_commit: str,
    skill_md_sha256: str,
    references: list[dict[str, str | int]],
    capability_manifest: dict[str, str],
    requires_confirmation: list[str],
) -> dict:
    """Return the manifest.json dict."""
    return {
        "schema_version": 1,
        "bundle_kind": BUNDLE_KIND,
        "version": version,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": git_commit,
        "minimum_cli_version": cli_version,
        "skill_name": "logion",
        "skill_md_sha256": skill_md_sha256,
        "references": references,
        "capability_manifest": capability_manifest,
        "safety": {
            "requires_confirmation": requires_confirmation,
        },
    }


def _manifest_json_bytes(manifest: dict) -> bytes:
    """Serialize manifest dict to deterministic JSON bytes."""
    text = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    return text.encode("utf-8")


def _deterministic_tar_info(name: str, size: int) -> tarfile.TarInfo:
    """Create a deterministic TarInfo with zeroed metadata."""
    info = tarfile.TarInfo(name=name)
    info.size = size
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o644
    info.type = tarfile.REGTYPE
    return info


def _deterministic_dir_info(name: str) -> tarfile.TarInfo:
    """Create a deterministic TarInfo for a directory."""
    info = tarfile.TarInfo(name=name)
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o755
    info.type = tarfile.DIRTYPE
    return info


def cmd_validate() -> int:
    """Run structural + secret validation (original behaviour)."""
    report: list[str] = []
    ok = True

    ok &= _check_structure(report)
    ok &= _check_skill_md(report)
    ok &= _check_capabilities(report)
    ok &= _check_no_secrets(report)

    for line in report:
        print(line)

    if not ok:
        print("\nFAILED: Package validation failed.")
        return 1

    print("\nPASSED: Package validation succeeded.")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """Build a deterministic release tarball + sidecar files."""
    version: str = args.version
    out_dir: Path = Path(args.out).resolve()

    # Verify source files exist
    for _tar_path, src_path in BUNDLE_FILES:
        if not src_path.is_file():
            print(f"ERROR: Source file not found: {src_path}")
            return 1

    # Compute sha256 for SKILL.md
    skill_md_sha256 = _file_sha256(ROOT / "SKILL.md")

    # Build references list (sorted by path)
    refs: list[dict[str, str | int]] = []
    for ref_path in sorted(BUNDLE_SKILL_REF_FILES):
        full = ROOT / ref_path
        if not full.is_file():
            print(f"ERROR: Reference not found: {ref_path}")
            return 1
        sha = _file_sha256(full)
        size = full.stat().st_size
        refs.append({"path": ref_path, "sha256": sha, "size": size})

    # Capability manifest entry
    cap_sha = _file_sha256(ROOT / "course" / "capabilities.yaml")

    # Read CLI version and git SHA
    cli_version = _read_cli_version()
    git_commit = _git_short_sha()

    # Parse safety from SKILL.md frontmatter
    requires_confirmation = _parse_frontmatter_safety()

    # Build manifest
    manifest = _build_manifest(
        version=version,
        cli_version=cli_version,
        git_commit=git_commit,
        skill_md_sha256=skill_md_sha256,
        references=refs,
        capability_manifest={
            "path": "course/capabilities.yaml",
            "sha256": cap_sha,
        },
        requires_confirmation=requires_confirmation,
    )

    manifest_bytes = _manifest_json_bytes(manifest)

    # Tarball name and top-level directory
    bundle_dir_name = f"{BUNDLE_KIND}-{version}"
    tarball_name = f"{bundle_dir_name}.tar.gz"

    # Create output directory
    out_dir.mkdir(parents=True, exist_ok=True)

    # Collect file entries for the tarball
    file_entries: list[tuple[str, bytes]] = []

    # Manifest
    file_entries.append((f"{bundle_dir_name}/manifest.json", manifest_bytes))

    # Regular files from BUNDLE_FILES
    for tar_path, src_path in BUNDLE_FILES:
        full_tar = f"{bundle_dir_name}/{tar_path}"
        file_entries.append((full_tar, src_path.read_bytes()))

    # Sort file entries lexicographically for determinism
    file_entries.sort(key=lambda e: e[0])

    # Collect unique directories needed
    dirs_needed: set[str] = set()
    for tar_path, _ in BUNDLE_FILES:
        parts = tar_path.split("/")
        for i in range(1, len(parts)):
            parent = "/".join(parts[:i])
            dirs_needed.add(f"{bundle_dir_name}/{parent}")
    for d in ["course", "references"]:
        dirs_needed.add(f"{bundle_dir_name}/{d}")
    dirs_needed.add(bundle_dir_name)

    # Sort directories for determinism
    all_dirs = sorted(dirs_needed)

    # Write tarball deterministically
    tarball_path = out_dir / tarball_name
    with open(tarball_path, "wb") as f_out:
        gz = gzip.GzipFile(fileobj=f_out, mode="wb", mtime=0)
        with tarfile.open(fileobj=gz, mode="w") as tar:
            # Add directories first (sorted)
            for d in all_dirs:
                tar.addfile(_deterministic_dir_info(d))

            # Add files (sorted)
            for name, data in file_entries:
                info = _deterministic_tar_info(name, len(data))
                tar.addfile(info, BytesIO(data))

        gz.close()

    # Write sidecar SKILL.md
    (out_dir / "SKILL.md").write_bytes((ROOT / "SKILL.md").read_bytes())

    # Write sidecar manifest.json
    (out_dir / "manifest.json").write_bytes(manifest_bytes)

    print(f"Built {tarball_path}")
    tar_hash = hashlib.sha256(tarball_path.read_bytes()).hexdigest()
    print(f"  SHA256: {tar_hash}")
    print(f"Sidecar: {out_dir / 'SKILL.md'}")
    print(f"Sidecar: {out_dir / 'manifest.json'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Logion Companion skill package tool"
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # validate subcommand (original behaviour)
    subparsers.add_parser(
        "validate",
        help="Validate the companion bundle structure and check for secrets",
    )

    # build subcommand
    sub_build = subparsers.add_parser(
        "build",
        help="Build a deterministic release tarball and sidecar files",
    )
    sub_build.add_argument(
        "--out",
        required=True,
        help="Output directory for the tarball and sidecar files",
    )
    sub_build.add_argument(
        "--version",
        required=True,
        help="SemVer version string (e.g. 0.1.0)",
    )
    sub_build.add_argument(
        "--release",
        action="store_true",
        help="Confirm this is a release build "
        "(required flag, present for CI safety)",
    )

    args = parser.parse_args()

    if args.command == "validate":
        return cmd_validate()
    if args.command == "build":
        if not args.release:
            parser.error("--release flag is required for build command")
        return cmd_build(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
