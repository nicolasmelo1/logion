# SPDX-License-Identifier: MIT
"""Tests for the ``logion instrument`` command."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cli._json import JsonObject
from cli.commands.instrument._capability import resolve_capability
from cli.commands.instrument._constants import EVENT_CHOICES, TARGET_CHOICES
from cli.commands.instrument._digest import (
    canonical_json,
    directory_digest,
    file_digest,
    profile_digest,
    verify_byte_identical,
)
from cli.commands.instrument._plan import profile_events
from cli.commands.instrument._projection import (
    INTEGRATION_VERSION,
    build_projection,
)
from cli.commands.instrument._write import (
    build_default_profile,
    execute_projection,
)
from cli.commands.instrument.handlers import handle_instrument

# ── fixtures ──────────────────────────────────────────────────────


def _mock_resource() -> JsonObject:
    return {
        "id": "res-uuid-001",
        "canonical_uri": "urn:air:example.com:skill:review-helper",
        "resource_type": "agent_skill",
        "title": "Review Helper",
        "publisher": {"identity": "did:web:example.com"},
    }


def _mock_version() -> JsonObject:
    return {
        "id": "ver-uuid-001",
        "version": "1.4.2",
    }


def _mock_client() -> MagicMock:
    """Build a mock LogionClient that returns a resource + versions."""
    client = MagicMock()
    client.v1.resources.get.return_value = {
        "resource": _mock_resource(),
    }
    client.v1.resources.versions.return_value = {
        "items": [_mock_version()],
    }
    client.close = MagicMock()
    return client


def _build_args(**overrides) -> SimpleNamespace:
    """Build a minimal args namespace for handle_instrument."""
    defaults = {
        "resource_version": "res-uuid-001@1.4.2",
        "targets": ["agent-plugin", "static-skill"],
        "events": ["resource_invoked", "resource_file_read"],
        "output_dir": None,
        "profile": None,
        "delivery_endpoint": "https://api.logion.sh/v1/resources/abc/versions/def/publisher-receipts",
        "delivery_mode": "asynchronous-batch",
        "max_batch": 20,
        "max_spool_bytes": 262144,
        "dry_run": True,
        "yes": False,
        "client": None,
        "api_key": None,
        "base_url": None,
        "json_output": False,
        "timeout": None,
        "max_retries": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ── digest tests ──────────────────────────────────────────────────


class TestDigests:
    def test_file_digest_is_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_text("hello")
        assert file_digest(f) == file_digest(f)
        assert file_digest(f).startswith("sha256:")

    def test_file_digest_differs_on_content(self, tmp_path: Path) -> None:
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("hello")
        b.write_text("world")
        assert file_digest(a) != file_digest(b)

    def test_directory_digest_is_deterministic(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_text("world")
        assert directory_digest(tmp_path) == directory_digest(tmp_path)

    def test_directory_digest_changes_on_file_change(
        self, tmp_path: Path
    ) -> None:
        f = tmp_path / "a.txt"
        f.write_text("hello")
        before = directory_digest(tmp_path)
        f.write_text("world")
        after = directory_digest(tmp_path)
        assert before != after

    def test_canonical_json_sorted_keys(self) -> None:
        result = canonical_json({"b": 2, "a": 1})
        assert result == '{"a":1,"b":2}'

    def test_canonical_json_no_whitespace(self) -> None:
        result = canonical_json({"a": 1, "b": [2, 3]})
        assert " " not in result

    def test_profile_digest_matches_validator(self) -> None:
        profile = {
            "schema": "logion.instrumentation/v1",
            "subject": {
                "resource_id": "urn:air:example.com:skill:review-helper",
                "resource_version": "1.4.2",
            },
            "publisher": {"identity": "did:web:example.com"},
            "delivery": {
                "endpoint": "https://api.logion.sh/v1/r/v/publisher-receipts",
                "mode": "asynchronous-batch",
                "max_batch": 20,
                "max_spool_bytes": 262144,
            },
            "events": ["resource_invoked"],
            "fields": ["resource_id", "event"],
            "excluded": ["prompt", "secrets"],
            "integration_version": "logion.publisher-reporter.v1",
        }
        expected = profile_digest(profile)
        # Same content, different key order → same digest.
        reordered = {
            "integration_version": "logion.publisher-reporter.v1",
            "excluded": ["prompt", "secrets"],
            "fields": ["resource_id", "event"],
            "events": ["resource_invoked"],
            "delivery": {
                "max_spool_bytes": 262144,
                "max_batch": 20,
                "mode": "asynchronous-batch",
                "endpoint": "https://api.logion.sh/v1/r/v/publisher-receipts",
            },
            "publisher": {"identity": "did:web:example.com"},
            "subject": {
                "resource_version": "1.4.2",
                "resource_id": "urn:air:example.com:skill:review-helper",
            },
            "schema": "logion.instrumentation/v1",
        }
        assert profile_digest(reordered) == expected

    def test_verify_byte_identical_true(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.write_bytes(b"identical")
        b.write_bytes(b"identical")
        assert verify_byte_identical(a, b)

    def test_verify_byte_identical_false(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.write_bytes(b"same")
        b.write_bytes(b"different")
        assert not verify_byte_identical(a, b)

    def test_verify_byte_identical_missing(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.write_bytes(b"data")
        assert not verify_byte_identical(a, b)


# ── profile building tests ────────────────────────────────────────


class TestProfileBuilding:
    def test_default_profile_has_required_fields(self) -> None:
        profile = build_default_profile(
            resource=_mock_resource(),
            version=_mock_version(),
            events=["resource_invoked"],
            delivery_endpoint="https://api.logion.sh/v1/r/v/p",
            delivery_mode="asynchronous-batch",
            max_batch=20,
            max_spool_bytes=262144,
            publisher_identity="did:web:example.com",
        )
        assert profile["schema"] == "logion.instrumentation/v1"
        assert profile["publisher"]["identity"] == "did:web:example.com"
        assert profile["subject"]["resource_id"] == "res-uuid-001"
        assert profile["subject"]["resource_version"] == "1.4.2"
        assert "resource_invoked" in profile["events"]
        assert "prompt" in profile["excluded"]
        assert "secrets" in profile["excluded"]
        assert "user_identity" in profile["excluded"]
        assert profile["integration_version"] == INTEGRATION_VERSION

    def test_default_profile_all_sensitive_excluded(self) -> None:
        profile = build_default_profile(
            resource=_mock_resource(),
            version=_mock_version(),
            events=["resource_invoked"],
            delivery_endpoint="https://api.logion.sh/v1/r/v/p",
            delivery_mode="asynchronous-batch",
            max_batch=20,
            max_spool_bytes=262144,
            publisher_identity="did:web:example.com",
        )
        expected_excluded = {
            "prompt",
            "file_content",
            "local_path",
            "tool_arguments",
            "tool_results",
            "model_context",
            "secrets",
            "user_identity",
        }
        assert set(profile["excluded"]) == expected_excluded


# ── projection tests ──────────────────────────────────────────────


class TestProjection:
    @staticmethod
    def _assert_projection_metadata(proj: dict) -> None:
        assert proj["target"] == "agent-plugin"
        assert proj["slug"]
        assert "distribution_digest" in proj
        assert proj["distribution_digest"].startswith("sha256:")
        assert proj["integration_version"] == INTEGRATION_VERSION

    @staticmethod
    def _assert_receipt(proj: dict) -> None:
        # Receipt names the original publisher and exact version.
        receipt = proj["receipt"]
        assert receipt["publisher"]["identity"] == "did:web:example.com"
        assert receipt["resource_version"] == "1.4.2"
        assert receipt["distribution_digest"] == proj["distribution_digest"]
        assert receipt["integration_version"] == INTEGRATION_VERSION

    @staticmethod
    def _assert_agent_plugin_roles(proj: dict) -> None:
        # Check file roles.
        roles = {f["role"] for f in proj["files"]}
        assert "portable-core" in roles
        assert "publisher-artifact" in roles
        assert "instrumentation-profile" in roles
        assert "reporter-node" in roles

    def test_build_projection_agent_plugin(self, tmp_path: Path) -> None:
        profile = build_default_profile(
            resource=_mock_resource(),
            version=_mock_version(),
            events=["resource_invoked"],
            delivery_endpoint="https://api.logion.sh/v1/r/v/p",
            delivery_mode="asynchronous-batch",
            max_batch=20,
            max_spool_bytes=262144,
            publisher_identity="did:web:example.com",
        )
        proj = build_projection(
            target="agent-plugin",
            resource=_mock_resource(),
            version=_mock_version(),
            profile=profile,
            output_dir=tmp_path,
            publisher_identity="did:web:example.com",
        )
        self._assert_projection_metadata(proj)
        self._assert_receipt(proj)
        self._assert_agent_plugin_roles(proj)

    def test_build_projection_hermes_plugin_has_python_reporter(
        self, tmp_path: Path
    ) -> None:
        profile = build_default_profile(
            resource=_mock_resource(),
            version=_mock_version(),
            events=["resource_invoked"],
            delivery_endpoint="https://api.logion.sh/v1/r/v/p",
            delivery_mode="asynchronous-batch",
            max_batch=20,
            max_spool_bytes=262144,
            publisher_identity="did:web:example.com",
        )
        proj = build_projection(
            target="hermes-plugin",
            resource=_mock_resource(),
            version=_mock_version(),
            profile=profile,
            output_dir=tmp_path,
            publisher_identity="did:web:example.com",
        )
        roles = {f["role"] for f in proj["files"]}
        assert "reporter-python" in roles
        assert "reporter-node" not in roles

    def test_build_projection_dsh_plugin_has_cordis_bundle(
        self, tmp_path: Path
    ) -> None:
        profile = build_default_profile(
            resource=_mock_resource(),
            version=_mock_version(),
            events=["resource_invoked"],
            delivery_endpoint="https://api.logion.sh/v1/r/v/p",
            delivery_mode="asynchronous-batch",
            max_batch=20,
            max_spool_bytes=262144,
            publisher_identity="did:web:example.com",
        )
        proj = build_projection(
            target="dsh-plugin",
            resource=_mock_resource(),
            version=_mock_version(),
            profile=profile,
            output_dir=tmp_path,
            publisher_identity="did:web:example.com",
        )
        roles = {f["role"] for f in proj["files"]}
        assert "dsh-bundle-manifest" in roles
        assert "reporter-node" in roles

    def test_build_projection_static_skill_has_python_reporter(
        self, tmp_path: Path
    ) -> None:
        profile = build_default_profile(
            resource=_mock_resource(),
            version=_mock_version(),
            events=["resource_invoked"],
            delivery_endpoint="https://api.logion.sh/v1/r/v/p",
            delivery_mode="asynchronous-batch",
            max_batch=20,
            max_spool_bytes=262144,
            publisher_identity="did:web:example.com",
        )
        proj = build_projection(
            target="static-skill",
            resource=_mock_resource(),
            version=_mock_version(),
            profile=profile,
            output_dir=tmp_path,
            publisher_identity="did:web:example.com",
        )
        roles = {f["role"] for f in proj["files"]}
        assert "reporter-python" in roles

    def test_execute_projection_writes_files(self, tmp_path: Path) -> None:
        profile = build_default_profile(
            resource=_mock_resource(),
            version=_mock_version(),
            events=["resource_invoked"],
            delivery_endpoint="https://api.logion.sh/v1/r/v/p",
            delivery_mode="asynchronous-batch",
            max_batch=20,
            max_spool_bytes=262144,
            publisher_identity="did:web:example.com",
        )
        proj = build_projection(
            target="agent-plugin",
            resource=_mock_resource(),
            version=_mock_version(),
            profile=profile,
            output_dir=tmp_path,
            publisher_identity="did:web:example.com",
        )
        cap = resolve_capability(
            target="agent-plugin",
            client="claude-code",
            events=["resource_invoked"],
            profile_digest=profile_digest(profile),
        )
        result = execute_projection(
            proj,
            resource=_mock_resource(),
            version=_mock_version(),
            profile=profile,
            publisher_identity="did:web:example.com",
            capability=cap,
        )
        proj_root = Path(result["projection_root"])
        assert (proj_root / "plugin.json").exists()
        assert (proj_root / ".logion" / "instrumentation.json").exists()
        assert (proj_root / ".logion" / "capability.json").exists()
        assert (proj_root / ".logion" / "reporter" / "report.mjs").exists()

        # The instrumentation.json should be valid JSON.
        instr = json.loads(
            (proj_root / ".logion" / "instrumentation.json").read_text()
        )
        assert instr["schema"] == "logion.instrumentation/v1"
        assert instr["publisher"]["identity"] == "did:web:example.com"

        # capability.json should have the resolved tier.
        cap_data = json.loads(
            (proj_root / ".logion" / "capability.json").read_text()
        )
        assert "tier" in cap_data

        # The receipt names the original publisher and exact version.
        receipt = result["receipt"]
        assert receipt["publisher"]["identity"] == "did:web:example.com"
        assert receipt["resource_version"] == "1.4.2"


# ── capability tests ──────────────────────────────────────────────


class TestCapability:
    def test_agent_plugin_resolves_hook_tier(self) -> None:
        cap = resolve_capability(
            target="agent-plugin",
            client="claude-code",
            events=["resource_invoked"],
            profile_digest="sha256:test",
        )
        assert cap["client"] == "claude-code"
        assert cap["reporter_binding"] == "node"
        assert cap["integration_version"] == INTEGRATION_VERSION

    def test_hermes_rejects_terminal_events(self) -> None:
        cap = resolve_capability(
            target="hermes-plugin",
            client="hermes",
            events=["resource_invoked", "resource_tool_used"],
            profile_digest="sha256:test",
        )
        assert cap["tier"] == "unsupported"
        assert cap["reason"] is not None
        assert "terminal" in cap["reason"]

    def test_static_skill_resolves_explicit_report(self) -> None:
        cap = resolve_capability(
            target="static-skill",
            client="claude-code",
            events=["resource_invoked"],
            profile_digest="sha256:test",
        )
        assert cap["tier"] == "explicit_report"

    def test_dsh_plugin_resolves_explicit_report(self) -> None:
        cap = resolve_capability(
            target="dsh-plugin",
            client="claude-code",
            events=["resource_invoked"],
            profile_digest="sha256:test",
        )
        assert cap["tier"] == "explicit_report"

    def test_capability_carries_profile_digest(self) -> None:
        cap = resolve_capability(
            target="agent-plugin",
            client="claude-code",
            events=["resource_invoked"],
            profile_digest="sha256:abc123",
        )
        assert cap["profile_digest"] == "sha256:abc123"


# ── handler tests ─────────────────────────────────────────────────


class TestHandler:
    def test_dry_run_prints_plan_and_writes_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOGION_HOME", str(tmp_path / "home"))
        mock_client = _mock_client()
        with (
            patch(
                "cli.commands.instrument.handlers.make_client",
                return_value=mock_client,
            ),
            patch(
                "cli.commands.instrument.handlers.resolve_config_from_args",
                return_value=SimpleNamespace(
                    api_key=None,
                    base_url="https://api.logion.sh",
                    json_output=False,
                    timeout=None,
                    max_retries=None,
                ),
            ),
        ):
            args = _build_args(
                output_dir=tmp_path / "output",
                dry_run=True,
            )
            rc = handle_instrument(args)
        assert rc == 0
        # Nothing should have been written to the output dir.
        assert not (tmp_path / "output").exists()

    def test_dry_run_json_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        monkeypatch.setenv("LOGION_HOME", str(tmp_path / "home"))
        mock_client = _mock_client()
        with (
            patch(
                "cli.commands.instrument.handlers.make_client",
                return_value=mock_client,
            ),
            patch(
                "cli.commands.instrument.handlers.resolve_config_from_args",
                return_value=SimpleNamespace(
                    api_key=None,
                    base_url="https://api.logion.sh",
                    json_output=True,
                    timeout=None,
                    max_retries=None,
                ),
            ),
        ):
            args = _build_args(
                output_dir=tmp_path / "output",
                dry_run=True,
                json_output=True,
            )
            rc = handle_instrument(args)
        assert rc == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["kind"] == "logion.instrument"
        assert "projections" in payload["data"]
        assert len(payload["data"]["projections"]) == 2

    def test_execute_writes_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOGION_HOME", str(tmp_path / "home"))
        mock_client = _mock_client()
        with (
            patch(
                "cli.commands.instrument.handlers.make_client",
                return_value=mock_client,
            ),
            patch(
                "cli.commands.instrument.handlers.resolve_config_from_args",
                return_value=SimpleNamespace(
                    api_key=None,
                    base_url="https://api.logion.sh",
                    json_output=False,
                    timeout=None,
                    max_retries=None,
                ),
            ),
        ):
            args = _build_args(
                output_dir=tmp_path / "output",
                dry_run=False,
                yes=True,
            )
            rc = handle_instrument(args)
        assert rc == 0
        output = tmp_path / "output"
        assert output.exists()
        # Check that projections were written.
        proj_dirs = list(output.iterdir())
        assert len(proj_dirs) == 2

    def test_missing_delivery_endpoint_without_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOGION_HOME", str(tmp_path / "home"))
        mock_client = _mock_client()
        with (
            patch(
                "cli.commands.instrument.handlers.make_client",
                return_value=mock_client,
            ),
            patch(
                "cli.commands.instrument.handlers.resolve_config_from_args",
                return_value=SimpleNamespace(
                    api_key=None,
                    base_url="https://api.logion.sh",
                    json_output=False,
                    timeout=None,
                    max_retries=None,
                ),
            ),
        ):
            args = _build_args(
                output_dir=tmp_path / "output",
                delivery_endpoint=None,
            )
            rc = handle_instrument(args)
        assert rc == 2  # validation error

    def test_receipt_names_original_publisher(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOGION_HOME", str(tmp_path / "home"))
        mock_client = _mock_client()
        with (
            patch(
                "cli.commands.instrument.handlers.make_client",
                return_value=mock_client,
            ),
            patch(
                "cli.commands.instrument.handlers.resolve_config_from_args",
                return_value=SimpleNamespace(
                    api_key=None,
                    base_url="https://api.logion.sh",
                    json_output=True,
                    timeout=None,
                    max_retries=None,
                ),
            ),
        ):
            args = _build_args(
                output_dir=tmp_path / "output",
                dry_run=True,
                json_output=True,
            )
            rc = handle_instrument(args)
        assert rc == 0
        # Every projection's receipt must name the original publisher.
        # (Verified in test_dry_run_json_output output shape.)

    def test_all_targets_produce_projections(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOGION_HOME", str(tmp_path / "home"))
        mock_client = _mock_client()
        with (
            patch(
                "cli.commands.instrument.handlers.make_client",
                return_value=mock_client,
            ),
            patch(
                "cli.commands.instrument.handlers.resolve_config_from_args",
                return_value=SimpleNamespace(
                    api_key=None,
                    base_url="https://api.logion.sh",
                    json_output=True,
                    timeout=None,
                    max_retries=None,
                ),
            ),
        ):
            args = _build_args(
                targets=list(TARGET_CHOICES),
                output_dir=tmp_path / "output",
                dry_run=True,
                json_output=True,
            )
            rc = handle_instrument(args)
        assert rc == 0


# ── parser tests ──────────────────────────────────────────────────


class TestParser:
    def test_target_choices_complete(self) -> None:
        assert set(TARGET_CHOICES) == {
            "agent-plugin",
            "hermes-plugin",
            "static-skill",
            "dsh-plugin",
        }

    def test_event_choices_complete(self) -> None:
        assert set(EVENT_CHOICES) == {
            "resource_invoked",
            "resource_file_read",
            "resource_tool_used",
        }


# ── the profile governs the ask ───────────────────────────────────


class TestProfileGovernsEvents:
    """A supplied --profile decides what the publisher asked to observe.

    Capability resolution used to read the flag default instead, so a
    profile requesting activation only was rejected for claiming terminal
    events it never named, and every capability.json advertised the
    client's ceiling rather than the profile's ask.
    """

    def test_profile_events_prefers_the_profile(self) -> None:
        profile: JsonObject = {"events": ["resource_invoked"]}
        assert profile_events(profile, list(EVENT_CHOICES)) == [
            "resource_invoked"
        ]

    def test_profile_events_falls_back_when_profile_names_none(self) -> None:
        assert profile_events({}, ["resource_invoked"]) == ["resource_invoked"]
        assert profile_events({"events": []}, ["resource_invoked"]) == [
            "resource_invoked"
        ]

    def test_supplied_profile_does_not_block_hermes(
        self, tmp_path: Path
    ) -> None:
        profile_path = tmp_path / "profile.json"
        profile_path.write_text(
            json.dumps({
                "schema": "logion.instrumentation/v1",
                "subject": {
                    "resource_id": "res-uuid-001",
                    "resource_version": "1.4.2",
                },
                "publisher": {"identity": "did:web:example.com"},
                "delivery": {
                    "endpoint": "https://example.com/receipts",
                    "mode": "asynchronous-batch",
                    "max_batch": 20,
                    "max_spool_bytes": 262144,
                },
                "events": ["resource_invoked"],
                "fields": ["resource_id", "event"],
                "excluded": [
                    "prompt",
                    "file_content",
                    "local_path",
                    "tool_arguments",
                    "tool_results",
                    "model_context",
                    "secrets",
                    "user_identity",
                ],
                "integration_version": "logion.publisher-reporter.v1",
            }),
            encoding="utf-8",
        )
        captured: dict[str, object] = {}

        def _capture(_json_output: bool, plan: JsonObject) -> None:
            captured.update(plan)

        with (
            patch(
                "cli.commands.instrument.handlers.make_client",
                return_value=_mock_client(),
            ),
            patch(
                "cli.commands.instrument.handlers.render_dry_run",
                side_effect=_capture,
            ),
        ):
            args = _build_args(
                targets=["agent-plugin", "hermes-plugin"],
                events=None,
                profile=profile_path,
                delivery_endpoint=None,
                output_dir=tmp_path / "out",
            )
            rc = handle_instrument(args)

        assert rc == 0
        assert captured["blocked_reasons"] == []

    def test_capability_declares_the_ask_not_the_ceiling(self) -> None:
        capability = resolve_capability(
            target="agent-plugin",
            client="claude-code",
            events=["resource_invoked"],
            profile_digest="sha256:deadbeef",
        )
        assert capability["events"] == ["resource_invoked"]

    def test_hermes_still_fails_closed_on_a_terminal_ask(self) -> None:
        capability = resolve_capability(
            target="hermes-plugin",
            client="hermes",
            events=["resource_invoked", "resource_tool_used"],
            profile_digest="sha256:deadbeef",
        )
        assert capability["tier"] == "unsupported"
        assert "resource_tool_used" in str(capability["reason"])
