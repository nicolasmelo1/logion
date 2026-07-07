"""Comprehensive tests for the package-map parser and validator."""

from __future__ import annotations

import pytest

from logion_skillmap.models import (
    CapabilityEntry,
    EvalsBlock,
    PackageMap,
    RuntimeBlock,
    SourceBlock,
)
from logion_skillmap.parser import (
    check_unknown_keys_raw,
    parse_package_map,
    validate_package_map,
)

# Fixtures

VALID_MINIMAL_YAML = """\
version: 1
slug: my-pkg
capabilities:
  - name: core
    entrypoint: src/main.py
"""

VALID_FULL_YAML = """\
version: 1
slug: my-pkg
capabilities:
  - name: core
    entrypoint: src/main.py
    description: Core capability
    dependencies: []
  - name: extra
    entrypoint: src/extra.py
    description: Extra capability
    dependencies:
      - core
source:
  include:
    - "src/**"
  exclude:
    - "src/test/**"
runtime:
  include:
    - "src/**"
  entrypoint: src/main.py
evals:
  include:
    - "tests/**"
  exclude:
    - "tests/fixtures/**"
  commands:
    lint: "ruff check ."
    test: "pytest"
"""


# Parse tests


class TestParsePackageMap:
    def test_parse_minimal(self):
        pm = parse_package_map(VALID_MINIMAL_YAML)
        assert pm.version == 1
        assert pm.slug == "my-pkg"
        assert len(pm.capabilities) == 1
        assert pm.capabilities[0].name == "core"
        assert pm.capabilities[0].entrypoint == "src/main.py"

    def test_parse_full(self):
        pm = parse_package_map(VALID_FULL_YAML)
        assert pm.version == 1
        assert pm.slug == "my-pkg"
        assert len(pm.capabilities) == 2
        assert pm.source is not None
        assert pm.runtime is not None
        assert pm.evals is not None

    def test_parse_empty_string(self):
        pm = parse_package_map("")
        assert pm.version == 1
        assert pm.capabilities == ()

    def test_parse_non_dict_raises(self):
        with pytest.raises((ValueError, TypeError), match="mapping"):
            parse_package_map("42")

    def test_parse_preserves_evals_commands(self):
        pm = parse_package_map(VALID_FULL_YAML)
        assert pm.evals is not None
        assert ("lint", "ruff check .") in pm.evals.commands
        assert ("test", "pytest") in pm.evals.commands


# Validation: unknown keys


class TestUnknownKeys:
    def test_unknown_top_level_key(self):
        import yaml

        data = yaml.safe_load(
            "version: 1\nslug: x\ncapabilities:\n"
            "  - name: c\n    entrypoint: a.py\n"
            "bogus_key: true\n"
        )
        warnings = check_unknown_keys_raw(data)
        codes = [w.code for w in warnings]
        assert "package_map_unknown_keys" in codes

    def test_known_keys_no_warning(self):
        import yaml

        data = yaml.safe_load(VALID_FULL_YAML)
        warnings = check_unknown_keys_raw(data)
        codes = [w.code for w in warnings]
        assert "package_map_unknown_keys" not in codes


class TestUnsupportedVersion:
    def test_version_2_warns(self):
        yaml_text = (
            "version: 2\nslug: x\ncapabilities:\n"
            "  - name: c\n    entrypoint: a.py\n"
        )
        pm = parse_package_map(yaml_text)
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_unsupported_version" in codes

    def test_version_1_ok(self):
        pm = parse_package_map(VALID_MINIMAL_YAML)
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_unsupported_version" not in codes


# Validation: empty capabilities


class TestEmptyCapabilities:
    def test_empty_capabilities_warns(self):
        yaml_text = "version: 1\nslug: x\ncapabilities: []\n"
        pm = parse_package_map(yaml_text)
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_empty_capabilities" in codes

    def test_non_empty_capabilities_ok(self):
        pm = parse_package_map(VALID_MINIMAL_YAML)
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_empty_capabilities" not in codes


# Validation: entrypoint traversal


