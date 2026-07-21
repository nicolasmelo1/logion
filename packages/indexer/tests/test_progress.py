"""Tests for bounded, non-fatal indexer progress reporting."""

from __future__ import annotations

from logion_indexer.progress import RunProgress
from logion_indexer.pusher import RunStats
from logion_indexer.transport import FakeTransport, HttpResponse


def test_checkpoint_accepts_204_and_emits_jsonl(capsys) -> None:
    transport = FakeTransport()
    url = "https://api.example/v1/admin/indexing/runs/run-1/progress"
    transport.set_patch_response(url, HttpResponse(204, b""))

    RunProgress(
        transport, "https://api.example", "run-1", RunStats()
    ).checkpoint("discovering")

    output = capsys.readouterr().err
    assert output.startswith("indexer-progress {")
    assert "publish-error" not in output


def test_checkpoint_sanitizes_adapter_error_and_tolerates_transport_failure(
    capsys,
) -> None:
    progress = RunProgress(
        FakeTransport(), "https://api.example", "run-1", RunStats()
    )
    progress.adapter("smithery", 0, "bad\nresponse")
    progress.checkpoint("discovering")

    output = capsys.readouterr().err
    assert '"smithery": "bad response"' in output
    assert "publish-error" in output
