# SPDX-License-Identifier: MIT
"""What the discovery commands put in their JSON, and why it matters.

Both outputs are read by something other than a human: a saved search
is the record that a hit came from a named registry with a
registry-supplied score, and a saved finder run is the record that a
finder was queried at all. A projection that keeps only the names
looks fine and proves neither.
"""

from __future__ import annotations

import argparse
import json

import pytest

from logion_indexer import cli
from logion_indexer.config import IndexerConfig
from logion_indexer.transport import FakeTransport, HttpResponse

REGISTRY = "https://registry.example.com"
SEARCH_URL = f"{REGISTRY}/search"

SEARCH_RESPONSE = {
    "results": [
        {
            "identifier": "urn:air:acme.com:agent:assistant",
            "displayName": "Corporate Assistant",
            "type": "application/a2a-agent-card+json",
            "url": "https://api.acme.com/agents/assistant.json",
            "score": 95,
            "source": "https://registry.acme.com/api/v1/",
        }
    ],
    "referrals": [],
    "pageToken": None,
}


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = FakeTransport()
    transport.set_post_response(
        SEARCH_URL,
        HttpResponse(200, json.dumps(SEARCH_RESPONSE).encode("utf-8")),
    )
    monkeypatch.setattr(cli, "_build_transport", lambda _config: transport)


def _search_output(capsys: pytest.CaptureFixture[str]) -> dict:
    return json.loads(capsys.readouterr().out)


@pytest.mark.usefixtures("registry")
def test_search_json_names_the_registry_that_answered(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.cmd_search(
        IndexerConfig(),
        argparse.Namespace(
            registry=REGISTRY,
            query="assistant",
            page_size=10,
            json=True,
            adapter="ard",
        ),
    )

    payload = _search_output(capsys)
    assert payload["registry"]["origin"] == REGISTRY
    assert payload["query"]["text"] == "assistant"


@pytest.mark.usefixtures("registry")
def test_search_json_carries_the_registry_supplied_score(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.cmd_search(
        IndexerConfig(),
        argparse.Namespace(
            registry=REGISTRY,
            query="assistant",
            page_size=10,
            json=True,
            adapter="ard",
        ),
    )

    hit = _search_output(capsys)["results"][0]
    # Registry-supplied metadata, never Logion's judgement -- but a
    # reader cannot check that claim against an output that dropped it.
    assert hit["score"] == "95"
    assert hit["source"] == "https://registry.acme.com/api/v1/"


class _Record:
    finder_id = "finder-a"
    endpoint = "https://finder.example.com/search"
    snapshot_commit = "abc123"
    query_text_digest = "sha256:deadbeef"
    result_identifiers = ("urn:air:example.com:mcp:weather",)
    relevance_scores = (("urn:air:example.com:mcp:weather", 90),)
    error = None


class _FinderResult:
    resources = ()
    records = (_Record(),)
    referrals = ()
    errors = ()


def test_dry_run_still_reports_as_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # --dry-run means "do not commit", not "do not report". It used to
    # return before the --json branch, so every caller parsing a
    # dry-run got three lines of prose.
    cli._print_agent_finders_json(_FinderResult(), dry_run=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["finder_count"] == 1
    assert payload["records"][0]["finder_id"] == "finder-a"
    assert payload["records"][0]["endpoint"].startswith("https://")
