# SPDX-License-Identifier: MIT
"""Tests for the release bundle build functionality.

Verifies that package_skill.py build produces a deterministic tarball
with the correct layout, manifest, and content hashes.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
import time
from pathlib import Path

COMPANION_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = COMPANION_ROOT.parent.parent
SCRIPT = COMPANION_ROOT / "scripts" / "package_skill.py"
CLI_VERSION_FILE = REPO_ROOT / "packages" / "cli" / "cli" / "_version.py"

BUNDLE_KIND = "logion-marketplace-companion"
VERSION = "0.1.0"

EXPECTED_TOP_LEVEL_DIRS = {
    f"{BUNDLE_KIND}-{VERSION}/course",
    f"{BUNDLE_KIND}-{VERSION}/references",
}

EXPECTED_TOP_LEVEL_FILES = {
    f"{BUNDLE_KIND}-{VERSION}/SKILL.md",
    f"{BUNDLE_KIND}-{VERSION}/LICENSE",
    f"{BUNDLE_KIND}-{VERSION}/README.md",
    f"{BUNDLE_KIND}-{VERSION}/manifest.json",
    f"{BUNDLE_KIND}-{VERSION}/course/capabilities.yaml",
}

EXPECTED_REFERENCES = {
    f"{BUNDLE_KIND}-{VERSION}/references/account-and-identity.md",
    f"{BUNDLE_KIND}-{VERSION}/references/admin-operations.md",
    f"{BUNDLE_KIND}-{VERSION}/references/bounties.md",
    f"{BUNDLE_KIND}-{VERSION}/references/course-review-queue.md",
    f"{BUNDLE_KIND}-{VERSION}/references/creator-course-management.md",
    f"{BUNDLE_KIND}-{VERSION}/references/notifications-and-reports.md",
    f"{BUNDLE_KIND}-{VERSION}/references/payments-and-checkout.md",
    f"{BUNDLE_KIND}-{VERSION}/references/troubleshooting.md",
}

FORBIDDEN_PATTERNS = [
    "evals/",
    "tests/",
    "scripts/",
    "__pycache__",
    ".pyc",
    "pyproject.toml",
    "node_modules/",
]


def _run_build(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run package_skill.py build and return the result."""
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "build",
            "--out",
            str(tmp_path),
            "--version",
            VERSION,
            "--release",
        ],
        capture_output=True,
        text=True,
        cwd=str(COMPANION_ROOT),
    )


def _tarball_path(tmp_path: Path) -> Path:
    """Return the expected tarball path."""
    return tmp_path / f"{BUNDLE_KIND}-{VERSION}.tar.gz"


def _extract_members(tarball: Path) -> set[str]:
    """Return the set of all member names in the tarball."""
    with tarfile.open(str(tarball), "r:gz") as tar:
        return {m.name for m in tar.getmembers()}


def _extract_manifest(tarball: Path) -> dict:
    """Extract and parse manifest.json from the tarball."""
    prefix = f"{BUNDLE_KIND}-{VERSION}"
    with tarfile.open(str(tarball), "r:gz") as tar:
        f = tar.extractfile(f"{prefix}/manifest.json")
        assert f is not None
        return json.loads(f.read())


