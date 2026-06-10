# SPDX-License-Identifier: MIT
"""Tests for ``logion courses report-usage`` convenience command."""

from __future__ import annotations

import argparse
from unittest.mock import patch

from cli.commands.courses.report_usage import (
    handle_report_usage,
    register_report_usage,
)


class _FakeResult:
    """Mimics an SDK review_version result with model_dump."""

    def __init__(self, **kwargs):
        self._data = kwargs

    def model_dump(self, **_kwargs):
        return dict(self._data)


def _make_args(**overrides):
    defaults = {
        "course_id": "550e8400-e29b-41d4-a716-446655440000",
        "version_id": "660e8400-e29b-41d4-a716-446655440001",
        "rating": 4,
        "body": None,
        "completed_task": None,
        "reliability": None,
        "usefulness": None,
        "tool_safety": None,
        "token_efficiency": None,
        "json_output": False,
        "api_key": "test-key",  # pragma: allowlist secret
        "base_url": "https://api.test.logion.sh",
        "timeout": 30,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestHandleReportUsage:
    """Handler forwards to SDK review_version with correct kwargs."""

    @patch("cli.commands.courses.report_usage.make_client")
    @patch("cli.commands.courses.report_usage.resolve_config_from_args")
    def test_basic_rating_only(self, mock_config, mock_client):
        mock_config.return_value = argparse.Namespace(
            api_key="k",
            base_url="https://api.test.logion.sh",
            timeout=30,
            json_output=True,
        )
        fake_result = _FakeResult(
            id="r1",
            rating=4,
            course_id="550e8400-e29b-41d4-a716-446655440000",
            course_version_id="660e8400-e29b-41d4-a716-446655440001",
        )
        mock_client.return_value.v1.courses.review_version.return_value = (
            fake_result
        )
        args = _make_args(rating=4, json_output=True)
        rc = handle_report_usage(args)
        assert rc == 0
        call_kwargs = (
            mock_client.return_value.v1.courses.review_version.call_args[1]
        )
        assert call_kwargs["rating"] == 4
        assert call_kwargs["course_id"] == args.course_id
        assert call_kwargs["version_id"] == args.version_id

    @patch("cli.commands.courses.report_usage.make_client")
    @patch("cli.commands.courses.report_usage.resolve_config_from_args")
    def test_all_tier_b_fields_forwarded(self, mock_config, mock_client):
        mock_config.return_value = argparse.Namespace(
            api_key="k",
            base_url="https://api.test.logion.sh",
            timeout=30,
            json_output=True,
        )
        fake_result = _FakeResult(id="r2", rating=5)
        mock_client.return_value.v1.courses.review_version.return_value = (
            fake_result
        )
        args = _make_args(
            rating=5,
            usefulness=4.5,
            reliability=4.0,
            tool_safety=5.0,
            token_efficiency=3.0,
            completed_task=True,
            body="Great course",
            json_output=True,
        )
        rc = handle_report_usage(args)
        assert rc == 0
        call_kwargs = (
            mock_client.return_value.v1.courses.review_version.call_args[1]
        )
        assert call_kwargs["usefulness"] == 4.5
        assert call_kwargs["reliability"] == 4.0
        assert call_kwargs["tool_safety"] == 5.0
        assert call_kwargs["token_efficiency"] == 3.0
        assert call_kwargs["completed_task"] is True
        assert call_kwargs["body"] == "Great course"

    def test_invalid_rating_returns_error(self):
        args = _make_args(rating=6)
        rc = handle_report_usage(args)
        assert rc == 2

    def test_invalid_uuid_returns_error(self):
        args = _make_args(course_id="not-a-uuid")
        rc = handle_report_usage(args)
        assert rc == 2

    @patch("cli.commands.courses.report_usage.make_client")
    @patch("cli.commands.courses.report_usage.resolve_config_from_args")
    def test_json_output_uses_model_dump(self, mock_config, mock_client):
        mock_config.return_value = argparse.Namespace(
            api_key="k",
            base_url="https://api.test.logion.sh",
            timeout=30,
            json_output=True,
        )
        fake_result = _FakeResult(
            id="r3",
            rating=4,
            review_id="r3",
        )
        mock_client.return_value.v1.courses.review_version.return_value = (
            fake_result
        )
        args = _make_args(rating=4, json_output=True)
        rc = handle_report_usage(args)
        assert rc == 0


class TestRegisterReportUsage:
    """Subcommand parser registration."""

    def test_registers_handler(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register_report_usage(subparsers)
        args = parser.parse_args([
            "report-usage",
            "550e8400-e29b-41d4-a716-446655440000",
            "660e8400-e29b-41d4-a716-446655440001",
            "--rating",
            "4",
        ])
        assert hasattr(args, "handler")
        assert args.rating == 4
