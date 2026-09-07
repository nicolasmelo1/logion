# SPDX-License-Identifier: MIT
"""Handlers for portable eval creation and reproduction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path, PurePosixPath

from logion_eval_contract import (
    EvalContract,
    contract_to_json,
    parse_contract_file,
)
from logion_runner.evals import (
    execute_eval_contract,
)

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import emit_error_json
from cli._json import JsonObject, JsonValue
from cli._version import __version__ as cli_version

_BUNDLE_MEDIA_TYPE = "application/vnd.logion.eval-reproduction.v1+zip"
_HARNESS_ID = "logion-cli"
_MODEL_ID = "reference-subject"
_MODEL_VERSION = "1.0.0"
_EXIT_INVALID = 2
_EXIT_ERROR = 1
_EXIT_REFUSED = 3


def _safe_member(name: str) -> str:
    """Reject absolute and parent-traversing bundle member names."""
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe bundle member path: {name!r}")
    return path.as_posix()


def _fail(code: str, message: str, exit_code: int = _EXIT_INVALID) -> int:
    emit_error_json(code, message, exit_code)
    return exit_code


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: JsonValue) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _write(path: Path, raw: bytes, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(
            f"{path} already exists; pass --force to replace it"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _load_contract(path: str) -> EvalContract:
    return parse_contract_file(path)


def _execute(contract: EvalContract, subject: bytes, contract_path: str):
    return execute_eval_contract(
        contract,
        subject,
        harness_id=_HARNESS_ID,
        harness_version=cli_version,
        model_id=_MODEL_ID,
        model_version=_MODEL_VERSION,
        contract_dir=Path(contract_path).resolve().parent,
    )


def _runner_credentials(path: str | None) -> tuple[str, str]:
    if not path:
        raise ValueError("--publish requires --runner-credentials")
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("runner credentials must contain a JSON object")
    runner_id = payload.get("runner_id")
    runner_key = payload.get("runner_key")
    if not isinstance(runner_id, str) or not runner_id:
        raise ValueError("runner credentials are missing runner_id")
    if not isinstance(runner_key, str) or not runner_key:
        raise ValueError("runner credentials are missing runner_key")
    return runner_id, runner_key


def _publish_result(args, contract, job, result) -> JsonObject:
    """Publish through the handwritten SDK surfaces only."""
    runner_id, runner_key = _runner_credentials(args.runner_credentials)
    config = resolve_config_from_args(args)
    user_client = make_client(config)
    runner_client = make_client(replace(config, api_key=runner_key))
    try:
        uploaded = user_client.v1.evals.upload_contract(
            contract_to_json(contract)
        )
        remote_digest = uploaded.get("contract_digest")
        if remote_digest != job.contract_digest:
            raise ValueError("server and local contract digests differ")
        user_client.v1.evals.validate_job(
            job.contract_digest,
            job.subject_digest,
            {fixture.name: fixture.digest for fixture in contract.fixtures},
        )
        submitted_result = dict(result)
        submitted_result.pop("contract_standing", None)
        submitted = runner_client.v1.evals.submit_result(submitted_result)
    finally:
        runner_client.close()
        user_client.close()
    run_id = submitted.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("server returned no eval run id")
    return {
        "contract_digest": remote_digest,
        "run_id": run_id,
        "runner_id": runner_id,
        "standing": uploaded.get("standing"),
        "terminal_status": "succeeded",
    }


def _scaffold_documents() -> tuple[JsonObject, JsonObject]:
    subject: JsonObject = {
        "input": {
            "email": " CREATOR@EXAMPLE.COM ",
            "name": "  Example Creator ",
        },
        "expected": {
            "input": {
                "email": "creator@example.com",
                "name": "Example Creator",
            }
        },
    }
    subject_digest = _digest(_json_bytes(subject))
    contract: JsonObject = {
        "archetype": "exact_match",
        "assertions": [
            {
                "expected": 1,
                "id": "output_matches_golden",
                "metric": "cases_passed",
                "operator": "eq",
            }
        ],
        "budgets": [
            {"kind": "wall_seconds", "max_value": 60},
            {"kind": "output_bytes", "max_value": 1048576},
        ],
        "determinism_class": "deterministic",
        "evaluator_requirement": {"kind": "none"},
        "fixtures": [{"digest": subject_digest, "name": "subject.json"}],
        "inputs": ["subject.json"],
        "metrics": [
            {
                "direction": "higher_is_better",
                "id": "cases_passed",
                "kind": "count",
            }
        ],
        "outputs": [{"name": "result", "path": "outputs/result.json"}],
        "redaction": {"fields": ["secret", "token"], "mode": "drop"},
        "runtime_requirements": [
            {"kind": "sandbox_profile", "value": "pinned-image"}
        ],
        "schema_version": 1,
        "steps": [
            {
                "action": "execute_subject",
                "id": "run_subject",
                "params": {"entrypoint": "normalize", "input": "subject.json"},
            }
        ],
        "subject": {"digest_constraint": "exact", "type": "agent_skill"},
    }
    return contract, subject
