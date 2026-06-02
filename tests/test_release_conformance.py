# SPDX-License-Identifier: MIT
"""Tests for the release conformance script.

Verifies that the conformance checker catches missing versions on
PyPI/npm and passes when the manifest matches the mocked published
state.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release_conformance.py"
STABLE_MANIFEST = REPO_ROOT / "releases" / "manifest-stable.json"


def _load_conformance_module():  # type: ignore[no-untyped-def]
    """Dynamically load the conformance script as a module."""
    spec = importlib.util.spec_from_file_location(
        "release_conformance",
        SCRIPT_PATH,
    )
    assert spec is not None, f"Could not load spec from {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {}):
        spec.loader.exec_module(  # type: ignore[union-attr]
            module,
        )
    return module


class TestConformanceChecksPyPIAndNpm:
    """With mocked network responses, the script catches
    missing or yanked versions.
    """

    def test_catches_missing_pypi_version(self) -> None:
        """If PyPI does not have the manifest version,
        _check_pypi appends an error.
        """
        mod = _load_conformance_module()
        errors: list[str] = []
        with patch.object(
            mod,
            "_pypi_versions",
            return_value={"0.0.1": False},
        ):
            mod._check_pypi("logion-cli", "99.99.99", errors)
        assert len(errors) == 1
        assert "99.99.99" in errors[0]
        assert "not on PyPI" in errors[0]

    def test_catches_missing_npm_version(self) -> None:
        """If npm does not have the manifest version,
        _check_npm appends an error.
        """
        mod = _load_conformance_module()
        errors: list[str] = []
        with patch.object(
            mod,
            "_npm_versions",
            return_value=["0.0.1"],
        ):
            mod._check_npm("@logion/cli", "99.99.99", errors)
        assert len(errors) == 1
        assert "99.99.99" in errors[0]

    def test_catches_yanked_pypi_version(self) -> None:
        """If PyPI version exists but is fully yanked,
        _check_pypi appends an error.
        """
        mod = _load_conformance_module()
        errors: list[str] = []
        with patch.object(
            mod,
            "_pypi_versions",
            return_value={"0.1.0": True},
        ):
            mod._check_pypi("logion-cli", "0.1.0", errors)
        assert len(errors) == 1
        assert "yanked" in errors[0]

    def test_pypi_network_error_appends_error(self) -> None:
        """If PyPI is unreachable, _check_pypi appends an error."""
        mod = _load_conformance_module()
        errors: list[str] = []
        with patch.object(
            mod,
            "_pypi_versions",
            side_effect=Exception("network error"),
        ):
            mod._check_pypi("logion-cli", "0.1.0", errors)
        assert len(errors) == 1
        assert "ERROR" in errors[0]

    def test_npm_network_error_appends_error(self) -> None:
        """If npm is unreachable, _check_npm appends an error."""
        mod = _load_conformance_module()
        errors: list[str] = []
        with patch.object(
            mod,
            "_npm_versions",
            side_effect=Exception("network error"),
        ):
            mod._check_npm("@logion/cli", "0.1.0", errors)
        assert len(errors) == 1
        assert "ERROR" in errors[0]


class TestConformancePassesOnRealManifest:
    """Network-mocked to mirror published state, exits 0."""

    def test_passes_when_all_publishers_match(self) -> None:
        """When all registries report the expected version,
        check_conformance returns True and main exits 0.
        """
        mod = _load_conformance_module()

        with STABLE_MANIFEST.open("r", encoding="utf-8") as f:
            real_manifest = json.load(f)

        # Patch the low-level network functions to return
        # data matching the manifest versions.
        pypi_versions: dict[str, bool] = {}
        npm_versions: list[str] = []
        for _name, entry in real_manifest.get("packages", {}).items():
            version = entry.get("version", "")
            if "pypi_name" in entry:
                pypi_versions[version] = False
            if "npm_name" in entry:
                npm_versions.append(version)

        with (
            patch.object(
                mod,
                "_pypi_versions",
                return_value=pypi_versions,
            ),
            patch.object(
                mod,
                "_npm_versions",
                return_value=npm_versions,
            ),
            patch.object(
                mod,
                "_check_url_reachable",
                return_value=True,
            ),
        ):
            result = mod.check_conformance("stable", deep=False)
        assert result, "check_conformance should return True"

        # Also verify main() exits 0 when invoked with --channel stable
        with (
            patch.object(
                mod,
                "_pypi_versions",
                return_value=pypi_versions,
            ),
            patch.object(
                mod,
                "_npm_versions",
                return_value=npm_versions,
            ),
            patch.object(
                mod,
                "_check_url_reachable",
                return_value=True,
            ),
            patch(
                "sys.argv",
                ["release_conformance.py", "--channel", "stable"],
            ),
        ):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
            assert exc_info.value.code == 0, (
                "Should exit 0 when all checks pass"
            )
