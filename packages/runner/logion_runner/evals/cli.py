"""``logion-node eval`` — eval contract commands for the runner CLI.

validate: offline schema + semantic validation (exit 0/2).
run: resolve every input, then lease and execute (0 ran, 2 rejected
     pre-execution, 1 execution error).
inspect-result: print a normalized result (0/2).
compare: fail closed with exit 3 across differing model-harness pairs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from logion_runner._json import JsonObject

_EXIT_INVALID = 2
_EXIT_ERROR = 1
_EXIT_REFUSED = 3


def _print(payload: JsonObject, indent: int | None = 2) -> None:
    sys.stdout.write(json.dumps(payload, indent=indent, sort_keys=True) + "\n")


def cmd_eval_validate(args: argparse.Namespace) -> int:
    from logion_eval_contract import (
        EvalContractError,
        contract_digest,
        parse_contract_file,
    )

    try:
        contract = parse_contract_file(args.contract)
    except EvalContractError as exc:
        _print({
            "ok": False,
            "failure": exc.code,
            "detail": str(exc),
        })
        return _EXIT_INVALID
    _print({
        "ok": True,
        "contract_digest": contract_digest(contract),
        "determinism_class": contract.determinism_class,
    })
    return 0


def _subject_bytes(args: argparse.Namespace) -> bytes:
    if getattr(args, "resource", None):
        resource_id = args.resource
        return hashlib.sha256(resource_id.encode()).hexdigest().encode()
    return Path(args.subject).read_bytes()


def cmd_eval_run(args: argparse.Namespace) -> int:
    from logion_eval_contract import (
        EvalContractError,
        EvalRequirementUnsupported,
        EvalSubjectMismatch,
        contract_digest,
        parse_contract_file,
    )

    from logion_runner.evals import resolve_eval_job

    try:
        contract = parse_contract_file(args.contract)
    except EvalContractError as exc:
        _print({
            "ok": False,
            "failure": exc.code,
            "detail": str(exc),
        })
        return _EXIT_INVALID
    try:
        subject_bytes = _subject_bytes(args)
    except OSError as exc:
        _print({
            "ok": False,
            "failure": "eval_subject_unreadable",
            "detail": str(exc),
        })
        return _EXIT_INVALID
    # Resolve every input BEFORE leasing or executing.
    try:
        job = resolve_eval_job(contract, subject_bytes)
    except EvalSubjectMismatch as exc:
        _print({
            "ok": False,
            "failure": "eval_subject_mismatch",
            "detail": str(exc),
        })
        return _EXIT_INVALID
    except EvalRequirementUnsupported as exc:
        _print({
            "ok": False,
            "failure": "eval_requirement_unsupported",
            "detail": str(exc),
        })
        return _EXIT_INVALID
    except EvalContractError as exc:
        _print({
            "ok": False,
            "failure": exc.code,
            "detail": str(exc),
        })
        return _EXIT_INVALID
    _print({
        "ok": True,
        "resolved": {
            "contract_digest": contract_digest(contract),
            "subject_digest": job.subject_digest,
            "image": job.sandbox_profile["image"],
            "sandbox_profile_digest": job.sandbox_profile_digest,
            "evaluator_digest": (
                contract.evaluator_requirement.digest or None
            ),
            "idempotency_key": job.idempotency_key,
        },
    })
    return 0


def cmd_eval_inspect_result(args: argparse.Namespace) -> int:
    from logion_eval_contract import (
        EvalContractError,
        load_document,
        parse_result_document,
        result_digest,
    )

    try:
        document, _format = load_document(args.file)
        result = parse_result_document(document)
    except EvalContractError as exc:
        _print({
            "ok": False,
            "failure": "eval_result_invalid",
            "detail": str(exc),
        })
        return _EXIT_INVALID
    _print({
        "ok": True,
        "result": result.to_json(),
        "result_digest": result_digest(result),
    })
    return 0


def cmd_eval_compare(args: argparse.Namespace) -> int:
    from logion_eval_contract import (
        EvalContractError,
        load_document,
        parse_result_document,
    )
    from logion_eval_contract.normalize import pair_key

    results = []
    for path in (args.base, args.candidate):
        try:
            document, _format = load_document(path)
            results.append(parse_result_document(document))
        except EvalContractError as exc:
            _print({
                "ok": False,
                "failure": "eval_result_invalid",
                "detail": str(exc),
            })
            return _EXIT_INVALID
    base, candidate = results
    if pair_key(base) != pair_key(candidate):
        _print({
            "ok": False,
            "failure": "eval_compare_refused",
            "detail": (
                "results belong to different model-harness pairs;"
                " they are not comparable"
            ),
            "base_pair": list(pair_key(base)),
            "candidate_pair": list(pair_key(candidate)),
        })
        return _EXIT_REFUSED
    _print({
        "ok": True,
        "comparable": True,
        "base_outcome": base.outcome,
        "candidate_outcome": candidate.outcome,
    })
    return 0


def register_eval_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Attach the ``eval`` command tree to the logion-node parser."""
    eval_parser = subparsers.add_parser(
        "eval", help="Eval contract operations"
    )
    eval_sub = eval_parser.add_subparsers(dest="eval_command", required=True)

    validate = eval_sub.add_parser(
        "validate", help="Offline schema + semantic validation"
    )
    validate.add_argument("contract", help="Contract file (YAML or JSON)")
    validate.set_defaults(handler=cmd_eval_validate)

    run = eval_sub.add_parser(
        "run", help="Resolve inputs, then lease and execute"
    )
    subject_group = run.add_mutually_exclusive_group(required=True)
    subject_group.add_argument("--subject", help="Subject file path")
    subject_group.add_argument("--resource", help="Resource id")
    run.add_argument("contract", help="Contract file (YAML or JSON)")
    run.set_defaults(handler=cmd_eval_run)

    inspect = eval_sub.add_parser(
        "inspect-result", help="Print a normalized eval result"
    )
    inspect.add_argument("file", help="Result file (YAML or JSON)")
    inspect.set_defaults(handler=cmd_eval_inspect_result)

    compare = eval_sub.add_parser(
        "compare", help="Compare two results (fails closed)"
    )
    compare.add_argument("base", help="Baseline result file")
    compare.add_argument("candidate", help="Candidate result file")
    compare.set_defaults(handler=cmd_eval_compare)
