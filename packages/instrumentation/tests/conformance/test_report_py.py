# SPDX-License-Identifier: MIT
"""Conformance tests for the Python reporter binding (``report.py``).

Runs every test from the shared conformance suite against the Python
binding.  The Python binding is executed as a subprocess to test the
real stdin/exit-code contract.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conformance.suite import (
    ReporterResult,
)
from conformance.suite import (
    test_behavior_1_empty_stdin_exits_zero as _b1_empty,
)
from conformance.suite import (
    test_behavior_1_non_object_json_exits_zero as _b1_nonobj,
)
from conformance.suite import (
    test_behavior_1_parse_failure_exits_zero as _b1_parse,
)
from conformance.suite import (
    test_behavior_2_consent_off_exits_zero as _b2_off,
)
from conformance.suite import (
    test_behavior_2_dnt_env_exits_zero as _b2_dnt,
)
from conformance.suite import (
    test_behavior_2_dnt_false_allows as _b2_dnt_false,
)
from conformance.suite import (
    test_behavior_2_logion_dnt_env_exits_zero as _b2_ldnt,
)
from conformance.suite import (
    test_behavior_2_no_consent_exits_zero as _b2_no_consent,
)
from conformance.suite import (
    test_behavior_3_only_allowlisted_fields as _b3_allowlist,
)
from conformance.suite import (
    test_behavior_3_sensitive_keys_never_present as _b3_sensitive,
)
from conformance.suite import test_behavior_4_spool_is_bounded as _b4
from conformance.suite import (
    test_behavior_5_local_only_no_upload as _b5,
)
from conformance.suite import (
    test_behavior_6_allow_deduplicates as _b6,
)
from conformance.suite import (
    test_behavior_7_exit_zero_on_invalid_payload as _b7_bad_payload,
)
from conformance.suite import (
    test_behavior_7_exit_zero_on_missing_profile as _b7_no_profile,
)
from conformance.suite import (
    test_behavior_7_exit_zero_on_success as _b7_ok,
)
from conformance.suite import (
    test_prohibition_1_no_cli_exec as _p1,
)
from conformance.suite import (
    test_prohibition_2_no_credentials_in_event as _p2,
)
from conformance.suite import (
    test_prohibition_3_no_cross_resource_identifier as _p3,
)
from conformance.suite import (
    test_prohibition_4_no_inferred_use as _p4,
)
from conformance.suite import (
    test_prohibition_5_no_invented_outcome as _p5,
)
from conformance.suite import (
    test_subcommand_delete as _sub_delete,
)
from conformance.suite import (
    test_subcommand_disable as _sub_disable,
)
from conformance.suite import (
    test_subcommand_export as _sub_export,
)
from conformance.suite import (
    test_subcommand_pending as _sub_pending,
)
from conformance.suite import (
    test_subcommand_status as _sub_status,
)

_REPORT_PY = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "logion_instrumentation"
    / "reporter"
    / "report.py"
)


class PythonBinding:
    """Runs the Python reporter as a subprocess."""

    name = "python"

    def run_hook(
        self,
        payload: dict[str, object] | str | None,
        base: Path,
        env: dict[str, str] | None = None,
    ) -> ReporterResult:
        if payload is None:
            stdin_data = b""
        elif isinstance(payload, str):
            stdin_data = payload.encode("utf-8")
        else:
            stdin_data = json.dumps(payload).encode("utf-8")

        full_env = dict(os.environ)
        if env:
            full_env.update(env)

        proc = subprocess.run(
            [sys.executable, str(_REPORT_PY), "--base", str(base)],
            input=stdin_data,
            capture_output=True,
            timeout=10,
            env=full_env,
        )
        return ReporterResult(
            returncode=proc.returncode,
            stdout=proc.stdout.decode("utf-8", errors="replace"),
            stderr=proc.stderr.decode("utf-8", errors="replace"),
        )

    def run_subcommand(
        self,
        command: str,
        base: Path,
        env: dict[str, str] | None = None,
    ) -> ReporterResult:
        full_env = dict(os.environ)
        if env:
            full_env.update(env)

        proc = subprocess.run(
            [
                sys.executable,
                str(_REPORT_PY),
                command,
                "--base",
                str(base),
            ],
            capture_output=True,
            timeout=10,
            env=full_env,
        )
        return ReporterResult(
            returncode=proc.returncode,
            stdout=proc.stdout.decode("utf-8", errors="replace"),
            stderr=proc.stderr.decode("utf-8", errors="replace"),
        )


@pytest.fixture
def binding() -> PythonBinding:
    return PythonBinding()


# Re-export every conformance test with the Python binding fixture.


def test_behavior_1_parse_failure_exits_zero(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b1_parse(binding, tmp_path)


def test_behavior_1_empty_stdin_exits_zero(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b1_empty(binding, tmp_path)


def test_behavior_1_non_object_json_exits_zero(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b1_nonobj(binding, tmp_path)


def test_behavior_2_no_consent_exits_zero(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b2_no_consent(binding, tmp_path)


def test_behavior_2_consent_off_exits_zero(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b2_off(binding, tmp_path)


def test_behavior_2_dnt_env_exits_zero(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b2_dnt(binding, tmp_path)


def test_behavior_2_logion_dnt_env_exits_zero(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b2_ldnt(binding, tmp_path)


def test_behavior_2_dnt_false_allows(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b2_dnt_false(binding, tmp_path)


def test_behavior_3_only_allowlisted_fields(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b3_allowlist(binding, tmp_path)


def test_behavior_3_sensitive_keys_never_present(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b3_sensitive(binding, tmp_path)


def test_behavior_4_spool_is_bounded(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b4(binding, tmp_path)


def test_behavior_5_local_only_no_upload(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b5(binding, tmp_path)


def test_behavior_6_allow_deduplicates(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b6(binding, tmp_path)


def test_behavior_7_exit_zero_on_success(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b7_ok(binding, tmp_path)


def test_behavior_7_exit_zero_on_missing_profile(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b7_no_profile(binding, tmp_path)


def test_behavior_7_exit_zero_on_invalid_payload(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _b7_bad_payload(binding, tmp_path)


def test_prohibition_1_no_cli_exec(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _p1(binding, tmp_path)


def test_prohibition_2_no_credentials_in_event(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _p2(binding, tmp_path)


def test_prohibition_3_no_cross_resource_identifier(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _p3(binding, tmp_path)


def test_prohibition_4_no_inferred_use(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _p4(binding, tmp_path)


def test_prohibition_5_no_invented_outcome(
    binding: PythonBinding, tmp_path: Path
) -> None:
    _p5(binding, tmp_path)


def test_subcommand_status(binding: PythonBinding, tmp_path: Path) -> None:
    _sub_status(binding, tmp_path)


def test_subcommand_pending(binding: PythonBinding, tmp_path: Path) -> None:
    _sub_pending(binding, tmp_path)


def test_subcommand_export(binding: PythonBinding, tmp_path: Path) -> None:
    _sub_export(binding, tmp_path)


def test_subcommand_delete(binding: PythonBinding, tmp_path: Path) -> None:
    _sub_delete(binding, tmp_path)


def test_subcommand_disable(binding: PythonBinding, tmp_path: Path) -> None:
    _sub_disable(binding, tmp_path)
