# SPDX-License-Identifier: MIT
"""Handlers for portable eval creation and reproduction."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from logion_eval_contract import (
    EvalContract,
    EvalContractError,
    contract_digest,
    contract_to_json,
    load_document,
    pair_key,
    parse_result_document,
    result_digest,
)

from cli._json import JsonObject
from cli._output import emit_json
from cli._version import __version__ as cli_version
from cli.commands.eval._scaffold import (
    _BUNDLE_MEDIA_TYPE,
    _digest,
    _fail,
    _json_bytes,
    _load_contract,
    _safe_member,
)

_HARNESS_ID = "logion-cli"
_MODEL_ID = "reference-subject"
_MODEL_VERSION = "1.0.0"
_EXIT_INVALID = 2
_EXIT_ERROR = 1
_EXIT_REFUSED = 3


def _bundle_manifest(
    contract: EvalContract,
    subject: bytes,
    fixture_entries: dict[str, JsonObject],
    result_entries: list[JsonObject],
) -> JsonObject:
    contract_bytes = _json_bytes(contract_to_json(contract))
    return {
        "contract": {
            "contract_digest": contract_digest(contract),
            "digest": _digest(contract_bytes),
            "path": "contract.json",
        },
        "fixtures": fixture_entries,
        "harness": {"id": _HARNESS_ID, "version": cli_version},
        "media_type": _BUNDLE_MEDIA_TYPE,
        "results": result_entries,
        "schema_version": 1,
        "subject": {"digest": _digest(subject), "path": "subject.bin"},
    }


def _checked_results(
    paths: list[str], contract: EvalContract, subject: bytes
) -> tuple[list[tuple[str, bytes]], list[JsonObject]]:
    if len(paths) < 2:
        raise ValueError("export requires at least two --result files")
    files: list[tuple[str, bytes]] = []
    entries: list[JsonObject] = []
    parsed = []
    for index, path in enumerate(paths, start=1):
        document, _ = load_document(path)
        result = parse_result_document(document)
        if result.contract_digest != contract_digest(contract):
            raise ValueError(f"result {path!r} belongs to another contract")
        if result.subject_digest != _digest(subject):
            raise ValueError(f"result {path!r} belongs to another subject")
        member = f"results/result-{index}.json"
        raw = _json_bytes(result.to_json())
        files.append((member, raw))
        entries.append({
            "digest": _digest(raw),
            "path": member,
            "result_digest": result_digest(result),
        })
        parsed.append(result)
    if any(pair_key(item) != pair_key(parsed[0]) for item in parsed[1:]):
        raise ValueError("results belong to different execution environments")
    if (
        contract.determinism_class == "deterministic"
        and len({result_digest(item) for item in parsed}) != 1
    ):
        raise ValueError("deterministic run results do not match")
    return files, entries


def _require_fixture_digest(raw: bytes, name: str, expected: str) -> None:
    if _digest(raw) != expected:
        raise ValueError(f"fixture {name!r} digest mismatch")


def handle_eval_export(args: argparse.Namespace) -> int:
    """Package the contract, fixtures, subject, and run evidence."""
    output = Path(args.output)
    try:
        if output.exists() and not args.force:
            raise FileExistsError(
                f"{output} already exists; pass --force to replace it"
            )
        contract = _load_contract(args.contract)
        subject = Path(args.subject).read_bytes()
        result_files, result_entries = _checked_results(
            args.result, contract, subject
        )
        base = Path(args.contract).resolve().parent
        fixture_files: list[tuple[str, bytes]] = []
        fixture_entries: dict[str, JsonObject] = {}
        for fixture in contract.fixtures:
            name = _safe_member(fixture.name)
            raw = (base / fixture.name).read_bytes()
            _require_fixture_digest(raw, fixture.name, fixture.digest)
            member = f"fixtures/{name}"
            fixture_files.append((member, raw))
            fixture_entries[fixture.name] = {
                "digest": fixture.digest,
                "path": member,
            }
        manifest = _bundle_manifest(
            contract, subject, fixture_entries, result_entries
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", _json_bytes(manifest))
            archive.writestr(
                "contract.json", _json_bytes(contract_to_json(contract))
            )
            archive.writestr("subject.bin", subject)
            for member, raw in [*fixture_files, *result_files]:
                archive.writestr(member, raw)
    except EvalContractError as exc:
        return _fail(exc.code, str(exc))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        return _fail("eval_bundle_invalid", str(exc))
    emit_json(
        "logion.eval.export",
        {
            "bundle": str(output),
            "bundle_digest": _digest(output.read_bytes()),
            "contract_digest": contract_digest(contract),
            "result_count": len(result_entries),
        },
    )
    return 0
