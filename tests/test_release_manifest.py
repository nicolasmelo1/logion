# SPDX-License-Identifier: MIT
"""Tests for the release manifest build/check tooling."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "scripts" / "release_manifest_schema.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "release_manifest.py"
STABLE_MANIFEST = REPO_ROOT / "releases" / "manifest-stable.json"

_HEX = frozenset("0123456789abcdef")


def _run(
    args: list[str],
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess via uv run."""
    return subprocess.run(
        ["uv", "run", "python", str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        **kwargs,  # type: ignore[arg-type]
    )


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Schema validation (manual - no jsonschema dependency required)
# ---------------------------------------------------------------------------


def _check_toplevel(
    manifest: dict,
    schema_props: dict,
    errors: list[str],
) -> None:
    """Validate top-level const/enum/pattern fields."""
    sv_prop = schema_props.get("schema_version", {})
    if (
        "const" in sv_prop
        and manifest.get("schema_version") != sv_prop["const"]
    ):
        errors.append(
            f"schema_version: expected {sv_prop['const']}, "
            f"got {manifest.get('schema_version')}"
        )

    ch_prop = schema_props.get("channel", {})
    if "enum" in ch_prop and manifest.get("channel") not in ch_prop["enum"]:
        errors.append(
            f"channel: expected one of "
            f"{ch_prop['enum']}, "
            f"got {manifest.get('channel')}"
        )

    gc_prop = schema_props.get("git_commit", {})
    if "pattern" in gc_prop and not re.match(
        gc_prop["pattern"],
        manifest.get("git_commit", ""),
    ):
        errors.append("git_commit does not match pattern")


def _check_packages(
    manifest: dict,
    schema_props: dict,
    errors: list[str],
) -> None:
    """Validate package entries against pattern properties."""
    packages = manifest.get("packages", {})
    pkg_pattern_props = schema_props.get(
        "packages",
        {},
    ).get("patternProperties", {})
    pkg_schema = pkg_pattern_props.get("^logion-", {})
    for pkg_name, pkg_entry in packages.items():
        pattern_key = (
            next(iter(pkg_pattern_props.keys())) if pkg_pattern_props else ""
        )
        if pattern_key and not re.match(pattern_key, pkg_name):
            errors.append(f"Package key {pkg_name} does not match pattern")

        for req in pkg_schema.get("required", []):
            if req not in pkg_entry:
                errors.append(f"{pkg_name}: missing required field {req}")

        allowed = set(pkg_schema.get("properties", {}).keys())
        for key in pkg_entry:
            if key not in allowed:
                errors.append(f"{pkg_name}: unexpected field {key}")


def _validate_manifest_against_schema(
    manifest: dict,
    schema: dict,
) -> list[str]:
    """Validate manifest fields against schema.

    Returns a list of error strings.
    """
    errors: list[str] = []

    for key in schema.get("required", []):
        if key not in manifest:
            errors.append(f"Missing required key: {key}")

    if not errors:
        schema_props = schema.get("properties", {})
        _check_toplevel(manifest, schema_props, errors)
        _check_packages(manifest, schema_props, errors)

    return errors


def test_manifest_validates_against_schema() -> None:
    """Load manifest and validate required fields."""
    manifest = _load_json(STABLE_MANIFEST)
    schema = _load_json(SCHEMA_PATH)
    errors = _validate_manifest_against_schema(manifest, schema)
    assert errors == [], "Schema validation errors:\n" + "\n".join(errors)


def test_manifest_build_deterministic() -> None:
    """Running build twice produces structurally identical output.

    Volatile fields (generated_at, git_commit) differ between runs,
    so we strip them and compare the remaining content.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(
        suffix=".json",
        delete=False,
    ) as f1:
        path1 = f1.name
    with tempfile.NamedTemporaryFile(
        suffix=".json",
        delete=False,
    ) as f2:
        path2 = f2.name

    volatile = ("generated_at", "git_commit")
    try:
        r1 = _run(["build", "--channel", "stable", "--out", path1])
        r2 = _run(["build", "--channel", "stable", "--out", path2])
        assert r1.returncode == 0, f"Build 1 failed: {r1.stderr}"
        assert r2.returncode == 0, f"Build 2 failed: {r2.stderr}"

        m1 = json.loads(Path(path1).read_text(encoding="utf-8"))
        m2 = json.loads(Path(path2).read_text(encoding="utf-8"))
        stable1 = {k: v for k, v in m1.items() if k not in volatile}
        stable2 = {k: v for k, v in m2.items() if k not in volatile}
        assert stable1 == stable2, "Manifests differ outside volatile fields"
    finally:
        os.unlink(path1)
        os.unlink(path2)


def test_manifest_check_passes_on_committed_manifest() -> None:
    """Running check on the committed manifest should exit 0."""
    result = _run(["check", "--in", str(STABLE_MANIFEST)])
    assert result.returncode == 0, (
        f"check failed (exit {result.returncode}): {result.stderr}"
    )
    # Also verify the manifest validates against the schema.
    manifest = _load_json(STABLE_MANIFEST)
    schema = _load_json(SCHEMA_PATH)
    errors = _validate_manifest_against_schema(manifest, schema)
    assert errors == [], "Manifest should validate against schema"


def test_manifest_check_fails_on_version_drift() -> None:
    """If a pyproject version is mutated, check detects drift."""
    import tempfile
    import tomllib

    cli_pyproject = REPO_ROOT / "packages" / "cli" / "pyproject.toml"
    original = cli_pyproject.read_bytes()

    try:
        data = tomllib.loads(original.decode("utf-8"))
        original_version = data["project"]["version"]
        cli_pyproject.write_text(
            cli_pyproject.read_text("utf-8").replace(
                original_version,
                "99.99.99",
            ),
            encoding="utf-8",
        )

        with tempfile.NamedTemporaryFile(
            suffix=".json",
            delete=False,
        ) as f:
            tmp_path = f.name

        try:
            # Build a manifest from the drifted state
            build_result = _run([
                "build",
                "--channel",
                "stable",
                "--out",
                tmp_path,
            ])
            assert build_result.returncode == 0, (
                f"build failed: {build_result.stderr}"
            )
            rebuilt = json.loads(
                Path(tmp_path).read_text(encoding="utf-8"),
            )
            assert (
                rebuilt["packages"]["logion-cli"]["version"] == "99.99.99"
            ), "Build should pick up mutated version"

            # Check against the committed (un-drifted) manifest
            # — this should fail because versions differ.
            check_result = _run([
                "check",
                "--in",
                str(STABLE_MANIFEST),
            ])
            assert check_result.returncode != 0, (
                "check should fail on version drift"
            )
        finally:
            os.unlink(tmp_path)
    finally:
        cli_pyproject.write_bytes(original)


def test_manifest_includes_minimum_python() -> None:
    """Every package entry must have minimum_python."""
    manifest = _load_json(STABLE_MANIFEST)
    for pkg_name, entry in manifest["packages"].items():
        assert "minimum_python" in entry, f"{pkg_name} missing minimum_python"


def test_manifest_cli_depends_on_minimum_client() -> None:
    """CLI's minimum_client should match client's major.minor."""
    manifest = _load_json(STABLE_MANIFEST)
    cli_entry = manifest["packages"].get("logion-cli")
    client_entry = manifest["packages"].get("logion-client")

    assert cli_entry is not None, "logion-cli entry missing"
    assert client_entry is not None, "logion-client entry missing"
    assert "minimum_client" in cli_entry, "logion-cli missing minimum_client"

    client_version = client_entry["version"]
    client_major_minor = ".".join(client_version.split(".")[:2])
    min_client = cli_entry["minimum_client"]
    min_client_major_minor = ".".join(min_client.split(".")[:2])

    assert min_client_major_minor == client_major_minor, (
        f"CLI minimum_client ({min_client}) doesn't "
        f"match client major.minor ({client_major_minor})"
    )


def test_manifest_sha256_lowercase_hex() -> None:
    """Every sha256 (if present) must be 64 lowercase hex chars."""
    manifest = _load_json(STABLE_MANIFEST)
    for pkg_name, entry in manifest["packages"].items():
        for field in ("wheel", "sdist", "bundle", "skill_md"):
            obj = entry.get(field)
            if obj is None:
                continue
            sha = obj.get("sha256", "")
            assert len(sha) == 64, f"{pkg_name}.{field}.sha256 length != 64"
            assert all(c in _HEX for c in sha), (
                f"{pkg_name}.{field}.sha256 has non-hex-lowercase"
            )


def test_manifest_schema_version_is_pinned() -> None:
    """The SCHEMA_VERSION constant must match manifest."""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"^SCHEMA_VERSION\s*=\s*(\d+)",
        source,
        re.MULTILINE,
    )
    assert match is not None, "SCHEMA_VERSION not found in script"

    script_version = int(match.group(1))
    manifest = _load_json(STABLE_MANIFEST)
    manifest_version = manifest["schema_version"]

    assert script_version == manifest_version, (
        f"Script SCHEMA_VERSION ({script_version}) != "
        f"manifest schema_version ({manifest_version})"
    )
