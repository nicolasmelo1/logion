# SPDX-License-Identifier: MIT
"""Tests for the ``logion skills search`` command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from cli._output import truncate_summary
from cli.commands.skills._search_handler import handle_skills_search


def _make_args(**overrides: Any) -> argparse.Namespace:
    """Build a minimal argparse Namespace for skills search."""
    defaults = {
        "query": "test-query",
        "limit": 5,
        "verbose": False,
        "target": None,
        "json_output": True,
        "api_key": None,
        "base_url": None,
        "timeout": None,
        "max_retries": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class FakeListingsResource:
    """Fake listings.search resource."""

    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self._items = items or []

    def search(self, **_kwargs: Any) -> dict[str, Any]:
        return {"items": self._items, "next_cursor": None}


class FakeCoursesResource:
    """Fake courses.get resource."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data = data or {}

    def get(self, **_kwargs: Any) -> dict[str, Any]:
        return self._data


class FakeV1Namespace:
    def __init__(
        self,
        listings: FakeListingsResource,
        courses: FakeCoursesResource | None = None,
    ) -> None:
        self.listings = listings
        self.courses = courses or FakeCoursesResource()


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def test_skills_search_json_shape_matches_envelope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Emit v1 envelope with kind=logion.skills.search."""
    items = [
        {
            "course_id": "course-1",
            "id": "course-1",
            "title": "Test Course",
            "short_summary": "A short summary",
        },
    ]
    listings = FakeListingsResource(items)
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))

    args = _make_args(target=tmp_path)
    with (
        patch(
            "cli.commands.skills._search_handler.make_client",
            return_value=fake,
        ),
        patch(
            "cli.commands.skills._search_handler.list_installed",
            return_value=[],
        ),
        patch(
            "cli.commands.skills._search_handler.resolve_config_from_args"
        ) as mock_cfg,
        patch(
            "cli.commands.skills._search_handler.resolve_target",
            return_value=tmp_path,
        ),
    ):
        mock_cfg.return_value = argparse.Namespace(
            json_output=True,
            api_key=None,
            base_url="https://api.logion.dev",
            timeout=None,
            max_retries=None,
        )
        rc = handle_skills_search(args)

    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["version"] == "v1"
    assert data["kind"] == "logion.skills.search"
    assert "items" in data["data"]
    assert "total" in data["data"]


def test_skills_search_uses_config_json_output_when_args_flag_is_false(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    items = [
        {
            "course_id": "course-1",
            "id": "course-1",
            "title": "Config Driven",
            "short_summary": "A short summary",
        },
    ]
    listings = FakeListingsResource(items)
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))

    args = _make_args(target=tmp_path, json_output=False)
    with (
        patch(
            "cli.commands.skills._search_handler.make_client",
            return_value=fake,
        ),
        patch(
            "cli.commands.skills._search_handler.list_installed",
            return_value=[],
        ),
        patch(
            "cli.commands.skills._search_handler.resolve_config_from_args"
        ) as mock_cfg,
        patch(
            "cli.commands.skills._search_handler.resolve_target",
            return_value=tmp_path,
        ),
    ):
        mock_cfg.return_value = argparse.Namespace(
            json_output=True,
            api_key=None,
            base_url="https://api.logion.dev",
            timeout=None,
            max_retries=None,
        )
        rc = handle_skills_search(args)

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.skills.search"


def test_skills_search_emits_entitlement_status_per_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Matching installed manifest entitlements annotate search results."""
    items = [
        {
            "course_id": "course-active",
            "id": "course-active",
            "title": "Active Course",
            "short_summary": "Summary",
        },
        {
            "course_id": "course-missing",
            "id": "course-missing",
            "title": "Missing Course",
            "short_summary": "Summary",
        },
    ]
    installed_manifests = [
        {"course_id": "course-active", "entitlement_status": "active"},
    ]
    listings = FakeListingsResource(items)
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))

    args = _make_args(target=tmp_path)
    with (
        patch(
            "cli.commands.skills._search_handler.make_client",
            return_value=fake,
        ),
        patch(
            "cli.commands.skills._search_handler.list_installed",
            return_value=installed_manifests,
        ),
        patch(
            "cli.commands.skills._search_handler.resolve_config_from_args"
        ) as mock_cfg,
        patch(
            "cli.commands.skills._search_handler.resolve_target",
            return_value=tmp_path,
        ),
    ):
        mock_cfg.return_value = argparse.Namespace(
            json_output=True,
            api_key=None,
            base_url="https://api.logion.dev",
            timeout=None,
            max_retries=None,
        )
        rc = handle_skills_search(args)

    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    result_items = data["data"]["items"]
    active_item = next(
        i for i in result_items if i["course_id"] == "course-active"
    )
    missing_item = next(
        i for i in result_items if i["course_id"] == "course-missing"
    )
    assert active_item["entitlement_status"] == "active"
    assert missing_item["entitlement_status"] == "missing"


def test_skills_search_result_without_course_id_stays_unknown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Do not infer entitlement from listing IDs when course_id is absent."""
    items = [
        {
            "id": "course-active",
            "title": "Listing Only",
            "short_summary": "Summary",
        },
    ]
    installed_manifests = [
        {"course_id": "course-active", "entitlement_status": "active"},
    ]
    listings = FakeListingsResource(items)
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))

    args = _make_args(target=tmp_path)
    with (
        patch(
            "cli.commands.skills._search_handler.make_client",
            return_value=fake,
        ),
        patch(
            "cli.commands.skills._search_handler.list_installed",
            return_value=installed_manifests,
        ),
        patch(
            "cli.commands.skills._search_handler.resolve_config_from_args"
        ) as mock_cfg,
        patch(
            "cli.commands.skills._search_handler.resolve_target",
            return_value=tmp_path,
        ),
    ):
        mock_cfg.return_value = argparse.Namespace(
            json_output=True,
            api_key=None,
            base_url="https://api.logion.dev",
            timeout=None,
            max_retries=None,
        )
        rc = handle_skills_search(args)

    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    result_item = data["data"]["items"][0]
    assert result_item["id"] == "course-active"
    assert result_item["entitlement_status"] == "unknown"


def test_skills_search_compact_default_truncates_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Long summaries are truncated via truncate_summary in human output."""
    long_summary = "A" * 200
    items = [
        {
            "course_id": "long-sum",
            "id": "long-sum",
            "title": "Long",
            "short_summary": long_summary,
        },
    ]
    listings = FakeListingsResource(items)
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))

    args = _make_args(target=tmp_path, json_output=False)
    with (
        patch(
            "cli.commands.skills._search_handler.make_client",
            return_value=fake,
        ),
        patch(
            "cli.commands.skills._search_handler.list_installed",
            return_value=[],
        ),
        patch(
            "cli.commands.skills._search_handler.resolve_config_from_args"
        ) as mock_cfg,
        patch(
            "cli.commands.skills._search_handler.resolve_target",
            return_value=tmp_path,
        ),
    ):
        mock_cfg.return_value = argparse.Namespace(
            json_output=False,
            api_key=None,
            base_url="https://api.logion.dev",
            timeout=None,
            max_retries=None,
        )
        rc = handle_skills_search(args)

    captured = capsys.readouterr()
    assert rc == 0
    truncated = truncate_summary(long_summary)
    assert truncated in captured.out
    assert len(truncated) < len(long_summary)


def test_skills_search_default_limit_is_five() -> None:
    """The --limit argument defaults to 5."""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    from cli.commands.skills.parser import register

    register(sub)
    args = parser.parse_args(["skills", "search", "my-query"])
    assert args.limit == 5
