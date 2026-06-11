# SPDX-License-Identifier: MIT
"""Tests for offline CLI documentation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cli.main import main

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_docs_lists_articles(capsys: pytest.CaptureFixture) -> None:
    assert main(["docs"]) == 0
    output = capsys.readouterr().out
    assert "concepts" in output
    assert "credits-terms" in output
    assert "reviews" in output


def test_docs_prints_article(capsys: pytest.CaptureFixture) -> None:
    assert main(["docs", "concepts"]) == 0
    output = capsys.readouterr().out
    assert output.startswith("# Core Concepts")
    assert "A course is a versioned package" in output


def test_docs_article_json(capsys: pytest.CaptureFixture) -> None:
    assert main(["docs", "reviews", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.docs.article"
    assert payload["data"]["slug"] == "reviews"
    assert "automatically" in payload["data"]["content"]


def test_docs_search(capsys: pytest.CaptureFixture) -> None:
    assert main(["docs", "search", "explicit", "approval"]) == 0
    output = capsys.readouterr().out
    assert "credits-and-purchases" in output


def test_docs_search_json(capsys: pytest.CaptureFixture) -> None:
    assert main(["docs", "search", "Stripe", "Connect", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.docs.search"
    assert payload["data"]["total"] > 0


def test_docs_search_matches_any_query_term(
    capsys: pytest.CaptureFixture,
) -> None:
    assert main(["docs", "search", "credits", "reviews", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    slugs = {match["slug"] for match in payload["data"]["matches"]}
    assert "credits-and-purchases" in slugs
    assert "reviews" in slugs


def test_docs_unknown_article_suggests_match(
    capsys: pytest.CaptureFixture,
) -> None:
    assert main(["docs", "concept"]) == 2
    error = capsys.readouterr().err
    assert "Unknown documentation article" in error
    assert "concepts" in error


def test_bundled_docs_match_repository_sources() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "packages/cli/scripts/sync_docs.py"),
            "--check",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0
