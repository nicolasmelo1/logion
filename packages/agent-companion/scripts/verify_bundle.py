#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify a Logion Marketplace Companion release bundle tarball.

Checks that the bundle layout matches the contract defined in
RELEASE_BUNDLE_LAYOUT.md: required files present, no forbidden files,
manifest.json schema valid, and all sha256 checksums match.

Exits 0 on success, 1 on failure.

Usage:
    python scripts/verify_bundle.py <tarball_path>
    python scripts/verify_bundle.py <directory_path>
"""

from __future__ import annotations

import hashlib
import json
import sys
import tarfile
from pathlib import Path

BUNDLE_KIND = "logion-marketplace-companion"

REQUIRED_TOP_FILES = [
    "SKILL.md",
    "LICENSE",
    "README.md",
    "manifest.json",
]

REQUIRED_DIRS = [
    "course",
    "references",
]

REQUIRED_COURSE_FILES = [
    "course/capabilities.yaml",
]

REQUIRED_REFERENCES = [
    "references/account-and-identity.md",
    "references/admin-operations.md",
    "references/bounties.md",
    "references/course-review-queue.md",
    "references/creator-course-management.md",
    "references/notifications-and-reports.md",
    "references/payments-and-checkout.md",
    "references/troubleshooting.md",
]

ALL_REQUIRED_FILES = (
    REQUIRED_TOP_FILES + REQUIRED_COURSE_FILES + REQUIRED_REFERENCES
)

FORBIDDEN_PATTERNS = [
    "__pycache__",
    ".pyc",
    "tests/",
    "evals/",
    "scripts/",
    "pyproject.toml",
    "node_modules/",
]

MANIFEST_SCHEMA_VERSIONS = {1}


def _sha256_bytes(data: bytes) -> str:
    """Return hex sha256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def _verify_layout(
    members: set[str], version: str, errors: list[str]
) -> str | None:
    """Check required files and directories exist.

    Tarballs may or may not include explicit directory entries (e.g.
    ``logion-marketplace-companion-0.1.0/course/``).  We accept both
    forms: a file path like ``prefix/references/troubleshooting.md``
    satisfies the ``references/`` directory requirement.
    """
    prefix = f"{BUNDLE_KIND}-{version}"

    # The top-level directory need not be an explicit member — file
    # paths starting with ``prefix/`` are sufficient proof it exists.
    has_prefix_entry = prefix in members
    has_prefix_files = any(m.startswith(prefix + "/") for m in members)
    if not has_prefix_entry and not has_prefix_files:
        errors.append(
            f"Missing top-level directory: {prefix} "
            f"(no members start with '{prefix}/')"
        )

    for d in REQUIRED_DIRS:
        full = f"{prefix}/{d}"
        # Accept: explicit dir entry (with or without trailing /),
        # or any file under that directory.
        dir_explicit = full in members or f"{full}/" in members
        dir_implicit = any(m.startswith(full + "/") for m in members)
        if not dir_explicit and not dir_implicit:
            errors.append(
                f"Missing directory: {full} (neither an entry nor "
                f"any files underneath it)"
            )

    for f in ALL_REQUIRED_FILES:
        full = f"{prefix}/{f}"
        if full not in members:
            errors.append(f"Missing required file: {full}")

    return prefix


def _verify_no_forbidden(
    members: set[str], prefix: str, errors: list[str]
) -> None:
    """Check that no forbidden files/patterns exist."""
    for member in members:
        rel = member
        if rel.startswith(prefix + "/"):
            rel = rel[len(prefix) + 1 :]
        elif rel == prefix:
            continue
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in rel:
                errors.append(
                    f"Forbidden pattern '{pattern}' found in member: {member}"
                )


def _verify_no_extra_files(
    members: set[str], prefix: str, errors: list[str]
) -> None:
    """Check that no files outside the expected set exist."""
    expected = set(ALL_REQUIRED_FILES)
    expected.add("manifest.json")
    # Also allow the directories themselves
    expected_dirs = set(REQUIRED_DIRS)
    for member in members:
        if member == prefix:
            continue
        if not member.startswith(prefix + "/"):
            continue
        rel = member[len(prefix) + 1 :]
        # Skip directory entries (ending with / or
        # matching a required directory with no trailing /)
        if rel in expected_dirs or rel == "":
            continue
        # Also skip if rel matches a directory
        # (e.g. "course" or "course/")
        if any(rel == d or rel == d + "/" for d in expected_dirs):
            continue
        if rel.endswith("/") and rel.rstrip("/") in expected_dirs:
            continue
        if rel not in expected:
            errors.append(f"Unexpected file in bundle: {member}")