class TestReleaseBundleDeterministic:
    """Two consecutive builds produce identical content.

    The manifest's ``generated_at`` timestamp changes between
    builds, so byte-level equality of the whole tarball is not
    expected.  Instead we verify that every file in the tarball
    is byte-identical except ``manifest.json``, and that
    ``manifest.json`` differs only in the ``generated_at`` field.
    """

    def test_release_bundle_deterministic(self, tmp_path: Path) -> None:
        out1 = tmp_path / "build1"
        out2 = tmp_path / "build2"
        out1.mkdir()
        out2.mkdir()

        result1 = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "build",
                "--out",
                str(out1),
                "--version",
                VERSION,
                "--release",
            ],
            capture_output=True,
            text=True,
            cwd=str(COMPANION_ROOT),
        )
        assert result1.returncode == 0, (
            f"First build failed:\n"
            f"stdout: {result1.stdout}\n"
            f"stderr: {result1.stderr}"
        )

        time.sleep(1)

        result2 = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "build",
                "--out",
                str(out2),
                "--version",
                VERSION,
                "--release",
            ],
            capture_output=True,
            text=True,
            cwd=str(COMPANION_ROOT),
        )
        assert result2.returncode == 0, (
            f"Second build failed:\n"
            f"stdout: {result2.stdout}\n"
            f"stderr: {result2.stderr}"
        )

        prefix = f"{BUNDLE_KIND}-{VERSION}"
        tb1 = _tarball_path(out1)
        tb2 = _tarball_path(out2)

        with (
            tarfile.open(str(tb1), "r:gz") as t1,
            tarfile.open(str(tb2), "r:gz") as t2,
        ):
            members1 = {m.name: m for m in t1.getmembers() if m.isfile()}
            members2 = {m.name: m for m in t2.getmembers() if m.isfile()}

            # Same set of files
            assert set(members1.keys()) == set(members2.keys())

            for name in members1:
                f1 = t1.extractfile(members1[name])
                f2 = t2.extractfile(members2[name])
                assert f1 is not None
                assert f2 is not None
                data1 = f1.read()
                data2 = f2.read()

                if name == f"{prefix}/manifest.json":
                    # Manifest may differ only
                    # in generated_at timestamp
                    m1 = json.loads(data1)
                    m2 = json.loads(data2)
                    gen1 = m1.pop("generated_at")
                    m2.pop("generated_at")
                    assert m1 == m2, (
                        f"Manifest content differs "
                        f"beyond generated_at:\n"
                        f"build1={m1}\nbuild2={m2}"
                    )
                    # Timestamps should be close
                    # but are not expected to be equal
                    assert isinstance(gen1, str), (
                        f"generated_at must be str, "
                        f"got {type(gen1).__name__}"
                    )
                else:
                    sha1 = hashlib.sha256(data1).hexdigest()
                    sha2 = hashlib.sha256(data2).hexdigest()
                    assert data1 == data2, (
                        f"File {name} differs between "
                        f"builds: sha1={sha1}, sha2={sha2}"
                    )

            # Verify same member set has
            # identical sha256 for content files
            # (excluding manifest.json)
            content_sha1 = {
                name: hashlib.sha256(t1.extractfile(m).read()).hexdigest()
                for name, m in members1.items()
                if name != f"{prefix}/manifest.json"
            }
            content_sha2 = {
                name: hashlib.sha256(t2.extractfile(m).read()).hexdigest()
                for name, m in members2.items()
                if name != f"{prefix}/manifest.json"
            }
            assert content_sha1 == content_sha2


