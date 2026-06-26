# SPDX-License-Identifier: MIT
"""Tests for capability manifest validation, focusing on runtime requirements.

These mirror the server-side validation rules for ``runtime.requires``
and ``runtime.install`` fields, plus cross-field warnings and summary
output.
"""

from __future__ import annotations

from typing import Any

import pytest

from cli._course_capabilities import (
    CapabilityManifestError,
    normalize_capability_manifest,
    runtime_requirement_warnings,
    summarize_capability_manifest,
)


def _manifest(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid manifest with optional overrides."""
    base: dict[str, Any] = {"version": 1}
    base.update(overrides)
    return base


class TestRuntimeNormalization:
    def test_valid_manifest_with_runtime_requirements_is_normalized(
        self,
    ) -> None:
        """Full runtime with all fields — assert sorted/deduped."""
        manifest = _manifest(
            runtime={
                "requires": {
                    "env": ["PYTHONPATH", "DJANGO_SETTINGS_MODULE"],
                    "bins": ["python3", "uv", "python3"],
                    "any_bins": [["uv", "pip"], ["docker", "podman"]],
                    "config": ["config/settings.yaml", ".env.defaults"],
                    "os": ["macos", "linux", "linux"],
                    "software": [
                        {
                            "name": "AutoCAD",
                            "install": "vendor",
                            "notes": "Proprietary.",
                        },
                    ],
                },
                "install": [
                    {
                        "kind": "uv",
                        "command": "uv sync",
                        "notes": "Disclosure only.",
                    },
                ],
            },
        )
        result = normalize_capability_manifest(manifest)
        requires = result["runtime"]["requires"]
        assert requires["env"] == ["DJANGO_SETTINGS_MODULE", "PYTHONPATH"]
        assert requires["bins"] == ["python3", "uv"]
        assert requires["any_bins"] == [["pip", "uv"], ["docker", "podman"]]
        assert requires["config"] == [".env.defaults", "config/settings.yaml"]
        assert requires["os"] == ["linux", "macos"]
        assert len(requires["software"]) == 1
        assert requires["software"][0]["name"] == "AutoCAD"
        assert result["runtime"]["install"][0]["kind"] == "uv"
        assert result["runtime"]["install"][0]["command"] == "uv sync"

    def test_runtime_requires_env_uses_env_name_validation(self) -> None:
        """Invalid env name rejected."""
        manifest = _manifest(
            runtime={"requires": {"env": ["invalid-lowercase"]}},
        )
        with pytest.raises(CapabilityManifestError, match="env var name"):
            normalize_capability_manifest(manifest)

    def test_runtime_requires_bins_rejects_shell_syntax(self) -> None:
        """Reject shell metacharacters, paths, and spaces in bin names."""
        for bad in ["python;rm", "./tool", "tool name"]:
            manifest = _manifest(
                runtime={"requires": {"bins": [bad]}},
            )
            with pytest.raises(CapabilityManifestError):
                normalize_capability_manifest(manifest)

    def test_runtime_requires_config_rejects_absolute_and_traversal(
        self,
    ) -> None:
        """Reject absolute paths and .. traversal in config."""
        for bad in ["/etc/passwd", "../secret"]:
            manifest = _manifest(
                runtime={"requires": {"config": [bad]}},
            )
            with pytest.raises(CapabilityManifestError):
                normalize_capability_manifest(manifest)

    def test_runtime_software_rejects_unknown_keys(self) -> None:
        """Extra key in software entry rejected."""
        manifest = _manifest(
            runtime={
                "requires": {
                    "software": [
                        {"name": "Thing", "bogus": True},
                    ],
                },
            },
        )
        with pytest.raises(CapabilityManifestError, match="software"):
            normalize_capability_manifest(manifest)

    def test_runtime_install_rejects_unknown_kind(self) -> None:
        """kind not in INSTALL_KINDS rejected."""
        manifest = _manifest(
            runtime={
                "install": [
                    {"kind": "choco", "command": "choco install thing"},
                ],
            },
        )
        with pytest.raises(CapabilityManifestError, match="install kind"):
            normalize_capability_manifest(manifest)

    def test_runtime_install_rejects_multiline_command(self) -> None:
        """Command with newline rejected."""
        manifest = _manifest(
            runtime={
                "install": [
                    {"kind": "uv", "command": "uv sync\n&& uv run"},
                ],
            },
        )
        with pytest.raises(CapabilityManifestError, match="newline"):
            normalize_capability_manifest(manifest)

    def test_manifest_unknown_top_level_key_still_fails(self) -> None:
        """Unknown top-level key rejected."""
        manifest = _manifest(bogus=True)
        with pytest.raises(CapabilityManifestError, match="Unknown"):
            normalize_capability_manifest(manifest)


class TestRuntimeWarnings:
    def test_runtime_env_not_in_secrets_emits_warning_not_failure(
        self,
    ) -> None:
        """env in runtime.requires.env but not in secrets.env — warning."""
        manifest = _manifest(
            runtime={"requires": {"env": ["PYTHONPATH"]}},
        )
        result = normalize_capability_manifest(manifest)
        # Manifest is valid (no exception).
        warnings = runtime_requirement_warnings(result)
        codes = [w["code"] for w in warnings]
        assert "runtime_env_not_declared_as_secret" in codes

    def test_runtime_install_without_human_approval_emits_warning_not_failure(
        self,
    ) -> None:
        """Install steps present, human_approval false — warning."""
        manifest = _manifest(
            runtime={
                "install": [
                    {"kind": "uv", "command": "uv sync"},
                ],
            },
        )
        result = normalize_capability_manifest(manifest)
        # Manifest is valid (no exception).
        warnings = runtime_requirement_warnings(result)
        codes = [w["code"] for w in warnings]
        assert "install_steps_without_human_approval" in codes

    def test_runtime_host_deps_without_terminal_emits_warning(self) -> None:
        """bins declared but terminal not in tools should warn."""
        manifest = _manifest(
            tools=["file"],
            runtime={"requires": {"bins": ["python3"]}},
        )
        result = normalize_capability_manifest(manifest)
        warnings = runtime_requirement_warnings(result)
        codes = [w["code"] for w in warnings]
        assert "runtime_declares_host_dependencies_without_terminal" in codes

    def test_runtime_install_without_network_domains_emits_warning(
        self,
    ) -> None:
        """install with package managers but no network domains should warn."""
        manifest = _manifest(
            tools=["terminal"],
            human_approval={"required": True},
            runtime={"install": [{"kind": "uv", "command": "uv sync"}]},
        )
        result = normalize_capability_manifest(manifest)
        warnings = runtime_requirement_warnings(result)
        codes = [w["code"] for w in warnings]
        assert "install_steps_without_network_domains" in codes


class TestSummary:
    def test_summarize_includes_runtime_keys(self) -> None:
        """summarize_capability_manifest returns runtime_* keys."""
        manifest = _manifest(
            runtime={
                "requires": {
                    "bins": ["python3"],
                    "os": ["linux"],
                },
                "install": [
                    {"kind": "uv", "command": "uv sync"},
                ],
            },
        )
        result = normalize_capability_manifest(manifest)
        summary = summarize_capability_manifest(result)
        assert "runtime_requires_env" in summary
        assert "runtime_requires_bins" in summary
        assert "runtime_requires_any_bins" in summary
        assert "runtime_requires_config" in summary
        assert "runtime_requires_os" in summary
        assert "runtime_requires_software" in summary
        assert "runtime_install" in summary
        assert summary["runtime_requires_bins"] == ["python3"]
        assert summary["runtime_requires_os"] == ["linux"]

    def test_runtime_warnings_codes_in_summary(self) -> None:
        """runtime_warning_codes in summary."""
        manifest = _manifest(
            runtime={
                "requires": {"env": ["PYTHONPATH"]},
                "install": [{"kind": "uv", "command": "uv sync"}],
            },
        )
        result = normalize_capability_manifest(manifest)
        summary = summarize_capability_manifest(result)
        assert "runtime_warning_codes" in summary
        assert isinstance(summary["runtime_warning_codes"], list)
        # At least the env-not-secret warning should be present.
        assert (
            "runtime_env_not_declared_as_secret"
            in summary["runtime_warning_codes"]
        )

    def test_summarize_includes_runtime_warnings(self) -> None:
        """Full warning dicts (code, severity, message) in summary."""
        manifest = _manifest(
            tools=["file"],
            runtime={"requires": {"env": ["GITHUB_TOKEN"]}},
        )
        result = normalize_capability_manifest(manifest)
        summary = summarize_capability_manifest(result)
        assert "runtime_warnings" in summary
        assert isinstance(summary["runtime_warnings"], list)
        assert len(summary["runtime_warnings"]) > 0