def _check_manifest_top_level(manifest: dict, errors: list[str]) -> None:
    """Check top-level manifest fields."""
    if "schema_version" not in manifest:
        errors.append("manifest.json missing 'schema_version'")
    elif not isinstance(manifest["schema_version"], int):
        errors.append(
            f"manifest.json schema_version must be an integer, "
            f"got {type(manifest['schema_version']).__name__}"
        )
    elif manifest["schema_version"] not in MANIFEST_SCHEMA_VERSIONS:
        errors.append(
            f"manifest.json schema_version "
            f"{manifest['schema_version']} not in "
            f"supported set {MANIFEST_SCHEMA_VERSIONS}"
        )

    if manifest.get("bundle_kind") != BUNDLE_KIND:
        errors.append(
            f"manifest.json bundle_kind must be "
            f"'{BUNDLE_KIND}', got "
            f"'{manifest.get('bundle_kind')}'"
        )

    if "version" not in manifest:
        errors.append("manifest.json missing 'version'")
    elif not isinstance(manifest["version"], str):
        errors.append(
            f"manifest.json version must be a string, "
            f"got {type(manifest['version']).__name__}"
        )

    if "generated_at" not in manifest:
        errors.append("manifest.json missing 'generated_at'")
    elif not isinstance(manifest["generated_at"], str):
        errors.append(
            f"manifest.json generated_at must be a string, "
            f"got {type(manifest['generated_at']).__name__}"
        )
    elif not manifest["generated_at"].endswith("Z"):
        errors.append(
            "manifest.json generated_at must be an "
            "ISO-8601 UTC timestamp ending with 'Z'"
        )

    if "minimum_cli_version" not in manifest:
        errors.append("manifest.json missing 'minimum_cli_version'")
    elif not isinstance(manifest["minimum_cli_version"], str):
        errors.append(
            f"manifest.json minimum_cli_version must be a string, "
            f"got {type(manifest['minimum_cli_version']).__name__}"
        )

    if manifest.get("skill_name") != BUNDLE_KIND:
        errors.append(
            f"manifest.json skill_name must be "
            f"'{BUNDLE_KIND}', got "
            f"'{manifest.get('skill_name')}'"
        )

    if "skill_md_sha256" not in manifest:
        errors.append("manifest.json missing 'skill_md_sha256'")


def _check_manifest_references(manifest: dict, errors: list[str]) -> None:
    """Check references entries in the manifest.

    Validates structure, completeness (exact count and paths), and
    sort order per the RELEASE_BUNDLE_LAYOUT.md contract.
    """
    refs = manifest.get("references")
    if not isinstance(refs, list):
        errors.append("manifest.json 'references' must be a list")
        return

    # Check exact count
    expected_count = len(REQUIRED_REFERENCES)
    if len(refs) != expected_count:
        errors.append(
            f"manifest.json references has {len(refs)} entries, "
            f"expected {expected_count}"
        )

    # Check exact paths and structure
    expected_paths = set(REQUIRED_REFERENCES)
    actual_paths = set()
    for i, ref in enumerate(refs):
        if not isinstance(ref, dict):
            errors.append(f"manifest.json references[{i}] is not a mapping")
            continue
        for key in ("path", "sha256", "size"):
            if key not in ref:
                errors.append(f"manifest.json references[{i}] missing '{key}'")
        path = ref.get("path", "")
        actual_paths.add(path)

    # Check for missing/extra paths
    missing = expected_paths - actual_paths
    if missing:
        for m in sorted(missing):
            errors.append(f"manifest.json references missing path: {m}")
    extra = actual_paths - expected_paths
    if extra:
        for e in sorted(extra):
            errors.append(f"manifest.json references has extra path: {e}")

    # Check sort order (paths must be sorted lexicographically)
    if len(refs) > 1:
        paths = [r.get("path", "") for r in refs if isinstance(r, dict)]
        if paths != sorted(paths):
            errors.append("manifest.json references must be sorted by path")


def _check_manifest_capability(manifest: dict, errors: list[str]) -> None:
    """Check capability_manifest in the manifest."""
    cap = manifest.get("capability_manifest")
    if not isinstance(cap, dict):
        errors.append("manifest.json 'capability_manifest' must be a mapping")
        return
    for key in ("path", "sha256"):
        if key not in cap:
            errors.append(f"manifest.json capability_manifest missing '{key}'")


