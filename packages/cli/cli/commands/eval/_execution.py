# SPDX-License-Identifier: MIT
"""Handlers for portable eval creation and reproduction."""

from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from pathlib import Path

import logion_eval_contract as eval_contract_package
import yaml
from logion_eval_contract import (
    EvalContractError,
    contract_digest,
    parse_result_document,
    result_digest,
)
from logion_runner.evals import (
    EvalExecutionError,
    resolve_eval_job,
)

from cli._output import emit_json
from cli.commands.eval._scaffold import (
    _digest,
    _execute,
    _fail,
    _json_bytes,
    _load_contract,
    _scaffold_documents,
    _write,
)


def _publish_result(args, contract, job, result):
    """Route publishing through the public module for testable clients."""
    from cli.commands.eval import handlers

    return handlers._publish_result(args, contract, job, result)


_BUNDLE_MEDIA_TYPE = "application/vnd.logion.eval-reproduction.v1+zip"
_HARNESS_ID = "logion-cli"
_MODEL_ID = "reference-subject"
_MODEL_VERSION = "1.0.0"
_EXIT_INVALID = 2
_EXIT_ERROR = 1
_EXIT_REFUSED = 3


def handle_eval_scaffold(args: argparse.Namespace) -> int:
    """Create a complete starter contract and subject."""
    directory = Path(args.directory)
    contract, subject = _scaffold_documents()
    try:
        _write(
            directory / "eval-contract.yaml",
            yaml.safe_dump(contract, sort_keys=False).encode(),
            force=args.force,
        )
        _write(
            directory / "subject.json",
            _json_bytes(subject),
            force=args.force,
        )
        parsed = _load_contract(str(directory / "eval-contract.yaml"))
    except (EvalContractError, OSError) as exc:
        return _fail("eval_scaffold_failed", str(exc))
    emit_json(
        "logion.eval.scaffold",
        {
            "contract": str(directory / "eval-contract.yaml"),
            "contract_digest": contract_digest(parsed),
            "subject": str(directory / "subject.json"),
        },
    )
    return 0


def handle_eval_validate(args: argparse.Namespace) -> int:
    """Validate a contract and resolve all declared fixtures."""
    try:
        contract = _load_contract(args.contract)
        base = Path(args.contract).resolve().parent
        fixture_digests: dict[str, str] = {}
        for fixture in contract.fixtures:
            raw = (base / fixture.name).read_bytes()
            actual = _digest(raw)
            if actual != fixture.digest:
                from logion_eval_contract import EvalFixtureDigestMismatch

                raise EvalFixtureDigestMismatch(
                    f"fixture {fixture.name!r} hashes to {actual},"
                    f" not {fixture.digest}"
                )
            fixture_digests[fixture.name] = actual
    except EvalContractError as exc:
        return _fail(exc.code, str(exc))
    except OSError as exc:
        return _fail("eval_fixture_unreadable", str(exc))
    emit_json(
        "logion.eval.validate",
        {
            "contract_digest": contract_digest(contract),
            "determinism_class": contract.determinism_class,
            "fixture_digests": fixture_digests,
            "valid": True,
            "validator_import_root": (
                "site-packages"
                if "site-packages" in str(eval_contract_package.__file__)
                else "source-tree"
            ),
            "validator_package_version": version("logion-eval-contract"),
        },
    )
    return 0


def handle_eval_run(args: argparse.Namespace) -> int:
    """Resolve inputs, execute the subject, and emit a normalized result."""
    try:
        contract = _load_contract(args.contract)
        subject = Path(args.subject).read_bytes()
        job = resolve_eval_job(
            contract,
            subject,
            contract_dir=Path(args.contract).resolve().parent,
        )
        outcome = _execute(contract, subject, args.contract)
        published = (
            _publish_result(args, contract, job, outcome.result_document)
            if args.publish
            else None
        )
        if args.output:
            _write(
                Path(args.output),
                _json_bytes(outcome.result_document),
                force=args.force,
            )
    except EvalContractError as exc:
        return _fail(exc.code, str(exc))
    except (OSError, FileExistsError, ValueError, json.JSONDecodeError) as exc:
        return _fail("eval_input_unreadable", str(exc))
    except EvalExecutionError as exc:
        return _fail("eval_execution_failed", str(exc), _EXIT_ERROR)
    emit_json(
        "logion.eval.run",
        {
            "assertion_outcomes": outcome.assertion_outcomes,
            "executed": True,
            "output": args.output,
            "resolved": {
                "contract_digest": job.contract_digest,
                "evaluator_digest": contract.evaluator_requirement.digest,
                "image": job.sandbox_profile["image"],
                "sandbox_profile_digest": job.sandbox_profile_digest,
                "subject_digest": job.subject_digest,
            },
            "result": outcome.result_document,
            "result_digest": result_digest(
                parse_result_document(outcome.result_document)
            ),
            "published": published,
        },
    )
    return 0
