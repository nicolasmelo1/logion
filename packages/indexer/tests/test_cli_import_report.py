# SPDX-License-Identifier: MIT
"""The crawl's own account of a run, and what it costs to ignore it.

An import report only helps if it reaches the operator: written where
they asked for it, and loud enough that a partial import cannot be
mistaken for a clean one.
"""

from __future__ import annotations

import argparse
import json

import pytest

from logion_indexer import cli
from logion_indexer.adapters.ai_catalog import AICatalogAdapter
from logion_indexer.config import IndexerConfig
from logion_indexer.dedup import DedupPlan, ResourceDedupPlan
from logion_indexer.transport import FakeTransport, HttpResponse

CATALOG_URL = "https://example.com/.well-known/ai-catalog.json"

GOOD_ENTRY = {
    "identifier": "urn:air:example.com:mcp:weather",
    "type": "application/mcp-server-card+json",
    "url": "https://api.example.com/mcp/weather",
}
MALFORMED_ENTRY = {
    "identifier": "urn:air:example.com:mcp:broken",
    "type": "application/mcp-server-card+json",
    "url": "https://api.example.com/mcp/broken",
    "data": {"inline": True},
}


@pytest.fixture
def catalog_crawl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the CLI at a fixed catalog with one unusable entry."""
    transport = FakeTransport()
    transport.set_response(
        CATALOG_URL,
        HttpResponse(
            200,
            json.dumps({
                "specVersion": "1.0",
                "host": {"displayName": "Test Host"},
                "entries": [GOOD_ENTRY, MALFORMED_ENTRY],
            }).encode("utf-8"),
        ),
    )
    monkeypatch.setattr(
        cli,
        "_get_adapter",
        lambda *_args, **_kwargs: AICatalogAdapter(transport=transport),
    )
    monkeypatch.setattr(cli, "_build_transport", lambda _config: transport)
    # The plan is the API's answer, not this test's subject.
    monkeypatch.setattr(
        cli,
        "build_indexing_plan",
        lambda *_a, **_k: (DedupPlan(), None),
    )
    monkeypatch.setattr(
        cli,
        "build_resource_indexing_plan",
        lambda resources, *_a, **_k: ResourceDedupPlan(create=list(resources)),
    )


def _args(**overrides: object) -> argparse.Namespace:
    base = {
        "out": None,
        "json": False,
        "adapter": "ai-catalog",
        "entrypoint": CATALOG_URL,
        "report": None,
        "allow_quarantine": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


@pytest.mark.usefixtures("catalog_crawl")
def test_quarantine_makes_the_crawl_exit_non_zero() -> None:
    # A crawl that dropped an entry and exits 0 teaches every caller
    # above it that a partial import is normal.
    assert cli.cmd_crawl(IndexerConfig(), _args()) == 2


@pytest.mark.usefixtures("catalog_crawl")
def test_allow_quarantine_is_how_you_accept_a_partial_import() -> None:
    assert cli.cmd_crawl(IndexerConfig(), _args(allow_quarantine=True)) == 0


@pytest.mark.usefixtures("catalog_crawl")
def test_report_records_what_the_source_offered(tmp_path) -> None:
    path = tmp_path / "crawl.json"

    cli.cmd_crawl(IndexerConfig(), _args(report=str(path)))
    report = json.loads(path.read_text())

    # seen counts the entries the document offered, importable or not:
    # without it a source that stopped publishing half its catalog
    # reads exactly like one that never had those entries.
    assert report["seen"] == 2
    assert report["created"] == 1
    assert report["quarantined"] == 1
    assert report["errors_by_code"] == {"ai_catalog_entry_invalid": 1}
    assert report["source"] == CATALOG_URL


@pytest.mark.usefixtures("catalog_crawl")
def test_catalog_entry_never_mints_a_version(tmp_path) -> None:
    # An AI Catalog entry is a selection descriptor. The report counts
    # this from the plan rather than hardcoding zero, so a plan that
    # started carrying bundles would show up here instead of hiding.
    path = tmp_path / "crawl.json"

    cli.cmd_crawl(IndexerConfig(), _args(report=str(path)))

    assert json.loads(path.read_text())["new_versions"] == 0


@pytest.mark.usefixtures("catalog_crawl")
def test_summary_reaches_stdout_without_being_asked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.cmd_crawl(IndexerConfig(), _args())

    out = capsys.readouterr().out
    assert "quarantined: 1" in out
    assert "ai_catalog_entry_invalid: 1" in out