def _check_manifest_safety(manifest: dict, errors: list[str]) -> None:
    """Check safety section in the manifest."""
    safety = manifest.get("safety")
    if not isinstance(safety, dict):
        errors.append("manifest.json 'safety' must be a mapping")
        return
    rc = safety.get("requires_confirmation")
    if not isinstance(rc, list):
        errors.append(
            "manifest.json safety.requires_confirmation must be a list"
        )


def _verify_manifest_schema(manifest: dict, errors: list[str]) -> None:
    """Verify manifest.json has the correct schema shape."""
    _check_manifest_top_level(manifest, errors)
    _check_manifest_references(manifest, errors)
    _check_manifest_capability(manifest, errors)
    _check_manifest_safety(manifest, errors)


def _verify_checksums(
    members: dict[str, bytes],
    manifest: dict,
    prefix: str,
    errors: list[str],
) -> None:
    """Verify sha256 checksums in manifest match actual files."""
    skill_key = f"{prefix}/SKILL.md"
    if skill_key in members:
        actual = _sha256_bytes(members[skill_key])
        expected = manifest.get("skill_md_sha256", "")
        if actual != expected:
            errors.append(
                f"SKILL.md sha256 mismatch: "
                f"manifest={expected}, actual={actual}"
            )

    for ref in manifest.get("references", []):
        path = ref.get("path", "")
        full = f"{prefix}/{path}"
        if full not in members:
            errors.append(f"Reference file not in tarball: {path}")
            continue
        actual_data = members[full]
        actual = _sha256_bytes(actual_data)
        if actual != ref.get("sha256", ""):
            errors.append(
                f"Reference sha256 mismatch for {path}: "
                f"manifest={ref.get('sha256')}, "
                f"actual={actual}"
            )
        # Validate size field (§4 schema contract)
        expected_size = ref.get("size")
        if expected_size is not None and len(actual_data) != expected_size:
            errors.append(
                f"Reference size mismatch for {path}: "
                f"manifest={expected_size}, "
                f"actual={len(actual_data)}"
            )

    cap = manifest.get("capability_manifest", {})
    cap_path = cap.get("path", "")
    full = f"{prefix}/{cap_path}"
    if full not in members:
        errors.append(f"Capability manifest not in tarball: {cap_path}")
    else:
        actual = _sha256_bytes(members[full])
        if actual != cap.get("sha256", ""):
            errors.append(
                f"Capability manifest sha256 mismatch: "
                f"manifest={cap.get('sha256')}, "
                f"actual={actual}"
            )


def verify_tarball(tarball_path: str) -> int:
    """Verify a release bundle tarball. Return 0 on success."""
    errors: list[str] = []
    path = Path(tarball_path)

    if not path.is_file():
        print(f"ERROR: Tarball not found: {path}")
        return 1

    try:
        with tarfile.open(str(path), "r:gz") as tar:
            member_names = {m.name for m in tar.getmembers()}
            file_contents: dict[str, bytes] = {}
            for member in tar.getmembers():
                if member.isfile():
                    f = tar.extractfile(member)
                    if f is not None:
                        file_contents[member.name] = f.read()
    except (tarfile.TarError, OSError) as exc:
        print(f"ERROR: Could not open tarball: {exc}")
        return 1

    # Extract version from top-level directory
    version = None
    for name in member_names:
        parts = name.split("/")
        if parts[0].startswith(BUNDLE_KIND + "-"):
            version = parts[0][len(BUNDLE_KIND) + 1 :]
            break

    if version is None:
        errors.append(
            "Cannot determine version from tarball "
            f"top-level directory. Expected "
            f"'{BUNDLE_KIND}-<version>/'"
        )
        for e in errors:
            print(f"FAIL {e}")
        return 1

    # Every member must live under the prefix directory — no
    # stray top-level entries allowed (RELEASE_BUNDLE_LAYOUT.md §3).
    prefix = f"{BUNDLE_KIND}-{version}"
    for entry in member_names:
        if entry == prefix:
            continue
        if not entry.startswith(prefix + "/"):
            errors.append(
                f"Member outside bundle directory: {entry} "
                f"(must be under '{prefix}/')"
            )

    # Verify layout
    _verify_layout(member_names, version, errors)

    _verify_no_forbidden(member_names, prefix, errors)
    _verify_no_extra_files(member_names, prefix, errors)

    # Read and verify manifest
    manifest_key = f"{prefix}/manifest.json"
    if manifest_key in file_contents:
        try:
            manifest = json.loads(file_contents[manifest_key])
        except json.JSONDecodeError as exc:
            errors.append(f"manifest.json is not valid JSON: {exc}")
            manifest = {}
        else:
            # Cross-check: tarball directory version must match
            # manifest version
            manifest_version = manifest.get("version", "")
            if manifest_version and manifest_version != version:
                errors.append(
                    f"Version mismatch: tarball directory "
                    f"says '{version}', manifest.json "
                    f"says '{manifest_version}'"
                )
            _verify_manifest_schema(manifest, errors)
            _verify_checksums(file_contents, manifest, prefix, errors)
    else:
        errors.append("manifest.json not found in tarball")

    if errors:
        for e in errors:
            print(f"FAIL {e}")
        print("\nFAILED: Bundle verification failed.")
        return 1

    print(f"PASSED: Bundle verification succeeded for {path.name}")
    return 0


