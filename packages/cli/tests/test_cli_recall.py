"""Tests for the ``logion recall`` command group."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli._local_state import (
    ensure_layout,
    record_workflow_success,
)
from cli.main import main


def _seed_workflow(home: Path) -> None:
    record_workflow_success(
        workflow_id="verify-companion",
        title="Verify companion package",
        commands=["make -C packages/agent-companion verify"],
        home=ensure_layout(home),
    )


class TestRecallSearch:
    def test_search_returns_matches(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        _seed_workflow(home)
        rc = main([
            "recall",
            "search",
            "verify",
            "--target",
            str(home),
        ])
        captured = capsys.readouterr()
        assert rc == 0
        assert "verify-companion" in captured.out

    def test_search_no_matches(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        ensure_layout(home)
        rc = main([
            "recall",
            "search",
            "nonexistent",
            "--target",
            str(home),
        ])
        captured = capsys.readouterr()
        assert rc == 0
        assert "No recall matches" in captured.out

    def test_search_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        _seed_workflow(home)
        rc = main([
            "recall",
            "search",
            "verify",
            "--target",
            str(home),
            "--json",
        ])
        captured = capsys.readouterr()
        assert rc == 0
        data = json.loads(captured.out)
        assert any(e["id"] == "verify-companion" for e in data["data"])


class TestRecallRecord:
    def test_record_persists_workflow(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        rc = main([
            "recall",
            "record",
            "--id",
            "deploy",
            "--title",
            "Deploy service",
            "--command",
            "./deploy.sh",
            "--target",
            str(home),
        ])
        captured = capsys.readouterr()
        assert rc == 0
        record = json.loads(captured.out)
        assert record["data"]["id"] == "deploy"
        assert record["data"]["success_count"] == 1

    def test_record_requires_command(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        rc = main([
            "recall",
            "record",
            "--id",
            "x",
            "--title",
            "X",
            "--target",
            str(home),
        ])
        captured = capsys.readouterr()
        assert rc == 2
        assert "at least one --command" in captured.err

    def test_record_increments_success_count(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        home = tmp_path / "home"
        for _ in range(3):
            main([
                "recall",
                "record",
                "--id",
                "x",
                "--title",
                "X",
                "--command",
                "echo x",
                "--target",
                str(home),
            ])
            capsys.readouterr()
        rc = main([
            "recall",
            "search",
            "x",
            "--target",
            str(home),
            "--json",
        ])
        captured = capsys.readouterr()
        assert rc == 0
        data = json.loads(captured.out)
        match = next(e for e in data["data"] if e["id"] == "x")
        assert match["success_count"] == 3
