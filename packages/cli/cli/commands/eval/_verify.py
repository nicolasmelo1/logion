# SPDX-License-Identifier: MIT
"""Handlers for portable eval creation and reproduction."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from logion_eval_contract import (
    EvalContract,
    EvalContractError,
    contract_digest,
    load_document,
    parse_contract_document,
    parse_result_document,
    result_digest,
)
from logion_runner.evals import (
    EvalExecutionError,
)

from cli._json import JsonObject
from cli._output import emit_json
from cli.commands.eval._bundle import _safe_member
from cli.commands.eval._scaffold import (
    _BUNDLE_MEDIA_TYPE,
    _digest,
    _execute,
    _fail,
    _load_contract,
)

_HARNESS_ID = "logion-cli"
_MODEL_ID = "reference-subject"
_MODEL_VERSION = "1.0.0"
_EXIT_INVALID = 2
_EXIT_ERROR = 1
_EXIT_REFUSED = 3


def _object(raw: bytes, where: str) -> JsonObject:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError(f"{where} must contain a JSON object")
    return value


def _entry(manifest: JsonObject, name: str) -> JsonObject:
    value = manifest.get(name)
    if not isinstance(value, dict):
        raise TypeError(f"bundle manifest {name!r} must be an object")
    return value


def _text(entry: JsonObject, name: str) -> str:
    value = entry.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"bundle manifest field {name!r} must be text")
    return value


def _read_member(
    archive: zipfile.ZipFile, entry: JsonObject, label: str
) -> bytes:
    path = _safe_member(_text(entry, "path"))
    raw = archive.read(path)
    if _digest(raw) != _text(entry, "digest"):
        raise ValueError(f"bundle {label} digest mismatch")
    return raw


def _open_bundle(path: str):
    archive = zipfile.ZipFile(path)
    manifest = _object(archive.read("manifest.json"), "manifest.json")
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported bundle schema_version")
    if manifest.get("media_type") != _BUNDLE_MEDIA_TYPE:
        raise ValueError("unsupported bundle media_type")
    return archive, manifest


def _materialize_fixtures(
    archive: zipfile.ZipFile,
    manifest: JsonObject,
    contract: EvalContract,
    root: Path,
) -> None:
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, dict):
        raise TypeError("bundle manifest fixtures must be an object")
    for fixture in contract.fixtures:
        raw_entry = fixtures.get(fixture.name)
        if not isinstance(raw_entry, dict):
            raise TypeError(f"missing bundled fixture {fixture.name!r}")
        raw = _read_member(archive, raw_entry, fixture.name)
        target = root / _safe_member(fixture.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def _expected_result_digests(
    archive: zipfile.ZipFile, manifest: JsonObject
) -> list[str]:
    entries = manifest.get("results")
    if not isinstance(entries, list) or len(entries) < 2:
        raise ValueError("bundle must contain at least two results")
    expected = []
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, dict):
            raise TypeError("bundle result entry must be an object")
        raw = _read_member(archive, raw_entry, f"result {index + 1}")
        result = parse_result_document(_object(raw, "result"))
        digest = result_digest(result)
        if digest != _text(raw_entry, "result_digest"):
            raise ValueError(f"bundle result {index + 1} digest mismatch")
        expected.append(digest)
    return expected


def _require_contract_digest(
    contract: EvalContract, manifest_entry: JsonObject
) -> None:
    if contract_digest(contract) != _text(manifest_entry, "contract_digest"):
        raise ValueError("bundle contract semantic digest mismatch")


def handle_eval_verify(args: argparse.Namespace) -> int:
    """Reproduce a bundle twice in a clean temporary workspace."""
    try:
        archive, manifest = _open_bundle(args.bundle)
        with archive, tempfile.TemporaryDirectory() as temp:
            contract_raw = _read_member(
                archive, _entry(manifest, "contract"), "contract"
            )
            subject = _read_member(
                archive, _entry(manifest, "subject"), "subject"
            )
            root = Path(temp)
            contract_path = root / "contract.json"
            contract_path.write_bytes(contract_raw)
            contract = _load_contract(str(contract_path))
            _require_contract_digest(contract, _entry(manifest, "contract"))
            _materialize_fixtures(archive, manifest, contract, root)
            expected = _expected_result_digests(archive, manifest)
            first = _execute(contract, subject, str(contract_path))
            second = _execute(contract, subject, str(contract_path))
            actual = [
                result_digest(parse_result_document(outcome.result_document))
                for outcome in (first, second)
            ]
            if len(set(actual)) != 1 or set(actual) != set(expected):
                return _fail(
                    "eval_reproduction_mismatch",
                    "clean-workspace runs do not match the exported results",
                    _EXIT_REFUSED,
                )
    except EvalContractError as exc:
        return _fail(exc.code, str(exc))
    except EvalExecutionError as exc:
        return _fail("eval_execution_failed", str(exc), _EXIT_ERROR)
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        return _fail("eval_bundle_invalid", str(exc))
    emit_json(
        "logion.eval.verify",
        {
            "bundle": args.bundle,
            "contract_digest": contract_digest(contract),
            "reproduced": True,
            "result_digest": actual[0],
            "runs": 2,
        },
    )
    return 0


def handle_eval_inspect(args: argparse.Namespace) -> int:
    """Inspect a result or bundle without executing it."""
    try:
        if zipfile.is_zipfile(args.artifact):
            archive, manifest = _open_bundle(args.artifact)
            with archive:
                contract_raw = _read_member(
                    archive, _entry(manifest, "contract"), "contract"
                )
                contract = parse_contract_document(
                    _object(contract_raw, "contract.json")
                )
            data: JsonObject = {
                "artifact_type": "reproduction_bundle",
                "contract_digest": contract_digest(contract),
                "manifest": manifest,
            }
        else:
            document, _ = load_document(args.artifact)
            result = parse_result_document(document)
            data = {
                "artifact_type": "eval_result",
                "result": result.to_json(),
                "result_digest": result_digest(result),
            }
    except EvalContractError as exc:
        return _fail("eval_result_invalid", str(exc))
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        return _fail("eval_artifact_invalid", str(exc))
    emit_json("logion.eval.inspect", data)
    return 0