class TestEntrypointTraversal:
    def test_absolute_entrypoint_warns(self):
        pm = PackageMap(
            capabilities=(
                CapabilityEntry(name="c", entrypoint="/abs/path.py"),
            )
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_entrypoint_traversal" in codes

    def test_dotdot_entrypoint_warns(self):
        pm = PackageMap(
            capabilities=(
                CapabilityEntry(name="c", entrypoint="../escape.py"),
            )
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_entrypoint_traversal" in codes

    def test_relative_entrypoint_ok(self):
        pm = PackageMap(
            capabilities=(CapabilityEntry(name="c", entrypoint="src/main.py"),)
        )
        warnings = validate_package_map(pm)
        traversal = [
            w for w in warnings if w.code == "package_map_entrypoint_traversal"
        ]
        assert len(traversal) == 0

    def test_runtime_absolute_entrypoint_warns(self):
        pm = PackageMap(
            capabilities=(CapabilityEntry(name="c", entrypoint="a.py"),),
            runtime=RuntimeBlock(
                include=("src/**",), entrypoint="/abs/main.py"
            ),
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_entrypoint_traversal" in codes

    def test_capabilities_manifest_traversal(self):
        pm = PackageMap(
            capabilities=(
                CapabilityEntry(
                    name="c",
                    entrypoint="a.py",
                    capabilities_manifest="../bad.yaml",
                ),
            )
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_entrypoint_traversal" in codes


# Validation: entrypoint not matched


class TestEntrypointNotMatched:
    def test_unmatched_entrypoint_warns(self):
        pm = PackageMap(
            capabilities=(
                CapabilityEntry(name="c", entrypoint="src/main.py"),
            ),
            source=SourceBlock(include=("doc/**",)),
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_entrypoint_not_matched" in codes

    def test_matched_entrypoint_ok(self):
        pm = PackageMap(
            capabilities=(
                CapabilityEntry(name="c", entrypoint="src/main.py"),
            ),
            source=SourceBlock(include=("src/**",)),
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_entrypoint_not_matched" not in codes


# Validation: dependency unknown


class TestDependencyUnknown:
    def test_unknown_dependency_warns(self):
        pm = PackageMap(
            capabilities=(
                CapabilityEntry(
                    name="c",
                    entrypoint="a.py",
                    dependencies=("nonexistent",),
                ),
            )
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_dependency_unknown" in codes

    def test_known_dependency_ok(self):
        pm = PackageMap(
            capabilities=(
                CapabilityEntry(name="core", entrypoint="a.py"),
                CapabilityEntry(
                    name="extra",
                    entrypoint="b.py",
                    dependencies=("core",),
                ),
            )
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_dependency_unknown" not in codes


# Validation: dependency cycle


class TestDependencyCycle:
    def test_cycle_warns(self):
        pm = PackageMap(
            capabilities=(
                CapabilityEntry(
                    name="a", entrypoint="a.py", dependencies=("b",)
                ),
                CapabilityEntry(
                    name="b", entrypoint="b.py", dependencies=("a",)
                ),
            )
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_dependency_cycle" in codes

    def test_no_cycle_ok(self):
        pm = PackageMap(
            capabilities=(
                CapabilityEntry(name="core", entrypoint="a.py"),
                CapabilityEntry(
                    name="extra",
                    entrypoint="b.py",
                    dependencies=("core",),
                ),
            )
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_dependency_cycle" not in codes


# Validation: glob invalid


class TestGlobInvalid:
    def test_invalid_glob_warns(self):
        pm = PackageMap(
            capabilities=(CapabilityEntry(name="c", entrypoint="a.py"),),
            source=SourceBlock(
                include=("src/[bad",),  # unbalanced bracket
            ),
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_glob_invalid" in codes

    def test_valid_glob_ok(self):
        pm = PackageMap(
            capabilities=(CapabilityEntry(name="c", entrypoint="a.py"),),
            source=SourceBlock(include=("src/**", "*.py")),
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_glob_invalid" not in codes


# Validation: commands not executed


class TestCommandsNotExecuted:
    def test_commands_flagged(self):
        pm = PackageMap(
            capabilities=(CapabilityEntry(name="c", entrypoint="a.py"),),
            evals=EvalsBlock(commands=(("test", "pytest"),)),
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_commands_not_executed" in codes

    def test_no_commands_no_flag(self):
        pm = PackageMap(
            capabilities=(CapabilityEntry(name="c", entrypoint="a.py"),),
            evals=EvalsBlock(),
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_commands_not_executed" not in codes


# Combined validation


class TestValidatePackageMap:
    def test_valid_map_no_warnings(self):
        pm = PackageMap(
            capabilities=(
                CapabilityEntry(name="core", entrypoint="src/main.py"),
            ),
            source=SourceBlock(include=("src/**",)),
        )
        warnings = validate_package_map(pm)
        assert len(warnings) == 0

    def test_multiple_warnings(self):
        pm = PackageMap(
            version=2,
            capabilities=(),
        )
        warnings = validate_package_map(pm)
        codes = [w.code for w in warnings]
        assert "package_map_unsupported_version" in codes
        assert "package_map_empty_capabilities" in codes
