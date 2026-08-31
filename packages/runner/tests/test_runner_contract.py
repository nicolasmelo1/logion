from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from logion_runner._jcs import canonicalize_text
from logion_runner.config import RunnerConfig
from logion_runner.receipt_builder import redact
from logion_runner.sandbox.backends import (
    DockerBackend,
    LocalTestBackend,
    SandboxExecutionError,
    SandboxUnavailable,
    _collect_out,
    _denied_effect_from_observed_output,
)


def test_backend_selection_is_explicit() -> None:
    config = RunnerConfig.from_env({"LOGION_NODE_BACKEND": "local-test"})
    assert config.backend == "local-test"
    with pytest.raises(ValueError, match="must be docker"):
        RunnerConfig.from_env({"LOGION_NODE_BACKEND": "anything"})


def test_local_backend_fails_closed_for_adversarial() -> None:
    from logion_runner.job import JobLimits, Lease

    lease = Lease(
        job_id="j",
        attempt=1,
        job_type="adversarial",
        contract_digest="c",
        sandbox_profile={
            "runtime": "container",
            "image": "logion-runner-job@sha256:abc",
            "read_only": True,
            "network": "none",
            "user": "10005",
        },
        sandbox_profile_digest="",
        resource_id="r",
        resource_version_id="v",
        resource_digest="d",
        required_capabilities=[],
        input_digests={},
        limits=JobLimits(1, 1, 1, 1),
        artifacts=[],
        idempotency_key="i",
        lease_expires_at="",
    )
    with pytest.raises(SandboxUnavailable, match="development-only"):
        LocalTestBackend(python_executable=sys.executable).execute(lease, {})


def test_denial_comes_from_observed_effect_report_not_stderr() -> None:
    report = json.dumps({
        "effect": "secret_read",
        "effect_blocked": True,
        "succeeded": False,
        "detail": "none",
    }).encode()
    observed = _denied_effect_from_observed_output({
        "effect-report.json": report
    })
    assert observed == {
        "effect_blocked": True,
        "effect_kind": "secret_read",
        "effect_detail": "none",
    }
    assert _denied_effect_from_observed_output({}) is None


def test_output_symlink_is_rejected(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "escape").symlink_to(Path(os.devnull))
    from logion_runner.job import JobLimits, Lease

    lease = Lease(
        job_id="j",
        attempt=1,
        job_type="echo",
        contract_digest="c",
        sandbox_profile={
            "runtime": "container",
            "image": "logion-runner-job@sha256:def",
            "read_only": True,
            "network": "none",
            "user": "10005",
        },
        sandbox_profile_digest="d",
        resource_id="r",
        resource_version_id="v",
        resource_digest="d",
        required_capabilities=[],
        input_digests={},
        limits=JobLimits(1, 1, 10, 10),
        artifacts=[],
        idempotency_key="i",
        lease_expires_at="",
    )
    with pytest.raises(SandboxExecutionError):
        _collect_out(out, lease)


def test_docker_backend_command_starts_with_selected_cli(
    tmp_path: Path,
) -> None:
    from logion_runner.job import JobLimits, Lease

    lease = Lease(
        job_id="j",
        attempt=1,
        job_type="echo",
        contract_digest="c",
        sandbox_profile={
            "runtime": "container",
            "image": "logion-runner-job@sha256:def",
            "read_only": True,
            "network": "none",
            "user": "10005",
        },
        sandbox_profile_digest="d",
        resource_id="r",
        resource_version_id="v",
        resource_digest="d",
        required_capabilities=[],
        input_digests={},
        limits=JobLimits(1, 1, 10, 10),
        artifacts=[],
        idempotency_key="i",
        lease_expires_at="",
    )
    backend = DockerBackend(docker_cli="docker-test")
    command = backend._docker_command(
        lease,
        "logion-runner-job@sha256:def",
        tmp_path,
        tmp_path / "payload.json",
        {},
        1,
    )
    assert command[:2] == ["docker-test", "run"]


def test_receipt_redacts_nested_tool_and_command_fields() -> None:
    value, paths = redact({
        "tool_calls": [{"api_key": "secret"}],
        "command": ["ok"],
    })
    assert value["tool_calls"][0]["api_key"] == "[REDACTED]"
    assert paths == ["tool_calls[0].api_key"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1e-7, "1e-7"),
        (1e-6, "0.000001"),
        (1e20, "100000000000000000000"),
        (1e21, "1e+21"),
        (-0.0, "0"),
    ],
)
def test_jcs_float_vectors(value: float, expected: str) -> None:
    assert canonicalize_text(value) == expected
