# SPDX-License-Identifier: MIT
"""Conformance tests for the Node reporter binding (``report.mjs``).

Runs every test from the shared conformance suite against the Node
binding.  The Node binding is executed as a subprocess to test the
real stdin/exit-code contract.

If Node is not available, all tests are skipped (runtime-absent case).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conformance.suite import (
    ReporterResult,
)
from tests.conformance.suite import (
    test_behavior_1_empty_stdin_exits_zero as _b1_empty,
)
from tests.conformance.suite import (
    test_behavior_1_non_object_json_exits_zero as _b1_nonobj,
)
from tests.conformance.suite import (
    test_behavior_1_parse_failure_exits_zero as _b1_parse,
)
from tests.conformance.suite import (
    test_behavior_2_consent_off_exits_zero as _b2_off,
)
from tests.conformance.suite import (
    test_behavior_2_dnt_env_exits_zero as _b2_dnt,
)
from tests.conformance.suite import (
    test_behavior_2_dnt_false_allows as _b2_dnt_false,
)
from tests.conformance.suite import (
    test_behavior_2_logion_dnt_env_exits_zero as _b2_ldnt,
)
from tests.conformance.suite import (
    test_behavior_2_no_consent_exits_zero as _b2_no_consent,
)
from tests.conformance.suite import (
    test_behavior_3_only_allowlisted_fields as _b3_allowlist,
)
from tests.conformance.suite import (
    test_behavior_3_sensitive_keys_never_present as _b3_sensitive,
)
from tests.conformance.suite import test_behavior_4_spool_is_bounded as _b4
from tests.conformance.suite import (
    test_behavior_5_local_only_no_upload as _b5,
)
from tests.conformance.suite import (
    test_behavior_6_allow_deduplicates as _b6,
)
from tests.conformance.suite import (
    test_behavior_7_exit_zero_on_invalid_payload as _b7_bad_payload,
)
from tests.conformance.suite import (
    test_behavior_7_exit_zero_on_missing_profile as _b7_no_profile,
)
from tests.conformance.suite import (
    test_behavior_7_exit_zero_on_success as _b7_ok,
)
from tests.conformance.suite import (
    test_prohibition_1_no_cli_exec as _p1,
)
from tests.conformance.suite import (
    test_prohibition_2_no_credentials_in_event as _p2,
)
from tests.conformance.suite import (
    test_prohibition_3_no_cross_resource_identifier as _p3,
)
from tests.conformance.suite import (
    test_prohibition_4_no_inferred_use as _p4,
)
from tests.conformance.suite import (
    test_prohibition_5_no_invented_outcome as _p5,
)
from tests.conformance.suite import (
    test_subcommand_delete as _sub_delete,
)
from tests.conformance.suite import (
    test_subcommand_disable as _sub_disable,
)
from tests.conformance.suite import (
    test_subcommand_export as _sub_export,
)
from tests.conformance.suite import (
    test_subcommand_pending as _sub_pending,
)
from tests.conformance.suite import (
    test_subcommand_status as _sub_status,
)

_REPORT_MJS = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "logion_instrumentation"
    / "reporter"
    / "report.mjs"
)

_NODE = shutil.which("node")
_SKIP = _NODE is None


class NodeBinding:
    """Runs the Node reporter as a subprocess."""

    name = "node"

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
            [_NODE or "node", str(_REPORT_MJS), "--base", str(base)],
            input=stdin_data,
            capture_output=True,
            timeout=15,
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
                _NODE or "node",
                str(_REPORT_MJS),
                command,
                "--base",
                str(base),
            ],
            capture_output=True,
            timeout=15,
            env=full_env,
        )
        return ReporterResult(
            returncode=proc.returncode,
            stdout=proc.stdout.decode("utf-8", errors="replace"),
            stderr=proc.stderr.decode("utf-8", errors="replace"),
        )


@pytest.fixture
def binding() -> NodeBinding:
    return NodeBinding()


pytestmark = pytest.mark.skipif(
    _SKIP,
    reason="Node.js runtime not available — runtime-absent case",
)


def test_behavior_1_parse_failure_exits_zero(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b1_parse(binding, tmp_path)


def test_behavior_1_empty_stdin_exits_zero(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b1_empty(binding, tmp_path)


def test_behavior_1_non_object_json_exits_zero(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b1_nonobj(binding, tmp_path)


def test_behavior_2_no_consent_exits_zero(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b2_no_consent(binding, tmp_path)


def test_behavior_2_consent_off_exits_zero(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b2_off(binding, tmp_path)


def test_behavior_2_dnt_env_exits_zero(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b2_dnt(binding, tmp_path)


def test_behavior_2_logion_dnt_env_exits_zero(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b2_ldnt(binding, tmp_path)


def test_behavior_2_dnt_false_allows(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b2_dnt_false(binding, tmp_path)


def test_behavior_3_only_allowlisted_fields(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b3_allowlist(binding, tmp_path)


def test_behavior_3_sensitive_keys_never_present(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b3_sensitive(binding, tmp_path)


def test_behavior_4_spool_is_bounded(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b4(binding, tmp_path)


def test_behavior_5_local_only_no_upload(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b5(binding, tmp_path)


def test_behavior_6_allow_deduplicates(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b6(binding, tmp_path)


def test_behavior_7_exit_zero_on_success(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b7_ok(binding, tmp_path)


def test_behavior_7_exit_zero_on_missing_profile(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b7_no_profile(binding, tmp_path)


def test_behavior_7_exit_zero_on_invalid_payload(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _b7_bad_payload(binding, tmp_path)


def test_prohibition_1_no_cli_exec(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _p1(binding, tmp_path)


def test_prohibition_2_no_credentials_in_event(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _p2(binding, tmp_path)


def test_prohibition_3_no_cross_resource_identifier(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _p3(binding, tmp_path)


def test_prohibition_4_no_inferred_use(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _p4(binding, tmp_path)


def test_prohibition_5_no_invented_outcome(
    binding: NodeBinding, tmp_path: Path
) -> None:
    _p5(binding, tmp_path)


def test_subcommand_status(binding: NodeBinding, tmp_path: Path) -> None:
    _sub_status(binding, tmp_path)


def test_subcommand_pending(binding: NodeBinding, tmp_path: Path) -> None:
    _sub_pending(binding, tmp_path)


def test_subcommand_export(binding: NodeBinding, tmp_path: Path) -> None:
    _sub_export(binding, tmp_path)


def test_subcommand_delete(binding: NodeBinding, tmp_path: Path) -> None:
    _sub_delete(binding, tmp_path)


def test_subcommand_disable(binding: NodeBinding, tmp_path: Path) -> None:
    _sub_disable(binding, tmp_path)