class TestReleaseBundleCanonicalLayout:
    """Tarball top-level matches the layout exactly; no extra files."""

    def test_release_bundle_contains_canonical_layout(
        self, tmp_path: Path
    ) -> None:
        result = _run_build(tmp_path)
        assert result.returncode == 0, (
            f"Build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        tarball = _tarball_path(tmp_path)
        members = _extract_members(tarball)

        # All expected files must be present
        expected_files = EXPECTED_TOP_LEVEL_FILES | EXPECTED_REFERENCES
        for f in expected_files:
            assert f in members, f"Missing expected file: {f}"

        # The top-level directory must exist
        top_dir = f"{BUNDLE_KIND}-{VERSION}"
        assert top_dir in members, f"Missing top-level directory: {top_dir}"

        # Expected subdirectories must be present
        for d in EXPECTED_TOP_LEVEL_DIRS:
            # tarfile may or may not include trailing /
            dir_entry = d in members or f"{d}/" in members
            assert dir_entry, f"Missing expected directory: {d}"

    def test_release_bundle_no_extra_top_level_entries(
        self, tmp_path: Path
    ) -> None:
        """No unexpected top-level entries in the tarball."""
        result = _run_build(tmp_path)
        assert result.returncode == 0

        tarball = _tarball_path(tmp_path)
        members = _extract_members(tarball)
        top_dir = f"{BUNDLE_KIND}-{VERSION}"

        # Collect all entries beyond the expected set
        expected = (
            EXPECTED_TOP_LEVEL_FILES
            | EXPECTED_REFERENCES
            | EXPECTED_TOP_LEVEL_DIRS
            | {top_dir}
        )
        # Also accept directory entries with trailing slash
        expected_with_slash = {f"{e}/" for e in expected}
        all_expected = expected | expected_with_slash

        extra = members - all_expected
        # Filter out directory entries that are just parent
        # dirs of expected files (e.g., course/ or references/)
        # which are legitimate
        non_dir_extras = {m for m in extra if not m.endswith("/")}
        # Allow directory entries for course and references
        # subdirs since tarfile may create them
        allowed_dirs = {
            f"{top_dir}/course",
            f"{top_dir}/references",
            f"{top_dir}/course/",
            f"{top_dir}/references/",
        }
        non_dir_extras -= allowed_dirs

        assert not non_dir_extras, (
            f"Unexpected files in tarball: {non_dir_extras}"
        )


class TestReleaseBundleExcludes:
    """Tarball does not contain evals/, tests/, scripts/."""

    def test_release_bundle_excludes_evals_and_tests(
        self, tmp_path: Path
    ) -> None:
        result = _run_build(tmp_path)
        assert result.returncode == 0

        tarball = _tarball_path(tmp_path)
        members = _extract_members(tarball)

        for pattern in FORBIDDEN_PATTERNS:
            for member in members:
                assert pattern not in member, (
                    f"Forbidden pattern '{pattern}' found "
                    f"in tarball member: {member}"
                )


class TestReleaseBundleManifestSchema:
    """manifest.json matches the §4 schema."""

    def test_release_bundle_internal_manifest_validates(
        self, tmp_path: Path
    ) -> None:
        result = _run_build(tmp_path)
        assert result.returncode == 0

        tarball = _tarball_path(tmp_path)
        manifest = _extract_manifest(tarball)

        # schema_version must be 1 (int)
        assert "schema_version" in manifest
        assert manifest["schema_version"] == 1
        assert isinstance(manifest["schema_version"], int)

        # bundle_kind must match
        assert manifest["bundle_kind"] == BUNDLE_KIND

        # version must be present
        assert "version" in manifest
        assert isinstance(manifest["version"], str)

        # generated_at must be present and ISO-8601
        assert "generated_at" in manifest
        assert isinstance(manifest["generated_at"], str)
        assert manifest["generated_at"].endswith("Z")

        # git_commit must be present
        assert "git_commit" in manifest
        assert isinstance(manifest["git_commit"], str)

        # minimum_cli_version must be present
        assert "minimum_cli_version" in manifest
        assert isinstance(manifest["minimum_cli_version"], str)

        # skill_name must match
        assert manifest["skill_name"] == BUNDLE_KIND

        # skill_md_sha256 must be present
        assert "skill_md_sha256" in manifest
        assert isinstance(manifest["skill_md_sha256"], str)

        # references must be a list with correct structure
        refs = manifest["references"]
        assert isinstance(refs, list)
        assert len(refs) == 8, f"Expected 8 references, got {len(refs)}"
        for ref in refs:
            assert "path" in ref, f"Reference missing 'path': {ref}"
            assert "sha256" in ref, f"Reference missing 'sha256': {ref}"
            assert "size" in ref, f"Reference missing 'size': {ref}"
            assert isinstance(ref["path"], str)
            assert isinstance(ref["sha256"], str)
            assert isinstance(ref["size"], int)

        # capability_manifest must have path and sha256
        cap = manifest["capability_manifest"]
        assert isinstance(cap, dict)
        assert "path" in cap
        assert "sha256" in cap

        # safety.requires_confirmation must be a list
        safety = manifest["safety"]
        assert isinstance(safety, dict)
        assert "requires_confirmation" in safety
        assert isinstance(safety["requires_confirmation"], list)


class TestReleaseBundleManifestHashes:
    """Every references[*].sha256 matches the file in the tarball."""

    def test_release_bundle_internal_manifest_hashes_match(
        self, tmp_path: Path
    ) -> None:
        result = _run_build(tmp_path)
        assert result.returncode == 0

        tarball = _tarball_path(tmp_path)
        manifest = _extract_manifest(tarball)
        prefix = f"{BUNDLE_KIND}-{VERSION}"

        with tarfile.open(str(tarball), "r:gz") as tar:
            # Verify SKILL.md sha256
            skill_key = f"{prefix}/SKILL.md"
            f = tar.extractfile(skill_key)
            assert f is not None
            skill_data = f.read()
            actual_skill_sha = hashlib.sha256(skill_data).hexdigest()
            assert actual_skill_sha == manifest["skill_md_sha256"], (
                f"SKILL.md sha256 mismatch: "
                f"actual={actual_skill_sha}, "
                f"manifest={manifest['skill_md_sha256']}"
            )

            # Verify each reference sha256
            for ref in manifest["references"]:
                ref_path = ref["path"]
                full_key = f"{prefix}/{ref_path}"
                f = tar.extractfile(full_key)
                assert f is not None, (
                    f"Reference file not in tarball: {ref_path}"
                )
                data = f.read()
                actual_sha = hashlib.sha256(data).hexdigest()
                assert actual_sha == ref["sha256"], (
                    f"Reference {ref_path} sha256 mismatch: "
                    f"actual={actual_sha}, "
                    f"manifest={ref['sha256']}"
                )

            # Verify capability manifest sha256
            cap = manifest["capability_manifest"]
            cap_key = f"{prefix}/{cap['path']}"
            f = tar.extractfile(cap_key)
            assert f is not None
            cap_data = f.read()
            actual_cap_sha = hashlib.sha256(cap_data).hexdigest()
            assert actual_cap_sha == cap["sha256"], (
                f"Capability manifest sha256 mismatch: "
                f"actual={actual_cap_sha}, "
                f"manifest={cap['sha256']}"
            )


class TestReleaseBundleMinimumCliVersion:
    """minimum_cli_version is set and pin-compatible."""

    def test_release_bundle_minimum_cli_version_present(
        self, tmp_path: Path
    ) -> None:
        result = _run_build(tmp_path)
        assert result.returncode == 0

        tarball = _tarball_path(tmp_path)
        manifest = _extract_manifest(tarball)

        min_cli = manifest["minimum_cli_version"]
        assert isinstance(min_cli, str)
        assert len(min_cli) > 0, "minimum_cli_version is empty"

        # Parse version components for pin-compatibility check
        # The CLI version from the workspace
        cli_version = _read_cli_version()
        cli_parts = [int(p) for p in cli_version.split(".")]
        min_parts = [int(p) for p in min_cli.split(".")]

        # minimum_cli_version should be pin-compatible:
        # at minimum the major.minor should match
        assert cli_parts[0] == min_parts[0], (
            f"minimum_cli_version major mismatch: "
            f"cli={cli_version}, min_cli={min_cli}"
        )
        assert cli_parts[1] == min_parts[1], (
            f"minimum_cli_version minor mismatch: "
            f"cli={cli_version}, min_cli={min_cli}"
        )


def _read_cli_version() -> str:
    """Read CLI version from pyproject.toml (canonical source)."""
    import tomllib

    pyproject = REPO_ROOT / "packages" / "cli" / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]
