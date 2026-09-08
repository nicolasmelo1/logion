# SPDX-License-Identifier: MIT
"""End-to-end tests for the public portable eval workflow."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from cli._parser import build_parser
from cli.commands.eval import handlers


def _run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def _creator_project(tmp_path: Path, capsys) -> tuple[Path, Path, Path, dict]:
    project = tmp_path / "creator"
    assert _run(["eval", "scaffold", str(project)]) == 0
    scaffold = _payload(capsys)
    contract = project / "eval-contract.yaml"
    subject = project / "subject.json"
    assert scaffold["kind"] == "logion.eval.scaffold"
    assert _run(["eval", "validate", str(contract)]) == 0
    validated = _payload(capsys)
    assert validated["data"]["valid"] is True
    return contract, subject, project, validated


def _run_results(contract: Path, subject: Path, project: Path, capsys):
    results = []
    for index in (1, 2):
        result = project / f"result-{index}.json"
        assert (
            _run([
                "eval",
                "run",
                str(contract),
                "--subject",
                str(subject),
                "--output",
                str(result),
            ])
            == 0
        )
        run = _payload(capsys)
        assert run["kind"] == "logion.eval.run"
        assert run["data"]["executed"] is True
        results.append(result)
    assert results[0].read_bytes() == results[1].read_bytes()
    return results


def _export_bundle(
    contract: Path, subject: Path, results, bundle: Path, capsys
):
    assert (
        _run([
            "eval",
            "export",
            str(contract),
            "--subject",
            str(subject),
            "--result",
            str(results[0]),
            "--result",
            str(results[1]),
            "--output",
            str(bundle),
        ])
        == 0
    )
    exported = _payload(capsys)
    assert exported["data"]["result_count"] == 2


def test_public_eval_creator_and_clean_consumer_flow(
    tmp_path: Path, capsys
) -> None:
    contract, subject, project, validated = _creator_project(tmp_path, capsys)
    results = _run_results(contract, subject, project, capsys)
    bundle = tmp_path / "reproduction.zip"
    _export_bundle(contract, subject, results, bundle, capsys)

    assert _run(["eval", "verify", str(bundle)]) == 0
    verified = _payload(capsys)
    assert verified["data"]["reproduced"] is True
    assert verified["data"]["runs"] == 2

    assert _run(["eval", "inspect", str(bundle)]) == 0
    inspected = _payload(capsys)
    assert inspected["data"]["artifact_type"] == "reproduction_bundle"
    assert (
        inspected["data"]["contract_digest"]
        == validated["data"]["contract_digest"]
    )

    assert _run(["eval", "inspect", str(results[0])]) == 0
    assert _payload(capsys)["data"]["artifact_type"] == "eval_result"


def test_export_requires_two_run_results(tmp_path: Path, capsys) -> None:
    project = tmp_path / "creator"
    assert _run(["eval", "scaffold", str(project)]) == 0
    _payload(capsys)
    contract = project / "eval-contract.yaml"
    subject = project / "subject.json"
    result = project / "result.json"
    assert (
        _run([
            "eval",
            "run",
            str(contract),
            "--subject",
            str(subject),
            "--output",
            str(result),
        ])
        == 0
    )
    _payload(capsys)

    assert (
        _run([
            "eval",
            "export",
            str(contract),
            "--subject",
            str(subject),
            "--result",
            str(result),
            "--output",
            str(tmp_path / "bundle.zip"),
        ])
        == 2
    )
    error = json.loads(capsys.readouterr().err)
    assert error["kind"] == "logion.error"
    assert error["data"]["code"] == "eval_bundle_invalid"


def test_eval_run_publish_uses_user_and_runner_sdk_clients(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "creator"
    assert _run(["eval", "scaffold", str(project)]) == 0
    scaffold = _payload(capsys)
    credentials = tmp_path / "runner.json"
    credentials.write_text(
        json.dumps({"runner_id": "runner-1", "runner_key": "runner-key"})
    )

    class Evals:
        def __init__(self, runner: bool = False) -> None:
            self.runner = runner

        def upload_contract(self, document):
            assert not self.runner
            assert document
            return {
                "contract_digest": scaffold["data"]["contract_digest"],
                "standing": "unreviewed",
            }

        def validate_job(self, contract_ref, subject_digest, fixture_digests):
            assert not self.runner
            assert contract_ref == scaffold["data"]["contract_digest"]
            assert subject_digest
            assert set(fixture_digests) == {"subject.json"}
            return {"valid": True}

        def submit_result(self, result):
            assert self.runner
            assert "contract_standing" not in result
            return {"run_id": "run-1"}

    class Client:
        def __init__(self, runner: bool = False) -> None:
            self.v1 = type("V1", (), {"evals": Evals(runner)})()

        def close(self) -> None:
            pass

    clients = iter((Client(), Client(runner=True)))
    monkeypatch.setattr(handlers, "make_client", lambda _config: next(clients))
    result = project / "result.json"

    assert (
        _run([
            "eval",
            "run",
            str(project / "eval-contract.yaml"),
            "--subject",
            str(project / "subject.json"),
            "--output",
            str(result),
            "--publish",
            "--runner-credentials",
            str(credentials),
            "--base-url",
            "http://example.test",
        ])
        == 0
    )
    payload = _payload(capsys)
    assert payload["data"]["published"] == {
        "contract_digest": scaffold["data"]["contract_digest"],
        "run_id": "run-1",
        "runner_id": "runner-1",
        "standing": "unreviewed",
        "terminal_status": "succeeded",
    }


def test_verify_rejects_tampered_bundle(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps({"schema_version": 1, "media_type": "wrong"}),
        )
    assert _run(["eval", "verify", str(bad)]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["data"]["code"] == "eval_bundle_invalid"


def test_eval_help_exposes_complete_workflow(capsys) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as caught:
        parser.parse_args(["eval", "--help"])
    assert caught.value.code == 0
    output = capsys.readouterr().out
    for command in (
        "scaffold",
        "validate",
        "run",
        "export",
        "verify",
        "inspect",
    ):
        assert command in output


def test_validate_without_installed_distribution_metadata(
    tmp_path, capsys, monkeypatch
):
    from importlib.metadata import PackageNotFoundError

    from cli.commands.eval import _execution

    def unavailable(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(_execution, "version", unavailable)
    project = tmp_path / "creator"
    assert _run(["eval", "scaffold", str(project)]) == 0
    _payload(capsys)
    assert _run(["eval", "validate", str(project / "eval-contract.yaml")]) == 0
    assert _payload(capsys)["data"]["validator_package_version"] == (
        _execution.eval_contract_package.__version__
    )