def verify_directory(dir_path: str) -> int:
    """Verify an extracted bundle directory.

    The directory must be named
    ``logion-marketplace-companion-<version>/`` and its manifest
    version must match the directory name.
    """
    errors: list[str] = []
    root = Path(dir_path).resolve()

    if not root.is_dir():
        print(f"ERROR: Directory not found: {root}")
        return 1

    # Directory name must match the bundle kind pattern
    dir_name = root.name
    dir_version: str = ""
    if not dir_name.startswith(BUNDLE_KIND + "-"):
        errors.append(
            f"Directory name must start with "
            f"'{BUNDLE_KIND}-', got '{dir_name}'"
        )
    else:
        # Cross-check version in directory name vs manifest
        dir_version = dir_name[len(BUNDLE_KIND) + 1 :]

    # Check required dirs
    for d in REQUIRED_DIRS:
        if not (root / d).is_dir():
            errors.append(f"Missing directory: {d}/")

    # Check required files
    for f in ALL_REQUIRED_FILES:
        if not (root / f).is_file():
            errors.append(f"Missing file: {f}")

    # Check forbidden files
    for item in root.rglob("*"):
        rel = str(item.relative_to(root))
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in rel:
                errors.append(f"Forbidden pattern '{pattern}' found in: {rel}")

    # Check for unexpected files and directories
    _expected_files: set[str] = set(ALL_REQUIRED_FILES)
    _expected_files.add("manifest.json")
    _expected_dirs: set[str] = set(REQUIRED_DIRS)
    for item in root.rglob("*"):
        rel = str(item.relative_to(root))
        if item.is_file():
            if rel not in _expected_files:
                errors.append(f"Unexpected file in bundle: {rel}")
        elif item.is_dir() and rel not in _expected_dirs:
            errors.append(f"Unexpected directory in bundle: {rel}")

    # Verify manifest
    manifest_path = root / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"manifest.json invalid JSON: {exc}")
            manifest = {}
        else:
            _verify_manifest_schema(manifest, errors)

            # Cross-check: directory version must match manifest version
            manifest_version = manifest.get("version", "")
            if (
                manifest_version
                and dir_version
                and manifest_version != dir_version
            ):
                errors.append(
                    f"Version mismatch: directory name "
                    f"says '{dir_version}', manifest.json "
                    f"says '{manifest_version}'"
                )

            if "skill_md_sha256" in manifest:
                skill_bytes = (root / "SKILL.md").read_bytes()
                actual = _sha256_bytes(skill_bytes)
                if actual != manifest["skill_md_sha256"]:
                    errors.append(
                        f"SKILL.md sha256 mismatch: "
                        f"manifest="
                        f"{manifest['skill_md_sha256']}, "
                        f"actual={actual}"
                    )

            for ref in manifest.get("references", []):
                rpath = ref.get("path", "")
                fpath = root / rpath
                if fpath.is_file():
                    actual = _sha256_bytes(fpath.read_bytes())
                    if actual != ref.get("sha256", ""):
                        errors.append(f"Reference sha256 mismatch for {rpath}")

            cap = manifest.get("capability_manifest", {})
            cap_path = root / cap.get("path", "")
            if cap_path.is_file():
                actual = _sha256_bytes(cap_path.read_bytes())
                if actual != cap.get("sha256", ""):
                    errors.append("Capability manifest sha256 mismatch")
    else:
        errors.append("manifest.json not found")

    if errors:
        for e in errors:
            print(f"FAIL {e}")
        print("\nFAILED: Bundle verification failed.")
        return 1

    print(f"PASSED: Bundle verification succeeded for {root}")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/verify_bundle.py "
            "<tarball_path|directory_path>"
        )
        return 1

    target = sys.argv[1]
    path = Path(target)

    if path.is_file() and target.endswith(".tar.gz"):
        return verify_tarball(target)
    if path.is_dir():
        return verify_directory(target)
    print(f"ERROR: Path is not a .tar.gz file or directory: {target}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
