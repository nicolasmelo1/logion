"""Comprehensive tests for the package-map parser and validator."""

from __future__ import annotations

import pytest
import yaml

from logion_skillmap.models import (
    CapabilityEntry,
    Components,
    Dependency,
    EvalsBlock,
    Package,
    PackageMap,
    RuntimeBlock,
    SourceBlock,
)
from logion_skillmap.parser import (
    check_unknown_keys_raw,
    parse_package_map,
    validate_package_map,
)


def _pm(
    *,
    version: int = 1,
    slug: str = "",
    capabilities: tuple[CapabilityEntry, ...] = (),
    runtime: RuntimeBlock | None = None,
    source: SourceBlock | None = None,
    evals: EvalsBlock | None = None,
) -> PackageMap:
    """Construct a nested PackageMap tersely for tests."""
    return PackageMap(
        version=version,
        package=Package(slug=slug),
        components=Components(
            capabilities=capabilities,
            runtime=runtime,
            source=source,
            evals=evals,
        ),
    )


# Fixtures (canonical nested schema)

VALID_MINIMAL_YAML = """\
version: 1
package:
  slug: my-pkg
components:
  capabilities:
    core:
      entrypoint: src/main.py
"""

VALID_FULL_YAML = """\
version: 1
package:
  slug: my-pkg
components:
  capabilities:
    core:
      entrypoint: src/main.py
      description: Core capability
      dependencies: []
    extra:
      entrypoint: src/extra.py
      description: Extra capability
      dependencies:
        - capability: core
          reason: "builds on core"
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

    def test_parse_dependencies_are_objects(self):
        pm = parse_package_map(VALID_FULL_YAML)
        extra = next(c for c in pm.capabilities if c.name == "extra")
        assert extra.dependencies == (
            Dependency(capability="core", reason="builds on core"),
        )

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

    def test_capabilities_list_form_tolerated(self):
        pm = parse_package_map(
            "version: 1\n"
            "components:\n"
            "  capabilities:\n"
            "    - name: core\n"
            "      entrypoint: a.py\n"
        )
        assert pm.capabilities[0].name == "core"


# Validation: unknown keys


class TestUnknownKeys:
    def test_unknown_top_level_key(self):
        data = yaml.safe_load(VALID_MINIMAL_YAML + "bogus_key: true\n")
        codes = [w.code for w in check_unknown_keys_raw(data)]
        assert "package_map_unknown_keys" in codes

    def test_unknown_nested_component_key(self):
        data = yaml.safe_load(
            "version: 1\ncomponents:\n  capabilities: {}\n  bogus: 1\n"
        )
        warnings = check_unknown_keys_raw(data)
        assert any(w.path == "components.bogus" for w in warnings)

    def test_known_keys_no_warning(self):
        data = yaml.safe_load(VALID_FULL_YAML)
        codes = [w.code for w in check_unknown_keys_raw(data)]
        assert "package_map_unknown_keys" not in codes


class TestUnsupportedVersion:
    def test_version_2_warns(self):
        pm = parse_package_map(
            VALID_MINIMAL_YAML.replace("version: 1", "version: 2")
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_unsupported_version" in codes

    def test_version_1_ok(self):
        pm = parse_package_map(VALID_MINIMAL_YAML)
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_unsupported_version" not in codes


# Validation: empty capabilities


class TestEmptyCapabilities:
    def test_empty_capabilities_warns(self):
        pm = parse_package_map("version: 1\npackage:\n  slug: x\n")
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_empty_capabilities" in codes

    def test_non_empty_capabilities_ok(self):
        pm = parse_package_map(VALID_MINIMAL_YAML)
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_empty_capabilities" not in codes


# Validation: entrypoint traversal


class TestEntrypointTraversal:
    def test_absolute_entrypoint_warns(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(name="c", entrypoint="/abs/path.py"),
            )
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_entrypoint_traversal" in codes

    def test_dotdot_entrypoint_warns(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(name="c", entrypoint="../escape.py"),
            )
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_entrypoint_traversal" in codes

    def test_relative_entrypoint_ok(self):
        pm = _pm(
            capabilities=(CapabilityEntry(name="c", entrypoint="src/main.py"),)
        )
        traversal = [
            w
            for w in validate_package_map(pm)
            if w.code == "package_map_entrypoint_traversal"
        ]
        assert len(traversal) == 0

    def test_runtime_absolute_entrypoint_warns(self):
        pm = _pm(
            capabilities=(CapabilityEntry(name="c", entrypoint="a.py"),),
            runtime=RuntimeBlock(
                include=("src/**",), entrypoint="/abs/main.py"
            ),
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_entrypoint_traversal" in codes

    def test_capabilities_manifest_traversal(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(
                    name="c",
                    entrypoint="a.py",
                    capabilities_manifest="../bad.yaml",
                ),
            )
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_entrypoint_traversal" in codes


# Validation: entrypoint not matched


class TestEntrypointNotMatched:
    def test_unmatched_entrypoint_warns(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(name="c", entrypoint="src/main.py"),
            ),
            source=SourceBlock(include=("doc/**",)),
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_entrypoint_not_matched" in codes

    def test_matched_entrypoint_ok(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(name="c", entrypoint="src/main.py"),
            ),
            source=SourceBlock(include=("src/**",)),
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_entrypoint_not_matched" not in codes

    def test_matched_by_capability_include(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(
                    name="c",
                    entrypoint="skills/c/SKILL.md",
                    include=("skills/c/**",),
                ),
            ),
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_entrypoint_not_matched" not in codes


# Validation: dependency unknown


class TestDependencyUnknown:
    def test_unknown_dependency_warns(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(
                    name="c",
                    entrypoint="a.py",
                    dependencies=(Dependency("nonexistent"),),
                ),
            )
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_dependency_unknown" in codes

    def test_known_dependency_ok(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(name="core", entrypoint="a.py"),
                CapabilityEntry(
                    name="extra",
                    entrypoint="b.py",
                    dependencies=(Dependency("core"),),
                ),
            )
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_dependency_unknown" not in codes


# Validation: dependency cycle


class TestDependencyCycle:
    def test_cycle_warns(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(
                    name="a",
                    entrypoint="a.py",
                    dependencies=(Dependency("b"),),
                ),
                CapabilityEntry(
                    name="b",
                    entrypoint="b.py",
                    dependencies=(Dependency("a"),),
                ),
            )
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_dependency_cycle" in codes

    def test_no_cycle_ok(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(name="core", entrypoint="a.py"),
                CapabilityEntry(
                    name="extra",
                    entrypoint="b.py",
                    dependencies=(Dependency("core"),),
                ),
            )
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_dependency_cycle" not in codes


# Validation: glob invalid


class TestGlobInvalid:
    def test_invalid_glob_warns(self):
        pm = _pm(
            capabilities=(CapabilityEntry(name="c", entrypoint="a.py"),),
            source=SourceBlock(include=("src/[bad",)),
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_glob_invalid" in codes

    def test_valid_glob_ok(self):
        pm = _pm(
            capabilities=(CapabilityEntry(name="c", entrypoint="a.py"),),
            source=SourceBlock(include=("src/**", "*.py")),
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_glob_invalid" not in codes


# Validation: commands not executed


class TestCommandsNotExecuted:
    def test_commands_flagged(self):
        pm = _pm(
            capabilities=(CapabilityEntry(name="c", entrypoint="a.py"),),
            evals=EvalsBlock(commands=(("test", "pytest"),)),
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_commands_not_executed" in codes

    def test_no_commands_no_flag(self):
        pm = _pm(
            capabilities=(CapabilityEntry(name="c", entrypoint="a.py"),),
            evals=EvalsBlock(),
        )
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_commands_not_executed" not in codes


# Combined validation


class TestValidatePackageMap:
    def test_valid_map_no_warnings(self):
        pm = _pm(
            capabilities=(
                CapabilityEntry(name="core", entrypoint="src/main.py"),
            ),
            source=SourceBlock(include=("src/**",)),
        )
        assert validate_package_map(pm) == []

    def test_multiple_warnings(self):
        pm = _pm(version=2, capabilities=())
        codes = [w.code for w in validate_package_map(pm)]
        assert "package_map_unsupported_version" in codes
        assert "package_map_empty_capabilities" in codes
