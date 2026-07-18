"""Regression tests for CLI partial-state and push diagnostics."""

from __future__ import annotations

import argparse
import json

from logion_indexer import cli
from logion_indexer.canonical import CanonicalSkillId
from logion_indexer.config import IndexerConfig
from logion_indexer.dedup import DedupPlan
from logion_indexer.models import DiscoveredSkill
from logion_indexer.pusher import PushResult
from logion_indexer.transport import FakeTransport


def test_run_parser_accepts_link_only() -> None:
    args = cli.build_parser().parse_args(["run", "--link-only"])

    assert args.command == "run"
    assert args.link_only is True


class _FailingAdapter:
    def discover(self, target: str, **kwargs: object):  # noqa: ARG002
        raise TimeoutError("request timed out")
        yield  # pragma: no cover


def test_adapter_failure_marks_crawl_plan_and_run_partial(
    tmp_path, monkeypatch, capsys
) -> None:
    seed = tmp_path / "sources.yaml"
    seed.write_text(
        "version: 1\nsources:\n  - adapter: github_direct\n"
        "    target: https://github.com/example/repo\n"
    )
    config = IndexerConfig(seed_file=str(seed), dry_run=True)
    monkeypatch.setattr(cli, "_get_adapter", lambda *_args: _FailingAdapter())

    crawl_args = argparse.Namespace(out=None, json=True)
    assert cli.cmd_crawl(config, crawl_args) == 0
    crawl_output = capsys.readouterr()
    assert json.loads(crawl_output.out)["partial"] is True
    assert "adapter github_direct error: request timed out" in crawl_output.err

    assert cli.cmd_run(config, argparse.Namespace()) == 1
    run_output = capsys.readouterr()
    assert "partial=yes" in run_output.out
    assert "adapter github_direct error: request timed out" in run_output.err


def test_adapter_construction_failure_marks_run_partial(
    tmp_path, monkeypatch, capsys
) -> None:
    seed = tmp_path / "sources.yaml"
    seed.write_text(
        "version: 1\nsources:\n  - adapter: unavailable\n"
        "    target: https://example.com/skills\n"
    )
    config = IndexerConfig(seed_file=str(seed), dry_run=True)

    def _raise_during_construction(*_args):
        raise ImportError("adapter dependency unavailable")

    monkeypatch.setattr(cli, "_get_adapter", _raise_during_construction)

    assert cli.cmd_run(config, argparse.Namespace()) == 1
    output = capsys.readouterr()
    assert "partial=yes" in output.out
    expected = "adapter unavailable error: adapter dependency unavailable"
    assert expected in output.err


def test_cmd_run_prints_safe_push_error_details(monkeypatch, capsys) -> None:
    secret = "ghp_super_secret_token"
    skill = DiscoveredSkill(
        canonical=CanonicalSkillId(owner="octocat", repo="broken")
    )

    class _FailingPusher:
        def __init__(self, _transport, _base_url):
            pass

        def open_run(self) -> str:
            return "run-1"

        def push_batch(self, items, *, run_id):  # noqa: ARG002
            return PushResult(
                errors=1,
                error_details=[
                    {
                        "canonical": "gh:octocat/broken",
                        "status": "error",
                        "error": f"rejected Bearer {secret}",
                        "body": f'{{"token":"{secret}"}}',
                    }
                ],
            )

        def close_run(self, _stats):
            pass

    monkeypatch.setattr(
        cli, "_build_transport", lambda _config: FakeTransport()
    )
    monkeypatch.setattr(
        cli,
        "_discover_all",
        lambda _config, _transport: cli.DiscoveryResult([skill]),
    )
    monkeypatch.setattr(
        cli,
        "build_indexing_plan",
        lambda _discoveries, _transport, _base_url, **_kwargs: (
            DedupPlan(create=[skill]),
            {},
        ),
    )
    monkeypatch.setattr(cli, "Pusher", _FailingPusher)

    config = IndexerConfig(github_token=secret)
    assert cli.cmd_run(config, argparse.Namespace()) == 1
    output = capsys.readouterr()
    assert "canonical=gh:octocat/broken" in output.err
    assert "status=error" in output.err
    assert "error=rejected Bearer [redacted]" in output.err
    assert 'body={"token":"[redacted]"}' in output.err
    assert secret not in output.err


def test_push_error_details_are_bounded(capsys) -> None:
    details = [
        {"canonical": f"gh:octocat/broken-{index}", "status": "error"}
        for index in range(25)
    ]

    cli._print_push_errors(
        PushResult(errors=len(details), error_details=details),
        IndexerConfig(),
    )

    output = capsys.readouterr()
    assert output.err.count("push error: canonical=") == 20
    assert "canonical=gh:octocat/broken-19" in output.err
    assert "canonical=gh:octocat/broken-20" not in output.err
    assert "push errors: omitted=5 additional details" in output.err
